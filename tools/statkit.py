#!/usr/bin/env python3
"""
statkit.py — 대조 도구가 같이 쓰는 **작은 수 셈**. 집이 여기 하나다.

── 왜 생겼나 (DECISIONS §379-9) ────────────────────────────────
`tools/widthcross.py` 와 `tools/clearance_cross.py` 가 `_num` 과 `quartiles`
를 **글자까지 같게** 들고 있었다. `dupcheck` 가 사본군 셋(152 · 95 · 46 노드)
으로 물었다. 둘 다 「폭을 다른 원천과 댄다」는 같은 일을 하는데 셈이 갈리면
두 표가 **다른 사분위 정의로** 같은 이름을 쓰게 된다 — 2족이다.

★ `src/firelane` 으로 안 올렸다. 그쪽은 판정 폐포라 함수 하나를 더해도 코드
  지문이 움직이고 재잠금이 따라온다(§239 가 `localgeo` 에서 든 판단과 같다).
  이 둘은 **판정 밖 조사 도구**다.

IN    없음 (순수 함수)
OUT   없음
PARAM 없음 · 인자 없이 치면 자기검사
밖    **통계를 안 한다.** 평균도 분산도 검정도 없다 — 여기 있는 것은
      「결측을 결측으로 읽기」와 「사분위」 둘뿐이고, 둘 다 표를 찍는 데만 쓴다.
      분포를 보고 무엇을 판단할지는 부르는 쪽이 정한다.
부류  생산   산출물·대장·그림을 만든다  (DECISIONS §398)
"""
from __future__ import annotations

import math


def num(v) -> float | None:
    """수로 읽는다. 결측 · 빈칸 · NaN 은 전부 None 이다. **0 은 수다.**

    ★ 0 을 결측으로 읽으면 「폭 0m」와 「폭을 모른다」가 같은 값이 된다.
      회색 = NULL 은 그 반대를 요구한다.
    """
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def quartiles(xs: list[float]) -> dict[str, float]:
    """사분위. numpy 를 안 쓴다 — 표를 찍을 뿐이고 의존을 안 늘린다.

    선형 보간이다(`numpy.percentile` 의 기본과 같은 꼴). 빈 목록은 **빈 표**를
    낸다 — 0 을 내면 「값이 0」과 「잴 것이 없다」가 같아진다.
    """
    if not xs:
        return {}
    s = sorted(xs)

    def q(p: float) -> float:
        if len(s) == 1:
            return s[0]
        i = p * (len(s) - 1)
        lo, hi = int(i), min(int(i) + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (i - lo)

    return {"n": len(s), "min": s[0], "q25": q(.25), "median": q(.5),
            "q75": q(.75), "max": s[-1]}


def selftest() -> int:
    """★ 두 함수가 **양방향으로** 맞는가."""
    bad = []
    if num("") is not None or num(None) is not None or num("x") is not None:
        bad.append("결측을 수로 읽는다")
    if num(0) != 0.0 or num("0") != 0.0:
        bad.append("0 을 결측으로 읽는다 — 0 은 수다")
    if num(float("nan")) is not None:
        bad.append("NaN 을 수로 읽는다")
    if num("3.5") != 3.5:
        bad.append("문자열 수를 못 읽는다")

    q = quartiles([1.0, 2.0, 3.0, 4.0])
    if not (q["n"] == 4 and q["min"] == 1.0 and q["median"] == 2.5
            and q["max"] == 4.0):
        bad.append(f"사분위가 틀렸다 — {q}")
    if quartiles([]):
        bad.append("빈 목록에서 값을 낸다")
    if quartiles([7.0])["median"] != 7.0:
        bad.append("한 점의 중앙이 그 점이 아니다")
    if abs(quartiles([1.0, 2.0, 3.0])["q25"] - 1.5) > 1e-9:
        bad.append("보간이 선형이 아니다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — 결측·0·NaN 가르기 · 사분위 선형 보간")
    return 0


if __name__ == "__main__":
    import argparse
    import sys
    # ★ `--selftest` 를 받는다. `tools/selftests.py` 가 그 깃발로 전수를 돌고,
    #   안 받으면 이 파일만 그 집계 **밖**에 남는다(`localgeo` 가 그 자리다 —
    #   그쪽은 `verify.sh` 가 따로 한 단계로 든다).
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.parse_args()           # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
    sys.exit(selftest())
