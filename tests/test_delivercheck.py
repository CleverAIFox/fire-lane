#!/usr/bin/env python3
"""
test_delivercheck.py — 배달물 판별식이 **살아 있는가.**  (DECISIONS §276-1)

── 왜 생겼나 ──────────────────────────────────────────────────
`deliver.py` 가 밑동·폐포·산출물·스윕·pytest 를 다 재면서 **PR 본문만 안 쟀다.**
검사기(`pr_body_check.py`)는 저장소에 있었고 그날 아침에 그것을 고치기까지 했는데,
**보내기 전 예습에는 안 걸었다.** 배치 B 에서 본문 둘이 체크박스를 안 골라
왕복 둘을 태웠다 — 둘 다 보내기 전에 기계가 알 수 있었다.

IN    tools/delivercheck.py
OUT   없음 (검사)
밖    **패치가 붙는지는 안 본다** — 워크트리를 떠야 알고 `deliver.dryrun` 이 든다.
      **본문의 내용이 옳은지도 안 본다** — 템플릿을 채웠는가만 본다.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ★ `sys.path` 를 건드리지 않는다 — `test_layering::test_sys_path_해킹이_없다` 가
#   막는다. 경로를 박으면 그 파일이 어디 있는지가 두 곳에 적히고, 옮기는 날
#   한쪽만 따라간다. 저장소 관례대로 파일에서 직접 올린다.
# ★ 경로를 **한 줄 리터럴**로 적는다. `test_tools_are_wired` 의 배선 탐지가
#   줄 단위라, 두 줄로 나누면 「아무도 안 부른다」로 읽힌다(§276-1 꼬리).
_spec = importlib.util.spec_from_file_location("delivercheck", ROOT / "tools/delivercheck.py")
assert _spec and _spec.loader
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)


def _run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


BODY_OK = """## 무엇을 · 왜

배선만 바꿨다.

## 리뷰어가 볼 곳 — **한 곳만**

`src/firelane/ingest.py:230`

## 산출물이 바뀌는가

- [x] 안 바뀐다
- [ ] 바뀐다 → `tools/golden.py lock` 재잠금 + 아래에 전후 값

## 계약을 건드리는가

- [x] 안 건드린다
- [ ] `src/contracts/` · `test_contract.py` · `web/config.js` 를 건드린다
"""


def test_a_delivery_without_a_pr_body_cries():
    """★ 본문이 없으면 열차 2단계가 죽는다 — 보내기 전에 안다."""
    bad = D.bodies_missing(["0001-x.patch", "EXPECT", "BASE"])
    assert bad, "`PR_BODY.md` 가 없는데 안 운다"
    assert "2단계" in bad[0], "왜 문제인지 안 알려준다"


def test_a_delivery_with_a_pr_body_is_quiet():
    assert not D.bodies_missing(["PR_BODY.md", "PR_BODY_DEV.md", "0001-x.patch"])


def test_a_body_that_skips_the_template_cries(tmp_path: Path):
    """★ 2026-09-27 실제 사고. 체크박스를 안 골라 열차가 두 번 죽었다."""
    (tmp_path / "PR_BODY.md").write_text("## 무엇을 · 왜\n\n대충\n", encoding="utf-8")
    bad = D.bodies_bad(tmp_path, _run, sys.executable)
    assert bad, "템플릿을 안 채웠는데 안 운다"
    assert "PR_BODY.md" in bad[0]


def test_a_body_that_fills_the_template_is_quiet(tmp_path: Path):
    (tmp_path / "PR_BODY.md").write_text(BODY_OK, encoding="utf-8")
    assert not D.bodies_bad(tmp_path, _run, sys.executable)


def test_every_pr_body_is_checked_not_just_the_first(tmp_path: Path):
    """★ `PR_BODY_DEV.md` 가 이번에 빠졌다. 하나만 보면 나머지가 8단계에서 죽는다."""
    (tmp_path / "PR_BODY.md").write_text(BODY_OK, encoding="utf-8")
    (tmp_path / "PR_BODY_DEV.md").write_text("## 무엇을 · 왜\n\n대충\n", encoding="utf-8")
    bad = D.bodies_bad(tmp_path, _run, sys.executable)
    assert bad and any("DEV" in b for b in bad), "둘째 본문을 안 본다"


def test_the_checker_it_calls_actually_exists():
    """★ 카나리아. 검사기가 없으면 `bodies_bad` 는 **언제나 빨갛다** — 그것은 검사가 아니다."""
    assert (ROOT / D.BODY_CHECK).exists(), f"{D.BODY_CHECK} 가 없다"


@pytest.mark.parametrize(("names", "want"), [
    (["0001-a.patch", "0001-a.patch"], True),
    (["0001-a.patch", "0002-b.patch"], False),
])
def test_duplicate_patch_names_are_caught(names, want):
    assert bool(D.collide(names)) is want


@pytest.mark.parametrize(("names", "want"), [
    (["0001-x.patch", "0003-x.patch"], True),
    (["0001-x.patch", "0002-y.patch"], False),
])
def test_same_tail_different_number_is_caught(names, want):
    assert bool(D.tails(names)) is want


def test_forbidden_strings_are_read_from_the_message_not_the_diff(tmp_path: Path):
    """규약은 커밋 메시지에 걸린다. diff 안의 같은 글자는 결함이 아니다."""
    msg = tmp_path / "0001-x.patch"
    msg.write_text(f"제목\n\n{D.FORBIDDEN[0]} <x@y>\n", encoding="utf-8")
    assert D.forbidden([msg])
    clean = tmp_path / "0002-y.patch"
    clean.write_text("제목\n\n본문뿐이다\n", encoding="utf-8")
    assert not D.forbidden([clean])


def test_the_forbidden_list_is_not_empty():
    """★ 대장이 비면 통과가 아니라 **볼 것이 없음**이다(`deadcheck ③`)."""
    assert D.FORBIDDEN, "`FORBIDDEN` 이 비었다"
