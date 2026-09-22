#!/usr/bin/env python3
"""
navi_env.py — **내비를 검사하는 환경이 CI 와 같은가.**

    uv run python tools/navi_env.py              잠금이 바뀌었으면 npm ci · 판 대조
    uv run python tools/navi_env.py --no-sync    대조만 (CI — 거기는 늘 npm ci 다)
    uv run python tools/navi_env.py --selftest   판 비교기가 살아 있나

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22 (DECISIONS §213-1). CI 에서 `Cannot find namespace 'GeoJSON'` 으로
내비 타입 검사가 죽었는데 로컬 verify 는 초록이었다. 원인이 셋 겹쳤다 —

    1. `GeoJSON` 타입을 maplibre 가 **끼워 주는** `@types/geojson` 에 얹혀 썼다.
       의존성이 한 판 바뀌면 사라진다(그날 죽은 것이 dependabot 의 maplibre 가지).
    2. CI 는 `npm ci` 로 **잠금대로** 새로 깔고, 로컬 verify 는 **있던 node_modules**
       로 검사했다. 잠금과 설치물이 어긋나도 로컬은 모른다.
    3. CI 노드는 `.nvmrc` 의 20 이었는데 잠금 안에 `node >= 22` 를 요구하는
       패키지가 이미 있었다(EBADENGINE 경고가 매번 떴다). 경고라 아무도 안 봤다.

1 은 `package.json` 에 직접 선언해 닫았다. 이 도구가 2 · 3 을 닫는다.

── 무엇을 보는가 ───────────────────────────────────────────────
    ① 잠금 지문 = 마지막 `npm ci` 때 지문   다르면 npm ci 를 돈다(로컬 = CI)
    ② 로컬 노드 메이저 = `.nvmrc`           다르면 실패 — CI 와 다른 런타임이다
    ③ 잠금의 모든 `engines.node` 를 `.nvmrc` 판이 만족하는가
       — **경고를 실패로 올린다.** 경고로 두면 3 이 또 난다

IN    web/navi/.nvmrc · web/navi/package.json · web/navi/package-lock.json
OUT   web/navi/node_modules/.fl-lock-sha256 (지문) · 표준출력
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAVI = ROOT / "web" / "navi"
STAMP = NAVI / "node_modules" / ".fl-lock-sha256"


def _ver(s: str) -> tuple[int, int, int]:
    nums = [int(x) for x in re.findall(r"\d+", s)[:3]]
    return tuple((nums + [0, 0, 0])[:3])  # type: ignore[return-value]


def _one(term: str, v: tuple[int, int, int]) -> bool:
    """`>=22.12.0` · `^20.19.0` · `18` · `>= 22` 한 항을 판정한다."""
    t = term.strip()
    if not t or t in ("*", "x"):
        return True
    m = re.match(r"^(>=|<=|>|<|\^|~|=)?\s*v?(\d+(?:\.\d+){0,2})", t)
    if not m:
        return True    # 모르는 문법은 막지 않는다 — 막으면 거짓 빨강이다
    op, w = m.group(1) or "=", _ver(m.group(2))
    parts = len(m.group(2).split("."))
    if op == ">=":
        return v >= w
    if op == ">":
        return v > w
    if op == "<=":
        return v <= w
    if op == "<":
        return v < w
    if op == "^":
        return v[0] == w[0] and v >= w
    if op == "~":
        return v[:2] == w[:2] and v >= w
    # 맨 숫자: `18` 은 18.x, `18.2` 는 18.2.x
    return v[:parts] == w[:parts]


def satisfies(rng: str, v: tuple[int, int, int]) -> bool:
    """`||` 로 묶인 범위. 공백으로 이은 항은 전부 참이어야 한다."""
    for alt in rng.split("||"):
        terms = re.findall(r"(?:>=|<=|>|<|\^|~|=)?\s*v?\d+(?:\.\d+){0,2}|\*", alt)
        if all(_one(t, v) for t in terms):
            return True
    return False


def nvmrc_major() -> int:
    return int((NAVI / ".nvmrc").read_text(encoding="utf-8").strip())


def engine_violations(major: int) -> list[str]:
    """`.nvmrc` 메이저의 **최신 부판**으로 잠금의 engines 를 전부 대 본다.

    ★ setup-node 는 `22` 를 받으면 22 의 최신을 깐다. 그래서 22.999.0 으로 본다.
    """
    v = (major, 999, 0)
    lock = json.loads((NAVI / "package-lock.json").read_text(encoding="utf-8"))
    bad = []
    for name, meta in lock.get("packages", {}).items():
        rng = (meta.get("engines") or {}).get("node") if isinstance(meta.get("engines"), dict) else None
        if rng and not satisfies(rng, v):
            bad.append(f"{name or '(루트)'}  node {rng}")
    return bad


def lock_sha() -> str:
    return hashlib.sha256((NAVI / "package-lock.json").read_bytes()).hexdigest()


def local_major() -> int | None:
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    return _ver(out)[0]


def selftest() -> int:
    cases = [
        (">= 22", (22, 999, 0), True), (">= 22", (20, 999, 0), False),
        ("^20.19.0 || >=22.12.0", (22, 999, 0), True),
        ("^20.19.0 || >=22.12.0", (21, 999, 0), False),
        ("^22.20 || ^24.12 || >=25", (22, 999, 0), True),
        ("^22.20 || ^24.12 || >=25", (20, 999, 0), False),
        (">=6.9.0", (20, 999, 0), True), ("18", (18, 3, 0), True), ("18", (20, 0, 0), False),
    ]
    bad = [(r, v, want) for r, v, want in cases if satisfies(r, v) != want]
    if bad:
        print("✗ 판 비교기가 틀린다:", bad)
        return 1
    print(f"✓ 판 비교기 {len(cases)}건 전부 맞다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true", help="npm ci 를 돌지 않는다 (CI)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    fail = 0
    want = nvmrc_major()

    # ③ 잠금의 engines
    bad = engine_violations(want)
    if bad:
        fail = 1
        print(f"✗ .nvmrc 노드 {want} 을 만족하지 않는 패키지 {len(bad)}개 — CI 에서 EBADENGINE 이다")
        for b in bad[:12]:
            print("    " + b)
        print("  .nvmrc 를 올리거나 그 패키지 판을 내린다. 경고로 두지 않는다(§213-1).")
    else:
        print(f"✓ 잠금의 engines 전부 노드 {want} 을 받는다")

    # ② 로컬 노드
    got = local_major()
    if got is None:
        print("✗ node 가 없다")
        return 1
    if got != want:
        fail = 1
        print(f"✗ 로컬 노드 {got} ≠ .nvmrc {want} — CI 와 다른 런타임에서 검사한다")
        print(f"  nvm use {want} (또는 fnm use) 뒤에 다시 돌린다")
    else:
        print(f"✓ 로컬 노드 {got} = .nvmrc")

    # ① 잠금 = 설치물
    if not a.no_sync:
        sha = lock_sha()
        have = STAMP.read_text(encoding="utf-8").strip() if STAMP.exists() else ""
        if have != sha:
            why = "지문 없음" if not have else "잠금이 바뀌었다"
            print(f"  {why} → npm ci (CI 와 같은 설치물로 맞춘다)")
            r = subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=NAVI,
                               capture_output=True, text=True)
            if r.returncode != 0:
                print("✗ npm ci 실패\n" + (r.stderr or r.stdout)[-1500:])
                return 1
            STAMP.write_text(sha + "\n", encoding="utf-8")
            print(f"✓ npm ci · 지문 {sha[:12]}")
        else:
            print(f"✓ node_modules = 잠금 (지문 {sha[:12]})")
    return fail


if __name__ == "__main__":
    sys.exit(main())
