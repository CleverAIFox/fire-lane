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
