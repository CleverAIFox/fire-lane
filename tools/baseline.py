#!/usr/bin/env python3
"""
baseline.py — 판정 산출물을 봉인하고, 나중 실행과 대조한다.

    uv run python tools/baseline.py freeze <태그> [--note "..."]
    uv run python tools/baseline.py list
    uv run python tools/baseline.py diff <태그>

── 왜 필요한가 ────────────────────────────────────────────────
MASTER §18-1 은 `processed` 를 보관하지 않는다. raw + 코드 + 대장이 있으면
결정론적으로 재생성되기 때문이다. **그 전제는 raw 가 살아 있을 때만 참이다.**

2026-08-15 원본을 전량 재취득하면서 수치지형도가 국토정보플랫폼
NGI 20도엽(2020·2022) → V-WORLD SHP 74도엽(2026-03)으로 교체됐다.
구 원본은 더 이상 없다. 즉 1102/386/210/62/444 를 낸 산출물은
**재생성 불가**이며, `field`(실측 원자료)와 같은 등급이 된다.

봉인하지 않고 파이프라인을 한 번 돌리면 덮어써지고, 그 순간
"V-WORLD 로 바꿔서 숫자가 이렇게 변했다" 를 영원히 말할 수 없게 된다.

── 무엇을 봉인하나 ────────────────────────────────────────────
    segments.geojson       판정 정본
    segments.schema.json   필드 계약
    _manifest.json         어떤 원본 파일·sha256 로 만들었나
    seg_uid_map.csv        구간 동일성 추적 키
    nfa_compare.json       ★ 소방서 지정 구간 대조
    meta.json              집계 · EXPECT · sha256 · 주의사항

★ `nfa_compare.json` 은 손으로 옮겨 적은 것이다.
  `segments.py` 의 대조 블록이 `print` 만 하고 파일로 남기지 않기 때문이다
  (segments.py:962). 유일한 외부 대조 수단이 터미널 출력으로만 존재했다.
  파서 교체 후 이것을 파일로 내도록 고쳐야 한다.

── diff 가 하는 일 ────────────────────────────────────────────
seg_uid 로 먼저 맞추고, 안 맞는 것은 중점 최근접(기본 15m)으로 다시 맞춘다.
seg_uid 는 중점 좌표 + 도로명 해시라 소스가 바뀌면 흔들린다.
특히 V-WORLD 는 A0020000 도로명이 채워져 있어(구 NGII 는 전부 빈 문자열)
도로명 해시가 갈릴 수 있다. 그래서 공간 매칭을 폴백으로 둔다.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
from firelane import paths as _p

BASE = _p.BASELINE
KST = timezone(timedelta(hours=9))

FILES = ["segments.geojson", "segments.schema.json",
         "_manifest.json", "seg_uid_map.csv"]

# MASTER §4 대조 결과 (2026-08-13, 도로명 매칭 7구간).
# segments.py 가 파일로 남기지 않아 문서에서 옮겨 적었다.
NFA_COMPARE = {
    "as_of": "2026-08-13",
    "source": "docs/MASTER.md §4 — segments.py 는 print 만 한다(962행)",
    "ref": "동부소방서 소방통로확보대상 지역 현황 2025-07-31 (20구간 7,120m)",
    "match_by": "도로명. 소방서 자료에 좌표가 없다",
    "compare": "구간 대표폭이므로 중앙값과 비교. 최솟값이면 -3~-7m 로 벌어진다",
    "caveat": ("검증이 아니라 적합(fit)이다. 12.6 → 7.24m 로 줄이는 과정에서 "
               "이 표를 게이트로 썼다. 게이트로 쓴 자료는 외부 검증 수단이 아니다."),
    "abs_dev_sum_m": 7.24,
    "abs_dev_sum_m_before": 12.6,
    "rows": [
        {"road": "필문대로289번길", "nfa_m": 8, "ours_median_m": 7.79, "dev_m": -0.21, "n_seg": 30},
        {"road": "필문대로205번길", "nfa_m": 8, "ours_median_m": 7.65, "dev_m": -0.35, "n_seg": 40},
        {"road": "동명로20번길",   "nfa_m": 5, "ours_median_m": 5.00, "dev_m":  0.00, "n_seg": 36},
        {"road": "밤실로4번길",    "nfa_m": 5, "ours_median_m": 6.00, "dev_m":  1.00, "n_seg":  3},
        {"road": "제봉로184번길",  "nfa_m": 5, "ours_median_m": 6.18, "dev_m":  1.18, "n_seg": 19},
        {"road": "중앙로272번길",  "nfa_m": 5, "ours_median_m": 3.50, "dev_m": -1.50, "n_seg":  4},
        {"road": "동계로9번길",    "nfa_m": 6, "ours_median_m": 8.97, "dev_m":  2.97, "n_seg": 18},
    ],
}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def load(p: Path):
    """segments.geojson → [(seg_uid, midpoint_xy, props)]"""
    feats = json.loads(p.read_text(encoding="utf-8"))["features"]
    out = []
    for f in feats:
        pr = f["properties"]
        c = f["geometry"]["coordinates"]
        if f["geometry"]["type"] == "MultiLineString":
            c = [pt for part in c for pt in part]
        mid = c[len(c) // 2] if c else (0, 0)
        out.append((pr.get("seg_uid"), (mid[0], mid[1]), pr))
    return out


def tally(rows) -> dict:
    P = [p for _, _, p in rows]
    v = collections.Counter(p["verdict"] for p in P)
    ln = [p.get("length_m") or 0 for p in P]
    return {
        "n": len(P),
        "verdict": {k: v[k] for k in ("clear", "needs_cv", "blocked", "unknown")},
        "unknown_reason": dict(collections.Counter(
            p.get("unknown_reason") for p in P if p["verdict"] == "unknown")),
        "width_src": dict(collections.Counter(p.get("width_src") for p in P)),
        "length_total_m": round(sum(ln)),
        "in_emd": sum(1 for p in P if p.get("in_emd")),
        "route_usage_pos": sum(1 for p in P if p.get("route_usage")),
        "nfa_designated": sum(1 for p in P if p.get("nfa_designated")),
        "width_verified": sum(1 for p in P if p.get("width_verified")),
    }


# ── freeze ────────────────────────────────────────────────────
def cmd_freeze(args) -> int:
    dst = BASE / args.tag
    if dst.exists() and not args.force:
        print(f"! 이미 있다: {dst}   덮어쓰려면 --force")
        return 1
    missing = [f for f in FILES if not (PROC / f).exists()]
    if missing:
        print(f"! 없다: {missing}   pipeline 을 먼저 돌려라")
        return 1

    dst.mkdir(parents=True, exist_ok=True)
    digests = {}
    for f in FILES:
        shutil.copy2(PROC / f, dst / f)
        digests[f] = sha(dst / f)

    (dst / "nfa_compare.json").write_text(
        json.dumps(NFA_COMPARE, ensure_ascii=False, indent=2), encoding="utf-8")
    digests["nfa_compare.json"] = sha(dst / "nfa_compare.json")

    rows = load(dst / "segments.geojson")
    src = (ROOT / "src/firelane/pipeline.py").read_text(encoding="utf-8")
    expect = src.split("EXPECT = {", 1)[1].split("\n}", 1)[0] if "EXPECT = {" in src else ""

    meta = {
        "tag": args.tag,
        "frozen_at": datetime.now(KST).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "note": args.note or "",
        "tally": tally(rows),
        "expect_snapshot": "EXPECT = {" + expect + "\n}",
        "sha256": digests,
        "why": ("구 원본(국토정보플랫폼 NGI 20도엽 2020·2022)이 2026-08-15 "
                "전량 재취득으로 소실됐다. 이 산출물은 재생성 불가다."),
        "known_limits": [
            "width_verified 전건 false. 레이저 실측 전이다",
            "nfa_compare 는 검증이 아니라 적합(fit)이다",
            "ngii1k 는 ingest 에서 FAIL 이었고 gpkg 는 손으로 돌려 만든 것이다",
        ],
    }
    (dst / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    t = meta["tally"]
    (dst / "README.md").write_text(f"""# 베이스라인 `{args.tag}`

**지우지 마라. 재생성 불가다.**

{meta['why']}

```
세그먼트   {t['n']}
판정      clear {t['verdict']['clear']} · needs_cv {t['verdict']['needs_cv']} · """
        f"""blocked {t['verdict']['blocked']} · unknown {t['verdict']['unknown']}
총연장     {t['length_total_m']:,}m
동명동     {t['in_emd']}
소방서대조  절대편차 합 {NFA_COMPARE['abs_dev_sum_m']}m (7구간, 적합값)
```

## 대조

```bash
uv run python tools/baseline.py diff {args.tag}
```

새 원본으로 파이프라인을 돌린 뒤 실행하면 구간이 어떻게 갈렸는지 나온다.
숫자가 바뀌는 것 자체는 정상이다. **바뀐 이유를 말할 수 있어야 한다.**

## 주의

{chr(10).join('- ' + s for s in meta['known_limits'])}
""", encoding="utf-8")

    print(f"봉인 {dst.relative_to(ROOT)}")
    for f, d in digests.items():
        print(f"  {f:24s} {d[:16]}")
    print(f"\n  세그먼트 {t['n']} · " + " · ".join(f"{k} {v}" for k, v in t["verdict"].items()))
    print("\n★ 커밋해라. .gitignore 는 data/processed 만 막는다.")
    return 0


def cmd_list(args) -> int:
    if not BASE.is_dir():
        print("베이스라인 없음")
        return 0
    for d in sorted(BASE.iterdir()):
        m = d / "meta.json"
        if not m.is_file():
            continue
        j = json.loads(m.read_text(encoding="utf-8"))
        t = j["tally"]
        print(f"{d.name:22s} {j['frozen_at'][:10]}  n={t['n']:5d}  "
              + " ".join(f"{k}={v}" for k, v in t["verdict"].items()))
    return 0


# ── diff ──────────────────────────────────────────────────────
def cmd_diff(args) -> int:
    old_p = BASE / args.tag / "segments.geojson"
    new_p = PROC / "segments.geojson"
    for p in (old_p, new_p):
        if not p.exists():
            print(f"! 없다: {p}")
            return 1

    old, new = load(old_p), load(new_p)
    told, tnew = tally(old), tally(new)

    print(f"베이스라인 {args.tag} → 현재\n")
    print(f"  세그먼트  {told['n']:5d} → {tnew['n']:5d}  ({tnew['n']-told['n']:+d})")
    for k in ("clear", "needs_cv", "blocked", "unknown"):
        a, b = told["verdict"][k], tnew["verdict"][k]
        print(f"  {k:9s} {a:5d} → {b:5d}  ({b-a:+d})")
    print(f"  총연장    {told['length_total_m']:,}m → {tnew['length_total_m']:,}m")
    print(f"  width_src {told['width_src']}\n         →  {tnew['width_src']}")

    # 1) seg_uid 매칭
    oi = {u: (xy, p) for u, xy, p in old if u}
    ni = {u: (xy, p) for u, xy, p in new if u}
    both = oi.keys() & ni.keys()
    pairs = [(oi[u][1], ni[u][1], "uid") for u in both]
    rest_o = [(u, xy, p) for u, xy, p in old if u not in both]
    rest_n = [(u, xy, p) for u, xy, p in new if u not in both]

    # 2) 중점 최근접 폴백
    tol = args.tol
    used = set()
    for _, xy, po in rest_o:
        best, bd = None, tol * tol
        for i, (_, xy2, _pn) in enumerate(rest_n):
            if i in used:
                continue
            d = (xy[0] - xy2[0]) ** 2 + (xy[1] - xy2[1]) ** 2
            if d < bd:
                best, bd = i, d
        if best is not None:
            used.add(best)
            pairs.append((po, rest_n[best][2], "geom"))

    by = collections.Counter(k for _, _, k in pairs)
    print(f"\n  매칭 {len(pairs)}  (seg_uid {by['uid']} · 중점 {tol}m {by['geom']})")
    print(f"  구 미매칭 {told['n']-len(pairs)}  ·  신규 {tnew['n']-len(pairs)}")
    if told["n"]:
        print(f"  seg_uid 유지율 {100*by['uid']/told['n']:.1f}%  (게이트 90%)")

    # 판정 전이
    trans = collections.Counter((a["verdict"], b["verdict"]) for a, b, _ in pairs)
    print("\n  판정 전이 (같은 구간)")
    order = ["clear", "needs_cv", "blocked", "unknown"]
    print("           " + "".join(f"{k:>10s}" for k in order))
    for a in order:
        print(f"    {a:8s}" + "".join(
            f"{trans.get((a,b),0):10d}" for b in order))
    moved = sum(v for (a, b), v in trans.items() if a != b)
    print(f"    바뀐 구간 {moved} / {len(pairs)}")

    # 폭 변화
    d = [(b.get("width_min_m") or 0) - (a.get("width_min_m") or 0)
         for a, b, _ in pairs
         if a.get("width_min_m") and b.get("width_min_m")]
    if d:
        d.sort()
        n = len(d)
        print(f"\n  width_min_m 변화 {n}건  "
              f"중앙 {d[n//2]:+.2f}m · 평균 {sum(d)/n:+.2f}m · "
              f"|Δ|>1m {sum(1 for x in d if abs(x) > 1)}")

    print("\n★ 소방서 7구간 대조는 자동 비교 대상이 아니다.")
    print("  segments.py 가 파일로 남기지 않는다(962행). 파일 출력부터 붙여라.")
    print(f"  구 절대편차 합 {NFA_COMPARE['abs_dev_sum_m']}m — "
          f"{(BASE/args.tag/'nfa_compare.json').relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze"); f.add_argument("tag")
    f.add_argument("--note", default=""); f.add_argument("--force", action="store_true")
    f.set_defaults(fn=cmd_freeze)
    ls = sub.add_parser("list"); ls.set_defaults(fn=cmd_list)
    d = sub.add_parser("diff"); d.add_argument("tag")
    d.add_argument("--tol", type=float, default=15.0)
    d.set_defaults(fn=cmd_diff)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
