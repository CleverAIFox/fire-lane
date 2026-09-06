#!/usr/bin/env python3
"""
matchcheck.py — Mapbox Map Matching 커버리지 배치 검증

  export MAPBOX_TOKEN="pk...."
  python3 matchcheck.py web/data/segments.geojson --n 200
  python3 matchcheck.py web/data/segments.geojson --all      # 1,101 전량

무엇을 답하나
  "우리 구간 중 어느 것이 상용 도로망에 매칭되는가"
  → 하이브리드 경계를 폭이 아니라 **실측 매칭률**로 긋기 위한 자료다.

★ 아무것도 안 바꾼다. 읽고 표를 낼 뿐이라 golden 지문에 영향이 없다.
  (tools/ 의 대조 도구들과 같은 성격 — MASTER §14-5)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

API = "https://api.mapbox.com/matching/v5/mapbox/driving/"
SEED = 20260904  # 재현성. sample_design.py 와 같은 원칙


def coords_of(geom, maxn=25):
    """구간 선형에서 좌표를 뽑는다. Map Matching 상한은 100점."""
    if geom["type"] == "LineString":
        c = geom["coordinates"]
    elif geom["type"] == "MultiLineString":
        c = [p for part in geom["coordinates"] for p in part]
    else:
        return None
    if len(c) < 2:
        return None
    if len(c) > maxn:
        step = max(1, len(c) // maxn)
        c = c[::step][:maxn]
    return c


def match(coords, token, radius=None, timeout=20):
    """Map Matching 1회. (code, confidence, n_steps, err) 를 돌려준다."""
    path = ";".join(f"{x:.6f},{y:.6f}" for x, y in coords)
    q = {
        "steps": "true",
        "voice_instructions": "true",
        "banner_instructions": "true",
        "geometries": "geojson",
        "access_token": token,
    }
    if radius:
        q["radiuses"] = ";".join([str(radius)] * len(coords))
    url = API + urllib.parse.quote(path) + "?" + urllib.parse.urlencode(q)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            d = json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 행으로 남긴다
        return ("EXC", None, 0, str(e)[:60])
    code = d.get("code")
    ms = d.get("matchings") or []
    if not ms:
        return (code, None, 0, d.get("message", "")[:60])
    m = ms[0]
    nstep = sum(len(leg.get("steps", [])) for leg in m.get("legs", []))
    return (code, m.get("confidence"), nstep, "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("segments", help="web/data/segments.geojson")
    ap.add_argument("--n", type=int, default=200, help="표본 수 (층화)")
    ap.add_argument("--all", action="store_true", help="전량")
    ap.add_argument("--sleep", type=float, default=0.25, help="요청 간 대기(초)")
    ap.add_argument("--radius", type=float, default=None,
                    help="매칭 허용 반경(m). 미지정이면 Mapbox 기본")
    ap.add_argument("--out", default="matchcheck.csv")
    a = ap.parse_args()

    token = os.environ.get("MAPBOX_TOKEN")
    if not token:
        sys.exit("MAPBOX_TOKEN 이 없다.  export MAPBOX_TOKEN='pk....'")

    feats = json.load(open(a.segments, encoding="utf-8"))["features"]
    print(f"구간 {len(feats)}개 로드")

    # ── 층화 표본: verdict × 폭대역. 한쪽만 보면 경계를 잘못 긋는다
    def band(w):
        if w is None:
            return "na"
        return "<3" if w < 3 else "3-7" if w < 7 else "7-15" if w < 15 else "15+"

    strata = defaultdict(list)
    for f in feats:
        p = f["properties"]
        strata[(p["verdict"], band(p.get("width_min_m")))].append(f)

    if a.all:
        pick = list(feats)
    else:
        rnd = random.Random(SEED)
        per = max(1, a.n // max(1, len(strata)))
        pick = []
        for k in sorted(strata):
            g = strata[k]
            pick += rnd.sample(g, min(per, len(g)))
        # 남는 자리는 큰 층에서 채운다
        rest = [f for f in feats if f not in pick]
        rnd.shuffle(rest)
        pick += rest[: max(0, a.n - len(pick))]

    print(f"검사 대상 {len(pick)}개 · 층 {len(strata)}개 · 예상 {len(pick)*a.sleep/60:.1f}분\n")

    rows = []
    okc = Counter()
    for i, f in enumerate(pick, 1):
        p = f["properties"]
        c = coords_of(f["geometry"])
        if not c:
            continue
        code, conf, nstep, err = match(c, token, a.radius)
        rows.append({
            "seg_uid": p["seg_uid"], "verdict": p["verdict"],
            "width_min_m": p.get("width_min_m"), "width_max_m": p.get("width_max_m"),
            "length_m": p.get("length_m"), "road_name": p.get("road_name"),
            "seg_label": p.get("seg_label"), "in_emd": p.get("in_emd"),
            "n_pts": len(c), "code": code,
            "confidence": conf, "n_steps": nstep, "err": err,
        })
        okc[code] += 1
        if i % 25 == 0 or i == len(pick):
            good = sum(1 for r in rows if (r["confidence"] or 0) >= 0.5)
            print(f"  {i:4d}/{len(pick)}  conf>=0.5 {good:4d} ({good/len(rows)*100:.0f}%)")
        time.sleep(a.sleep)

    import csv
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ── 집계
    print("\n" + "=" * 68)
    print("응답 코드:", dict(okc))

    def summarize(key, label):
        print(f"\n[{label}]")
        g = defaultdict(list)
        for r in rows:
            g[key(r)].append(r["confidence"] or 0.0)
        for k in sorted(g, key=str):
            v = sorted(g[k])
            hi = sum(1 for x in v if x >= 0.5)
            med = v[len(v) // 2]
            print(f"  {k!s:>10s}  n={len(v):4d}  중앙 {med:.3f}  "
                  f"conf>=0.5 {hi:4d} ({hi/len(v)*100:3.0f}%)")

    summarize(lambda r: r["verdict"], "판정별")
    summarize(lambda r: band(r["width_min_m"]), "폭 대역별 (width_min_m)")
    summarize(lambda r: "동명동" if r["in_emd"] else "회랑", "스코프별")
    summarize(lambda r: "짧음<30m" if (r["length_m"] or 0) < 30 else
                        "30-80m" if (r["length_m"] or 0) < 80 else "80m+", "길이별")

    allc = sorted(r["confidence"] or 0.0 for r in rows)
    hi = sum(1 for x in allc if x >= 0.5)
    print(f"\n전체: n={len(allc)} · 중앙 {allc[len(allc)//2]:.3f} · "
          f"conf>=0.5 {hi} ({hi/len(allc)*100:.0f}%)")
    print(f"→ {a.out} 에 저장. 이 표로 하이브리드 경계를 긋는다")


if __name__ == "__main__":
    main()
