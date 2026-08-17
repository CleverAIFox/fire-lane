#!/usr/bin/env python3
"""
fix3_20260817.py — 남은 배선 3건.

    uv run python tools/fix3_20260817.py --check
    uv run python tools/fix3_20260817.py

1. sources.yaml  ngii_road 의 인라인 주석·설명이 값과 반대다.
   ledger_20260817.py 가 값만 고치고 주석을 안 고쳤다.
   대장이 정본인데 주석이 거짓말하면 다음 사람이 그걸 믿는다.

2. ingest.py     kind: shp_dir 분기가 없어 ValueError 로 매 실행 FAIL 했다.
   ngii1k 분기가 이미 하는 일과 같으므로 kind 이름만 받아준다.

3. publish_web.py  소화전 컬럼을 하드코딩해서, 소스가 바뀐 2026-08-15 이후
   KeyError 로 파이프라인 전체를 세웠다.
   ★ 결손은 폐기가 아니다(MASTER 18-3). 속성이 없거나 0건이어도
     빈 레이어로 발행하고 멈추지 않는다. 대신 조용히 넘어가지도 않는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATCHES: list[tuple[str, str, str]] = [
    # ── 1. 대장 주석 ────────────────────────────────────────
    ("sources.yaml",
     "    encoding: cp949                        # ★ cp949 아님. .cpg가 UTF-8",
     "    encoding: cp949                        # 2026-08-17 실물 확인. 구 선언 utf-8 은 틀렸다"),
    ("sources.yaml",
     "    what: 국가기본공간정보 수치지도 도로경계면 NF_A_A01000 (1:5,000) — 도로폭 주 소스",
     "    what: 연속수치지도 1:5,000 도로경계면 N3A_A0010000 — 폭 트랜섹트 소스(기하 전용)"),
    ("sources.yaml",
     "    desc: 국가기본공간정보 수치지도 도로경계면 NF_A_A01000 (1:5,000) — 도로폭 주 소스",
     "    desc: 연속수치지도 1:5,000 도로경계면 N3A_A0010000 — 폭 트랜섹트 소스(기하 전용)\n"
     "    # ★ 2026-08-17. 레이어명이 NF_A_A01000 → N3A_A0010000 으로 바뀌었고\n"
     "    #   rvwd(도로폭)가 이 면 레이어에서 사라져 도로중심선으로 옮겨갔다.\n"
     "    #   → datasets.ngii_road_center 참조. segments 는 폴리곤 기하로만 쓰므로\n"
     "    #     폭 산출에는 지장이 없다. 속성 교차검증 축만 그쪽으로 이동했다."),

    # ── 2. shp_dir 분기 ────────────────────────────────────
    ("src/etl/ingest.py",
     'elif kind in ("ngii1k", "ngii_1k"):',
     # shp_dir 은 2026-08-15 대장 개편에서 도입된 일반 이름이다.
     # 하는 일은 같다 — 도엽 묶음을 열어 레이어별로 합친다.
     'elif kind in ("ngii1k", "ngii_1k", "shp_dir"):'),

    # ── 3. 소화전 발행 ─────────────────────────────────────
    ("src/etl/publish_web.py",
     '    hcols = ["시설번호", "소재지도로명주소", "상세위치", "설치연도",\n'
     '             "보호틀유무", "관할기관명"] + (["z"] if "z" in hyd.columns else [])\n'
     '    hyd = hyd[hyd.within(scope4)][hcols + ["geometry"]]\n'
     '    hyd.to_file(W/"hydrants.geojson", **PREC)',
     '    # ★ 컬럼을 하드코딩하지 않는다. 2026-08-15 소스 교체 때 여기가\n'
     '    #   KeyError 로 파이프라인 전체를 세웠다. 있는 것만 싣는다.\n'
     '    #   결손은 폐기가 아니다 — 0건이어도 빈 레이어로 발행하고 지도는 뜬다.\n'
     '    #   다만 조용히 넘어가지도 않는다. 없으면 이름을 찍는다.\n'
     '    want = ["시설번호", "시설유형코드", "소재지도로명주소", "소재지지번주소",\n'
     '            "상세위치", "설치연도", "보호틀유무", "관할기관명", "안전센터명"]\n'
     '    have = [c for c in want if c in hyd.columns]\n'
     '    miss = [c for c in want if c not in hyd.columns]\n'
     '    if miss:\n'
     '        print(f"  ! 소화전 속성 없음 {miss} — 있는 것만 싣는다")\n'
     '    hcols = have + (["z"] if "z" in hyd.columns else [])\n'
     '    hyd = hyd[hyd.within(scope4)][hcols + ["geometry"]] if len(hyd) else hyd\n'
     '    print(f"  소화전 {len(hyd)}개 · 속성 {len(have)}종")\n'
     '    if len(hyd):\n'
     '        hyd.to_file(W/"hydrants.geojson", **PREC)\n'
     '    else:\n'
     '        # 빈 GeoDataFrame 은 드라이버가 거부한다. 빈 FeatureCollection 을 직접 쓴다.\n'
     '        (W/"hydrants.geojson").write_text(\n'
     '            \'{"type":"FeatureCollection","features":[]}\', encoding="utf-8")\n'
     '        print("    ★ 스코프 안 소화전 0개. 빈 레이어로 발행했다.")'),
]


def main() -> int:
    check = "--check" in sys.argv
    todo: dict[Path, str] = {}
    bad = 0
    for rel, old, new in PATCHES:
        p = ROOT / rel
        if not p.exists():
            print(f"! 없다: {rel}")
            bad += 1
            continue
        t = todo.get(p) or p.read_text(encoding="utf-8")
        if new.split("\n")[0] in t and old not in t:
            print(f"  {rel} 이미 적용됨 — 건너뜀")
            todo[p] = t
            continue
        n = t.count(old)
        if n != 1:
            print(f"! {rel} 앵커 {n}회 — {old.splitlines()[0][:60]}")
            bad += 1
            continue
        todo[p] = t.replace(old, new, 1)

    if bad:
        print(f"\n★ 앵커 {bad}건 실패. 아무것도 쓰지 않았다.")
        return 1
    if check:
        print("앵커 전건 일치. --check 이므로 쓰지 않았다.")
        return 0
    for p, t in todo.items():
        p.write_text(t, encoding="utf-8")
        print(f"  {p.relative_to(ROOT)}")
    print("\n다음:")
    print("  uv run python src/etl/contract.py")
    print("  uv run python src/etl/pipeline.py")
    print("  uv run python tools/baseline.py diff 20260814-ngii-ngi20")
    return 0


if __name__ == "__main__":
    sys.exit(main())
