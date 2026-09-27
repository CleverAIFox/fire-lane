"""JSON 나무에서 **이름으로 칸을 빼는** 일의 집. 정책은 안 든다.

★ 2026-09-24 (PLAN §13 W13-4 · DECISIONS §243). 같은 재귀가 둘이었다 —
  `shardseal._no_docs`(서술 칸을 빼고 지문을 잰다)와
  `tools/freshcheck.py::canon`(비결정 칸을 빼고 대조한다). 59노드가 글자까지
  같았고 `dupcheck` 가 사본군으로 셌다. 4족(직접 구현)이다.

★ **무엇을 뺄지는 부르는 쪽이 정한다.** 여기 있는 것은 「어떻게 빼는가」
  하나다 — `tests/docparse.py` 가 펜스 처리에 세운 규율과 같다.
  두 쓰임은 정책이 정반대로 움직인다(한쪽은 늘수록 안 찢어지고, 다른 쪽은
  늘수록 못 본다). 정책까지 합치면 한쪽 변경이 다른 쪽 판정을 조용히 민다.

★ 이 파일은 `firelane.ingest` 의 코드 폐포에 든다(shardseal 이 import 한다).
  그러므로 **여기를 고치면 샤드가 찢어진다.** 고칠 일이 없게 정책을 안 둔다.

IN    없음
OUT   없음 (순수 함수)
PARAM 없음
밖    값은 안 본다 — 이름으로만 뺀다. 리스트 안의 dict 도 같은 규칙으로 판다.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def drop(obj: Any, names: Iterable[str]) -> Any:
    """`names` 에 든 키를 **어느 깊이에서든** 뺀 사본."""
    keys = frozenset(names)
    def go(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: go(x) for k, x in v.items() if k not in keys}
        if isinstance(v, list):
            return [go(x) for x in v]
        return v
    return go(obj)


def selftest() -> int:
    """깊이와 리스트를 정말 파는가. 두 쓰임이 이 함수를 믿는다."""
    src = {"a": 1, "note": "x", "b": {"note": "y", "c": [{"note": "z", "d": 2}]}}
    got = drop(src, {"note"})
    assert got == {"a": 1, "b": {"c": [{"d": 2}]}}, got
    assert src["note"] == "x", "원본을 건드렸다"
    assert drop(src, ()) == src, "뺄 것이 없으면 그대로여야 한다"
    assert drop(3, {"note"}) == 3 and drop(None, {"note"}) is None
    print("jsonkeys OK — 깊이 · 리스트 · 원본 보존")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())
