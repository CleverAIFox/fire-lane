#!/usr/bin/env python3
"""
pipeline.py — 파이프라인 단일 진입점.

    python src/etl/pipeline.py              # 전체
    python src/etl/pipeline.py --from segments   # 그 단계부터 끝까지
    python src/etl/pipeline.py --only terrain ortho
    python src/etl/pipeline.py --check      # 실행 없이 상태만

★ 단계를 하나씩 손으로 치면 반드시 빠뜨린다.
  terrain 을 건너뛰면 지형이 안 뜨고, publish_web 을 건너뛰면 지도가 옛 데이터를 본다.
  순서도 중요하다. publish_web 은 terrain/ortho 가 기록한 타일 범위를 읽어 보존한다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED, RAW, WEB  # noqa: E402

for st in (sys.stdout, sys.stderr):
    try:
        st.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# (이름, 스크립트, 설명, 산출물 확인 경로)
STEPS = [
    ("ingest",   "ingest.py",      "raw → processed (19종)",      PROCESSED / "_manifest.json"),
    ("segments", "segments.py",    "노딩 → 폭 → 판정",             PROCESSED / "segments.geojson"),
    ("terrain",  "terrain.py",     "공개DEM → Terrain-RGB 타일",   WEB / "terrain"),
    ("ortho",    "ortho.py",       "항공정사영상 → 배경 타일",      WEB / "ortho"),
    ("publish",  "publish_web.py", "→ web/data",                   WEB / "segments.geojson"),
]

# 이 값과 다르면 뭔가 잘못된 것이다. 바뀌면 여기도 같이 고칠 것.
EXPECT = {
    # ingest 산출 기준선. 도엽이 빠지거나 소스가 바뀌면 여기서 먼저 걸린다.
    "ingest": {"ngii1k": 3593, "ngii_road": 3740, "road_link": 1508,
               "road_rw": 1957, "node_link": 1366, "streetlight": 1786},
    "segments": 1102,
    # 2026-08-13 갱신. 노드접합 + 산출단위 병합 + 소스별 snap + 구간단위 소스채택.
    # 폭 미산출 127 → 0. unknown 은 전부 no_cctv 다(영상판정 불가).
    # 길이 0.0m 유령 피처 40개가 clear 로 표출되고 있었다.
    "verdict": {"clear": 386, "needs_cv": 210, "blocked": 62, "unknown": 444},
    "unknown_reason": {"no_cctv": 396, "width": 0},
}


def c(t, k):
    return f"\033[{k}m{t}\033[0m" if sys.stdout.isatty() else t


def check_only():
    print(f"RAW        {RAW}")
    if RAW.is_dir():
        n = sum(1 for _ in RAW.rglob("*") if _.is_file())
        sz = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e9
        print(f"           {n}개 파일 · {sz:.2f} GB")
    else:
        print(c("           없다. FIRE_LANE_RAW 설정 또는 normalize_raw.py 실행", "33"))
    print()
    for name, script, desc, out in STEPS:
        ok = out.exists()
        mark = c("OK  ", "32") if ok else c("없음", "33")
        extra = ""
        if ok and out.is_dir():
            extra = f"  ({sum(1 for _ in out.rglob('*') if _.is_file())}개)"
        print(f"  {mark} {name:9s} {desc:28s} {out.relative_to(ROOT)}{extra}")


def verify():
    """산출물이 기대값과 맞는지 본다."""
    import json
    p = WEB / "segments.schema.json"
    if not p.exists():
        return
    s = json.loads(p.read_text(encoding="utf-8"))
    n = s.get("count")
    ok = n == EXPECT["segments"]
    want = EXPECT["segments"]
    mark = c("OK", "32") if ok else c(f"★ 기대 {want}", "33")
    print(f"\n  세그먼트 {n}  {mark}")
    import collections
    g = json.loads((WEB / "segments.geojson").read_text(encoding="utf-8"))
    v = collections.Counter(f["properties"]["verdict"] for f in g["features"])
    for k, want in EXPECT["verdict"].items():
        got = v.get(k, 0)
        mark = c("OK", "32") if got == want else c(f"★ 기대 {want}", "33")
        print(f"    {k:10s} {got:4d}  {mark}")
    for d, label in ((WEB / "terrain", "지형 타일"), (WEB / "ortho", "항공영상")):
        if d.is_dir():
            print(f"  {label} {sum(1 for _ in d.rglob('*') if _.is_file())}장")
    if WEB.is_dir():
        mb = sum(f.stat().st_size for f in WEB.rglob("*") if f.is_file()) / 1e6
        warn = "" if mb < 60 else c("  ★ CI 상한 60MB 초과", "31")
        print(f"  web/data {mb:.0f} MB{warn}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", choices=[s[0] for s in STEPS],
                    help="이 단계부터 끝까지")
    ap.add_argument("--only", nargs="+", choices=[s[0] for s in STEPS],
                    help="이 단계만")
    ap.add_argument("--check", action="store_true", help="실행 없이 상태만")
    ap.add_argument("--no-test", action="store_true", help="계약 테스트 생략")
    a = ap.parse_args()

    if a.check:
        check_only()
        return

    steps = STEPS
    if a.only:
        steps = [s for s in STEPS if s[0] in a.only]
    elif a.frm:
        i = [s[0] for s in STEPS].index(a.frm)
        steps = STEPS[i:]

    if not RAW.is_dir() or not any(RAW.rglob("*.zip")):
        print(c(f"★ raw 가 비어 있다: {RAW}", "31"))
        print("  export FIRE_LANE_RAW=... 또는")
        print("  python src/etl/normalize_raw.py <다운로드폴더>")
        if "ingest" in [s[0] for s in steps]:
            sys.exit(1)

    print(f"실행 {len(steps)}단계: {' → '.join(s[0] for s in steps)}\n")
    t0 = time.time()
    for name, script, desc, _ in steps:
        print(c(f"── {name}  {desc}", "36"))
        t = time.time()
        r = subprocess.run([sys.executable, str(HERE / script)], cwd=ROOT)
        if r.returncode:
            print(c(f"\n★ {name} 실패. 여기서 멈춘다.", "31"))
            print(f"  고친 뒤: python src/etl/pipeline.py --from {name}")
            sys.exit(1)
        print(c(f"   {time.time()-t:.1f}s", "90"))

    if not a.no_test:
        print(c("── 계약 테스트", "36"))
        r = subprocess.run([sys.executable, "-m", "pytest",
                            "tests/test_contract.py", "-q"], cwd=ROOT)
        if r.returncode:
            print(c("\n★ 계약 테스트 실패. 머지하지 말 것.", "31"))
            sys.exit(1)

    verify()
    print(f"\n총 {time.time()-t0:.1f}s")
    print("\n지도 확인:  cd web && python -m http.server 8000")


if __name__ == "__main__":
    main()
