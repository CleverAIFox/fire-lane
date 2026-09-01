#!/usr/bin/env python3
"""
pull_data.py — 반입 체인 단일 트리거. **Downloads 에서 processed 까지 한 번에.**

    uv run python tools/pull_data.py            관측만 (아무것도 안 바꾼다)
    uv run python tools/pull_data.py --yes       반입 · 편입 · 정규화까지
    uv run python tools/pull_data.py --yes --all 위 + 파이프라인 + golden
    uv run python tools/pull_data.py --yes --keep-landing   landing 원본을 남긴다

════════════════════════════════════════════════════════════════
── 왜 만들었나 ─────────────────────────────────────────────────
`uv run fire-lane` 은 **raw 부터** 시작한다. 그 앞의 다섯 단계가 도구로만
있었고 사람이 순서를 외워서 하나씩 쳤다.

    intake --stage --yes        Downloads → landing
    acquire --stage             landing → raw
    acquire --verify            sha 대조
    acquire --prune-landing     중복 원본 정리
    acquire --quarantine        대장 밖 raw 격리
    prep --apply                raw → norm

★ `normalize_raw` 를 여기 넣지 않는다. 이름이 정규화처럼 보이지만 실제로는
  **Downloads → raw** 이고 `acquire` 가 대체한 옛 경로다. 넣으면 편입이 두 번
  돌고, 그 도구의 "크기만 보는 이미 있음 판정" 이 되살아난다.

`pipeline.py` 가 적은 그대로다 — ***단계를 하나씩 손으로 치면 반드시
빠뜨린다.*** 2026-09-01 에 그것이 실증됐다. 소방차량현황 CSV 둘을 대장에
등재하고 `acquire.py` 를 인자 없이 돌려 **"결손 2종" 만 보고 편입이 된 줄
알았다.** 인자 없는 실행은 관측만 한다는 것이 도구 머리말에 적혀 있었다.

★ 그리고 그 앞에서 한 번 더 틀렸다. `intake --stage` 가 있는데 모르고
  PowerShell `Move-Item` 으로 손이관을 시켰다. **체인이 이미 다 있었는데
  입구가 하나가 아니라서 아무도 전체를 못 봤다.**

── 왜 fire-lane 에 단계를 더하지 않았나 ───────────────────────
`STEPS` 는 `data/processed` 산출물을 내는 단계들이고 `lineage` 와 `golden`
이 그 이름·산출경로에 묶여 있다. 반입은 산출물을 안 만들고 **외장 SSD 를
건드린다.** 섞으면 `--only` · `--from` 의 뜻이 흐려지고 지문 계산에 반입이
끼어든다. 그래서 앞단은 여기서 묶고 `--all` 일 때만 `fire-lane` 을 부른다.

── 규약 ───────────────────────────────────────────────────────
★ **기본이 관측이다.** `--yes` 없이는 아무것도 안 바꾼다. `intake` ·
  `acquire` 가 같은 규약이라 그것을 깨지 않는다.

★ **한 단계라도 실패하면 멈춘다.** 편입이 안 됐는데 정규화가 돌면 낡은
  raw 로 산출물이 나오고, 그게 `golden` 을 통과해 거짓 초록불이 된다
  (2026-08-23 에 실제로 있었다).

★ **다운로드 폴더는 읽기 전용이다.** `intake` 의 설계 ① 을 그대로 따른다 —
  사용자의 폴더지 파이프라인의 것이 아니다. 지우지 않는다.

IN    FIRE_LANE_INBOX (없으면 자동탐색) · FIRE_LANE_DATA
OUT   landing · raw · norm · (--all 이면 processed · web)
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def c(s: str, code: str) -> str:
    return s if os.environ.get("NO_COLOR") else f"\033[{code}m{s}\033[0m"


class Step:
    def __init__(self, name: str, what: str, cmd: list[str], *,
                 only_yes: bool = True, optional: bool = False):
        self.name, self.what, self.cmd = name, what, cmd
        self.only_yes, self.optional = only_yes, optional


def steps(a) -> list[Step]:
    py = [sys.executable]
    T = lambda n: [*py, str(ROOT / "tools" / n)]          # noqa: E731
    out = [
        Step("intake", "Downloads → landing",
             T("intake.py") + ["--stage", "--yes"]),
        Step("stage", "landing → raw (대장 매칭)",
             T("acquire.py") + ["--stage"]),
        Step("verify", "raw ↔ landing sha 대조",
             T("acquire.py") + ["--verify"]),
    ]
    if not a.keep_landing:
        out.append(Step("prune", "sha 같은 landing 원본 정리",
                        T("acquire.py") + ["--prune-landing"]))
    out += [
        Step("quarantine", "대장에 없는 raw 파일 격리",
             T("acquire.py") + ["--quarantine"]),
        Step("judge", "세 판정 — 결손이 남았는가",
             T("acquire.py"), only_yes=False),
        Step("prep", "raw → norm (인코딩·개행·정규명만)",
             [*py, "-m", "firelane.prep", "--apply"]),
        Step("prep-check", "norm 이 raw 와 정합한가",
             [*py, "-m", "firelane.prep", "--check"], only_yes=False),
    ]
    if a.all:
        out += [
            Step("pipeline", "raw/norm → processed · web", ["fire-lane"]),
            Step("golden", "판정 지문 대조",
                 T("golden.py") + ["check"], only_yes=False),
        ]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="실제로 반입한다")
    ap.add_argument("--all", action="store_true",
                    help="파이프라인·golden 까지 이어서 돈다")
    ap.add_argument("--keep-landing", action="store_true",
                    help="landing 원본을 지우지 않는다")
    a = ap.parse_args()

    try:
        sys.path.insert(0, str(ROOT / "src"))
        from firelane import paths as P
        print(c("반입 체인", "1"))
        print(f"  inbox    {P.inbox()}")
        print(f"  landing  {P.LANDING}")
        print(f"  raw      {P.RAW}")
    except Exception as e:                                # noqa: BLE001
        print(c(f"  경로를 못 읽었다: {e}", "31"))
        return 2
    finally:
        if sys.path and sys.path[0] == str(ROOT / "src"):
            sys.path.pop(0)

    plan = steps(a)
    if not a.yes:
        print(c("\n관측만 한다. 실제로 반입하려면 --yes 를 붙여라.\n", "33"))
        for i, s in enumerate(plan, 1):
            mark = "  " if s.only_yes else "· "
            print(f"  {i}. {mark}{s.name:11s} {s.what}")
        print(c("\n  · 표시는 --yes 없이도 도는 관측 단계다.", "90"))
        plan = [s for s in plan if not s.only_yes]
        if not plan:
            return 0
        print()

    t0 = time.time()
    for i, s in enumerate(plan, 1):
        print(c(f"\n[{i}/{len(plan)}] {s.name} — {s.what}", "1;36"))
        print(c("  $ " + " ".join(s.cmd), "90"))
        r = subprocess.run(s.cmd, cwd=ROOT)
        if r.returncode != 0:
            if s.optional:
                print(c(f"  ! {s.name} 실패 — 선택 단계라 계속한다", "33"))
                continue
            print(c(f"\n★ {s.name} 에서 멈췄다 (종료코드 {r.returncode}).", "31"))
            print(c("  다음 단계를 돌리지 않는다 — 낡은 raw 로 산출물이 나오면"
                    "\n  그것이 golden 을 통과해 거짓 초록불이 된다.", "31"))
            return r.returncode

    print(c(f"\n반입 체인 완료 · {time.time() - t0:.1f}s", "1;32"))
    if not a.all:
        print("  다음:  uv run fire-lane  ·  uv run python tools/golden.py check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
