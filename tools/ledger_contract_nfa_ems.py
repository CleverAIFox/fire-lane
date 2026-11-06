#!/usr/bin/env python3
"""
ledger_contract_nfa_ems.py — **비웠다. `tools/ledger_extract.py` 를 써라.**  (DECISIONS §648)

이 도구는 nfa_ems 에 추출 선언을 박아 넣었고 필터가 **단일 조건**(`sgg_nm=동구`)이었다. 「동구」가 여섯 광역시에 있어 406,168행이 나왔다(§647).
복사하면 같은 결함이 같이 복사된다 — 그래서 원천 키와 조건을 인자로 받는 `tools/ledger_extract.py` 로 다시 세웠다.

    uv run python tools/ledger_extract.py --key <키> --normalize <lower_strip|upper_strip> \\
        --filter COL=VAL [--filter COL=VAL …] --scope-min N --scope-max M [--apply]

왜 지우지 않고 한 줄로 남겼나 — MASTER §23-2 등재 · DECISIONS · 문서 도장 · `finish_647_seal.py` 가 이 경로를 가리킨다. 지우면 그 참조가 한꺼번에 죽고,
옛 명령을 친 사람은 「없다」만 받는다. 여기서는 이유와 새 명령을 받는다. 이 파일은 아무것도 고치지 않는다.

IN    없음
OUT   없음 (종료 2 — 새 도구로 안내만 한다)
PARAM 없음
부류  절차   옛 이름을 새 도구로 돌린다. **산출물에 안 닿는다**  (DECISIONS §398)
밖    대장을 고치지 않는다.
"""
from __future__ import annotations

import sys


def main() -> int:
    print("✗ 이 도구는 비웠다 — tools/ledger_extract.py 를 써라 (--key · --normalize · --filter 반복 · --scope-min · --scope-max).\n"
          "  이유: 단일 조건 필터가 광주 밖 다섯 광역시의 「동구」를 섞어 406,168행을 냈다(DECISIONS §647 · §648).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
