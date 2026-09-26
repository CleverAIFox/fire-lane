#!/usr/bin/env python3
"""
test_tools_are_wired.py — 만들어놓고 안 부르는 도구가 있는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-02. `tools/docx_check.py` 에 캡션 절을 새로 붙였다. 그날 그것으로
기획서의 `1,102` 셋과 낡은 캡션 둘을 잡았다. 그런데 **그 도구는
`verify.sh` 에도 CI 에도 테스트에도 걸려 있지 않았다.** 사람이 손으로
칠 때만 돌았고, 그 사람은 2026-09-03 에 나간다.

같은 상태인 것이 넷이었다 — `docx_check` · `refcheck` · `treecheck` ·
`triage`. 만드는 것과 **거는 것**은 다른 일인데 거는 쪽에 강제자가 없었다.

★ 이 저장소가 반복해 배운 형태다(MASTER §17) — 규약은 존재하고 강제하는
  검사가 없다. 이번에는 그 대상이 **강제자 자신**이었다.

── 무엇을 보는가 ───────────────────────────────────────────────
`tools/*.py` 각각이 아래 중 한 곳에서라도 **실행되는가.**

    tools/verify.sh · tools/ship.py · .github/workflows/*.yml · tests/*.py

★ 문서에 이름이 적혀 있는 것은 배선이 아니다. README 가 도구를 나열하는
  것과 그 도구가 도는 것은 다르다.

EXEMPT 는 **사유를 함께 적는다.** 비우는 것이 목표가 아니다 — 조사 도구는
사람이 판단하려고 부르는 것이라 자동 실행이 오히려 틀리다.

IN    tools/*.py
OUT   없음 (검사)
PARAM EXEMPT
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 자동 실행하지 않는 것. 사유 없이 늘리지 않는다.
# ★ 2026-09-13. 여섯을 뺐다 — verify.sh 가 `step` 으로 **실제로 부르는데**
#   면제 목록에 남아 있었다. `--check` 로 강제자 승격만 하고 여기서 안 뺐다.
#   그 상태에서는 verify.sh 배선을 끊어도 우는 곳이 없다. 면제가 사각지대다.
EXEMPT = {
    "widen": "넓혔을 때를 **재는** 도구다. 지금 상태에서 항상 수십 건을 내므로\n             배선하면 매번 뜨는 경고가 되고, 그러면 아무도 안 읽는다",
    "codepatch": "배치 스크립트가 import 하는 **라이브러리**다. 실행 대상이 아니다",
    "inbox_fl": "INBOX 에 `fl.sh` 로 **복사해 두는** 부트스트랩이다. 저장소 안에서 부르는 곳이\n             없는 것이 설계다 — 사람이 INBOX 에서 부른다. 동작은 test_batch_tools 가 든다(§214-1)",
    "inbox_go": "INBOX 에 `go.sh` 로 **복사해 두는** 한 줄 진입점이다. `inbox_fl` 과 같은 자리 —\n             저장소 안에서 부르는 곳이 없는 것이 설계다. `.env` 적재 · zip 풀기 · 브랜치 ·\n             `--relock` 판단을 하고 `fl.sh` 를 부른다. 모의 실행으로 넷을 봤다(§256)",

    "kpi": "진입 실패율 산출. 발표에서 인용할 숫자라 사람이 조건과 함께 부른다",
    "its_linkmap": "ITS 소통정보 링크 ↔ seg_uid 대조표. 외부 API 규격 확인용이라 CI 에 못 건다",
    "matchcheck": "Mapbox Map Matching 커버리지 대조. 토큰 필요·외부 API 라 CI 에 못 건다",
    "bridge_audit": "다리 분석으로 실측 우선순위 산출. 사람이 답사 계획을 세우려고 부른다",
    # ── 조사 도구. 사람이 판단하려고 부른다. 아무것도 안 바꾼다(README).
    "clearance_probe": "최대내접원 방식 대조. 2026-08-22 기각(DECISIONS §32)",
    "corner_probe": "코너 기하 조사",
    "transition": "R2 전이표. R3 전후로 사람이 부른다 — `baseline.py diff --transition` 이 같은 모듈을 쓴다(DECISIONS §187)",
    "lanes_probe": "표준노드링크 차로수로 폭 하한 대조",
    # ── 일회성 이관. 돌리고 나면 no-op 이다(R8).
    "ledger_stem": "대장 stem 이관. 완료",
    "migrate_names": "raw 개명 백필",
    # ── 사람이 부르는 것. 자동으로 돌면 안 되는 이유가 있다.
    # ★ 2026-09-24 (DECISIONS §239). 넷이 **시험 파일 독스트링 한 줄**로 배선
    #   판정을 통과하고 있었다. 검사가 독스트링을 빼면서 드러났다 — 사각지대가
    #   선언조차 안 돼 있던 것이라 사유를 적어 등재한다.
    "doctor": "레이크 **전체**를 훑는다. 레이크 없는 기계(CI)에서는 돌 수 없고, "
              "돌면 수 분이 걸린다. 사람이 레이크 기계에서 친다",
    "jijeok_probe": "연속지적도 대조. `--extract` 가 zip 을 풀어야 하고 그 원본이 "
                    "레이크에 있다 — `clearance_probe` · `corner_probe` 와 같은 족",
    "ledger_feeds": "`feeds` 산문 → 리스트 이관. `--apply` 가 `sources.yaml` 을 "
                    "고친다. 사람이 확인하고 친다(`ledger_stem` 과 같은 꼴)",
    "serve": "개발 서버. **끝나지 않는 프로세스**라 관문에 걸 수 없다",
    "intake": "Downloads → landing 게이트",
    "docx_fix": "기획서를 실제로 고친다. 사람이 확인하고 친다",
    "baseline": "봉인. 사람이 시점을 정한다",
    "triage": "대장 밖 파일을 내용으로 판정. Downloads·landing 을 본다",
    # ── 2026-09-20. 검사 범위를 `.sh` · `.mjs` 까지 넓히며 드러났다.
}

CALLERS = ("tools/verify.sh", "tools/ship.py")

# ★ 2026-09-20. 이 검사가 **네 자리에서 헐거웠다.** 실측으로 하나씩 확인했다.
#   ① 범위가 `tools/*.py` 뿐이었다 — `.sh` · `.mjs` 다섯이 검사 밖이었고
#      그중 `janitor.sh` 는 **아무도 안 불렀다.** 이름은 `every_tool` 이다.
#      W3-8 · W4-8 · W3-16 · W3-18 · §197-1 과 같은 족의 여섯 번째다.
#   ② **죽은 면제를 안 봤다** — 면제 31 중 **12** 가 실제로는 불리고 있었다.
#      2026-09-13 에 같은 이유로 여섯을 뺐다는 주석이 위에 있는데, 그때
#      강제자를 안 세워 다시 열둘로 늘었다. 손으로 고친 것은 되돌아온다.
#   ③ **주석 속 이름을 호출로 셌다.** 파일 전체를 이어 붙여 grep 했으므로
#      「`tools/x.py` 를 참고하라」는 주석도 배선으로 보였다.
#   ④ **이름 충돌을 못 봤다** — `from firelane import transition` 이
#      `tools/transition.py` 의 호출로 세어졌다. 둘은 다른 파일이다.
TOOL_SUFFIX = (".py", ".sh", ".mjs")
_COMMENT = ("#", "//", "*", "<!--")


def _tools() -> list[Path]:
    return sorted(p for p in (ROOT / "tools").iterdir()
                  if p.is_file() and p.suffix in TOOL_SUFFIX)


def _ambiguous() -> set[str]:
    """`src/firelane/` 에 같은 이름이 있는 도구. `import x` 로는 구분이 안 된다."""
    src = {p.stem for p in (ROOT / "src").rglob("*.py")} if (ROOT / "src").exists() else set()
    return {p.stem for p in _tools() if p.suffix == ".py"} & src


def _docstring_lines(src: str) -> set[int]:
    """모듈 · 클래스 · 함수 **독스트링**이 차지하는 줄 번호.

    ★ 2026-09-24 (DECISIONS §239). ③ 이 주석만 걸렀다. `#` 로 시작하는 줄은
      뺐지만 `\"\"\"…\"\"\"` 안의 산문은 **코드로 셌다.** 그래서 도구 다섯이
      시험 파일 독스트링의 한 줄로 「배선됐다」가 됐다 —

          doctor        tests/test_norm_wiring.py 머리말의 설명 한 줄
          jijeok_probe  tests/test_shp_zip_multi_bbox.py 머리말
          ledger_feeds  tests/test_declaration_reality.py · _sync.py 머리말
          route_probe   tests/test_declaration_reality.py 머리말

      ③ 을 고친 주석이 바로 위에 있는데 **같은 병의 다른 꼴이 남아 있었다.**
      독스트링만 뺀다 — 다른 문자열은 뺄 수 없다. `subprocess.run([...,
      str(ROOT / "tools" / "x.py")])` 의 문자열은 **진짜 호출**이다.
    """
    import ast
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    out: set[int] = set()
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)):
            continue
        body = getattr(n, "body", None)
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            out.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return out


#: 셸에서 **찍기만 하는** 명령. `printf '… tools/serve.py'` 는 안내문이지 실행이 아니다.
_PRINTS = re.compile(r"^\s*(?:printf|echo)\b")


def _scan() -> list[tuple[str, int, str]]:
    """호출자가 될 수 있는 파일들의 **실행되는 줄**만 모은다.

    주석 · 독스트링 · 셸 안내문(`printf` · `echo`)은 뺀다. 셋 다 이름을
    **적을 뿐** 부르지 않는다.
    """
    files = [ROOT / r for r in CALLERS]
    for d in (".github/workflows", "tests"):
        base = ROOT / d
        if base.exists():
            files += [p for p in base.rglob("*")
                      if p.is_file() and p.suffix in (".yml", ".yaml", ".py")]
    out = []
    for p in files:
        if not p.is_file():
            continue
        src = p.read_text(encoding="utf-8", errors="ignore")
        doc = _docstring_lines(src) if p.suffix == ".py" else set()
        for i, line in enumerate(src.splitlines(), 1):
            s = line.strip()
            if not s or s.startswith(_COMMENT) or i in doc or _PRINTS.match(line):
                continue
            out.append((str(p.relative_to(ROOT)), i, s))
    return out


def call_sites(name: str, lines: list[tuple[str, int, str]] | None = None) -> list[str]:
    """도구 하나를 **실제로 부르는** 자리들. 없으면 빈 목록."""
    lines = _scan() if lines is None else lines
    stem = name.rsplit(".", 1)[0]
    path_rx = re.compile(rf"tools/{re.escape(name)}(?![\w.])")
    # ★ `import <stem>` 은 `src/firelane/` 에 같은 이름이 없을 때만 인정한다.
    imp_rx = (None if stem in _ambiguous()
              else re.compile(rf"(?:^|;)\s*(?:from|import)\s+{re.escape(stem)}\b"))
    # ★ 2026-09-24 (DECISIONS §239). `importlib` 로 **조립해서** 부르는 자리를
    #   못 봤다. `spec_from_file_location("x", ROOT / "tools" / "x.py")` 는
    #   `tools/x.py` 라는 **리터럴을 만들지 않는다.** 그래서 실제로 CI 에서
    #   도는 넷(baseline · ledger_schema · skeleton_compare · wmax_audit)이
    #   「사람이 부른다」 면제에 앉아 있었다 — 면제는 사각지대이므로
    #   **거짓 면제는 이유 없이 넓은 사각지대**다.
    dyn_rx = re.compile(
        rf'(?:spec_from_file_location|_load|_mod|_tool|import_module)\s*\([^)]*'
        rf'["\']{re.escape(stem)}(?:\.py)?["\']')
    hits = []
    for f, i, s in lines:
        # ★ 2026-09-24 (DECISIONS §231). 종전에는 `f.endswith(name)` 이었다.
        #   그러면 `tests/test_proposal_pdf.py` 가 `proposal_pdf.py` 로 끝나므로
        #   **그 도구의 시험이 호출자에서 통째로 빠졌다.** 도구가 제 시험
        #   하나로만 배선돼 있으면 「아무 데서도 안 부른다」가 나온다.
        #   빼야 하는 것은 **도구 자신**이지 이름이 그것으로 끝나는 파일이 아니다.
        if f == f"tools/{name}":
            continue
        if path_rx.search(s) or (imp_rx and imp_rx.search(s)) or dyn_rx.search(s):
            hits.append(f"{f}:{i}")
    return hits


def test_every_tool_is_called_somewhere():
    """도구가 어딘가에서 **실행되는가.** 목록에만 있는 것은 배선이 아니다.

    ★ 범위는 `.py` 뿐이 아니다. `.sh` · `.mjs` 도 도구다.
    """
    lines = _scan()
    bad = [f"  tools/{p.name} 를 아무 데서도 안 부른다"
           for p in _tools()
           if p.stem not in EXEMPT and p.name not in EXEMPT
           and not call_sites(p.name, lines)]
    assert not bad, (
        "만들어놓고 안 부르는 도구가 있다.\n" + "\n".join(bad)
        + "\n\n  verify.sh 에 걸거나, 자동 실행하면 안 되는 이유를\n"
          "  EXEMPT 에 사유와 함께 적어라. **사유 없이 넣지 마라** —\n"
          "  그러면 이 검사가 항상 통과하는 검사가 된다(DECISIONS §69).")


def test_exemptions_are_not_dead():
    """면제가 **아직 필요한가.** 실제로 불리는데 면제에 남아 있으면 거짓이다.

    ★ 2026-09-20 실측 — 면제 31 중 **12** 가 이미 불리고 있었다. 면제된
      도구는 배선을 끊어도 아무도 안 운다. 즉 **면제 자체가 사각지대**이고,
      낡은 면제는 그 사각지대를 이유 없이 넓힌다.
    ★ 2026-09-13 에 사람이 여섯을 손으로 뺐다. 강제자를 안 세웠고 일곱 달도
      아니고 **일주일 만에 열둘로 늘었다.** 손으로 고친 것은 되돌아온다.
    """
    lines = _scan()
    dead = []
    for n in sorted(EXEMPT):
        for cand in (f"{n}.py", f"{n}.sh", f"{n}.mjs", n):
            if (ROOT / "tools" / cand).is_file():
                hits = call_sites(cand, lines)
                if hits:
                    dead.append(f"  {n:<18} {', '.join(hits[:3])}")
                break
    assert not dead, (
        f"실제로 불리는데 면제 목록에 남아 있다. {len(dead)}건\n" + "\n".join(dead)
        + "\n\n  면제는 **사각지대**다 — 면제된 도구는 배선이 끊겨도 안 운다.\n"
          "  불리게 됐으면 EXEMPT 에서 빼라. 그래야 그 배선을 누가 끊으면 운다.")


def test_exempt_entries_are_real():
    """EXEMPT 가 없는 도구를 들면 목록이 낡은 것이다. 양방향이다."""
    # ★ 2026-09-20. 여기도 `.py` 뿐이었다. 면제 범위와 유령 검사 범위가
    #   갈리면 `.sh` 면제가 항상 유령으로 뜨거나 영영 안 걸린다.
    have = {p.stem for p in _tools()}
    ghost = sorted(n for n in EXEMPT if n not in have)
    assert not ghost, (
        f"EXEMPT 가 없는 도구를 든다 — {', '.join(ghost)}\n"
        "  도구를 지웠으면 그 줄도 지워라.")


def test_exempt_entries_carry_a_reason():
    """사유가 비면 면제가 아니라 방치다."""
    blank = sorted(n for n, why in EXEMPT.items() if not (why or "").strip())
    assert not blank, f"사유 없는 EXEMPT — {', '.join(blank)}"


# ★ 2026-09-16. README 는 *"재현적이면 `tools/` 에 두고 verify.sh 에 배선하고 README 에
#   적는다"* 고 적는다. 위 검사는 배선 반쪽만 봤다. 적는 반쪽에 강제자가 없어서
#   `bridge_audit` · `its_linkmap` · `matchcheck` · `merge_batch.sh` 넷이 README 에 없었다 —
#   머지 진입점까지 찾을 곳이 없었다(DECISIONS §168).
README_EXEMPT: dict[str, str] = {}


def test_every_tool_is_named_in_readme():
    """`tools/` 의 도구가 README 에 이름으로 적혀 있는가. 배선과 별개의 반쪽이다."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    miss = sorted(p.name for p in (ROOT / "tools").iterdir()
                  if p.is_file() and p.suffix in (".py", ".sh", ".mjs")
                  and p.name not in README_EXEMPT and p.name not in text)
    assert not miss, (
        "README 에 없는 도구가 있다 — " + ", ".join(miss)
        + "\n\n  README `## 도구` 또는 `### 대조 도구` 에 한 줄로 적어라.\n"
          "  일회성이면 저장소 밖(`~/oneoff/`)으로 옮겨라 — README 규약이 둘 중 하나다.")


def _argv_flags(src: str) -> list[str]:
    """`"--x" in sys.argv` 꼴로 읽는 플래그. selftest 가 같은 함수를 쓴다."""
    import ast
    out = []
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.Compare) and len(n.ops) == 1
                and isinstance(n.ops[0], ast.In)
                and isinstance(n.left, ast.Constant)
                and isinstance(n.left.value, str) and n.left.value.startswith("-")
                and ast.unparse(n.comparators[0]).endswith("sys.argv")):
            out.append(n.left.value)
    return out


def test_no_tool_reads_flags_by_membership():
    """`"--x" in sys.argv` 는 **오타를 조용히 무시한다.**

    ★ 2026-09-24 (PLAN §13 W13-6 · DECISIONS §243). 여섯이 그랬다 —
      `render_figures.py --chek` 은 `check=False` 로 떨어져 **검사 대신 그림
      파일을 덮어썼고**, `commit_policy.py --traked` 는 전량 대신 스테이지만
      보고 통과했다. 둘 다 「안 한 일을 한 것처럼」 끝난다.

    ★ argparse 는 모르는 인자에 스스로 운다. 직접 구현할 일이 아니다(4족).
    """
    # ★ `tools/` 만 보지 않는다. `python -m firelane.x` 로 치는 모듈도 같은 병에
    #   걸리고, 좁게 훑는 검사는 넓힐 때까지 그 절반을 영영 안 본다(deadcheck ⑤).
    files = sorted((ROOT / "tools").glob("*.py")) + \
        sorted((ROOT / "src/firelane").rglob("*.py")) + \
        sorted((ROOT / "tests").glob("*.py"))
    bad = {p.relative_to(ROOT).as_posix(): f for p in files
           if (f := _argv_flags(p.read_text(encoding="utf-8")))}
    assert not bad, (
        "멤버십으로 플래그를 읽는다 — 오타가 조용히 무시된다:\n  "
        + "\n  ".join(f"{k}  {v}" for k, v in bad.items())
        + "\n  argparse 로 옮겨라. 모르는 인자에 스스로 운다.")


def test_the_flag_matcher_is_alive():
    """**목표에 닿는 날 빨개지는가.** 실물이 다 깨끗해도 판별식이 사는지 본다."""
    assert _argv_flags('x = "--check" in sys.argv') == ["--check"]
    assert _argv_flags('if "--sync" in sys.argv:\n    pass') == ["--sync"]
    assert _argv_flags('x = "--check" in argv') == [], "sys.argv 가 아닌데 잡는다"
    assert _argv_flags('x = "check" in sys.argv') == [], "플래그가 아닌데 잡는다"
    assert _argv_flags('p.add_argument("--check")') == []


def test_the_compare_tool_list_has_one_home():
    """「대조 도구」 목록이 두 문서에 사본으로 살면 갈린다. 실제로 아홉이 갈렸다.

    ★ 2026-09-24 (DECISIONS §243). README 와 MASTER §14-5 가 같은 목록을
      각자 들고 있었다 — README 에만 여섯, MASTER 에만 셋. 어느 쪽도
      상대를 안 봤고 대조하는 검사가 없었다. README 를 정본으로 두고
      (강제자가 그쪽에 있다 — 바로 위 `test_every_tool_is_named_in_readme`)
      MASTER 는 가리키기만 한다.

    ★ 보는 것은 **MASTER §14-5 안에 `tools/*.py` 호출줄이 있는가** 하나다.
      목록이 돌아오는 유일한 꼴이 그것이고, 문장 대조가 아니라 꼴 대조라
      사람이 말을 바꿔 써도 안 깨진다.
    """
    import re
    m = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    a = m.index("### 14-5.")
    b = m.index("### 14-6.", a)
    dup = sorted(set(re.findall(r"tools/([\w_]+\.(?:py|sh|mjs))", m[a:b])))
    assert not dup, (
        "MASTER §14-5 가 대조 도구 목록의 **사본**을 다시 들었다 — "
        + ", ".join(dup) + "\n"
        "  목록의 집은 README 의 「대조 도구」 블록 하나다.\n"
        "  여기서는 가리키기만 해라 — 두 벌이 되면 갈린다(2026-09-24 에 아홉이 갈렸다).")


def test_readme_exempt_entries_are_real_and_reasoned():
    have = {p.name for p in (ROOT / "tools").iterdir() if p.is_file()}
    ghost = sorted(n for n in README_EXEMPT if n not in have)
    blank = sorted(n for n, why in README_EXEMPT.items() if not why.strip())
    assert not ghost and not blank, f"없는 도구 {ghost} · 사유 없음 {blank}"


# ── 판별식 카나리아 — 합성 입력으로 **직접** 흔든다 ───────────────
#
# ★ 2026-09-24 (DECISIONS §239). 위 두 시험은 실물 트리를 본다. 실물이 다
#   맞으면 초록이고, **판별식이 망가져도 초록**이다. 판별식 자체를 여기서 문다.
def test_a_docstring_mention_is_not_a_call_site():
    """머리말 산문에 이름이 적힌 것은 **호출이 아니다.**

    이것이 실제로 넷을 통과시켰다(doctor · jijeok_probe · ledger_feeds · route_probe).
    """
    # ★ 합성 이름을 쓴다. 실제 도구 이름을 **코드 줄**에 적으면 이 파일이
    #   그 도구의 호출자가 되어 `test_exemptions_are_not_dead` 가 운다 —
    #   검사를 시험하다 검사를 어기는 자리다. 실제 사례는 위 독스트링이 든다.
    src = ('"""머리말.\n\n실물 대조는 `tools/zq7_absent.py` 가 맡는다.\n"""\n'
           'x = 1\n')
    doc = _docstring_lines(src)
    assert doc == {1, 2, 3, 4}, doc
    assert 5 not in doc, "독스트링 밖까지 먹었다 — 진짜 호출이 사라진다"


def test_a_function_docstring_is_also_skipped():
    src = 'def f():\n    """`tools/zq7_absent.py` 를 참고할 것."""\n    return 1\n'
    assert _docstring_lines(src) == {2}


def test_a_real_string_argument_is_not_skipped():
    """★ 반대 방향. `subprocess.run([..., "tools/x.py"])` 는 **진짜 호출**이다."""
    src = 'import subprocess\nsubprocess.run(["python", "tools/zq7_absent.py"])\n'
    assert _docstring_lines(src) == set(), "문자열 인자까지 먹으면 배선이 통째로 안 보인다"


def test_a_printed_line_is_not_a_call_site():
    """셸 안내문은 실행이 아니다 — `verify.sh` 의 `printf` 가 그랬다."""
    assert _PRINTS.match("    printf '    uv run python tools/zq7_absent.py\\n'")
    assert _PRINTS.match("  echo tools/zq7_absent.py")
    assert not _PRINTS.match("  uv run python tools/zq7_absent.py check")


def test_an_importlib_call_site_is_seen():
    """`spec_from_file_location` 으로 **조립**해 부르는 자리도 호출이다.

    이것을 못 봐서 면제 셋이 거짓으로 살아 있었다(ledger_schema ·
    skeleton_compare · wmax_audit — 셋 다 CI 에서 실제로 돈다).
    """
    lines = [("tests/test_x.py", 9,
              'spec = importlib.util.spec_from_file_location("wmax_audit", '
              'ROOT / "tools" / "wmax_audit.py")')]
    assert call_sites("wmax_audit.py", lines) == ["tests/test_x.py:9"]
    assert call_sites("zq7_absent.py", lines) == [], "아무 이름에나 걸리면 그물이 빈다"


def test_the_loader_helper_form_is_seen():
    """`_load("x")` 꼴도 본다 — 이 저장소 시험들이 실제로 쓰는 축약이다."""
    lines = [("tests/test_y.py", 3, 'mod = _load("skeleton_compare")')]
    assert call_sites("skeleton_compare.py", lines) == ["tests/test_y.py:3"]


def test_a_by_path_loader_registers_the_module():
    """경로로 적재한 모듈을 **`sys.modules` 에 등록하는가.**  (§258-10)

    ★ 2026-09-26 실기 사고. `tests/test_dest_scope.py` 가 `tools/fixture_recut.py`
      를 경로로 적재했는데 등록을 안 했다. 그 도구에 `@dataclass` 가 있고,
      `dataclasses` 는 문자열 주석을 풀려고 `sys.modules[cls.__module__]` 를
      되짚는다 — 없으면 `AttributeError: 'NoneType' object has no attribute
      '__dict__'` 로 죽는다. 전수 verify 의 **유일한 실패**가 그것이었다.

    ★ **지식은 이미 저장소에 있었다.** `tests/test_guards.py` 가 같은 자리에
      「@dataclass 는 cls.__module__ 로 sys.modules 를 되짚는다. 등록 없이
      exec_module 하면 AttributeError 로 죽는다」고 적어 뒀다. 주석으로만 있고
      **강제자가 없어서** 열여덟 파일이 그 함정을 밟은 채로 살아 있었다.
      터지는 날은 그 도구가 `@dataclass` 를 갖는 날이라 **지연 신관**이다.

    ★ 2026-09-26. 처음 판은 `tests/` 만 훑었고 `deadcheck ⑤`(좁은 범위)가 그것을
      잡았다 — **강제자가 제 이름보다 좁았다.** 넓히자 `tools/` 에서 넷이 더
      나왔다(`docx_check` · `docx_figs` · `pull_data` · `treecheck`).
      「범위가 이름보다 좁다」를 잡으려고 만든 배치에서 또 그 족을 저질렀고,
      이번엔 **사람이 아니라 검사가** 잡았다.

    밖  등록 **이름**이 옳은지는 안 본다(`spec.name` 을 쓰는 것이 관례다).
        평범한 `import` 는 대상이 아니다 — 경로 적재만 본다.
    """
    import ast as _ast

    bad = []
    scan = [q for d in ("src", "tools", "tests") for q in sorted((ROOT / d).rglob("*.py"))]
    for p in scan:
        tree = _ast.parse(p.read_text(encoding="utf-8"))
        loads = [n for n in _ast.walk(tree)
                 if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)
                 and n.func.attr == "module_from_spec"]
        if not loads:
            continue
        regs = [n for n in _ast.walk(tree)
                if isinstance(n, _ast.Subscript) and isinstance(n.value, _ast.Attribute)
                and n.value.attr == "modules"]
        if len(regs) < len(loads):
            bad.append(f"  {p.relative_to(ROOT)}  적재 {len(loads)} · 등록 {len(regs)}")
    assert not bad, (
        "경로로 적재하고 `sys.modules` 에 안 넣었다\n" + "\n".join(bad)
        + "\n\n  `spec.loader.exec_module(m)` **앞에** 한 줄 넣는다 —\n"
          "      sys.modules[spec.name] = m\n"
          "  `@dataclass` 가 `cls.__module__` 로 되짚는다. 없으면 AttributeError 다.\n"
          "  지금 안 터져도 그 도구가 dataclass 를 갖는 날 터진다 — 지연 신관이다.")
