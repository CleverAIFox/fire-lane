#!/usr/bin/env python3
"""
tools/naver_join.py — 네이버 대조 결과를 봉인값과 합쳐 분석한다

    uv run python tools/naver_join.py

★ naver_check.csv 를 다 채운 뒤에 돌린다. 그 전에 돌리면 봉인의 의미가
  없다 — 우리 값을 보고 나서 재면 그 근처로 수렴한다.

── 무엇을 보나 ─────────────────────────────────────────────────
A. 기초번호   label_ok 비율. 낮으면 seg_label 산출이 잘못된 것이다
B. 폭         네이버 vs 우리 wmin

B 에서 셋을 가른다.

  편차의 **중앙값**   계통오차. 크면 한쪽이 일관되게 치우친 것이다
  편차의 **산포**     우연오차. 이게 크면 네이버를 준-실측으로 못 쓴다
  대역별 편차         특정 대역에서만 벌어지면 원인이 좁혀진다

★ 판단 기준
  |중앙 편차| < 0.3m 이고 표준편차 < 0.5m
      → 네이버를 1,101구간 전수 대조에 쓸 수 있다. 실측 규모를 줄인다.
  중앙 편차는 크지만 산포가 작다
      → 계통오차다. 보정 상수 하나로 잡히므로 여전히 쓸 수 있다.
  산포가 크다
      → 못 쓴다. 클릭 정확도가 한계다. 순서형 참고로만.

★ 이 결과로 실측을 없애지 않는다. 네이버도 결국 지도이고, 우리 소스와
  같은 국가 데이터에서 파생됐을 수 있다. 그러면 독립 검증이 아니라 같은
  것을 두 번 보는 것이다. 레이저 실측 3~5곳이 **네이버가 맞는지**를
  확인하고, 그 다음에 네이버로 전수를 간다.
"""
from __future__ import annotations

import csv

import pandas as pd

from firelane.paths import FIELD


def load(p):
    return pd.DataFrame(list(csv.DictReader(p.open(encoding="utf-8-sig"))))


def main() -> int:
    chk, seal = FIELD / "naver_check.csv", FIELD / ".naver_sealed.csv"
    for p in (chk, seal):
        if not p.exists():
            print(f"::error::{p} 없다. tools/naver_check.py 를 먼저 돌려라")
            return 1

    a, b = load(chk), load(seal)
    d = a.merge(b, on=["no", "seg_uid"], suffixes=("", "_ours"))

    # ── A. 기초번호 ────────────────────────────────────────────
    lab = d[d.label_ok.str.upper().isin(["Y", "N"])]
    print(f"── A. 기초번호 — 채운 것 {len(lab)}/{len(d)}")
    if len(lab):
        ok = (lab.label_ok.str.upper() == "Y").sum()
        print(f"   일치 {ok}/{len(lab)} ({ok / len(lab) * 100:.0f}%)")
        bad = lab[lab.label_ok.str.upper() == "N"]
        if len(bad):
            print("   ★ 불일치")
            for r in bad.itertuples():
                print(f"     {r.seg_uid}  우리 {r.seg_label_ours!r} "
                      f"· 실제 {r.label_seen!r}")

    # ── B. 폭 ──────────────────────────────────────────────────
    w = d[d.naver_w_m.astype(str).str.strip() != ""].copy()
    print(f"\n── B. 폭 — 채운 것 {len(w)}/{len(d)}")
    if not len(w):
        print("   아직 없다")
        return 0

    w["naver"] = pd.to_numeric(w.naver_w_m, errors="coerce")
    w["ours"] = pd.to_numeric(w.width_min_m, errors="coerce")
    w = w.dropna(subset=["naver", "ours"])
    w["dev"] = w.naver - w.ours

    med, sd = w.dev.median(), w.dev.std()
    print(f"   편차(네이버 − 우리)  중앙 {med:+.2f}m · 평균 {w.dev.mean():+.2f}m "
          f"· 표준편차 {sd:.2f}m")
    for t in (0.3, 0.5, 1.0):
        print(f"     |편차| < {t}m : {(w.dev.abs() < t).mean() * 100:5.1f}%")

    print("\n   대역별")
    for band, gg in w.groupby("band"):
        print(f"     {band:>6} n={len(gg):2d}  중앙 {gg.dev.median():+.2f} "
              f"· 표준편차 {gg.dev.std() if len(gg) > 1 else 0:.2f}")

    hi = w[w.confident.str.upper() == "H"]
    if len(hi) >= 3:
        print(f"\n   confident=H 만 (n={len(hi)})  중앙 {hi.dev.median():+.2f} "
              f"· 표준편차 {hi.dev.std():.2f}")
        print("     ← 클릭이 정확했던 것만 본 값이다. 이쪽 산포가 작으면"
              " 한계는 도구가 아니라 사람이다")

    # ── 판정 ───────────────────────────────────────────────────
    print("\n── 판단")
    if abs(med) < 0.3 and sd < 0.5:
        print("   ★ 네이버를 1,101구간 전수 대조에 쓸 수 있다.")
        print("     실측은 3~5곳으로 줄이고 '네이버가 맞는지' 확인에 쓴다.")
    elif sd < 0.5:
        print(f"   ★ 계통오차 {med:+.2f}m. 산포가 작으므로 보정 상수로 잡힌다.")
        print("     레이저 실측으로 이 상수를 확정한 뒤 전수로 간다.")
    else:
        print(f"   산포 {sd:.2f}m 가 크다. 준-실측으로 못 쓴다.")
        print("     3.0m 임계에서 판정이 뒤집히는 크기다. 순서형 참고로만.")

    print("\n   ★ 어느 쪽이든 레이저 실측을 없애지 않는다. 네이버도 지도이고")
    print("     우리 소스와 같은 국가 데이터에서 파생됐을 수 있다.")

    out = FIELD / "naver_join.csv"
    w[["no", "seg_uid", "band", "road_name", "ours", "naver", "dev",
       "confident", "naver_w_at", "note"]].to_csv(out, index=False,
                                                  encoding="utf-8-sig")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
