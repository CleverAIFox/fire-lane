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
    6. **양성 대조** — 프로브마다 합성 트리가 있는가 · 거기서 우는가 ·
       그리고 **대조 자신이 빈 그물이 아닌가**(프로브를 죽이면 집어내는가)

★ 2026-09-21 추가(DECISIONS §208). 5 까지는 「프로브가 옳게 세는가」를 물었다.
  6 은 **「살아 있는가를 어디서 묻는가」**를 든다 — 그것을 실제 저장소의
  0건으로 물으면, 프로브가 제 일을 다 해 0건이 되는 날 관문이 빨개진다.
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


# ── 6 · 양성 대조 ───────────────────────────────────────────────
# 2026-09-21 (DECISIONS §208). 「프로브가 살아 있는가」를 **실제 저장소의
# 0건**으로 답하던 것을 **합성 트리**로 옮겼다. 왜냐면 ② 를 전수 분류해
# 59건 → 0건으로 만든 바로 그날, `dms.py` 의 봉인 강제자가 이렇게 울었다 ——
#
#     ✗ probe/deadcheck   ★ selftest 실패 — 아무것도 못 낸 프로브: ['② 손목록']
#
# **프로브가 제 일을 다 했기 때문에 봉인이 안 찍혔다.** DECISIONS §73 이
# ④ 에 대해 적어둔 문장이 그대로 재현됐다 — 「검사가 자기 성공을 실패로
# 읽으면 사람이 검사를 끈다」. 그때 고친 방식이 `not k.startswith('④')`
# 라는 한 글자 면제였고, ①③⑤ 도 분류를 마치면 차례로 같은 일이 난다.
def test_every_probe_has_a_positive_control():
    """프로브마다 대조가 있는가. **대조 없는 프로브의 0건은 읽을 수 없다.**"""
    names = {n for n, _ in dc.PROBES}
    assert set(dc.CONTROLS) == names, (
        f"프로브와 양성 대조가 갈렸다 — 대조에만 {sorted(set(dc.CONTROLS) - names)} · "
        f"프로브에만 {sorted(names - set(dc.CONTROLS))}\n"
        "  프로브를 늘렸으면 **일부러 결함을 심은 합성 트리**도 같이 짓는다.")


def test_the_positive_control_is_green():
    """지금 다섯이 전부 제 합성 트리에서 우는가."""
    dead = dc.positive_control()
    assert not dead, "양성 대조 실패 —\n  " + "\n  ".join(dead)


@pytest.mark.parametrize("target", [n for n, _ in dc.PROBES])
def test_the_control_catches_a_dead_probe(target):
    """**대조 자신이 빈 그물이 아닌가.**

    ★ 프로브를 하나씩 무력화하고, 대조가 **그 이름을 집어내는지** 본다.
      이것이 없으면 「대조 통과」는 아무 뜻이 없다 — 이 저장소가 반복해
      당한 형태가 바로 「검사가 있는데 안 운다」이고, 대조도 검사다.
    """
    def neutered(root=None):
        return None

    live = list(dc.PROBES)
    dc.PROBES[:] = [(n, neutered if n == target else f) for n, f in live]
    try:
        dead = dc.positive_control()
    finally:
        dc.PROBES[:] = live
    assert any(d.startswith(target) for d in dead), (
        f"`{target}` 를 죽였는데 양성 대조가 조용하다 — 대조가 빈 그물이다.\n"
        f"  대조가 낸 것: {dead}")


def test_selftest_does_not_read_the_real_tree_any_more():
    """`--selftest` 가 **실제 트리의 건수**를 다시 보게 되면 운다.

    ★ 이것이 정확히 2026-09-21 에 봉인을 막은 코드다 ——
          dead = [k for k, v in per.items() if v == 0 and not k.startswith('④')]
      실제 트리의 0건을 프로브의 죽음으로 읽는다. 되돌아오면 **분류를
      끝낼수록 관문이 더 막힌다.** 생사의 근거는 `positive_control()` 하나다.
    """
    import ast
    tree = ast.parse((ROOT / "tools" / "deadcheck.py").read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    assert fn is not None, "`deadcheck.py` 에 `main()` 이 없다 — 이 검사가 빈 그물이 됐다"
    branches = [n for n in ast.walk(fn)
                if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
                and n.test.id == "selftest"]
    assert branches, (
        "`main()` 에 `if selftest:` 가지가 없다 — `--selftest` 가 사라졌거나\n"
        "  모양이 바뀌었다. 이 검사도 같이 옮겨라.")
    for br in branches:
        used = {n.id for n in ast.walk(br) if isinstance(n, ast.Name)}
        assert "per" not in used, (
            "`--selftest` 가 다시 `per`(실제 트리의 프로브별 건수)를 읽는다.\n"
            "  그러면 프로브가 제 일을 다 해 0건이 되는 날 관문이 빨개진다 —\n"
            "  2026-09-21 에 그것이 봉인을 막았다(DECISIONS §208).\n"
            "  생사는 `positive_control()` 이 합성 트리에서 답한다.")


def test_dms_still_asks_liveness_not_the_ratchet():
    """`dms.py` 의 `PROBES` 는 **`--selftest`** 로 남는가.

    ★ 같은 인자가 한 자리에서는 옳고 다른 자리에서는 틀리다. `verify.sh` 와
      `contract.yml` 에서 `--selftest` 는 **방향이 뒤집힌 관문**이라 틀렸다
      (위 검사 1). 그러나 `dms.py` 가 묻는 것은 「프로브가 살아 있나」이고
      `env_check`·`dupcheck` 셀프테스트와 한 줄로 묶여 있다 — 거기서는 옳다.
      무엇을 묻는 자리인지가 인자를 정한다. 그래서 이 비대칭을 **못으로 박는다.**
    """
    src = (ROOT / "tools" / "dms.py").read_text(encoding="utf-8")
    m = re.search(r'PROBES\s*=\s*\[(.*?)\]\s*\n', src, re.S)
    assert m, "`dms.py` 에 `PROBES` 가 없다 — 이 검사가 빈 그물이 됐다"
    blk = m.group(1)
    assert "deadcheck.py" in blk, "`dms.py` 의 `PROBES` 가 deadcheck 를 안 부른다"
    line = next(ln for ln in blk.splitlines() if "deadcheck.py" in ln)
    assert "--selftest" in line, (
        "`dms.py` 의 `PROBES` 가 `--selftest` 가 아니다.\n"
        "  거기는 **생사를 묻는 자리**다. 래칫을 부르면 봉인이 저장소 청결도에\n"
        "  묶이고, 그러면 미분류 41건 때문에 영영 못 찍는다.")
