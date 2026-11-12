#!/usr/bin/env python3
"""
wallab.py — **판정 두 판을 구간 단위로 맞댄다.** 바뀐 구간 · 갈림 표 · 측량 도로폭과의 일치.  (PLAN #53 · DECISIONS §709)

    uv run python tools/wallab.py 기준.geojson 비교.geojson [비교2.geojson …]

── 왜 있나 ──────────────────────────────────────────────────
재잠금은 판정 지문이 움직이는 판이라 **예보와 실제를 대야** 한다. 그런데 예보는 「수 넷」으로만 적히고 **어느 구간이 어디로 갔는지**는 안 적힌다 — 그래서 틀린 수의
이유(`clear` 275 → 249 처럼 예보에 없던 움직임)가 안 보인다. 이 도구는 두 `segments.geojson`(`seg_uid` 로 짝짓는다)에서 ① 판정 수 · `width_max_m` 결손 ② 갈림 표
(`blocked → unknown` …) ③ blocked 에서 풀리거나 새로 막힌 구간의 **측량 도로폭 분포** ④ 측량이 있는 구간의 **혼동표**(측량 3m 미만인데 어떻게 판정했나)를 낸다.

★ **측량은 진실이 아니다.** 대조의 한 축이다(`tools/widthcross.py` 의 머리말이 같은 말을 한다). 측량이 없는 구간은 「측량 없음」으로 따로 센다 — 못 재는 것을 맞다 · 틀리다에 안 넣는다.
★ **어느 판이 옳은가는 안 말한다.** 수만 낸다 — 고르는 것은 사람이다(재잠금은 사람 몫).
★ 측량 폭은 **지금 저장소의** `data/processed`(`widthcross._load` · 띠 `SURVEY_BAND`)에서 붙인다. 구간 기하는 판마다 같으므로(폭만 다르다) 한 번 붙이면 된다.

IN    비교할 `segments.geojson` 둘 이상 · `data/processed/segments_5186.gpkg` · `ngii1k_center_5186.gpkg`(측량 폭)
OUT   표준출력
PARAM `FLOOR_M`(3.0 — 소방차 통과 하한 · `seg/params.TRUCK` 와 같다)
밖    **판정을 안 바꾼다 · 파이프라인을 안 돌린다** — 이미 나온 두 파일을 읽을 뿐이다. 두 파일의 `seg_uid` 집합이 다르면 **죽는다**(다른 구간을 짝지으면 표가 거짓이다).
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

#: 소방차 통과 하한(m) — `firelane.seg.params.TRUCK`. 측량이 이 아래면 「통행 불가가 맞다」로 본다.
FLOOR_M = 3.0
VERDICTS = ("blocked", "needs_cv", "unknown", "clear")


def load(path: str | Path) -> dict[str, dict]:
    """`segments.geojson` → `seg_uid` → 속성. 키가 없는 구간이 있으면 죽는다."""
    feats = json.loads(Path(path).read_text(encoding="utf-8"))["features"]
    out: dict[str, dict] = {}
    for f in feats:
        uid = f["properties"].get("seg_uid")
        if not uid:
            raise SystemExit(f"★ {path} 에 seg_uid 가 없는 구간이 있다 — 짝지을 수 없다")
        out[uid] = f["properties"]
    return out


def survey_class(s: float | None) -> str:
    """측량 폭 → 갈래. 모르면 「측량 없음」(맞다 · 틀리다에 안 넣는다)."""
    if s is None:
        return "측량 없음"
    return "측량<3" if s < FLOOR_M else ("측량3~6" if s < 6 else "측량≥6")


def counts(d: dict[str, dict]) -> tuple[Counter, int]:
    """(판정 수, `width_max_m` 결손 수)."""
    return Counter(p["verdict"] for p in d.values()), sum(1 for p in d.values() if p.get("width_max_m") is None)


def transitions(base: dict[str, dict], cur: dict[str, dict]) -> Counter:
    """(기준 판정, 비교 판정) → 구간 수 — 바뀐 것만. 두 집합이 다르면 죽는다."""
    if set(base) != set(cur):
        raise SystemExit(f"★ seg_uid 집합이 다르다(기준 {len(base)} · 비교 {len(cur)}) — 다른 구간을 짝지으면 표가 거짓이다")
    return Counter((base[u]["verdict"], cur[u]["verdict"]) for u in cur if base[u]["verdict"] != cur[u]["verdict"])


def moved(base: dict[str, dict], cur: dict[str, dict], survey: dict[str, float]) -> dict:
    """blocked 에서 풀린 구간 · 새로 막힌 구간의 측량 갈래별 수, 바뀐 전체의 갈래."""
    freed = [u for u in cur if base[u]["verdict"] == "blocked" and cur[u]["verdict"] != "blocked"]
    newly = [u for u in cur if base[u]["verdict"] != "blocked" and cur[u]["verdict"] == "blocked"]
    chg = [u for u in cur if base[u]["verdict"] != cur[u]["verdict"]]
    def c(us: list[str]) -> dict:
        return dict(Counter(survey_class(survey.get(u)) for u in us))

    return {"풀림": (len(freed), c(freed)), "새로 막힘": (len(newly), c(newly)), "바뀐 전체": (len(chg), c(chg))}


def confusion(d: dict[str, dict], survey: dict[str, float]) -> dict:
    """측량이 있는 구간만 — 측량 3m 미만 · 이상에서 판정이 어떻게 나뉘나. 순수.

    `측량<3` 쪽의 `clear` 는 **측량이 좁다는데 통과 가능으로 판정한** 위험한 쪽이고, `측량≥3` 쪽의 `blocked` 는 과잉이다.
    """
    lo, hi = Counter(), Counter()
    for u, s in survey.items():
        if u in d:
            (lo if s < FLOOR_M else hi)[d[u]["verdict"]] += 1
    return {"측량<3": dict(lo), "측량≥3": dict(hi)}


def survey_by_uid() -> dict[str, float]:
    """지금 저장소의 산출물에서 구간별 측량 폭. 못 읽으면 빈 표(그러면 모두 「측량 없음」)."""
    import widthcross as W

    rows = W._load() or []
    return {r["seg_uid"]: float(r["survey"]) for r in rows if r.get("seg_uid") and r.get("survey") is not None}


def report(label: str, base: dict[str, dict], cur: dict[str, dict], survey: dict[str, float]) -> str:
    c, miss = counts(cur)
    c0, miss0 = counts(base)
    L = [f"== {label}", "   " + " · ".join(f"{v} {c.get(v, 0)}({c.get(v, 0) - c0.get(v, 0):+d})" for v in VERDICTS) + f" · wmax 결손 {miss}({miss - miss0:+d})"]
    for (a, b), n in sorted(transitions(base, cur).items(), key=lambda kv: -kv[1]):
        L.append(f"     {a:9} → {b:9} {n}")
    m = moved(base, cur, survey)
    for k, (n, by) in m.items():
        L.append(f"   {k} {n} {by}")
    cf = confusion(cur, survey)
    lo, hi = cf["측량<3"], cf["측량≥3"]
    L.append(f"   측량 {sum(lo.values()) + sum(hi.values())}구간 — 측량<3 {sum(lo.values())}: blocked {lo.get('blocked', 0)} · unknown/needs_cv {lo.get('unknown', 0) + lo.get('needs_cv', 0)} · clear {lo.get('clear', 0)}(위험)"
             f" | 측량≥3 {sum(hi.values())}: blocked {hi.get('blocked', 0)}(과잉)")
    return "\n".join(L)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    base = load(argv[0])
    survey = survey_by_uid()
    print(f"기준 {argv[0]} — {dict(counts(base)[0])} · 측량 {len(survey)}구간(<3m {sum(1 for s in survey.values() if s < FLOOR_M)})")
    print(report("기준", base, base, survey))
    for p in argv[1:]:
        print(report(p, base, load(p), survey))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
