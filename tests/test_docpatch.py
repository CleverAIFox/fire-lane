#!/usr/bin/env python3
"""
test_docpatch.py — 문서 절 교체기가 **정말 멱등인가.** (DECISIONS §481)

── 왜 생겼나 ───────────────────────────────────────────────────
`tools/docpatch.py` 의 머리말이 제 존재 이유를 이렇게 적는다 —
「**멱등** 교체기. 같은 입력이면 두 번 돌려도 같다」. 그리고
「`docfix_20260817.py` 계열이 일회성이라 **아홉 번 다시 만들어진** 것과
`PLAN §7-5` 가 **두 벌이 된** 것(§18)이 이 도구의 존재 이유다」.

**그 주장을 아무도 민 적이 없었다.** 이 도구는 `부류 관문` 인데 그것을
미는 시험도, 자기검사도 없었다(§481 이 그 분모를 쟀다). 멱등이 아니면
이 도구가 막으려던 바로 그 사고(절이 두 벌)가 이 도구 손에서 난다.

IN    없음 (합성 문서로 민다)
OUT   없음 (검사)
PARAM 없음
밖    **문서 규약은 안 본다** — 제목 어휘 · 별표 밀도 따위는 `doc_fsck` ·
      `test_doc_style` 의 일이다. 여기가 드는 것은 **교체의 성질** 셋이다:
      멱등 · 자리 · 중복 탐지.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def dp():
    """경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering — 경로 조작 금지)."""
    spec = importlib.util.spec_from_file_location("docpatch", ROOT / "tools/docpatch.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


DOC = """# 제목

## 1. 처음

본문 하나.

## 2. 가운데

본문 둘.

## 3. 끝

본문 셋.
"""


def _doc(tmp_path: Path, text: str = DOC) -> Path:
    p = tmp_path / "D.md"
    p.write_text(text, encoding="utf-8")
    return p


def _frag(tmp_path: Path, text: str, name: str = "f.md") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# ── ① 멱등 — 이 도구의 존재 이유다 ─────────────────────────────
def test_replacing_twice_gives_the_same_file(dp, tmp_path):
    """★ **본체.** 같은 조각을 두 번 넣어도 파일이 같다."""
    doc = _doc(tmp_path)
    frag = _frag(tmp_path, "## 2. 가운데\n\n바뀐 본문.\n")
    first = dp.ensure_section(doc, "## 2.", frag, None)
    once = doc.read_text(encoding="utf-8")
    second = dp.ensure_section(doc, "## 2.", frag, None)
    twice = doc.read_text(encoding="utf-8")
    assert once == twice, (
        "두 번 돌리자 파일이 달라졌다 — **멱등이 아니다.**\n"
        "  이 도구가 막으려던 사고(절이 두 벌)가 이 도구 손에서 난다")
    assert "교체" in first and "변경 없음" in second, (
        f"두 번째가 「변경 없음」이 아니다 — {second!r}. 같은 입력인데 다시 쓴다")


def test_the_section_is_not_duplicated(dp, tmp_path):
    """★ 교체인가 **덧붙임**인가 — §18 의 `PLAN §7-5` 두 벌이 그 사고다."""
    doc = _doc(tmp_path)
    frag = _frag(tmp_path, "## 2. 가운데\n\n바뀐 본문.\n")
    dp.ensure_section(doc, "## 2.", frag, None)
    got = doc.read_text(encoding="utf-8")
    assert got.count("## 2.") == 1, f"절이 둘이 됐다\n{got}"
    assert "본문 둘" not in got, "옛 본문이 남았다 — 교체가 아니라 덧붙임이다"
    # 이웃 절은 안 건드린다
    assert "본문 하나" in got and "본문 셋" in got, "옆 절을 먹었다"


# ── ② 자리 — `--after` 가 가리키는 절 **뒤**다 ──────────────────
def test_a_new_section_lands_after_its_anchor(dp, tmp_path):
    doc = _doc(tmp_path)
    frag = _frag(tmp_path, "## 1-5. 새 절\n\n새 본문.\n")
    dp.ensure_section(doc, "## 1-5.", frag, "## 1.")
    lines = doc.read_text(encoding="utf-8").splitlines()
    i1 = next(k for k, x in enumerate(lines) if x.startswith("## 1."))
    i15 = next(k for k, x in enumerate(lines) if x.startswith("## 1-5."))
    i2 = next(k for k, x in enumerate(lines) if x.startswith("## 2."))
    assert i1 < i15 < i2, f"자리가 틀렸다 — 1 {i1} · 1-5 {i15} · 2 {i2}"


def test_a_missing_anchor_stops_instead_of_guessing(dp, tmp_path):
    """★ 앵커가 없으면 **멈춘다.** 짐작으로 끼우면 그 문서가 조용히 망가진다."""
    doc = _doc(tmp_path)
    before = doc.read_text(encoding="utf-8")
    frag = _frag(tmp_path, "## 9. 새 절\n\n새 본문.\n")
    with pytest.raises(SystemExit):
        dp.ensure_section(doc, "## 9.", frag, "## 없는절.")
    assert doc.read_text(encoding="utf-8") == before, "멈추면서 파일을 건드렸다"


def test_a_new_section_without_an_anchor_stops(dp, tmp_path):
    doc = _doc(tmp_path)
    frag = _frag(tmp_path, "## 9. 새 절\n\n새 본문.\n")
    with pytest.raises(SystemExit):
        dp.ensure_section(doc, "## 9.", frag, None)


def test_a_fragment_that_does_not_start_with_the_key_stops(dp, tmp_path):
    """조각의 첫 줄이 열쇠와 다르면 **엉뚱한 자리를 덮는다** — 멈춰야 한다."""
    doc = _doc(tmp_path)
    frag = _frag(tmp_path, "## 7. 다른 절\n\n본문.\n")
    with pytest.raises(SystemExit):
        dp.ensure_section(doc, "## 2.", frag, None)


# ── ③ 표 행 덧붙임 — 있는 행은 다시 안 넣는다 ──────────────────
TBL = """# 제목

## 1. 표

| ID | 값 |
|---|---|
| A | 1 |
| B | 2 |

### 1-1. 하위

| ID | 값 |
|---|---|
| Z | 9 |
"""


def test_existing_rows_are_not_appended_twice(dp, tmp_path):
    doc = _doc(tmp_path, TBL)
    frag = _frag(tmp_path, "| A | 1 |\n| C | 3 |\n")
    dp.append_rows(doc, "## 1.", frag)
    got = doc.read_text(encoding="utf-8")
    assert got.count("| A | 1 |") == 1, f"있는 행을 또 넣었다\n{got}"
    assert "| C | 3 |" in got, "새 행을 안 넣었다"
    again = dp.append_rows(doc, "## 1.", frag)
    assert "변경 없음" in again, f"두 번째가 「변경 없음」이 아니다 — {again!r}"


def test_rows_land_before_the_first_subsection(dp, tmp_path):
    """★ §18 의 그 사고 — 넣을 자리를 안 좁히면 하위절 표 끝에 붙는다."""
    doc = _doc(tmp_path, TBL)
    frag = _frag(tmp_path, "| C | 3 |\n")
    dp.append_rows(doc, "## 1.", frag)
    lines = doc.read_text(encoding="utf-8").splitlines()
    ic = next(k for k, x in enumerate(lines) if x.startswith("| C |"))
    isub = next(k for k, x in enumerate(lines) if x.startswith("### 1-1."))
    assert ic < isub, f"행이 하위절 뒤로 갔다 — C {ic} · 하위 {isub}"


# ── ④ 중복 제목 — **종료 수로** 운다 ───────────────────────────
def test_duplicate_headings_are_found(dp, tmp_path):
    """★ 양방향. 멀쩡한 문서는 조용하고 중복이 있으면 짚는다."""
    ok = _doc(tmp_path)
    assert "중복 없음" in dp.check(ok), "멀쩡한 문서에서 중복을 본다"
    dup = _doc(tmp_path, DOC + "\n## 2. 가운데\n\n또.\n")
    assert "중복 제목" in dp.check(dup), "중복 제목을 못 본다"


def test_the_check_cries_with_an_exit_code(dp, tmp_path):
    """★ 머리말이 적은 그 사고 — 「검사가 있는데 안 운다」(F-142).

    `check()` 는 글자를 돌려주므로 `print` 만 하면 **종료 수가 0** 이다.
    `check_many()` 가 그 자리이고, 여기가 그것을 든다.
    """
    dup = _doc(tmp_path, DOC + "\n## 2. 가운데\n\n또.\n")
    assert dp.check_many([dup]), (
        "중복을 찾고도 종료 수가 0 이다 — 게이트에 달아도 안 운다")
    # ★ 멀쩡한 쪽을 **음성으로** 민다 — 양쪽을 같은 자로 밀어야 그 자가
    #   「무엇에나 운다」가 아님을 보인다(`tools/canary.py` 가 드는 꼴이다).
    assert not dp.check_many([_doc(tmp_path)]), "멀쩡한 문서에서 운다"


# ── 종료코드가 **빨개질 수 있는가** (DECISIONS §541) ──────────────
# ★ 2026-10-20. `check_many` 는 1 을 내는데 `__main__` 이 `sys.exit` 없이
#   `main()` 을 불렀다. 종료코드가 늘 0 이라 verify 의 「문서 제목 무결」
#   축이 두 달 동안 영원히 초록이었다 — **관문이 빨개질 수 없으면 없는
#   것보다 나쁘다.** 덮고 있다고 주장하기 때문이다.
# ★ 이 파일에 이미 시험이 열 개 있었고 **전부 통과했다.** 그중 종료코드를
#   보는 자가 없었다. 안에서 `check_many` 를 부르면 오늘도 1 이 나온다 —
#   병은 함수가 아니라 **배선**에 있었다. 그래서 아래는 하위 프로세스다.
# ★ 실제 문서의 중복 수는 안 본다 — 그것은 배치마다 움직이고, 여기서 수를
#   박으면 문서를 고칠 때마다 이 시험이 낡는다. 합성 입력만 쓴다.
_DP_ROOT = Path(__file__).resolve().parents[1]
_DP_TOOL = _DP_ROOT / "tools" / "docpatch.py"
_DP_DUP = "# 머리\n\n## 1. 가\n\n본문\n\n## 1. 가\n\n본문\n"
_DP_OK = "# 머리\n\n## 1. 가\n\n## 2. 나\n"


def _dp_check(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_DP_TOOL), "check", *args],
        capture_output=True, text=True, cwd=_DP_ROOT, check=False, timeout=60)


def test_a_duplicate_title_turns_the_gate_red(tmp_path):
    """★ 이 시험이 2026-10-20 에 **빨강으로 먼저 섰다.** 그것이 근거다."""
    d = tmp_path / "dup.md"
    d.write_text(_DP_DUP, encoding="utf-8")
    r = _dp_check(str(d))
    assert r.returncode != 0, (
        f"중복 제목인데 종료코드가 0 이다\n{r.stdout}{r.stderr}")
    assert "중복" in r.stdout, f"무엇이 중복인지 말하지 않는다\n{r.stdout}"


def test_a_clean_document_stays_green(tmp_path):
    """반대쪽 — 늘 빨개지면 그것도 그물이 아니다."""
    d = tmp_path / "ok.md"
    d.write_text(_DP_OK, encoding="utf-8")
    r = _dp_check(str(d))
    assert r.returncode == 0, f"깨끗한 문서에서 운다\n{r.stdout}{r.stderr}"


def test_a_missing_document_turns_the_gate_red(tmp_path):
    """없는 경로를 조용히 넘기면 오타 하나로 관문이 빈다."""
    r = _dp_check(str(tmp_path / "없는것.md"))
    assert r.returncode != 0, f"없는 문서에서 조용하다\n{r.stdout}{r.stderr}"


def test_one_bad_document_among_many_turns_the_gate_red(tmp_path):
    """★ 여럿을 줄 때 **뒤의 초록이 앞의 빨강을 덮지 않는가.**"""
    bad, ok = tmp_path / "bad.md", tmp_path / "ok.md"
    bad.write_text(_DP_DUP, encoding="utf-8")
    ok.write_text(_DP_OK, encoding="utf-8")
    r = _dp_check(str(bad), str(ok))
    assert r.returncode != 0, f"빨간 문서가 뒤의 초록에 덮였다\n{r.stdout}"


def test_the_other_subcommands_still_exit_zero(tmp_path):
    """★ `return 0` 을 붙이면서 다른 가지를 깨지 않았는가."""
    doc = tmp_path / "d.md"
    doc.write_text("## 1. 가\n\n| 가 |\n|---|\n| x |\n", encoding="utf-8")
    frag = tmp_path / "f.md"
    frag.write_text("| y |\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(_DP_TOOL), "append-rows", str(doc),
         "## 1.", str(frag)],
        capture_output=True, text=True, cwd=_DP_ROOT, check=False, timeout=60)
    assert r.returncode == 0, f"append-rows 가 운다\n{r.stdout}{r.stderr}"
