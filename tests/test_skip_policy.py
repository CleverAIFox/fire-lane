"""skip 정책 카나리아 — 판별식과 훅이 **실제로** 분류 밖 skip 을 실패로 바꾸는가.

★ 2026-09-17 (DECISIONS §175). 정책이 문서에만 있으면 51 이 다시 쌓인다.
  판별식은 합성 사유로, 훅은 합성 테스트 파일을 별도 pytest 프로세스로 돌려 흔든다.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import skip_policy as sp

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 17)
TITLES = {"대장 · SSD 디렉토리 구조와 해석기 하나"}


def _j(reason: str, lake: bool = False) -> str | None:
    return sp.judge(reason, lake_attached=lake, today=TODAY, plan_titles=TITLES)


def test_judge_classifies_reasons():
    assert _j("환경skip(도구) — node 없음") is None
    assert _j("환경skip(산출물) — 파이프라인 미실행") is None
    assert _j("환경skip(레이크) — 레이크 미마운트") is None
    assert _j("could not import 'pydantic': No module named 'pydantic'") is None
    assert _j("유예skip — 「대장 · SSD 디렉토리 구조와 해석기 하나」 · 2026-09-10 — L2 대기") is None


def test_judge_rejects_what_hides():
    assert _j("환경skip(레이크) — 레이크 미마운트", lake=True), "레이크 기계의 레이크 skip 은 실패다"
    assert _j("랜덤 미사용"), "해당없음은 skip 이 아니다"
    assert _j("got empty parameter set ['x'], function f at t.py:1"), "빈 parametrize 도 해당없음이다"
    assert _j("환경skip — 태그 없음"), "환경skip 은 무엇이 없는지 태그를 단다"
    assert _j("유예skip — 「없는 행」 · 2026-09-10 — x"), "닫힌 PLAN 행을 붙든 유예"
    assert _j("유예skip — 「대장 · SSD 디렉토리 구조와 해석기 하나」 · 2026-08-01 — x"), "21일 넘은 유예"
    assert _j("유예skip — 「대장 · SSD 디렉토리 구조와 해석기 하나」 · 2026-10-01 — x"), "미래 날짜"


def test_plan_titles_are_read():
    """PLAN §1 행 제목을 못 읽으면 모든 유예가 거부된다 — 파서가 살아 있는가."""
    titles = sp.plan_titles()
    assert len(titles) > 20, f"PLAN §1 행 제목 {len(titles)}개 — 표 파서가 죽었다"


def test_hook_turns_unclassified_skip_into_failure(tmp_path):
    """훅 카나리아 — 합성 테스트 셋(분류 밖 · 환경 · 해당없음 빈 parametrize)을 별도 프로세스로 돌린다."""
    t = tmp_path / "test_synth.py"
    t.write_text(
        "import pytest\n"
        "def test_bad():\n    pytest.skip('랜덤 미사용')\n"
        "def test_ok():\n    pytest.skip('환경skip(도구) — 합성')\n"
        "@pytest.mark.parametrize('x', [])\ndef test_empty(x):\n    pass\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "tests"), str(ROOT / "src"),
                                                         os.environ.get("PYTHONPATH", "")]),
           "FIRE_LANE_DATA": ""}
    r = subprocess.run([sys.executable, "-m", "pytest", "-p", "conftest", "-p", "no:cacheprovider",
                        "-q", "-rA", str(t)], cwd=tmp_path, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr
    # 호출 단계 skip 은 failed, 준비 단계 skip(빈 parametrize)은 error 로 나온다 — 둘 다 초록이 아니다
    assert "1 failed, 1 skipped, 1 error" in out, f"훅이 안 걸렸다 — conftest 가 죽었다\n{out[-1500:]}"
    assert "skip 정책 위반" in out
