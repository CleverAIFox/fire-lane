#!/usr/bin/env python3
"""
b2_close.py — B2 **마감**. 남은 열 건을 전부 닫는다.

    uv run python tools/b2_close.py            무엇을 할지만
    uv run python tools/b2_close.py --apply    실제로

멱등이다. `b2_lake.py` 다음에 돈다.

닫는 것 —

  ⑥ retired 3종에 stem       ★ ledger_fields --apply 의 파괴를 막는 선행 조건
  ⑦ 미등재 격리 1건 등재      hydrant_point_kr_truncated 11.3MB
  ⑧ norm 고아 1건 제거        eais_bldg_ledger — 폐기 자산의 파생
  ⑨ landing 이관              승인분 6종 + 사물주소 1종
  ⑩ landing_disposition       8건 처분 기록 · held 를 넷째 action 으로
  ⑪ 승인분 4종 대장 등재       ★ 반입 전에 적는다
  ⑫ verify.sh 배선            lakecheck 를 게이트에

★ `sources.yaml` 은 주석이 본체라 텍스트로 고친다. 대신 파싱 키 집합을
  전후 대조해서 항목이 사라지면 되돌린다(`b2_lake.Ledger` 와 같은 방식).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sources.yaml"


def keyset(text: str) -> set[str]:
    d = yaml.safe_load(text) or {}
    out: set[str] = set()
    for blk, items in d.items():
        out.add(blk)
        if isinstance(items, dict):
            for k, v in items.items():
                out.add(f"{blk}.{k}")
                if isinstance(v, dict):
                    out |= {f"{blk}.{k}.{f}" for f in v}
    return out


class Ledger:
    def __init__(self) -> None:
        self.orig = LEDGER.read_text(encoding="utf-8")
        self.text = self.orig
        self.log: list[str] = []
        self.skip: list[str] = []

    def sub(self, old: str, new: str, *, why: str) -> Ledger:
        n = self.text.count(old)
        if n == 0:
            self.skip.append(why)
            return self
        if n > 1:
            raise RuntimeError(f"`{old[:44]}` 가 {n}건이다. 모호하면 안 바꾼다")
        self.text = self.text.replace(old, new, 1)
        self.log.append(why)
        return self

    def commit(self, *, apply: bool) -> bool:
        if self.text == self.orig:
            print(f"  = sources.yaml  변경 없음 ({len(self.skip)}건 이미 적용)")
            return True
        try:
            after = keyset(self.text)
        except yaml.YAMLError as e:
            print(f"  ✗ sources.yaml  YAML 오류 — {e}")
            return False
        lost = keyset(self.orig) - after
        if lost:
            print(f"  ✗ sources.yaml  **키가 사라졌다** — {sorted(lost)[:6]}")
            return False
        print(f"  {'→' if apply else '·'} sources.yaml")
        for x in self.log:
            print(f"      + {x}")
        for x in self.skip:
            print(f"      = {x} (이미 적용)")
        new_keys = sorted(after - keyset(self.orig))
        if new_keys:
            print(f"      새 키 {len(new_keys)}개 — {new_keys[:5]}")
        if apply:
            LEDGER.write_text(self.text, encoding="utf-8")
        return True


# ── ⑥ retired 3종에 stem ────────────────────────────────────────
# ★ 이 셋은 실물이 _quarantine 에 있고, `file`/`files` 가 **재유입을 막는
#   유일한 근거**다. stem 없이 별칭을 지우면 acquire 가 폐기 자료를 다시
#   받아들인다. 그래서 stem 을 먼저 채운다 — 순서를 뒤집으면 안 된다.
# ★ provider·source_hint 도 같이 넣는다. retired 머리말이 "없으면 3개월 뒤
#   또 받고 또 조사한다" 고 적는데, **어디서 받았는지**가 빠져 있으면 그
#   목적을 못 이룬다. 지금 1663144302440.hwp 를 못 찾는 게 그 결과다.
RETIRED = [
    ("  kfs_paint_marking_20241224:\n"
     "    what: 소방차 도장 및 표지 (KFS-1-0006-2024-01)\n"
     "    files:\n"
     "      - safety/safety_kfs_paint_marking_kr_20241224.pdf\n",
     "  kfs_paint_marking_20241224:\n"
     "    what: 소방차 도장 및 표지 (KFS-1-0006-2024-01)\n"
     "    stem: safety_kfs_paint_marking\n"
     "    ext: [pdf]\n"
     "    provider: safety\n"
     "    source_hint: 소방청 소방장비 기술기준(KFS) 고시 첨부\n"
     "    files:\n"
     "      - safety/safety_kfs_paint_marking_kr_20241224.pdf\n",
     "retired.kfs_paint_marking — stem·provider·source_hint"),

    ("  firestation_kr_20250701:\n"
     "    what: 소방청 시도 소방서 현황 (2025-07-01 판)\n"
     "    file: safety/safety_firestation_kr_20250701.csv\n",
     "  firestation_kr_20250701:\n"
     "    what: 소방청 시도 소방서 현황 (2025-07-01 판)\n"
     "    stem: safety_firestation\n"
     "    ext: [csv]\n"
     "    provider: safety\n"
     "    source_hint: 공공데이터포털 소방청 표준데이터\n"
     "    file: safety/safety_firestation_kr_20250701.csv\n",
     "retired.firestation_kr — stem·provider·source_hint"),

    ("  hydrant_point_jngj_20250917:\n"
     "    what: 전남광주통합특별시 소방 용수시설 현황 (2025-09-17)\n"
     "    file: safety/safety_hydrant_point_jngj_20250917.csv\n",
     "  hydrant_point_jngj_20250917:\n"
     "    what: 전남광주통합특별시 소방 용수시설 현황 (2025-09-17)\n"
     "    stem: safety_hydrant_point\n"
     "    ext: [csv]\n"
     "    provider: safety\n"
     "    source_hint: 전남광주통합특별시 소방본부\n"
     "    file: safety/safety_hydrant_point_jngj_20250917.csv\n",
     "retired.hydrant_point_jngj — stem·provider·source_hint"),
]


# ── ⑦ 미등재 격리 1건 ───────────────────────────────────────────
# ★ 11.3MB 가 대장 어디에도 없다. 그런데 이것이 sources.yaml 이 세 번 인용한
#   "딱 떨어지는 행수는 상한이다" 교훈의 **유일한 물증**이다. 지우지 않는다.
TRUNCATED = """  hydrant_point_kr_20240207_truncated:
    what: 전국 소방용수시설 표준데이터 — 50,000행 절단본 (2024-02-07)
    stem: safety_hydrant_point
    ext: [csv]
    provider: safety
    source_hint: 공공데이터포털 CSV 내려받기 (상한 50,000행)
    file: safety/safety_hydrant_point_kr_20240207_truncated.csv
    at: '2026-09-10'
    successor: hydrant_point (safety_hydrant_point_jngj_20240207.csv)
    reason: |
      포털 CSV 내려받기 상한 50,000 에 걸려 잘린 판이다. 재취득한 전량과
      비교하면 종전 197건이 새 파일에 **전부 포함**된다(겹침 197 · 기존에만 0)
      — 커버리지가 다른 것이 아니라 잘린 것이고 새 파일이 상위집합이다.
      ★ 지우지 않는다. 이것이 "딱 떨어지는 행수는 자연수가 아니라 상한이다.
        50,000 · 10,000 · 1,000 을 보면 의심해야 한다" 의 유일한 물증이다.
        종전 contract.rows 가 50000 이라 상한을 정상으로 인정하고 있었다.
      ★ 2026-09-10 lakecheck L2 가 "격리 사유가 대장에 없다" 로 잡아냈다.

"""


# ── ⑨⑩ landing ────────────────────────────────────────────────
MOVE = [
    "건물도형_전체분_전남광주통합특별시_동구.zip",
    "건물군내동도형_전체분_전남광주통합특별시_동구.zip",
    "사물주소도형_전체분_전남광주통합특별시_동구.zip",
    "기타자료_전체분_전남광주통합특별시_동구.zip",
    "도로명주소 건물 도형.zip",
    "건물군 내 상세주소 동 도형.zip",
    "202607_사물주소_전체분.zip",
]

DISPOSITION = """    # ── 2026-09-10 추가 ────────────────────────────────────────
    # ★ action 에 `held` 를 더한다. **판단 보류도 처분이다** — 안 적힌 것과
    #   다르다. _quarantine 이 "판단 보류지 폐기가 아니다" 인 것과 같다.
    #   landing 은 backup·committed 가 둘 다 false 라 소실 대기 상태이므로,
    #   무엇이 왜 거기 있는지가 적혀 있어야 한다.
    - file: 건물도형_전체분_전남광주통합특별시_동구.zip
      key: juso_bldg_geom
      action: ledgered
      why: >-
        ★ 2026-09-10 승인. 건물 15,518 · 출입구 17,069 · 접속선 15,518.
        TL_SPOT_CNTC 가 건물 출입구와 도로를 잇고 접속거리를 준다
        (중앙 7.6m · 최대 402m) — 출동 종점이 "도로 위 최근접점" 이
        아니라 실제 출입구가 된다.
    - file: 건물군내동도형_전체분_전남광주통합특별시_동구.zip
      key: juso_bldggrp_geom
      action: ledgered
      why: 건물군 내 동 도형 8,221 · 동 출입구 939. 아파트 단지 내부 진입.
    - file: 사물주소도형_전체분_전남광주통합특별시_동구.zip
      key: juso_spotaddr_geom_2608
      action: ledgered
      why: >-
        소화전 30 · 비상급수 12 · 버스정류장 190. 186파일 중 다수가 0건
        빈 껍데기다. ★ LMTT_HG(제한높이)가 전 레이어 0.0 이라 높이
        판정에는 못 쓴다 — 컬럼이 있다고 값이 있는 것이 아니다.
    - file: 기타자료_전체분_전남광주통합특별시_동구.zip
      key: juso_etc_geom
      action: ledgered
      why: >-
        ★ 터널 10(지산·산수·지원·소태) · 고가 4(너릿재로·제2순환로) ·
        교량 36. sources.yaml 이 "동명동에 터널·고가 하부는 없다" 를
        근거 없이 단정했는데 이것이 확인 수단이다.
    - file: 도로명주소 건물 도형.zip
      key: null
      action: retired
      why: AlterD 일변동분 31개. 전체분(건물도형)이 있으면 불필요하다.
    - file: 건물군 내 상세주소 동 도형.zip
      key: null
      action: retired
      why: AlterD 일변동분 31개. 전체분(건물군내동도형)이 있으면 불필요하다.
    - file: 202607_사물주소_전체분.zip
      key: null
      action: held
      why: >-
        전국분이다. 동구 판(사물주소도형_전체분)이 이미 있어 우선순위가
        낮다. 전국 비교가 필요해지면 그때 자른다.
    - file: 202608_내비게이션용DB_전체분.7z
      key: null
      action: held
      why: >-
        ★ 2026-09-10 승인. match_build_*.txt 시도별 전량이라 풀면 수 GB다.
        juso_building_db 선례대로 match_build_jeonnamgwangju.txt 만 뽑아
        법정동 1221010800 으로 자른다. 자른 결과가 csv 로 들어가면
        `.7z` 가 ext 어휘 밖인 문제도 같이 없어진다 — 어휘를 넓히지 않는다.
    - file: 202608_상세주소DB_전체분.zip
      key: null
      action: held
      why: 승인 계열. 상세주소는 원룸 구분을 안 주므로 우선순위가 낮다.
    - file: 202607_상세주소 표시_전체분.zip
      key: null
      action: held
      why: 승인 계열. 위와 같다.
    - file: 202608_주소DB_전체분.zip
      key: null
      action: held
      why: 좌표가 없다. 내비게이션용DB 와 짝이어야 지도에 찍힌다.
    - file: 민원행정기관전자지도_240124.zip
      key: null
      action: held
      why: >-
        SHP 세트. 내부 한글 파일명이 CP437 로 깨져 있다(CP949 로 되돌려
        매칭). 정체 확인 전까지 보류한다.
    - file: 제35회+동구통계연보(2024기준).pdf
      key: null
      action: held
      why: 244MB 참조용. 인구·시설 통계이며 진입 판정에 직접 쓰지 않는다.
    - file: 1663144302440.hwp
      key: gjcity_road_facility
      action: ledgered
      why: >-
        ★ 도로시설물 현황 378개소 — 교량 207 · 지하차도 15 · 터널/공동구 17 ·
        고가교 14. 동구 지명 출현 지산 4 · 서석 1 · 두암 1 · 동구 2.
        기타자료 SHP 와 함께 "터널·고가 없음" 단정의 확인 근거다.
        ★ 제공처 미상. 2026-09-06 에 hwp 를 열어 PDF 로 저장한 흔적만
        남았고(Creator Hwp 2020 · CreationDate 20260906) 원본 URL 을 잃었다.
        기관은 내용으로 확정했다 — 광주 전역 시설물이므로 gjcity.
    - file: 1739345334447.xls
      key: null
      action: retired
      why: >-
        동구청 공용차량 보유현황 128대(2024-12-31). 관용차량이고 소방차가
        아니다. 소방차 보유는 gjfire_fleet_dongbu 가 이미 갖고 있다.
        진입 판정과 무관하다.
    - file: 교통소통정보_도로구간정보_설명.pdf
      key: null
      action: retired
      why: API 설명서다. 데이터가 아니다.
"""


# ── ⑪ 승인분 4종 대장 등재 ─────────────────────────────────────
# ★ 반입 전에 적는다. 순서를 뒤집으면 "일단 넣고 나중에 적기" 가 되고,
#   그게 지금 retired 5종이 reason 만 남은 이유다.
DATASETS = """
  # ── 2026-09-10 juso 승인분 4종 ──────────────────────────────
  # ★ .prj 가 없다. 좌표 범위(X 946k~952k · Y 1675k~1686k)로 EPSG:5179
  #   (Korea 2000 / Unified CS)로 **추정**했다. 명시가 아니다.
  # ★ SIG_CD 는 12210(새 코드)인데 BD_MGT_SN 접두는 29110·29155·29170 이다
  #   — 새 동구가 옛 동구·서구·광산구 일부를 흡수했다. 스코프 대장에 그
  #   사실이 없다. jngj-donggu 로 필터한 종전 자료들이 새 경계와 다른
  #   범위를 담고 있을 수 있고, BD_MGT_SN 이 그 대조 키다.
  juso_bldg_geom:
    stem: juso_bldg_geom
    ext: [zip]
    kind: vector
    layer: raw
    scope: jngj-donggu
    updated: '2026-08-01'
    crs_native: EPSG:5179
    what: |
      도로명주소 건물 도형 전체분 — 건물 15,518 · 출입구 17,069 ·
      접속선 15,518 (TL_SGCO_RNADR_MST · TL_SPBD_ENTRC · TL_SPOT_CNTC)
    feeds: []
    feeds_why: |
      ★ 아직 배선하지 않았다. TL_SPOT_CNTC 의 접속선을 어떻게 쓸지는
        판정 규칙 변경이므로 B4(재잠금)에서 정한다. 지금은 반입만 한다.
    note: |
      ★ TL_SPOT_CNTC 가 이 자산의 핵심이다. CNT_DST_LN(접속거리) 중앙
        7.6m · 최대 402.5m · 0m 0건, CNT_DRC_LN 은 L 8,053 / R 7,462.
        출동 종점을 "도로 위 최근접점" 이 아니라 실제 출입구로 잡을 수 있다.

  juso_bldggrp_geom:
    stem: juso_bldggrp_geom
    ext: [zip]
    kind: vector
    layer: raw
    scope: jngj-donggu
    updated: '2026-08-01'
    crs_native: EPSG:5179
    what: 건물군 내 동 도형 8,221 · 동 출입구 939
    feeds: []
    feeds_why: 아직 배선하지 않았다. 아파트 단지 내부 진입 판정에 쓸 후보다.

  juso_spotaddr_geom_2608:
    stem: juso_spotaddr_geom
    ext: [zip]
    kind: vector
    layer: raw
    scope: jngj-donggu
    updated: '2026-08-01'
    crs_native: EPSG:5179
    what: 사물주소 도형 — 소화전 30 · 비상급수 12 · 버스정류장 190
    feeds: []
    feeds_why: |
      아직 배선하지 않았다. 소화전 30건은 기존 hydrant_point(동명동 11건)와
      대조가 필요하다 — 같은 것인지 다른 계열인지 확인 전에는 안 쓴다.
    note: |
      ★ LMTT_HG(제한높이) 컬럼이 전 레이어에 있는데 값이 **전부 0.0** 이다.
        컬럼이 있다고 값이 있는 것이 아니다. 높이 판정에 못 쓴다.
      ★ 186파일 중 다수가 0건 빈 껍데기다 — 드론배송 · 어린이CCTV ·
        물놀이 · 파크골프 · 푸드트럭 · 보호수 등.

  juso_etc_geom:
    stem: juso_etc_geom
    ext: [zip]
    kind: vector
    layer: raw
    scope: jngj-donggu
    updated: '2026-08-01'
    crs_native: EPSG:5179
    what: |
      기타자료 — 터널 10 · 고가 4 · 교량 36 · 공원 34 · 하천 27 ·
      지하철역 6 · 지하철출입구 26
    feeds: []
    feeds_why: |
      ★ 아직 배선하지 않았다. 그러나 이 자산은 **선언 하나를 반증한다** —
        sources.yaml 이 "동명동에 터널·고가 하부는 없다" 를 근거 없이
        단정했는데 동구에 터널 10(지산·산수·지원·소태) · 고가 4(너릿재로·
        제2순환로)가 실재한다. 동명동 안인지는 좌표로 확인해야 하고,
        어느 쪽이든 그 문장은 고쳐야 한다. B4 에서 다룬다.
"""


VERIFY = """
# ── 데이터 레이크 정합 (B2) ─────────────────────────────────────
# ★ 선언과 실물이 갈리는 것을 fsck 가 다 보지 못했다 — 제공기관 state ·
#   격리 잔재 · landing 우회 · ext 어휘 · norm 계보 다섯 축이 밖에 있었다.
#   lakecheck 가 그 축을 든다. FIRE_LANE_INBOX 를 기본 스캔 대상으로 쓴다.
step "레이크 선언↔실물" uv run python tools/lakecheck.py
"""


def do_ledger(apply: bool) -> int:
    print("── ⑥ retired 3종에 stem  ★ ledger_fields --apply 의 선행 조건")
    print("── ⑦ 미등재 격리 1건 등재")
    print("── ⑩ landing_disposition 16건")
    print("── ⑪ 승인분 4종 등재  ★ 반입 전에 적는다")
    L = Ledger()
    try:
        for old, new, why in RETIRED:
            L.sub(old, new, why=why)
        if "hydrant_point_kr_20240207_truncated" not in L.text:
            L.sub("  kfs_paint_marking_20241224:\n",
                  TRUNCATED + "  kfs_paint_marking_20241224:\n",
                  why="retired.hydrant_point_kr_truncated 등재 (11.3MB · 상한 증적)")
        else:
            L.skip.append("truncated 등재")
        if "2026-09-10 추가" not in L.text:
            L.sub("    - file: 2025년 소방자동차 다수공급자 계약(MAS) 제작규격 선택장비.hwp\n",
                  DISPOSITION + "    - file: 2025년 소방자동차 다수공급자 계약(MAS) 제작규격 선택장비.hwp\n",
                  why="landing_disposition 16건 (held 를 넷째 action 으로)")
        else:
            L.skip.append("landing_disposition")
        if "juso_bldg_geom:" not in L.text:
            # ★ `\nretired:` 를 앵커로 쓰면 그 바로 앞 블록(basemap)의 하위로
            #   들어간다. 키 집합 대조가 `basemap.juso_bldg_geom` 으로 잡아냈다
            #   — 텍스트 치환은 들여쓰기 문맥을 모른다. datasets 머리로 넣는다.
            m = re.search(r"^datasets:\n", L.text, re.M)
            if not m:
                raise RuntimeError("datasets 블록을 못 찾았다")
            L.text = L.text[:m.end()] + DATASETS.lstrip("\n") + L.text[m.end():]
            L.log.append("datasets 승인분 4종 등재")
        else:
            L.skip.append("승인분 4종")
        return 0 if L.commit(apply=apply) else 1
    except RuntimeError as e:
        print(f"  ✗ sources.yaml  {e}")
        return 1


def do_files(apply: bool) -> int:
    D = os.environ.get("FIRE_LANE_DATA")
    print("\n── ⑧ norm 고아 제거")
    if not D or not Path(D).is_dir():
        print("  ✗ FIRE_LANE_DATA 가 없다")
        return 1
    D = Path(D)
    orphan = D / "norm" / "eais" / "eais_bldg_ledger_jngj-donggu_20260817.csv"
    if orphan.exists():
        print(f"  {'→' if apply else '·'} 삭제 {orphan.relative_to(D)}"
              f"  ({orphan.stat().st_size / 1e6:.1f}MB)")
        print("      retired.building_ledger 의 파생이다. 상류가 raw 에 없다")
        if apply:
            orphan.unlink()
    else:
        print("  = 없음 (이미 제거)")

    print("\n── ⑨ landing 이관")
    # ★ 이 스크립트가 안 한다. tools/intake.py 가 그 일이다 —
    #   다운로드→landing 은 sha 기록과 정규명 제안이 붙어야 하고,
    #   원본 정리는 sweep 이 근거를 대고 지운다. 여기서 shutil.move
    #   를 직접 부르다 cross-device 로 **세 번** 죽었고, 그 바람에
    #   뒤에 있던 ⑫(verify.sh 배선)가 한 번도 실행되지 못했다.
    print("  = intake --stage / sweep --sweep 소관. 여기서 안 한다")
    return 0


def do_verify(apply: bool) -> int:
    print("\n── ⑫ verify.sh 배선")
    p = ROOT / "tools" / "verify.sh"
    if not p.exists():
        print("  ✗ tools/verify.sh 없음")
        return 1
    s = p.read_text(encoding="utf-8")
    if "레이크 선언↔실물" in s:
        print("  = 이미 있다")
        return 0
    import re as _re
    m = _re.search(r"^printf .*통과", s, _re.M)
    at = m.start() if m else len(s)
    out = s[:at] + VERIFY.strip("\n") + "\n\n" + s[at:]
    print(f"  {'→' if apply else '·'} lakecheck 스텝 추가")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.apply:
        bak = LEDGER.with_suffix(".yaml.b2close")
        if not bak.exists():
            shutil.copy2(LEDGER, bak)
            print(f"백업 {bak.name}\n")
    print(f"{'적용' if a.apply else 'dry-run — --apply 로 실행'}\n")
    fail = do_ledger(a.apply) + do_files(a.apply) + do_verify(a.apply)
    print(f"\n{'실패 ' + str(fail) + '건' if fail else '전부 통과'}")
    if a.apply and not fail:
        print("\n다음 —")
        print("  uv run python tools/lakecheck.py")
        print("  uv run python -m firelane.datalog fsck")
        print("  uv run python tools/acquire.py --stage --yes   # ⑤ 반입")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
