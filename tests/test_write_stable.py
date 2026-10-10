"""
test_write_stable.py — **시각·커밋 말고** 달라졌을 때만 쓰는가.
  (DECISIONS §445 · PLAN #56 ③ G-8 「manifest write_stable」)

★ 왜 이 시험이 있나 — 봉인 셋(`meta.json` · `eval.json` · `nfa_compare.json`)이
  매 실행 `as_of` · `frozen_at` · `git_sha` 만 바뀌어 **추적 파일이 더럽다**로
  열차를 세웠다. `git_sha` 는 **직전 커밋**을 적으므로 커밋하면 또 바뀐다 —
  닿을 수 없는 고정점이다.

★ `tests/test_freshcheck.py` 와 **겹치지 않는다.** 그쪽은 「안 쓰는 것이
  신선함 판정을 어떻게 흔드나」를 보고, 이쪽은 **판별식 자체**를 양방향으로
  민다. 그리고 넓힌 키가 **진짜 변화를 가리지 않는가**를 실물에서 센다.

밖    **무엇이 시각인가는 안 정한다** — 목록은 `manifest.STAMP_KEYS` 가 들고,
      이 시험은 그 목록대로 움직이는가만 본다.
"""
from __future__ import annotations

import json
from pathlib import Path

from firelane.manifest import STAMP_KEYS, write_stable

ROOT = Path(__file__).resolve().parents[1]


def test_it_writes_when_the_file_is_new(tmp_path):
    p = tmp_path / "a.json"
    assert write_stable(p, {"n": 1}) is True
    assert json.loads(p.read_text(encoding="utf-8")) == {"n": 1}


def test_it_does_not_write_when_only_the_clock_moved(tmp_path):
    """정상 입력 — 수가 같으면 **조용하다.** 옛 시각이 남고 그것이 더 참이다."""
    p = tmp_path / "a.json"
    write_stable(p, {"as_of": "1", "git_sha": "aaa", "n": 1})
    assert write_stable(p, {"as_of": "2", "git_sha": "bbb", "n": 1}) is False
    got = json.loads(p.read_text(encoding="utf-8"))
    assert got["as_of"] == "1" and got["git_sha"] == "aaa"


def test_it_writes_when_a_real_number_moved(tmp_path):
    """합성 결함 — 수가 바뀌면 **운다.** 안 울면 봉인이 거짓을 들고 있게 된다."""
    p = tmp_path / "a.json"
    write_stable(p, {"as_of": "1", "n": 1})
    assert write_stable(p, {"as_of": "1", "n": 2}) is True
    assert json.loads(p.read_text(encoding="utf-8"))["n"] == 2


def test_the_trailing_newline_is_not_flattened(tmp_path):
    """봉인은 끝개행이 있고 매니페스트는 없다. **그 차이를 뭉개면** 한쪽이
    매 실행 한 바이트 다르다 — 고친 것과 같은 병이 반대 방향으로 난다."""
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    write_stable(a, {"n": 1})
    write_stable(b, {"n": 1}, tail="\n")
    assert not a.read_text(encoding="utf-8").endswith("\n")
    assert b.read_text(encoding="utf-8").endswith("\n")
    assert write_stable(b, {"n": 1}, tail="\n") is False, "끝개행이 매번 달라진다"


def test_a_broken_file_is_not_left_alone(tmp_path):
    """깨진 파일을 **조용히 두지 않는다** — 두면 영원히 남는다."""
    p = tmp_path / "a.json"
    p.write_text("{ 깨짐", encoding="utf-8")
    assert write_stable(p, {"n": 1}) is True


def test_no_manifest_carries_a_stamp_key_as_content():
    """★ 실측 — 넓힌 키가 **진짜 변화를 가리는 자리**가 아직 없는가.

    `_borrow_stamps` 는 중첩을 따라간다. 어느 매니페스트가 `git_sha` 를
    **내용으로** 들면 그 변화를 조용히 빌려 온다. 2026-10-09 실측은 0종이고,
    생기면 여기서 운다 — 그때는 키를 좁히거나 그 매니페스트가 이름을 바꾼다.
    """
    seen: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                seen.add(k)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    found = []
    for rel in ("web/data/_manifest.json", "data/processed/_manifest.json"):
        p = ROOT / rel
        if p.is_file():
            seen.clear()
            walk(json.loads(p.read_text(encoding="utf-8")))
            found += [f"{rel}::{k}" for k in seen
                      if k in STAMP_KEYS and k != "generated_at"]
    assert not found, (
        f"매니페스트가 시각 키를 **내용으로** 든다 — {found}\n"
        "  중첩 빌림이 그 변화를 가린다. 키를 좁히거나 그 칸의 이름을 바꿔라.")


def test_the_list_names_the_four_that_bit():
    """★ 빈 그물 금지 — 목록이 비면 모든 축이 조용히 통과한다."""
    assert set(STAMP_KEYS) == {"generated_at", "as_of", "frozen_at", "git_sha"}, STAMP_KEYS
