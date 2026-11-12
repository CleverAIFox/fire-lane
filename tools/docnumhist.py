#!/usr/bin/env python3
"""
docnumhist.py — **방금 대체된 값은 저절로 폐기값이 된다.**  (DECISIONS §715 · #53 재잠금 ②)

★ 왜 생겼나 — `docnumtable.RETIRED` 는 **사람이 적는 목록**이다(「산출값이 바뀌면 옛 값을 한 줄 더한다」 — 그것이 유일한 유지보수였다).
  2026-11-12 재잠금에서 판정 넷 · 소방청 지정의 옛 값이 **하나도 안 들어갔고**, 문서 밖 서술(`blocked 193` 넷 · `소방청 지정 251` 셋 …)이 조용히
  낡았다. 옛 값은 **이미 어딘가에 적혀 있다** — 골든 지문의 git 이력(`L1.verdict`)과 봉인(`eval.json` 의 `tally`). 거기서 유도한다.

★ **방금 대체된 값 하나만** 낸다. 이력 전체를 폐기값으로 두면 수년 전 값까지 현재형 서술에 걸려 쏟아지고(실험: 47줄 · 스물다섯은 옛 구간 수 1,281),
  그러면 사람이 이 문을 끈다. 재잠금마다 새로 낡는 것은 **바로 그 직전 값**이다. 구간 수(`n`)와 회색 사유는 안 넣는다 — 구간 수는 묵은 빚이라
  사람이 정하는 `RETIRED["세그먼트 수"]` 가 지키고, 회색 사유는 이름 앵커(`no_cctv_thin N`)가 이미 현재값을 대조한다.

IN    `data/golden/segments.fingerprint.json` 의 git 이력 · `data/baseline/*/eval.json`
OUT   replaced_values(history, cur) → {라벨: [옛 값]} · previous_values() → 새것부터의 이력
PARAM VERDICT_LABELS · GOLDEN_FP_REL
밖    **판정은 안 한다** — 어느 줄이 폐기값을 현재형으로 쓰는지는 `docnum_check` 가 든다. **얕은 클론이면 이력이 줄 뿐**이고 거짓 폐기값은 안 낸다.
부류  몸통   `docnum_check.py` 가 import 한다  (DECISIONS §398)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 판정 네 수 → RETIRED 라벨. 값은 **골든 지문**(`data/golden/segments.fingerprint.json` 의 `L1.verdict`)의 git 이력에서 읽는다.
#: ★ 구간 수(`n`)와 회색 사유는 **안 넣는다** — 구간 수는 옛 값(1,281)이 현재형 서술 스물다섯에 남아 있는 **묵은 빚**이라 이번 재잠금의 일이 아니고
#:   (사람이 정하는 `RETIRED["세그먼트 수"]` 가 지킨다), 회색 사유는 이름 앵커(`no_cctv_thin N`)가 이미 현재값을 대조한다.
GOLDEN_FP_REL = "data/golden/segments.fingerprint.json"     # git 이력 조회용 상대 경로(아래 `GOLDEN_FP` 는 절대 경로다)
VERDICT_LABELS: tuple[tuple[str, str], ...] = (
    ("clear", "clear"), ("needs_cv", "needs_cv"), ("blocked", "blocked"), ("unknown(회색)", "unknown"))


def replaced_values(history: list[dict], cur: dict[str, int]) -> dict[str, list[str]]:
    """각 축에서 **방금 대체된 값**(현재와 다른 가장 가까운 옛 값)을 폐기값으로 낸다. 순수 함수 — `--selftest` · 시험이 부른다.  (DECISIONS §715)

    `history` 는 **새것부터** 옛것으로 가는 `{라벨: 값}` 목록(골든 지문의 `L1.verdict` + 소방청 지정). 지금 **어느 축의** 값과도 같은 수는 뺀다
    (`retired_clashes` 와 같은 이유 — 맞는 문서가 빨개진다).

    ★ **왜 「방금 대체된 값 하나」인가.** 이력 전체를 폐기값으로 두면 수년 전 값까지 현재형 서술에 걸려 쏟아지고(실험: 47줄 · 대부분 묵은 값),
      그러면 사람이 이 문을 끈다. 재잠금마다 새로 낡는 것은 **바로 그 직전 값**이다 — 그 하나만 문다.
    """
    live = {x for v in cur.values() for x in (str(v), f"{v:,}")}
    out: dict[str, list[str]] = {}
    for label, now in cur.items():
        for h in history:
            v = h.get(label)
            if isinstance(v, int) and v != now:
                x = f"{v:,}" if v >= 1000 else str(v)
                if x not in live:
                    out[label] = [x]
                break
    return out


def previous_values(root: Path = ROOT, depth: int = 40) -> list[dict]:
    """골든 지문 git 이력의 `{라벨: 값}` 목록(새것부터) + 봉인 이력의 소방청 지정. 못 읽으면 덜 읽는다 — **얕은 클론이면 검사가 줄 뿐 거짓은 아니다.**"""
    out: list[dict] = []
    try:
        shas = subprocess.run(["git", "log", f"-{depth}", "--format=%H", "--", GOLDEN_FP_REL], cwd=root,  # noqa: S603,S607 — PATH 의 git 이다 · 저장소 안의 고정 인자
                              capture_output=True, text=True, timeout=60, check=False).stdout.split()
    except (OSError, subprocess.SubprocessError):
        shas = []
    for sha in shas:
        try:        # ★ 커밋마다 따로 — 옛 지문 한 판의 형식이 달라도 이력 전체를 못 읽게 되지는 않는다
            blob = subprocess.run(["git", "show", f"{sha}:{GOLDEN_FP_REL}"], cwd=root,  # noqa: S603,S607 — PATH 의 git 이다 · 저장소 안의 고정 인자
                                  capture_output=True, text=True, timeout=60, check=False)
            v = (json.loads(blob.stdout).get("L1") or {}).get("verdict") or {}
            out.append({lab: v.get(k) for lab, k in VERDICT_LABELS})
        except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
            continue
    # 소방청 지정은 지문에 없다 — 봉인(`eval.json` 의 `tally`)이 새것부터 남긴다.
    seals = []
    for p in sorted((root / "data" / "baseline").glob("*/eval.json"), reverse=True):
        try:
            seals.append({"소방청 지정": json.loads(p.read_text(encoding="utf-8")).get("tally", {}).get("nfa_designated")})
        except (OSError, ValueError):
            continue
    return out + seals
