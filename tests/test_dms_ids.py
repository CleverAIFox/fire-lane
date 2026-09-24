"""
test_dms_ids.py — `dms` 절 ID 는 제목 경로다. 절을 끼워도 남의 ID 가 안 밀린다.

2026-09-22 (PLAN §13 W3-5 닫힘 · DECISIONS §217-5). 종전 ID 는 문서 안 순번
(`MASTER-082`)이었고, `MASTER` 중간에 절 하나를 끼우면 뒤 70절이 `delta` 에서
「변경」으로 떴다. 내용은 한 바이트도 안 바뀌었는데 사람이 70절을 다시 봐야 했다.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dms():
    spec = importlib.util.spec_from_file_location("_dms_ids", ROOT / "tools" / "dms.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def test_ids_unique_and_titled():
    d = _dms()
    ids = [s["id"] for rel in d.DOCS for s in d.sections(rel)]
    assert len(ids) == len(set(ids)), "절 ID 가 겹친다"
    dup = [i for i in ids if "~" in i]
    assert not dup, f"제목 경로가 겹쳐 `~N` 이 붙었다 — 제목을 가른다: {dup[:5]}"
    assert "MASTER/12-8" in ids, "W3-5 가 약속한 표기 `MASTER/12-8` 이 안 나온다"


def test_insert_does_not_shift_others(tmp_path, monkeypatch):
    d = _dms()
    rel = "docs/MASTER.md"
    before = [s["id"] for s in d.sections(rel)]
    src = (ROOT / rel).read_text(encoding="utf-8")
    i = src.index("\n## ", len(src) // 2)
    fake = tmp_path / "docs" / "MASTER.md"
    fake.parent.mkdir()
    fake.write_text(src[:i] + "\n## 끼운 절 — 시험용\n\n본문\n" + src[i:], encoding="utf-8")
    monkeypatch.setattr(d, "ROOT", tmp_path)
    after = [s["id"] for s in d.sections(rel)]
    assert set(after) - set(before) == {"MASTER/끼운_절_시험용"}
    assert set(before) <= set(after), "절 하나를 끼웠더니 남의 ID 가 바뀌었다"


def test_bookmark_and_seal_use_current_ids():
    d = _dms()
    ids = {s["id"] for rel in d.DOCS for s in d.sections(rel)}
    bm = json.loads((ROOT / "data" / "dms" / "BOOKMARK.json").read_text(encoding="utf-8"))
    gone = [k for k in bm["done"] if k not in ids]
    assert not gone, f"북마크가 없는 절을 든다: {gone[:5]}"
    seal = json.loads((ROOT / "data" / "dms" / "SEAL.json").read_text(encoding="utf-8"))
    legacy = [k for k in seal["sections"] if "/" not in k]
    assert not legacy, f"봉인이 옛 순번 ID 를 든다: {legacy[:5]}"


# ── 분모 둘을 0 에 박는다 ────────────────────────────────────────
#
# ★ 2026-09-24 (DECISIONS §241). `blank`(칸 없음)는 2026-09-24 에 0 이 됐고,
#   물림 침묵(부모가 덮는다고 **안 적은** 하위 절)도 같은 날 0 이 됐다.
#   0 은 **지키지 않으면 다시 자란다** — 새 절을 적는 사람은 칸을 잊고,
#   새 하위 절을 적는 사람은 부모의 수를 안 고친다.
#   래칫으로 박는다. 이 저장소가 `deadcheck` · `sizecheck` 에 쓰는 규율과 같다.
def test_no_section_is_without_a_field():
    """분모(blank) = 0. 칸도 부모 칸도 없는 절이 있으면 운다."""
    m = _dms()
    data = m.scan()
    assert len(data["rows"]) > 500, f"절을 {len(data['rows'])}개밖에 못 셌다 — 수집기가 죽었다"
    bad = [f"  {r['doc']}:{r['line']}  {r['id']}  {r['title'][:50]}"
           for r in data["rows"] if r["state"] == "blank"]
    assert not bad, (
        f"강제자 칸이 없는 절 {len(bad)}개\n" + "\n".join(bad[:20]) + "\n\n"
        "  절마다 줄머리에 `강제자  …` 한 줄을 적는다. 없으면\n"
        "  `강제자 없음 — 사유: …` 로 **없다는 것을 적는다.**")


def test_every_inherited_section_is_declared_with_a_count():
    """물림 침묵 = 0. 그리고 선언한 **수**가 실제와 같은가.

    ★ 두 갈래를 같이 문다. 선언만 있고 수가 없으면 하위 절이 늘어도 조용하고,
      수가 있으면 늘 때 어긋나서 운다 — 그때 사람이 **그 새 절을 실제로 본다.**
    """
    m = _dms()
    data = m.scan()
    said, mute = m.inherit_split(data)
    assert said, "물림 선언이 0 이다 — 판정기가 죽었거나 문서가 비었다"
    assert not mute, (
        f"부모가 덮는다고 안 적은 하위 절 {len(mute)}개\n"
        + "\n".join(f"  {i}" for i in mute[:20]) + "\n\n"
        "  부모 칸 끝에 「하위 N이 이 칸을 물려받는다」를 적거나,\n"
        "  부모가 안 덮는 자식이면 그 자식에 제 칸을 적어라.")
    bad = m.inherit_counts(data)
    assert not bad, "물림 선언이 적은 수가 실제와 다르다:\n" + "\n".join(bad)


def test_the_inherit_count_judge_bites():
    """★ 빈 그물인가 — 실물이 0 이므로 **합성 데이터**로 확인한다(§230)."""
    m = _dms()
    synth = {"rows": [
        {"id": "D/9", "doc": "d.md", "at": 1, "state": "wired",
         "field": "강제자 `tests/test_x.py`. 하위 셋이 이 칸을 물려받는다"},
        {"id": "D/9-1", "doc": "d.md", "at": 2, "state": "inherit", "field": ""},
        {"id": "D/9-2", "doc": "d.md", "at": 3, "state": "inherit", "field": ""},
    ]}
    assert m.inherit_counts(synth), "선언 3 · 실제 2 를 안 잡는다"
    synth["rows"][0]["field"] = "강제자 `tests/test_x.py`. 하위 둘이 이 칸을 물려받는다"
    assert not m.inherit_counts(synth), "맞는 수를 어긋남으로 잡는다"
    # 수를 **안 적은** 선언은 세지 않는다 — 첫날부터 시끄러우면 검사가 꺼진다
    synth["rows"][0]["field"] = "강제자 `tests/test_x.py`. 하위 절이 이 칸을 물려받는다"
    assert not m.inherit_counts(synth), "수 없는 옛 표기까지 잡는다"


def test_a_multiline_field_is_read_whole():
    """칸은 여러 줄에 걸친다(실측 113곳). 첫 줄만 보면 뒷줄이 안 보인다."""
    m = _dms()
    sec = {"line": 0, "body": [(1, "강제자  `tests/test_a.py` ·"),
                               (2, "`tests/test_b.py`. 하위 둘이 이 칸을 물려받는다"),
                               (3, ""),
                               (4, "이 문단은 칸이 아니다")]}
    state, field, _ = m.classify(sec)
    assert state == "wired"
    assert "test_b" in field, "이어지는 줄을 안 본다 — 범위가 이름보다 좁다"
    assert m._said_count(field) == 2, "뒷줄의 물림 수를 못 읽는다"
    assert "이 문단은" not in field, "빈 줄 뒤까지 칸으로 먹는다"
