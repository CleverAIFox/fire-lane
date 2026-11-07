"""`width_med_m` — 법선 폭 표본의 **중앙값**. 판정은 읽지 않는다.  (Zm22 · DECISIONS §568-5 · 사람이 잠그기 전)

`width_min_m` 과 **같은 표본 · 같은 선택 규칙**(채택 소스 하나 · carve/escape/sum · `width_src` 우선순위)이고 집계만 min → median 이다.
새 규칙을 만들지 않는다. 발행 칸이 느니 골든 코드 지문이 움직인다 — 잠그는 것은 사람이 한다.

IN    src/firelane/seg/width.py · segments.py · classify.py · geom.py · 발행본 · width_samples.csv
OUT   없음 (검사)
PARAM 없음
밖    **중앙값이 옳은 대표값인가**는 안 본다 — 정의대로 나오는지, 판정이 안 읽는지, 발행본에 실렸는지만 본다.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

from firelane.seg.width import WidthEngine

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "web/data/segments.geojson"
SAMPLES = ROOT / "data/processed/width_samples.csv"
CENTER = LineString([(0, 0), (100, 0)])


def _engine(poly) -> WidthEngine:
    from shapely.geometry import MultiPoint
    from shapely.ops import unary_union

    return WidthEngine(poly, None, None, unary_union([]), MultiPoint([(-9999, -9999)]), None, walk_u=None)


def _road_with_pinch() -> Polygon:
    # 폭 8m 도로가 40~60 구간에서 2m 로 좁아진다 → 최솟값 2.0 · 중앙값은 8 쪽이다
    return Polygon([(-10, -4), (40, -4), (40, -1), (60, -1), (60, -4), (110, -4), (110, 4), (60, 4), (60, 1), (40, 1),
                    (40, 4), (-10, 4)])


def test_engine_returns_the_median_next_to_the_minimum() -> None:
    out = _engine(_road_with_pinch()).widths(CENTER)
    wmin, cov = out[0], out[6]
    assert len(cov) == 5, "_covr() 가 중앙값을 안 싣는다"
    wmed = cov[4]
    assert wmin == pytest.approx(2.0, abs=0.2)
    assert wmed is not None and wmed > wmin + 3.0, "병목 하나가 중앙값을 끌어내렸다 — 최솟값과 같은 집계다"


def test_median_of_a_uniform_road_equals_the_minimum() -> None:
    uniform = Polygon([(-10, -3), (110, -3), (110, 3), (-10, 3)])
    out = _engine(uniform).widths(CENTER)
    assert out[6][4] == pytest.approx(out[0], abs=0.05)


def test_no_source_gives_no_median() -> None:
    from shapely.geometry import MultiPoint
    from shapely.ops import unary_union

    out = WidthEngine(None, None, None, unary_union([]), MultiPoint([(-9999, -9999)]), None, walk_u=None).widths(CENTER)
    assert out[0] is None and out[6][4] is None


def _published() -> list[dict]:
    if not SEG.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    return [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]


def test_published_column_is_present_and_never_below_the_minimum() -> None:
    P = _published()
    assert all("width_med_m" in p for p in P), "발행본에 width_med_m 칸이 없다 — 재발행이 필요하다"
    bad = [p["seg_id"] for p in P if p["width_med_m"] is not None and p["width_min_m"] is not None
           and p["width_med_m"] < p["width_min_m"] - 0.011]
    assert not bad, f"중앙값이 최솟값보다 작은 구간: {bad[:5]}"
    assert any(p["width_med_m"] is not None for p in P)


def test_published_median_matches_the_sample_file_where_the_minimum_does() -> None:
    """표본 파일의 같은 소스 표본으로 최솟값이 재현되는 구간에서는 중앙값도 재현된다 — 같은 표본 · 같은 선택이다."""
    P = {p["seg_uid"]: p for p in _published()}
    if not SAMPLES.exists():
        pytest.skip("환경skip(산출물) — width_samples.csv 가 없다")
    by: dict[str, list[float]] = {}
    with SAMPLES.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            p = P.get(r["seg_uid"])
            if p and r["w_m"] and r["src"] == p["width_src"]:
                by.setdefault(r["seg_uid"], []).append(float(r["w_m"]))
    checked = same = 0
    for uid, ws in by.items():
        p = P[uid]
        if p["width_min_m"] is None or round(min(ws), 2) != round(p["width_min_m"], 2):
            continue                       # 최솟값이 재현되는 구간만 — 나머지는 다른 경로(병합 · 폴백)에서 왔다
        checked += 1
        same += abs(round(statistics.median(ws), 2) - p["width_med_m"]) <= 0.011
    assert checked > 800, f"비교할 구간이 {checked} — 이 시험이 아무것도 안 잰다"
    # ★ 정확 일치가 아니라 98% 다. 표본 파일의 `w_m` 은 표본마다 **채택된 값**이고 `width_min_m` 이 min 하는 목록(`_by[소스]`)과
    #   15/1,191 구간(1.3%)에서 다르다 — 최솟값은 우연히 같고 분포는 다르다(표본 수가 `n_sample` 과 다른 구간이 그렇다). 중앙값의 **정의**는
    #   위 엔진 단위 시험이 정확히 못박는다. 여기는 발행본이 그 정의를 따르는지만 본다.
    assert same / checked >= 0.98, f"중앙값이 표본과 어긋난다: {checked - same}/{checked}"


def test_the_judgment_never_reads_the_median() -> None:
    """`clear_min_m` 을 막은 것과 같은 방식 — 판정 코드가 `width_med_m` · 중앙값 인자를 읽으면 운다."""
    for rel in ("src/firelane/seg/classify.py", "src/firelane/seg/geom.py"):
        body = "\n".join(ln for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#"))
        assert "width_med" not in body and "wmed" not in body, f"{rel} 가 중앙값을 읽는다 — 판정은 width_min_m 만 읽는다"
    seg = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    call = seg[seg.index("classify(wmin=wmin"):]
    call = call[:call.index(")\n")]
    assert "wmed" not in call and "width_med" not in call, "classify() 호출에 중앙값이 들어갔다"
