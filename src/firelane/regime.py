"""
regime.py — 구간의 **폭 표본 체제** 네 가지(2×2). **판정 폐포 밖**이다 — `segments.py` · `seg/classify.py` 가 이 모듈을 안 부른다.  (Zm23 · DECISIONS §569-4)

IN    구간의 `ecc_rel_med_m`(발행 칸) · 구간의 폭 표본 `w_rule` 목록(`width_samples.csv`)
OUT   체제 이름 하나: `둘다멀쩡` · `편심만` · `escape만` · `둘다발동`
PARAM `ECC_THRESHOLD`
밖    **판정을 안 한다.** 체제가 폭의 진위를 말하지도 않는다 — 폭 표본이 어떤 모양으로 났는지의 분류일 뿐이다.
      **폭 급변(`SPREAD_MAX`)과 대장 괴리(`|d|`)는 체제가 아니다** — 별도 축이다. 체제 위에 덧씌우는 **표시**로만 둔다
      (`evalset` 의 봉인 키가 체제와 따로 적는다). 섞어서 여섯으로 만들지 않는다.

── 정의 ───────────────────────────────────────────────────────
  편심 발동    `ecc_rel_med_m ≥ ECC_THRESHOLD`
  escape 발동  그 구간의 폭 표본 중 `w_rule == "escape"` 가 **하나 이상** (이진이다 — 문턱이 없다)
  네 체제      위 두 조건의 2×2 이고 **배타적**이다.

── `ECC_THRESHOLD = 1/3` 의 근거 — 분포가 아니라 기하다 ─────────────────
`ecc_rel = (넓은 쪽 − 좁은 쪽) / 전폭` 이다(중심선에서 양쪽 경계까지의 거리 차를 전폭으로 나눈 것).
`ecc_rel = 1/3` 이면 넓은 쪽이 전폭의 2/3, 좁은 쪽이 1/3 이므로 **좁은 쪽이 넓은 쪽의 정확히 절반**이다 — 한쪽이 다른 쪽의 두 배인 선이다.
이 수는 데이터 분포를 보고 뽑은 것이 아니다. 분수로 적는 것은 그래서다. **맞추려고 조정하지 않는다.**
"""
from __future__ import annotations

from collections.abc import Iterable

#: 편심 발동 문턱. 분포가 아니라 기하에서 나온 분수다(위 근거) — 계산하지 않고 박는다.
ECC_THRESHOLD = 1 / 3

NONE_, ECC_ONLY, ESCAPE_ONLY, BOTH = "둘다멀쩡", "편심만", "escape만", "둘다발동"
REGIMES = (NONE_, ECC_ONLY, ESCAPE_ONLY, BOTH)


def ecc_fires(ecc_rel_med_m: float | None) -> bool | None:
    """편심 발동. 값이 없으면 `None` — 「없다」를 「멀쩡하다」로 읽지 않는다."""
    return None if ecc_rel_med_m is None else ecc_rel_med_m >= ECC_THRESHOLD


def escape_fires(w_rules: Iterable[str | None]) -> bool:
    """escape 발동 — 폭 표본 중 `w_rule == "escape"` 가 하나 이상."""
    return any(r == "escape" for r in w_rules)


def regime_of(ecc_rel_med_m: float | None, w_rules: Iterable[str | None]) -> str | None:
    """2×2 체제. 편심 값이 없으면 `None`."""
    e = ecc_fires(ecc_rel_med_m)
    if e is None:
        return None
    s = escape_fires(w_rules)
    return BOTH if (e and s) else ECC_ONLY if e else ESCAPE_ONLY if s else NONE_
