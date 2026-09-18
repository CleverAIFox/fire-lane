#!/usr/bin/env python3
"""
baseline.py — 판정 산출물을 봉인하고, 나중 실행과 대조한다.

    uv run python tools/baseline.py freeze <태그> [--note "..."]
    uv run python tools/baseline.py list
    uv run python tools/baseline.py diff <태그>
    uv run python tools/baseline.py diff <태그> --transition   경계가 갈린 경우까지

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

★ `nfa_compare.json` 은 **봉인 시점 산출물의 사본**이다(2026-09-17 · DECISIONS §171-2).
  `seg/report.py` 가 매 실행 `processed/nfa_compare.json` 을 쓴다(2026-08-18~).
  종전에는 여기 박힌 2026-08-13 자 손제작 표를 복사했다 — 세 벌 봉인이 전부
  같은 옛 표를 들고 있어 **실행 간 대조가 성립하지 않았다.** 그 세 벌은
  구 원본 소실로 재생성 불가라 그대로 둔다(지우지 않는다).

── diff 가 하는 일 ────────────────────────────────────────────
★ 이 diff 는 **1:1 매칭**이다. 뼈대를 갈면(R3) 구간이 다른 자리에서 잘려 1:N · N:1 이 생기고,
  그때 중점 최근접은 한쪽을 임의로 버린다 — **판정이 움직인 것과 경계가 움직인 것을 구별 못 한다.**
  `--transition` 이 `firelane.transition` 으로 그 경우까지 센다(DECISIONS §187).

seg_uid 로 먼저 맞추고, 안 맞는 것은 중점 최근접(기본 15m)으로 다시 맞춘다.
seg_uid 는 중점 좌표 + 도로명 해시라 소스가 바뀌면 흔들린다.
특히 V-WORLD 는 A0020000 도로명이 채워져 있어(구 NGII 는 전부 빈 문자열)
도로명 해시가 갈릴 수 있다. 그래서 공간 매칭을 폴백으로 둔다.
"""
from __future__ import annotations

import argparse
import collections
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

NFA = "nfa_compare.json"


def nfa_delta(old: dict, new: dict) -> dict:
    """소방서 대조 두 판을 도로명으로 맞춘다. 파일을 안 읽는다 — 테스트가 부른다.

    ★ 도로명이 키인 이유 — 소방서 자료에 좌표가 없다(`match_by`).
    """
    o = {r["road"]: r for r in old.get("rows") or []}
    n = {r["road"]: r for r in new.get("rows") or []}
    rows = []
    for road in sorted(o.keys() | n.keys()):
        a, b = o.get(road), n.get(road)
        rows.append({
            "road": road,
            "old_dev_m": a and a.get("dev_m"),
            "new_dev_m": b and b.get("dev_m"),
            "old_n": a and a.get("n_seg"),
            "new_n": b and b.get("n_seg"),
        })
    return {
        "abs_old": old.get("abs_dev_sum_m"),
        "abs_new": new.get("abs_dev_sum_m"),
        "only_old": sorted(o.keys() - n.keys()),
        "only_new": sorted(n.keys() - o.keys()),
        "rows": rows,
    }


from firelane.hashing import sha256 as _h_sha256


def sha(p, chunk: int = 1 << 20) -> str:
    # ★ 2026-09-13. 구현은 `firelane.hashing` 한 곳이다.
    #   이름은 호출부 때문에 남긴다 — 옮긴 것과 고친 것을
    #   한 커밋에 섞지 않는다(원칙 ⑤).
    return _h_sha256(p, chunk)


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
    missing = [f for f in FILES + [NFA] if not (PROC / f).exists()]
    if missing:
        print(f"! 없다: {missing}   pipeline 을 먼저 돌려라")
        return 1

    dst.mkdir(parents=True, exist_ok=True)
    digests = {}
    for f in FILES:
        shutil.copy2(PROC / f, dst / f)
        digests[f] = sha(dst / f)

    # ★ 봉인 시점 산출물을 복사한다. 손으로 옮겨 적지 않는다(§171-2).
    shutil.copy2(PROC / NFA, dst / NFA)
    digests[NFA] = sha(dst / NFA)
    nfa = json.loads((dst / NFA).read_text(encoding="utf-8"))

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
        ],
    }
    (dst / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
소방서대조  절대편차 합 {nfa.get('abs_dev_sum_m')}m ({len(nfa.get('rows') or [])}도로명, 적합값)
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

    # ★ 소방서 블록보다 **먼저** 부른다. 그 블록은 파일이 없으면 early return 하고,
    #   2026-09-18 첫 배선에서 전이표가 그 뒤에 있어 **조용히 생략됐다**(초록불인데 안 돈 그 형태).
    if args.transition:
        _transition(old_p, new_p)

    # 소방서 대조 — 봉인판 대 현재판
    op, np_ = BASE / args.tag / NFA, PROC / NFA
    if not (op.exists() and np_.exists()):
        print(f"\n  ! 소방서 대조 생략 — 없다: {[str(x) for x in (op, np_) if not x.exists()]}")
        return 0
    old_n = json.loads(op.read_text(encoding="utf-8"))
    dl = nfa_delta(old_n, json.loads(np_.read_text(encoding="utf-8")))
    print(f"\n  소방서 대조  절대편차 합 {dl['abs_old']}m → {dl['abs_new']}m")
    for r in dl["rows"]:
        f = lambda v: "   —  " if v is None else f"{v:+6.2f}"  # noqa: E731
        print(f"    {r['road']:14s} {f(r['old_dev_m'])} → {f(r['new_dev_m'])}   "
              f"세그 {r['old_n'] or 0:3d} → {r['new_n'] or 0:3d}")
    if old_n.get("as_of", "") <= "2026-08-13":
        print("  ★ 봉인판이 2026-08-13 손제작 표다 — 재생성 불가 판이라 그대로 둔다(§171-2)")
    return 0


def _transition(old_p: Path, new_p: Path) -> None:
    """경계가 갈린 경우까지 — 1:N · N:1 · 소멸 · 신설. 판정 전이는 **길이 m 가중**이다(§187)."""
    import geopandas as gpd

    from firelane import transition as X

    o, n = gpd.read_file(old_p).to_crs(5186), gpd.read_file(new_p).to_crs(5186)
    t = X.build(o, n)
    s = X.summarize(t, len(o), len(n))
    print("\n  전이표 — 경계가 갈린 경우까지")
    print("    대응  " + " · ".join(f"{k} {v}" for k, v in s["cardinality"].items())
          + f"  ·  신설 {s['added']}")
    print(f"    길이 옛 {s['len_old_m']:,.0f}m · 대응 {s['len_matched_m']:,.0f}m · 중점 폴백 {s['fallback_mid']}")
    print("\n  판정 전이 (길이 m 가중)")
    print("\n".join("    " + x for x in X.verdict_flow(t).to_string().splitlines()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze"); f.add_argument("tag")
    f.add_argument("--note", default=""); f.add_argument("--force", action="store_true")
    f.set_defaults(fn=cmd_freeze)
    ls = sub.add_parser("list"); ls.set_defaults(fn=cmd_list)
    d = sub.add_parser("diff"); d.add_argument("tag")
    d.add_argument("--tol", type=float, default=15.0)
    d.add_argument("--transition", action="store_true",
                   help="경계가 갈린 경우까지 본다 — 1:N · N:1 · 소멸 · 신설 (R3 전후. DECISIONS §187)")
    d.set_defaults(fn=cmd_diff)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
