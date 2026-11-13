#!/usr/bin/env python3
"""
docnumhist.py — **대체된 값은 저절로 폐기값이 된다 — 이력 전체가.**  (DECISIONS §715 · §721 · #53 재잠금 ②)

★ 왜 생겼나 — `docnumtable.RETIRED` 는 **사람이 적는 목록**이다(「산출값이 바뀌면 옛 값을 한 줄 더한다」 — 그것이 유일한 유지보수였다).
  2026-11-12 재잠금에서 판정 넷 · 소방청 지정의 옛 값이 **하나도 안 들어갔고**, 문서 밖 서술(`blocked 193` 넷 · `소방청 지정 251` 셋 …)이 조용히
  낡았다. 옛 값은 **이미 어딘가에 적혀 있다** — 골든 지문의 git 이력(`L1.n` · `L1.verdict`)과 봉인(`eval.json` 의 `tally`). 거기서 유도한다.

★ **이력 전체를 쓴다**(2026-11-12 · §721 — 처음에는 「방금 대체된 값 하나」였다). 하나만 보면 **그 앞의 값은 영영 안 잡힌다** — 옛 구간 수 1,281 이 그렇게 살아남았다
  (바뀐 것이 2026-11-04 이고 그 뒤 재잠금에서는 직전 값이 아니었다 · 사람이 적는 `RETIRED` 에도 없었다 · 현재형 서술 스물일곱에 묵은 거짓으로 남았다).
  처음에 하나만 쓴 사유는 「이력 전체를 두면 47줄이 걸린다」였다 — 그 47줄을 **읽었더니 이력 전체를 써도 된다**: 현재형 서술은 수를 빼거나 지금 값으로 고쳤고,
  날짜 붙은 회고는 **수를 DECISIONS 참조로 돌렸다**(MASTER · PLAN · README 는 현재형 문서이고 회고는 DECISIONS 에 산다 — `docnum_check.HIST` 가 비어 있는 이유다).
  치른 값: 이제 이 세 문서에 **옛 수를 회고로 쓰면 바로 울린다** — 회고는 DECISIONS 에 쓴다. 이력 전체의 폐기값이 현재 어느 축의 값과 같으면 뺀다.
  구간 수 · 판정 넷 · 소방청 지정만이다 — 회색 사유는 이름 앵커(`no_cctv_thin N`)가 이미 현재값을 대조한다.

IN    `data/golden/segments.fingerprint.json` 의 git 이력 · `data/baseline/*/eval.json`
OUT   is_shallow() · replaced_values(history, cur) → {라벨: [옛 값]} · previous_values() → 새것부터의 이력
PARAM VERDICT_LABELS · GOLDEN_FP_REL
★ **얕은 클론에서는 이 방어선이 줄거나 꺼진다**(이력이 현재 커밋 하나). 침묵하지 않는다 — `is_shallow()` 를 `docnum_check` 가 묻고, CI 에서는 오류다(CI 체크아웃이 이력을 받는다 — `contract.yml` 의 `filter: blob:none`).
밖    **판정은 안 한다** — 어느 줄이 폐기값을 현재형으로 쓰는지는 `docnum_check` 가 든다. **얕은 클론이면 이력이 줄 뿐**이고 거짓 폐기값은 안 낸다.
부류  몸통   `docnum_check.py` 가 import 한다  (DECISIONS §398)
"""
from __future__ import annotations

import json
from pathlib import Path

from firelane import gitq

ROOT = Path(__file__).resolve().parents[1]

#: 판정 네 수 → RETIRED 라벨. 값은 **골든 지문**(`data/golden/segments.fingerprint.json` 의 `L1.verdict`)의 git 이력에서 읽는다. 구간 수는 `L1.n`(아래 `previous_values`).
GOLDEN_FP_REL = "data/golden/segments.fingerprint.json"     # git 이력 조회용 상대 경로(`docnum_check.GOLDEN_FP` 는 절대 경로다)
VERDICT_LABELS: tuple[tuple[str, str], ...] = (
    ("clear", "clear"), ("needs_cv", "needs_cv"), ("blocked", "blocked"), ("unknown(회색)", "unknown"))


def is_shallow(root: Path = ROOT) -> bool:
    """얕은 클론인가(`git rev-parse --is-shallow-repository`). git 이 못 답했으면 아니다 — 거짓 경고를 안 낸다(못 답한 것은 `previous_values` 가 `None` 으로 알린다)."""
    return (gitq.ask(["rev-parse", "--is-shallow-repository"], cwd=root) or "").strip() == "true"


def replaced_values(history: list[dict], cur: dict[str, int]) -> dict[str, list[str]]:
    """각 축에서 **이력의 모든 옛 값**(현재와 다른 값 전부)을 폐기값으로 낸다. 순수 함수 — `--selftest` · 시험이 부른다.  (DECISIONS §715 · §721)

    `history` 는 **새것부터** 옛것으로 가는 `{라벨: 값}` 목록. 지금 **어느 축의** 값과도 같은 수는 뺀다(`retired_clashes` 와 같은 이유 — 맞는 문서가 빨개진다).
    네 자리 이상은 **콤마 있는 꼴과 없는 꼴**(`1,281` · `1281`) 둘 다 낸다 — 문서에 둘 다 실제로 있었다.

    ★ 「방금 대체된 값 하나」가 아니다(§715 의 처음 설계 — 그 앞의 값이 영영 안 잡혀 옛 구간 수 1,281 이 살아남았다). 이력 전체가 문서에 쏟아지는 것(실험 47줄)은 현재형 서술을
      고치고 회고를 DECISIONS 로 돌려 0줄로 만들었다 — 그 뒤에 넓혔다.
    """
    live = {x for v in cur.values() for x in (str(v), f"{v:,}")}
    out: dict[str, list[str]] = {}
    for label in cur:
        got: list[str] = []
        for h in history:                       # 새것 → 옛것
            v = h.get(label)
            if isinstance(v, int) and v != cur[label]:
                for x in dict.fromkeys((str(v), f"{v:,}")):
                    if x not in live and x not in got:
                        got.append(x)
        if got:
            out[label] = got
    return out


def previous_values(root: Path = ROOT, depth: int = 40) -> list[dict] | None:
    """골든 지문 git 이력의 `{라벨: 값}` 목록(새것부터) + 봉인 이력의 소방청 지정. **git 이 못 답했으면 `None`** — 빈 이력과 다른 사실이다(`firelane.gitq` · §372).

    ★ 종전에는 `check=False` 로 stdout 을 갈라 쓰고 실패하면 빈 목록이었다 — git 이 없는 기계 · 깨진 저장소가 「이력이 비었다」로 읽혀 **방어선이 초록으로 꺼졌다**
      (`deadcheck ③ 조용한 통과(git)` 가 잡았다). 이제 부르는 쪽(`docnum_check`)이 `None` 을 소리 내어 알린다.
    ★ 커밋 하나의 블롭을 못 읽으면 그 커밋만 건너뛴다(옛 지문 한 판의 형식이 달라도 이력 전체를 못 읽게 되지는 않는다).
    """
    log = gitq.ask(["log", f"-{depth}", "--format=%H", "--", GOLDEN_FP_REL], cwd=root)
    if log is None:
        return None
    out: list[dict] = []
    for sha in log.split():
        blob = gitq.ask(["show", f"{sha}:{GOLDEN_FP_REL}"], cwd=root)
        if blob is None:
            continue
        try:
            l1 = json.loads(blob).get("L1") or {}
            v = l1.get("verdict") or {}
        except (ValueError, AttributeError):
            continue
        out.append({**{lab: v.get(k) for lab, k in VERDICT_LABELS}, "세그먼트 수": l1.get("n")})
    # 소방청 지정은 지문에 없다 — 봉인(`eval.json` 의 `tally`)이 새것부터 남긴다.
    for p in sorted((root / "data" / "baseline").glob("*/eval.json"), reverse=True):
        try:
            out.append({"소방청 지정": json.loads(p.read_text(encoding="utf-8")).get("tally", {}).get("nfa_designated")})
        except (OSError, ValueError):
            continue
    return out
