#!/usr/bin/env python3
"""
bldg_buried.py — **경사면에서 건물이 지형에 묻히는 정도를 건물마다 잰다.**  (PLAN #239 · DECISIONS §796)

    uv run python tools/bldg_buried.py                 분포 표 + 후보(A · B) 발행 비용(바이트)
    uv run python tools/bldg_buried.py --center rep    중심점 규칙을 바꿔 본다(centroid · rep · bbox)
    uv run python tools/bldg_buried.py --csv OUT       건물별 값(경위도 무게중심 · 중심 · 최저 · 최고 · 묻힘 · 높이)을 파일로

── 왜 있나 ────────────────────────────────────────────────────
MapLibre 는 지형 위에서 건물을 **발자국 중심 한 점의 지형 표고**에 올린다. 경사면에서는 발자국 한쪽이 그 높이보다 높아 **묻히고**(오르막 쪽) 다른 쪽은 **뜬다**(내리막 쪽).
지형을 z16 으로 세밀하게 구운 뒤 묻힘이 더 드러났다(사람이 배포본에서 봤다 · 2026-11-15). 맞는 고침은 건물마다 올림값을 발행물에 싣는 것이고 그 값과 바이트가 이 도구가 내는 것이다.

── 무엇을 재나 ────────────────────────────────────────────────
건물마다 발자국 아래 지형(구운 z16 타일 · 쌍선형)의 **중심 · 최저 · 최고** 고도. 묻힘 = 최고 − 중심(오르막 쪽 벽이 지형 아래로 들어가는 깊이) · 뜸 = 중심 − 최저(내리막 쪽 벽 아래가 비는 깊이).
**통째로 묻힘** = 높이 `h` 가 묻힘 이하(지붕이 오르막 지반 아래다). 후보 둘의 **발행 비용**: 건물 파일 `buildings.geojson` 에 칸 하나(올림값 · 소수 1자리)를 모든 건물에 더했을 때 늘어나는 바이트(원본 · gzip 6).
  A  `base = 최고 − 중심`(+ 높이 `h + base`)   안 묻힌다 — 내리막 쪽 아래가 뜬 채다
  B  `base = 최저 − 중심`(**음수**) · 높이 `h + 묻힘`(지붕 = 최고 지반 + h · 두께 = h + 최고 − 최저)   아래까지 메운다(옹벽 · 기초) — 음수 `base` 를 MapLibre 가 받는지는 이 도구가 안 본다(헤드리스 실측 — DECISIONS §796)

IN    `web/data/buildings.geojson`(발행물) · `web/data/terrain/16/{x}/{y}.png`(구운 지형 · mapbox Terrain-RGB 0.1m)
OUT   화면 표 · (`--csv`) 건물별 파일. 저장소 파일을 안 쓴다 · 판정을 안 읽는다
PARAM `ZOOM` 16 · `BURY` 1.0 · 3.0(m) · `SPARSE_M` 0.5 · `CENTERS` centroid · rep · bbox
밖    **MapLibre 가 실제로 어느 점을 중심으로 쓰는지는 안 본다**(세 규칙을 맞대어 어제의 215 · 23 · 6 에 맞는 것을 가릴 뿐이다) · 지형 위 그림이 어떻게 보이는지는 안 본다(헤드리스 실측)
      · 건물의 발행 번호 칸은 안 읽는다(§320 — 재발행하면 달라진다) · 높이 `h` 만 읽는다
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import shape

from firelane.bldg_ground import SPARSE_M, TILE, ZOOM, Dem, load_dem, stats  # noqa: F401 — `TILE` · `Dem` 은 시험이 이 이름으로 읽는다

ROOT = Path(__file__).resolve().parent.parent
BUILDINGS = ROOT / "web" / "data" / "buildings.geojson"
BURY = (1.0, 3.0)
CENTERS = ("centroid", "rep", "bbox")
TERRAIN = ROOT / "web" / "data" / "terrain"


def table(rows: list[dict]) -> list[str]:
    ok = [r for r in rows if r["ok"]]
    bury = np.array([max(r["hi"] - r["center"], 0.0) for r in ok])
    float_ = np.array([max(r["center"] - r["lo"], 0.0) for r in ok])
    rng = np.array([r["hi"] - r["lo"] for r in ok])
    h = np.array([r["h"] for r in ok])
    whole = bury >= h
    out = [f"건물 {len(rows)}동 중 지형을 잰 것 {len(ok)}동(타일 밖 {len(rows) - len(ok)})",
           f"  묻힘(최고 − 중심) : 1m 초과 {int((bury > BURY[0]).sum())} · 3m 초과 {int((bury > BURY[1]).sum())} · **통째(높이 이하) {int(whole.sum())}**",
           f"  뜸(중심 − 최저)   : 1m 초과 {int((float_ > BURY[0]).sum())} · 3m 초과 {int((float_ > BURY[1]).sum())}",
           f"  최고 − 최저       : 중앙 {np.median(rng):.2f}m · p90 {np.quantile(rng, .9):.2f}m · 최대 {rng.max():.2f}m · 3m 초과 {int((rng > 3).sum())}",
           f"  묻힘 분포(m)      : 중앙 {np.median(bury):.2f} · p90 {np.quantile(bury, .9):.2f} · 최대 {bury.max():.2f}"]
    return out


def costs(feats: list[dict], rows: list[dict]) -> list[str]:
    """후보 A · B 를 건물 파일에 실었을 때의 바이트 — 전부에 싣는 꼴과 **해당 건물에만**(희소 · 묻힘/뜸이 `SPARSE_M` 이상) 싣는 꼴."""
    base_raw = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":")).encode()
    base_gz = len(gzip.compress(base_raw, 6))
    out = []
    for name, kind, sparse in (("A  base = 최고 − 중심            · 전부", "A", False), ("A  base = 최고 − 중심            · 희소", "A", True),
                               ("B  base = 최저 − 중심(음수)      · 전부", "B", False), ("B  base = 최저 − 중심(음수)      · 희소", "B", True)):
        add, n_set = [], 0
        for ft, r in zip(feats, rows, strict=True):
            props = dict(ft["properties"])
            if r["ok"]:
                up, down = max(r["hi"] - r["center"], 0.0), max(r["center"] - r["lo"], 0.0)
                hit = (up >= SPARSE_M) if kind == "A" else (up >= SPARSE_M or down >= SPARSE_M)
                if hit or not sparse:
                    zb = round(up, 1) if kind == "A" else round(-down, 1)
                    props["zb"] = zb
                    props["h"] = round(float(props.get("h") or 0) + up, 1)   # `fill-extrusion-height` 는 중심 지반에서 **지붕까지**다 — 지붕은 최고 지반 + h
                    n_set += 1
            add.append({**ft, "properties": props})
        raw = json.dumps({"type": "FeatureCollection", "features": add}, ensure_ascii=False, separators=(",", ":")).encode()
        out.append((name, n_set, len(raw) - len(base_raw), len(gzip.compress(raw, 6)) - base_gz))
    return [f"후보 비용(건물 파일 `buildings.geojson` · 칸 `zb` + 높이 갱신 · 같은 직렬화로 맞댄 증가분 · 원본 {len(base_raw):,}B · gzip {base_gz:,}B · 희소 = 묻힘/뜸 ≥ {SPARSE_M}m 인 건물만)",
            "  후보                                     건물    원본 +B    gzip +B"] + [f"  {n:<36} {k:>6} {a:>10,} {b:>10,}" for n, k, a, b in out]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--center", choices=CENTERS, default="centroid")
    ap.add_argument("--csv", type=Path)
    a = ap.parse_args(argv)
    gj = json.loads(BUILDINGS.read_text(encoding="utf-8"))
    feats = gj["features"]
    dem = load_dem(TERRAIN)
    rows = []
    for f in feats:
        g = shape(f["geometry"])
        r = stats(dem, g, a.center)
        r["h"] = float(f["properties"].get("h") or 0)
        c = g.centroid
        r["lon"], r["lat"] = c.x, c.y
        rows.append(r)
    print("\n".join(table(rows) + [""] + costs(feats, rows)))
    if a.csv:
        with a.csv.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["lon", "lat", "ok", "center", "lo", "hi", "h"])
            w.writeheader()
            w.writerows({k: r.get(k) for k in w.fieldnames} for r in rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
