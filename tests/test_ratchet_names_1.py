"""선언한 축 == 산출한 축, 도구 조각 1 — 물음과 단언은 `tests/ratchet_names.py` 가 든다(DECISIONS §802-G).

IN    tools/ratchet.py 의 `owners()` 를 `i::K` 로 가른 조각 · 각 도구의 `ratchet_values()`
OUT   없음
밖    **축의 값이 옳은가는 안 본다** — 이름의 집합(선언 == 산출)만 본다. 다른 조각의 도구는 그 조각 파일이 든다
"""
from ratchet_names import run_slice


def test_declared_ratchet_names_equal_produced_names_slice():
    run_slice(__file__)
