#!/usr/bin/env python3
"""
mutatesilent.py — 붙잡이가 **침묵한** 것을 판정하고 세는 집.

── 왜 옆집인가 (2026-10-14 · DECISIONS 532-3) ──────────────────
`mutate.py` 가 **정확히 상한 600 에 서 있었다.** 이 축을 거기 두면 넘고,
예외로 올리면 「상한에 붙어 사는 파일이 많다」는 신호가 꺼진다
(`sizetable` 의 2026-09-24 문단이 그 말을 적고 있다).

이 도구는 이미 옆집 셋을 갖고 있다 — `mutatetest`(자기검사) ·
`mutatescope` · `prevfield`. 넷째를 두는 것이 이 저장소의 방식이고,
「어느 파일에 있나」가 기억거리가 되는 문제(§18-3)는 **이름이 곧 축**이라
안 생긴다.

── 무엇을 보나 ─────────────────────────────────────────────────
붙잡이가 `rc=0` 인데 **한 글자도 안 찍었으면** 돈 것이 아니라 안 돈 것이다.
돌연변이가 **자기 붙잡이를 끊는** 자리라 생존·사망 어느 쪽도 아니다 —
`못 쟀다`가 참이다. 사유와 실측은 DECISIONS 532 ~ 532-2.

IN    `subprocess.CompletedProcess` · 장부(`data/golden/mutation.json`)
OUT   없음 (판정 · 수)
PARAM SILENCED — **이 축을 아는 도구가 제 래칫을 든다.** 이 저장소의 꼴이
      그렇다: `canary.NO_CANARY` · `sealcov.SEALED_FILES` · `docseal.UNSEALED` ·
      `navicov.NAVI_UNTESTED` · `toolclass.UNDECLARED`. `ratchet.py` 가 모은다
밖    **흔드는 일도 재는 일도 안 한다.** 침묵인지만 가른다.
"""
from __future__ import annotations

#: 침묵을 적는 꼬리표. 「못 쟀다」 문자열이 이것을 들면 `SILENCED` 로 센다.
MARK = "★붙잡이 침묵"


class SilentCatcher(RuntimeError):
    """붙잡이가 **rc=0 인데 한 글자도 안 찍었다** — 돈 것이 아니라 안 돈 것이다.

    강제자는 `tests/test_entry_guard.py`(그 자리를 받는 자)와
    `tests/test_mutatesilent.py`(이 판정을 미는 자)다.
    """


def is_silent(rc: int, out: str, err: str) -> bool:
    """`rc=0` 인데 아무 글자도 없으면 참."""
    return rc == 0 and not (out + err).strip()


def label(cmd: list[str]) -> str:
    """침묵한 명령을 **기계 이름 없이** 적는다.

    ★ `cmd[0]` 은 `sys.executable` 이고 **절대 경로**다. 그대로 적으면
      기계마다 다른 경로가 **장부에 커밋된다** — 작업 폴더 이름이 UUID 꼴이면
      `test_gitleaks_allowlist` 가 울고, 울지 않아도 남의 기계 경로가 떠돈다.
    """
    return " ".join(["python", *cmd[1:]])


def count(ledger: dict) -> int:
    """장부에서 침묵한 **과녁** 수. `UNCATCHABLE`(붙잡이가 0 인 **도구** 수)과
    다른 축이다 — 섞으면 「안 달았다」와 「끊겼다」가 한 수가 된다."""
    return sum(1 for r in ledger.get("도구별", [])
               for u in r.get("못 쟀다", []) if MARK in u)


#: 침묵한 과녁 수 — **내려가는 쪽으로만.**
#: ★ 2026-10-14 (DECISIONS 532) 초기값은 실측이다 —
#:   `docgen` · `planclose` · `ratchet` · `sizecheck`. 넷 다 같은 자리다.
SILENCED = 4
RATCHETS = {"SILENCED": "down"}


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. **판정은 안 한다**(`ratchet.py` 소관)."""
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "data/golden/mutation.json"
    if not p.is_file():
        raise RuntimeError("data/golden/mutation.json 이 없다 — "
                           "`mutate.py --write` 가 만든다 (느리다)")
    return {"SILENCED": count(json.loads(p.read_text(encoding="utf-8")))}
