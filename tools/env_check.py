#!/usr/bin/env python3
"""
env_check.py — 환경변수 선언 ↔ 실물. **양방향이다.**

    uv run python tools/env_check.py              검사
    uv run python tools/env_check.py --readers    os.environ 독자 전수
    uv run python tools/env_check.py --selftest   ★ 프로브가 살아 있나

★ 왜 양방향인가.
  한쪽만 걸면 예외값에 영원히 머문다. 두 방향 다 실제로 썩는다 —

    코드 → 예시   새 변수를 코드에 넣고 `.env.example` 에 안 적는다.
                  다음 사람이 기계를 세팅하면 그 변수만 비어 있고,
                  증상은 엉뚱한 데서 난다(오늘 FIRE_LANE_INBOX 가 그랬다).
    예시 → 코드   예시에 있는데 코드가 안 쓴다. `FIRE_LANE_RAW` 가 그 상태다.
                  지워진 변수를 계속 세팅하게 만들고, 그게 현역을 이겼다.

★ **단일 독자**가 키 목록 대조보다 세다.
  키 목록은 `os.environ[f"FIRE_LANE_{x}"]` 같은 동적 접근을 못 잡는다.
  "paths.py 밖에서 os.environ 금지" 는 문법만 보면 되고 빠져나갈 구멍이 없다.
  지금은 12곳이 어긴다 — 그래서 이 검사는 **지금 빨갛다.**
  숫자를 줄이는 것이 일이고, 검사를 무르게 만드는 것이 일이 아니다.

★ 면제는 `os.environ` 전체를 보되 명시적으로 적는다.
  `FIRE_LANE_*` 만 보면 `GDAL_*` 같은 것이 또 열두 곳에 흩어지고,
  그때 두 번째 검사를 만들게 된다. 면제는 적히고 세지므로 낡지 않는다.

IN    .env.example · src/**.py · tools/**.py
OUT   없음 (검사)
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"

# ── 분류 ──────────────────────────────────────────────────────
# 설정  — `.env.example` 에 반드시 있어야 한다
SETTINGS = {"FIRE_LANE_DATA", "FIRE_LANE_INBOX",
            "FIRE_LANE_STAGE", "FIRE_LANE_BACKUP"}
# 스위치 — 일회성 디버그. 셸 export 로 쓴다. 예시에 적으면 잡음이다
SWITCHES = {"FIRE_LANE_DEBUG_SEG", "FIRE_LANE_DEBUG_XY", "FIRE_LANE_MIX_SRC",
            "FIRE_LANE_NO_MERGE", "FIRE_LANE_OLD_SNAP"}
# 폐기  — 설정돼 있으면 시끄럽게. 예시에 있으면 안 된다
RETIRED = {"FIRE_LANE_RAW"}

# ── 단일 독자 면제 ────────────────────────────────────────────
#   paths      정본
#   quiet_gdal GDAL_* 를 끄는 자리. 우리 변수가 아니다
#   batches/   일회성. 이미 돌았고 다시 안 돈다(tools/batches/README.md)
#   tests/     검사가 환경을 흉내 내는 것은 정상이다
EXEMPT = ("src/firelane/paths.py", "src/firelane/quiet_gdal.py",
          "tools/batches/", "tests/")

ENV_RE = re.compile(r"""os\.environ(?:\.get)?[\[(]\s*["']([A-Z_]+)["']|"""
                    r"""getenv\(\s*["']([A-Z_]+)["']""")
READ_RE = re.compile(r"os\.environ|os\.getenv")


def _py() -> list[Path]:
    return sorted([*(ROOT / "src").rglob("*.py"), *(ROOT / "tools").rglob("*.py")])


def used_keys() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in _py():
        for m in ENV_RE.finditer(p.read_text(encoding="utf-8", errors="replace")):
            k = m.group(1) or m.group(2)
            if k and k.startswith("FIRE_LANE"):
                out.setdefault(k, []).append(str(p.relative_to(ROOT)))
    return out


def declared_keys() -> set[str]:
    if not EXAMPLE.exists():
        return set()
    keys = set()
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k = line.removeprefix("export ").partition("=")[0].strip()
        if k:
            keys.add(k)
    return keys


def readers() -> list[tuple[str, int, str]]:
    hits = []
    for p in _py():
        rel = str(p.relative_to(ROOT))
        if rel.startswith(EXEMPT) or any(rel.startswith(e) for e in EXEMPT):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace")
                                 .splitlines(), 1):
            code = line.split("#", 1)[0]
            if READ_RE.search(code):
                hits.append((rel, i, line.strip()[:70]))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readers", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    used, decl = used_keys(), declared_keys()
    fail = 0

    if a.selftest:
        # ★ 0건이 청결인지 죽음인지 가르는 유일한 방법이다(HANDOFF 원칙 ④).
        print("양성 대조 — 없는 키를 넣으면 잡히나")
        ok1 = "FIRE_LANE_GHOST" not in used and "FIRE_LANE_GHOST" not in decl
        probe = dict(used); probe["FIRE_LANE_GHOST"] = ["<가짜>"]
        ok2 = bool(set(probe) - decl - SWITCHES - RETIRED)
        print(f"  · 유령 키 미검출 상태  {ok1}")
        print(f"  · 넣으면 검출          {ok2}")
        print(f"  · 독자 프로브          {len(readers())}곳 (0 이면 프로브를 의심하라)")
        return 0 if (ok1 and ok2 and readers()) else 1

    if a.readers:
        r = readers()
        print(f"── os.environ 독자 — paths.py 밖 {len({x[0] for x in r})}파일 · {len(r)}곳")
        for rel, ln, src in r:
            print(f"  {rel}:{ln}  {src}")
        print("\n★ 목표는 0 이다. paths.py 가 유일한 독자여야 동적 접근까지 막힌다.")
        return 0

    # ── ① 코드 → 예시 ────────────────────────────────────────
    miss = sorted((set(used) & SETTINGS) - decl)
    ghost = sorted(set(used) - decl - SETTINGS - SWITCHES - RETIRED)
    if miss or ghost:
        fail = 1
        print("✗ 코드가 쓰는데 .env.example 에 없다")
        for k in miss + ghost:
            print(f"    {k}   ← {', '.join(sorted(set(used[k])))[:70]}")
        print("  새 기계를 세팅하면 이 값만 비고, 증상은 엉뚱한 데서 난다.")

    # ── ② 예시 → 코드 ────────────────────────────────────────
    dead = sorted(decl - set(used))
    if dead:
        fail = 1
        print("✗ .env.example 에 있는데 코드가 안 쓴다")
        for k in dead:
            print(f"    {k}")
        print("  지워진 변수를 계속 세팅하게 만든다. FIRE_LANE_RAW 가 그랬다.")

    # ── ③ 분류 위반 ──────────────────────────────────────────
    bad = sorted(decl & (SWITCHES | RETIRED))
    if bad:
        fail = 1
        print("✗ 예시에 있으면 안 되는 것")
        for k in bad:
            why = "일회성 디버그 스위치" if k in SWITCHES else "폐기된 변수"
            print(f"    {k}   {why}")

    # ── ④ 단일 독자 ──────────────────────────────────────────
    r = readers()
    files = sorted({x[0] for x in r})
    if r:
        fail = 1
        print(f"✗ paths.py 밖에서 os.environ 을 읽는다 — {len(files)}파일 · {len(r)}곳")
        for f in files:
            print(f"    {f}")
        print("  ★ 키 목록 대조는 동적 접근을 못 잡는다. 단일 독자는 못 빠져나간다.")
        print("    tools/env_check.py --readers 로 줄 번호를 본다.")

    if not fail:
        print(f"✓ 없음 — 설정 {len(decl)}키 · 독자 paths.py 하나")
    return fail


if __name__ == "__main__":
    raise SystemExit(main())
