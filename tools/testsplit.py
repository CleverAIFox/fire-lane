#!/usr/bin/env python3
"""
tools/testsplit.py — **`contract-tests` 의 조각을 CI 조건의 실측 시간으로 가른다.**  (DECISIONS §760 · ⓲L-C)

    uv run python tools/testsplit.py --part 2 --of 4        그 조각의 시험 파일(한 줄에 하나) — 워크플로가 부른다
    uv run python tools/testsplit.py --report --of 4        조각별 예상 초 · 최대/최소 비 · 장부에 없는 파일
    uv run python tools/testsplit.py --selftest             ★ 프로브가 살아 있나

IN    `tests/**/test_*.py` · `data/golden/ci_testtimes.json`(CI 조건으로 잰 파일별 초 — `{"seconds": {"test_x.py": 12.3}}`)
OUT   파일 목록 · 보고
PARAM 조각 수(`--of`)
밖    **시간 그 자체는 안 잰다**(장부가 든다 · 새로 재는 법은 DECISIONS §760). 시험이 서로 독립인지 · CI 러너의 속도는 안 본다.
      장부가 **로컬(레이크 있음) 실측**이면 안 맞는다 — `data/golden/testtimes.json` 으로 가른 예측은 CI 실측과 2.6~6.1 배 어긋났다(§760).

★ 왜 만들었나 — 옛 분할은 「파일 수 + 손으로 꽂은 핀 열 개」 였다. 조각 넷이 6분 29초 · 3분 12초 · 1분 44초 · 2분 38초(4배 어긋남)로 돌았고 **가장 느린 조각이 전체를 정한다.**
★ 알고리즘: **LPT**(긴 것부터 놓고, 매번 합이 가장 작은 조각에 둔다). 결정적이다 — (초 내림차순 · 이름순) 정렬 · 동률은 낮은 조각 번호. 장부에 없는 새 파일은 **장부 중앙값**으로 친다 —
  그 파일은 어느 조각에든 들어간다(빠짐 · 겹침이 없다는 계약은 `tests/test_contract_split.py` 가 문다).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "golden" / "ci_testtimes.json"


def test_files(root: Path = ROOT) -> list[str]:
    """`find tests -name 'test_*.py' | LC_ALL=C sort` 와 같은 순서(바이트순)."""
    return sorted((str(p.relative_to(root)) for p in (root / "tests").rglob("test_*.py")), key=lambda s: s.encode())


def load_seconds(path: Path = LEDGER) -> dict[str, float]:
    if not path.is_file():
        return {}
    return {k: float(v) for k, v in json.loads(path.read_text(encoding="utf-8"))["seconds"].items()}


def split(files: list[str], seconds: dict[str, float], n: int) -> list[list[str]]:
    """LPT. 반환은 조각마다 파일 목록(바이트순)."""
    med = statistics.median(seconds.values()) if seconds else 1.0
    w = {f: seconds.get(Path(f).name, med) for f in files}
    bins: list[list[str]] = [[] for _ in range(n)]
    tot = [0.0] * n
    for f in sorted(files, key=lambda f: (-w[f], f.encode())):
        i = min(range(n), key=lambda k: (tot[k], k))
        bins[i].append(f)
        tot[i] += w[f]
    return [sorted(b, key=lambda s: s.encode()) for b in bins]


def defects(files: list[str], parts: list[list[str]], seconds: dict[str, float], ratio: float = 2.0) -> list[str]:
    """조각의 **결함** — 빠진 파일 · 겹친 파일 · 장부 시간이 `ratio` 배 넘게 치우친 것. 비어 있으면 깨끗하다."""
    flat = [f for p in parts for f in p]
    out = [f"빠짐 {f}" for f in sorted(set(files) - set(flat))]
    out += [f"겹침 {f}" for f in sorted({f for f in flat if flat.count(f) > 1})]
    med = statistics.median(seconds.values()) if seconds else 1.0
    sums = [sum(seconds.get(Path(f).name, med) for f in p) for p in parts]
    if sums and max(sums) > ratio * min(sums):
        out.append(f"치우침 {[round(x) for x in sums]}")
    return out


def report(files: list[str], seconds: dict[str, float], n: int) -> str:
    med = statistics.median(seconds.values()) if seconds else 1.0
    bins = split(files, seconds, n)
    sums = [sum(seconds.get(Path(f).name, med) for f in b) for b in bins]
    missing = [f for f in files if Path(f).name not in seconds]
    ratio = max(sums) / min(sums) if min(sums) else float("inf")
    return (f"조각 {n} — 예상 초 {[round(s) for s in sums]} · 최대/최소 {ratio:.2f} · 가장 느린 조각 {max(sums):.0f}초\n"
            f"장부에 없는 파일 {len(missing)}{(' ' + str(missing[:5])) if missing else ''}")


def selftest() -> int:
    fs = [f"tests/test_{c}.py" for c in "abcdef"]
    sec = {"test_a.py": 10, "test_b.py": 9, "test_c.py": 5, "test_d.py": 5, "test_e.py": 1, "test_f.py": 1}
    b = split(fs, sec, 2)
    ok = sorted(sum(sec[Path(f).name] for f in x) for x in b) == [15, 16]            # 균형
    ok &= sorted(f for x in b for f in x) == sorted(fs)                              # 빠짐 · 겹침 없다
    ok &= split(fs, sec, 2) == b                                                     # 결정적
    ok &= any("tests/test_new.py" in x for x in split(fs + ["tests/test_new.py"], sec, 2))   # 장부에 없는 새 파일도 든다
    print("✓ 프로브가 산다" if ok else "✗ 프로브가 죽었다")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="contract-tests 조각을 실측 시간으로 가른다")
    ap.add_argument("--part", type=int)
    ap.add_argument("--of", type=int, default=4)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    files, sec = test_files(), load_seconds()
    if a.report:
        print(report(files, sec, a.of))
        return 0
    if not a.part or not 1 <= a.part <= a.of:
        print(f"✗ --part 는 1..{a.of} 여야 한다", file=sys.stderr)
        return 2
    print("\n".join(split(files, sec, a.of)[a.part - 1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
