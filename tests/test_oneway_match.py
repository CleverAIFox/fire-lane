"""
test_oneway_match.py — `tools/oneway_match.py`(일방통행 두 목록 → 우리 구간 · 발행 변화 계산)의 **순수 함수**.  (DECISIONS §652)

① 끝점 지번 읽기(접두 · 괄호 · 행정동 → 법정동 · 지번 없음) ② 두 목록 읽기(병합 머리 3줄을 위치로 건너뛰고 머리글이 바뀌면 죽는다 · hwpx 의 기호 `～` `→`)
③ 경로 방향(a→b 와 같으면 +1) ④ 분류가 두 문턱을 닫힌 구간으로 쓴다 ⑤ 방향 계수가 `rules.ts` 와 같고 상수를 거기서 읽는다 ⑥ 매칭 · 방향 근거 · 민감도(합성 구간)

IN    합성 CSV · 합성 hwpx · 합성 구간 표 · `web/navi/src/domain/rules.ts`
OUT   통과/실패
밖    실제 레이크 · 지적도 · 발행본. 실물 결과는 DECISIONS §652 가 든다.
"""
from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("oneway_match", ROOT / "tools/oneway_match.py")
assert _spec and _spec.loader
tool = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = tool
_spec.loader.exec_module(tool)


# ── ① 끝점 ──
@pytest.mark.parametrize("raw,want", [
    ("대인동 156", ("대인동", "156")),
    ("황금동5-11", ("황금동", "5-11")),
    ("금남로5가 185", ("금남로5가", "185")),
    ("지산1동461-1", ("지산동", "461-1")),                                    # 행정동 → 법정동
    ("동명동125", ("동명동", "125")),
    ("～ 동구 동명동 118-21(순환도로 입구)", ("동명동", "118-21")),           # 접두 · 괄호 속 장소명
    ("광주광역시 동구 대인동 156(중앙로 맹호4거리)", ("대인동", "156")),
    ("→ 동구 장동86-7(새벽달)", ("장동", "86-7")),
])
def test_endpoints_become_legal_dong_and_jibun(raw, want):
    assert tool.parse_endpoint(raw)[0] == want


@pytest.mark.parametrize("raw", ["설월교", "장동교차로", "→ 장동교차로", "광주광역시 동구 학동 설월교(천변우로 방향)", ""])
def test_endpoints_without_a_jibun_are_none_not_a_guess(raw):
    assert tool.parse_endpoint(raw)[0] is None


def test_legal_dong_only_strips_the_administrative_digit():
    assert tool.legal_dong("지산1동") == "지산동" and tool.legal_dong("금남로5가") == "금남로5가" and tool.legal_dong("동명동") == "동명동"


# ── ② 두 목록 ──
CITY = ("연번,관할 ,도로명 ,구간,,\n,경찰서,,길이,,\n,,,(m) ,시점부 ,종점부 \n"
        "1,동부,구성로204번길,300,대인동 156,대인동 32-12\n2,동부,필문대로,670,지산동502-1,동명동 118-21\n,,,,,\n")


def test_the_three_line_merged_header_is_skipped_by_position_and_checked_by_text(tmp_path):
    f = tmp_path / "c.csv"
    f.write_text(CITY, encoding="utf-8")
    rows = tool.read_city_rows(f)
    assert [(r["n"], r["road"], r["len"], r["s"], r["e"]) for r in rows] == [
        (1, "구성로204번길", 300, "대인동 156", "대인동 32-12"), (2, "필문대로", 670, "지산동502-1", "동명동 118-21")], "빈 줄 · 머리는 행이 아니다"
    g = tmp_path / "bad.csv"
    g.write_text(CITY.replace("시점부", "출발").replace("종점부", "도착"), encoding="utf-8")
    with pytest.raises(ValueError, match="머리글이 바뀌었다"):
        tool.read_city_rows(g)


def _hwpx(tmp_path, paras):
    body = "".join(f"<hp:p><hp:run><hp:t>{t}</hp:t></hp:run></hp:p>" for t in paras)
    f = tmp_path / "p.hwpx"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Contents/section0.xml", f"<root>{body}</root>")
    f.write_bytes(buf.getvalue())
    return f


def test_the_police_rows_keep_the_range_or_arrow_symbol_and_the_remarks(tmp_path):
    P = ["□ 차량 일방통행구간(동구)", "연번", "구간(장소)", "거리(m)", "비고",
         "1", "광주광역시 동구 대인동 156(중앙로 맹호4거리)", "～ 동구 대인동 32-12(코스코 앞)", "300",
         "2", "광주광역시 동구 대인동 138(신평회관)", "～ 동구 대인동 83-3(흥국생명 옆 4거리)", "30", "단, 충장로4가 58 ～ 40-3 60m 제외",
         "3", "광주광역시 동구 백서로219 (동명모락)", "→ 동구 장동로11 (새벽달)", "1,320",
         "계", "12,853"]
    rows = tool.read_police_rows(_hwpx(tmp_path, P))
    assert [(r["n"], r["op"], r["len"]) for r in rows] == [(1, "～", 300), (2, "～", 30), (3, "→", 1320)], "쉼표 천 단위 · 합계 행은 행이 아니다"
    assert rows[1]["rest"] == ["단, 충장로4가 58 ～ 40-3 60m 제외"], "비고(제외 구간)가 남는다"


# ── ③ 방향 ──
def test_edge_signs_follow_the_path_against_each_segments_a_to_b():
    ab = {frozenset((1, 2)): (1, 2), frozenset((2, 3)): (3, 2)}      # 둘째 구간은 a=3 → b=2
    assert tool.edge_signs([1, 2, 3], ab) == [1, -1], "경로가 a→b 와 같으면 +1 · 반대면 −1"
    assert tool.edge_signs([3, 2, 1], ab) == [1, -1], "거꾸로 가면 부호가 뒤집힌다 — 3→2 는 a→b 이고 2→1 은 b→a"


# ── ④ 분류 ──
def test_classify_uses_the_two_tolerances_as_closed_bounds():
    t, (lo, hi) = tool.END_TOL_M, tool.RATIO
    assert tool.classify(t, t, 1.0) == "붙음" and tool.classify(t, t, lo) == "붙음" and tool.classify(t, t, hi) == "붙음"
    assert tool.classify(t, t, hi + 0.01) == "어긋남" and tool.classify(t, t, None) == "어긋남"
    assert tool.classify(t, t + 0.1, 1.0) == "부분" and tool.classify(t + 0.1, t, 1.0) == "부분"
    assert tool.classify(t + 1, t + 1, 1.0) == "밖" and tool.classify(None, None, None) == "밖"


# ── ⑤ 방향 계수 ──
def test_rule_constants_are_read_from_rules_ts_and_direction_factor_matches_it():
    c = tool.rule_consts((ROOT / "web/navi/src/domain/rules.ts").read_text(encoding="utf-8"))
    assert c["WRONG_WAY"] >= 1 and c["ONEWAY_UNKNOWN"] >= 1, "배수가 1 이상이라 A* 휴리스틱이 admissible 하다"
    w, u = c["WRONG_WAY"], c["ONEWAY_UNKNOWN"]
    assert (tool.direction_factor(1, True, w, u), tool.direction_factor(1, False, w, u)) == (1.0, w)
    assert (tool.direction_factor(-1, True, w, u), tool.direction_factor(-1, False, w, u)) == (w, 1.0)
    assert tool.direction_factor(2, True, w, u) == tool.direction_factor(2, False, w, u) == u, "방향 모름은 양쪽 다"
    assert tool.direction_factor(0, True, w, u) == 1.0
    with pytest.raises(ValueError):
        tool.rule_consts("export const WRONG_WAY = 4;")


# ── ⑥ 매칭 · 근거 · 민감도(합성 구간) ──
def _seg():
    """x 축으로 놓인 같은 도로명 세 구간(각 100m · a→b 가 동쪽). 노드 1-2-3-4."""
    rows = [("U1", 1, 2, 0, 0), ("U2", 2, 3, 100, 2), ("U3", 3, 4, 200, 2)]
    g = gpd.GeoDataFrame({"seg_uid": [r[0] for r in rows], "a": [r[1] for r in rows], "b": [r[2] for r in rows], "ow": [r[4] for r in rows],
                          "road_name": "시험로", "length_m": 100.0, "width_min_m": 6.0, "verdict": "clear",
                          "geometry": [LineString([(r[3], 0), (r[3] + 100, 0)]) for r in rows]}, crs=5186)
    xy = {1: (0, 0), 2: (100, 0), 3: (200, 0), 4: (300, 0)}
    return g, xy


def test_match_row_joins_a_same_named_path_and_reports_the_direction_per_segment():
    seg, xy = _seg()
    idx = {("가동", "1"): (2, 0), ("가동", "2"): (298, 0)}            # 시점 → 종점이 동쪽
    row = {"n": 1, "road": "시험로", "len": 300, "s": "가동 1", "e": "가동 2"}
    r = tool.match_row(row, seg, xy, idx)
    assert r["status"] == "붙음" and r["ratio"] == 1.0 and [e["sheet"] for e in r["edges"]] == [1, 1, 1]
    assert [e["ow"] for e in r["edges"]] == [0, 2, 2], "우리 ow 와 같이 나온다 — 0 이면 충돌이다"
    rev = tool.match_row({**row, "s": "가동 2", "e": "가동 1"}, seg, xy, idx)
    assert [e["sheet"] for e in rev["edges"]] == [-1, -1, -1], "시점 · 종점이 바뀌면 부호가 뒤집힌다"


@pytest.mark.parametrize("row,idx,status", [
    ({"n": 1, "road": "시험로", "len": 200, "s": "설월교", "e": "가동 2"}, {("가동", "2"): (298, 0)}, "끝점 지번 없음"),
    ({"n": 1, "road": "시험로", "len": 200, "s": "가동 9", "e": "가동 2"}, {("가동", "2"): (298, 0)}, "끝점 좌표 없음"),
    ({"n": 1, "road": "없는로", "len": 200, "s": "가동 1", "e": "가동 2"}, {("가동", "1"): (2, 0), ("가동", "2"): (298, 0)}, "도로명 구간 없음"),
    ({"n": 1, "road": "시험로", "len": 300, "s": "가동 1", "e": "가동 2"}, {("가동", "1"): (2, 0), ("가동", "2"): (5000, 0)}, "부분"),
    ({"n": 1, "road": "시험로", "len": 20, "s": "가동 1", "e": "가동 2"}, {("가동", "1"): (2, 0), ("가동", "2"): (298, 0)}, "어긋남"),
])
def test_match_row_names_the_reason_instead_of_forcing_a_match(row, idx, status):
    seg, xy = _seg()
    assert tool.match_row(row, seg, xy, idx)["status"] == status


def test_a_duplicated_parcel_key_is_reported_as_duplicate_not_missing():
    seg, xy = _seg()
    r = tool.match_row({"n": 1, "road": "시험로", "len": 200, "s": "가동 1", "e": "가동 2"}, seg, xy, {("가동", "2"): (298, 0)}, dup={("가동", "1")})
    assert r["status"] == "끝점 좌표 없음(중복)" and "같은 지번이 둘" in r["why"]


def test_orientation_checks_pair_by_endpoint_and_length_and_skip_other_streets_ends():
    seg, xy = _seg()
    seg.loc[0, "ow"] = 1                                              # 우리 ow=1(a→b 허용 = 동쪽)
    idx = {("가동", "1"): (3, 0), ("가동", "2"): (101, 0), ("가동", "9"): (298, 0)}
    rows = [{"n": 7, "len": 100, "s": "가동 1", "e": "가동 2"},      # 이 구간을 덮는다: 시점이 a 에 붙는다 → +1
            {"n": 8, "len": 320, "s": "가동 9", "e": "가동 2"}]      # 길이가 안 맞는다 — 교차로로 들어오는 다른 구간
    out = tool.orientation_checks(rows, seg, {1: (0, 0), 2: (100, 0), 3: (200, 0), 4: (300, 0)}, idx)
    assert {x["row"] for x in out} == {7} and all(x["same"] for x in out) and {x["side"] for x in out} == {"s", "e"}
    seg.loc[0, "ow"] = -1
    assert not any(x["same"] for x in tool.orientation_checks(rows, seg, {1: (0, 0), 2: (100, 0), 3: (200, 0), 4: (300, 0)}, idx)), "반대면 어긋남으로 나온다"


def test_sensitivity_reports_zero_change_without_known_directions_and_counts_wrong_way_uses_with_them():
    seg, _xy = _seg()
    seg = seg.copy()
    consts = {"WRONG_WAY": 4.0, "ONEWAY_UNKNOWN": 1.5}
    out = tool.sensitivity(seg, consts, [("지금", {}), ("방향 부여", {"U2": 1})])      # 센터가 동쪽이라 서쪽으로 가는 길이 a→b(동쪽만 허용) 의 역주행이 된다
    now = [r for r in out if r["variant"] == "지금"]
    assert all(r["changed"] == 0 and r["uses_wrong_way"] == 0 for r in now), "방향 확정이 없으면 배수는 경로를 못 바꾼다"
    given = {r["wrong"]: r for r in out if r["variant"] == "방향 부여"}
    assert given[1e6]["uses_wrong_way"] >= 1, "역주행으로만 닿는 노드는 배수가 아무리 커도 그 간선을 쓴다 — 막지 않고 비싸게 칠 뿐이다"
