#!/usr/bin/env python3
"""
tools/navi_setup.py — 내비 작업물을 저장소 규약에 맞게 앉힌다.

    uv run python tools/navi_setup.py            무엇이 바뀔지만 (기본)
    uv run python tools/navi_setup.py --apply    실제로

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-05 에 내비를 붙이면서 **루트에 일회성 스크립트 3개**를 놓았다.
`commit_policy.py` 머리말이 실제 사고로 적어둔 바로 그 형태다.

더 나쁜 것은 그중 둘이 **소스를 텍스트 치환으로 고쳤다**는 점이다.
두 번 돌리면 깨지고, 실제로 heredoc 이스케이프가 어긋나 문법 오류를 냈다.
치환은 재현이 아니다 — 같은 입력에 같은 출력이 나온다는 보장이 없다.

이 도구는 그 반대다. **멱등이고, 기본이 dry-run 이고, 무엇을 왜 하는지
출력한다.** 두 번 돌려도 결과가 같다.

── 무엇을 하나 ─────────────────────────────────────────────────
  1. 루트의 일회성 스크립트를 지운다 (tools/ 에 정본이 있는 것만)
  2. 루트의 산출물 CSV 를 지운다 (도구가 다시 뽑는다)
  3. .gitignore 에 web/navi 항목을 넣는다
  4. .github/CODEOWNERS 에 web/navi 소유자를 넣는다
  5. tests/test_tools_are_wired.py 의 EXEMPT 에 조사 도구를 등재한다

★ 5번은 사유를 함께 적는다. 비우는 것이 목표가 아니다 — 조사 도구는
  사람이 판단하려고 부르는 것이라 자동 실행이 오히려 틀리다.

IN    저장소 트리
OUT   삭제·추가 (--apply 일 때만)
PARAM --apply · --owner
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 루트에 놓였던 일회성 스크립트. tools/ 에 정본이 있거나 애초에 남길 것이 아니다.
ONESHOT = ("scaffold_navi.sh", "fix_style.sh", "fix_tiles.sh",
           "snap.ts", "route.ts", "matchcheck.py")
# 루트에 떨어진 산출물. 도구가 다시 뽑는다 — 커밋 대상이 아니다.
ARTIFACT = ("matchcheck.csv", "matchcheck_200.csv", "bottlenecks.csv")

GITIGNORE_BLOCK = """
# ── web/navi (React 내비) ──────────────────────────────────
# 소스는 커밋한다. 의존성과 빌드 산출물은 CI 가 만든다.
# web/data 와 반대 원칙인데 이유가 다르다 — web/data 는 재생성에 raw
# 2.5GB 가 필요하고, dist 는 `npm ci` 하나면 된다.
web/navi/node_modules/
web/navi/dist/
web/navi/.vite/
"""

CODEOWNERS_BLOCK = """
# ── React 내비 (PLAN #63) ──────────────────────────────────
# lib/ 는 로직이라 계약 대조가 걸린다. components/ 는 화면이라 UI 소관이다.
# 둘을 가른 이유는 지혜님이 화면만 고칠 때 로직 리뷰가 걸리지 않게 하려는 것이다.
/web/navi/src/lib/        {owner}   # !strict
/web/navi/src/components/ {owner}
/web/navi/                {owner}
"""

EXEMPT_ADD = {
    "matchcheck": "Mapbox Map Matching 커버리지 대조. 토큰 필요·외부 API 라 CI 에 못 건다",
    # ★ 2026-09-10 제거. `bottleneck` 이라는 도구는 없다 —
    #   실물은 `bridge_audit.py` 이고 그 머리말이 옛 이름을
    #   그대로 적고 있었다(F-096). 공유 목록에 유령이 낀 것이다.
    "bridge_audit": "다리 분석으로 실측 우선순위 산출. 사람이 답사 계획을 세우려고 부른다",
    "navi_setup": "저장소 정리. 1회성 배치이며 멱등이다. 자동 실행 대상이 아니다",
}



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
        print(f"\u2717 {len(bad)}건")
        for b in bad:
            print(f"   {b}")
        return 1
    print(f"\u2713 루트 잔재 0건 · 면제 등재 {len(EXEMPT_ADD)}종 전부 실재")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 바꾼다")
    ap.add_argument("--check", action="store_true",
                    help="상태만 본다. 아무것도 안 바꾼다")
    ap.add_argument("--owner", default="@CleverAIFox", help="CODEOWNERS 에 적을 소유자")
    a = ap.parse_args()
    # ★ --check 는 아무것도 안 바꾼다. verify.sh 전용
    if a.check:
        return check()
    act = a.apply
    tag = "" if act else "  (dry-run — --apply 로 실행)"
    print(f"저장소 {ROOT}{tag}\n")
    n = 0

    # ── 1·2. 루트 청소 ────────────────────────────────────────
    for name in ONESHOT + ARTIFACT:
        p = ROOT / name
        if not p.exists():
            continue
        why = ("일회성 스크립트 — commit_policy R8 이 막는다"
               if name in ONESHOT else "산출물 — 도구가 다시 뽑는다")
        print(f"  삭제  {name:24s} {why}")
        if act:
            p.unlink()
        n += 1

    # ── 3. .gitignore ─────────────────────────────────────────
    n += _append_once(ROOT / ".gitignore", "web/navi/node_modules/",
                      GITIGNORE_BLOCK, act, ".gitignore 에 web/navi 항목")

    # ── 4. CODEOWNERS ─────────────────────────────────────────
    co = ROOT / ".github" / "CODEOWNERS"
    n += _append_once(co, "/web/navi/",
                      CODEOWNERS_BLOCK.format(owner=a.owner), act,
                      f"CODEOWNERS 에 web/navi 소유자 {a.owner}")

    # ── 5. EXEMPT ─────────────────────────────────────────────
    n += _exempt(ROOT / "tests" / "test_tools_are_wired.py", act)

    print(f"\n{'적용' if act else '예정'} {n}건")
    if not act and n:
        print("  실행:  uv run python tools/navi_setup.py --apply")
    if act:
        print("\n확인:  uv run python tools/commit_policy.py --tracked")
        print("       uv run pytest tests/test_tools_are_wired.py tests/test_ownership.py -q")
    return 0


def _append_once(path: Path, marker: str, block: str, act: bool, what: str) -> int:
    """이미 있으면 아무것도 안 한다. **멱등의 핵심이다.**"""
    if path.exists() and marker in path.read_text(encoding="utf-8"):
        return 0
    print(f"  추가  {path.relative_to(ROOT)}: {what}")
    if act:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(block)
    return 1


def _exempt(path: Path, act: bool) -> int:
    """EXEMPT dict 에 항목을 넣는다. 이미 있는 키는 건드리지 않는다."""
    if not path.exists():
        print(f"  ★ {path.relative_to(ROOT)} 이 없다. 건너뜀")
        return 0
    txt = path.read_text(encoding="utf-8")
    add = {k: v for k, v in EXEMPT_ADD.items() if f'"{k}"' not in txt}
    if not add:
        return 0
    for k in add:
        print(f"  추가  EXEMPT[{k}]")
    if act:
        anchor = "EXEMPT = {\n"
        if anchor not in txt:
            print("  ★ EXEMPT 선언을 못 찾았다. 손으로 넣어라")
            return len(add)
        lines = "".join(f'    "{k}": "{v}",\n' for k, v in add.items())
        txt = txt.replace(anchor, anchor + lines, 1)
        path.write_text(txt, encoding="utf-8")
    return len(add)


if __name__ == "__main__":
    raise SystemExit(main())
