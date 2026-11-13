"""tests/test_closewords.py — 닫는 문단의 후속 어휘. 카나리아는 `#144` 옛 닫는 문단(DECISIONS §696)이다.  (DECISIONS §733 · E2)

IN    tools/closewords.py · .pre-commit-config.yaml
OUT   없음 (검사)
밖    인용한 행이 그 일을 **정말 드는지**(번호의 실재만 본다) · 훅이 실제 커밋에서 도는지(등록만 본다) · 목록 밖의 말로 쓴 후속
PLAN 본문  규칙 없음 — 닫는 문단을 무는 검사이고 PLAN 의 어느 행도 이 파일을 근거로 서지 않는다
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import closewords as cw

AFTER = "| 7 | x |\n| 225 | y |\n"


def test_canary_144_old_paragraph_is_blocked():
    assert cw.verdict(cw.CANARY_PLAN, cw.CANARY_DEC, AFTER)[0] == 1


def test_citing_an_existing_open_row_passes():
    assert cw.verdict(cw.CANARY_PLAN, cw.CANARY_DEC.replace("이 행의", "`#225` 가 든다 — 이 행의"), AFTER)[0] == 0


def test_citing_a_missing_row_is_blocked():
    assert cw.verdict(cw.CANARY_PLAN, cw.CANARY_DEC.replace("이 행의", "`#999` 가 든다 — 이 행의"), AFTER)[0] == 1


def test_closed_row_cannot_be_its_own_followup():
    dec = cw.CANARY_DEC.replace("이 행의", "`#144` 가 든다 — 이 행의")
    assert cw.verdict(cw.CANARY_PLAN, dec, "| 144 | 아직 |\n")[0] == 1


def test_unverifiable_wording_is_allowed():
    dec = cw.CANARY_DEC.replace("이 행의 범위가 아니다", "더 알 수 없어 확인 불가로 닫는다")
    assert cw.verdict(cw.CANARY_PLAN, dec, AFTER)[0] == 0


def test_no_closed_row_means_nothing_to_check():
    assert cw.verdict("", cw.CANARY_DEC, AFTER)[0] == 0


def test_selftest_and_hook():
    assert cw.selftest() == 0
    assert "id: closewords" in (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
