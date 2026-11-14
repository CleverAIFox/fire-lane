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

★ 2026-11-14 (PLAN #227 · DECISIONS §730-3 의 2 — 사람이 골랐다). **선언이 바뀌었다.**
  범위는 이제 **지도 이동 범위**(`view.maxBounds`)다. 판정 범위(동명동)와 검색
  범위는 다른 축이다 — 지도에 관공서 38이 보이는데 검색은 2였다. 위 2026-09-24 의
  교훈(범위를 읽고 판정하라)은 그대로고, 읽을 범위만 바뀌었다. 동명동 경계는
  「넓힌 것이 실제로 넓은가」를 재는 자로 남는다.

IN    web/data/dest.geojson · web/data/poi.geojson · web/data/view.json ·
      web/data/navi_graph.json · web/config.js(지점의 정본) ·
      data/processed/boundary_emd.geojson (없으면 tests/fixtures/dongmyeong_boundary.geojson)
OUT   없음 (검사)
밖    **검색이 잘 되는가는 안 본다.** 초성·부분일치 같은 질의 동작은
      `web/navi/test/domain.test.ts` 소관이다. 여기서 드는 것은 색인에
      **무엇이 들어 있는가** 하나다.
      그리고 주소·건물 항목의 범위는 안 본다 — 그쪽은 `navi_build` ·
      `navi_jibun` 이 원천이고 상가와 계보가 다르다.
      **관공서 갈래의 수 대조는 CI 에서 안 돈다**(이름 셋은 돈다) — `data/processed/civil_office.geojson` 이
      추적 밖이다. 경계와 달리 그쪽은 사본을 안 뜬다(64건 · 용도가 이 시험 하나뿐이라
      사본 유지 비용이 값어치를 넘는다). 그 갈래는 레이크 기계에서만 선다.
PARAM 없음 — 범위는 `view.json` 에서 읽는다(여기 적지 않는다)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "web" / "data" / "dest.geojson"
POI = ROOT / "web" / "data" / "poi.geojson"
VIEW = ROOT / "web" / "data" / "view.json"
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
def move():
    """지도 이동 범위 — `web/data/view.json` 의 `maxBounds`. 화면이 읽는 바로 그 값이다."""
    from shapely.geometry import box
    (w, s), (e, n) = _load(VIEW)["maxBounds"]
    return box(w, s, e, n)


@pytest.fixture(scope="module")
def stores():
    return [f for f in _load(DEST)["features"]
            if (f["properties"].get("src") or "") == "store"]


def _pt(f):
    from shapely.geometry import Point
    return Point(f["geometry"]["coordinates"][:2])


def test_index_is_inside_the_declared_scope(move):
    """색인이 **지도 이동 범위 밖**을 담지 않는가 (DECISIONS §730-3 의 2 · PLAN #227)."""
    out = [f["properties"].get("name") for f in _load(DEST)["features"] if not move.covers(_pt(f))]
    assert not out, (
        f"목적지 색인에 지도 이동 범위 **밖**이 {len(out)}건 있다: {out[:8]}\n"
        "  지도가 못 가는 곳을 검색이 데려간다. 넓히려면 `view.maxBounds` 를 먼저 고친다.")


def test_every_store_on_the_map_is_indexed(move, stores):
    """지도에 찍히는 상가가 빠짐없이 색인에 있는가.

    ★ 이 방향이 진짜 결함을 잡는 쪽이다. 위 시험은 「넘치지 않는가」이고
      이쪽은 「모자라지 않는가」다. 둘 다 있어야 범위가 선언이 된다.
    ★ 2026-11-14. 종전에는 「동명동 안 상가」만 물었다 — 그래서 지도에 보이는
      동명동 밖 가게 712곳이 검색에 없어도 초록이었다(§183-1 이 그렇게 정했다).
    """
    poi = [f for f in _load(POI)["features"] if move.covers(_pt(f))]
    indexed = {f["properties"].get("name") for f in stores}
    miss = sorted({f["properties"].get("name") for f in poi} - indexed - {None, ""})
    assert not miss, (
        f"지도에 찍히는데 검색이 안 되는 상가 {len(miss)}건: {miss[:8]}\n"
        "  사용자가 화면에서 보는 가게를 검색창에 쳐도 안 나온다.")
    assert len(stores) == len(poi), (
        f"색인 상가 {len(stores)} ≠ 지도 상가 {len(poi)} — 한쪽이 넘치거나 뭉갰다")


def test_the_widening_is_real_not_an_empty_net(emd, stores):
    """★ **빈 그물이 아닌가.** 색인이 실제로 동명동 **밖** 상가를 담고, 안쪽도 비지 않았는가.

    밖이 0 이면 범위가 §183-1(동명동만)로 되돌아간 것이고 위 두 시험은 그것을
    못 잡는다(동명동 ⊂ 지도 이동 범위라 「안 넘친다」는 여전히 참이다).
    2026-11-14 실측 — 상가 987 중 동명동 안 275 · 밖 712.
    """
    out = [f for f in stores if not emd.covers(_pt(f))]
    assert len(out) > 100, (
        f"색인 상가 중 동명동 밖이 {len(out)}건뿐이다 — 검색 범위가 동명동으로 되돌아갔거나 "
        "경계 판정이 죽었다(PLAN #227)")
    assert len(stores) - len(out) > 100, "동명동 안 상가가 너무 적다 — 원천이 비었다"


def test_offices_seen_on_the_map_are_searchable(emd):
    """PLAN #227 도착 ② — 지도 안에 보이는 관공서가 색인에 있는가. **CI 에서 돈다**(발행물만 읽는다).

    ★ 동구청 · 동부소방서는 동명동 **밖**이고 서석초는 **안**이다. 셋이 다 있어야
      「범위가 지도다」가 참이다. 밖의 둘이 빠지면 §183-1 로 되돌아간 것이다.
    """
    civil = {f["properties"]["name"]: f for f in _load(DEST)["features"]
             if (f["properties"].get("src") or "") == "civil"}
    need = {"동구청", "동부소방서", "광주서석초등학교"}
    assert need <= set(civil), f"지도에 보이는데 검색에 없는 관공서 — {sorted(need - set(civil))}"
    assert not emd.covers(_pt(civil["동구청"])) and not emd.covers(_pt(civil["동부소방서"])), (
        "동구청 · 동부소방서가 동명동 안으로 읽힌다 — 경계나 좌표가 틀렸다")
    assert emd.covers(_pt(civil["광주서석초등학교"]))


def test_civil_offices_are_scoped_not_lost(move):
    """관공서 색인 수가 **지도 이동 범위 안 원천 수**와 같은가 — 조인이 흘리거나 넘치지 않았는가.

    ★ 2026-11-14 실측 — `civil_office` 64건 중 지도 이동 범위 안이 **38**이다
      (동명동 안은 2). 「64 중 38」은 관측이고 「흘렸다」는 판정이며, 판정에는
      범위가 필요하다 — §235 가 상가에서 배운 것을 여기에도 건다.
    """
    co = _load(ROOT / "data" / "processed" / "civil_office.geojson")
    inside = [f for f in co["features"] if move.contains(_pt(f))]
    indexed = [f for f in _load(DEST)["features"]
               if (f["properties"].get("src") or "") == "civil"]
    assert len(indexed) == len(inside), (
        f"관공서 색인 {len(indexed)} ≠ 지도 이동 범위 안 {len(inside)} — 조인이 흘렸거나 넘쳤다")
    assert len(inside) > 2, "지도 이동 범위 안 관공서가 동명동 수준이다 — 범위나 원천이 죽었다"


def test_landmarks_are_in_the_index():
    """지점(`web/config.js` landmarks)이 **같은 좌표로** 색인에 있는가 (PLAN #227).

    ★ 정본은 config.js 한 곳이다. 지도는 `navi_graph.json.landmarks` 로, 검색은
      `dest.geojson` 으로 받는다 — 길이 둘이라 한쪽만 다시 발행하면 갈린다. 셋을 댄다.
    """
    from firelane.publish_navi import landmarks
    want = {r["name"]: (round(r["lng"], 6), round(r["lat"], 6)) for r in landmarks()}
    assert "광주 인공지능사관학교" in want, "config.js 에서 그 지점이 사라졌다 — 이 시험의 전제가 깨졌다"
    got = {f["properties"]["name"]: tuple(f["geometry"]["coordinates"][:2])
           for f in _load(DEST)["features"] if (f["properties"].get("src") or "") == "landmark"}
    assert got == want, f"색인의 지점 {got} ≠ config.js {want} — publish 를 다시 돌려라"
    graph = {r["name"]: (round(r["lng"], 6), round(r["lat"], 6))
             for r in _load(ROOT / "web" / "data" / "navi_graph.json").get("landmarks") or []}
    assert graph == want, f"지도의 지점 {graph} ≠ config.js {want}"


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


def test_from_landmarks_carries_name_and_point_and_invents_no_address():
    """지점 → 목적지. 좌표 · 이름은 그대로, 주소는 **지어내지 않는다**(빈 칸) · 화면 설명글 `note` 는 검색어가 아니라 안 싣는다."""
    from firelane.destinations import from_landmarks
    g = from_landmarks([{"name": " 어느 지점 ", "lng": 126.92, "lat": 35.14, "note": "설명"}])
    r = g.iloc[0]
    assert (r["name"], r["cat"], r["src"], r["addr"], r["alt"]) == ("어느 지점", "지점", "landmark", "", "")
    assert (round(r.geometry.x, 2), round(r.geometry.y, 2)) == (126.92, 35.14) and "note" not in g.columns
    assert not len(from_landmarks([])), "지점이 없는데 행이 섰다"
