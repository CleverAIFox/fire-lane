"""`tools/intake.py` 의 **단서 ④ 본문** — 이름이 아무 말도 안 할 때 (DECISIONS §399).

★ 이 파일이 지키는 것은 「맞히는가」가 아니라 **「틀리게 안 맞히는가」**다. 틀린
  이름으로 landing 에 넣으면 그 오염이 raw 까지 내려간다. 그래서 사례 대부분이
  「안 고른다 · 못 가른다 · 사람이 정한다」쪽이다.

밖    **진짜 PDF 를 안 연다.** 본문은 `body_text` 를 갈아끼워 글자로 쥐여 준다 —
      pypdf 가 그 PDF 에서 글자를 뽑는가는 이 파일이 안 본다. 그 축은 실물로
      한 번 쟀다(DECISIONS §399-3). **단서 ①②③** 과 `--stage` 의 복사 · sha
      기록도 안 본다 — 그것은 이 배치가 안 건드린 자리다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_intake", ROOT / "tools" / "intake.py")
intake = importlib.util.module_from_spec(_spec)
# ★ `exec_module` **앞**이다 — `@dataclass` 가 `cls.__module__` 로 되짚는다
sys.modules[_spec.name] = intake
_spec.loader.exec_module(intake)

DS = {
    "roadtraffic_act": {
        "what": "도로교통법 긴급자동차 특례 조문",
        "authority": "국가법령정보센터",
        "files": ["moleg/moleg_roadtraffic-act_kr_20260701_a29.pdf",
                  "moleg/moleg_roadtraffic-act_kr_20260701_a30.pdf"],
    },
    "hydrantdevice_rule": {
        "what": "비상소화장치 설치 및 관리 예규",
        "authority": "국가법령정보센터",
        "files": ["moleg/moleg_hydrantdevice-rule_kr_20220523.pdf"],
    },
    "nfa_rapidresponse": {
        "what": "119패스 신속출동 보도자료",
        "authority": "화재대응조사과",
        "files": ["nfa/nfa_rapidresponse_kr_20250429.pdf"],
    },
}


def test_marks_drop_words_that_two_entries_share():
    """구별 낱말은 **그 항목에만** 있는 것이다 — 공유 낱말은 구별을 못 한다."""
    m = intake.body_marks(DS)
    assert "국가법령정보센터" not in m["roadtraffic_act"]   # BODY_STOP 이기도 하다
    assert "도로교통법" in m["roadtraffic_act"]
    assert "비상소화장치" in m["hydrantdevice_rule"]
    assert not (m["roadtraffic_act"] & m["hydrantdevice_rule"])


def test_a_clear_body_picks_its_entry():
    key, why = intake.body_match("비상소화장치 설치 및 관리 예규", DS)
    assert key == "hydrantdevice_rule"
    assert "맞는다" in why


def test_one_matching_word_is_not_a_match():
    key, why = intake.body_match("비상소화장치", DS)
    assert key is None
    assert "바닥" in why


def test_a_body_that_fits_two_entries_is_refused():
    """1등과 2등이 붙어 있으면 **안 고른다** — 반반 맞히지 않는다."""
    ds = {"a": {"what": "소화전 배치 지도", "files": ["x/a.pdf"]},
          "b": {"what": "소화전 배치 지도", "files": ["x/b.pdf"]}}
    key, why = intake.body_match("소화전 배치 지도", ds)
    assert key is None


def test_an_empty_body_is_not_a_match():
    key, why = intake.body_match("", DS)
    assert key is None
    assert "못 읽었다" in why


def test_two_articles_of_one_law_are_split_by_the_printed_url():
    """같은 법령 인쇄본 둘은 점수가 같다 — **조 번호만이 가른다.**"""
    e = DS["roadtraffic_act"]
    a30, why = intake.body_file_of("… lsBdyPrint.do?efYd=20260701&joNo=0030", e)
    assert a30.endswith("_a30.pdf")
    assert "제30조" in why
    a29, _ = intake.body_file_of("… joNo=0029", e)
    assert a29.endswith("_a29.pdf")


def test_without_an_article_number_neither_file_is_chosen():
    rel, why = intake.body_file_of("도로교통법 긴급자동차 특례", DS["roadtraffic_act"])
    assert rel is None
    assert "못 가른다" in why


def test_a_single_declared_file_needs_no_article_number():
    rel, why = intake.body_file_of("아무 글자", DS["hydrantdevice_rule"])
    assert rel.endswith("hydrantdevice-rule_kr_20220523.pdf")
    assert "하나" in why


def test_an_entry_without_files_is_not_guessed():
    rel, why = intake.body_file_of("아무 글자", {"what": "무엇"})
    assert rel is None
    assert "files" in why


@pytest.mark.parametrize("name", ["x.zip", "x.csv", "x.hwp"])
def test_body_text_refuses_everything_that_is_not_a_pdf(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"\x00\x01")
    assert intake.body_text(p) == ""


def test_a_broken_pdf_does_not_stop_the_intake(tmp_path):
    """못 읽는 파일 하나가 취입 전체를 멈추면 안 된다."""
    p = tmp_path / "broken.pdf"
    p.write_bytes(b"not really a pdf")
    assert intake.body_text(p) == ""


def test_the_body_clue_only_runs_when_the_name_said_nothing(tmp_path, monkeypatch):
    """단서 ④ 는 **마지막**이다 — 이름으로 맞은 것을 본문이 덮지 않는다."""
    called = []
    monkeypatch.setattr(intake, "body_text",
                        lambda p, pages=3: called.append(p) or "")
    ds = {"nfa_rapidresponse": {"stem": "nfa_rapidresponse", "provider": "nfa",
                                "what": "119패스", "files": ["nfa/x.pdf"]}}
    src = tmp_path / "nfa_rapidresponse_kr_20250429.pdf"
    src.write_bytes(b"%PDF")
    out = intake.propose(src, ds)
    assert out["matched_key"] == "nfa_rapidresponse"
    assert called == []


def test_a_browser_named_file_reaches_the_body_clue(tmp_path, monkeypatch):
    monkeypatch.setattr(intake, "body_text",
                        lambda p, pages=3: "비상소화장치 설치 및 관리 예규")
    src = tmp_path / "행정규칙 인쇄 _ 국가법령정보센터.pdf"
    src.write_bytes(b"%PDF")
    out = intake.propose(src, DS)
    assert out["matched_key"] == "hydrantdevice_rule"
    assert out["suggest"].endswith("hydrantdevice-rule_kr_20220523.pdf")


def test_a_batch_zip_in_the_inbox_is_never_matched(tmp_path, monkeypatch):
    """배치 zip 은 글자가 0 이라 본문 단서에서도 안 걸린다."""
    monkeypatch.setattr(intake, "body_text", lambda p, pages=3: "")
    src = tmp_path / "fire-lane-batch-1005ze.zip"
    src.write_bytes(b"PK")
    out = intake.propose(src, DS)
    assert out["matched_key"] is None
    assert out["suggest"] is None
