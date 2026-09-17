"""skip 정책 — **건너뛴 것은 통과가 아니다.** 사유가 분류 안에 있어야 skip 이다.

★ 2026-09-17 (DECISIONS §173-6 · §175). 레이크 기계의 skip 51 이 전부 "랜덤 미사용" 하나였다.
  검사 대상이 아닌 파일을 skip 으로 세고 있어서, 진짜 skip 이 늘어도 51 에 묻혔다.
  새 모듈 하나(firelane.lake)를 넣자 51 → 52 가 됐고 아무도 안 봤다.

    환경skip(레이크) — …   레이크가 없는 기계(CI). **레이크가 붙은 기계에서는 실패로 센다**
    환경skip(산출물) — …   파이프라인 산출물이 없는 기계(clone 직후 · CI). 레이크 기계에 산출물이 있으면 실패
    환경skip(도구) — …     git · node · 선택 의존성이 없는 환경. importorskip 은 여기로 친다
    유예skip — 「PLAN 행 제목」 · YYYY-MM-DD — …   그 행이 PLAN §1 에 있고 21일 안일 때만
    그 밖                   실패. 해당없음은 skip 이 아니다 — 수집 단계에서 거르거나 통과시킨다

`tests/conftest.py` 가 모든 skip 보고에 `judge` 를 건다. 카나리아 — `tests/test_skip_policy.py`.
"""
from __future__ import annotations

import re
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = re.compile(r"^환경skip\((레이크|산출물|도구)\) — \S")
DEFER = re.compile(r"^유예skip — 「(?P<title>[^」]+)」 · (?P<d>\d{4}-\d{2}-\d{2}) — \S")
IMPORT = re.compile(r"^could not import ")
MAX_DEFER_DAYS = 21


def judge(reason: str, *, lake_attached: bool, today: date, plan_titles: set[str],
          outputs_present: bool = False) -> str | None:
    """위반이면 사유 문장, 아니면 None."""
    reason = reason.strip().removeprefix("Skipped: ")
    if IMPORT.match(reason):
        return None
    if m := ENV.match(reason):
        if m.group(1) == "레이크" and lake_attached:
            return "레이크가 붙은 기계에서 레이크 skip 이 났다 — 여기서는 돌아야 한다. 조건식을 보라"
        if m.group(1) == "산출물" and lake_attached and outputs_present:
            return ("레이크 기계에 파이프라인 산출물이 있는데 산출물 skip 이 났다 — 조건식이 틀렸거나 "
                    "산출물 이름이 바뀌었다")
        return None
    if m := DEFER.match(reason):
        if m.group("title") not in plan_titles:
            return f"유예 사유의 PLAN 행 「{m.group('title')}」 이 §1 에 없다 — 행이 닫혔으면 skip 을 풀어라"
        age = (today - date.fromisoformat(m.group("d"))).days
        if age < 0:
            return "유예 날짜가 미래다"
        if age > MAX_DEFER_DAYS:
            return f"유예 {age}일 — 상한 {MAX_DEFER_DAYS}일. 닫거나, 사유가 바뀌었으면 날짜와 함께 다시 적어라"
        return None
    return ("사유가 분류 밖이다 — `환경skip(레이크|산출물|도구) — …` · `유예skip — 「행」 · 날짜 — …` 중 하나.\n"
            "  해당없음이면 skip 이 아니다 — 수집 단계에서 대상을 거르거나 통과시켜라")


@lru_cache(maxsize=1)
def lake_attached() -> bool:
    from firelane import paths
    d = paths.DATA
    try:
        return bool(d and (d / "raw").is_dir() and any((d / "raw").iterdir()))
    except OSError:
        return False


@lru_cache(maxsize=1)
def outputs_present() -> bool:
    """파이프라인이 한 번이라도 돈 기계인가 — 커밋 안 하는 gpkg 가 있으면 돈 것이다."""
    d = ROOT / "data" / "processed"
    return d.is_dir() and any(d.glob("*.gpkg"))


@lru_cache(maxsize=1)
def plan_titles() -> frozenset[str]:
    p = ROOT / "docs" / "PLAN.md"
    if not p.exists():
        return frozenset()
    rows = re.findall(r"^\| *\d+ *\| *(.+?) *\| *(?:📄|🟡|🔴|⏳|⚠)", p.read_text(encoding="utf-8"), re.M)
    return frozenset(rows)


def is_git_repo() -> bool:
    import shutil
    import subprocess
    if not shutil.which("git"):
        return False
    return subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT,
                          capture_output=True).returncode == 0
