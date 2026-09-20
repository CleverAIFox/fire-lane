#!/usr/bin/env python3
"""
tests/test_commit_policy.py — 커밋 정책이 실제로 작동하는가.

규칙을 만들어놓고 아무도 안 돌리면 장식이다. 여기서 강제한다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

import commit_policy as cp  # tools/ — pyproject 의 pytest pythonpath 로 잡힌다


@pytest.mark.parametrize("path,rule", [
    ("data/processed/ngii_road_5186.gpkg.stale_20260821", cp.r_stale),
    ("data/processed/building.geojson", cp.r_processed),
    ("data/processed/enforcement.csv", cp.r_processed),
    ("apply.sh", cp.r_root_script),
    ("fix-lineage.sh", cp.r_root_script),
    (".env", cp.r_env),
    (".work/12210/TL_SPRD_RW.shp", cp.r_work),
    ("_backup_20260812/data/raw/x", cp.r_work),
    ("data/processed/_lineage.json", cp.r_lineage),
])
def test_금지_대상을_잡는다(path, rule):
    assert rule(path), f"{path} 를 못 잡는다"


@pytest.mark.parametrize("path", [
    "data/processed/segments.geojson",
    "data/processed/segments.schema.json",
    "data/processed/_manifest.json",
    "data/processed/seg_uid_map.csv",
    "src/firelane/segments.py",
    "tools/commit_policy.py",
    "web/data/segments.geojson",
    ".env.example",
    ".githooks/pre-commit",
])
def test_정상_파일은_통과한다(path):
    hit = [name for name, fn, _ in cp.RULES if fn(path)]
    assert not hit, f"{path} 가 {hit} 에 잘못 걸린다"


def test_훅이_저장소에_있다():
    """커밋 방어가 **클론에 따라오는가.** `.git/hooks` 는 안 따라온다.

    ★ 2026-09-18 (W1b). W1 이 이 테스트를 바꾸고 `.githooks/pre-commit` 을 지웠다.
      근거는 "로컬 `core.hooksPath` 가 있어야 돌고 `dms` 가 그것을 실패로 치니
      구조적으로 못 도는 코드다" 였는데 **틀렸다.** 전역 훅이 후보 경로
      (`<repo>/.githooks/pre-commit`)를 뒤져 실행 가능한 것을 부른다 —
      `bash -x ~/.githooks/pre-commit` 추적으로 확인했다.
      **원래 이 테스트가 맞았다.** 되돌리고, 놓쳤던 것을 더한다.

    셋을 본다 —
      ① 훅 파일이 있고 실행 가능한가   전역 훅이 `[ -x ]` 로 후보를 고른다
      ② 규칙의 정본이 있는가           `.pre-commit-config.yaml`
      ③ 훅이 그 정본에 **위임하는가**   규칙을 훅에 직접 적으면 정본이 둘이 된다
    """
    h = ROOT / ".githooks" / "pre-commit"
    assert h.exists(), ".githooks/pre-commit 이 없다 — 전역 훅이 부를 것이 없다"
    assert h.stat().st_mode & 0o111, "실행 권한이 없다 — 전역 훅이 후보로 안 집는다"

    cfg = ROOT / ".pre-commit-config.yaml"
    assert cfg.exists(), ".pre-commit-config.yaml 이 없다 — 커밋 방어 규칙의 정본이 없다"

    body = h.read_text(encoding="utf-8")
    assert "pre-commit run" in body, (
        ".githooks/pre-commit 이 pre-commit 에 위임하지 않는다.\n"
        "  규칙을 훅에 직접 적으면 .pre-commit-config.yaml 과 정본이 둘이 된다(2족).")


def test_훅_도달이_방법이_사람의_말이_아니다():
    """훅 도달을 **실행으로** 재는 수단이 있는가.

    ★ 2026-09-18 (W1b). W1 의 `global-chain.sh --check` 는 전역 훅에 마커
      **문자열**이 있는지만 봤다. 그 스니펫은 전역 훅의 `exit 0` 뒤에 붙어
      한 번도 안 불렸는데 검사는 통과했고 verify 도 초록이었다.
      「있는가」가 아니라 「도는가」를 물어야 한다 — 이 저장소가 열두 군데에
      자백해놓은 그 병이고, 그것을 닫겠다는 배치가 그것을 새로 만들었다.
    """
    chain = ROOT / ".githooks" / "global-chain.sh"
    assert chain.exists(), ".githooks/global-chain.sh 가 없다 — 도달을 잴 수단이 없다"
    src = chain.read_text(encoding="utf-8")
    assert "FIRE_LANE_HOOK_PROBE" in src, (
        "global-chain.sh 가 탐침 변수를 안 쓴다 — 실행으로 재지 않는다는 뜻이다")
    hook = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "FIRE_LANE_HOOK_PROBE" in hook, (
        ".githooks/pre-commit 이 탐침에 응답하지 않는다 — 체인이 끊겨도 초록이 된다")


def test_CI_가_정책을_돌린다():
    """훅은 로컬 설정이라 다른 기계에는 적용되지 않는다. CI 가 받쳐야 한다."""
    ci = (ROOT / ".github/workflows/contract.yml").read_text(encoding="utf-8")
    assert "commit_policy" in ci, "contract.yml 이 커밋 정책을 안 돌린다"


def test_추적_중인_파일이_정책을_지킨다():
    # ★ 2026-08-23. 종전에는 저장소가 아닌 곳(배포 zip · 임시 체크아웃)에서도
    #   이 테스트가 **통과**했다. commit_policy 가 git 실패를 빈 목록으로 읽고
    #   0 을 반환했기 때문이다 — 테스트도 같이 조용히 통과한 것이다.
    #   정책은 이제 1 을 반환한다. 테스트는 못 보는 상황을 통과로 위장하지
    #   않고 명시적으로 건너뛴다.
    if not (ROOT / ".git").exists():
        pytest.skip("환경skip(도구) — git 저장소가 아니다. 추적 목록을 볼 수 없다")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "commit_policy.py"),
                        "--tracked"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"추적 파일이 정책을 위반한다\n{r.stdout}"


def test_global_chain_rejects_unknown_args():
    """`global-chain.sh` 가 **모르는 인자를 조용히 삼키지 않는가** (W3-19).

    ★ 2026-09-19 실측. `case` 의 `--check|*)` 가 catch-all 이라 `--install`
      이 오류 없이 `--check` 로 떨어졌다. 그 사이 `verify.sh` 는 「미설정이면
      한 명령으로 끝난다 — `global-chain.sh --install`」이라는 **없는 모드를
      안내**하고 있었고, 따라 친 사람은 초록을 보고 「됐다」고 읽었다.
      **틀린 안내가 영원히 사는 자리** — 조용한 통과(1족)다.
    ★ 인자 검증이 `hookdir()` 보다 **먼저**여야 이 시험이 성립한다. 뒤에
      두면 전역 훅이 없는 기계(CI)에서 「모르는 인자」와 「훅 미설정」이
      둘 다 exit 2 라 무엇을 잡았는지 구분이 안 된다.
    """
    import subprocess

    sh = ROOT / ".githooks" / "global-chain.sh"
    r = subprocess.run(["bash", str(sh), "--install"],
                       capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert r.returncode != 0, (
        "`global-chain.sh --install` 이 통과했다 — 없는 모드인데 조용히 삼킨다.\n"
        "  모르는 인자는 쓰는 법을 찍고 실패해야 한다(W3-19).")
    assert "모르는 인자" in (r.stderr + r.stdout), (
        "실패는 했는데 **왜** 실패했는지 안 말한다.\n"
        "  전역 훅 미설정과 모르는 인자가 같은 코드로 겹치면 구분이 안 된다.\n"
        f"  지금 출력: {(r.stderr + r.stdout)[:300]}")
