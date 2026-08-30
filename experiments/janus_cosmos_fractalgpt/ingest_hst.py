"""Fail-closed public Hubble image ingestion for Janus Cosmos.

The original pilot treated MAST zCut as a generic HST cutout endpoint. zCut is
survey-oriented and can legitimately return a non-ZIP response when no
supported survey image exists at a target.  This implementation uses the
Hubble Legacy Archive (HLA) SIA service to discover Hubble images that cover an
exact sky position, then retrieves small true-pixel FITS cutouts through the
HLA fitscut service.

Requires numpy and astropy only.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import urllib.parse
import urllib.request

import numpy as np
from astropy.io import fits
from astropy.io.votable import parse_single_table


USER_AGENT = "Janus-Cosmos/0.2"
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

    # HLA documents the SIA access reference as the URL field.  Keep a small
    # compatibility fallback for case/legacy naming without guessing content.
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
        text = _text(value)
        if text.startswith(("https://", "http://")):
            urls.append(text)
    urls = sorted(set(urls))
    if not urls:
        raise RuntimeError(f"No public FITS access URL returned for {item['object_id']}")
    return query_url, urls[:MAX_PRODUCTS_PER_TARGET]


def normalize_cutout_url(access_url: str, item) -> str:
    """Keep HLA/MAST data provenance but force small FITS cutouts when possible."""
    parsed = urllib.parse.urlparse(access_url)
    params = urllib.parse.parse_qs(parsed.query)

    # HLA SIA commonly returns fitscut access references. Rebuild those with a
    # fixed target-centered cutout and FITS output so CI never downloads a full
    # archival mosaic merely to obtain the 64x64 analysis grid.
    if parsed.netloc.casefold() == "hla.stsci.edu" and parsed.path.endswith("/fitscut.cgi"):
        flat = {key: values[-1] for key, values in params.items() if values}
        flat.update(
            {
                "RA": item["ra"],
                "Dec": item["dec"],
                "size": item.get("size_px", 96),
                "format": "fits",
                "TextErrors": "yes",
            }
        )
        return urllib.parse.urlunparse(
            parsed._replace(query=urllib.parse.urlencode(flat))
        )

    # If HLA returned a dataset identifier through a standard data URL rather
    # than fitscut, do not synthesize a dataset name. Fetch the authoritative
    # URL as returned and let the FITS parser validate it fail-closed.
    return access_url


def read_fits_image(blob: bytes, object_id: str, source_url: str):
    try:
        with fits.open(io.BytesIO(blob), memmap=False) as hdul:
            arr = next(
                (
                    np.asarray(hdu.data)
                    for hdu in hdul
                    if getattr(hdu, "data", None) is not None
                    and np.asarray(hdu.data).ndim == 2
                ),
                None,
            )
    except Exception as exc:
        prefix = blob[:120].decode("utf-8", "replace")
        raise RuntimeError(
            f"Non-FITS HLA payload for {object_id} from {source_url}: {prefix!r}"
        ) from exc
    if arr is None:
        raise RuntimeError(f"No 2-D science image in HLA FITS payload for {object_id}")
    return arr


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
            arr = resize(read_fits_image(blob, item["object_id"], data_url), 64)
            if arr is None:
                continue
            accepted += 1
            provenance.append(
                {
                    "object_id": item["object_id"],
                    "sia_query": sia_url,
                    "access_url": access_url,
                    "data_url": data_url,
                    "bytes": len(blob),
                }
            )
            for iy, y in enumerate(np.linspace(-1, 1, 64)):
                for ix, x in enumerate(np.linspace(-1, 1, 64)):
                    rows.append(
                        {
                            "object_id": item["object_id"],
                            "band": access_url,
                            "x": float(x),
                            "y": float(y),
                            "signal": float(arr[iy, ix]),
                            "source_url": sia_url,
                            "source_file": data_url,
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
                "products": provenance,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python ingest_hst.py manifest.json output.csv")
    main(sys.argv[1], sys.argv[2])
