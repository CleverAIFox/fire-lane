#!/usr/bin/env python3
"""
tools/occ_pressure.py — 점유압력 β 의 **수요점**을 만든다 (건축물대장 → 좌표)

    uv run python tools/occ_pressure.py            수요점을 만들어 data/processed/occ_demand.csv 에 쓴다 + 수를 찍는다
    uv run python tools/occ_pressure.py --report   만들지 않고 구간 β 의 밴드별 분포만 찍는다
    uv run python tools/occ_pressure.py --selftest ★ 판별식이 살아 있나

── 무엇을 하나 ──────────────────────────────────────────────────
CCTV 없는 구간 447개가 순서 없이 평평하게 쌓여 있다 — 어디부터 현장을 나갈지 모른다. **판정은 안 만들고 순서만 만든다.**
β 의 정의와 관문은 `firelane.occ` 가 든다(길이 기준 · `cap_style=2` · 밴드 안 순위 · null 과 0).

  레이크  `$FIRE_LANE_DATA/norm/eais/eais_bldgledger_dm_jngj-dongmyeong_20260906.json`  — 최상위가 dict 다.
          `{Description: 77칸의 한글 뜻, Data: 1,989행}`. **칸 이름은 영문 코드다.**
  units   = max(HH_CNT, FML_CNT, HO_CNT)   ← `HH_CNT` 는 41건뿐이라 단독으로 못 쓴다(FML 901 · HO 19)
  버림    units == 0 인 동(1,038)
  남김    부설주차 4칸 `INDR_MCNCL_AREA` · `OTDR_MCNCL_AREA` · `INDR_SFPRPL_AREA` · `OTDR_SFPRPL_AREA` 의 합이 0 인 동만
          → **818동 · 1,794단위** (좌표 붙이기 전)
  좌표    대장 (MNO, SNO) → `navi_jibun` (c06, c07) → c18 → `navi_build` c10 → (c23, c24) EPSG:5179
          세 값 모두 `int(float(x))` 로 정규화한다 — 문자열 비교는 '0' 대 '00' 에서 깨진다.
          → **774동 · 1,744단위** 가 β 에 들어간다. **좌표 없는 44동은 β 에 안 들어간다.**
  ★ **한 지번에 건물관리번호가 여럿이면 첫 매칭 하나만 썼다. 이것은 근사다**(여럿인 지번 — 대장 전체 43 · 필터 후 13). 정확한 줄 알면 안 된다.
  ★ `navi_jibun` · `navi_build` 는 **헤더 없는 juso 원본**이라 칸 이름이 `c00..c32` 다(sources.yaml 에 칸 뜻을 적었다).

IN    `$FIRE_LANE_DATA/norm/eais/eais_bldgledger_dm_*.json` · data/processed/{navi_jibun,navi_build}.csv
OUT   data/processed/occ_demand.csv (x · y · units · bldg_key — processed 산출물이라 커밋 안 한다)
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
밖    **상업 유입은 안 본다** — 수요에 거주 세대만 잡힌다(단속 141,556건이 그 유입의 증거다). 거주 세대가 있는 곳이
      **차가 서는 곳**이라는 것도 가정이다. 동명동 밖은 대장이 없어 못 잰다. 판정을 안 움직인다.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
from pathlib import Path

from firelane.paths import NORM, PROCESSED

LEDGER_GLOB = "eais/eais_bldgledger_dm_jngj-dongmyeong_*.json"
PARK_COLS = ("INDR_MCNCL_AREA", "OTDR_MCNCL_AREA", "INDR_SFPRPL_AREA", "OTDR_SFPRPL_AREA")


def _int(x) -> int:
    """`int(float(x))` — '0' 대 '00' 에서 깨지지 않게. 못 읽으면 0."""
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def units_of(r: dict) -> int:
    """거주단위. `HH_CNT` 는 41건뿐이라 단독으로 못 쓴다 — 셋 중 max."""
    return max(_int(r.get("HH_CNT")), _int(r.get("FML_CNT")), _int(r.get("HO_CNT")))


def keep_row(r: dict) -> bool:
    """units > 0 이고 부설주차 4칸 합이 0 인 동."""
    if units_of(r) <= 0:
        return False
    return sum(float(r.get(p) or 0) for p in PARK_COLS) == 0


def build_demand(rows: list[dict], jibun: dict, build: dict) -> tuple[list[tuple], dict]:
    """(x, y, units, key) 목록과 수. `jibun`: (본번, 부번) → [건물관리번호…] · `build`: 건물관리번호 → (x, y)."""
    kept = [r for r in rows if keep_row(r)]
    out, multi = [], 0
    for r in kept:
        ks = jibun.get((_int(r.get("MNO")), _int(r.get("SNO")))) or []
        if len(ks) > 1:
            multi += 1
        key = next((k for k in ks if k in build), None)     # ★ 첫 매칭 하나 — 근사다
        if key is not None:
            out.append((*build[key], units_of(r), key))
    stat = {"rows": len(rows), "kept": len(kept), "kept_units": sum(units_of(r) for r in kept),
            "reach": len(out), "reach_units": sum(o[2] for o in out), "multi_key": multi}
    return out, stat


def load_juso() -> tuple[dict, dict]:
    jibun: dict = {}
    build: dict = {}
    with (PROCESSED / "navi_jibun.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.reader(f):
            if r and r[0] != "c00":
                jibun.setdefault((_int(r[6]), _int(r[7])), []).append(r[18])
    with (PROCESSED / "navi_build.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.reader(f):
            if r and r[0] != "c00":
                build[r[10]] = (float(r[23]), float(r[24]))
    return jibun, build


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--report", action="store_true", help="만들지 않고 구간 β 분포만 찍는다")
    ap.add_argument("--selftest", action="store_true", help="판별식이 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.report:
        return report()
    src = sorted((NORM).glob(LEDGER_GLOB))
    if not src:
        print(f"✗ 레이크에 {LEDGER_GLOB} 가 없다 — FIRE_LANE_DATA 를 확인해라", file=sys.stderr)
        return 2
    # ★ 레이크(9p/drvfs)에서 곧장 읽지 않는다 — 로컬로 복사해 읽고 지운다(3.2MB 라 싸다).
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / src[-1].name
        shutil.copyfile(src[-1], tmp)
        led = json.loads(tmp.read_text(encoding="utf-8"))
    rows = led["Data"]
    jibun, build = load_juso()
    demand, st = build_demand(rows, jibun, build)
    dst = PROCESSED / "occ_demand.csv"
    with dst.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x", "y", "units", "bldg_key"])
        w.writerows(demand)
    print(f"대장 {st['rows']:,}동 → 필터(units>0 · 부설주차 0) {st['kept']}동 · {st['kept_units']:,}단위 (좌표 붙이기 전)")
    print(f"좌표에 닿는 것 {st['reach']}동 · {st['reach_units']:,}단위  ← β 는 이쪽을 쓴다")
    print(f"좌표 없는 {st['kept'] - st['reach']}동은 β 에 안 들어간다 · 한 지번에 건물관리번호 여럿 {st['multi_key']} (첫 매칭 하나 — 근사)")
    print(f"→ {dst}")
    return 0


def report() -> int:
    import geopandas as gpd

    from firelane.occ import load_demand, occ_columns
    seg = gpd.read_file(PROCESSED / "segments.geojson")
    occ, rank = occ_columns(seg, load_demand(PROCESSED / "occ_demand.csv"))
    emd = seg["in_emd"].astype(bool)
    print(f"구간 {len(seg)} · 동명동 안 {int(emd.sum())} · β 가 null 인 동명동 밖 {int((~emd).sum())} (0 이 아니다)")
    print(f"동명동 안 β>0 {sum(1 for v in occ[emd] if v and v > 0)} · rank 가 있는 {int(rank.notna().sum())}")
    return 0


def selftest() -> int:
    bad: list[str] = []
    rows = [
        {"HH_CNT": "0", "FML_CNT": "3", "HO_CNT": "0", "MNO": "0018", "SNO": "0012"},          # 남김 · 지번 (18,12)
        {"HH_CNT": "2", "FML_CNT": "0", "HO_CNT": "5", "MNO": "7", "SNO": "0", "INDR_MCNCL_AREA": "10"},   # 주차 있음 → 버림
        {"HH_CNT": "0", "FML_CNT": "0", "HO_CNT": "0", "MNO": "1", "SNO": "1"},               # units 0 → 버림
        {"HH_CNT": "1", "FML_CNT": "0", "HO_CNT": "0", "MNO": "99", "SNO": "0"},              # 좌표 없음
    ]
    jibun = {(18, 12): ["K-bad", "K-ok"]}               # 첫 키가 build 에 없으면 다음 키 — '0018' 과 18 이 같다
    build = {"K-ok": (1.0, 2.0)}
    out, st = build_demand(rows, jibun, build)
    if units_of(rows[0]) != 3:
        bad.append("units 는 셋 중 max 여야 한다")
    if [o[:3] for o in out] != [(1.0, 2.0, 3)]:
        bad.append(f"좌표 붙이기가 틀렸다 — {out}")
    if (st["kept"], st["reach"], st["multi_key"]) != (2, 1, 1):
        bad.append(f"수가 틀렸다 — {st}")
    for b in bad:
        print("  ✗", b)
    print("✓ 살아 있다" if not bad else f"✗ {len(bad)}건")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
