"""
tests/ratchet_names.py — 「선언한 축 == 산출한 축」을 **도구 조각 단위로** 훑는 문 (W13-17 · DECISIONS §802-G).

시험 파일이 아니다(`test_` 로 안 시작해 수집되지 않는다). `tests/test_ratchet_names_<i>.py` 셋이 부른다.

── 왜 갈랐나 (2026-11-16) ──────────────────────────────────────
옛 시험 한 건(`test_ratchet.py::test_declared_ratchet_names_equal_produced_names_per_tool`)이 도구 38개의 `ratchet_values()` 를 한 프로세스에서 차례로 불러
**단독 61~69초**였다(서브프로세스는 없다 — 도구가 소스를 `ast` · 정규식으로 훑는 일이 대부분이고 가장 무거운 다섯이 약 46초). 파일 단위로 병렬을 도는
`testpick` 에서는 이 한 건이 **병렬 8 에서 303초**로 부풀어 시험당 시한 300초를 넘겼다.
같은 물음을 도구를 세 조각으로 나눠 **세 파일**로 묻는다 — 단언은 한 글자도 안 바꿨다(`check_tool` 이 옛 반복문의 몸통 그대로다). 도구 목록은 `RT.owners()`
(손목록이 아니다)를 `i::K` 로 가르고 K 는 `test_ratchet_names_*.py` 파일 수이므로 **조각 사이로 새는 도구가 없다**(`slice_of` 가 번호의 연속을 문다).

IN    tools/ratchet.py(`owners()` · `lake_only()` · `_map_keys`) · 각 도구의 `ratchet_values()`
OUT   `check_tool` · `run_slice` · `slice_of`
밖    **축의 값이 옳은가는 안 본다**(이름의 집합만). 시험이 아니라 문이라 스스로는 수집되지 않는다
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HERE = Path(__file__).resolve().parent


def _rt():
    spec = importlib.util.spec_from_file_location("ratchet_n", ROOT / "tools" / "ratchet.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m          # @dataclass·되짚기 (§258-10)
    spec.loader.exec_module(m)
    return m


RT = _rt()
_NAME = re.compile(r"test_ratchet_names_(\d+)\.py$")


def slice_files() -> list[Path]:
    return sorted(_HERE.glob("test_ratchet_names_*.py"))


def slice_of(test_file: str) -> tuple[int, int]:
    """이 시험 파일의 (번호, 조각 수). 번호는 파일 이름에서 읽고 0..K-1 이 이어져야 한다."""
    nums = sorted(int(m.group(1)) for p in slice_files() if (m := _NAME.search(p.name)))
    assert nums == list(range(len(nums))), f"조각 번호가 0..K-1 로 안 이어진다 {nums} — 도구가 조각 사이로 샌다"
    m = _NAME.search(Path(test_file).name)
    assert m, f"{test_file} 은 조각 이름(test_ratchet_names_<번호>.py)이 아니다"
    return int(m.group(1)), len(nums)


def check_tool(p, m, exempt) -> str:
    """도구 하나의 선언 축 == 산출 축. `"checked"` 또는 `"skipped"`(면제 선언된 것만). 어긋나면 AssertionError."""
    try:
        produced = set(m.ratchet_values())
    except Exception as e:                  # noqa: BLE001 — 레이크 의존 도구의 실측 함수
        # 변이 장부가 낡으면 `mutate.py` 가 **일부러** 죽는다(장부를 다시 재라는 사람 몫의 빨강). 그 하나만 건너뛴다 — 면제 선언된 레이크 도구도 건너뛴다.
        stale_ledger = p.name == "mutate.py" and "mutate.py --write --stale" in str(e)
        assert p.name in exempt or stale_ledger, f"{p.name} 의 `ratchet_values()` 가 죽었는데 면제 사유가 없다 — {e}"
        return "skipped"
    src = p.read_text(encoding="utf-8")
    declared: set[str] = set()
    for name, direction in m.RATCHETS.items():
        if direction == "down-map":
            # 표는 **예외 항목**만 선언한다 — 산출은 모든 파일을 낸다. 그래서 선언 키 ⊆ 산출 키(산출이 모르는 키를 선언했으면 그 항목이 죽었다)이고
            # 표 항목은 같음 비교에서 뺀다(그 표의 산출 키는 다른 선언이 없으면 표 키 전부다).
            keys = set(RT._map_keys(src, name))
            assert keys <= produced, f"{p.name}: 표 `{name}` 이 산출이 모르는 키를 선언했다 {sorted(keys - produced)[:5]}"
            declared |= produced if len(m.RATCHETS) == 1 else keys
        else:
            declared.add(name)
    # 레이크 없는 기계는 `ratchet_values()` 가 예외 대신 **이름을 안 낸다**(0 으로 쓰면 조용히 초록 — `contract.py`). 빠져도 되는 것은 소유 모듈이
    # `LAKE_ONLY` 로 **이름까지** 선언한 것뿐이다(`ratchet.py` 본체와 같은 규칙) — 선언 안 된 이름이 빠지면 그대로 빨강이고, 산출이 선언 밖이어도 빨강이다.
    lake = m.LAKE_ONLY if isinstance(getattr(m, "LAKE_ONLY", None), dict) else {}
    missing = declared - produced
    if missing and missing <= set(lake):
        assert produced <= declared, f"{p.name}: 산출만 {sorted(produced - declared)[:5]}"
        return "skipped"
    assert declared == produced, (
        f"{p.name}: 선언만 {sorted(declared - produced)[:5]} · 산출만 {sorted(produced - declared)[:5]}")
    return "checked"


def run_slice(test_file: str) -> None:
    i, k = slice_of(test_file)
    exempt = RT.lake_only()
    mine = RT.owners()[i::k]
    checked = skipped = 0
    for p, m in mine:
        if check_tool(p, m, exempt) == "checked":
            checked += 1
        else:
            skipped += 1
    # 옛 「checked >= 5 and checked > skipped」(도구 38개)를 조각 크기에 맞춘 빈 그물 막이 — 조각이 거의 다 건너뛰면 그물이 비었다
    assert checked >= 3 and checked > skipped, f"조각 {i}/{k}: 훑은 도구 {checked} · 건너뜀 {skipped} — 빈 그물이다"
