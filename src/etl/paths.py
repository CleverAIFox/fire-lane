#!/usr/bin/env python3
"""
paths.py — 경로 정본. 모든 ETL 스크립트가 여기를 본다.

★ 심링크를 쓰지 않는다.
  `data/raw` 를 심링크로 걸었더니 git 이 그것을 추적했고,
  exFAT 에서 `git reset --hard` 시 경로 문자열 파일로 체크아웃되면서
  원본 2.5GB 가 소실됐다(2026-08-11). 환경변수는 git 에 아무것도 남기지 않는다.

★ raw 가 커질수록 이 분리가 중요하다.
  지금 1.6GB, 정사영상 4도엽 포함. 스코프를 넓히면 더 는다.
  저장소에는 절대 넣지 않고, 위치만 각자 환경에서 지정한다.

설정
    리눅스/맥   export FIRE_LANE_RAW="/mnt/f/.../FIRE_LANE/data/raw"
    윈도우      setx FIRE_LANE_RAW "D:\\...\\FIRE_LANE\\data\\raw"
    미설정 시   <repo>/data/raw 를 쓴다 (단일 머신 작업이면 이걸로 충분)

향후
    AWS S3 로 옮기면 FIRE_LANE_RAW 에 s3:// 를 받도록 확장한다.
    스크립트들이 이 모듈만 보므로 그때 여기만 고치면 된다.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 원본. 저장소 밖에 둘 수 있다.
RAW = Path(os.environ.get("FIRE_LANE_RAW") or (ROOT / "data" / "raw")).expanduser()

# 중간 산출물. 저장소 안. *.gpkg / *.tif 는 .gitignore 로 제외된다.
PROCESSED = ROOT / "data" / "processed"

# 표출용. 저장소 안. UI 담당이 raw 없이 작업할 수 있어야 하므로 커밋한다.
WEB = ROOT / "web" / "data"

# 계산은 미터 좌표계, 표출은 경위도. 순서를 바꾸면 전부 어긋난다.
CRS_M = "EPSG:5186"
CRS_W = "EPSG:4326"


def check() -> None:
    """경로 상태를 사람이 읽을 수 있게 출력한다."""
    src = "FIRE_LANE_RAW" if os.environ.get("FIRE_LANE_RAW") else "기본값(repo/data/raw)"
    print(f"RAW       {RAW}   [{src}]")
    if not RAW.is_dir():
        print("          ★ 없다. 환경변수를 설정하거나 원본을 배치할 것")
    else:
        n = sum(1 for _ in RAW.rglob("*") if _.is_file())
        sz = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e9
        print(f"          {n}개 파일 · {sz:.2f} GB")
    print(f"PROCESSED {PROCESSED}")
    print(f"WEB       {WEB}")


if __name__ == "__main__":
    check()
