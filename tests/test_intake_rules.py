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


# ── absorb — 순서가 자료구조인가 ───────────────────────────────
#
# ★ 2026-08-31 신설. `absorb.py` 가 네 단계를 한 명령으로 묶는다. 묶는 것
#   자체는 편의지만, **삭제가 검증에 매달려 있다**는 것은 규약이다.
#   `acquire --prune-landing` 은 단독으로도 돈다 — 즉 검증 없이 원본을
#   지울 수 있다. absorb 는 그 경로를 막는 것이 존재 이유이므로, 그
#   불변식을 여기서 든다.
#
#   raw 없이 돈다. 게이트는 종료코드만 보는 순수 판정이라 CI 에서 잡힌다.
def _absorb():
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("absorb", root / "tools/absorb.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _spy_run(m, step, results):
    """단계를 돌리되 **실제 호출이 일어났는지**를 돌려준다.

    ★ 종료코드만 보면 안 된다. 게이트를 뚫어놓고 실험해보니,
      막히지 않고 내려간 subprocess 가 어떤 이유로든 실패하면 rc 가
      0 이 아니게 되고 **테스트는 그대로 통과했다.** 옳게 우는 것처럼
      보이는 검사가 또 하나 생길 뻔했다(audit_pattern('') 과 같은 형태).

      불변식은 "종료코드가 0 이 아니다" 가 아니라 **"삭제 명령이 실행되지
      않았다"** 이다. 그것을 직접 본다.
    """
    import subprocess
    seen: list[list[str]] = []
    orig = subprocess.call
    subprocess.call = lambda a, **k: (seen.append(a), 0)[1]
    try:
        rc = m.run(step, apply=True, results=results)
    finally:
        subprocess.call = orig
    return rc, seen


def test_absorb_prune_needs_verify():
    """검증이 실패하면 삭제 명령이 **실행되지 않는다.**"""
    m = _absorb()
    prune = m.Step("prune", "④", ["acquire.py", "--prune-landing"], needs="verify")
    rc, seen = _spy_run(m, prune, {"stage": 0, "verify": 1})
    assert not seen, (
        f"검증이 1 로 끝났는데 삭제 명령이 실행됐다: {seen}\n"
        "  확인 없이 원본을 지우는 경로다. 이 도구의 존재 이유가 여기다.")
    assert rc != 0, "삭제를 막았으면서 종료코드 0 을 내면 호출부가 성공으로 읽는다"


def test_absorb_prune_needs_verify_to_have_run():
    """검증이 **아예 안 돌았으면**도 삭제 명령이 없다.

    ★ 없는 것과 통과한 것을 가른다. `results.get()` 이 None 을 내는데
      그것을 0 처럼 다루면 건너뛴 검증이 통과로 읽힌다.
    """
    m = _absorb()
    prune = m.Step("prune", "④", ["acquire.py", "--prune-landing"], needs="verify")
    for res in ({}, {"stage": 0}):
        rc, seen = _spy_run(m, prune, res)
        assert not seen, f"선행 검증 없이 삭제가 실행됐다 (results={res}): {seen}"
        assert rc != 0


def test_absorb_gate_lets_the_good_path_through():
    """★ 역방향 — 검증이 0 이면 삭제가 **실제로 호출된다.**

    막기만 하고 통과를 안 시키면 그것도 죽은 검사다. 게이트가 항상
    막으면 absorb 는 ④ 를 영영 안 돌리고, 아무도 그 사실을 모른다.
    """
    m = _absorb()
    prune = m.Step("prune", "④", ["acquire.py", "--prune-landing"], needs="verify")
    rc, seen = _spy_run(m, prune, {"stage": 0, "verify": 0})
    assert rc == 0 and len(seen) == 1, f"통과 경로가 막혔다: rc={rc} seen={seen}"
    assert "--prune-landing" in seen[0] and "--yes" in seen[0], seen[0]


def test_absorb_dry_run_never_passes_yes():
    """`--yes` 없이는 어떤 단계도 파괴적 인자를 받지 않는다."""
    import subprocess
    m = _absorb()
    seen: list[list[str]] = []
    orig = subprocess.call
    subprocess.call = lambda a, **k: (seen.append(a), 0)[1]
    try:
        for key, argv in (("intake", ["intake.py", "--stage"]),
                          ("stage", ["acquire.py", "--stage"]),
                          ("prune", ["acquire.py", "--prune-landing"])):
            m.run(m.Step(key, key, argv), apply=False, results={})
    finally:
        subprocess.call = orig
    assert seen, "아무 단계도 안 돌았다"
    for a in seen:
        assert "--yes" not in a, f"관측 모드인데 --yes 가 붙었다: {a}"


def test_absorb_does_not_reimplement_acquire():
    """단계는 **기존 도구를 부른다.** 판정 로직을 옮겨 적지 않는다.

    ★ 08-30 에 고친 여섯 건 중 넷이 사본이었다(JUNK 3벌 · 글롭 11벌).
      absorb 가 sha 비교나 세 판정을 자기 안에 다시 쓰면 그것이 다섯째다.
      사전 대조의 sha256 은 **보고용**이고 편입·삭제 판정에 쓰이지 않는다.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "tools/absorb.py").read_text(
        encoding="utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    for banned in ("shutil.copy", "shutil.move", "os.remove", ".unlink(",
                   "shutil.rmtree"):
        assert banned not in code, (
            f"absorb.py 가 {banned} 로 직접 실물을 움직인다.\n"
            "  이관·편입·삭제의 정본은 intake.py · acquire.py 다. 불러라.")


# ── 대장 조회기가 하나인가 ─────────────────────────────────────
#
# ★ 2026-08-31 신설. 08-27 에 `retired` 항목이 같은 배포물의 다른 포맷을
#   담으려고 `files:` 를 도입했다. 그런데 `acquire.retired_names()` 는
#   `file:` 만 읽는 자기 구현을 갖고 있었고 그쪽을 안 고쳤다.
#
#   결과 — mas_optional 의 pdf 와 kfs_paint_marking 전체가 폐기 등재돼
#   있는데도 매 스캔마다 "판단 필요" 로 떴다. 이미 8-24·8-27 에 열어보고
#   판정을 끝낸 문서를 몇 번이나 다시 조사했다. **사유는 적혀 있었고
#   도구가 그것을 안 읽었다.**
#
#   조회기의 정본은 `firelane.ledger.globs` 하나다. raw 없이 돈다.
def _yaml():
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parents[1]
    return yaml.safe_load((root / "sources.yaml").read_text(encoding="utf-8")) or {}


def test_no_file_and_files_coexist():
    """한 항목이 `file:` 과 `files:` 를 동시에 갖지 않는다.

    ★ 둘이 같이 있으면 어느 쪽을 읽느냐로 답이 갈린다. 실제로 갈렸다 —
      `ledger.globs` 는 files 를 보고 `retired_names` 는 file 을 봤다.
    """
    d = _yaml()
    bad = [f"{blk}.{k}" for blk in ("datasets", "retired")
           for k, e in (d.get(blk) or {}).items()
           if isinstance(e, dict) and "file" in e and "files" in e]
    assert not bad, (
        f"file: 과 files: 가 함께 있는 항목 {len(bad)}개\n  " + "\n  ".join(bad)
        + "\n  files: 하나만 남겨라. 둘이면 읽는 쪽마다 다른 답이 나온다.")


def test_retired_declares_every_format():
    """폐기 항목이 배포물의 **모든 포맷**을 적는가.

    포맷이 다르면 다른 파일이다(naming.py). 하나만 적으면 나머지가
    폐기 등재 밖이 되고 매 스캔마다 "미상" 으로 떠 다시 조사하게 만든다.
    """
    from pathlib import Path
    d = _yaml()
    bad = []
    for k, e in (d.get("retired") or {}).items():
        if not isinstance(e, dict):
            continue
        files = [str(x) for x in (e.get("files") or ([e["file"]] if e.get("file") else []))]
        stems = {Path(f).stem for f in files}
        if len(stems) == 1 and len(files) == 1 and (e.get("ext") or []):
            bad.append(f"retired.{k} — ext 는 {e['ext']} 인데 files 는 1건")
    assert not bad, "\n  ".join(["폐기 등재가 포맷을 빠뜨렸다:"] + bad)


def test_retired_names_uses_the_canonical_reader():
    """`acquire.retired_names()` 가 조회기를 다시 구현하지 않는가.

    ★ 이것이 도돌이표의 근원이었다. 정본은 ledger.globs 하나다.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    src = (root / "tools/acquire.py").read_text(encoding="utf-8")
    i = src.index("def retired_names(")
    body = src[i:src.index("\ndef ", i + 10)]
    code = "\n".join(x for x in body.splitlines() if not x.lstrip().startswith("#"))
    assert "globs(" in code, (
        "retired_names 가 ledger.globs 를 안 쓴다.\n"
        "  file: 만 읽으면 files: 로 적힌 폐기분이 매번 '판단 필요' 로 뜬다.")
    assert 'v.get("file")' not in code, (
        "retired_names 가 아직 file: 을 직접 읽는다. ledger.globs 가 정본이다.")
