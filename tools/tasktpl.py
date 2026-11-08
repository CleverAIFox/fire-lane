#!/usr/bin/env python3
"""
tasktpl.py — LLM 에게 주는 **작업 지시문 틀**을 저장소에서 읽어 찍어 낸다.  (PLAN #204)

    uv run python tools/tasktpl.py                 틀을 화면에 낸다
    uv run python tools/tasktpl.py --write PATH    그 경로에 쓴다
    uv run python tools/tasktpl.py --check PATH    PATH 가 지금 틀과 다르면 rc 1

── 왜 있나 ─────────────────────────────────────────────────────
틀이 불변량 수 · 관문 이름 · 등재 의무를 **손으로 적으면** MASTER · PLAN · 도구의 사본이 되고 사본은 한쪽만 고쳐지는 날이 온다
(`.claude/TASK_TEMPLATE.md` 가 `test_no_fifth_doc` 에 물려 되돌려졌다). 2026-11-07 에는 지시문에서 금지 블록을 빠뜨렸고 그 판에서
`evalset_2610.key.json` 봉인이 열렸다. 정본은 하나고 틀은 산출이다 — `render_workflow.py` 가 MASTER §12 를 굽는 것과 같은 꼴이다.

── 무엇이 어디서 오나 ───────────────────────────────────────
  먼저 읽을 절         `READ_FIRST` — 문서 · 절 이름표. **그 절이 실재하는지**를 이 도구가 문서 제목에서 확인한다(없으면 rc 1).
  불변량 수            `docnum_check.verdicts()` — MASTER 의 판정 표를 채우는 그 함수. 손으로 안 적는다.
  푸시를 막는 관문      `.githooks/pre-push.gates` 의 이름 열.
  푸시 전 한 명령의 축   `pushready.CHECKS` 의 키와 그 도구 머리말 「무엇을 보나」 줄.
  새 파일의 등재 의무    `obligations.OBLIGATIONS`.
  ★ **사람이 이번 일에 거는 규칙**(푸시 금지 · 도장 금지 …)은 저장소에 없다 — 틀에는 빈 칸 한 줄만 두고 안 지어낸다.

IN    위의 다섯 곳 읽기 전용 · `--check` 의 PATH
OUT   화면 · `--write` 가 준 경로 한 파일. 기본 위치가 없다 — 어디에 두는가는 사람이 정한다(PLAN #204)
PARAM READ_FIRST
밖    **틀이 지시문으로서 좋은가는 안 본다.** 어느 지시문이 규칙을 지켰는지도 안 본다.
      **금지 목록의 정본을 아직 모른다**(위 ★) — 봉인(`evalset_2610.key.json`)을 지키는 줄은 이 도구가 못 낸다.
부류  조사   사람이 손으로 돌려 틀을 낸다. 어느 관문에도 안 올렸다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import docnum_check
import obligations
import pushready

ROOT = Path(__file__).resolve().parent.parent
GATES = ROOT / ".githooks" / "pre-push.gates"

#: (문서, 절 이름표). 지시문이 「먼저 읽어라」 하는 곳. 이름표가 문서 제목에 **실재해야** 한다.
READ_FIRST = (
    ("docs/PLAN.md", "0-1"), ("docs/PLAN.md", "0-2"),
    ("docs/MASTER.md", "0"), ("docs/MASTER.md", "22"), ("docs/MASTER.md", "23"),
)

_HEAD = re.compile(r"^#{2,4} (\d+(?:-\d+)*)\.")


def _sections(rel: str) -> set[str]:
    return {m.group(1) for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines() if (m := _HEAD.match(ln))}


def missing_sections() -> list[str]:
    """`READ_FIRST` 중 문서에 없는 절. 비면 모두 실재한다."""
    cache: dict[str, set[str]] = {}
    out = []
    for rel, sec in READ_FIRST:
        have = cache.setdefault(rel, _sections(rel))
        if sec not in have:
            out.append(f"{rel} §{sec}")
    return out


def gate_names() -> list[str]:
    return [ln.split("\t", 1)[0] for ln in GATES.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def axes() -> list[str]:
    """`pushready` 의 축 — 키와 머리말의 한 줄 설명."""
    said = {m.group(1): m.group(2) for ln in (pushready.__doc__ or "").splitlines() if (m := re.match(r"\s+(㉠|㉡|㉢|㉣|㉤|㉥|㉦|㉧) (.+)", ln))}
    return [f"{k} {said.get(k, '(머리말에 설명이 없다)')}" for k, _ in pushready.CHECKS]


def render(verdicts: dict[str, int] | None = None) -> str:
    v = verdicts if verdicts is not None else docnum_check.verdicts()
    L = ["# 작업 지시문 틀 — 이 파일은 `tools/tasktpl.py` 가 찍는다. 손으로 고치지 않는다.", ""]
    L += ["## 먼저 읽어라 — 세금은 저장소가 안다. 받아쓴 목록을 믿지 마라"]
    L += [f"- {rel} §{sec}" for rel, sec in READ_FIRST]
    L += [f"- {GATES.relative_to(ROOT)} — 무엇이 푸시를 막는가", "- `uv run python tools/obligations.py --new` — 새 파일의 등재 의무를 이름으로 댄다", ""]
    L += ["## 불변량 — 움직이면 판정이 움직인 것이다"]
    L += [f"- {k} {v[k]}" for k in ("clear", "needs_cv", "blocked", "unknown") if k in v]
    if "n" in v:
        L.append(f"- 구간 {v['n']}")
    L += ["", "## 푸시를 막는 관문(`pre-push.gates`)"] + [f"- {n}" for n in gate_names()]
    L += ["", "## 푸시 전 한 명령 — `uv run python tools/pushready.py`"] + [f"- {a}" for a in axes()]
    L += ["", "## 새 파일에 따라붙는 의무(`obligations --new` 가 이름으로 댄다)"]
    L += [f"- {o.name} — {o.applies}: {o.fix}" for o in obligations.OBLIGATIONS]
    L += ["", "## 이번 일에 거는 규칙 — 사람이 적는다(저장소에 정본이 없다)", "- (여기)", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="작업 지시문 틀을 저장소에서 찍는다")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", metavar="PATH")
    g.add_argument("--check", metavar="PATH")
    a = ap.parse_args(argv)
    miss = missing_sections()
    if miss:
        print(f"✗ 먼저 읽을 절이 문서에 없다: {', '.join(miss)}", file=sys.stderr)
        return 1
    text = render()
    if a.check:
        p = Path(a.check)
        if not p.is_file() or p.read_text(encoding="utf-8") != text:
            print(f"✗ {p} 가 지금 틀과 다르다 — `--write {p}` 로 다시 찍는다(손으로 고친 것은 사라진다)", file=sys.stderr)
            return 1
        print(f"✓ {p} 가 틀과 같다")
        return 0
    if a.write:
        Path(a.write).write_text(text, encoding="utf-8")
        print(f"틀을 {a.write} 에 썼다")
        return 0
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
