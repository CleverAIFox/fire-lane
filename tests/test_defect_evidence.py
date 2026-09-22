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
    "W9-4": "tests/test_web_labels.py::test_toggle_rows_carry_no_hand_written_names",
    "W9-5": "tests/test_web_labels.py::test_toggles_js_fills_names_from_config",
    "W3-13": "tests/test_generated_registry.py::test_call_site_values_come_from_registry",
    "W10-1": "tests/test_deadcheck_probes.py::test_every_ceiling_is_zero",
    "W5-1": "tests/test_defect_evidence.py::test_evidence_exists_in_tree",
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


def test_navi_toolchain_is_vite8_and_vitest():
    """W8-1 — vite 8(rolldown) · plugin-react 6 · 시험은 vitest (수제 러너 폐기)."""
    pkg = json.loads((ROOT / "web" / "navi" / "package.json").read_text(encoding="utf-8"))
    dev = pkg["devDependencies"]
    assert re.match(r"\^?8\.", dev["vite"]), dev["vite"]
    assert re.match(r"\^?6\.", dev["@vitejs/plugin-react"]), dev["@vitejs/plugin-react"]
    assert "vitest" in dev and pkg["scripts"]["test"].startswith("vitest"), pkg["scripts"]["test"]
    assert not (ROOT / "web" / "navi" / "scripts" / "test.mjs").exists(), "수제 러너가 되살아났다"
    act = (ROOT / ".github" / "actions" / "build-navi" / "action.yml").read_text(encoding="utf-8")
    assert "maplibre-gl-worker[^\"'\"'\"'`]" in act, "워커 grep 이 백틱을 모른다 — rolldown 번들에서 죽는다"
