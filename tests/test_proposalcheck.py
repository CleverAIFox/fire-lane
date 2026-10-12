"""
test_proposalcheck.py — 기획서 **정본** 대조가 양방향인가.
  (DECISIONS §444 · PLAN #142 · 옛 W3-3 · W4-2 의 증거)

★ 왜 이 시험이 옛 `tests/test_docx_targets.py` 를 이어받나 —
  그 시험이 지킨 것은 「기획서 ↔ 산출물 대조가 **찾는 쪽과 고치는 쪽 둘 다**
  살아 있는가」였다. 고치는 쪽(`docx_fix`)은 docx 가 바이너리라 필요했고(R9 의
  반대 경우), 정본이 `docs/proposal.md` 로 옮겨지며 그 사유가 사라졌다 —
  md 는 diff 가 되므로 사람이 고친다. 남은 물음은 **찾는 쪽이 비어 있지
  않은가** 하나이고, 그것을 여기서 양방향으로 민다.

★ 도구의 자기검사와 같은 판별식을 두 곳에서 민다. 자기검사는 합성 입력으로
  그물이 비었나를 보고(`selftests.py` 가 돌린다), 이쪽은 **실물 정본**에서 본다.

밖    **수는 안 본다** — 구간 수 · 판정 4종 · 회색 사유는 `tests/test_doc_numbers.py`
      와 `tools/docnum_check.py` 가 든다. **화면이 정본과 같은가**도 안 본다
      (`build_proposal --check`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "src")]

import proposalcheck as P  # noqa: E402 — `sys.path` 를 먼저 깔아야 import 가 된다


def test_the_real_proposal_passes_every_axis():
    """실물 — 총연장 · 캡션 · 폐기 어휘 · 참조 · 긴 칸 다섯이 전부 맞는가."""
    bad = P.audit()
    assert not bad, "\n".join(bad)


def test_the_source_is_actually_read():
    """★ **빈 그물 금지.** 정본을 못 읽으면 모든 축이 조용히 통과한다."""
    txt = P.text()
    assert txt is not None, f"{P.MD.relative_to(ROOT)} 을 못 읽었다"
    assert len(P.cells(txt)) > 500, "표 칸을 너무 적게 셌다 — 파서를 의심하라"
    assert len(P.captions(txt)) >= 20, "캡션을 너무 적게 찾았다"
    assert P.text(ROOT / "없는파일.md") is None, "없는 파일에서 빈 문자열을 낸다"


def test_every_axis_bites_synthetic_input():
    """합성 입력 — 다섯 축이 **각자** 운다. 하나라도 안 울면 그 축은 장식이다."""
    dead = []
    if not P.total_faults("총연장 1.0km", 58308.7):
        dead.append("총연장")
    if not P.caption_faults(["[그림 1] 원천 11종"], {"ds": 80, "ret": 10}):
        dead.append("캡션")
    if not P.retired_faults("src/etl 을 쓴다"):
        dead.append("폐기 어휘")
    if not P.ref_faults("tools/절대없는것.py", ["tools/proposalcheck.py"]):
        dead.append("참조")
    if not P.long_faults([P.LONG_CELL + 1]):
        dead.append("긴 칸")
    assert not dead, f"안 우는 축: {dead}"


def test_the_retired_words_name_what_replaced_them():
    """폐기 어휘마다 **왜 폐기인지**가 있다. 사유 없는 금지는 다음 사람이 못 지운다."""
    for k, why in P.RETIRED.items():
        assert len(why.strip()) >= 15, f"`{k}` 의 사유가 너무 짧다"


def test_the_long_cell_ratchet_is_at_the_measured_value():
    """양방향 래칫 — 선언이 실측과 같은가. 느슨한 래칫은 상한이 아니라 지난 기록이다."""
    got = P.ratchet_values()
    assert got["LONG_MAX_N"] == P.LONG_MAX_N, got
    assert got["LONG_MAX_LEN"] == P.LONG_MAX_LEN, got
