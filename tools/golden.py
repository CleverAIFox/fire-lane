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

    # ★ 2026-08-25. 코드 지문을 같이 남긴다.
    #   `lock` 의 뜻은 **"이 산출물이 지금 판정 코드의 정답이다"** 다.
    #   종전에는 `.code_fingerprint` 를 파일이 아예 없을 때만 썼다. 그래서
    #   판정 코드가 정당하게 바뀐 뒤에는 파이프라인을 다시 돌려도, lock 을
    #   다시 해도 낡음 경보가 계속 울렸다. 남는 길이 손으로 지우기 아니면
    #   `--allow-stale` 뿐이었고, 둘 다 게이트를 죽이는 습관을 만든다.
    code_fp = _logic_fingerprint()
    CODE_FP.write_text(code_fp + "\n", encoding="utf-8")

    L1 = fp["L1"]
    print("잠갔다 →", GOLD / "segments.fingerprint.json")
    print(f"  판정 코드 지문 {code_fp}  → {CODE_FP.name}")
    print(f"  구간 {L1['n']} · " + " · ".join(f"{k} {v}" for k, v in L1["verdict"].items()))
    print(f"  총연장 {L1['length_total_m']:,.0f}m · 기하 {fp['L3'][:12]}")
    print("\n이제 쪼개라. 한 덩어리마다:")
    print("  uv run fire-lane --only segments && uv run python tools/golden.py check")
    return 0


def _logic_fingerprint() -> str:
    """판정에 관여하는 코드의 로직 해시.

    ★ 주석 · docstring · 빈 줄을 걷어낸 AST 만 본다. 주석 한 줄을 고쳤다고
      게이트가 울면 사람이 `--allow-stale` 을 쓰기 시작하고, 그 순간
      게이트가 죽는다.
    """
    import ast

    watch = ["src/firelane/segments.py", "src/firelane/seg/width.py",
             "src/firelane/seg/geom.py", "src/firelane/seg/params.py",
             "src/firelane/seg/graph.py", "src/firelane/seg/report.py"]

    def _logic(src: str) -> str:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return src
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.ClassDef,
                              ast.FunctionDef, ast.AsyncFunctionDef)):
                d = ast.get_docstring(n)
                if d is not None and n.body:
                    n.body = n.body[1:] or [ast.Pass()]
        return ast.dump(tree)

    h = hashlib.sha256()
    for rel in sorted(watch):
        q = ROOT / rel
        if q.exists():
            h.update(rel.encode())
            h.update(_logic(q.read_text(encoding="utf-8")).encode())
    return h.hexdigest()[:16]


CODE_FP = SEG.parent / ".code_fingerprint"


def _staleness() -> list[str]:
    """산출물이 코드보다 낡았는가.

    ★ 2026-08-23. `fire-lane` 이 PATH 에 없어 파이프라인이 안 돈 채로
      이 검사를 돌렸고 **통과했다.** golden 은 `segments.geojson` 을 읽는데
      그것이 안 바뀌었으니 옛 산출물을 옛 지문과 비교한 것이다 —
      아무것도 증명하지 않는데 초록불이 뜬다.

      R11 은 "리팩 전후 동일을 증명하기 전에는 커밋하지 마라" 인데,
      증명한 것처럼 보이게 만드니 규칙 자체가 무력해진다.
      **이 저장소가 반복해 겪은 그 모양이다 — 검사가 죽었는데 초록불.**

      판정 로직보다 산출물이 오래됐으면 경고한다. 시각은 거칠지만,
      "안 돌린 채로 통과" 를 막기에는 충분하다.
    """
    if not SEG.exists():
        return []
    now = _logic_fingerprint()
    was = CODE_FP.read_text(encoding="utf-8").strip() if CODE_FP.exists() else None
    if was == now:
        return []
    if was is None:
        # 기준선이 없다. 이번 산출물이 지금 코드로 나온 것으로 본다 —
        # 아니라면 golden 대조 자체가 곧 잡는다.
        CODE_FP.write_text(now + "\n", encoding="utf-8")
        return []
    return [f"판정 로직이 바뀌었다 ({was} → {now})"]


def cmd_check(args) -> int:
    p = GOLD / "segments.fingerprint.json"
    if not p.exists():
        sys.exit("★ 잠근 지문이 없다 — 리팩 시작 전에 golden.py lock 을 했어야 한다")

    stale = _staleness()
    if stale and not getattr(args, "allow_stale", False):
        print("★ 산출물이 판정 코드보다 낡았다. 이 대조는 아무것도 증명하지 않는다.")
        for rel in stale:
            print(f"    {rel}  가 segments.geojson 보다 최근이다")
        print("\n  uv run fire-lane --from segments   ← 먼저 돌려라")
        print("  (uv run 을 빼면 command not found 다. 진입점은 .venv/bin 에 있다)")
        print("\n  정말 낡은 것을 알고 대조하려면 --allow-stale")
        return 1
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


def cmd_selftest(_args) -> int:
    """게이트가 울고, 또 풀리는가.

    ★ 2026-08-25. `lock` 이 `.code_fingerprint` 를 갱신하지 않아 판정 코드가
      한 번 바뀌면 게이트가 영구히 울었다(DECISIONS §69). 산출물 지문
      L1·L2·L3 가 전부 동일한데도 낡았다고 떴고, 남는 길은 손으로 지우기
      아니면 `--allow-stale` 뿐이었다.

      **게이트를 만들 때는 정상적으로 해제되는 경로를 같이 만든다.**
      그 경로가 실제로 도는지를 여기서 본다.

    ★ 실제 지문 파일을 건드리지 않는다. 임시 폴더로 갈아끼우고 되돌린다.
      검사가 정본을 덮어쓰면 그 검사 자체가 사고 원인이 된다.
    """
    import contextlib
    import io
    import tempfile
    global GOLD, CODE_FP

    if not SEG.exists():
        print("· 산출물이 없다 — 건너뛴다 (raw 가 있는 기계에서 돌릴 것)")
        return 0

    keep_gold, keep_fp = GOLD, CODE_FP
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        GOLD = Path(td) / "golden"
        CODE_FP = Path(td) / ".code_fingerprint"

        class _A:
            allow_stale = False
            loose = False

        def q(fn) -> int:
            """소리 없이 돌린다. lock/check 의 정상 출력이 섞이면 읽을 수 없다."""
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                return fn(_A())

        try:
            q(cmd_lock)
            if not CODE_FP.exists():
                print("★ ① lock 이 .code_fingerprint 를 안 남긴다"); bad += 1
            elif CODE_FP.read_text(encoding="utf-8").strip() != _logic_fingerprint():
                print("★ ① 코드 지문이 로직 해시와 다르다"); bad += 1
            else:
                print("  ① lock 이 코드 지문을 남긴다  OK")

            if q(cmd_check) != 0:
                print("★ ② 방금 잠근 것을 check 가 통과 못 한다"); bad += 1
            else:
                print("  ② lock 직후 check 통과      OK")

            CODE_FP.write_text("0" * 16 + "\n", encoding="utf-8")
            if q(cmd_check) == 0:
                print("★ ③ 코드 지문이 어긋났는데 통과한다 — 게이트가 죽었다"); bad += 1
            else:
                print("  ③ 지문이 어긋나면 운다      OK")

            q(cmd_lock)
            if q(cmd_check) != 0:
                print("★ ④ lock 해도 안 풀린다 — 해제 경로가 없다"); bad += 1
            else:
                print("  ④ lock 으로 해제된다        OK")
        finally:
            GOLD, CODE_FP = keep_gold, keep_fp

    if bad:
        print(f"\n★ 게이트 자기검사 {bad}건 실패")
        return 1
    print("\n게이트는 울고, 또 풀린다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lock").set_defaults(fn=cmd_lock)
    sub.add_parser("selftest").set_defaults(fn=cmd_selftest)
    c = sub.add_parser("check")
    c.add_argument("--allow-stale", action="store_true",
                   help="산출물이 코드보다 낡아도 대조한다 (증명이 아님을 알고 쓸 것)")
    c.add_argument("--loose", action="store_true", help="L3 기하 해시를 건너뛴다")
    c.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
