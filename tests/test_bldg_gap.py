"""
test_bldg_gap.py — 동명동의 빠진 건물 면을 뽑는 **추출 절차**(`firelane.bldg_gap`).  (PLAN #232 ④ · DECISIONS §776)

── 이 시험이 무는 것 ──────────────────────────────────────────
① 합성 입력에서 규칙 다섯이 선다 — 동 밖은 빠진다(대표점) · 덮인 몫 10% 가 문턱이다(9% 는 남고 50% 는 빠진다) · 층수는 비었거나 0 이면 1 ·
   칸은 `flo` 하나 · 경위도.
② **제 산출물이 제 입력을 덮지 않는다** — 발행 건물 중 번호 ≥ `GAP_ID0`(이 추출이 발행에 얹은 면)은 「덮는 건물」로 안 센다. 안 빼면 두 번째 실행이 0면이다.
③ 쓴 파일이 **커밋된 파일과 같은 꼴**이다 — 머리(`name` · `crs` · 좌표 해상도) · 칸 · 도형 갈래 · 좌표 6자리.
④ 조용히 덜 하지 않는다 — 층수 칸이 없거나 좌표계가 경위도면 죽는다 · 다른 판(sha)은 안 읽는다.
⑤ 대장이 이 절차를 말한다 — 원천 항목(`pending` 또는 `datasets` 한 곳)이 산출물 경로 · 만드는 자 · 읽는 자 · 원본명 · 정규 이름 · sha 가 코드의 상수와 같고 칸 뜻 표가 29칸 전부를 든다.

IN    합성 도형(시험 안에서 만든다) · `sources.yaml` · `data/extra/bldg_gap_dongmyeong.geojson`(커밋본 — 꼴만 읽는다)
OUT   없음(`tmp_path` 에만 쓴다)
PARAM 없음
밖    **실물(레이크의 291MB zip)로는 여기서 안 돌린다** — 한 번에 25초라 시험에 안 싣는다. 그 대조는 `uv run python -m firelane.bldg_gap` 이 한다
      (2026-11-14 실측: 323면 · 커밋본과 바이트 동일). 발행이 이 파일을 어떻게 거르는지(274면)는 `publish_web` 의 일이다.
"""
from __future__ import annotations

import json
import re

import geopandas as gpd
import pytest
from shapely.geometry import box

from firelane import bldg_gap, ledger, naming
from firelane.paths import ROOT
from firelane.publish_web import GAP_BUILDINGS, GAP_ID0, drop_gap

CRS = 5186
X0, Y0 = 192_000.0, 283_000.0          # 동명동 근처의 미터 좌표(값 자체는 뜻이 없다)


def _sq(x: float, y: float, s: float = 10.0):
    return box(X0 + x, Y0 + y, X0 + x + s, Y0 + y + s)


DONG = box(X0, Y0, X0 + 100, Y0 + 100)
#: 이름 → (도형, 층수 칸 값). 발행 건물은 `PUB` 가 든다.
AL = {
    "빈자리·층수빔": (_sq(10, 10), None),
    "빈자리·층수0": (_sq(30, 10), 0.0),
    "9%덮임·6층":   (_sq(50, 10), 6.0),
    "50%덮임":      (_sq(70, 10), 3.0),
    "동밖":         (_sq(200, 10), 2.0),
    "제산출물만덮음": (_sq(10, 50), 2.0),
}
PUB = [
    (20, box(X0 + 50, Y0 + 10, X0 + 50.9, Y0 + 20)),      # 10㎡ 중 0.9 × 10 = 9㎡ → 9%
    (21, box(X0 + 70, Y0 + 10, X0 + 75, Y0 + 20)),        # 50%
    (GAP_ID0 + 3, _sq(10, 50)),                           # 지난 실행이 발행에 얹은 면 — 덮는 건물이 아니다
    (22, _sq(400, 400)),                                  # 아무것도 안 덮는 먼 건물
]


def _al(drop: str | None = None) -> gpd.GeoDataFrame:
    g = gpd.GeoDataFrame({"A26": [v for _, v in AL.values()], "nm": list(AL)}, geometry=[s for s, _ in AL.values()], crs=CRS)
    return g.drop(columns=drop) if drop else g


def _pub() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"BUL_MAN_NO": [n for n, _ in PUB]}, geometry=[s for _, s in PUB], crs=CRS).to_crs(4326)


def _names(out: gpd.GeoDataFrame) -> list[str]:
    al = _al()
    return [al.nm[i] for i in out.index]


def test_rules_on_synthetic_faces():
    out = bldg_gap.pick(_al(), DONG, _pub())
    assert _names(out) == ["빈자리·층수빔", "빈자리·층수0", "9%덮임·6층", "제산출물만덮음"], "동 밖 · 절반 덮인 면만 빠져야 한다"
    assert out.flo.tolist() == [1, 1, 6, 2], "층수는 비었거나 0 이면 1 이고 나머지는 그대로다"
    assert list(out.columns) == ["flo", "geometry"] and str(out.flo.dtype).startswith("int"), "칸은 정수 `flo` 하나다"
    assert out.crs.to_epsg() == 4326 and out.geometry.geom_type.eq("Polygon").all()


def test_own_output_in_published_set_does_not_hide_the_face():
    """②. 번호 ≥ GAP_ID0 를 「덮는 건물」로 세면 그 면이 사라진다 — 같은 건물을 낮은 번호로 바꿔 그 차이를 보인다."""
    pub = _pub()
    assert "제산출물만덮음" in _names(bldg_gap.pick(_al(), DONG, pub))
    pub.loc[pub.BUL_MAN_NO == GAP_ID0 + 3, "BUL_MAN_NO"] = 23
    assert "제산출물만덮음" not in _names(bldg_gap.pick(_al(), DONG, pub)), "진짜 발행 건물이 덮으면 빠져야 한다 — 문턱이 살아 있다"


def test_cover_threshold_is_the_declared_one(monkeypatch):
    """문턱을 움직이면 답이 움직인다 — 9% 면이 문턱 바로 아래에 있다."""
    monkeypatch.setattr(bldg_gap, "COVER_MAX", 0.05)
    assert "9%덮임·6층" not in _names(bldg_gap.pick(_al(), DONG, _pub()))


def test_written_file_has_the_committed_shape(tmp_path):
    p = tmp_path / GAP_BUILDINGS.name
    bldg_gap.write(bldg_gap.pick(_al(), DONG, _pub()), p)
    new = json.loads(p.read_text(encoding="utf-8"))
    old = json.loads(GAP_BUILDINGS.read_text(encoding="utf-8"))
    head = lambda d: {k: v for k, v in d.items() if k != "features"}  # noqa: E731  한 줄 투영 — 이름 붙일 값이 아니다
    assert head(new) == head(old), "머리(`name` · `crs` · 좌표 해상도)가 커밋본과 같아야 한다"
    for d in (new, old):
        assert {tuple(f["properties"]) for f in d["features"]} == {("flo",)}
        assert {f["geometry"]["type"] for f in d["features"]} == {"Polygon"}
        assert all(isinstance(f["properties"]["flo"], int) and f["properties"]["flo"] >= 1 for f in d["features"])
        assert all(len(repr(c).partition(".")[2]) <= 6 for f in d["features"] for ring in f["geometry"]["coordinates"] for xy in ring for c in xy)
    assert len(old["features"]) == 323, "커밋본은 323면이다(274 는 발행이 더 거른 수 — DECISIONS §776)"


def test_does_not_quietly_do_less(tmp_path):
    with pytest.raises(ValueError, match="A26"):
        bldg_gap.pick(_al(drop="A26"), DONG, _pub())
    with pytest.raises(ValueError, match="BUL_MAN_NO"):
        bldg_gap.pick(_al(), DONG, _pub().drop(columns="BUL_MAN_NO"))
    with pytest.raises(ValueError, match="미터"):
        bldg_gap.pick(_al().to_crs(4326), DONG, _pub())
    other = tmp_path / "AL_D010_other.zip"
    other.write_bytes(b"not the vintage this recipe knows")
    with pytest.raises(SystemExit, match="다른 판"):
        bldg_gap.source(other)


def test_ledger_declares_the_recipe():
    led = ledger.load()
    assert naming.check(bldg_gap.CANON.rsplit("/", 1)[-1])[0], "정규 이름이 명명 규칙을 지나야 사람이 그 이름으로 옮길 수 있다"
    # 원천은 `pending`(사람이 이름을 옮기기 전) 또는 `datasets`(옮긴 뒤) 중 **정확히 한 곳**에 있다 — 둘 다거나 어디에도 없으면 대장이 낡았다
    pend = [x for x in led.get("pending") or [] if x.get("key") == bldg_gap.KEY]
    live = (led.get("datasets") or {}).get(bldg_gap.KEY)
    assert (len(pend) == 1) != bool(live), "원천 항목이 pending · datasets 중 한 곳에만 있어야 한다"
    text = " ".join(str(v) for v in (live or pend[0]).values())
    made = str(GAP_BUILDINGS.relative_to(ROOT))
    for must in (bldg_gap.SRC_SHA256, bldg_gap.INNER, bldg_gap.ORIGIN.rsplit("/", 1)[-1], bldg_gap.CANON, made, "src/firelane/bldg_gap.py", "src/firelane/publish_web.py"):
        assert must in text, f"대장과 코드가 같은 것을 가리켜야 한다 — `{must}` 가 대장 항목에 없다"
    missing = [f"A{i}" for i in range(29) if not re.search(rf"^\s*A{i}\s", text, re.M)]
    assert not missing, f"칸 뜻 표에 빠진 칸 — {missing}"
    assert text.count("**확인**") == 5 and text.count("값으로 추정") >= 24, "확인 다섯(A4 · A5 · A9 · A12 · A26) · 나머지는 추정이라고 적는다"


def test_drop_gap_removes_only_the_faces_the_publisher_appended_and_cries_without_the_column():
    """발행에 얹힌 면(번호 ≥ `GAP_ID0`)을 가르는 것은 그 번호를 만드는 `publish_web.drop_gap` 하나다 — 추출 쪽은 그 칸을 직접 안 읽는다(DECISIONS §320)."""
    pub = _pub()
    kept = drop_gap(pub)
    assert len(kept) == len(pub) - 1 and (kept.BUL_MAN_NO < GAP_ID0).all()
    assert not len(drop_gap(pub[pub.BUL_MAN_NO >= GAP_ID0])), "얹힌 면만 있는데 남았다"
    with pytest.raises(ValueError, match="BUL_MAN_NO"):
        drop_gap(pub.drop(columns="BUL_MAN_NO"))
