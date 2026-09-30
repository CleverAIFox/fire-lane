"""
test_defect_evidence.py — 닫힌 결함마다 **증표**(그 닫힘을 지키는 시험)가 트리에 있는가.

2026-09-22 (PLAN §13 W5-1 닫힘 · DECISIONS §217-5). 2026-09-18 에 배치 0 이 강제 갱신으로
브랜치에서 떨어졌는데 PLAN §13 은 「닫힘」을 계속 선언했고 강제자 51개 중 하나도 안 울었다.
행 수를 세는 강제자(`test_defect_ledger_counts_agree_everywhere`)는 섰지만 그것은 **수**만
본다. 이 파일은 **증표**를 본다 —

  ① 등록부의 증표(시험 노드)가 실재한다          — 떨어진 배치는 증표도 없다
  ② 등록된 ID 는 §13-3 표에 없다                 — 닫혔다면서 남아 있으면 2족
  ③ DECISIONS 의 `닫힘` 줄(§217 부터)이 든 ID 는 전부 등록부에 있다 — 선언만 있고 증표가 없으면 1족

★ 범위는 **이 등록부가 생긴 배치(§217)부터**다. 그 전 닫힘(배치 0 · W1 · W2 · W3-8 · W4-8 …)은
  증표가 선언된 적이 없고, 소급해서 지어내면 그것이 거짓 기록이다(W5-1 행의 조건).
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 닫힌 W-ID → 그 닫힘을 지키는 시험. 행을 닫으면 여기에 한 줄을 단다.
EVIDENCE = {
    "W11-1": "tests/test_turn_restriction_filter.py::test_missing_node_point_stops",
    "W3-5": "tests/test_dms_ids.py::test_insert_does_not_shift_others",
    "W3-2": "tests/test_declaration_sync.py::test_master_roles_do_not_copy_codeowners",
    "W3-3": "tests/test_docx_targets.py::test_docx_check_is_bidirectional",
    "W4-2": "tests/test_docx_targets.py::test_docx_check_is_bidirectional",
    "W3-9": "tests/test_declaration_sync.py::test_sources_plan_row_refs_resolve",
    "W7-3": "tests/test_verify_scope.py::test_scope_declarations_ratchet",
    "W3-15": "tests/test_publish_context.py::test_deploy_uses_drop_list",
    "W3-18": "tests/test_ci_env.py::test_devcontainer_env_notice_is_conditional",
    "W8-1": "tests/test_defect_evidence.py::test_navi_toolchain_is_vite8_and_vitest",
    # ★ 2026-09-22. W9-4 · W9-5 의 증표였던 tests/test_web_labels.py 는 옛 지도와 함께 지웠다.
    #   토글 행 · toggles.js 가 없어져 재발할 자리가 없다 — 지도가 안 돌아오는 것이 증표다.
    "W9-4": "tests/test_web_ownership.py::test_old_map_is_retired_and_entry_redirects",
    "W9-5": "tests/test_web_ownership.py::test_old_map_is_retired_and_entry_redirects",
    "W3-13": "tests/test_generated_registry.py::test_call_site_values_come_from_registry",
    "W10-1": "tests/test_deadcheck_probes.py::test_every_ceiling_is_zero",
    "W5-1": "tests/test_defect_evidence.py::test_evidence_exists_in_tree",
    "W4-7": "tests/test_docx_targets.py::test_long_cell_ratchet_bites",
    "W3-6": "tests/test_golden_fp.py::test_display_only_constants_are_outside_the_judgment_closure",
    # ★ 2026-09-24 (DECISIONS §227). §13 의 **마지막** 행. 증표는 옛 판정을
    #   박제해 경계에서 대조하는 시험이다 — 수용 조건이 「불변 증명」이었으므로
    #   증표도 「불변이 관측된다」여야 한다.
    "W6-1": "tests/test_ledger_contract.py::test_row_count_boundary_is_unchanged",
    # ★ 2026-10-01 (DECISIONS §336). 정책 다섯이 훅에서 `domain` 으로 내려갔다.
    #   증표는 **그 정책을 묻는 시험이 실재하는가** — 되돌리면 훅 안에 정책이
    #   다시 생기고, 그때 이 시험 파일이 없어진다.
    "W13-5": "tests/test_defect_evidence.py::test_navi_policy_lives_in_domain",
    # ★ 2026-09-29 (DECISIONS §306). 셋을 늦게 등록했다. 셋 다 PLAN §13-3 표에
    #   「닫힘」으로 **남아 있었고** 등록부에는 없었다 — §13-1 이 「닫힌 결함은
    #   행이 아니라 부재로 기록된다」고 적어둔 그 규약을 세 번 어긴 것이다.
    #   관문 ③이 이것을 잡아야 했는데, 그것은 DECISIONS 의 `닫힘` **줄**만
    #   읽고 §288 · §297 · §302 가 그 형식을 안 썼다. 줄을 같이 넣었고,
    #   표에 닫힘이 남는 것 자체를 무는 관문을 새로 세웠다
    #   (`test_no_closed_row_lingers_in_the_table`).
    #
    # ★ W13-7 은 **증표가 아예 없었다.** `fieldseal` 을 무는 시험이 트리에
    #   하나도 없이 닫혀 있었다 — 도구는 있고 `verify.sh` 가 부르는데, 그것이
    #   「불린다」와 「무엇을 본다」를 증명하지는 않는다. 그래서 등록하면서
    #   증표를 새로 썼다(`tests/test_fieldseal.py` 6개).
    "W13-7": "tests/test_fieldseal.py::test_the_seal_matches_the_tracked_table",
    "W13-8": "tests/test_ledger_outputs.py::test_retired_step_is_really_gone",
    "W13-10": "tests/test_docseal_view.py::test_지목한_도구를_관문에서_떼면_지문이_움직인다",
}


def _open_ids() -> set[str]:
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    sec = plan[plan.index("### 13-3."):]
    sec = sec[:sec.index("\n### ", 5)]
    return set(re.findall(r"^\| (W\d+-\d+) \|", sec, re.M))


def test_evidence_exists_in_tree():
    missing = []
    for wid, node in EVIDENCE.items():
        f, fn = node.split("::")
        p = ROOT / f
        if not p.is_file():
            missing.append(f"{wid}: {f} 가 없다")
            continue
        names = {n.name for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
                 if isinstance(n, ast.FunctionDef)}
        if fn not in names:
            missing.append(f"{wid}: {node} 가 없다")
    assert not missing, "닫힘의 증표가 트리에 없다 — 그 배치가 떨어졌다:\n  " + "\n  ".join(missing)


def test_no_closed_row_lingers_in_the_table():
    """★ 2026-09-29 (DECISIONS §306). **표에 「닫힘」이 남아 있으면 결함이다.**

    PLAN §13-1 이 이미 그렇게 적는다 — 「이 절은 빚 목록이다. 닫힌 결함은 행이
    아니라 부재로 기록된다.」 그런데 그 규약을 무는 것이 없었다. 아래
    `test_closed_ids_are_not_open` 은 **등록부에 든 ID** 만 보므로, 등록도 안
    하고 표에 「닫힘」으로 눌러앉은 행은 어느 관문도 안 봤다. 실제로 셋이
    그 상태로 있었다(W13-7 · W13-8 · W13-10).

    ★ 왜 「부재로 기록」이 맞는가. 닫힌 행을 남기면 표가 **단조 증가**한다.
      그러면 「남은 결함 N건」이 빚의 크기를 못 말하고, 사람이 표를 보고
      「얼마나 남았나」를 셀 수 없다. 닫힌 이유는 DECISIONS 가, 닫힘을 지키는
      시험은 위 등록부가 든다 — 표가 세 번째 집이 될 이유가 없다(R3).
    """
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    sec = plan[plan.index("### 13-3."):]
    sec = sec[:sec.index("\n### ", 5)]
    lingering = [m.group(1) for m in re.finditer(r"^\| (W\d+-\d+) \|.*$", sec, re.M)
                 if "닫힘" in m.group(0)]
    assert not lingering, (
        f"닫힌 행이 §13-3 표에 남아 있다: {lingering}\n"
        "  §13-1 — 「닫힌 결함은 행이 아니라 부재로 기록된다」\n"
        "  ① 행을 지우고  ② 제목·문단의 수를 내리고\n"
        "  ③ EVIDENCE 에 그 닫힘을 지키는 시험을 한 줄 적고\n"
        "  ④ DECISIONS 의 해당 절에 `    닫힘   <ID>` 줄을 넣어라")


def test_closed_ids_are_not_open():
    both = sorted(set(EVIDENCE) & _open_ids())
    assert not both, f"닫혔다고 등록했는데 PLAN §13-3 에 남아 있다: {both}"


def test_decisions_closures_have_evidence():
    dec = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    start = dec.index("\n## 217.")
    said = set()
    for line in dec[start:].splitlines():
        if re.match(r"^\s*닫힘\s", line):
            said |= set(re.findall(r"W\d+-\d+", line))
    assert said, "DECISIONS §217 부터 `닫힘` 줄이 하나도 안 읽힌다 — 이 시험이 빈 그물이다"
    lost = sorted(said - set(EVIDENCE))
    assert not lost, f"DECISIONS 가 닫았다고 적었는데 증표가 등록되지 않았다: {lost}"


def test_navi_policy_lives_in_domain():
    """W13-5 — 훅의 정책이 `domain` 에 있고 **물어지는가.** (DECISIONS §336)

    ★ 증표는 「파일이 있다」가 아니라 **「그 정책을 묻는 시험이 있다」**다.
      모듈만 두고 시험을 지우면 정책은 다시 아무도 안 묻는 값이 된다.
    ★ 되돌리는 쪽도 문다 — 훅이 제 안에서 단계를 박으면(`setPhase("guiding")`)
      표가 정본이 아니게 되고, 그때 이 시험이 운다.
    """
    navi = ROOT / "web" / "navi"
    for mod, fns in (("domain/track.ts", ("chooseSource", "nextBearing", "weakCrossed", "edgeShare")),
                     ("domain/phase.ts", ("nextPhase",))):
        src = (navi / "src" / mod).read_text(encoding="utf-8")
        for fn in fns:
            assert f"export function {fn}" in src, f"`{mod}` 에 `{fn}` 이 없다 — 정책이 훅으로 돌아갔다"
    for t_ in ("test/track.test.ts", "test/phase.test.ts"):
        q = navi / t_
        assert q.is_file(), f"`{t_}` 가 없다 — 정책이 다시 안 물어진다"
        assert q.read_text(encoding="utf-8").count("it(") >= 8, f"`{t_}` 가 비었다"

    hook = (navi / "src" / "app" / "useNavigation.ts").read_text(encoding="utf-8")
    # ★ 단계를 **문자열로 박는** 자리가 남아 있으면 표가 정본이 아니다.
    hard = re.findall(r'setPhase\(\s*"([a-z]+)"', hook)
    assert not hard, f"훅이 단계를 문자열로 박는다 {hard} — 정본은 `nextPhase` 표다"
    assert "nextPhase" in hook, "훅이 `nextPhase` 를 안 쓴다 — 표가 죽은 선언이다"


def test_navi_toolchain_is_vite8_and_vitest():
    """W8-1 — vite 8(rolldown) · plugin-react 6 · 시험은 vitest (수제 러너 폐기)."""
    pkg = json.loads((ROOT / "web" / "navi" / "package.json").read_text(encoding="utf-8"))
    dev = pkg["devDependencies"]
    assert re.match(r"\^?8\.", dev["vite"]), dev["vite"]
    assert re.match(r"\^?6\.", dev["@vitejs/plugin-react"]), dev["@vitejs/plugin-react"]
    assert "vitest" in dev and pkg["scripts"]["test"].startswith("vitest"), pkg["scripts"]["test"]
    assert not (ROOT / "web" / "navi" / "scripts" / "test.mjs").exists(), "수제 러너가 되살아났다"

    # ★ **2026-09-30 (DECISIONS §323). 이 축의 증표가 옮겨갔다.**
    #   종전에는 「`build-navi` 의 워커 grep 이 백틱을 아는가」를 물었다 —
    #   rolldown 압축기가 문자열을 백틱으로 내므로 셸 grep 의 문자 클래스에
    #   백틱이 없으면 다음 따옴표까지 3,348자를 삼켰기 때문이다.
    #
    #   그 grep 이 없어졌다. 판정이 `tools/naviweight.py` 로 갔고, 파이썬
    #   정규식은 낱말 문자에서 끊으므로 **백틱도 따옴표도 삼킬 수가 없다.**
    #   고친 것이 아니라 **그 결함이 성립하지 않는 자리로 옮긴 것**이고,
    #   그래서 여기서 묻는 것도 바뀐다 — 「그 판정이 아직 있는가」다.
    nw = (ROOT / "tools" / "naviweight.py").read_text(encoding="utf-8")
    assert "def worker_faults" in nw, "워커 판정이 없다 — 배포본을 아무도 안 본다(§323)"
    assert r"[\w.\-]*" in nw, (
        "워커 참조 정규식이 낱말 문자에서 안 끊긴다 — rolldown 의 백틱을 삼킬 수 있다")
