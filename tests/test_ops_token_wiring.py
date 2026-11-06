"""중계 토큰이 배포 사슬을 끝까지 건너는가 — `deploy.yml` → `stage-site` → `build-navi` → `VITE_OPS_TOKEN`.  (DECISIONS §655 · PLAN #176)

토큰이 사슬 어디서든 끊기면 **화면은 멀쩡하고 연결만 조용히 안 된다.** 빌드도 배포도 초록이다(§343-3 의 `ws://` 와 같은 꼴).
그래서 이 시험이 사슬의 각 이음매를 문자열이 아니라 **구조**로 읽는다(YAML 을 파싱한다).

IN    .github/workflows/deploy.yml · .github/actions/stage-site/action.yml · .github/actions/build-navi/action.yml · web/navi/vite.config.ts
OUT   없음 (검사)
PARAM 없음
밖    **GitHub Secrets 에 값이 있는가는 못 본다**(저장소 밖이다 — 사람이 친다). 배포본에서 실제로 이어지는지도 못 본다(눈으로 본다 — PLAN #176 ④).
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / ".github/workflows/deploy.yml"
STAGE = ROOT / ".github/actions/stage-site/action.yml"
BUILD = ROOT / ".github/actions/build-navi/action.yml"
VITE = ROOT / "web/navi/vite.config.ts"


def _y(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _uses(steps: list[dict], needle: str) -> list[dict]:
    return [s for s in steps if needle in str(s.get("uses", ""))]


def test_both_deploy_jobs_pass_the_secret_not_a_var() -> None:
    """배포와 시운전이 **둘 다** 넘긴다 — 한쪽만 넘기면 시운전이 거짓을 말한다. 출처는 `secrets` 다(`vars` 는 공개된다)."""
    jobs = _y(DEPLOY)["jobs"]
    seen = []
    for name, job in jobs.items():
        for s in _uses(job.get("steps", []), "stage-site"):
            seen.append((name, s["with"].get("ops-token")))
    assert len(seen) == 2, f"stage-site 를 부르는 곳이 둘이어야 한다: {seen}"
    for name, v in seen:
        assert v == "${{ secrets.FIRE_LANE_OPS_TOKEN }}", f"{name}: 토큰이 secrets 로 안 넘어간다 — {v!r}"


def test_stage_site_forwards_the_token_unchanged() -> None:
    a = _y(STAGE)
    assert "ops-token" in a["inputs"]
    (s,) = _uses(a["runs"]["steps"], "build-navi")
    assert s["with"]["ops-token"] == "${{ inputs.ops-token }}"


def test_build_navi_hands_it_to_vite_under_the_name_vite_reads() -> None:
    """`vite.config.ts` 가 읽는 이름과 액션이 내는 이름이 같아야 한다 — 이름이 어긋나면 **빈 문자열이 박힌다**."""
    a = _y(BUILD)
    assert "ops-token" in a["inputs"]
    step = next(s for s in a["runs"]["steps"] if "내비 빌드" in str(s.get("name", "")))
    assert step["env"]["VITE_OPS_TOKEN"] == "${{ inputs.ops-token }}"
    assert "VITE_OPS_TOKEN" in VITE.read_text(encoding="utf-8")


def test_the_build_warns_when_url_is_set_but_token_is_not_and_never_prints_the_value() -> None:
    run = next(s for s in _y(BUILD)["runs"]["steps"] if "내비 빌드" in str(s.get("name", "")))["run"]
    assert '[ -n "$VITE_OPS_URL" ] && [ -z "$VITE_OPS_TOKEN" ]' in run, "주소만 있고 토큰이 없는 꼴을 안 운다"
    assert "::warning" in run
    for line in run.splitlines():
        if "echo" in line:
            assert "$VITE_OPS_TOKEN" not in line, f"토큰 값을 찍는다: {line.strip()}"
