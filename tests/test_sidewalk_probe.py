"""`tools/sidewalk_probe.py` — 보도 자료 결손 표본표가 규약대로 뽑히고 **덮어쓰지 않는다.**  (Zm32 · DECISIONS §577)

IN    tools/sidewalk_probe.py
OUT   없음 (검사)
PARAM 없음
밖    보도가 실제로 있는지는 안 본다 — 사람이 거리뷰로 채운다. 표본이 틀 안에서 결정적으로 뽑히는지, 사람이 채운 표를 안 덮는지만 본다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import sidewalk_probe as P

FRAME = [{"seg_id": f"DM{i:05d}", "seg_uid": f"DM-1-{i}-AAAA"} for i in range(200)]
PROPS = {r["seg_id"]: {"seg_uid": r["seg_uid"], "road_name": "가로", "length_m": 30.0 + i % 5} for i, r in enumerate(FRAME)}
MIDS = {r["seg_id"]: (35.15 + i * 1e-5, 126.92 + i * 1e-5) for i, r in enumerate(FRAME)}


def test_draw_is_deterministic_inside_the_frame_and_empty_when_asked_for_nothing() -> None:
    a, b = P.draw(FRAME, 20), P.draw(FRAME, 20)
    assert a == b and len(a) == 20 and len({r["seg_id"] for r in a}) == 20
    assert {r["seg_id"] for r in a} <= {r["seg_id"] for r in FRAME}
    assert not P.draw(FRAME, 0)
    assert len(P.draw(FRAME[:3], 20)) == 3, "틀이 k 보다 작으면 틀 전부"


def test_the_draw_does_not_depend_on_the_input_order() -> None:
    assert P.draw(FRAME, 20) == P.draw(list(reversed(FRAME)), 20), "표본이 입력 순서에 끌린다"


def test_the_table_has_only_prefilled_columns_and_blank_human_columns(tmp_path: Path) -> None:
    rows = P.build(FRAME, PROPS, MIDS)
    assert len(rows) == P.K and set(rows[0]) == set(P.COLS)
    assert all(r["sidewalk_present"] == "" and r["note"] == "" for r in rows)
    assert all(len(r["위도"].split(".")[1]) == 6 and len(r["경도"].split(".")[1]) == 6 for r in rows), "위경도는 소수 6자리"
    assert all(r["seg_uid"] for r in rows), "seg_uid 가 함께 있어야 한다"


def test_a_stale_frame_that_points_at_another_segment_stops_the_draw() -> None:
    bad = {**PROPS, FRAME[0]["seg_id"]: {**PROPS[FRAME[0]["seg_id"]], "seg_uid": "DM-9-9-ZZZZ"}}
    with pytest.raises(SystemExit):
        P.build([FRAME[0]], bad, MIDS)


def test_main_never_overwrites_an_existing_or_filled_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "p.csv"
    monkeypatch.setattr(P, "OUT_CSV", out)
    P.write(P.build(FRAME, PROPS, MIDS))
    assert out.exists() and not P.filled()
    assert P.main([]) == 3, "이미 있는데 다시 뽑았다"
    out.write_text(out.read_text(encoding="utf-8").replace(",,\n", ",Y,x\n", 1), encoding="utf-8")
    assert P.filled()
    before = out.read_text(encoding="utf-8")
    assert P.main(["--force"]) == 3 and out.read_text(encoding="utf-8") == before, "채워진 표를 덮어썼다"
