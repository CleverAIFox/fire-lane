#!/usr/bin/env python3
"""
tools/commit_policy.py — 커밋에 들어가면 안 되는 것을 막는다.

    uv run python tools/commit_policy.py            스테이지된 것만 검사 (훅용)
    uv run python tools/commit_policy.py --tracked  추적 중인 전체 검사 (CI용)

── 왜 커밋 시점인가 ───────────────────────────────────────────
CI 는 push 후에 돈다. 그때 잡히면 이미 히스토리에 박혀 있고,
`git rm --cached` 로 추적을 끊어도 객체는 남는다.

2026-08-21 에 네 번 겪었다 — processed 산출물 16.4MB · `.stale_*` 격리 파일 ·
루트의 일회성 스크립트 3개 · web/data 상한 초과. 전부 사후 발견이었다.

── 규칙 ───────────────────────────────────────────────────────
각 규칙은 **왜** 를 함께 출력한다. 이유를 모르면 우회하게 된다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ── 한계값 ────────────────────────────────────────────────────
MAX_FILE_MB = 5.0          # 단일 파일. 이보다 크면 재생성 가능한지 따진다
MAX_WEBDATA_MB = 40        # contract.yml 과 같은 값
ROOT = Path(__file__).resolve().parents[1]


def sh(*args: str) -> list[str] | None:
    """git 출력. **명령 자체가 실패하면 None** 을 낸다.

    ★ 2026-08-23. 종전에는 실패해도 빈 리스트를 냈고, main 이 그것을
      "검사할 파일이 없다" 로 읽어 조용히 0 을 반환했다. git 이 없거나
      저장소가 아닌 곳에서 돌리면 **아무것도 검사하지 않고 초록불**이다.
      막는 것이 일인 도구가 못 보는 상태를 통과로 보고하면 안 된다 —
      이 저장소가 반복해 겪은 "검사가 죽었는데 초록불" 그 자체다.
    """
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        return None
    return [x for x in r.stdout.splitlines() if x]


def staged() -> list[str] | None:
    return sh("git", "diff", "--cached", "--name-only", "--diff-filter=ACM")


def tracked() -> list[str] | None:
    return sh("git", "ls-files")


# ── 규칙 ──────────────────────────────────────────────────────
# (이름, 판정함수, 왜)

def r_stale(p: str) -> bool:
    """ingest 실패 시 격리되는 옛 산출물."""
    return ".stale_" in p


def r_processed(p: str) -> bool:
    """재생성 가능(285초)한 산출물. 예외 4개만 UI 입력이라 커밋한다."""
    if not p.startswith("data/processed/"):
        return False
    keep = {"data/processed/segments.geojson",
            "data/processed/segments.schema.json",
            "data/processed/_manifest.json",
            "data/processed/seg_uid_map.csv"}
    return p not in keep


def r_root_script(p: str) -> bool:
    """루트의 일회성 스크립트. README §18-5 R8."""
    return "/" not in p and p.endswith(".sh")


def r_env(p: str) -> bool:
    """비밀 값. .env.example 만 커밋한다."""
    name = Path(p).name
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def r_work(p: str) -> bool:
    """파이프라인 임시 작업물."""
    return p.startswith(".work/") or p.startswith("_backup_") or ".bak_" in p


def r_lineage(p: str) -> bool:
    """실행마다 달라지는 로컬 기록. 커밋하면 기계 간 교착이 난다."""
    return p.endswith("data/processed/_lineage.json")


RULES = [
    ("격리 산출물", r_stale,
     "ingest 실패 시 하류를 막으려고 개명한 파일이다. 재실행하면 사라진다"),
    ("processed 산출물", r_processed,
     "285초에 재생성된다. README '데이터 계층'이 커밋하지 않는다고 선언했다"),
    ("루트 일회성 스크립트", r_root_script,
     "README §18-5 R8. 필요하면 tools/ 에 이름 있는 도구로 넣어라"),
    ("비밀 값", r_env,
     ".env.example 만 커밋한다"),
    ("임시 작업물", r_work,
     "재생성 대상이다"),
    ("계보 기록", r_lineage,
     "실행마다 달라진다. 커밋하면 다른 기계에서 교착한다"),
]


def check_paths(paths: list[str]) -> list[str]:
    bad = []
    for name, fn, why in RULES:
        hit = [p for p in paths if fn(p)]
        if hit:
            bad.append(f"\n  ✗ {name} — {why}")
            for p in hit[:12]:
                bad.append(f"      {p}")
            if len(hit) > 12:
                bad.append(f"      ... 외 {len(hit) - 12}건")
    return bad


def check_size(paths: list[str]) -> list[str]:
    bad = []
    big = []
    for p in paths:
        f = ROOT / p
        if not f.is_file():
            continue
        mb = f.stat().st_size / 1e6
        if mb > MAX_FILE_MB:
            big.append((mb, p))
    if big:
        bad.append(f"\n  ✗ 단일 파일 {MAX_FILE_MB}MB 초과 — "
                   "재생성 가능한지 먼저 따져라")
        for mb, p in sorted(big, reverse=True)[:8]:
            bad.append(f"      {mb:7.1f}MB  {p}")

    web = ROOT / "web" / "data"
    if web.is_dir():
        mb = sum(f.stat().st_size for f in web.rglob("*") if f.is_file()) / 1e6
        if mb >= MAX_WEBDATA_MB:
            bad.append(f"\n  ✗ web/data {mb:.1f}MB — 상한 {MAX_WEBDATA_MB}MB")
            bad.append("      타일 줌 단계를 줄이거나 외부 호스팅으로 옮겨라")
    return bad


def main() -> int:
    full = "--tracked" in sys.argv
    paths = tracked() if full else staged()

    # ★ 못 본 것과 볼 것이 없는 것은 다르다.
    if paths is None:
        print("\033[31m커밋 정책: git 목록을 못 읽었다\033[0m")
        print("  저장소가 아니거나 git 이 없다. 검사하지 못했으므로 통과가 아니다.")
        return 1
    if full and not paths:
        print("\033[31m커밋 정책: 추적 파일이 0개다\033[0m")
        print("  --tracked 는 저장소 전체를 보는 모드다. 0개는 정상이 아니다.")
        return 1
    if not paths:
        # 스테이지가 비어 있는 것은 정상이다(커밋할 것이 없다).
        return 0

    # ★ web/data 상한은 스테이지 내용과 무관하게 본다. 종전에는 이 검사가
    #   check_size(paths) 안에 묶여 있어, 스테이지가 비면 같이 죽었다.

    bad = check_paths(paths) + check_size(paths)
    if not bad:
        n = len(paths)
        print(f"커밋 정책 OK · {n}개 {'추적' if full else '스테이지'}")
        return 0

    print("\033[31m커밋 정책 위반\033[0m", end="")
    print("\n".join(bad))
    print("\n  해제가 필요하면:")
    print("      git rm --cached <파일>        추적만 끊는다 (파일은 남는다)")
    print("      git commit --no-verify        ★ 최후수단. 이유를 커밋 메시지에 남겨라")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
