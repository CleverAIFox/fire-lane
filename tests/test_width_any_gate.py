#!/usr/bin/env python3
"""
test_width_any_gate.py — 측정된 병목을 버리고 **통과로 발표하지 않는다.** + 폭 계측 칸의 불변식.

── 왜 이 관문인가 ──────────────────────────────────────────────
측정된 병목을 버리고 통과로 발표하는 것이 이 프로젝트가 낼 수 있는 최악의 오류다. 과소판정은 출동을 늦추지만 과대판정은
소방차를 못 들어가는 길로 보낸다.
구간 폭(`width_min_m`)은 채택된 한 소스의 표본만으로 낸다. 엔진은 표본마다 세 소스를 다 재고 하나만 남겼고, 그래서 채택에서 밀린
소스가 소방차 폭(`TRUCK` 3.0m) 미만을 쟀어도 `clear` 가 나갈 수 있었다. 소스 무관 최솟값(`width_min_any_m`)이 그것을 보이게 했고
판정 규칙 [8] 이 `clear` 를 거둔다 — `needs_cv`(CCTV 유효범위 안) 또는 `unknown/needs_survey`(밖).
**이 시험이 그 규칙이 지켜지는지 발행본으로 판다.** 어긴 구간은 목록으로 출력한다.

── 계측 불변식 (Zm3) ──────────────────────────────────────────
`width_samples.csv` 의 `left_m` · `right_m` 은 **채택 소스의 좌우 거리**다. `w_m = left_m + right_m` 이 성립하는 것은 규칙 `sum` · `carve` 뿐이고
`escape`(한쪽이 20m 를 넘어 샌 표본)는 `w_m = 2·min(left_m, right_m)` 이다. 이 시험이 그 셋을 따로 검산한다 — 합쳐서 검산하면
`escape` 가 거짓 위반으로 보인다.

IN    data/processed/segments.geojson · data/processed/width_samples.csv
OUT   없음 (검사)
PARAM 없음
밖    **폭이 참인가는 안 본다** — 기록이 정의대로인지, 규칙이 지켜졌는지만 본다. `sym_w_m`(대칭폭)은 판정에 안 쓴다 — 다음 판의 재료다.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "data" / "processed" / "segments.geojson"
SAMPLES = ROOT / "data" / "processed" / "width_samples.csv"
TRUCK = 3.0


def _need(p: Path):
    if not p.exists():
        pytest.skip(f"환경skip(산출물) — {p.name} 이 없다. fire-lane --from segments 가 만든다")


def test_no_clear_is_published_when_any_source_measured_below_truck():
    _need(SEG)
    feats = json.loads(SEG.read_text(encoding="utf-8"))["features"]
    bad = [p for p in (f["properties"] for f in feats)
           if p["verdict"] == "clear" and p.get("width_min_any_m") is not None and p["width_min_any_m"] < TRUCK]
    assert not bad, (
        f"소스 무관 최솟값이 {TRUCK}m 미만인데 clear 로 발표된 구간 {len(bad)}:\n  "
        + "\n  ".join(f"{p['seg_id']} any={p['width_min_any_m']}({p['width_min_any_src']}) 발행={p['width_min_m']} "
                      f"cctv={p['cctv_dist_m']}" for p in bad))


def test_demoted_clears_say_why():
    """규칙 [8] 이 거둔 구간은 `unknown/needs_survey` 이거나 `needs_cv` 다 — 이유 낱말 없이 회색이 되지 않는다."""
    _need(SEG)
    feats = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    ns = [p for p in feats if p.get("unknown_reason") == "needs_survey"]
    for p in ns:
        assert p["verdict"] == "unknown" and p["width_min_any_m"] is not None and p["width_min_any_m"] < TRUCK, p["seg_id"]
        assert not p["cv_feasible"], f"{p['seg_id']}: CCTV 유효범위 안인데 needs_survey 다 — needs_cv 여야 한다"


def test_sample_columns_respect_the_width_definition():
    _need(SAMPLES)
    n = {"sum": 0, "carve": 0, "escape": 0}
    bad = []
    with SAMPLES.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not r["left_m"]:
                continue
            w, left, right, rule = float(r["w_m"]), float(r["left_m"]), float(r["right_m"]), r["w_rule"]
            n[rule] += 1
            want = 2 * min(left, right) if rule == "escape" else left + right
            if abs(w - want) > 0.0021:
                bad.append((r["seg_id"], r["s_m"], w, left, right, rule))
            assert abs(float(r["sym_w_m"]) - 2 * min(left, right)) < 0.0011
            assert abs(float(r["ecc_m"]) - (left - right) / 2) < 0.0011
    assert sum(n.values()) > 10000, f"좌우를 남긴 표본이 너무 적다 — {n}"
    assert not bad, f"w_m 이 규칙대로 안 맞는 표본 {len(bad)} — {bad[:5]}"


def test_every_three_source_value_is_kept_and_any_min_is_their_min():
    """표본마다 세 소스 값을 남기고, 소스 무관 최솟값은 **그 값들의 최솟값**이다(채택된 한 줄이 아니다)."""
    _need(SAMPLES)
    _need(SEG)
    lowest: dict[str, float] = {}
    with SAMPLES.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            for c in ("w_ngii1k_m", "w_ngii_m", "w_silpok_m"):
                if r[c]:
                    v = float(r[c])
                    if v < lowest.get(r["seg_id"], 1e9):
                        lowest[r["seg_id"]] = v
    feats = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    diff = [(p["seg_id"], p["width_min_any_m"], lowest[p["seg_id"]]) for p in feats
            if p["seg_id"] in lowest and p["width_min_any_m"] is not None
            and abs(p["width_min_any_m"] - lowest[p["seg_id"]]) > 0.0011]
    assert not diff, f"width_min_any_m 이 세 소스 값의 최솟값과 다르다 — {diff[:5]}"
    hidden = sum(1 for p in feats if p["seg_id"] in lowest and p["width_min_any_m"] is not None
                 and p["width_min_any_m"] < (p["width_min_m"] or 1e9) - 0.05)
    assert hidden > 0, "채택에서 밀린 더 좁은 값이 하나도 없다 — 이 시험이 아무것도 안 잰다"
