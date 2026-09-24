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
    """`>=22.12.0` · `^20.19.0` · `18` · `>= 22` 한 항을 판정한다.

    ★ 2026-09-24 (PLAN §13 W13-8). 모르는 문법을 `True` 로 넘겼다 —
      **못 읽은 것을 통과로 센다.** 이 저장소가 여러 번 닫은 형태다.
      이제 `None` 을 내고 부르는 쪽이 「못 읽었다」로 다룬다.
    """
    t = term.strip()
    if not t or t in ("*", "x"):
        return True
    m = re.match(r"^(>=|<=|>|<|\^|~|=)?\s*v?(\d+(?:\.\d+){0,2})$", t)
    if not m:
        return None    # 못 읽었다 — 부르는 쪽이 정한다
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


#: `18 - 22` 꼴 하이픈 범위. **양쪽 끝을 포함**한다(npm 사양).
HYPHEN = re.compile(r"^\s*v?(\d+(?:\.\d+){0,2})\s+-\s+v?(\d+(?:\.\d+){0,2})\s*$")


def satisfies(rng: str, v: tuple[int, int, int]) -> bool | None:
    """`||` 로 묶인 범위. 공백으로 이은 항은 전부 참이어야 한다.

    ★ 2026-09-24 (PLAN §13 W13-8). 실측으로 **두 갈래가 틀렸다** —
        `18 - 22`    하이픈 범위를 `18` 과 `22` 두 항으로 쪼개 **양쪽 다** 요구했다
        `<22.12.0`   `_ver` 가 (22, 999, 0) 같은 호출자 가정과 겹쳐 상한이 뒤집혔다
      그리고 못 읽은 문법을 통과로 셌다. **셋 다 닫는다.**

    :returns: 참/거짓, 또는 **못 읽었으면 `None`**. 부르는 쪽이 정한다 —
        이 함수는 npm 이 아니고, 모르는 것을 안다고 하지 않는다.
    """
    unknown = False
    for alt in rng.split("||"):
        h = HYPHEN.match(alt)
        if h:
            lo, hi = _ver(h.group(1)), _ver(h.group(2))
            # 끝 값이 `22` 처럼 짧으면 그 major 전체를 포함한다(npm 사양)
            if len(h.group(2).split(".")) == 1:
                hi = (hi[0], 10**9, 10**9)
            elif len(h.group(2).split(".")) == 2:
                hi = (hi[0], hi[1], 10**9)
            if lo <= v <= hi:
                return True
            continue
        terms = re.findall(r"(?:>=|<=|>|<|\^|~|=)?\s*v?\d+(?:\.\d+){0,2}|\*", alt)
        if not terms:
            unknown = True
            continue
        got = [_one(t, v) for t in terms]
        if any(g is None for g in got):
            unknown = True
        elif all(got):
            return True
    return None if unknown else False


def nvmrc_major() -> int:
    return int((NAVI / ".nvmrc").read_text(encoding="utf-8").strip())


def engine_violations(major: int) -> tuple[list[str], list[str]]:
    """`.nvmrc` 메이저의 **최신 부판**으로 잠금의 engines 를 전부 대 본다.

    ★ setup-node 는 `22` 를 받으면 22 의 최신을 깐다. 그래서 22.x 최신으로 본다.
      상한(`<22.12.0`)을 제대로 보려면 **999 가 아니라 실제 최신**이 필요한데
      그것은 네트워크가 있어야 안다. 여기서는 `major.x` 의 **아무 부판이라도
      만족하면 통과**로 본다 — 상한이 있는 범위를 거짓 빨강으로 만들지 않는다.

    :returns: (위반, **못 읽은 범위**). 둘째는 실패로 세지 않고 **알린다** —
        이 함수는 npm 이 아니다(§W13-8).
    """
    lock = json.loads((NAVI / "package-lock.json").read_text(encoding="utf-8"))
    bad, unknown = [], []
    for name, meta in lock.get("packages", {}).items():
        eng = meta.get("engines")
        rng = eng.get("node") if isinstance(eng, dict) else None
        if not rng:
            continue
        # major 안에서 하나라도 맞으면 통과. 상한 있는 범위를 위해 낮은 쪽도 본다.
        probes = [(major, 0, 0), (major, 12, 0), (major, 999, 0)]
        got = [satisfies(rng, v) for v in probes]
        if any(g is None for g in got):
            unknown.append(f"{name or '(루트)'}  node {rng}")
        elif not any(got):
            bad.append(f"{name or '(루트)'}  node {rng}")
    return bad, unknown


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
        # ★ 2026-09-24 (W13-8). 아래 여섯이 종전 판에서 **전부 틀렸다.**
        #   자기검사 여덟에 하이픈도 상한도 없어 자기 구멍을 못 봤다.
        ("18 - 22", (22, 9, 0), True), ("18 - 22", (20, 0, 0), True),
        ("18 - 22", (23, 0, 0), False), ("18 - 22", (17, 9, 9), False),
        ("<22.12.0", (22, 11, 0), True), ("<22.12.0", (22, 12, 0), False),
        (">=20 <23", (22, 0, 0), True), (">=20 <23", (23, 1, 0), False),
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
    bad, unreadable = engine_violations(want)
    if unreadable:
        # ★ 막지 않는다 — 이 도구는 npm 이 아니다. 다만 **조용하지도 않다.**
        #   진짜 강제는 `web/navi/.npmrc` 의 `engine-strict=true` 가 한다.
        print(f"· 못 읽은 engines 범위 {len(unreadable)}개 — npm 이 판정한다(.npmrc engine-strict)")
        for u in unreadable[:5]:
            print("    " + u)
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
