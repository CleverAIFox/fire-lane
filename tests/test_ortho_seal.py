#!/usr/bin/env python3
"""
test_ortho_seal.py — ortho 단계가 **봉인지를 보고 건너뛰는가.**  (DECISIONS §223-1)

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-23. `ortho` 는 매 실행 `web/data/ortho` 를 통째로 지우고 타일 1,423장을
처음부터 구웠다. 원본 TIF 넉 장(1.25GB)과 스코프가 한 바이트도 안 바뀌어도 그랬다.
같은 날 실측 편차가 **34초 ~ 28분(50배)** 이었고, 그 28분이 재잠금 배치마다 붙었다.

ingest 는 이미 샤드 봉인지로 같은 문제를 풀었다(§164 · §165). 단위만 다르다 —
거기는 소스 하나, 여기는 이 단계 전체다.

★ **모르면 안 건너뛴다.** 넷(raw · scope · code · out) 중 하나라도 다르거나 없으면
  다시 굽는다. 특히 `out` 은 「봉인지는 같은데 타일이 지워진」 경우를 막는다 —
  그때 건너뛰면 배경이 통째로 빈 채 성공으로 보인다(1족).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    from firelane import ortho
    return ortho


def test_seal_has_four_slots():
    """봉인지는 넉 장이다 — raw · scope · code · out."""
    src = (ROOT / "src" / "firelane" / "ortho.py").read_text(encoding="utf-8")
    for slot in ('"raw"', '"scope"', '"code"', '"out"'):
        assert slot in src, f"봉인지 칸 {slot} 이 없다"
    assert "_tiles_print" in src, "산출물 지문을 안 잰다 — 지워진 타일을 재사용한다"
    assert 'code_print("firelane.ortho")' in src, "코드 닫힘을 안 잰다"


def test_tiles_print_is_none_without_tiles(tmp_path):
    """타일이 없으면 지문이 없다 — 없으면 건너뛰지 않는다."""
    o = _mod()
    assert o._tiles_print(tmp_path / "없다") is None
    empty = tmp_path / "ortho"
    empty.mkdir()
    assert o._tiles_print(empty) is None, "빈 디렉터리를 「있다」로 읽으면 빈 배경이 통과한다"


def test_tiles_print_changes_with_content(tmp_path):
    """타일 하나가 바뀌면 지문이 바뀐다 — 빈 그물이 아니다."""
    o = _mod()
    d = tmp_path / "ortho" / "15" / "1"
    d.mkdir(parents=True)
    (d / "2.jpg").write_bytes(b"a")
    a = o._tiles_print(tmp_path / "ortho")
    (d / "2.jpg").write_bytes(b"b")
    b = o._tiles_print(tmp_path / "ortho")
    assert a and b and a != b, "내용이 바뀌었는데 지문이 같다"
    (d / "3.jpg").write_bytes(b"b")
    c = o._tiles_print(tmp_path / "ortho")
    assert c != b and c.startswith("2:"), "장수가 지문에 안 들어간다"


def test_skip_needs_every_slot_to_match():
    """**넷이 전부 같을 때만** 건너뛴다 — 코드가 그렇게 적혀 있는가."""
    src = (ROOT / "src" / "firelane" / "ortho.py").read_text(encoding="utf-8")
    i = src.index("if prev and out_now")
    blk = src[i:i + 400]
    assert "all(prev.get(k) == v for k, v in seal.items())" in blk, "칸 하나라도 다르면 멈추는 조건이 아니다"
    assert 'prev.get("out") == out_now' in blk, "산출물 지문을 조건에서 뺐다"
    assert "SKIP" in blk, "건너뛴 것을 화면에 안 적는다 — 조용한 생략이다"


def test_seal_does_not_enter_the_judgment_closure():
    """ortho 는 판정 지문 밖이다 — 이 배선이 golden 을 건드리면 안 된다."""
    from firelane.shardseal import code_closure
    seg = {p.name for p in code_closure("firelane.segments")}
    assert "ortho.py" not in seg, "ortho 가 판정 닫힘 안에 들어왔다 — 배경 타일이 판정을 흔든다"
    ing = {p.name for p in code_closure("firelane.ingest")}
    assert "ortho.py" not in ing, "ortho 가 ingest 닫힘 안이면 샤드 45종이 매번 찢어진다"


def test_hashlib_is_used_not_a_weak_digest():
    """지문은 sha256 이다 — 짧은 해시로 충돌을 만들지 않는다."""
    o = _mod()
    assert hashlib.sha256 is not None
    src = (ROOT / "src" / "firelane" / "ortho.py").read_text(encoding="utf-8")
    assert "hashlib.sha256()" in src and "md5" not in src
    assert o is not None


# ── 도엽 원점 — 시험이 이름을 안 부르고 있었다 (DECISIONS §493) ───
# ★ `sheet_origin_5186` 은 정사영상 넉 장(1.25GB)이 **지도 위 어디에 놓이는가**를
#   혼자 정한다. 틀리면 배경이 통째로 몇십 m 밀리고, 타일은 정상으로 보인다 —
#   배경이 밀렸다는 것은 **다른 레이어와 겹쳐 봐야** 보이고 그것은 사람 눈이다.
#   §473 이 상수에서 당한 그 꼴이라 자를 밖에서 댄다.
def _sheet_bounds(key: str):
    """도엽 bbox 를 5186 으로 옮긴 경계. **함수가 쓰는 것과 같은 길로** 낸다."""
    import geopandas as gpd

    o = _mod()
    b = o.SHEET_5179[key]
    return gpd.GeoSeries.from_wkt(
        [f"POLYGON(({b[0]} {b[1]},{b[2]} {b[1]},{b[2]} {b[3]},"
         f"{b[0]} {b[3]},{b[0]} {b[1]}))"],
        crs=5179).to_crs(o.ORTHO_CRS).total_bounds


def test_the_pixel_is_gsd_and_the_image_is_north_up():
    """화소 크기가 `GSD` 이고 **y 가 음수**다 — 양수면 영상이 뒤집힌다."""
    o = _mod()
    a = o.sheet_origin_5186(sorted(o.SHEET_5179)[0], 9232, 11194)
    assert a.a == o.GSD and a.e == -o.GSD, f"{a.a} · {a.e}"
    assert a.b == 0 and a.d == 0, "회전·전단이 들어갔다"


def test_the_image_centre_is_the_sheet_centre():
    """★ 본체. 영상이 도엽보다 커도 **가운데가 같다** — 그것이 '사방으로 민다'다.

    수를 손으로 적지 않는다. 도엽 경계에서 **유도한다** — 적으면 그 수가
    둘째 정의가 되고, 둘이면 어긋난다(§18-3).
    """
    o = _mod()
    bad = []
    for key in sorted(o.SHEET_5179):
        box = _sheet_bounds(key)
        for w, h in ((9232, 11194), (14000, 14000), (9232, 14000)):
            a = o.sheet_origin_5186(key, w, h)
            cx = a.c + w * o.GSD / 2
            cy = a.f - h * o.GSD / 2
            if abs(cx - (box[0] + box[2]) / 2) > 1e-6 or \
                    abs(cy - (box[1] + box[3]) / 2) > 1e-6:
                bad.append(f"{key} {w}x{h}: 중심 ({cx:.3f}, {cy:.3f}) ≠ "
                           f"({(box[0]+box[2])/2:.3f}, {(box[1]+box[3])/2:.3f})")
    assert not bad, "영상 중심이 도엽 중심과 다르다 — 배경이 그만큼 밀린다\n  " \
        + "\n  ".join(bad)


def test_an_image_exactly_the_sheet_size_gets_no_padding():
    """도엽 크기만큼이면 여백이 **0** 이다 — 좌상단이 도엽 경계 그대로다."""
    o = _mod()
    key = sorted(o.SHEET_5179)[0]
    box = _sheet_bounds(key)
    w = round((box[2] - box[0]) / o.GSD)
    h = round((box[3] - box[1]) / o.GSD)
    a = o.sheet_origin_5186(key, w, h)
    assert abs(a.c - box[0]) < o.GSD, f"{a.c} ≠ {box[0]}"
    assert abs(a.f - box[3]) < o.GSD, f"{a.f} ≠ {box[3]}"


def test_a_bigger_image_pushes_the_origin_outward_by_half_the_surplus():
    """★ 여백이 **절반**인가. 전부를 한쪽에 주면 영상이 도엽 크기만큼 밀린다."""
    o = _mod()
    key = sorted(o.SHEET_5179)[0]
    a = o.sheet_origin_5186(key, 9232, 11194)
    b = o.sheet_origin_5186(key, 9232 + 800, 11194 + 800)
    assert abs((a.c - b.c) - 800 * o.GSD / 2) < 1e-9, "x 여백이 절반이 아니다"
    assert abs((b.f - a.f) - 800 * o.GSD / 2) < 1e-9, "y 여백이 절반이 아니다"


def test_an_unknown_sheet_is_refused_not_guessed():
    """★ 모르는 도엽에 **원점을 지어주지 않는다.**"""
    import pytest

    o = _mod()
    with pytest.raises(KeyError):
        o.sheet_origin_5186("999", 100, 100)
