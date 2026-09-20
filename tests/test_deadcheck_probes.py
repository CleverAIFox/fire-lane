#!/usr/bin/env python3
"""
test_deadcheck_probes.py — **검사가 죽었는가를 검사하는 도구**가 죽었는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (DECISIONS §202 · PLAN §13 W10-1).

`tools/deadcheck.py` 는 「검사가 있는데 안 운다」를 잡으려고 만든 도구다.
그런데 **그 도구 자신이 정확히 그 병에 걸려 있었다.**

    verify.sh:628      step "검사가 죽었는가"  …  deadcheck.py --selftest
    contract.yml:256                            …  deadcheck.py --selftest

세 곳 전부 `--selftest` 였다. `--selftest` 가 묻는 것은 **「프로브가 한 건이라도
내는가」**뿐이다. 즉 **결함이 쌓일수록 더 확실히 초록**이 되는 관문이었다.
맨몸으로 돌리면 148건이 나왔고 아무도 그것을 읽지 않았다. 그 148건 안에
`golden.py:151 WATCH` 가 있었다 — 대장에 **W3-8 로 따로 등재해 사람이 다시
발견한** 결함이다. 도구는 진작에 찾아놨다.

★ 족은 W3-8 · W4-8 · W3-16 · W4-9 · W3-18① 과 같다 — **범위가 이름보다 좁고
  그것이 선언돼 있지 않은 것.** 이 인스턴스가 제일 위쪽이라 제일 나빴다.
  단계 이름은 「검사가 죽었는가」인데 실제로는 프로브의 생사만 봤다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 관문이 `--ratchet` 인가 (로컬 · CI 둘 다). `--selftest` 면 운다
    2. 래칫 천장이 프로브 전부를 덮는가
    3. ② 의 짝짓기가 **부분집합**인가 — 「이름이 본문에 나오는가」로 되돌아가면 운다
    4. 면제가 죽어 있지 않은가 (면제했는데 실은 안 걸리는 것)
    5. ② 의 `판정코드` 분모가 `golden.judgment_files()` 와 같은 정본인가
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify.sh"
CI = ROOT / ".github" / "workflows" / "contract.yml"


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(f"_{stem}", ROOT / "tools" / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


dc = _load("deadcheck")


# ── 1 · 관문 ────────────────────────────────────────────────────
@pytest.mark.parametrize("path", [VERIFY, CI], ids=["verify.sh", "contract.yml"])
def test_the_gate_is_the_ratchet_not_the_selftest(path):
    """`deadcheck` 을 관문으로 부르는 자리가 `--ratchet` 인가.

    ★ `--selftest` 를 관문으로 쓰면 **방향이 뒤집힌다** — 결함이 많을수록
      통과한다. 이것이 2026-09-20 까지의 실제 상태였다.
    """
    src = path.read_text(encoding="utf-8")
    calls = re.findall(r"deadcheck\.py\s+(--\w+)", src)
    assert calls, f"{path.name} 이 deadcheck 을 안 부른다 — 관문이 사라졌다"
    assert "--selftest" not in calls, (
        f"{path.name} 이 `deadcheck.py --selftest` 를 관문으로 쓴다.\n"
        "  그것은 「프로브가 살아 있는가」지 「저장소가 깨끗한가」가 아니다.\n"
        "  결함이 쌓일수록 더 확실히 통과한다 — 관문은 `--ratchet` 이다.")
    assert "--ratchet" in calls, f"{path.name} 에 `--ratchet` 호출이 없다"


def test_ratchet_covers_every_probe():
    """천장이 프로브 전부를 덮는가. 프로브를 늘리고 천장을 안 적으면 그것이 무음 통과다."""
    names = {n for n, _ in dc.PROBES}
    assert set(dc.CEILING) == names, (
        f"래칫과 프로브가 갈렸다 — 천장에만 {sorted(set(dc.CEILING) - names)} · "
        f"프로브에만 {sorted(names - set(dc.CEILING))}")


def test_handlist_ceiling_is_zero():
    """② 는 래칫이 아니라 **0** 이다.

    ★ ①③⑤ 는 아직 한 건씩 본 적이 없어 래칫으로 둔다(「이만큼이 미분류다」).
      ② 는 2026-09-20 에 59건 → 0건으로 전수 분류를 마쳤다. 분류가 끝난
      프로브를 래칫으로 두면 **다시 들어와도 천장 안이라 안 운다.**
    """
    assert dc.CEILING["② 손목록"] == 0, (
        "② 의 천장이 0 이 아니다. 전수 분류가 끝난 프로브는 0 으로 내려온다 — "
        "래칫에 남겨두면 새 손목록이 천장 안으로 조용히 들어온다.")


# ── 3 · 짝짓기 규칙 ─────────────────────────────────────────────
def test_pairing_is_membership_not_word_occurrence():
    """②의 짝짓기가 **부분집합**인가.

    ★ 종전 판별은 `key in src(p).lower()` 였다 — 원본 이름이 파일 아무 데나
      나오면 짝지었다. `tools/` 밑 파일은 머리말에 자기 경로를 적으므로
      **`"tools"` 가 항상 참**이고 분모가 64 로 고정됐다.
      그래서 `DOCS 가 4개 리터럴인데 tools 는 64종이다` 같은, 비교가
      성립하지 않는 짝짓기가 59건 쌓였다. 신호가 59분의 1이면 아무도 안 읽는다.
    """
    src = (ROOT / "tools" / "deadcheck.py").read_text(encoding="utf-8")
    body = src[src.index("def probe_handlist"):src.index("# ── ③")]
    assert "in src(p).lower()" not in body, (
        "② 가 「원본 이름이 본문에 나오는가」로 되돌아갔다.\n"
        "  그 판별은 분모를 의미 없게 만든다 — 리터럴 전부가 원본의 원소일 때만 짝지어라.")
    assert "all(i in elems for i in items)" in body, (
        "② 의 부분집합 판별이 사라졌다")


def test_docs_constant_is_no_longer_a_false_pair():
    """옛 판별의 대표 오검이 실제로 안 나오는가 — 역방향 대조.

    `dms.py` 의 `DOCS` 는 문서 넷이다. `tools/*.py` 64종과 비교할 이유가
    없는데 옛 판별은 비교했다. 지금 판별로는 어느 원본의 부분집합도 아니다.
    """
    dc.HITS.clear()
    dc.probe_handlist()
    bad = [h for h in dc.HITS if h["file"].endswith("dms.py") and "DOCS" in h["what"]]
    assert not bad, f"DOCS 가 여전히 짝지어진다 — {bad}"


# ── 4 · 면제 ────────────────────────────────────────────────────
def test_exemptions_are_not_dead():
    """면제했는데 **실은 안 걸리는 것**이 있는가.

    ★ 2026-09-20 에 `tests/test_tools_are_wired.py` 에서 같은 일을 겪었다 —
      면제 31개 중 12개가 이미 죽어 있었다. 죽은 면제는 「이건 봐줬다」는
      거짓 기록이고, 그 목록을 믿고 다음 사람이 안 본다.
    """
    dc.HITS.clear()
    live = dict(dc.EXEMPT_HANDLIST)
    dc.EXEMPT_HANDLIST.clear()
    try:
        dc.probe_handlist()
        would = {re.match(r"(\S+) 가 ", h["what"]).group(1)
                 for h in dc.HITS if re.match(r"(\S+) 가 ", h["what"])}
    finally:
        dc.EXEMPT_HANDLIST.update(live)
    dead = sorted(set(live) - would)
    assert not dead, (
        f"면제가 죽었다 — {dead} 는 면제를 빼도 ② 에 안 걸린다.\n"
        "  지워라. 죽은 면제는 「봐줬다」는 거짓 기록이고 다음 사람이 그것을 믿는다.")


def test_every_exemption_states_a_reason():
    """면제마다 사유가 있는가. 사유 없는 면제는 그냥 구멍이다."""
    for name, why in dc.EXEMPT_HANDLIST.items():
        assert why and len(why) > 15, f"`{name}` 면제에 사유가 없다"


# ── 5 · 정본 ────────────────────────────────────────────────────
def test_judgment_source_has_one_home():
    """②의 `판정코드` 분모와 `golden.judgment_files()` 가 같은 곳에서 오는가.

    ★ 둘이 갈리면 지도와 검사가 다른 것을 말하는 그 형태가 된다. 합칠 수
      있으므로 합친다 — 둘 다 `firelane.shardseal.code_closure` 하나를 부른다.
    """
    golden = _load("golden")
    mine = set(dc._members()["판정코드"][0])
    theirs = {x for r in golden.judgment_files() if r != "uv.lock"
              for x in (r, Path(r).name, Path(r).stem)}
    assert mine == theirs, (
        "② 의 판정코드 분모와 golden 의 판정 범위가 다르다 —\n"
        f"  ② 에만 {sorted(mine - theirs)[:5]} · golden 에만 {sorted(theirs - mine)[:5]}\n"
        "  둘 다 `firelane.shardseal.code_closure('firelane.segments')` 를 불러라.")
