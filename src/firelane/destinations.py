"""
destinations.py — 내비 목적지 검색 색인. 상가 · 주소/건물 · 관공서/학교 셋을 하나로.

IN    processed/poi_store.geojson · processed/navi_build.csv ·
      processed/navi_jibun.csv · processed/civil_office.geojson
OUT   web/data/dest.geojson   (publish_web 이 부른다 — 여기서는 쓰지 않고 표를 돌려준다)
PARAM 열 번호 — 내비게이션용DB 활용방법 붙임 1 · 2 (DECISIONS §181-1)

★ 2026-09-17 (PLAN 「목적지 검색 — 주소 · 건물명 · 관공서」 · DECISIONS §181).
  `poi.geojson` 상가 2,077 만 색인이라 법원 · 구청 · 학교 · 아파트 · 주소가 안 나왔다.

★ 스키마는 `poi.geojson` 과 같다(name · cat · sub · addr) + `alt`(지번) · `src`(원천).
  `search.ts` 가 옛 필드만 읽어도 돈다.

★ 좌표 규칙 — 출입구(c25 · c26) → 없으면 건물중심점(c23 · c24) → 둘 다 없으면 **뺀다**.
  비공개 · 공개제한 건물은 좌표가 빈 값으로 온다. 빼는 수를 돌려준다 — 조용히 줄지 않는다.
  도착점은 여기서 정하지 않는다. 앱이 `snap` 으로 도로 위 점으로 바꾼다.

★ `c` 번호는 헤더 없는 `|` 텍스트를 ingest 가 c00 … 로 이름 붙인 것이다.
  이름을 지어내지 않는다(ingest text_table). 뜻은 아래 상수에만 적는다.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

# ── 내비게이션용DB 건물(33열) — 활용방법 붙임 1 ───────────────────────
B_SIGUNGU, B_ROAD, B_UNDER, B_MAIN, B_SUB = "c02", "c05", "c06", "c07", "c08"
B_PK, B_NAME, B_USE, B_APT, B_DETAIL = "c10", "c11", "c12", "c17", "c19"
B_CX, B_CY, B_EX, B_EY = "c23", "c24", "c25", "c26"
B_EMD = "c03"
# ── 내비게이션용DB 지번(20열) — 활용방법 붙임 2 ───────────────────────
J_EMD, J_RI, J_SAN, J_MAIN, J_SUB, J_PK = "c03", "c04", "c05", "c06", "c07", "c18"

CRS_NAVI = 5179            # GRS80 UTM-K
APT = {"1": "아파트", "2": "연립·다세대"}
COLS = ["name", "cat", "sub", "addr", "alt", "src", "geometry"]


def _num(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce")
    return v.where(v > 0)          # 0 · 빈 값 = 좌표 없음


def _txt(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip()


def road_addr(d: pd.DataFrame) -> pd.Series:
    """`동구 필문대로 230-1` · 지하는 `지하 ` 를 붙인다."""
    sub = _txt(d[B_SUB]).where(~_txt(d[B_SUB]).isin(["", "0"]), "")
    num = _txt(d[B_MAIN]) + sub.map(lambda x: f"-{x}" if x else "")
    under = _txt(d[B_UNDER]).map(lambda x: "지하 " if x == "1" else "")
    return _txt(d[B_SIGUNGU]) + " " + _txt(d[B_ROAD]) + " " + under + num


def jibun_by_pk(j: pd.DataFrame) -> pd.Series:
    """건물관리번호 → `동명동 18-12 · 동명동 18-11`. 한 건물에 지번이 여럿이다."""
    sub = _txt(j[J_SUB]).where(~_txt(j[J_SUB]).isin(["", "0"]), "")
    san = _txt(j[J_SAN]).map(lambda x: "산" if x == "1" else "")
    ri = _txt(j[J_RI]).map(lambda x: f" {x}" if x else "")
    lot = _txt(j[J_EMD]) + ri + " " + san + _txt(j[J_MAIN]) + sub.map(lambda x: f"-{x}" if x else "")
    t = pd.DataFrame({"pk": _txt(j[J_PK]), "lot": lot})
    return t.drop_duplicates().groupby("pk", sort=True)["lot"].agg(" · ".join)


def from_navi(build: pd.DataFrame, jibun: pd.DataFrame | None = None) -> tuple[gpd.GeoDataFrame, dict]:
    """내비게이션용DB 건물 → 목적지. 이름이 없는 건물은 **주소 자체가 이름**이다(cat `주소`)."""
    d = build.copy()
    x = _num(d[B_EX]).fillna(_num(d[B_CX]))
    y = _num(d[B_EY]).fillna(_num(d[B_CY]))
    has_entr = _num(d[B_EX]).notna() & _num(d[B_EY]).notna()
    ok = x.notna() & y.notna()
    stats = {"rows": len(d), "entrance": int((has_entr & ok).sum()),
             "center": int((~has_entr & ok).sum()), "no_coord": int((~ok).sum())}
    d, x, y = d[ok], x[ok], y[ok]

    nm, det = _txt(d[B_NAME]), _txt(d[B_DETAIL])
    name = nm.where(det.eq("") | det.eq(nm), (nm + " " + det).str.strip())
    addr = road_addr(d)
    named = name.ne("")
    apt = _txt(d[B_APT]).map(APT)
    alt = _txt(d[B_PK]).map(jibun_by_pk(jibun)) if jibun is not None else None
    out = gpd.GeoDataFrame({
        "name": name.where(named, addr),
        "cat": named.map({True: "건물", False: "주소"}),
        "sub": apt.fillna(_txt(d[B_USE])),
        "addr": addr + " (" + _txt(d[B_EMD]) + ")",
        "alt": alt.fillna("") if alt is not None else "",
        "src": "build",
    }, geometry=gpd.points_from_xy(x, y), crs=CRS_NAVI).to_crs(4326)
    stats["named"] = int(named.sum())
    # ★ 한 도로명주소에 건물이 여럿이다(본건물 · 부속). 검색 결과에 같은 줄이 겹쳐 뜨므로
    #   이름 · 주소가 같으면 하나만 남긴다 — 지번이 붙은 행(본건물)을 먼저, 그다음 건물관리번호 순.
    #   뺀 수를 센다.
    out["_pk"] = _txt(d[B_PK]).values
    out = out.sort_values(["name", "addr", "alt", "_pk"], key=lambda s: s.eq("") if s.name == "alt" else s,
                          kind="stable")
    n0 = len(out)
    out = out.drop_duplicates(["name", "addr"], keep="first")
    stats["same_addr"] = n0 - len(out)
    return out[COLS], stats


def from_civil(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """민원행정기관 전자지도 → 목적지. 학교는 `학교`, 나머지는 `관공서`."""
    kind = _txt(g["유형"])
    return gpd.GeoDataFrame({
        "name": _txt(g["기관명"]),
        "cat": kind.map(lambda k: "학교" if k == "학교" else "관공서"),
        "sub": _txt(g["상세분류"]),
        "addr": _txt(g["도로명주소"]),
        "alt": "", "src": "civil",
    }, geometry=g.geometry.values, crs=g.crs).to_crs(4326)[COLS]


def from_store(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """상가 — `publish_web` 이 이미 거른 poi(name · cat · sub · addr)를 그대로 받는다."""
    o = g.to_crs(4326).copy()
    o["alt"], o["src"] = "", "store"
    return o[COLS]


def build_index(store: gpd.GeoDataFrame, build: pd.DataFrame, jibun: pd.DataFrame,
                civil: gpd.GeoDataFrame, clip) -> tuple[gpd.GeoDataFrame, dict]:
    """세 원천을 합쳐 `clip`(4326 도형) 안만 남긴다. 이름 없는 행은 뺀다."""
    b, st = from_navi(build, jibun)
    parts = {"store": from_store(store), "build": b, "civil": from_civil(civil)}
    stats = {"navi": st}
    kept = []
    for k, p in parts.items():
        p = p[p.within(clip) & p["name"].ne("")]
        stats[k] = len(p)
        kept.append(p)
    out = gpd.GeoDataFrame(pd.concat(kept, ignore_index=True), crs=4326)
    # ★ 결정적 순서 — 같은 입력에 같은 산출물(web/data 계보 지문)
    out = out.sort_values(["src", "name", "addr"], kind="stable").reset_index(drop=True)
    stats["total"] = len(out)
    return out, stats
