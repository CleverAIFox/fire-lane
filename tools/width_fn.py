#!/usr/bin/env python3
"""
tools/width_fn.py — 폭을 함수 w(s) 로 다룬다

    uv run python tools/width_fn.py             전체 비교표
    uv run python tools/width_fn.py --seg UID   한 구간의 w(s) 를 그대로 본다
    uv run python tools/width_fn.py --car 8.0   차 길이를 바꿔 본다

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 읽고 표를 낸다.
  `clearance_probe.py` · `jijeok_probe.py` 와 같은 성격이다.

── 왜 만들었나 ─────────────────────────────────────────────────
`width.py` 는 표본을 만들고 **`min` 만 뽑아 버렸다.** 그래서 폭을
함수로 다룰 수가 없었다.

**`min` 은 최악의 통계량이다.** 표본 하나가 틀리면 판정이 뒤집힌다.

    DM02647 구성로238번길   wmin 10.51m · 커버율 0.056
    DM02916 필문대로289번길  wmin 27.46m · 커버율 0.231

둘 다 `min` 이 이상치를 집은 것이고, 파이프라인이 커버율로 이미 지목하고
있었다. **커버율이 낮다는 건 표본이 적다는 뜻이고, 표본이 적으면 `min` 이
가장 먼저 무너진다.**

── 세 가지 통계량 ──────────────────────────────────────────────
    wmin        min{w(s)}                   지금 쓰는 것
    blocked_m   μ{s : w(s) < TRUCK}         3m 미만인 **길이**
    opening     차 길이만큼 연속으로 이어지는 폭

**`opening` 이 물리적으로 맞는 정의다.** 소방펌프차가 8m 인데 병목이
0.5m 길이면 그건 표본 노이즈일 가능성이 크다. 12m 길이면 확실히 못 간다.

형태학적으로는 **열림(opening)** 이고, 지금 `wmin` 은 `L_car = 0` 인
특수 경우다. 그것은 물리적으로 틀렸다.

★ 곡선은 상관없다. `s` 는 이미 중심선을 따라가는 호길이 매개변수라
  직선이든 곡선이든 같은 식이다.

── 아직 판정에 안 쓴다 ─────────────────────────────────────────
`wmin` 과 `opening` 이 얼마나 다른지 먼저 본다. 크게 다르면 그 구간들이
D-25 실측 1순위이고, 거의 같으면 `min` 을 계속 써도 된다.

**측정하고 대조한 뒤에 바꾼다.** 이 저장소가 08-22 clearance 를 `n=7` 로
기각했다가 08-23 에 근거를 다시 쓴 것이 그 교훈이다.

IN    data/processed/width_samples.csv   (segments 단계 산출)
      web/data/segments.geojson
OUT   없음. --save 를 주면 data/processed/width_fn.csv
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict

from firelane.paths import PROCESSED, WEB
from firelane.seg.params import TRUCK

CAR_L = 8.0          # 소방펌프차 길이(m). 전장 7~9m 이고 8m 를 기준으로 둔다
STEP = 2.0           # width.py 의 표본 간격. 표본 사이는 선형으로 본다

C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m",
     "c": "\033[36m", "d": "\033[90m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def load() -> dict[str, list[tuple[float, float]]]:
    """seg_uid → [(s, w)] · 결측은 뺀다."""
    src = PROCESSED / "width_samples.csv"
    if not src.exists():
        print(col(f"{src} 가 없다.", "r"))
        print("  uv run fire-lane --from segments 를 먼저 돌려라.")
        raise SystemExit(1)
    d: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with src.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["w_m"]:
                d[r["seg_uid"]].append((float(r["s_m"]), float(r["w_m"])))
    for v in d.values():
        v.sort()
    return dict(d)


def blocked_len(pts: list[tuple[float, float]], th: float) -> float:
    """w(s) < th 인 구간의 총 길이.

    ★ 표본 사이는 선형 보간한다. 2m 간격이라 그 안에서 폭이 크게 뛰지
      않는다는 가정이고, 그것이 트랜섹트 방식의 원래 전제다.
    """
    if len(pts) < 2:
        return STEP if (pts and pts[0][1] < th) else 0.0
    tot = 0.0
    for (s0, w0), (s1, w1) in zip(pts, pts[1:], strict=False):
        d = s1 - s0
        if d <= 0:
            continue
        b0, b1 = w0 < th, w1 < th
        if b0 and b1:
            tot += d
        elif b0 or b1:
            # 선형 보간으로 임계를 지나는 지점을 찾는다
            f = (th - w0) / (w1 - w0) if w1 != w0 else 0.5
            tot += d * (f if b0 else 1 - f)
    return tot


def opening(pts: list[tuple[float, float]], car: float) -> float | None:
    """구간을 **통과**할 수 있는 폭.

    ★ 2026-08-23. 처음에 "차 길이만큼 연속으로 이어지는 폭" 으로 짰다가
      되돌렸다. 그것은 **주차 가능 여부**지 통과가 아니다.

      합성 표본으로 걸렸다 — 40m 구간 가운데 12m 가 2m 로 막혔는데
      `opening` 이 5.0 을 줬다. 양쪽 14m 씩이 5m 로 넓어 "8m 차가 들어갈
      자리가 있다" 는 이유였다. **들어갈 수 있다와 통과한다는 다르다.**

    ── 맞는 정의 ────────────────────────────────────────────────
    구간 전체를 지나가야 하므로 병목이 하나라도 있으면 못 간다.
    다만 **병목이 차보다 짧으면** 넘어갈 수 있다 — 앞바퀴가 나가는 동안
    뒷바퀴가 아직 넓은 데 있으면 차체가 통과한다.

        통과폭 = max{ c : w(s) < c 인 모든 구간의 길이가 car 미만 }

    `car = 0` 이면 `wmin` 과 같아진다. 지금 판정이 그 특수 경우다.

    ★ 이것도 근사다. 실제로는 차체 형상과 회전이 들어가고, 짧은 병목이라도
      폭이 차폭(2.5m)보다 좁으면 물리적으로 못 지나간다. 그 하한은
      호출부에서 걸러야 한다.
    """
    if not pts:
        return None
    span = pts[-1][0] - pts[0][0]

    # ★ 2026-08-23 두 번째 정정. 구간이 차보다 짧으면 **병목이 car 를 넘을
    #   수가 없다.** 그래서 모든 후보가 통과로 판정되고 최댓값이 나왔다 —
    #   길이 5.8m 구간에서 `opening 49.30m` 가 그렇게 나왔다.
    #   49m 짜리 골목은 없다.
    #
    #   물리적으로도 맞지 않는다. 5.8m 구간은 그것만으로 통과 여부를 못
    #   정한다 — 차가 구간보다 길면 이웃까지 이어 봐야 한다.
    #   **낙관적으로 틀리느니 wmin 을 쓴다.** 보수적인 쪽이 안전하다.
    if span < car:
        return min(w for _, w in pts)

    # ★ 표본이 적으면 병목 **길이**를 잴 수 없다. 표본 간격이 2m 이므로
    #   4개는 있어야 그 사이를 논할 수 있다. 그 아래는 `min` 과 다를 게 없다.
    if len(pts) < 4:
        return min(w for _, w in pts)

    ws = sorted({w for _, w in pts}, reverse=True)
    for c in ws:
        # w(s) < c 인 구간들의 길이를 재서 가장 긴 것이 car 미만이면 통과
        worst, run = 0.0, 0.0
        for (s0, w0), (s1, w1) in zip(pts, pts[1:], strict=False):
            d = s1 - s0
            if w0 < c and w1 < c:
                run += d
            elif w0 < c or w1 < c:
                f = (c - w0) / (w1 - w0) if w1 != w0 else 0.5
                run += d * (f if w0 < c else 1 - f)
                worst = max(worst, run)
                run = 0.0
            else:
                worst = max(worst, run)
                run = 0.0
        worst = max(worst, run)
        if worst < car:
            return c
    return min(ws)


def cmd_one(uid: str, car: float) -> int:
    d = load()
    pts = d.get(uid)
    if not pts:
        print(col(f"{uid} 표본이 없다", "r"))
        return 1
    print(f"{uid} · 표본 {len(pts)}개 · 길이 {pts[-1][0]-pts[0][0]:.1f}m\n")
    for s, w in pts:
        bar = "█" * int(min(w, 20) * 2)
        mark = col(" ★", "r") if w < TRUCK else ""
        print(f"  s={s:6.1f}  w={w:6.2f}  {bar}{mark}")
    print(f"\n  wmin      {min(w for _, w in pts):6.2f}")
    print(f"  opening   {opening(pts, car):6.2f}  (차 {car}m)")
    print(f"  막힌 길이  {blocked_len(pts, TRUCK):6.2f} m")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", help="한 구간만 본다")
    ap.add_argument("--car", type=float, default=CAR_L, help="차 길이(m)")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    if a.seg:
        return cmd_one(a.seg, a.car)

    d = load()
    seg = {f["properties"]["seg_uid"]: f["properties"]
           for f in json.loads((WEB / "segments.geojson").read_text(encoding="utf-8"))["features"]}
    print(f"표본이 있는 구간 {len(d):,} / 산출 {len(seg):,}\n")

    rows = []
    for uid, pts in d.items():
        p = seg.get(uid)
        if not p or p.get("width_min_m") is None:
            continue
        wm = float(p["width_min_m"])
        op = opening(pts, a.car)
        rows.append({
            "seg_uid": uid, "label": p.get("seg_label") or p.get("road_name") or "",
            "verdict": p["verdict"], "wmin": wm, "opening": op,
            "blocked_m": blocked_len(pts, TRUCK),
            "len": float(p["length_m"]), "n": len(pts),
            "cov": p.get("width_cov"),
        })

    if not rows:
        print(col("대조할 구간이 없다", "r"))
        return 1

    diff = [r for r in rows if abs(r["opening"] - r["wmin"]) > 0.5]
    flip = [r for r in rows if (r["wmin"] < TRUCK) != (r["opening"] < TRUCK)]

    print(f"{col('① min 과 opening 의 차이', 'c')}  (차 {a.car}m 기준)")
    print(f"   0.5m 초과로 다른 구간   {len(diff):4} / {len(rows)}")
    print(f"   {TRUCK}m 임계가 갈리는 구간  {col(str(len(flip)), 'y'):>4} / {len(rows)}")

    print(f"\n{col('② 임계가 갈리는 구간', 'c')} — min 이 이상치를 집은 곳")
    cols = f"   {'라벨':22}{'판정':10}{'wmin':>7}{'open':>7}{'막힘m':>7}{'길이':>7}{'표본':>5}"
    print(cols)
    for r in sorted(flip, key=lambda r: -abs(r["opening"] - r["wmin"]))[:14]:
        print(f"   {str(r['label'])[:20]:22}{r['verdict']:10}"
              f"{r['wmin']:>7.2f}{r['opening']:>7.2f}"
              f"{r['blocked_m']:>7.1f}{r['len']:>7.1f}{r['n']:>5}")

    print(f"\n{col('③ 막힌 길이가 짧은데 blocked 인 곳', 'c')} — 병목이 노이즈일 수 있다")
    noise = [r for r in rows if r["wmin"] < TRUCK and r["blocked_m"] < 2.0]
    print(f"   {len(noise)}구간 (3m 미만이 2m 미만만 이어진다)")
    for r in sorted(noise, key=lambda r: r["blocked_m"])[:10]:
        print(f"   {str(r['label'])[:20]:22}{r['verdict']:10}"
              f"{r['wmin']:>7.2f}{r['opening']:>7.2f}"
              f"{r['blocked_m']:>7.2f}{r['len']:>7.1f}{r['n']:>5}")

    if a.save:
        dst = PROCESSED / "width_fn.csv"
        with dst.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\n{col('→', 'g')} {dst}")

    print(col("\n★ 판정에 반영하지 않았다. 먼저 대조하고 실측으로 정한다.", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
