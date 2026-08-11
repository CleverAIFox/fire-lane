#!/usr/bin/env python3
"""
normalize_raw.py — 다운로드 폴더의 원본을 명명규칙에 맞게 data/raw 로 배치한다.

    python src/etl/normalize_raw.py                      # 기본 다운로드 폴더 탐색
    python src/etl/normalize_raw.py /mnt/c/Users/Fox/Downloads
    python src/etl/normalize_raw.py <폴더> --move        # 복사 대신 이동
    python src/etl/normalize_raw.py <폴더> --in-place    # 그 자리에서 이름만 정리
    python src/etl/normalize_raw.py <폴더> --dry-run

명명규칙 (data/raw/README.md)
    {기관}_{데이터}_{범위}_{기준일}.{확장자}
    폴더명 = 기관명

기관별 폴더
    juso ngii its sbiz safety gjcity nsdi

★ 기준일은 다운로드일이 아니라 데이터 기준일이다.
  원본 파일명이나 메타데이터에서 읽어 쓴다. 알 수 없으면 물어본다.

★ 확장자도 정규화 대상이다.
      .zip   SHP 세트 · 다중 파일 묶음
      .csv   모든 표 (json 으로 와도 여기서 변환한다)
      .tif   래스터 (+ 같은 이름의 .xml 메타데이터)
  같은 데이터셋이 csv 였다가 json 으로 내려오는 일이 흔하다.
  그때마다 ingest 의 kind 를 바꾸면 파이프라인이 흔들리므로 여기서 맞춘다.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW  # noqa: E402

for st in (sys.stdout, sys.stderr):
    try:
        st.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 원본 파일명 패턴 → (폴더, 목적지 파일명)
# 정규식은 소문자 변환 후 매칭한다. 괄호는 브라우저가 &#40; 로 바꾸기도 해서 느슨하게 본다.
RULES: list[tuple[str, str, str]] = [
    # 도로명주소
    (r"전남광주통합특별시_동구\.zip$",           "juso",   "juso_elctrnmap_jngj_20260711.zip"),
    (r"도로도형_전체분",                          "juso",   "juso_road_geom_jngj_20260701.zip"),
    # 국토지리정보원
    (r"b030.*국가기본공간정보.*7824",             "ngii",   "ngii_basemap_gj048_20260806.zip"),
    (r"b030.*국가기본공간정보.*7825",             "ngii",   "ngii_basemap_gj037_20260806.zip"),
    (r"b030.*국가기본공간정보.*7832",             "ngii",   "ngii_basemap_gj038_20260807.zip"),
    (r"b030.*국가기본공간정보.*7833",             "ngii",   "ngii_basemap_gj047_20260807.zip"),
    (r"b080.*공개dem.*35616",                     "ngii",   "ngii_dem_gj35616_20251117.zip"),
    (r"b060.*정사영상_\d+_35616(\d{3})\.tif$",    "ngii",   "ngii_ortho_gj{0}_20251231.tif"),
    (r"b060.*정사영상메타데이터_\d+35616(\d{3})\.xml$", "ngii", "ngii_ortho_gj{0}_20251231.xml"),
    # 교통
    (r"nodelinkdata\.zip$",                       "its",    "its_nodelink_kr_20260810.zip"),
    (r"^내역서\.csv$",                            "its",    "its_nodelink_changelog_20260810.csv"),
    # 상권
    (r"소상공인시장진흥공단_상가",                "sbiz",   "sbiz_store_kr_20260630.zip"),
    # 안전
    (r"전남광주통합특별시_cctv",                  "safety", "safety_cctv_jngj_20260630.csv"),
    (r"전국소방서.?좌표현황",                     "safety", "safety_firestation_kr_20240901.csv"),
    # ★ 표는 전부 csv 로 통일한다. 같은 데이터셋이 csv 였다가 json 으로 오기도 한다.
    #   포맷이 흔들리면 ingest 의 kind 도 흔들린다. 여기서 한 번에 맞춘다.
    (r"전국소방용수시설표준데이터\.json$",        "safety", "safety_hydrant_point_kr_20260811.csv"),
    (r"소방통로확보대상",                         "safety", "safety_fire_access_gj_dong_20250731.csv"),
    (r"소방청_연간화재통계",                      "safety", "safety_fire_stat_kr_20241231.csv"),
    (r"불법.?주정차.*단속|주정차.*단속현황",      "safety", "safety_parking_enforce_dongu_20240108.csv"),
    (r"소방용수시설.?현황",                       "safety", "safety_hydrant_summary_jngj_20251231.csv"),
    # 광주광역시·산하기관
    (r"전남광주통합특별시_동구_주차장정보",       "gjcity", "gjcity_parking_dongu_20260811.csv"),
    (r"광주광역시도시공사_주차장정보",            "gjcity", "gjcity_parking_corp_20260811.csv"),
    # 공간정보
    (r"건물.*변동|building_change",               "nsdi",   "nsdi_building_change_kr_20260806.zip"),
]

# 없으면 파이프라인이 도는 데 지장이 있는 것
REQUIRED = [
    "juso/juso_elctrnmap_jngj_20260711.zip",
    "its/its_nodelink_kr_20260810.zip",
    "ngii/ngii_basemap_gj037_20260806.zip",
    "sbiz/sbiz_store_kr_20260630.zip",
    "safety/safety_cctv_jngj_20260630.csv",
    "safety/safety_firestation_kr_20240901.csv",
    "safety/safety_fire_access_gj_dong_20250731.csv",
    "gjcity/gjcity_parking_dongu_20260811.csv",
    "safety/safety_parking_enforce_dongu_20240108.csv",
    "safety/safety_hydrant_summary_jngj_20251231.csv",
]


def convert(src: Path, dst: Path) -> bool:
    """확장자가 바뀌는 경우 내용을 변환한다. 아니면 False.

    표(csv/json)는 csv 로 통일한다. 공공데이터포털 표준데이터가
    csv 였다가 json 으로 바뀌어 내려오는 일이 흔한데, 그때마다
    ingest 의 kind 를 바꾸면 파이프라인이 흔들린다.
    """
    if src.suffix.lower() == ".json" and dst.suffix.lower() == ".csv":
        import csv as _csv
        import json as _json
        d = _json.loads(src.read_text(encoding="utf-8"))
        rows = d.get("records", d if isinstance(d, list) else [])
        if not rows:
            return False
        with dst.open("w", encoding="utf-8-sig", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        return True
    return False


def find_downloads() -> Path | None:
    for c in (Path.home() / "Downloads",
              Path("/mnt/c/Users") ):
        if c.name == "Downloads" and c.is_dir():
            return c
        if c.is_dir():
            for u in c.iterdir():
                d = u / "Downloads"
                if d.is_dir() and any(d.iterdir()):
                    return d
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", help="다운로드 폴더")
    ap.add_argument("--move", action="store_true", help="복사 대신 이동")
    ap.add_argument("--in-place", action="store_true",
                    help="폴더로 옮기지 않고 그 자리에서 이름만 바꾼다(보관용 원본 정리)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = Path(a.src).expanduser() if a.src else find_downloads()
    if not src or not src.is_dir():
        print("다운로드 폴더를 찾지 못했다. 경로를 직접 넘길 것")
        return
    print(f"원본  {src}")
    print(f"대상  {RAW}\n")

    # ★ 이미 규칙에 맞는 이름이면 그대로 배치한다.
    #   --in-place 로 한 번 정리한 폴더를 다시 원본으로 쓸 수 있어야 한다.
    ORG = {"juso", "ngii", "its", "sbiz", "safety", "gjcity", "nsdi"}
    for org in ORG:
        RULES.append((rf"^{org}_[a-z0-9_]+_\d{{8}}\.(zip|csv|tif|xml)$", org, None))

    files = [f for f in src.iterdir() if f.is_file()]
    done, skip = [], []
    for f in files:
        low = f.name.lower()
        for pat, folder, tmpl in RULES:
            m = re.search(pat, low)
            if not m:
                continue
            name = f.name if tmpl is None else (tmpl.format(*m.groups()) if m.groups() else tmpl)
            dst = (src / name) if a.in_place else (RAW / folder / name)
            if dst == f or (dst.exists() and dst.stat().st_size == f.stat().st_size):
                skip.append((f.name, name if a.in_place else f"{folder}/{name}"))
                break
            size = f.stat().st_size      # ★ move 하면 원본이 사라지므로 먼저 잰다
            if not a.dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if convert(f, dst):
                    f.unlink()               # 변환했으면 원본 포맷은 남기지 않는다
                elif a.in_place or a.move:
                    shutil.move(str(f), str(dst))
                else:
                    # ★ copy2 는 utime, copy 는 chmod 를 복사하는데
                    #   exFAT/9p(WSL 외장) 에서 EPERM 이 난다. copyfile 은 내용만 복사한다.
                    shutil.copyfile(str(f), str(dst))
            done.append((f.name, name if a.in_place else f"{folder}/{name}", size))
            break

    for o, n, sz in done:
        print(f"  {'→' if not a.dry_run else '·'} {n:52s} {sz/1e6:8.1f} MB   ← {o[:38]}")
    if skip:
        print(f"\n  이미 있음 {len(skip)}건")
    unmatched = [f.name for f in files
                 if not any(f.name == o for o, _, _ in done)
                 and not any(f.name == o for o, _ in skip)]
    if unmatched:
        print(f"\n  규칙에 없는 파일 {len(unmatched)}건 (건너뜀)")
        for u in unmatched[:12]:
            print(f"    {u}")

    if a.in_place:
        print(f"\n제자리 정리 완료. 파일명·확장자가 규칙에 맞다.")
        print(f"작업용 사본을 만들려면:  python src/etl/normalize_raw.py {src}")
        return

    print("\n[필수 파일 점검]")
    miss = []
    for r in REQUIRED:
        ok = (RAW / r).exists()
        print(f"  {'OK  ' if ok else '★없음'} {r}")
        if not ok:
            miss.append(r)
    if miss:
        print(f"\n  {len(miss)}건 부족. sources.yaml 의 url 로 재취득할 것")
    else:
        print("\n  전부 확보. python src/etl/ingest.py 로 진행")

    if RAW.is_dir():
        n = sum(1 for _ in RAW.rglob("*") if _.is_file())
        sz = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e9
        print(f"\ndata/raw  {n}개 파일 · {sz:.2f} GB")


if __name__ == "__main__":
    main()
