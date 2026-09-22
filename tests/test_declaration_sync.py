"""선언 ↔ 실물 역방향 정합.

`test_reproducibility.py` 는 **문서가 가리키는 것이 실재하는가**를 본다.
이 파일은 반대다 — **실재하는 것이 선언돼 있는가**를 본다.

한 방향만 검사하면 드리프트가 조용히 쌓인다. 2026-08-26 전수 대조에서
같은 형태의 구멍이 다섯 나왔다.

    CI            `test_doc_style` 이 MASTER §0-1 의 강제자로 지목돼 있는데
                  워크플로가 파일을 열거해 부르느라 빠져 있었다
    verdict_rule  스키마가 규칙 7개 중 6개만 적었다. 빠진 것은
                  `정규표본 1개 -> clear 보류`(DM02825 방어)
    config.js     "임계값은 반드시 같아야 한다"고 선언하고 끝났다
    README §7     CI 가 직접 부르는 도구 다섯이 목록에 없었다
    PLAN §1       행 번호 26·27 결번, 22 가 맨 끝. 본문이 번호로
                  서로를 가리키므로(24행이 "23번") 순서가 곧 의미다

★ 규칙을 고칠 때는 정본을 고친다. 여기 값을 맞추는 것이 아니다.
"""

from __future__ import annotations

import ast
import fnmatch
import functools
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PLAN = ROOT / "docs" / "PLAN.md"


def _const(rel: str, names: set[str]) -> dict[str, object]:
    """모듈을 임포트하지 않고 최상위 상수를 읽는다. GIS 의존 없이 돈다."""
    out: dict[str, object] = {}
    for node in ast.parse((ROOT / rel).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in names:
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def _params() -> dict[str, float]:
    p = _const("src/firelane/seg/params.py", {"TRUCK", "PARK", "CCTV_RANGE"})
    missing = {"TRUCK", "PARK", "CCTV_RANGE"} - set(p)
    assert not missing, f"seg/params.py 에서 {sorted(missing)} 를 읽지 못했다"
    return {k: float(v) for k, v in p.items()}  # type: ignore[arg-type]


def _verdict_rule() -> list[str]:
    r = _const("src/firelane/seg/geom.py", {"VERDICT_RULE"}).get("VERDICT_RULE")
    assert r, "seg/geom.py 에 VERDICT_RULE 이 없다"
    return list(r)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────
# 1. 자동화가 부르는 도구가 README 에 있는가
# ─────────────────────────────────────────────────────────────

# ★ 2026-09-18 (W1). `_deploy.yml` 을 더했다. 배포 본문을 거기로 옮기면서
#   `pages.yml` 에는 `tools/` 호출이 하나도 안 남았다 — 빼면 `render_workflow.py` ·
#   `stage_pages.py` 가 이 검사의 그물 밖으로 나간다. 부르는 자리를 따라간다.
CALLERS = (".github/workflows/contract.yml", ".github/workflows/pages.yml",
           ".github/workflows/_deploy.yml", ".github/actions/stage-site/action.yml",
           "tools/verify.sh", "tools/ship.py")


def test_readme_lists_tools_the_automation_calls():
    """CI · verify · ship 이 부르는 도구는 README 에서 이름으로 찾을 수 있어야 한다.

    ★ README §7 은 전수 색인이 아니라 요약이다. 그래서 **모든** 파일을
      요구하지 않는다. 다만 자동화가 의존하는 것은 다르다 — 빨간불이
      떴을 때 다음 사람이 그 도구가 무엇인지 알아야 한다.
      `test_seg_*.py` 같은 글롭 표기는 그대로 인정한다.
    """
    txt = "".join((ROOT / c).read_text(encoding="utf-8")
                  for c in CALLERS if (ROOT / c).exists())
    called = sorted(set(re.findall(r"tools/([A-Za-z0-9_]+\.(?:py|mjs|sh))", txt)))
    assert called, "자동화 정의에서 도구 호출을 찾지 못했다"

    rd = README.read_text(encoding="utf-8")
    globs = [t for t in re.findall(r"[A-Za-z0-9_*./-]+\.(?:py|mjs|sh)", rd) if "*" in t]
    missing = [c for c in called
               if c not in rd and not any(fnmatch.fnmatch(c, g) for g in globs)]
    assert not missing, (
        f"자동화가 부르는데 README 에 없는 도구 {len(missing)}개\n  "
        + "\n  ".join(missing))


def test_readme_globs_still_match_something():
    """글롭 표기가 아무것도 안 가리키게 되면 목록이 거짓이 된다."""
    rd = README.read_text(encoding="utf-8")
    dead = []
    for g in {t for t in re.findall(r"[A-Za-z0-9_*./-]+\.(?:py|mjs|sh)", rd) if "*" in t}:
        if not any(fnmatch.fnmatch(p.name, g) for p in ROOT.rglob("*")
                   if p.is_file() and "__pycache__" not in str(p)):
            dead.append(g)
    assert not dead, f"실재 파일을 가리키지 않는 글롭 표기: {dead}"


# ─────────────────────────────────────────────────────────────
# 2. 산출물 스키마가 코드 정본과 같은가
# ─────────────────────────────────────────────────────────────

SCHEMAS = ("data/processed/segments.schema.json", "web/data/segments.schema.json")


@pytest.mark.parametrize("rel", SCHEMAS)
def test_schema_verdict_rule_matches_code(rel: str):
    """스키마는 산출물과 함께 배포된다. 규칙이 빠지면 외부 재현이 어긋난다.

    ★ 정본은 `seg/geom.py::VERDICT_RULE` 이다. 어긋나면 파이프라인을
      다시 돌려 스키마를 재생성한다. 손으로 JSON 을 고치지 않는다.
    """
    path = ROOT / rel
    assert path.exists(), f"{rel} 가 없다 — 커밋된 스키마다"
    got = json.loads(path.read_text(encoding="utf-8")).get("verdict_rule")
    assert got == _verdict_rule(), (
        f"{rel} 의 verdict_rule 이 seg/geom.py 와 다르다\n"
        f"  스키마 {len(got or [])}줄 · 정본 {len(_verdict_rule())}줄")


@pytest.mark.parametrize("rel", SCHEMAS)
def test_schema_params_match_params_module(rel: str):
    """스키마 `params` 블록도 `seg/params.py` 가 정본이다."""
    path = ROOT / rel
    assert path.exists(), f"{rel} 가 없다 — 커밋된 스키마다"
    p = _params()
    got = json.loads(path.read_text(encoding="utf-8")).get("params", {})
    for key, name in (("truck_width_m", "TRUCK"), ("park_occupancy_m", "PARK"),
                      ("cctv_range_m", "CCTV_RANGE")):
        if key in got:
            assert float(got[key]) == p[name], (
                f"{rel} — {key} 가 {got[key]}, params.py 는 {p[name]}")


# ─────────────────────────────────────────────────────────────
# 3. UI 임계값이 파이프라인 정본과 같은가
# ─────────────────────────────────────────────────────────────

def test_config_js_thresholds_match_params():
    """`web/config.js` 머리말이 "반드시 같아야 한다"고 선언한다. 그걸 검사한다.

    UI 는 표시용 사본이라 자동 생성하지 않는다. 대신 임계값이 문면에
    그대로 박혀 있으므로, 정본에서 만든 문자열이 파일에 있는지 본다.
    임계값을 바꾸면 이 테스트가 UI 갱신을 강제한다.
    """
    cfg = (ROOT / "web" / "config.js").read_text(encoding="utf-8")
    p = _params()
    truck, clear_at, rng = p["TRUCK"], p["TRUCK"] + 2 * p["PARK"], p["CCTV_RANGE"]

    want = {
        f"임계값({truck:.1f} / {clear_at:.1f} / {rng:.1f})": "머리말 선언",
        f"{truck:.1f}m 미만": "blocked 설명",
        f"{clear_at:.1f}m 이상": "clear 설명",
        # ★ 2026-09-22 (DECISIONS §218-6) `radius:{rng}`(markers[].cover — CCTV 커버리지 원)를
        #   unknown 설명으로 옮겼다. 그 원을 그리던 옛 지도를 걷어내며 markers 블록을 지웠다 —
        #   읽는 코드가 없는 사본을 이 시험 하나 때문에 남기지 않는다. 25m 는 설명에 산다.
        f"유효범위 {rng:g}m 밖": "unknown 설명",
    }
    missing = [f"{s!r} ({why})" for s, why in want.items() if s not in cfg]
    assert not missing, (
        "web/config.js 가 params.py 임계값과 어긋난다\n  " + "\n  ".join(missing)
        + f"\n\n  정본 — TRUCK={truck} PARK={p['PARK']} CCTV_RANGE={rng}")


# ─────────────────────────────────────────────────────────────
# 4. PLAN 이 스스로를 정확히 가리키는가
# ─────────────────────────────────────────────────────────────

def _plan_rows() -> list[int]:
    lines = PLAN.read_text(encoding="utf-8").splitlines()
    start = next(k for k, x in enumerate(lines) if x.startswith("## 1. 남은 일"))
    stop = next(k for k in range(start + 1, len(lines)) if lines[k].startswith("### "))
    return [int(m.group(1)) for x in lines[start:stop]
            if (m := re.match(r"\| (\d+) \|", x))]


def test_plan_row_numbers_are_unique_and_sorted():
    """`§1` 표의 번호는 **영구 식별자**다. 유일하고 오름차순이면 된다.

    ★ 2026-09-20 (DECISIONS §205). 종전 이름은
      `test_plan_row_numbers_are_contiguous_and_sorted` 였고 **결번을 빨간불로
      셌다.** 그래서 행을 지울 때마다 `plan_renumber.py --apply` 로 뒤를 당겨야 했다.

      그 도구는 `docs/PLAN.md` **하나만** 연다. 그런데 §1 행을 가리키는 인용은
      밖에 **83곳** 있다 — `DECISIONS` 70 · `MASTER` 7 · `sources.yaml` 6.
      즉 당길 때마다 그 83곳이 **조용히 다른 행을 가리켰다.**
      `plan_renumber.py` 안의 주석이 그 사고를 이미 적고 있었다(`§1 #16`).
      방어가 있었지만 **PLAN 안의 참조만** 봤다.

      DECISIONS 70곳은 append-only 역사라 고칠 수 없다. 그러면 답은 하나다 ——
      **당기지 않는다.** 결번을 허용하고 번호를 영구 식별자로 만든다.

    ★ 그리고 이것이 **§1 이 줄어들 수 있게 만든다.** 지금까지 닫힌 행이
      목록에 그대로 앉아 있던 이유가 「지우면 뒤가 당겨진다」였다.
    """
    nums = _plan_rows()
    assert nums, "PLAN §1 에서 표 행을 찾지 못했다"
    assert nums == sorted(nums), f"번호가 오름차순이 아니다: {nums}"
    dup = sorted({n for n in nums if nums.count(n) > 1})
    assert not dup, (
        f"중복 번호: {dup}.\n"
        "  같은 번호가 두 행에 있으면 밖의 인용이 어느 쪽인지 모른다.\n"
        "  ★ 번호는 **다시 쓰지 않는다** — 지운 번호는 비워 둔다(§0-2).")


def test_plan_renumber_cannot_shift_numbers_any_more():
    """재배번 경로가 되살아나지 않았는가.

    ★ 손으로 되돌리기 쉬운 자리다 — 결번을 보면 「당겨야지」가 먼저 떠오른다.
      그 순간 밖의 83곳이 조용히 어긋난다. **없앴다는 사실을 검사가 든다.**
    """
    src = (ROOT / "tools" / "plan_renumber.py").read_text(encoding="utf-8")
    assert "폐지됐다" in src, "`--apply` 폐지 안내가 사라졌다"
    assert "old2new" not in src, (
        "`plan_renumber.py` 에 재배번 치환이 되살아났다.\n"
        "  §1 번호를 당기면 `DECISIONS`(70) · `MASTER`(7) · `sources.yaml`(6) 의\n"
        "  인용 83곳이 조용히 다른 행을 가리킨다. 그중 70곳은 고칠 수 없는 역사다.")


def test_master_and_decisions_bare_refs_resolve():
    """문서명 없는 `§N` 은 MASTER 를 가리킨다(MASTER §0-2).

    ★ 2026-09-02. `PLAN` 에만 이 검사가 있었다(`test_plan_section_refs_resolve`).
      규약은 세 문서 전부에 적용되는데 강제자가 하나뿐이었다 — `PLAN #69` 가
      그 공백을 들고 있었고 이것이 그것을 닫는다(DECISIONS §103).

    ★ 자기 문서를 가리키는 것도 허용한다. `DECISIONS` 안의 `§86` 은
      맥락상 자기 절이고, MASTER 절 번호와 겹치면 어느 쪽인지 사람이
      가린다 — 여기서는 **어디에도 없는 번호**만 잡는다.
    """
    # ★ 세 문서 합집합으로 푼다. `MASTER` 가 `DECISIONS §79` 를 bare `§79`
    #   로 쓰는 관행이 이미 굳어 있고, 그것까지 잡으면 수백 곳이 걸려
    #   사람이 검사를 끈다(§78-4). 여기서 잡는 것은 **어디에도 없는 번호**다.
    master_secs: set[str] = set()
    for _rel in ("docs/MASTER.md", "docs/PLAN.md", "docs/DECISIONS.md"):
        master_secs |= set(re.findall(
            r"^#{2,3} ([0-9]+(?:-[0-9a-z]+)?)\. ",
            (ROOT / _rel).read_text(encoding="utf-8"), re.M))
    for rel in ("docs/MASTER.md", "docs/DECISIONS.md"):
        txt = (ROOT / rel).read_text(encoding="utf-8")
        own = set(re.findall(r"^#{2,3} ([0-9]+(?:-[0-9a-z]+)?)\. ", txt, re.M))
        bad = set()
        # ★ 들여쓴 블록은 **인용**이다. `DECISIONS §18` 이 무너진 번호
        #   체계를 그대로 옮겨 적는데, 실체가 없는 것이 그 문장의 요지다.
        #   과거를 적는 문서에서 과거를 위반으로 세면 그 문서를 못 쓴다.
        body = "\n".join(l for l in txt.splitlines()
                          if not (l.startswith("    ") and l.strip()))
        for m in re.finditer(r"(?<![A-Za-z])§\s?([0-9]+(?:-[0-9a-z]+)?)", body):
            # 앞에 문서명이 붙은 것은 그 문서 소관이다.
            head = body[max(0, m.start() - 12):m.start()]
            if any(k in head for k in ("MASTER", "PLAN", "DECISIONS", "기획서",
                                       "workflow", "playbook")):
                continue
            num = m.group(1)
            if num not in master_secs and num not in own:
                bad.add(num)
        assert not bad, (
            f"{rel} 안에 실체가 없는 절 참조: {sorted(bad)}\n"
            "  문서명 없는 `§N` 은 MASTER 를 가리킨다(MASTER §0-2).\n"
            "  다른 문서면 `PLAN §4-5` 처럼 소속을 적어라.")


def test_plan_section_refs_resolve():
    """`§N` · `§N-M` 참조가 이 문서 안에 실재해야 한다.

    다른 문서를 가리킬 때는 `MASTER §16-1` 처럼 소속을 앞에 적는다.
    2026-08-26 에 있지도 않은 하위 절 번호(당시 `13-9` 표기)가 실체 없이
    남아 있었고 실제로는 `§8-1` 이었다.

    ★ 2026-09-18. 위에서 `§` 를 뗐다. PLAN §13 이 신설되며 `### 13-M.` 이
      1 부터 연속 다섯이 되자 §13 이 `test_docref` 의 번호 체계 대상이
      됐고, 그 순간 이 줄의 `13-9` 표기가 **죽은 참조로 드러났다.** 없던
      결함이 생긴 것이 아니라 가려져 있던 것이 보이게 된 것이다 —
      그 검사가 목록을 손으로 관리하지 않는 이유가 이것이다.
    """
    text = PLAN.read_text(encoding="utf-8")
    h2 = set(re.findall(r"^## (\d+)\.", text, re.M))
    h3 = set(re.findall(r"^### (\d+-[0-9a-z]+)\.", text, re.M))

    bad = set()
    for m in re.finditer(r"§(\d+)(?:-([0-9a-z]+))?", text):
        # 다른 문서를 가리키면 바로 앞에 소속이 붙는다 — `MASTER §16-1`.
        # 앞에 조사나 여는 괄호가 붙어도(`잡는다(MASTER §16-1`) 인정한다.
        before = text[max(0, m.start() - 12):m.start()]
        if re.search(r"(MASTER|DECISIONS|README)\s*$", before):
            continue
        top, sub = m.group(1), m.group(2)
        if sub:
            if f"{top}-{sub}" not in h3 and top not in h2:
                bad.add(f"§{top}-{sub}")
        elif top not in h2:
            bad.add(f"§{top}")
    assert not bad, (
        f"PLAN 안에 실체가 없는 절 참조: {sorted(bad)}\n"
        "  다른 문서를 가리키는 것이면 `MASTER §N` 처럼 소속을 적는다.")



def _code_only(src: str) -> str:
    """FL_AST_REFCHECK — 주석과 docstring 을 뺀 코드만 돌려준다.

    ★ 종전에는 원문을 통째로 grep 했다. 그러면 **주석에 키 이름만 적어도
      '코드가 참조한다'** 가 된다. 그 오류는 미참조 수를 줄이는 쪽으로
      틀리므로 낡음을 숨긴다 — 강제자가 정반대로 작동한 셈이다.

      실제로 2026-08-26 손 대조가 `enforcement` 를 "코드에 붙었다" 로
      판정했는데, 근거는 `normalize_raw.py` 의 주석 한 줄이었다.
      같은 방법으로 만든 이 테스트가 그 오판을 숫자로 굳혔다.
      대장의 `enforcement.feeds` 는 처음부터 참조 0곳이라 적고 있었다 —
      **대장이 맞고 PLAN 이 틀렸다.**

    ★ 문자열 리터럴은 남긴다. 소비자는 이름을 문자열로 부르므로
      그것까지 지우면 이번엔 반대 방향으로 틀린다. 지우는 것은
      docstring 과 주석, 그리고 `RULES` 표 셋이다.

    ★ 2026-09-07. `RULES` 를 더 걷는다. **그것은 소비가 아니다.**
      취득처가 준 파일명을 정규명으로 바꾸는 표이고, 정규명 문법이
      `{provider}_{dataset}_{scope}_{vintage}` 라 **대장 키를 부분문자열로
      품는다.** `gjcity_school_zone_...` 안에 `school_zone` 이 들어 있다.

      그래서 RULES 에 줄을 추가하면 그 데이터셋이 자동으로 "참조됨" 이
      됐다. 실제로 PLAN §1 #23 이 *"2026-09-06 에 12종이 됐다 —
      `school_zone` 이 코드에 붙었다"* 고 적었는데, `school_zone` 은
      `src`·`tools` 어디에도 없다. **파일명 규칙에 이름이 들어간 것을
      코드 참조로 읽었고 그 오판이 문서에 근거까지 붙어 기록됐다.**
      `bin_trash` · `bin_cloth` 도 같은 이유로 숨어 있었다.

      2026-08-26 의 `enforcement` 오판(주석 한 줄을 참조로 셈)과 같은
      형태다. 그때는 주석을 걷어 고쳤고 이번에는 RULES 를 걷는다 —
      **미참조 수를 줄이는 쪽으로 틀리는 오류는 낡음을 숨긴다.**
    """
    import ast
    import re as _re

    # RULES 표는 원본 파일명 목록이다. ast 로는 대입문이라 남으므로 먼저 뗀다.
    src = _re.sub(r"^RULES: list\[tuple\[str, str, str\]\] = \[.*?^\]",
                  "", src, flags=_re.S | _re.M)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr)
                    and isinstance(getattr(b[0], "value", None), ast.Constant)
                    and isinstance(b[0].value.value, str)):
                node.body = b[1:] or [ast.Pass()]
    return ast.unparse(tree)          # ast 는 주석을 갖지 않는다

def _unwired(ledger: dict, code: str) -> list[str]:
    """코드 참조 0곳 · `raw_only` 아님. 배선할 코드가 있을 수 있는 소스."""
    return sorted(k for k, e in (ledger.get("datasets") or {}).items()
                  if k not in code and (e or {}).get("kind") != "raw_only")


_PURPOSE = re.compile(r"^미투입 — \S")


def _undeclared(ledger: dict, keys: list[str]) -> list[str]:
    """`feeds: 미투입 — <용도>` 를 안 적은 미배선 소스."""
    ds = ledger.get("datasets") or {}
    return [k for k in keys
            if not _PURPOSE.match(str((ds.get(k) or {}).get("feeds") or ""))]


def test_unwired_sources_declare_purpose():
    """코드가 안 읽는 소스는 대장에 **용도를 적고 산다.** 수를 문서에 적지 않는다.

    ★ 2026-09-17 (DECISIONS §171-1). 종전 강제자는 `PLAN §1` 의
      `참조 0곳인 소스 N종` 과 실제 수를 대조했다. 그런데 그 행은 스스로
      *"정리 완료. 수는 남는다"* 고 적었다 — 22종 전부가 이미
      `feeds: 미투입 — <용도>` 로 분류돼 있었다. **갚을 빚이 없는 행이
      빚 목록에 살았고**, 강제자가 그 행을 지우지 못하게 붙들었다.
      `EXEMPT` 가 조사 도구 아홉을 사유와 함께 등재한 것과 같은 형태로
      바꾼다(DECISIONS §162) — 분류된 거주는 빚이 아니다.

    ★ 수가 늘어도 안 운다. **용도 없이 늘면** 운다. 그것이 낡음이다.
    """
    yaml = pytest.importorskip("yaml")
    ledger = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    code = "".join(
        _code_only(p.read_text(encoding="utf-8", errors="ignore"))
        for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "tools").glob("*.py"))
    )
    bad = _undeclared(ledger, _unwired(ledger, code))
    assert not bad, (
        "코드 참조 0곳인데 대장에 `feeds: 미투입 — <용도>` 가 없다 — "
        + ", ".join(bad)
        + "\n  배선하거나, 안 쓰는 이유(용도)를 대장에 적는다")


def test_unwired_probe_is_alive():
    """카나리아 — 판별식이 죽으면 위 검사는 영원히 초록이다."""
    ledger = {"datasets": {
        "zz_probe_wired": {"kind": "csv_table"},
        "zz_probe_raw":   {"kind": "raw_only"},
        "zz_probe_ok":    {"kind": "csv_table", "feeds": "미투입 — 대조축"},
        "zz_probe_bare":  {"kind": "csv_table", "feeds": "미투입"},
        "zz_probe_none":  {"kind": "csv_table"},
    }}
    keys = _unwired(ledger, 'load("zz_probe_wired")')
    assert keys == ["zz_probe_bare", "zz_probe_none", "zz_probe_ok"]
    assert _undeclared(ledger, keys) == ["zz_probe_bare", "zz_probe_none"]


def test_sources_plan_row_refs_resolve():
    """`sources.yaml` 이 드는 PLAN 행 번호가 **실재하는가** (W3-9).

    ── 왜 생겼나 ───────────────────────────────────────────────
    `plan_renumber.py` 는 PLAN **안만** 당긴다. 그래서 §1 에서 행 하나를
    지우면 `sources.yaml` 의 인용이 조용히 어긋난다. 2026-09-19 실측 —
    `bldg_ledger_dm` 이 드는 `#62` 는 **없는 행**이었고(β 점유위험도는
    `#60` 이다), 아무도 몰랐다.

    ★ **더 나쁜 것은 그 다음이다.** 그 상태에서 §1 에 62번 행을 새로 달면
      죽은 인용 셋이 **조용히 새 행을 가리킨다.** 틀린 참조가 맞는 참조인
      척하는 것 — 없는 참조보다 나쁘다.

    ★ 형식을 강제하지 않는다. 지금 `sources.yaml` 은 `PLAN #26` 과 맨
      `#2` 를 섞어 쓰고 둘 다 정상이다(13곳이 맨 형태다). **표기를 바꾸라고
      요구하면 이 검사를 넣는 값보다 고치는 값이 커진다.** 해석되는지만 본다.
    """
    src = (ROOT / "sources.yaml").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    rows = {int(m.group(1)) for m in re.finditer(r"^\| (\d+) \|", plan, re.M)}
    assert rows, "PLAN §1 에서 번호 행을 0개 찾았다 — 이 검사가 빈 그물이 됐다"

    bad = []
    for m in re.finditer(r"(?<![\w-])#(\d+)\b", src):
        n = int(m.group(1))
        if n in rows:
            continue
        line = src[: m.start()].count("\n") + 1
        text = src.splitlines()[line - 1].strip()
        bad.append(f"  sources.yaml:{line}  #{n} — PLAN §1 에 없다\n      {text[:76]}")

    assert not bad, (
        "대장이 **없는 PLAN 행**을 인용한다.\n" + "\n".join(bad)
        + f"\n  PLAN §1 은 지금 1..{max(rows)} 다.\n"
        + "  `plan_renumber.py` 는 PLAN 안만 당기므로 행을 지우면 여기가 어긋난다.\n"
        + "  고칠 때 **그 번호가 무엇을 가리켰는지**부터 찾아라 — 새 행이\n"
        + "  그 자리에 오면 틀린 참조가 맞는 참조인 척한다(W3-9).")


# ── §13 결함 대장 — 세는 일을 사람에게 맡기지 않는다 ─────────────
def _ledger_section() -> str:
    """§13-3 절 본문. 못 찾으면 곧 빈 그물이므로 여기서 죽는다."""
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    m = re.search(r"^### 13-3\..*?$(.*?)(?=^###\s)", plan, re.M | re.S)
    assert m, "PLAN §13-3 절을 못 찾았다 — 이 검사가 빈 그물이 됐다"
    return m.group(1)


def _ledger_rows() -> list[str]:
    """§13-3 표의 W-ID 목록. 순서대로."""
    return re.findall(r"^\|\s*(W\d+-\d+)\s*\|", _ledger_section(), re.M)


def test_defect_ledger_counts_agree_everywhere():
    """§13 의 「남은 건수」가 **세 곳에서 같은가**.

    ★ 2026-09-20 (PLAN §13 W5-1 · 가드 1의 첫 물음). 이 절은 **같은 사고를
      두 번 당했다.**

        2026-09-19  §13-1 문단 「22행」 · §13-3 제목 「30건」 · 실제 표 30행
                    — 세 숫자가 전부 달랐고, 그중 셋은 🟢 로 닫힌 채 남아 있었다
        2026-09-20  §13-1 문단 「30행」 · 제목 「28건」 · 실제 28행
                    — **정정한 다음 날 다시 갈렸다**

      2026-09-19 의 정정문이 직접 이렇게 적었다 — 「세는 일을 사람에게
      맡기지 않으려면 행 수를 세는 강제자가 필요하다. 그것은 가드 1 이
      받는다.」 가드를 안 세웠고, 그래서 하루 만에 다시 났다.
      **선언이 있고 강제자가 없으면 반드시 갈린다** — 이 절이 세는 1족 그 자체다.

    ★ 범위를 선언한다. 이 검사는 **수 셋이 같은가**만 본다.
      가드 1 의 나머지 물음(「닫혔다고 적힌 배치의 증표가 트리에 있는가」)은
      증표 등록부가 있어야 성립하고 그것은 아직 없다 — W5-1 이 열려 있는
      이유다. **「섰다」로 적지 않는다**(§13-4 가 가드 2 에 적용한 그 규율).
    """
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    rows = _ledger_rows()
    assert rows, "§13-3 에서 행을 0개 찾았다"

    t = re.search(r"^### 13-3\. 남은 결함 (\d+)건", plan, re.M)
    assert t, "§13-3 제목이 「남은 결함 N건」 꼴이 아니다 — 세는 자리가 사라졌다"
    p = re.search(r"남은 것이 아래 \*\*(\d+)행\*\*이다", plan)
    assert p, "§13-1 이 「남은 것이 아래 **N행**이다」를 안 적는다"

    title, para, real = int(t.group(1)), int(p.group(1)), len(rows)
    assert title == para == real, (
        f"§13 의 건수가 갈렸다 — 제목 {title}건 · §13-1 문단 {para}행 · 실제 표 {real}행\n"
        "  정본은 **표**다. 행을 지웠으면 두 숫자를 같이 고친다.\n"
        "  (2026-09-19 에 22/30/30 으로 갈렸고, 정정한 다음 날 30/28/28 로 또 갈렸다)")


def test_defect_ledger_ids_are_unique():
    """같은 W-ID 가 두 행에 있으면 어느 쪽이 정본인지 알 수 없다."""
    rows = _ledger_rows()
    dup = sorted({r for r in rows if rows.count(r) > 1})
    assert not dup, f"§13-3 에 중복 ID: {dup}"


# ── §13 행이 **실재하는 것**을 가리키는가 ────────────────────────
# ★ 대장에 담긴 경로 표기 중 **파일이 아닌 것.** 사유를 적는다.
#   비어 있어도 된다 — 아래 `test_ledger_exemptions_are_not_dead` 가
#   「면제했는데 실은 안 걸리는 것」을 지운다.
LEDGER_NOT_A_PATH: dict[str, str] = {
    # 2026-09-22 — `MASTER/12-8`(W3-5 가 제안한 `dms` 절 ID 표기)이 여기 있었다. W3-5 가 닫히며
    # 그 행이 지워져 더는 인용되지 않는다.
}

# 경로처럼 보이는 백틱 토큰 — 슬래시가 하나 이상 있어야 한다
_LEDGER_PATH = re.compile(r"`([\w.-]+(?:/[\w.@-]+)+/?)`")


def _ledger_citations() -> list[tuple[str, str]]:
    """(W-ID, 경로 표기) 목록. 글롭은 뺀다 — 0건인지 아닌지는 refcheck 소관이다."""
    out = []
    for line in _ledger_section().splitlines():
        m = re.match(r"^\|\s*(W\d+-\d+)\s*\|(.*)$", line)
        if not m:
            continue
        for p in sorted(set(_LEDGER_PATH.findall(m.group(2)))):
            if any(c in p for c in "*?"):
                continue
            out.append((m.group(1), p))
    return out


@functools.lru_cache(maxsize=1)
def _tracked() -> tuple[str, ...]:
    """git 이 추적하는 파일 전부. **대장이 가리킬 수 있는 것의 전부**이기도 하다.

    ★ 2026-09-21 (DECISIONS §206). 종전에는 `ROOT.rglob()` 으로 훑었다.
      그것은 **`.git/` 안까지 본다.** 그래서 `part/infra`(브랜치 이름)가
      `.git/refs/heads/part/infra` 에 걸려 **로컬에서는 통과했다.**
      CI 는 새로 clone 해 ref 가 `packed-refs` 하나로 묶이므로 그 파일이 없고,
      **거기서만 빨개졌다.** 로컬 837 초록 · CI 빨강 — 제일 나쁜 모양이다.
      `git ls-files` 는 `.git` 을 구조적으로 안 담는다. 훑는 자리를 좁히는 것이
      아니라 **물음에 맞는 자리로 옮기는 것**이다.
    """
    r = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, "git ls-files 가 실패했다 — 이 검사가 빈 그물이 된다"
    out = tuple(f for f in r.stdout.split("\0") if f)
    assert out, "추적 파일이 0개다 — git 저장소가 아니거나 프로브가 죽었다"
    return out


def _resolves(rel: str) -> bool:
    """실재하는가. **추적 파일**의 정확 경로거나 그 꼬리거나.

    ★ 작업 트리가 아니라 `git ls-files` 를 본다 — 위 `_tracked()` 의 ★ 참조.
      디렉터리 인용은 그 밑에 추적 파일이 하나라도 있으면 실재로 본다.
    """
    rel = rel.rstrip("/")
    tail, pre = "/" + rel, rel + "/"
    return any(f == rel or f.startswith(pre) or f.endswith(tail)
               or f"/{pre}" in f
               for f in _tracked())


def test_every_ledger_row_points_at_something_real():
    """§13-3 의 행이 드는 경로가 실재하는가.

    ★ 2026-09-20 (DECISIONS §203). 가드 1 이 「닫혔다고 적힌 것이 정말
      닫혔나」를 묻는다면, 이것은 **거울상**이다 — 「열려 있다고 적힌 것이
      정말 열려 있나」. 둘 다 없으면 대장은 양쪽으로 샌다.

    ★ 세우고 재니 **25행 중 셋이 유령이었다.**

        W4-1  `outputs/diagrams/` 2개 — 생성 코드가 없다
        W3-7  폰트 스택 둘 — `outputs/diagrams` vs `docs/figures`

      `outputs/diagrams/` 는 **git 역사상 한 번도 없었다.** `outputs/` 자체는
      html 두 장짜리였고 2026-08-09(`bf86828`)에 사라졌다. 즉 2026-09-18 감사가
      **없는 디렉터리에 대한 결함 둘**을 등재했고, 그 뒤 이틀간 아무도 몰랐다.
      (셋째 W4-3 은 경로가 아니라 **이미 닫힌 것**이 남은 경우다 — 그쪽은
      기계가 못 잡는다. 사람이 `baseline.py` 머리말을 읽어야 알 수 있었다.)

    ★ `refcheck ⑦` 이 왜 못 잡았나 — 그 정규식이
      `` `(src|tools|tests|docs|web|data)/…\\.\\w{1,6}` `` 다. **확장자를 요구하므로
      디렉터리 참조는 애초에 후보가 안 된다.** 접두 목록도 손목록이고,
      `outputs` 는 거기 없다. 범위가 이름(「선언이 가리키는 모든 것」)보다
      좁고 그것이 선언돼 있지 않았다 — 이 저장소가 세는 그 족이다.
      여기서는 **확장자를 요구하지 않고 디렉터리도 본다.**

    ★ 범위는 §13-3 하나다. DECISIONS 는 **역사**라 죽은 경로를 인용하는 것이
      정상이고, 거기까지 넓히면 16건이 뜨는데 대부분 옳다(측정했다).
      대장의 행만이 **지금에 대한 주장**이다.
    """
    bad, untracked = [], []
    for wid, rel in _ledger_citations():
        if rel in LEDGER_NOT_A_PATH or _resolves(rel):
            continue
        # ★ 2026-09-21. **작업 트리에는 있는데 git 에 없는** 경우를 갈라 말한다.
        #   이 배치에서 새 파일을 만들고 그것을 대장에 적으면 `git add` 전까지
        #   여기가 빨간데, 위의 「행을 지워라」는 **정확히 틀린 처방**이다.
        #   (§206 이후 이 검사는 작업 트리가 아니라 `git ls-files` 를 본다.
        #   그 자리는 옳다 — 커밋되지 않은 것은 CI 에 없으니까. 다만 **왜
        #   빨간지를 말해야** 다음 사람이 파일을 지우지 않는다.)
        if (ROOT / rel).exists():
            untracked.append(f"  {wid}  `{rel}` — 파일은 있는데 git 에 없다")
        else:
            bad.append(f"  {wid}  `{rel}` — 없다")
    assert not untracked, (
        "§13-3 의 행이 **아직 git 에 올라가지 않은 것**을 가리킨다.\n"
        + "\n".join(untracked) + "\n\n"
        "  파일은 작업 트리에 있다. 지우지 마라 — `git add` 하면 된다.\n"
        "  이 검사가 작업 트리가 아니라 `git ls-files` 를 보는 이유는\n"
        "  **CI 에는 커밋된 것만 있기 때문**이다(DECISIONS §206).")
    assert not bad, (
        "§13-3 의 행이 **없는 것**을 가리킨다.\n" + "\n".join(bad) + "\n\n"
        "  전제가 사라졌으면 행을 지운다(§13-5 규약 4). 결함이 닫힌 것이 아니라\n"
        "  **애초에 없던 것**일 수도 있다 — 어느 쪽인지 git 으로 먼저 확인해라:\n"
        "    git log --all --diff-filter=D --name-only -- '<경로>'\n"
        "  경로가 아니라 표기(ID 꼴 등)이면 `LEDGER_NOT_A_PATH` 에 사유와 함께 적는다.")


def test_ledger_exemptions_are_not_dead():
    """면제했는데 실은 안 걸리는 것이 있는가.

    ★ 죽은 면제는 「이건 봐줬다」는 거짓 기록이고, 다음 사람이 그 목록을
      믿고 안 본다. 2026-09-20 에 `test_tools_are_wired` 에서 31개 중 12개가,
      `deadcheck` 에서도 같은 형태가 나왔다. 세 번째다 — 면제에는 늘 이것을 붙인다.
    """
    cited = {rel for _, rel in _ledger_citations()}
    dead = sorted(k for k in LEDGER_NOT_A_PATH if k not in cited or _resolves(k))
    assert not dead, (
        f"면제가 죽었다 — {dead}\n"
        "  대장이 더는 인용하지 않거나, 인용하는데 실재한다. 지워라.")


def test_every_ledger_exemption_states_a_reason():
    """사유 없는 면제는 그냥 구멍이다."""
    for name, why in LEDGER_NOT_A_PATH.items():
        assert why and len(why) > 15, f"`{name}` 면제에 사유가 없다"


def test_plan_section1_count_agrees():
    """`§1` 제목의 수와 실제 행 수가 같은가.

    ★ 2026-09-20 (DECISIONS §205). §13 은 하루 전에 같은 것을 세웠고
      **세우자마자 갈린 것이 걸렸다**(문단 30 · 제목 28 · 표 28). §1 은 62행을
      굴리면서 수를 **어디에도 안 적었다** — 「얼마나 남았나」를 물으면 매번
      손으로 세야 했다. 손으로 세는 것은 갈린다. 세어 본 적이 없으니
      갈릴 기회조차 없었을 뿐이다.

    ★ 이 수가 **줄어들 수 있게 된 것**이 같은 배치의 일이다 — 종전에는 행을
      지우면 뒤 번호가 당겨지고 밖의 인용 83곳이 어긋나서 **지울 수가 없었다.**
      결번을 허용하면서 그 잠금이 풀렸다.
    """
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    m = re.search(r"^## 1\. 남은 일 — (\d+)행\s*$", plan, re.M)
    assert m, (
        "§1 제목이 「남은 일 — N행」 꼴이 아니다 — 세는 자리가 사라졌다.\n"
        "  행을 지우거나 더하면 제목의 수도 같이 고친다.")
    declared, real = int(m.group(1)), len(_plan_rows())
    assert declared == real, (
        f"§1 의 수가 갈렸다 — 제목 {declared}행 · 실제 표 {real}행\n"
        "  정본은 **표**다. 제목을 고쳐라.")


def test_master_roles_do_not_copy_codeowners():
    """MASTER §8 은 CODEOWNERS 를 베끼지 않는다 (PLAN §13 W3-2 닫힘 · DECISIONS §217-5).

    2026-09-20 감사에서 §8 담당표의 개인 핸들 넷이 CODEOWNERS 에 0회였고 설명 산문 둘도
    거짓이었다. 소유의 정본은 CODEOWNERS 하나다 — §8 에 `@핸들` 이 다시 나오면 운다.
    CODEOWNERS 에 없는 핸들이면 거짓이고, 있는 핸들이면 낡을 사본이다.
    """
    master = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    s8 = master[master.index("\n## 8. 역할\n"):master.index("\n## 9. ")]
    body = re.sub(r"`[^`]*`", "", s8)            # 인용(과거 거짓 문구 · 정본 이름)은 뺀다
    handles = re.findall(r"(?<![\w/])@[A-Za-z0-9][\w-]*(?:/[\w-]+)?", body)
    assert not handles, f"MASTER §8 이 CODEOWNERS 핸들을 베낀다: {sorted(set(handles))}"
    owners = set(re.findall(r"@[\w-]+(?:/[\w-]+)?", (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")))
    quoted = set(re.findall(r"`(@[A-Za-z0-9][A-Za-z0-9-]*(?:/[A-Za-z0-9-]+)?)`", s8))
    assert quoted - owners <= {"@AIMasterFox", "@woongtopia/gis"}, \
        f"§8 이 인용한 핸들 중 CODEOWNERS 에도 없고 과거 인용도 아닌 것: {quoted - owners}"
