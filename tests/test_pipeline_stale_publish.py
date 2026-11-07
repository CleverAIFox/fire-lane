"""일부 단계만 돌려 `publish` 가 **낡은 입력을 읽게 되면 아무것도 쓰기 전에 거절한다.**  (Zm48 · DECISIONS §587)

IN    src/firelane/pipeline.py (`stale_publish_blockers` · `main`)
OUT   없음 (검사)
밖    **어느 단계가 어느 산출물을 만드는가는 안 본다** — 단계 선언(`Step.produces` · `consumes`)의 정확성은 `tests/test_declaration_reality.py` 가 든다.

★ 왜 생겼나 — `--only segments publish` 는 `terrain`(고도 `z` 를 산출물에 덧쓴다)을 건너뛰고도 **경고만 하고 진행했고**, `publish` 가 `z` 없는 `web/data` 를 **먼저 썼다.**
  계약 위반은 그 뒤 끝에서야 울었다. 2026-08-18 에 `--only publish` 가 `z` 를 소실시킨 것과 같은 사고이고(그때도 가드는 경고였다) 2026-10-26 에 같은 길로 또 났다.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from firelane import pipeline

ALL = {s.name for s in pipeline.STEPS}


def test_publish_after_segments_without_terrain_is_blocked_and_names_the_step() -> None:
    assert "terrain" in pipeline.stale_publish_blockers({"ingest", "segments", "nfa_compare", "scope", "publish"})


def test_a_full_run_or_one_that_includes_terrain_is_not_blocked() -> None:
    assert pipeline.stale_publish_blockers(ALL) == []
    assert pipeline.stale_publish_blockers({"ingest", "segments", "nfa_compare", "scope", "terrain", "ortho", "publish"}) == []


def test_publish_alone_is_blocked_too_because_it_rewrites_the_view_that_terrain_reads() -> None:
    """`publish` 는 `view.json` 을 다시 쓰고 `terrain` 이 그것을 읽는다 — 2026-08-18 에 `--only publish` 가 `z` 를 소실시킨 바로 그 길이다."""
    assert "terrain" in pipeline.stale_publish_blockers({"publish"})


def test_a_run_without_publish_is_not_blocked() -> None:
    assert pipeline.stale_publish_blockers({"ingest", "segments"}) == []


def test_main_refuses_before_running_anything(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path) -> None:
    """실제 `main` 이 단계를 하나도 돌기 전에 끝낸다 — 자식 프로세스를 부르면 시험이 운다.

    ★ 레이크 유무와 무관하다. `main` 은 raw 검사(`RAW` 에 zip 이 없으면 `ingest` 가 든 실행을 `exit 1`)가 stale 가드보다 **앞**이라, 레이크가 없는 CI 에서는
      가드에 닿기 전에 raw 검사가 먼저 끝나 메시지가 달랐다(Zm53 의 깨끗한 체크아웃 재현). 그 길로 통과하면 이 시험은 **가드를 시험하지 않는다** — 그래서 임시 raw 폴더에
      빈 zip 을 두어 raw 검사만 통과시키고 가드가 거절하는 것을 본다. 환경이 없다고 건너뛰지 않는다 — 그러면 CI 에서 가드가 안 시험된다.
    """
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "x.zip").write_bytes(b"")
    monkeypatch.setattr(pipeline, "RAW", raw)

    def boom(*a, **k):
        raise AssertionError("거절해야 하는데 단계를 돌았다")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(sys, "argv", ["fire-lane", "--only", "ingest", "segments", "nfa_compare", "scope", "publish", "--no-test"])
    with pytest.raises(SystemExit) as e:
        pipeline.main()
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "terrain" in out and "--from terrain" in out, out
