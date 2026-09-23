#!/usr/bin/env python3
"""
test_dest_scope.py — 목적지 색인의 **범위가 선언대로인가.**

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-24 (PLAN §1 #59 정정 · DECISIONS §235). 2026-09-23 에 조사 도구가
  「지도에 찍히는 상가 2,106건 중 검색 색인에 든 것이 519건뿐이다.
  **1,587건이 빠졌다**」고 냈고, 그것이 `PLAN #59` 의 남은 일로 올라갔다.

  **결함이 아니었다.** `DECISIONS §183-1` 이 목적지를 **동명동 경계 안**으로
  한정한다. 지도는 표출 스코프(동명동 + 접근 회랑)를 그리므로 그 차이가
  1,587 이다. 실측 —

      지도 상가 poi 2,106   동명동 안 519 · 밖 1,587
      검색 색인 상가류 521   동명동 밖 **0**
      동명동 안인데 색인에 없는 이름 **0**

★ 왜 그 도구가 틀렸나 — **경계를 안 읽고 수만 셌다.** 두 수가 다르다는
  것은 관측이지만 「빠졌다」는 판정이고, 판정에는 범위가 필요하다.
  같은 날 같은 형태로 셋이 났다(§226) — 범위를 모르는 도구는 수를 맞게
  세고도 **틀린 결론**을 낸다.

★ 이 시험이 있었으면 그 발견이 애초에 안 났다. 그래서 여기 세운다 —
  **관측을 판정으로 만드는 것은 범위 선언이고, 그 선언은 실행돼야 한다.**

IN    web/data/dest.geojson · web/data/poi.geojson · data/processed/boundary_emd.geojson
OUT   없음 (검사)
밖    **검색이 잘 되는가는 안 본다.** 초성·부분일치 같은 질의 동작은
      `web/navi/test/domain.test.ts` 소관이다. 여기서 드는 것은 색인에
      **무엇이 들어 있는가** 하나다.
      그리고 주소·건물 항목의 범위는 안 본다 — 그쪽은 `navi_build` ·
      `navi_jibun` 이 원천이고 상가와 계보가 다르다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "web" / "data" / "dest.geojson"
POI = ROOT / "web" / "data" / "poi.geojson"
BND = ROOT / "data" / "processed" / "boundary_emd.geojson"

#: 상가가 아닌 색인 항목. 계보가 달라 범위 규칙도 다르다.
NON_STORE = {"주소", "건물"}


def _load(p: Path):
    if not p.exists():
        pytest.skip(f"{p.relative_to(ROOT)} 이 없다 — 파이프라인 산출물이다")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def emd():
    from shapely.geometry import shape
    b = _load(BND)
    got = [shape(f["geometry"]) for f in b["features"]
           if f["properties"].get("EMD_KOR_NM") == "동명동"]
    assert len(got) == 1, (
        f"동명동 경계가 {len(got)}개다 — 경계 원본이 바뀌었다. "
        "이 시험의 전제가 깨졌으므로 수를 고치기 전에 원인을 본다")
    return got[0]


@pytest.fixture(scope="module")
def stores():
    return [f for f in _load(DEST)["features"]
            if (f["properties"].get("cat") or "") not in NON_STORE]


def test_index_is_inside_the_declared_scope(emd):
    """색인이 **동명동 밖**을 담지 않는가 (DECISIONS §183-1)."""
    from shapely.geometry import Point
    out = [f["properties"].get("name") for f in _load(DEST)["features"]
           if not emd.covers(Point(f["geometry"]["coordinates"]))]
    assert not out, (
        f"목적지 색인에 동명동 **밖**이 {len(out)}건 있다: {out[:8]}\n"
        "  §183-1 이 목적지를 동명동으로 한정한다. 넓히려면 그 결정을 먼저 고친다.")


def test_every_store_inside_the_scope_is_indexed(emd, stores):
    """동명동 **안** 상가가 빠짐없이 색인에 있는가.

    ★ 이 방향이 진짜 결함을 잡는 쪽이다. 위 시험은 「넘치지 않는가」이고
      이쪽은 「모자라지 않는가」다. 둘 다 있어야 범위가 선언이 된다.
    """
    from shapely.geometry import Point
    inside = {f["properties"].get("name") for f in _load(POI)["features"]
              if emd.covers(Point(f["geometry"]["coordinates"]))}
    indexed = {f["properties"].get("name") for f in stores}
    miss = sorted(x for x in inside - indexed if x)
    assert not miss, (
        f"지도에 찍히는데 검색이 안 되는 동명동 상가 {len(miss)}건: {miss[:8]}\n"
        "  사용자가 화면에서 보는 가게를 검색창에 쳐도 안 나온다.")


def test_the_gap_is_scope_not_loss(emd):
    """★ **빈 그물이 아닌가.** 지도와 색인의 수 차이가 실제로 크고,
    그 차이가 전부 **경계 밖**으로 설명되는가.

    차이가 0 이면 위 두 시험은 아무것도 안 든 것이다 — 이 저장소가
    0건을 청결로 읽지 않는 규율(`deadcheck` 2026-09-21)을 여기에도 건다.
    """
    from shapely.geometry import Point
    poi = _load(POI)["features"]
    out = [f for f in poi if not emd.covers(Point(f["geometry"]["coordinates"]))]
    assert len(out) > 100, (
        f"지도 상가 중 동명동 밖이 {len(out)}건뿐이다 — 표출 스코프가 좁아졌거나 "
        "경계 판정이 죽었다. 어느 쪽이든 위 두 시험이 빈 그물이 된다")
    assert len(poi) - len(out) > 100, "동명동 안 상가가 너무 적다 — 원천이 비었다"
