#!/usr/bin/env python3
"""
tools/ship.py — 푸시 전에 밟아야 하는 것을 한 번에 밟는다

    uv run python tools/ship.py            검사만 (아무것도 안 바꾼다)
    uv run python tools/ship.py --fix      고칠 수 있는 것은 고친다
    uv run python tools/ship.py --push     검사 통과 시 push 까지

════════════════════════════════════════════════════════════════
── 왜 만들었나 ─────────────────────────────────────────────────
푸시 전에 밟아야 하는 것이 흩어져 있었다.

    verify.sh            8단계 검증
    tidy.py              로컬 찌꺼기
    docnum_check.py      문서 숫자
    문서 4축 반영         손으로 확인
    golden.py check      리팩 증명

**손으로 기억해야 하는 목록은 언젠가 하나를 빠뜨린다.** 2026-08-23 에
그것이 세 번 났다 — `golden` 을 파이프라인 없이 돌려 거짓 초록불을 봤고,
`_backup_apply_*` 가 하루에 여덟 개 쌓였고, CI 가 `gis` 를 안 보는 채로
PR 이 머지되고 있었다.

★ `verify.sh` 와 겹치지 않는다. 역할이 다르다.

    verify.sh   **코드가 도는가** — pytest · ruff · 파이프라인 · JS
    ship.py     **내보내도 되는가** — 위 + 문서 4축 + 위생 + git 상태

`ship.py` 는 `verify.sh` 를 부른다. 중복 구현하지 않는다.

── 검사 목록 ───────────────────────────────────────────────────
    git      워킹트리 · 브랜치 · upstream · 미푸시 커밋
    코드     verify.sh (--fast 는 파이프라인 생략)
    문서     4축 반영 · 숫자 대조 · 죽은 경로 · 생애주기
    위생     tidy 대상 · 루트 일회성 스크립트 · 백업 폴더
    증명     golden 지문 (산출물이 코드보다 최신일 때만 유효)

IN    저장소
OUT   없음. --fix 는 tidy 를 돌리고, --push 는 git push 한다
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m",
     "c": "\033[36m", "d": "\033[90m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def sh(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd or ROOT)
    return r.returncode, (r.stdout + r.stderr).strip()


class Report:
    """검사 결과. ★ 실패를 세되 중간에 멈추지 않는다.

    한 번에 다 보여줘야 사람이 한 번에 고친다. 첫 실패에서 죽으면
    고치고 다시 돌리기를 반복하게 된다 — `verify.sh` 가 같은 이유로
    끝까지 돈다.
    """

    def __init__(self) -> None:
        self.fail: list[str] = []
        self.warn: list[str] = []

    def ok(self, name: str, note: str = "") -> None:
        print(f"  {col('OK  ', 'g')}{name:26}{col(note, 'd')}")

    def bad(self, name: str, why: str) -> None:
        self.fail.append(f"{name} — {why}")
        print(f"  {col('★   ', 'r')}{name:26}{why}")

    def note(self, name: str, why: str) -> None:
        self.warn.append(f"{name} — {why}")
        print(f"  {col('·   ', 'y')}{name:26}{col(why, 'd')}")


# ── git ────────────────────────────────────────────────────────
def check_git(R: Report) -> None:
    print(col("\n── git", "c"))
    rc, _ = sh("git", "rev-parse", "--git-dir")
    if rc:
        R.bad("저장소", "git 저장소가 아니다")
        return

    # ★ 커밋이 하나도 없으면 `HEAD` 가 없어 rev-parse 가 에러 문자열을 낸다.
    #   그것을 브랜치 이름으로 쓰면 뒤 검사가 전부 오작동한다 —
    #   2026-08-23 에 갓 만든 저장소에서 그랬다. 종료코드를 본다.
    rc, br = sh("git", "rev-parse", "--abbrev-ref", "HEAD")
    if rc or not re.fullmatch(r"[\w./-]+", br):
        R.note("브랜치", "커밋이 없다 — git 검사를 건너뛴다")
        return
    _, dirty = sh("git", "status", "--porcelain")
    if dirty:
        n = len([x for x in dirty.splitlines() if x.strip()])
        R.bad("워킹트리", f"미커밋 {n}건 — 커밋하거나 stash 하라")
    else:
        R.ok("워킹트리", "깨끗하다")

    # ★ upstream 이 원격에서 사라졌으면 push 가 통째로 실패한다.
    rc, up = sh("git", "rev-parse", "--abbrev-ref", f"{br}@{{upstream}}")
    if rc:
        R.note("upstream", f"{br} 에 upstream 이 없다 — push -u 가 필요하다")
    else:
        _, track = sh("git", "for-each-ref", "--format=%(upstream:track)",
                      f"refs/heads/{br}")
        if "gone" in track:
            R.bad("upstream", f"{up} 이 원격에 없다 — tidy.py 로 정리하라")
        else:
            R.ok("upstream", up)

    _, ahead = sh("git", "rev-list", "--count", "@{u}..HEAD")
    if ahead.isdigit() and int(ahead):
        R.ok("미푸시 커밋", f"{ahead}건")

    # CI 가 이 브랜치를 보는가 — 검사 없이 머지되는 것을 막는다
    #
    # ★ 2026-08-23. 처음엔 모든 `branches:` 목록에 현재 브랜치가 있어야
    #   한다고 짰다. 오탐이었다. 두 트리거의 뜻이 다르다.
    #
    #     push          **소스** 브랜치. 여기에 밀면 검사가 돈다
    #     pull_request  **대상** 브랜치. 거기로 PR 을 열면 검사가 돈다
    #
    #   `fix/review-0823 → gis` PR 은 `pull_request: [gis]` 가 잡는다.
    #   작업 브랜치가 목록에 있을 이유가 없다. 봐야 하는 것은
    #   **PR 대상이 될 브랜치가 pull_request 트리거에 있는가** 다.
    ci = (ROOT / ".github/workflows/contract.yml").read_text(encoding="utf-8")

    def _branches(kind: str) -> set[str]:
        m = re.search(rf"{kind}:\s*\n\s*branches:\s*\[([^\]]+)\]", ci)
        return {b.strip() for b in m.group(1).split(",")} if m else set()

    push_b, pr_b = _branches("push"), _branches("pull_request")
    base = next((b for b in ("gis", "main", "master") if b in pr_b), None)
    if not pr_b:
        R.bad("CI 트리거", "contract.yml 에 pull_request 트리거가 없다")
    elif br in push_b:
        R.ok("CI 트리거", f"push 로 {br} 를 본다")
    elif base:
        R.ok("CI 트리거", f"{br} → {base} PR 을 pull_request 가 본다")
    else:
        R.bad("CI 트리거", f"{br} 도 대상 브랜치도 트리거에 없다")


# ── 코드 ───────────────────────────────────────────────────────
def check_code(R: Report, fast: bool) -> None:
    print(col("\n── 코드", "c"))
    args = ["bash", str(ROOT / "tools" / "verify.sh")]
    if fast:
        args.append("--fast")
    rc, out = sh(*args)
    if rc:
        # ★ 2026-08-24. 처음엔 마지막 줄을 실패 사유로 썼다. 그런데
        #   `verify.sh` 는 실패 시 안내 문구를 마지막에 찍는다 —
        #   "원본으로 되돌리려면: web/app.js.orig …". 그것이 실패 사유로
        #   표시돼 **없는 파일을 찾게 만들었다.**
        #   `실패` 로 표시된 줄을 골라 보여준다.
        import re

        hit = [re.sub(r"\x1b\[[0-9;]*m", "", x).strip()
               for x in out.splitlines() if "실패" in x and "머지" not in x]
        R.bad("verify.sh", (hit[0] if hit else "실패")[:70])
        for x in hit[1:4]:
            print(f"        {col(x[:96], 'd')}")
    else:
        R.ok("verify.sh", ("--fast" if fast else "전량") + " 통과")


# ── 문서 ───────────────────────────────────────────────────────
def check_docs(R: Report) -> None:
    print(col("\n── 문서 4축", "c"))
    M = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    P = (ROOT / "docs/PLAN.md").read_text(encoding="utf-8")
    D = (ROOT / "docs/DECISIONS.md").read_text(encoding="utf-8")

    # ① 숫자 대조
    rc, out = sh(sys.executable, str(ROOT / "tools/docnum_check.py"))
    (R.ok if rc == 0 else lambda a, b: R.bad(a, b))(
        "숫자 대조", out.splitlines()[-1][:60] if out else "")

    # ② 생애주기 — 미래 **작업**이 MASTER 에 있는가
    #    ★ 절 제목만 보면 못 잡는다. 2026-08-23 에 §16-1 안에 실험 설계가
    #      들어가 있었고 `test_open_work_lives_only_in_plan` 이 놓쳤다.
    #
    #    ★ `~해야 한다` 를 그대로 세면 안 된다. 규칙 서술이 전부 그 형태다
    #      ("gis 는 항상 동작해야 한다"). 처음에 그렇게 짰다가 오탐 6건이
    #      나왔다. **검사가 시끄러우면 사람이 안 읽는다.**
    #      작업 계획의 표지(일정 · 담당 · 미착수)가 같이 있을 때만 잡는다.
    #    ★ `D-25` 는 **미결정 항목 번호**지 날짜가 아니다(MASTER §10-0).
    #      "이건 D-25 실측 대상이다" 는 현재 상태 서술이라 MASTER 가 맞다.
    #      그걸 계획으로 세면 26줄이 걸린다 — 두 번째 오탐이었다.
    #      `남은 일` 도 R14 를 설명하는 문장에 나온다.
    #      **남는 것은 일정과 담당뿐이다.** 그 둘이 MASTER 에 있으면 잘못이다.
    PLANLIKE = r"(다음 주에|다음주에|착수 예정|담당자 없음|담당 미정|" \
               r"TODO|FIXME|아직 안 했다|하기로 했다)"
    future = [x.strip()[:60] for x in re.findall(r"^.*$", M, re.M)
              if re.search(PLANLIKE, x) and not x.lstrip().startswith(("#", ">", "|"))]
    if future:
        R.note("생애주기", f"MASTER 에 계획성 서술 {len(future)}줄 — PLAN 이 맞는지 보라")
    else:
        R.ok("생애주기", "MASTER 는 현재만")

    # ③ 절 제목이 축마다 고유한가
    #    ★ 제목 **끼리** 비교한다. 본문 포함 여부로 보면 `계약` · `판정` 같은
    #      한 단어가 전부 걸린다. 처음에 그렇게 짰다가 오탐 8건이 나왔다.
    def heads(txt: str) -> set[str]:
        return {h.strip() for h in re.findall(r"^###?\s+(.+)$", txt, re.M)
                if len(h.strip()) >= 6}          # 한두 단어 제목은 겹쳐도 무해하다

    hm, hp, hd = heads(M), heads(P), heads(D)
    dup = sorted((hm & hp) | (hm & hd) | (hp & hd))
    if dup:
        R.note("절 제목 중복", f"{len(dup)}개 — {dup[0][:36]}")
    else:
        R.ok("절 제목", "축마다 고유")

    # ④ 문체
    #    ★ 팀원에게 말 거는 대목은 경어체가 맞다. 그것까지 잡으면
    #      "규칙을 지키려고 사과를 반말로 바꾸는" 우스운 일이 된다.
    #      MASTER §7 의 미검증 고지와 DECISIONS 의 사과 절이 그렇다.
    POLITE_OK = ("님", "제 잘못", "죄송", "부탁", "보세요", "미검증")
    tone = 0
    for rel, txt in (("MASTER", M), ("PLAN", P), ("DECISIONS", D)):
        bad = [ln for ln in txt.splitlines()
               if re.search(r"(합니다|입니다|습니다)", ln)
               and not any(k in ln for k in POLITE_OK)]
        if bad:
            tone += len(bad)
            R.note(f"{rel} 문체", f"경어체 {len(bad)}줄 — {bad[0].strip()[:40]}")
    if tone == 0:
        R.ok("문체", "평서체 통일 (말 거는 대목 제외)")

    # ⑤ 죽은 경로 · 없는 도구는 pytest 가 본다. 여기서는 세지 않는다.
    R.ok("죽은 경로·도구", "test_guards 가 본다")


# ── 위생 ───────────────────────────────────────────────────────
def check_hygiene(R: Report, fix: bool) -> None:
    print(col("\n── 위생", "c"))
    rc, out = sh(sys.executable, str(ROOT / "tools/tidy.py"))
    m = re.search(r"(\d+)건 — 아무것도", out)
    n = int(m.group(1)) if m else 0
    if n == 0:
        R.ok("로컬 찌꺼기", "없다")
    elif fix:
        sh(sys.executable, str(ROOT / "tools/tidy.py"), "--yes")
        R.ok("로컬 찌꺼기", f"{n}건 정리했다")
    else:
        R.note("로컬 찌꺼기", f"{n}건 — --fix 로 정리한다")

    stray = [p.name for p in ROOT.glob("*.sh")] + [p.name for p in ROOT.glob("apply*.py")]
    if stray:
        R.note("루트 일회성", f"{stray} — §18-5 R8, 돌리고 지운다")
    else:
        R.ok("루트 일회성", "없다")


# ── 증명 ───────────────────────────────────────────────────────
def check_golden(R: Report) -> None:
    print(col("\n── 증명", "c"))
    rc, out = sh(sys.executable, str(ROOT / "tools/golden.py"), "check")
    if rc == 0:
        R.ok("golden", "리팩 전후 동일")
    elif "낡았다" in out:
        # ★ 거짓 초록불을 막는 그 검사다. 실패가 아니라 "아직 증명 못 함" 이다.
        R.bad("golden", "산출물이 판정 코드보다 낡았다 — fire-lane --from segments")
    else:
        R.bad("golden", (out.splitlines() or ["실패"])[0][:60])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="고칠 수 있는 것은 고친다")
    ap.add_argument("--push", action="store_true", help="통과하면 push 한다")
    ap.add_argument("--fast", action="store_true", help="파이프라인 전량 생략")
    a = ap.parse_args()

    print(col("ship — 내보내도 되는가", "c"))
    R = Report()
    check_git(R)
    check_code(R, a.fast)
    check_docs(R)
    check_hygiene(R, a.fix)
    check_golden(R)

    print()
    if R.fail:
        print(col(f"★ 막힌 것 {len(R.fail)}건", "r"))
        for x in R.fail:
            print(f"    {x}")
        print("\n  고치고 다시 돌려라. 검사를 건너뛰고 내보내지 마라.")
        return 1

    if R.warn:
        print(col(f"· 참고 {len(R.warn)}건", "y"))
        for x in R.warn:
            print(f"    {x}")
        print()

    print(col("내보내도 된다.", "g"))
    if a.push:
        rc, out = sh("git", "push")
        print(out[-400:] if out else "")
        return rc
    print(col("  git push", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
