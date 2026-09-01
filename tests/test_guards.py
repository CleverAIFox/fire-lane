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

from firelane.guards import (
    CRITICAL,
    GuardFailure,
    coverage_check,
    lineage_check,
    quarantine_stale,
    uncovered_ratio,
)

ROOT = Path(__file__).resolve().parents[1]


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
    TARGETS = ("src/firelane", "docs/MASTER", "sources.yaml", "README.md")

    # ★ 좁은 예외 하나. **git 밖의 실물과 함께 움직여야 하는 것**만 허용한다.
    #
    #   이 규칙의 근거는 "패치 스크립트는 diff 의 열등한 사본" 이다. 그것이
    #   성립하려면 바꾸려는 대상이 **git 안에 있어야** 한다. raw 는 아니다 —
    #   2.6GB 가 저장소 밖 SSD 에 있고, 파일 하나를 개명하면 세 곳이 동시에
    #   바뀌어야 한다(실물 · _acquire.json 키 · 대장 file). diff 로는 셋 중
    #   둘밖에 못 담고, 나머지 하나가 어긋나면 어느 쪽이 정본인지 모른다.
    #
    #   허용 조건은 마커 한 줄이다. 실수로 붙지 않을 만큼 길고, 붙이려면
    #   이유를 읽게 되어 있다.
    # ★ 예외를 파일명으로 늘리지 않는다. 그러면 목록이 계속 길어지고,
    #   길어진 목록은 아무도 안 읽는다. **규칙을 정확히 좁힌다.**
    #
    #   이 규칙이 막으려는 것은 "소스를 고치는 대신 고치는 스크립트를
    #   커밋하는 것" 이다. 그 해악은 **정본이 두 곳이 되는 것**이고,
    #   그것이 성립하려면 대상이 git 안에 있어야 한다.
    #
    #   대장(`sources.yaml`)을 고치는 도구는 다르다 — 대장은 코드가 아니라
    #   **데이터**이고, 그 값은 저장소 밖 raw 실물에서 나온다. 실물이 바뀌면
    #   대장이 따라 바뀌어야 하며 그것은 매번 도는 작업이다. diff 로는 못
    #   담는다(raw 가 git 에 없다).
    #
    #   그래서 예외 조건을 둘로 한다 —
    #     ① 마커가 있고
    #     ② TARGETS 중 **sources.yaml 만** 건드린다(src/ · docs/ 는 안 된다)
    #
    #   ②가 핵심이다. 소스 코드를 문자열로 고치는 도구는 마커를 붙여도
    #   못 지나간다.
    ALLOW_MARKER = "FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다"
    CODE_TARGETS = ("src/firelane", "docs/MASTER", "README.md")

    offenders = []
    for p in (ROOT / "tools").glob("*.py"):
        src = p.read_text(encoding="utf-8")
        # 패처의 서명: 정본 파일을 읽어 문자열 치환하고 되쓴다.
        # 읽기만 하는 도구(baseline.py 가 EXPECT 를 읽는 등)는 해당 없다.
        # ★ 2026-08-31. 종전에는 TARGETS 문자열이 **어디에든** 있으면 잡았다.
        #   그래서 `render_workflow.py` 가 걸렸다 — `docs/MASTER.md` 를 **읽어**
        #   `web/workflow.html` 을 쓰는 도구인데, 규칙이 막으려는 것과 방향이
        #   반대다. `publish_web.py` 가 processed 를 읽어 web/data 를 쓰는 것과
        #   같은 계층 이동이다.
        #
        #   이 규칙의 해악은 "정본을 문자열로 고쳐 정본이 둘이 되는 것" 이므로
        #   **쓰기 대상이 정본인지**를 본다. 읽기는 해당 없다.
        writes = re.findall(r"(\w+)\.write_text\(", src)
        target_write = any(
            re.search(rf"{w}\s*=\s*.*?(?:{'|'.join(re.escape(x) for x in TARGETS)})",
                      src) for w in writes)
        if not (target_write and ".replace(" in src):
            continue
        if ALLOW_MARKER in src and not any(x in src for x in CODE_TARGETS):
            continue
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
    seg = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    ing = (ROOT / "src/firelane/ingest.py").read_text(encoding="utf-8")
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
    src = (ROOT / "src/firelane/paths.py").read_text(encoding="utf-8")
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
        "pipeline", ROOT / "src/firelane/pipeline.py")
    m = importlib.util.module_from_spec(spec)
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
    src = (ROOT / "src/firelane/pipeline.py").read_text(encoding="utf-8")
    assert '"verdict": {"clear"' not in src, (
        "pipeline.py 에 판정 숫자가 하드코딩돼 있다.\n"
        "  data/golden/segments.fingerprint.json 에서 읽어라.")


# ── 계보 (2026-08-18) ─────────────────────────────────────────
def test_lineage_catches_tampered_input(tmp_path):
    """
    ★ 상류가 쓴 것과 지금 디스크가 다르면 하류를 돌리지 않는다.

    2026-08-18. `_manifest` 는 ngii1k 14336 을 적었는데 segments 는 옛
    레이어 6,675 개를 읽고 있었다. 파일은 갱신됐고 mtime 도 새것이고
    status 는 OK 라 어떤 가드도 보지 못했다. 숫자는 다 있었고 대조가
    없었다. 이 테스트가 그 대조를 지킨다.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "lineage", ROOT / "src/firelane/lineage.py")
    lg = importlib.util.module_from_spec(spec)
    sys.modules["lineage"] = lg
    spec.loader.exec_module(lg)

    class S:
        def __init__(self, name, reads, writes):
            self.name, self.reads, self.writes, self.mutates = \
                name, reads, writes, ()
        consumes = property(lambda s: s.reads)
        produces = property(lambda s: s.writes)

    up_out = tmp_path / "a.json"
    up_out.write_text('{"n": 1}', encoding="utf-8")
    up = S("up", (), (up_out,))
    down = S("down", (up_out,), (tmp_path / "b.json",))
    steps = [up, down]

    def expand(d):
        return list(d)

    lg.record(tmp_path, tmp_path, up, expand)
    lg.record(tmp_path, tmp_path, down, expand)
    lg.verify(tmp_path, tmp_path, down, expand, steps)     # 통과해야 한다

    up_out.write_text('{"n": 2}', encoding="utf-8")        # 손으로 바꾼다
    try:
        lg.verify(tmp_path, tmp_path, down, expand, steps)
        raise AssertionError("변조를 못 잡았다")
    except lg.LineageError:
        pass


def test_lineage_is_pipeline_concern_not_step_concern():
    """
    ★ 계보는 파이프라인이 본다. 단계 스크립트는 계보를 모른다.

    종전에는 segments.py 안에서 lineage_check 를 불렀다. 단계마다 손으로
    배선해야 했고 `--only publish` 가 그 구멍으로 빠져나가 z 를 소실시켰다.
    Step 선언이 reads/writes 를 알고 있으므로 pipeline 이 일괄로 한다.
    """
    src = (ROOT / "src/firelane/pipeline.py").read_text(encoding="utf-8")
    assert "lineage.verify" in src and "lineage.record" in src, \
        "pipeline 이 계보를 배선하지 않는다"


# ── 4. 단일 정본 — 같은 값이 세 곳에 살면 어긋난다 ──────────────
# ★ 2026-08-23 신설. 아래 셋은 전부 "규칙은 있는데 강제자가 없어서
#   조용히 갈라진" 자리다. 이 저장소가 계보·판정·문서·인코딩·계층에
#   대해 이미 하고 있는 일을, 남은 자리에도 한다.

def test_webdata_limit_is_one_number():
    """web/data 용량 상한이 세 곳에서 같아야 한다.

    ★ 실제로 갈라져 있었다 — contract.yml 40 · commit_policy 40 · pipeline 60.
      PLAN #12 가 "60 → 40 으로 조정" 이라 적었는데 pipeline 만 안 고쳤다.
      40~60 구간에서 **로컬 파이프라인은 초록불이고 CI 만 빨간불**이 된다.
      값이 무엇이냐보다 하나냐가 중요하다.
    """
    import re

    from firelane.pipeline import WEB_MAX_MB

    ci = (ROOT / ".github/workflows/contract.yml").read_text(encoding="utf-8")
    m = re.search(r'SIZE"?\s*-ge\s*(\d+)', ci) or re.search(r'-ge\s*"?(\d+)"?', ci)
    assert m, "contract.yml 에서 web/data 상한을 못 찾았다"
    ci_mb = int(m.group(1))

    pol = (ROOT / "tools/commit_policy.py").read_text(encoding="utf-8")
    m2 = re.search(r"MAX_WEBDATA_MB\s*=\s*(\d+)", pol)
    assert m2, "commit_policy.py 에서 MAX_WEBDATA_MB 를 못 찾았다"
    pol_mb = int(m2.group(1))

    assert WEB_MAX_MB == ci_mb == pol_mb, (
        f"web/data 상한이 갈렸다 — pipeline {WEB_MAX_MB} · "
        f"contract.yml {ci_mb} · commit_policy {pol_mb}")


def test_ci_watches_the_working_branch():
    """CI 트리거가 실제 작업 브랜치를 포함해야 한다.

    ★ 두 번 같은 사고가 났다. 08-22 에 `gis` 를 추가하자마자 세 건을
      잡았다는 기록이 DECISIONS 에 남아 있는데, 워크플로가 다시
      `[main]` 단독으로 되돌아가 있었다(2026-08-23 발견).

      README · MASTER · CODEOWNERS 는 `gis` 를 정본 브랜치로 적고
      pages.yml 은 `[main, gis]` 를 배포한다. contract 만 main 을 보면
      **PR 이 검사 없이 머지된다** — 검사가 죽었는데 초록불이 뜨는,
      이 저장소가 계속 겪은 바로 그 모양이다.
    """
    import re
    ci = (ROOT / ".github/workflows/contract.yml").read_text(encoding="utf-8")
    pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")

    def lists(txt):
        """`branches: [...]` 선언을 **하나씩** 낸다.

        ★ 합집합으로 보면 안 된다. contract.yml 에는 push 와 pull_request
          두 개가 있고, 둘 중 하나만 gis 를 빠뜨려도 그쪽 이벤트가 검사를
          비껴간다. 합집합 검사는 그것을 통과시킨다 — 실제로 이 테스트를
          처음 쓸 때 그렇게 짰다가 역검증에서 걸렸다.
        """
        return [{b.strip() for b in m.split(",")}
                for m in re.findall(r"branches:\s*\[([^\]]+)\]", txt)]

    ci_lists = lists(ci)
    pg_b = set().union(*lists(pages)) if lists(pages) else set()
    assert ci_lists, "contract.yml 에 branches 선언이 없다"
    for i, b in enumerate(ci_lists):
        missing = pg_b - b
        assert not missing, (
            f"배포는 {sorted(pg_b)} 에서 도는데 contract.yml 의 트리거 "
            f"{i + 1}번은 {sorted(b)} 만 본다.\n"
            f"  검사를 비껴가는 브랜치: {sorted(missing)}\n"
            "  pages.yml 이 배포하는 브랜치는 push · pull_request 양쪽에서 봐야 한다.")


def test_docs_point_at_the_real_package():
    """문서가 죽은 모듈 경로(`src/etl`)를 가리키면 안 된다.

    ★ 2026-08-21 패키지화로 `src/etl/` → `src/firelane/` 이 됐는데
      MASTER 51곳 · PLAN 5곳 · sources.yaml 13곳이 옛 경로로 남아 있었다.
      그중 10줄은 **사람이 그대로 칠 수 있는 실행 명령**이었고 전부
      "그런 파일 없음" 으로 죽는다.

      R16(`test_readme_structure_lists_real_files`)은 README 의 구조
      블록만 본다. 그 밖은 아무도 안 봤다.

    ★ DECISIONS 와 MIGRATION 은 제외한다. 과거 기록이므로 그 시점의
      경로를 적는 것이 옳다(R14 — 시제가 다르면 문서가 다르다).
    """
    stale = []
    targets = ["README.md", "docs/MASTER.md", "docs/PLAN.md",
               "sources.yaml", "web/config.js", "web/README.md"]
    for rel in targets:
        p = ROOT / rel
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "src/etl" in line:
                stale.append(f"{rel}:{i}  {line.strip()[:70]}")
    assert not stale, (
        f"죽은 모듈 경로 src/etl 이 {len(stale)}곳 남아 있다:\n  "
        + "\n  ".join(stale[:12]))


def test_ingest_kinds_are_documented():
    """`sources.yaml` 이 쓰는 `kind` 가 전부 ingest 분기에 있고, 문서 표와 같은가.

    ★ 2026-08-23. `src/firelane/README.md` 는 "kind 가 여섯 종류로 모든
      케이스를 덮는다" 고 적고 있었는데 실제 분기는 12개(별칭 포함)였고,
      `sources.yaml` 이 실제로 쓰는 `shp_dir` · `raw_only` 가 문서에 없었다.

      `data/raw/README.md` 는 아홉을 적었지만 `shp_dir` 대신 옛 이름
      `ngii_1k` 였다. 문서 둘이 서로도 다르고 코드와도 달랐다.

      대장에 없는 kind 를 쓰면 `unknown kind` 로 **시끄럽게** 죽는다.
      문제는 그 반대다 — 코드에 있는데 문서에 없으면 다음 사람이 없는 줄 알고
      새 분기를 또 만든다.
    """
    import re

    import yaml

    src = (ROOT / "src/firelane/ingest.py").read_text(encoding="utf-8")
    body = src[src.index("def build("):src.index("\ndef main(")]
    impl = set()
    for m in re.finditer(r'kind\s*==\s*"(\w+)"|kind\s+in\s*\(([^)]+)\)', body):
        if m.group(1):
            impl.add(m.group(1))
        else:
            impl |= {x.strip().strip('"') for x in m.group(2).split(",")}
    assert len(impl) >= 8, f"ingest 분기를 못 읽었다: {impl}"

    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    used = {(v or {}).get("kind") for v in y["datasets"].values()} - {None}
    unknown = sorted(used - impl)
    assert not unknown, (
        f"sources.yaml 이 ingest 에 없는 kind 를 쓴다: {unknown}\n"
        "  실행하면 ValueError('unknown kind') 로 죽는다.")

    # ★ 문서 전체가 아니라 **표 행**에서 찾는다. 본문 어딘가에 이름이
    #   언급된 것만으로 통과시키면 안 된다 — 실제로 별칭 설명 문단이
    #   `shp_dir` 을 언급하는 바람에 표에서 빼도 통과했다(역검증에서 걸림).
    doc = (ROOT / "src/firelane/README.md").read_text(encoding="utf-8")
    rows = set(re.findall(r"^\|\s*`(\w+)`\s*\|", doc, re.M))
    assert rows, "src/firelane/README.md 에서 kind 표를 못 찾았다"
    missing = sorted(used - rows)
    assert not missing, (
        f"sources.yaml 이 쓰는 kind 가 src/firelane/README.md 표에 없다: {missing}")


def test_etl_imports_are_declared():
    """파이프라인이 import 하는 외부 패키지가 `pyproject` 필수 의존성에 전부 있는가.

    ★ 2026-08-23. `requirements-etl.txt` 가 `rasterio` · `pillow` 를 빠뜨리고
      있었다. 그 파일로 설치하면 `fire-lane` 이 terrain 단계에서 ImportError
      로 죽는다. 참조하는 곳이 0곳이라 아무도 안 돌려봐서 몰랐다.

      파일은 지웠고, 이제 정본은 `pyproject.dependencies` 하나다. 그것이
      실제 import 를 덮는지는 사람이 아니라 여기가 본다.

    ★ `[api]` · `[vision]` extras 는 보지 않는다. 그쪽은 아직 코드가 없다
      (`src/api/` 는 존재하지 않는다). 필수 의존성만 파이프라인의 계약이다.
    """
    import ast
    import re
    import sys
    import tomllib

    pkg = ROOT / "src" / "firelane"
    std = set(sys.stdlib_module_names)
    # import 이름 → 배포 이름. 다른 것만 적는다.
    DIST = {"PIL": "pillow", "yaml": "PyYAML", "ruamel": "ruamel-yaml"}

    used: dict[str, set[str]] = {}
    for f in sorted(pkg.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods = [n.module]
            else:
                continue
            for m in mods:
                top = m.split(".")[0]
                if top in std or top == "firelane":
                    continue
                used.setdefault(DIST.get(top, top).lower(), set()).add(f.name)

    proj = tomllib.load((ROOT / "pyproject.toml").open("rb"))["project"]
    declared = {re.match(r"[\w\-]+", d).group(0).lower()
                for d in proj["dependencies"]}

    missing = {k: sorted(v) for k, v in used.items() if k not in declared}
    assert not missing, (
        "파이프라인이 import 하는데 pyproject 필수 의존성에 없다:\n  "
        + "\n  ".join(f"{k}  ← {v}" for k, v in sorted(missing.items()))
        + "\n  설치만 하고 돌리면 ImportError 로 죽는다.")


def test_no_second_dependency_ledger():
    """의존성 대장은 `pyproject.toml` 하나다.

    ★ `requirements*.txt` 가 다시 생기면 잡는다. 손대장이 둘이 되면 반드시
      어긋난다(§18-3) — `requirements-etl.txt` 가 `rasterio` · `pillow` 를
      빠뜨린 채 살아 있었다.
    """
    stray = sorted(p.name for p in ROOT.glob("requirements*.txt"))
    assert not stray, (
        f"두 번째 의존성 대장: {stray}\n"
        "  pyproject.toml 의 dependencies / optional-dependencies 로 옮겨라.")


def test_local_verify_covers_ci():
    """`tools/verify.sh` 가 CI 검사를 전부 포함하는가.

    ★ 2026-08-23. README 는 "받자마자 이것 하나면 된다" 고 하는데
      `verify.sh` 가 CI 검사 다섯을 안 돌고 있었다 — commit_policy ·
      encoding_check · docnum_check · web_manifest · web/data 용량.
      로컬 검증이 CI 의 부분집합이면 **"내 기계에서는 됐는데"** 가 나온다.
      그것을 없애려고 만든 스크립트인데 스스로 그 상태였다.

    ★ 반대 방향은 검사하지 않는다. `verify.sh` 는 `fire-lane` 전량과
      `golden` 을 돌지만 CI 는 못 돈다 — raw 2.5GB 가 저장소에 없다.
      로컬이 CI 보다 **더** 보는 것은 정상이다.
    """
    ci = (ROOT / ".github/workflows/contract.yml").read_text(encoding="utf-8")
    vs = (ROOT / "tools/verify.sh").read_text(encoding="utf-8")

    # ★ 2026-08-23 추가. 검사 목록이 같아도 **환경**이 다르면 결과가 갈린다.
    #   로컬은 uv sync 로 전부 깔려 있고 CI 는 최소한만 깐다.
    #   `verify.sh` 가 그 환경을 흉내내지 않으면 로컬 초록불이 보증이 안 된다.
    assert "CI 환경 재현" in vs, \
        "verify.sh 가 CI 의 좁은 환경을 재현하지 않는다 — 로컬 초록불이 보증이 아니다"

    tools = ("commit_policy", "encoding_check", "docnum_check",
             "web_manifest", "js_graph_check", "web_boot_check")
    missing = [t for t in tools if t in ci and t not in vs]
    assert not missing, (
        f"CI 가 돌리는데 verify.sh 가 안 돌리는 검사: {missing}\n"
        "  로컬이 CI 의 부분집합이면 '내 기계에서는 됐는데' 가 나온다.")

    if "du -sm web/data" in ci:
        assert "web/data" in vs and "du -sm" in vs, \
            "CI 가 web/data 용량을 보는데 verify.sh 는 안 본다"


def test_scan_data_sizes_add_up():
    """`scan_data` 의 제공기관 크기 합이 raw 계층 크기와 같은가.

    ★ 2026-08-23. `psize[k] += sz` 가 루프 변수(`_sz`)가 아니라 **앞 루프의
      마지막 `sz`** 를 더하고 있었다. 함수 스코프에 이름이 살아 있어
      NameError 도 안 나고 `test_static.py` 도 못 잡는다.

      실측(외장 SSD): 전체 5.8GB 인데 폴더 합이 30GB 를 넘었다. 전부
      970.2MB(마지막 파일 크기)의 배수였는데, 숫자가 그럴듯해서 오래 안 보였다.
      **합계와 대조했으면 즉시 드러났다.** 그래서 여기서 대조한다.
    """
    import re
    import subprocess
    import sys
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        for rel, n in (("raw/eais/a.csv", 1_000_000), ("raw/its/b.zip", 2_000_000),
                       ("raw/its/c.zip", 3_000_000), ("landing/x.zip", 5_000_000)):
            p = base / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"\0" * n)
        r = subprocess.run([sys.executable, str(ROOT / "tools/scan_data.py"),
                            "--root", str(base)], capture_output=True, text=True)
    out = r.stdout
    unit = {"B": 1, "KB": 1 << 10, "MB": 1 << 20, "GB": 1 << 30}
    to_b = lambda v, u: float(v) * unit[u]

    # ★ 기대값을 손으로 박지 않는다. §1 의 raw 계층 크기와 §2 의 제공기관
    #   합이 **같아야 한다** 는 것이 불변식이다. 표기 단위가 바뀌어도 산다.
    m = re.search(r"^  raw\s+\d+개\s+([\d.]+) (\w+)", out, re.M)
    assert m, f"§1 에서 raw 계층 줄을 못 읽었다:\n{out}"
    tier = to_b(m.group(1), m.group(2))

    prov = re.findall(r"^  (eais|its)\s+\d+개\s+([\d.]+) (\w+)", out, re.M)
    assert len(prov) == 2, f"§2 에서 제공기관 줄을 못 읽었다:\n{out}"
    got = sum(to_b(v, u) for _, v, u in prov)

    assert abs(got - tier) < tier * 0.02, (
        f"제공기관 합 {got:,.0f}B 가 raw 계층 {tier:,.0f}B 와 다르다\n"
        "  scan_data 의 psize 누적이 엉뚱한 변수를 더하고 있다.")


def test_tidy_never_touches_data():
    """`tools/tidy.py` 가 재생성 불가능한 계층을 절대 지우지 않는가.

    ★ 정리 도구는 잘못 돌면 복구가 안 된다. 규칙(RULES)에 실수로 데이터
      경로가 들어가도 `NEVER` 가 막아야 한다 — 규칙은 사람이 고치고,
      안전장치는 고치지 않는다.

      `data/raw` 는 2.5GB 이고 재취득에 며칠이 걸린다. `data/field` 는
      **재생성 자체가 불가능하다**(8월 20일 오전 10시의 그 골목은 다시 안 온다).
      2026-08-11 에 심링크를 git 이 추적해 원본 2.5GB 를 두 번 날린 저장소다.
    """
    import tidy  # tools/ — pyproject 의 pytest pythonpath 로 잡힌다

    must = ("data/raw", "data/norm", "data/field", "web/data", ".git",
            "data/golden", "data/baseline",
            "data/processed/segments.geojson",
            "data/processed/_manifest.json",
            "data/processed/seg_uid_map.csv")
    for m in must:
        assert m in tidy.NEVER, f"tidy.NEVER 에 {m} 가 없다"
        assert tidy.guarded(tidy.ROOT / m), f"guarded() 가 {m} 를 막지 못한다"
        assert tidy.guarded(tidy.ROOT / m / "안쪽" / "파일.zip"), \
            f"guarded() 가 {m} 하위를 막지 못한다"

    # 규칙에 데이터 경로가 섞여도 scan 결과에 안 나와야 한다
    orig = list(tidy.RULES)
    try:
        tidy.RULES.append(("테스트", ["data/raw", "web/data"], "일부러 넣는다"))
        hit = {str(p.relative_to(tidy.ROOT)) for _, p, _, _ in tidy.scan_fs()}
    finally:
        tidy.RULES[:] = orig
    assert not (hit & {"data/raw", "web/data"}), \
        "규칙에 넣었더니 실제로 잡혔다 — NEVER 가 무력하다"


def test_tidy_knows_the_leftovers_that_bit_us():
    """실제로 사고를 낸 찌꺼기를 `tidy` 가 알고 있는가.

    규칙 목록이 추상적인 위생 항목이 되면 다음에 또 같은 것에 물린다.
    셋 다 **조용히 틀린 것이 실행된** 사고였다.
    """
    import tidy  # tools/ — pyproject 의 pytest pythonpath 로 잡힌다

    globs = {g for _, gs, _ in tidy.RULES for g in gs}
    for g, why in (("data/processed/*.stale_*", "08-18 — 격리본이 진단을 흐렸다"),
                   (".work", "08-13 — raw 옆에 풀린 _unz_* 1,570파일")):
        assert g in globs, f"tidy 규칙에 {g} 가 없다 ({why})"

    # ★ 글롭 문자열을 그대로 요구하면 규칙을 넓힐 때 테스트가 깨진다.
    #   실제로 그랬다 — `fix-*.sh` 를 `*.sh` 로 넓히자 `apply.sh` 문자열이
    #   사라져 빨간불이 됐다. **규칙이 나아졌는데 검사가 막는 건 잘못이다.**
    #   문자열이 아니라 **행동**을 본다: 루트에 옛 패처를 놓고 잡히는가.
    probe = tidy.ROOT / "apply.sh"
    made = not probe.exists()
    if made:
        probe.write_text("#!/bin/bash\necho old\n", encoding="utf-8")
    try:
        hit = {p.name for _, p, _, _ in tidy.scan_fs()}
        assert "apply.sh" in hit, \
            "루트의 옛 패처를 tidy 가 안 잡는다 (08-23 — 새 스크립트를 가렸다)"
    finally:
        if made:
            probe.unlink()

    # tools/ 의 이름 있는 도구는 잡으면 안 된다
    assert not any(p.parent.name == "tools" and p.suffix == ".sh"
                   for _, p, _, _ in tidy.scan_fs()), \
        "tools/*.sh 를 일회성으로 잡는다 — verify.sh 가 지워진다"


def test_tools_declared_in_docs_exist():
    """문서가 이름까지 적어놓은 도구가 실재하는가.

    ★ 2026-08-23. MASTER §18-12 가 획득 게이트를 `acquire.py stage` 라고
      **이름까지 적어놓고** 있었는데 파일이 없었다. `contract.py` 머리말이
      적은 것과 같은 일이다 — *"설계는 있었고 구현이 없었다."*

      그 사이 실제 획득은 `normalize_raw` 가 복사만 하고 검증은 없었고,
      landing 2.4GB 가 raw 와 중복된 채 쌓였다.

    ★ R16(`test_readme_structure_lists_real_files`)은 README 구조 블록만 본다.
      MASTER · PLAN 이 가리키는 도구는 아무도 안 봤다.
    """
    import re

    missing = []
    for rel in ("docs/MASTER.md", "docs/PLAN.md", "README.md"):
        txt = (ROOT / rel).read_text(encoding="utf-8")
        for i, ln in enumerate(txt.splitlines(), 1):
            # `tools/xxx.py` · tools/xxx.py — 실행을 지시하는 표기만 본다
            # ★ `(삭제됨)` 이 붙은 줄은 회고다. 08-18 에 지운 일회성 패처를
            #   "이래서 지웠다" 로 인용하는 자리라 파일이 없는 것이 옳다.
            #   `<!--stale-ok-->` 와 같은 방식 — 표기하는 행위가 곧 기록이다.
            for m in re.findall(r"tools/([\w_]+\.(?:py|sh|mjs))`?\s*(\(삭제됨\))?", ln):
                name, retired = m
                if retired or (ROOT / "tools" / name).exists():
                    continue
                missing.append(f"{rel}:{i}  tools/{name}")
    assert not missing, (
        "문서가 가리키는데 없는 도구:\n  " + "\n  ".join(sorted(set(missing)))
        + "\n  만들거나, 문서에서 지우거나, '미구현' 을 명시하라.")


def test_acquisition_verifies_content_not_size():
    """적재 판정이 크기가 아니라 내용을 보는가.

    ★ `normalize_raw` 의 "이미 있음" 이 `st_size` 비교였다. 313MB 정사영상이
      전송 중 잘려도, 같은 크기의 다른 판이 와도 통과한다. 실증했다 —
      같은 크기 · 다른 sha 두 파일을 놓으면 "이미 있음 1건" 으로 넘어갔다.

      §18-8 이 백업에 대해 적은 문장이 획득에도 그대로 적용된다:
      *"문제는 백업이 없어서가 아니라 백업이 깨진 걸 몰랐던 것이다."*
    """
    src = (ROOT / "src/firelane/normalize_raw.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "st_size == f.stat().st_size" not in code, (
        "normalize_raw 가 크기만 보고 '이미 있음' 을 판정한다.\n"
        "  같은 크기로 잘린 파일이 조용히 통과한다. sha 로 볼 것.")
    assert "_same(" in code, "normalize_raw 가 내용 비교(_same)를 쓰지 않는다"


def test_nothing_writes_into_raw():
    """어떤 코드도 `raw` 에 쓰지 않는가 (§18-1 R1 · §18-10).

    ★ 2026-08-23. `tools/acquire.py` 를 만들면서 sha 대장을
      `RAW / "_acquire.json"` 에 뒀다가 되돌렸다. **검증하겠다고 만든 도구가
      검증 대상을 건드렸다.** 그 순간 대장이 스스로를 무효화한다.

      raw 에 쓰는 것은 이 저장소가 이미 겪은 사고다 — 2026-08-13 에
      `ngii1k.py` 가 zip 을 raw 옆에 풀어 `_unz_*` 8폴더 1,570파일을 만들었고
      raw 파일 수가 40배로 보였다. 그래서 `.work/` 가 생겼다.

    ★ 문자열 패턴으로 본다. 완벽하진 않지만 `RAW / "..."` 꼴의 쓰기 대상
      선언은 잡는다. 읽기(`RAW.glob` · `RAW.rglob` · `RAW / x` 를 읽는 것)는
      정상이므로 **대입되는 상수 경로**만 본다.
    """
    import re

    # ★ 처음에 "RAW / 상수를 변수에 대입하면 쓸 작정" 이라고 짰다가 되돌렸다.
    #   `report.py` 의 소방청 대조 CSV, `terrain.py` 의 DEM zip 은 **읽기**다.
    #   대입 자체는 죄가 아니다. 보아야 하는 것은 **쓰기 동사**다.
    WRITE = ("write_text", "write_bytes", "mkdir", "touch", "unlink",
             "rename", "replace", "to_file", "to_csv", "rmtree")
    bad = []
    for p in sorted(list((ROOT / "src/firelane").rglob("*.py"))
                    + list((ROOT / "tools").glob("*.py"))):
        src = p.read_text(encoding="utf-8")
        # ★ 별칭은 **모듈 상수만** 본다. 처음에 들여쓰기 없는 조건을 안 걸었더니
        #   `cmd_verify` 의 `p = RAW / rel`(읽기) 때문에 `p` 가 파일 전체에서
        #   raw 취급이 됐고, landing 파일을 지우는 `p.unlink()` 가 걸렸다.
        #   지역 루프 변수는 재사용되므로 이름만으로 추적할 수 없다.
        aliases = {"RAW"} | set(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=\s*RAW\s*/", src, re.M))
        pat = "|".join(re.escape(a) for a in aliases)
        for i, ln in enumerate(src.splitlines(), 1):
            if ln.lstrip().startswith("#"):
                continue
            for verb in WRITE:
                if re.search(rf"\b(?:{pat})\b[^#]*\.{verb}\s*\(", ln):
                    bad.append(f"{p.relative_to(ROOT)}:{i}  {ln.strip()[:70]}")
            # shutil.copy/move 의 **목적지** 가 raw 인 경우
            if re.search(rf"(?:copyfile|copy2?|move)\s*\([^,]+,\s*(?:str\()?\s*(?:{pat})\b", ln):
                bad.append(f"{p.relative_to(ROOT)}:{i}  {ln.strip()[:70]}")
            # open(..., "w")
            if re.search(rf"\b(?:{pat})\b[^#]*\.open\s*\(\s*[\'\"][wa]", ln):
                bad.append(f"{p.relative_to(ROOT)}:{i}  {ln.strip()[:70]}")
    assert not bad, (
        "raw 에 쓰려는 코드:\n  " + "\n  ".join(bad)
        + "\n  raw 는 읽기 전용이다(§18-1). 산출물은 processed·저장소 안·.work 로."
    )


def test_acquire_stage_and_quarantine_do_not_fight():
    """편입과 격리가 서로를 되돌리지 않는가.

    ★ 2026-08-23. `--quarantine` 으로 내린 파일이 landing 에 원본으로 남아
      있으면 다음 `--stage` 가 규칙대로 **다시 끌어올렸다.** 실제로
      `firestation_kr_20250701` · `hydrant_point_jngj_20250917` 이 raw 로
      되돌아왔다. 두 명령이 서로를 무한히 되돌린다.

      `normalize_raw` 는 이름 규칙만 알고 대장을 안 읽는다 — 그것이 옳다.
      규칙 정본은 하나여야 하고, 이름 규칙과 대장은 다른 층이다.
      그래서 **판정하는 쪽**(acquire)이 막는다.
    """
    import shutil
    import subprocess
    import sys
    import tempfile

    import yaml

    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    ret = {v["file"] for v in (y.get("retired") or {}).values()
           if isinstance(v, dict) and v.get("file")}
    assert ret, "retired 에 file 이 적힌 항목이 없다 — 이 검사가 무의미해진다"

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        (base / "landing").mkdir()
        (base / "raw").mkdir()
        # 폐기 등재된 파일을 landing 에 놓고 편입시킨다
        for rel in sorted(ret):
            name = Path(rel).name
            src = base / "raw" / rel
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("x\n", encoding="utf-8")
            assert name  # 이름이 있어야 되돌림이 매칭된다

        env = {**__import__("os").environ, "FIRE_LANE_DATA": str(base)}
        r = subprocess.run([sys.executable, str(ROOT / "tools/acquire.py"),
                            "--stage", "--yes"],
                           capture_output=True, text=True, cwd=ROOT, env=env)
        left = sorted(p.name for p in (base / "raw").rglob("*") if p.is_file()
                      and not p.name.startswith("_"))
        quarantined = sorted(p.name for p in (base / "_quarantine").rglob("*")
                             if p.is_file()) if (base / "_quarantine").is_dir() else []
        shutil.rmtree(base / "raw", ignore_errors=True)

    names = {Path(x).name for x in ret}
    assert not (set(left) & names), (
        f"폐기 등재된 파일이 raw 에 남았다: {sorted(set(left) & names)}\n"
        f"{r.stdout[-600:]}")
    assert names <= set(quarantined), (
        f"되돌려지지 않았다. _quarantine: {quarantined}\n{r.stdout[-600:]}")


def test_acquire_ledger_ends_with_newline():
    """sha 대장이 커밋 정책(UTF-8 · LF · 끝 개행)을 지키는가.

    ★ `json.dumps` 는 끝 개행을 안 붙인다. 그래서 pre-commit 훅이 커밋을
      막았다 — 훅이 제 일을 한 것이고 막힌 쪽이 잘못이었다.
    """
    src = (ROOT / "tools/acquire.py").read_text(encoding="utf-8")
    i = src.index("LEDGER.write_text(")
    assert '+ "\\n"' in src[i:i + 200], \
        "LEDGER 를 쓸 때 끝 개행을 안 붙인다 — encoding_check 가 커밋을 막는다"


def test_verify_tells_quarantine_from_loss():
    """`--verify` 가 격리(정상 처분)와 소실(사고)을 구분하는가.

    ★ 2026-08-23. 대장에 있는데 raw 에 없으면 전부 "사라짐" 으로 봤다.
      `--quarantine` 으로 내린 파일이 거기 걸려 **정상 처분이 빨간불**이 됐다.
      게이트가 정상 상태에서 울리면 사람이 그 게이트를 무시하기 시작한다 —
      그 순간 게이트가 없는 것과 같아진다.

      격리는 소실이 아니라 이동이다. `_quarantine` 에 있으면 그렇게 말하고
      대장에서 뺀다. 대장은 **raw 의 현재 상태**를 말하고, 무엇이 있었는지의
      역사는 `sources.yaml` 의 `retired` 가 맡는다.
    """
    src = (ROOT / "tools/acquire.py").read_text(encoding="utf-8")
    assert "QUARANTINE / r" in src, \
        "verify 가 _quarantine 을 안 본다 — 격리를 소실로 오판한다"
    assert "moved" in src and "gone" in src, \
        "verify 가 격리와 소실을 한 목록으로 다룬다"


def test_docs_call_the_entrypoint_through_uv():
    """문서의 `fire-lane` 실행 줄이 `uv run` 을 거치는가.

    ★ 2026-08-23. 문서가 `fire-lane --from segments` 라고 적고 있었는데
      진입점은 `.venv/bin/fire-lane` 에 설치되고 그 폴더는 PATH 에 없다.
      `command not found` 로 죽는다.

      더 나쁜 것은 그 뒤에 일어난 일이다. 파이프라인이 안 돈 채로
      `tools/golden.py check` 를 돌렸고 **통과했다.** golden 은
      `data/processed/segments.geojson` 을 읽는데 그것이 안 바뀌었으니
      옛 산출물을 옛 지문과 비교한 것이다 — 아무것도 증명하지 않는데
      초록불이 뜬다. R11("리팩 전후 동일을 증명하기 전에는 커밋하지 마라")을
      만족한 것처럼 보이게 만든다.

      `tools/verify.sh` 만 `uv run --project` 로 제대로 부르고 있어서
      CI 에서도 안 드러났다.
    """
    import re

    bad = []
    for rel in ("README.md", "docs/MASTER.md", "docs/PLAN.md",
                "src/firelane/README.md", "src/firelane/pipeline.py"):
        p = ROOT / rel
        if not p.exists():
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            # 줄 맨 앞(들여쓰기 허용)에서 시작하는 실행 지시만 본다.
            if re.match(r"^\s*fire-lane(\s|$)", ln) and "uv run" not in ln:
                bad.append(f"{rel}:{i}  {ln.strip()[:60]}")
    assert not bad, (
        "PATH 에 없는 진입점을 그대로 부르는 줄:\n  " + "\n  ".join(bad)
        + "\n  `uv run fire-lane ...` 로 적어라.")


def test_golden_refuses_stale_artifacts():
    """`golden check` 가 낡은 산출물로 통과하지 않는가.

    ★ 2026-08-23. `fire-lane` 이 PATH 에 없어 파이프라인이 안 돈 채로
      `golden.py check` 를 돌렸고 **L1·L2·L3 전부 통과했다.**
      옛 산출물을 옛 지문과 비교했으니 당연하다 — 아무것도 증명하지 않는데
      *"리팩 전후 동일. 다음 덩어리로 넘어가도 된다"* 가 찍힌다.

      R11 은 "증명 전에 커밋하지 마라" 인데, 증명한 것처럼 보이게 만들면
      규칙이 무력해진다. **거짓 초록불은 빨간불보다 나쁘다.**
    """
    import subprocess
    import sys

    src = (ROOT / "tools/golden.py").read_text(encoding="utf-8")
    assert "_staleness" in src, "golden 에 낡음 검사가 없다"
    assert "allow_stale" in src, "낡음을 알고 넘길 탈출구(--allow-stale)가 없다"

    seg = ROOT / "data/processed/segments.geojson"
    fp = ROOT / "data/golden/.code_fingerprint"
    if not seg.exists():
        pytest.skip("산출물이 없다")

    # ★ 2026-08-23. 처음엔 `os.utime` 으로 mtime 을 조작해 검증했다.
    #   지금은 **판정 로직의 내용 해시**를 보므로 mtime 은 무관하다.
    #   지문을 다른 값으로 바꿔 "코드가 바뀐 상태" 를 만든다.
    keep = fp.read_text(encoding="utf-8") if fp.exists() else None
    try:
        fp.write_text("0000000000000000\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools/golden.py"), "check"],
                           capture_output=True, text=True, cwd=ROOT)
        assert r.returncode != 0, (
            "판정 로직이 바뀌었는데 통과했다:\n" + r.stdout[-500:])
        assert "낡" in r.stdout, "왜 막혔는지 말하지 않는다"
    finally:
        if keep is not None:
            fp.write_text(keep, encoding="utf-8")
        else:
            fp.unlink(missing_ok=True)


def test_tidy_ignores_the_virtualenv():
    """`tidy` 가 `.venv` 를 훑지 않는가.

    ★ 2026-08-23. `**/__pycache__` 가 `.venv/lib/.../site-packages` 안까지
      훑어 130여 건이 목록에 올라왔다. 셋 다 나쁘다.
        · uv 가 관리하는 영역이다
        · 지워도 첫 import 때 다시 생긴다 — **매번 같은 목록이 뜬다**
        · 진짜 찌꺼기(일회성 패처 12개 · 백업 7개)가 그 속에 묻힌다

      정리 도구가 매번 백 건을 보고하면 사람이 목록을 안 읽게 된다.
      그러면 도구가 있어도 없는 것과 같다.
    """
    import tidy
    assert ".venv" in tidy.NEVER, "tidy.NEVER 에 .venv 가 없다"
    assert tidy.guarded(tidy.ROOT / ".venv" / "lib" / "x" / "__pycache__"), \
        "guarded() 가 .venv 하위를 막지 못한다"
    hit = [str(p.relative_to(tidy.ROOT)) for _, p, _, _ in tidy.scan_fs()]
    assert not [x for x in hit if x.startswith(".venv")], \
        f"scan 결과에 .venv 가 들어있다: {[x for x in hit if x.startswith('.venv')][:3]}"


def test_acquire_ledger_is_stable_when_nothing_changed():
    """대장이 무변경일 때 파일을 건드리지 않는가.

    ★ 2026-08-23. `at` 을 매번 갱신해서 sha 가 하나도 안 바뀌어도 파일이
      바뀌었다. `--verify` 를 돌릴 때마다 `git diff` 가 생기고, 워킹트리가
      더러워져 `apply` 가 **두 번** 막혔다.

      "아무것도 안 바뀌었는데 diff 가 생긴다" 는 그 자체로 비용이다 —
      진짜 변경이 무의미한 변경 속에 묻힌다.
    """
    src = (ROOT / "tools/acquire.py").read_text(encoding="utf-8")
    i = src.index("def save_ledger")
    body = src[i:i + 1200]
    assert 'cur.get("files") == d.get("files")' in body, \
        "save_ledger 가 내용 비교 없이 매번 쓴다"
    assert body.index('d["at"]') > body.index("return"), \
        "무변경 반환보다 먼저 at 을 찍으면 소용이 없다"


def test_review_page_uses_our_own_ortho():
    """대조 페이지가 **우리** 정사영상을 쓰는가.

    ★ 2026-08-23. 네이버 지도로 대조하려다 접었다 — 하단 표기가
      `국토지리정보원` 이고, 우리 `ortho`(정사영상 2025, 25cm)와 **같은
      항공사진**이다. 같은 것을 두 번 보는 것이라 독립 검증이 아니다.

      다만 "어느 쪽이 맞나" 를 가리는 데는 영상이 심판으로 쓸 수 있다.
      그때도 남의 재압축본이 아니라 **도엽 원본**을 쓴다.

    ★ 외부 지도 타일을 배경으로 끌어오면 이 구분이 무너진다.
    """
    src = (ROOT / "tools/jijeok_review.py").read_text(encoding="utf-8")
    assert "data/ortho/{z}/{x}/{y}.jpg" in src, \
        "우리 정사영상 타일을 안 쓴다"
    for bad in ("map.naver.com", "map.kakao.com", "openstreetmap.org/{z}",
                "tile.openstreetmap"):
        assert bad not in src, f"외부 지도 타일을 배경으로 쓴다: {bad}"


def test_review_page_hides_nothing_it_should_show():
    """대조 페이지가 판정 어휘와 임계를 코드와 맞추는가.

    ★ 임계 3.0m 를 페이지에 손으로 박으면 `seg/params.py` 의 TRUCK 이
      바뀔 때 조용히 어긋난다(R3 — 임계값 정본은 params.py 하나다).
    """
    from firelane.seg.params import TRUCK
    src = (ROOT / "tools/jijeok_review.py").read_text(encoding="utf-8")
    assert f"TH = {TRUCK}" in src, \
        f"jijeok_review.TH 가 params.TRUCK({TRUCK}) 과 다르다"
    # 판정 넷이 다 있어야 CSV 가 해석된다
    for k in ("우리가 맞다", "지적이 맞다", "둘 다 아니다", "못 보겠다"):
        assert k in src, f"판정 어휘 누락: {k}"


def test_review_page_lands_where_serve_can_find_it():
    """`review.html` 이 `serve.py` 가 주는 위치에 놓이는가.

    ★ 2026-08-23. `paths.WEB` 이 `web/data` 인데 그걸 그대로 써서
      `web/data/review.html` 에 만들었다. `serve.py` 는 `web/` 을 루트로
      주므로 `http://localhost:8000/review.html` 이 404 였다.

      도구가 "만들었다" 고 찍고 사람은 열지 못하는 상태다 — 이 저장소가
      반복해 겪은 그 모양(초록불인데 실제로는 안 됨)의 파일 버전이다.
    """
    src = (ROOT / "tools/jijeok_review.py").read_text(encoding="utf-8")
    assert "WEBROOT = WEB.parent" in src, \
        "review.html 을 web/data 에 만든다 — serve.py 가 못 준다"
    assert "dst = WEBROOT / OUT" in src, "저장 위치가 WEBROOT 이 아니다"
    # 타일 상대경로는 web/ 기준이라야 맞는다
    assert '"data/ortho/{z}/{x}/{y}.jpg"' in src, \
        "web/ 기준 타일 경로가 아니다"
    ign = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "web/review.html" in ign, "생성물인데 gitignore 에 없다"


def test_seg_label_is_not_used_as_an_identifier():
    """`seg_label` 을 식별자처럼 쓰는 곳이 없는가.

    ★ 2026-08-23. `seg_label` 은 표시용이다. 1,101구간 중 **273(24.8%)이
      중복**이고 62종은 같은 라벨인데 판정이 다르다 —
      `동계천로43번길 1-5` 하나가 unknown(5.26) · blocked(1.04) ·
      blocked(1.19) 세 골목을 가리킨다.

      대조 페이지가 라벨만 띄우는 바람에 사람이 어느 골목인지 못 골랐다.
      네이버로 5.6m 를 잰 골목과 페이지가 보여준 1.19m 짜리가 서로 달랐다.

      고유 식별자는 `seg_uid` 다(결정 72 · 중복 0 · 실행 간 유지).
      MASTER §11 이 "화면 표기는 seg_label, 외부 참조는 seg_uid" 라고
      적어놨는데 그 경계가 지켜지지 않았다.
    """
    src = (ROOT / "tools/jijeok_review.py").read_text(encoding="utf-8")
    assert '"uid": r.seg_uid' in src, "review 항목에 seg_uid 가 없다"
    assert "${d.uid}" in src, "화면에 seg_uid 를 안 띄운다"
    assert '"sib"' in src, "같은 라벨을 쓰는 형제 수를 안 센다"


def test_ship_covers_the_release_checklist():
    """`tools/ship.py` 가 내보내기 전 검사를 전부 부르는가.

    ★ 2026-08-23. 푸시 전에 밟아야 하는 것이 흩어져 있었다 —
      `verify.sh` · `tidy.py` · `docnum_check.py` · 문서 4축 · `golden`.
      **손으로 기억해야 하는 목록은 언젠가 하나를 빠뜨린다.**
      같은 날 세 번 났다: golden 을 파이프라인 없이 돌려 거짓 초록불을 봤고,
      `_backup_apply_*` 가 여덟 개 쌓였고, CI 가 `gis` 를 안 보는 채로
      PR 이 머지되고 있었다.

    ★ `verify.sh` 와 역할이 다르다.
        verify.sh   코드가 도는가
        ship.py     내보내도 되는가 (위 + 문서 + 위생 + git)
      중복 구현하지 않고 `verify.sh` 를 부른다.
    """
    src = (ROOT / "tools/ship.py").read_text(encoding="utf-8")
    for tool in ("verify.sh", "tidy.py", "docnum_check.py", "golden.py"):
        assert tool in src, f"ship.py 가 {tool} 을 안 부른다"
    # 브랜치가 CI 트리거에 있는지 — 검사 없이 머지되는 것을 막는 핵심
    assert "contract.yml" in src, "ship.py 가 CI 트리거를 안 본다"
    assert "--push" in src, "push 까지 이어지지 않는다"


def test_ci_installs_what_the_tests_import():
    """CI 가 테스트에서 쓰는 외부 패키지를 전부 깔았는가.

    ★ 2026-08-23. `test_ingest_kinds_are_documented` 와
      `test_acquire_stage_and_quarantine_do_not_fight` 가 `import yaml` 을
      쓰는데 CI 는 `pytest shapely numpy ruff` 만 깔고 `--no-deps` 로
      설치한다. **로컬은 `uv sync` 로 전부 깔려 초록불이었고 CI 만
      빨간불이었다.**

      `test_local_verify_covers_ci` 는 "verify.sh 가 CI 검사를 다 부르는가"
      만 봤다. 반대 방향 — **CI 환경이 로컬보다 좁은가** — 은 아무도 안 봤다.
      부분집합 검사는 양방향이어야 한다.

    ★ 정규식으로 YAML 을 파싱해 우회하지 않는다. 대장은 중첩이 깊고
      `retired.file` 처럼 두 단계 아래를 읽어야 한다. 취약한 파서를
      테스트에 두면 그 파서가 또 하나의 버그 원천이 된다.
    """
    import ast
    import re
    import sys

    ci = (ROOT / ".github/workflows/contract.yml").read_text(encoding="utf-8")
    installed: set[str] = set()
    for m in re.finditer(r"pip install ((?:[\w.\-\[\]]+ ?)+)", ci):
        for tok in m.group(1).split():
            if tok.startswith("-") or tok == ".":
                continue
            installed.add(re.split(r"[<>=\[]", tok)[0].lower())

    # ★ 2026-08-27. CI 가 `pip install` 손목록에서 `uv sync --all-extras` 로
    #   바뀌었다. 이 검사는 `pip install` 만 읽고 있어서 **설치 목록을 빈
    #   집합으로 보고** shapely·pyyaml 이 없다고 했다. 검사 자체가 낡은
    #   가정 위에 서 있었던 것이다 — 정본이 둘이면 어긋난다(§18-3)의
    #   또 다른 얼굴이다.
    #
    #   uv sync 는 pyproject 를 통째로 깐다. 그러니 손목록을 유지하지 말고
    #   **pyproject 를 읽는다.** 목록을 손으로 관리하지 않는 것이 이 저장소의
    #   방식이다.
    if re.search(r"uv sync", ci):
        import tomllib
        with open(ROOT / "pyproject.toml", "rb") as fh:
            pp = tomllib.load(fh)
        deps = list(pp["project"].get("dependencies", []))
        if "--all-extras" in ci:
            for group in pp["project"].get("optional-dependencies", {}).values():
                deps += list(group)
        for d in deps:
            installed.add(re.split(r"[<>=\[; ]", d)[0].strip().lower())

    # 로컬 전용 도구(pandas 등)를 쓰는 테스트는 skip 으로 빠지므로 제외한다.
    # 여기서 보는 것은 **모듈 최상단** import — 그것은 수집 단계에서 죽는다.
    std = set(sys.stdlib_module_names)
    DIST = {"yaml": "pyyaml", "PIL": "pillow"}
    CI_TESTS = ("test_guards.py", "test_static.py", "test_reproducibility.py",
                "test_layering.py")

    need: dict[str, set[str]] = {}
    for name in CI_TESTS:
        f = ROOT / "tests" / name
        if not f.exists():
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods = [n.module]
            for m in mods:
                top = m.split(".")[0]
                # ★ tools/ 의 모듈은 pyproject 의 pytest pythonpath 로 잡힌다.
                #   외부 패키지가 아니므로 pip install 대상이 아니다.
                #   목록을 손으로 유지하지 않는다 — 파일 존재로 판정한다.
                if top in std or top == "firelane" or top == "pytest":
                    continue
                if (ROOT / "tools" / f"{top}.py").exists():
                    continue
                need.setdefault(DIST.get(top, top).lower(), set()).add(name)

    missing = {k: sorted(v) for k, v in need.items() if k not in installed}
    assert not missing, (
        "CI 가 안 깔았는데 테스트가 import 한다:\n  "
        + "\n  ".join(f"{k}  ← {v}" for k, v in sorted(missing.items()))
        + "\n  contract.yml 의 pip install 에 추가하라."
        "\n  ★ 로컬은 uv sync 로 전부 깔려 있어 이 실패가 안 보인다.")


def test_width_samples_are_kept():
    """`widths()` 가 표본을 버리지 않는가.

    ★ 2026-08-23. 표본 배열을 만들고 `min` 만 뽑아 버렸다. 그래서 폭을
      **함수 `w(s)` 로** 다룰 수가 없었다.

      `min` 은 최악의 통계량이다 — 표본 하나가 틀리면 판정이 뒤집힌다.
      `DM02647`(커버율 0.056 · wmin 10.51m) · `DM02916`(0.231 · 27.46m)
      둘 다 `min` 이 이상치를 집은 것이고, 파이프라인이 커버율로 이미
      지목하고 있었다.

    ★ 판정은 안 바꾼다. 산출물 컬럼도 안 더한다. `width_samples.csv` 를
      따로 낼 뿐이라 golden 지문이 그대로다.
    """
    w = (ROOT / "src/firelane/seg/width.py").read_text(encoding="utf-8")
    assert "_rows" in w, "widths() 가 표본을 모으지 않는다"
    assert "_n_try, _rows" in w, "_covr() 가 표본을 반환하지 않는다"

    s = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    # ★ 2026-08-24. 종전 `"wcov, wnt, wrows" in s` 는 4-튜플로 늘렸을 때
    #   **부분문자열이라 그냥 통과했다.** 우연히 통과하는 검사는 검사가
    #   아니다. 언패킹 전체를 본다.
    assert "(wcov, wnt, wrows, wneff) = W[uid]" in s, \
        "호출부 언패킹이 _covr() 반환과 다르다"
    assert "width_samples.csv" in s, "표본을 파일로 안 남긴다"
    # 결측도 남겨야 "어디가 비었는지" 를 알 수 있다
    assert '"drop"' in w, "결측 사유(drop)를 안 남긴다"


def test_passage_width_is_not_just_min():
    """통과폭이 `min` 과 다른 정의인가 — 그리고 물리적으로 맞는가.

    ★ 2026-08-23. `tools/width_fn.py` 를 만들면서 정의를 한 번 틀렸다.
      "차 길이만큼 연속으로 이어지는 폭" 으로 짰는데 그것은 **주차 가능
      여부**지 통과가 아니다. 40m 구간 가운데 12m 가 2m 로 막혔는데
      양쪽이 넓다는 이유로 5.0 을 줬다.

      **들어갈 수 있다와 통과한다는 다르다.**

          통과폭 = max{ c : w(s) < c 인 모든 구간의 길이가 car 미만 }

      `car = 0` 이면 `wmin` 과 같아진다. 지금 판정이 그 특수 경우다.
    """
    import width_fn  # tools/ — pyproject 의 pytest pythonpath

    def pts(f):
        return [(float(s), f(s)) for s in range(0, 41, 2)]

    CAR = 8.0
    # 한 점만 좁다 → 병목 길이가 차보다 짧다 → 통과
    noise = pts(lambda s: 2.0 if s == 20 else 5.0)
    assert abs(width_fn.opening(noise, CAR) - 5.0) < 0.01, \
        "짧은 병목을 통과 불가로 본다 — min 과 다를 게 없어진다"

    # 12m 가 좁다 → 차보다 길다 → 못 간다
    wall = pts(lambda s: 2.0 if 14 <= s <= 26 else 5.0)
    assert abs(width_fn.opening(wall, CAR) - 2.0) < 0.01, \
        "차보다 긴 병목을 통과로 본다 — 못 가는 길을 간다고 한다"

    # car=0 이면 min 과 같다
    assert abs(width_fn.opening(wall, 0.0) - 2.0) < 0.01

    # ★ 2026-08-23 두 번째 정정. 구간이 차보다 짧으면 **병목이 car 를 넘을
    #   수가 없어** 모든 후보가 통과가 되고 최댓값이 나왔다.
    #   실제 산출에서 길이 5.8m 구간이 `opening 49.30m` 를 받았다 —
    #   49m 짜리 골목은 없다. **낙관적으로 틀리느니 min 을 쓴다.**
    assert abs(width_fn.opening([(1.4, 2.75), (4.3, 49.3)], CAR) - 2.75) < 0.01, \
        "구간이 차보다 짧은데 통과폭을 낙관적으로 준다"

    # 표본이 적으면 병목 길이를 잴 수 없다. 표본 간격 2m 라 4개는 있어야 한다.
    assert abs(width_fn.opening([(2.0, 1.7), (10.0, 45.5), (18.0, 8.0)], CAR)
               - 1.7) < 0.01, "표본 3개로 병목 길이를 판정한다"

    # 막힌 길이 — ★ 표본 사이는 선형 보간한다.
    #   s=12 에서 5m, s=14 에서 2m 이므로 3m 를 지나는 지점은 s=13.33 이다.
    #   양끝 합쳐 13.33m 가 정답이고 12m 가 아니다.
    #   처음에 12m 를 기대값으로 박았다가 걸렸다 — 표본 격자에 값을
    #   반올림하면 그것이 곧 오차가 된다.
    assert abs(width_fn.blocked_len(wall, 3.0) - 13.33) < 0.1
    assert abs(width_fn.blocked_len(noise, 3.0) - 1.33) < 0.1


def test_golden_staleness_ignores_comments():
    """`golden` 의 낡음 검사가 **주석 변경**을 로직 변경으로 보지 않는가.

    ★ 2026-08-23. 처음엔 `mtime` 을 봤다. 조잡했다 — **주석 한 줄만 고쳐도
      "낡았다"** 가 뜬다. 하루에 판정 파일을 스무 번 고쳤고 그중 판정을
      바꾼 것은 0 번인데 매번 막혔다.

      **게이트가 정상 상태에서 울리면 사람이 `--allow-stale` 을 쓰기
      시작하고, 그 순간 게이트가 죽는다.** `unknown` 을 회색으로 두는 것과
      같은 이유로, 경고는 참일 때만 울려야 한다.

      주석·docstring·빈 줄을 AST 로 걷어내고 남은 것만 해시한다.

    ★ 이 검사를 만들면서 테스트를 한 번 틀렸다. `TRUCK      = 3.0` 이
      정렬 공백을 갖고 있는데 `replace("TRUCK = 3.0", ...)` 로 바꾸려 해서
      아무것도 안 바뀌었고, **해시가 정상인데 고장 난 줄 알았다.**
      여기서는 정규식으로 바꾼다.
    """
    import re
    import subprocess
    import sys

    fp = ROOT / "data/golden/.code_fingerprint"
    seg = ROOT / "data/processed/segments.geojson"
    if not seg.exists():
        pytest.skip("산출물이 없다")

    def stale() -> str:
        # ★ `sys.path.insert` 를 문자열로 쓰면 `test_sys_path_해킹이_없다`
        #   가 잡는다. 정당한 지적이라 PYTHONPATH 로 넘긴다 —
        #   경로 조작을 코드에 심지 않는다는 규칙은 문자열 안에서도 같다.
        import os
        env = dict(os.environ, PYTHONPATH=str(ROOT / "tools"))
        r = subprocess.run(
            [sys.executable, "-c",
             "import golden; print(golden._staleness())"],
            capture_output=True, text=True, cwd=ROOT, env=env)
        return r.stdout.strip()

    keep = fp.read_text(encoding="utf-8") if fp.exists() else None
    W = ROOT / "src/firelane/seg/width.py"
    P = ROOT / "src/firelane/seg/params.py"
    w0, p0 = W.read_text(encoding="utf-8"), P.read_text(encoding="utf-8")
    try:
        fp.unlink(missing_ok=True)
        assert stale() == "[]", "기준선을 만들 때 낡았다고 한다"

        W.write_text(w0.replace("class WidthEngine", "# 주석\nclass WidthEngine", 1),
                     encoding="utf-8")
        assert stale() == "[]", \
            "주석만 고쳤는데 낡았다고 한다 — 게이트가 정상 상태에서 울린다"
        W.write_text(w0, encoding="utf-8")

        P.write_text(re.sub(r"^TRUCK\s*=\s*3\.0", "TRUCK      = 3.5",
                            p0, count=1, flags=re.M), encoding="utf-8")
        assert stale() != "[]", "임계값을 바꿨는데 안 잡는다 — 게이트가 죽었다"
    finally:
        W.write_text(w0, encoding="utf-8")
        P.write_text(p0, encoding="utf-8")
        if keep is not None:
            fp.write_text(keep, encoding="utf-8")
        else:
            fp.unlink(missing_ok=True)


def test_sample_writer_uses_a_key_that_survives_merging():
    """표본 파일이 **병합 후에도 유효한 키**를 쓰는가.

    ★ 2026-08-23. `_SAMPLES[uid]` 로 넣었다. `uid` 는 노딩 단위 키이고
      `seg_uid` 는 병합이 끝난 뒤 `attach_seg_uid()` 가 붙인다.
      **완전히 다른 키다.** 그래서 19,393개를 모으고 **0행을 썼다** —
      필터가 전부 걸렀다.

      더 나쁜 것은 로그가 그걸 말하고 있었다는 점이다.

          폭 표본 0행 (19,393 유효 · -19,393 결측)

      **음수가 나온 순간 알아챘어야 했다.** 집계도 쓴 것이 아니라 모은 것
      전부를 세고 있었다.
    """
    src = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    assert "_SAMPLES[sid]" in src, \
        "표본 키가 sid 가 아니다 — 병합 후 매칭이 안 된다"
    assert "zip(g.seg_id, g.seg_uid" in src, \
        "seg_id → seg_uid 매핑 없이 쓴다"
    # 집계는 쓴 행 기준이어야 한다
    i = src.index("def _write_samples")
    body = src[i:i + 2500]
    assert "ok += r[" in body, "쓴 행이 아니라 모은 것 전부를 센다"


def test_ingest_can_retry_only_what_failed():
    """`ingest` 가 실패한 소스만 다시 돌릴 수 있는가.

    ★ 2026-08-23. 19종을 한 덩어리로 돌아서 **하나가 FAIL 하면 전체가
      무효**였다. 그리고 그 실패가 비결정적이다(PLAN §1-19) — 같은 입력·
      같은 코드로 1회차 `turn_restriction`·`cctv`, 2회차 통과, 3회차
      `ngii_road`, 4회차 `node_link`. **하루에 세 번 났고 매번 다른
      소스였다.** 그때마다 200초를 다시 태웠다. 성공한 18종은 산출물이
      멀쩡한데도.

      `_manifest.json` 에 소스별 status 가 이미 있었다. 구조는 있는데
      그것을 읽어 고르는 경로가 없었을 뿐이다.

    ★ `--only` 가 대장을 통째로 덮어쓰던 문제(2026-08-22)는 이미 병합으로
      고쳐져 있다. `--retry-failed` 는 그 위에 올라간다.
    """
    src = (ROOT / "src/firelane/ingest.py").read_text(encoding="utf-8")
    assert "--retry-failed" in src, "실패분만 재시도할 방법이 없다"
    assert '"FAIL", "MISSING"' in src, "무엇을 실패로 볼지 안 적혀 있다"
    assert "a.only = bad" in src, "고른 것을 --only 경로에 태우지 않는다"

    # 파이프라인이 실패했을 때 그 방법을 알려줘야 한다
    pl = (ROOT / "src/firelane/pipeline.py").read_text(encoding="utf-8")
    assert "--retry-failed" in pl, "ingest 실패 시 재시도 방법을 안 알려준다"


def test_ingest_keeps_the_unzip_cache():
    """`.work` 압축 해제분을 성공 시 남기는가.

    ★ 2026-08-23. 매 실행 지웠더니 `캐시 0` 이 매번 떴다. `ngii1k` 묶음만
      도엽 74장 + NGI 143장을 다시 푼다 — ingest 180초의 대부분이 여기다.

    ★ 지우던 이유는 있었다 — 2026-08-13 에 `_unz_*` 8폴더 1,570파일이
      raw 옆에 풀려 raw 파일 수가 40배로 보였다. 그래서 `.work` 가 생겼다.
      **지금은 raw 밖이라 그 사고가 안 난다.**

    ★ 실패했을 때는 지운다. 반쯤 풀린 것이 다음 실행을 오염시킨다.
    """
    src = (ROOT / "src/firelane/ingest.py").read_text(encoding="utf-8")
    assert "--keep-work" in src, ".work 를 남길 방법이 없다"
    assert "_failed or not a.keep_work" in src, \
        "실패했을 때도 .work 를 남긴다 — 반쯤 풀린 것이 오염을 만든다"

    pl = (ROOT / "src/firelane/pipeline.py").read_text(encoding="utf-8")
    assert "--keep-work" in pl, "파이프라인이 캐시를 안 쓴다"

    # tidy 가 .work 를 알고 있어야 쌓이지 않는다
    import tidy
    assert any(".work" in g for _, gs, _ in tidy.RULES for g in gs), \
        "tidy 가 .work 를 모른다 — 캐시가 무한히 쌓인다"


def test_every_dataset_says_where_it_is_used():
    """대장의 모든 소스가 `feeds` 를 갖는가 (R4 · MASTER §18-3a).

    ★ 2026-08-23. 28종 중 **21종이 비어 있었다.**
      §18-3a 가 *"못 채우면 raw 에 둘 이유가 없다"* 라고 적어놨는데
      아무도 안 채웠다. 규칙은 있고 강제자가 없었다 — 오늘 반복해 본 그 모양.

      채우고 나니 **참조 0곳이 넷** 드러났다.

          node_point        turn_restriction 필터로만. 직접 참조 0
          fire_access       report.py 가 raw CSV 를 직접 읽는다
          enforcement       85,380행을 ingest 하고 아무도 안 읽는다
          hydrant_summary   5행. 미투입

      `feeds` 는 문서가 아니라 **"이 데이터를 왜 받았나" 의 답**이다.
      못 적으면 안 받는 게 맞다.
    """
    import yaml

    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    # ★ 2026-08-30. `feeds: []` 는 **판정 결과**다(grade → unused, R4).
    #   그것을 금지하면 unused 가 영원히 나올 수 없고 R4 목록이 다시 빈다
    #   — 08-23 에 고친 그 상태로 되돌아간다.
    #
    #   이 docstring 이 이미 답을 적고 있다: *"안 쓰이면 그렇게 적어라."*
    #   요구는 "비지 않을 것" 이 아니라 **판단을 적을 것** 이다.
    #   빈 값 + 사유(feeds_why) 는 판단이고, 사유 없는 빈 값은 방치다.
    miss = [k for k, v in (y.get("datasets") or {}).items()
            if not ((v or {}).get("feeds") or (v or {}).get("feeds_why"))]
    assert not miss, (
        f"feeds 가 비어 있다 ({len(miss)}종): {miss}\n"
        "  R4 — 못 채우면 raw 에 둘 이유가 없다.\n"
        "  '어디에 쓰이는가' 를 적어라. 안 쓰이면 그렇게 적어라."
    )


def test_vehicle_offtracking_is_physical():
    """내륜차 계산이 물리적으로 맞는가.

    ★ 회전할 때 뒷바퀴가 앞바퀴보다 안쪽으로 돈다. 그만큼 폭이 더 필요하다.

          Δ = R - √(R² - L²)        1차 근사는 L²/(2R)

      R 이 L 에 가까워지면 근사가 무너진다. 골목에는 R < 8m 인 곳이 실제로
      있으므로 정확식을 쓴다. R=8·L=4 에서 근사 1.000 vs 정확 1.072 —
      7cm 차이고 그것이 3.0m 임계 근처에서는 판정을 가른다.
    """
    import math

    from firelane.seg import vehicle as V

    assert V.offtracking(None) == 0.0
    assert V.offtracking(1e9) == 0.0, "직선인데 내륜차가 있다"

    for R in (50.0, 20.0, 12.0, 8.0):
        got = V.offtracking(R)
        exact = R - math.sqrt(R * R - V.WHEELBASE ** 2)
        assert abs(got - exact) < 1e-6, f"R={R} 에서 근사식을 쓴다"

    # 반경이 작을수록 더 필요하다
    assert V.offtracking(8.0) > V.offtracking(20.0) > V.offtracking(50.0)
    # 축거보다 작은 반경은 물리적으로 못 돈다
    assert V.offtracking(2.0) == V.WHEELBASE
    assert not V.can_turn(6.0), "최소회전반경보다 급한데 돌 수 있다고 한다"
    assert V.can_turn(None), "직선을 못 돈다고 한다"

    # 직선 필요폭이 params.TRUCK 과 맞물려야 한다
    from firelane.seg.params import TRUCK
    assert abs(V.required_width() - TRUCK) < 1e-9, (
        f"직선 필요폭 {V.required_width()} 와 TRUCK {TRUCK} 이 어긋난다 — "
        "둘 중 하나만 고치면 판정과 경로가 갈린다")


def test_edge_cost_blocks_what_cannot_pass():
    """통행 비용이 못 가는 길을 실제로 막는가.

    ★ 경로 탐색은 이미 있었다 — `graph.access_corridor()` 가 Dijkstra 로
      `route_usage` 를 낸다(579구간). **없던 것은 비용 함수다.**
      `weight="length"` 라 거리만 봐서 `blocked` 159구간도 최단이면
      지나갔다. 그러면 "소방차가 갈 수 있는 길" 이 아니라 "제일 짧은 선" 이다.

    ★ `unknown` 352 + `needs_cv` 190 = 절반이 "모른다" 다. 전부 막으면
      그래프가 끊겨 경로가 아예 안 나온다. `lenient` 로 가른다.
      **어느 쪽이든 `blocked` 는 막는다** — 그것만은 판정이 확정이다.
    """
    import math

    from firelane.seg import vehicle as V

    assert V.edge_cost(40, 1.2, "blocked") == math.inf
    assert V.edge_cost(40, 9.9, "blocked", lenient=True) == math.inf, \
        "lenient 에서 blocked 가 뚫린다"
    assert V.edge_cost(40, 2.8, "clear") == math.inf, "필요폭 미만인데 통과"
    assert V.edge_cost(40, 5.0, "clear", 6.0) == math.inf, \
        "최소회전반경보다 급한데 통과"

    # 넓은 직선은 거리 그대로
    assert V.edge_cost(40, 5.0, "clear") == 40.0
    # 여유가 적으면 비싸다
    assert V.edge_cost(40, 3.2, "clear") > 40.0
    # 모르는 곳은 lenient 에서 싸진다
    strict = V.edge_cost(40, None, "unknown")
    soft = V.edge_cost(40, None, "unknown", lenient=True)
    assert math.isfinite(strict) and soft < strict, \
        "lenient 가 모르는 곳을 안 열어준다 — 그래프가 끊긴다"


def test_vehicle_spec_has_a_source():
    """차량 제원이 대장에 있고 출처를 갖는가.

    ★ 2026-08-23. `seg/vehicle.py` 를 만들면서 전폭 2.5 · 축거 4.0 ·
      최소회전반경 8.0m 를 **모듈 상수로 박았다.** "표준규격 중앙값" 이라고
      적었을 뿐 어느 문서 몇 쪽인지가 없었다.

      **그것이 이 저장소가 계속 막아온 "근거 없는 상수" 다.** 같은 날
      `CCTV_RANGE = 25.0` 을 두고 *"계산으로 예상한 값을 그대로 상수에
      박으면 그 순간 근거 없는 상수가 하나 더 생긴다"* 고 적어놓고 어겼다.

      제원은 `sources.yaml` 의 `vehicle_spec` 에서 읽는다. **기본값을 두지
      않는다** — 없으면 모듈이 죽는다. 기본값을 두면 아무도 안 채우고
      그 값이 판정에 들어간다(`feeds` 21종이 비어 있던 것과 같은 이유).
    """
    import yaml

    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    s = y.get("vehicle_spec")
    assert s, "sources.yaml 에 vehicle_spec 이 없다"
    for k in ("width_m", "length_m", "wheelbase_m", "turn_radius_m",
              "clearance_m", "source", "verified", "feeds"):
        assert s.get(k) not in (None, ""), f"vehicle_spec.{k} 가 비었다"

    # 모듈이 상수를 다시 박지 않았는가
    src = (ROOT / "src/firelane/seg/vehicle.py").read_text(encoding="utf-8")
    import re
    hard = re.findall(r"^(WIDTH|LENGTH|WHEELBASE|TURN_R|CLEARANCE)\s*=\s*[\d.]",
                      src, re.M)
    assert not hard, f"모듈에 제원 상수가 박혀 있다: {hard}"
    assert "SpecMissing" in src, "제원이 없을 때 죽지 않는다"

    # 직선 필요폭이 params.TRUCK 과 맞물려야 한다
    from firelane.seg import vehicle as V
    from firelane.seg.params import TRUCK
    assert abs(V.required_width() - TRUCK) < 1e-9, (
        f"vehicle_spec 의 width_m + clearance_m = {V.required_width()} 인데 "
        f"TRUCK = {TRUCK} 이다 — 판정과 경로가 갈린다")


def test_unverified_vehicle_spec_is_announced():
    """미검증 제원으로 낸 결과가 그 사실을 말하는가.

    ★ 폭 값이 `width_verified: false` 라 화면 상단에 경고가 뜨는 것과
      같은 규칙이다. **미검증 값이 검증된 값처럼 쓰이면** 그 순간
      숫자가 사실이 된다(MASTER §18-3a `verified` 항목).
    """
    src = (ROOT / "tools/route_probe.py").read_text(encoding="utf-8")
    assert 'get("verified")' in src, "제원 검증 여부를 안 본다"
    assert "참고값이지 판정이 아니다" in src, "미검증임을 화면에 안 알린다"


def test_route_usage_is_not_a_passability_claim():
    """`route_usage` 가 통행 가능성을 주장하지 않는가.

    ★ 2026-08-24 실측. `access_corridor()` 는 **폭 산출보다 먼저** 돈다
      (`segments.py` 194줄 vs 435줄). 그래서 `weight="length"` 밖에 못 쓴다.

          route_usage > 0        579구간
            그중 blocked          41   ★ 폭 0.41m 를 70회 지나간다
            폭 3.0m 미만         168

      스키마는 정직하게 *"최단경로 사용횟수"* 라고 적혀 있다. 문제는 이름이
      **"출동 경로" 로 읽힌다**는 것이다. 화면이 아직 이 값을 안 써서
      잘못된 지도가 나가지는 않았다.

    ★ 순서를 바꾸는 대신 **한 번 더 돈다**(`_write_route`). 순서를 바꾸면
      회랑 산정(표출 스코프)이 폭에 의존하게 되어 계보가 꼬인다.
      결과는 `route_vehicle.csv` 로 따로 낸다 — 산출물 컬럼을 안 더하므로
      golden 지문이 그대로다.
    """
    rep = (ROOT / "src/firelane/seg/report.py").read_text(encoding="utf-8")
    i = rep.index('"route_usage"')
    desc = rep[i:i + 200]
    for bad in ("통행 가능", "진입 가능", "소방차가 갈"):
        assert bad not in desc, \
            f"route_usage 설명이 통행 가능성을 주장한다: {bad}"

    seg = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    assert "_write_route" in seg, "차량 비용 경로를 안 낸다"
    assert "route_vehicle.csv" in seg, "2차 경로 결과를 안 남긴다"
    # 산출물 컬럼을 더하면 golden 이 깨진다
    assert "route_vehicle=" not in seg, \
        "route_vehicle 을 segments 컬럼으로 넣었다 — golden 이 깨진다"


def test_route_does_not_pass_through_blocked_edges():
    """차량 경로가 통행 불가 엣지를 지나가지 않는가.

    ★ 2026-08-24. 처음엔 막힌 엣지에 `BIG = 1e7` 을 주고 그래프에 남겼다.
      `math.inf` 를 networkx 가 못 다루기 때문이었다. 그러나 **다른 길이
      없으면 Dijkstra 가 그 엣지를 쓴다.**

          통행 불가 416  ·  경로에 쓰인 구간 996

      "막힌 길로라도 도달" 이라 답이 아니다. 막힌 엣지를 **빼고** 돈다.
      도달하지 못하면 그것이 사실이다 — `unknown` 352구간을 회색으로
      남기는 것과 같은 규칙이다.

    ★ `reachable` 은 양 끝 노드가 모두 도달 가능할 때만 1 이다.
      한쪽만 닿으면 그 구간에 들어갈 수 없다.
    """
    src = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    i = src.index("def _write_route")
    body = src[i:i + 6000]
    assert "P.remove_edges_from" in body, \
        "막힌 엣지를 그래프에 남겨둔 채 경로를 돈다"
    assert 'd["blocked"]]' in body, "무엇을 뺄지 blocked 로 안 고른다"
    assert "reachable" in body, "도달 가능 여부를 안 낸다"
    assert 'd["a"] in reach and d["b"] in reach' in body, \
        "한쪽 끝만 닿아도 도달로 본다 — 그 구간에는 못 들어간다"


def test_route_graph_snaps_nodes_like_build_graph():
    """2차 경로가 `graph.py` 와 같은 규칙으로 노드를 묶는가.

    ★ 2026-08-24. `_write_route` 가 끝점을 `round(x / 0.5)` 격자로 묶었다.
      **0.02m 차이로 노드가 갈린다** — 10.24 는 격자 20, 10.26 은 21 이다.
      그 결과 폭 15~18m 대로가 "도달 불가" 로 나왔다.

          동계로 6-323      clear  폭 14.96  282m   ← 도달 불가
          경양로347번길 1-347 clear  폭 15.0   255m   ← 도달 불가

      `graph.py` 는 같은 문제를 union-find 로 푼다(§4 노드 접합).
      `NODE_TOL` 안의 끝점을 묶으므로 경계가 없다.

    ★ **두 곳이 다른 규칙으로 노드를 묶으면 그래프가 두 개가 된다.**
      `route_usage` 와 `route_vehicle` 이 서로 다른 위상 위에서 계산되면
      비교 자체가 성립하지 않는다.
    """
    pytest.importorskip("geopandas")   # ★ CI 는 로컬보다 좁다.
    # 2026-08-24. 이 테스트는 PR #40 이 먹어서 한 번도 CI 를 안 거쳤다.
    src = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    i = src.index("def _write_route")
    body = src[i:i + 8000]
    # ★ 문자열 존재가 아니라 **실제로 도는지**를 본다. 처음에 `"STRtree" in
    #   body` 로만 봤더니 import 줄을 지워도 주석에 남은 이름 때문에 통과했다.
    assert "_tree = STRtree(_pts)" in body, "격자 반올림으로 노드를 묶는다"
    assert "_pts[i].distance(_pts[j]) <= NODE_TOL" in body, \
        "graph.py 와 다른 허용치로 묶는다"
    assert "_par[max(ri, rj)] = min(ri, rj)" in body, "union-find 접합이 없다"
    assert "round(co[0][0] / TOL" not in body, "격자 반올림이 남아 있다"

    # 실제로 import 되는가 — 모듈을 불러 확인한다
    import firelane.segments as _S
    assert hasattr(_S, "_write_route")

    # graph.py 도 같은 상수를 쓰는지
    gp = (ROOT / "src/firelane/seg/graph.py").read_text(encoding="utf-8")
    assert "NODE_TOL" in gp, "graph.py 가 NODE_TOL 을 안 쓴다"


def test_ship_reports_the_real_failure():
    """`ship` 이 실패 사유로 안내 문구를 집지 않는가.

    ★ 2026-08-24. `verify.sh` 출력의 **마지막 줄**을 실패 사유로 썼다.
      그런데 `verify.sh` 는 실패 시 안내 문구를 마지막에 찍는다 —
      *"원본으로 되돌리려면: web/app.js.orig 가 분리 전 app.js 다."*

      그것이 실패 사유로 표시되어 **없는 파일(08-21 분리 때 삭제)을 찾게
      만들었다.** 진짜 원인은 그 위에 있었다.

      **오진을 유도하는 오류 메시지는 오류보다 나쁘다.**
      `실패` 로 표시된 줄을 골라 보여준다.
    """
    src = (ROOT / "tools/ship.py").read_text(encoding="utf-8")
    i = src.index("def check_code")
    body = src[i:i + 1500]
    assert '"실패" in x' in body, "실패 표시가 있는 줄을 안 고른다"
    assert "tail[0]" not in body, "마지막 줄을 실패 사유로 쓴다"
    assert '"머지" not in x' in body, "머지 안내 문구를 걸러내지 않는다"


# ── golden 게이트의 해제 경로 (2026-08-25) ─────────────────────
def test_golden_lock_writes_the_code_fingerprint():
    """`lock` 이 판정 코드 지문을 같이 남기는가.

    ★ DECISIONS §69. 종전에는 `.code_fingerprint` 를 **파일이 아예 없을 때만**
      썼다. 그래서 판정 코드가 정당하게 바뀐 뒤에는 파이프라인을 다시 돌려도
      `lock` 을 다시 해도 낡음 경보가 영구히 울었다. 남는 길이 손으로 지우기
      아니면 `--allow-stale` 뿐이었고, 둘 다 게이트를 죽이는 습관을 만든다.

      **잠그는 법만 있고 푸는 법이 없으면 사람은 우회로를 만든다.**

    ★ 이 검사는 데이터 없이 돈다. 구조만 본다.
    """
    src = (ROOT / "tools/golden.py").read_text(encoding="utf-8")
    i = src.index("def cmd_lock")
    body = src[i:src.index("def _staleness", i)]
    assert "CODE_FP.write_text" in body, (
        "cmd_lock 이 .code_fingerprint 를 갱신하지 않는다 — "
        "게이트가 한 번 울면 해제할 길이 없다")
    assert "_logic_fingerprint()" in body, "lock 이 로직 해시를 쓰지 않는다"


def test_golden_lock_releases_the_gate():
    """게이트가 실제로 울고, 또 풀리는가.

    구조 검사(위)는 `write_text` 가 있는지만 본다. 그것이 옳은 값을 쓰는지,
    어긋난 지문에서 실제로 우는지는 돌려봐야 안다.

    ★ 산출물이 없으면 건너뛴다. CI 에는 `data/raw` 가 없어 판정을 만들 수
      없다. **로컬이 CI 보다 더 보는 것은 정상이다**(verify.sh 머리말).
    """
    if not (ROOT / "data/processed/segments.geojson").exists():
        pytest.skip("산출물이 없다 — 파이프라인이 도는 기계에서만 검사한다")
    r = subprocess.run([sys.executable, str(ROOT / "tools/golden.py"), "selftest"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"golden 게이트 자기검사 실패\n{r.stdout}{r.stderr}"


# ── 매니페스트 churn (2026-08-25) ──────────────────────────────
def test_manifest_write_is_idempotent(tmp_path):
    """같은 내용을 두 번 쓰면 파일이 안 바뀌는가.

    ★ DECISIONS §70. `_manifest.json` 두 개가 매 실행 `generated_at` 만
      바뀌어 diff 가 났고, `verify.sh` 를 한 번 돌릴 때마다 워킹트리가
      더러워져 `git checkout` 이 막혔다. 커밋해야 하는 파일과 매 실행
      바뀌는 파일이 같은 파일이었다.
    """
    from firelane import manifest

    f = tmp_path / "_manifest.json"
    a = {"generated_at": "2026-08-25T09:00:00+09:00", "datasets": [{"key": "x"}],
         "terrain": {"tiles": 22, "generated_at": "2026-08-25T09:00:01+09:00"}}
    assert manifest.write_stable(f, a) is True, "처음에는 써야 한다"
    before = f.read_text(encoding="utf-8")

    b = dict(a, generated_at="2026-08-25T18:30:00+09:00")
    b["terrain"] = dict(a["terrain"], generated_at="2026-08-25T18:30:01+09:00")
    assert manifest.write_stable(f, b) is False, "시각만 달라졌는데 썼다"
    assert f.read_text(encoding="utf-8") == before, "파일이 바뀌었다"

    # ★ 2026-08-25. 파이썬 객체와 JSON 표현이 다른 자리. `ingest` 는
    #   `BBOX_4326` 을 **튜플**로 넘기는데 파일에는 리스트로 저장된다.
    #   객체끼리 비교하면 `(1, 2) != [1, 2]` 라 매번 "달라졌다" 가 되고,
    #   실측 diff 는 시각 한 줄뿐인데 churn 이 안 죽는다.
    t = dict(b, bbox=(1.0, 2.0))
    assert manifest.write_stable(f, t) is True, "새 키는 써야 한다"
    t2 = dict(t, generated_at="2026-08-26T00:00:00+09:00")
    assert manifest.write_stable(f, t2) is False, (
        "튜플을 다시 넘겼는데 또 썼다 — JSON 왕복 없이 비교하고 있다")

    c = dict(b, datasets=[{"key": "y"}])
    assert manifest.write_stable(f, c) is True, "내용이 달라졌는데 안 썼다"
    assert "18:30" in f.read_text(encoding="utf-8"), (
        "내용이 바뀌었으면 시각도 새것이어야 한다 — "
        "그래야 '언제 실제로 달라졌나' 가 남는다")


def test_manifest_writers_go_through_write_stable():
    """매니페스트를 쓰는 곳이 전부 같은 통로를 쓰는가.

    ★ 한 곳만 직접 쓰면 그 파일만 churn 이 남고, 그 자리가 다시
      `git checkout` 을 막는다. **정본이 둘이면 반드시 어긋난다.**
    """
    bad = []
    for rel in ("ingest.py", "terrain.py", "ortho.py", "webmanifest.py"):
        src = (ROOT / "src/firelane" / rel).read_text(encoding="utf-8")
        if "manifest.write_stable" not in src:
            bad.append(f"  {rel}: write_stable 을 안 쓴다")
        for ln in src.splitlines():
            code = ln.split("#", 1)[0]
            if "_manifest" in code and ".write_text(" in code:
                bad.append(f"  {rel}: 매니페스트를 직접 쓴다 — {ln.strip()[:60]}")
    assert not bad, ("매니페스트 쓰기가 통로를 벗어났다.\n" + "\n".join(bad))


def test_ingest_keeps_manifest_keys_it_does_not_own():
    """`ingest` 가 terrain · ortho 기록을 지우지 않는가.

    ★ 종전에는 대장을 통째로 덮어썼다. 전량 실행에서는 뒤 단계가 다시
      넣어주므로 안 보였지만 `--only ingest` 는 그 기록을 날린다.
    """
    src = (ROOT / "src/firelane/ingest.py").read_text(encoding="utf-8")
    assert "manifest.read(man)" in src, (
        "ingest 가 기존 매니페스트를 안 읽는다 — 자기 것이 아닌 키를 지운다")


# ── 여러 판으로 오는 소스 (2026-08-25) ─────────────────────────
def test_multi_part_sources_are_not_read_as_one():
    """글롭이 여러 개를 잡는 소스가 하나만 읽히고 있지 않은가.

    ★ DECISIONS §71. `enforcement` 는 대장이 두 판을 잡는데 `kind: csv_table`
      이 정렬 첫 번째 하나만 읽었다. 파일명에 날짜가 있으므로 그것은 옛 판이다.
      대장 note 와 `contract.py` 는 두 판을 전제하고 있었는데 파이프라인만
      한 판을 읽었다 — **검사는 두 판을 보고 산출은 한 판이었다.**

    ★ 파일 존재는 안 본다. raw 는 저장소에 없다. 대장 선언만 본다.
    """
    import yaml

    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    SINGLE = {"shp_zip", "csv_points", "csv_point", "csv_points_in_zip",
              "dbf_in_zip", "json_points", "csv_table"}
    bad = []
    for k, v in (y.get("datasets") or {}).items():
        f, kind = (v or {}).get("file", ""), (v or {}).get("kind", "")
        note = str((v or {}).get("note", "")) + str((v or {}).get("what", ""))
        if kind in SINGLE and any(ch in f for ch in "*?[") and "이어붙" in note:
            bad.append(f"  {k}: kind={kind} 인데 대장이 '이어붙인다' 고 적었다")
    assert not bad, (
        "대장 서술과 kind 가 어긋난다 — 한 판만 읽힌다.\n" + "\n".join(bad)
        + "\n  여러 판을 쓰려면 kind 를 csv_table_multi 로 바꿔라.")


def test_multi_part_reader_refuses_mixed_columns():
    """판마다 컬럼이 다르면 세우는가.

    ★ `pd.concat` 은 없는 컬럼을 조용히 NaN 으로 메운다. 그러면 판이 섞인
      채로 통과하고, 그 결과를 아무도 못 본다(R6 — 조용한 실패 금지).
    """
    src = (ROOT / "src/firelane/ingest.py").read_text(encoding="utf-8")
    i = src.find('kind == "csv_table_multi"')
    assert i > 0, "csv_table_multi 핸들러가 없다"
    body = src[i:i + 2200]
    assert '"status": "FAIL"' in body, "컬럼 불일치에 FAIL 하지 않는다"
    assert '"_src"' in body, "어느 판에서 온 행인지 산출물에 안 남긴다"
    # ★ 예외는 대장 선언으로만 열린다. 코드에 박은 화이트리스트는
    #   3개월 뒤에 근거를 알 수 없다(§18-3).
    assert "optional_cols" in body, "결손 허용이 대장 선언을 안 본다"
    assert "undeclared" in body, "선언되지 않은 컬럼 차이를 그냥 넘긴다"
