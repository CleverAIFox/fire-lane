"""`tools/ledgercross.py` — 대장 계단 올림 · d 계산 · 산출 스키마 · 폐포 밖 · 문턱이 분포에서 나오는가.  (Zm21)

IN    tools/ledgercross.py · src/firelane/segments.py(폐포) · web/data/segments.geojson
OUT   없음 (검사)
PARAM 없음
밖    **대장이 참인가**는 안 본다 — 정의대로 세는지, 판정 폐포를 안 건드리는지, 문턱을 박지 않았는지만 본다.
      `ledger_cross.json` 의 **수**가 옳은지는 `uv run python tools/ledgercross.py` 가 낸 표를 사람이 읽는다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import ledgercross as L
import pyfiles
import pytest

ROOT = Path(__file__).resolve().parents[1]
STEPS = [1.0, 2.0, 3.0, 6.0, 9.0, 15.0]


def test_ceil_picks_the_first_step_at_or_above() -> None:
    assert L.ceil_idx(2.0, STEPS) == (1, False)          # 같으면 자기 자신 — 동점은 올리지 않는다
    assert L.ceil_idx(2.0001, STEPS) == (2, False)
    assert L.ceil_idx(0.2, STEPS) == (0, False)
    assert L.ceil_idx(15.4, STEPS) == (5, True)          # 최대 초과는 접고 표시한다


def test_gap_is_ledger_index_minus_ours_and_signed() -> None:
    assert L.gap(15.0, 2.5, STEPS) == (3, False)         # 대장이 위 → 양수
    assert L.gap(1.0, 7.0, STEPS) == (-4, False)         # 대장이 아래 → 음수
    assert L.gap(6.0, 5.2, STEPS) == (0, False)


def test_steps_are_derived_not_listed() -> None:
    assert L.steps_of([3.0, 1.0, 3.0000001, 15.0]) == [1.0, 3.0, 15.0]
    src = (ROOT / "tools/ledgercross.py").read_text(encoding="utf-8")
    assert not re.search(r"\[\s*1\.0\s*,\s*2\.0\s*,\s*3\.0\s*,\s*4\.0", src), "계단 집합을 손으로 적었다"


def _rows(scale: float = 1.0) -> list[dict]:
    rows = []
    pairs = [(2.0, 2.0), (3.0, 2.5), (9.0, 1.0), (1.0, 8.5), (9.0, 8.9), (15.0, 14.0), (6.0, 5.5), (30.0, 1.0), (1.0, 29.0), (25.0, 2.0)] * 5
    for i, (lg, w) in enumerate(pairs):
        rows.append({"seg_id": f"S{i:03d}", "road_name": f"R{i % 3}", "road_bt_m": lg, "width_min_m": w,
                     "ecc_rel_med_m": scale * (0.1 + 0.01 * i), "verdict": "clear", "lat": 35.1, "lon": 126.9})
    return rows


def test_output_has_the_required_keys_and_shapes() -> None:
    res = L.analyse(_rows())
    assert set(res) == set(L.KEYS)
    assert set(res["groups"]) >= {"ledger_above", "ledger_below", "ecc_high", "overlap"}
    assert res["groups"]["ecc_high"]["percentile"] == L.ECC_PCT
    assert res["groups"]["ecc_high"]["threshold"] is not None
    row = res["contradictions"][0]
    assert set(L.LIST_COLS) <= set(row) and re.fullmatch(r"-?\d+\.\d{6}, -?\d+\.\d{6}", row["latlon"])
    json.dumps(res, ensure_ascii=False)                     # 직렬화가 된다


def test_groups_partition_by_sign() -> None:
    g = L.analyse(_rows())["groups"]
    assert g["ledger_above"]["n"] + g["ledger_below"]["n"] == g["n_contradictions"] > 0


def test_ecc_threshold_comes_from_the_normal_group_distribution() -> None:
    a = L.analyse(_rows(1.0))["groups"]["ecc_high"]["threshold"]
    b = L.analyse(_rows(3.0))["groups"]["ecc_high"]["threshold"]
    assert a is not None and b is not None
    assert b == pytest.approx(a * 3.0, rel=1e-3), "문턱이 분포를 따라 움직이지 않는다 — 상수로 박혔다"
    src = (ROOT / "tools/ledgercross.py").read_text(encoding="utf-8")
    assert not re.search(r"ecc\w*\s*[<>]=?\s*0\.\d", src), "ecc 문턱을 리터럴로 박았다"


def test_empty_input_does_not_invent_numbers() -> None:
    res = L.analyse([])
    assert res["counts"]["usable"] == 0 and res["groups"]["ecc_high"]["threshold"] is None


def test_missing_values_are_excluded_and_counted() -> None:
    res = L.analyse(_rows() + [{"seg_id": "X", "road_bt_m": None, "width_min_m": 3.0}])
    assert res["counts"]["excluded"] == 1


def test_the_tool_is_outside_the_judgment_closure() -> None:
    from firelane.shardseal import code_closure

    files = {p.relative_to(ROOT).as_posix() for p in code_closure("firelane.segments")}
    assert "tools/ledgercross.py" not in files
    # ★ Zm35. 훑기는 src · tools · tests 전부 하고 **단언이 src 만 본다** — tools · tests 가 이 도구를 부르는 것은 정상이다(도구의 쓰임 · 그 시험).
    #   금지되는 것은 판정 쪽(src)이 부르는 것 하나다. 훑는 폴더를 src 로 좁히면 좁음이 의도인지 빠뜨림인지 코드에서 안 읽힌다(deadcheck ⑤).
    users = [u for u in pyfiles.rel(ROOT, pyfiles.all_py(ROOT)) if u.startswith("src/")
             and re.search(r"\bledgercross\b", (ROOT / u).read_text(encoding="utf-8"))]
    assert not users, f"src 가 이 도구를 부른다 — 폐포가 넓어진다: {users}"


def test_real_publication_if_present() -> None:
    if not L.SEG.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    res = L.analyse(L.load())
    assert res["counts"]["segments"] == 1281 and res["counts"]["usable"] > 1000
    assert res["steps"]["n_distinct"] >= 10


def test_median_basis_changes_only_our_side() -> None:
    """같은 구간 · 같은 계단에서 우리 폭 칸만 바꾼다 — 대장 쪽 통계는 같다.  (Zm22)"""
    rows = _rows()
    for r in rows:
        r["width_med_m"] = r["width_min_m"] * 1.5
    res = L.analyse_both(rows)
    assert set(res) == set(L.KEYS_BOTH)
    assert res["median_basis"]["params"]["our_width_col"] == "width_med_m"
    assert res["median_basis"]["steps"]["values"] == res["steps"]["values"]
    ov = res["contradiction_overlap"]
    assert ov["both"] + ov["only_min"] == ov["min_basis"] and ov["both"] + ov["only_median"] == ov["median_basis"]
