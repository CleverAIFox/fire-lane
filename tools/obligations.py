#!/usr/bin/env python3
"""
obligations.py — 새 파일에 따라붙는 **등재 의무**를, 이미 그 의무를 지키는 검사에게 물어 **이름으로** 댄다.  (PLAN #199)

    uv run python tools/obligations.py --new               추적 안 된 새 파일 · 스테이징한 새 파일의 빠진 의무
    uv run python tools/obligations.py --file tools/x.py   그 파일의 빠진 의무
    uv run python tools/obligations.py --table             종류 → 의무 → 그 의무를 지키는 검사 (도출된 표)

── 왜 있나 ─────────────────────────────────────────────────────
새 도구 · 새 시험 · 새 절을 두면 의무가 종류마다 따라붙는다 — 머리말 「부류」(`toolclass`) · 「밖」(`scopedecl`) · MASTER §22·§23 등재(`sealcov`) …
각 검사가 따로 우니 사람은 **빨강이 뜬 순서대로** 하나씩 고친다. 2026-11-06 의 빨강 여섯과 11-07 의 열셋이 전부 이 하나에서 났다.
이 도구는 **하나씩 우는 대신 한 번에 무엇이 빠졌는지 이름을 댄다** — 「무언가 빠졌다」가 아니라 「`밖` 이 빠졌다」.

★ **정본은 기존 선언이다 — 표를 새로 세우지 않는다**(사람이 골랐다). 의무마다 정본이 이미 있다 — `sealcov` 가 MASTER §22·§23 의 본문 지목을,
  `toolclass` · `scopedecl` 이 머리말을. 이 표는 그 검사들의 **판정 함수를 부를 뿐**이고 의무의 내용을 한 줄도 다시 적지 않는다.
  검사가 바뀌면 표가 따라간다 — 표가 따로 낡을 자리가 없다. 같은 판단을 두 자리에 적어 한쪽만 고쳐지는 병(`.gitleaks.toml` · `plan_renumber` 정규식)을 안 만든다.

★ **아직 도출 못 한 의무는 표에 「미도출」로 적는다**(`NOT_DERIVED`) — 새 절의 하위 번호 · 「쓴 칸」 머릿줄 · 대장을 건드릴 때의 받은 경로 괄호 · `none:` 선언 · 봉인지.
  그 검사들은 파일 단위 판정 함수가 없거나 절 단위다. 있는 척하지 않는다.

IN    `toolclass.classify` · `scopedecl.measure` · `sealcov.survey` 의 판정 · git 의 새 파일
OUT   화면 · 종료 코드(빠진 의무가 있으면 1). 아무것도 안 쓴다
PARAM NOT_DERIVED
밖    **의무가 옳은가는 안 본다** — 검사가 그렇다고 하면 그렇다. 절 단위 의무(새 절 · 대장)는 이 도구가 안 든다(위 「미도출」).
      **고치지 않는다** — 어느 의무가 빠졌는지와 그 검사가 무엇이라 하는지만 낸다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398 — 어느 관문에도 안 올렸다)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import scopedecl
import sealcov
import toolclass

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Obligation:
    name: str         # 사람이 읽는 이름 — 보고에 그대로 찍힌다
    owner: str        # 그 의무를 지키는 검사(정본)
    applies: str      # 어느 파일에 따라붙는가 — 검사의 **분모**에서 온다
    fix: str          # 어디에 무엇을 적는가 — 검사가 우는 문장에서 가져온 한 줄


#: 파일 단위로 도출한 의무. **검사가 정본이다** — 여기는 이름표뿐이다.
OBLIGATIONS = (
    Obligation("MASTER §22·§23 등재", "tools/sealcov.py", "손으로 쓴 코드 파일(`.py` `.ts` `.tsx` `.js` `.sh` · 생성물 제외)",
               "MASTER §22(화면) · §23(가장자리 · 검사)의 표에 그 파일을 백틱 경로로 지목하는 줄을 적는다"),
    Obligation("머리말 「부류」", "tools/toolclass.py", "`tools/` 의 도구(진입점이 아니면 `부류  몸통`)",
               "머리말에 `부류  조사|절차|생산|몸통` 한 줄을 적는다(verify · CI 가 부르면 관문이라 안 적는다)"),
    Obligation("머리말 「밖」", "tools/scopedecl.py", "`tools/` 의 도구 · `tests/test_*.py`",
               "머리말에 `밖  …` 칸을 적는다 — 이 도구가 **안 보는 것**"),
)

#: 아직 파일 단위로 도출 못 한 의무 — 있는 척하지 않는다. (종류 → 의무 · 그 검사)
NOT_DERIVED = (
    ("새 절", "하위 번호 · 「쓴 칸」 머릿줄", "tools/dms.py · tools/measurecols.py — 절 단위 판정이라 파일 하나로 못 묻는다"),
    ("대장을 건드릴 때", "받은 경로 괄호 · `none:` 선언 · 봉인지(`ledger_*` · `shardseal`)", "대장 검사들 — 파일 단위 판정 함수가 없다"),
)


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _state() -> dict[str, set[str]]:
    """검사마다 **지금 우는 파일 집합**과 **분모**. 검사의 판정 함수를 부를 뿐 — 규칙을 다시 적지 않는다."""
    rows = toolclass.classify()
    bad, none = toolclass.judge(rows)
    bad_files = {ln.split()[0] for ln in bad}
    ens, no_decl, _selftest, _gap = scopedecl.measure()
    s = sealcov.survey()
    return {
        "MASTER §22·§23 등재 분모": set(sealcov.denominator()),
        "MASTER §22·§23 등재 빠짐": set(s["빈 곳"]),
        "머리말 「부류」 분모": set(rows),
        "머리말 「부류」 빠짐": set(none) | bad_files,
        "머리말 「밖」 분모": {_rel(p) for p in ens},
        "머리말 「밖」 빠짐": {_rel(p) for p in no_decl},
    }


#: ★ 이것이 **먼저**다 — 검사들의 분모는 git 이 **추적하는** 파일이라, 추적 전의 새 파일은 어느 검사에도 안 보인다. 그대로 두면 「빠진 의무 없음」이 **거짓 초록**이다(§278-10).
UNTRACKED = Obligation("추적(`git add`)", "tools/docseal.py (§278-10)", "git 이 아직 모르는 새 파일",
                       "`git add` 를 먼저 한다 — 추적 전에는 위 세 검사가 이 파일을 분모에 안 센다")


def tracked() -> set[str]:
    r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60)
    return set(r.stdout.split("\n"))


def unmet(rels: list[str], state: dict[str, set[str]] | None = None, known: set[str] | None = None) -> dict[str, list[Obligation]]:
    """파일 → 빠진 의무들. 따라붙지 않는 의무는 세지 않는다(분모에 없으면 빠진 것이 아니다).

    추적 안 된 파일은 **다른 의무를 판정하지 않고** 「추적」 하나만 댄다 — 판정할 수 없는 것을 「없음」으로 읽지 않는다.
    """
    st = state if state is not None else _state()
    trk = known if known is not None else tracked()
    out: dict[str, list[Obligation]] = {}
    for rel in rels:
        if rel not in trk:
            out[rel] = [UNTRACKED]
            continue
        miss = [o for o in OBLIGATIONS if rel in st[f"{o.name} 분모"] and rel in st[f"{o.name} 빠짐"]]
        if miss:
            out[rel] = miss
    return out


def new_files() -> list[str]:
    """추적 안 된 새 파일과 스테이징한 새 파일."""
    r = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60)
    return sorted(ln[3:] for ln in r.stdout.splitlines() if ln[:2] in ("??", "A ", "AM"))


def table() -> str:
    L = ["종류 → 의무 → 그 의무를 지키는 검사  (정본은 검사다 — 이 표는 그 검사의 판정 함수를 부른다)", ""]
    for o in OBLIGATIONS:
        L += [f"  {o.name}", f"      따라붙는 곳  {o.applies}", f"      지키는 검사  {o.owner}", f"      적는 곳      {o.fix}"]
    L += ["", "  미도출 — 파일 단위로 못 묻는다(있는 척하지 않는다)"]
    L += [f"      {kind}: {what}  ← {why}" for kind, what, why in NOT_DERIVED]
    return "\n".join(L)


def render(missing: dict[str, list[Obligation]]) -> str:
    if not missing:
        return "✓ 빠진 의무가 없다 — 도출한 의무(MASTER §22·§23 · 「부류」 · 「밖」)만 봤다. 새 절 · 대장 의무는 미도출이다(`--table`)."
    L = [f"✗ 빠진 의무 — 파일 {len(missing)}개", ""]
    for rel, obs in missing.items():
        L.append(f"  {rel}")
        L += [f"      · {o.name}  ({o.owner} 가 운다)\n        {o.fix}" for o in obs]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="obligations", description=__doc__.split("──")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--new", action="store_true")
    g.add_argument("--file", nargs="+", metavar="PATH")
    g.add_argument("--table", action="store_true")
    a = ap.parse_args(argv)
    if a.table:
        print(table())
        return 0
    files = new_files() if a.new else [Path(f).as_posix() for f in a.file]
    if a.new and not files:
        print("새 파일이 없다 — 추적 안 된 것도 스테이징한 새 것도 없다")
        return 0
    miss = unmet(files)
    print(render(miss))
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
