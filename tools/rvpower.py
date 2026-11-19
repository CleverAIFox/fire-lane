#!/usr/bin/env python3
"""
rvpower.py — **거리뷰 판독표 검정의 검정력** — 판독 전에 「대조군이 얼마 이하여야 기각할 수 있나」를 말하고 · 판독 뒤 실측이 선언을 벗어나면 운다.  (PLAN #263 · DECISIONS §835)

`tools/evalset.py` 의 `rv_check`(판독 뒤) · `rv_main`(표를 뽑을 때)이 부른다. 피셔 정확검정 한쪽(`fisher`)도 여기 든다 — `evalset.rv_fisher` 는 이 함수의 다른 이름이다.

판별식   `ceiling(n1, n0)` = 가설군 n1 이 **전부 참**일 때 `fisher ≤ α` 가 되는 대조군 「그 답」 수의 최대(없으면 -1 — 어떤 대조군에서도 기각 못 한다)
① 본 몫(분모)      판독 뒤에 실제로 센 가설군 · 대조군 수(`길 아님` · `가림` · 거리뷰 없다는 빠진 몫) — 설계 수가 아니라 **본 수**로 천장을 다시 낸다
② 못 세는 값이 갈 칸  대조군 「그 답」 수 b 가 천장 위면 p 는 의미가 없다 — 검정 결과 칸 옆에 `검정력.울음` 으로 간다(결과를 지우지 않는다)
③ 전제와 우는 것   전제 = 대조군 비율의 **선언한 상한**(`rvsheet.RV_CTRL_MAX` — 설계 수로 낸 천장 이하여야 한다 · 근거는 조건부다: 사전 추정이 없다).
                  우는 것 둘 — (가) 본 표본의 천장을 실측이 넘음 = 이 표본으로는 결론을 못 낸다 (나) 실측 비율이 선언한 상한을 넘음 = 전제가 깨졌다.
                  **울음은 결과를 무효로 만들지 않는다** — 「가설이 거짓」도 「가설이 참」도 아니고 「이 표본으로는 가를 수 없었다」이다.

IN    `rvsheet` 의 `RV_HYPO` · `RV_ALPHA` · `RV_CTRL_MAX`
OUT   문자열 · dict(`evalset.rv_check` 의 stat 에 실린다)
PARAM `RV_ALPHA`(유의수준) · `RV_CTRL_MAX`(가설마다 선언한 대조군 상한)
밖    **판독 값을 읽지도 판정을 바꾸지도 않는다.** 대조군 비율이 얼마여야 옳은가는 안 정한다(사전 추정이 없다 — 선언을 틀리게 적으면 같은 병이 선언 안에서 되풀이된다).
부류  몸통   진입점이 **아니다.** `evalset.py` 가 import 한다  (DECISIONS §398)
"""
from __future__ import annotations

import math

from rvsheet import RV_ALPHA, RV_CTRL_MAX, RV_HYPO

MEANING = "울음은 결과를 무효로 만들지 않는다 — 「가설이 거짓」도 「가설이 참」도 아니고 「이 표본으로는 결론을 못 낸다」는 뜻이다"


def fisher(a: int, n1: int, b: int, n0: int) -> float:
    """피셔 정확검정 한쪽 p — 가설군 n1 중 a · 대조군 n0 중 b 가 「그 답」일 때, 비율이 같다면 가설군에 a 이상이 몰릴 확률."""
    k = a + b
    return sum(math.comb(n1, x) * math.comb(n0, k - x) for x in range(a, min(n1, k) + 1) if 0 <= k - x <= n0) / math.comb(n1 + n0, k)


def ceiling(n1: int, n0: int, alpha: float = RV_ALPHA) -> int:
    """가설군이 전부 참(n1/n1)일 때 기각이 가능한 대조군 「그 답」 수의 최대. 0 도 못 기각하면 -1."""
    return max((b for b in range(n0 + 1) if n1 and fisher(n1, n1, b, n0) <= alpha), default=-1)


def _frac(h: int, n: int) -> str:
    return f"{h}/{n}({h / n:.0%})" if n else "0/0"


def _cap(n1: int, n0: int) -> str:
    c = ceiling(n1, n0)
    return f"{_frac(c, n0)} 이하" if c >= 0 else "0 이어도 기각 불가능(표본이 너무 작다)"


def _bound(n1: int, n0: int) -> str:
    return f"대조군이 {_cap(n1, n0)}여야 기각할 수 있다" if ceiling(n1, n0) >= 0 else f"대조군이 {_cap(n1, n0)}"


def design_stat() -> dict:
    """판독 **전**에 말한다 — 가설마다 설계 수로 「대조군이 얼마 이하여야 기각할 수 있나」와 선언한 상한. 사전 추정이 없어 **조건부**다. 어느 행이 대조군인지는 안 샌다(수는 머리 규칙에 이미 있다)."""
    return {k: {"설계(가설 쪽 대 대조 쪽)": f"{h[0]} 대 {h[1]}", "검정력(조건부)": f"가설 쪽이 전부 참일 때 {_bound(h[0], h[1])}", "선언한 상한": _frac(*RV_CTRL_MAX[k][:2]), "근거": RV_CTRL_MAX[k][2]}
            for k, h in RV_HYPO.items() if k in RV_CTRL_MAX} | {"조건": "대조군 비율의 사전 추정이 없다 — 위 수는 「대조군이 얼마일 때」의 조건부다. 판독 뒤 실측이 이 수를 넘으면 `검정력.울음` 이 선다 — " + MEANING}


def declaration_flaws() -> list[str]:
    """선언이 빠졌거나 · 근거가 비었거나 · 설계 수가 허용하는 천장보다 느슨하면 결함 — 선언 안에서 같은 병이 되풀이되는 것을 막는다."""
    out = []
    for k, h in RV_HYPO.items():
        d = RV_CTRL_MAX.get(k)
        if not d or not str(d[2]).strip():
            out.append(f"가설 {k}: 대조군 상한 선언이 없거나 근거가 비었다(RV_CTRL_MAX)")
        elif d[1] != h[1] or d[0] > ceiling(h[0], h[1]):
            out.append(f"가설 {k}: 선언 {d[0]}/{d[1]} 이 설계({h[0]} 대 {h[1]})가 기각할 수 있는 천장 {ceiling(h[0], h[1])}/{h[1]} 보다 느슨하거나 대조군 수와 안 맞다")
    return out


def power_report(hyp: str, n1: int, n0: int, a: int, b: int) -> dict:
    """판독 **뒤** — 본 수(n1 · n0 · 대조군 「그 답」 b)로 천장을 다시 내고 선언과 맞댄다. `울음` 이 비어 있지 않으면 결론을 못 내는 표본이다."""
    hb, hn = RV_CTRL_MAX[hyp][:2]
    cry = []
    if n1 and n0 and b > ceiling(n1, n0):
        cry.append(f"기각 불가능 — 본 표본({n1} 대 {n0})에서 기각하려면 대조군이 {_cap(n1, n0)}여야 하는데 실측은 {_frac(b, n0)}라, 가설군이 {n1}/{n1} 이었어도 p 는 {fisher(n1, n1, b, n0):.4f} 로 {RV_ALPHA} 를 못 넘는다")
    if n0 and b * hn > hb * n0:
        cry.append(f"선언한 전제 이탈 — 대조군 상한을 {_frac(hb, hn)} 로 선언했는데 실측은 {_frac(b, n0)}")
    return {"본 표본(가설군 대 대조군)": f"{n1} 대 {n0}", "검정력": f"가설군이 전부 참일 때 {_bound(n1, n0)}", "선언한 상한": _frac(hb, hn), "실측 대조군": _frac(b, n0),
            "울음": cry, "뜻": MEANING if cry else "전제 안이다 — 이 표본으로 기각이 가능하다(p 가 낮은지는 별개다)"}


def cries(stat: dict) -> list[str]:
    """`rv_check` 가 낸 stat 에서 우는 가설의 줄을 모은다 — 출력 · 시험이 같이 쓴다."""
    return [f"가설 {k}: {c}" for k, v in stat.items() if isinstance(v, dict) for c in v.get("검정력", {}).get("울음", [])]
