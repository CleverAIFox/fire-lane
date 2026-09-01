#!/usr/bin/env python3
"""
test_doc_fsck.py — `tools/doc_fsck.py` 의 넷을 CI 에서 강제한다.

★ 도구를 만들어 두고 사람이 가끔 돌리는 것으로는 안 된다. `§79` 가 적은 대로
  **예외는 문서 밖에서 자라서 읽어도 안 보인다.** 검사가 CI 에서 울어야 보인다.

★ 이 파일은 판정을 하지 않는다. 어긋난 자리를 그대로 옮겨 실패 메시지로 낸다.
  어느 쪽이 정본인지는 사람이 정한다 — 보통 최신이지만 늘 그렇지는 않다.

IN    tools/doc_fsck.py
OUT   없음 (검사)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ★ `sys.path` 를 건드리지 않는다. `tools/` 는 패키지가 아니라 스크립트
#   모음이라 import 경로에 넣으면 이름이 전역에 샌다.
#   `tests/test_layering.py::test_sys_path_해킹이_없다` 가 그것을 막는다.
_spec = importlib.util.spec_from_file_location(
    "doc_fsck", ROOT / "tools" / "doc_fsck.py")
doc_fsck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(doc_fsck)


@pytest.fixture(scope="module")
def led():
    return doc_fsck._ledger()


def _fail(title: str, bad: list[str], why: str) -> None:
    assert not bad, (
        f"{title}\n" + "\n".join(f"  · {b}" for b in bad) + f"\n\n  {why}")


def test_ledger_schema_doc_matches_reality(led):
    """★ 2026-09-01. README 예시가 `url` `license` `retrieved` 를 드는데 실물
    41개 중 0건이었다. 지혜님이 그 예시를 보고 대장 초안을 쓰다 어긋났다."""
    _fail("대장 스키마 문서가 실물과 다르다", doc_fsck.check_schema(led),
          "src/firelane/README.md 의 예시를 실물에 맞춘다. "
          "메타 항목의 정본은 sources.yaml 머리말이다.")


def test_paths_that_docs_point_at_exist():
    """★ 2026-09-01. `web/config.js` 가 `profiles.json` 을 fetch 하는데 저장소에
    그 파일이 없었다. clone 한 사람은 제원 칸이 빈 화면을 본다."""
    _fail("문서·설정이 없는 파일을 가리킨다", doc_fsck.check_paths(),
          "DECISIONS(경위) 와 PLAN(계획) 은 대상이 아니다. "
          "여기 잡힌 것은 '지금 그렇게 동작한다' 고 말하는 자리다.")


def test_absent_declarations_are_true(led):
    """★ 2026-09-01. 대장이 `turn_radius_m` 을 "7종 전수 확인 0건" 으로
    선언하는데 `profiles.json` 은 7300~11889 를 갖고 있었다."""
    _fail("대장이 없다고 한 값이 실물에 있다", doc_fsck.check_absent(led),
          "값을 지우는 것이 아니라 선언을 사실에 맞춘다. "
          "출처가 있으면 적고 미검증이면 그렇게 적는다(§81).")


def test_human_made_layer_is_in_the_ledger(led):
    """★ 2026-09-01. `layers.field` 는 재취득 불가한 실측이라고 선언하는데
    재취득 가능한 공공데이터 CSV 가 들어와 있었고 대장에도 없었다."""
    _fail("사람이 만드는 계층에 대장 밖 파일이 있다",
          doc_fsck.check_field_ledger(led),
          "재취득 가능하면 landing→raw 로 보낸다. 실측이면 대장에 등재한다. "
          "유예가 필요하면 doc_fsck.FIELD_EXEMPT 에 사유와 날짜를 적는다.")


def test_the_gate_actually_cries():
    """★ 해제만 검사하면 항상 통과하는 검사를 만들게 된다(§69).
    없는 경로를 하나 심어 ② 가 우는지 본다."""
    probe = ROOT / "docs/MASTER.md"
    original = probe.read_text(encoding="utf-8")
    try:
        probe.write_text(original + "\n\n<!-- tools/__doc_fsck_probe__.py -->\n",
                         encoding="utf-8")
        assert doc_fsck.check_paths(), "없는 경로를 심었는데 ② 가 조용하다"
    finally:
        probe.write_text(original, encoding="utf-8")
