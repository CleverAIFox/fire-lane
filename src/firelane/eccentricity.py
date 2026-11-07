"""
eccentricity.py — 구간별 **중심선 편심**(ecc)을 진단 칸으로 싣는다. **판정에 안 쓴다.** (Zm13 · DECISIONS §556)

IN    `data/processed/width_samples.csv`(표본점마다 `ecc_m` — 중심선이 도로 한가운데에서 벗어난 거리, 부호 있음) · 구간 `seg_id` · 구간 `width_min_m`
OUT   `ecc_rel_med_m` · `ecc_rel_max_m` · `ecc_cov`
PARAM 없음 (임계가 없다 — 아래)
밖    **판정을 안 한다.** `seg/classify.py` · `segments.py` 가 이 칸을 읽으면 시험이 운다(`tests/test_eccentricity.py`). **임계는 사람이 정한다** — 이 판은 편심이 클 때 무엇을 하라고 정하지 않는다.
      판정 폐포(`segments.py`) 밖이다 — 출판(`publish_web`)이 부른다. 골든 코드 지문을 안 건드린다.
      **새로 재지 않는다** — `width_samples.csv` 의 `ecc_m` 를 그대로 쓴다(폭 엔진이 이미 낸 값).

── 칸 ───────────────────────────────────────────────────────────
`ecc_rel_med_m`  표본 `|ecc_m|` 의 **중앙값 ÷ 반폭**. 반폭 = 그 구간의 발행 `width_min_m / 2`.
`ecc_rel_max_m`  표본 `|ecc_m|` 의 **최댓값 ÷ 반폭**.
`ecc_cov`        `ecc_m` 가 있는 표본점 ÷ 그 구간의 표본점 전부(교차부 제외 등으로 `ecc_m` 이 빈 행이 분모에 든다). 0~1.

★ 이름이 `_m` 으로 끝나지만 **둘은 길이가 아니라 무차원 비율**이다(지시문이 정한 이름이다). 0 이면 정중앙, 1 이면 중심선이 도로 한쪽 경계에 닿는다.
★ 반폭이 없거나 0 이하(`width_min_m` 이 null · 0)면 비율을 못 낸다 → null. 표본에 `ecc_m` 가 하나도 없어도 null 이다. **0 이 아니다** — 0 은 「정중앙」으로 읽힌다.
★ 반폭을 `width_min_m` 으로 잡았다 — 편심이 큰 구간에서 `width_min_m` 이 작게 나오면 비율이 1 을 넘을 수 있다(그 자체가 신호다. 자르지 않는다).
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

NAMES = ("ecc_rel_med_m", "ecc_rel_max_m", "ecc_cov")


def load(path: Path) -> dict[str, list[float | None]]:
    """표본 CSV → 구간(`seg_id`)마다 표본점별 `ecc_m`(빈 칸은 None). 행 수가 `ecc_cov` 의 분모다."""
    out: dict[str, list[float | None]] = defaultdict(list)
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[r["seg_id"]].append(float(r["ecc_m"]) if r.get("ecc_m") not in (None, "") else None)
    return out


def relative(eccs: list[float | None], width_min: float | None) -> tuple[float | None, float | None, float]:
    """한 구간의 `(상대 편심 중앙값, 상대 편심 최댓값, 덮임)`. 못 내면 비율은 None."""
    vals = [abs(e) for e in eccs if e is not None]
    cov = round(len(vals) / len(eccs), 3) if eccs else 0.0
    if not vals or width_min is None or width_min <= 0:
        return None, None, cov
    half = width_min / 2.0
    return round(statistics.median(vals) / half, 3), round(max(vals) / half, 3), cov


def columns(seg_ids, width_mins, samples: dict[str, list[float | None]]) -> dict[str, list]:
    """구간 목록(같은 순서) → 세 칸의 목록. 판정에 안 쓴다."""
    out: dict[str, list] = {k: [] for k in NAMES}
    for sid, wm in zip(seg_ids, width_mins, strict=True):
        med, mx, cov = relative(samples.get(sid, []), wm)
        out["ecc_rel_med_m"].append(med)
        out["ecc_rel_max_m"].append(mx)
        out["ecc_cov"].append(cov)
    return out
