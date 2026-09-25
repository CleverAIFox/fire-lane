"""봉인 무효화가 **실제 영향만큼만 넓은가.**

★ 2026-09-25 (DECISIONS §255). 종전에는 `SEAL.json` 의 `tool` 지문 **하나**가
  봉인 전체를 무효화했다. `_tool_print()` 가 `dms.py` 가 부르는 도구 다섯
  (`dms` · `dupcheck` · `deadcheck` · `env_check` · `verify.sh`)을 한 해시로
  합쳤기 때문이다. 그래서 —

      `dupcheck.py` 한 줄 수정  →  절 1,036개가 통째로 재검사 대상

  `dupcheck` 는 **코드 사본을 세는 도구**이고 절 내용과 아무 상관이 없다.
  실제로 이 배치가 `verify.sh` 에 단계 하나를 더한 순간 봉인 전체가 무효가 됐다.

★ **그 구조가 「감사할 일을 만든다».** 전수 재검사는 비싸고, 사람이 그것을
  회피하기 시작하면 봉인은 장식이 된다. §243 이 「선언이 검사보다 넓으면 거짓
  초록이 된다」를 적었고 이것은 그 거울상이다 — **무효화가 영향보다 넓으면
  재검사가 습관적으로 건너뛰어진다.**

★ 이 파일이 지키는 것은 둘이다. ① 축별 무효가 **실제로 좁게** 나오는가
  ② 새 축이 생겼는데 `AXIS_TOOLS` 에 없으면 우는가 — **손목록이 실물보다
  좁아지는 것**이 이 저장소가 반복해 겪은 형태다(W3-8 족).

IN    tools/dms.py (읽기) · data/dms/SEAL.json (있으면)
OUT   없음
PARAM 없음
밖    어느 도구가 어느 축을 **정말** 정하는지는 사람이 판단한다. 이 검사는
      그 선언이 **실물 축을 다 덮는가**와 **판정이 선언대로 도는가**만 본다.
      선언 자체가 틀렸으면(예: `sections` 가 `dupcheck` 에도 의존한다면)
      여기서는 안 잡힌다 — 그것은 `seal` 재실행이 잡는다.
"""
from __future__ import annotations

import json
from pathlib import Path

import dms
import pytest

ROOT = Path(__file__).resolve().parent.parent
SEAL = ROOT / "data/dms/SEAL.json"


def _fake_old(**over) -> dict:
    """지금 도구 지문을 그대로 담은 **가짜 옛 봉인.** 한 도구만 흔들어 쓴다."""
    base = {"tools": dict(dms._tool_prints()), "tool": dms._tool_print()}
    tools = base["tools"]
    for name, val in over.items():
        key = f"tools/{name}"
        assert key in tools, f"{key} 가 도구 범위에 없다 — 범위가 바뀌었다"
        tools[key] = val
    return base


# ── 선언이 실물을 덮는가 ────────────────────────────────────────
def test_every_sealed_axis_is_declared():
    """**실물 봉인의 축이 전부 선언돼 있는가.** 빠진 축은 아무도 안 본다."""
    if not SEAL.exists():
        pytest.skip("환경skip(산출물) — 봉인이 아직 없다. `dms.py seal` 이 찍는다")
    keys = set(json.loads(SEAL.read_text(encoding="utf-8")))
    missing = sorted(keys - set(dms.AXIS_TOOLS) - set(dms.SEAL_META))
    assert not missing, (
        f"봉인에 있는데 `AXIS_TOOLS` 에 없는 축: {missing}\n"
        "  선언 밖의 축은 **무효 판정을 안 받는다** — 도구가 바뀌어도 유효한\n"
        "  것처럼 남는다. 축을 더하고 어느 도구가 그것을 정하는지 적어라.\n"
        "  봉인 자신의 기록이면 `SEAL_META` 에 넣어라.")


def test_no_declared_axis_is_a_ghost():
    """반대 방향 — 선언에만 있고 봉인에 없는 축. 있으면 선언이 낡았다."""
    if not SEAL.exists():
        pytest.skip("환경skip(산출물) — 봉인이 아직 없다")
    keys = set(json.loads(SEAL.read_text(encoding="utf-8")))
    ghost = sorted(set(dms.AXIS_TOOLS) - keys)
    assert not ghost, (
        f"`AXIS_TOOLS` 에만 있고 봉인에 없는 축: {ghost}\n"
        "  유령 선언은 「있다고 적혀 있으면 사람이 안 본다」의 형태다(§243).")


def test_the_declared_tools_exist():
    """선언이 가리키는 도구가 실물인가. 없는 파일을 가리키면 **영영 안 바뀐다.**"""
    scope = {p.relative_to(ROOT).as_posix() for p in dms._tool_scope()}
    bad = []
    for axis, tools in dms.AXIS_TOOLS.items():
        for t in tools:
            if not (ROOT / t).is_file():
                bad.append(f"{axis} → {t} (파일이 없다)")
            elif t not in scope:
                bad.append(f"{axis} → {t} (`dms` 도구 범위 밖 — 지문이 안 잡힌다)")
    assert not bad, (
        "선언이 잡히지 않는 도구를 가리킨다:\n  " + "\n  ".join(bad) + "\n"
        f"  범위: {sorted(scope)}\n"
        "  범위는 `dms.py` 본문의 `tools/…` 리터럴에서 나온다(`_tool_scope`).")


# ── 무효가 좁게 나오는가 ────────────────────────────────────────
def test_nothing_is_stale_when_no_tool_moved():
    """아무 도구도 안 바뀌면 **전 축이 살아 있다.** 이게 안 되면 봉인이 무의미하다."""
    assert dms.stale_axes(_fake_old()) == {}, (
        "도구가 그대로인데 무효인 축이 있다 — 지문 계산이 결정적이지 않다.")


def test_a_counting_tool_does_not_invalidate_the_sections():
    """**`dupcheck` 를 고쳐도 절 1,036개는 살아 있다.** 이것이 §255 의 전부다."""
    stale = dms.stale_axes(_fake_old(**{"dupcheck.py": "0" * 16}))
    assert set(stale) == {"dup_groups"}, (
        f"`dupcheck.py` 하나를 고쳤는데 무효 축이 {sorted(stale)} 다.\n"
        "  `dupcheck` 는 코드 사본을 세는 도구다 — 절 내용과 무관하다.\n"
        "  종전에는 이 한 줄이 봉인 **전체**를 무효화했다.")
    assert "sections" not in stale, "절 축이 사본 세기에 딸려 무효가 됐다"
    assert "denominator" not in stale and "dead_refs" not in stale


def test_the_parser_tool_does_invalidate_the_sections():
    """반대로 **`dms.py` 가 바뀌면 절 축은 무효다.** 좁히기만 하면 안 된다."""
    stale = dms.stale_axes(_fake_old(**{"dms.py": "0" * 16}))
    for axis in ("sections", "denominator", "dead_refs"):
        assert axis in stale, (
            f"`dms.py` 가 바뀌었는데 `{axis}` 가 유효하다고 나온다.\n"
            "  절 해시·상태·물림은 이 도구의 파싱·분류 규칙이 정한다 —\n"
            "  규칙이 바뀌면 옛 통과는 증표가 아니다.")
    assert "dup_groups" not in stale, "사본군까지 딸려 무효가 됐다 — 여전히 너무 넓다"


def test_the_gate_tools_invalidate_only_the_enforcer_record():
    """관문 도구가 바뀌면 **강제자 기록만** 무효다."""
    for name in ("verify.sh", "deadcheck.py", "env_check.py"):
        stale = dms.stale_axes(_fake_old(**{name: "0" * 16}))
        assert set(stale) == {"enforcers"}, (
            f"`{name}` 하나를 고쳤는데 무효 축이 {sorted(stale)} 다.\n"
            "  이 배치가 실제로 `verify.sh` 에 단계를 더했고, 종전 구조에서는\n"
            "  그 한 줄에 봉인 전체가 무효가 됐다.")


def test_the_tool_free_axes_survive_every_tool_change():
    """**도구와 무관한 축**은 도구가 전부 바뀌어도 살아 있다.

    `docs` · `raw` · `code` 는 순수 파일·입력 해시다. 도구를 고쳐도 그 파일의
    내용이 달라지지 않는다 — 무효로 보는 것은 근거 없는 재검사다.
    """
    dead = {f"{p.name}": "0" * 16 for p in dms._tool_scope()}
    stale = dms.stale_axes(_fake_old(**dead))
    for axis in ("docs", "raw", "code", "declared_red"):
        assert axis not in stale, (
            f"도구를 다 바꿨는데 `{axis}` 가 무효로 나온다 — 그 축은 도구를 안 쓴다.")


def test_an_old_seal_is_treated_as_fully_stale():
    """`tools` 칸이 없는 옛 봉인은 **전 축 무효**다. 모를 때 유효하다 하지 않는다."""
    stale = dms.stale_axes({"tool": "abc"})
    assert set(stale) == set(dms.AXIS_TOOLS), (
        "옛 봉인인데 일부 축을 유효하다고 본다 — 축별 판정의 재료가 없는데\n"
        "  유효하다고 말하는 것은 검사를 끄는 것과 같다.")
    assert dms.stale_axes({}) , "봉인이 비어도 전 축 무효여야 한다"


def test_the_probe_itself_is_alive():
    """카나리아 — 판별식이 죽으면 위 전부가 **조용히 초록**이다."""
    assert dms.stale_axes(_fake_old()) == {}, "기준선이 안 맞는다"
    got = dms.stale_axes(_fake_old(**{"dupcheck.py": "x"}))
    assert got, "도구를 흔들었는데 아무것도 안 잡힌다 — 판별식이 죽었다"
    assert len(dms._tool_prints()) >= 4, (
        f"도구 지문이 {len(dms._tool_prints())}개뿐이다 — 범위가 줄었다")
    assert set(dms._tool_prints()) == {
        p.relative_to(ROOT).as_posix() for p in dms._tool_scope()}, "범위와 지문이 어긋난다"
