#!/usr/bin/env python3
"""
cost_inputs.py — **경로 비용 입력이 결측과 0 을 가르는가.** 그리고 계수가 켜졌는가.

    uv run python tools/cost_inputs.py             판정
    uv run python tools/cost_inputs.py --table     입력마다 값 · 결측 · 0 을 표로
    uv run python tools/cost_inputs.py --selftest  ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-25. 받아 둔 자료를 경로 비용에 붙이면서 **같은 실수를 두 번 할 자리**가
  둘 보였다.

  ① **0 을 빼서 발행했다.** `publish_navi.py` 가 `if n:` 으로 `park` 이 0 인 구간
     110개의 칸을 통째로 뺐다. 받는 쪽에서는 그것이 「도로명이 없어 못 셌다」와
     **같은 모습**(`undefined`)이 되고, `BottleneckPanel.tsx` 가 둘을 「없음」 하나로
     찍었다. 모르는 것을 없다고 말하는 것이 이 저장소가 반복해 낸 결함이다.
     ★ 실측하니 그 110 은 **전부 실제 0** 이었다(구간 1,281 전부에 도로명이 있다).
       표기는 우연히 맞았고 **스키마가 틀렸다** — 자료가 조금 바뀌면 거짓이 된다.

  ② **0 의 강도가 다르다.** `ecam` 은 57지점 중 18지점만 도로명이 붙는다(나머지는
     「지산동 521-3」 꼴 지번 주소). 그래서 `ecam: 0` 은 「카메라가 없다」가 아니라
     **「붙은 18지점 중에 없다」** 다. 미배치 몫을 같이 싣지 않으면 읽는 쪽이 0 을
     강한 0 으로 읽는다.

  눈으로 세면 틀린다 — 2026-08-26 에 `feeds` 를 눈으로 세다 틀린 것과 같은 족
  (`ledger_feeds.py` 머리말). 그래서 센다.

★ 그리고 **계수**를 본다. 압력 계수(`TUNING.parkPer1000` 등)는 전부 0 이고 0 인 것이
  요점이다 — 근거가 없어서 비워 뒀다(`web/navi/src/domain/pressure.ts`). 누가 값을
  넣으면 그 순간 **근거 없는 상수가 하나 더** 생긴다(PLAN §1 #2 · #70 이 `avoidUncertain
  = 2.0` 을 그렇게 들고 있다). 그래서 켜는 것 자체는 막지 않고 **적었는가**를 본다 —
  PLAN §1-27 측정 대장(가드 6 · 재기 전에 적는다)에 그 계수 이름이 서 있어야 한다.

IN    web/data/navi_graph.json · web/data/context.geojson
      web/navi/src/domain/vehicle.ts (압력 계수) · docs/PLAN.md §1-27
OUT   표준출력 (판정)
PARAM KNOBS · 없음(문턱을 안 만든다 — 발행물의 자기신고와 실물을 대조할 뿐이다)
밖    **주변 사정(과속방지턱 · 보호구역)이 구간에 붙는 수는 못 본다.** 그 붙이기는
      `domain/pressure.ts` 가 `NEAR_M` 으로 TS 에서 하고, 거리 문턱을 파이썬에 한 벌
      더 두지 않기로 했다(두 벌이면 조용히 갈린다). 그쪽은
      `web/navi/test/pressure.test.ts` 가 든다. 여기는 **발행물에 실린 칸**만 본다.
      ★ 값이 **맞는가**도 못 본다 — 단속 이력의 도로명 붙이기가 옳은지는 이 도구
      밖이다(`_road_of` · `test_seg_roadname`). 여기가 보는 것은 **결측과 0 을
      가르는가**와 **계수가 근거 없이 켜졌는가** 둘이다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "web" / "data" / "navi_graph.json"
CTX = ROOT / "web" / "data" / "context.geojson"
VEHICLE = ROOT / "web" / "navi" / "src" / "domain" / "vehicle.ts"
PLAN = ROOT / "docs" / "PLAN.md"

#: 도로명으로 붙는 구간 단위 증거. (칸, 발행물 자기신고 접두, 미배치 칸, 단위)
FIELDS = (
    ("park", "park", "park_unplaced_rows", "건"),
    ("ecam", "ecam", "ecam_unplaced_sites", "지점"),
)

#: 압력 계수. **전부 0 이어야 하고**, 0 이 아니면 측정 대장에 이름이 서야 한다.
KNOBS = ("parkPer1000", "ecamPerSite", "speedbumpEach", "speedcamEach", "zoneEach")


# ── 수집 ────────────────────────────────────────────────────────
def knobs(txt: str) -> dict[str, float]:
    """`vehicle.ts` 의 `TUNING` 에서 압력 계수를 읽는다.

    ★ 못 읽으면 **죽는다.** 기본값 0 을 두면 계수가 켜져도 이 검사가 조용히 통과한다 —
      빈 그물이 초록으로 위장하는 꼴이고 `publish_navi._verdict_style` 과 같은 선택이다.
    """
    m = re.search(r"export const TUNING\s*:\s*TuningKnobs\s*=\s*\{(.*?)\n\};", txt, re.S)
    if not m:
        raise SystemExit("★ vehicle.ts 에서 TUNING 블록을 못 찾았다")
    blk, out = m.group(1), {}
    for k in KNOBS:
        hit = re.search(rf"\b{k}\s*:\s*(-?[\d.]+)", blk)
        if not hit:
            raise SystemExit(f"★ vehicle.ts TUNING 에 압력 계수 `{k}` 가 없다 — "
                             "칸을 지웠으면 이 도구와 `pressure.ts` 도 같이 정리한다")
        out[k] = float(hit.group(1))
    return out


def ledger_text() -> str:
    """PLAN §1-27 측정 대장 본문. 없으면 빈 문자열이 아니라 죽는다."""
    txt = PLAN.read_text(encoding="utf-8")
    m = re.search(r"^### 1-27\.[^\n]*\n(.*?)(?=^#{2,3} )", txt, re.M | re.S)
    if not m:
        raise SystemExit("★ docs/PLAN.md 에 `### 1-27.` 측정 대장 절이 없다")
    return m.group(1)


def tally(edges: list[dict], field: str) -> dict[str, int]:
    """칸 하나의 값 · 결측 · 0 · **칸 자체가 없음**을 센다.

    ★ 넷을 가른다. `missing_key` 는 **옛 발행물**이다 — 0 으로 읽으면 안 된다.
    """
    out = {"n": len(edges), "missing_key": 0, "null": 0, "zero": 0, "positive": 0}
    for e in edges:
        if field not in e:
            out["missing_key"] += 1
        elif e[field] is None:
            out["null"] += 1
        elif e[field] == 0:
            out["zero"] += 1
        else:
            out["positive"] += 1
    return out


# ── 판정 ────────────────────────────────────────────────────────
def judge(graph: dict, kn: dict[str, float], ledger: str) -> list[str]:
    """어긋난 것들. 빈 목록이면 초록이다."""
    bad: list[str] = []
    edges, counts = graph.get("edges", []), graph.get("counts", {})
    if not edges:
        return ["발행물에 구간이 없다 — 그래프를 못 읽었다"]

    for field, pre, unplaced, unit in FIELDS:
        t = tally(edges, field)
        if t["missing_key"]:
            bad.append(
                f"`{field}` 칸이 없는 구간 {t['missing_key']}개 — **0 을 빼서 발행했다.**\n"
                f"    받는 쪽에서 결측과 0 이 같은 모습이 되고 「없음」 하나로 찍힌다.\n"
                f"    `publish_navi.py` 가 0 도 `null` 도 **명시해서** 실어야 한다.")
        # 발행물의 자기신고가 실물과 맞는가. 어긋나면 그 수를 읽는 도구·시험이 다 틀린다.
        for key, got in ((f"{pre}_null", t["null"]), (f"{pre}_zero", t["zero"])):
            if key not in counts:
                bad.append(f"`counts.{key}` 가 없다 — 발행물이 결측·0 을 스스로 안 센다")
            elif counts[key] != got:
                bad.append(f"`counts.{key}` = {counts[key]} 인데 실물은 {got} 다 — "
                           f"발행물의 자기신고가 틀렸다")
        # 0 의 강도. 미배치 몫이 없으면 0 을 강한 0 으로 읽는다.
        if unplaced not in counts:
            bad.append(
                f"`counts.{unplaced}` 가 없다 — `{field}: 0` 이 「없다」인지 "
                f"「붙은 것 중에 없다」인지 읽는 쪽이 알 수 없다({unit} 단위 원천).")

    on = {k: v for k, v in kn.items() if v != 0}
    for k, v in on.items():
        if k not in ledger:
            bad.append(
                f"압력 계수 `{k}` = {v} 로 켰는데 PLAN §1-27 측정 대장에 그 이름이 없다.\n"
                f"    **재기 전에 적는다**(가드 6) — 무엇을 묻고 무엇이 나오면 어느 쪽으로\n"
                f"    판정하는지 먼저 적어야 한다. 기준을 재고 나서 적으면 그것은 판정이\n"
                f"    아니라 사후 합리화다. `avoidUncertain = 2.0` 이 그 빚이다(#2 · #70).")
    return bad


def table(graph: dict, kn: dict[str, float]) -> str:
    edges, counts = graph.get("edges", []), graph.get("counts", {})
    w = []
    w.append(f"  구간 {len(edges)}")
    for field, _pre, unplaced, unit in FIELDS:
        t = tally(edges, field)
        w.append(f"  {field:<6} 값 {t['positive']:>5} · 0 {t['zero']:>5} · 결측 {t['null']:>5}"
                 f" · 칸없음 {t['missing_key']:>5}"
                 f"   (못 붙은 원천 {counts.get(unplaced, '?')}{unit})")
    if CTX.exists():
        ctx = json.loads(CTX.read_text(encoding="utf-8"))
        kinds: dict[str, int] = {}
        for f in ctx.get("features", []):
            k = f.get("properties", {}).get("kind", "?")
            kinds[k] = kinds.get(k, 0) + 1
        w.append("  주변 사정  " + " · ".join(f"{k} {n}" for k, n in sorted(kinds.items()))
                 + "   (구간에 붙이는 것은 pressure.ts — 이 도구 밖)")
    w.append("  압력 계수  " + " · ".join(f"{k}={kn[k]:g}" for k in KNOBS)
             + ("   ← 전부 0. 경로를 안 바꾼다" if all(v == 0 for v in kn.values()) else "   ← 켜졌다"))
    return "\n".join(w)


def selftest() -> bool:
    """판정기가 무는가. **빈 그물이면 이 도구가 영원히 초록이다.**"""
    ok = True

    def want(cond: bool, msg: str) -> None:
        nonlocal ok
        if not cond:
            ok = False
            print(f"  ✗ {msg}")

    good = {"edges": [{"park": 0, "ecam": 3}, {"park": None, "ecam": 0}],
            "counts": {"park_null": 1, "park_zero": 1, "ecam_null": 0, "ecam_zero": 1,
                       "park_unplaced_rows": 9, "ecam_unplaced_sites": 9}}
    zero = dict.fromkeys(KNOBS, 0.0)
    want(not judge(good, zero, ""), "온전한 발행물을 문다")

    # ① 0 을 빼서 발행한 꼴 — 칸이 없다
    miss = json.loads(json.dumps(good))
    del miss["edges"][0]["park"]
    miss["counts"]["park_zero"] = 0
    want(any("0 을 빼서 발행했다" in b for b in judge(miss, zero, "")), "빠진 칸을 안 문다")

    # ② 자기신고가 실물과 어긋난다
    lie = json.loads(json.dumps(good))
    lie["counts"]["park_zero"] = 99
    want(any("자기신고가 틀렸다" in b for b in judge(lie, zero, "")), "거짓 자기신고를 안 문다")

    # ③ 0 의 강도(미배치 몫)가 없다
    weak = json.loads(json.dumps(good))
    del weak["counts"]["ecam_unplaced_sites"]
    want(any("ecam_unplaced_sites" in b for b in judge(weak, zero, "")), "0 의 강도 누락을 안 문다")

    # ④ 계수를 켰는데 측정 대장에 이름이 없다 / 있다
    on = {**zero, "parkPer1000": 0.4}
    want(any("측정 대장에 그 이름이 없다" in b for b in judge(good, on, "")), "근거 없이 켠 계수를 안 문다")
    want(not judge(good, on, "| `park-pressure` | 31 | parkPer1000 을 묻는다 |"),
         "대장에 섰는데도 문다")

    # ⑤ 계수 읽기가 죽으면 죽는가 — 기본값으로 조용히 통과하지 않는다
    try:
        knobs("export const TUNING: TuningKnobs = {\n  unknown: 2.5,\n};")
        want(False, "계수가 빠진 TUNING 을 안 문다")
    except SystemExit:
        pass
    try:
        knobs("const other = {};")
        want(False, "TUNING 블록이 없는데 안 문다")
    except SystemExit:
        pass

    want(len(judge({"edges": []}, zero, "")) == 1, "빈 그래프를 안 문다")
    print("  ✓ 판정기가 문다" if ok else "  ★ 판정기가 헐겁다")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="경로 비용 입력이 결측과 0 을 가르는가")
    ap.add_argument("--table", action="store_true", help="입력마다 값 · 결측 · 0")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args(argv)

    if a.selftest:
        return 0 if selftest() else 1

    if not GRAPH.exists():
        print(f"  ! {GRAPH.relative_to(ROOT)} 없음 — `python -m firelane.publish_navi` 먼저")
        return 1
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    kn = knobs(VEHICLE.read_text(encoding="utf-8"))

    if a.table:
        print(table(graph, kn))
        return 0

    bad = judge(graph, kn, ledger_text())
    print(table(graph, kn))
    if bad:
        print("\n★ 경로 비용 입력이 어긋났다.")
        for b in bad:
            print(f"  ✗ {b}")
        return 1
    print("\n  ✓ 결측과 0 이 갈려 있고 · 자기신고가 실물과 맞고 · 계수가 근거 없이 안 켜졌다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
