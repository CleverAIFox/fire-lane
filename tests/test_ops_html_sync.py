#!/usr/bin/env python3
"""
test_ops_html_sync.py — 운영 방침 HTML 이 실물과 어긋나지 않는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-27. 5인 체제 전환 때 운영 방침을 HTML 로 시각화했다.
**그 순간 규약 정본이 둘이 됐다.**

`test_no_fifth_doc` 은 `.md` 만 본다. HTML 은 그 그물을 통과한다.
그래서 규칙 밖에서 자라다가 조용히 낡는다 — DECISIONS §65 가 정확히
그 사례다. `apply.py` 는 지웠는데 **절차만 MASTER §14 에 남아** 있었고,
다음 사람이 따라 하면 `그런 파일 없음` 으로 죽는 상태였다.

없앨 수 없는 중복이라면 최소한 어긋남은 잡는다(R15~R18).

── 관계 ────────────────────────────────────────────────────────
    정본     docs/MASTER.md §12        산문. 사람이 고친다
    사본     docs/ops.html             표시용. 한눈에 본다
    강제자   이 파일                   양방향 대조

`web/config.js` 가 `seg/params.py` 의 표시용 사본인 것과 같은 관계다(R3).

IN    docs/ops.html · .github/CODEOWNERS · .github/workflows/*.yml
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPS = ROOT / "docs/ops.html"
CO = ROOT / ".github/CODEOWNERS"
WF = ROOT / ".github/workflows"

# 현행 브랜치 계층. 여기를 바꾸면 HTML · 워크플로 · 룰셋을 같이 바꾼다.
TIERS = ["main", "dev", "part/gis", "part/cv", "part/infra"]

# 폐기된 이름. 하나라도 남아 있으면 문서가 낡은 것이다.
RETIRED = ["feat/gis-dev", "feat/cv-dev", "feat/*-dev", "3-Tier"]


def _ops() -> str:
    return OPS.read_text(encoding="utf-8") if OPS.exists() else ""


def test_ops_html_exists():
    assert OPS.exists(), (
        "docs/ops.html 이 없다.\n"
        "  MASTER §12 가 이 파일을 표시용 사본으로 가리킨다.\n"
        "  지울 거면 MASTER §12 의 참조와 이 검사를 같이 지워라.")


def test_ops_html_lists_every_branch_tier():
    """계층 다섯이 전부 적혀 있는가."""
    t = _ops()
    if not t:
        return
    missing = [b for b in TIERS if b not in t]
    assert not missing, (
        f"운영 방침에 빠진 브랜치: {missing}\n"
        "  구조가 바뀌었으면 docs/ops.html 과 MASTER §12 를 같이 고친다.")


def test_ops_html_has_no_retired_branch_names():
    """폐기된 브랜치명이 남아 있지 않은가.

    ★ 이게 §65 형태의 사고를 막는 검사다. 구조를 바꿔도 문서에는
      옛 이름이 남고, 신규 인원은 문서를 보고 그대로 따라 한다.
    """
    t = _ops()
    if not t:
        return
    hit = [r for r in RETIRED if r in t]
    assert not hit, (
        f"운영 방침에 폐기된 이름이 남아 있다: {hit}\n"
        "  통합 브랜치는 part/* 다. feat/* 는 임시 브랜치 전용이며\n"
        "  둘을 같은 접두사로 두면 룰셋이 구분하지 못한다.")


def test_ops_html_branches_match_ci_triggers():
    """HTML 이 적는 계층을 CI 가 실제로 보는가.

    ★ 이 저장소는 CI 트리거와 문서가 갈린 사고를 **두 번** 겪었다
      (2026-08-22 · 08-23). 문서는 `gis` 를 정본이라 적고 워크플로는
      `main` 만 봤다 — **검사가 죽은 채 뜨는 초록불**이었다.
      세 번째를 여기서 막는다.
    """
    t = _ops()
    ci = WF / "contract.yml"
    if not t or not ci.exists():
        return
    txt = ci.read_text(encoding="utf-8")
    body = "\n".join(l for l in txt.splitlines() if not l.lstrip().startswith("#"))
    declared = set()
    for m in re.findall(r"branches:\s*\[([^\]]+)\]", body):
        declared |= {b.strip().strip("'\"") for b in m.split(",")}

    def covered(branch: str) -> bool:
        if branch in declared:
            return True
        prefix = branch.split("/")[0]
        return any(d.startswith(prefix + "/") or d == prefix + "/**"
                   for d in declared)

    missing = [b for b in TIERS if not covered(b)]
    assert not missing, (
        f"운영 방침이 적는 브랜치를 contract.yml 이 보지 않는다: {missing}\n"
        f"  contract.yml 트리거: {sorted(declared)}\n"
        "  검사되지 않는 브랜치로 PR 을 걸면 검사 없이 머지된다.")


def test_ops_html_teams_exist_in_codeowners():
    """HTML 이 언급한 팀이 CODEOWNERS 에 실재하는가."""
    t, co = _ops(), (CO.read_text(encoding="utf-8") if CO.exists() else "")
    if not t or not co:
        return
    teams = set(re.findall(r"@[\w-]+/[\w-]+", t))
    missing = sorted(x for x in teams if x not in co)
    assert not missing, (
        f"운영 방침의 팀이 CODEOWNERS 에 없다: {missing}\n"
        "  둘 중 하나가 낡았다. 존재하지 않는 팀은 GitHub 이 조용히\n"
        "  무시하고 그 경로는 리뷰 없이 머지된다.")


def test_ops_html_declares_itself_a_copy():
    """사본임을 스스로 밝히는가.

    ★ 사본이 정본처럼 읽히면 사람이 여기를 고치기 시작한다. 그러면
      MASTER 와 갈리고, 갈린 채로 신규 인원이 이것만 읽는다.
    """
    t = _ops()
    if not t:
        return
    assert "MASTER" in t and ("사본" in t or "정본" in t), (
        "docs/ops.html 이 정본을 가리키지 않는다.\n"
        "  '정본은 docs/MASTER.md §12' 를 문서 상단에 명시할 것.")


def test_master_points_at_ops_html():
    """정본이 사본을 가리키는가 — 역방향.

    ★ 한쪽만 가리키면 정본을 고칠 때 사본을 잊는다.
      test_declaration_sync.py 와 같은 역방향 검사다.
    """
    m = ROOT / "docs/MASTER.md"
    if not m.exists() or not OPS.exists():
        return
    assert "ops.html" in m.read_text(encoding="utf-8"), (
        "MASTER 가 docs/ops.html 을 가리키지 않는다.\n"
        "  §12 에 '표시용 사본은 docs/ops.html' 한 줄을 넣어라.\n"
        "  정본이 사본의 존재를 모르면 정본을 고칠 때 사본을 잊는다.")

