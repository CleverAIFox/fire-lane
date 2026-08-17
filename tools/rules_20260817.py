#!/usr/bin/env python3
"""
rules_20260817.py — 새 소스 3종의 배치 규칙과 필수 목록을 등록한다.

    uv run python tools/rules_20260817.py --check
    uv run python tools/rules_20260817.py

배경
    2026-08-15 원본 재취득 때 소방 계열 3종이 잘못 잡혔다.

      fire_station     좌표현황(안전센터 포함) → 시도 소방서 현황(좌표 없음)
                       csv_points 인데 X/Y 컬럼이 없어 매 실행 FAIL
      hydrant_point    전국 표준데이터 → 전남 소방용수시설
                       시_군 22개가 전부 전남. 광주 0건이라 OK 0건으로 통과
      hydrant_summary  미확보. 588 중 31 논거의 근거 데이터였다

    셋 다 대체 소스를 확보했다. 규칙에 등록해 landing → raw 가 자동으로 돌게 한다.

★ 이 저장소는 2026-08-15 개편으로 normalize_raw.py 가 크게 바뀌었다.
  파일을 덮어쓰지 않고 앵커를 확인한 뒤 삽입·치환만 한다.
  앵커가 없으면 아무것도 쓰지 않는다. 재실행해도 안전하다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src/etl/normalize_raw.py"

ANCHOR = "RULES: list[tuple[str, str, str]] = [\n"
MARK = "# ── 2026-08-17 소방 계열 3종 재확보"

INSERT = ANCHOR + '''    # ── 2026-08-17 소방 계열 3종 재확보 ──────────────────────
    #   ★ 아래 세 줄이 위쪽 기존 규칙보다 먼저 매칭돼야 한다.
    #     "소방용수시설.?현황" 이 전남 판 좌표 파일을 summary 로 오분류했었다.
    #
    # 소화전 좌표. 전국 표준데이터 50,000행 절단본이나 광주는 전량 포함
    # (광주 197 · 동구 31 · 데이터기준일자 2024-02-07).
    # 전남 판(jngj_20250917)에는 광주가 0건이라 이것 말고 대안이 없다.
    (r"전국소방용수시설표준데이터\\.(csv|json)$",
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
'''

# 필수 목록 — 실제로 파이프라인이 쓰는 파일로 교체한다.
SWAPS = [
    ('"safety/safety_firestation_kr_20250701.csv"',
     '"safety/safety_firestation_kr_20240901.csv"'),
    ('"safety/safety_hydrant_point_jngj_20250917.csv"',
     '"safety/safety_hydrant_point_kr_20240207.csv",\n'
     '    "safety/safety_hydrant_summary_gj_dong_20250731.csv"'),
]


def main() -> int:
    check = "--check" in sys.argv
    if not TARGET.exists():
        print(f"! 없다: {TARGET}")
        return 1
    t = TARGET.read_text(encoding="utf-8")

    if MARK in t:
        print("  이미 등록됨 — 건너뜀")
        return 0

    bad = 0
    if t.count(ANCHOR) != 1:
        print(f"! RULES 앵커 {t.count(ANCHOR)}회")
        bad += 1
    for old, _ in SWAPS:
        if t.count(old) != 1:
            print(f"! 필수목록 앵커 {t.count(old)}회 — {old}")
            bad += 1
    if bad:
        print(f"\n★ 앵커 {bad}건 실패. 아무것도 쓰지 않았다.")
        print("  normalize_raw.py 의 RULES / 필수목록을 직접 보고 손으로 넣어라.")
        return 1

    if check:
        print("앵커 전건 일치. --check 이므로 쓰지 않았다.")
        return 0

    t = t.replace(ANCHOR, INSERT, 1)
    for old, new in SWAPS:
        t = t.replace(old, new, 1)
    TARGET.write_text(t, encoding="utf-8")
    print("  normalize_raw.py 규칙 3건 + 필수목록 3건 반영")
    print("\n다음: uv run python src/etl/normalize_raw.py \"$FIRE_LANE_DATA/landing\" --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
