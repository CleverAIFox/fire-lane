"""`landing/_hold` 의 전국본은 주인이 있다 — **대장이 이름으로 선언한 입력만.**  (DECISIONS §647 · 2026-11-07)

§647 은 「전국본을 raw 에 안 올리고 `_hold` 에서 제자리로 읽는다」를 설계로 정했는데 `lake` · `ledger_schema` · `contract` 가 그 층을 몰라
관문이 주인없음 29 · 결손 29 · 스키마 「실물 없음」 5 를 냈다. 선언과 도구가 갈려 있었다.

★ **양성 대조가 이 시험의 본체다.** 푸는 쪽만 보면 `_hold` 의 모든 파일을 풀어 주는 구현도 초록이다 —
  이름이 선언 밖이면 · 선언이 `status: missing` + 추출이 아니면 · `_hold` 가 아닌 자리에 있으면 **여전히 주인없음**이어야 한다.

  밖    `_hold` 파일의 **내용**이 대장 계약과 맞는지는 안 본다 — 주인이 있는지와 이름이 선언과 맞는지뿐이다(읽어 거르는 쪽은 `ingest --extract-from`)
"""
from __future__ import annotations

from pathlib import Path

from firelane import contract, lake, paths
from firelane.extract_decl import held, held_names, hold_hits

NAME = "nfa_x_kr_20221231.csv"
HELD = {"stem": "nfa_x", "kind": "csv_table", "status": "missing", "missing_why": "전국본을 쥐지 않는다",
        "files": [f"nfa/{NAME}", "nfa/nfa_x_kr_20231231.csv"],
        "contract": {"normalize_columns": "upper_strip", "filter": [{"column": "A", "equals": "b"}]}}


def _lake(tmp: Path, files: list[str]) -> Path:
    for rel in files:
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    return tmp


def _by(y: dict, root: Path) -> dict[str, lake.Row]:
    return {r.rel: r for r in lake.resolve(y, root)}


def test_declared_hold_inputs_have_an_owner_and_are_not_missing(tmp_path):
    """선언한 이름이 `_hold` 에 있으면 주인이 있고, 같은 이름이 raw 에 없다고 결손으로 세지 않는다."""
    y = {"datasets": {"nfa_x": HELD}}
    root = _lake(tmp_path, [f"landing/_hold/{NAME}"])
    rows = lake.resolve(y, root)
    row = {r.rel: r for r in rows}[f"landing/_hold/{NAME}"]
    assert (row.state, row.owners) == ("정상", ("datasets:nfa_x",)), row
    miss = [r.rel for r in rows if r.state == "결손"]
    assert miss == ["?/nfa/nfa_x_kr_20231231.csv"], f"`_hold` 에 있는 것만 결손에서 빠진다 — {miss}"
    assert lake.gate(y, rows) == []


def test_hold_is_not_a_door_for_any_name(tmp_path):
    """양성 대조 — 아무 이름이나 `_hold` 에 넣으면 **여전히 주인없음**이다(관문이 닫힌다)."""
    held_y = {"datasets": {"nfa_x": HELD}}
    live = dict(HELD, status="ok")                     # 살아 있는 항목 — raw 가 제자리다
    live.pop("missing_why")
    plain = dict(HELD, contract={})                    # 결손이지만 추출 선언이 없다
    cases = [
        ("선언 밖 이름", held_y, "landing/_hold/random.csv"),
        ("같은 이름 · 하위 폴더", held_y, f"landing/_hold/sub/{NAME}"),
        ("같은 이름 · `_hold` 가 아닌 landing", held_y, f"landing/{NAME}"),
        ("같은 이름 · 다른 폴더 `_held`", held_y, f"landing/_held/{NAME}"),
        ("항목이 살아 있다(status 가 missing 이 아니다)", {"datasets": {"nfa_x": live}}, f"landing/_hold/{NAME}"),
        ("추출 선언이 없다", {"datasets": {"nfa_x": plain}}, f"landing/_hold/{NAME}"),
    ]
    for why, y, rel in cases:
        root = _lake(tmp_path / str(abs(hash(why))), [rel])
        row = _by(y, root)[rel]
        assert row.state == "주인없음", f"{why}: {row}"
        assert any("주인없음" in w for w in lake.gate(y, lake.resolve(y, root))), why


def test_hold_hits_reads_only_declared_names_and_only_when_held(tmp_path):
    """`ledger_schema.probe` · `contract` 가 쓰는 조회 — 선언한 이름만, `held` 인 항목에만."""
    hold = _lake(tmp_path, [f"landing/_hold/{NAME}", "landing/_hold/other.csv"]) / "landing" / "_hold"
    assert [p.name for p in hold_hits(HELD, hold)] == [NAME]
    assert hold_hits(dict(HELD, status="ok"), hold) == [], "살아 있는 항목은 `_hold` 를 안 읽는다"
    assert hold_hits(dict(HELD, contract={}), hold) == [], "추출 선언이 없으면 안 읽는다"
    assert hold_hits(HELD, tmp_path / "nowhere") == []


def test_contract_reports_how_many_hold_inputs_are_there(tmp_path, monkeypatch):
    """결손 선언 항목의 경고가 `_hold` 입력 수를 든다 — 모자라면 그렇게 적는다."""
    _lake(tmp_path, [f"landing/_hold/{NAME}"])
    monkeypatch.setattr(paths, "LANDING", tmp_path / "landing")
    msg = " ".join(m for _, m in contract.check_one("nfa_x", HELD, tmp_path / "raw", None).lines)
    assert "1/2" in msg and "모자란다" in msg, msg
    _lake(tmp_path, ["landing/_hold/nfa_x_kr_20231231.csv"])
    msg = " ".join(m for _, m in contract.check_one("nfa_x", HELD, tmp_path / "raw", None).lines)
    assert "2/2" in msg and "모자란다" not in msg, msg


def test_held_is_missing_plus_extract_and_nothing_else():
    """판별식 자체 — `status: missing` **이고** 추출을 선언했을 때만 `held` 다. 이름 색인도 그 항목만 든다."""
    assert held(HELD)
    assert not held(dict(HELD, status="ok")) and not held(dict(HELD, contract={})) and not held(None)
    names = held_names({"nfa_x": HELD, "live": dict(HELD, status="ok", files=["nfa/live.csv"]), "plain": dict(HELD, contract={}, files=["nfa/p.csv"])})
    assert names == {NAME: ["nfa_x"], "nfa_x_kr_20231231.csv": ["nfa_x"]}, names
    assert held_names(None) == {}
