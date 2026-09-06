#!/usr/bin/env python3
"""
tools/ledger_add_2026_09_06.py — 2026-09-06 확보분 일곱을 대장에 등재한다.

    uv run python tools/ledger_add_2026_09_06.py          무엇이 들어갈지만
    uv run python tools/ledger_add_2026_09_06.py --apply

── 왜 도구인가 ─────────────────────────────────────────────────
★ **문서는 손으로 고친다.** 이 저장소 규약이다. 그런데 대장은 문서가
  아니라 **데이터**다 — `datalog`·`refcheck`·`encoding_check` 가 기계로
  검증하고, 항목이 일곱이면 손으로 칠 때 오타가 난다.
  `docpatch.py` 가 절 단위 교체를 도구로 하는 것과 같은 자리다.

★ 멱등이다. 이미 있는 키는 건너뛴다. 두 번 돌려도 결과가 같다.

★ **값은 전부 실물에서 잰 것이다.** `rows`·`encoding`·`columns` 는 파일을
  열어 셌고, `updated` 는 데이터기준일자 컬럼에서 읽었다. 추측이 없다.

── 대장 규약 ───────────────────────────────────────────────────
★ `url` 필드는 대장에 **없다**(54건 중 0). 제공처는 `authority` 다.
★ `scope` 는 `kr` · `jngj` · `jngj-donggu` · `jngj-dongmyeong` 넷뿐이다.
★ `updated` 는 **데이터 기준일**이지 내려받은 날이 아니다.

IN    sources.yaml
OUT   sources.yaml (--apply 일 때만)
PARAM --apply

★ FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다
  대장은 코드가 아니라 **데이터**다. 그 값은 저장소 밖 raw 실물에서
  오고, 실물이 바뀌면 대장이 따라 바뀐다 — diff 로는 못 담는다
  (raw 가 git 에 없다). `ledger_schema` · `ledger_feeds` ·
  `migrate_names` 가 같은 자리다.

★ **`sources.yaml` 만 건드린다.** `src/` · `docs/` 는 안 만진다 —
  그것이 예외의 핵심 조건이다(test_no_source_patching_scripts).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "sources.yaml"

# `datasets:` 블록의 끝. 이 키 바로 앞에 끼워넣는다.
ANCHOR = "\nraw_only:"

BLOCK = '''
  bldg_ledger_dm:
    stem:       moli_bldg_ledger_dm
    ext:        [json]
    scope:      jngj-dongmyeong
    updated:    "2026-09-06"
    authority:  국토교통부 건축행정시스템
    kind:       json_table
    encoding:   utf-8
    what:       건축물대장 표제부. 동명동 1,989동 · 필드 77
    feeds:      미투입 — β 점유위험도(#62) · 원룸 판별 · 건물높이 대조축
    feeds_why: |
      ★ **이 파일 하나가 세 문제를 푼다.**
        ① 원룸 판별 — 단독주택 932동 중 다가구(가구3+) 170 · 2가구 184.
          상세주소DB 는 "몇 동 몇 호" 를 주지만 **원룸인지는 안 준다.**
        ② β 근거 — 가구+세대 2,431 대 주차면 1,792. 주거건물 951동 중
          **주차 0 인 곳이 803동(84%)**. 그 차들은 골목에 선다.
          단속 이력은 "적발된 것" 만 보는데 이것은 **압력 자체**를 준다.
        ③ 건물높이 523동 — buildings.h(층수 추정)의 실측 대조축.
    note: |
      ★ **좌표가 없다.** 대지위치(지번) 1,989 · 도로명대지위치 1,873 뿐.
        jijeok(24,183) 이나 building 폴리곤과 **지번으로 붙여야** 한다.
      ★ {Description, Data} 구조다. Description 이 필드 사전이다.
      ★ 광주 동구 주차 확보율은 통계상 136.3% 인데 동명동 주거는 31% 다.
        상업·업무가 평균을 끌어올린 것 — **주차장은 있는데 사람 사는 곳에
        없다.** 이 괴리가 β 의 논거다.
    contract:
      encoding: utf-8
      rows: 1989
      required_cols: [PLOT_PSTN, MN_USG_CD_NM, FML_CNT, HH_CNT]
    schema:
      root: {Description: 필드사전, Data: 행배열}
      columns_used: [PLOT_PSTN, ROAD_NM_PLOT_PSTN, BLDG_NM, MN_USG_CD_NM,
                     FML_CNT, HH_CNT, HG, GRND_NOFL, INDR_SFPRPL_CNTOM,
                     OTDR_SFPRPL_CNTOM, INDR_MCNCL_CNTOM, OTDR_MCNCL_CNTOM]
      encoding_seen: utf-8

  child_zone_std:
    stem:       mois_child_zone_std
    ext:        [json]
    scope:      kr
    updated:    "2026-07-28"
    authority:  행정안전부 (전국 표준데이터)
    kind:       json_table
    encoding:   utf-8
    what:       전국 어린이보호구역 14,652 → 광주 동구 32 → 스코프 8
    feeds:      미투입 — TBT 안내 · A* 우회 가중치(#2) · **폭 판정 대조축**
    feeds_why: |
      ★ `보호구역도로폭` 이 **행정 고시값**이다. 폭 판정의 외부 대조축이
        하나 더 생긴다 — 지금은 ngii1k_center 하나뿐이다.
        스코프 표본에서 셋이 1m 안쪽으로 일치했다
        (중앙초 5m/6.01 · 서석초 6m/6.53 · 동구어린이집 15m/16.4).
      ★ 대장의 school_zone(32곳)과 **같은 대상이다.** 그쪽은 주소만 있어
        지오코딩이 필요했는데 이쪽은 좌표가 붙어 온다.
    note: |
      ★ 보호구역 **경계 폴리곤이 아니다.** 시설 좌표뿐이라 반경으로
        근사해야 하고, 그 반경이 또 미검증 상수가 된다.
      ★ 전국분이다. 스코프 밖 14,644건은 ingest 에서 버린다.
    contract:
      encoding: utf-8
      rows: 14652
      required_cols: [대상시설명, 위도, 경도, 소재지도로명주소]
    schema:
      root: {fields: 필드정의, records: 행배열}
      columns: [시설종류, 대상시설명, 소재지도로명주소, 소재지지번주소,
                위도, 경도, 관리기관명, 관할경찰서명, CCTV설치여부,
                CCTV설치대수, 보호구역도로폭, 데이터기준일자]
      encoding_seen: utf-8

  senior_zone_std:
    stem:       mois_senior_zone_std
    ext:        [json]
    scope:      kr
    updated:    "2026-06-19"
    authority:  행정안전부 (전국 표준데이터)
    kind:       json_table
    encoding:   utf-8
    what:       전국 노인·장애인보호구역 4,120 → 광주 동구 17 → 스코프 10
    feeds:      미투입 — TBT 안내 · A* 우회 가중치(#2)
    feeds_why:  보호구역 제한속도 30km/h. 어린이보호구역과 같은 축이다
    note: |
      ★ `장소유형코드` 가 1(노인) · 2(장애인) 이다. 문자열이 아니다.
      ★ `보호구역도로폭` 은 동구 17건 중 1건만 채워져 있다 —
        대조축으로는 child_zone_std 만 쓴다.
    contract:
      encoding: utf-8
      rows: 4120
      required_cols: [대상시설명, 위도, 경도, 제한속도]
    schema:
      root: {fields: 필드정의, records: 행배열}
      columns: [장소유형코드, 대상시설명, 시도명, 시군구명, 시군구코드,
                소재지도로명주소, 소재지지번주소, 위도, 경도, 제한속도,
                보호구역도로폭, 데이터기준일자]
      encoding_seen: utf-8

  speedbump:
    stem:       gjcity_speedbump
    ext:        [csv]
    scope:      jngj-donggu
    updated:    "2023-04-05"
    authority:  동구청 건설과
    kind:       csv_table
    encoding:   cp949
    what:       동구 과속방지턱 342개소 → 스코프 46
    feeds:      미투입 — TBT 안내
    feeds_why: |
      스코프 46개. 전부 소로 · 규격 미달(N) · 원호형 28 · 가상형 18.
      ★ `가상형` 은 도색만 있고 실제 턱이 없다 — 데이터는 남기되 안내
        여부는 앱이 정한다(domain/hazard.ts::shouldAnnounce).
    note: |
      ★ **기준일자가 2023-04-05 다. 3년 묵었다.** 그 사이 신설·철거가
        있었을 수 있고, 화면이 그것을 확정으로 말하면 안 된다.
      ★ `과속방지턱높이` 는 스코프 46건 전량 0 이다. 미기입 필드라 못 쓴다.
      ★ 행정안전부 REST API 의 **스냅샷**이다. 앱에서 API 를 부르지 않는다 —
        서버가 없고, 응답이 바뀌면 golden 이 깨진다. 파일이면 sha 로 못박힌다.
        인증키는 저장소에 넣지 않는다.
    contract:
      encoding: cp949
      rows: 342
      required_cols: [WGS84위도, WGS84경도, 설치장소, 과속방지턱형태구분]
    schema:
      columns: [개방자치단체코드, 관리번호, 과속방지턱관리번호, 도로명, 시도명,
                시군구명, 소재지도로명주소, 소재지지번주소, 설치장소,
                과속방지턱재료, 과속방지턱형태구분, 과속방지턱높이,
                과속방지턱폭, 과속방지턱연장, 도로유형구분, 규격여부,
                WGS84위도, WGS84경도, 보차분리여부, 연속형여부,
                과속방지턱설치연도, 관리기관명, 관리기관전화번호,
                데이터기준일자, 데이터갱신구분, 데이터갱신시점, 최종수정시점]
      encoding_seen: cp949

  admin_cctv:
    stem:       gjcity_admin_cctv
    ext:        [csv]
    scope:      jngj-donggu
    updated:    "2020-08-14"
    authority:  서남동행정복지센터
    kind:       csv_table
    encoding:   cp949
    what:       동구 행정 CCTV 81대 (쓰레기단속·생활방범·다목적) → 스코프 33
    feeds:      미투입 — bin_trash 대조축
    feeds_why: |
      ★ **영상판정에 못 쓴다.** 목적이 노면이 아니다 — 스코프 33건 중
        쓰레기단속이 26건이고 화각이 배출지를 향한다.
        우리 cctv(방범 678건)와 **다른 자산이다.**
      ★ 대신 **쓰레기 배출지는 골목의 고정 장애물**이다. bin_trash 31건의
        대조축으로 쓴다.
    note: |
      ★ **기준일자가 2020-08-14 다. 6년 묵었다.** 판정에 쓰지 마라.
      ★ `시군구명` 컬럼이 없다. 파일 자체가 동구분이다.
      ★ 화각을 확인하면 일부는 영상판정에 쓸 수도 있다 — 지금은 못 한다.
    contract:
      encoding: cp949
      rows: 81
      required_cols: [WGS84위도, WGS84경도, 설치목적구분, 관리기관명]
    schema:
      columns: [개방자치단체코드, 관리번호, 관리기관명, 소재지도로명주소,
                소재지지번주소, 설치목적구분, 카메라대수, 카메라화소수,
                촬영방면정보, 보관일수, 설치연월, 관리기관전화번호,
                WGS84위도, WGS84경도, 데이터기준일자, 데이터갱신구분,
                데이터갱신시점, 최종수정시점]
      encoding_seen: cp949

  speed_cam:
    stem:       gjbg_traffic_cam
    ext:        [csv]
    scope:      jngj
    updated:    "2025-12-31"
    authority:  광주광역시 빅데이터 통합플랫폼
    kind:       csv_table
    encoding:   utf-8-sig
    what:       광주 무인교통단속카메라 510 → 동구 49 → 스코프 9
    feeds:      미투입 — **실측 제한속도** · TBT 안내
    feeds_why: |
      ★ `제한속도` 가 **실측값**이다. domain/speed.ts 의 폭 추정을 덮는다.
        준법로 폭 18.6m → 표 추정 50km/h → **실제 30km/h**(동산초교 스쿨존).
        폭만 보면 절대 못 얻는 값이다.
      ★ 스코프 9곳이 전부 큰길이다 — 30km/h 스쿨존 6 · 50km/h 사거리 3.
        **골목에는 하나도 없다.**
      ★ `보호구역구분`(2=어린이)이 child_zone_std 와 교차 검증된다.
    note: |
      ★ 소방차는 긴급자동차라 과속단속 대상이 아니다. 안내는 상용 동등성을
        위한 것이지 기능이 아니다 — **제한속도 쪽이 본체다.**
      ★ 기준일자 컬럼이 없다. 파일명의 2025 를 따랐다.
      ★ 인코딩이 utf-8-sig 다. 다른 지자체 CSV(cp949)와 다르다.
    contract:
      encoding: utf-8-sig
      rows: 510
      required_cols: [위도, 경도, 제한속도, 설치장소, 시군구명]
    schema:
      columns: [무인교통단속카메라관리번호, 시군구명, 도로노선번호, 도로노선명,
                도로노선방향, 위도, 경도, 설치장소, 단속구분, 제한속도,
                보호구역구분, 설치년도]
      encoding_seen: utf-8-sig

  juso_building_db:
    stem:       juso_building_db
    ext:        [zip]
    scope:      jngj
    updated:    "2026-07"
    authority:  행정안전부 도로명주소
    kind:       text_table
    encoding:   cp949
    what:       도로명주소 건물DB. 전남광주 205MB → 동명동 5,718
    feeds:      미투입 — 목적지 검색(건물명)
    feeds_why: |
      poi.geojson 은 상가 2,077 뿐이라 **학교·병원·관공서가 통째로 없다.**
      전남여자고등학교가 검색에 안 잡히는 이유다. 이 파일에 건물명이 있다.
    note: |
      ★ **좌표가 없다.** 주소 DB 라 건물명·도로명·건물번호만 있다.
        지도에 찍으려면 juso 내비게이션용DB(건물중심점·출입구 좌표)가
        필요하다 — 승인 대기.
      ★ `|` 구분 · CRLF 개행 · cp949.
      ★ **전국 전체분을 raw 에 넣지 마라.** build_jeonnamgwangju.txt 가
        205MB 다. 동명동 5,718건만 잘라낸다 — enforcement(8.1MB)가
        용량으로 retired 됐다.
    contract:
      encoding: cp949
      delimiter: "|"
    schema:
      files: [build_jeonnamgwangju.txt, jibun_jeonnamgwangju.txt]
      primary: build_jeonnamgwangju.txt
      encoding_seen: cp949
'''

KEYS = re.findall(r"^  (\w+):$", BLOCK, re.M)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not F.exists():
        print(f"★ {F} 가 없다"); return 1
    txt = F.read_text(encoding="utf-8")

    have = [k for k in KEYS if re.search(rf"^  {k}:$", txt, re.M)]
    todo = [k for k in KEYS if k not in have]
    for k in have:
        print(f"  이미 있음  {k}")
    for k in todo:
        print(f"  추가       {k}")
    if not todo:
        print("\n전부 등재됨. 할 일 없음")
        return 0

    if txt.count(ANCHOR) != 1:
        print(f"★ 앵커 `raw_only:` 가 {txt.count(ANCHOR)}번 나온다 (1이어야 한다).")
        print("  datasets 블록 끝에 손으로 넣어라.")
        return 1

    block = "".join(
        m.group(0) for m in re.finditer(
            r"\n  \w+:\n(?:(?:    |\n).*\n?)*", BLOCK)
        if re.match(r"\n  (\w+):", m.group(0)).group(1) in todo)

    print(f"\n{'적용' if a.apply else '예정'} {len(todo)}건")
    if a.apply:
        F.write_text(txt.replace(ANCHOR, block + ANCHOR, 1), encoding="utf-8")
        print("  sources.yaml 갱신")
        print("\n확인:")
        print("  uv run python -m firelane.datalog")
        print("  uv run python tools/refcheck.py")
    else:
        print("  실행:  uv run python tools/ledger_add_2026_09_06.py --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
