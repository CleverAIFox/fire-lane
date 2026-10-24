"""규칙 [9] 가 `needs_cv` 로 보낼 때 이유를 단다.  (감사 N6 · Zm20 · B — 사람이 잠그기 전)

[8] · [10] · [11] 은 `cv_reason = source_conflict` 를 다는데 [9](대칭폭 < 3.0)만 `None` 이었다 — `needs_cv` 인데
이유가 비어 화면이 「왜 확인이 필요한가」를 못 말했다. 이유 낱말은 `sym_low` 다(`survey_queue` 의 태그와 같은 말).
**발행 칸이 바뀌어 골든 L2 가 움직인다** — 재잠금은 사람이 한다.

IN    이 파일의 대상 모듈 · 실물
OUT   없음 (검사)
PARAM 없음
밖    **[9] 의 문턱(3.0)이 옳은가**는 안 본다 — 이유 낱말이 붙는지만 본다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from firelane.seg.classify import classify
from firelane.seg.geom import VERDICT_RULE

ROOT = Path(__file__).resolve().parents[1]
ARGS = dict(wmin=9.0, wmax=None, nreg=20, road_bt=8.0, length_m=50.0)


def test_rule9_names_its_reason_inside_the_cctv_range() -> None:
    assert classify(**ARGS, cctv_dist=5.0, wsym=2.9) == ("needs_cv", "sym_low")


def test_rule9_outside_the_range_is_unchanged() -> None:
    assert classify(**ARGS, cctv_dist=60.0, wsym=2.9) == ("unknown", "needs_survey")
    assert classify(**ARGS, cctv_dist=5.0, wsym=3.0) == ("clear", None)


def test_the_other_rules_keep_source_conflict() -> None:
    assert classify(**ARGS, cctv_dist=5.0, wmin_any=2.0) == ("needs_cv", "source_conflict")
    assert classify(**ARGS, cctv_dist=5.0, clear_med=6.0) == ("needs_cv", "source_conflict")


def test_the_rule_text_and_schema_name_sym_low() -> None:
    assert "sym_low" in VERDICT_RULE[9], "규칙 [9] 문언이 cv_reason=sym_low 를 안 말한다"
    schema = (ROOT / "data/processed/segments.schema.json").read_text(encoding="utf-8")
    cv = json.loads(schema)["fields"]["cv_reason"]
    assert "sym_low" in cv and "source_conflict" in cv


def test_published_sym_low_is_exactly_rule9_territory() -> None:
    seg = ROOT / "web/data/segments.geojson"
    if not seg.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    feats = [f["properties"] for f in json.loads(seg.read_text(encoding="utf-8"))["features"]]
    got = [p for p in feats if p.get("cv_reason") == "sym_low"]
    assert got, "sym_low 가 한 건도 없다 — 이 시험이 아무것도 안 잰다(재발행 전이면 파이프라인을 돌려라)"
    for p in got:
        assert p["verdict"] == "needs_cv" and p["width_min_sym_m"] is not None and p["width_min_sym_m"] < 3.0, p["seg_id"]
    assert re.search(r"sym_low", VERDICT_RULE[9])
