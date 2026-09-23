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
