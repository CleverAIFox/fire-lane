#!/usr/bin/env python3
"""
finish_652_seal.py — §652 가 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_652_seal.py            계획만
    uv run python tools/finish_652_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
  ① MASTER §23-2 에 `tools/` 파일 둘(`oneway_match` · 이 파일 자신)을, §23-3 에 시험 `tests/test_oneway_match.py` 를 등재한다.
  ② MASTER §7-2(아직 검증되지 않은 것)에 일방통행 방향의 한계 한 줄을 더한다 — 방향 확정 57 중 1 · 두 목록이 채울 후보 5구간 · 시점부 → 종점부가 통행 방향이라는 근거는 n=1 ·
     역주행 배수는 근거 없는 정책 값이고 지금 발행에서는 경로를 안 바꾼다. **한계 절의 몫**이다(PLAN #1 · DECISIONS §652).

`sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636). 적는 주체가 사람이라는 뜻이지 적는 방법이 손이라는 뜻이 아니다 — `finish_650_seal.py` 가 선례다.
멱등이다. 앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

IN    docs/MASTER.md
OUT   같은 파일 (--apply 일 때만)
PARAM 없음
부류  생산   문서의 줄을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서)
밖    절이 옳은지는 안 본다(`sealcov` 도 안 본다). 수는 DECISIONS §652 의 실행 값이다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MASTER = Path(__file__).resolve().parent.parent / "docs" / "MASTER.md"
TOOLS_ANCHOR = "| `tools/fetch_api.py` |"
TESTS_ANCHOR = "| `tests/test_snap_groups.py` |"
LIMIT_ANCHOR = "- **`cost` 의 절대값은 119 출동 실측과 2배 넘게 어긋난다**"

TOOL_ROWS = [
    ("tools/oneway_match.py",
     "| `tools/oneway_match.py` | **일방통행 두 목록(동구청 표 · 동부경찰서 hwpx)을 우리 구간에 대고 발행 변화를 계산하는 조사 도구**(읽기 전용 · 판정 불변 · DECISIONS §652). 두 목록을 행으로 읽고(병합 머리 3줄은 위치로 건너뛰며 머리글이 바뀌면 죽는다) "
     "끝점 지번을 지적도 필지 중심으로 옮겨 같은 도로명 구간에 댄다 — **붙음 · 부분 · 밖 · 도로명 구간 없음 · 끝점 좌표 없음 · 끝점 지번 없음**을 사유별로 센다. `ow` 가 어떻게 바뀔지를 **계산만** 하고 `navi_graph.json` 을 안 쓴다. "
     "`--sensitivity` 는 `rules.ts` 의 역주행 배수(상수를 거기서 읽는다)를 바꿔 센터 → 노드 경로가 얼마나 바뀌나를 낸다 |"),
    ("tools/finish_652_seal.py",
     "| `tools/finish_652_seal.py` | §652 가 만든 문서 빈 곳을 닫는다 — 이 절의 도구 둘 · 시험 하나 등재와 MASTER §7-2 의 일방통행 방향 한계 한 줄. `sealcov` 는 `--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |"),
]
TEST_ROW = ("tests/test_oneway_match.py",
            "| `tests/test_oneway_match.py` | 일방통행 매칭 도구의 순수 함수 — 끝점 읽기(접두 · 행정동 → 법정동 · **지번이 없으면 추측하지 않는다**) · 두 목록 읽기(머리글이 바뀌면 죽는다 · `～` `→`) · 경로 방향 · "
            "분류가 두 문턱을 닫힌 구간으로 쓰는가 · 방향 계수가 **`rules.ts` 와 같고 상수를 거기서 읽는가** · 매칭이 억지로 붙이지 않고 사유를 대는가 · 방향 근거 · 민감도 |")
LIMIT = ("- **일방통행 방향은 57구간 중 1 만 확정이고, 두 목록이 채울 후보는 5구간이다**(DECISIONS §652 · PLAN #1). 방향의 유일한 출처인 표준노드링크가 골목을 안 든다(`nl_none` 44). 동구청 표 33행을 지적도로 좌표화해 같은 도로명 구간에 댄 결과 "
         "**붙음 3 · 부분 9 · 밖 9 · 끝점 좌표 없음 8 · 도로명 구간 없음 2 · 끝점 지번 없음 2** 이고 방향이 새로 정해질 곳은 `ow=2` 5구간이다. **표의 시점부 → 종점부가 통행 방향이라는 것은 문서에 없다** — "
         "경찰 문서가 화살표로 방향을 적는 행은 42 중 5개이고 우리 `ow=1` 한 구간과의 일치(n=1)가 전부라 **발행에 쓰지 않았다.** 역주행 배수(`rules.ts` ×4 · ×1.5)는 **근거 없는 정책 값**이다 — "
         "지금 발행에서는 경로를 하나도 안 바꾸고(센터 → 노드 1,392 중 0) 방향 5구간을 넣어도 ×2 ~ ×8 은 역주행 경로 6 → 2 로만 갈린다. 판정은 안 움직인다.\n")


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
        print("① §23-3 에 tests/test_oneway_match.py 를 등재한다")

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
