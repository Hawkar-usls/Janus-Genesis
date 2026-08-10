#!/usr/bin/env python3
"""FractalGPT-inspired search planner for Janus Cristal.

Fractal trajectory chooses WHERE to inspect. Conventional measurements decide
WHAT is present. No post-hoc cipher or semantic decoding is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import cv2
import numpy as np

UA = "Janus-Genesis-FractalGPT-Crystal/0.1"
TOKEN_RE = re.compile(r"[A-Z0-9][A-Z0-9_+\-*/=^<>()[\]{}.:]{2,23}")
FORMULA_RE = re.compile(r"(?=.*\d)(?=.*[=+\-*/^])[A-Z0-9_+\-*/=^<>()[\]{}.:]{3,24}")
CODE_HINTS = ("IF", "FOR", "WHILE", "DEF", "INT", "HEX", "0X", "==", "->", "::", "{}", "[]")


def sha256_bytes(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)


def normalize_token(text: str) -> str:
    text = text.upper().replace(" ", "").replace("|", "I")
    allowed = "_+-*/=^<>()[].{}:"
    return "".join(c for c in text if c.isalnum() or c in allowed)[:24]


def classify_token(token: str) -> str:
    if FORMULA_RE.fullmatch(token):
        return "FORMULA_LIKE"
    if any(h in token for h in CODE_HINTS) or sum(c in "_{}[]():<>" for c in token) >= 2:
        return "CODE_LIKE"
    if token.isalpha():
        return "WORD_LIKE"
    return "SYMBOL_SEQUENCE"


def fractal_trajectory(seed: str, count: int, scales: list[float]) -> list[dict]:
    """Content-independent multiscale path from a SHA-256-seeded coupled map."""
    b = sha256_bytes(seed)
    x = (int.from_bytes(b[0:8], "big") + 1) / (2**64 + 2)
    y = (int.from_bytes(b[8:16], "big") + 1) / (2**64 + 2)
    r1 = 3.82 + (b[16] / 255.0) * 0.16
    r2 = 3.82 + (b[17] / 255.0) * 0.16
    eps = 0.015 + (b[18] / 255.0) * 0.02

    def step(xv: float, yv: float) -> tuple[float, float]:
        nx = r1 * xv * (1.0 - xv) + eps * (yv - xv)
        ny = r2 * yv * (1.0 - yv) + eps * (xv - yv)
        return min(0.999999, max(0.000001, nx)), min(0.999999, max(0.000001, ny))

    for _ in range(64):
        x, y = step(x, y)

    out = []
    for i in range(count):
        x, y = step(x, y)
        selector = int((x * 997 + y * 991 + i * 17) * 1_000_003) % len(scales)
        out.append({
            "index": i,
            "cx": round(x, 8),
            "cy": round(y, 8),
            "scale": float(scales[selector]),
        })
    return out


def crop_window(image: np.ndarray, window: dict) -> np.ndarray:
    h, w = image.shape[:2]
    side = max(32, int(round(min(h, w) * float(window["scale"]))))
    cx = int(round(float(window["cx"]) * (w - 1)))
    cy = int(round(float(window["cy"]) * (h - 1)))
    x0 = max(0, min(w - side, cx - side // 2))
    y0 = max(0, min(h - side, cy - side // 2))
    return image[y0:y0 + side, x0:x0 + side]


def block_shuffle(image: np.ndarray, seed: str, block: int = 48) -> np.ndarray:
    """Preserve local texture tiles while disrupting global arrangement."""
    h, w = image.shape[:2]
    ph = int(math.ceil(h / block) * block)
    pw = int(math.ceil(w / block) * block)
    padded = cv2.copyMakeBorder(image, 0, ph - h, 0, pw - w, cv2.BORDER_REFLECT)
    tiles = [
        padded[y:y + block, x:x + block].copy()
        for y in range(0, ph, block)
        for x in range(0, pw, block)
    ]
    raw = sha256_bytes(seed)
    rng = np.random.default_rng(int.from_bytes(raw[:8], "big"))
    rng.shuffle(tiles)
    out = np.empty_like(padded)
    k = 0
    for y in range(0, ph, block):
        for x in range(0, pw, block):
            out[y:y + block, x:x + block] = tiles[k]
            k += 1
    return out[:h, :w]


def resize_max(image: np.ndarray, max_dim: int = 1400) -> np.ndarray:
    h, w = image.shape[:2]
    s = min(1.0, max_dim / max(h, w))
    if s == 1.0:
        return image
    return cv2.resize(image, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)


def ocr_crop(crop: np.ndarray, min_conf: float) -> list[dict]:
    if shutil.which("tesseract") is None:
        raise RuntimeError("tesseract binary not found")
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(6, 6)).apply(gray)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        p = Path(f.name)
    try:
        cv2.imwrite(str(p), gray)
        cmd = [
            "tesseract", str(p), "stdout", "--psm", "11", "-l", "eng", "tsv",
            "-c", "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_+-*/=^<>()[].{}:"
        ]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=20)
        if r.returncode != 0:
            return []
        rows = r.stdout.splitlines()[1:]
        out = []
        for row in rows:
            c = row.split("\t")
            if len(c) < 12:
                continue
            try:
                conf = float(c[10])
            except ValueError:
                continue
            token = normalize_token(c[11])
            if conf < min_conf or not TOKEN_RE.fullmatch(token):
                continue
            out.append({"token": token, "class": classify_token(token), "confidence": round(conf, 2)})
        return out
    finally:
        p.unlink(missing_ok=True)


def structure_metrics(crop: np.ndarray) -> dict:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if min(gray.shape) > 320:
        s = 320 / min(gray.shape)
        gray = cv2.resize(gray, (max(1, round(gray.shape[1] * s)), max(1, round(gray.shape[0] * s))))
    edges = cv2.Canny(gray, 70, 150)
    edge_density = float((edges > 0).mean())
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180.0, threshold=35, minLineLength=max(12, min(gray.shape) // 8), maxLineGap=6)
    line_count = 0 if lines is None else len(lines)
    left = gray[:, : gray.shape[1] // 2]
    right = gray[:, gray.shape[1] - left.shape[1] :]
    right = np.fliplr(right)
    symmetry = 0.0
    if left.size and left.std() > 0 and right.std() > 0:
        symmetry = float(np.corrcoef(left.ravel(), right.ravel())[0, 1])
    return {
        "edge_density": round(edge_density, 6),
        "line_count": int(line_count),
        "mirror_symmetry": round(symmetry, 6),
    }


def analyze_image(image: np.ndarray, trajectory: list[dict], min_conf: float, control_seed: str) -> dict:
    image = resize_max(image)
    control = block_shuffle(image, control_seed)
    result = {"real": [], "control": []}
    token_counts = {"real": Counter(), "control": Counter()}
    token_best_conf = {"real": defaultdict(float), "control": defaultdict(float)}

    for label, source in (("real", image), ("control", control)):
        for window in trajectory:
            crop = crop_window(source, window)
            metrics = structure_metrics(crop)
            tokens = ocr_crop(crop, min_conf)
            for t in tokens:
                token_counts[label][t["token"]] += 1
                token_best_conf[label][t["token"]] = max(token_best_conf[label][t["token"]], t["confidence"])
            result[label].append({"window": window, "metrics": metrics, "tokens": tokens})

    real_counts = token_counts["real"]
    ctrl_counts = token_counts["control"]
    escalated = []
    for token, count in real_counts.items():
        if len(token) < 3 or count < 2 or ctrl_counts[token] > 0:
            continue
        cls = classify_token(token)
        if cls not in {"WORD_LIKE", "FORMULA_LIKE", "CODE_LIKE"}:
            continue
        escalated.append({
            "token": token,
            "class": cls,
            "real_window_hits": count,
            "control_window_hits": 0,
            "best_confidence": round(token_best_conf["real"][token], 2),
            "status": "SINGLE_SOURCE_ESCALATION_ONLY_NOT_MESSAGE",
        })
    escalated.sort(key=lambda x: (-x["real_window_hits"], -x["best_confidence"], x["token"]))

    def summarize_metrics(rows: list[dict]) -> dict:
        return {
            key: round(float(median([r["metrics"][key] for r in rows])), 6)
            for key in ("edge_density", "line_count", "mirror_symmetry")
        }

    real_summary = summarize_metrics(result["real"])
    ctrl_summary = summarize_metrics(result["control"])
    metric_ratios = {}
    for key in real_summary:
        c = float(ctrl_summary[key])
        metric_ratios[key] = None if abs(c) < 1e-12 else round(float(real_summary[key]) / c, 6)

    return {
        "window_count": len(trajectory),
        "real_token_counts": dict(real_counts),
        "control_token_counts": dict(ctrl_counts),
        "single_source_escalation_candidates": escalated,
        "single_source_escalation_count": len(escalated),
        "median_structure_real": real_summary,
        "median_structure_control": ctrl_summary,
        "real_to_control_metric_ratio": metric_ratios,
        "window_receipts": result,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-ocr-confidence", type=float, default=55.0)
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    cfg = manifest["trajectory"]
    trajectory = fractal_trajectory(cfg["seed"], int(cfg["window_count"]), [float(x) for x in cfg["scale_ladder"]])
    report = {
        "schema": "genesis.janus_cristal_fractalgpt.result.v1",
        "trajectory": {
            **cfg,
            "sha256": hashlib.sha256(json.dumps(trajectory, sort_keys=True).encode()).hexdigest(),
            "windows": trajectory,
            "content_independent": True,
        },
        "sources": [],
        "cross_modality_escalation_candidates": [],
        "semantic_admission": "NO_MESSAGE_FORMULA_CODE_OR_ALGORITHM_ADMITTED",
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_source_candidates = defaultdict(set)

    errors = 0
    with tempfile.TemporaryDirectory(prefix="genesis-fractal-crystal-") as td:
        td = Path(td)
        for i, source in enumerate(manifest["sources"]):
            entry = {k: v for k, v in source.items() if k != "download_url"}
            try:
                path = td / f"source_{i}.img"
                fetch(source["download_url"], path)
                image = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if image is None:
                    raise RuntimeError("image decode failed")
                entry["sha256"] = sha256_file(path)
                entry["dimensions"] = [int(image.shape[1]), int(image.shape[0])]
                entry["analysis"] = analyze_image(
                    image,
                    trajectory,
                    args.min_ocr_confidence,
                    control_seed=f"{cfg['seed']}::{source['id']}::shuffle",
                )
                for c in entry["analysis"]["single_source_escalation_candidates"]:
                    per_source_candidates[c["token"]].add(source["id"])
                entry["status"] = "ANALYZED"
            except Exception as exc:
                errors += 1
                entry["status"] = "ERROR"
                entry["error"] = f"{type(exc).__name__}: {exc}"
            report["sources"].append(entry)

    source_by_id = {s["id"]: s for s in report["sources"]}
    cross = []
    for token, ids in sorted(per_source_candidates.items()):
        modalities = sorted({source_by_id[i].get("modality") for i in ids})
        if len(modalities) >= 2:
            cross.append({
                "token": token,
                "source_ids": sorted(ids),
                "modalities": modalities,
                "status": "CROSS_MODALITY_ESCALATION_ONLY_REPLICATION_REQUIRED",
            })
    report["cross_modality_escalation_candidates"] = cross
    report["cross_modality_escalation_count"] = len(cross)
    report["claim_ceiling"] = (
        "Fractal path selection plus OCR/structure metrics can identify reproducible detector candidates. "
        "It cannot establish intentional encoding, a message, formula, code, algorithm, intelligence, or supernatural cause."
    )

    result_path = out_dir / "GENESIS-JANUS-CRISTAL-FRACTALGPT-result.json"
    result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Janus Cristal × FractalGPT CI receipt",
        "",
        f"Sources: {len(report['sources']) - errors}/{len(report['sources'])} analyzed; errors={errors}",
        f"Trajectory windows: {len(trajectory)}",
        f"Trajectory SHA-256: `{report['trajectory']['sha256']}`",
        "",
        "| source | modality | single-source escalations |",
        "|---|---|---:|",
    ]
    for s in report["sources"]:
        n = s.get("analysis", {}).get("single_source_escalation_count", "error")
        lines.append(f"| {s['id']} | {s.get('modality')} | {n} |")
    lines += [
        "",
        f"Cross-modality escalation candidates: **{len(cross)}**",
        "",
        "`NO_MESSAGE_FORMULA_CODE_OR_ALGORITHM_ADMITTED`",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
