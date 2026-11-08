#!/usr/bin/env python3
"""
testpick.py — 푸시 전에 도는 시험 묶음을 **실측으로** 고른다.  (PLAN #209)

    uv run python tools/testpick.py --measure [--write]     전수를 통으로 나눠 병렬로 돌며 `--durations=0` 으로 파일별 초를 잰다(느리다 · 사람이 가끔)
    uv run python tools/testpick.py --list   [--budget 20]  예산 안에 드는 묶음을 낸다(읽기 전용)
    uv run python tools/testpick.py --run    [--budget 20]  그 묶음을 병렬로 돌린다(pre-push · pushready 가 부른다)

── 왜 있나 ────────────────────────────────────────────────────
2026-11-08. `pushready`(#207)가 다섯 축으로 초록을 냈는데 CI 가 `test_layering` 2건으로 죽었다. 같은 사고에서
`test_no_unbounded_waits` · `test_sizecheck` 도 pre-push · pushready 를 통과했다. **구조 규약을 무는 시험이 어느 관문에도
없었다.** 전수 1,526초 중 상위 25개 파일이 1,374초이고 나머지 전부가 약 152초다 — `test_layering.py` 는 2초다.

★ **손으로 목록을 들지 않는다.** 손 목록은 기운다(DECISIONS §633-3 의 핀이 그래서 기울었다). 입력은 **실측 장부** 하나
  (`data/golden/testtimes.json` — `--measure --write` 가 쓴다)이고, 묶음은 거기서 **계산한다:**
    · 파일을 짧은 순으로 세워 `시작 비용 + (남의 일 + 합) ÷ 실효 병렬 ≤ 예산` 이 되는 데까지 든다 — 짧은 시험이 늘면 묶음이 저절로 커진다.
    · **장부에 없는 파일(새 시험)은 무조건 든다** — 새 시험이 새 규약을 문다. 비용은 장부 중앙값으로 친다.
    · 파일 하나가 예산보다 길면 못 든다(그 파일은 CI 몫이다).
  시험이 늘어도 사람이 목록을 안 든다. 장부가 낡으면(`--list` 가 「장부에 없음」 · 「없어진 파일」 을 적는다) `--measure --write`.

★ **예산 30초는 어느 조건의 30초인가** (PLAN #210 ㉡ · 2026-11-08 실측) — **`pre-push` 훅 전체의 벽시계, 모든 게이트가 동시에, 8코어 조용한 기계.**
  사람이 기다리는 시간이 그것이기 때문이다. 단독으로 재면 거짓이다: 시험 묶음은 단독 24.4초인데 같은 훅 안의 22게이트와 코어를 다퉈 36~37초였고
  (게이트만 14.7초), 그 차 약 12초는 게이트들이 쓰는 CPU 약 60초(`LOAD`)다. 그래서 훅에 거는 줄은 `--budget 28 --load 60`, 훅 밖(pushready)은 `--load 0`.
  ★ **그 조건에서 훅에 드는 묶음은 `test_layering`(장부 2.3초 · 짧은 순 187번째)을 못 품는다** — 품으려면 훅이 약 38초다. 훅은 예산 안의 짧은 쪽을,
  pushready 가 더 큰 쪽(`--budget 30 --load 0`)을 돈다.

부류  조사   `--measure` 는 사람이 손으로 돌린다. `--list` · `--run` 은 읽기 전용이다(장부도 안 쓴다)
IN    `tests/test_*.py` 의 목록 · `data/golden/testtimes.json` · `--measure` 는 pytest `--durations=0` 의 파일별 합(setup+call+teardown)
OUT   화면 · 종료 코드(`--run`: 빨간 파일이 있으면 1). `--measure --write` 만 장부 한 파일을 쓴다
밖    **어떤 시험이 어떤 규약을 무는지는 모른다** — 오직 초만 본다. 예산을 넘는 파일은 이 묶음이 안 돌고 CI 가 돈다.
      파일 **안**의 시험 하나하나는 안 고른다(파일이 단위다). 장부의 초는 기계마다 다르다 — 절대값이 아니라 **순서**로 쓰인다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "golden" / "testtimes.json"
DEFAULT_BUDGET = 28.0     # 초 — **훅 전체의 벽시계**(아래 ★ 조건) 30초에서 여유 2초를 뺀 값
STARTUP = 6.5            # 초 — 단독 실행의 고정 비용(통 시작 · 수집 · 마무리). 실측: 묶음 크기를 바꿔 잰 세 점의 절편
EFF = 5.0                # 실효 병렬 수 — 코어 8개여도 통의 꼬리 · 입출력 · 수집이 겹쳐 **단독으로 4.7~5.3** 이다(실측)
LOAD = 60.0              # CPU-초 — **같은 훅 안의 다른 게이트들이 쓰는 몫**. 훅 36.3초 − 단독 24.4초 = 11.9초 × EFF 에서 역산(`--load`)
PROC_TIMEOUT = 900        # 시한 없는 기다림은 빨강을 무한 대기로 바꾼다. 파일 하나의 상한(pytest 자체 시한은 시험당 300초)


def test_files(root: Path = ROOT) -> list[str]:
    return sorted(p.name for p in (root / "tests").glob("test_*.py"))


def load_ledger(path: Path | None = None) -> dict[str, float]:
    try:
        return {k: float(v) for k, v in json.loads((path or LEDGER).read_text(encoding="utf-8")).get("seconds", {}).items()}
    except (OSError, ValueError):
        return {}


def pick(files: list[str], ledger: dict[str, float], budget: float, jobs: int, startup: float = STARTUP,
         load: float = 0.0) -> tuple[list[str], dict]:
    """순수 함수 — (고른 파일, 설명). 같은 입력이면 같은 묶음이다.

    비용 모형: `startup + (load + 합) ÷ min(jobs, EFF)`. `load` 는 같은 시간에 도는 **남의 일**(훅 안의 다른 게이트)의 CPU-초다.
    가장 긴 파일 하나는 병렬로도 못 줄이므로 그 파일 하나가 예산을 넘기면 뺀다.
    """
    known = {f: ledger[f] for f in files if f in ledger}
    new = [f for f in files if f not in ledger]
    med = statistics.median(known.values()) if known else 0.0
    spent = med * len(new)
    eff = min(jobs, EFF)
    chosen = list(new)
    skipped = []
    for f, s in sorted(known.items(), key=lambda kv: (kv[1], kv[0])):
        if startup + s > budget or startup + (load + spent + s) / eff > budget:
            skipped.append(f)
            continue
        spent += s
        chosen.append(f)
    gone = sorted(set(ledger) - set(files))
    return sorted(chosen), {
        "new": sorted(new), "gone": gone, "skipped": skipped, "est": startup + (load + spent) / eff, "median": med,
        "total": sum(known.values()), "known": len(known),
    }


def bins(names: list[str], jobs: int, ledger: dict[str, float]) -> list[list[str]]:
    """가장 긴 것부터 가장 가벼운 통에 넣는다(LPT). 장부에 없는 파일은 중앙값으로 친다."""
    med = statistics.median(ledger.values()) if ledger else 1.0
    out: list[list[str]] = [[] for _ in range(max(1, min(jobs, len(names))))]
    load = [0.0] * len(out)
    for n in sorted(names, key=lambda n: (-ledger.get(n, med), n)):
        k = load.index(min(load))
        out[k].append(n)
        load[k] += ledger.get(n, med)
    return [b for b in out if b]


_DUR = re.compile(r"^\s*([0-9.]+)s (?:setup|call|teardown)\s+(tests/\S+?\.py)::")
_RED = re.compile(r"^(?:FAILED|ERROR) (tests/\S+?\.py)")


def run_bin(names: list[str], root: Path = ROOT) -> tuple[int, str, dict[str, float], set[str]]:
    """한 pytest 프로세스에 파일 여럿 — 시작 비용을 나눈다. (rc, 출력, 파일별 초(setup+call+teardown), 빨간 파일)"""
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", *[f"tests/{n}" for n in names], "-q", "-p", "no:cacheprovider",
                            "--no-header", "-o", "addopts=", "--durations=0", "--durations-min=0", "-rfE"],
                           cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=PROC_TIMEOUT, stdin=subprocess.DEVNULL)
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"시한 {PROC_TIMEOUT}초 초과", {}, set(names)
    secs: dict[str, float] = {}
    for ln in out.splitlines():
        m = _DUR.match(ln)
        if m:
            f = m.group(2).split("/", 1)[1]
            secs[f] = secs.get(f, 0.0) + float(m.group(1))
    red = {m.group(1).split("/", 1)[1] for ln in out.splitlines() if (m := _RED.match(ln))}
    if rc not in (0, 5) and not red:
        red = set(names)        # 죽은 이유를 못 읽었다 — 닫힌 쪽으로 전부 빨강이다
    return rc, out, secs, red


def run_all(names: list[str], jobs: int, ledger: dict[str, float], root: Path = ROOT) -> tuple[dict[str, float], dict[str, str]]:
    """(파일별 초, 빨간 파일 → 그 파일이 든 통의 출력 꼬리)"""
    groups = bins(names, jobs, ledger)
    with ThreadPoolExecutor(max_workers=len(groups) or 1) as ex:
        results = list(ex.map(lambda g: run_bin(g, root), groups))
    secs: dict[str, float] = {}
    red: dict[str, str] = {}
    for _rc, out, sec, rd in results:
        secs.update(sec)
        for f in rd:
            red[f] = "\n".join(x for x in out.splitlines() if "Error" in x or x.startswith(("FAILED", "ERROR", "E  ")))[-1500:] or out[-800:]
    return secs, red


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="testpick", description=__doc__.split("──")[0], formatter_class=argparse.RawTextHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--measure", action="store_true", help="모든 시험 파일을 돌려 파일별 초를 잰다(pytest --durations=0)")
    g.add_argument("--list", action="store_true", help="고른 묶음을 낸다")
    g.add_argument("--run", action="store_true", help="고른 묶음을 병렬로 돌린다")
    ap.add_argument("--write", action="store_true", help="--measure 결과를 장부에 쓴다")
    ap.add_argument("--only", nargs="+", metavar="FILE", help="--measure 가 이 파일들만 다시 잰다(나머지 장부 칸은 그대로 — 고친 시험 하나를 11분 안 들이고 갱신)")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET, help="벽시계 예산(초)")
    ap.add_argument("--load", type=float, default=0.0, help=f"같은 시간에 도는 남의 일(CPU-초). 훅 안에서는 {LOAD:g}")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args(argv)
    files = test_files()

    if a.measure:
        t = time.monotonic()
        if a.only:
            unknown = [n for n in a.only if n not in files]
            if unknown:
                print(f"✗ 없는 시험 파일: {', '.join(unknown)}", file=sys.stderr)
                return 1
            files = sorted(a.only)
        secs, red = run_all(files, a.jobs, load_ledger())
        secs = {n: round(s, 2) for n, s in secs.items()}
        for n, o in sorted(red.items()):
            print(f"  ✗ {n}\n" + "\n".join("      " + x for x in o.splitlines()[-6:]), file=sys.stderr)
        top = sorted(secs.items(), key=lambda kv: -kv[1])
        print(f"{len(secs)}/{len(files)}개 파일 · 합 {sum(secs.values()):.0f}초 · 벽시계 {time.monotonic() - t:.0f}초 (병렬 {a.jobs}) · 빨강 {len(red)}")
        print(f"  상위 25 합 {sum(s for _, s in top[:25]):.0f}초 · 나머지 합 {sum(s for _, s in top[25:]):.0f}초")
        if a.write:
            # 장부에 못 적힌 파일(죽은 통 · 시한)은 「새 시험」이라 무조건 묶음에 든다(닫힌 쪽). 빨간 파일의 초는 시험이 끝까지 돌았으니 적는다.
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            if a.only:      # 일부만 쟀다 — 나머지 칸은 그대로 두고 잰 칸만 덮는다(없어진 파일은 버린다)
                secs = {**{k: v for k, v in load_ledger().items() if k in test_files()}, **secs}
            LEDGER.write_text(json.dumps({"_": "tools/testpick.py --measure --write 가 쓴다. 손으로 고치지 않는다.",
                                          "seconds": dict(sorted(secs.items()))}, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")
            print(f"장부 {LEDGER} 를 썼다")
        return 1 if red else 0

    ledger = load_ledger()
    if not ledger:
        # ★ 장부가 비면 모든 파일이 「새 시험」이라 전부 든다 — 조용히 25분짜리 묶음이 된다. 닫힌 쪽으로 실패한다.
        print("✗ 장부가 없거나 비었다(data/golden/testtimes.json) — `tools/testpick.py --measure --write` 로 만든다", file=sys.stderr)
        return 1
    chosen, info = pick(files, ledger, a.budget, a.jobs, load=a.load)
    print(f"묶음 {len(chosen)}/{len(files)}개 파일 · 추정 {info['est']:.1f}초(예산 {a.budget:g}초 · 병렬 {a.jobs} · 남의 일 {a.load:g}) · "
          f"장부 {info['known']}개 합 {info['total']:.0f}초", file=sys.stderr)
    if info["new"]:
        print(f"  장부에 없음(새 시험 · 무조건 든다) {len(info['new'])}개: {', '.join(info['new'][:5])}"
              f"{' …' if len(info['new']) > 5 else ''}  → `--measure --write`", file=sys.stderr)
    if info["gone"]:
        print(f"  장부에만 있음(없어진 파일) {len(info['gone'])}개 → `--measure --write`", file=sys.stderr)
    if a.list:
        print("\n".join(chosen))
        return 0

    t = time.monotonic()
    secs, red = run_all(chosen, a.jobs, ledger)
    for n, s in sorted(secs.items()):
        if n in ledger and s > 3 * ledger[n] + 5:
            print(f"  ⚠ {n} 가 장부({ledger[n]:.1f}초)보다 훨씬 걸렸다({s:.1f}초) — 장부가 낡았다", file=sys.stderr)
    for n, o in sorted(red.items()):
        print(f"  ✗ {n}\n" + "\n".join("      " + x for x in o.splitlines()[-12:]), file=sys.stderr)
    print(f"{'✗' if red else '✓'} 시험 묶음 {len(chosen)}개 파일 · 빨강 {len(red)} · {time.monotonic() - t:.1f}초 (추정 {info['est']:.1f}초)")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
