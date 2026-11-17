#!/usr/bin/env python3
"""
bldg_fill.py — 지도 이동 범위 안에서 **도로명주소 건물 윤곽(`TL_SPBD_BULD`)이 안 가진** 건축물대장 윤곽(`AL_D010`)을 뽑는다.  (PLAN #244 · DECISIONS §786)

    uv run python -m firelane.bldg_fill               다시 뽑아 커밋된 파일과 **대조만** 한다(안 쓴다 · 다르면 종료 1)
    uv run python -m firelane.bldg_fill --apply       `data/extra/bldg_gap_move.geojson` 을 쓴다
    uv run python -m firelane.bldg_fill --report      ★ 일치도(㉮) · 좌표계(㉱) 를 낸다 — 합치기 전에 사람이 읽는 표
    uv run python -m firelane.bldg_fill --src <zip>   대장이 적은 자리 대신 이 zip 을 읽는다(sha 는 똑같이 묻는다)

── 왜 있나 ────────────────────────────────────────────────────
`bldg_gap`(§776)은 동명동 323면만 더했다. 법원 · 전당 · 병원이 있는 동명동 **밖**에도 `AL_D010` 에만 있는 면이 있다. 그 면은 **검증하고** 더한다 —
(a) 두 출처가 둘 다 가진 면으로 위치 · 모양이 맞는지 먼저 재고(`--report`) (b) **빠진 것만** 더하고 겹치는 면은 기존 것을 둔다
(c) 더한 면마다 출처 칸(`src`)을 단다 (d) 좌표계를 실측으로 확인한다.

── 규칙 (순서가 결과다) ───────────────────────────────────────
 ① `AL_D010` zip 의 1번 쉐이프를 **지도 이동 범위**(`web/data/view.json` 의 `maxBounds`)로 읽고 **대표점**이 범위 안인 면.
 ② 대표점이 동명동 경계 **밖**인 면 — 안은 `bldg_gap` 이 든다(두 파일이 같은 면을 두 번 더하지 않는다).
 ③ `TL_SPBD_BULD`(`processed/building_5186.gpkg` — 발행물이 아니라 **판정 입력**이라 이 파일이 발행에 안 기댄다)에 **덮인 몫 < 10%**.
 ④ ★ **어긋난 같은 건물을 뺀다.** 대표점 아닌 **무게중심이 `DUP_M` 안**이고 면적비가 `DUP_RATIO` 안인 `TL` 면이 있으면
    「빠진 면」이 아니라 같은 건물이 두 측량에서 비껴 그려진 것이다 — 더하면 겹쳐 두 번 솟는다. `DUP_M` 은 둘 다 가진 면의 중심 거리 p95(8.3m)다.
 ④′ ★ **`AL_D010` 안의 같은 기하를 맞댄다**(DECISIONS §823 · PLAN #256). 같은 윤곽이 서로 다른 법정동 레코드로 두 번 오는 쌍(범위 안 16,454행 중 59쌍 · 59/59 가 계림동 ↔ 중흥동)에서 **윤곽이 든 동**
    (`boundary_emd` 에 대표점이 드는 동)의 레코드를 남기고 나머지를 뺀다. 윤곽이 든 동의 레코드가 하나가 아니면(없거나 둘) 파일 순서의 첫 행을 남기고 장부에 「애매」로 적는다.
 ⑤ 칸 — `flo`(지상층수 `A26` · 비었거나 0 이면 1) · `use`(용도명 `A9`) · `nm`(건물명 `A24` · 없으면 빈 글자) · `src`(`AL_D010`).
 ⑥ 5186 에서 0.2m 단순화(위상 보존) → 경위도 → 좌표 6자리 GeoJSON.

IN    레이크 `raw/juso/juso_bldg_ledger_jngj_20261109.zip` · `processed/building_5186.gpkg` · `processed/boundary_emd_5186.gpkg` · `web/data/view.json`
OUT   `data/extra/bldg_gap_move.geojson` (--apply 일 때만)
PARAM `COVER_MAX` 0.1 · `DUP_M` 8.0 · `DUP_RATIO` (0.5, 2.0) · `SIMPLIFY_M` 0.2 · `SRC_TAG`
밖    **판정은 이 파일을 안 읽는다**(표시용 · `publish_web._add_gap_buildings` 가 도로 위 면 · 덮인 면을 더 걸러 더한다). 판정 입력에 넣었을 때의 이동은
      격리 사본에서 따로 쟀다(DECISIONS §786-D) — 본 저장소의 판정은 안 움직인다.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import normalize, set_precision
from shapely.geometry import box

from firelane import bldg_gap, hashing, paths
from firelane.seg.params import EMD_CD

FILL_BUILDINGS = paths.ROOT / "data" / "extra" / "bldg_gap_move.geojson"
VIEW = paths.ROOT / "web" / "data" / "view.json"
COVER_MAX = 0.1
DUP_M = 8.0                    # 둘 다 가진 면(덮임 ≥ 50%)의 무게중심 거리 p95 = 8.3m (DECISIONS §786-B)
DUP_RATIO = (0.5, 2.0)
SIMPLIFY_M = 0.2
SRC_TAG = "AL_D010"
USE_COL, NAME_COL = "A9", "A24"
TL = "building_5186.gpkg"


def move_bounds():
    v = json.loads(VIEW.read_text(encoding="utf-8"))["maxBounds"]
    return gpd.GeoSeries([box(v[0][0], v[0][1], v[1][0], v[1][1])], crs=4326).to_crs(5186).iloc[0]


def agreement(al: gpd.GeoDataFrame, tl: gpd.GeoDataFrame) -> pd.DataFrame:
    """`al` 면마다 닿는 `tl` 면들의 **합집합**과의 IoU · 무게중심 거리 · 면적비 · 덮인 몫 · 편차(dx · dy). 안 닿으면 행이 없다.

    ★ 합집합으로 잰다 — 한 건물을 한쪽이 둘로 쪼갠 경우(1:1 로 맞대면 IoU 가 깎인다)를 공정하게 본다.
    """
    st = tl.sindex
    rows = []
    for i, g in enumerate(al.geometry):
        near = [j for j in st.query(g, predicate="intersects") if tl.geometry.iloc[j].intersection(g).area > 0]
        if not near:
            continue
        u = tl.geometry.iloc[near].union_all()
        a = u.intersection(g).area
        rows.append((i, len(near), a / (g.area + u.area - a), g.centroid.distance(u.centroid),
                     g.area / u.area, a / g.area, g.centroid.x - u.centroid.x, g.centroid.y - u.centroid.y))
    return pd.DataFrame(rows, columns=["i", "n", "iou", "d", "ratio", "cover", "dx", "dy"])


def drop_twins(x: gpd.GeoDataFrame, emd: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    """④′ — 같은 기하(정규화한 좌표열)가 둘 이상인 행에서 **윤곽이 든 동의 레코드**(`A3` 앞 8자리 == 대표점이 드는 `EMD_CD`)를 남긴다. 장부: 쌍 수 · 뗀 면 · 애매(남길 레코드가 하나로 안 정해진 쌍)."""
    if "A3" not in x.columns:
        raise ValueError("칸 `A3`(법정동 코드)이 없다 — 조용히 덜 하지 않는다")
    emd = emd.to_crs(x.crs)
    # 같은 기하 = **쓰는 모양**에서 같다 — 0.2m 단순화 · 경위도 6자리 반올림 뒤(원본 부동소수에서는 다르고 파일에서는 같은 쌍이 여섯이었다: 53 대 59)
    shown = x.geometry.simplify(SIMPLIFY_M, preserve_topology=True).to_crs(4326)
    groups = x.groupby(shown.map(lambda g: normalize(set_precision(g, 1e-6)).wkb_hex)).groups
    drop, amb, n = [], 0, 0
    for idx in groups.values():
        if len(idx) < 2:
            continue
        n += 1
        hit = emd[emd.contains(x.geometry.loc[idx[0]].representative_point())]
        code = str(hit.iloc[0]["EMD_CD"])[:8] if len(hit) else None
        match = [i for i in idx if str(x.at[i, "A3"])[:8] == code]
        keep = match[0] if len(match) == 1 else idx[0]
        amb += len(match) != 1
        drop += [i for i in idx if i != keep]
    return x.drop(index=drop), {"twin_groups": n, "twin_dropped": len(drop), "twin_ambiguous": amb}


def pick(al: gpd.GeoDataFrame, move, dong, tl: gpd.GeoDataFrame, emd: gpd.GeoDataFrame | None = None) -> tuple[gpd.GeoDataFrame, dict]:
    """`al`(미터 좌표계) 중 규칙 ①~⑤ 를 통과한 면 → (경위도 · 4칸, 뺀 수 장부)."""
    if al.crs is None or al.crs.is_geographic:
        raise ValueError(f"건축물대장 윤곽의 좌표계가 미터가 아니다 — {al.crs}(면적 몫을 못 잰다)")
    for c in ("A26", USE_COL, NAME_COL):
        if c not in al.columns:
            raise ValueError(f"칸 `{c}` 이 없다 — 조용히 덜 하지 않는다")
    tl = tl.to_crs(al.crs)
    rp = al.geometry.representative_point()
    led = {"in_move": int(rp.within(move).sum())}
    x = al[rp.within(move) & ~rp.within(dong)]
    led["outside_dong"] = len(x)
    near = tl.iloc[sorted(set(tl.sindex.query(x.geometry, predicate="intersects")[1]))]
    cover = x.geometry.intersection(near.geometry.union_all()).area / x.geometry.area
    x = x[cover < COVER_MAX]
    led["uncovered"] = len(x)
    # ④ 어긋난 같은 건물 — 무게중심 DUP_M 안 · 면적비 DUP_RATIO 안의 TL 면
    cen = tl.geometry.centroid
    tla = tl.geometry.area.values
    dup = []
    for g in x.geometry:
        c = g.centroid
        cand = list(tl.sindex.query(c.buffer(DUP_M), predicate="intersects"))
        hit = any(cen.iloc[j].distance(c) <= DUP_M and DUP_RATIO[0] <= g.area / tla[j] <= DUP_RATIO[1] for j in cand)
        dup.append(hit)
    dup = pd.Series(dup, index=x.index, dtype=bool)
    led["dup_suspect"] = int(dup.sum())
    x = x[~dup]
    if emd is not None:         # 합성 표본(시험)은 법정동 경계를 안 준다 — 실물(`main`)은 늘 준다
        x, tw = drop_twins(x, emd)
        led.update(tw)
    nm = x[NAME_COL].fillna("").astype(str).str.strip()
    out = gpd.GeoDataFrame({
        "flo": x["A26"].fillna(1).clip(lower=1).astype(int),
        "use": x[USE_COL].fillna("").astype(str),
        "nm": nm,
        "src": SRC_TAG,
    }, geometry=x.geometry.simplify(SIMPLIFY_M, preserve_topology=True), crs=al.crs)
    led["added"] = len(out)
    return out.to_crs(4326), led


def write(out: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(path, driver="GeoJSON", COORDINATE_PRECISION=6, layer=path.stem)


def load() -> tuple[gpd.GeoDataFrame, object, object, gpd.GeoDataFrame]:
    zip_ = bldg_gap.source(None)
    emd = gpd.read_file(paths.PROCESSED / bldg_gap.BOUNDARY)
    dong = emd[emd["EMD_CD"] == EMD_CD].geometry.union_all()
    move = move_bounds()
    al = gpd.read_file(f"/vsizip/{zip_}/{bldg_gap.INNER}", bbox=tuple(move.bounds))
    return al, move, dong, gpd.read_file(paths.PROCESSED / TL)


def report(al, move, tl) -> None:
    """일치도(㉮) · 좌표계(㉱). 합치기 전에 사람이 읽는 표다 — 판정은 안 한다."""
    al = al[al.geometry.representative_point().within(move)].reset_index(drop=True)
    tl = tl[tl.intersects(move)].reset_index(drop=True)
    r = agreement(al, tl)
    print(f"AL 면 {len(al):,} (범위 안 대표점) · TL 면 {len(tl):,} · 닿는 AL 면 {len(r):,}")
    for nm, s in (("같은 건물(덮임 ≥ 50%)", r[r.cover >= .5]), ("덮임 ≥ 80%", r[r.cover >= .8]),
                  ("덮임 10~50%(애매)", r[(r.cover >= .1) & (r.cover < .5)]), ("덮임 < 10%(닿았으나 빠진)", r[r.cover < .1])):
        q = s[["iou", "d", "ratio", "dx", "dy"]].quantile([.05, .5, .95]).round(2)
        print(f"{nm}: {len(s):,}면 · IoU 중앙 {q.iou[.5]} (p5 {q.iou[.05]}) · 거리 중앙 {q.d[.5]}m p95 {q.d[.95]}m · 면적비 중앙 {q.ratio[.5]} · "
              f"편차 중앙 dx {q.dx[.5]} dy {q.dy[.5]} · IoU<0.5 {(s.iou < .5).sum():,} · 거리>10m {(s.d > 10).sum():,}")
    print(f"좌표계: AL `.prj` = {al.crs.to_string()} · TL = {tl.crs.to_string()}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    if a.src:
        bldg_gap.source(a.src)
    al, move, dong, tl = load()
    if a.report:
        report(al, move, tl)
        return 0
    out, led = pick(al, move, dong, tl, gpd.read_file(paths.PROCESSED / bldg_gap.BOUNDARY))
    print("  장부 — " + " · ".join(f"{k} {v:,}" for k, v in led.items()))
    if a.apply:
        write(out, FILL_BUILDINGS)
        print(f"✓ 썼다 — {FILL_BUILDINGS.relative_to(paths.ROOT)} · {len(out)}면 · sha256 {hashing.sha256(FILL_BUILDINGS)[:16]}…")
        return 0
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / FILL_BUILDINGS.name
        write(out, tmp)
        new, old = hashing.sha256(tmp), (hashing.sha256(FILL_BUILDINGS) if FILL_BUILDINGS.is_file() else "")
    if new == old:
        print(f"✓ {len(out)}면 · 커밋된 파일과 바이트가 같다 — sha256 {new[:16]}…")
        return 0
    print(f"✗ {len(out)}면 · 커밋된 파일과 다르다 — 새 {new[:16]}… · 지금 {old[:16] or '(없음)'}…", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
