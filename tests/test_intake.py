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
# ★ 2026-10-08 (DECISIONS §431 · PLAN #157). 단서 ①②③ 이 `intake_name` 으로,
#   ④ 는 그 앞서 `intake_body` 로 떨어져 나갔다. **갈아끼우는 자리가 거기다** —
#   `propose()` 가 제 모듈 전역에서 `body_text` 를 찾으므로 `intake` 쪽을
#   패치하면 아무 일도 안 일어난다. 조용히 통과하는 시험이 제일 나쁘다.
from firelane import intake_name as iname

assert iname.body_match is not None
assert intake.propose is iname.propose, \
    "도구가 `propose` 를 제 것으로 다시 정의했다 — 정본이 둘이다"

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
    from firelane.intake_body import body_marks
    m = body_marks(DS)
    assert "국가법령정보센터" not in m["roadtraffic_act"]   # BODY_STOP 이기도 하다
    assert "도로교통법" in m["roadtraffic_act"]
    assert "비상소화장치" in m["hydrantdevice_rule"]
    assert not (m["roadtraffic_act"] & m["hydrantdevice_rule"])


def test_a_clear_body_picks_its_entry():
    key, why = iname.body_match("비상소화장치 설치 및 관리 예규", DS)
    assert key == "hydrantdevice_rule"
    assert "맞는다" in why


def test_one_matching_word_is_not_a_match():
    key, why = iname.body_match("비상소화장치", DS)
    assert key is None
    assert "바닥" in why


def test_a_body_that_fits_two_entries_is_refused():
    """1등과 2등이 붙어 있으면 **안 고른다** — 반반 맞히지 않는다."""
    ds = {"a": {"what": "소화전 배치 지도", "files": ["x/a.pdf"]},
          "b": {"what": "소화전 배치 지도", "files": ["x/b.pdf"]}}
    key, why = iname.body_match("소화전 배치 지도", ds)
    assert key is None


def test_an_empty_body_is_not_a_match():
    key, why = iname.body_match("", DS)
    assert key is None
    assert "못 읽었다" in why


def test_two_articles_of_one_law_are_split_by_the_printed_url():
    """같은 법령 인쇄본 둘은 점수가 같다 — **조 번호만이 가른다.**"""
    e = DS["roadtraffic_act"]
    a30, why = iname.body_file_of("… lsBdyPrint.do?efYd=20260701&joNo=0030", e)
    assert a30.endswith("_a30.pdf")
    assert "제30조" in why
    a29, _ = iname.body_file_of("… joNo=0029", e)
    assert a29.endswith("_a29.pdf")


def test_without_an_article_number_neither_file_is_chosen():
    rel, why = iname.body_file_of("도로교통법 긴급자동차 특례", DS["roadtraffic_act"])
    assert rel is None
    assert "못 가른다" in why


def test_a_single_declared_file_needs_no_article_number():
    rel, why = iname.body_file_of("아무 글자", DS["hydrantdevice_rule"])
    assert rel.endswith("hydrantdevice-rule_kr_20220523.pdf")
    assert "하나" in why


def test_an_entry_that_declares_nothing_is_not_guessed():
    """아무것도 선언 안 한 항목은 **추측하지 않는다.**

    ★ 2026-10-07 (DECISIONS §430). 이름과 메시지에서 `files` 를 뺐다.
      `files` 는 2026-08-31 뒤로 **선언 수단 하나일 뿐**이고(`stem`+`ext` 가
      정본이다), 그 낱말로 못 박으면 **`stem` 식 예순여섯 종이 "선언 없음"
      으로 떨어지는 그 결함**을 시험이 지켜 주는 꼴이 된다. 실제로 그랬다.
      `stem` 식이 집히는지는 `tests/test_ledger_accessor.py` 가 든다.
    """
    rel, why = iname.body_file_of("아무 글자", {"what": "무엇"})
    assert rel is None
    assert "안 선언" in why


@pytest.mark.parametrize("name", ["x.zip", "x.csv", "x.hwp"])
def test_body_text_refuses_everything_that_is_not_a_pdf(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"\x00\x01")
    assert iname.body_text(p) == ""


def test_a_broken_pdf_does_not_stop_the_intake(tmp_path):
    """못 읽는 파일 하나가 취입 전체를 멈추면 안 된다."""
    p = tmp_path / "broken.pdf"
    p.write_bytes(b"not really a pdf")
    assert iname.body_text(p) == ""


def test_the_body_clue_only_runs_when_the_name_said_nothing(tmp_path, monkeypatch):
    """단서 ④ 는 **마지막**이다 — 이름으로 맞은 것을 본문이 덮지 않는다."""
    called = []
    monkeypatch.setattr(iname, "body_text",
                        lambda p, pages=3: called.append(p) or "")
    ds = {"nfa_rapidresponse": {"stem": "nfa_rapidresponse", "provider": "nfa",
                                "what": "119패스", "files": ["nfa/x.pdf"]}}
    src = tmp_path / "nfa_rapidresponse_kr_20250429.pdf"
    src.write_bytes(b"%PDF")
    out = iname.propose(src, ds)
    assert out["matched_key"] == "nfa_rapidresponse"
    assert called == []


def test_a_browser_named_file_reaches_the_body_clue(tmp_path, monkeypatch):
    monkeypatch.setattr(iname, "body_text",
                        lambda p, pages=3: "비상소화장치 설치 및 관리 예규")
    src = tmp_path / "행정규칙 인쇄 _ 국가법령정보센터.pdf"
    src.write_bytes(b"%PDF")
    out = iname.propose(src, DS)
    assert out["matched_key"] == "hydrantdevice_rule"
    assert out["suggest"].endswith("hydrantdevice-rule_kr_20220523.pdf")


def test_a_batch_zip_in_the_inbox_is_never_matched(tmp_path, monkeypatch):
    """배치 zip 은 글자가 0 이라 본문 단서에서도 안 걸린다."""
    monkeypatch.setattr(iname, "body_text", lambda p, pages=3: "")
    src = tmp_path / "fire-lane-batch-1005ze.zip"
    src.write_bytes(b"PK")
    out = iname.propose(src, DS)
    assert out["matched_key"] is None
    assert out["suggest"] is None


# ── 방아쇠는 대장이다  (DECISIONS §401) ────────────────────────
#
# ★ 사람이 실물로 잡았다 — 다운로드 폴더에 배치 zip · 남의 패치 · 채용공고가
#   같이 사는데 도구가 그 전부에 대고 「대장에 항목을 만들어라」라고 말했다.
#   「이상한거 까지 다 들어갔잖아」. 방향이 반대였다.
LEDGER = {
    "roadtraffic_act": {
        "what": "도로교통법 긴급자동차 특례 조문", "authority": "국가법령정보센터",
        "files": ["moleg/moleg_roadtraffic-act_kr_20260701_a29.pdf",
                  "moleg/moleg_roadtraffic-act_kr_20260701_a30.pdf"],
    },
    "gone": {"status": "missing", "missing_why": "상폐", "what": "없다",
             "files": ["x/y.pdf"]},
}


def test_the_trigger_is_the_ledger_not_the_folder(monkeypatch, tmp_path):
    """결손이 0 이면 다운로드 폴더를 **열지도 않는다.**"""
    raw = tmp_path / "raw"
    (raw / "moleg").mkdir(parents=True)
    for n in ("a29", "a30"):
        (raw / "moleg" / f"moleg_roadtraffic-act_kr_20260701_{n}.pdf").write_bytes(b"x")
    monkeypatch.setattr(intake, "RAW", raw, raising=False)
    import firelane.paths as fp
    monkeypatch.setattr(fp, "RAW", raw)
    assert intake.waiting(LEDGER) == []


def test_a_retired_entry_is_not_waiting(monkeypatch, tmp_path):
    raw = tmp_path / "raw"; raw.mkdir()
    import firelane.paths as fp
    monkeypatch.setattr(fp, "RAW", raw)
    assert "gone" not in {k for k, _ in intake.waiting(LEDGER)}


def test_a_person_can_override_the_guess_by_number(tmp_path, monkeypatch):
    """`--assign N=조각` — 대장이 이름을 아는데 추측기와 싸울 이유가 없다."""
    box = tmp_path / "inbox"; box.mkdir()
    for n in ("법령 _ 국가법령정보센터.pdf", "인쇄 _ 국가법령정보센터.pdf"):
        (box / n).write_bytes(b"%PDF")
    raw = tmp_path / "raw"; raw.mkdir()
    import firelane.paths as fp
    monkeypatch.setattr(fp, "RAW", raw)
    monkeypatch.setattr(iname, "body_text", lambda p, pages=3: "")
    want = intake.waiting(LEDGER)
    a29 = intake._match_one(box, LEDGER, *want[0], ["1=법령 _"])
    assert a29 is not None and a29.name.startswith("법령")


def test_an_ambiguous_fragment_picks_nothing(tmp_path, monkeypatch):
    box = tmp_path / "inbox"; box.mkdir()
    for n in ("국가법령 1.pdf", "국가법령 2.pdf"):
        (box / n).write_bytes(b"%PDF")
    raw = tmp_path / "raw"; raw.mkdir()
    import firelane.paths as fp
    monkeypatch.setattr(fp, "RAW", raw)
    monkeypatch.setattr(iname, "body_text", lambda p, pages=3: "")
    want = intake.waiting(LEDGER)
    assert intake._match_one(box, LEDGER, *want[0], ["1=국가법령"]) is None


# ── 단서 넷을 전부 쓴다 (DECISIONS §431) ────────────────────────
def test_the_planner_uses_the_naming_rules_not_only_the_body(tmp_path, monkeypatch):
    """★ **사람이 `--assign` 을 네 번 친 자리.**  (DECISIONS §431)

    `body_text` 는 PDF 가 아니면 빈 문자열이다. 그래서 자리 고르기가 단서 ④만
    쓰면 **zip · csv 는 영영 못 맞춘다** — `normalize_raw.RULES` 가 그 이름을
    전부 알고 있는데도. 2026-10-08 실측에서 다섯 중 PDF 하나만 붙었다.
    """
    import firelane.paths as fp

    (raw := tmp_path / "raw").mkdir()
    monkeypatch.setattr(fp, "RAW", raw)
    inb = tmp_path / "dl"; inb.mkdir()
    for n in ("C_UQ153.zip", "LSMD_CONT_UQ164_5174_전남광주통합특별시.zip",
              "15. 도로대장_20261006153718.csv", "202608_상세주소DB_전체분.zip"):
        (inb / n).write_bytes(b"PK\x03\x04")

    ds = intake.sources_index()
    files = sorted(q for q in inb.iterdir())
    for key, want in (("vworld_uq153", "C_UQ153.zip"),
                      ("vworld_uq164", "LSMD_CONT_UQ164_5174_전남광주통합특별시.zip"),
                      ("eais_roadledger_dm", "15. 도로대장_20261006153718.csv"),
                      ("juso_adrdc", "202608_상세주소DB_전체분.zip")):
        pat = intake._led.globs(ds[key])[0]
        got, why = intake._pick(files, ds, key, pat)
        assert got is not None and got.name == want, f"{key}: {got} ({why})"
        assert "규칙" in why or "stem" in why, f"{key}: 본문으로 맞췄다 — {why}"


def test_a_download_the_ledger_does_not_wait_for_is_not_picked(tmp_path, monkeypatch):
    """★ 반대 방향. 대장이 안 기다리는 파일은 **안 집는다**(§401)."""
    import firelane.paths as fp

    (raw := tmp_path / "raw").mkdir()
    monkeypatch.setattr(fp, "RAW", raw)
    inb = tmp_path / "dl"; inb.mkdir()
    (inb / "채용공고.pdf").write_bytes(b"%PDF-1.4\n")
    (inb / "fire-lane-batch-1008zj.zip").write_bytes(b"PK\x03\x04")
    ds = intake.sources_index()
    files = sorted(q for q in inb.iterdir())
    got, _ = intake._pick(files, ds, "vworld_uq153", "**/vworld_uq153_*")
    assert got is None, f"남의 파일을 집었다 — {got}"


# ── 이름 둘 — 시험이 이름을 안 부르고 있었다 (DECISIONS §493) ──
# ★ `tools/srccov.py` 가 `rule_path` · `stem_of` 를 셌다. 둘은 단서 ①② 의
#   입구이고, 아래 ④ 본문 시험들은 그 둘을 **지나쳐** 간다.
def test_rule_path_matches_lowercase_like_the_tool_does():
    """★ 대소문자. 2026-09-07 에 **대문자가 든 파일명만** 관문에 막혔다.

    `normalize_raw.main()` 은 `low = f.name.lower()` 로 맞추는데 여기가
    원본 그대로 맞춰서 `건물DB` · `CCTV정보` · `GJBG_LSI…` 가 전부
    「대장에 없다」로 떨어졌다. 두 곳이 **같은 방식**으로 맞춰야 한다.
    """
    got = iname.rule_path("CCTV정보_전남광주동구.csv")
    assert got == "gjcity/gjcity_admin_cctv_jngj-donggu_20200814.csv", got
    # 소문자 원본도 같은 자리로 간다 — 맞추기가 대소문자에 안 걸린다
    assert iname.rule_path("cctv정보_전남광주동구.csv") == got


def test_rule_path_fills_the_captured_groups():
    """자리표가 있는 규칙은 **잡은 것을 끼워** 경로를 낸다."""
    got = iname.rule_path("전남광주통합특별시 동구_불법 주정차 단속현황_20240108.csv")
    assert got == "gjcity/gjcity_parking_enforce_jngj-donggu_20240108.csv", got
    # 날짜가 바뀌면 자리도 따라 바뀐다 — 고정 문자열이 아니다
    assert iname.rule_path(
        "전남광주통합특별시 동구_불법 주정차_20250226.csv") == (
        "gjcity/gjcity_parking_enforce_jngj-donggu_20250226.csv")


def test_rule_path_is_silent_for_a_file_no_rule_claims():
    """★ 음성 — 규칙이 없으면 `None` 이다. **추측해서 두지 않는다.**"""
    for n in ("채용공고.pdf", "", "스크린샷 2026-10-12.png", "noname"):
        assert iname.rule_path(n) is None, f"{n!r} 를 어딘가에 두려 한다"


def test_stem_of_strips_the_scope_and_the_vintage():
    """raw 상대경로 → `provider_dataset`. 대장 `stem` 과 **같은 글자**여야 한다."""
    for rel, want in (
            ("safety/safety_cctv_jngj_20260630.csv", "safety_cctv"),
            ("juso/juso_adrdc_kr_202608.zip", "juso_adrdc"),
            ("gjcity/gjcity_parking_enforce_jngj-donggu_20240108.csv",
             "gjcity_parking_enforce"),
            # 도엽(part)이 뒤에 붙어도 줄기는 같다
            ("ngii/ngii_basemap_jngj-donggu_20260812_gj9708.zip", "ngii_basemap"),
            ("ngii/ngii_ortho_jngj-donggu_20251231_gj037.tif", "ngii_ortho"),
    ):
        assert iname.stem_of(rel) == want, f"{rel} → {iname.stem_of(rel)!r}"


def test_stem_of_agrees_with_the_ledger_for_every_real_file():
    """★ **실물 전수로 민다.** 대장이 적은 stem 과 어긋나면 반입이 못 짝짓는다.

    손으로 적은 표가 아니라 `data/_acquire.json`(raw 실물) 에서 가져온다 —
    §494 가 같은 날 두 자리에서 걷은 그 병이다(사본을 사본과 대조한다).
    """
    import json

    from firelane import ledger as L

    stems = set()
    for e in L.load()["datasets"].values():
        if e.get("stem"):
            stems.add(str(e["stem"]))
        stems.update(str(x) for x in (e.get("stems") or []))
    raw = sorted(json.loads(
        (ROOT / "data/_acquire.json").read_text(encoding="utf-8"))["files"])
    assert len(raw) > 50, "실물 목록이 비었다 — 이 검사가 빈 그물이 됐다"
    bad = [f"  {p} → {iname.stem_of(p)!r}" for p in raw
           if iname.stem_of(p) not in stems]
    assert not bad, (
        "줄기가 대장의 어느 stem 과도 같지 않다 — 반입이 그 파일을 못 짝짓는다.\n"
        + "\n".join(bad))
