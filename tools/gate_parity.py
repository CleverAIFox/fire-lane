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

★ **래칫에 면제 칸이 없다 — 이것이 알려진 결함이다**(PLAN §13 W3-10). 로컬 전용
  수만 세므로 **레이크를 요구해 CI 에서 못 도는 검사**까지 옮기라고 압박한다.
  2026-09-18 에 실제로 `refcheck.py` 를 CI 에 넣었다가 되돌렸다(DECISIONS §191-4).

★ **래칫이다.** 25개를 오늘 다 옮길 수는 없다(레이크가 필요한 것 · 기계 설정을
  보는 것이 섞여 있다). 그래서 `dupcheck --max 1` · `vintage_check --max 0` ·
  커버리지 래칫 14% 와 같은 방식을 쓴다 — **수는 줄기만 한다.**
  사유를 25개 쓰는 대신 숫자 하나를 내린다. 다음 배치가 그 숫자를 또 내린다.

── 무엇을 맞추나 ──────────────────────────────────────────────
단계 **이름**이 아니라 **검사기**를 맞춘다. 이름은 로컬과 CI 가 서로 다르게
적는다(`인코딩·개행` vs `인코딩·개행` 은 우연히 같지만 `pytest` vs
`★ 소유권 — 미소유 경로가 없는가` 는 다르다). 검사기는 파일이라 안 갈린다.

    tools/X.py · tools/X.mjs · tools/X.sh      도구
    firelane.X                                 `python -m` 진입점
    .githooks/X.sh                             훅
    pytest · ruff · pre-commit · gitleaks      외부 도구
    navi:typecheck                             web/navi 타입 검사

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

# ★ 검사기 하나에 패턴 하나. 늘릴 때는 **왜 그것이 검사기인가** 를 적는다.
EXTERNAL = {
    "pytest": r"\bpytest\b",
    "ruff": r"\bruff\b",
    "pre-commit": r"\bpre-commit\b",
    "gitleaks": r"gitleaks",
    "navi:typecheck": r"npm run\s+(?:-s\s+)?typecheck",
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


def local_tokens() -> set[str]:
    raw = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    mark = "# ── 결과"          # 「── 결과」
    if mark in raw:
        raw = raw[: raw.index(mark)]
    return tokens(_nocomment(raw))


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
        if "deploy-pages" not in body and "_deploy.yml" not in body:
            continue                                  # 배포 워크플로가 아니다
        if "needs:" not in body and "_deploy.yml" not in body:
            bad.append(f"{p.name}: 배포인데 needs: 가 없다 — 검사와 병렬로 돈다")
    dep = WF / "_deploy.yml"
    if dep.exists():
        body = _nocomment(dep.read_text(encoding="utf-8"))
        if "needs:" not in body:
            bad.append("_deploy.yml: 배포 본문에 needs: 가 없다 — 게이트를 안 지난다")
    return bad


def report(max_local: int | None) -> int:
    loc, ci = local_tokens(), ci_tokens()
    only_local = sorted(loc - ci)
    only_ci = sorted(ci - loc)
    both = sorted(loc & ci)

    print(f"검사기  로컬 {len(loc)} · CI {len(ci)} · 공통 {len(both)}")
    print()
    print(f"★ 로컬 전용 {len(only_local)}개 — CI 가 이것을 안 본다")
    for t in only_local:
        print(f"    {t}")
    print()
    print(f"CI 전용 {len(only_ci)}개 — 로컬이 이것을 안 본다")
    for t in only_ci:
        print(f"    {t}")

    rc = 0
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
            print(f"✗ 로컬 전용 {len(only_local)} > 래칫 {max_local}")
            print("  새 검사를 로컬에만 붙였다. CI 에도 넣거나 래칫을 올릴 사유를 적어라.")
            rc = 1
        elif len(only_local) < max_local:
            # ★ 줄었으면 래칫을 내리도록 요구한다. 안 그러면 다시 늘어날
            #   자리가 생긴다 — 래칫은 느슨해지면 래칫이 아니다.
            print(f"✗ 로컬 전용 {len(only_local)} < 래칫 {max_local} — 래칫을 {len(only_local)} 로 내려라")
            rc = 1
        else:
            print(f"✓ 로컬 전용 {len(only_local)} = 래칫 {max_local}")
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
        if not tokens({"navi:typecheck": "npm run typecheck"}.get(name, f"uv run {name}")):
            bad.append(f"외부 도구 {name} 패턴이 자기 예상을 못 잡는다")
    if bad:
        print("✗ 프로브 자기검사 실패")
        for b in bad:
            print(f"    {b}")
        return 1
    print(f"✓ 프로브 OK — 로컬 {len(loc)} · CI {len(ci)} 검사기를 읽었다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="로컬 관문과 CI 의 차집합")
    ap.add_argument("--max", type=int, default=None, help="로컬 전용 래칫")
    ap.add_argument("--list", action="store_true", help="로컬 전용 토큰만 출력")
    ap.add_argument("--selftest", action="store_true", help="프로브가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.list:
        for t in sorted(local_tokens() - ci_tokens()):
            print(t)
        return 0
    return report(a.max)


if __name__ == "__main__":
    sys.exit(main())
