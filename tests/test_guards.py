"""
test_guards.py — 방어 로직 회귀 + 저장소 위생

test_contract.py 는 GIS ↔ UI 경계를 지킨다. 이 파일은 **파이프라인이
스스로에게 거짓말하지 못하게** 하는 장치들을 지킨다.

깨지면: 누군가 방어를 지웠거나, 지운 줄도 모르고 지웠다.

── 왜 생겼나 ──────────────────────────────────────────────────
1093(08-17) · 1091(08-18) 두 무효 산출은 같은 원인이었다. FAIL 난 단계의
낡은 파일을 하류가 조용히 읽었다. 방어는 8/18 에 들어갔으나 **테스트가
없었다.** 그 블록을 누가 지워도 CI 는 초록불이었다.

문서에 규칙을 적는 것과 규칙을 강제하는 것은 다르다. MASTER 는 사람이
읽어야 작동하고, 이 파일은 읽지 않아도 작동한다. 그 차이가 이 파일의 존재
이유다.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "etl"))

from guards import (  # noqa: E402
    CRITICAL,
    GuardFailure,
    coverage_check,
    lineage_check,
    quarantine_stale,
    uncovered_ratio,
)


# ── 1. 계보 검사 ────────────────────────────────────────────────
def _manifest(tmp_path: Path, outputs=None, **status) -> Path:
    d = tmp_path / "processed"
    d.mkdir(exist_ok=True)
    outputs = outputs or {}
    (d / "_manifest.json").write_text(json.dumps(
        {"datasets": [{"key": k, "status": v, "outputs": outputs.get(k, [])}
                      for k, v in status.items()]}),
        encoding="utf-8")
    return d


def test_lineage_passes_when_all_ok(tmp_path):
    lineage_check(_manifest(tmp_path, **{k: "OK" for k in CRITICAL}))


def test_lineage_accepts_skip(tmp_path):
    """SKIP 은 '이번 실행에서 건드리지 않음'이다. 실패가 아니다."""
    st = {k: "OK" for k in CRITICAL}
    st["cctv"] = "SKIP"
    lineage_check(_manifest(tmp_path, **st))


def test_lineage_blocks_on_fail(tmp_path):
    """★ 이것이 1093 을 만든 상황이다. ngii1k FAIL 인데 파일은 남아 있었다."""
    st = {k: "OK" for k in CRITICAL}
    st["ngii1k"] = "FAIL"
    with pytest.raises(GuardFailure, match="ngii1k"):
        lineage_check(_manifest(tmp_path, **st))


def test_lineage_blocks_on_missing_key(tmp_path):
    """대장에서 통째로 빠진 것도 FAIL 과 같게 본다. 없는 것은 OK 가 아니다."""
    st = {k: "OK" for k in CRITICAL if k != "road_rw"}
    with pytest.raises(GuardFailure, match="road_rw"):
        lineage_check(_manifest(tmp_path, **st))


def test_lineage_blocks_without_manifest(tmp_path):
    with pytest.raises(GuardFailure, match="_manifest"):
        lineage_check(tmp_path / "없는곳")


# ── 1b. 계보 — 파일 층 ─────────────────────────────────────────
def test_lineage_blocks_orphan_derived_output(tmp_path):
    """
    ★ key 가 OK 여도 파생 산출물이 낡았을 수 있다.

    ngii1k 는 한 번에 10개 파일을 낸다. 그중 평면교차점(xsec)만 옛 실행 것이
    남아 있으면 key 층 검사는 통과한다. 그러면 교차부 제외 형상이 옛것이 되어
    폭 표본이 달라지고 판정이 조용히 갈린다 — 1093 사고가 한 단계 아래에서
    그대로 재현되는 경로다.
    """
    st = {k: "OK" for k in CRITICAL}
    d = _manifest(tmp_path, outputs={"ngii1k": ["ngii1k_5186.gpkg"]}, **st)
    (d / "ngii1k_5186.gpkg").write_text("new")
    (d / "ngii1k_xsec_5186.gpkg").write_text("낡음")     # 대장에 없다
    with pytest.raises(GuardFailure, match="xsec"):
        lineage_check(d)


def test_lineage_ok_when_all_outputs_declared(tmp_path):
    st = {k: "OK" for k in CRITICAL}
    d = _manifest(tmp_path,
                  outputs={"ngii1k": ["ngii1k_5186.gpkg", "ngii1k_xsec_5186.gpkg"]},
                  **st)
    (d / "ngii1k_5186.gpkg").write_text("new")
    (d / "ngii1k_xsec_5186.gpkg").write_text("new")
    lineage_check(d)


def test_lineage_ignores_absent_files(tmp_path):
    """없는 파일은 이 검사 대상이 아니다. 하류가 FileNotFoundError 로 시끄럽게 죽는다.

    조용한 오답과 시끄러운 죽음 중에서는 후자가 낫다.
    """
    st = {k: "OK" for k in CRITICAL}
    lineage_check(_manifest(tmp_path, **st))


def test_lineage_ignores_outputs_of_failed_key(tmp_path):
    """FAIL 한 key 의 outputs 는 이번 계보로 치지 않는다."""
    st = {k: "OK" for k in CRITICAL}
    d = _manifest(tmp_path, outputs={"cctv": ["cctv_5186.gpkg"]}, **{**st, "cctv": "FAIL"})
    (d / "cctv_5186.gpkg").write_text("x")
    with pytest.raises(GuardFailure):
        lineage_check(d)


# ── 2. 낡은 산출물 격리 ─────────────────────────────────────────
def test_quarantine_renames_not_deletes(tmp_path):
    """삭제가 아니라 개명이다. 옛 파일은 진단의 증거다(08-18 실제로 봤다)."""
    for n in ("ngii1k_5186.gpkg", "ngii1k.geojson", "ngii1k_north_5186.gpkg"):
        (tmp_path / n).write_text("x")
    (tmp_path / "road_link_5186.gpkg").write_text("keep")

    staled = quarantine_stale(tmp_path, "ngii1k", tag="20260818")

    assert len(staled) == 3
    assert not (tmp_path / "ngii1k_5186.gpkg").exists(), "하류가 아직 읽을 수 있다"
    assert (tmp_path / "ngii1k_5186.gpkg.stale_20260818").exists(), "증거가 지워졌다"
    assert (tmp_path / "road_link_5186.gpkg").exists(), "무관한 key 를 건드렸다"


def test_quarantine_is_rerunnable(tmp_path):
    """두 번 돌려도 죽지 않는다. 같은 날 두 번 FAIL 날 수 있다."""
    (tmp_path / "cctv.geojson").write_text("a")
    quarantine_stale(tmp_path, "cctv", tag="20260818")
    (tmp_path / "cctv.geojson").write_text("b")
    quarantine_stale(tmp_path, "cctv", tag="20260818")
    assert (tmp_path / "cctv.geojson.stale_20260818").read_text() == "b"


def test_quarantine_noop_when_nothing(tmp_path):
    assert quarantine_stale(tmp_path, "없는키") == []


# ── 3. 공간 커버리지 ────────────────────────────────────────────
COVER = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])


def test_uncovered_counts_lines_outside():
    inside = [LineString([(10, 10), (20, 20)]), LineString([(30, 30), (40, 40)])]
    outside = [LineString([(500, 500), (510, 510)])]
    miss, total = uncovered_ratio(inside + outside, [COVER])
    assert (miss, total) == (1, 3)


def test_coverage_blocks_the_0818_situation():
    """★ 스코프의 69% 가 도로경계 밖이었던 상태를 재현한다.

    건수·컬럼·CRS 검사는 그때 전부 통과했다. 이 검사만이 잡는다.
    """
    lines = ([LineString([(i, i), (i + 1, i + 1)]) for i in range(31)]
             + [LineString([(500 + i, 500), (501 + i, 500)]) for i in range(69)])
    with pytest.raises(GuardFailure, match="69"):
        coverage_check(lines, [COVER])


def test_coverage_passes_at_confirmed_level():
    """2026-08-18 확정 실행 수준(미커버 4.3%)은 통과해야 한다."""
    lines = ([LineString([(i % 90, 10), (i % 90 + 1, 10)]) for i in range(1054)]
             + [LineString([(500, 500), (501, 501)])] * 47)
    assert coverage_check(lines, [COVER]) < 0.10


def test_coverage_blocks_empty_polygon_source():
    """폭 소스가 통째로 비면 '전부 미커버'다. 조용한 통과가 제일 나쁘다."""
    with pytest.raises(GuardFailure):
        coverage_check([LineString([(0, 0), (1, 1)])], [])


# ── 4. 저장소 위생 — 규칙을 문서가 아니라 여기서 강제한다 ──────
DATED = re.compile(r"_20\d{6}\.py$")


def test_no_dated_scripts_in_tools():
    """
    ★ tools/ 에 날짜 붙은 스크립트를 남기지 않는다.

    2026-08-17~18 에 8개가 쌓였고 전부 일회성 패처였다. 적용된 뒤에는
    no-op 이고, 둘은 앵커가 깨져 재실행조차 불가능했다. 1,000줄이
    "돌릴 수도 없고 돌릴 필요도 없는 코드"로 남아 있었다.

    일회성 작업은 돌리고 지운다. 남길 값이 있으면 docs/DECISIONS.md 에
    이유를, tools/ 에는 날짜 없는 재실행 가능한 도구만 둔다.
    """
    bad = sorted(p.name for p in (ROOT / "tools").glob("*.py") if DATED.search(p.name))
    assert not bad, (
        f"일회성 패처가 남아 있다: {bad}\n"
        "  적용했으면 지워라. 이유는 docs/DECISIONS.md 로 옮긴다.")


def test_no_source_patching_scripts():
    """
    ★ src/ 를 문자열 치환으로 고치는 스크립트를 만들지 않는다.

    소스를 고쳐서 커밋하는 대신 '고치는 스크립트'를 커밋하면, git 이 이미
    하는 일을 파이썬으로 재구현하는 것이다. 진짜 코드가 어디 있는지
    두 곳이 되고, 리뷰는 diff 가 아니라 문자열 쌍을 읽어야 한다.

    삭제된 9개로 역검증했다. 8개가 이 규칙에 걸린다. 나머지 하나
    (ledger_20260817, ruamel.yaml 로 조작해 .replace 를 안 쓴다)는
    위의 날짜 규칙이 잡는다. 두 검사가 겹쳐서 덮는다.
    """
    TARGETS = ("src/etl", "docs/MASTER", "sources.yaml", "README.md")
    offenders = []
    for p in (ROOT / "tools").glob("*.py"):
        src = p.read_text(encoding="utf-8")
        # 패처의 서명: 정본 파일을 읽어 문자열 치환하고 되쓴다.
        # 읽기만 하는 도구(baseline.py 가 EXPECT 를 읽는 등)는 해당 없다.
        if (".write_text(" in src and ".replace(" in src
                and any(x in src for x in TARGETS)):
            offenders.append(p.name)
    assert not offenders, (
        f"src 를 문자열로 패치하는 스크립트: {offenders}\n"
        "  소스를 직접 고치고 커밋해라. 패치 스크립트는 diff 의 열등한 사본이다.")


def test_guard_calls_are_wired():
    """
    방어가 모듈에만 있고 호출되지 않으면 없는 것과 같다.
    guards.py 를 통째로 지우는 것은 이 테스트가 잡고,
    호출부만 지우는 것은 여기가 잡는다.
    """
    seg = (ROOT / "src/etl/segments.py").read_text(encoding="utf-8")
    ing = (ROOT / "src/etl/ingest.py").read_text(encoding="utf-8")
    assert "_lineage_check()" in seg, "segments 가 계보 검사를 부르지 않는다"
    assert "lineage_check" in seg, "segments 가 guards 를 쓰지 않는다"
    assert "quarantine_stale" in ing, "ingest 가 FAIL 산출물을 격리하지 않는다"
    assert "coverage_check" in seg, (
        "segments 가 공간 커버리지를 검사하지 않는다 — "
        "함수만 있고 배선이 없으면 손으로 세는 것과 같다")


def test_docnum_check_is_in_ci():
    """
    ★ 도구를 만들어놓고 수동 실행으로 두면 안 돌린다.

    docnum_check.py 는 문서 숫자와 산출물을 대조한다. 8/17 의 1093 은
    이것을 돌렸으면 그날 잡혔다. CI 에 없으면 다음에도 안 돌린다.
    """
    ci = (ROOT / ".github/workflows/contract.yml").read_text(encoding="utf-8")
    assert "docnum_check" in ci, "docnum_check.py 가 CI 에 없다"


def test_fire_lane_raw_does_not_silently_win():
    """
    ★ 폐기된 FIRE_LANE_RAW 가 FIRE_LANE_DATA 를 조용히 이기면 안 된다.

    기계마다 다른 값이 남아 있어 '기계 간 재현성 붕괴'로 오인한 원인 중
    하나였다. .bashrc 를 기계마다 고치는 것은 해결이 아니다 — 코드가
    알아채야 한다.
    """
    src = (ROOT / "src/etl/paths.py").read_text(encoding="utf-8")
    assert "_legacy_raw" in src or "폐기" in src, "paths.py 가 구 변수를 경고하지 않는다"


def test_repo_python_compiles():
    """치환·삭제 후 구문이 깨지지 않았는지 한 번에 본다."""
    files = sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "tools").glob("*.py"))
    r = subprocess.run([sys.executable, "-m", "py_compile", *map(str, files)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ── 단계 간 계약 (2026-08-18) ──────────────────────────────────
def _steps():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pipeline", ROOT / "src/etl/pipeline.py")
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "src/etl"))
    # ★ @dataclass 는 cls.__module__ 로 sys.modules 를 되짚는다.
    #   등록 없이 exec_module 하면 AttributeError 로 죽는다.
    sys.modules["pipeline"] = m
    spec.loader.exec_module(m)
    return m


def test_no_two_steps_write_the_same_path():
    """
    ★ 두 단계가 같은 파일을 쓰면 실행 순서에 따라 결과가 달라진다.

    덧쓰기가 필요하면 `writes` 가 아니라 `mutates` 로 선언한다. terrain 이
    segments.geojson 에 z 를 넣는 것이 그렇다. 이름을 나눠두면 "이 파일은
    앞 단계 산출을 덧쓴다"가 코드에 드러나고, 그것이 2026-08-18 에
    `--only publish` 로 z 가 소실된 원인이었다.
    """
    m = _steps()
    seen = {}
    for s in m.STEPS:
        for w in s.writes:
            assert w not in seen, (
                f"{s.name} 과 {seen[w]} 이 같은 경로를 쓴다: {w}\n"
                "  덧쓰기라면 mutates 로 선언해라.")
            seen[w] = s.name


def test_every_read_is_produced_by_an_earlier_step():
    """
    ★ 읽는 것은 앞 단계가 만든 것이거나 raw 여야 한다.

    뒤 단계가 만드는 것을 앞 단계가 읽으면 첫 실행에서 죽거나, 더 나쁘게는
    지난 실행의 산출물을 읽어 조용히 돈다. 2026-08-17 의 1093 이 그것이었다.
    """
    m = _steps()
    made = [m.RAW]
    for s in m.STEPS:
        for r in s.consumes:
            assert any(m.matches(r, d) for d in made), (
                f"{s.name} 이 {r.name} 을 읽는데 앞 단계가 만들지 않는다.\n"
                "  선언이 틀렸거나 STEPS 순서가 틀렸다.")
        made += list(s.produces)


def test_expect_is_not_hardcoded():
    """
    ★ 판정 숫자의 정본은 golden 지문 하나다.

    2026-08-18 까지 pipeline.EXPECT · golden 지문 · 문서 셋이 같은 값을
    따로 들고 있었다. 동기화 도구가 필요하다는 것은 정본이 하나가 아니라는
    뜻이다. EXPECT 를 지우고 지문에서 읽는다.
    """
    src = (ROOT / "src/etl/pipeline.py").read_text(encoding="utf-8")
    assert '"verdict": {"clear"' not in src, (
        "pipeline.py 에 판정 숫자가 하드코딩돼 있다.\n"
        "  data/golden/segments.fingerprint.json 에서 읽어라.")
