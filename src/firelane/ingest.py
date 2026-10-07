#!/usr/bin/env python3
"""
ingest.py — data/raw 원본을 동명동 범위 표준 산출물로 변환한다.


IN    sources.yaml (대장) · $FIRE_LANE_DATA/raw/**  (불변)
OUT   data/processed/<key>_5186.gpkg + <key>.geojson  (20종) — 예: building.geojson
      data/processed/_manifest.json
      ★ 하류가 이름으로 읽는 것 — boundary_emd.geojson · fire_station.geojson ·
        hydrant_point.geojson · cctv.geojson · poi_store.geojson ·
        road_intrvl.geojson · navi_build.csv · navi_jibun.csv · civil_office.geojson ·
        turn_restriction.csv · speedbump.csv · speed_cam.csv · nfa_dispatch_119.csv ·
        nfa_rescue.csv · nfa_fire_incident.csv · parking_enforce.csv · enforce_cam.csv.
        `pipeline.Step` 이 그 열일곱을 명시한다(§181 · §215-1 · §216-3 · §426-2 —
        **열일곱 번째가 3주 동안 빠져 있었다**)
      data/processed/_manifest.json                    실행 기록 · 계보 정본
PARAM sources.yaml 의 datasets.<key>.contract 블록

원칙
  1. data/raw 는 불변. 어떤 코드도 여기에 쓰지 않는다.
  2. 모든 입력에 SHA-256을 찍는다. 원본이 바뀌면 즉시 드러난다.
  3. 좌표계는 sources.yaml 값으로 '정의'한 뒤 표준으로 '변환'한다.
     set_crs(정의) → to_crs(변환). 순서 바뀌면 전부 어긋난다.
  4. 산출물은 두 벌. *_5186.gpkg(계산용) + *.geojson(표출용).
  5. 실행 기록 전체가 data/processed/_manifest.json 에 남는다.

사용
    python -m firelane.ingest
    python -m firelane.ingest --only road_link ngii_road
    python -m firelane.ingest --check          # 체크섬만 검증
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
import yaml
from shapely import make_valid

from firelane import ledger, manifest, prep, read

# ★ 좌표계 · 절단 상자 · 읽기 연장의 정본은 `read._io` 다. 여기 두면
#   `read` 가 `ingest` 를 도로 임포트해 고리가 돈다(DECISIONS §274-4).
from firelane.hashing import sha256
from firelane.paths import PROCESSED, RAW, ROOT
from firelane.read._io import BBOX_4326, CRS_M, CRS_W

OUT = PROCESSED





def sha_of(p: Path) -> str:
    """파일이면 그 해시, 디렉터리면 하위 파일 해시들의 해시.

    도엽 디렉터리(ngii1k)처럼 '여러 파일이 한 데이터셋'인 경우가 있다.
    도엽 한 장이 빠지거나 연도가 바뀌면 여기서 드러나야 한다.
    """
    if p.is_file():
        return sha256(p)
    files = sorted(x for x in p.rglob("*") if x.is_file() and not x.name.startswith("_"))
    h = hashlib.sha256()
    for f in files:
        h.update(f.relative_to(p).as_posix().encode())
        h.update(sha256(f).encode())
    return h.hexdigest()


def save(gdf: gpd.GeoDataFrame, key: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    # ★ 2026-09-17 (§182-6). `GeoSeries.notna()` 는 geopandas 가 빈 도형 의미를 바꾸면서 매 실행 경고를 낸다.
    #   뜻은 "없거나 비었으면 뺀다" 하나다 — shapely 로 직접 묻는다. 매번 뜨는 경고는 진짜 경고를 죽인다.
    _g = np.asarray(gdf.geometry.values, dtype=object)
    gdf = gdf[~(shapely.is_missing(_g) | shapely.is_empty(_g))].copy()
    # ★ 2026-08-18. 쓰기 전에 파일을 지운다.
    #   GPKG 는 컨테이너다. to_file(layer=key) 는 그 **레이어**를 덮어쓸 뿐
    #   파일 안의 다른 레이어는 건드리지 않는다. layer= 를 안 쓰던 시절의
    #   레이어가 남아 있었고, GeoPandas 는 레이어를 지정하지 않으면 첫
    #   레이어를 읽는다. 그래서 segments 가 08-17 판 ngii1k_5186(6,675개)을
    #   읽었고, 08-18 산출 14,336 개는 옆 레이어로 놀고 있었다.
    #
    #     More than one layer found in 'ngii1k_5186.gpkg':
    #       'ngii1k_5186' (default), 'ngii1k'
    #
    #   결과: 스코프 북부 미커버 13.4%. 파일은 갱신됐고 mtime 은 새것이고
    #   status 는 OK 라 어떤 가드도 보지 못했다. 근거는 DECISIONS 08-18.
    #
    #   한 파일 = 한 레이어를 불변식으로 세운다. 컨테이너에 누적하지 않는다.
    # ★ 2026-08-22. 무효 기하를 여기서 한 번에 잡는다.
    #   sources.yaml 의 road_rw 에 이미 경고가 적혀 있었다 —
    #   "winding order 오류 폴리곤 포함. make_valid + buffer(0) 없이
    #    unary_union 하면 …". 그런데 make_valid 는 shp_zip_multi 분기에만
    #   걸려 있었고 road_rw(shp_zip)는 그냥 통과했다. **대장의 note 는
    #   사람이 읽는 글이지 강제자가 아니다**(§5-6 과 같은 계열).
    #
    #   실제로 터졌다: road_rw 를 union 하면
    #   TopologyException: side location conflict.
    #   더 나쁜 것은 예외가 아니라 조용한 오답이 나오는 경우다 —
    #   나비넥타이 폴리곤을 그냥 union 하면 면적이 정답의 2/3 로 나온다.
    #
    #   kind 별로 배선하지 않고 save() 에 건다. 모든 소스의 공통 관문이다.
    _inv = ~gdf.geometry.is_valid & gdf.geometry.notna()
    if _inv.any():
        gdf = gdf.copy()
        gdf.loc[_inv, "geometry"] = gdf.loc[_inv, "geometry"].apply(make_valid)
        _still = int((~gdf.geometry.is_valid & gdf.geometry.notna()).sum())
        print(f"          · 무효 기하 {int(_inv.sum())}건 make_valid"
              + (f" · 잔여 {_still}건 ★" if _still else ""))

    _gpkg = OUT / f"{key}_5186.gpkg"
    _gpkg.unlink(missing_ok=True)
    gdf.to_crs(CRS_M).to_file(_gpkg, driver="GPKG", layer=key)
    gdf.to_crs(CRS_W).to_file(OUT / f"{key}.geojson", driver="GeoJSON")
    return {"features": len(gdf), "geom": sorted(set(gdf.geom_type)),
            # ★ 대장에 남긴다. 어떤 소스가 얼마나 깨져 있었는지가
            #   다음 사람에게 필요한 정보다.
            "invalid_fixed": int(_inv.sum()),
            "columns": [c for c in gdf.columns if c != "geometry"]}


def paths_for(key: str, e: dict) -> list[Path]:
    """이 소스의 실물 경로. **입력 계층을 여기 한 곳에서 가른다.**

    ★ 2026-08-31. 종전에는 raw 하드코딩이 두 곳에 박혀 있었다.
      `layers.norm.migrated` 를 채워도 아무 일이 안 났고, `golden.py check` 는
      `segments.geojson` 하나만 보므로 **통과했다**(DECISIONS §77).
      선언이 실물보다 앞선 것이다. `tests/test_norm_wiring.py` 가 그 상태를
      이제 빨간불로 만든다.

    글롭은 raw 에서 푼다. raw 는 절대 수정하지 않으므로 항상 전량이 있고,
    norm 은 같은 상대 경로에 정규화 사본을 둔다. 상대 경로를
    `prep.source_path()` 에 넘기면 이관 여부에 따라 갈린다 — 선언은 됐는데
    실물이 없으면 거기서 `FileNotFoundError` 로 죽는다. **조용히 raw 로
    떨어지지 않는 것**이 이 함수의 요점이다.
    """
    if key not in prep.migrated():
        return ledger.paths_of(e, RAW)
    rels = [q.relative_to(RAW).as_posix() for q in ledger.paths_of(e, RAW)]
    if not rels:
        rels = [g for g in ledger.globs(e) if not any(c in g for c in "*?[")]
    return sorted({prep.source_path(key, r) for r in rels})


def build(key: str, e: dict, tmp: Path) -> dict:
    pats = ledger.globs(e)
    hits = paths_for(key, e)
    if not hits:
        return {"key": key, "status": "MISSING", "files": pats}
    src = hits[0]
    # ★ 2026-08-23. glob 이 여러 개를 잡으면 **정렬 첫 번째**가 쓰인다.
    #   날짜가 파일명에 있으므로 그것은 대개 **옛 판**이다.
    #   2026-08-23 에 `gjcity_parking_enforce_dongu_20250226.csv` 를 새로
    #   편입했는데 파이프라인은 계속 20240108 을 읽었고 아무도 몰랐다.
    #
    #   여기서 자동으로 최신을 고르지 않는다. 그러면 raw 에 파일 하나를
    #   떨구는 것만으로 산출물이 조용히 바뀐다 — 대장이 정본이라는 원칙이
    #   깨진다(§18-3). 대신 **시끄럽게 알리고** 사람이 대장을 고치게 한다.
    # ★ 2026-08-23 정정. 처음엔 `hits > 1` 이면 무조건 경고했다. 오탐이었다.
    #   kind 마다 여러 파일이 **정상**인 것이 있다.
    #
    #     shp_zip_multi   도엽 여러 zip 을 병합한다. 여러 개가 정상
    #     shp_dir         ngii1k.py 가 묶음 전체를 편다. 여러 개가 정상
    #     raw_only        읽지 않는다. ortho.py 가 4도엽을 직접 읽는다
    #
    #   실전에서 5종이 경고를 냈고 그중 4종이 오탐이었다.
    #   **매번 뜨는 경고는 아무도 안 읽는다** — 그러면 진짜 하나를 놓친다.
    #   `hits[0]` 만 쓰는 kind 에서만 말한다.
    SINGLE_PICK = ledger.SINGLE_PICK      # 정본은 ledger. 사본을 두지 않는다
    if len(hits) > 1 and e["kind"] in SINGLE_PICK:
        rest = ", ".join(x.name for x in hits[1:])
        print(f"  ★ {key}: 대장 glob 이 {len(hits)}개를 잡는데 "
              f"kind={e['kind']} 는 하나만 쓴다 → {src.name}")
        print(f"     쓰이지 않는 것: {rest}")
        print("     날짜가 파일명에 있으므로 정렬 첫 번째는 대개 **옛 판**이다.")
        print("     sources.yaml 의 file 을 하나로 좁혀라.")

    # ── FL_EXT_COLLISION ─────────────────────────────────────
    # 줄기가 같고 확장자만 다른 파일이 raw 에 함께 있으면, 어느 것을
    # 읽는지가 **사전순 우연**으로 정해진다. kind 와 무관하다.
    #
    # 2026-08-25 에 KFS 규격서를 PDF 판으로 다시 읽고 결론을 뒤집었는데,
    # 대장이 `..._20251224.*` 라 두 판을 한 항목으로 보고 있었다.
    # raw_only 는 위 SINGLE_PICK 경고 밖이라 아무 말도 안 났을 것이다.
    # ★ 2026-08-30. `.xml` `.prj` `.tfw` 등은 사이드카다 — 본체와 함께
    #   오는 부속이지 "포맷이 다른 별개 자산" 이 아니다. 종전에는
    #   ortho 가 매 실행 4건을 오탐했고, 매번 뜨는 경고는 진짜 하나를
    #   죽인다(바로 위 SINGLE_PICK 주석이 같은 이유로 적혀 있다).
    SIDECAR = {".xml", ".prj", ".tfw", ".cpg", ".aux", ".ovr", ".meta"}
    _stems = {}
    for h in hits:
        if h.suffix.lower() in SIDECAR:
            continue
        _stems.setdefault(h.name.rsplit(".", 1)[0], []).append(h.name)
    # ★ 2026-09-17 (§182-5). 대장이 `primary` 로 이미 못박았으면 판단이 끝난 것이다(kfs · mas 3건이
    #   `primary: hwp` 인데 매 실행 경고했다). 파일 이름이든 확장자든 그중 하나를 가리키면 조용히 한다.
    _pri = str(e.get("primary") or "").lower().lstrip(".")
    for _st, _fs in _stems.items():
        if len(_fs) > 1 and _pri and any(f.lower() == _pri or f.lower().endswith("." + _pri) for f in _fs):
            continue
        if len(_fs) > 1:
            print(f"  ★ {key}: 확장자만 다른 동명 파일 {len(_fs)}개 — "
                  f"{', '.join(sorted(_fs))}")
            print(f"     사전순 첫 번째는 {sorted(_fs)[0]} 다.")
            print("     포맷이 다르면 다른 자산이다. 대장을 files: + primary:")
            print("     로 적어 못박아라(firelane.ledger 가 강제한다).")
    crs = ledger.crs_of(e)
    rec = {"key": key, "source_files": pats, "source_sha256": sha_of(src),
           "resolved": src.name,
           **({"ambiguous": [x.name for x in hits]} if len(hits) > 1 else {}),
           # csv_table / raw_only 는 좌표가 없다. crs 를 필수로 두면 거기서 죽는다.
           # ★ license · url 은 대장에서 제거됐다. 빈 칸을 계보에 박으면
           #   "출처 불명" 과 "출처를 안 적는 정책" 이 같은 모양이 된다.
           "source_crs": crs}
    kind = e["kind"]

    # ── 갈래를 부른다.  (PLAN §1 #132 · DECISIONS §274) ──────────
    # ★ 종전에는 여기가 `if kind == …` 열두 갈래 389줄이었다. 그 하나가
    #   **72개 데이터셋 전부의 샤드 `seal.code`** 를 들고 있어서 `text_table`
    #   한 줄을 고치면 `raw_only` 26개까지 재도장됐다. 갈래를 `read/` 로 내려
    #   샤드가 **제 갈래만** 문다(DECISIONS §274-3).
    got = read.reader(kind)(read.Ctx(
        key=key, e=e, src=src, hits=hits, crs=crs, tmp=tmp, out=OUT,
        rec=rec, save=save))

    # ★ 선언(`read.GEOM_KINDS`)과 실물이 갈리면 **여기서** 세운다. 안 그러면
    #   dict 가 `save()` 로 들어가 한참 아래에서 엉뚱한 이름으로 죽는다 —
    #   `ngii1k` 가 튜플을 geom 으로 받아 매 실행 FAIL 하던 그 형태다(2026-08-17).
    want_geom = kind in read.GEOM_KINDS
    if isinstance(got, gpd.GeoDataFrame) is not want_geom:
        raise TypeError(
            f"{key}: kind={kind} 의 갈래가 {type(got).__name__} 를 냈는데 "
            f"`read.GEOM_KINDS` 는 "
            f"{'도형' if want_geom else '계보 조각'} 이라고 선언한다 — 선언과 실물이 갈렸다")
    if not want_geom:
        return got
    g = got

    info = save(g, key)
    # ★ 2026-08-30. 종전에는 0건도 status: OK 였다. `jijeok` 이 970MB 를
    #   읽고 0건을 내면서 초록불이었다 — 파일은 생겼고 mtime 은 새것이고
    #   어떤 가드도 보지 못한다. 2026-08-18 gpkg 레이어 사고와 같은 형태다.
    #
    #   **조용히 덜 하는 것이 시끄럽게 죽는 것보다 나쁘다.** 0건이
    #   정상인 소스가 있다면 대장에 선언하게 한다 — 코드가 봐주지 않는다.
    _min = int((e.get("contract") or {}).get("scope_min", 1))
    if info["features"] < _min:
        rec |= {"status": "FAIL", **info,
                "error": f"산출 {info['features']}건 < scope_min {_min}. "
                         "좌표계·BBOX·필터를 확인하라. 0건이 정상이면 "
                         "contract.scope_min 에 선언해라",
                "outputs": []}
        print(f"  ★ {key}: 산출 {info['features']}건 — scope_min {_min} 미달")
        print(f"     source_crs={crs} · 읽은 것 {src.name}")
        return rec
    rec |= {"status": "OK"} | info
    rec["outputs"] = [f"{key}.geojson", f"{key}_5186.gpkg"]
    return rec


# ★ 부모가 자식에게 결과를 받는 표식. 자식의 화면 출력을 그대로
#   흘리면서도 결과 한 줄만 골라내야 한다.
_MARK = "@@ingest-result@@ "


def _spawn(key: str) -> dict:
    """소스 하나를 **자식 프로세스**로 돌리고 결과 dict 를 받는다.

    ── 왜 자식인가 (PLAN #15) ─────────────────────────────────────
    `geopandas` 가 놓은 메모리를 OS 에 안 돌려줘 한 프로세스로 66종을
    돌면 RSS 가 단조증가한다. 뒤쪽 무거운 소스가 `Errno 12` 로 죽는다.
    종료 시 OS 가 회수하게 하면 누적이 0 으로 리셋된다.

    ★ **"무거운 것만" 이 아니라 전부 자식으로 돌린다.** 2026-09-14 에
      `jijeok`(1.0GB · 630만 행)을 `on_demand` 로 뺐더니 OOM 이
      `ngii_road` 로 **옮겨갔다.** 문제는 개별 크기가 아니라 누적이므로,
      무거운 것을 고르는 일 자체가 답이 아니다. `_manifest` 에 시간도
      없어서 고를 근거도 없다.

    ★ `--keep-work` 를 준다. 자식마다 `.work` 를 지우면 `ngii1k` 가
      도엽 74장 + NGI 143장을 매번 다시 푼다 — ingest 시간의 대부분이
      거기다(아래 2026-08-23 주석). **OOM 을 고치고 시간을 폭발시키면
      안 바꾼 것만 못하다.** `.work` 는 부모가 마지막에 한 번 판단한다.

    ★ `--emit-json` 을 준다. 자식은 대장을 쓰지 않는다. 40번 쓰면 I/O 도
      낭비고, 중간에 죽으면 대장이 반쯤 갱신된 채 남는다 — `--check` 가
      "조회는 아무것도 쓰지 않는다" 로 세운 선과 같은 이유다(2026-08-31).

    ★ `python -m firelane.ingest` 가 아니라 `main()` 을 직접 부른다.
      전자는 `warn_direct_call` 이 자식마다 경고를 찍어 화면이 40줄
      늘어난다. 그 경고는 **사람**이 단계를 직접 부를 때를 위한 것이고
      부모가 부르는 것은 그 경우가 아니다.

    실패는 예외로 낸다. 호출부의 `except` 가 `quarantine_stale` 까지
    이미 처리하므로 새 경로를 만들지 않는다.
    """
    cmd = [sys.executable, "-c",
           "from firelane.ingest import main; main()",
           "--only", key, "--keep-work", "--emit-json"]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, check=False)
    # ★ 자식의 진행 줄은 삼킨다. 부모가 같은 내용을 `[OK ]` 로 다시
    #   찍으므로 안 삼키면 **한 소스가 두 줄**이 된다. `.work 유지` 도
    #   자식 것은 거짓이다 — 정리 판단은 부모 몫이고 자식은 항상 남긴다.
    #   부모가 못 내는 것(원본 행수·select 내역)만 흘린다.
    for line in p.stdout.splitlines():
        if line.startswith(_MARK) or line.startswith(("[", "  · .work")):
            continue
        print(line)
    if p.stderr.strip():
        print(p.stderr.rstrip(), file=sys.stderr)
    for line in reversed(p.stdout.splitlines()):
        if line.startswith(_MARK):
            return json.loads(line[len(_MARK):])
    # ★ 결과가 없다 = 자식이 중간에 죽었다. OOM 이면 rc 가 -9(SIGKILL) 다.
    #   그것을 그대로 사유로 적는다 — "실패했다" 만 적으면 다음 사람이
    #   또 추측한다(2026-09-14 오진 넷).
    raise RuntimeError(
        f"자식이 결과를 안 냈다 (rc={p.returncode}"
        + (" · SIGKILL — 메모리일 가능성이 높다" if p.returncode in (-9, 137) else "")
        + ")")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--check", action="store_true")
    # ★ 2026-08-23. 실패한 것만 다시 돌린다.
    #
    #   19종을 한 덩어리로 돌아서 **하나가 FAIL 하면 전체가 무효**였다.
    #   그리고 그 실패가 비결정적이다(PLAN §1-19) — 같은 입력·같은 코드로
    #   1회차 `turn_restriction`·`cctv`, 2회차 통과, 3회차 `ngii_road`,
    #   4회차 `node_link`. 하루에 세 번 났고 매번 다른 소스였다.
    #
    #   그때마다 200초를 다시 태웠다. 성공한 18종은 산출물이 멀쩡한데도.
    #   `_manifest.json` 에 소스별 status 가 이미 있으므로 읽어서 고르면 된다.
    ap.add_argument("--retry-failed", action="store_true",
                    help="지난 실행에서 FAIL·MISSING 인 소스만 다시 돌린다")
    ap.add_argument("--keep-work", action="store_true",
                    help=".work 압축 해제분을 남긴다 (다음 실행이 빨라진다)")
    # ★ PLAN #15. 소스마다 자식 프로세스로 돌려 메모리를 OS 에 반납한다.
    #   사유는 `_spawn` 에 있다. 기본값은 실측 뒤에 정한다.
    ap.add_argument("--split", action="store_true",
                    help="소스마다 자식 프로세스로 돌린다 (메모리 반납)")
    # ★ 자식 전용. 대장을 쓰지 않고 결과 한 줄만 낸다.
    ap.add_argument("--emit-json", action="store_true",
                    help=argparse.SUPPRESS)
    ap.add_argument("--rebuild", action="store_true",
                    help="샤드 봉인을 무시하고 전부 다시 빌드한다")
    ap.add_argument("--reseal-out", action="store_true",
                    help="하류가 덧쓴 산출물로 샤드 봉인지의 out 칸만 고친다 (파이프라인이 terrain 뒤에 부른다)")
    # ★ 2026-09-23 (DECISIONS §224-2a). 사유는 `shardseal.reseal_code` 머리말.
    ap.add_argument("--reseal-code", action="store_true",
                    help="raw · 산출물이 봉인과 같은 샤드의 code 칸만 지금 코드 지문으로 고친다")
    ap.add_argument("--stamp", action="store_true",
                    help="빌드 없이, 지금 산출물에 샤드 봉인지를 붙인다 (사람이 판단해서 부른다)")
    a = ap.parse_args()

    if a.retry_failed:
        man0 = OUT / "_manifest.json"
        if not man0.exists():
            sys.exit("★ _manifest.json 이 없다. 전량을 한 번 돌려라.")
        prev0 = json.loads(man0.read_text(encoding="utf-8")).get("datasets", [])
        bad = [r["key"] for r in prev0
               if isinstance(r, dict) and r.get("status") in ("FAIL", "MISSING")]
        if not bad:
            print("실패한 소스가 없다. 할 일이 없다.")
            return 0
        print(f"지난 실행 실패 {len(bad)}종만 다시 돌린다: {', '.join(bad)}")
        a.only = bad

    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))

    # ★ 2026-09-16. 샤드(소스 하나) 봉인 — shardseal.py 머리말. 봉인지 네 칸
    #   (raw · cfg · code · out)이 전부 같으면 다시 빌드하지 않는다. 이 8GB
    #   기계에서 `ngii_road` 는 다시 빌드하면 거의 반드시 죽는다(DECISIONS §165).
    from firelane import shardseal
    _code = shardseal.code_print()
    _man0 = OUT / "_manifest.json"
    _prev = {}
    if _man0.exists():
        try:
            _prev = {r["key"]: r for r in json.loads(_man0.read_text(encoding="utf-8"))
                     .get("datasets", []) if isinstance(r, dict) and "key" in r}
        except Exception:
            _prev = {}

    if a.reseal_out:
        return shardseal.reseal_out_cli(_man0, OUT, manifest)

    if a.reseal_code:
        return shardseal.reseal_code_cli(_man0, cfg, OUT, _code, paths_for, manifest)

    if a.stamp:
        # 빌드하지 않는다. 지금 디스크의 산출물이 지금 코드 · raw 로 만든 것이라는
        # 판단은 **사람이** 한다(직전 전량 성공 · golden 불변). 여기서는 잴 수 있는
        # 것만 잰다 — 산출물이 대장에 적힌 대로 다 있는가.
        if a.only:
            sys.exit("★ --stamp 는 --only 와 같이 쓰지 않는다. 대장 전체에 붙인다.")
        stamped, left = 0, []
        for key, e in cfg["datasets"].items():
            r = _prev.get(key)
            if not r or r.get("status") != "OK":
                continue
            try:
                _h = paths_for(key, e)
            except Exception:
                _h = []
            s = shardseal.make(cfg, key, _h, OUT, r.get("outputs", []), _code)
            if s is None:
                left.append(key)
                continue
            r["seal"] = s
            stamped += 1
        results = [_prev[k] for k in cfg["datasets"] if k in _prev] + \
                  [v for k, v in _prev.items() if k not in cfg["datasets"]]
        print(f"샤드 봉인지 {stamped}종 · 못 붙인 것 {len(left)}종"
              + (f": {', '.join(left)}" if left else ""))
        if left:
            print("  못 붙인 샤드는 산출물이 없거나 raw 를 못 쟀다. 다음 실행에서 다시 빌드된다.")
        doc = {k: v for k, v in manifest.read(_man0).items()
               if k not in ("generated_at", "bbox_4326", "standard_crs", "datasets")}
        doc.update({"generated_at": datetime.now(UTC).astimezone().isoformat(),
                    "bbox_4326": BBOX_4326,
                    "standard_crs": {"metric": CRS_M, "display": CRS_W},
                    "datasets": results})
        wrote = manifest.write_stable(_man0, doc)
        print(f"→ {_man0}" + ("" if wrote else "  (내용 동일 — 갱신 없음)"))
        return 0

    tmp = ROOT / ".work"
    tmp.mkdir(exist_ok=True)
    results = []
    _done = False

    # ★ 2026-09-13. `finally` 로 감쌌다. 아래의 "실패했을 때는 지운다" 는
    #   맞는 규율인데 **그 줄까지 도달해야 돈다.** Ctrl-C 는 루프 한가운데서
    #   스택을 걷어내므로 반쯤 풀린 `.work` 가 그대로 남고, 다음 실행이
    #   그것을 캐시로 믿는다.
    # ★ 2026-09-14 재정정. `ngii_road` · `jijeok` 이 죽은 진짜 원인은
    #   **메모리**였다(`Errno 12`). `.work` 오염도 stdin 누락도 아니었다.
    #   같은 증상을 두 번 오진했다 — 증상이 맞아떨어진다고 원인이 아니다.
    #   이 `finally` 자체는 옳으므로 남긴다. 중단된 실행이 반쯤 풀린
    #   `.work` 를 남기는 것은 사실이고, 막는 것이 맞다.
    # ★ 아래 옛 사유는 틀렸다. 지우지 않고 남겨 둔다 — 무엇을 잘못
    #   짚었는지가 다음 사람에게 정보다.
    # ☓ 2026-09-14 (틀림). 그날 `ngii_road` 가 죽은 원인은 이것이 아니었다.
    #   진범은 `verify.sh` 의 `step()` 이 자식에게 파이프 stdin 을 물려준
    #   것이었다(`</dev/null` 누락). 같은 자리에서 같은 증상이 두 번 났으면
    #   공통 원인을 먼저 의심했어야 했다. 이 `finally` 자체는 옳으므로
    #   남기되, **사유를 고쳐 적는다** — 틀린 사유는 침묵보다 나쁘다.
    try:
      for key, e in cfg["datasets"].items():
        if a.only and key not in a.only:
            continue
        # ★ 2026-09-14. 요청할 때만 읽는다. `jijeok` 은 1.0GB 를 풀어
        #   630만 행을 파싱해 24,183건을 내는데 **판정도 화면도 안 읽는다** —
        #   소비자가 `tools/jijeok_probe.py` · `jijeok_review.py` 둘뿐이다.
        #   8GB 기계에서 `verify.sh` 안의 전량이 그것 때문에 OOM 으로
        #   죽었다(Errno 12). 2026-09-03 에도 같은 일이 있었다.
        # ★ `raw_only` 로 안 바꾼다. 그것은 "읽지 않는다" 이고 이쪽은
        #   **읽을 수는 있어야** 한다 — 탐색 도구가 산출물을 쓴다.
        if e.get("on_demand") and not a.only:
            results.append({"key": key, "status": "SKIP", "features": "",
                            "geom": [], "outputs": [],
                            "note": "on_demand — --only 로 지목할 때만 읽는다"})
            print(f"[SKIP   ] {key:22} on_demand")
            continue
        if a.check:
            hits = paths_for(key, e)
            results.append({"key": key, "found": len(hits),
                            "sha256": [sha256(h)[:16] for h in hits]})
            print(f"[{'OK ' if hits else 'MISS'}] {key:20} {len(hits)}개")
            continue
        # ★ 샤드 재사용. 지목(--only)·조회·자식·--rebuild 에서는 안 한다.
        if not (a.only or a.emit_json or a.rebuild):
            try:
                _hits = paths_for(key, e)
            except Exception:
                _hits = []                                  # 못 재면 재사용 안 한다
            _ok, _why = shardseal.check(_prev.get(key), cfg, key, _hits, OUT, _code)
            if _ok:
                results.append(_prev[key])
                print(f"[SEALED ] {key:20} 봉인 일치 — 다시 빌드하지 않는다")
                continue
            if _prev.get(key, {}).get("status") == "OK":
                print(f"          {key}: 봉인지 찢어짐 — {_why}")
        try:
            r = _spawn(key) if a.split else build(key, e, tmp)
            if r.get("status") == "OK" and not a.emit_json:
                _s = shardseal.make(cfg, key, paths_for(key, e), OUT, r.get("outputs", []), _code)
                if _s:
                    r["seal"] = _s
        except Exception as ex:
            r = {"key": key, "status": "FAIL", "error": f"{type(ex).__name__}: {ex}"}
            # ★ FAIL 이면 이 key 의 기존 산출물을 개명해 하류에서 떼어낸다.
            #   2026-08-17 ngii1k FAIL 때 8/13 gpkg 가 남아 segments 가 그것으로
            #   판정을 냈고(1093), 다음 날 진짜 실행(1091)과 갈려 "기계 간
            #   재현성 붕괴"로 오인해 반나절을 태웠다. 로직은 guards.py 정본.
            from firelane.guards import quarantine_stale
            staled = quarantine_stale(OUT, key, keys=list(cfg["datasets"]))
            if staled:
                r["staled"] = staled
                print(f"          ★ 옛 산출물 {len(staled)}개 격리(.stale_) — 하류가 못 읽는다")
        # ★ 2026-09-10. 종전에는 status 와 건수만 찍고 error 는
        #   _manifest.json 에만 적었다. 실패 사유를 보려면 JSON 을
        #   손으로 파싱해야 했고, 그 바람에 juso 3종 FAIL 의 원인을
        #   **세 번 추측**했다(vector → shp_zip_multi → raw_only).
        #   339행이 같은 병을 이미 적어놨다. 화면에 낸다.
        _st = r.get("status", "-")
        _msg = f"{r.get('features', ''):>8} feat"
        if _st in ("FAIL", "MISSING") and r.get("error"):
            _msg = str(r["error"])[:78]
        print(f"[{_st:7}] {key:20} {_msg}")
        results.append(r)
      _done = True
    finally:
        if not _done:
            # 끊겼거나 터졌다. 압축 해제분을 남기지 않는다.
            shutil.rmtree(tmp, ignore_errors=True)

    # ★ 2026-08-23. 매 실행 지웠더니 `캐시 0` 이 매번 떴다.
    #   `ngii1k` 묶음만 도엽 74장 + NGI 143장을 다시 푼다 — ingest 180초의
    #   대부분이 여기다. 그리고 `--retry-failed` 로 한 소스만 돌릴 때도
    #   그 소스가 쓰는 zip 을 통째로 다시 풀어야 했다.
    #
    #   ★ 지우는 것이 안전한 이유는 있었다 — 2026-08-13 에 `_unz_*` 8폴더
    #     1,570파일이 raw 옆에 풀려 raw 파일 수가 40배로 보였다. 그래서
    #     `.work` 가 생겼다. **지금은 raw 밖이라 그 사고가 안 난다.**
    #     `tidy.py` 가 `.work` 를 정리 대상으로 알고 있으므로 쌓이지도 않는다.
    #
    #   실패했을 때는 지운다. 반쯤 풀린 것이 다음 실행을 오염시킨다.
    _failed = any(r.get("status") == "FAIL" for r in results)
    if _failed or not a.keep_work:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        _n = sum(1 for _ in tmp.rglob("*") if _.is_file())
        print(f"  · .work 유지 {_n:,}파일 — 다음 실행이 빨라진다 "
              f"(정리: uv run python tools/tidy.py --yes)")

    # ★ 자식 모드. **대장을 쓰지 않는다.** `--check` 와 같은 선이고 같은
    #   이유다 — 부분 실행이 전체 상태를 파괴하는 것을 막는다(아래 08-31).
    #   결과는 부모가 모아서 한 번에 쓴다.
    # ★ `--check` **앞**에 둔다. `--check --emit-json` 이면 raw 실물의
    #   sha256 이 나오고 `dms.py` 가 그것을 봉인 지문으로 쓴다(PLAN #68).
    #   대장의 `source_sha256` 을 쓰면 안 된다 — 그것은 ingest 가 돌 때
    #   찍힌 값이라 **raw 가 바뀌어도 ingest 전까지 안 바뀐다.** 그 값으로
    #   대조하면 "같다" 가 항상 참인 죽은 검사가 된다.
    if a.emit_json:
        for r in results:
            print(_MARK + json.dumps(r, ensure_ascii=False, sort_keys=True))
        return 0

    # ★ 2026-08-31. **`--check` 는 조회다. 아무것도 쓰지 않는다.**
    #
    #   종전에는 `if a.check:` 가 루프를 `continue` 로 건너뛸 뿐이었고,
    #   아래 쓰기 경로로 그대로 떨어졌다. `--check` 의 레코드는
    #   `key·found·sha256` 셋뿐이라 **계보 27건을 얕은 판으로 덮었다.**
    #   그날 커밋에 `rewrite _manifest.json (95%)` 가 찍혔고 `golden` 은
    #   L1·L2·L3 전부 OK 를 냈다 — `segments.geojson` 하나만 읽으니
    #   입력 계보가 죽은 것을 모른다. 복구에 전량 재실행 317초를 태웠다.
    #
    #   같은 형태를 이 파일이 이미 두 번 겪었다 — `--only` 가 대장을
    #   통째로 덮은 것(08-22), 최상위 키를 날린 것(08-25). 셋 다
    #   **조회·부분실행이 전체 상태를 파괴**한 것이다.
    #   강제자 — `tests/test_ledger_outputs.py::test_check_does_not_write`
    if a.check:
        _miss = [r["key"] for r in results if not r["found"]]
        print(f"\n조회만 했다 — {len(results)}종 · 없음 {len(_miss)}종"
              + (f": {', '.join(_miss)}" if _miss else ""))
        print("  대장은 건드리지 않았다. 갱신하려면 --check 없이 돌린다.")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    man = OUT / "_manifest.json"

    # ★ 2026-08-22. --only 가 대장을 통째로 덮어쓰고 있었다.
    #   `--only ngii_road` 한 번에 27개 기록이 1개로 줄었고, 그 다음
    #   segments 의 계보 검사가 ngii1k=None · road_link=None ... 을 보고
    #   정당하게 거부했다. 디스크에 gpkg 는 멀쩡히 있는데 대장만 사라진 것이다.
    #
    #   §7 의 OOM 우회법(--only 로 실패분만 → 그 다음 전량)이 굴러간 이유는
    #   **뒤에 전량을 다시 돌려 대장을 재구축했기 때문**이다. 중간 상태는
    #   파괴적이었고 아무도 몰랐다. OOM 이 잦은 5GB 환경에서 --only 는
    #   우회로가 아니라 함정이다.
    #
    #   이제 기존 대장을 읽어 이번에 처리한 key 만 갈아끼운다.
    #   ★ 순서는 sources.yaml 을 따른다. 갱신 순서로 쓰면 같은 내용인데도
    #     datasets 블록의 sha 가 달라져 계보가 오탐한다(§5-4 와 같은 함정).
    if a.only and man.exists():
        try:
            prev = json.loads(man.read_text(encoding="utf-8")).get("datasets", [])
        except Exception:
            prev = []
        merged = {r["key"]: r for r in prev if isinstance(r, dict) and "key" in r}
        merged.update({r["key"]: r for r in results})
        order = list(cfg["datasets"].keys())
        results = ([merged[k] for k in order if k in merged]
                   + [v for k, v in merged.items() if k not in order])
        print(f"  · 대장 병합: 기존 {len(prev)}종 중 {len(a.only)}종 갱신 "
              f"→ {len(results)}종 유지")

    # ★ 2026-08-25. 자기 것이 아닌 최상위 키를 보존한다.
    #   종전에는 대장을 통째로 덮어써 terrain · ortho 기록을 지웠다.
    #   전량 실행에서는 뒤 단계가 다시 넣어주므로 안 보였지만
    #   `--only ingest` 는 그 기록을 날린다.
    doc = {k: v for k, v in manifest.read(man).items()
           if k not in ("generated_at", "bbox_4326", "standard_crs", "datasets")}
    doc.update({
        "generated_at": datetime.now(UTC).astimezone().isoformat(),
        "bbox_4326": BBOX_4326,
        "standard_crs": {"metric": CRS_M, "display": CRS_W},
        "datasets": results,
    })
    # ★ 내용이 같으면 쓰지 않는다. 시각만 바뀌는 diff 가 커밋을 막았다.
    wrote = manifest.write_stable(man, doc)
    print(f"\n→ {man}" + ("" if wrote else "  (내용 동일 — 갱신 없음)"))

    # ★ FAIL 이 있으면 종료코드로 알린다. 종전에는 대장에만 적고 0 을
    #   반환해서 pipeline 의 `if r.returncode:` 가 안 걸렸다 — 실패가
    #   기록되는데 파이프라인은 초록불이었다(§5-2 와 같은 계열).
    #   2026-08-21 에 ngii_road 가 FAIL 한 채 ingest 가 OK 로 끝났고,
    #   계보 검사가 우연히 막아줬을 뿐이다.
    failed = [r["key"] for r in results if r.get("status") == "FAIL"]
    if failed:
        print(f"\n★ FAIL {len(failed)}종: {' · '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    from firelane.guards import warn_direct_call

    warn_direct_call(__name__)
    # ★ 메모리로 죽은 것을 메모리로 죽었다고 말한다(stagerun.py 머리말 · §224-3a).
    from firelane.stagerun import run_stage

    run_stage(main)
