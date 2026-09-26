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

IN    web/data/dest.geojson · web/data/poi.geojson ·
      data/processed/boundary_emd.geojson (없으면 tests/fixtures/dongmyeong_boundary.geojson)
OUT   없음 (검사)
밖    **검색이 잘 되는가는 안 본다.** 초성·부분일치 같은 질의 동작은
      `web/navi/test/domain.test.ts` 소관이다. 여기서 드는 것은 색인에
      **무엇이 들어 있는가** 하나다.
      그리고 주소·건물 항목의 범위는 안 본다 — 그쪽은 `navi_build` ·
      `navi_jibun` 이 원천이고 상가와 계보가 다르다.
      **관공서 갈래는 CI 에서 안 돈다** — `data/processed/civil_office.geojson` 이
      추적 밖이다. 경계와 달리 그쪽은 사본을 안 뜬다(64건 · 용도가 이 시험 하나뿐이라
      사본 유지 비용이 값어치를 넘는다). 그 갈래는 레이크 기계에서만 선다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "web" / "data" / "dest.geojson"
POI = ROOT / "web" / "data" / "poi.geojson"
BND = ROOT / "data" / "processed" / "boundary_emd.geojson"
#: 동명동 경계 **한 장**을 떼어 커밋한 것. `BND` 는 `.gitignore:26` 으로 추적 밖이라
#: CI 클론에 없고, 그러면 이 파일의 시험 다섯이 통째로 안 돈다 — 범위를 강제하려고
#: 세운 시험이 정작 관문에서 안 도는 것이다(2026-09-24 · DECISIONS §238).
#: 낡을 위험은 `test_committed_boundary_matches_the_pipeline` 이 든다 —
#: 레이크 기계에서 원본과 다르면 운다. **사본이 조용히 갈리는 길을 막는다.**
FIXTURE = ROOT / "tests" / "fixtures" / "dongmyeong_boundary.geojson"

#: 상가가 아닌 색인 항목. 계보가 달라 범위 규칙도 다르다.
NON_STORE = {"주소", "건물"}


def _load(p: Path):
    if not p.exists():
        # ★ 2026-09-24. 사유가 **분류 밖**이었다(`tests/skip_policy.py`). `boundary_emd`
        #   · `civil_office` 는 `.gitignore:26` 으로 추적 밖이라 CI 클론에는 없고,
        #   그러면 `conftest` 가 이 skip 을 **실패로** 바꾼다 — 로컬 초록 · CI 빨강
        #   (DECISIONS §206 이 제일 나쁜 모양이라고 적은 것).
        pytest.skip(f"환경skip(산출물) — {p.relative_to(ROOT)} 이 없다")
    return json.loads(p.read_text(encoding="utf-8"))


def _dongmyeong(doc) -> list:
    return [f for f in doc["features"]
            if f["properties"].get("EMD_KOR_NM") == "동명동"]


@pytest.fixture(scope="module")
def emd():
    """동명동 경계. **원본이 있으면 원본, 없으면 커밋된 사본.**

    ★ 사본을 쓰는 것이 아니라 *원본이 없을 때만* 쓴다. 둘이 갈리는 것은
      아래 `test_committed_boundary_matches_the_pipeline` 이 든다.
    """
    from shapely.geometry import shape
    src = BND if BND.exists() else FIXTURE
    got = _dongmyeong(json.loads(src.read_text(encoding="utf-8")))
    assert len(got) == 1, (
        f"{src.name} 의 동명동 경계가 {len(got)}개다 — 경계 원본이 바뀌었다. "
        "이 시험의 전제가 깨졌으므로 수를 고치기 전에 원인을 본다")
    return shape(got[0]["geometry"])


def test_committed_boundary_matches_the_pipeline():
    """커밋된 경계 사본이 파이프라인 산출과 **같은가.**

    ★ 사본을 두는 대가가 이것이다 — 원본이 바뀌면 사본이 조용히 낡는다.
      레이크 기계(원본이 있는 곳)에서만 잴 수 있고, 거기서 재면 충분하다.
      CI 는 사본으로 돌고 사본의 참은 여기서 지킨다(2족 · 정본이 둘).
    """
    if not BND.exists():
        pytest.skip(f"환경skip(산출물) — {BND.relative_to(ROOT)} 이 없다")
    src = json.loads(BND.read_text(encoding="utf-8"))
    kept_doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    real, kept = _dongmyeong(src), _dongmyeong(kept_doc)
    assert len(real) == 1 and len(kept) == 1, (real and len(real), len(kept))
    if real[0]["properties"] == kept[0]["properties"] and real[0]["geometry"] == kept[0]["geometry"]:
        return
    # ★ 2026-09-25 (§258). **갈렸을 때 원인을 여기서 가른다.** 「다시 떼라」만
    #   적혀 있던 종전 판은 원인이 ㉠ 재현 불가인지 ㉡ 원본 판 변경인지 알려주지
    #   않았고, 처방이 정반대다. 도구가 그 수치를 든다 — 사람이 손으로 재지 않는다.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "fixture_recut_t", ROOT / "tools" / "fixture_recut.py")
    assert spec and spec.loader
    fr = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fr   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(fr)
    why = "\n".join(fr.diagnose(kept_doc, src, fr.CUTS[0]))
    raise AssertionError(
        f"커밋된 경계 사본이 파이프라인 산출과 다르다 — {FIXTURE.relative_to(ROOT)}\n"
        f"{why}\n"
        "  1mm 넘게 움직였으면:  uv run python tools/fixture_recut.py --write\n"
        "  1mm 미만이면 같은 기계에서 두 번 돌려 원인을 먼저 가른다(§258-14).\n"
        "  이대로 두면 CI 는 옛 경계로 범위를 판정한다.")


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


def test_civil_offices_are_scoped_not_lost(emd):
    """관공서가 **2건뿐**인 것이 범위 때문인가, 조인이 흘린 것인가.

    ★ 2026-09-24 실측 — `civil_office` 64건 중 **동명동 안이 정확히 2**다
      (동명동행정복지센터 · 광주서석초등학교). 색인의 2건과 같다.
      「64 중 2뿐」은 관측이고 「흘렸다」는 판정이며, 판정에는 범위가 필요하다 —
      §235 가 상가에서 배운 것을 여기에도 건다.
    """
    from shapely.geometry import Point
    co = _load(ROOT / "data" / "processed" / "civil_office.geojson")
    inside = [f for f in co["features"]
              if emd.covers(Point(f["geometry"]["coordinates"][:2]))]
    indexed = [f for f in _load(DEST)["features"]
               if (f["properties"].get("src") or "") == "civil"]
    assert len(indexed) == len(inside), (
        f"관공서 색인 {len(indexed)} ≠ 동명동 안 {len(inside)} — 조인이 흘렸거나 넘쳤다")
    assert inside, "동명동 안 관공서가 0건이다 — 경계 판정이나 원천이 죽었다"


def test_apartment_buildings_are_not_collapsed_into_one():
    """같은 도로명주소로 묶으면서 **아파트 동을 뭉개지 않았는가.**

    ★ 2026-09-24 실측 — `조대명품타운 104동` · `105동` 이 각각 산다. 같은
      도로명주소가 둘 이상인 주소는 4개(8행)이고 전부 서로 다른 건물이다.
      **아파트 동이 뭉개지면 출동 지령이 엉뚱한 동으로 간다.**

    ★ 이름만으로 유일성을 보면 안 된다 — `주건축물제1동` 은 건축물대장의
      **일반 라벨**이라 다른 주소의 다른 건물이 같은 이름을 갖는다. 실제로
      둘 있다. 유일한 것은 `(이름, 주소)` 짝이다.
    """
    import re
    b = [f for f in _load(DEST)["features"]
         if (f["properties"].get("src") or "") == "build"]
    key = [(f["properties"].get("name"), f["properties"].get("addr")) for f in b]
    dup = sorted({k for k in key if key.count(k) > 1})
    assert not dup, f"같은 (이름, 주소) 가 두 번 들어갔다 — 뭉갠 흔적이다: {dup[:5]}"

    named = sorted({f["properties"]["name"] for f in b
                    if re.search(r"\S+\s\d+동$", f["properties"].get("name") or "")})
    assert len(named) >= 2, (
        f"이름 붙은 `N동` 건물이 {len(named)}개뿐이다: {named} — "
        "뭉갰거나 원천이 바뀌었다. 동명동에는 아파트가 셋뿐이라 수가 작다")
