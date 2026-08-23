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
    for g, why in (("apply.sh", "08-23 — 옛 패처가 새 스크립트를 가렸다"),
                   ("data/processed/*.stale_*", "08-18 — 격리본이 진단을 흐렸다"),
                   (".work", "08-13 — raw 옆에 풀린 _unz_* 1,570파일")):
        assert g in globs, f"tidy 규칙에 {g} 가 없다 ({why})"


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
