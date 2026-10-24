"""`width_fn.py --aggregators` 가 판정 입력을 **전부** 넘겨 산출물을 재현한다.  (감사 N4 · Zm20)

`cls` 가 규칙 [8]~[10] 의 입력(`width_min_any_m` · `width_min_sym_m` · `clear_med_m`)을 안 넘기고
[11] 은 `spread_max=None` 으로 껐다 — Zm19 이후 산출물 1,281 중 143 이 재현되지 않아 도구가
「재현이 깨졌다」로 아무 표도 못 냈다. 바꿔 보는 것은 폭 **집계 하나**여야 하고 나머지 입력은
산출물 그대로여야 한다(`verdictsim` 과 같은 규율).

IN    이 파일의 대상 모듈 · 실물
OUT   없음 (검사)
PARAM 없음
밖    **집계 함수가 옳은가**는 안 본다 — 판정 재현이 깨지지 않는지만 본다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from firelane.paths import PROCESSED


def _needs_data() -> None:
    if not (PROCESSED / "segments_5186.gpkg").exists() or not (PROCESSED / "width_samples.csv").exists():
        pytest.skip("환경skip(산출물) — segments_5186.gpkg · width_samples.csv 가 없다")


def test_aggregators_reproduces_the_published_verdicts(capsys: pytest.CaptureFixture[str]) -> None:
    _needs_data()
    import width_fn

    assert not width_fn.cmd_aggregators(), f"재현이 깨졌다 — 판정 입력을 전부 넘기지 않는다:\n{capsys.readouterr().out[:300]}"


def test_aggregators_refuses_when_the_replay_breaks(monkeypatch: pytest.MonkeyPatch) -> None:
    """**카나리아.** 판정을 재현 못 하는 `classify` 를 끼우면 도구는 표를 내지 않고 1 을 돌려준다."""
    _needs_data()
    import width_fn

    import firelane.seg.classify as C
    monkeypatch.setattr(C, "classify", lambda **kw: ("clear", None))
    assert width_fn.cmd_aggregators()


def test_cls_passes_every_rule_input() -> None:
    src = (ROOT / "tools/width_fn.py").read_text(encoding="utf-8")
    body = src[src.index("def cls(r, w):"):src.index("rows = widthcross._load()")]
    for kw in ("wmin_any=", "wsym=", "clear_med="):
        assert kw in body, f"cls 가 {kw} 를 안 넘긴다"
    assert "spread_max=None" not in body, "규칙 [11] 을 끄면 재현이 안 된다"
