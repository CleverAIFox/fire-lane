#!/usr/bin/env python3
"""
test_oneway_reason.py — **「방향을 모른다」의 사유가 실제로 갈리는가.** (§367)

── 왜 생겼나 ───────────────────────────────────────────────────
`publish_rules._oneway` 가 일방통행 57건 중 **1건만** 방향을 정했다. 남은 56건이
왜 모름인지는 **어디에도 없었다** — `stat` 이 `nl_twoway` 하나만 세고, 그 하나도
「넓게 봐서 반대 방향 둘이 잡힌」 좁은 갈래였다.

그 구별이 중요한 이유는 **처방이 다르기 때문**이다 —

    양방향이라 모른다      **모름이 맞다.** 고칠 것이 없다
    링크가 없다            표준노드링크가 그 골목을 안 든다(간선만 덮는다).
                           다른 원천이 필요하다 — 조율로는 안 풀린다
    좁게↔넓게 갈린다       버퍼 조율로 풀릴 수 있다
    node_link 가 없다      레이크 문제다

★ 이 시험은 **레이크를 안 읽는다.** 합성 GeoDataFrame 넷을 지어 네 갈래를
  각각 **한 건씩** 태운다 — 「실물에서 0건이니 통과」는 안 고치는 코드도
  통과시킨다(`test_fix_door` 가 결함을 심는 그 사유).

★ **사유가 분할인지도 문다.** 넷의 합이 「모름」과 같아야 한다. 안 같으면
  어떤 구간이 어느 칸에도 안 세어지고, 그러면 그 수가 거짓이 된다.

IN    src/firelane/publish_rules.py::_oneway
OUT   없음 (검사)
밖    **방향이 옳은가는 안 본다.** 그것은 실물 대조이고 레이크가 든다.
      **몇 건이어야 하는가도 안 본다** — 래칫(`navicheck`)이 든다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ★ `sys.path` 를 안 만진다 — 패키지이고 `test_layering` 이 그 손질을 막는다.
#   `geopandas` 가 없는 기계에서는 **이 파일째 건너뛴다**: `importorskip` 을
#   모듈 꼭대기에 두면 그 아래 import 가 E402 를 내므로, `pytest.importorskip`
#   대신 `pytestmark` 로 같은 일을 한다 — 억제 주석이 하나도 안 남는다.
pytest.importorskip("geopandas", reason="레이크 없이도 도는 검사지만 gpd 는 필요하다")

import geopandas as gpd
from shapely.geometry import LineString

from firelane import publish_rules as PN

CRS = "EPSG:5186"


def _gdf(lines: list[LineString], **cols) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({**cols, "geometry": lines}, crs=CRS)


def _seg(x0: float, y0: float, x1: float, y1: float) -> LineString:
    return LineString([(x0, y0), (x1, y1)])


@pytest.fixture
def lake(tmp_path, monkeypatch):
    """`_oneway` 가 읽는 두 파일을 합성으로 깐다. **`P` 를 갈아끼운다.**"""
    monkeypatch.setattr(PN, "P", tmp_path)
    return tmp_path


def _center(lake: Path, lines: list[LineString]) -> None:
    """`ngii1k_center_5186.gpkg` — 전부 「일방통행」으로 표시한다."""
    _gdf(lines, 일방통행=["일방통행"] * len(lines)).to_file(
        lake / "ngii1k_center_5186.gpkg", driver="GPKG")


def _nodelink(lake: Path, lines: list[LineString]) -> None:
    _gdf(lines, LINK_ID=[str(i) for i in range(len(lines))]).to_file(
        lake / "node_link_5186.gpkg", driver="GPKG")


# 구간 하나 — 동서로 200m. 넉넉히 길어 `_nl_signs` 의 10m 하한을 넘는다.
SEG = _seg(0, 0, 200, 0)
SAME = _seg(0, 0.5, 200, 0.5)        # 같은 방향으로 나란히
OPPO = _seg(200, -0.5, 0, -0.5)      # 반대 방향으로 나란히
FAR = _seg(0, 500, 200, 500)         # 버퍼 밖


def _run(lake: Path) -> dict:
    m = _gdf([SEG])
    _, stat = PN._oneway(m)
    return stat


def test_the_lake_file_missing_is_its_own_reason(lake):
    """`node_link` 가 없으면 `nl_absent` 다 — 「양방향」으로 안 센다."""
    _center(lake, [SEG])
    s = _run(lake)
    assert s["oneway"] == 1
    assert s["nl_absent"] == 1
    assert s["nl_twoway"] == 0 and s["nl_none"] == 0 and s["nl_split"] == 0


def test_two_way_is_the_reason_when_both_signs_are_there(lake):
    """반대 방향 둘이 잡히면 `nl_twoway` — **모름이 맞는** 갈래다."""
    _center(lake, [SEG])
    _nodelink(lake, [SAME, OPPO])
    s = _run(lake)
    assert s["nl_twoway"] == 1, s
    assert s["dir_known"] == 0


def test_no_link_at_all_is_a_different_reason(lake):
    """★ 버퍼 안에 링크가 없으면 `nl_none` 이다.

    종전에는 이것이 **어느 칸에도 안 세어졌다** — 「양방향 N」만 찍었으므로
    사람이 보면 「나머지는 뭐지」로 끝났다. 처방이 가장 다른 갈래다:
    조율로 안 풀리고 **다른 원천이 필요하다.**
    """
    _center(lake, [SEG])
    _nodelink(lake, [FAR])
    s = _run(lake)
    assert s["nl_none"] == 1, s
    assert s["nl_twoway"] == 0


def test_one_direction_both_narrow_and_wide_is_known(lake):
    """한 방향만 좁게도 넓게도 잡히면 **방향을 정한다.** 양성 대조다."""
    _center(lake, [SEG])
    _nodelink(lake, [SAME])
    s = _run(lake)
    assert s["dir_known"] == 1, s
    assert s["nl_none"] == 0 and s["nl_twoway"] == 0 and s["nl_split"] == 0


def test_the_reasons_partition_the_unknowns(lake):
    """★ **분할인가.** 넷의 합이 「모름」과 같아야 한다.

    안 같으면 어떤 구간이 어느 칸에도 안 세어지고, 그러면 화면의 수가
    거짓이 된다 — 바로 이 시험이 생긴 사유의 되풀이다.
    """
    _center(lake, [SEG, _seg(0, 100, 200, 100), _seg(0, 200, 200, 200)])
    # 첫 구간엔 같은 방향 하나(확정) · 둘째엔 반대 둘(양방향) · 셋째엔 아무것도
    _nodelink(lake, [SAME, _seg(0, 100.5, 200, 100.5), _seg(200, 99.5, 0, 99.5)])
    m = _gdf([SEG, _seg(0, 100, 200, 100), _seg(0, 200, 200, 200)])
    _, s = PN._oneway(m)
    unknown = s["oneway"] - s["dir_known"]
    reasons = s["nl_twoway"] + s["nl_none"] + s["nl_split"] + s["nl_absent"]
    assert reasons == unknown, (
        f"사유 {reasons} ≠ 모름 {unknown} — 어느 칸에도 안 세어진 구간이 있다\n  {s}")
    assert unknown > 0, "모름이 0 이면 이 시험이 빈 그물이다 — 합성을 고쳐라"


def test_the_stat_declares_all_four_reasons():
    """칸 넷이 **처음부터 0 으로 선언**돼 있는가 — 늦게 생기면 `KeyError` 다."""
    import inspect
    src = inspect.getsource(PN._oneway)
    for k in ("nl_twoway", "nl_none", "nl_split", "nl_absent"):
        assert f'"{k}": 0' in src, f"`{k}` 가 초기 선언에 없다"
