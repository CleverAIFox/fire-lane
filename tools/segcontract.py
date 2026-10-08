#!/usr/bin/env python3
"""
segcontract.py — **발행된 판정이 제 계약을 지키는가.** (PLAN #104)

    uv run python tools/segcontract.py            센다
    uv run python tools/segcontract.py --rows     위반 전수
    uv run python tools/segcontract.py --selftest

── 무엇을 재나 (셋) ────────────────────────────────────────────
`PLAN #104` 가 적은 셋이다 — 폭 상한 · 도로명 규칙 위반 · 조용한 결측.

```
WIDTH_OUT_OF_RANGE   폭이 상한 밖이거나 min > max 로 뒤집혔다
ROADNAME_OFF_RULE    도로명이 도로명주소 꼴 밖이다
SILENT_MISSING       값이 없는데 **왜 없는지를 산출물이 안 말한다**
```

★ 셋째가 제일 중요하다. 앞 둘은 **값이 틀렸다**를 말하고, 셋째는 **왜인지를
  읽는 사람이 알 수 없다**를 말한다. 2026-10-08 실측 2건이고 둘 다 같은 꼴이다 —
  `blocked` 인데 `width_min_m` 이 비었고 사유 칸이 없다. 파이프라인은 사유를
  **안다**(`all_xsec` — 트랜섹트가 전부 교차부에 걸렸다) 그런데 그 진단이
  표준출력에만 찍히고 **산출물에 안 들어간다.** 화면과 보고서는 그 둘을
  「폭 미상 통행불가」로만 보고, 왜인지 물을 자리가 없다.

★ 상한 셋 다 **문턱이 아니라 지금 수다.** 앞 둘은 0 이고 그 0 을 지킨다 —
  빈 그물이 되지 않게 `--selftest` 가 **합성 위반**으로 셋을 다 민다.

★ 레이크를 **안 읽는다.** `data/processed/segments.geojson` 은 커밋돼 있어
  (`.gitignore` 예외) 이 관문이 CI 에서 선다. `widthcross` · `clearance_cross`
  가 같은 축의 더 깊은 물음을 들지만 그쪽은 `processed/*.gpkg` 를 읽어
  CI 에서 건너뛴다 — `greycheck` 와 같은 경계다.

RATCHETS  WIDTH_OUT_OF_RANGE · ROADNAME_OFF_RULE · SILENT_MISSING — 전부 내려가는 쪽

IN    data/processed/segments.geojson · firelane.seg.params(WMAX_CAP · TRUCK)
OUT   표준출력
밖    **판정을 안 바꾼다.** 값을 고치거나 칸을 더하는 것은 산출물을 움직이고
      `golden` 재잠금이 따라온다 — 측정 배치의 일이다(PLAN §13-5 규칙 2).
      **어느 판정이 옳은가도 안 본다** — 그 물음은 `widthcross` 가 든다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "data" / "processed" / "segments.geojson"

#: 폭이 상한 밖이거나 뒤집힌 구간. **0 이고 그 0 을 지킨다.**
WIDTH_OUT_OF_RANGE = 0
#: 도로명이 꼴 밖인 **고유 이름** 수. 구간이 아니라 이름을 센다 — 한 이름이
#: 틀리면 그 이름의 구간 전부가 같은 결함이고, 고칠 것은 이름 하나다.
ROADNAME_OFF_RULE = 0
#: 값이 없는데 사유를 산출물이 안 말하는 구간. **2026-10-08 첫 실측 2.**
SILENT_MISSING = 2

RATCHETS = {"WIDTH_OUT_OF_RANGE": "down", "ROADNAME_OFF_RULE": "down",
            "SILENT_MISSING": "down"}

#: 도로명주소 꼴. `로` · `길` · `가` 로 끝나고, `번길` 은 숫자를 앞세운다.
#: ★ 이 정규식은 **발행된 107개 고유 이름에서 유도했다**(2026-10-08 실측 · 꼴 밖 0).
#:   규칙의 정본은 도로명주소법 시행령이고 여기는 그 꼴을 **좁게** 받는다 —
#:   넓히면 아무것도 안 걸리고, 좁히면 멀쩡한 이름이 빨개진다.
ROADNAME = re.compile(r"^[가-힣A-Za-z0-9]+(?:로|길|가)(?:\d+번?길)?$")

#: 값이 비면 사유를 적어야 하는 칸 → 사유를 담는 칸.
#: ★ `unknown_reason` 은 `unknown` 전용이다 — `blocked` 는 담을 칸이 없고
#:   그래서 실측 2건이 거기 떨어진다. 칸을 더하는 것은 산출물을 움직인다.
NEEDS_REASON = {"width_min_m": ("unknown_reason",)}


def rows() -> list[dict]:
    if not SEG.is_file():
        raise RuntimeError(f"{SEG.relative_to(ROOT)} 가 없다 — 커밋돼 있어야 한다")
    return [f["properties"]
            for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]


def width_out_of_range(P: list[dict], cap: float) -> list[str]:
    """폭이 상한 밖이거나 `min > max` 로 뒤집힌 구간."""
    out = []
    for p in P:
        lo, hi = p.get("width_min_m"), p.get("width_max_m")
        sid = p.get("seg_id")
        for name, v in (("width_min_m", lo), ("width_max_m", hi)):
            if v is not None and (v <= 0 or v > cap):
                out.append(f"{sid}: {name} {v} — 상한 {cap} 밖이다")
        if lo is not None and hi is not None and lo > hi:
            out.append(f"{sid}: min {lo} > max {hi} — 뒤집혔다")
    return out


def roadname_off_rule(P: list[dict]) -> list[str]:
    """꼴 밖인 **고유** 도로명. 결측도 든다 — 이름 없는 구간은 찾을 수가 없다."""
    names: dict[str, int] = {}
    blank = 0
    for p in P:
        n = p.get("road_name")
        if n is None or not str(n).strip():
            blank += 1
        elif not ROADNAME.match(str(n)):
            names[str(n)] = names.get(str(n), 0) + 1
    out = [f"{n} — 구간 {c}" for n, c in sorted(names.items())]
    if blank:
        out.append(f"(이름 없음) — 구간 {blank}")
    return out


def silent_missing(P: list[dict]) -> list[str]:
    """값이 없는데 **왜 없는지를 산출물이 안 말하는** 구간."""
    out = []
    for p in P:
        for col, reasons in NEEDS_REASON.items():
            if p.get(col) is not None:
                continue
            if any(str(p.get(r) or "").strip() for r in reasons):
                continue
            out.append(f"{p.get('seg_id')}: {col} 가 비었고 사유 칸"
                       f"({' · '.join(reasons)})도 비었다 · verdict={p.get('verdict')}")
    return out


def findings() -> dict:
    from firelane.seg.params import WMAX_CAP
    P = rows()
    return {"segments": len(P), "cap": WMAX_CAP,
            "width": width_out_of_range(P, WMAX_CAP),
            "name": roadname_off_rule(P),
            "silent": silent_missing(P)}


def ratchet_values() -> dict[str, int]:
    f = findings()
    return {"WIDTH_OUT_OF_RANGE": len(f["width"]),
            "ROADNAME_OFF_RULE": len(f["name"]),
            "SILENT_MISSING": len(f["silent"])}


def selftest() -> int:
    """★ 셋이 **합성 위반**에서 운다. 실물이 전부 0 이 되는 날에도 산다."""
    bad = []
    cap = 60.0
    # ① 폭 — 상한 밖 · 0 이하 · 뒤집힘. 멀쩡한 것은 안 걸려야 한다
    w = width_out_of_range([
        {"seg_id": "A", "width_min_m": 3.0, "width_max_m": 7.0},     # 정상
        {"seg_id": "B", "width_min_m": 3.0, "width_max_m": 61.0},    # 상한 밖
        {"seg_id": "C", "width_min_m": 0.0, "width_max_m": 5.0},     # 0 이하
        {"seg_id": "D", "width_min_m": 9.0, "width_max_m": 4.0},     # 뒤집힘
        {"seg_id": "E", "width_min_m": None, "width_max_m": None},   # 결측은 여기가 아니다
    ], cap)
    if sorted(x.split(":")[0] for x in w) != ["B", "C", "D"]:
        bad.append(f"폭 판별식이 죽었다: {w}")
    # ② 도로명 — 꼴 밖 · 결측. 같은 이름 둘은 **하나로** 센다
    n = roadname_off_rule([
        {"road_name": "필문대로"}, {"road_name": "필문대로205번길"},
        {"road_name": "지호로86번길"}, {"road_name": "2순환로"},
        {"road_name": "엉뚱한것"}, {"road_name": "엉뚱한것"},
        {"road_name": None}, {"road_name": "   "},
    ])
    if len(n) != 2 or not any("엉뚱한것 — 구간 2" in x for x in n) \
            or not any("(이름 없음) — 구간 2" in x for x in n):
        bad.append(f"도로명 판별식이 죽었다: {n}")
    # ③ 조용한 결측 — 사유가 있으면 조용한 것이 아니다
    s = silent_missing([
        {"seg_id": "A", "width_min_m": 3.0},                               # 값이 있다
        {"seg_id": "B", "width_min_m": None, "unknown_reason": "no_cctv"},  # 사유가 있다
        {"seg_id": "C", "width_min_m": None, "unknown_reason": "  "},       # 공백은 사유가 아니다
        {"seg_id": "D", "width_min_m": None},                               # 조용하다
    ])
    if sorted(x.split(":")[0] for x in s) != ["C", "D"]:
        bad.append(f"조용한 결측 판별식이 죽었다: {s}")
    # ★ 빈 그물 — 실물을 못 읽으면 셋이 다 0 이고 이 관문이 언제나 초록이다
    try:
        f = findings()
    except RuntimeError as e:
        bad.append(str(e))
    else:
        if f["segments"] < 1000:
            bad.append(f"구간을 {f['segments']}개밖에 못 읽었다 — 수집기를 의심하라")
        if not ROADNAME.match("필문대로205번길"):
            bad.append("실물 이름 꼴을 정규식이 거부한다")
    for x in bad:
        print(f"  ✗ {x}")
    # 합성 구간 5 + 8 + 4 = 17 · 그중 위반 3 + 2 + 2 = 7 · 실물 판별식 둘
    print(f"{'✗' if bad else '✓'} 자기검사 — 합성 구간 17 에서 위반 7 을 **정확히** "
          "집어낸다(폭 셋 · 도로명 둘 · 조용한 결측 둘) · 실물 판별식 둘")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", action="store_true", help="위반 전수")
    ap.add_argument("--ratchet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    f = findings()
    if a.ratchet:
        print(" · ".join(f"{k} {v}" for k, v in ratchet_values().items()))
        return 0

    print(f"── 발행된 판정의 계약  구간 {f['segments']:,} · 폭 상한 {f['cap']}")
    rc = 0
    for label, key, cap in (("폭이 상한 밖이거나 뒤집힘", "width", WIDTH_OUT_OF_RANGE),
                            ("도로명이 꼴 밖(고유 이름)", "name", ROADNAME_OFF_RULE),
                            ("조용한 결측", "silent", SILENT_MISSING)):
        got = len(f[key])
        sign = "=" if got == cap else ("↑" if got > cap else "↓")
        print(f"  {label:<26} 실측 {got:>3} {sign} 래칫 {cap:>3}")
        if a.rows or got != cap:
            for x in f[key][:30]:
                print(f"       {x}")
        if got > cap:
            print("    ✗ **늘었다.** 이 배치가 발행물의 계약을 깼다")
            rc = 1
        elif got < cap:
            print("    ✗ 줄었다. **래칫을 그 수로 내려라** — 안 내리면 되돌아간다")
            rc = 1
    if rc == 0 and len(f["silent"]):
        print("\n  ★ 조용한 결측이 0 이 아니다. 파이프라인은 사유를 **안다** —")
        print("    `width_fail`(=`all_xsec`)을 표준출력에만 찍고 산출물에 안 넣는다.")
        print("    칸을 더하는 것은 발행 스키마를 움직이므로 측정 배치의 일이다(PLAN).")
    return rc


if __name__ == "__main__":
    sys.exit(main())
