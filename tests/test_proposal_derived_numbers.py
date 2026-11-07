"""기획서의 영상판정 문단 수가 **발행본에서 유도한 값**과 같다.  (감사 5-3 · Zm22)

`docnum_check` 는 판정 건수와 사유별 수만 본다 — 이 문단의 연장(m) · 비율(%) · CCTV 거리 요약은 손으로 적혀 있었고
Zm19 뒤에도 옛 값(400구간 · 17,181m · 29% · 65%)으로 남았다. 여기서 발행본이 말하는 값을 재서 문장에 댄다.

IN    docs/proposal.md · web/data/segments.geojson
OUT   없음 (검사)
PARAM 없음
밖    **그 비율이 옳은 해석인가**는 안 본다 — 문장의 수가 발행본에서 나온 수와 같은지만 본다.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "web/data/segments.geojson"


def _facts() -> dict:
    if not SEG.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    P = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    total = sum(p["length_m"] for p in P)
    unk = [p for p in P if p["verdict"] == "unknown"]
    dist = [p["cctv_dist_m"] for p in P if p["cctv_dist_m"] is not None]
    inn = sum(1 for p in P if p["cv_feasible"])
    return {"unk_n": len(unk), "unk_m": round(sum(p["length_m"] for p in unk)),
            "unk_pct": round(sum(p["length_m"] for p in unk) / total * 100, 1),
            "out_pct": round((1 - inn / len(P)) * 100, 1),
            "med": round(statistics.median(dist), 1), "max": round(max(dist))}


def _doc() -> str:
    return (ROOT / "docs/proposal.md").read_text(encoding="utf-8")


def test_unavailable_video_span_matches_the_publication() -> None:
    f, doc = _facts(), _doc()
    want = f"영상판정 불가는 {f['unk_n']}구간 · {f['unk_m']:,}m 이며 전체 연장의 {f['unk_pct']}%에 해당한다"
    assert want in doc, f"기획서 영상판정 문단이 발행본과 다르다 — 기대: {want}"


def test_video_share_and_cctv_distance_match_the_publication() -> None:
    f, doc = _facts(), _doc()
    assert f"골목의 {f['out_pct']}%에는 적용할 수 없다" in doc
    assert f"CCTV 최단거리 중앙값은 {f['med']}m, 최대 {f['max']}m다" in doc


def test_the_stale_values_are_gone() -> None:
    doc = _doc()
    for stale in ("400구간 · 17,181m", "전체 연장의 29%", "골목의 65%"):
        assert stale not in doc, f"낡은 값이 남았다: {stale}"
