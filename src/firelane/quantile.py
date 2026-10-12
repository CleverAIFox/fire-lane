#!/usr/bin/env python3
"""
quantile.py — 분위수 정본. **「p90」 이 뜻하는 것이 여기 하나다.**

── 왜 생겼나 (2026-10-11 · DECISIONS §471) ─────────────────────
저장소가 **같은 분위수를 네 공식으로** 재고 있었다 —

    tools/evalgen.py        색인 「n×0.9 의 정수부」   ← n ≤ 10 이면 **최댓값**
    tools/kpi.py            같은 색인                  ← 같은 자리
    src/firelane/publish_context.py
                            색인 「0.9×(n−1) 의 정수부」 ← n = 2 면 **최솟값**
    tools/statkit.py        손 선형보간 (§379-9)
    tools/skeleton_compare.py · corner_probe.py
                            pandas .quantile(.9)       ← 선형보간

★ 위 네 꼴을 **글자 그대로 안 적는다** — `tests/test_handrolled.py` 가 그
  색인 꼴을 저장소 전체에서 금지하고, 여기 적으면 정본이 제 금지를 어긴다
  (§469 가 `localgeo` 머리말에서 같은 값을 치렀다).

앞의 둘은 **「p90」 이라고 적고 최댓값을 찍는다** — `evalgen` 은 그 수를
`ratio_max` **바로 옆 칸에** 둔다. 두 칸이 같은 수가 되는데 아무도 안 울었다.

★ **공식을 여기 안 짠다** — `numpy.quantile` 이 한다. 사용자 원칙이
  「가능한 한 모든 것을 의존성에 맡긴다」이고, 정본을 세우면서 그 안에 손
  공식을 남기면 **이 절이 고치는 병을 이 파일이 다시 앓는다.**

★ `numpy` 는 이미 선언된 의존성이고 `src/firelane` 열 모듈이 든다 —
  `ingest` · `segments` · `ortho` 를 포함한다. **무게가 안 늘어난다.**

★ 선형보간(type 7)이다. 실측으로 `pandas.Series.quantile` 과 **전부 같다**
  (n 1~80 · q 여덟 · 600회 · 불일치 0). 새 규칙을 세우는 것이 아니라
  **이미 이 저장소가 두 도구에서 쓰던 규칙**을 하나로 모은다.

★ 집이 `src/firelane` 이다 — `publish_context` 가 소비자이고 `src` 는 계층
  때문에 `tools/` 를 import 할 수 없다. 그래서 `statkit.quartiles` 가 있는데도
  `publish_context` 는 제 공식을 손으로 짰다. **정본을 못 쓰게 두면 사본이
  생긴다**(§469-1 이 같은 값을 치렀다). 봉인은 안 움직인다 — 실측으로 폐포
  셋(`ingest` 4836c1e8 · `segments` 1ecbdadb · `ortho` bcf0af56)이 이
  파일을 **하나도 안 든다.**

── 중앙값은 여기 없다 ─────────────────────────────────────────
`statistics.median` 이 정본이고 그것으로 충분하다. 여기 감싸면 **같은 것의
이름이 둘**이 되고 그것이 이 절이 고치는 병이다. §471 이 손으로 센 중앙값
다섯 자리를 `statistics.median` 으로 바로 보냈다.

IN    없음 (순수 함수)
OUT   없음
PARAM 없음
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
밖    **가중 분위수는 안 든다.** 길이 가중 중앙값은 `seg/width.py` 가 제
      자리에서 들고 그것은 다른 일감이다.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

#: p90 의 q. 이름이 코드 안에 글자로 흩어지지 않게 둔다.
P90 = 0.9


def quantile(xs: Iterable[float], q: float) -> float:
    """선형보간 분위수. `numpy.quantile` 이 센다 — 정렬도 그쪽이 한다.

    ★ 빈 표본은 **부른 쪽이 가른다** — 여기서 `None` 을 내면 「없다」와
      「0 이다」가 섞인다(§467 이 같은 족이다). `ValueError` 를 던진다.
      `numpy` 는 빈 입력에 `RuntimeWarning` 과 `nan` 을 내므로 **조용히
      넘어가는 길을 막는다.**
    """
    v = list(xs)
    if not v:
        raise ValueError("빈 표본의 분위수는 없다 — 부르는 쪽이 가른다")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"q 는 0~1 이다 — 받은 것 {q!r}")
    return float(np.quantile(v, q))


def p90(xs: Iterable[float]) -> float:
    """상위 10% 문턱. `quantile(xs, 0.9)` 다 — 이름을 한 번만 적는다."""
    return quantile(xs, P90)
