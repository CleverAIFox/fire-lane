#!/usr/bin/env python3
"""
tools/transition.py — 옛 구간 → 새 구간 **전이표**. R3 전후 비교의 틀이다 (R2 · DECISIONS §187)

    uv run python tools/transition.py <봉인태그>        봉인 ↔ 현재 segments
    uv run python tools/transition.py --self            현재 ↔ 현재 (항등 자기검사)
    uv run python tools/transition.py --to-skeleton     현행 구간 → R1 하이브리드 엣지 (R3 예보)
    uv run python tools/transition.py <태그> --csv      행 표까지 쓴다

★ 판정을 안 바꾼다. `segments` · `web/data` · golden 을 건드리지 않는다. 표를 낸다.
  R3 가 뼈대를 갈면 구간이 다른 자리에서 잘린다 — `baseline.py diff` 의 1:1 중점 매칭으로는
  **판정이 움직인 것과 경계가 움직인 것을 구별할 수 없다**(firelane.transition 머리말).

IN    data/processed/segments.geojson · data/baseline/<태그>/segments.geojson ·
      (--to-skeleton) data/desk/r1/skeleton_5186.gpkg — `tools/skeleton_compare.py` 가 먼저 돈다
OUT   data/desk/r2/transition_<태그>.csv · summary.json (재생성물 · gitignore)
PARAM firelane.transition 의 상수(STEP · MATCH_R · MATCH_ANGLE · MIN_SHARE · FALLBACK_R)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd

from firelane import paths
from firelane import transition as X

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "data" / "desk" / "r2"
SKEL = ROOT / "data" / "desk" / "r1" / "skeleton_5186.gpkg"


def _read(p: Path) -> gpd.GeoDataFrame:
    if not p.exists():
        raise SystemExit(f"★ 없다: {p}")
    return gpd.read_file(p).to_crs(5186)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tag", nargs="?", help="data/baseline 의 봉인 태그")
    ap.add_argument("--self", dest="ident", action="store_true", help="현재 ↔ 현재 항등 자기검사")
    ap.add_argument("--to-skeleton", action="store_true", help="현행 구간 → R1 하이브리드 엣지")
    ap.add_argument("--csv", action="store_true", help="행 표(CSV)까지 쓴다")
    a = ap.parse_args()
    if not (a.tag or a.ident or a.to_skeleton):
        ap.error("봉인 태그 · --self · --to-skeleton 중 하나는 있어야 한다")

    cur = _read(PROC / "segments.geojson")
    if a.to_skeleton:
        new = _read(SKEL)
        # 엣지에는 판정이 없다. 경계가 어떻게 갈리는지(1:N · N:1)만 본다.
        new = new.rename(columns={"edge_id": "seg_uid"})
        new["verdict"] = None
        old, name = cur, "to-skeleton"
    elif a.ident:
        old, new, name = cur, cur, "self"
    else:
        old, new, name = _read(paths.BASELINE / a.tag / "segments.geojson"), cur, a.tag

    print(f"전이표 {name} — 옛 {len(old):,} → 새 {len(new):,}")
    t = X.build(old, new)
    s = X.summarize(t, len(old), len(new))
    card = s["cardinality"]
    print("  대응  " + " · ".join(f"{k} {v}" for k, v in card.items())
          + f"  ·  신설 {s['added']}")
    print(f"  seg_uid 유지 {s['same_uid']}/{s['old']} ({s['same_uid_rate']}%) · 중점 폴백 {s['fallback_mid']}")
    print(f"  길이 옛 {s['len_old_m']:,.0f}m · 대응 {s['len_matched_m']:,.0f}m "
          f"({100*s['len_matched_m']/max(1.0, s['len_old_m']):.1f}%) · 표본 대응률 중앙 {s['cover_median']}")

    if not a.to_skeleton:
        print("\n  판정 전이 — **길이 m 가중**(1:N 을 구간 수로 세면 옛 구간이 여러 번 세어진다)")
        print(X.verdict_flow(t).to_string())

    split = t[(t.match.isin(["방향", "중점"]))].groupby("old_uid").new_uid.nunique()
    worst = split[split > 1].sort_values(ascending=False).head(10)
    if len(worst):
        print(f"\n  가장 잘게 쪼개지는 옛 구간 (상위 {len(worst)})")
        for u, k in worst.items():
            r = t[t.old_uid == u].iloc[0]
            road, vd = r.old_road or "", r.old_verdict or ""
            print(f"    {u}  {road:14s} {vd:9s} {r.old_len_m:6.1f}m → {k} 조각")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"summary_{name}.json").write_text(
        json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    wrote = [f"summary_{name}.json"]
    if a.csv:
        t.to_csv(OUT / f"transition_{name}.csv", index=False, encoding="utf-8-sig")
        wrote.append(f"transition_{name}.csv")
    print(f"\n→ {OUT.relative_to(ROOT)}/" + " · ".join(wrote))

    if a.ident:
        bad = [f"1:1 이 아닌 것 {s['old'] - card.get('1:1', 0)}" if card.get("1:1") != s["old"] else "",
               f"소멸 {s['gone']}" if s["gone"] else "",
               f"신설 {s['added']}" if s["added"] else "",
               f"seg_uid 유지 {s['same_uid_rate']}%" if s["same_uid"] != s["old"] else ""]
        bad = [b for b in bad if b]
        if bad:
            print("\n★ 항등 자기검사 실패 — " + " · ".join(bad))
            print("  같은 산출물끼리인데 1:1 이 아니면 전이표를 R3 전후 비교에 쓸 수 없다")
            return 1
        print("\n항등 자기검사 통과 — 같은 산출물끼리는 전부 1:1 · 소멸 0 · 신설 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
