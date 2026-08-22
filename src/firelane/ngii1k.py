#!/usr/bin/env python3
"""ngii1k.py — 수치지형도 1:1,000 도엽을 하나로 합쳐 GeoPackage 로 낸다.

    python -m firelane.ngii1k <도엽디렉터리> [출력디렉터리]

도엽 하나가 456 x 555m 뿐이라 스코프를 덮으려면 여러 장이 필요하다.
배포 형식이 셋이다.

    V-WORLD        중첩 zip → SHP   2026-03   74도엽   ★ 현재 주 소스
    국토정보플랫폼  SHP              2022년~
    국토정보플랫폼  NGI 텍스트        ~2020년   GDAL 드라이버가 없어 직접 파싱

좌표계는 전부 EPSG:5186 이라 변환이 필요 없다(V-WORLD 는 .prj 명시).

레이어
    A0010000  도로경계    ★ 폭 산출 주 소스 → ngii1k_5186.gpkg
    A0020000  도로중심선     → ngii1k_center_5186.gpkg   (속성 보유)
    A0033320  보도           → ngii1k_walk_5186.gpkg
    A0080000  평면교차점      → ngii1k_xsec_5186.gpkg
    C0220000  가로등·보안등   → ngii1k_light_5186.gpkg

1:5,000(NF_A_A01000)은 보행자 통로급 골목을 도로면으로 안 그린다.
동계천로 실측 11.8m 구간에 1:5,000 은 도로면이 아예 없었고 실폭도로는
1.30m 짜리 측구 조각만 있었다. 그 빈칸을 이 데이터가 메운다.

── V-WORLD 전환 (2026-08-17) ──────────────────────────────────
1. 압축이 중첩이다.
       vworld_map1k_gjdonggu_20260307.zip
         └ 356161406.zip … 74개       ← 도엽 zip. 이름에만 도엽번호가 있다
             └ N1A_A0010000.shp …     ← 평평하다. 하위 폴더가 없다
   바깥 zip 이름에 도엽번호가 없어서 예전 collect() 는 0장을 찾았다.

2. ★ 압축을 raw 에 풀지 않는다.
   예전 read_sheet 는 `path.parent/_unz_*` 에 풀었다. 지금 raw 는 외장 SSD 이고
   MASTER 18-1 이 '절대 수정 안 함'으로 못 박았다. 74도엽이면 raw 안에 디렉터리
   74개가 생기고 18-3 게이트가 전부 _quarantine 대상으로 잡는다.
   전부 .work/ 아래에서 푼다.

3. ★ 도로명이 채워졌다.
   구 국토정보플랫폼 1:1,000 은 A0020000 도로명이 전부 빈 문자열이라
   "매칭은 기하로만" 이라고 적어 두었다. V-WORLD 는 채워져 있다(필문대로 등).
   전제가 바뀌었으므로 속성으로 받는다. 다만 seg_uid 해시 입력이 바뀔 수
   있으니 베이스라인 diff 의 공간 폴백으로 확인할 것(MASTER 18-8-1).

4. 자동차전용 컬럼이 새로 생겼다.
   도로구분은 여전히 쓰지 않는다 — 관리주체(광역시도/일반국도)와 도시계획
   규모가 한 필드에 섞여 있다. 자동차전용은 값이 하나뿐이라 대조가 성립한다.

5. A0010000 은 UFID + geometry 뿐이다. 속성이 없다. 폭은 기하로만 낸다.
   같은 코드로 N1A(면)·N1L(선)이 둘 다 오므로 geom_type 으로 거른다.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from firelane.paths import ROOT

WORK = ROOT / ".work" / "ngii1k"          # .gitignore 에 .work/ 가 있다

LAYERS = {"A0010000": ("ngii1k",        "도로경계"),
          "A0020000": ("ngii1k_center", "도로중심선"),
          "A0033320": ("ngii1k_walk",   "보도"),
          "A0080000": ("ngii1k_xsec",   "평면교차점"),
          "C0220000": ("ngii1k_light",  "가로등·보안등")}

# 속성을 쓰는 레이어. 나머지는 기하만 쓴다.
#   A0020000 도로폭은 측량 성과다. 우리 기하 계산과 독립이라 대조 검증에 쓴다.
#   일방통행은 라우팅 입력. node_link 에서 따로 구할 필요가 없다.
#   도로구분은 쓰지 않는다 — 관리주체와 도시계획 규모가 한 필드에 섞여 있다.
ATTR_LAYERS = {
    "A0020000": ["도로폭", "일방통행", "차로수", "분리대유무", "포장재질",
                 "도로명", "자동차전용"],
    "A0033320": ["폭", "재질", "자전거도로유무", "종류"],
    # 평면교차점. XSEC_EXCL(노드에서 5m)은 근거 없는 반경인데 이건 실제 형상이다.
    "A0080000": ["명칭", "종류"],
    # 가로등·보안(방범)등 점. 측량 성과라 실제 폴 위치다.
    # 등 수·관리번호는 gjcity 가 정본이고 위치는 이쪽이 정본이다.
    "C0220000": ["구분"],
}

# 레이어별로 채택할 기하 타입. 같은 코드로 N1A(면)·N1L(선)·N1P(점)이
# 함께 오므로 반드시 하나를 골라야 한다.
# ★ 보도 A0033320 은 V-WORLD 에서 N1A(면)로만 온다. 구 코드가 선으로 걸러
#   보도 레이어가 통째로 비는 것을 픽스처에서 잡았다(2026-08-17).
GEOM_OF = {"ngii1k":       "Polygon",
           "ngii1k_center": "LineString",
           "ngii1k_walk":  "Polygon",
           "ngii1k_xsec":  "Polygon",
           "ngii1k_light": "Point"}

SHEET = re.compile(r"(3561\d{5})")
YEAR = re.compile(r"_(\d{4})\d{4}(?!\d)")     # _20201231 → 2020


def _read_ngi(path, want):
    """NGI 텍스트 파서는 구 도엽 전용이라 지연 로드한다.

    모듈 최상단에서 import 하면 ngi.py 를 retire 하는 순간 이 파일 전체가
    import 단계에서 죽는다. 구 도엽으로 베이스라인을 재현할 여지를 남긴다.
    """
    from firelane.ngi import read_ngi
    return read_ngi(path, want)


# ── 준비: 중첩 zip 을 .work 로 한 겹 편다 ─────────────────────
def stage(src: Path) -> Path:
    """도엽번호 없는 zip 안에 도엽 zip 이 있으면 .work 로 꺼낸다.

    raw 를 건드리지 않는다. 이미 꺼내 둔 것은 건너뛴다.
    """
    WORK.mkdir(parents=True, exist_ok=True)
    # ★ src 가 디렉터리일 수도 파일일 수도 있다.
    #   ingest 는 sources.yaml 의 file 값을 그대로 넘기므로 zip 파일 경로가 온다.
    #   손으로 돌릴 때는 도엽 디렉터리를 준다. 둘 다 받는다.
    # src 는 파일 · 디렉터리 · 목록 셋 다 온다(대장 file 이 글롭이면 목록).
    if isinstance(src, (list, tuple)):
        cands = [Path(x) for x in src]
    else:
        cands = [src] if src.is_file() else sorted(src.rglob("*.zip"))
    for z in cands:
        if z.suffix.lower() != ".zip":
            continue
        if SHEET.search(z.name):
            continue                       # 도엽 zip 자체. 여기서 풀 것이 없다
        try:
            with zipfile.ZipFile(z) as zf:
                inner = [n for n in zf.namelist()
                         if n.lower().endswith(".zip")
                         and SHEET.search(Path(n).name)]
                if not inner:
                    # ★ NGI 판은 한 겹이다. 356160900.ngi + .nda 가 직접 들어 있다.
                    #   SHP 판(도엽 zip 중첩)과 구조가 다르므로 따로 편다.
                    flat = [n for n in zf.namelist()
                            if n.lower().endswith((".ngi", ".nda"))
                            and SHEET.search(Path(n).name)]
                    if not flat:
                        continue
                    got = 0
                    for n in flat:
                        dst = WORK / Path(n).name
                        if not dst.exists():
                            dst.write_bytes(zf.read(n))
                            got += 1
                    ns = {SHEET.search(Path(n).name).group(1) for n in flat}
                    print(f"  묶음 {z.name} → NGI 도엽 {len(ns)}장"
                          f" (새로 편 것 {got} 파일)")
                    continue
                got = 0
                for n in inner:
                    dst = WORK / Path(n).name
                    if not dst.exists():
                        dst.write_bytes(zf.read(n))
                        got += 1
                print(f"  묶음 {z.name} → 도엽 {len(inner)}장"
                      f" (새로 편 것 {got} · 캐시 {len(inner) - got})")
        except zipfile.BadZipFile:
            print(f"  ! zip 이 아니다: {z.name}")
    return WORK


# ── 도엽 수집 ─────────────────────────────────────────────────
def collect(src: Path) -> dict:
    """도엽번호 → (연도, 종류, 경로). 같은 도엽은 최신 연도만 남긴다."""
    stage(src)
    best: dict[str, tuple] = {}
    _dirs = [x for x in (src if isinstance(src, (list, tuple)) else [src])
             if Path(x).is_dir()]
    roots = [WORK] + [Path(x) for x in _dirs]
    for root in roots:
        if not root.exists():
            continue
        for f in (list(root.rglob("*.ngi")) + list(root.rglob("*.zip"))
                  + list(root.rglob("*.shp"))):
            m = SHEET.search(f.name) or SHEET.search(str(f.parent))
            if not m:
                continue
            sheet = m.group(1)
            y = YEAR.search(f.name)
            year = int(y.group(1)) if y else 0
            kind = "NGI" if f.suffix == ".ngi" else "SHP"
            cur = best.get(sheet)
            # 같은 도엽·같은 연도면 SHP 를 쓴다. GDAL 이 읽으니 파싱 오차가 없다.
            if cur is None or (year, kind == "SHP") > (cur[0], cur[1] == "SHP"):
                best[sheet] = (year, kind, f)
    return best


def read_sheet(kind: str, path: Path, want: list) -> dict:
    """레이어 → [(geom, attrs), ...]"""
    if kind == "NGI":
        got = _read_ngi(path, want)
        out = {}
        for k in want:
            recs = got.get(k, {}).get("records", [])
            keep = ATTR_LAYERS.get(k, [])
            out[k] = [(r["geom"], {a: r.get(a) for a in keep}) for r in recs]
        return out

    out: dict[str, list] = {k: [] for k in want}
    if path.suffix == ".zip":
        # ★ raw 가 아니라 .work 아래에 푼다.
        base = WORK / f"_unz_{path.stem}"
        if not base.exists():
            base.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path) as z:
                z.extractall(base)
    else:
        base = path.parent

    for k in want:
        keep = ATTR_LAYERS.get(k, [])
        # 한 레이어가 N1A_(면) · N1L_(선) · N1P_(점) 으로 나뉘어 나온다.
        for shp in sorted(base.rglob(f"*{k}.shp")):
            try:
                g = gpd.read_file(shp)          # .cpg 가 있으면 GDAL 이 따른다
            except Exception:
                g = gpd.read_file(shp, encoding="cp949")
            if g.crs is None:
                g = g.set_crs(5186)
            g = g.to_crs(5186)
            cols = [a for a in keep if a in g.columns]
            recs = g[cols].to_dict("records") if cols else [{}] * len(g)
            out[k] += list(zip(g.geometry, recs))
    return out


# ── 프레임 조립 ───────────────────────────────────────────────
def build(layer: str, items: list):
    """(geom, attrs) 목록 → GeoDataFrame. ingest 와 공유한다.

    ★ 예전에는 이 로직이 main() 에만 있고 ingest 는 따로 짰다. 그래서 ingest 가
      속성을 통째로 버렸고 결국 사람이 이 스크립트를 손으로 돌려야 했다.
      같은 산출을 두 곳에서 만들면 반드시 갈린다.
    """
    key = LAYERS[layer][0]
    keep = GEOM_OF[key]
    raw_n = len(items)
    kinds = [g.geom_type for g, _ in items if g is not None]
    items = [(g, a) for g, a in items if g is not None and g.geom_type == keep]
    if raw_n and not items:
        # ★ 읽기는 했는데 타입 필터로 전멸했다. 소스 형식이 바뀐 것이다.
        #   여기서 안 세우면 레이어 하나가 통째로 빈 채 파이프라인이 OK 를 찍는다.
        import collections
        got = collections.Counter(t for t in kinds if t)
        raise ValueError(
            f"{layer}({key}) 기대 {keep} 인데 0건이다. 실제: {dict(got)}. "
            f"GEOM_OF 를 고쳐라")
    if not items:
        return None

    cols = {"src": ["ngii1k"] * len(items)}
    for a in ATTR_LAYERS.get(layer, []):
        cols[a] = [attrs.get(a) for _, attrs in items]
    g = gpd.GeoDataFrame(cols, geometry=[geom for geom, _ in items], crs=5186)
    if keep == "Polygon":
        g["geometry"] = g.geometry.buffer(0)        # self-intersection 정리

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
        g.loc[g.non_vehicular, "도로폭"] = None
    return g


def summary(layer: str, g) -> str:
    label = LAYERS[layer][1]
    s = f"  {label} {len(g):6}"
    if "도로폭" in g.columns:
        s += (f"  도로폭 {int(g['도로폭'].notna().sum())}"
              f" · 통행불가통로 {int(g.non_vehicular.sum())}")
    if "도로명" in g.columns:
        n = int(g["도로명"].fillna("").astype(str).str.strip().ne("").sum())
        s += f" · 도로명 {n}"
    return s


def write(g, key: str, out: Path) -> Path:
    # ★ 기존 파일을 지우고 쓴다. GPKG 는 append 라 레이어명을 바꾸면 옛 레이어가
    #   남고, 다음에 누가 layer 지정 없이 읽으면 옛 데이터를 집는다.
    #   light_count 가 0 인 채 파이프라인이 OK 를 찍던 것과 같은 함정이다.
    dst = out / f"{key}_5186.gpkg"
    dst.unlink(missing_ok=True)
    g.to_file(dst, driver="GPKG", layer=key)
    return dst


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/processed")
    want = list(LAYERS)

    sheets = collect(src)
    if not sheets:
        print(f"도엽 없음: {src}")
        return 1
    print(f"도엽 {len(sheets)}장")

    acc = {k: [] for k in want}
    empty = []
    for sheet, (year, kind, path) in sorted(sheets.items()):
        got = read_sheet(kind, path, want)
        for k, v in got.items():
            acc[k] += v
        if not got["A0010000"]:
            empty.append(sheet)
        print(f"  {sheet} {year or '----'} {kind:3}  " +
              " ".join(f"{k}={len(got[k]):4}" for k in want))

    # ★ 도엽별 0건은 오류가 아니다(2026-08-17 정정).
    #   구 가드는 손으로 고른 20도엽 시절 것이다. 전부 스코프 안이라 0건이면
    #   zip/ngi 중복을 의심하는 것이 맞았다. V-WORLD 74도엽은 동구 전역이라
    #   무등산·하천만 걸친 도엽이 정상적으로 섞인다.
    #   판정 기준을 도엽에서 합계로 옮긴다. 다만 조용히 넘기지 않는다.
    if empty:
        print(f"\n  도로경계 0건 도엽 {len(empty)}장: {empty}")
    if not acc["A0010000"]:
        print("\n★ 도로경계 총 0건. 레이어 코드나 압축 구조가 바뀌었다.")
        return 1

    out.mkdir(parents=True, exist_ok=True)
    for layer, items in acc.items():
        g = build(layer, items)
        if g is None:
            print(f"  {LAYERS[layer][1]} 비어 있음 — 건너뜀")
            continue
        print(summary(layer, g))
        write(g, LAYERS[layer][0], out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
