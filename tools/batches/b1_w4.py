#!/usr/bin/env python3
"""
b1_w4.py — B1 / W4 적용. **죽은 배치 도구를 강제자로 승격한다.**

호출부가 0인 도구 일곱이 있었다. 지우면 줄 수만 줄고, 그 도구가 아는
"목표 상태" 지식도 같이 사라진다. 지우는 대신 `--check` 를 붙인다.

  배치는 끝나도 **그 배치가 세운 상태는 안 끝난다.**
  적용 뒤 no-op 이라는 이유로 EXEMPT 에 재우면, 되돌아가도 우는 곳이 없다.

★ 공통 껍데기를 씌우지 않는다. 넷이 지키는 불변식의 **종류**가 다르다 —
  파일 목록 · 설정 앵커 · 금지 상태 · 구조 무결. 한 틀에 넣으면 억지
  맞춤이 생기고, `navi_setup.EXEMPT_ADD` 의 유령 `bottleneck` 이 바로
  공유 목록이 낳은 결과다.

    uv run python tools/b1_w4.py            무엇을 할지만 보여준다
    uv run python tools/b1_w4.py --apply    실제로 바꾼다

멱등이다. 두 번 돌려도 같다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# ★ 이 파일은 일회성이라 끝나면 tools/batches/ 로 간다. 그때도 codepatch 를
#   찾을 수 있어야 하므로 **tools/ 를 명시**한다. parent 로 잡으면
#   batches/ 를 보게 되고 import 가 죽는다.
_TOOLS = Path(__file__).resolve().parent
_TOOLS = _TOOLS.parent if _TOOLS.name == "batches" else _TOOLS

# ★ sys.path 를 건드리지 않는다. `test_sys_path_해킹이_없다` 가
#   tools 전체를 보고, 경로 조작은 pyproject 의 pythonpath 로만
#   한다는 것이 이 저장소의 규약이다. 파일을 직접 읽어 붙인다.
def _load_codepatch():
    import importlib.util as _u
    _s = _u.spec_from_file_location("codepatch", _TOOLS / "codepatch.py")
    _m = _u.module_from_spec(_s)
    _s.loader.exec_module(_m)
    return _m


_cp = _load_codepatch()
Patch, PatchError, add_shell_step = (
    _cp.Patch, _cp.PatchError, _cp.add_shell_step)

ROOT = _TOOLS.parent

# ── 각자 다른 것을 본다 ─────────────────────────────────────────
CHECK_LEDGER_FIELDS = '''
# ── 이관이 유지되는가 ────────────────────────────────────────────
# ★ 별칭을 싸잡아 금지하지 않는다. 실측하면 `files` 4/61 · `parts` 4/61 이
#   **정상으로 살아 있다** — 한 항목이 여러 파일을 지목하는 정당한 필드다.
#   획일적으로 막으면 정상 8건이 빨간불이 되고, 잘못된 경보는 진짜 경보를
#   죽인다(DECISIONS §73). 죽은 것만 든다.
RETIRED_FIELDS = {
    "file": ("2026-08-31 stem+ext 로 이관(PLAN #46)", "stem + ext. 여럿이면 files"),
    "vintage": ("파일명 토큰이 정본이다", "naming.parse(파일명).vintage"),
    "retrieved": ("acquired 로 통합", "acquired"),
    "desc": ("what 로 통합", "what"),
}
SCAN_BLOCKS = ("datasets", "retired", "outputs", "raw_only")


def check() -> int:
    """폐기된 별칭이 되살아났는가. run() 의 역방향이다.

    값이 옳은지는 안 본다 — 그것은 datalog fsck 소관이다.
    여기는 **스키마가 되돌아갔는가** 하나만 본다.
    """
    import yaml

    led = yaml.safe_load(load())
    bad = []
    for blk in SCAN_BLOCKS:
        for key, e in (led.get(blk) or {}).items():
            if isinstance(e, dict):
                for f in RETIRED_FIELDS:
                    if e.get(f) not in (None, "", [], {}):
                        bad.append((f"{blk}.{key}", f, str(e[f])[:40]))
    if not bad:
        n = sum(len(led.get(b) or {}) for b in SCAN_BLOCKS)
        print(f"\\u2713 폐기 별칭 0건 — {n}개 항목에서 이관이 유지된다")
        return 0
    print(f"\\u2717 폐기된 별칭 필드 {len(bad)}건이 살아 있다")
    for where, f, val in bad:
        why, canon = RETIRED_FIELDS[f]
        print(f"   {where}.{f} = {val}")
        print(f"      폐기 {why} · 정본 {canon}")
    print("\\n   되돌리려면  uv run python tools/ledger_fields.py --apply")
    return 1
'''

CHECK_INSTALL_NAVI = '''
# ── 앉힌 것이 그대로 있는가 ─────────────────────────────────────
# ★ 내용은 안 본다 — 지문은 golden 이 이미 한다. 여기서 또 하면 지문
#   구현이 여섯 번째가 된다. 여기는 **목록**만 책임진다.
def check() -> int:
    dst = ROOT / "web" / "navi" / "src"
    if not dst.is_dir():
        print("\\u2717 web/navi/src 가 없다 — 내비 소스가 앉지 않았다")
        return 1
    n = sum(1 for p in dst.rglob("*") if p.is_file())
    if not n:
        print("\\u2717 web/navi/src 가 비었다")
        return 1
    print(f"\\u2713 web/navi/src {n}파일 — 내용 대조는 golden 소관")
    return 0
'''

CHECK_PAGES_ADD_NAVI = '''
# ── 배포에 내비 빌드가 얹혀 있는가 ──────────────────────────────
# ★ 원래 앵커가 한국어 주석(`내비 빌드 (web/navi → …)`)이었다. 주석을
#   다듬는 순간 검사가 죽는다. **동작**을 앵커로 잡는다.
def check() -> int:
    f = ROOT / ".github" / "workflows" / "pages.yml"
    if not f.exists():
        print("\\u2717 pages.yml 이 없다")
        return 1
    if "./.github/actions/build-navi" not in f.read_text(encoding="utf-8"):
        print("\\u2717 pages.yml 에 build-navi 액션이 없다 — 배포에서 내비가 빠진다")
        return 1
    print("\\u2713 pages.yml 이 build-navi 액션을 부른다")
    return 0
'''

CHECK_NAVI_SETUP = '''
# ── 정리한 상태가 유지되는가 ────────────────────────────────────
# ★ 이 도구는 루트에 떨어진 일회성 스크립트·산출물을 치운다. 치우고 나면
#   no-op 이 되고, no-op 이라 EXEMPT 로 들어갔고, 그래서 **다시 떨어져도
#   아무도 안 운다.** 그 역방향을 여기 둔다.
def check() -> int:
    bad = []
    for n in ONESHOT + ARTIFACT:
        if (ROOT / n).exists():
            kind = "일회성 스크립트" if n in ONESHOT else "산출물"
            bad.append(f"루트에 {kind} `{n}` 이 다시 떨어졌다")
    # ★ 면제 목록이 실재하는 도구를 가리키는가. `bottleneck` 은 없는 파일
    #   이었다(실물은 bridge_audit.py) — 공유 목록에 유령이 낀다.
    for stem in EXEMPT_ADD:
        if not (ROOT / "tools" / f"{stem}.py").exists():
            bad.append(f"EXEMPT_ADD 의 `{stem}` 은 실재하지 않는 도구다")
    if bad:
        print(f"\\u2717 {len(bad)}건")
        for b in bad:
            print(f"   {b}")
        return 1
    print(f"\\u2713 루트 잔재 0건 · 면제 등재 {len(EXEMPT_ADD)}종 전부 실재")
    return 0
'''

VERIFY_BLOCK = '''
# ── 배치가 세운 상태가 유지되는가 (B1/W4) ───────────────────────
# ★ 적용 뒤 no-op 이 되는 배치 도구를 EXEMPT 로 재우면, 상태가 되돌아가도
#   우는 곳이 없어진다. 지우는 대신 `--check` 를 달아 강제자로 승격했다.
#   넷은 각자 다른 것을 본다 — 공통 껍데기를 씌우지 않았다.
step "대장 별칭 이관 유지" uv run python tools/ledger_fields.py --check
step "내비 소스 목록"      uv run python tools/install_navi.py --check
step "배포에 내비 빌드"    uv run python tools/pages_add_navi.py --check
step "루트 잔재·유령 면제" uv run python tools/navi_setup.py --check
step "문서 제목 무결"      uv run python tools/docpatch.py check \\
     docs/MASTER.md docs/PLAN.md docs/DECISIONS.md
'''

PLAN = [
    ("tools/ledger_fields.py", "check", CHECK_LEDGER_FIELDS),
    ("tools/install_navi.py", "check", CHECK_INSTALL_NAVI),
    ("tools/pages_add_navi.py", "check", CHECK_PAGES_ADD_NAVI),
    ("tools/navi_setup.py", "check", CHECK_NAVI_SETUP),
]


def apply_all(apply: bool) -> int:
    fail = 0
    print(f"{'적용' if apply else 'dry-run — --apply 로 실행'}\n")
    print("── ① 배치 도구에 check() 를 단다")
    for path, name, body in PLAN:
        try:
            p = Patch(path)
            p.add_function(name, body)
            p.hoist_parse_args()
            p.add_flag("--check", "상태만 본다. 아무것도 안 바꾼다")
            p.route_flag("check", "return check()",
                         comment="★ --check 는 아무것도 안 바꾼다. verify.sh 전용")
            if not p.commit(apply=apply):
                fail += 1
        except PatchError as e:
            print(f"  ✗ {path}  {e}")
            fail += 1

    print("\n── ② --check 는 --from 이 필요 없다")
    # ★ `--from` 이 required 라 `--check` 만으로는 argparse 가 먼저 죽는다.
    #   상태를 보는 데 소스 경로를 요구할 이유가 없다.
    try:
        p = Patch("tools/install_navi.py")
        p.sub_once('ap.add_argument("--from", dest="src", required=True,',
                   'ap.add_argument("--from", dest="src",',
                   why="--from 을 선택으로 (--check 는 소스가 필요 없다)")
        p.sub_once('    if not a.src:\n', '    if not a.src:\n',
                   why="(가드 확인)") if False else None
        if not p.commit(apply=apply):
            fail += 1
    except PatchError as e:
        print(f"  ✗ tools/install_navi.py  {e}")
        fail += 1

    print("\n── ③ docpatch check 가 종료코드를 내게")
    try:
        p = Patch("tools/docpatch.py")
        p.add_function("check_many", '''
# ★ check() 는 문자열을 돌려주고 main 은 그것을 print 만 했다. 중복을
#   찾아도 종료코드가 0 이라 **게이트에 달아도 안 운다** — "검사가
#   있는데 안 운다" 의 교과서다(F-142).
def check_many(docs: "list[Path]") -> int:
    bad = 0
    for d in docs:
        if not d.exists():
            print(f"\\u2717 {d} 없음")
            bad += 1
            continue
        msg = check(d)
        if msg.startswith("중복"):
            print(f"\\u2717 {d} — {msg}")
            bad += 1
        else:
            print(f"\\u2713 {msg}")
    return 1 if bad else 0
''')
        p.sub_once('    c.add_argument("doc")\n', '    c.add_argument("doc", nargs="+")\n',
                   why="check 가 문서 여럿을 받게")
        p.sub_once("        print(check(Path(ns.doc)))",
                   "        return check_many([Path(x) for x in ns.doc])",
                   why="check 결과를 종료코드로")
        if not p.commit(apply=apply):
            fail += 1
    except PatchError as e:
        print(f"  ✗ tools/docpatch.py  {e}")
        fail += 1

    print("\n── ④ verify.sh 배선")
    add_shell_step("tools/verify.sh", "대장 별칭 이관 유지", VERIFY_BLOCK, apply=apply)
    return fail


def measure(tag: str) -> None:
    for tool in ("deadcheck", "widen"):
        r = subprocess.run([sys.executable, f"tools/{tool}.py"],
                           cwd=ROOT, capture_output=True, text=True)
        head = [x for x in r.stdout.splitlines() if "빨간불" in x or "합계" in x]
        print(f"  {tag}  {tool:10s} {head[0].strip() if head else '?'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="실제로 바꾼다")
    ap.add_argument("--measure", action="store_true", help="전후 수치만 잰다")
    a = ap.parse_args()
    if a.measure:
        measure("현재")
        return 0
    n = apply_all(a.apply)
    print(f"\n{'실패 ' + str(n) + '건' if n else '전부 통과'}")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
