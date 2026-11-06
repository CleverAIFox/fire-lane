#!/usr/bin/env python3
"""
finish_653_seal.py — §653 이 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_653_seal.py            계획만
    uv run python tools/finish_653_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
  ① MASTER §23-2 에 이 파일 자신을, §23-3 에 시험 `tests/test_oneway_field.py` 를 등재한다.
  ② MASTER 의 일방통행 방향 서술 셋을 **발행이 바뀐 사실**로 고친다 — 방향 확정이 1 → 6(표준노드링크 1 + 사람이 확인한 표 5 · DECISIONS §653).
     낡은 서술을 두면 다음 사람이 「57 중 1 만 확정」으로 읽는다. §7-2 의 한계 줄은 §652 가 「발행에 쓰지 않았다」로 적었는데 **그 말이 지금은 틀렸다.**

`sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636). 적는 주체가 사람이라는 뜻이지 적는 방법이 손이라는 뜻이 아니다 — `finish_652_seal.py` 가 선례다.
멱등이다. 앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

IN    docs/MASTER.md
OUT   같은 파일 (--apply 일 때만)
PARAM 없음
부류  생산   문서의 줄을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서)
밖    절이 옳은지는 안 본다(`sealcov` 도 안 본다). 수는 DECISIONS §653 의 실행 값이다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MASTER = Path(__file__).resolve().parent.parent / "docs" / "MASTER.md"
TOOLS_ANCHOR = "| `tools/fetch_api.py` |"
TESTS_ANCHOR = "| `tests/test_snap_groups.py` |"
SELF = ("tools/finish_653_seal.py",
        "| `tools/finish_653_seal.py` | §653 이 만든 문서 빈 곳을 닫는다 — 이 도구 · 시험 하나 등재와 일방통행 방향 서술 셋의 정정(방향 확정 1 → 6). `sealcov` 는 `--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |")
TEST = ("tests/test_oneway_field.py",
        "| `tests/test_oneway_field.py` | 사람이 확인한 일방통행 방향 표가 `ow` 로 옮겨지는 규칙 — **`ow=2` 인 구간에만**(노드링크 ±1 · 양방향은 안 덮는다) · `use` 가 「적용」인 행만 · 방향은 부호가 아니라 **좌표**로(두 끝이 안 붙는 낡은 표는 모름으로 둔다) · "
        "모름의 사유 수가 **남은 모름**의 분할로 남는가 · 실제 표의 칸 · 어휘 · 근거 · `seg_uid` 실재 |")
REPL = [
    ("| 일방통행 방향 | 57구간 중 **확정 1**이다. 모르는 구간은 양쪽 다 불리하게 계산한다(§4) |",
     "| 일방통행 방향 | 57구간 중 **확정 6**이다(표준노드링크 1 + 사람이 확인한 표 5 · §653). 모르는 51은 양쪽 다 불리하게 계산한다(§4) |"),
    ("일방통행 57구간 중 방향 확정은 1곳뿐이다 —\n  1:1000 중심선에 방향 필드가 없다.",
     "일방통행 57구간 중 방향 확정은 6곳이다(표준노드링크 1 · 사람이 확인한 표 5 · §653) —\n  1:1000 중심선에 방향 필드가 없고 표준노드링크가 골목을 안 든다."),
]
OLD_LIMIT_START = "- **일방통행 방향은 57구간 중 1 만 확정이고, 두 목록이 채울 후보는 5구간이다**"
NEW_LIMIT = ("- **일방통행 방향은 57구간 중 6 이 확정이다 — 표준노드링크 1 · 사람이 확인한 표 5**(DECISIONS §653 · PLAN #1). 방향의 유일한 출처인 표준노드링크가 골목을 안 든다(`nl_none` 39 남음). 동구청 표 33행을 지적도로 좌표화해 같은 도로명 구간에 댄 결과 "
             "**붙음 3 · 부분 9 · 밖 9 · 끝점 좌표 없음 8 · 도로명 구간 없음 2 · 끝점 지번 없음 2**. 붙음 3행(구성로204번길 · 구성로194번길 · 독립로264번길)과 표 32행은 **사람이 네이버 자동차 길찾기로 정방향 · 역방향을 대조**해 "
             "시점부 → 종점부가 통행 방향임을 확인했다(역방향은 1.84 · 2.43 · 5.88배 우회 · 서로 다른 도로 넷). 그래서 `ow=2` 인 5구간에 방향을 썼다. **근거는 지도 서비스의 경로이지 현장 표지가 아니다.** "
             "「부분」 9행은 안 썼고(구간의 일부만 우리 안 · 확인 없음) 우리는 양방향인데 표는 일방인 충돌 8구간도 안 썼다. 역주행 배수(`rules.ts` ×4 · ×1.5)는 **근거 없는 정책 값**이다 — 방향 5구간이 서면 "
             "×2 ~ ×8 이 역주행을 쓰는 경로를 6 → 2 로 가를 뿐 값을 이 자료로 좁힐 수 없다. 판정은 안 움직인다.\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t = MASTER.read_text(encoding="utf-8")
    new = t
    for key, row, anchor in ((SELF[0], SELF[1], TOOLS_ANCHOR), (TEST[0], TEST[1], TESTS_ANCHOR)):
        if key in new:
            print(f"① {key} 이미 등재돼 있다 — 건너뛴다")
        elif new.count(anchor) != 1:
            print(f"✗ 앵커가 {new.count(anchor)}번 — 하나여야 한다: {anchor}", file=sys.stderr)
            return 1
        else:
            new = new.replace(anchor, row + "\n" + anchor, 1)
            print(f"① {key} 를 등재한다")
    for old, rep in REPL:
        if rep in new:
            print("② 이미 들어가 있다 — 건너뛴다")
        elif new.count(old) != 1:
            print(f"✗ 앵커가 {new.count(old)}번 — 하나여야 한다: {old[:40]}…", file=sys.stderr)
            return 1
        else:
            new = new.replace(old, rep, 1)
            print(f"② 고친다: {old[:36]}…")
    i = new.find(OLD_LIMIT_START)
    if NEW_LIMIT[:40] in new:
        print("② §7-2 이미 고쳐져 있다 — 건너뛴다")
    elif i < 0:
        print("✗ §7-2 의 §652 한계 줄을 못 찾았다", file=sys.stderr)
        return 1
    else:
        j = new.index("\n", i) + 1
        new = new[:i] + NEW_LIMIT + new[j:]
        print("② §7-2 의 한계 줄을 고친다")
    if new != t and a.apply:
        MASTER.write_text(new, encoding="utf-8")
        print("✓ 썼다")
    elif new != t:
        print("(계획만 — --apply 로 쓴다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
