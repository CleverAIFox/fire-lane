#!/usr/bin/env python3
"""ngii1k.py — 수치지형도 1:1,000 도엽을 하나로 합쳐 GeoPackage 로 낸다.

    uv run python src/etl/ngii1k.py <도엽디렉터리> [출력디렉터리]

국토정보플랫폼 1:1,000 은 도엽 하나가 456 x 555m 뿐이라 스코프를 덮으려면
12장 이상이 필요하다. 배포 형식이 두 가지다.

    2022년~   SHP  (N1A_A0010000.shp)      GDAL 로 바로 읽힌다
    ~2020년   NGI  (텍스트 포맷)            GDAL 드라이버가 없어 직접 파싱한다

같은 도엽이 여러 해로 있으면 최신을 쓴다. 좌표계는 둘 다 EPSG:5186 이라
지금 파이프라인과 같고 변환이 필요 없다.

레이어
    A0010000  도로경계    ★ 폭 산출 주 소스 → ngii1k_5186.gpkg
    A0020000  도로중심선     → ngii1k_center_5186.gpkg

1:5,000(NF_A_A01000)은 보행자 통로급 골목을 도로면으로 안 그린다.
동계천로 실측 11.8m 구간에 1:5,000 은 도로면이 아예 없었고 실폭도로는
1.30m 짜리 측구 조각만 있었다. 그 빈칸을 이 데이터가 메운다.
"""
import re
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Polygon, Point
import pandas as pd
from ngi import read_ngi  # noqa: E402

LAYERS = {"A0010000": ("ngii1k",        "도로경계"),
          "A0020000": ("ngii1k_center", "도로중심선"),
          "A0033320": ("ngii1k_walk",   "보도"),
          "A0080000": ("ngii1k_xsec",   "평면교차점"),
          "C0220000": ("ngii1k_light",  "가로등·보안등")}

# ★ 속성을 쓰는 레이어. .nda 에 있는데 그동안 통째로 버리고 있었다.
#   A0020000 도로폭은 측량 성과다. 우리 기하 계산과 독립이라 대조 검증에 쓴다.
#   일방통행 387건은 네비 라우팅 입력. node_link 에서 따로 구할 필요가 없다.
#   도로구분은 쓰지 않는다 — 관리주체(광역시도 98%)와 도시계획 규모(소로)가
#   한 필드에 섞여 있어 대조가 성립하지 않는다.
#   도로명도 쓰지 않는다 — 1:1,000 은 전부 빈 문자열이다. 매칭은 기하로만.
ATTR_LAYERS = {
    "A0020000": ["도로폭", "일방통행", "차로수", "분리대유무", "포장재질"],
    "A0033320": ["폭", "재질", "자전거도로유무", "종류"],
    # 평면교차점. 종류='평면교차점' 인 폴리곤이다.
    # 지금 XSEC_EXCL(노드에서 5m) 은 눈대중 반경인데 이건 실제 교차부 형상이다.
    "A0080000": ["명칭", "종류"],
    # 가로등·보안(방범)등 점. 측량 성과라 실제 폴 위치다.
    # gjcity CSV(지번 대표점)와 중앙 74.1m 어긋난다 — ±50m 원이 부족했다.
    "C0220000": ["구분"],
}
SHEET = re.compile(r"(3561\d{5})")
YEAR = re.compile(r"_(\d{4})\d{4}(?!\d)")   # _20201231 → 2020


# NGI 파서는 ngi.py 로 옮겼다. 기하만 읽던 것을 속성까지 읽게 하면서
# 파서가 두 벌이 되면 반드시 갈리므로 여기서는 import 만 한다.


# ── 도엽 수집 ─────────────────────────────────────────────────
def collect(src):
    """도엽번호 → (연도, 종류, 경로). 같은 도엽은 최신 연도만 남긴다."""
    best = {}
    for f in list(src.rglob("*.ngi")) + list(src.rglob("*.zip")) + list(src.rglob("*.shp")):
        m = SHEET.search(f.name) or SHEET.search(str(f.parent))
        if not m:
            continue
        sheet = m.group(1)
        y = YEAR.search(f.name)
        year = int(y.group(1)) if y else 0
        kind = "NGI" if f.suffix == ".ngi" else "SHP"
        # 같은 도엽·같은 연도면 SHP 를 쓴다. GDAL 이 읽으니 파싱 오차가 없다.
        cur = best.get(sheet)
        if cur is None or (year, kind == "SHP") > (cur[0], cur[1] == "SHP"):
            best[sheet] = (year, kind, f)
    return best


def read_sheet(kind, path, want):
    """레이어 → [(geom, attrs), ...]

    기하만 내던 것을 (기하, 속성) 튜플로 바꾼다. 속성이 필요 없는 레이어는
    빈 dict 가 붙을 뿐이라 호출부는 형태만 맞추면 된다.
    """
    if kind == "NGI":
        got = read_ngi(path, want)
        out = {}
        for k in want:
            recs = got.get(k, {}).get("records", [])
            keep = ATTR_LAYERS.get(k, [])
            out[k] = [(r["geom"], {a: r.get(a) for a in keep}) for r in recs]
        return out

    # SHP 경로. 2022년 이후 도엽은 속성이 컬럼으로 온다.
    out = {k: [] for k in want}
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            tmp = path.parent / f"_unz_{path.stem}"
            tmp.mkdir(exist_ok=True)
            z.extractall(tmp)
            base = tmp
    else:
        base = path.parent
    # 한 레이어가 N1A_(면) · N1L_(선) · N1P_(점) 으로 나뉘어 나온다.
    for k in want:
        keep = ATTR_LAYERS.get(k, [])
        for shp in sorted(base.rglob(f"*{k}.shp")):
            try:
                g = gpd.read_file(shp, encoding="cp949")
            except Exception:
                g = gpd.read_file(shp)
            if g.crs is None:
                g = g.set_crs(5186)
            g = g.to_crs(5186)
            cols = [a for a in keep if a in g.columns]
            for _, row in g.iterrows():
                out[k].append((row.geometry, {a: row.get(a) for a in cols}))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/processed")
    want = list(LAYERS)

    sheets = collect(src)
    if not sheets:
        print(f"도엽 없음: {src}")
        sys.exit(1)
    print(f"도엽 {len(sheets)}장")

    acc = {k: [] for k in want}
    for sheet, (year, kind, path) in sorted(sheets.items()):
        got = read_sheet(kind, path, want)
        for k, v in got.items():
            acc[k] += v
        print(f"  {sheet} {year} {kind:3}  " +
              " ".join(f"{k}={len(got[k]):4}" for k in want))

    out.mkdir(parents=True, exist_ok=True)
    for k, items in acc.items():
        key, label = LAYERS[k]
        if not items:
            print(f"  {label} 비어 있음 — 건너뜀")
            continue

        # 도로경계는 면, 나머지는 선. 선 조각은 면적의 0.1% 미만이라 무시한다.
        keep = ("Polygon" if key in ("ngii1k", "ngii1k_xsec")
                else "Point" if key == "ngii1k_light" else "LineString")
        items = [(g, a) for g, a in items
                 if g is not None and g.geom_type == keep]
        if not items:
            print(f"  {label} 해당 타입 없음 — 건너뜀")
            continue

        cols = {"src": ["ngii1k"] * len(items)}
        for a in ATTR_LAYERS.get(k, []):
            cols[a] = [attrs.get(a) for _, attrs in items]
        g = gpd.GeoDataFrame(cols, geometry=[geom for geom, _ in items], crs=5186)
        if keep == "Polygon":
            g["geometry"] = g.geometry.buffer(0)      # self-intersection 정리

        # 숫자 속성은 숫자로. 문자열로 두면 비교가 사전순이 되어
        # "10.0" < "9.0" 이 참이 된다.
        for a in ("도로폭", "폭", "차로수"):
            if a in g.columns:
                g[a] = pd.to_numeric(g[a], errors="coerce")

        # ★ 도로폭 0.500 은 결측이 아니라 '차량 통행 불가 통로' 코드다.
        #   스코프 내 7건 전수 확인(2026-08-14, 네이버 거리뷰·지도):
        #     무등산 등산로 4 · 볼라드+난간 1 · 건물 사이 통로 1 · 미제공 골목 1
        #   폭 소스에서는 빼되 사실은 플래그로 남긴다. 지우면 정보가 사라진다.
        #   verdict blocked 로 직접 매핑하지 않는다 — 우리 blocked 는
        #   '소방차가 못 지나감'이고 이건 '차도가 아님'이라 사유가 다르다.
        if "도로폭" in g.columns:
            g["non_vehicular"] = g["도로폭"] <= 0.6
            n_nv = int(g.non_vehicular.sum())
            g.loc[g.non_vehicular, "도로폭"] = None
            n_w = int(g["도로폭"].notna().sum())
            print(f"  {label} {len(g):5}  도로폭 {n_w} · 통행불가통로 {n_nv}")
        else:
            print(f"  {label} {len(g):5}")

        # ★ 기존 파일을 지우고 쓴다. GPKG 는 append 라 레이어명을 바꾸면
        #   옛 레이어가 남고, 다음에 누가 layer 지정 없이 읽으면 옛 데이터를
        #   집는다. light_count 가 0 인 채 파이프라인이 OK 를 찍던 것과 같은 함정이다.
        dst = out / f"{key}_5186.gpkg"
        dst.unlink(missing_ok=True)
        g.to_file(dst, driver="GPKG", layer=key)

if __name__ == "__main__":
    main()
