#!/usr/bin/env python3
"""
sample_design.py — 실측 대상 구간을 뽑고 관측점 3점을 찍는다.

    python -m firelane.sample_design

── 왜 그냥 무작위가 아닌가 ────────────────────────────────────
무작위 20개를 뽑으면 silpok 소스(29구간, 전체의 2.7%)가 한 개도 안 걸릴 확률이
절반을 넘는다. 그러면 그 소스의 편향을 영영 모른다.
층화 무작위는 칸을 먼저 나누고 **각 칸 안에서는 무작위로** 뽑는다.
무작위를 버리는 게 아니라 무작위에 보험을 씌우는 것이다.

── 트랙 세 개를 절대 섞지 마라 ────────────────────────────────
A  층화 무작위 12구간   소스별 편향(bias) 추정용. 모집단을 대표해야 한다
B  의도 표본     8구간   판정이 뒤집힐 구간 교정용. 대표성이 없다
C  홀드아웃      5구간   측정만 하고 봉인. 최종 보고 전까지 열지 않는다

A 와 B 를 합쳐서 편향을 추정하면 추정치가 망가진다. B 는 "소스끼리 값이 다른
곳"만 고른 표본이라 그 오차 분포는 전체 분포가 아니기 때문이다.

C 가 필요한 이유: 소방서 지정 7구간은 이미 학습셋이다. 절대편차를 12.6 → 7.24 로
줄이는 데 그 표를 게이트로 썼으므로 더 이상 검증 수단이 아니다.
지금 외부 검증 수단은 0개이고 C 가 그 자리를 대신한다.

── 산출 ───────────────────────────────────────────────────────
data/field/sample_segments.csv    구간 25개 + 트랙 라벨
data/field/obs_points.csv         관측점 75개(구간당 3점) + 방위각
data/field/fieldsheet.md          출력해서 들고 나갈 야장
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from firelane.paths import PROCESSED, ROOT
from firelane.segkey import attach_seg_uid, bearing_at

# ★ 종전에는 `from paths import PROCESSED` 를 try/except 로 감싸고 실패하면
#   cwd 기준 경로를 만들었다. 스크립트 더미라 import 가 실제로 실패할 수
#   있었기 때문이다. 패키지가 된 지금 그 폴백은 **경로 정본을 둘로 만드는
#   버그**일 뿐이다 — cwd 가 다르면 다른 데이터를 읽고도 조용히 성공한다.

# ★ 불일치. paths.FIELD 는 FIRE_LANE_DATA 가 있으면 SSD 를 가리키는데
#   이 스크립트는 저장소 안(data/field)에 써왔고 그 산출물이 커밋돼 있다
#   (sample_segments.csv · obs_points.csv · fieldsheet.md).
#   여기서 paths.FIELD 로 갈아끼우면 야장이 조용히 SSD 로 이사한다.
#   패키지화는 동작을 안 바꾸는 작업이므로 종전 경로를 유지한다.
#   → 어느 쪽이 정본인지 정하는 것은 별건. DECISIONS 에 올릴 것.
FIELD = ROOT / "data" / "field"
CRS_M = "EPSG:5186"

SEED = 20260814                 # 고정. 재현 안 되면 표본 설계가 아니다
N_A, N_B, N_C = 12, 8, 5
THRESH = (3.0, 7.0)             # 판정 임계. segments.py 와 같아야 한다
NEAR = 0.7                      # 임계 ±0.7m 안이면 "뒤집힐 수 있는 구간"
DISAGREE_MIN = 1.0              # 소스 간 차이 1m 초과
MIN_LEN = 15.0                  # 너무 짧으면 3점을 못 찍는다
OBS_FRAC = (0.15, 0.50, 0.85)   # 관측점 위치(구간장 비율)

# ★ 구간당 1점이 아니라 3점인 이유
#   1점만 재면 "소스 편향"과 "구간 안에서 폭이 원래 변하는 것"이 뒤섞여
#   분리가 안 된다. 3점이면 구간 랜덤효과 u_i 와 지점 오차 e_ij 를 나눌 수 있다.
#   레이저로는 한 지점당 1분이라 25구간 × 3점이 반나절이면 끝난다.


def _band(w: float | None) -> str:
    if w is None or pd.isna(w):
        return "na"
    if w < THRESH[0]:
        return "lt3"
    if w < THRESH[1]:
        return "3to7"
    return "ge7"


def _near_threshold(w) -> bool:
    if w is None or pd.isna(w):
        return False
    return any(abs(w - t) <= NEAR for t in THRESH)


def main() -> None:
    # ★ 여기 있던 rng = np.random.default_rng(SEED) 는 삭제했다. 만들어
    #   놓고 한 번도 쓰지 않았다. 실제 추출은 전부 pandas 의
    #   random_state=SEED 를 쓰므로 재현성은 그쪽이 보장한다.
    #   쓰지 않는 난수원이 남아 있으면 "시드가 두 개인가" 를 의심하게 된다.
    g = gpd.read_file(PROCESSED / "segments.geojson").to_crs(CRS_M)
    # segments.py 가 이미 seg_uid 를 붙였으면 그것이 정본이다.
    # 여기서 다시 계산하면 규칙이 두 군데가 되어 언젠가 어긋난다.
    if "seg_uid" not in g.columns:
        print("  ! segments.geojson 에 seg_uid 없음 — 자체 계산으로 대체")
        g = attach_seg_uid(g)
    g["band"] = g.width_min_m.map(_band)
    g["near"] = g.width_min_m.map(_near_threshold)
    g["usage"] = pd.to_numeric(g.get("route_usage"), errors="coerce").fillna(0)
    g["disagree"] = pd.to_numeric(g.get("width_disagree_m"), errors="coerce")

    # 실측이 물리적으로 가능한 것만. 길이가 짧으면 3점이 서로 겹친다.
    pool = g[(g.length_m >= MIN_LEN) & (g.width_src.notna()) & (g.band != "na")].copy()
    print(f"모집단 {len(g)} → 실측 가능 {len(pool)}")

    # ── 트랙 B 먼저 ───────────────────────────────────────────
    # A 보다 먼저 뽑는다. B 의 모집단이 좁아서(94구간 수준) 나중에 뽑으면
    # A 가 그중 일부를 가져가 버려 B 를 채우지 못할 수 있다.
    bpool = pool[pool.near & (pool.disagree > DISAGREE_MIN)]
    print(f"트랙 B 모집단(임계 ±{NEAR}m & 불일치 >{DISAGREE_MIN}m) {len(bpool)}")
    # 통행량 상위 2배수를 만든 뒤 그 안에서 무작위. 상위 8개를 그냥 자르면
    # 특정 도로 한 곳에 몰린다.
    bcand = bpool.sort_values("usage", ascending=False).head(N_B * 2)
    B = bcand.sample(n=min(N_B, len(bcand)), random_state=SEED)

    rest = pool[~pool.seg_uid.isin(B.seg_uid)]

    # ── 트랙 A 층화 무작위 ────────────────────────────────────
    # 층 = width_src × 폭대역. 각 층에 최소 1개를 보장한 뒤 남는 몫을
    # 층 크기에 비례해 배분한다(비례배분).
    strata = rest.groupby(["width_src", "band"])
    keys = [k for k, v in strata if len(v) > 0]
    alloc = {k: 1 for k in keys}
    left = N_A - len(alloc)
    if left < 0:
        # 층이 12개보다 많으면 큰 층부터 살린다
        keys = sorted(keys, key=lambda k: -len(strata.get_group(k)))[:N_A]
        alloc = {k: 1 for k in keys}
        left = 0
    if left > 0:
        sizes = np.array([len(strata.get_group(k)) for k in keys], dtype=float)
        share = np.floor(sizes / sizes.sum() * left).astype(int)
        for i, k in enumerate(keys):
            alloc[k] += int(share[i])
        # 반올림 잔여는 큰 층부터
        for k in sorted(keys, key=lambda k: -len(strata.get_group(k))):
            if sum(alloc.values()) >= N_A:
                break
            alloc[k] += 1

    A_parts = []
    for k, n in alloc.items():
        grp = strata.get_group(k)
        A_parts.append(grp.sample(n=min(n, len(grp)), random_state=SEED))
    A = pd.concat(A_parts)

    # ── 트랙 C 홀드아웃 ───────────────────────────────────────
    # A 와 같은 방식(층화 아님, 단순 무작위)으로 뽑는다.
    # C 는 대표성보다 "손대지 않았다"가 중요하다.
    rest2 = rest[~rest.seg_uid.isin(A.seg_uid)]
    C = rest2.sample(n=min(N_C, len(rest2)), random_state=SEED + 1)

    A = A.assign(track="A"); B = B.assign(track="B"); C = C.assign(track="C")
    sel = pd.concat([A, B, C])
    assert sel.seg_uid.is_unique, "트랙 간 중복. 표본이 겹치면 분석이 무효다"

    print("\n[트랙 A 층화 배분]")
    print(A.groupby(["width_src", "band"]).size().to_string())
    print(f"\n선정 {len(sel)}구간  A {len(A)} · B {len(B)} · C {len(C)}")

    # ── 관측점 3점 ────────────────────────────────────────────
    rows = []
    sel_w = sel.to_crs(4326)
    # ★ sel 과 sel_w 는 같은 프레임을 to_crs 한 것이라 행 수가 같다.
    #   다르면 관측점이 엉뚱한 구간에 찍히므로 죽어야 한다.
    for (_, r), (_, r4) in zip(sel.iterrows(), sel_w.iterrows(), strict=True):
        for i, frac in enumerate(OBS_FRAC, start=1):
            off = r.geometry.length * frac
            p4 = r4.geometry.interpolate(frac, normalized=True)
            rows.append({
                "obs_id": f"{r.seg_uid}#{i}",
                "seg_uid": r.seg_uid,
                "track": r.track,
                "seq": i,
                "offset_m": round(off, 1),
                "bearing_deg": round(bearing_at(r.geometry, off), 1),
                "lon": round(p4.x, 6),
                "lat": round(p4.y, 6),
                "road_name": r.get("road_name"),
                "width_src": r.width_src,
                "width_min_m": r.width_min_m,
                "width_max_m": r.width_max_m,
                "verdict": r.verdict,
                "landmark": "",          # 현장에서 채운다
                "measured_m": "",        # 현장에서 채운다
                "kind": "",              # wall|curb|passable|corner
            })
    obs = pd.DataFrame(rows)

    FIELD.mkdir(parents=True, exist_ok=True)
    scols = ["seg_uid", "track", "seg_id", "road_name", "width_src", "band",
             "width_min_m", "width_max_m", "disagree", "verdict", "usage", "length_m"]
    sel[[c for c in scols if c in sel.columns]].to_csv(
        FIELD / "sample_segments.csv", index=False, encoding="utf-8-sig")
    obs.to_csv(FIELD / "obs_points.csv", index=False, encoding="utf-8-sig")

    # ── 야장 ──────────────────────────────────────────────────
    # ★ 트랙 C 는 야장에 폭 예측값을 찍지 않는다. 현장에서 우리 값을 보면
    #   그 값에 끌린 측정이 나온다(확증 편향). C 는 "그냥 재고 오는" 구간이다.
    L = ["# 실측 야장", "",
         f"시드 {SEED} · 구간 {len(sel)} · 관측점 {len(obs)}", "",
         "규칙", "",
         "- 관측점마다 **기준 지물을 글로 적고 사진**을 남긴다. GPS 는 보조다(오차 5~15m)",
         "- 측정 종류를 반드시 적는다: wall(담~담) / curb(연석~연석) / passable(통행폭) / corner(코너)",
         "- 소스값 3종(ngii1k·ngii·silpok)을 같은 지점에서 함께 기록한다",
         "- **트랙 C 는 우리 예측값을 보지 않고 잰다**", "",
         "---", ""]
    for track in ("A", "B", "C"):
        t = sel[sel.track == track]
        L += [f"## 트랙 {track} — {len(t)}구간", ""]
        for _, r in t.iterrows():
            head = f"### {r.seg_uid} · {r.get('road_name') or '(도로명 없음)'}"
            L.append(head)
            if track == "C":
                L.append(f"- 길이 {r.length_m:.0f}m · **예측값 비공개(홀드아웃)**")
            else:
                wmax = "미산출" if pd.isna(r.width_max_m) else f"{r.width_max_m:.2f}"
                L.append(f"- 길이 {r.length_m:.0f}m · 소스 {r.width_src} · "
                         f"폭 {r.width_min_m:.2f}~{wmax}m · 판정 {r.verdict}")
            for _, o in obs[obs.seg_uid == r.seg_uid].iterrows():
                L.append(f"  - `{o.obs_id}` {o.offset_m}m · 방위 {o.bearing_deg}° · "
                         f"({o.lat}, {o.lon})  실측 ____ m  종류 ____  지물 ______")
            L.append("")
    (FIELD / "fieldsheet.md").write_text("\n".join(L), encoding="utf-8")

    print(f"\n→ {FIELD/'sample_segments.csv'}")
    print(f"→ {FIELD/'obs_points.csv'}")
    print(f"→ {FIELD/'fieldsheet.md'}")
    print("\n★ 트랙 C 5구간은 분석에 쓰지 마라. 열면 외부 검증 수단이 다시 0이 된다.")


if __name__ == "__main__":
    main()
