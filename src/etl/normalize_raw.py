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
★ 예외 한 곳. 폴더명 = 기관명 규칙을 깬다. 코드가 이 경로를 직접 읽으므로 고정이다.
    ngii1k        ngii1k.py 가 폴더를 rglob. ngii/ 로 합치면 연속수치지도까지 집는다
  파일명 접두사는 규칙대로 기관명(ngii_ · gjcity_)을 쓴다.

★ 기준일은 다운로드일이 아니라 데이터 기준일이다.
  원본 파일명이나 메타데이터에서 읽어 쓴다. 알 수 없으면 물어본다.

★ 확장자도 정규화 대상이다.
      .zip   SHP 세트 · 다중 파일 묶음
      .csv   모든 표 (json 으로 와도 여기서 변환한다)
      .tif   래스터 (+ 같은 이름의 .xml 메타데이터)
      .ngi   1:1,000 수치지형도 (+ .nda 속성). NGI 포맷은 변환하지 않는다
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
    # ── 2026-08-17 소방 계열 3종 재확보 ──────────────────────
    #   ★ 아래 세 줄이 위쪽 기존 규칙보다 먼저 매칭돼야 한다.
    #     "소방용수시설.?현황" 이 전남 판 좌표 파일을 summary 로 오분류했었다.
    #
    # 소화전 좌표. 전국 표준데이터 50,000행 절단본이나 광주는 전량 포함
    # (광주 197 · 동구 31 · 데이터기준일자 2024-02-07).
    # 전남 판(jngj_20250917)에는 광주가 0건이라 이것 말고 대안이 없다.
    (r"전국소방용수시설표준데이터\.(csv|json)$",
     "safety", "safety_hydrant_point_kr_20240207.csv"),
    # 소화전 집계표. 좌표는 없고 총량만 있다. 지상418+지하171 = 589.
    # "588 중 31" 공개율 논거의 분모가 이것이다. 소방차진입불가지역 컬럼도 있다.
    (r"동부소방서.*소화전.?현황",
     "safety", "safety_hydrant_summary_gj_dong_20250731.csv"),
    # 소방서·119안전센터 좌표. X좌표=위도 · Y좌표=경도 (뒤바뀐 이름이 원본 그대로다).
    # 접근 회랑과 D-28 시나리오 출발점이 여기서 나온다.
    #   대인119안전센터 35.1545794 126.9147654
    #   지산119안전센터 35.1499634 126.9385315
    # 좌표 없는 "시도 소방서 현황"(20250701)은 규칙을 두지 않는다. landing 에 남긴다.
    (r"전국소방서.?좌표현황",
     "safety", "safety_firestation_kr_20240901.csv"),
    # ── juso · 도로명주소 ────────────────────────────────────
    # 전자지도 zip 하나에 5종이 들어 있다.
    # TL_SPRD_MANAGE(도로구간) TL_SPRD_RW(실폭도로) TL_SCCO_EMD(경계)
    # TL_SPBD_BULD(건물) TL_SPBD_ENTRC(출입구)
    (r"^전남광주통합특별시_동구\.zip$",   "juso", "juso_elctrnmap_jngj_20260711.zip"),
    (r"사물주소도형.*동구\.zip$",         "juso", "juso_spotaddr_geom_jngj_20260801.zip"),
    (r"사물주소기준점.*동구\.zip$",       "juso", "juso_spotaddr_ref_jngj_20260801.zip"),
    (r"^juso_(elctrnmap|spotaddr_\w+)_jngj_\d{8}\.zip$", "juso", None),

    # ── its · 국가교통정보센터 ───────────────────────────────
    # ★ 258MB 전국이다. 광주 절단은 norm 이후 단계에서 한다.
    #   raw 는 원본 보존이 원칙이므로 여기서 자르지 않는다.
    (r"nodelinkdata\.zip$",  "its", "its_nodelink_kr_20260812.zip"),
    (r"^내역서\.csv$",       "its", "its_nodelink_changelog_20260812.csv"),
    (r"^its_nodelink_(kr|changelog)_\d{8}\.(zip|csv)$", "its", None),

    # ── ngii · 국토정보플랫폼 ────────────────────────────────
    # ★ (B020)(B060)(B080) 접두는 정규식에 넣지 않는다.
    #   브라우저가 괄호를 인코딩해 내려주는 경우가 있다.
    (r"연속수치지도_(\d{8})(\d{4})\.zip$",      "ngii", "ngii_basemap_gj{1}_{0}.zip"),
    (r"정사영상_(\d{4})_35616(\d{3})\.tif$",    "ngii", "ngii_ortho_gj{1}_{0}1231.tif"),
    (r"정사영상메타데이터_\d+35616(\d{3})\.xml$", "ngii", "ngii_ortho_gj{0}_20251231.xml"),
    (r"공개dem_35616.*\.zip$",                   "ngii", "ngii_dem_gj35616_20251117.zip"),
    (r"^ngii_(basemap|ortho|dem)_gj\w+_\d{8}\.(zip|tif|xml)$", "ngii", None),

    # ── vworld · 브이월드 ────────────────────────────────────
    # ★ ngii 와 폴더를 나눈다. 같은 수치지형도라도 원천이 다르면 폴더가 다르다.
    #   섞으면 어느 판인지 파일명만으로 구분되지 않는다. (2026-08-17)
    # ★ 도엽 zip 74개가 상위 zip 안에 중첩돼 있다. 이중 해제는 ingest 담당.
    (r"^2map1000_shp_광주_동구\.zip$", "vworld", "vworld_map1k_gjdonggu_20260307.zip"),
    (r"^vworld_map1k_gjdonggu_\d{8}\.zip$", "vworld", None),
    # ★ 2026-08-18. 같은 브이월드 동구 상품의 NGI 포맷판을 함께 받는다.
    #   SHP 판(74도엽)은 1:5,000 부모 3561609 대(동명동 북부 12도엽)를 통째로
    #   흘린다. 행정구역 수출이 1:50,000 경계에 걸친 도엽을 빠뜨리는 것으로
    #   보인다 — 북·남·서구 상품도 그 띠를 비껴가 세 묶음 합쳐 교차 0장이었다.
    #   스코프 1,091구간 중 755개(69%)의 중점이 SHP 판 폴리곤 밖이었고,
    #   그래서 폭 채택이 silpok 폴백으로 몰렸다(ngii1k 885 → 319).
    #   NGI 판에 356160983~988 · 993~998 이 있어 그 띠를 정확히 메운다.
    #   같은 도엽이 양쪽에 있으면 파서가 SHP 를 우선한다(ngii1k.collect).
    (r"^2map1000_ngi_광주_동구\.zip$", "vworld", "vworld_map1k_ngi_gjdonggu_20260307.zip"),
    (r"^vworld_map1k_ngi_gjdonggu_\d{8}\.zip$", "vworld", None),

    # ── safety · 공공데이터포털(안전) ────────────────────────
    (r"^전남광주통합특별시_cctv_(\d{8})\.csv$",     "safety", "safety_cctv_jngj_{0}.csv"),
    (r"소방\s*용수시설\s*현황_(\d{8})\.csv$",      "safety", "safety_hydrant_point_jngj_{0}.csv"),
    (r"소방통로확보대상.*_(\d{8})\.csv$",           "safety", "safety_fire_access_gj_dong_{0}.csv"),
    (r"^소방청_시도\s*소방서\s*현황_(\d{8})\.csv$", "safety", "safety_firestation_kr_{0}.csv"),
    (r"^safety_\w+_\d{8}\.csv$", "safety", None),

    # ── gjcity · 공공데이터포털(광주 동구) ───────────────────
    # ★ enforcement 가 safety 에서 여기로 옮겨왔다.
    #   폴더 = 제공기관 원칙. 불법주정차 단속은 광주 동구가 제공한다.
    (r"동구_가로등현황_(\d{8})\.csv$",              "gjcity", "gjcity_streetlight_dongu_{0}.csv"),
    (r"동구_불법\s*주정차\s*단속현황_(\d{8})\.csv$", "gjcity", "gjcity_parking_enforce_dongu_{0}.csv"),
    (r"동구_쓰레기통현황_(\d{8})\.csv$",            "gjcity", "gjcity_bin_trash_dongu_{0}.csv"),
    (r"동구_의류수거함위치_(\d{8})\.csv$",          "gjcity", "gjcity_bin_cloth_dongu_{0}.csv"),
    (r"동구_주차장정보.*(\d{8})\.csv$",             "gjcity", "gjcity_parking_dongu_{0}.csv"),
    (r"^gjcity_\w+_dongu_\d{8}\.csv$", "gjcity", None),

    # ── sbiz · 소상공인시장진흥공단 ──────────────────────────
    # ★ 다운로드 사이트가 괄호를 HTML 엔티티로 준다(&#40; &#41;).
    #   쉘·경로에서 계속 문제를 일으키므로 여기서 흡수한다.
    (r"소상공인시장진흥공단_상가.*(\d{8})\.zip$", "sbiz", "sbiz_store_kr_{0}.zip"),
    (r"^sbiz_store_kr_\d{8}\.zip$", "sbiz", None),

    # ── eais · 건축HUB ───────────────────────────────────────
    # ★ 원본이 "03. 표제부_20260817013434.csv" 다. 앞의 03 은 서식 번호이고
    #   뒤 14자리는 다운로드 시각이다. 데이터 기준일이 아니므로 앞 8자리만 쓴다.
    (r"표제부_(\d{8})\d{6}\.csv$", "eais", "eais_bldg_ledger_gjdonggu_{0}.csv"),
    (r"^eais_bldg_ledger_\w+_\d{8}\.csv$", "eais", None),
]

# 없으면 파이프라인이 도는 데 지장이 있는 것
REQUIRED = [
    "juso/juso_elctrnmap_jngj_20260711.zip",
    "vworld/vworld_map1k_gjdonggu_20260307.zip",     # 폭 산출 주 소스
    "vworld/vworld_map1k_ngi_gjdonggu_20260307.zip", # 북부 12도엽 보완분
    "its/its_nodelink_kr_20260812.zip",
    "ngii/ngii_basemap_gj9708_20260812.zip",
    "ngii/ngii_dem_gj35616_20251117.zip",
    "safety/safety_cctv_jngj_20260630.csv",
    "safety/safety_hydrant_point_kr_20240207.csv",
    "safety/safety_hydrant_summary_gj_dong_20250731.csv",
    "safety/safety_fire_access_gj_dong_20250731.csv",
    "safety/safety_firestation_kr_20240901.csv",
    "gjcity/gjcity_streetlight_dongu_20240415.csv",
    "gjcity/gjcity_parking_enforce_dongu_20240108.csv",
    "sbiz/sbiz_store_kr_20260630.zip",
    "eais/eais_bldg_ledger_gjdonggu_20260817.csv",
]

# 이번 재확보에서 못 받은 것. 결손이지 폐기가 아니다(MASTER §18-12).
# 지우면 잊는다. 목록에 남겨야 다음에 받을 때 뜬다.
MISSING = [
    "gjcity/gjcity_parking_dongu_*.csv",             # 광주 동구 주차장
    "safety/safety_hydrant_summary_jngj_*.csv",      # 소화전 집계표
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
