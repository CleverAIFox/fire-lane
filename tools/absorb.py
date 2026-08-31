#!/usr/bin/env python3
"""
absorb.py — **Downloads 부터 raw 까지 한 명령.** 이관 → 편입 → 검증 → 사본삭제.

    uv run python tools/absorb.py              관측만 (아무것도 안 움직인다)
    uv run python tools/absorb.py --yes        실제로 옮기고 지운다
    uv run python tools/absorb.py --no-prune   사본은 남긴다
    uv run python tools/absorb.py --force      대장에 없는 것도 올린다(먼저 대장에 적어라)

FL_DATA_MIGRATION — git 밖 실물을 움직인다

── 왜 만들었나 ────────────────────────────────────────────────
계층은 넷인데 명령은 다섯이었다.

    intake --stage --yes           Downloads → landing
    acquire --stage --yes          landing   → raw
    acquire --verify               raw sha 대조
    acquire --prune-landing --yes  사본 삭제

**사람이 순서를 외워야 하는 것이 문제가 아니다.** 중간을 건너뛸 수 있는
것이 문제다. `--prune-landing` 은 `--verify` 없이도 돈다. 그러면 편입이
성공했다는 확인 없이 원본을 지운다 — 그것이 소실이다.

이 저장소는 그 형태를 이미 겪었다. exFAT 에서 2.5GB 를 날렸을 때
*"문제는 백업이 없어서가 아니라 백업이 깨진 걸 몰랐던 것"* 이라고
적었다(§18-8). 획득 쪽에서도 같은 구멍이 남아 있었다 — 지우는 명령과
확인하는 명령이 **서로를 요구하지 않는다.**

여기서 순서를 자료구조로 만든다. ④ 는 ③ 이 0 을 냈을 때만 존재한다.

── 설계 ───────────────────────────────────────────────────────
    ① 각 단계는 **기존 도구를 그대로 부른다.** 로직을 옮겨 적지 않는다.

       판정 코드가 두 벌이 되면 반드시 갈라진다. 이 저장소가 08-30 에
       고친 여섯 건 중 넷이 사본이었다(JUNK 3벌 · 글롭 11벌). 절대
       재구현하지 않는다 — subprocess 로 부른다. 느린 것이 갈라지는
       것보다 낫다.

    ② **삭제는 검증에 매달려 있다.** ③ 이 0 이 아니면 ④ 는 안 돈다.

       종료코드를 그대로 본다. `acquire --verify` 는 이미 종료코드가
       게이트가 되도록 짜여 있다(cmd_verify 머리말). 그것을 쓴다.

    ③ **할 일 없음과 성공을 가른다.**

       입력이 0건인데 "완료" 를 찍으면 그 초록불은 아무것도 증명하지
       않는다. `audit_pattern('')` 이 42번 정상적으로 울고 원인이
       호출부였던 것과 같은 병이다 — 옳게 도는 것처럼 보이는 것이
       제일 오래 간다. 0건이면 0건이라고 말한다.

    ④ Downloads 는 **읽기 전용**이다(intake ①). 남의 폴더를 안 비운다.

    ⑤ 사전 대조를 먼저 낸다 — inbox 파일의 sha 가 raw 에 이미 있는가.

       ★ 이것이 "같은 날짜판이 이미 있다" 를 가르는 자리다. 날짜가 같아도
         내용이 다르면 **다른 판**이고, 격리가 아니라 편입 대상이다.
         이름·날짜로 판정하면 조용히 덮어쓴다. sha 로 본다.

    ⑥ 멱등하다. 두 번 돌리면 두 번째는 전부 "이미 있음" 이다.
       각 단계가 이미 멱등하므로 조합도 멱등하다.

── 흐름 ───────────────────────────────────────────────────────
    Downloads (읽기 전용)
        │  ① intake --stage        원본명 보존 · sha 기록
        ▼
    landing (SSD)                  규칙 없음
        │  ② acquire --stage       대장 매칭 · 세 판정
        ▼
    raw                            불변
        │  ③ acquire --verify      ★ 게이트. 여기서 막히면 ④ 가 없다
        │  ④ acquire --prune-landing
        ▼
    landing 사본 삭제              ③ 통과분만

IN    $FIRE_LANE_INBOX · $FIRE_LANE_DATA/landing · sources.yaml
OUT   $FIRE_LANE_DATA/{raw,_quarantine} · data/_intake.json · data/_acquire.json
PARAM 없음
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m",
     "c": "\033[36m", "d": "\033[2m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"


# ── 단계 ───────────────────────────────────────────────────────
class Step:
    """한 단계. 도구 하나의 호출과 그 근거를 같이 든다.

    ★ `need` 가 이 단계의 **선행 조건**이다. 이름이 아니라 앞 단계의
      종료코드를 본다. 순서를 주석으로 적으면 지켜지지 않는다.
    """

    def __init__(self, key: str, label: str, argv: list[str],
                 *, needs: str | None = None, mutating: bool = True):
        self.key, self.label, self.argv = key, label, argv
        self.needs, self.mutating = needs, mutating
        self.rc: int | None = None


def run(step: Step, *, apply: bool, results: dict[str, int]) -> int:
    """단계 하나를 돌린다. 선행 조건이 안 맞으면 **건너뛰지 않고 멈춘다.**"""
    if step.needs is not None:
        prev = results.get(step.needs)
        if prev is None:
            print(col(f"  ✗ {step.label} — 선행 단계 {step.needs} 가 안 돌았다", "r"))
            return 1
        if prev != 0:
            # ★ 여기가 이 도구의 존재 이유다. 검증이 실패했으면 삭제가 없다.
            print(col(f"  ⏸ {step.label} — {step.needs} 가 {prev} 로 끝나 멈춘다", "y"))
            print(col("     사본을 지우지 않았다. 원본은 landing 에 그대로 있다.", "d"))
            return prev

    argv = [sys.executable, str(ROOT / "tools" / step.argv[0]), *step.argv[1:]]
    if step.mutating and apply:
        argv.append("--yes")

    tag = "실행" if (apply and step.mutating) else "관측"
    print(col(f"\n── {step.label}  ({tag})", "c"))
    print(col(f"   {' '.join(step.argv)}{' --yes' if step.mutating and apply else ''}", "d"))
    rc = subprocess.call(argv, cwd=ROOT)
    step.rc = rc
    if rc:
        print(col(f"  ✗ {step.label} 종료코드 {rc}", "r"))
    return rc


# ── 사전 대조 ──────────────────────────────────────────────────
def pre_compare() -> int:
    """inbox 파일이 raw 에 이미 있는가. **sha 로만 판정한다.**

    ★ 이름과 날짜가 같아도 내용이 다르면 다른 판이다. 인수인계의
      "소화전 현황 20250731 — raw 에 같은 날짜판 있음. 격리 대상" 이
      정확히 이 자리다. 같은 날짜라는 것은 근거가 아니다.
    """
    # ★ intake.py 의 inbox 판정을 그대로 쓴다. 재구현하지 않는다(설계 ①).
    import importlib.util

    from firelane.paths import RAW
    spec = importlib.util.spec_from_file_location("intake", ROOT / "tools/intake.py")
    intake = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(intake)
    inb = intake.inbox()

    if inb is None or not Path(inb).is_dir():
        print(col("inbox 를 못 찾았다 — ① 은 건너뛴다", "y"))
        return 0

    files = sorted(p for p in Path(inb).rglob("*") if p.is_file())
    if not files:
        print(f"{col('inbox', 'd')}    {inb}   {col('0건 — 올릴 것이 없다', 'y')}")
        return 0

    raw_sha: dict[str, Path] = {}
    for p in RAW.rglob("*"):
        if p.is_file() and not p.name.startswith("_"):
            raw_sha.setdefault(sha256(p), p)

    print(col("── 사전 대조 (sha256)", "c"))
    same = diff = 0
    for p in files:
        s = sha256(p)
        twin = raw_sha.get(s)
        if twin:
            same += 1
            print(f"  {col('이미 편입', 'g')}  {p.name}")
            print(f"             {col(f'= {twin.relative_to(RAW)}', 'd')}")
            continue
        # 이름의 날짜 토큰이 raw 에 있는데 sha 가 다르면 **다른 판**이다.
        stem_hits = [q for q in raw_sha.values()
                     if any(t in q.name for t in _date_tokens(p.name))]
        if stem_hits:
            diff += 1
            print(f"  {col('★ 다른 판', 'y')}  {p.name}  {human(p.stat().st_size)}")
            print(f"             {col(f'같은 날짜 토큰: {stem_hits[0].relative_to(RAW)}', 'd')}")
            print(col("             날짜가 같아도 내용이 다르다. 격리가 아니라 판정 대상이다.", "d"))
        else:
            print(f"  {col('신규', 'c')}      {p.name}  {human(p.stat().st_size)}")
    print(f"\n  {len(files)}건 — 이미 편입 {same} · 같은날짜 다른내용 {diff} · "
          f"신규 {len(files) - same - diff}")
    return 0


DATE_TOKEN = re.compile(r"20\d{6}")


def _date_tokens(name: str) -> list[str]:
    """파일명 안의 YYYYMMDD. 판 구분의 **후보**일 뿐 근거가 아니다."""
    return DATE_TOKEN.findall(name)


# ── 본체 ───────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Downloads → landing → raw → 사본삭제. 한 명령.")
    ap.add_argument("--yes", action="store_true", help="실제로 옮기고 지운다")
    ap.add_argument("--no-prune", action="store_true", help="사본을 남긴다")
    ap.add_argument("--force", action="store_true",
                    help="대장에 없는 것도 올린다. ★ 먼저 대장에 적어라")
    a = ap.parse_args()

    # ★ 관문은 하나다(paths.require_lake). 도구마다 따로 검사하면 빠뜨린다.
    from firelane.paths import LANDING, RAW, require_lake
    require_lake(need=("raw",))

    print(col("absorb — 이관 → 편입 → 검증 → 사본삭제", "c"))
    print(f"{col('raw', 'd')}      {RAW}")
    print(f"{col('landing', 'd')}  {LANDING}"
          f"{'' if LANDING.is_dir() else col('   (없음)', 'y')}\n")

    pre_compare()

    fx = ["--force"] if a.force else []
    steps = [
        Step("intake", "① 이관  Downloads → landing",
             ["intake.py", "--stage", *fx]),
        Step("stage", "② 편입  landing → raw",
             ["acquire.py", "--stage"], needs="intake"),
        Step("verify", "③ 검증  raw sha 대조",
             ["acquire.py", "--verify"], needs="stage", mutating=False),
    ]
    if not a.no_prune:
        steps.append(
            Step("prune", "④ 사본삭제  landing 정리",
                 ["acquire.py", "--prune-landing"], needs="verify"))

    results: dict[str, int] = {}
    for s in steps:
        rc = run(s, apply=a.yes, results=results)
        results[s.key] = rc
        if rc and s.key in ("intake", "stage"):
            # 이관·편입이 깨졌으면 뒤는 볼 것도 없다.
            print(col(f"\n{s.label} 에서 멈췄다. 뒤 단계는 돌리지 않았다.", "r"))
            return rc

    print(col("\n── 결과", "c"))
    for s in steps:
        mark = "·" if s.rc is None else ("✓" if s.rc == 0 else "✗")
        kind = "g" if s.rc == 0 else ("d" if s.rc is None else "r")
        print(f"  {col(mark, kind)} {s.label}"
              f"{'' if s.rc in (0, None) else col(f'   rc={s.rc}', 'r')}")

    if not a.yes:
        print(col("\n관측만 했다. 실제로 옮기려면 --yes", "y"))
        return 0

    bad = [s for s in steps if s.rc not in (0, None)]
    if bad:
        print(col(f"\n{len(bad)}단계가 실패했다. "
                  "landing 원본은 지우지 않았다.", "r"))
        return 1
    print(col("\n완료. raw 가 정본이고 landing 사본은 정리됐다.", "g"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
