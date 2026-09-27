#!/usr/bin/env python3
"""
cv_queue.py — **영상판정을 어느 구간부터 붙일 것인가.** 순서만 정한다.

    uv run python tools/cv_queue.py                요약 (층별 수 · 비율)
    uv run python tools/cv_queue.py --out q.csv    순서대로 CSV 로
    uv run python tools/cv_queue.py --selftest     ★ 판정기가 살아 있나

── 왜 생겼나 (PLAN §1 #54 · DECISIONS §273-6) ─────────────────
그 행은 「측량폭을 판정 입력으로 쓸 것인가」였고 교환이 하나였다 —

    넣으면   CV 자원이 측량이 이미 답한 구간에 안 간다
    넣으면   MASTER §2 의 **유일한 독립 검증축이 사라진다**

2026-09-27 에 **판정에는 안 넣고 순서에만 쓰는 쪽**으로 정했다. 그러면 교환이
아니라 둘 다 얻는다 — 측량은 CV 와 독립으로 남고(서로를 검증할 수 있다), CV
자원은 측량이 못 가른 구간으로 간다.

★ 실측이 그 결정을 뒷받침한다(2026-09-27 · 구간 1,281).

      CV 가능한 판정 대상            226
        측량이 이미 답했다           122   54%   ← 뒤로 민다
        임계 인접 (3m ≤ w < 6m)      104   46%   ← 먼저 붙인다

  **자원의 절반이 이미 답이 있는 자리에 가고 있었다.**

★ PLAN 이 적은 「3m 미만 156 · 6m 이상 117」은 **낡은 수다.** 어느 칸에서도 그
  값이 안 나온다 — 그 뒤로 판정이 여러 번 움직였다. 이 도구가 매번 다시 잰다.
  그것이 「지표는 값이 아니라 실행이다」(PLAN §1 #91)의 뜻이다.

── 층 ─────────────────────────────────────────────────────────
    ① 임계 인접   3.0 ≤ 측량폭 < 6.0. **CV 가 답을 바꾸는 유일한 구간**이다.
                  임계가 3.0/7.0(MASTER §2-2)이라 이 띠 안에서는 측량만으로
                  통행 가부를 못 정한다
    ② 폭 없음     측량폭이 아예 없다. 답이 없으니 CV 가 유일한 길이다
    ③ 이미 답함   측량폭 < 3.0 이거나 ≥ 6.0. CV 를 붙여도 판정이 뒤집힐 여지가
                  작다 — **버리지 않고 뒤로 민다.** 측량이 틀렸을 수 있고
                  그것을 가리는 것이 독립 검증축의 존재 이유다

    같은 층 안에서는 **통행량(route_usage)** 이 많은 순. 같으면 긴 순.

IN    data/processed/segments.geojson
OUT   표준출력 · (--out) CSV
PARAM NARROW · WIDE
밖    **판정을 안 바꾼다.** 이 도구의 출력은 어떤 판정 경로도 안 읽는다 —
      읽는 순간 측량이 판정 입력이 되고 독립 검증축이 사라진다.
      `tests/test_cv_queue.py` 가 그 경계를 문다.
      **CV 를 실제로 붙이지도 않는다** — 순서만 낸다. 붙이는 것은 #3 이다.
      그리고 **CCTV 가 없는 구간은 안 센다**(`cv_feasible`) — 순서를 매겨도
      붙일 수 없는 자리라서, 세면 큐가 거짓으로 길어진다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "data" / "processed" / "segments.geojson"

#: 임계는 `seg/params.py` 가 정본이다. 여기 있는 것은 **띠의 경계**이고
#: 판정 임계(3.0/7.0)와 뜻이 다르다 — 6.0 은 「측량만으로 넓다고 볼 선」이다.
NARROW = 3.0
WIDE = 6.0

TIERS = ("임계 인접", "폭 없음", "이미 답함")


def tier(p: dict) -> str:
    w = p.get("width_min_m")
    if not isinstance(w, (int, float)):
        return "폭 없음"
    return "임계 인접" if NARROW <= w < WIDE else "이미 답함"


def targets(feats: list[dict]) -> list[dict]:
    """CV 를 붙일 수 있는 판정 대상. **붙일 수 없는 자리는 큐가 아니다.**"""
    return [f["properties"] for f in feats
            if f["properties"].get("verdict") in ("needs_cv", "unknown")
            and f["properties"].get("cv_feasible")]


def order(rows: list[dict]) -> list[dict]:
    rank = {t: i for i, t in enumerate(TIERS)}
    return sorted(rows, key=lambda p: (rank[tier(p)],
                                       -(p.get("route_usage") or 0),
                                       -(p.get("length_m") or 0)))


def load(path: Path = SEG) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    per = {t: sum(1 for p in rows if tier(p) == t) for t in TIERS}
    return {
        "what": "영상판정 큐 — 측량이 못 가른 구간부터. 측량폭은 판정에 안 든다",
        "queue": n,
        "per_tier": per,
        "already_answered_pct": round(100 * per["이미 답함"] / n, 1) if n else 0.0,
        "narrow_m": NARROW,
        "wide_m": WIDE,
        "note": "PLAN §1 #54 는 156 · 117 을 적지만 그 수는 낡았다 — 매번 다시 잰다",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="영상판정을 어느 구간부터 붙일 것인가")
    ap.add_argument("--out", help="순서대로 CSV 로 쓴다")
    ap.add_argument("--seg", default=str(SEG))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    p = Path(a.seg)
    if not p.is_file():
        print(f"★ {p} 가 없다 — 파이프라인을 먼저 돌려라")
        return 1
    rows = order(targets(load(p)))
    s = summarize(rows)
    print(f"영상판정 큐 {s['queue']}구간  (CCTV 가 없어 못 붙이는 자리는 뺐다)")
    for t in TIERS:
        c = s["per_tier"][t]
        mark = "  ← 먼저" if t == "임계 인접" else ("  ← 뒤로" if t == "이미 답함" else "")
        print(f"   {t:<10} {c:>4}  ({100 * c / s['queue']:.0f}%){mark}" if s["queue"]
              else f"   {t:<10} {c:>4}")
    if s["queue"]:
        print(f"\n★ 측량이 이미 답한 자리가 큐의 {s['already_answered_pct']}% 다 — "
              f"그만큼이 뒤로 밀린다(버리지 않는다).")
    if a.out:
        cols = ("seg_uid", "seg_label", "road_name", "verdict", "width_min_m",
                "width_src", "route_usage", "length_m", "unknown_reason")
        with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(("순위", "층", *cols))
            for i, r in enumerate(rows, 1):
                w.writerow((i, tier(r), *(r.get(c) for c in cols)))
        print(f"→ {a.out}")
    return 0


def selftest() -> int:
    """층이 실제로 갈리는가. 하나로 뭉개지면 순서가 없는 것과 같다."""
    bad = []
    mk = lambda w, u=0, v="needs_cv", f=True: {  # noqa: E731
        "properties": {"width_min_m": w, "route_usage": u, "verdict": v,
                       "cv_feasible": f, "length_m": 10}}
    feats = [mk(4.0, 5), mk(1.0, 9), mk(None, 1), mk(9.0, 3),
             mk(4.5, 2, v="clear"), mk(4.5, 2, f=False)]
    got = targets(feats)
    if len(got) != 4:
        bad.append(f"대상 고르기가 틀렸다 — clear 와 CV 불가를 빼면 4여야 하는데 {len(got)}")
    if {tier(p) for p in got} != set(TIERS):
        bad.append(f"층이 안 갈린다: {[tier(p) for p in got]}")
    seq = [tier(p) for p in order(got)]
    if seq != ["임계 인접", "폭 없음", "이미 답함", "이미 답함"]:
        bad.append(f"층 순서가 틀렸다: {seq}")
    # ★ 같은 층 안에서 통행량이 많은 쪽이 먼저인가
    two = order(targets([mk(4.0, 1), mk(4.0, 7)]))
    if [p["route_usage"] for p in two] != [7, 1]:
        bad.append(f"같은 층에서 통행량 순이 아니다: {[p['route_usage'] for p in two]}")
    if summarize([])["queue"] != 0:
        bad.append("빈 큐에서 죽는다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — 층 셋이 갈리고 순서가 선다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
