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
EXEMPT = {
    # ── 조사 도구. 사람이 판단하려고 부른다. 아무것도 안 바꾼다(README).
    "clearance_probe": "최대내접원 방식 대조. 2026-08-22 기각(DECISIONS §32)",
    "corner_probe": "코너 기하 조사",
    "desk_check": "정사영상 위에 구간·폭 렌더. 책상 대조",
    "jijeok_probe": "연속지적도로 폭 대조",
    "jijeok_review": "갈리는 구간을 정사영상 위에서 사람이 판정",
    "lanes_probe": "표준노드링크 차로수로 폭 하한 대조",
    "route_probe": "거리만 대 차량 비용 경로 비교",
    "width_fn": "폭을 함수 w(s) 로 — min 대 통과폭",
    "wmax_audit": "width_max_m 결손이 판정에 미치는 규모",
    # ── 일회성 이관. 돌리고 나면 no-op 이다(R8).
    "ledger_feeds": "feeds 산문 → 소비자 리스트. 이관 완료",
    "ledger_fields": "대장 별칭 필드 통합. 이관 완료",
    "ledger_stem": "대장 stem 이관. 완료",
    "ledger_schema": "실물에서 스키마 추출. --check 는 사람이 부른다",
    "migrate_names": "raw 개명 백필",
    "docpatch": "문서 절 단위 멱등 교체. 배치 작업 도구",
    # ── 사람이 부르는 것. 자동으로 돌면 안 되는 이유가 있다.
    "pull_data": "데이터 반입. raw 를 건드린다",
    "intake": "Downloads → landing 게이트",
    "acquire": "landing → raw 획득 게이트",
    "doctor": "전 계층 진단. 데이터 레이크가 있어야 한다",
    "ruleset_check": "관리자 토큰이 필요해 CI 에 못 붙인다(MASTER §12-1)",
    "docx_fix": "기획서를 실제로 고친다. 사람이 확인하고 친다",
    "baseline": "봉인. 사람이 시점을 정한다",
    "scan_data": "데이터 레이크 구조 점검. raw 필요",
    "serve": "개발 서버",
    "tidy": "로컬 찌꺼기. verify 가 관측만 부른다",
    "triage": "대장 밖 파일을 내용으로 판정. Downloads·landing 을 본다",
}

CALLERS = ("tools/verify.sh", "tools/ship.py")


def _haystack() -> str:
    out = []
    for rel in CALLERS:
        p = ROOT / rel
        if p.exists():
            out.append(p.read_text(encoding="utf-8"))
    for d in (".github/workflows", "tests"):
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.suffix in (".yml", ".yaml", ".py") and p.is_file():
                out.append(p.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(out)


def test_every_tool_is_called_somewhere():
    """도구가 어딘가에서 **실행되는가.** 목록에만 있는 것은 배선이 아니다."""
    hay = _haystack()
    bad = []
    for p in sorted((ROOT / "tools").glob("*.py")):
        name = p.stem
        if name in EXEMPT:
            continue
        # `tools/name.py` 또는 `import name` 형태로 실제 호출되는가
        if re.search(rf"tools/{re.escape(name)}\.py", hay):
            continue
        if re.search(rf"\b(?:from|import)\s+{re.escape(name)}\b", hay):
            continue
        bad.append(f"  tools/{name}.py 를 아무 데서도 안 부른다")

    assert not bad, (
        "만들어놓고 안 부르는 도구가 있다.\n" + "\n".join(bad)
        + "\n\n  verify.sh 에 걸거나, 자동 실행하면 안 되는 이유를\n"
          "  EXEMPT 에 사유와 함께 적어라. **사유 없이 넣지 마라** —\n"
          "  그러면 이 검사가 항상 통과하는 검사가 된다(DECISIONS §69).")


def test_exempt_entries_are_real():
    """EXEMPT 가 없는 도구를 들면 목록이 낡은 것이다. 양방향이다."""
    have = {p.stem for p in (ROOT / "tools").glob("*.py")}
    ghost = sorted(n for n in EXEMPT if n not in have)
    assert not ghost, (
        f"EXEMPT 가 없는 도구를 든다 — {', '.join(ghost)}\n"
        "  도구를 지웠으면 그 줄도 지워라.")


def test_exempt_entries_carry_a_reason():
    """사유가 비면 면제가 아니라 방치다."""
    blank = sorted(n for n, why in EXEMPT.items() if not (why or "").strip())
    assert not blank, f"사유 없는 EXEMPT — {', '.join(blank)}"
