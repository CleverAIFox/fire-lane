#!/usr/bin/env python3
"""
obligations.py — 새 파일에 따라붙는 **등재 의무**를, 이미 그 의무를 지키는 검사에게 물어 **이름으로** 댄다.  (PLAN #199)

    uv run python tools/obligations.py --new               새 파일(추적 안 된 것 · 스테이징한 것 · **푸시 범위에서 커밋된 것**)의 빠진 의무
    uv run python tools/obligations.py --file tools/x.py   그 파일의 빠진 의무
    uv run python tools/obligations.py --table             종류 → 의무 → 그 의무를 지키는 검사 (도출된 표)

── 왜 있나 ─────────────────────────────────────────────────────
새 도구 · 새 시험 · 새 절을 두면 의무가 종류마다 따라붙는다 — 머리말 「부류」(`toolclass`) · 「밖」(`scopedecl`) · MASTER §22·§23 등재(`sealcov`) …
각 검사가 따로 우니 사람은 **빨강이 뜬 순서대로** 하나씩 고친다. 2026-11-06 의 빨강 여섯과 11-07 의 열셋이 전부 이 하나에서 났다.
이 도구는 **하나씩 우는 대신 한 번에 무엇이 빠졌는지 이름을 댄다** — 「무언가 빠졌다」가 아니라 「`밖` 이 빠졌다」.

★ **정본은 기존 선언이다 — 표를 새로 세우지 않는다**(사람이 골랐다). 의무마다 정본이 이미 있다 — `sealcov` 가 MASTER §22·§23 의 본문 지목을,
  `toolclass` · `scopedecl` 이 머리말을. 이 표는 그 검사들의 **판정 함수를 부를 뿐**이고 의무의 내용을 한 줄도 다시 적지 않는다.
  검사가 바뀌면 표가 따라간다 — 표가 따로 낡을 자리가 없다. 같은 판단을 두 자리에 적어 한쪽만 고쳐지는 병(`.gitleaks.toml` · `plan_renumber` 정규식)을 안 만든다.

★ **새 절 · 새 대장 항목도 이름으로 댄다**(2026-11-08 · PLAN #199 ④) — 푸시 범위의 밑에서 작업 트리까지의 `git diff` 로 **새로 더해진 `#` 제목 줄**을 찾아 그 절만 `dms`(칸 · 물림 · 하위 수) ·
  `measurecols`(쓴 칸 · `none:` 선언)에 묻고, 새 `datasets` 키는 `firelane.authority`(받은 경로 괄호)에 묻는다. 받은 경로 판정은 시험 안에 살았다 — 한 벌로 꺼냈다.
★ **아직 도출 못 한 의무는 표에 「미도출」로 적는다**(`NOT_DERIVED`) — 대장을 건드릴 때의 봉인지(`shardseal`)뿐이다. 있는 척하지 않는다.

IN    `toolclass.classify` · `scopedecl.measure` · `sealcov.survey` · `dms` · `measurecols` · `authority` 의 판정 · git 의 새 파일 · 푸시 범위의 밑(`@{u}` · `origin/dev` 와의 merge-base)에서 작업 트리까지의 `git diff`
OUT   화면 · 종료 코드(빠진 의무가 있으면 1). 아무것도 안 쓴다
PARAM NOT_DERIVED
밖    **의무가 옳은가는 안 본다** — 검사가 그렇다고 하면 그렇다. 봉인지 의무는 안 든다(위 「미도출」). **옛 절 · 옛 대장 항목의 빚은 안 센다**(래칫이 센다) — 새로 더해진 것만 본다.
      **고치지 않는다** — 어느 의무가 빠졌는지와 그 검사가 무엇이라 하는지만 낸다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398 — 어느 관문에도 안 올렸다)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import dms
import scopedecl
import sealcov
import toolclass

from firelane import authority, ledger, measurecols

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
               "어느 절의 **산문**이든 그 파일을 백틱 경로로 지목해야 `sealcov` 가 덮인 것으로 센다 — 관례의 자리는 MASTER §22(화면) · §23(가장자리 · 검사)의 표다"),
    Obligation("머리말 「부류」", "tools/toolclass.py", "`tools/` 의 도구(진입점이 아니면 `부류  몸통`)",
               "머리말에 `부류  조사|절차|생산|몸통` 한 줄을 적는다(verify · CI 가 부르면 관문이라 안 적는다)"),
    Obligation("머리말 「밖」", "tools/scopedecl.py", "`tools/` 의 도구 · `tests/test_*.py`",
               "머리말에 `밖  …` 칸을 적는다 — 이 도구가 **안 보는 것**"),
    Obligation("PLAN 본문 표지", "tools/tasktpl.py", "PLAN.md 를 읽는 `tests/test_*.py`(PLAN #204)",
               "머리말(모듈 docstring)에 `PLAN 본문  규칙 — <무엇을 무는가>` 또는 `PLAN 본문  규칙 없음 — <사유>` 한 줄을 적는다"),
)

#: 아직 파일 단위로 도출 못 한 의무 — 있는 척하지 않는다. (종류 → 의무 · 그 검사)
NOT_DERIVED = (
    ("대장을 건드릴 때", "봉인지(`src/firelane/shardseal.py`)", "ingest 가 짓는 것이라 사람이 적는 의무인지 못 가렸다 — 모르는 것을 있는 척 도출하지 않는다"),
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
    import tasktpl  # 늦게 든다 — `tasktpl` 이 이 모듈을 맨 위에서 가져온다(순환을 피한다)
    readers = tasktpl.plan_reader_tests()
    return {
        "PLAN 본문 표지 분모": {_rel(p) for p in readers},
        "PLAN 본문 표지 빠짐": {_rel(p) for p in readers if tasktpl.plan_marker(p) is None},
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


def _git(args: list[str], root: Path) -> str | None:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else None


def push_base(root: Path = ROOT) -> str | None:
    """푸시 범위의 **밑**(커밋) — `@{u}` 와의 merge-base, 없으면 `origin/dev` 와의 merge-base. 둘 다 못 읽으면 `None`(작업 트리만 본다).

    ★ 2026-11-12 (DECISIONS §705 · `#216` 한계 ②). 종전 `--new` 는 **커밋 안 된 파일만** 봤다 — 새 파일을 만들자마자 커밋하면 그 창을 안 지났다
      (오늘 두 번: `test_silent_branches` · `motion.ts`). 기준을 푸시 범위 ∪ 작업 트리로 넓힌다 — `tools/testpick.changed_files` 와 같은 기준이다.
    """
    for ref in ("@{u}", "origin/dev"):
        out = _git(["merge-base", "HEAD", ref], root)
        if out and out.strip():
            return out.strip()
    return None


def new_files(root: Path = ROOT, base: str | None = None) -> list[str]:
    """새 파일 — 추적 안 된 것 · 스테이징한 것 · **푸시 범위에서 커밋으로 더해진 것**(지금도 있는 것만)."""
    out = set()
    st = _git(["status", "--porcelain=v1", "--untracked-files=all"], root)
    if st is None:
        raise subprocess.CalledProcessError(1, "git status")
    out.update(ln[3:] for ln in st.splitlines() if ln[:2] in ("??", "A ", "AM"))
    b = base if base is not None else push_base(root)
    if b:
        added = _git(["diff", "--name-only", "--diff-filter=A", "--no-renames", b], root) or ""
        out.update(f for f in added.split("\n") if f and (root / f).is_file())
    return sorted(out)


#: 의무를 지키는 문서 — dms 의 절 ID 가 이 문서들에서 나온다.
DOC_FILES = ("docs/MASTER.md", "docs/DECISIONS.md", "docs/PLAN.md", "README.md")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def added_headings(diff: str) -> dict[str, set[int]]:
    """`git diff -U0` 본문에서 **새로 더해진 `#` 제목 줄**의 (문서 → 새 파일의 줄 번호). 절의 신설을 이 줄로 가른다."""
    out: dict[str, set[int]] = {}
    rel, at = "", 0
    for ln in diff.splitlines():
        if ln.startswith("+++ "):
            rel = ln[6:] if ln.startswith("+++ b/") else ""
        elif (m := _HUNK.match(ln)):
            at = int(m.group(1))
        elif ln.startswith("+") and not ln.startswith("+++"):
            if rel and ln.startswith("+#"):
                out.setdefault(rel, set()).add(at)
            at += 1
    return out


def _diff_head(root: Path = ROOT, base: str | None = None) -> str:
    """문서의 변경 — **푸시 범위 ∪ 작업 트리**(`base` → 작업 트리). 범위를 못 읽으면 `HEAD` → 작업 트리."""
    b = base if base is not None else push_base(root)
    return _git(["diff", b or "HEAD", "-U0", "--no-color", "--", *DOC_FILES], root) or ""


def section_unmet(added: dict[str, set[int]], data: dict | None = None) -> dict[str, list[str]]:
    """새 절 → 빠진 의무. **판정은 기존 검사가 한다** — `dms`(칸 · 물림 · 하위 수) · `measurecols`(쓴 칸 · `none:` 선언). 여기는 새 절만 거른다."""
    d = data if data is not None else dms.scan()
    new = [r for r in d["rows"] if r["line"] in added.get(r["doc"], set())]
    out: dict[str, list[str]] = {}
    if not new:
        return out
    _said, mute = dms.inherit_split(d)
    parents = {f"{r['id'].partition('/')[0]}/{r['id'].partition('/')[2].split('/')[0].split('-')[0]}" for r in new}
    count_bad = dms.inherit_counts(d)
    for r in new:
        miss = []
        if r["state"] == "blank":
            miss.append("칸 없음 — 절에 `유병률` · `강제자` 칸이 없다(tools/dms.py)")
        if r["id"] in mute:
            miss.append("물림이 말이 없다 — 부모 칸이 하위 절을 덮는다고 안 적었다(tools/dms.py)")
        if miss:
            out[r["id"]] = miss
    for ln in count_bad:                       # 「하위 N」 이 실제와 다르다 — 새 절이 늘렸다
        pid = next((p for p in parents if f"  {p}  " in ln), None)
        if pid:
            out.setdefault(pid, []).append(ln.strip() + " (tools/dms.py)")
    return out


def measure_unmet(added: dict[str, set[int]], decisions: str | None = None, sources: dict | None = None) -> dict[str, list[str]]:
    """새 DECISIONS 측정 절의 「쓴 칸」 머릿줄 · `none:` 선언 — `measurecols.check_section` 이 판정한다."""
    text = decisions if decisions is not None else (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    lines = text.split("\n")
    nums = set()
    for ln in added.get("docs/DECISIONS.md", set()):
        m = re.match(r"## (\d+)\.", lines[ln - 1]) if 0 < ln <= len(lines) else None
        if m:
            nums.add(int(m.group(1)))
    led = sources if sources is not None else ledger.load_sources()
    out: dict[str, list[str]] = {}
    for num, title, body in measurecols.sections(text):
        if num in nums and num >= measurecols.START and (any(w in title for w in measurecols.SCOPE_WORDS) or measurecols.used_line(body) is not None):
            errs = measurecols.check_section(num, title, body, led)
            if errs:
                out[f"DECISIONS/{num}"] = [f"{e} (src/firelane/measurecols.py)" for e in errs]
    return out


def new_datasets(now: dict, before: dict) -> list[str]:
    return sorted(set(now.get("datasets") or {}) - set(before.get("datasets") or {}))


def dataset_unmet(now: dict, before: dict) -> dict[str, list[str]]:
    """새 대장 항목 → 빠진 의무(받은 경로 괄호 · 칸 · 개인 경유). 판정은 `firelane.authority` 한 벌이다."""
    keys = set(new_datasets(now, before))
    sub = {"datasets": {k: v for k, v in (now.get("datasets") or {}).items() if k in keys}}
    out: dict[str, list[str]] = {}
    for line in authority.bad(sub):
        k = line.split(":", 1)[0]
        out.setdefault(k, []).append(line.split(": ", 1)[1] + " (src/firelane/authority.py)")
    return out


def _sources_at_head(root: Path = ROOT, base: str | None = None) -> dict:
    """대장의 **밑** 모습 — 푸시 범위의 밑 커밋(없으면 `HEAD`)의 `sources.yaml`."""
    b = base if base is not None else push_base(root)
    out = _git(["show", f"{b or 'HEAD'}:sources.yaml"], root)
    return ledger.parse(out) if out is not None else {}


def document_unmet() -> dict[str, list[str]]:
    """새 절 · 새 대장 항목의 빠진 의무 — 푸시 범위 ∪ 작업 트리에서 **새로 더해진 것**만 본다(커밋 · 스테이징 여부와 무관)."""
    base = push_base()
    added = added_headings(_diff_head(ROOT, base))
    out = {**section_unmet(added), **measure_unmet(added)}
    out.update({f"대장/{k}": v for k, v in dataset_unmet(ledger.load(), _sources_at_head(ROOT, base)).items()})
    return out


def table() -> str:
    L = ["종류 → 의무 → 그 의무를 지키는 검사  (정본은 검사다 — 이 표는 그 검사의 판정 함수를 부른다)", ""]
    for o in OBLIGATIONS:
        L += [f"  {o.name}", f"      따라붙는 곳  {o.applies}", f"      지키는 검사  {o.owner}", f"      적는 곳      {o.fix}"]
    L += ["", "  미도출 — 파일 단위로 못 묻는다(있는 척하지 않는다)"]
    L += [f"      {kind}: {what}  ← {why}" for kind, what, why in NOT_DERIVED]
    return "\n".join(L)


def render(missing: dict[str, list[Obligation]], docs: dict[str, list[str]] | None = None) -> str:
    docs = docs or {}
    if not missing and not docs:
        return "✓ 빠진 의무가 없다 — 새 파일(등재 · 「부류」 · 「밖」) · 새 절(칸 · 물림 · 쓴 칸) · 새 대장 항목(받은 경로)을 봤다. 봉인지는 미도출이다(`--table`)."
    L = []
    if missing:
        L += [f"✗ 빠진 의무 — 파일 {len(missing)}개", ""]
        for rel, obs in missing.items():
            L.append(f"  {rel}")
            L += [f"      · {o.name}  ({o.owner} 가 운다)\n        {o.fix}" for o in obs]
    if docs:
        L += ([""] if L else []) + [f"✗ 빠진 의무 — 새 절 · 새 대장 항목 {len(docs)}개", ""]
        for key, msgs in docs.items():
            L.append(f"  {key}")
            L += [f"      · {m}" for m in msgs]
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
    docs = document_unmet() if a.new else {}
    if a.new and not files and not docs:
        print("새 파일이 없다 — 추적 안 된 것도 스테이징한 새 것도 없다 · 새 절 · 새 대장 항목도 빠진 의무가 없다")
        return 0
    miss = unmet(files)
    print(render(miss, docs))
    return 1 if miss or docs else 0


if __name__ == "__main__":
    sys.exit(main())
