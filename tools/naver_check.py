#!/usr/bin/env python3
"""
tools/naver_check.py — 네이버 지도 대조 표본을 만든다 (폭 + 기초번호)

════════════════════════════════════════════════════════════════
현장 실측은 25구간 75점이다. 그걸로 1,101구간을 못 덮는다.
네이버 지도의 거리 측정 도구를 **준-실측**으로 쓸 수 있으면 전수 대조가
가능해진다. 이 스크립트는 그 가능성을 먼저 재보는 표본을 만든다.

두 가지를 한 번에 본다. 같은 구간을 한 번 열어서 둘 다 확인한다.

  A. 기초번호(seg_label)  우리가 붙인 "동명로25번길 9-14" 가
                          실제 도로명주소 체계와 맞는가
  B. 폭(width_min_m)      우리 산출 폭이 네이버 축척과 맞는가

── ★ 재는 위치를 명시하는 이유 ─────────────────────────────────
우리 width_min_m 은 **구간 내 표본들의 최솟값**이다. 네이버로 중점 한 곳을
재면 "그 지점의 폭"이라 서로 다른 것을 비교하게 된다. 구간이 균일하면
같지만 병목이 있으면 크게 벌어진다.

그래서 **가장 좁아 보이는 곳**을 재도록 지시한다. 그것이 wmin 의 정의와
같다. 눈으로 고르는 것이라 완벽하진 않지만, 중점을 재는 것보다 훨씬 맞다.

── ★ 우리 값을 CSV 에 넣지 않는다 ──────────────────────────────
먼저 보면 그 근처로 수렴한다. "지도가 3.5m 라니까 3.5m 근처겠지" 가 되면
대조의 의미가 사라진다. 우리 값은 봉인 파일에 따로 두고, 다 재고 난 뒤
tools/naver_join.py 로 합친다.

이 프로젝트가 §5-1(poi_store 오프셋)과 MASTER §4(nfa_compare)에서 두 번
겪은 것이다 — **보정에 쓴 자료는 그 순간부터 검증 수단이 아니다.**

── 표본 설계 ───────────────────────────────────────────────────
폭 대역별 층화. 판정 임계(3.0 / 7.0m) 근처를 두껍게 뽑는다.
12m 이상은 재봐야 판정이 안 바뀌므로 얇게.

길이 20m 미만은 뺀다. 네이버에서 두 점을 정확히 찍기 어렵다.

기초번호 검증을 위해 **같은 도로에서 연속된 구간을 여러 개** 뽑는다.
번호가 단조증가하는지 보면 체계 오류가 바로 드러난다.

실행:  uv run python tools/naver_check.py
산출:  data/field/naver_check.csv        ← 들고 다니며 채운다
       data/field/.naver_sealed.csv      ← 우리 값. 다 채우기 전에 열지 마라
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import csv

import geopandas as gpd
import pandas as pd
from pyproj import Transformer

from firelane.paths import FIELD, PROCESSED

CRS_M = "EPSG:5186"
SEED = 20260823            # ★ 고정. 재현 안 되면 표본 설계가 아니다
MIN_LEN = 20.0             # 이보다 짧으면 네이버에서 두 점 찍기가 어렵다

# 폭 대역별 표본 수. 판정 임계 근처를 두껍게.
BANDS = [
    ("<3",    None, 3.0,  10),   # blocked 후보
    ("3~5",   3.0,  5.0,  10),   # ★ 3.0 임계 바로 위. 제일 민감
    ("5~7",   5.0,  7.0,   8),   # ★ 7.0 임계 아래
    ("7~12",  7.0, 12.0,   6),
    ("12+",  12.0, None,   3),   # 재봐야 판정 안 바뀐다
]

_to3857 = Transformer.from_crs(4326, 3857, always_xy=True)


def naver(lon: float, lat: float, z: int = 19) -> str:
    """네이버 지도 링크. c= 는 EPSG:3857 환산값을 받는다(위경도 아님).

    ★ 거리뷰 딥링크는 만들 수 없다. 거리뷰는 좌표가 아니라 파노라마 ID 로
      열리고(p=wDEiG1JU...), ID 는 네이버 API 로만 얻는다. 지도가 그 위치로
      열리므로 거리뷰가 필요하면 화면에서 한 번 더 누른다.
    """
    x, y = _to3857.transform(lon, lat)
    return f"https://map.naver.com/p?c={x:.2f},{y:.2f},{z},0,0,0,dh"


def main() -> int:
    # ★ 임시 컬럼명에 밑줄을 쓰지 마라. itertuples() 가 밑줄로 시작하는
    #   컬럼을 _1, _2 로 바꿔버려서 r._band 가 AttributeError 가 된다.
    g = gpd.read_file(PROCESSED / "segments_5186.gpkg").to_crs(CRS_M)
    g["wq"] = pd.to_numeric(g.get("width_min_m"), errors="coerce")
    g["lenq"] = pd.to_numeric(g.get("length_m"), errors="coerce")
    g = g[g.lenq >= MIN_LEN].copy()
    print(f"후보 {len(g)}구간 (길이 {MIN_LEN}m 이상)")

    picks = []
    for name, lo, hi, k in BANDS:
        b = g[g.wq.notna()]
        if lo is not None:
            b = b[b.wq >= lo]
        if hi is not None:
            b = b[b.wq < hi]
        take = b.sample(n=min(k, len(b)), random_state=SEED)
        picks.append(take.assign(band=name))
        print(f"  {name:>5}  후보 {len(b):4d} → {len(take)}개")

    sel = pd.concat(picks)

    # ★ 기초번호 검증용. 표본에 든 도로 중 구간이 많은 것에서 연속 구간을
    #   추가로 뽑는다. 번호가 단조증가하는지 보면 체계 오류가 드러난다.
    top = sel.road_name.value_counts().head(3).index.tolist()
    extra = (g[g.road_name.isin(top) & ~g.seg_uid.isin(sel.seg_uid)]
             .sort_values(["road_name", "seg_label"])
             .groupby("road_name").head(3).assign(band="라벨연속"))
    sel = pd.concat([sel, extra])
    print(f"  라벨연속  {top} 에서 {len(extra)}개 추가")

    w = sel.to_crs(4326)
    rows, sealed = [], []
    for i, (r, r4) in enumerate(zip(sel.itertuples(), w.itertuples(), strict=True), 1):
        line = r4.geometry
        if line.geom_type != "LineString":
            line = max(line.geoms, key=lambda q: q.length)
        mid = line.interpolate(0.5, normalized=True)
        a, b2 = line.coords[0], line.coords[-1]

        rows.append({
            "no": i,
            "seg_uid": r.seg_uid,
            "band": r.band,
            "seg_label_ours": r.seg_label,          # ★ A 검증 대상. 가리지 않는다
            "road_name": r.road_name,
            "length_m": round(float(r.lenq), 1),
            "mid_lat": round(mid.y, 6), "mid_lon": round(mid.x, 6),
            "start_lat": round(a[1], 6), "start_lon": round(a[0], 6),
            "end_lat": round(b2[1], 6), "end_lon": round(b2[0], 6),
            "naver_mid": naver(mid.x, mid.y),
            "naver_start": naver(a[0], a[1], 18),
            # ── 여기부터 채운다 ──────────────────────────────
            # A. 기초번호
            "label_ok": "",          # Y / N — 네이버 건물번호 범위와 맞는가
            "label_seen": "",        # 실제로 보인 번호 범위 (예: 9-14, 11-17)
            # B. 폭. ★ 가장 좁아 보이는 곳을 재라. 중점이 아니다.
            "naver_w_m": "",         # 네이버 거리 도구 측정값 (m, 소수 2자리)
            "naver_w_at": "",        # 어디를 쟀나 (예: 시점에서 20m 지점)
            "confident": "",         # H / M / L — 두 점을 얼마나 정확히 찍었나
            "note": "",
        })
        sealed.append({"no": i, "seg_uid": r.seg_uid,
                       "width_min_m": r.wq, "verdict": r.verdict,
                       "width_src": r.width_src, "width_cov": r.width_cov,
                       "n_sample": getattr(r, "n_sample", "")})

    # ── 이웃 형상 ──────────────────────────────────────────────
    # ★ 미니맵에 대상 구간만 그리면 소용이 없다. 같은 도로 이름이 네 갈래에
    #   붙어 있는 곳이 있고(동계로13번길), 주변이 같이 보여야 어느 갈래인지
    #   안다. 반경 120m 안의 구간 형상을 같이 낸다.
    #   CSV 에 넣으면 열이 지저분해지므로 별도 JSON 이다.
    import json as _json
    NEAR_M = 120.0
    neigh = {}
    for r in sel.itertuples():
        buf = r.geometry.buffer(NEAR_M)
        near = g[g.geometry.intersects(buf)]
        near4 = near.to_crs(4326)
        neigh[r.seg_uid] = [
            [[round(x, 6), round(y, 6)] for x, y in
             (q.coords if q.geom_type == "LineString"
              else max(q.geoms, key=lambda z: z.length).coords)]
            for q in near4.geometry
        ]
    (FIELD / "naver_near.json").write_text(
        _json.dumps(neigh, ensure_ascii=False), encoding="utf-8")

    FIELD.mkdir(parents=True, exist_ok=True)
    dst = FIELD / "naver_check.csv"
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=list(rows[0]))
        cw.writeheader(); cw.writerows(rows)

    seal = FIELD / ".naver_sealed.csv"
    with seal.open("w", encoding="utf-8-sig", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=list(sealed[0]))
        cw.writeheader(); cw.writerows(sealed)

    print(f"\n→ {dst}  ({len(rows)}구간)")
    print(f"→ {FIELD/'naver_near.json'}  (미니맵용 이웃 형상)")
    print(f"→ {seal}  ★ 다 채우기 전에 열지 마라")
    print()
    print("  A 기초번호 — naver_mid 를 열고 그 구간 건물번호를 본다")
    print("     label_ok 에 Y/N · label_seen 에 실제 번호 범위")
    print("  B 폭 — ★ 구간에서 **가장 좁아 보이는 곳**을 재라. 중점이 아니다.")
    print("     우리 width_min_m 이 구간 내 최솟값이라 그것과 맞춰야 한다.")
    print("     naver_w_m 에 값 · naver_w_at 에 위치 · confident 에 H/M/L")
    print()
    print("  다 채우면:  uv run python tools/naver_join.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
