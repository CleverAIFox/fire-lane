#!/usr/bin/env python3
"""
test_ci_env.py — CI 환경과 로컬이 같은 것을 보는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-24. `contract.yml` 이 의존성을 **손으로 나열**하고 있었다.

    pip install pytest shapely numpy ruff pyyaml
    pip install -e . --no-deps

`pyproject.toml` 과 `uv.lock` 에 의존성이 있는데 CI 는 그것을 안 읽는다.
**정본이 둘이고, 새 모듈을 쓰는 검사가 들어올 때마다 사람이 맞춰야 했다.**
2026-08-23 에 pyyaml 을 뒤늦게 붙인 것이 그 증거다.

결과: 로컬 283 · CI 216. **67개가 CI 에서 한 번도 안 돌았다.**
그중 `test_route_graph_snaps_nodes_like_build_graph` 는 PR #40 이 2,468줄을
지운 것을 잡을 수 있었던 검사다. 그 PR 은 초록불로 머지됐다.

초록불이 무엇을 보증하는지 모르면 CI 는 없는 것만 못하다 —
있다고 믿게 만들기 때문이다.

IN    .github/workflows/*.yml · pyproject.toml
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WF = sorted((ROOT / ".github/workflows").glob("*.yml"))


def test_ci_installs_from_lock_not_a_handpicked_list():
    bad = []
    for p in WF:
        t = p.read_text(encoding="utf-8")
        body = "\n".join(l for l in t.splitlines()
                         if not l.lstrip().startswith("#"))
        for m in re.finditer(r"pip install\s+(?!-e\s+\.)([^\n]+)", body):
            bad.append(f"  {p.name}: pip install {m.group(1)[:50]}")
    assert not bad, (
        "CI 가 의존성을 손으로 나열한다. uv.lock 이 정본이다.\n"
        + "\n".join(bad)
        + "\n  목록이 둘이면 반드시 어긋난다 — 로컬 283 vs CI 216 (2026-08-24).")


def test_ci_uses_uv_sync():
    hits = [p.name for p in WF
            if "uv sync" in p.read_text(encoding="utf-8")]
    assert hits, "어느 워크플로도 uv sync 를 쓰지 않는다"


def test_ci_runs_everything_through_uv():
    """시스템 python 으로 부르면 uv 가 만든 환경을 안 본다."""
    bad = []
    for p in WF:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            # ★ 2026-08-24 확대. 종전에는 `run:` 바로 뒤만 봤다. 그래서
            #   `run: |` 블록 안의 `if [ -f x ]; then python ...` 를 놓쳤고,
            #   CI 가 `web/data 계보 검사` 에서 ModuleNotFoundError 로 죽었다.
            #   **검사가 사고와 같은 사각을 갖고 있었다.**
            if "uv run" in code or "uv sync" in code:
                continue
            m = re.search(r"(?<![-\w/.])(python3?|pytest|ruff|pip)(?=\s)", code)
            if m:
                bad.append(f"  {p.name}:{i}  {line.strip()[:60]}")
    assert not bad, (
        "CI 가 시스템 인터프리터를 부른다. `uv run` 을 붙여라.\n"
        + "\n".join(bad))


def test_navi_node_version_has_one_source_of_truth():
    """게이트와 빌드가 같은 노드에서 도는가 (DECISIONS §186-2).

    ★ 2026-09-18. `contract` 의 내비 타입 검사는 22, 배포 액션 `build-navi` 는 20 이었다.
      그 게이트는 maplibre 5→6 · vite 5→6 이 PR 초록 · 0 vulnerabilities 로 통과해 main 에서
      `TS1192` 로 죽은 사고 때문에 생긴 것이다(contract.yml). **런타임이 다르면 같은 형태가 또 난다** —
      게이트가 통과시킨 판과 배포가 빌드하는 판이 애초에 다르기 때문이다.
      정본은 `web/navi/.nvmrc` 하나. 노드 판을 손으로 두 군데 적지 않는다.
    """
    nvmrc = ROOT / "web/navi/.nvmrc"
    assert nvmrc.exists(), "web/navi/.nvmrc 가 없다 — 내비 노드 판의 정본이 사라졌다"
    assert nvmrc.read_text(encoding="utf-8").strip().isdigit(), "web/navi/.nvmrc 는 메이저 판 하나만 적는다"

    bad = []
    for p in [*WF, ROOT / ".github/actions/build-navi/action.yml"]:
        t = p.read_text(encoding="utf-8")
        body = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
        # 노드를 **직접 세우는** 파일만 본다. `build-navi` 에 위임하는 배포 셋은
        # 자기 자리에 판을 안 적으므로 정본이 갈릴 여지가 없다.
        if "actions/setup-node" not in body or "web/navi" not in body:
            continue
        if "node-version-file: web/navi/.nvmrc" not in body:
            bad.append(f"  {p.name}: web/navi 에서 노드를 세우는데 .nvmrc 를 안 읽는다")
        # 같은 파일 안에서 내비 구간이 판을 손으로 적으면 정본이 둘이 된다
        for m in re.finditer(r"node-version:\s*[\"']?(\d+)", body):
            seg = body[max(0, m.start() - 400):m.start() + 400]
            if "web/navi" in seg:
                bad.append(f"  {p.name}: 내비 근처에 node-version: {m.group(1)} 을 손으로 적었다")
    # ★ 2026-09-19 (W3-18). **범위를 devcontainer 까지 넓힌다.**
    #   종전 이 검사는 워크플로와 `build-navi` 만 봤다. 그래서
    #   `devcontainer.json` 이 node feature 판을 `"20"` 으로 **손으로 적는
    #   것**이 범위 밖이었고, 그 축의 강제자는 0건이었다 — 이름은
    #   「노드 판의 정본이 하나인가」인데 실제 범위가 그보다 좁았다
    #   (W3-8 · W4-8 · W3-16 · W4-9 와 같은 족).
    # ★ devcontainer feature 는 파일을 못 읽는다(`.nvmrc` 를 가리킬 수단이
    #   없다). **합칠 수 없으면 같은지를 강제한다** — 합칠 수 없는 사본을
    #   방치하는 것과 검사하는 것은 다르다.
    want = nvmrc.read_text(encoding="utf-8").strip()
    dc = ROOT / ".devcontainer/devcontainer.json"
    if dc.exists():
        import json

        feats = json.loads(dc.read_text(encoding="utf-8")).get("features") or {}
        for key, cfg in feats.items():
            if "/node" not in key or not isinstance(cfg, dict):
                continue
            got = str(cfg.get("version", "")).strip()
            if got and got != want:
                bad.append(
                    f"  devcontainer.json: node feature 가 {got!r} 인데 "
                    f"web/navi/.nvmrc 는 {want!r} 다")

    assert not bad, (
        "내비 노드 판의 정본이 둘 이상이다.\n" + "\n".join(bad)
        + "\n  게이트와 빌드가 다른 판에서 돌면 초록불이 배포를 보증하지 않는다.")


def test_python_version_has_one_source_of_truth() -> None:
    """게이트 · 배포 · 이미지가 같은 파이썬에서 도는가 (W3-17).

    ★ 2026-09-19. `Dockerfile` 이 W8-2 로 `3.14-slim` 이 됐는데 워크플로 셋은
      `"3.11"` 을 손으로 적은 채였다. `pyproject` 의 `requires-python >=3.11`
      이 둘 다 허용하므로 **아무것도 안 울었다.**
      개발자가 쓰는 런타임(devcontainer = Dockerfile)과 게이트가 도는 런타임이
      달랐다 — 내비 노드 22 vs 20 과 **같은 형태**다(§186-2). 그때의 교훈이
      「게이트가 통과시킨 판과 배포가 빌드하는 판이 애초에 다르면 같은 사고가
      또 난다」였고, 파이썬 축에서 그대로 반복됐다.
    ★ 정본은 `.python-version` 하나다. `uv` 와 `actions/setup-python` 이 **둘 다**
      이 파일을 읽으므로 합칠 수 있었다 — 합칠 수 있으면 합친다.
      `Dockerfile` 만 파일을 못 읽으므로 거기는 **같은지를 강제한다.**
    ★ `pyproject` 의 `requires-python` 은 **안 좁혔다.** 좁히면 `uv.lock` 이
      재해결을 요구해 `--frozen` 이 전부 깨진다. 그것은 잠금 갱신을 포함하는
      별도 배치다 — 이 배치의 수용 조건(판정 불변)과 섞지 않는다(§13-5 규칙 2).
    """
    pv = ROOT / ".python-version"
    assert pv.exists(), (
        ".python-version 이 없다 — 파이썬 판의 정본이 사라졌다.\n"
        "  없으면 워크플로마다 판을 손으로 적게 되고, 그것이 W3-17 이다.")
    want = pv.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", want), (
        f".python-version 이 {want!r} 다 — `3.14` 형태로 적는다")

    bad = []
    for p in WF:
        body = "\n".join(l for l in p.read_text(encoding="utf-8").splitlines()
                         if not l.lstrip().startswith("#"))
        for m in re.finditer(r"python-version:\s*[\"']?([\d.]+)", body):
            bad.append(f"  {p.name}: `python-version: {m.group(1)}` 을 손으로 적었다")

    # ★ Dockerfile 은 빌드 시점에 파일을 못 읽는다. 합칠 수 없으면 같은지를 본다.
    dockerfile = ROOT / "Dockerfile"
    if dockerfile.exists():
        m = re.search(r"^FROM\s+python:([\d.]+)", dockerfile.read_text(encoding="utf-8"), re.M)
        if m and not (m.group(1) == want or m.group(1).startswith(want + ".")):
            bad.append(f"  Dockerfile: `FROM python:{m.group(1)}` 인데 "
                       f".python-version 은 {want} 다")

    assert not bad, (
        "파이썬 판의 정본이 둘 이상이다.\n" + "\n".join(bad)
        + f"\n  정본은 `.python-version`({want}) 하나다.\n"
        + "  워크플로는 `python-version-file: .python-version` 으로 읽는다.\n"
        + "  배포되는 런타임과 게이트가 도는 런타임이 다르면\n"
        + "  초록불이 아무것도 보증하지 않는다(W3-17 · §186-2 와 같은 형태).")


def test_devcontainer_sync_matches_verify() -> None:
    """devcontainer 가 세우는 환경이 `verify.sh` 가 검증하는 환경과 같은가.

    ★ 2026-09-19 (W3-18). `setup.sh` 가 맨몸 `uv sync` 를 돌고 있었다 —
      **환경을 세우는 도구가 `uv.lock` 을 갱신할 수 있는 자리**다.
      W2 가 `verify.sh` 의 「의존성 동기화」 단계에 `--frozen` 을 더한 이유가
      (「검증 도구가 검증 대상을 변형하는 유일한 자리」) 여기 그대로 남아
      있었다. Dockerfile · 워크플로는 전부 `--frozen` 인데 여기만 아니었다.
    ★ `--all-extras` 의 차이는 **선언된 차이**라 안 본다 — CI 만 붙이고
      로컬은 torch 를 안 받는다. 여기서 보는 것은 `--frozen` 하나다.
    """
    setup = ROOT / ".devcontainer/setup.sh"
    verify = ROOT / "tools/verify.sh"
    # ★ 2026-09-22 (PLAN §13 W10-1 · deadcheck ③). 종전 `if not setup.exists(): return` — 추적 파일이다.
    #   지워지면 이 검사가 **초록으로** 사라졌다. 없으면 운다.
    assert setup.exists(), ".devcontainer/setup.sh 가 없다 — 추적 파일이다"

    def _syncs(path: Path) -> list[str]:
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            code = line.split("#", 1)[0]
            if "uv sync" in code:
                out.append(code.strip())
        return out

    assert any("--frozen" in s for s in _syncs(verify)), (
        "verify.sh 가 `uv sync --frozen` 을 안 쓴다 — 이 검사의 전제가 사라졌다")

    bad = [s for s in _syncs(setup) if "--frozen" not in s]
    assert not bad, (
        "devcontainer 가 잠금을 갱신할 수 있는 `uv sync` 를 돈다.\n"
        + "".join(f"  .devcontainer/setup.sh: {s}\n" for s in bad)
        + "  환경을 세우는 도구가 정본(`uv.lock`)을 변형하면\n"
        + "  「내 컨테이너에서는 됐는데」가 난다. `--frozen` 을 붙여라.")


def test_devcontainer_actually_runs_its_setup_script():
    """`.devcontainer/setup.sh` 를 아무도 안 불렀다 (DECISIONS §186-1).

    ★ 2026-09-18. `postCreateCommand` 가 `uv sync` 한 줄이라 setup.sh 는 **한 번도 안 돌았다.**
      그 안의 `core.quotepath` · `core.precomposeunicode` 가 안 걸려 한글 파일명이 팔진수로 나온다.
      "기계 차이로 하루에 세 번 걸렸다" 는 이유로 만든 파일이 정작 배선이 빠져 있었다 —
      이 저장소가 반복해 겪은 **있는데 아무도 안 부르는** 그 형태다.
    """
    import json

    dc = ROOT / ".devcontainer/devcontainer.json"
    setup = ROOT / ".devcontainer/setup.sh"
    assert setup.exists(), ".devcontainer/setup.sh 가 없다"
    cmd = json.loads(dc.read_text(encoding="utf-8")).get("postCreateCommand", "")
    cmd = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    assert "setup.sh" in cmd, (
        f"postCreateCommand 가 setup.sh 를 안 부른다 — 지금: {cmd!r}\n"
        "  setup.sh 는 있는데 아무도 안 부르면 그 안의 방어가 전부 없는 것과 같다")
    assert "uv sync" not in cmd, "setup.sh 가 이미 uv sync 를 한다 — postCreateCommand 에서 또 하지 않는다"


def test_devcontainer_env_notice_is_conditional():
    """PLAN W3-18 ③ (DECISIONS §217-5). 환경변수 안내가 **비었을 때만** 나온다.

    ★ 종전에는 조건 없이 늘 찍혀 신호가 아니었다. 값은 기계마다 달라 박을 수 없으니
      단일 독자(`paths.env`)로 묻고 빈 것만 말한다.
    """
    s = (ROOT / ".devcontainer/setup.sh").read_text(encoding="utf-8")
    assert "paths.env(k)" in s and 'if [ -n "$MISSING" ]' in s, "환경변수 안내가 조건 없이 찍힌다"
    assert "FIRE_LANE_INBOX" in s, "머리말이 드는 INBOX 를 안 본다"


# ── 「가드가 제 시험보다 좁다」 ─────────────────────────────────
# ★ 2026-09-27 (§263). 일반 판별식을 **네 번 시도해서 네 번 실패했다.**
#     ① `# ci-exempt` 가 이름 댄 파일명을 시험에서 찾기
#        → 오탐(`tmp_path / "route_vehicle.csv"`). 게다가 원래 결함은 파일명이
#          시험에 안 나온다(게이트가 안에서 읽는다) — 애초에 못 잡는 형태였다
#     ② 모듈의 `data/` 경로가 전부 커밋돼 있으면 결함
#        → `ROOT / "tools"` 를 `data/tools` 로 붙여 **전 모듈 통과**. 빈 그물
#     ③ ②의 접두를 고침 → `test_lake.py` 오탐. 가드는 `lake_attached()` 인데
#        모듈 **딴 데** 있는 경로를 가드로 읽었다
#     ④ 가드 식만 AST 로 떼어내기 → 가드가 함수·헬퍼·`lru_cache` 로 흩어져 있어
#        「가드 식」이라는 것이 모듈마다 다른 모양이다
#   거짓 빨강은 침묵보다 나쁘다 — 사람이 검사를 끈다(§69). **일반화를 포기하고
#   좁고 참인 것만 남긴다.** 이 족의 일반 강제자는 CI 자신이다(그리고 CI 가
#   실제로 이번에 잡았다). 여기 남는 것은 그 한 모듈에 대한 충분성 검사다.


def test_the_evalgen_guard_is_not_narrower_than_its_tests():
    """★ 위 시험은 「가드가 있는가」만 본다. 이건 **그 가드가 충분한가**를 본다.

    2026-09-27 의 결함이 정확히 「가드는 있는데 좁았다」였다 — 있는 것만 보고
    통과시키면 다음 사람이 「가드가 있으니 봤겠지」로 읽는다.
    """
    # ★ 경로를 건드리지 않고 모듈로 읽는다 — `test_layering` 이 `sys.path` 조작을 막는다.
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("te_guard", ROOT / "tests" / "test_evalgen.py")
    assert spec and spec.loader
    te = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = te      # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(te)

    if not te.HAVE_REAL:
        # ★ 조용히 통과하지 않는다(`deadcheck ③`). 트리가 없으면 **잴 것이 없는
        #   것**이지 깨끗한 것이 아니다 — 생략으로 세어 그 사실이 보이게 한다.
        pytest.skip("환경skip(산출물) — 실제 트리가 없다. 이 검사는 CI 에서 문다")
    need = [te.REAL / "processed" / "route_vehicle.csv",
            te.REAL / "processed" / "segments.geojson",
            te.REAL / "golden" / "segments.fingerprint.json"]
    missing = [str(p.relative_to(ROOT)) for p in need if not p.is_file()]
    assert not missing, (
        f"가드가 「실제 트리 있음」이라 했는데 {missing} 가 없다 — 가드가 좁다(§263)")
    import evalgate as gt

    n = (gt.gate_manifest(te.REAL / "processed")[0] or {}).get("outputs_missing")
    assert not n, (
        f"가드가 「실제 트리 있음」이라 했는데 매니페스트 산출물 {n}개가 없다 — "
        "CI 에서 이 상태로 시험 넷이 돌다 죽었다(§263)")


def test_the_navi_lock_stamp_is_not_inside_what_npm_ci_deletes():
    """★ 2026-09-27 (DECISIONS §269). 잠금 지문이 `node_modules/` **안**에 살았다.

    그런데 `npm ci` 는 그 디렉터리를 통째로 지우고 다시 깐다 — **지문을 지우는
    명령이 지문을 들고 있었다.** 누가 `npm install` 을 치거나 devcontainer 를 다시
    만들거나 트리를 옮기면 지문이 사라지고, 다음 verify 가 예고 없이 네트워크로
    `npm ci` 를 돈다. 실패하면 `node_modules` 가 반쯤 지워진 채 남아 뒤의
    `내비 타입 검사` · `내비 단위 시험` 이 연쇄로 죽는다.

    밖  지문 계산이 옳은지는 안 본다 — `navi_env` 소관이다. 여기서 보는 것은
        **지문이 사는 자리** 하나다.
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("navienv_t", ROOT / "tools" / "navi_env.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m       # @dataclass 가 되짚는다 (DECISIONS §258-10)
    spec.loader.exec_module(m)

    rel = m.STAMP.relative_to(ROOT).as_posix()
    assert "node_modules" not in rel, (
        f"잠금 지문이 `{rel}` 에 있다 — `npm ci` 가 그 디렉터리를 지운다.\n"
        "  지워지면 다음 verify 가 예고 없이 네트워크로 `npm ci` 를 돈다(§269).")

    ign = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert rel in ign, (
        f"`{rel}` 이 gitignore 밖이다 — 기계마다 다른 값이 커밋된다")


# ── 쉘 환경이 시험에 새지 않는가 (PLAN #151 · DECISIONS §431) ──
def test_every_known_env_name_is_either_cleared_or_kept_with_a_reason():
    """**양방향이다.** 새 환경변수가 생기면 둘 중 하나에 들어가야 한다.

    ★ `conftest` 가 비우는 목록은 `env_check.SWITCHES | RETIRED` 에서
      **유도한다.** 그래서 이 시험이 묻는 것은 「`env_check` 가 아는 이름이
      전부 분류되는가」다 — 손목록을 두 벌 만들면 그것이 족 2 다.
    """
    import env_check as ec

    known = set(ec.SETTINGS) | set(ec.SWITCHES) | set(ec.RETIRED)
    assert len(known) > 8, f"아는 이름이 {len(known)}개뿐 — 정본이 죽었다"
    cleared = set(ec.SWITCHES) | set(ec.RETIRED)
    kept = set(ec.SETTINGS)
    assert not (cleared & kept), f"같은 이름을 비우고 또 지킨다: {sorted(cleared & kept)}"
    assert known == cleared | kept, (
        f"분류 밖 이름: {sorted(known - cleared - kept)}\n"
        "  스위치면 `SWITCHES`, 설정이면 `SETTINGS` 에 적어라. 분류 밖은 "
        "비우지도 지키지도 않는다 — 그러면 쉘이 조용히 이긴다.")


def test_the_fixture_actually_clears_a_switch(monkeypatch):
    """★ 카나리아. 픽스처가 **실제로** 비우는가 — autouse 는 조용히 죽는다."""
    import os

    import env_check as ec

    sw = sorted(ec.SWITCHES)[0]
    assert sw not in os.environ, (
        f"{sw} 가 아직 환경에 있다 — `_shell_switches_do_not_leak` 이 안 돌았다")
