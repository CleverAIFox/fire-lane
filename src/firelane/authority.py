"""authority — 대장 항목(`sources.yaml` 의 `datasets`)이 **받은 경로를 적었는가**의 판정.  (PLAN #199 ④ · DECISIONS §445 · §453)

IN    `ledger.load()` 가 낸 대장 한 벌(`datasets` 의 각 항목 `authority` 칸)
OUT   `bad(y)` 위반 문장 · `split(y)` 사유별 갈래 — **판정만 한다.** 파일도 대장도 안 쓴다.
PARAM 없음 — 상한(`MAX_AUTHORITY_*`)은 이 모듈이 아니라 `tests/test_lake.py` 의 래칫이 든다
밖    **받은 경로가 사실인가는 안 본다**(괄호 꼴인지만 본다). 상한이 옳은가도 안 본다.

★ 왜 시험 안에서 꺼냈나 — 이 판정이 `tests/test_lake.py` 안에 살면 그 시험 말고는 아무도 못 부른다. 새 대장 항목이 받은 경로를 안 적었는지를
  푸시 전에 이름으로 대려면(`tools/obligations.py`) **같은 판정을 한 벌** 불러야 한다 — 두 번째 정규식을 만들면 사본이다(오늘 `plan_renumber` 에서도
  같은 일을 했다). 시험은 이 함수를 부르고 래칫만 든다.
"""
from __future__ import annotations

import re

AUTHORITY = re.compile(r"^\S.*\S \((?P<route>[^()]+)\)$")

#: `bad` 가 내는 꼬리말의 **세 갈래 문구** — 가름의 키. 문구가 바뀌면 `tests/test_lake.py` 의 전수 시험이 운다.
KINDS = ("칸 없음", "받은 경로 괄호 없음", "개인 경유")


def bad(y: dict) -> list[str]:
    out = []
    for k, e in (y.get("datasets") or {}).items():
        a = str((e or {}).get("authority") or "").strip()
        if not a:
            out.append(f"{k}: 칸 없음")
        elif "경유" in a:
            out.append(f"{k}: 개인 경유 — {a}")
        elif not AUTHORITY.match(a):
            out.append(f"{k}: 받은 경로 괄호 없음 — {a}")
    return out


def split(y: dict) -> dict[str, list[str]]:
    """위반을 **사유별로** 가른다. 판별은 `bad` 하나가 한다 — 낱말로 다시 가르지 않고 그 함수의 세 갈래 문구를 키로 쓴다."""
    out: dict[str, list[str]] = {k: [] for k in KINDS}
    for b in bad(y):
        for k in out:
            if k in b:
                out[k].append(b)
                break
    return out
