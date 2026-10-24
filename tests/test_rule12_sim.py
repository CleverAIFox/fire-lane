"""규칙 [12](대장 괴리)는 짜 두되 **발행하지 않는다**.  (Zm23)

IN    tools/rule12_sim.py · src/firelane/seg/classify.py · segments.py · 발행본
OUT   없음 (검사)
PARAM 없음
밖    **규칙이 옳은가**는 안 본다 — 0판 평가셋 채점(Q4) 전에는 발행하지 않는다는 것과 경계가 정의대로라는 것만 본다.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import rule12_sim as R

ROOT = Path(__file__).resolve().parents[1]
STEPS = [1.0, 2.0, 3.0, 6.0, 9.0, 15.0]


def test_boundary_is_three_steps() -> None:
    assert R.applies("clear", 15.0, 2.5, STEPS)            # d = 5 − 2 = 3
    assert not R.applies("clear", 9.0, 2.5, STEPS)         # d = 4 − 2 = 2


def test_only_clear_is_touched() -> None:
    assert not R.applies("blocked", 15.0, 1.0, STEPS)
    assert not R.applies("needs_cv", 15.0, 1.0, STEPS)


def test_exclusions() -> None:
    assert not R.applies("clear", 4.5, 1.0, STEPS)         # 소수 대장값
    assert not R.applies("clear", 15.0, None, STEPS)       # 중앙값 없음
    assert not R.applies("clear", None, 1.0, STEPS)


def test_ledger_blocked_rows_never_reach_rule12() -> None:
    """`ROAD_BT < 3.0` → blocked 에서 끝난 구간은 `clear` 가 아니라 [12] 까지 오지 않는다 — classify 를 실제로 돌려 확인."""
    from firelane.seg.classify import classify

    v, _ = classify(wmin=2.0, wmax=None, nreg=20, road_bt=2.0, length_m=50.0, cctv_dist=5.0)
    assert v == "blocked"
    assert not R.applies(v, 2.0, 30.0, STEPS)              # 설령 계단 차가 커도 clear 가 아니라 건드리지 않는다


def test_threshold_is_a_constant_of_structure_not_a_parameter() -> None:
    assert R.GAP_RULE12 == 3
    sig = inspect.signature(R.applies)
    assert not any("gap" in p or "thresh" in p for p in sig.parameters), "문턱을 인자로 받으면 분포로 조정할 길이 열린다"


def test_it_is_not_published_or_read_by_the_judgment() -> None:
    for rel in ("src/firelane/seg/classify.py", "src/firelane/seg/geom.py", "src/firelane/segments.py",
                "src/firelane/publish_web.py", "src/firelane/seg/report.py"):
        txt = (ROOT / rel).read_text(encoding="utf-8")
        assert "ledger_gap" not in txt and "rule12" not in txt, f"{rel} 가 규칙 [12] 를 읽는다 — 채점 전 발행 금지"
    seg = ROOT / "web/data/segments.geojson"
    if seg.exists():
        reasons = {f["properties"].get("cv_reason") for f in json.loads(seg.read_text(encoding="utf-8"))["features"]}
        assert "ledger_gap" not in reasons


def test_simulation_does_not_change_the_published_counts() -> None:
    seg = ROOT / "web/data/segments.geojson"
    if not seg.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    rows = [f["properties"] for f in json.loads(seg.read_text(encoding="utf-8"))["features"]]
    out = R.report(rows)
    assert out["before"] == {"blocked": 192, "clear": 290, "needs_cv": 278, "unknown": 521}
    assert out["blocked_untouched"] and out["moved"] >= 0
    assert sum(out["after"].values()) == len(rows)
