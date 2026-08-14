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

LAYERS = {"A0010000": ("ngii1k", "도로경계"),
          "A0020000": ("ngii1k_center", "도로중심선")}
SHEET = re.compile(r"(3561\d{5})")
YEAR = re.compile(r"_(\d{4})\d{4}(?!\d)")   # _20201231 → 2020


# ── NGI 파서 ──────────────────────────────────────────────────
def parse_ngi(path, want):
    """NGI 한 도엽에서 지정 레이어의 지오메트리를 뽑는다.

    포맷은 텍스트다. <LAYER_START> 로 레이어가 갈리고 <DATA> 아래
    $RECORD n / 타입 / 좌표수 / 좌표들 이 반복된다.
    """
    txt = path.read_bytes().decode("cp949", "replace").replace("\r", "")
    out = {k: [] for k in want}

    for block in txt.split("<LAYER_START>")[1:]:
        m = re.search(r'\$LAYER_NAME\n"([^"]+)"', block)
        if not m or m.group(1) not in want or "<DATA>" not in block:
            continue
        lay = m.group(1)
        for rec in block.split("<DATA>", 1)[1].split("$RECORD ")[1:]:
            ln = rec.split("\n")
            if len(ln) < 3:
                continue
            typ, i = ln[1].strip(), 2
            try:
                if typ == "POINT":
                    out[lay].append(Point(*map(float, ln[i].split()[:2])))
                elif typ == "LINESTRING":
                    n = int(ln[i]); i += 1
                    pts = [tuple(map(float, ln[i + k].split()[:2])) for k in range(n)]
                    if len(pts) >= 2:
                        out[lay].append(LineString(pts))
                elif typ == "POLYGON":
                    nparts = int(ln[i].split()[1]); i += 1
                    rings = []
                    for _ in range(nparts):
                        n = int(ln[i]); i += 1
                        pts = [tuple(map(float, ln[i + k].split()[:2])) for k in range(n)]
                        i += n
                        if len(pts) >= 3:
                            rings.append(pts)
                    if rings:
                        out[lay].append(Polygon(rings[0], rings[1:] or None))
            except (ValueError, IndexError):
                continue
    return out


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
    if kind == "NGI":
        return parse_ngi(path, want)
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
    # 도로경계는 면 파일에 도로면이, 선 파일에 경계선이 들어 있다. 둘 다 읽는다.
    for k in want:
        for shp in sorted(base.rglob(f"*{k}.shp")):
            g = gpd.read_file(shp)
            if g.crs is None:
                g = g.set_crs(5186)
            out[k] += list(g.to_crs(5186).geometry)
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
    for k, geoms in acc.items():
        key, label = LAYERS[k]
        if not geoms:
            print(f"  {label} 비어 있음 — 건너뜀")
            continue
        # 도로경계는 면만 쓴다. 선 조각은 면적의 0.1% 미만이라 무시한다.
        keep = "Polygon" if key == "ngii1k" else "LineString"
        geoms = [g for g in geoms if g.geom_type == keep]
        if not geoms:
            print(f"  {label} 해당 타입 없음 — 건너뜀")
            continue
        g = gpd.GeoDataFrame({"src": ["ngii1k"] * len(geoms)},
                             geometry=geoms, crs=5186)
        if keep == "Polygon":
            g["geometry"] = g.geometry.buffer(0)      # self-intersection 정리
        g = g[~g.geometry.is_empty]
        p = out / f"{key}_5186.gpkg"
        if p.exists():
            p.unlink()
        g.to_file(p, driver="GPKG")
        b = g.total_bounds
        print(f"  → {p.name}  {label} {len(g)}건  "
              f"x {b[0]:.0f}~{b[2]:.0f}  y {b[1]:.0f}~{b[3]:.0f}")


if __name__ == "__main__":
    main()
