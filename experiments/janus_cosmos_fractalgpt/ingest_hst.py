"""Fail-closed public Hubble image ingestion for Janus Cosmos.

The original pilot treated MAST zCut as a generic HST cutout endpoint. zCut is
survey-oriented and can legitimately return a non-ZIP response when no
supported survey image exists at a target. This implementation uses the Hubble
Legacy Archive (HLA) SIA service to discover Hubble images that cover an exact
sky position, then retrieves small true-pixel FITS cutouts through the HLA
fitscut service.

Requires numpy and astropy only.
"""
from __future__ import annotations

import csv
import html
import io
import json
import sys
import urllib.parse
import urllib.request

import numpy as np
from astropy.io import fits
from astropy.io.votable import parse_single_table


USER_AGENT = "Janus-Cosmos/0.2.3"
HLA_SIA = "https://hla.stsci.edu/cgi-bin/hlaSIAP.cgi"
HLA_FITSCUT = "https://hla.stsci.edu/cgi-bin/fitscut.cgi"
MAX_PRODUCTS_PER_TARGET = 3


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def resize(a, n: int = 64):
    a = np.asarray(a, dtype=float)
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    if a.ndim > 2:
        a = np.squeeze(a)
    if a.ndim != 2:
        return None
    yy = np.linspace(0, a.shape[0] - 1, n).astype(int)
    xx = np.linspace(0, a.shape[1] - 1, n).astype(int)
    b = a[np.ix_(yy, xx)]
    b -= np.median(b)
    scale = np.std(b)
    return b / (scale if scale > 0 else 1.0)


def _text(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").strip()
    return str(value).strip()


def discover_hla_images(item):
    # SIZE=0 is an HLA-specific exact-footprint query: return only images whose
    # actual footprint covers the requested RA/Dec point.
    query = urllib.parse.urlencode(
        {
            "POS": f"{item['ra']},{item['dec']}",
            "SIZE": 0,
            "format": "image/fits",
        }
    )
    query_url = f"{HLA_SIA}?{query}"
    payload = fetch(query_url)
    try:
        table = parse_single_table(io.BytesIO(payload)).to_table(use_names_over_ids=True)
    except Exception as exc:
        prefix = payload[:160].decode("utf-8", "replace")
        raise RuntimeError(
            f"HLA SIA did not return a readable VOTable for {item['object_id']}: {prefix!r}"
        ) from exc

    if len(table) == 0:
        raise RuntimeError(f"No HLA image covers target {item['object_id']}")

    by_casefold = {name.casefold(): name for name in table.colnames}
    url_column = by_casefold.get("url")
    if url_column is None:
        candidates = [
            name
            for name in table.colnames
            if "url" in name.casefold() or "access" in name.casefold()
        ]
        if len(candidates) == 1:
            url_column = candidates[0]
    if url_column is None:
        raise RuntimeError(
            f"HLA SIA result for {item['object_id']} has no unique access URL column; "
            f"columns={table.colnames!r}"
        )

    urls = []
    for value in table[url_column]:
        # VOTable text may expose query separators as XML entities. Normalize
        # them before URL parsing; otherwise keys like "amp;green" silently
        # change the requested product.
        text = html.unescape(_text(value))
        if text.startswith(("https://", "http://")):
            urls.append(text)
    urls = sorted(set(urls))
    if not urls:
        raise RuntimeError(f"No public FITS access URL returned for {item['object_id']}")
    return query_url, urls[:MAX_PRODUCTS_PER_TARGET]


def _fitscut_url(params: dict[str, object], item) -> str:
    flat = {key: value for key, value in params.items() if value not in (None, "")}
    flat.update(
        {
            "RA": item["ra"],
            "Dec": item["dec"],
            "size": item.get("size_px", 96),
            "format": "fits",
            "TextErrors": "yes",
            "config": flat.get("config", "ops"),
        }
    )
    return f"{HLA_FITSCUT}?{urllib.parse.urlencode(flat)}"


def normalize_cutout_url(access_url: str, item) -> str:
    """Preserve HLA provenance while forcing bounded target-centred FITS data."""
    access_url = html.unescape(access_url)
    parsed = urllib.parse.urlparse(access_url)
    params = urllib.parse.parse_qs(parsed.query)
    flat = {key: values[-1] for key, values in params.items() if values}

    if parsed.netloc.casefold() == "hla.stsci.edu" and parsed.path.endswith("/fitscut.cgi"):
        return _fitscut_url(flat, item)

    # SIA can also return full-product getdata URLs. Convert the exact returned
    # dataset id to fitscut instead of downloading hundreds of MB merely to
    # derive a 64x64 analysis grid.
    if parsed.netloc.casefold() == "hla.stsci.edu" and parsed.path.endswith("/getdata.cgi"):
        dataset = flat.get("dataset")
        if not dataset:
            raise RuntimeError(
                f"HLA getdata access URL has no dataset id for {item['object_id']}: {access_url}"
            )
        return _fitscut_url({"red": dataset, "config": flat.get("config", "ops")}, item)

    # Unknown access forms remain authoritative as returned and must validate
    # as FITS below; no guessed dataset identity is permitted.
    return access_url


def read_fits_planes(blob: bytes, object_id: str, source_url: str):
    """Return every genuine 2-D science plane without silently discarding bands."""
    try:
        with fits.open(io.BytesIO(blob), memmap=False) as hdul:
            planes = []
            raw_shapes = []
            for hdu_index, hdu in enumerate(hdul):
                data = getattr(hdu, "data", None)
                if data is None:
                    continue
                candidate = np.asarray(data)
                raw_shapes.append(tuple(candidate.shape))
                normalized = np.squeeze(candidate)
                if normalized.ndim == 2:
                    planes.append((f"hdu{hdu_index}:plane0", normalized))
                    continue
                # HLA colour/composite fitscut products can legitimately be
                # channel-first cubes such as 3x96x96. Preserve every 2-D
                # channel as an independent, provenance-bound band instead of
                # selecting one after observing the data.
                if normalized.ndim == 3 and normalized.shape[-2] > 1 and normalized.shape[-1] > 1:
                    for plane_index in range(normalized.shape[0]):
                        plane = np.asarray(normalized[plane_index])
                        if plane.ndim == 2:
                            planes.append((f"hdu{hdu_index}:plane{plane_index}", plane))
    except Exception as exc:
        prefix = blob[:120].decode("utf-8", "replace")
        raise RuntimeError(
            f"Non-FITS HLA payload for {object_id} from {source_url}: {prefix!r}"
        ) from exc
    if not planes:
        raise RuntimeError(
            f"No 2-D science plane in HLA FITS payload for {object_id}; "
            f"HDU data shapes={raw_shapes!r}"
        )
    return planes


def main(manifest: str, out: str):
    with open(manifest, encoding="utf-8") as handle:
        config = json.load(handle)

    rows = []
    provenance = []
    for item in config["targets"]:
        sia_url, access_urls = discover_hla_images(item)
        accepted = 0
        for access_url in access_urls:
            data_url = normalize_cutout_url(access_url, item)
            blob = fetch(data_url)
            planes = read_fits_planes(blob, item["object_id"], data_url)
            accepted_planes = 0
            for plane_label, plane in planes:
                arr = resize(plane, 64)
                if arr is None:
                    continue
                accepted_planes += 1
                band_id = f"{access_url}#{plane_label}"
                for iy, y in enumerate(np.linspace(-1, 1, 64)):
                    for ix, x in enumerate(np.linspace(-1, 1, 64)):
                        rows.append(
                            {
                                "object_id": item["object_id"],
                                "band": band_id,
                                "x": float(x),
                                "y": float(y),
                                "signal": float(arr[iy, ix]),
                                "source_url": sia_url,
                                "source_file": data_url,
                            }
                        )
            if accepted_planes == 0:
                continue
            accepted += 1
            provenance.append(
                {
                    "object_id": item["object_id"],
                    "sia_query": sia_url,
                    "access_url": access_url,
                    "data_url": data_url,
                    "bytes": len(blob),
                    "science_planes": accepted_planes,
                }
            )
        if accepted == 0:
            raise RuntimeError(f"No usable HLA FITS product for {item['object_id']}")

    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "object_id",
                "band",
                "x",
                "y",
                "signal",
                "source_url",
                "source_file",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(
        json.dumps(
            {
                "status": "INGESTED_HLA_SIA",
                "rows": len(rows),
                "objects": sorted({row["object_id"] for row in rows}),
                "bands": len({row["band"] for row in rows}),
                "products": provenance,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python ingest_hst.py manifest.json output.csv")
    main(sys.argv[1], sys.argv[2])
