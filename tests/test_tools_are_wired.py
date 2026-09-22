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

    "kpi": "진입 실패율 산출. 발표에서 인용할 숫자라 사람이 조건과 함께 부른다",
    "its_linkmap": "ITS 소통정보 링크 ↔ seg_uid 대조표. 외부 API 규격 확인용이라 CI 에 못 건다",
    "matchcheck": "Mapbox Map Matching 커버리지 대조. 토큰 필요·외부 API 라 CI 에 못 건다",
    "bridge_audit": "다리 분석으로 실측 우선순위 산출. 사람이 답사 계획을 세우려고 부른다",
    # ── 조사 도구. 사람이 판단하려고 부른다. 아무것도 안 바꾼다(README).
    "clearance_probe": "최대내접원 방식 대조. 2026-08-22 기각(DECISIONS §32)",
    "corner_probe": "코너 기하 조사",
    "skeleton_compare": "R1 뼈대 후보 대조표. 사람이 R3 를 판정하려고 부른다(DECISIONS §184)",
    "transition": "R2 전이표. R3 전후로 사람이 부른다 — `baseline.py diff --transition` 이 같은 모듈을 쓴다(DECISIONS §187)",
    "lanes_probe": "표준노드링크 차로수로 폭 하한 대조",
    "wmax_audit": "width_max_m 결손이 판정에 미치는 규모",
    # ── 일회성 이관. 돌리고 나면 no-op 이다(R8).
    "ledger_stem": "대장 stem 이관. 완료",
    "ledger_schema": "실물에서 스키마 추출. --check 는 사람이 부른다",
    "migrate_names": "raw 개명 백필",
    # ── 사람이 부르는 것. 자동으로 돌면 안 되는 이유가 있다.
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


def _scan() -> list[tuple[str, int, str]]:
    """호출자가 될 수 있는 파일들의 **주석 아닌 줄**만 모은다."""
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
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            s = line.strip()
            if not s or s.startswith(_COMMENT):
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
    hits = []
    for f, i, s in lines:
        if f.endswith(name):
            continue
        if path_rx.search(s) or (imp_rx and imp_rx.search(s)):
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


def test_readme_exempt_entries_are_real_and_reasoned():
    have = {p.name for p in (ROOT / "tools").iterdir() if p.is_file()}
    ghost = sorted(n for n in README_EXEMPT if n not in have)
    blank = sorted(n for n, why in README_EXEMPT.items() if not why.strip())
    assert not ghost and not blank, f"없는 도구 {ghost} · 사유 없음 {blank}"
