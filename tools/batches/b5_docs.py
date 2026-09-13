#!/usr/bin/env python3
"""
b5_docs.py — **오늘 한 판단을 문서와 강제자에 앉힌다.**

    uv run python tools/batches/b5_docs.py            무엇을 할지만
    uv run python tools/batches/b5_docs.py --apply    실제로

★ `MASTER §12-1` 룰셋 표는 **손대지 않는다.**
  이 저장소는 팀 운영 방식을 기록으로 남기는 것이 목적이다. 예외 하나
  때문에 표를 고쳐 쓰면 그 기록이 사라진다. 승인 1은 형식이 아니라
  **협업자가 생기는 순간 즉시 유효해지는 선언**이다.
  예외는 §12-1a 에 적는다 — 그 절이 정확히 그 자리다.

★ **회수 조건을 날짜가 아니라 조건으로 적는다.**
  `DECISIONS §76` 이 막으려던 것은 "적어두지 않은 완화" 지 "날짜 없는
  예외" 가 아니다. 날짜는 지나가도 아무 일이 안 일어난다. 조건은
  **실제로 걸린다** — `collaborators` 가 둘이 되는 순간 검사가 운다.
  그래서 이 배치는 문서만 고치지 않고 `ruleset_check` 에 그 조건을 심는다.

★ 강제자가 하는 일 —
      선언된 bypass(admin) + 협업자 1명   → 통과
      선언 밖 bypass                      → 운다
      협업자 2명 이상인데 bypass 가 남음   → **운다. 회수 조건이 찼다**
  §12-1a 가 죽은 문서가 아니라 실행되는 계약이 된다. 회수를 잊을 수 없다.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

# ── ① MASTER §12-1a ──────────────────────────────────────────────
M_ANCHOR = """★ **`actor_id 5` 는 사람 수가 아니라 역할 번호다.**"""

M_NEW = """★ **`bypass_actors` 를 2026-09-12 에 다시 넣었다 — 이번엔 영구다.**

| | |
|---|---|
| 대상 | `release` · `trunk` · `part` 셋 다 |
| 예외 | `RepositoryRole:5`(Repository admin) · `always` |
| 사유 | 저장소가 `woongtopia` 조직에서 `CleverAIFox` 개인으로 **미러 이관**됐다. `release` 가 요구하는 승인 1은 **자기 PR 을 자기가 승인할 수 없어**(§12-3) 혼자서는 만족할 수 없다 |
| 회수 | **본인 외 협업자가 생기면** 제거한다. 날짜가 아니라 조건이다 |

★ 날짜를 안 쓴 이유. 날짜는 지나가도 아무 일이 안 일어나지만 조건은
  **검사가 잡는다.** `ruleset_check` 이 `collaborators` 를 세고 있고,
  둘이 되는 순간 "회수 조건이 찼다" 를 낸다. `§76` 이 막으려던 것은
  "적어두지 않은 완화" 이지 "날짜 없는 예외" 가 아니다.

★ 규칙을 낮추지 않고 예외를 뒀다. 승인을 0으로 내리면 팀이 돌아왔을 때
  낮은 채로 남는다. 예외는 지우면 끝난다. **위 표(§12-1)를 안 고치는
  이유가 그것이다** — 이 저장소는 팀 운영 방식을 기록으로 남긴다.

★ **`actor_id 5` 는 사람 수가 아니라 역할 번호다.**"""

# ── ② admin 명단 ─────────────────────────────────────────────────
A_ANCHOR = "★ **저장소 admin 은 넷이다.**\n\n    diyon13  gayeoniii  marscoolcat  wlsdnr052475\n"

A_NEW = """★ **저장소 admin 은 하나다(2026-09-12~).**

    CleverAIFox

이관 전 넷은 기록으로 남긴다 — `diyon13` · `gayeoniii` · `marscoolcat` ·
`wlsdnr052475`. 개인 저장소라 팀 핸들을 쓸 수 없고 `CODEOWNERS` 도
단독 소유로 정리했다. **이관의 결과이지 고장이 아니다.**
"""

# ── ③ ruleset_check — 선언된 bypass + 회수 조건 ──────────────────
R_ANCHOR = '''            bad.append(f"{name}: bypass actor {who}"'''

R_NEW = '''            # ★ 선언된 예외는 통과시킨다. MASTER §12-1a (2026-09-12).
            #   개인 저장소라 승인 1을 혼자 만족할 수 없다. 규칙을 낮추지
            #   않고 예외를 뒀다. **회수는 날짜가 아니라 조건이다** —
            #   협업자가 둘이 되면 아래에서 운다.
            if set(who) <= BYPASS_DECLARED:
                continue
            bad.append(f"{name}: bypass actor {who}"'''

R_RECALL_ANCHOR = '''    admins = sorted(c["login"] for c in _gh(f"repos/{REPO}/collaborators")
                    if (c.get("permissions") or {}).get("admin"))
'''

R_RECALL = '''    people = _gh(f"repos/{REPO}/collaborators")

    # ★ 회수 조건. §12-1a 가 "본인 외 협업자가 생기면 제거한다" 고 적었고
    #   여기가 그것을 **실제로 거는** 자리다. 문서만 적으면 잊는다 —
    #   `contract.yml` 죽은 게이트가 CI 에서 한 번도 안 돌았던 그 모양이다.
    if len(people) > 1 and BYPASS_DECLARED:
        bad.append(
            f"bypass 회수 조건이 찼다 — 협업자 {len(people)}명"
            "\\n      ★ MASTER §12-1a 의 예외는 '본인 외 협업자가 생기면"
            "\\n        제거한다' 는 조건부다. 지금이 그때다."
            "\\n        룰셋 셋에서 bypass_actors 를 비우고 §12-1a 를 회수로 고쳐라")

    admins = sorted(c["login"] for c in people
                    if (c.get("permissions") or {}).get("admin"))
'''

R_CONST = '''# ★ MASTER §12-1a 가 선언한 예외. 여기 없는 bypass 는 운다.
#   "RepositoryRole:5" 는 Repository admin 역할이다 — 개인이 아니라 역할에 준다.
BYPASS_DECLARED = {"RepositoryRole:5(always)"}

ADMINS ='''

EDITS: list[tuple[str, str, str, str]] = [
    ("docs/MASTER.md", M_ANCHOR, M_NEW, "이번엔 영구다"),
    ("docs/MASTER.md", A_ANCHOR, A_NEW, "저장소 admin 은 하나다"),
    ("tools/ruleset_check.py", R_ANCHOR, R_NEW, "if set(who) <= BYPASS_DECLARED"),
    ("tools/ruleset_check.py", R_RECALL_ANCHOR, R_RECALL, "bypass 회수 조건이 찼다"),
    ("tools/ruleset_check.py", "ADMINS =", R_CONST, "BYPASS_DECLARED = {"),
]


def _names(src: str) -> set[str]:
    out: set[str] = set()
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    by_file: dict[str, list[tuple[str, str, str]]] = {}
    for rel, old, new, done in EDITS:
        by_file.setdefault(rel, []).append((old, new, done))

    changed = skipped = 0
    for rel, pairs in by_file.items():
        p = ROOT / rel
        before = p.read_text(encoding="utf-8")
        text = before
        for old, new, done in pairs:
            if done in text:
                skipped += 1
                continue
            if text.count(old) != 1:
                sys.exit(f"★ {rel} — 대상이 {text.count(old)}곳이다. 멈춘다.\n{old[:80]!r}")
            text = text.replace(old, new)
            changed += 1
        if text == before:
            print(f"  = {rel}  이미 적용됨")
            continue
        if rel.endswith(".py"):
            lost = _names(before) - _names(text)
            if lost:
                sys.exit(f"★ {rel} — 이름이 사라진다: {sorted(lost)}")
            ast.parse(text)
        print(f"  {'✓' if a.apply else '·'} {rel}")
        if a.apply:
            p.write_text(text, encoding="utf-8")

    print(f"\n변경 {changed} · 건너뜀 {skipped}"
          + ("" if a.apply else "   ★ dry-run. --apply 를 붙일 것"))
    if a.apply:
        print("\n다음 — uv run python tools/ruleset_check.py")
        print("       ★ 빨간불이 전부 꺼져야 한다. 선언과 실물이 같아졌다.")
        print("       ★ 그리고 일부러 깨뜨려 본다 — BYPASS_DECLARED 를")
        print("         빈 집합으로 바꿔 돌리면 셋이 다시 울어야 한다(원칙 ④).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
