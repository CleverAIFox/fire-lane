#!/usr/bin/env python3
"""
owned_paths.py — CODEOWNERS 를 소유권·검사강도의 단일 정본으로 읽는다.

── 왜 생겼나 ───────────────────────────────────────────────────
5인 체제로 가면서 두 가지가 동시에 필요해졌다.

    1. 경로마다 누가 소유하는가        (리뷰 권한)
    2. 경로마다 어느 강도로 검사하는가  (CI 게이트)

이 둘을 따로 적으면 반드시 어긋난다. 이 저장소가 세 번 겪었다 —
contract.yml 의 브랜치 목록(2회) · requirements-etl · CI 의존성 손목록.
**정본이 둘이면 반드시 어긋난다**(MASTER §18-3).

그래서 CODEOWNERS 하나만 고치면 둘이 같이 움직이게 한다.
단독 소유 경로는 그 사람이 전권을 갖는 대신 엄격 검사를 받는다.

── 규칙 ────────────────────────────────────────────────────────
CODEOWNERS 는 **마지막에 매치된 규칙이 이긴다**(GitHub 사양).
gitignore 문법의 부분집합만 쓴다 — `/dir/` · `/path/file` · `*.ext`.
`**` 는 쓰지 않는다. 파서와 GitHub 의 해석이 갈릴 여지를 남기지 않는다.

IN    .github/CODEOWNERS
OUT   stdout (경로 목록) 또는 import 해서 함수로
PARAM --owner <핸들>   단독 소유 경로만 출력. 기본 @AIMasterFox
      --all            추적되는 전 경로와 소유자를 표로
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODEOWNERS = ROOT / ".github/CODEOWNERS"


# ── 파싱 ───────────────────────────────────────────────────────
def rules() -> list[tuple[str, set[str], bool]]:
    """CODEOWNERS 를 (패턴, 소유자집합, 엄격여부) 목록으로. 선언 순서를 보존한다.

    ★ 엄격 여부는 줄 끝 `# !strict` 태그로 표시한다. 별도 파일을 만들지
      않는 이유는 하나다 — **정본이 둘이면 반드시 어긋난다**(MASTER §18-3).
      소유자가 누구냐와 엄격하게 관리할 것이냐는 상관관계지 같은 것이
      아니므로, 소유자로 추론하지 않고 명시적으로 적는다.
    """
    if not CODEOWNERS.exists():
        return []
    out: list[tuple[str, set[str], bool]] = []
    for line in CODEOWNERS.read_text(encoding="utf-8").splitlines():
        head, _, tail = line.partition("#")
        s = head.strip()
        if not s:
            continue
        parts = s.split()
        pat, owners = parts[0], {p for p in parts[1:] if p.startswith("@")}
        out.append((pat, owners, "!strict" in tail))
    return out


def _match(pattern: str, rel: str) -> bool:
    """CODEOWNERS 패턴 하나가 경로 하나에 걸리는가.

    ★ 접두 일치로 퉁치면 안 된다. `/src/cv` 가 `/src/cvtools/x.py` 를
      잡아버린다. 디렉토리 경계를 명시적으로 본다.
    """
    p = pattern.lstrip("/")
    if p.endswith("/"):                       # 디렉토리 전체
        return rel.startswith(p)
    if "*" in p or "?" in p:                  # 글롭
        return fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(Path(rel).name, p)
    return rel == p or rel.startswith(p + "/")


def owners_of(rel: str) -> set[str]:
    """경로 하나의 소유자. 매치가 없으면 빈 집합 = 미소유."""
    found: set[str] = set()
    for pat, own, _ in rules():               # 마지막 매치가 이긴다
        if _match(pat, rel):
            found = own
    return found


def is_strict(rel: str) -> bool:
    """경로 하나가 엄격 검사 대상인가. 마지막 매치가 이긴다."""
    flag = False
    for pat, _, st in rules():
        if _match(pat, rel):
            flag = st
    return flag


def tracked(prefix: str = "") -> list[str]:
    """git 이 추적하는 경로만. 디스크를 훑지 않는다.

    ★ 2026-08-24 의 교훈이다(test_web_ownership). 디스크를 보면 로컬
      생성물 때문에 기기마다 결과가 갈린다. CODEOWNERS 는 리뷰 권한을
      정하는 파일이고, 저장소에 안 들어오는 것은 리뷰 대상이 아니다.
    """
    r = subprocess.run(["git", "ls-files", prefix] if prefix else ["git", "ls-files"],
                       cwd=ROOT, capture_output=True, text=True)
    return sorted(x for x in r.stdout.split() if x)


# ── 질의 ───────────────────────────────────────────────────────
def strict_paths() -> list[str]:
    """`# !strict` 로 표시된 추적 경로.

    ★ 종전에는 "@AIMasterFox 단독 소유" 로 추론했다. 게으른 대리
      지표였다 — 지혜님 단독 소유(`style.css`)가 빠지고, 공동 소유지만
      엄격해야 하는 경로(`config.js`)도 빠졌다. 명시 태그로 바꿨다.

    엄격 검사를 남의 경로에 강요하지 않는 것이 원칙이다. 우회가
    습관이 되면 강제자 전체가 무력해진다. **범위를 좁혀서 강도를 유지한다.**
    """
    return [f for f in tracked() if is_strict(f)]


def unowned() -> list[str]:
    """소유자가 없는 추적 경로. 있으면 CI 가 막는다."""
    return [f for f in tracked() if not owners_of(f)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default=None, help="이 핸들이 소유한 경로만")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--unowned", action="store_true")
    ap.add_argument("--py-only", action="store_true", help="*.py 만")
    a = ap.parse_args()

    if a.unowned:
        for f in unowned():
            print(f)
        return 0
    if a.all:
        for f in tracked():
            o = owners_of(f)
            print(f"{f:60s} {' '.join(sorted(o)) if o else '── 미소유 ──'}")
        return 0

    paths = strict_paths()
    if a.owner:
        paths = [p for p in paths if a.owner in owners_of(p)]
    if a.py_only:
        paths = [p for p in paths if p.endswith(".py")]
    for f in paths:
        print(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())

