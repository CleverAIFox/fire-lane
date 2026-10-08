#!/usr/bin/env python3
"""
sizecheck.py — **파일이 얼마나 긴가.** 양방향 래칫이다.

    uv run python tools/sizecheck.py            판정 (verify.sh · CI)
    uv run python tools/sizecheck.py --table    상한을 넘는 파일 전부를 표로
    uv run python tools/sizecheck.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-22 (DECISIONS §218-5 · 하토르 `check_file_size.py` 모범). 길이를 세는 검사가
  하나도 없었다. 실측으로 `tests/test_guards.py` 가 2,396줄 · `tools/dms.py` 가 1,250줄이고,
  둘 다 **한 번에 는 것이 아니라 배치마다 조금씩** 늘었다. 조금씩 느는 것은 어느 배치도
  「내가 늘렸다」고 느끼지 않는다 — 그래서 세는 자리가 있어야 한다.

★ 오늘 넘는 파일을 오늘 줄이라고 하지 않는다. `dupcheck --max` · `gate_parity` 의
  `RATCHET` 과 같은 방식이다 — **지금 값에서 시작해 내린다.** 넘는 파일은 `EXCEPTIONS` 에
  오늘 줄 수 그대로 박힌다.

── 판정 (양방향) ──────────────────────────────────────────────
    예외 없는 파일이 상한을 넘었다        실패 — 새로 넘었다. 쪼개거나 예외를 사유와 함께
    예외 파일이 기록보다 늘었다           실패 — 예외는 늘 자리가 아니다
    예외 파일이 기록보다 줄었다           실패 — **예외를 그 수로 내려라** (안 내리면 다시 는다)
    예외 파일이 상한 아래로 내려왔다      실패 — 예외를 지워라
    예외 파일이 없어졌다                  실패 — 예외를 지워라

★ 줄었을 때도 실패인 이유 — 느슨해진 래칫은 초록으로 위장한다. 2026-09-19 에 커버리지
  래칫이 14 인데 실물이 24% 인 것을 나흘간 아무도 몰랐다(PLAN §13 W4-9). 이 도구의 수는
  **선언된 개수**라 같음이 의미를 갖는다(verify.sh 「커버리지 래칫」 머리의 이산/연속 구분).

── 무엇을 세나 ────────────────────────────────────────────────
`src/` · `tools/` · `tests/` 아래 `.py` · `.sh` · `.mjs`. 줄 수는 `wc -l` 과 같게 센다.
`tests/` 는 시험 상한(700), 나머지는 코드 상한(600)이다 — 시험은 사례를 나열하므로
같은 일을 하는 코드보다 길다.
★ 추적 여부는 안 가린다. 커밋 **전에** 늘어난 것을 잡는 것이 목적이다.

── 예외 표는 여기 없다 (2026-10-09 · DECISIONS §440-3) ────────
예외 한 줄에 **왜 안 쪼개는지**가 따라붙는 것이 규약이라(§69) 표가 자랄수록
이 파일이 제 상한에 가까워졌다 — 하루에 세 번 그 벽을 쳤다. **재는 쪽과
적는 쪽을 갈랐다**: 표와 래칫 선언은 `tools/sizetable.py` 가 들고, 여기는
세고 판정하는 일만 남는다. 올리는 쪽은 안 골랐다 — 「검사기가 제 검사를
못 지킨다」는 이 파일이 재는 바로 그 병이다.

IN    src/** · tools/** · tests/** · `sizetable.EXCEPTIONS`
OUT   표준출력 (판정)
PARAM LIMITS   (예외와 래칫 선언은 `tools/sizetable.py`)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sizetable import EXCEPTIONS

ROOT = Path(__file__).resolve().parents[1]
# ★ 2026-09-24 (DECISIONS §244). `web/navi/src` 가 범위 밖이었다. 그래서 상한을
#   넘는 프런트 파일 셋(`OpsApp.tsx` 744 · `App.tsx` 640 · `domain/graph.ts` 627)이
#   **래칫에 한 번도 안 잡혔다.** 길이 상한은 「한 파일이 몇 가지 일을 하는가」를
#   재는 것이고 그 물음에 언어는 상관없다.
DIRS = ("src", "tools", "tests", "web/navi/src", "web/navi/test")
SUFFIX = (".py", ".sh", ".mjs", ".ts", ".tsx")
SKIP = {"__pycache__", ".venv", "node_modules", "fixtures"}

# ★ 상한. 한 곳에만 산다 — 부르는 쪽(verify.sh · contract.yml)은 인자를 안 적는다.
LIMITS = {"code": 600, "test": 700}


def kind(rel: str) -> str:
    return "test" if rel.startswith("tests/") else "code"


def count_lines(p: Path) -> int:
    """`wc -l` 과 같다 — 개행 문자 수. 끝개행이 없는 마지막 줄은 안 센다."""
    return p.read_bytes().count(b"\n")


def measure(root: Path = ROOT) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in SUFFIX:
                continue
            rel = p.relative_to(root)
            if SKIP & set(rel.parts):
                continue
            out[rel.as_posix()] = count_lines(p)
    return out


def judge(counts: dict[str, int], exceptions: dict[str, int],
          limits: dict[str, int] = LIMITS) -> list[str]:
    """위반 목록. 비면 통과다. **순수 함수**라 시험이 합성 입력으로 부른다."""
    bad: list[str] = []
    for rel, n in sorted(counts.items()):
        lim = limits[kind(rel)]
        if rel in exceptions:
            want = exceptions[rel]
            if n <= lim:
                bad.append(f"{rel}: {n}줄 — 상한 {lim} 아래로 내려왔다. EXCEPTIONS 에서 지워라")
            elif n > want:
                bad.append(f"{rel}: {n}줄 > 예외 {want} — 늘었다. 예외는 늘 자리가 아니다")
            elif n < want:
                bad.append(f"{rel}: {n}줄 < 예외 {want} — 줄었다. EXCEPTIONS 를 {n} 으로 내려라"
                           " (안 내리면 다시 늘어도 안 운다)")
        elif n > lim:
            bad.append(f"{rel}: {n}줄 > 상한 {lim} — 새로 넘었다. 쪼개거나, 못 쪼개는 사유와"
                       " 함께 EXCEPTIONS 에 오늘 수로 적어라")
    for rel, want in sorted(exceptions.items()):
        if rel not in counts:
            bad.append(f"{rel}: 예외 {want} 인데 파일이 없다. EXCEPTIONS 에서 지워라")
        elif want <= limits[kind(rel)]:
            bad.append(f"{rel}: 예외 {want} 가 상한 {limits[kind(rel)]} 이하다 — 예외가 아니다")
    return bad


def selftest() -> int:
    """★ 빈 그물인가. 판정기가 다섯 갈래를 전부 우는지 합성 입력으로 본다."""
    lim = {"code": 10, "test": 20}
    cases = {
        "새로 넘음": ({"tools/a.py": 11}, {}),
        "늘어남": ({"tools/a.py": 13}, {"tools/a.py": 12}),
        "줄어듦": ({"tools/a.py": 11}, {"tools/a.py": 12}),
        "상한 아래": ({"tools/a.py": 9}, {"tools/a.py": 12}),
        "없어짐": ({}, {"tools/a.py": 12}),
    }
    dead = [name for name, (c, e) in cases.items() if not judge(c, e, lim)]
    if judge({"tools/a.py": 12, "tests/t.py": 20}, {"tools/a.py": 12}, lim):
        dead.append("정상 입력에서 운다")
    if not measure():
        dead.append("저장소에서 파일을 0개 셌다 — 수집기가 죽었다")
    if dead:
        print("✗ 판정기 자기검사 실패 — " + ", ".join(dead))
        return 1
    print(f"✓ 판정기 OK — 다섯 갈래가 울고 정상은 통과한다 · 파일 {len(measure())}개")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="파일 길이 양방향 래칫")
    ap.add_argument("--table", action="store_true", help="상한을 넘는 파일 전부를 표로")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    counts = measure()
    if not counts:
        print("✗ 파일을 0개 셌다 — 수집기가 죽었다")
        return 1
    if a.table:
        for rel, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            lim = LIMITS[kind(rel)]
            if n > lim:
                tag = f"예외 {EXCEPTIONS[rel]}" if rel in EXCEPTIONS else "★ 미등재"
                print(f"  {n:>6}  {rel:<40} 상한 {lim} · {tag}")
    bad = judge(counts, EXCEPTIONS)
    if bad:
        print(f"✗ 파일 길이 {len(bad)}건")
        for b in bad:
            print(f"    {b}")
        return 1
    over = sum(1 for r, n in counts.items() if n > LIMITS[kind(r)])
    print(f"✓ 파일 {len(counts)}개 · 상한 코드 {LIMITS['code']} · 시험 {LIMITS['test']}"
          f" · 예외 {len(EXCEPTIONS)}개가 기록과 같다 (넘는 파일 {over})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
