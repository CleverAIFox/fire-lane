#!/usr/bin/env python3
"""
gate_parity.py — **로컬 관문과 CI 가 같은 것을 보는가.** 3족의 클래스 가드다.

    uv run python tools/gate_parity.py              표 + 래칫 판정
    uv run python tools/gate_parity.py --max 19     로컬 전용이 19 와 다르면 실패
    uv run python tools/gate_parity.py --list       토큰만 (스크립트용)
    uv run python tools/gate_parity.py --selftest   ★ 프로브가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
2026-09-18 감사 실측 — `verify.sh` 가 도는 검사 42단계 중 **CI 가 도는 것은
10단계**였다. 32단계가 로컬 전용이고, 그 사실이 **어디에도 선언돼 있지 않았다.**

그것이 왜 위험한가. 로컬 전용 검사는 "그 기계에서 사람이 verify 를 돌렸을 때만"
돈다. 안 돌리면 아무도 모른다. 그리고 실제로 그 형태의 사고가 났다 —
`verify.sh` 주석이 `web_manifest.py --check` 를 두고 **"CI 가 본다"** 라고
적어놨는데 CI 에 없었다. 주석이 거짓이 된 것을 잡은 검사가 없었다.

★ 이 도구는 **인스턴스 가드가 아니라 클래스 가드다.** "이 검사가 CI 에
  있는가" 를 하나씩 묻지 않는다. "선언되지 않은 차집합이 있는가" 를 묻는다.
  그래서 새 검사를 로컬에만 붙이는 순간 여기서 걸린다 — 강제자를 하나 더
  만들지 않아도 족이 닫힌다.

★ **면제 칸이 생겼다**(PLAN §13 W3-10 · 2026-09-20). 종전에는 로컬 전용 **수만**
  세서 **레이크를 요구해 CI 에서 원리적으로 못 도는 검사**까지 옮기라고 압박했다.
  2026-09-18 에 실제로 `refcheck.py` 를 CI 에 넣었다가 되돌렸다(DECISIONS §191-4) —
  **래칫이 옳은 일을 못 하게 밀었다.**

  이제 `verify.sh` 가 그 자리에서 선언한다:

      # ci-exempt: tools/lakecheck.py 레이크(2.5GB 외장)가 있어야 돈다
      step "레이크 선언↔실물" uv run python tools/lakecheck.py

  선언된 것은 차집합에서 빠지고, **래칫은 미선언만 센다.** 목표는 0 이다.

★ **미선언이 실패다.** 사유를 안 적으면 「옮길 수 있는데 안 옮긴 것」으로 센다.
  `doc_fsck ⑥` · `pr_body_check` 와 같은 규율 — **검사가 자기 전제를 스스로
  선언한다**(§13-5 · MASTER §3-2). 선언을 안 하고 면제받는 길은 없다.

★ **죽은 면제도 잡는다.** 면제해 놓고 그 검사를 CI 로 옮기면 그 선언은
  거짓말이 된다. 면제 토큰이 실제로 로컬 전용이 아니면 실패한다 —
  「거짓말하는 강제자는 없는 강제자보다 나쁘다」.

★ **래칫이다.** 미선언 11개를 오늘 다 옮길 수는 없다(2026-09-20 서술 — 2026-09-22
  (DECISIONS §218-5)에 열을 CI 로 옮기고 하나를 면제로 선언해 0 이 됐다). `dupcheck --max` ·
  `vintage_check --max` · 커버리지 래칫(`verify.sh` 의 `COV_MIN`)과 같은 방식을
  쓴다 — **수는 줄기만 한다.** 다음 배치가 그 숫자를 또 내린다.

★ **숫자는 여기 한 곳에만 산다**(PLAN §13 W3-11 · 2026-09-20). 종전에는
  `verify.sh` 와 `contract.yml` **둘**에 `--max 19` 가 손으로 적혀 있었고,
  2026-09-18 에 `verify.sh` 만 고쳐서 **로컬 초록 · CI 빨강**이 났다.
  이제 둘 다 인자 없이 부르고 기본값이 `RATCHET` 이다.

── 무엇을 맞추나 ──────────────────────────────────────────────
단계 **이름**이 아니라 **검사기**를 맞춘다. 이름은 로컬과 CI 가 서로 다르게
적는다(`인코딩·개행` vs `인코딩·개행` 은 우연히 같지만 `pytest` vs
`★ 소유권 — 미소유 경로가 없는가` 는 다르다). 검사기는 파일이라 안 갈린다.

    tools/X.py · tools/X.mjs · tools/X.sh      도구
    firelane.X                                 `python -m` 진입점
    .githooks/X.sh                             훅
    pytest · ruff · pre-commit · gitleaks      외부 도구
    navi:typecheck                             web/navi 타입 검사
    navi:test                                  web/navi 단위 시험

★ 주석은 걷어낸다. 주석에 적힌 도구 이름은 **호출이 아니다** — 그것을 세면
  `web_manifest.py` 처럼 "CI 가 본다" 고 적어놓기만 한 것이 통과한다.
  `dms.py` 가 산문 언급을 칸으로 세지 않는 것과 같은 원리다.

★ `verify.sh` 는 **「── 결과」 앞까지만** 본다. 그 뒤는 사람에게 주는 안내문이고
  `tools/serve.py` 같은 것이 거기 적혀 있다 — 검사가 아니다.

── 배포 게이트도 본다 ─────────────────────────────────────────
배포 워크플로가 검사를 지나는가. 2026-09-18 실측 — 배포 4종에 `needs:` 도
`workflow_run:` 도 0건이었고 contract 와 **병렬로** 돌았다. `workflow_dispatch`
는 검사 0건으로 임의 배포였다.

IN    tools/verify.sh · .github/workflows/*.yml · .github/actions/**/*.yml
OUT   표준출력 (차집합 표)
PARAM --max · --list · --selftest
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
ACT = ROOT / ".github" / "actions"

# ★ 미선언 로컬 전용 검사의 상한. **이 파일이 유일한 집이다** — `verify.sh` 도
#   `contract.yml` 도 인자 없이 부른다(W3-11). 내릴 때 여기만 고친다.
# ★ 2026-09-22 (DECISIONS §218-5). 11 → 0. 미선언 11 중 레이크 없이 도는 열(ledger · docpatch ·
#   docx_check · dupcheck · golden · install_navi · ledger_fields · navi_setup · pages_add_navi ·
#   plan_renumber)을 contract.yml 로 옮기고, git 역사가 필요한 dms.py 하나를 `# ci-exempt:` 로
#   선언했다. 0 이므로 새 검사를 로컬에만 붙이는 순간 여기서 운다.
RATCHET = 0

# `# ci-exempt: <검사기> <사유...>` — 사유는 다섯 글자 이상이어야 한다.
#   짧은 사유는 사유가 아니다. "필요" 두 글자로 면제받는 길을 막는다.
EXEMPT_RE = re.compile(r"^\s*#\s*ci-exempt:\s*(\S+)\s+(.+?)\s*$", re.M)
MIN_REASON = 5

# ★ 검사기 하나에 패턴 하나. 늘릴 때는 **왜 그것이 검사기인가** 를 적는다.
EXTERNAL = {
    "pytest": r"\bpytest\b",
    "ruff": r"\bruff\b",
    "pre-commit": r"\bpre-commit\b",
    "gitleaks": r"gitleaks",
    "navi:typecheck": r"npm run\s+(?:-s\s+)?typecheck",
    # ★ 2026-09-22 (§213-3). 내비 단위 시험. 검사기가 npm 스크립트라 파일로 못 잡는다
    "navi:test": r"npm run\s+(?:-s\s+)?test\b",
    # ★ 2026-09-22 (DECISIONS §218-5). 의존성 선언 ↔ import. 잠금 밖 `--with` 로 얹는 외부 도구다
    "deptry": r"\bdeptry\b",
}


def _nocomment(text: str) -> str:
    """`#` 주석을 걷는다. 주석의 도구 이름은 호출이 아니다(머리말 ★)."""
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def tokens(text: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"tools/([A-Za-z0-9_]+\.(?:py|mjs|sh))", text):
        out.add("tools/" + m.group(1))
    for m in re.finditer(r"-m\s+(firelane\.[A-Za-z0-9_.]+)", text):
        out.add(m.group(1))
    for m in re.finditer(r"\.githooks/([A-Za-z0-9_.-]+\.sh)", text):
        out.add(".githooks/" + m.group(1))
    for name, pat in EXTERNAL.items():
        if re.search(pat, text):
            out.add(name)
    return out


def _verify_src() -> str:
    raw = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    mark = "# ── 결과"          # 「── 결과」
    return raw[: raw.index(mark)] if mark in raw else raw


def local_tokens() -> set[str]:
    return tokens(_nocomment(_verify_src()))


def exemptions() -> dict[str, str]:
    """`# ci-exempt:` 선언 — 검사기 → 사유.

    ★ 주석에서 읽는 **유일한 자리**다. 머리말이 "주석의 도구 이름은 호출이
      아니다" 라고 적은 것과 모순되지 않는다 — 여기서 읽는 것은 호출이 아니라
      **선언**이고, 형식(`ci-exempt:`)으로 그 둘을 가른다. 산문에 적힌 도구
      이름은 여전히 안 센다.
    """
    return {m.group(1): m.group(2).strip()
            for m in EXEMPT_RE.finditer(_verify_src())}


def ci_tokens() -> set[str]:
    out: set[str] = set()
    for p in sorted(WF.glob("*.yml")) + sorted(ACT.rglob("*.yml")):
        out |= tokens(_nocomment(p.read_text(encoding="utf-8")))
    return out


def deploy_gaps() -> list[str]:
    """배포가 검사를 지나는가. 지나지 않는 경로를 돌려준다."""
    bad: list[str] = []
    for p in sorted(WF.glob("*.yml")):
        if p.name.startswith("_"):
            continue
        body = _nocomment(p.read_text(encoding="utf-8"))
        # ★ 2026-09-23 (§224). 배포 여섯을 하나로 합쳤다 — 재사용 본문(`_deploy.yml`)이
        #   없어졌으므로 "본문을 부르니까 봐준다" 는 예외도 없앴다. 배포하는 파일이
        #   **자기 안에** 게이트를 들어야 한다.
        if "deploy-pages" not in body:
            continue                                  # 배포 워크플로가 아니다
        if "needs:" not in body:
            bad.append(f"{p.name}: 배포인데 needs: 가 없다 — 검사와 병렬로 돈다")
    return bad


def report(max_local: int | None) -> int:
    loc, ci = local_tokens(), ci_tokens()
    ex = exemptions()
    only_local = sorted(loc - ci)
    only_ci = sorted(ci - loc)
    both = sorted(loc & ci)
    declared = sorted(t for t in only_local if t in ex)
    undeclared = sorted(t for t in only_local if t not in ex)

    print(f"검사기  로컬 {len(loc)} · CI {len(ci)} · 공통 {len(both)}")
    print()
    print(f"선언된 면제 {len(declared)}개 — CI 에서 원리적으로 못 돈다")
    for t in declared:
        print(f"    {t}  —  {ex[t]}")
    print()
    print(f"★ 미선언 로컬 전용 {len(undeclared)}개 — 옮길 수 있는데 안 옮겼다")
    for t in undeclared:
        print(f"    {t}")
    print()
    print(f"CI 전용 {len(only_ci)}개 — 로컬이 이것을 안 본다")
    for t in only_ci:
        print(f"    {t}")

    rc = 0

    # ★ 죽은 면제 — 면제해 놓고 CI 로 옮겼거나, 아예 없는 검사기를 면제했다.
    #   면제는 선언이므로 **선언이 실물과 갈리면 그 자체가 결함**이다.
    dead = []
    for t, why in sorted(ex.items()):
        if len(why) < MIN_REASON:
            dead.append(f"{t}: 사유가 너무 짧다 ({why!r}) — {MIN_REASON}자 이상")
        elif t not in loc:
            dead.append(f"{t}: verify.sh 가 안 부르는 검사기를 면제했다")
        elif t in ci:
            dead.append(f"{t}: CI 가 이미 돈다 — 면제 선언을 지워라")
    if dead:
        print()
        print("★ 죽은 면제")
        for d in dead:
            print(f"    ✗ {d}")
        print("    있다고 적혀 있으면 사람이 안 본다. 선언은 실물과 같아야 한다.")
        rc = 1

    only_local = undeclared          # ★ 래칫은 미선언만 센다
    gaps = deploy_gaps()
    if gaps:
        print()
        print("★ 배포 게이트")
        for g in gaps:
            print(f"    ✗ {g}")
        rc = 1

    if max_local is not None:
        print()
        if len(only_local) > max_local:
            print(f"✗ 미선언 로컬 전용 {len(only_local)} > 래칫 {max_local}")
            print("  새 검사를 로컬에만 붙였다. 셋 중 하나를 해라 —")
            print("    ① CI 에도 넣는다")
            print("    ② `# ci-exempt: <검사기> <사유>` 를 verify.sh 에 적는다")
            print(f"    ③ {__file__} 의 RATCHET 을 올리고 **왜 올리는지** 커밋에 적는다")
            rc = 1
        elif len(only_local) < max_local:
            # ★ 줄었으면 래칫을 내리도록 요구한다. 안 그러면 다시 늘어날
            #   자리가 생긴다 — 래칫은 느슨해지면 래칫이 아니다.
            #   2026-09-19 에 커버리지 래칫이 14 인데 실물이 24% 인 것을 나흘간
            #   아무도 몰랐다(PLAN §13 W4-9). 느슨해진 래칫은 초록으로 위장한다.
            print(f"✗ 미선언 로컬 전용 {len(only_local)} < 래칫 {max_local}"
                  f" — RATCHET 을 {len(only_local)} 로 내려라")
            rc = 1
        else:
            print(f"✓ 미선언 로컬 전용 {len(only_local)} = 래칫 {max_local}"
                  f" · 선언된 면제 {len(declared)}")
    return rc


def selftest() -> int:
    """★ 빈 그물인가. deadcheck ① 와 같은 물음이다."""
    bad = []
    loc, ci = local_tokens(), ci_tokens()
    if not loc:
        bad.append("verify.sh 에서 검사기를 0개 찾았다 — 추출기가 죽었다")
    if not ci:
        bad.append("워크플로에서 검사기를 0개 찾았다 — 추출기가 죽었다")
    if "pytest" not in loc:
        bad.append("verify.sh 가 pytest 를 부르는데 못 잡았다")
    if "pytest" not in ci:
        bad.append("CI 가 pytest 를 부르는데 못 잡았다")
    # ★ 주석을 정말 걷는가. 이것이 핵심이다 — 안 걷으면
    #   "CI 가 본다" 고 적어만 놓은 것이 통과한다.
    if tokens(_nocomment("# uv run python tools/nonexistent_probe.py")):
        bad.append("주석 속 도구 이름을 호출로 센다 — 거짓 선언이 통과한다")
    if not tokens("uv run python tools/nonexistent_probe.py"):
        bad.append("호출을 못 센다 — 추출기가 죽었다")
    for name in EXTERNAL:
        if not tokens({"navi:typecheck": "npm run typecheck",
                       "navi:test": "npm run test"}.get(name, f"uv run {name}")):
            bad.append(f"외부 도구 {name} 패턴이 자기 예상을 못 잡는다")
    # ★ 면제 파서가 죽으면 **전부 미선언으로 세어 래칫이 폭발**하거나, 반대로
    #   아무거나 면제로 읽어 차집합이 조용히 0 이 된다. 둘 다 조용하지 않게
    #   여기서 양성·음성 대조를 한다.
    ex = exemptions()
    if not ex:
        bad.append("verify.sh 에서 `# ci-exempt:` 선언을 0개 찾았다 — 파서가 죽었다")
    if not EXEMPT_RE.search("# ci-exempt: tools/x.py 레이크가 있어야 돈다"):
        bad.append("면제 파서가 자기 예상 형식을 못 읽는다")
    if EXEMPT_RE.search("# 레이크가 필요해서 ci-exempt 로 뺐다"):
        bad.append("산문 속 `ci-exempt` 를 선언으로 센다 — 형식이 선언을 안 가른다")
    if bad:
        print("✗ 프로브 자기검사 실패")
        for b in bad:
            print(f"    {b}")
        return 1
    print(f"✓ 프로브 OK — 로컬 {len(loc)} · CI {len(ci)} 검사기를 읽었다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="로컬 관문과 CI 의 차집합")
    # ★ 기본값이 `RATCHET` 이다. **부르는 쪽이 숫자를 적지 않는다** —
    #   적게 두면 `verify.sh` 와 `contract.yml` 이 갈린다(W3-11, 2026-09-18 실측).
    ap.add_argument("--max", type=int, default=RATCHET, help=f"미선언 래칫 (기본 {RATCHET})")
    ap.add_argument("--list", action="store_true", help="미선언 로컬 전용 토큰만 출력")
    ap.add_argument("--selftest", action="store_true", help="프로브가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.list:
        ex = exemptions()
        for t in sorted(local_tokens() - ci_tokens()):
            if t not in ex:
                print(t)
        return 0
    return report(a.max)


if __name__ == "__main__":
    sys.exit(main())
