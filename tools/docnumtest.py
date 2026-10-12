#!/usr/bin/env python3
"""
docnumtest.py — **`docnum_check.py` 의 자기검사.** 판별식만 산다.

★ 왜 별채인가 — §445-1 과 같은 사유이고 이 저장소에서 **세 번째**다
  (`mutatetest` · `uichecktest` · 여기). 흔드는 쪽과 재는 쪽을 한 파일에 두면
  자기검사가 제 판별식을 흔들고(§398-6 · §443-6), 그리고 그 파일이 상한을
  넘었다. `#166` 이 넓힌 지문 범위가 이 별채를 덮으므로 떼도 장부가 안 샌다.

★ 세 번째라서 **배선 면제를 손으로 적지 않는다** — `tools/<x>test.py` 를
  `tools/<x>.py` 가 함수 안에서 끌어오면 배선으로 **도출한다**(§449-2 ·
  `tests/test_tools_are_wired.py`). §445-8 이 배운 자리와 같다.

IN    (없음 — 합성 입력으로 판별식을 민다)
OUT   표준출력 · 종료코드
부류  몸통   진입점이 **아니다.** `docnum_check.py --selftest` 가 부른다
밖    **실물이 맞는가는 안 본다** — 그것은 `docnum_check.main()` 이 든다.
"""
from __future__ import annotations

from docnum_check import ROOT, contradiction_faults, doc_pairs, retired_clashes


def selftest() -> int:
    """★ **폐기목록이 지금 값을 폐기라고 적는가**를 실제로 가르는가.

    문서도 산출물도 안 읽는다 — 합성 표로 본다. 2026-09-30 실기의 그 모양을
    그대로 넣는다: `clear` 의 폐기값 400 이 `unknown` 의 현재값이 됐다(§330).
    """
    fails = []
    cur = {"clear": 464, "unknown": 400, "blocked": 192}

    got = retired_clashes(cur, {"clear": ["392", "400"]})
    if not any("다른 축" in g for g in got):
        fails.append("**축을 가로지른 충돌을 못 본다** — 2026-09-30 실기가 그것이다")

    got = retired_clashes(cur, {"clear": ["464"]})
    if not any("현재값" in g and "다른 축" not in g for g in got):
        fails.append("같은 축의 현재값이 폐기목록에 있는데 못 본다")

    if retired_clashes(cur, {"clear": ["392", "443"]}):
        fails.append("깨끗한 목록을 충돌로 읽는다 — 이러면 사람이 검사를 끈다")

    # ★ 반대 방향. 실물 목록이 지금 깨끗한가 — 여기서 0 이 아니면 결함이다.
    if retired_clashes({"clear": 1, "unknown": 2}, {}):
        fails.append("빈 목록에서 무언가를 낸다 — 빈 그물의 반대쪽")

    for f in fails:
        print(f"  ✗ {f}")
    # ★ 뒤집힘 축 (§449 · PLAN #101 닫힘) — **양방향**
    _f = {"seg_id": "str, 실행 내 표시용 일련번호. ★불변이 아니다. 외부 참조 금지"}
    if not contradiction_faults([("seg_id", "**런 내 불변.** 외부 참조 금지")], _f):
        fails.append("표가 정본을 뒤집었는데 안 운다")
    if contradiction_faults([("seg_id", "**불변이 아니다.** 실행 내 표시용")], _f):
        fails.append("바르게 적었는데 운다")
    # ★ 짧아진 것은 결함이 아니다 — 그것이 이 표의 일이다
    if contradiction_faults([("seg_id", "표시용 번호")], _f):
        fails.append("짧아진 풀이에 운다 — 그러면 사람이 이 문을 끈다")
    # ★ 빈 그물 — 정본에 그 필드가 없으면 조용하다(없는 것을 뒤집을 수 없다)
    if contradiction_faults([("없는필드", "**불변**")], _f):
        fails.append("정본에 없는 필드에 운다")
    if not doc_pairs((ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")):
        fails.append("§11 표에서 쌍을 하나도 못 읽었다 — 수집기가 죽었다")

    print("✓ 자기검사 통과 · 판별식 9" if not fails else f"✗ {len(fails)}건")
    return 1 if fails else 0
