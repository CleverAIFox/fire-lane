"""저장소의 파이썬 소스 전부 — 시험이 「어느 폴더를 훑는가」를 한 곳에서 정한다.  (Zm35)

IN    저장소 루트
OUT   `src` · `tools` · `tests` 의 `*.py` 전부(정렬)
PARAM 없음
밖    어느 폴더에서 **무엇을 단언하는가**는 호출 쪽이 정한다 — 이 함수는 훑기만 한다.

★ 왜 한 문장인가 — `tools/deadcheck.py` ⑤ 「좁은 범위」 가 **훑는 폴더가 파일 집합보다 좁은 시험**을 결함으로 센다. 「`src` 에서만 금지」는 흔한 뜻인데,
  그것을 `(ROOT / "src").rglob(...)` 로 적으면 훑기 자체가 `src` 만 보게 되어 **tools · tests 가 대상에서 빠졌는지 의도인지** 가 코드에서 안 읽힌다.
  훑기는 셋을 다 하고 단언 줄이 `h.startswith("src/")` 로 **의도를 말한다.**
"""
from __future__ import annotations

from pathlib import Path


def all_py(root: Path) -> list[Path]:
    return sorted([*(root / "src").rglob("*.py"), *(root / "tools").rglob("*.py"), *(root / "tests").rglob("*.py")])


def rel(root: Path, paths: list[Path]) -> list[str]:
    return [p.relative_to(root).as_posix() for p in paths]
