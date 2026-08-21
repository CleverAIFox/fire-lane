#!/usr/bin/env python3
"""
golden.py — 산출물 지문을 뜨고, 리팩 전후가 같은지 증명한다.

    uv run python tools/golden.py lock            현재 산출물을 정답으로 잠근다
    uv run python tools/golden.py check           지금 산출물이 정답과 같은가
    uv run python tools/golden.py check --loose   기하 부동소수 오차를 허용한다

── 왜 필요한가 ────────────────────────────────────────────────
`segments.py` 는 1,168줄이고 `main()` 하나가 1,030줄이다. 이것을 쪼개려면
**쪼갠 뒤에도 판정이 같다**를 증명해야 한다. 증명 없이 쪼개면, 다음에
숫자가 흔들릴 때 원인 후보에 "리팩 때문인가"가 추가된다. 08-17/18 에
반나절씩 태운 것이 정확히 그 종류의 혼선이었다.

`tools/baseline.py` 는 **소스가 바뀌었을 때** 판정이 어떻게 달라졌나를 본다.
이 도구는 반대다. **아무것도 달라지면 안 되는 상황**에서 쓴다.

    baseline  V-WORLD 로 갈아탔다 → 27구간 바뀌었다, 왜인가
    golden    코드만 옮겼다       → 0 이어야 한다, 아니면 즉시 되돌린다

── 무엇을 비교하나 ────────────────────────────────────────────
지오메트리 바이트를 통째로 비교하면 부동소수 말단에서 거짓 경보가 난다.
그래서 세 층으로 나눈다.

    L1 집계   구간 수 · 판정 분포 · 총연장 · unknown_reason
              → 이게 깨지면 로직이 바뀐 것이다. 변명 불가.
    L2 구간별 seg_uid 마다 verdict · width_min · width_max · width_src
              → 어느 구간이 어떻게 달라졌는지 짚어낸다.
    L3 기하   좌표 반올림(mm) 후 해시
              → --loose 는 이 층만 건너뛴다.

── 쓰는 법 ────────────────────────────────────────────────────
    1. 리팩 시작 전에  golden.py lock
    2. 한 덩어리 옮길 때마다  pipeline --only segments  →  golden.py check
    3. 다르면 그 자리에서 되돌린다. 쌓아두고 나중에 찾지 않는다.

지문은 `data/golden/` 에 남는다. 산출물이 아니라 **판정의 사진**이므로
가볍고(수백 KB) 커밋해도 된다. 리팩이 끝나면 지우거나 그대로 둔다.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "data/processed/segments.geojson"
GOLD = ROOT / "data/golden"

# L2 에서 구간마다 비교할 필드. 판정에 직접 관계된 것만 넣는다.
# 진단용 컬럼(merged_n, n_sample 등)은 리팩으로 바뀌어도 무해하므로 뺀다.
FIELDS = ("verdict", "width_min_m", "width_max_m", "width_src",
          "unknown_reason", "length_m", "route_usage")

# 부동소수 비교 허용치. 폭은 mm, 길이는 cm 이하 차이를 같다고 본다.
TOL = {"width_min_m": 1e-3, "width_max_m": 1e-3, "length_m": 1e-2}


def _round_geom(geom, nd: int = 3):
    """좌표를 mm 로 반올림한다. EPSG:4326 이므로 실제로는 소수 7자리."""
    t = geom["type"]
    c = geom["coordinates"]

    def rec(x):
        if isinstance(x, (int, float)):
            return round(x, nd)
        return [rec(i) for i in x]
    return {"type": t, "coordinates": rec(c)}


def fingerprint() -> dict:
    if not SEG.exists():
        sys.exit(f"★ {SEG} 없음 — segments 를 먼저 돌려라")
    d = json.loads(SEG.read_text(encoding="utf-8"))
    feats = d["features"]

    per: dict[str, dict] = {}
    geo = hashlib.sha256()
    for f in sorted(feats, key=lambda f: f["properties"].get("seg_uid", "")):
        p = f["properties"]
        uid = p.get("seg_uid")
        per[uid] = {k: p.get(k) for k in FIELDS}
        geo.update(json.dumps(_round_geom(f["geometry"]), sort_keys=True).encode())

    v = collections.Counter(f["properties"]["verdict"] for f in feats)
    ur = collections.Counter(f["properties"].get("unknown_reason")
                             for f in feats if f["properties"].get("unknown_reason"))
    ws = collections.Counter(f["properties"].get("width_src")
                             for f in feats if f["properties"].get("width_src"))

    return {
        "L1": {
            "n": len(feats),
            "verdict": dict(sorted(v.items())),
            "unknown_reason": dict(sorted(ur.items())),
            "width_src": dict(sorted(ws.items())),
            # 총연장은 판정 로직이 아니라 기하 병합이 바뀌면 움직인다.
            "length_total_m": round(sum(f["properties"].get("length_m") or 0
                                        for f in feats), 1),
        },
        "L2": per,
        "L3": geo.hexdigest(),
    }


def _same(a, b, tol: float | None) -> bool:
    if a is None or b is None:
        return a == b
    if tol is not None and isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol
    return a == b


def cmd_lock(_args) -> int:
    GOLD.mkdir(parents=True, exist_ok=True)
    fp = fingerprint()
    (GOLD / "segments.fingerprint.json").write_text(
        json.dumps(fp, ensure_ascii=False, indent=1), encoding="utf-8")
    L1 = fp["L1"]
    print("잠갔다 →", GOLD / "segments.fingerprint.json")
    print(f"  구간 {L1['n']} · " + " · ".join(f"{k} {v}" for k, v in L1["verdict"].items()))
    print(f"  총연장 {L1['length_total_m']:,.0f}m · 기하 {fp['L3'][:12]}")
    print("\n이제 쪼개라. 한 덩어리마다:")
    print("  uv run fire-lane --only segments && uv run python tools/golden.py check")
    return 0


def cmd_check(args) -> int:
    p = GOLD / "segments.fingerprint.json"
    if not p.exists():
        sys.exit("★ 잠근 지문이 없다 — 리팩 시작 전에 golden.py lock 을 했어야 한다")
    old = json.loads(p.read_text(encoding="utf-8"))
    new = fingerprint()
    bad = 0

    # ── L1 집계 ────────────────────────────────────────────
    for k, ov in old["L1"].items():
        nv = new["L1"].get(k)
        if ov != nv:
            bad += 1
            print(f"★ L1 {k}\n    before {ov}\n    after  {nv}")
    if not bad:
        L1 = new["L1"]
        print(f"L1 OK  구간 {L1['n']} · "
              + " · ".join(f"{k} {v}" for k, v in L1["verdict"].items()))

    # ── L2 구간별 ──────────────────────────────────────────
    o2, n2 = old["L2"], new["L2"]
    gone = sorted(set(o2) - set(n2))
    born = sorted(set(n2) - set(o2))
    diffs = []
    for uid in sorted(set(o2) & set(n2)):
        for f in FIELDS:
            if not _same(o2[uid].get(f), n2[uid].get(f), TOL.get(f)):
                diffs.append((uid, f, o2[uid].get(f), n2[uid].get(f)))
    if gone or born or diffs:
        bad += 1
        print(f"★ L2 소실 {len(gone)} · 신규 {len(born)} · 값변경 {len(diffs)}")
        for uid, f, a, b in diffs[:10]:
            print(f"    {uid}  {f}  {a} → {b}")
        if len(diffs) > 10:
            print(f"    … 외 {len(diffs)-10}건")
        for uid in (gone[:5] + born[:5]):
            print(f"    구간 출입: {uid}")
    else:
        print(f"L2 OK  {len(n2)}구간 전부 동일")

    # ── L3 기하 ────────────────────────────────────────────
    if args.loose:
        print("L3 건너뜀 (--loose)")
    elif old["L3"] != new["L3"]:
        bad += 1
        print(f"★ L3 기하 해시 불일치\n    before {old['L3'][:16]}\n    after  {new['L3'][:16]}")
        print("    L1·L2 가 통과했다면 좌표 말단 오차일 수 있다. --loose 로 확인해봐라.")
        print("    다만 '왜 좌표가 움직였나'를 설명할 수 없으면 되돌리는 쪽이 맞다.")
    else:
        print("L3 OK  기하 동일")

    if bad:
        print("\n★ 산출물이 달라졌다. 방금 옮긴 덩어리를 되돌려라.")
        print("  쌓아두고 나중에 찾지 않는다 — 그게 08-17/18 에 반나절씩 태운 방식이다.")
        return 1
    print("\n리팩 전후 동일. 다음 덩어리로 넘어가도 된다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lock").set_defaults(fn=cmd_lock)
    c = sub.add_parser("check")
    c.add_argument("--loose", action="store_true", help="L3 기하 해시를 건너뛴다")
    c.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
