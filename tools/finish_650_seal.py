#!/usr/bin/env python3
"""
finish_650_seal.py — §650 이 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_650_seal.py            계획만
    uv run python tools/finish_650_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
  ① MASTER §23-2 에 `tools/` 파일 둘(`cost_vs_dispatch` · 이 파일 자신)을, §23-3 에 시험 `tests/test_cost_vs_dispatch.py` 를 등재한다.
  ② MASTER §7-2(아직 검증되지 않은 것)에 「`cost` 의 절대값은 119 출동 실측과 2배 넘게 어긋난다」를 더한다 — **한계 절의 몫**이다(PLAN #195 · DECISIONS §650).
     한계가 PLAN 에만 있으면 「남은 일」로만 읽히고 산출물의 한계로는 안 읽힌다.

`sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636). 적는 주체가 사람이라는 뜻이지 적는 방법이 손이라는 뜻이 아니다 — `finish_649_seal.py` 가 선례다.
멱등이다. 앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

IN    docs/MASTER.md
OUT   같은 파일 (--apply 일 때만)
PARAM 없음
부류  생산   문서의 줄을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서)
밖    절이 옳은지는 안 본다(`sealcov` 도 안 본다). 수는 DECISIONS §650 의 실행 값이다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MASTER = Path(__file__).resolve().parent.parent / "docs" / "MASTER.md"
TOOLS_ANCHOR = "| `tools/fetch_api.py` |"
TESTS_ANCHOR = "| `tests/test_snap_groups.py` |"

TOOL_ROWS = [
    ("tools/cost_vs_dispatch.py",
     "| `tools/cost_vs_dispatch.py` | **`cost` 를 119 출동 실측으로 구간 단위에서 대는 조사 도구**(읽기 전용 · 판정 불변 · DECISIONS §650). 행 → 사건 → 위치로 접고(한 사건의 여러 신고접수는 하나로 · 같은 곳의 다른 날은 따로) "
     "`SNAP_TRUST` · `SNAP_MAX` 로 구간에 붙이고, `segments._write_route` 와 같은 그래프에서 센터 → 지점을 `edge_cost` 로 구해 `speed.ts::travelSeconds` 와 같은 식으로 시간을 낸다 — "
     "**속도표는 `speed.ts` 에서 읽는다(사본 없음) · `edge_cost` 에 속도도 고정분도 없다.** 치우침 · 순위상관 · 적합 · 부트스트랩 95% · 선택 편향 · 거리 레버리지 · 막힌 구간 위 지점을 같이 낸다 |"),
    ("tools/finish_650_seal.py",
     "| `tools/finish_650_seal.py` | §650 이 만든 문서 빈 곳을 닫는다 — 이 절의 도구 둘 · 시험 하나 등재와 MASTER §7-2 의 한계 한 줄. `sealcov` 는 `--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |"),
]
TEST_ROW = ("tests/test_cost_vs_dispatch.py",
            "| `tests/test_cost_vs_dispatch.py` | 조사 도구의 순수 함수 — 속도표를 **`speed.ts` 에서 읽고 맞는가** · 접기(사건 · 위치 · 센터가 다르면 다른 위치) · 스냅 분류가 두 상수를 닫힌 구간으로 쓰는가 · "
            "계산 소요가 **`travelSeconds` 식**(Σ 길이/속도 × cost/길이)인가 · 막힌 구간은 닿는 끝까지만 |")
LIMIT_ANCHOR = "- **현장 접근시간(도착 → 환자 접촉)은 판정 · `cost` 의 입력에 없다.**"
LIMIT = ("- **`cost` 의 절대값은 119 출동 실측과 2배 넘게 어긋난다**(DECISIONS §650 · PLAN #195). 센터에서 지점까지를 `edge_cost` 로 구해 `speed.ts` 의 `travelSeconds` 식으로 낸 주행 시간이 중앙 **180초 안팎**이고 "
         "같은 지점의 실제 출동지령 → 현장도착이 **380초 안팎**이다(스냅된 106곳 치우침 중앙 **+208초** [+183, +227] · 스냅 한계 없이 364곳 +227초). **속도 탓인지 고정분 탓인지는 못 가른다** — "
         "지점이 센터에서 1.0~1.4km 에 몰려 있어 이 범위에서는 거리가 시간을 설명하지 못한다(전체 598곳 rho −0.04). 치우침이 거리에 늘지 않아(rho −0.215) 고정분 쪽으로 읽히나 확정이 아니다. "
         "**`edge_cost` 에는 속도도 고정분도 없고** 앱의 도착 예정 시각은 주행 시간뿐이라 지령 → 출발 · 현장 접근을 안 든다. "
         "119 신고접수에는 차종이 없어 구급차 · 구조차가 섞이고 좌표는 건물 위치라 스냅 79% 가 6m 밖이다. 스냅된 지점의 **45%(64/141)가 `edge_cost` 가 막은 구간 위**이고 그중 50 은 "
         "판정이 「모른다」인 구간을 폭 추정(중앙 1.37m)이 막은 것인데 실제 출동은 거기에 닿았다 — 판정 오류의 증거는 아니고(차종 · 접근로 모호) 현장 확인 대상이다. 판정은 안 움직인다.\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t = MASTER.read_text(encoding="utf-8")
    new = t

    todo = [(k, r) for k, r in TOOL_ROWS if k not in t]
    print(f"① §23-2 — 등재할 줄 {len(todo)} / {len(TOOL_ROWS)}")
    if todo:
        if t.count(TOOLS_ANCHOR) != 1:
            print(f"✗ 앵커가 {t.count(TOOLS_ANCHOR)}번 — 하나여야 한다: {TOOLS_ANCHOR}", file=sys.stderr)
            return 1
        new = new.replace(TOOLS_ANCHOR, "\n".join(r for _, r in todo) + "\n" + TOOLS_ANCHOR, 1)
    if TEST_ROW[0] in new:
        print("① §23-3 이미 등재돼 있다 — 건너뛴다")
    elif new.count(TESTS_ANCHOR) != 1:
        print(f"✗ 앵커가 {new.count(TESTS_ANCHOR)}번 — 하나여야 한다: {TESTS_ANCHOR}", file=sys.stderr)
        return 1
    else:
        new = new.replace(TESTS_ANCHOR, TEST_ROW[1] + "\n" + TESTS_ANCHOR, 1)
        print("① §23-3 에 tests/test_cost_vs_dispatch.py 를 등재한다")

    if LIMIT[:40] in new:
        print("② §7-2 이미 들어가 있다 — 건너뛴다")
    elif new.count(LIMIT_ANCHOR) != 1:
        print(f"✗ 앵커가 {new.count(LIMIT_ANCHOR)}번 — 하나여야 한다: {LIMIT_ANCHOR[:40]}…", file=sys.stderr)
        return 1
    else:
        new = new.replace(LIMIT_ANCHOR, LIMIT + LIMIT_ANCHOR, 1)
        print("② §7-2 에 한계 한 줄을 더한다")

    if new != t and a.apply:
        MASTER.write_text(new, encoding="utf-8")
        print("✓ 썼다")
    elif new != t:
        print("(계획만 — --apply 로 쓴다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
