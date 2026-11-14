#!/usr/bin/env python3
"""
bldg_gap.py — 동명동에서 **도로명주소 건물 윤곽이 안 가진** 건축물대장 윤곽(`AL_D010`)을 뽑는다.  (PLAN #232 ④ · DECISIONS §776)

    uv run python -m firelane.bldg_gap                다시 뽑아 커밋된 파일과 **대조만** 한다(안 쓴다 · 다르면 종료 1)
    uv run python -m firelane.bldg_gap --apply        `data/extra/bldg_gap_dongmyeong.geojson` 을 쓴다
    uv run python -m firelane.bldg_gap --src <zip>    대장이 적은 자리 대신 이 파일을 읽는다(sha 는 똑같이 묻는다)

── 왜 있나 ────────────────────────────────────────────────────
`data/extra/bldg_gap_dongmyeong.geojson`(323면)은 2026-11-13 에 **손으로 한 번** 뽑은 파일이었다. 규칙은 DECISIONS §776 에 글로만 있었고
그 글에는 빠진 것이 셋 있었다 — 「동명동 경계로 자른」이 **대표점**이라는 것 · 「발행 건물」이 `web/data/buildings.geojson` 이고 **이 파일이 더한 면
(번호 ≥ `GAP_ID0`)을 빼고** 재야 돈다는 것(안 빼면 제 산출물이 제 입력을 덮어 0면이 된다) · 층수 0 도 1 로 올린다는 것.
셋을 맞춰야 커밋된 파일과 **바이트가 같다**(2026-11-14 실측 · sha256 `eb2a7dd7…`). 그 절차를 여기 못 박는다.

── 규칙 (순서가 결과다) ───────────────────────────────────────
 ① `AL_D010` zip 의 **1번 쉐이프**(`…20261109.shp` · 1,000,000행 · EPSG:5186)를 동명동 경계의 bbox 로 읽는다(`(2)` 쉐이프는 안 읽는다 — 동명동이 1번에 다 든다).
 ② **대표점**(`representative_point`)이 동명동 경계(`boundary_emd` 의 `EMD_CD` 12210108) 안인 면 — 1,935.
    ★ 법정동 칸(`A3` == 1221010800)으로 거르면 1,940 · 무게중심이면 1,936 이다. 칸 뜻은 값으로 추정한 것이라(대장 `pending.juso_bldg_ledger` 의 표) 도형으로 거른다.
 ③ 발행 건물(`web/data/buildings.geojson` 중 번호 < `GAP_ID0`)의 합집합에 **덮인 몫 < 10%** 인 면 — 323.
 ④ 층수 `flo` = `A26`(지상층수) · 비었거나 0 이면 1 · 정수.
 ⑤ 5186 에서 0.2m 단순화(위상 보존) → 경위도 → 좌표 6자리 GeoJSON. 칸은 `flo` 하나다.

IN    레이크 `raw/juso/juso_bldg_ledger_jngj_20261109.zip`(대장 `pending` 의 `juso_bldg_ledger` — 사람이 옮기기 전에는 원본명 `AL_D010_12_20261109.zip` 이고
      그때까지 `datasets` 에 안 오른다)
      · `processed/boundary_emd_5186.gpkg` · `web/data/buildings.geojson`
OUT   `data/extra/bldg_gap_dongmyeong.geojson` (--apply 일 때만)
PARAM `COVER_MAX` 0.1 · `SIMPLIFY_M` 0.2 · `SRC_SHA256` · `--src` · `--apply`
밖    **발행 건물이 바뀌면 답이 바뀐다** — ③ 의 기준은 발행물이다(판정 입력 `building_5186.gpkg` 로 재면 321면이라 커밋본과 다르다). 그래서 기본 동작이 대조다.
      판정은 이 파일을 안 읽는다(표시용 · `publish_web._add_gap_buildings` 가 여기서 도로 위 면 등을 더 걸러 274면을 더한다).
      `AL_D010` 의 판(版)이 바뀌면 `SRC_SHA256` 이 막는다 — 새 판으로 뽑는 것은 사람의 판단이다.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import geopandas as gpd

from firelane import hashing, paths
from firelane.publish_web import GAP_BUILDINGS, W, drop_gap
from firelane.seg.params import EMD_CD

KEY = "juso_bldg_ledger"                 # 대장 키 — 지금은 `pending`, 사람이 이름을 옮기면 `datasets`
CANON = "juso/juso_bldg_ledger_jngj_20261109.zip"   # 정규 이름(DECISIONS §773-1 의 제안 · `naming.check` 통과)
ORIGIN = "juso/AL_D010_12_20261109.zip"             # 사람이 레이크에 놓은 이름(`treecheck` D6)
INNER = "AL_D010_12_20261109.shp"        # zip 안 1번 쉐이프. 이름을 옮겨도 zip 안 이름은 그대로다
SRC_SHA256 = "3198c591e0411b48e5df1ca382e2c827f2e1abf5a9ab45d1492beb554cfddd91"   # DECISIONS §776
COVER_MAX = 0.1                          # 발행 건물에 덮인 몫이 이보다 작아야 「빠진 면」이다
SIMPLIFY_M = 0.2
FLOOR_COL = "A26"                        # 지상층수 — 실측으로 맞은 칸(§776 · 광주 인공지능사관학교 건물 8 ↔ 8)
BOUNDARY = "boundary_emd_5186.gpkg"
PUBLISHED = W / "buildings.geojson"


def pick(al: gpd.GeoDataFrame, dong, pub: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """`al`(건축물대장 윤곽 · 미터 좌표계) 중 `dong` 안이고 `pub`(발행 건물)이 안 덮는 면 → 경위도 · `flo` 한 칸.

    ★ `pub` 에서 번호 ≥ `GAP_ID0` 는 **뺀다** — 그것은 이 함수의 지난 산출물이 발행에 얹힌 것이다. 안 빼면 두 번째 실행이 0면을 낸다.
    """
    if al.crs is None or al.crs.is_geographic:
        raise ValueError(f"건축물대장 윤곽의 좌표계가 미터가 아니다 — {al.crs}(면적 몫을 못 잰다)")
    if FLOOR_COL not in al.columns:
        raise ValueError(f"칸 `{FLOOR_COL}` 이 없다 — 조용히 덜 하지 않는다")
    base = drop_gap(pub).to_crs(al.crs)      # 제 지난 산출물을 가르는 것은 그 번호를 만드는 `publish_web` 이 든다(밖에서 그 칸을 안 읽는다 · DECISIONS §320)
    x = al[al.geometry.representative_point().within(dong)]
    # 후보 면에 닿는 발행 건물만 합친다(전체 12,663동을 합치면 분 단위다 — 닿지 않는 건물은 덮인 몫에 0 을 보태므로 답이 같다)
    near = base.iloc[sorted(set(base.sindex.query(x.geometry, predicate="intersects")[1]))]
    cover = x.geometry.intersection(near.geometry.union_all()).area / x.geometry.area
    x = x[cover < COVER_MAX]
    out = gpd.GeoDataFrame({"flo": x[FLOOR_COL].fillna(1).clip(lower=1).astype(int)},
                           geometry=x.geometry.simplify(SIMPLIFY_M, preserve_topology=True), crs=al.crs)
    return out.to_crs(4326)


def write(out: gpd.GeoDataFrame, path: Path) -> None:
    """좌표 6자리 GeoJSON. 층 이름은 파일 이름이다(커밋본의 `name` 칸과 같다)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(path, driver="GeoJSON", COORDINATE_PRECISION=6, layer=path.stem)


def source(src: Path | None = None) -> Path:
    """읽을 zip. 정규 이름 → 없으면 원본명(사람이 아직 안 옮겼다 · 크게 말한다). 어느 쪽이든 sha 가 같아야 읽는다."""
    if src is None:
        if paths.RAW is None:
            raise SystemExit("✗ 레이크가 없다 — FIRE_LANE_DATA 를 걸거나 --src 로 zip 을 준다")
        cands = [paths.RAW / CANON, paths.RAW / ORIGIN]
        src = next((p for p in cands if p.is_file()), None)
        if src is None:
            raise SystemExit(f"✗ 원천이 없다 — {[str(p) for p in cands]}")
        if src != cands[0]:
            print(f"  ! 정규 이름이 아직 없다 — 원본명으로 읽는다: {src.name} (사람이 옮길 것 · PLAN #232 ④)")
    if not Path(src).is_file():
        raise SystemExit(f"✗ 파일이 없다 — {src}")
    got = hashing.sha256(Path(src))
    if got != SRC_SHA256:
        raise SystemExit(f"✗ 다른 판이다 — sha256 {got[:16]}… (이 절차가 아는 판은 {SRC_SHA256[:16]}…). 새 판으로 뽑는 것은 사람의 판단이다")
    return Path(src)


def extract(src: Path | None = None) -> gpd.GeoDataFrame:
    """실물로 뽑는다(레이크 · 경계 · 발행 건물을 읽는다)."""
    zip_ = source(src)
    emd = gpd.read_file(paths.PROCESSED / BOUNDARY)
    dong = emd[emd["EMD_CD"] == EMD_CD].geometry.union_all()
    if dong.is_empty:
        raise SystemExit(f"✗ 경계에 {EMD_CD} 가 없다 — {BOUNDARY}")
    al = gpd.read_file(f"/vsizip/{zip_}/{INNER}", bbox=tuple(dong.bounds))
    return pick(al, dong, gpd.read_file(PUBLISHED))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, help="대장이 적은 자리 대신 읽을 zip(sha 는 똑같이 묻는다)")
    ap.add_argument("--apply", action="store_true", help="산출물을 쓴다(없으면 대조만)")
    a = ap.parse_args(argv)
    out = extract(a.src)
    if a.apply:
        write(out, GAP_BUILDINGS)
        print(f"✓ 썼다 — {GAP_BUILDINGS.relative_to(paths.ROOT)} · {len(out)}면 · sha256 {hashing.sha256(GAP_BUILDINGS)[:16]}…")
        return 0
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / GAP_BUILDINGS.name
        write(out, tmp)
        new, old = hashing.sha256(tmp), (hashing.sha256(GAP_BUILDINGS) if GAP_BUILDINGS.is_file() else "")
    if new == old:
        print(f"✓ {len(out)}면 · 커밋된 파일과 바이트가 같다 — sha256 {new[:16]}…")
        return 0
    print(f"✗ {len(out)}면 · 커밋된 파일과 다르다 — 새 {new[:16]}… · 지금 {old[:16] or '(없음)'}…\n"
          "   발행 건물이 바뀌었으면 정상이다(머리말 「밖」). 받아들이려면 --apply 뒤 발행을 다시 돈다", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
