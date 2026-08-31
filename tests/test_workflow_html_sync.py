#!/usr/bin/env python3
"""
test_workflow_html_sync.py — 운영 방침 HTML 이 실물과 어긋나지 않는가.

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
    사본     docs/workflow.html             표시용. 한눈에 본다
    강제자   이 파일                   양방향 대조

`web/config.js` 가 `seg/params.py` 의 표시용 사본인 것과 같은 관계다(R3).

IN    docs/workflow.html · .github/CODEOWNERS · .github/workflows/*.yml
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs/workflow.html"
CO = ROOT / ".github/CODEOWNERS"
WF = ROOT / ".github/workflows"

# 현행 브랜치 계층. 여기를 바꾸면 HTML · 워크플로 · 룰셋을 같이 바꾼다.
TIERS = ["main", "dev", "part/gis", "part/cv", "part/infra"]

# 폐기된 이름. 하나라도 남아 있으면 문서가 낡은 것이다.
RETIRED = ["feat/gis-dev", "feat/cv-dev", "feat/*-dev", "3-Tier"]


def _wf() -> str:
    return HTML.read_text(encoding="utf-8") if HTML.exists() else ""


def test_workflow_html_exists():
    assert HTML.exists(), (
        "docs/workflow.html 이 없다.\n"
        "  MASTER §12 가 이 파일을 표시용 사본으로 가리킨다.\n"
        "  지울 거면 MASTER §12 의 참조와 이 검사를 같이 지워라.")


def test_workflow_html_lists_every_branch_tier():
    """계층 다섯이 전부 적혀 있는가."""
    t = _wf()
    if not t:
        return
    missing = [b for b in TIERS if b not in t]
    assert not missing, (
        f"운영 방침에 빠진 브랜치: {missing}\n"
        "  구조가 바뀌었으면 docs/workflow.html 과 MASTER §12 를 같이 고친다.")


def test_workflow_html_has_no_retired_branch_names():
    """폐기된 브랜치명이 남아 있지 않은가.

    ★ 이게 §65 형태의 사고를 막는 검사다. 구조를 바꿔도 문서에는
      옛 이름이 남고, 신규 인원은 문서를 보고 그대로 따라 한다.
    """
    t = _wf()
    if not t:
        return
    hit = [r for r in RETIRED if r in t]
    assert not hit, (
        f"운영 방침에 폐기된 이름이 남아 있다: {hit}\n"
        "  통합 브랜치는 part/* 다. feat/* 는 임시 브랜치 전용이며\n"
        "  둘을 같은 접두사로 두면 룰셋이 구분하지 못한다.")


def test_workflow_html_branches_match_ci_triggers():
    """HTML 이 적는 계층을 CI 가 실제로 보는가.

    ★ 이 저장소는 CI 트리거와 문서가 갈린 사고를 **두 번** 겪었다
      (2026-08-22 · 08-23). 문서는 `gis` 를 정본이라 적고 워크플로는
      `main` 만 봤다 — **검사가 죽은 채 뜨는 초록불**이었다.
      세 번째를 여기서 막는다.
    """
    t = _wf()
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


def test_workflow_html_teams_exist_in_codeowners():
    """HTML 이 언급한 팀이 CODEOWNERS 에 실재하는가."""
    t, co = _wf(), (CO.read_text(encoding="utf-8") if CO.exists() else "")
    if not t or not co:
        return
    teams = set(re.findall(r"@[\w-]+/[\w-]+", t))
    missing = sorted(x for x in teams if x not in co)
    assert not missing, (
        f"운영 방침의 팀이 CODEOWNERS 에 없다: {missing}\n"
        "  둘 중 하나가 낡았다. 존재하지 않는 팀은 GitHub 이 조용히\n"
        "  무시하고 그 경로는 리뷰 없이 머지된다.")


def test_workflow_html_declares_itself_a_copy():
    """사본임을 스스로 밝히는가.

    ★ 사본이 정본처럼 읽히면 사람이 여기를 고치기 시작한다. 그러면
      MASTER 와 갈리고, 갈린 채로 신규 인원이 이것만 읽는다.
    """
    t = _wf()
    if not t:
        return
    assert "MASTER" in t and ("사본" in t or "정본" in t), (
        "docs/workflow.html 이 정본을 가리키지 않는다.\n"
        "  '정본은 docs/MASTER.md §12' 를 문서 상단에 명시할 것.")


def test_master_points_at_workflow_html():
    """정본이 사본을 가리키는가 — 역방향.

    ★ 한쪽만 가리키면 정본을 고칠 때 사본을 잊는다.
      test_declaration_sync.py 와 같은 역방향 검사다.
    """
    m = ROOT / "docs/MASTER.md"
    if not m.exists() or not HTML.exists():
        return
    assert "workflow.html" in m.read_text(encoding="utf-8"), (
        "MASTER 가 docs/workflow.html 을 가리키지 않는다.\n"
        "  §12 에 '표시용 사본은 docs/workflow.html' 한 줄을 넣어라.\n"
        "  정본이 사본의 존재를 모르면 정본을 고칠 때 사본을 잊는다.")



def test_ship_ci_check_actually_discriminates():
    """★ 역방향 — `ship.py` 의 CI 트리거 판정이 **입력을 검사하는가.**

    2026-08-31. 위 `test_workflow_html_branches_match_ci_triggers` 는 문서가
    적는 계층이 트리거에 있는지만 봤다. 정방향이라 통과했다. 그런데
    `ship.py` 쪽 판정은 `base` 를 ("gis","main","master") 에서 찾아
    하나라도 pr 트리거에 있으면 OK 를 냈고, `main` 은 항상 있으므로
    **어떤 브랜치 이름에도 초록불을 냈다.**

    같은 병을 두 번 겪었다 — `audit_pattern('')` 이 42번 정상적으로 울었고
    원인은 호출부였다. 옳게 우는 것처럼 보이는 검사가 제일 오래 간다.
    여기서는 **틀린 입력에 실제로 빨간불이 뜨는지**를 본다.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("ship", ROOT / "tools/ship.py")
    ship = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ship)

    push_b = ship.ci_branches("push")
    assert push_b, "contract.yml 에서 push 트리거를 못 읽었다"

    for good in TIERS + ["feat/gis-x", "part/gis"]:
        assert ship.branch_covered(good, push_b), (
            f"운영방침상 정상 브랜치 {good} 가 CI 밖으로 판정된다.\n"
            f"  push 트리거: {sorted(push_b)}")

    for bad in ("wip/data-hygiene-20260830", "hotfix/x", "아무거나-쓰레기"):
        assert not ship.branch_covered(bad, push_b), (
            f"방침 밖 브랜치 {bad} 가 CI 대상으로 판정된다 — 검사가 죽었다.\n"
            "  이 검사가 초록불이면 밀어도 CI 가 안 도는 브랜치를 알 수 없다.")


def test_ci_trigger_has_no_retired_trunk():
    """폐기된 `gis` 트렁크가 **실행되는 값**으로 남아 있지 않은가.

    08-27 에 4단으로 갔는데 `ship.py` 가 `gis` 를 base 후보 1순위로
    들고 있었다. 낡은 이름은 조용히 판정을 왜곡한다.

    ★ 산문은 잡지 않는다. 이 저장소는 판단의 근거를 주석·독스트링에
      남기는 것이 규약이고, 거기 적힌 `gis` 는 이력이지 값이 아니다.
      AST 로 **문자열 상수만** 본다.
    """
    import ast

    tree = ast.parse((ROOT / "tools/ship.py").read_text(encoding="utf-8"))
    docs = {id(ast.get_docstring(n, clean=False)) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))}
    hit = [n.lineno for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)
           and n.value == "gis" and id(n.value) not in docs]
    assert not hit, (
        f"tools/ship.py {hit} 행에 폐기된 트렁크 `gis` 가 값으로 남아 있다.\n"
        "  08-27 에 main ← dev ← part/* ← feat/* 4단으로 갔다.")


# ── 문서 쪽 강제자 ──────────────────────────────────────────────
# ★ 2026-08-30. 위 검사들은 전부 workflow.html · ship.py · contract.yml 을 본다.
#   **정본인 MASTER 는 아무도 안 봤다.** 그래서 §11-1 · §12-4 · §12-5 ·
#   §12-7 이 08-27 에 폐기한 `gis` 트렁크 절차를 그대로 들고 있었고,
#   §12-7 표는 트리거를 `main`·`gis` 라고 적고 있었다.
#
#   사본을 지키는 검사만 만들고 정본은 놔둔 꼴이다. DECISIONS §65 —
#   `apply.py` 는 지웠는데 절차만 MASTER 에 남아 다음 사람이 따라 하면
#   `그런 파일 없음` 으로 죽던 그 형태가 정본 쪽에 다시 났다.
CANON_DOCS = ["docs/MASTER.md", "docs/PLAN.md", "README.md"]

# 폐기된 브랜치 이름. `git` 명령의 인자로 등장하면 낡은 절차다.
RETIRED_BRANCHES = ["gis", "master"]

# 실행 가능한 자리 — 코드 펜스 안의 git 명령.
_FENCE = re.compile(r"^\s*```")
_GIT = re.compile(
    r"\bgit\s+(?:checkout|switch|merge|pull|push|rebase|branch)\b[^\n#]*")
STALE_OK = "<!--stale-ok-->"


def _fenced_git_lines(path: Path) -> list[tuple[int, str]]:
    """코드 펜스 안의 git 명령 줄만 낸다.

    ★ 산문은 보지 않는다. DECISIONS 가 폐기된 절차를 증거로 인용하고
      워크플로 머리말이 `gis 트렁크 폐기` 라고 적는 것은 **이력**이다.
      이력을 위반으로 세면 회고를 쓸 수 없게 되고, 그러면 사람이
      검사를 끈다 — test_doc_style._lines 가 같은 이유로 펜스를 뺀다.
      여기는 반대다. **따라 하면 실행되는 자리**만 본다.
    """
    p = ROOT / path if not path.startswith("/") else Path(path)
    if not p.exists():
        return []
    out, fence = [], False
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE.match(line):
            fence = not fence
            continue
        if fence and STALE_OK not in line and _GIT.search(line):
            out.append((n, line.strip()))
    return out


def test_canon_docs_have_no_retired_branch_commands():
    """정본의 **따라 할 수 있는 명령**에 폐기된 브랜치가 없는가.

    workflow.html 만 지키던 그물을 MASTER · PLAN · README 로 넓힌다.
    사본이 최신이고 정본이 낡으면 사본을 정본으로 되돌릴 근거가 사라진다.
    """
    bad: list[str] = []
    for rel in CANON_DOCS:
        for n, line in _fenced_git_lines(rel):
            for cmd in _GIT.findall(line):
                args = cmd.split()[2:]
                for b in RETIRED_BRANCHES:
                    if b in args or f"origin/{b}" in args:
                        bad.append(f"  {rel}:{n}  {line[:70]}  ← `{b}`")
    assert not bad, (
        "정본 문서에 폐기된 브랜치를 쓰는 명령이 남아 있다.\n"
        f"위반 {len(bad)}건\n" + "\n".join(bad[:20])
        + "\n\n  08-27 에 main ← dev ← part/* ← feat/* 4단으로 갔다.\n"
        "  신규 인원은 이 명령을 그대로 붙여넣고 `그런 브랜치 없음` 을 본다.\n"
        f"  의도적 인용이면 줄 끝에 {STALE_OK} 를 붙인다.")


def test_canon_docs_workflow_table_matches_contract_yml():
    """MASTER 가 적는 CI 트리거가 워크플로 실물과 같은가.

    ★ §12-7 이 `main`·`gis` 라고 적고 있었다. 표는 사람이 손으로 쓰고
      아무도 대조하지 않았다. 위 test_workflow_html_branches_match_ci_triggers
      의 정본판이다.
    """
    m = ROOT / "docs/MASTER.md"
    ci = WF / "contract.yml"
    if not m.exists() or not ci.exists():
        return
    txt = m.read_text(encoding="utf-8")
    body = "\n".join(l for l in ci.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    declared = set()
    for mm in re.findall(r"branches:\s*\[([^\]]+)\]", body):
        declared |= {b.strip().strip("'\"") for b in mm.split(",")}

    rows = [l for l in txt.splitlines()
            if l.startswith("|") and "`contract`" in l]
    assert rows, ("MASTER 에 `contract` 워크플로 행이 없다.\n"
                  "  §12-7 표가 사라졌거나 이름이 바뀌었다.")
    row = rows[0]
    missing = sorted(d for d in declared if f"`{d}`" not in row)
    assert not missing, (
        f"MASTER §12-7 의 `contract` 행이 트리거를 빠뜨렸다: {missing}\n"
        f"  contract.yml 실물: {sorted(declared)}\n"
        f"  MASTER 표: {row.strip()[:90]}\n"
        "  문서가 좁게 적으면 사람이 검사되는 브랜치를 좁게 안다.")


# ── 룰셋 방침의 정본이 셋이다 ───────────────────────────────────
# ★ 2026-08-31. 같은 방침이 세 곳에 있다 —
#     tools/ruleset_check.py  EXPECT   실물과 대조하는 코드판
#     docs/workflow.html      §4 표     팀이 읽는 표
#     docs/MASTER.md          §12-1     정본 산문
#
#   그날 아침 MASTER 에 승인 열을 넣으면서 `dev` 를 1로 적었는데 실물은
#   0이었고, 오후 룰셋 재구축 뒤에도 MASTER 만 낡은 채로 남았다.
#   **정본이 셋인데 대조가 없으면 반드시 갈린다**(R3 · DECISIONS §78).
def test_ruleset_policy_agrees_across_three_places():
    """`ruleset_check.EXPECT` ↔ workflow §4 ↔ MASTER §12-1."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "rsc", ROOT / "tools/ruleset_check.py")
    rsc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rsc)

    html = _wf()
    master = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    bad = []
    for name, want in rsc.EXPECT.items():
        for doc, text in (("workflow.html", html), ("MASTER.md", master)):
            if want["ref"] not in text:
                bad.append(f"  {doc}: 대상 `{want['ref']}` 가 없다 ({name})")
            if name not in text:
                bad.append(f"  {doc}: 룰셋 이름 `{name}` 이 없다")
        # 머지 방식은 이름이 문서마다 달라 대소문자를 무시하고 본다.
        for doc, text in (("workflow.html", html), ("MASTER.md", master)):
            if want["merge"][0].lower() not in text.lower():
                bad.append(f"  {doc}: 머지 방식 `{want['merge'][0]}` 이 없다 ({name})")
    assert not bad, (
        "룰셋 방침이 세 곳에서 갈린다:\n" + "\n".join(sorted(set(bad)))
        + "\n\n  정본은 tools/ruleset_check.py 의 EXPECT 다 — 실물과 대조하는 것이 그것뿐이다.\n"
        "  거기를 고치면 workflow §4 와 MASTER §12-1 도 같이 고친다.")
