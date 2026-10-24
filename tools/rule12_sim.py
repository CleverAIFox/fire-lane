#!/usr/bin/env python3
"""
tools/rule12_sim.py — 규칙 [12](대장 괴리)를 **짜 두고 발행하지 않는다.**  판정 수가 어떻게 바뀔지만 낸다.  (Zm23 · DECISIONS §569)

    uv run python tools/rule12_sim.py            적용 시 판정 수 전후를 찍는다 (아무것도 쓰지 않는다)
    uv run python tools/rule12_sim.py --selftest ★ 판별식이 살아 있나

── 규칙 [12] ───────────────────────────────────────────────────
`clear` 인데 대장 명목폭(`road_bt_m`)과 `width_med_m` 의 **계단 차 `|d| ≥ 3`** 이면 `clear` 를 거두고 `needs_cv`
(`cv_reason = "ledger_gap"`)로 보낸다. 판정 폐포 **밖**이다 — `classify()` · `segments.py` 가 이 모듈을 안 부른다.

── 문턱 3 의 근거 — 분포가 아니라 계단 구조다 ───────────────────
대장은 정수 미터 등재 계단값이다(DECISIONS §567). 우리 값을 계단에 올림한 것과의 차 `d` 는 이렇게 읽는다:
    ±1칸   양자화 — 올림 하나로 생긴다
    ±2칸   반올림 + 최솟값 대 대표값 집계차가 만드는 범위(DECISIONS §568-5)
    ≥ 3칸  계단 정의상 설명되지 않는다
★ **분포를 보고 조정하지 않는다.** 감사가 [11] 의 `SPREAD_MAX` 2.5 를 「같은 데이터로 규칙을 만들고 평가했다」고 때렸다.
  3 은 이 데이터를 본 뒤 정한 수가 아니라 계단 구조에서 나온 수이고, **이 도구는 3 을 인자로 받지 않는다.**

── 적용 범위 ───────────────────────────────────────────────────
· 대장이 **소수**인 구간(45)은 뺀다 — 계단이 없어 `d` 가 정의되지 않는다.
· `width_med_m` 이 **없는** 구간은 뺀다.
· `clear` 만 건드린다. `ROAD_BT < 3.0` 규칙 [1](`blocked`)과 규칙 [7](`ledger_disputes`)에서 끝난 구간은 **`clear` 가 아니라서 [12] 까지 오지 않는다**
  (`clear` 가 아니면 이 규칙의 전제가 거짓이다 — 시험이 합성 입력으로 확인한다).

IN    web/data/segments.geojson
OUT   표준출력 (아무 파일도 안 쓴다)
PARAM `GAP_RULE12` (3 — 계단 구조에서 나온 수. 인자로 안 받는다)
밖    **규칙이 옳은가는 안 정한다.** 0판 평가셋(`tools/evalset.py`)의 채점(Q4)이 끝나기 전에는 발행하지 않는다. 판정을 안 움직인다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

from collections import Counter

from ledgercross import SEG, gap, is_step, steps_of
from statkit import num

GAP_RULE12 = 3          # 계단 구조에서 나온 수 — 분포로 조정하지 않는다
REASON = "ledger_gap"


def applies(verdict: str, ledger: float | None, wmed: float | None, steps: list[float]) -> bool:
    """규칙 [12] 가 이 구간을 거두는가. `clear` 만, 대장이 계단값일 때만, 중앙값이 있을 때만."""
    if verdict != "clear" or ledger is None or wmed is None:
        return False
    if not is_step(ledger):
        return False
    d, _ = gap(ledger, wmed, steps)
    return abs(d) >= GAP_RULE12


def apply(rows: list[dict]) -> list[tuple[str, str | None]]:
    """구간마다 (판정, cv_reason). 규칙을 얹은 **가상** 판정이다 — 발행값이 아니다."""
    steps = steps_of([num(r["road_bt_m"]) for r in rows if num(r.get("road_bt_m")) is not None])
    out = []
    for r in rows:
        lg, wm = num(r.get("road_bt_m")), num(r.get("width_med_m"))
        if applies(r["verdict"], lg, wm, steps):
            out.append(("needs_cv", REASON))
        else:
            out.append((r["verdict"], r.get("cv_reason") if r["verdict"] == "needs_cv" else None))
    return out


def report(rows: list[dict]) -> dict:
    new = apply(rows)
    before = Counter(r["verdict"] for r in rows)
    after = Counter(v for v, _ in new)
    hit = [r for r, (v, why) in zip(rows, new, strict=True) if why == REASON]
    return {"before": dict(sorted(before.items())), "after": dict(sorted(after.items())), "moved": len(hit),
            "moved_cctv_in": sum(1 for r in hit if r.get("cv_feasible")),
            "moved_cctv_out": sum(1 for r in hit if not r.get("cv_feasible")),
            "non_step_ledger": sum(1 for r in rows if num(r.get("road_bt_m")) is not None and not is_step(num(r["road_bt_m"]))),
            "no_median": sum(1 for r in rows if num(r.get("width_med_m")) is None),
            "blocked_untouched": all(v == "blocked" for r, (v, _) in zip(rows, new, strict=True) if r["verdict"] == "blocked")}


def selftest() -> int:
    bad: list[str] = []
    steps = [1.0, 2.0, 3.0, 6.0, 9.0, 15.0]
    if not applies("clear", 15.0, 2.5, steps):
        bad.append("d=3 이상인데 안 거둔다")
    if applies("clear", 9.0, 2.5, steps):
        bad.append("d=2 인데 거뒀다 — 문턱은 3 이다")
    if applies("blocked", 15.0, 1.0, steps) or applies("needs_cv", 15.0, 1.0, steps):
        bad.append("clear 가 아닌 구간을 건드렸다")
    if applies("clear", 4.5, 1.0, steps) or applies("clear", 15.0, None, steps):
        bad.append("소수 대장값 · 중앙값 없음을 안 뺐다")
    for x in bad:
        print("  ✗", x)
    print("✓ 살아 있다" if not bad else f"✗ {len(bad)}건")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--selftest", action="store_true", help="판별식이 살아 있나")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rows = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    r = report(rows)
    print(f"규칙 [12] 가상 적용 — 대장 계단 차 |d| ≥ {GAP_RULE12} (width_med_m 기준) · 발행하지 않는다")
    print(f"  전  {r['before']}\n  후  {r['after']}")
    print(f"  거둔 구간 {r['moved']} (CCTV 19m 안 {r['moved_cctv_in']} · 밖 {r['moved_cctv_out']}) · 소수 대장값 제외 {r['non_step_ledger']} · 중앙값 없음 제외 {r['no_median']}")
    print(f"  blocked 불변: {r['blocked_untouched']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
