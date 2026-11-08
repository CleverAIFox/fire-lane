"""`lakecheck L5`(norm 의 상류) 가 **상류를 무엇으로 대는지** 잰다.  (#197)

★ 왜 이 파일이 있나 (2026-11-07). L5 는 norm 파일명 앞 14자로 시작하는 raw 가
  **하나라도** 있으면 그 norm 을 통과시켰다. 같은 데이터셋의 형제 raw 한 장이면
  짝 없는 norm 이 전부 가려진다 — **초록인데 틀린 이유로 초록**이었다.
  지금은 `_prep.json` 의 raw 경로 키(`dst` 가 이 norm)로 대고, raw 가 레이크에
  있어야 상류로 친다. 주인 판정은 `lake.norm_owners` 가 정본이다.

★ 양성 대조가 이 파일의 핵심이다 — 「형제 raw 가 있어도 짝 없는 norm 은 잡힌다」.
  없으면 이 시험은 옛 구현에서도 초록이다.

IN    tools/lakecheck.py::l5 · firelane.lake.norm_owners
OUT   없음
밖    **실물 레이크는 안 본다.** 레이크(`FIRE_LANE_DATA`)가 있어야 도는 실물 검사는
      `uv run python tools/lakecheck.py` 이고, 없는 기계에서는 그 도구가
      「못 쟀다」로 멈춘다. 여기는 합성 레이크로 판별식만 민다.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

from firelane import lake

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "lakecheck.py"

OLD = "nfa/nfa_dispatch_119_jngj-dongmyeong_20260903.csv"   # 짝 없는 norm
NEW = "nfa/nfa_dispatch_119_jngj-dongmyeong_20261104.csv"   # 짝 있는 norm
SIB = "nfa/nfa_dispatch_119_jngj_20250101.csv"              # 형제 raw


@pytest.fixture
def lc():
    spec = importlib.util.spec_from_file_location("lakecheck_l5t", SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    m.HITS.clear()
    return m


def _put(base: pathlib.Path, layer: str, *rels: str) -> None:
    for r in rels:
        f = base / layer / r
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")


def _prep(**pairs: str) -> dict:
    """raw 키 → dst. `dst` 가 키와 같으면 적지 않는다(실물 꼴)."""
    return {"files": {k.replace("__", "/"): ({"dst": v} if v else {})
                      for k, v in pairs.items()}}


def _run(lc, tmp, prep) -> list[str]:
    lc.HITS.clear()
    lc.l5(tmp, {}, prep)
    return [h["what"] for h in lc.HITS]


def test_a_sibling_raw_does_not_hide_an_unpaired_norm(lc, tmp_path):
    """★ 양성 대조. 형제 raw 가 있고 prep 항목은 raw 가 **없는** 짝을 가리킨다."""
    _put(tmp_path, "raw", NEW, SIB)
    _put(tmp_path, "norm", OLD, NEW)
    prep = {"files": {OLD: {}, NEW: {}}}      # OLD 의 raw 는 레이크에 없다
    got = _run(lc, tmp_path, prep)
    assert len(got) == 1 and "20260903" in got[0], got


def test_the_old_prefix_rule_would_have_passed_it(tmp_path):
    """이 합성 레이크가 **옛 구현에서는 초록**이었음을 못박는다 — 대조가 비지 않게."""
    _put(tmp_path, "raw", NEW, SIB)
    raw_stems = [p.stem for p in (tmp_path / "raw").rglob("*") if p.is_file()]
    key = "_".join(pathlib.Path(OLD).stem.split("_")[:3])
    assert any(r.startswith(key[:14]) for r in raw_stems)


def test_a_paired_norm_is_not_flagged(lc, tmp_path):
    _put(tmp_path, "raw", NEW)
    _put(tmp_path, "norm", NEW)
    assert _run(lc, tmp_path, {"files": {NEW: {}}}) == []


def test_a_paired_norm_through_dst_is_not_flagged(lc, tmp_path):
    """변환기가 확장자를 바꾸면 norm 은 `dst` 에 있다 — 키만 보면 거짓 양성이 난다."""
    _put(tmp_path, "raw", "safety/card.pdf")
    _put(tmp_path, "norm", "safety/card.csv")
    assert _run(lc, tmp_path, {"files": {"safety/card.pdf": {"dst": "safety/card.csv"}}}) == []


def test_a_norm_with_no_prep_entry_is_flagged(lc, tmp_path):
    _put(tmp_path, "raw", NEW, SIB)
    _put(tmp_path, "norm", NEW, "nfa/nfa_dispatch_119_jngj_99999999.csv")
    got = _run(lc, tmp_path, {"files": {NEW: {}}})
    assert len(got) == 1 and "99999999" in got[0], got


def test_an_empty_prep_flags_every_norm(lc, tmp_path):
    _put(tmp_path, "raw", NEW)
    _put(tmp_path, "norm", NEW)
    assert len(_run(lc, tmp_path, {})) == 1


def test_the_ownership_verdict_is_lakes_not_a_copy(lc):
    """`resolve` 와 L5 는 같은 `norm_owners` 를 읽는다 — 사본이 생기면 갈린다."""
    body = SRC.read_text(encoding="utf-8")
    assert "_lake.norm_owners" in body
    assert 'get("dst")' not in body, "L5 가 dst 를 직접 읽는다 — 사본이다"
    assert lake.norm_owners({"files": {"a/b.pdf": {"dst": "a/b.csv"}, "c/d.csv": {}}}) == {
        "a/b.csv": ["a/b.pdf"], "c/d.csv": ["c/d.csv"]}


def test_load_prep_reads_the_committed_state_and_owners_cover_every_entry():
    """`lake.load_prep` 를 **이름으로** 부른다 — L5 가 실물에서 읽는 자리다.
    실물 `_prep.json` 의 모든 항목이 주인 표에 들어간다(`dst` 가 있으면 그쪽 이름으로)."""
    prep = lake.load_prep()
    assert prep.get("files"), "_prep.json 이 비었다 — 이 검사가 빈 그물이 됐다"
    owners = lake.norm_owners(prep)
    assert sum(len(v) for v in owners.values()) == len(prep["files"])
