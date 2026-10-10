"""`doc_fsck` 의 프로브들. 진입점은 `tools/doc_fsck.py` 하나다.  (§258-19 · PLAN #136)

★ 여기에는 **프로브가 공유하는 것만** 둔다. 프로브 자신은 각자 파일에 있다.
밖    판정은 안 한다 — 이 묶음은 자리이지 검사가 아니다.
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
"""
from __future__ import annotations


def _today() -> str:
    """오늘(KST).

    ★ 시간대를 명시한다. `date.today()` 는 실행 머신의 시간대를 쓰는데
      CI 는 UTC 이고 사람은 KST 다. 게이트가 아홉 시간 늦게 운다.
      `.ruff-strict.toml` 의 DTZ011 이 이것을 막는다.

    ★ 계산을 한 곳에 둔다. 종전에는 `check_expiry` 안에만 있었고
      `check_deferred` 가 생기면서 두 벌이 됐다(§73 과 같은 형태).
    """
    import datetime as _dt
    return _dt.datetime.now(
        tz=_dt.timezone(_dt.timedelta(hours=9))).date().isoformat()
