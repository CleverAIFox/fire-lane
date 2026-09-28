"""도장이 **절이 주장하는 것만** 무는가.  (DECISIONS §297 · PLAN W13-10)

★ 왜 이 파일이 따로 있나 (2026-09-29). `docseal` 은 절 본문과 **지목 파일의
  바이트 전부**를 해시했다. `tools/verify.sh` 는 검사의 목록이라 배치마다 자라고,
  그래서 그 파일을 지목한 절 전부가 배치마다 죽었다. 실측 —

    COV_MIN=34 → 35  (한 글자)          →  27절의 도장이 무효
    같은 수정 + 단계 하나 추가 (고친 뒤) →  1절

  절들이 주장하는 것은 「이 관문이 이 도구를 부른다」이고, 단계가 늘어난 것이
  그 주장을 거짓으로 만들지 않는다. 배치마다 27절을 다시 찍으면 그것이
  도장 찍기다(§290-2) — 그리고 도장 찍기는 도장이 없는 것보다 나쁘다.

★ 여기 잠그는 것은 **양방향**이다.
    ① 그 절과 무관한 줄이 바뀌어도 지문이 안 움직인다   (거짓 빨간불을 없앤다)
    ② 지목한 도구를 관문에서 **떼면** 지문이 움직인다     (느슨해지지 않았다)
  ②가 없으면 이 고침은 검사를 끈 것과 같다.

IN    tools/docseal.py (`view` · `LIST_VIEW` · `FP_METHOD`)
OUT   없음
밖    어느 절이 어느 파일을 지목하는가(`refs`)는 여기서 판단하지 않는다.
      지문을 **어떤 관점으로** 내는가만 든다.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "docseal.py"


@pytest.fixture
def ds():
    """경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering — 경로 조작 금지)."""
    spec = importlib.util.spec_from_file_location("docseal_viewt", SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


VERIFY = b"""#!/usr/bin/env bash
COV_MIN=34
step "pytest" uv run pytest tests/ -q
step "\xeb\xa0\x88\xec\x9d\xb4\xed\x81\xac" uv run python tools/lakecheck.py
step "\xed\x8f\xad" uv run python tools/widthcross.py
"""


# ── ① 무관한 줄이 바뀌어도 안 움직인다 ─────────────────────────


def test_래칫_한_글자는_다른_절의_지문을_안_움직인다(ds):
    """★ 이것이 27절을 죽인 그 수정이다."""
    files = ["tools/verify.sh", "tools/lakecheck.py"]
    a = ds.view("tools/verify.sh", VERIFY, files)
    b = ds.view("tools/verify.sh", VERIFY.replace(b"COV_MIN=34", b"COV_MIN=35"), files)
    assert a == b, "래칫 한 글자에 지문이 움직인다 — 배치마다 그 절들을 다시 찍게 된다"


def test_단계를_하나_붙여도_안_움직인다(ds):
    files = ["tools/verify.sh", "tools/lakecheck.py"]
    grown = VERIFY + b'step "new gate" true\n'
    assert ds.view("tools/verify.sh", VERIFY, files) == \
           ds.view("tools/verify.sh", grown, files)


# ── ② 지목한 도구를 떼면 움직인다 ───────────────────────────────


def test_지목한_도구를_관문에서_떼면_지문이_움직인다(ds):
    """★ 이것이 없으면 위의 고침은 검사를 끈 것과 같다."""
    files = ["tools/verify.sh", "tools/lakecheck.py"]
    torn = VERIFY.replace(b"uv run python tools/lakecheck.py", b"true")
    assert ds.view("tools/verify.sh", VERIFY, files) != \
           ds.view("tools/verify.sh", torn, files)


def test_부르는_줄이_바뀌면_지문이_움직인다(ds):
    files = ["tools/verify.sh", "tools/lakecheck.py"]
    moved = VERIFY.replace(b"tools/lakecheck.py", b"tools/lakecheck.py --scan /tmp")
    assert ds.view("tools/verify.sh", VERIFY, files) != \
           ds.view("tools/verify.sh", moved, files)


def test_아예_안_부르면_빈_지문을_내지_않는다(ds):
    """빈 것을 해시하면 「안 부른다」가 조용히 통과한다(빈 그물)."""
    files = ["tools/verify.sh", "tools/없는도구.py"]
    got = ds.view("tools/verify.sh", VERIFY, files)
    assert got.strip(), "지목한 도구를 안 부르는데 빈 지문을 냈다"
    assert "안 부른다".encode() in got, "「안 부른다」는 사실이 지문에 안 박혔다"


# ── 관점의 경계 ────────────────────────────────────────────────


def test_목록_파일이_아니면_바이트_전부를_본다(ds):
    """관점은 **목록 파일에만** 준다. 넓히면 판정이 느슨해진다."""
    raw = b"TRUCK = 3.0\n"
    assert ds.view("src/firelane/seg/params.py", raw, ["src/firelane/seg/params.py"]) == raw


def test_verify_만_지목하는_절은_단계_목록을_본다(ds):
    """그 절의 주장이 「이런 단계가 있다」이므로 단계가 늘면 다시 봐야 한다."""
    files = ["tools/verify.sh"]
    a = ds.view("tools/verify.sh", VERIFY, files)
    assert b"pytest" in a
    assert b"COV_MIN" not in a, "단계 이름만 봐야 하는데 본문이 섞였다"
    grown = VERIFY + b'step "new gate" true\n'
    assert ds.view("tools/verify.sh", grown, files) != a


def test_관점_대장이_비면_통과가_아니다(ds):
    """`deadcheck ③` — 대장이 비면 이 관점이 죽은 칸이 된다."""
    assert ds.LIST_VIEW, "`LIST_VIEW` 가 비었다 — 관점이 아무 파일에도 안 걸린다"
    assert "tools/verify.sh" in ds.LIST_VIEW


def test_지문_공식에_판_이름이_있다(ds):
    """공식이 바뀌면 옛 도장은 전부 무효다.

    **어느 공식으로 찍힌 도장인지** 갈릴 수 있어야 일회성 이관을 증명할 수 있다.
    """
    assert getattr(ds, "FP_METHOD", ""), "`FP_METHOD` 가 없다 — 공식 변경을 못 갈랐다"


def test_parts_는_digest_와_같은_관점을_쓴다(ds):
    """다르면 「무효인데 어디가 움직였는지 아무 칸도 안 바뀌었다」가 나온다."""
    src = SRC.read_text(encoding="utf-8")
    i = src.index("def parts(")
    j = src.index("\ndef why(", i)
    body = src[i:j]
    assert "view(f," in body, "`parts` 가 관점을 안 쓴다 — 설명이 판정과 어긋난다"
