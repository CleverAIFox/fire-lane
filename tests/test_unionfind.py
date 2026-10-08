#!/usr/bin/env python3
"""
test_unionfind.py — 뺀 `find` 가 **네 사본과 같은 답**을 내는가.  (PLAN #47)

── 왜 생겼나 (2026-10-08 · DECISIONS §431) ────────────────────
`dupcheck --min 40` 의 **마지막 사본군**이 `find` ×4 였다. `PLAN #47` 이
「**동치성 증명이 먼저**고 그 뒤 전량 1회 → `golden.py lock`」이라고 적었다.
증명 없이 합치면 노드 묶음이 달라지고 `seg_uid` 가 움직인다(DECISIONS §144).

★ 읽어 보니 **합칠 것과 못 합칠 것이 갈렸다.** `find` 다섯 줄은 네 곳이
  글자까지 같고 **순수**하다. 반면 **묶는 로직 넷은 서로 다르다** —
  `seg/geom` 은 STRtree, 나머지는 격자이고 그 격자도 셀 키가 다르다.
  그래서 다섯 줄만 뺐다. 이 파일이 그 「같다」를 **수로** 든다.

IN    src/firelane/seg/unionfind.py
OUT   없음 (검사)
PARAM 없음
밖    **묶는 로직은 안 본다.** 이웃을 어떻게 찾는지는 부르는 쪽 일이고,
      그것이 같은지는 이 시험이 묻지 않는다 — 다르다는 것이 위 결론이다.
"""
from __future__ import annotations

import random

from firelane.seg.unionfind import find


def _legacy(parent, i: int) -> int:
    """네 사본이 공유하던 원본 다섯 줄. **글자 그대로** 둔다."""
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def test_the_extracted_find_matches_the_four_copies_it_replaced():
    """합성 격자로 민다 — 답도, **압축 뒤 부모 배열도** 같아야 한다.

    ★ 반환값만 보면 부족하다. 이 함수는 가는 길에 `parent` 를 **고친다** —
      그 부작용이 다르면 다음 호출의 비용이 달라지고, 두 사본이 서로 다른
      상태로 갈린다.
    """
    random.seed(7)
    for _ in range(400):
        n = random.randint(1, 60)
        base = list(range(n))
        for _ in range(random.randint(0, n * 2)):
            a, b = random.randrange(n), random.randrange(n)
            ra, rb = _legacy(base[:], a), _legacy(base[:], b)
            if ra != rb:
                base[max(ra, rb)] = min(ra, rb)

        for grab in (list, dict):
            A = dict(enumerate(base)) if grab is dict else list(base)
            B = dict(enumerate(base)) if grab is dict else list(base)
            for i in range(n):
                assert find(A, i) == _legacy(B, i), f"n={n} i={i}"
            got = list(A.values()) if grab is dict else A
            want = list(B.values()) if grab is dict else B
            assert got == want, f"압축 부작용이 다르다 — n={n} {grab.__name__}"


def test_it_takes_both_a_list_and_a_dict():
    """★ 네 사본의 그릇이 달랐다 — `publish_navi` 는 `dict`, 나머지는 `list`."""
    assert find([0, 0, 1], 2) == 0
    assert find({0: 0, 1: 0, 2: 1}, 2) == 0


def test_a_single_node_is_its_own_root():
    """경계 — 혼자인 노드는 제가 뿌리다. 루프가 한 번도 안 돈다."""
    assert find([0], 0) == 0
