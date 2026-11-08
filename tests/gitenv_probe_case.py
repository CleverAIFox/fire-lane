"""test_git_env_scrub 가 **중첩 pytest 로** 돌리는 탐침. 직접 모이지 않는다(`test_*.py` 가 아니다).

`GIT_DIR` 을 물려받은 채 `tmp_path` 안에서 `git init` · `config core.hooksPath` 를 부른다 — 그 둘이 물려받은 gitdir 에 쓰이는지가 사고 #200 의 모양이다.
"""
from __future__ import annotations

import os
import subprocess


def test_git_init_in_tmp_path_stays_in_tmp_path(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=work, check=True, timeout=60)
    subprocess.run(["git", "config", "core.hooksPath", str(tmp_path)], cwd=work, check=True, timeout=60)
    assert (work / ".git").is_dir(), f"git init 이 {work} 가 아니라 다른 곳(GIT_DIR={os.environ.get('GIT_DIR')})에 썼다"
