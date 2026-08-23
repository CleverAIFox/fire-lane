#!/usr/bin/env python3
"""
tidy.py — 푸시·PR·머지 뒤에 남는 로컬 찌꺼기를 정리한다.

    uv run python tools/tidy.py            무엇이 지워질지만 (기본은 안 지운다)
    uv run python tools/tidy.py --yes      실제로 지운다
    uv run python tools/tidy.py --only git 브랜치·upstream 만
    uv run python tools/tidy.py --only fs  파일만

── 왜 만들었나 ────────────────────────────────────────────────
찌꺼기가 실제로 사고를 냈다. 셋 다 "조용히 틀린 것이 실행된" 사고다.

  2026-08-23  루트에 08-21 이전 판 `apply.sh` 가 남아 있었고, 새 스크립트를
              같은 이름으로 받자 `bash apply.sh` 가 **옛 것을 돌렸다.**
              `.gitignore` 의 `/*.sh` 는 커밋만 막지 디스크는 안 건드린다.
  2026-08-23  머지된 원격 브랜치가 지워졌는데 로컬 upstream 이 남아
              `git pull` 이 "no such ref was fetched" 로 실패했다.
  2026-08-18  `ingest` FAIL 로 격리된 `*.stale_*` 가 남아 진단을 흐렸다.

★ 데이터는 건드리지 않는다. `data/raw` · `data/norm` · `data/field` ·
  `web/data` 는 대상이 아니다. 재생성 가능한 것과 재생성 불가능한 것을
  이 도구가 판단하지 않는다 — 그 판단은 MASTER §18-1 이 이미 했고,
  여기서 다시 하면 정본이 둘이 된다.

★ `data/processed` 도 안 지운다. 재생성되지만 285초 걸리고, 무엇보다
  `segments.geojson` · `_manifest.json` · `seg_uid_map.csv` 는 커밋 대상이다.
  정리하려면 `fire-lane` 을 다시 돌리는 것이 옳은 방법이다.

IN    저장소 (git 필요)
OUT   없음 — 삭제만 한다. `--yes` 없이는 아무것도 지우지 않는다
PARAM 아래 RULES
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m", "c": "\033[36m",
     "d": "\033[90m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def human(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024
    return ""


def sh(*args: str) -> list[str] | None:
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        return None
    return [x for x in r.stdout.splitlines() if x.strip()]


# ── 파일 규칙 ──────────────────────────────────────────────────
# (이름, 글롭 목록, 왜 지워도 되는가)
#
# ★ 글롭은 저장소 루트 기준이다. 데이터 계층은 넣지 않는다.
RULES: list[tuple[str, list[str], str]] = [
    # ★ 2026-08-23. `fix-*.sh` 만 적어놨더니 여섯 개를 놓쳤다 —
    #   doc-audit · doc-nums · doc-update · diag-0xa0 · diag-0xa0b · wsl-tune.
    #   `ship.py` 가 "루트 .sh 전부" 로 세다가 발견했다.
    #   접두를 나열하면 또 놓친다. **루트의 .sh 는 전부 일회성으로 본다** —
    #   이름 있는 도구는 tools/ 에 둔다는 것이 R8 이다.
    ("일회성 패처", ["*.sh", "apply.py", "push.py"],
     "§18-5 R8 — 돌리고 지운다. 남아 있으면 `bash apply.sh` 가 옛 것을 돌린다"),
    ("적용 백업", ["_backup_*", "_apply_backup_*"],
     "apply 스크립트가 만든 원복용 사본. 커밋 확인 뒤에는 쓸 일이 없다"),
    ("격리 산출물", ["data/processed/*.stale_*"],
     "ingest FAIL 때 하류를 막으려고 개명한 것. 재실행하면 다시 생긴다"),
    ("파이프라인 임시", [".work"],
     "압축 해제·도엽 전개용. ngii1k 가 다시 만든다"),
    ("책상 대조 산출", ["data/desk"],
     "desk_check.py 가 만든 PNG. 언제든 다시 만든다"),
    ("인코딩 백업", ["**/*.bak_enc"],
     "encoding_check --fix 가 남긴 것"),
    ("파이썬 캐시", ["**/__pycache__", ".pytest_cache", ".ruff_cache",
                 "**/*.egg-info"],
     "전부 재생성된다"),
    ("노드 모듈", ["node_modules", "package-lock.json"],
     "jsdom 스모크용. `npm install --no-save jsdom` 로 다시 받는다"),
]

# ★ 여기 있는 것은 어떤 규칙에 걸려도 안 지운다. 마지막 안전장치다.
NEVER = ("data/raw", "data/norm", "data/field", "web/data",
         "data/processed/segments.geojson",
         "data/processed/segments.schema.json",
         "data/processed/_manifest.json",
         "data/processed/seg_uid_map.csv",
         "data/golden", "data/baseline", ".git",
         # ★ 2026-08-23. `.venv` 를 뺐다. `**/__pycache__` 가 그 안을 훑어
         #   site-packages 캐시 130여 건이 목록에 올라왔다. 셋 다 나쁘다.
         #     · uv 가 관리하는 영역이다. 남의 살림을 건드리는 셈이다
         #     · 지워도 첫 import 때 다시 생긴다 — **매번 같은 목록이 뜬다**
         #     · 진짜 찌꺼기(일회성 패처 12개 · 백업 7개)가 그 속에 묻힌다
         #   정리 도구가 매번 백 건을 보고하면 사람이 목록을 안 읽게 된다.
         ".venv", "venv", ".git")


def guarded(p: Path) -> bool:
    rel = p.relative_to(ROOT).as_posix()
    return any(rel == n or rel.startswith(n + "/") for n in NEVER)


def size_of(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def scan_fs() -> list[tuple[str, Path, int, str]]:
    out = []
    for name, globs, why in RULES:
        for g in globs:
            for p in sorted(ROOT.glob(g)):
                if guarded(p) or not p.exists():
                    continue
                out.append((name, p, size_of(p), why))
    return out


# ── git 규칙 ───────────────────────────────────────────────────
def scan_git() -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """(죽은 upstream, 머지된 로컬 브랜치, 사라진 원격 추적)."""
    gone, merged, stale_remote = [], [], []

    # 1. upstream 이 원격에서 사라진 로컬 브랜치
    #    ★ 2026-08-23. `refactor/package-and-web-modules` 가 머지되고 원격에서
    #      지워졌는데 로컬 설정이 그것을 가리켜 `git pull` 이 통째로 실패했다.
    #      "no such ref was fetched" 가 그 메시지다.
    for ln in sh("git", "for-each-ref", "--format=%(refname:short) %(upstream:short) %(upstream:track)",
                 "refs/heads") or []:
        parts = ln.split()
        if len(parts) >= 3 and "gone" in ln:
            gone.append((parts[0], parts[1]))

    # 2. 현재 브랜치에 이미 머지된 로컬 브랜치
    cur = (sh("git", "rev-parse", "--abbrev-ref", "HEAD") or ["?"])[0]
    for ln in sh("git", "branch", "--merged") or []:
        b = ln.replace("*", "").strip()
        if b and b != cur and b not in ("main", "master", "gis"):
            merged.append(b)

    # 3. 원격에서 사라진 추적 참조 (git remote prune 대상)
    for ln in sh("git", "remote", "prune", "--dry-run", "origin") or []:
        if "would prune" in ln:
            stale_remote.append(ln.split()[-1])

    return gone, merged, stale_remote


# ── 실행 ───────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="실제로 지운다")
    ap.add_argument("--only", choices=["git", "fs"], help="한쪽만")
    a = ap.parse_args()

    if not (ROOT / ".git").exists():
        print(col("git 저장소가 아니다.", "r"))
        return 1

    do_git = a.only in (None, "git")
    do_fs = a.only in (None, "fs")
    n_act = 0

    if do_git:
        print(col("── git", "c"))
        gone, merged, stale_remote = scan_git()
        if not (gone or merged or stale_remote):
            print(f"  {col('깨끗하다', 'g')}")
        for b, up in gone:
            n_act += 1
            print(f"  {col('죽은 upstream', 'y')}  {b} → {up} (원격에 없음)")
            print(f"    {col('git branch --unset-upstream ' + b, 'd')}")
            if a.yes:
                sh("git", "branch", "--unset-upstream", b)
        for b in merged:
            n_act += 1
            print(f"  {col('머지된 브랜치', 'y')}  {b}")
            print(f"    {col('git branch -d ' + b, 'd')}")
            if a.yes:
                sh("git", "branch", "-d", b)
        if stale_remote:
            n_act += len(stale_remote)
            print(f"  {col('사라진 원격 추적', 'y')}  {len(stale_remote)}개")
            for r in stale_remote[:8]:
                print(f"    {r}")
            print(f"    {col('git remote prune origin', 'd')}")
            if a.yes:
                sh("git", "remote", "prune", "origin")
        print()

    if do_fs:
        print(col("── 파일", "c"))
        items = scan_fs()
        if not items:
            print(f"  {col('깨끗하다', 'g')}")
        seen: set[str] = set()
        total = 0
        for name, p, sz, why in items:
            rel = p.relative_to(ROOT).as_posix()
            if name not in seen:
                seen.add(name)
                print(f"  {col(name, 'y')}  {col('— ' + why, 'd')}")
            total += sz
            n_act += 1
            print(f"    {human(sz):>10}  {rel}")
            if a.yes:
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
        if items:
            print(f"  {col('합계 ' + human(total), 'd')}")
        print()

    if n_act == 0:
        print(col("정리할 것이 없다.", "g"))
        return 0

    if a.yes:
        print(col(f"정리 완료 · {n_act}건", "g"))
        print("  파이프라인을 다시 돌려야 하는 것: .work · data/desk 는 자동 재생성")
    else:
        print(col(f"{n_act}건 — 아무것도 지우지 않았다.", "y"))
        print("  실제로 지우려면:  uv run python tools/tidy.py --yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
