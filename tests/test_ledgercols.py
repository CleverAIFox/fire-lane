"""
test_ledgercols.py — 대장 칸의 **독자가 있는가**.  (DECISIONS §444 · PLAN #134 ㉠)

★ 도구의 자기검사와 **같은 판별식을 두 곳에서** 민다. 자기검사는 도구가
  혼자 설 수 있나를 보고(`selftests.py` 가 돌린다), 이쪽은 **실물 트리**에서
  본다 — 둘이 갈리면 그 갈림이 신호다(§435-9 와 같은 배치).

밖    **칸의 값이 맞는가는 안 본다** — 그것은 `ledger_check` 가 든다.
      **읽는 코드가 옳은가**도 안 본다 — 누가 읽는가만 센다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "src")]

import ledgercols as L  # noqa: E402 — `sys.path` 를 먼저 깔아야 import 가 된다


def test_the_real_ledger_has_a_reader_for_every_column():
    """실물 — 칸마다 읽는 자가 있거나 **왜 사람만 읽는지**가 적혀 있다."""
    cols = L.columns()
    assert len(cols) >= 40, f"대장 칸이 {len(cols)}개뿐이다 — 도출을 의심하라"
    bad = L.faults(cols, L.readers(set(cols)))
    assert not bad, "\n".join(bad)


def test_prose_columns_are_declared_with_a_reason():
    """사유 없는 선언은 **그물을 비운다**(§69)."""
    for c, why in L.PROSE.items():
        assert len(why.strip()) >= 20, f"`{c}` 의 사유가 너무 짧다 — 다음 사람이 못 지운다"


def test_the_probe_reads_syntax_not_text():
    """주석·로그의 낱말을 읽는 것으로 세면 **① 이 영원히 0건**이 된다."""
    assert L.reads('x = e.get("note")\n', {"note"}) == {"note"}
    assert L.reads('x = e["note"]\n', {"note"}) == {"note"}
    assert not L.reads('# note\nprint("note 를 읽는다")\n', {"note"})
    assert not L.reads("def (:::", {"note"}), "문법 오류에서 칸을 낸다"


def test_the_three_axes_fire_on_synthetic_input():
    """★ 양방향. 실물로만 재면 「언제나 초록」과 구별이 안 된다(§230)."""
    syn = {"산문칸": "사유" * 10}
    assert L.faults({"새칸": 1}, {}, {}), "① 읽는 자 없는 새 칸에 안 운다"
    assert not L.faults({"새칸": 1}, {"새칸": {"tools/x.py"}}, {}), "거짓 경보"
    assert not L.faults({"산문칸": 1}, {}, syn), "선언된 산문 칸에 운다"
    assert L.faults({"산문칸": 1}, {"산문칸": {"tools/x.py"}}, syn), "② 를 안 잡는다"
    assert L.faults({"다른칸": 1}, {"다른칸": {"tools/x.py"}}, syn), "③ 을 안 잡는다"
    assert L.faults({}, {}, {}), "대장이 비었는데 통과한다"


def test_the_ratchet_counts_the_declaration_not_the_reality():
    """래칫이 **선언 수**를 든다 — 실측을 들면 줄일 이유가 사라진다."""
    assert L.ratchet_values() == {"PROSE_MAX": len(L.PROSE)}
    assert L.RATCHETS == {"PROSE_MAX": "down"}, "선언이 느는 쪽으로 열려 있으면 안 된다"
    assert L.PROSE_MAX == len(L.PROSE), "선언과 실측이 갈렸다"
