#!/usr/bin/env python3
"""
test_intake_rules.py — 획득 규칙 삼종의 강제자.

    firelane.scope      스코프 통제 어휘
    firelane.naming     파일명 문법
    firelane.encoding   인코딩 판별

★ 이 셋은 raw 없이 검증된다. 순수 함수이고, 그래서 CI 에서 돈다.
  `test_contract.py` 는 raw 2.6GB 가 붙은 기계에서만 도는데 그 말은
  **규칙 위반이 그 기계에서만 잡힌다**는 뜻이다. 문법은 CI 에서 잡는다.
"""
from __future__ import annotations

import pytest

from firelane import encoding as enc
from firelane import naming as nm
from firelane import scope as sc


# ── 스코프 ────────────────────────────────────────────────────
def test_scope_chain_is_ordered():
    assert sc.chain("jngj-dong-dm") == ["jngj-dong-dm", "jngj-dong", "jngj", "kr"]


def test_scope_containment():
    assert sc.contains("kr", "jngj-dong-dm")
    assert sc.contains("jngj-dong-dm", "jngj-dong-dm")
    assert not sc.contains("jngj-dong-dm", "kr")


def test_project_coverage():
    """전국·시도·시군구 자료는 동명동을 덮는다. 반대는 아니다."""
    assert sc.covers_project("kr")
    assert sc.covers_project("jngj-dong")
    assert not sc.covers_project("jngj-dong-dm", target="jngj-dong")


def test_unknown_scope_is_loud():
    with pytest.raises(sc.ScopeError):
        sc.resolve("mokpo")


def test_legacy_tokens_resolve_but_flag():
    for tok in ("gjdonggu", "dongu"):
        alias, state = sc.resolve(tok)
        assert alias == "jngj-dong"
        assert state == "legacy"


def test_gj_dong_is_not_a_scope():
    """★ 동부소방서는 행정구역이 아니다. 별칭을 주면 그 사실이 지워진다."""
    assert "gj_dong" not in sc.LEGACY
    with pytest.raises(sc.ScopeError):
        sc.resolve("gj_dong")


def test_map_sheet_tokens_are_flagged_as_part():
    for tok in ("gj9708", "gj35616", "gj037"):
        _, state = sc.resolve(tok)
        assert state == "part"


# ── 파일명 ────────────────────────────────────────────────────
def test_parse_canonical():
    n = nm.parse("juso_elctrnmap_jngj_20260711.zip", folder="juso")
    assert (n.provider, n.dataset, n.scope, n.vintage, n.ext) == (
        "juso", "elctrnmap", "jngj", "20260711", "zip")
    assert n.clean


def test_dataset_may_contain_underscores():
    """오른쪽부터 파싱하는 이유. 기존 36건을 개명하지 않기 위해서다."""
    n = nm.parse("safety_kfs_ambulance_special_kr_20251224.hwpx")
    assert n.dataset == "kfs_ambulance_special"
    assert n.scope == "kr"


def test_part_field_is_separated_from_scope():
    n = nm.parse("ngii_ortho_jngj-dong_20251231_35616037.tif")
    assert n.scope == "jngj-dong"
    assert n.part == "35616037"


def test_revision_suffix():
    n = nm.parse("its_nodelink_kr_20260812_r2.zip")
    assert n.rev == 2 and n.vintage == "20260812"


def test_roundtrip():
    for s in ("juso_elctrnmap_jngj_20260711.zip",
              "safety_kfs_pumptruck_kr_20251224.hwpx",
              "ngii_ortho_jngj-dong_20251231_35616037.tif",
              "its_nodelink_kr_20260812_r2.zip"):
        assert nm.parse(s).filename() == s


def test_missing_scope_rejected():
    """전국 자료도 `kr` 을 적는다. 생략과 누락은 구분되어야 한다."""
    with pytest.raises(nm.NameError_, match="최소 4개"):
        nm.parse("safety_cctv_20260630.csv")


def test_hangul_filename_rejected():
    with pytest.raises(nm.NameError_, match="한글"):
        nm.parse("safety_소방펌프차_kr_20251224.hwpx")


def test_uppercase_rejected():
    with pytest.raises(nm.NameError_, match="대문자"):
        nm.parse("Safety_cctv_jngj_20260630.csv")


def test_folder_provider_mismatch_rejected():
    with pytest.raises(nm.NameError_, match="폴더"):
        nm.parse("safety_cctv_jngj_20260630.csv", folder="gjcity")


def test_bad_vintage_rejected():
    with pytest.raises(nm.NameError_, match="달력"):
        nm.parse("safety_cctv_jngj_20261340.csv")


def test_wildcard_rejected_in_parse():
    with pytest.raises(nm.NameError_, match="와일드카드"):
        nm.parse("safety_kfs_pumptruck_kr_20251224.*")


# ── 확장자 ────────────────────────────────────────────────────
def test_ext_alias():
    assert nm.normalize_ext("a_b_kr_2020.JPEG") == "a_b_kr_2020.jpg"
    assert nm.normalize_ext("a_b_kr_2020.TIFF") == "a_b_kr_2020.tif"


def test_double_ext_kept_whole():
    assert nm.split_ext("a_b_kr_2020.tar.gz")[1] == "tar.gz"


def test_document_formats_are_not_merged():
    """★ .hwpx 와 .pdf 는 같은 자산이 아니다. 뭉개면 hits[0] 이 뒤집힌다."""
    a = nm.parse("safety_mas_vehicle_spec_kr_20241111.hwp")
    b = nm.parse("safety_mas_vehicle_spec_kr_20241111.pdf")
    assert a.ext != b.ext
    assert a.filename() != b.filename()


# ── 대장 패턴 ─────────────────────────────────────────────────
def test_extension_wildcard_is_a_violation():
    bad = nm.audit_pattern("safety/safety_kfs_pumptruck_20251224.*")
    assert any("확장자에 와일드카드" in x for x in bad)


def test_sane_pattern_passes():
    assert nm.audit_pattern("juso/juso_elctrnmap_jngj_20260711.zip") == []


def test_glob_without_provider_prefix_is_flagged():
    assert nm.audit_pattern("gjcity/*streetlight*.csv")


# ── 인코딩 ────────────────────────────────────────────────────
def _w(tmp_path, name, data: bytes):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_utf8_detected(tmp_path):
    p = _w(tmp_path, "a.csv", "위도,경도\n35.1,126.9\n".encode())
    v = enc.detect(p)
    assert v.encoding == "utf-8" and v.confidence == "strong" and not v.bom


def test_bom_detected(tmp_path):
    p = _w(tmp_path, "a.csv", "\ufeff건물명,높이\n".encode("utf-8-sig"))
    v = enc.detect(p)
    assert v.encoding == "utf-8-sig" and v.bom


def test_cp949_detected(tmp_path):
    p = _w(tmp_path, "a.csv", "위도,경도,소재지도로명주소\n".encode("cp949"))
    v = enc.detect(p)
    assert v.encoding == "cp949" and v.confidence == "strong"
    assert v.hangul_ratio > 0


def test_cp949_decode_success_is_not_evidence(tmp_path):
    """★ 이 테스트가 이 모듈의 존재 이유다.

    b"\xa1\xa1" 은 UTF-8 로는 못 읽고 CP949 로는 전각공백으로 잘 읽힌다.
    **디코드는 성공하는데 한글이 없다.** 그러면 증거가 아니다.
    """
    p = _w(tmp_path, "a.bin", b"\xa1\xa1" * 40)
    v = enc.detect(p)
    assert v.confidence == "none"
    assert v.encoding is None


def test_ascii_only_is_not_claimed_as_utf8(tmp_path):
    """ASCII 는 넷 모두와 호환이다. utf-8 이라 단정하면 cp949 선언이
    오탐으로 잡힌다."""
    p = _w(tmp_path, "a.csv", b"lat,lon\n35.1,126.9\n")
    assert enc.detect(p).encoding == "ascii"
    assert enc.verify_declared(p, "cp949") == []


def test_mojibake_is_flagged(tmp_path):
    """UTF-8 바이트를 CP949 로 읽어 저장해버린 파일.

    ★ 무서운 점 — 결과 문자열에 `쐞` `룄` 같은 **진짜 한글 음절**이 섞인다.
      한글 비율만 보면 정상 CP949 로 보인다. U+FFFD 지문으로 잡는다.
    """
    broken = "위도,경도,소재지".encode("cp949").decode("utf-8", errors="replace")
    p = _w(tmp_path, "a.csv", broken.encode("utf-8") * 4)
    v = enc.detect(p)
    assert v.encoding == "utf-8"          # 문법적으로는 멀쩡한 UTF-8 이다
    assert any("U+FFFD" in n for n in v.notes), v.notes
    assert enc.verify_declared(p, "utf-8")    # 선언이 맞아도 문제로 올린다


def test_newline_detection(tmp_path):
    assert enc.detect(_w(tmp_path, "a.csv", b"a,b\r\nc,d\r\n")).newline == "crlf"
    assert enc.detect(_w(tmp_path, "b.csv", b"a,b\nc,d\n")).newline == "lf"
    assert enc.detect(_w(tmp_path, "c.csv", b"a,b\r\nc,d\n")).newline == "mixed"


def test_cp437_recovery():
    mangled = "동명동".encode("cp949").decode("cp437")
    assert enc.recover_cp437(mangled) == "동명동"


def test_declared_encoding_mismatch_is_reported(tmp_path):
    p = _w(tmp_path, "a.csv", "위도,경도\n".encode("cp949"))
    assert enc.verify_declared(p, "utf-8")
    assert enc.verify_declared(p, "cp949") == []


def test_euckr_alias_is_accepted(tmp_path):
    p = _w(tmp_path, "a.csv", "위도,경도\n".encode("cp949"))
    assert enc.verify_declared(p, "euc-kr") == []


def test_to_norm_changes_form_not_values(tmp_path):
    src = _w(tmp_path, "a.csv", "\ufeff위도,경도\r\n35.1, 126.9 \r\n".encode("utf-8-sig"))
    dst = tmp_path / "out" / "a.csv"
    meta = enc.to_norm(src, dst)
    got = dst.read_bytes()
    assert got.decode() == "위도,경도\n35.1, 126.9 \n"   # ★ 공백은 그대로다
    assert meta["dst_encoding"] == "utf-8" and meta["src_newline"] == "crlf"
    assert not got.startswith(b"\xef\xbb\xbf")
