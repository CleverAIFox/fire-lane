"""
gitq.py — **git 에게 묻는 한 문.** 못 답하면 빈 것이 아니라 `None` 이다. (DECISIONS §372)

── 왜 생겼나 ───────────────────────────────────────────────────
저장소에 「git 이 추적하는 것」을 묻는 자리가 **넷**이었고 **하나만 맞았다** —

    tools/treecheck.py::tracked          returncode 를 보고 None 을 돌려준다  ✓
    tools/encoding_check.py::tracked     except → []       ← 관문의 우주가 0 이 된다
    tools/docseal.py::_tracked           check=False, rc 안 봄 → frozenset()
    src/firelane/datalog.py              check=False, rc 안 봄 → frozenset()
    tools/readmecheck.py::web_entries    rc!=0 → []

빈 집합과 「못 물었다」는 **다른 사실**이다. 섞으면 —

    `encoding_check` 는 **검사할 파일이 0개**라고 보고 **초록**이 된다
    `datalog` 는 추적 목록이 비었으므로 산출물 전부를 **「안 지었다」**로 읽는다
                 (§290-7 이 세운 「추적 밖 = 안 지었다」 구분이 통째로 사라진다)

★ 그리고 `check=False` 는 **바이너리가 없는 경우를 안 막는다.** 실측 —
  `subprocess.run(["git", ...], check=False)` 는 PATH 에 git 이 없으면
  `FileNotFoundError` 를 던진다. `check` 는 **종료코드**에만 관여한다.
  `Dockerfile` 은 git 을 깔지 않고 `.git` 도 안 담으므로 그 기계가 실물이다.

★ **회색 = NULL.** 이 저장소가 판정에서 쓰는 규율을 도구에도 쓴다 — 모르는
  것을 0 으로 적으면 그 0 이 답처럼 쓰인다.

IN    git (외부 명령)
OUT   `frozenset[str] | None` · `str | None`
밖    **git 을 재구현하지 않는다.** `.gitignore` 규칙을 손으로 파싱하면 git 과
      갈리고, 갈리면 오탐이 나고, 오탐은 사람이 `--force` 를 쓰게 만든다(§73).
      **판정을 안 내린다.** `None` 을 받았을 때 터질지 건너뛸지 보고할지는
      부르는 쪽이 정한다 — 그 자리마다 「못 물었다」의 값이 다르다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

#: 넉넉하되 무한은 아니다. 큰 저장소의 `ls-files` 도 1초 안이다.
TIMEOUT = 60


def ask(args: list[str], cwd: Path | str | None = None,
        timeout: int = TIMEOUT) -> str | None:
    """git 한 번. **못 물었으면 `None`, 물었으면 표준출력.**

    `None` 이 되는 경우 셋 —
      · 바이너리가 없다            `FileNotFoundError` (`check=False` 가 안 막는다)
      · 저장소가 아니다            `rc=128 fatal: not a git repository`
      · 안 끝난다                  `TimeoutExpired`

    ★ 빈 문자열은 `None` 이 **아니다.** 「추적하는 것이 하나도 없다」는 답일
      수 있고(빈 커밋), 그것은 「못 물었다」와 다른 사실이다.
    """
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                           text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def tracked(cwd: Path | str | None = None) -> frozenset[str] | None:
    """`git ls-files` 의 결과. **못 물었으면 `None`.**"""
    out = ask(["ls-files", "-z"], cwd=cwd)
    if out is None:
        return None
    return frozenset(x for x in out.split("\0") if x)


def ignored(rels: list[str], cwd: Path | str | None = None) -> frozenset[str] | None:
    """`git check-ignore` 가 무시한다고 말하는 것. **못 물었으면 `None`.**

    ★ `--no-index` 가 없으면 **추적 중인 파일은 보고되지 않는다**(git 사양).
      무시 규칙인데 추적 중인 상태가 바로 찾으려는 것이라, 빼면 영원히 0건이다.

    ★ `check-ignore` 는 **일치가 없으면 rc=1** 이다 — 그것은 실패가 아니라
      「무시되는 것이 없다」는 답이다. 그래서 `ask` 를 안 쓰고 직접 가른다.
    """
    if not rels:
        return frozenset()
    try:
        r = subprocess.run(["git", "check-ignore", "--no-index", "--stdin", "-z"],
                           cwd=cwd, input="\0".join(rels), capture_output=True,
                           text=True, check=False, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1):
        return None
    return frozenset(x for x in r.stdout.split("\0") if x)


def head(cwd: Path | str | None = None) -> str | None:
    """`HEAD` 의 짧은 sha. **못 물었으면 `None`.**"""
    out = ask(["rev-parse", "--short", "HEAD"], cwd=cwd)
    return out.strip() if out is not None else None


def dirty(cwd: Path | str | None = None) -> list[str] | None:
    """더러운 경로 목록. **못 물었으면 `None`** — 빈 목록(깨끗하다)과 다르다."""
    out = ask(["status", "--porcelain"], cwd=cwd)
    if out is None:
        return None
    return [ln for ln in out.splitlines() if ln.strip()]
