#!/usr/bin/env python3
"""
test_mutate_scope_set.py — 돌연변이 장부가 과녁 전부를 들고 있는가.  (PLAN #259)

── 무엇을 보는가 ───────────────────────────────────────────────
과녁 목록(`mutatescope.targets()`)의 집합과 장부(`data/golden/mutation.json`)에
든 도구의 집합이 **같다.** 지문은 장부에 이미 있는 행만 비교하므로, 새 과녁이
생겨도 장부에 행이 없으면 아무도 울지 않았다 — 그 구멍을 여기서 막는다.

★ 지문의 해시 입력은 넓히지 않았다. 넓히면 모든 행의 지문이 달라져 장부가
  낡고, 장부를 다시 쓰는 일은 사람 몫이다. 그래서 지문 밖의 별도 시험으로 건다.
★ 이 파일은 과녁 도구의 이름을 낱말로 적지 않는다 — 적으면 그 도구의 지문이
  이 파일을 해시해 장부가 낡는다.

밖    장부 값(생존 수 등)이 옳은지는 안 본다. 낡음은 지문이 따로 잡는다.
"""
from __future__ import annotations

import json
from pathlib import Path

import mutatescope as MS

ROOT = Path(__file__).resolve().parents[1]


def _gap(want: set[str], held: set[str]) -> list[str]:
    """어긋난 이름. 같으면 빈 목록이고 이 값이 「조용하다」다."""
    return sorted(want - held) + sorted(held - want)


def _diff(want: set[str], held: set[str]) -> str:
    return f"과녁인데 장부에 없다 {sorted(want - held)} · 장부에만 있다 {sorted(held - want)}"


def _held(path: Path) -> set[str]:
    return {r["도구"] for r in json.loads(path.read_text(encoding="utf-8"))["도구별"]}


def test_the_ledger_holds_exactly_the_targets():
    want, held = set(MS.targets()), _held(ROOT / "data/golden/mutation.json")
    print(f"과녁 {len(want)} · 장부 {len(held)}")
    assert not _gap(want, held), _diff(want, held)


def test_a_missing_or_extra_row_is_caught(tmp_path, monkeypatch):
    """음성 — 임시 과녁 하나가 장부에 없거나, 장부에만 남은 행이 있으면 같음 검사가 운다."""
    real = _held(ROOT / "data/golden/mutation.json")
    ledger = tmp_path / "mutation.json"
    ledger.write_text(json.dumps({"도구별": [{"도구": n} for n in sorted(real)]}), encoding="utf-8")
    monkeypatch.setattr(MS, "targets", lambda: sorted(real | {"a_new_target"}))
    assert not _gap(real, _held(ledger)), "정상 입력에서 울었다 — 장부와 같은 집합인데 어긋났다고 했다"
    assert _gap(set(MS.targets()), _held(ledger)) == ["a_new_target"], "새 과녁이 장부에 없는데 같다고 했다"
    assert "a_new_target" in _diff(set(MS.targets()), _held(ledger))
    monkeypatch.setattr(MS, "targets", lambda: sorted(real - {sorted(real)[0]}))
    assert _gap(set(MS.targets()), _held(ledger)) == [sorted(real)[0]], "장부에만 남은 행을 같다고 했다"
    assert sorted(real)[0] in _diff(set(MS.targets()), _held(ledger))
