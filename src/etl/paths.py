#!/usr/bin/env python3
"""
paths.py — 경로 정본. 모든 ETL 스크립트가 여기를 본다.

★ 심링크를 쓰지 않는다.
  `data/raw` 를 심링크로 걸었더니 git 이 그것을 추적했고,
  exFAT 에서 `git reset --hard` 시 경로 문자열 파일로 체크아웃되면서
  원본 2.5GB 가 소실됐다(2026-08-11). 환경변수는 git 에 아무것도 남기지 않는다.

── 계층 (MASTER §18-1) ───────────────────────────────────────
  landing     외장 SSD fire-lane-data/   다운로드 원본. 규칙 없음
  raw         절대 수정하지 않는다
  norm        파일명·인코딩·확장자만 통일. 값은 안 바꾼다
  field       실측 원자료. ★ 재생성 불가
  quarantine  대장에 없는 파일. 삭제하지 않고 격리
  processed   산출물. 재생성 가능하므로 백업·커밋하지 않는다

설정
    export FIRE_LANE_DATA="/mnt/ssd/.../fire-lane-data"
    (구방식 FIRE_LANE_RAW 도 계속 인식한다)

향후
    S3 로 옮기면 FIRE_LANE_DATA 에 s3:// 를 받도록 확장한다.
    스크립트들이 이 모듈만 보므로 그때 여기만 고치면 된다.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── 데이터 레이크 루트 ────────────────────────────────────────
DATA = os.environ.get("FIRE_LANE_DATA")
DATA = Path(DATA).expanduser() if DATA else None

# 원본. 절대 수정하지 않는다.
RAW = Path(os.environ.get("FIRE_LANE_RAW")
           or (DATA / "raw" if DATA else ROOT / "data" / "raw")).expanduser()

# 정규화본. 파일명·인코딩·확장자만 통일한다. 값은 안 바꾼다(MASTER §18-1).
NORM = (DATA / "norm") if DATA else (ROOT / "data" / "norm")

# 실측 원자료. ★ 재생성 불가. raw 와 같은 등급으로 보호한다.
FIELD = (DATA / "field") if DATA else (ROOT / "data" / "field")

# 대장에 없는 파일. 삭제하지 않고 격리한다(MASTER §18-12).
QUARANTINE = (DATA / "_quarantine") if DATA else (ROOT / "data" / "_quarantine")

# ── 산출물 ────────────────────────────────────────────────────
# ★ processed 는 백업하지도 커밋하지도 않는다.
#   raw + 코드 + 대장 이 있으면 결정론적으로 재생성된다(현재 80초).
#   산출물만 보관하는 것은 "함수 결과는 저장하고 함수는 안 저장하는 것"이다.
#   재현 증적은 _manifest.json 의 git_sha 가 담당한다.
# ★ SSD(drvfs)에 두지 않는다. 파일당 I/O 가 경계를 넘어 크게 느려진다.
PROCESSED = ROOT / "data" / "processed"

# 표출용. 저장소 안. UI 담당이 raw 없이 작업할 수 있어야 하므로 커밋한다.
WEB = ROOT / "web" / "data"

# 계산은 미터 좌표계, 표출은 경위도. 순서를 바꾸면 전부 어긋난다.
CRS_M = "EPSG:5186"
CRS_W = "EPSG:4326"


def check() -> None:
    """경로 상태를 사람이 읽을 수 있게 출력한다."""
    if DATA:
        src = "FIRE_LANE_DATA"
    elif os.environ.get("FIRE_LANE_RAW"):
        src = "FIRE_LANE_RAW (구방식)"
    else:
        src = "기본값(repo/data)"
    print(f"DATA      {DATA or '—'}   [{src}]")
    print(f"RAW       {RAW}")
    if not RAW.is_dir():
        print("          ★ 없다. FIRE_LANE_DATA 를 설정하거나 원본을 배치할 것")
    else:
        n = sum(1 for _ in RAW.rglob("*") if _.is_file())
        sz = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e9
        print(f"          {n}개 파일 · {sz:.2f} GB")
    for nm, p in (("NORM", NORM), ("FIELD", FIELD), ("QUARANTINE", QUARANTINE)):
        print(f"{nm:9} {p}{'' if p.is_dir() else '   (없음)'}")
    print(f"PROCESSED {PROCESSED}   [재생성 가능. 백업·커밋 안 함]")
    print(f"WEB       {WEB}")


if __name__ == "__main__":
    check()
