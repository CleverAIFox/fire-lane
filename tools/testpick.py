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

★ **훅 줄의 워커는 6 이다**(PLAN #214 · DECISIONS §679). 코어 8 에 게이트 24 가 동시에 뜨는데 묶음이 8워커로 코어를 채우면 단일 스레드 `deadcheck`(단독 약 11초)가 몫을 못 얻고
  훅 안에서 24~30초에 끝났다. 훅 전체 벽시계가 5회 중앙 29.5초(최대 32.3)에서 24.8초(최대 26.6)로 줄었다. 고르는 파일은 같다 — `eff = min(jobs, EFF)` 라 6 · 8 이 같은 집합이다.

★ **바뀐 파일에 닿는 시험은 예산과 무관하게 든다**(PLAN #218). 실측으로 고른 묶음은 **정렬**일 뿐 입력(무엇이 바뀌었나)을 몰랐다 —
  문서만 고친 날에도 같은 묶음이 돌고, 고친 문서를 읽는 시험이 짧은 순 밖이면 안 돌았다. 그래서 예산으로 고른 묶음에 **더한다**:
    · 바뀐 파일 = 푸시하는 커밋 범위(`--range` 로 주면 그것, 안 주면 `@{u}..HEAD`) ∪ 작업 트리의 추적 파일 변경.
      범위를 못 읽으면(원격 객체가 없다 등) `@{u}..HEAD`, 그것도 없으면 `origin/dev` 와의 merge-base 부터다. 못 읽으면 닫힌 쪽이 아니라 **「범위를 못 읽었다」를 출력에 적는다**.
    · 「그 파일에 닿는 시험」 = **정적 스캔**(`touching` · 순수 함수): 시험 파일 본문에 ① 그 경로 전체 ② 확장자 붙은 파일명(`PLAN.md`) ③ `.py` 면 import 한 모듈 이름이 나오는가.
      ★ **하한이다** — 경로를 헬퍼 · 상수 · 글롭으로 조립해 읽는 시험은 못 센다(그 시험은 안 든다). 못 센 것이 「닿지 않는다」는 뜻이 아니다.
    · **실측이 정적 스캔을 보탠다**(PLAN #218 ②): `--measure-reads` 가 시험 파일마다 프로세스를 따로 돌며 파이썬 감사 훅(`tests/audit_site/fsaudit.py` — 쓰기를 보는 `#219` 와 **같은 훅**)이
      **실제로 연 추적 파일**을 적는다(`data/golden/testreads.json`). 헬퍼 · 글롭 · 조립한 경로로 읽는 시험도 열면 잡히고 자식 프로세스의 읽기도 잡힌다.
      `touching` 은 **정적 ∪ 실측**이다. ★ 그래도 **장부가 낡으면 하한이다** — 시험이 새 파일을 읽게 바뀐 뒤 다시 안 쟀으면 그 읽기는 없다.
      **낡음은 도구가 말한다**(`reads_stale` — `testtimes` 의 「장부에 없음」 수법 + 잰 때의 시험 본문 지문): 새 시험은 **정적 스캔만**, 바뀐 시험은 **옛 실측 ∪ 정적 스캔**으로 떨어지고
      그 사실과 개수를 출력이 적는다(조용히 하한으로 돌아가지 않는다). **배경 목록은 장부 파일이 든다**(`ambient` 키 — 코드에 안 박는다 · 시험이 장부의 실측과 맞는지 문다).
    · **훅은 이 연동을 끈다**(`--no-touched` · 30초를 지킨다), **`pushready` ㉥ 는 상한 없이 전부 든다**(`--no-cap`) — 같은 `select` 하나를 쓰고 갈리는 것은 인자뿐이다(#216).
    · **파일당 상한**(`TOUCH_CAP` 초 · 장부 기준 · `--no-cap` 이 아니면)을 넘는 시험은 못 든다 — **출력에 이름을 대고 「CI 몫」으로 적는다**(조용히 빼지 않는다).
  `--files` 로 바뀐 파일을 직접 줄 수 있다(실측 · 시험용).

부류  조사   `--measure` 는 사람이 손으로 돌린다. `--list` · `--run` 은 읽기 전용이다(장부도 안 쓴다)
IN    `tests/test_*.py` 의 목록 · `data/golden/testtimes.json` · `--measure` 는 pytest `--durations=0` 의 파일별 합(setup+call+teardown)
OUT   화면 · 종료 코드(`--run`: 빨간 파일이 있으면 1). `--measure --write` 만 장부 한 파일을 쓴다
밖    **`web/navi/test/*` (vitest)는 고르지 않는다 — pytest 만 본다**(DECISIONS §719). 읽기 장부는 파이썬 감사 훅이 잰 것이라 node 의 읽기를 못 본다.
      그래서 재잠금이 `web/data` · `data/golden` 의 수를 움직여도 vitest 의 `astarbench` 둘이 **CI 에서야** 빨갰다. 그물은 여기가 아니라 `pushready` ㉨ 의 `ready` 층이다
      (`gatefast.LAYERS` 의 `navi:test` — 푸시 전에 전수 12.8초). 할 수는 있다: `npx vitest related <바뀐 파일>` 이 모듈 그래프로 고른다(정적 import 만 따르는데 vitest 는 `fs` 읽기가 0 이라 정확하다).
      안 한 것: 훅 예산(30초)에 node 를 넣으면 경합하고, 전수가 ㉨ 에서 돌아 선택이 중복이다.
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
READS_LEDGER = ROOT / "data" / "golden" / "testreads.json"     # 시험 파일 → 실행 중 **실제로 연** 추적 파일들(`--measure-reads --write` 가 쓴다 · PLAN #218)
DEFAULT_BUDGET = 28.0     # 초 — **훅 전체의 벽시계**(아래 ★ 조건) 30초에서 여유 2초를 뺀 값
STARTUP = 6.5            # 초 — 단독 실행의 고정 비용(통 시작 · 수집 · 마무리). 실측: 묶음 크기를 바꿔 잰 세 점의 절편
EFF = 5.0                # 실효 병렬 수 — 코어 8개여도 통의 꼬리 · 입출력 · 수집이 겹쳐 **단독으로 4.7~5.3** 이다(실측)
LOAD = 60.0              # CPU-초 — **같은 훅 안의 다른 게이트들이 쓰는 몫**. 훅 36.3초 − 단독 24.4초 = 11.9초 × EFF 에서 역산(`--load`)
TOUCH_CAP = 40.0         # 초 — 바뀐 파일에 닿는 시험 하나의 상한(장부 초 · 8병렬 경합이 낀 값이라 단독의 약 3배). 넘으면 CI 몫이다(PLAN #218)
PROC_TIMEOUT = 900        # 시한 없는 기다림은 빨강을 무한 대기로 바꾼다. 파일 하나의 상한(pytest 자체 시한은 시험당 300초)
# ★ **재는 쪽만 시한이 다르다**(PLAN #214 재고 · 2026-11-11). `--measure` 는 **시험이 아니라 재는 것**이다 — 시험의 300초 시한은
#   「이 시험이 멈췄는가」를 가리는 문턱이고, 재는 쪽은 「얼마나 걸리나」를 적는다. 장부 값이 이미 그 문턱에 붙은 시험(`test_fix_door` 304 ·
#   `test_ratchet` 296 — 병렬 8 경합이 낀 값)은 부하가 조금만 늘어도 문턱을 넘어 재는 일 자체가 거부됐다(연속 두 번). 시한에 걸려 죽은 시험은
#   **초를 못 적고 빨강으로 장부 쓰기를 막는다** — 그러면 장부가 영영 낡는다. 그래서 재는 길에서만 시험당 시한을 늘린다.
#   **평소 시험의 300초(pyproject)와 `--run` 의 시한은 그대로다** — 시험을 느슨하게 한 것이 아니다. 늘려도 **초는 그대로 장부에 적힌다**
#   (느려진 시험이 감춰지지 않는다 — 오히려 시한에 막혀 안 보이던 값이 보인다).
MEASURE_TEST_TIMEOUT = 1200   # 초 — 재는 길의 시험당 시한
MEASURE_PROC_TIMEOUT = 2400   # 초 — 재는 길의 통 하나 상한


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


def _git(args: list[str], root: Path) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def changed_files(root: Path = ROOT, ranges: list[str] | None = None) -> tuple[list[str], list[str]]:
    """(바뀐 추적 파일, 설명). 기준 = 푸시하는 커밋 범위 ∪ 작업 트리. 범위를 못 읽으면 `@{u}..HEAD` → `origin/dev` merge-base.

    범위를 직접 주지 않으면 `@{u}` 가 기준이라 새 브랜치 · 다른 refspec 에서는 틀릴 수 있다 — 그때는 출력에 그렇게 적힌다."""
    notes: list[str] = []
    out: set[str] = set()
    ok = 0
    for rg in ranges or []:
        d = _git(["diff", "--name-only", "--no-renames", rg], root)
        if d is None:
            notes.append(f"범위 {rg} 를 못 읽었다")
        else:
            ok += 1
            out.update(d.split())
    if not ok:
        for rg in ("@{u}..HEAD", None):
            if rg is None:
                mb = _git(["merge-base", "HEAD", "origin/dev"], root)
                rg = f"{mb.strip()}..HEAD" if mb and mb.strip() else None
            d = _git(["diff", "--name-only", "--no-renames", rg], root) if rg else None
            if d is not None:
                out.update(d.split())
                ok += 1
                notes.append(f"범위 {rg}")
                break
        if not ok:
            notes.append("커밋 범위를 못 읽었다(@{u} · origin/dev 둘 다 없다) — 작업 트리 변경만 본다")
    wt = _git(["diff", "--name-only", "--no-renames", "HEAD"], root)
    if wt:
        out.update(wt.split())
    return sorted(out), notes


def _mentions(text: str, path: str) -> bool:
    """시험 본문이 `path` 를 가리키는가 — ① 경로 전체 ② 확장자 붙은 파일명 ③ `.py` 면 import 한 모듈 이름. **하한**이다."""
    if re.search(r"(?<![\w.-])" + re.escape(path) + r"(?![\w-])", text):
        return True
    base = path.rsplit("/", 1)[-1]
    if "." in base and re.search(r"(?<![\w.-])" + re.escape(base) + r"(?![\w-])", text):
        return True
    if base.endswith(".py"):
        stem = base[:-3]
        if stem == "__init__":
            return False
        pat = re.compile(r"^\s*(?:from|import)\s+[\w.]*\b" + re.escape(stem) + r"\b", re.M)
        return bool(pat.search(text)) or f"-m firelane.{stem}" in text
    return False


def touching(changed: list[str], texts: dict[str, str], reads: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """순수 함수 — 시험 파일 이름 → 그 시험이 닿는 바뀐 파일들(**정적 스캔 ∪ 실측 읽기**). 닿는 것이 없으면 키가 없다.

    ★ 정적 스캔은 하한이다 — 헬퍼 · 글롭 · 조립한 경로로 읽는 시험은 못 센다. `reads`(실측 장부)가 그것을 메운다 — 장부에 있는 시험만.
    바뀐 시험 파일은 그 자신에 닿는다. 남의 시험 파일(`tests/test_*`)이 바뀐 것은 그 시험을 읽는 시험에 닿지 않는다."""
    out: dict[str, list[str]] = {}
    for name, text in texts.items():
        ran = set((reads or {}).get(name, ()))
        hit = [c for c in changed if c == f"tests/{name}" or (c != f"tests/{name}" and not c.startswith("tests/test_") and (_mentions(text, c) or c in ran))]
        if hit:
            out[name] = hit
    return out


AMBIENT_SHARE = 0.9      # 시험 파일의 이 비율 이상이 읽는 추적 파일은 **배경**이다 — conftest 가 import 하는 인프라(`firelane.paths` · `sources.yaml` 등)라 모든 시험이 읽는다


def ambient(reads: dict[str, list[str]], share: float = AMBIENT_SHARE) -> list[str]:
    """거의 모든 시험이 읽는 파일 — 순수 함수. 이것을 닿음으로 세면 아무 파일이나 바꿔도 전수가 돈다(그 변경은 어느 시험을 고르는 신호가 못 된다)."""
    if not reads:
        return []
    count: dict[str, int] = {}
    for v in reads.values():
        for p in set(v):
            count[p] = count.get(p, 0) + 1
    return sorted(p for p, k in count.items() if k >= share * len(reads))


def _read_reads_file(path: Path | None = None) -> dict:
    try:
        d = json.loads((READS_LEDGER if path is None else path).read_text(encoding="utf-8"))
        return d if isinstance(d.get("reads"), dict) else {}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def ledger_ambient(path: Path | None = None) -> list[str]:
    """장부 **파일에 적힌** 배경 목록(`--measure-reads --write` 가 적는다) — 코드에 박지 않는다. 시험이 이 목록이 장부의 실측과 맞는지 문다."""
    return list(_read_reads_file(path).get("ambient", []))


def load_reads(path: Path | None = None, drop_ambient: bool = True) -> dict[str, list[str]]:
    """실측 읽기 장부. 없거나 깨졌으면 빈 장부(= 정적 스캔만). **배경 파일은 뺀다** — 장부 파일이 적은 목록(`ledger_ambient`)이다."""
    d = _read_reads_file(path)
    out = {k: list(v) for k, v in d.get("reads", {}).items()}
    if drop_ambient:
        amb = set(d.get("ambient", [])) if "ambient" in d else set(ambient(out))
        out = {k: [p for p in v if p not in amb] for k, v in out.items()}
    return out


def test_hash(name: str, root: Path = ROOT) -> str:
    """시험 파일의 지문 — 읽기 장부가 **어느 본문을 재고 적었나**. 본문이 바뀌면 그 장부 칸은 낡았다."""
    import hashlib
    return hashlib.sha1((root / "tests" / name).read_bytes(), usedforsecurity=False).hexdigest()[:16]    # 보안이 아니라 **지문**이다 — 같은 값이라 읽기 장부가 안 낡는다


def reads_stale(files: list[str], path: Path | None = None, root: Path = ROOT) -> tuple[list[str], list[str], list[str]]:
    """(새 시험 · 바뀐 시험 · 없어진 시험) — `testtimes` 가 「장부에 없음 · 없어진 파일」을 말하는 수법에 **본문 지문**을 더했다.

    새 시험 = 장부에 칸이 없다 · 바뀐 시험 = 장부가 잰 뒤로 본문이 달라졌다(지문 불일치 · 지문이 안 적힌 옛 칸도 낡은 것이다)."""
    d = _read_reads_file(path)
    reads, hashes = d.get("reads", {}), d.get("hashes", {})
    new = sorted(n for n in files if n not in reads)
    changed = sorted(n for n in files if n in reads and hashes.get(n) != test_hash(n, root))
    gone = sorted(n for n in reads if n not in files)
    return new, changed, gone


def pick_touched(touch: dict[str, list[str]], ledger: dict[str, float], cap: float = TOUCH_CAP) -> tuple[list[str], dict[str, float]]:
    """순수 함수 — (드는 것, 상한에 걸려 못 드는 것 → 장부 초). 장부에 없는 시험은 무조건 든다."""
    go = sorted(n for n in touch if ledger.get(n, 0.0) <= cap)
    over = {n: ledger[n] for n in sorted(touch) if ledger.get(n, 0.0) > cap}
    return go, over


def select(files: list[str], ledger: dict[str, float], texts: dict[str, str], changed: list[str], budget: float, jobs: int,
           load: float = 0.0, touched: bool = True, cap: float | None = TOUCH_CAP, reads: dict[str, list[str]] | None = None) -> tuple[list[str], dict]:
    """**하나뿐인 선택 함수**(PLAN #218 · #216) — 훅도 `pushready` 도 이것을 부른다. 갈리는 것은 인자뿐이다:
    `touched`(바뀐 파일에 닿는 시험을 더하나) · `cap`(닿는 시험 하나의 상한 · `None` 이면 상한 없음) · `budget`/`load`(예산으로 고르는 몫).
    훅은 `touched=False`(30초를 지킨다), `pushready` 는 `touched=True, cap=None`(시간 제약이 없다)이다. 두 도구가 다른 규칙을 쓰면 그것이 #216 의 재발이다."""
    chosen, info = pick(files, ledger, budget, jobs, load=load)
    info.update({"touch": {}, "forced": [], "over": {}})
    if touched:
        touch = touching(changed, texts, reads)
        go, over = pick_touched(touch, ledger, float("inf") if cap is None else cap)
        info.update(touch=touch, forced=[n for n in go if n not in chosen], over=over)
        chosen = sorted({*chosen, *go})
        info["est"] += sum(ledger.get(n, 0.0) for n in info["forced"]) / min(jobs, EFF)
    return chosen, info


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


def run_bin(names: list[str], root: Path = ROOT, measuring: bool = False) -> tuple[int, str, dict[str, float], set[str]]:
    """한 pytest 프로세스에 파일 여럿 — 시작 비용을 나눈다. (rc, 출력, 파일별 초(setup+call+teardown), 빨간 파일)

    `measuring` 이면 시험당 시한과 통 상한만 늘린다(머리의 ★ — 재는 것이지 시험이 아니다). 아니면 pyproject 의 300초 그대로다."""
    extra = ["-o", f"timeout={MEASURE_TEST_TIMEOUT}"] if measuring else []
    limit = MEASURE_PROC_TIMEOUT if measuring else PROC_TIMEOUT
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", *[f"tests/{n}" for n in names], "-q", "-p", "no:cacheprovider",
                            "--no-header", "-o", "addopts=", *extra, "--durations=0", "--durations-min=0", "-rfE"],
                           cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=limit, stdin=subprocess.DEVNULL)
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"시한 {limit}초 초과", {}, set(names)
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


def run_reads(name: str, root: Path = ROOT, out_dir: Path | None = None) -> tuple[int, str, list[str]]:
    """시험 파일 **하나를 자기 프로세스에서** 돌려 그 시험이 연 추적 파일을 얻는다. (rc, 출력 꼬리, 읽은 파일들)

    ★ 파일마다 프로세스가 따로여야 한다 — 이미 import 된 모듈은 다시 안 읽혀서 한 프로세스에 여럿이면 뒤 파일의 읽기가 샌다(`fsaudit` 머리말).
    ★ 훅은 `tests/tracked_guard.py` 의 세션 훅이 켠다. 이 길은 `--fl-reads-out` 인자만 더한다(환경변수가 아니다 — `env_check`) — 시험을 느슨하게 하지 않는다."""
    import tempfile
    d = out_dir or Path(tempfile.mkdtemp(prefix="fl-reads-"))
    dest = d / f"{name}.json"
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", f"tests/{name}", "-q", "-p", "no:cacheprovider", "--no-header", "-o", "addopts=",
                            "-o", f"timeout={MEASURE_TEST_TIMEOUT}", "-rfE", "--fl-reads-out", str(dest)],
                           cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=MEASURE_PROC_TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, f"시한 {MEASURE_PROC_TIMEOUT}초 초과", []
    out = (r.stdout or "") + (r.stderr or "")
    try:
        got = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return (r.returncode if r.returncode not in (0, 5) else 1), out[-800:], []
    reads = sorted({p for k, v in got.items() if k == name for p in v if p != f"tests/{name}"})
    return (0 if r.returncode in (0, 5) else r.returncode), out[-800:], reads


def run_all(names: list[str], jobs: int, ledger: dict[str, float], root: Path = ROOT, measuring: bool = False) -> tuple[dict[str, float], dict[str, str]]:
    """(파일별 초, 빨간 파일 → 그 파일이 든 통의 출력 꼬리)"""
    groups = bins(names, jobs, ledger)
    with ThreadPoolExecutor(max_workers=len(groups) or 1) as ex:
        results = list(ex.map(lambda g: run_bin(g, root, measuring), groups))
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
    g.add_argument("--measure-reads", action="store_true", help="시험 파일마다 따로 돌며 **실제로 연 추적 파일**을 잰다(PLAN #218 · 감사 훅 · 느리다 · 사람이 가끔)")
    g.add_argument("--list", action="store_true", help="고른 묶음을 낸다")
    g.add_argument("--run", action="store_true", help="고른 묶음을 병렬로 돌린다")
    ap.add_argument("--write", action="store_true", help="--measure 결과를 장부에 쓴다")
    ap.add_argument("--only", nargs="+", metavar="FILE", help="--measure 가 이 파일들만 다시 잰다(나머지 장부 칸은 그대로 — 고친 시험 하나를 11분 안 들이고 갱신)")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET, help="벽시계 예산(초)")
    ap.add_argument("--load", type=float, default=0.0, help=f"같은 시간에 도는 남의 일(CPU-초). 훅 안에서는 {LOAD:g}")
    ap.add_argument("--range", action="append", metavar="A..B", help="바뀐 파일의 커밋 범위(여럿 가능). 안 주면 @{u}..HEAD")
    ap.add_argument("--files", nargs="+", metavar="PATH", help="바뀐 파일을 직접 준다(실측 · 시험용 — git 을 안 본다)")
    ap.add_argument("--no-touched", action="store_true", help="바뀐 파일에 닿는 시험을 안 더한다(예전 동작 — 실측 대조용)")
    ap.add_argument("--cap", type=float, default=TOUCH_CAP, help="닿는 시험 하나의 상한(장부 초). 넘으면 CI 몫")
    ap.add_argument("--no-reads", action="store_true", help="실측 읽기 장부를 안 쓴다(정적 스캔만 — 대조용)")
    ap.add_argument("--no-cap", action="store_true", help="상한을 안 건다 — 닿는 시험을 전부 든다(시간 제약이 없는 pushready)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args(argv)
    files = test_files()

    if a.measure_reads:
        names = sorted(a.only) if a.only else files
        unknown = [n for n in names if n not in files]
        if unknown:
            print(f"✗ 없는 시험 파일: {', '.join(unknown)}", file=sys.stderr)
            return 1
        t = time.monotonic()
        with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
            results = list(ex.map(lambda n: (n, *run_reads(n)), names))
        red = {n: tail for n, rc, tail, _ in results if rc != 0}
        reads = {n: r for n, rc, _, r in results if rc == 0}
        for n, o in sorted(red.items()):
            print(f"  ✗ {n}\n" + "\n".join("      " + x for x in o.splitlines()[-6:]), file=sys.stderr)
        print(f"{len(reads)}/{len(names)}개 파일 · 읽은 추적 파일 합 {sum(map(len, reads.values()))}개 · 벽시계 {time.monotonic() - t:.0f}초 (병렬 {a.jobs}) · 빨강 {len(red)}")
        if a.write and red:
            print("✗ 빨간 파일이 있어 읽기 장부를 안 썼다 — 빨강을 고치거나 흔들림인지 가린 뒤 다시 잰다", file=sys.stderr)
            return 1
        if a.write:
            old = _read_reads_file()
            hashes = {n: test_hash(n) for n in reads}
            if a.only:      # 일부만 쟀다 — 나머지 칸은 그대로 두고 잰 칸만 덮는다(없어진 파일은 버린다)
                reads = {**{k: v for k, v in old.get("reads", {}).items() if k in files}, **reads}
                hashes = {**{k: v for k, v in old.get("hashes", {}).items() if k in files}, **hashes}
            READS_LEDGER.write_text(json.dumps({"_": "tools/testpick.py --measure-reads --write 가 쓴다. 손으로 고치지 않는다. 시험 파일 → 실행 중 연 추적 파일(감사 훅) · hashes = 잰 때의 시험 본문 지문(낡음 판정) · ambient = 거의 모든 시험이 읽어 닿음으로 안 세는 배경 파일.",
                                                "ambient": ambient(reads), "hashes": dict(sorted(hashes.items())),
                                                "reads": dict(sorted(reads.items()))}, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
            print(f"읽기 장부 {READS_LEDGER} 를 썼다")
        return 1 if red else 0

    if a.measure:
        t = time.monotonic()
        if a.only:
            unknown = [n for n in a.only if n not in files]
            if unknown:
                print(f"✗ 없는 시험 파일: {', '.join(unknown)}", file=sys.stderr)
                return 1
            files = sorted(a.only)
        secs, red = run_all(files, a.jobs, load_ledger(), measuring=True)
        secs = {n: round(s, 2) for n, s in secs.items()}
        for n, o in sorted(red.items()):
            print(f"  ✗ {n}\n" + "\n".join("      " + x for x in o.splitlines()[-6:]), file=sys.stderr)
        top = sorted(secs.items(), key=lambda kv: -kv[1])
        print(f"{len(secs)}/{len(files)}개 파일 · 합 {sum(secs.values()):.0f}초 · 벽시계 {time.monotonic() - t:.0f}초 (병렬 {a.jobs}) · 빨강 {len(red)}")
        print(f"  상위 25 합 {sum(s for _, s in top[:25]):.0f}초 · 나머지 합 {sum(s for _, s in top[25:]):.0f}초")
        if a.write and red:
            print("✗ 빨간 파일이 있어 장부를 안 썼다 — 빨강을 고치거나 흔들림인지 가린 뒤 다시 잰다", file=sys.stderr)
            return 1
        if a.write:
            # 장부에 못 적힌 파일(죽은 통 · 시한)은 「새 시험」이라 무조건 묶음에 든다(닫힌 쪽). 빨강이 있으면 위에서 이미 막았다.
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
    texts: dict[str, str] = {}
    changed: list[str] = []
    notes: list[str] = []
    if not a.no_touched:
        if a.files is not None:
            changed, notes = sorted(a.files), ["--files 로 받았다"]
        else:
            changed, notes = changed_files(ROOT, a.range or [])
        texts = {n: (ROOT / "tests" / n).read_text(encoding="utf-8", errors="replace") for n in files}
    cap = None if a.no_cap else a.cap
    reads = {} if a.no_reads else load_reads()
    chosen, info = select(files, ledger, texts, changed, a.budget, a.jobs, a.load, touched=not a.no_touched, cap=cap, reads=reads)
    print(f"묶음 {len(chosen)}/{len(files)}개 파일 · 추정 {info['est']:.1f}초(예산 {a.budget:g}초 · 병렬 {a.jobs} · 남의 일 {a.load:g}) · "
          f"장부 {info['known']}개 합 {info['total']:.0f}초", file=sys.stderr)
    if info["new"]:
        print(f"  장부에 없음(새 시험 · 무조건 든다) {len(info['new'])}개: {', '.join(info['new'][:5])}"
              f"{' …' if len(info['new']) > 5 else ''}  → `--measure --write`", file=sys.stderr)
    if info["gone"]:
        print(f"  장부에만 있음(없어진 파일) {len(info['gone'])}개 → `--measure --write`", file=sys.stderr)
    if not a.no_touched:
        print(f"  바뀐 파일 {len(changed)}개({'; '.join(notes)}) → 닿는 시험 {len(info['touch'])}개 · 예산 밖에서 더함 {len(info['forced'])}개 "
              f"(정적 스캔 ∪ 실측 읽기 {sum(1 for n in files if n in reads)}/{len(files)}개 파일 — 장부에 없거나 낡은 시험은 **하한**)", file=sys.stderr)
        if not a.no_reads:
            new_r, chg_r, gone_r = reads_stale(files)
            if new_r or chg_r or gone_r:
                print(f"  ⚠ 읽기 장부가 낡았다 — 새 시험 {len(new_r)} · 바뀐 시험 {len(chg_r)} · 없어진 시험 {len(gone_r)}: "
                      f"{', '.join((new_r + chg_r + gone_r)[:4])}{' …' if len(new_r + chg_r + gone_r) > 4 else ''}", file=sys.stderr)
                if new_r:
                    print(f"    → 새 시험 {len(new_r)}개는 **정적 스캔만**으로 닿음을 센다(하한 — 헬퍼 · 글롭으로 읽는 파일은 못 센다)", file=sys.stderr)
                if chg_r:
                    print(f"    → 바뀐 시험 {len(chg_r)}개는 **옛 실측 ∪ 정적 스캔**이다(본문이 바뀐 뒤 새로 읽게 된 파일은 못 센다)", file=sys.stderr)
                print("    → `uv run python tools/testpick.py --measure-reads --write --only <파일…>` 로 다시 잰다", file=sys.stderr)
        if reads:
            print(f"  배경으로 뺀 파일 {len(ledger_ambient() or ambient(load_reads(drop_ambient=False)))}개(시험 {AMBIENT_SHARE:.0%} 이상이 읽는다 — conftest 인프라): 실측으로는 안 센다", file=sys.stderr)
        for n, sec in info["over"].items():
            t3 = info["touch"][n]
            print(f"  ⚠ CI 몫 — {n} ({sec:.0f}초 > 상한 {a.cap:g}초): {', '.join(t3[:3])}{' …' if len(t3) > 3 else ''} 에 닿지만 못 돈다", file=sys.stderr)
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
