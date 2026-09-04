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
    assert sc.chain("jngj-dongmyeong") == ["jngj-dongmyeong", "jngj-donggu", "jngj", "kr"]


def test_scope_containment():
    assert sc.contains("kr", "jngj-dongmyeong")
    assert sc.contains("jngj-dongmyeong", "jngj-dongmyeong")
    assert not sc.contains("jngj-dongmyeong", "kr")


def test_project_coverage():
    """전국·시도·시군구 자료는 동명동을 덮는다. 반대는 아니다."""
    assert sc.covers_project("kr")
    assert sc.covers_project("jngj-donggu")
    assert not sc.covers_project("jngj-dongmyeong", target="jngj-donggu")


def test_unknown_scope_is_loud():
    with pytest.raises(sc.ScopeError):
        sc.resolve("mokpo")


def test_legacy_tokens_resolve_but_flag():
    for tok in ("gjdonggu", "dongu"):
        alias, state = sc.resolve(tok)
        assert alias == "jngj-donggu"
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
    n = nm.parse("ngii_ortho_jngj-donggu_20251231_35616037.tif")
    assert n.scope == "jngj-donggu"
    assert n.part == "35616037"


def test_revision_suffix():
    n = nm.parse("its_nodelink_kr_20260812_r2.zip")
    assert n.rev == 2 and n.vintage == "20260812"


def test_roundtrip():
    for s in ("juso_elctrnmap_jngj_20260711.zip",
              "safety_kfs_pumptruck_kr_20251224.hwpx",
              "ngii_ortho_jngj-donggu_20251231_35616037.tif",
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


# ── pull_data — 순서가 자료구조인가 ───────────────────────────
#
# ★ 2026-08-31 신설(absorb 대상) · 2026-09-03 이관.
#   `absorb.py` 를 지우고 `pull_data.py` 로 합쳤다. 둘이 같은 네 단계를
#   각자 구현하고 있었고 README 는 absorb 를, MASTER §18-11 은 pull_data 를
#   "입구 하나" 로 선언했다 — **정본이 둘이었다.**
#
#   남긴 쪽은 pull_data 다. 상위집합이고(prep·judge 포함) MASTER 가
#   정본으로 지목한다. 대신 absorb 의 `needs=` 게이트를 그대로 가져왔다 —
#   **방어가 강한 쪽의 설계를 남긴다.**
#
#   묶는 것 자체가 위험을 만든다. 순서가 주석으로만 있으면 나중에 한 줄
#   옮기는 것으로 검증 없이 landing 원본을 지울 수 있다. landing 은
#   윈도우 Downloads 사본이고 그것을 지우면 되돌릴 데가 없다.
import importlib.util
import types
from pathlib import Path


def _pull():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "pull_data", root / "tools/pull_data.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _plan(m, **kw):
    a = types.SimpleNamespace(keep_landing=False, all=False, **kw)
    return {s.name: s for s in m.steps(a)}


def test_prune_needs_verify():
    """삭제는 검증에 매달려 있어야 한다. 주석이 아니라 선언으로."""
    m = _pull()
    assert _plan(m)["prune"].needs == "verify", (
        "prune 의 needs 가 verify 가 아니다.\n"
        "  검증 없이 landing 원본을 지우면 되돌릴 데가 없다.")


def test_stage_and_quarantine_hang_off_earlier_steps():
    """편입·격리도 앞 단계에 매달린다. 게이트가 prune 하나만이 아니다."""
    p = _plan(_pull())
    assert p["stage"].needs == "intake"
    assert p["verify"].needs == "stage"
    assert p["quarantine"].needs == "stage"


def test_gate_distinguishes_not_run_from_failed():
    """안 돈 것(None)과 실패한 것(≠0)을 구분하는가.

    ★ None 을 0 으로 읽으면 "안 돌았다" 가 "성공했다" 가 된다. 게이트가
      뚫리는 가장 흔한 방식이다.
    """
    src = (Path(__file__).resolve().parents[1]
           / "tools/pull_data.py").read_text(encoding="utf-8")
    assert "prev is None" in src, (
        "pull_data 가 선행 결과의 None 을 따로 보지 않는다.\n"
        "  `seen.get(name)` 이 None 이면 안 돈 것이고 0 이 아니다.")


def test_keep_landing_removes_prune_not_the_gate():
    """--keep-landing 은 prune 을 빼는 것이지 게이트를 푸는 것이 아니다."""
    m = _pull()
    p = _plan(m, )
    assert "prune" in p
    a = types.SimpleNamespace(keep_landing=True, all=False)
    names = {s.name for s in m.steps(a)}
    assert "prune" not in names
    assert {"verify", "quarantine"} <= names, (
        "--keep-landing 이 prune 말고 다른 단계까지 뺐다.")


def test_pull_data_does_not_reimplement_acquire():
    """반입 체인이 sha 비교나 세 판정을 자기 안에 다시 쓰면 정본이 둘이 된다.

    ★ absorb 를 지운 이유가 그것이다. 같은 일을 하는 두 번째 구현은
      반드시 어긋난다.
    """
    src = (Path(__file__).resolve().parents[1]
           / "tools/pull_data.py").read_text(encoding="utf-8")
    for banned in ("shutil.move", "shutil.copy", "os.remove", "unlink(",
                   "hashlib"):
        assert banned not in src, (
            f"pull_data.py 가 {banned} 로 직접 실물을 움직인다.\n"
            "  반입 체인은 부르기만 한다. 실물은 acquire·intake 가 만진다.")


def test_absorb_is_gone():
    """absorb.py 가 되살아나면 정본이 다시 둘이 된다. **역방향이다.**"""
    root = Path(__file__).resolve().parents[1]
    assert not (root / "tools/absorb.py").exists(), (
        "tools/absorb.py 가 다시 생겼다.\n"
        "  반입 입구는 pull_data.py 하나다(MASTER §18-11).")


def test_dry_run_never_passes_a_confirm_flag():
    """`--yes` 없이는 어떤 단계도 파괴적 인자를 받지 않는다.

    ★ 2026-09-03. `--yes` 를 `steps()` 의 argv 에 박아두고 있었다. 그러면
      관측 모드 필터(`only_yes`)와 argv 의 `--yes` 를 **사람이 맞춰야 하고**,
      어긋나면 관측 모드가 파괴 명령을 돈다. 붙일 수 없게 만드는 것이
      규율보다 낫다 — `argv(apply)` 가 유일한 부착 지점이다.
    """
    m = _pull()
    for s in _plan(m).values():
        assert "--yes" not in s.cmd, (
            f"{s.name} 의 cmd 에 --yes 가 박혀 있다.\n"
            "  확인 인자는 Step.argv(apply) 가 붙인다.")
        assert "--yes" not in s.argv(False), (
            f"관측 모드인데 {s.name} 이 --yes 를 받는다: {s.argv(False)}")


def test_confirm_flag_matches_what_the_tool_accepts():
    """확인 인자가 도구마다 다르다. 없는 인자를 붙이면 argparse 가 죽는다.

    ★ `firelane.prep` 은 `--apply` 자체가 확인이라 `--yes` 를 안 받는다.
      그 실패는 게이트가 아니라 오타이므로 게이트처럼 보이면 안 된다.
    """
    m = _pull()
    a = types.SimpleNamespace(keep_landing=False, all=True)
    for s in m.steps(a):
        if s.confirm is None:
            assert "--yes" not in s.argv(True), f"{s.name}"
        elif s.mutating:
            assert s.argv(True)[-1] == s.confirm, f"{s.name}"


def test_observation_mode_does_not_trip_the_gate():
    """관측 모드는 비파괴 단계만 돈다. 걸러진 선행 단계로 멈추면 안 된다.

    ★ 2026-09-03 회귀. `needs` 게이트를 붙이면서 관측 모드를 안 봤다.
      `verify.needs="stage"` 인데 관측 모드는 `stage` 를 거르므로
      "선행이 안 돌았다" 로 즉시 멈췄다. **게이트는 옳고 범위가 틀렸다.**
    """
    src = (Path(__file__).resolve().parents[1]
           / "tools/pull_data.py").read_text(encoding="utf-8")
    assert "if a.yes and s.needs is not None:" in src, (
        "게이트가 --yes 여부와 무관하게 걸린다.\n"
        "  관측 모드에서는 선행이 걸러지므로 게이트를 걸지 않는다.")


def test_observation_mode_keeps_only_non_mutating_steps():
    """관측 모드에 남는 것이 전부 비파괴인가."""
    m = _pull()
    a = types.SimpleNamespace(keep_landing=False, all=False)
    obs = [s for s in m.steps(a) if not s.mutating]
    assert {s.name for s in obs} == {"verify", "judge", "prep-check"}, (
        f"관측 단계 구성이 바뀌었다: {[s.name for s in obs]}")
    for s in obs:
        assert "--yes" not in s.argv(True), f"{s.name} 이 파괴 인자를 받는다"
