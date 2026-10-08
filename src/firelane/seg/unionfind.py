"""
unionfind.py — union-find 의 `find`. **경로 절반 압축 다섯 줄.**  (PLAN #47)

── 왜 생겼나 (2026-10-08 · DECISIONS §431) ────────────────────
`dupcheck --min 40` 이 남긴 **마지막 사본군**이었다 — `publish_navi` ·
`seg/geom` · `bridge_audit` · `kpi` 넷이 41노드를 공유했다. `PLAN #47` 이
그것을 들고 있었고, 행은 「**동치성 증명이 먼저**고 그 뒤 전량 1회 →
`golden.py lock`」이라고 적었다.

★ 읽어 보니 **합칠 수 있는 것과 없는 것이 갈렸다.**

    같다    `find` 다섯 줄. 그릇 이름만 `parent` · `par` 로 다르고
            나머지는 글자까지 같다. **순수 함수라 합쳐도 값이 안 바뀐다**
    다르다  **묶는 로직 넷.** `seg/geom` 은 STRtree + `buffer(tol)` 로 찾고
            나머지 셋은 격자다. 그 격자도 키가 다르다 —
            `publish_navi` 는 `_node_key(x, y, NODE_TOL)`,
            `bridge_audit` · `kpi` 는 `int(x // tol)`.
            **이것들을 합치면 노드 묶음이 달라지고 `seg_uid` 가 움직인다**
            (DECISIONS §144). 행이 경고한 그 자리가 여기다

그래서 **다섯 줄만** 뺀다. 사본군은 사라지고 판정은 안 움직인다.

IN    없음
OUT   없음 (순수 함수)
PARAM 없음
밖    **무엇을 묶을지는 안 정한다.** 이웃을 찾는 일도, `tol` 도, 셀 키도
      부르는 쪽 것이다. 여기는 「이미 정해진 부모 배열에서 뿌리를 찾는다」만 한다.
"""
from __future__ import annotations

from typing import Protocol, TypeVar

_K = TypeVar("_K")


class Parent(Protocol):
    """`parent[i]` 로 읽고 쓰는 그릇. `list[int]` 와 `dict[int, int]` 둘 다 온다."""

    def __getitem__(self, k: int) -> int: ...
    def __setitem__(self, k: int, v: int) -> None: ...


def find(parent: Parent, i: int) -> int:
    """`i` 의 뿌리. 가는 길에 **경로를 절반으로 접는다.**

    ★ 절반 압축(path halving)이다 — 재귀 없이 한 번 훑으면서 한 칸씩 건너뛰게
      다시 건다. 완전 압축(path compression)과 점근은 같고 스택을 안 쓴다.
      네 사본이 전부 이 꼴이었고, 바꾸지 않았다 — **이 판은 값을 안 움직인다.**
    """
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i
