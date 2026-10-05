#!/usr/bin/env python3
"""
after_squash.py — **열차가 만든 상태를 다시 본다.** 스쿼시 뒤의 강제자다.

    uv run python tools/after_squash.py             판정 (fl.sh 7b · 손으로도)
    uv run python tools/after_squash.py --list      무엇을 왜 다시 보는지 표로
    uv run python tools/after_squash.py --selftest  ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-27 (DECISIONS §273-5). **전수 verify 는 `feat` 가지에서 한 번 돌고,
  그 뒤 열차가 만드는 상태는 아무도 안 본다.** 스쿼시 · 재도장 · 발행 · 봉인이
  전부 그 뒤에 일어난다. 그날 이 족이 세 번 났다.

      ortho.seal.code   `go.sh` 가 파이프라인 **전에** `data/` 를 커밋했다.
                        파이프라인이 뒤에서 그 칸을 다시 내므로 커밋본은
                        구조상 항상 한 칸 뒤처진다
      doc_fsck ⑥        **스쿼시가** `proposal.docx` 의 마지막 커밋 날짜를
                        머지일로 바꾼다. `feat` 에서는 09-24 라 초록이고
                        `part/infra` 로 접히면 09-27 이 되어 표지와 어긋난다
      docseal           봉인 PR 의 것이라 `part/infra` 에는 안 들어갔다 —
                        이 셋 중 유일하게 배치 탓이 아니었다

  셋 다 CI 가 잡았고 왕복이 5분씩이었다. **`[13/59] 관문 동등` 은 초록이었다** —
  그 검사는 「검사 목록이 같은가」를 보지 **「도는 시점이 같은가」는 안 본다.**
  범위가 이름보다 좁고 그것이 선언돼 있지 않은 그 족이다(`scopedecl` 머리말).

★ 전수를 또 돌리지 않는다(10분 32초). **스쿼시가 답을 바꿀 수 있는 것만** 센다.
  기준은 하나다 — **「git 이력이나 커밋된 산출물을 읽는가」.** 그 둘만 스쿼시로
  움직인다. 순수하게 트리 내용만 보는 검사는 스쿼시 전후가 같으므로 여기 없다.

★ 목록을 손으로 들지 않는다. 각 줄이 **왜 여기 있는지**를 같이 든다 —
  사유 없는 목록은 다음 사람이 지울지 늘릴지 판단할 수 없고, 그러면 목록이
  낡는다(`doc_fsck` 의 면제 대장을 사유 딸린 dict 로 바꾼 §270 과 같은 규율).

IN    저장소 (스쿼시된 `part/infra`) · CHECKS 의 도구들
OUT   표준출력 · 종료코드
PARAM CHECKS
밖    **전수가 아니다.** 여기서 초록이어도 `tools/verify.sh` 를 대신하지 않는다 —
      스쿼시가 답을 바꿀 수 없는 검사는 일부러 뺐다. 그리고 **왜 빨간지 고치지
      않는다** — 판정만 하고 고침은 사람이 한다.
부류  절차   배치를 옮기고 기계를 치운다. **산출물에 안 닿는다**  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 이름 → (명령, 왜 스쿼시가 답을 바꾸는가, 레이크가 필요한가)
CHECKS: dict[str, tuple[tuple[str, ...], str, bool]] = {
    "문서 ↔ 문서": (
        ("python", "tools/doc_fsck.py"),
        "⑥ 이 `git log -1 -- proposal.docx` 의 저자 날짜를 표지와 견준다. "
        "스쿼시가 그 날짜를 머지일로 바꾼다",
        False),
    "문서 정합 도장": (
        ("python", "tools/docseal.py", "check"),
        "절 본문과 그 절이 든 파일의 내용을 같이 센다. 스쿼시가 트리를 바꾸지는 "
        "않지만 봉인 커밋이 끼면 달라진다",
        False),
    "기획서 대조": (
        ("python", "tools/docx_check.py"),
        "기획서 수치가 커밋된 산출물과 맞는가. 열차가 산출물을 다시 커밋한다",
        False),
    "web/data 계보": (
        ("python", "tools/web_manifest.py", "--check"),
        "커밋된 발행물의 계보 지문. 재발행 커밋이 열차 뒤에 붙는다",
        False),
    "커밋된 web/data 가 최신인가": (
        ("python", "tools/freshcheck.py"),
        "파이프라인 재실행 산출과 커밋본을 견준다. `go.sh` 가 파이프라인 **전에** "
        "커밋하면 여기가 한 칸 뒤처진다 — 그것이 오늘 난 결함이다",
        True),
}


def has_lake() -> bool:
    """레이크가 붙어 있나. **환경을 직접 안 읽는다** — `paths.py` 가 유일한 독자다.

    ★ 처음엔 `os.environ.get("FIRE_LANE_RAW")` 를 직접 읽었고 `env_check` 가 잡았다.
      단일 독자가 깨지면 키 목록 대조가 동적 접근을 못 잡는다(그 도구 머리말).
    """
    try:
        from firelane.paths import RAW
    except Exception:
        return (ROOT / "data" / "raw").is_dir()
    return bool(RAW and Path(RAW).is_dir())


def run_one(cmd: tuple[str, ...]) -> tuple[int, str]:
    """★ `uv run` 으로 다시 부르지 않는다. 이 도구는 이미 그 환경 안에서 돌고 있고,
    다시 부르면 **의존성 해결을 한 번 더** 타서 느릴 뿐 아니라 해결이 막힌 기계에서는
    검사가 아니라 `uv` 가 죽는다 — 그 빨간불은 검사의 답이 아니다."""
    argv = [sys.executable, *cmd[1:]] if cmd[0] == "python" else list(cmd)
    try:
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=900)
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"
    return r.returncode, (r.stdout + r.stderr)


def check(only: list[str] | None = None) -> int:
    lake = has_lake()
    bad: list[str] = []
    for name, (cmd, _why, needs_lake) in CHECKS.items():
        if only and name not in only:
            continue
        if needs_lake and not lake:
            print(f"   - {name} — 레이크가 없어 건너뛴다(CI 가 든다)")
            continue
        rc, out = run_one(cmd)
        if rc == 0:
            print(f"   OK {name}")
        else:
            bad.append(name)
            print(f"   ✗ {name}")
            print("\n".join("      " + x for x in out.strip().splitlines()[-12:]))
    if bad:
        print(f"\n★ 스쿼시 뒤에 빨간불 {len(bad)}건 — {' · '.join(bad)}")
        print("  여기서 잡는 것이 목적이다. CI 까지 가면 왕복이 5분이다.")
        return 1
    print(f"✓ 열차가 만든 상태 — {len(CHECKS)}축 이상 없음"
          + ("" if lake else " (레이크 없는 축은 건너뜀)"))
    return 0


def table() -> int:
    print("스쿼시가 답을 바꿀 수 있는 검사 — 왜 여기 있는가\n")
    for name, (cmd, why, needs_lake) in CHECKS.items():
        print(f"  {name}{'  (레이크 필요)' if needs_lake else ''}")
        print(f"      {' '.join(cmd)}")
        print(f"      {why}\n")
    return 0


def selftest() -> int:
    """★ 목록이 비거나 사유가 비면 통과가 아니다(`deadcheck ③`)."""
    bad = []
    if not CHECKS:
        bad.append("CHECKS 가 비었다 — 볼 것이 없으면 통과가 아니다")
    for name, row in CHECKS.items():
        cmd, why, _ = row
        if not cmd:
            bad.append(f"{name}: 명령이 없다")
        if len(why.strip()) < 20:
            bad.append(f"{name}: 사유가 비었거나 너무 짧다 — 사유 없는 줄은 낡는다")
        if cmd[0] == "python" and not (ROOT / cmd[1]).is_file():
            bad.append(f"{name}: {cmd[1]} 가 없다 — 죽은 참조다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — {len(CHECKS)}축이 전부 실재하고 사유를 든다")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="열차가 만든 상태를 다시 본다")
    ap.add_argument("--list", action="store_true", help="무엇을 왜 다시 보는지")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--only", nargs="*", help="이름으로 골라서")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.list:
        return table()
    return check(a.only)


if __name__ == "__main__":
    sys.exit(main())
