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
    """`.git/hooks` 는 클론에 안 따라온다. `.githooks/` 여야 한다."""
    h = ROOT / ".githooks" / "pre-commit"
    assert h.exists(), ".githooks/pre-commit 이 없다"
    assert h.stat().st_mode & 0o111, "실행 권한이 없다"


def test_CI_가_정책을_돌린다():
    """훅은 로컬 설정이라 다른 기계에는 적용되지 않는다. CI 가 받쳐야 한다."""
    ci = (ROOT / ".github/workflows/contract.yml").read_text(encoding="utf-8")
    assert "commit_policy" in ci, "contract.yml 이 커밋 정책을 안 돌린다"


def test_추적_중인_파일이_정책을_지킨다():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "commit_policy.py"),
                        "--tracked"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"추적 파일이 정책을 위반한다\n{r.stdout}"
