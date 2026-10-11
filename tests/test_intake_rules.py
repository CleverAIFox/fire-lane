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

import sys

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


# ── 한글 판별 · 토큰 제안 (DECISIONS §493) ────────────────────
# ★ `has_hangul` · `slugify` 를 **시험이 이름으로도 안 부르고 있었다**
#   (`tools/srccov.py` 가 셌다). 둘은 파일명 관문의 입구이고, 느슨해지면
#   관문이 조용히 통과시킨다.
def test_decomposed_hangul_is_hangul():
    """★ NFD(자모 분해)도 한글이다 — 맥OS·일부 zip 이 그렇게 적는다.

    종전에는 `[가-힣]` 로 받은 글자를 그대로 봐서 분해본이 **하나도 안
    걸렸다.** 문법은 뒤에서 막았지만(아스키만 받는다) 나오는 말이
    「dataset 이 문법 밖이다」였고, 그 말로는 무엇을 해야 하는지 모른다.
    """
    import unicodedata

    nfd = unicodedata.normalize("NFD", "한글")
    assert len(nfd) == 6, "전제 — NFD 가 실제로 자모로 쪼개졌다"
    assert nm.has_hangul(nfd), "분해된 한글을 한글로 안 센다"
    # ★ 관문이 **옳은 말**을 하는가. 아스키 정규식이 뒤에서 막는 것과 다르다
    with pytest.raises(nm.NameError_, match="한글"):
        nm.parse(f"safety_{nfd}_jngj_20260101.csv")


def test_lone_jamo_counts_as_hangul():
    """낱자도 한글이다. 자료제공 파일명에 절판 표지로 실제로 들어온다."""
    for ch in ("ㄱ", "ㅎ", "ㅏ", "ㅣ"):
        assert nm.has_hangul(f"a{ch}b"), f"{ch!r} 를 한글로 안 센다"


def test_the_hangul_ruler_is_one():
    """★ 한글 자가 **한 벌인가.** 두 벌이면 한쪽만 넓어지는 날이 온다."""
    for ch in ("가", "힣", "ㄱ", "ㅎ", "ㅏ", "ㅣ"):
        assert bool(nm._HANGUL.search(ch)) == bool(enc.HANGUL.search(ch)), (
            f"{ch!r} 를 naming 과 encoding 이 다르게 센다")


def test_ascii_is_not_hangul():
    """★ 음성 — 아스키·한자·전각을 한글로 세면 정상 파일이 막힌다."""
    for t in ("safety_cctv_jngj", "", "123", "漢字", "ＡＢＣ"):
        assert not nm.has_hangul(t), f"{t!r} 를 한글로 센다"


def test_slugify_suggests_a_token_and_does_not_romanize():
    """★ 음역하지 않는다 — 머리말이 적은 그 선택을 못박는다.

    `소방펌프차` → `sobangpeompeuca` 가 되면 대장의 `kfs_pumptruck` 과
    아무 관계 없는 이름이 생긴다. 그래서 **한글을 그대로 둔다**.
    """
    assert nm.slugify("소방펌프차 현황(2026)") == "소방펌프차_현황"
    assert nm.slugify("  Road Ledger v2.1 .csv ") == "road_ledger_v2_1_csv"
    # NFKC — 전각·동글이숫자를 모은다
    assert nm.slugify("ＣＣＴＶ") == "cctv"
    assert nm.slugify("①번") == "1번"


def test_slugify_output_is_only_a_proposal():
    """★ **제안은 문법이 아니다.** 한글이 남은 제안은 그대로 쓰면 막힌다.

    이것이 결함이 아니라 설계다(사람이 정한다 — 머리말). 그러나
    **자동 채택하는 호출부가 생기면** 그 호출부가 `parse` 에서 운다.
    그 꼴을 여기 적어 둔다.
    """
    tok = nm.slugify("소방펌프차")
    assert nm.has_hangul(tok), "전제 — 제안에 한글이 남는다"
    with pytest.raises(nm.NameError_, match="한글"):
        nm.parse(f"safety_{tok}_kr_20251224.hwp")


def test_slugify_never_leaves_edge_underscores():
    """`_` 로 시작·끝나는 토큰은 `DATASET_RE` 가 막는다. 제안이 만들지 않는다."""
    for t in ("(2026)", "___", "", " - - ", "...csv"):
        g = nm.slugify(t)
        assert g == g.strip("_"), f"{t!r} → {g!r}"
        assert "__" not in g, f"{t!r} → {g!r}"


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


def test_bom_order_puts_utf32_before_utf16():
    """★ `BOMS` 의 **순서가 판정이다.** 뒤집히면 UTF-32 가 UTF-16 이 된다.

    UTF-32LE 의 BOM 은 `ff fe 00 00` 이고 그 앞 두 바이트가 곧 UTF-16LE
    의 BOM 이다. `sniff_bom` 은 사전 순서대로 훑으므로 **긴 것이 먼저**
    있어야 한다. 사전 리터럴을 보기 좋게 다시 늘어놓는 날, 그 한 줄이
    UTF-32 파일을 UTF-16 으로 읽게 만든다 — 디코드가 **성공**하고
    (널 바이트가 글자로 섞인다) 아무도 안 운다.
    """
    assert enc.sniff_bom(b"\xff\xfe\x00\x00abcd") == "utf-32"
    assert enc.sniff_bom(b"\x00\x00\xfe\xffabcd") == "utf-32"
    assert enc.sniff_bom(b"\xff\xfea\x00b\x00") == "utf-16"
    assert enc.sniff_bom(b"\xfe\xff\x00a\x00b") == "utf-16"
    assert enc.sniff_bom(b"\xef\xbb\xbf\xec\x9c\x84\xeb\x8f\x84") == "utf-8-sig"


def test_sniff_bom_is_silent_without_a_bom():
    """★ 음성 — BOM 이 없으면 `None` 이다. 추측하지 않는다."""
    for head in (b"", b"a", b"\xff", b"\x00\x00", b"\xec\x9c\x84",
                 b"PK\x03\x04", b"%PDF-1.4"):
        assert enc.sniff_bom(head) is None, f"{head!r} 에 BOM 이 있다고 한다"


def test_sniff_bom_names_a_codec_python_knows():
    """★ 낸 이름을 `detect` 가 **그대로 디코드에 쓴다**. 오타가 있으면 터진다."""
    import codecs

    for name in set(enc.BOMS.values()):
        codecs.lookup(name)       # 모르는 이름이면 LookupError


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
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
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


def test_the_syntax_allows_three_vintage_forms_but_the_norm_gate_takes_only_eight():
    """★ **선언 둘이 다른 수를 말한다** — 적어 두고 실물로 붙든다 (§494-5).

        `firelane.naming` 머리말 ·`VINTAGE_RE`   YYYYMMDD | YYYYMM | YYYY
        `layers.norm.naming`(`providers.pattern_file`)  `\\d{8}` **만**
        MASTER §18-2b 의 토큰표                 「**8자리**」

    셋 중 둘이 8 이고 하나가 셋을 받는다. 지금 실물은 **전부 8자리**라
    (`_acquire.json` 89건 · 대장 글롭 전건) 어긋남이 **잠복**해 있다 —
    월 단위로만 내는 원천이 처음 오는 날 깨어난다. 실제로 `RULES` 는 그
    자리를 이미 **01 로 채워서** 8자리를 만든다(`juso_adrdc_kr_{0}01.zip`).

    ★ 여기서 문법을 조이지 않는다. `naming` 이 raw 쪽에서 세 꼴을 받는 것은
      머리말이 **일부러** 적어 둔 선택이고, 그것을 밤에 혼자 뒤집으면
      「왜 받게 해 뒀나」가 사라진다. 대신 **두 선언의 차이를 못박는다** —
      월 단위 원천이 오면 이 시험이 그 자리를 가리킨다.
    """
    import re as _re

    from firelane import providers

    # ① 문법은 세 꼴을 받는다
    for v in ("20260630", "202606", "2026"):
        assert nm.parse(f"safety_cctv_jngj_{v}.csv").vintage == v

    # ② norm 관문은 8자리만 받는다 — 같은 이름 셋 중 하나만 통과한다
    rx = _re.compile(providers.pattern_file())
    passed = [v for v in ("20260630", "202606", "2026")
              if rx.match(f"safety/safety_cctv_jngj_{v}.csv")]
    assert passed == ["20260630"], f"관문이 받는 꼴이 바뀌었다 — {passed}"

    # ③ 그래서 지금 실물은 전부 8자리여야 한다. 하나라도 아니면 그 파일이
    #    문법은 통과하고 **관문에서 막힌다** — 이 차이가 깨어난 순간이다
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root / "data/_acquire.json").read_text(encoding="utf-8"))["files"]
    assert raw, "실물 목록이 비었다 — 이 검사가 빈 그물이 됐다"
    short = [p for p in sorted(raw)
             if not _re.search(r"_\d{8}(?=[._])", p.rsplit("/", 1)[-1])]
    assert not short, (
        "vintage 가 8자리가 아닌 실물이 생겼다 — **잠복한 어긋남이 깨어났다**:\n  "
        + "\n  ".join(short)
        + "\n  ★ 셋 중 하나를 고쳐야 한다 — 문법을 조이거나(8자리만),"
        "\n    관문을 넓히거나(`\\d{4,8}`), 반입이 01 로 채우거나."
        "\n    `RULES` 는 이미 세 번째를 한다(`juso_adrdc_kr_{0}01.zip`).")


# ── 정규명 산출 — 개명 규칙의 정본 (DECISIONS §496) ───────────
# ★ `naming.canonical` 은 **개명이 무엇으로 갈 것인가**를 혼자 정한다. 그
#   머리말이 2026-08-26 의 사고를 적는다: 「끝이 날짜면 그 앞이 스코프」라고
#   **추측**했다가 도엽번호와 관할서 뒤에 스코프를 또 박을 뻔했다 —
#   30건 중 **22건**이 그 오작동이었고 드라이런이 아니었으면 raw 가 망가졌다.
#
# ★ 그런데 `tools/srccov.py` 가 이 함수를 **입출력으로 가르고 있었다** —
#   `e.get("scope")` 의 `get` 하나 때문이다(§496). 그래서 「안 드는 순수
#   함수」 목록에 안 뜨고, 아무도 안 밀고 있었다.
def test_canonical_refuses_to_guess_when_the_ledger_is_silent():
    """★ 본체. 대장이 안 적으면 **None** 이다 — 2026-08-26 이 그 자리다."""
    # 도엽이 스코프 자리에 있는데 대장에 `scope` 가 없다 → 손대지 않는다
    assert nm.canonical("ngii/ngii_basemap_gj9708_20260812.zip", {}) is None
    # 스코프 토큰이 아예 없는데 대장도 모른다 → 손대지 않는다
    assert nm.canonical("its/its_nodelink_changelog_20260812.csv", {}) is None
    # 대장 스코프가 통제 어휘 밖이다 → 손대지 않는다
    assert nm.canonical("safety/safety_cctv_dongu_20260630.csv",
                        {"scope": "없는스코프"}) is None


def test_canonical_renames_a_legacy_scope_token():
    """옛 토큰은 대장이 적은 정규 스코프로 간다."""
    assert nm.canonical("safety/safety_cctv_dongu_20260630.csv",
                        {"scope": "jngj-donggu"}) == \
        "safety/safety_cctv_jngj-donggu_20260630.csv"


def test_canonical_moves_a_map_sheet_out_of_the_scope_slot():
    """★ 도엽은 스코프가 아니다 — **vintage 뒤 part** 로 옮긴다."""
    assert nm.canonical("ngii/ngii_basemap_gj9708_20260812.zip",
                        {"scope": "jngj-donggu"}) == \
        "ngii/ngii_basemap_jngj-donggu_20260812_gj9708.zip"


def test_canonical_needs_an_authority_before_it_drops_a_word():
    """★ `gj_dong` 은 **동부소방서**다 — 버리려면 대장이 그것을 받았어야 한다.

    관할기관은 행정구역과 경계가 다르므로 scope 에 적으면 안 된다. 그렇다고
    낱말을 **조용히 버리면** 그 사실이 저장소에서 사라진다. 그래서
    `authority:` 가 있어야 버린다 — 없으면 None 이다.
    """
    rel = "safety/safety_fire_access_gj_dong_20250731.csv"
    assert nm.canonical(rel, {"scope": "jngj-donggu"}) is None
    assert nm.canonical(rel, {"scope": "jngj-donggu",
                              "authority": "동부소방서"}) == \
        "safety/safety_fire_access_jngj-donggu_20250731.csv"


def test_canonical_inserts_a_missing_scope_and_keeps_the_rest():
    """스코프가 없으면 vintage 앞에 끼워 넣는다. rev · 확장자는 그대로 간다."""
    assert nm.canonical("its/its_nodelink_changelog_20260812.csv",
                        {"scope": "kr"}) == \
        "its/its_nodelink_changelog_kr_20260812.csv"
    assert nm.canonical("safety/safety_cctv_dongu_20260630_r2.csv",
                        {"scope": "jngj-donggu"}) == \
        "safety/safety_cctv_jngj-donggu_20260630_r2.csv"
    assert nm.canonical("safety/safety_cctv_dongu_20260630.CSV",
                        {"scope": "jngj-donggu"}) == \
        "safety/safety_cctv_jngj-donggu_20260630.csv"


def test_canonical_says_nothing_when_the_name_is_already_right():
    """★ 음성 — 맞는 이름에 **None** 이다. 아니면 개명이 매번 돈다."""
    for rel in ("safety/safety_cctv_jngj-donggu_20260630.csv",
                "ngii/ngii_basemap_jngj-donggu_20260812_gj9708.zip",
                "safety/확장자없음"):
        assert nm.canonical(rel, {"scope": "jngj-donggu"}) is None, rel


def test_the_rules_and_the_real_files_are_already_canonical():
    """★ **전수 교차 — §494 가 손으로 유도한 그 변환이 여기 있었다.**

    `normalize_raw.RULES` 의 자리표 없는 템플릿과 raw 실물 전건에 대해
    `canonical` 이 「고칠 것 없다」(None)고 해야 한다. §494 **전에는** 이것이
    템플릿 스물넷에서 울었을 것이다 — 그 배치가 스크립트로 유도한 답이
    이 함수의 답과 **같다.** 정본이 둘이면 어긋나는데, 여기서는 둘이
    같다는 것을 기계가 댄다.
    """
    import json
    from pathlib import Path

    from firelane import ledger as L
    from firelane import normalize_raw as N

    root = Path(__file__).resolve().parents[1]
    bystem: dict[str, dict] = {}
    for e in L.load()["datasets"].values():
        for st in ([e["stem"]] if e.get("stem") else []) + list(e.get("stems") or []):
            bystem[str(st)] = e

    def entry_for(name: str):
        base = name.rsplit(".", 1)[0]
        c = [s for s in bystem if base == s or base.startswith(s + "_")]
        return bystem[max(c, key=len)] if c else None

    checked, bad = 0, []
    for _pat, folder, tmpl in N.RULES:
        if not tmpl or "{" in tmpl:
            continue
        if (e := entry_for(tmpl)) is None:
            continue
        checked += 1
        if (got := nm.canonical(f"{folder}/{tmpl}", e)) is not None:
            bad.append(f"  규칙 {folder}/{tmpl} → {got}")
    for p in sorted(json.loads(
            (root / "data/_acquire.json").read_text(encoding="utf-8"))["files"]):
        if (e := entry_for(p.split("/", 1)[1])) is None:
            continue
        checked += 1
        if (got := nm.canonical(p, e)) is not None:
            bad.append(f"  실물 {p} → {got}")
    assert checked > 80, f"{checked}건만 봤다 — 이 검사가 빈 그물이 됐다"
    assert not bad, ("정규명 산출기가 고치라는 것이 남아 있다:\n" + "\n".join(bad)
                     + "\n  ★ 고치는 쪽은 이름이다 — 대장이 정본이다(§18-3).")
