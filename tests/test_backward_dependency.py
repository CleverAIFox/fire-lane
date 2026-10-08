#!/usr/bin/env python3
"""
test_backward_dependency.py — **후진 의존. 목록 · 실물 · 산문 세 면을 맞춘다.**

뒤 단계가 만드는 것을 앞 단계가 읽으면 첫 실행에서 죽거나, 더 나쁘게는
**지난 실행의 산출물을 읽어 조용히 돈다.** 2026-08-17 의 무효 산출 1093 이
그것이었다.

── 세 면 ──────────────────────────────────────────────────────
    목록 → 실물   `BACKWARD` 가 든 것이 아직 후진인가
    실물 → 목록   후진인데 목록에 없는 것이 있나
    산문 → 목록   「후진 의존이다」라고 **적은** 단계를 목록이 드는가

★ 두 면만 보면 **셋째가 갈린다.** 2026-09-04 에 ortho 의 후진 의존을 고치고
  `BACKWARD` 줄을 지웠는데, 같은 사실을 적은 산문 둘(`ortho.py` 머리말 ·
  `STEPS` 의 ortho 주석)은 그대로 남았다 — 그리고 둘 다 들지도 않는 강제자를
  증인으로 세웠다(DECISIONS §435).

── 왜 제 파일인가 ─────────────────────────────────────────────
★ 2026-10-08 (DECISIONS §435). 셋이 `test_guards.py` 에 있었다. 그 파일은
  「파이프라인이 스스로에게 거짓말하지 못하게」 하는 장치를 지키는 2,700줄짜리
  묶음이고, 거기 네 번째를 더하면 길이 예외가 또 올라간다 — **예외는 늘
  자리가 아니다.** 물음 하나(후진 의존)에 선언 하나(`BACKWARD`)라 가르는
  자리가 분명하다.

IN    src/firelane/pipeline.py (STEPS · 주석) · src/firelane/*.py (머리말)
OUT   없음 (검사)
PARAM `BACKWARD` — 알려진 후진 의존. **사유와 해소 조건을 함께 적는다**
밖    선언이 실물을 덮는가는 `test_declaration_reality.py` 가 든다.
      단계 순서 · writes 충돌은 `test_guards.py` 가 든다.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _steps():
    spec = importlib.util.spec_from_file_location(
        "pipeline", ROOT / "src/firelane/pipeline.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["pipeline"] = m          # @dataclass 가 cls.__module__ 로 되짚는다
    spec.loader.exec_module(m)
    return m


# ★ 2026-09-03. 알려진 후진 의존. **사유와 해소 조건을 함께 적는다.**
#
#   선언을 실물에 맞추자 둘이 드러났다. 종전에는 `reads` 가 비어 있어
#   이 검사가 볼 것이 없었고, 그래서 **잡으라고 만든 버그를 그대로 두고
#   초록불이었다.** 여기 적는 것은 면제가 아니라 **등록**이다 —
#   숨어 있던 것을 이름 붙여 꺼내 놓고 처리를 PLAN 이 든다.
#
#   ★ 지금 안 죽는 이유는 `web/data` 가 커밋돼 있어 파일이 늘 존재하기
#     때문이다. 위험은 죽는 것이 아니라 **한 실행 늦게 따라오는 것**이다.
BACKWARD = {
    # ★ 2026-09-04 해소. ("ortho","scope.geojson") 이 여기 있었다.
    #   scope 계산을 `segments._write_scope()` 로 올려 순방향이 됐고,
    #   `test_backward_entries_are_still_real` 이 "후진 의존이 아닌 것을
    #   든다" 로 울어 이 줄을 지우기를 요구했다 — 설계대로다.
    ("terrain", "view.json"):
        "publish 산출에 구운 범위를 덧쓴다. `if vj.exists()` 가 첫 실행을 "
        "넘긴다. 해소 = 타일 범위를 processed 로 내고 publish 가 합친다(PLAN)",
}
# ★ ("ortho","view.json") 은 여기 없다. 처음에 적었다가
#   test_backward_entries_are_still_real 이 **바로 잡았다** — terrain 이
#   앞에서 mutates 로 선언하므로 ortho 시점에는 이미 만들어진 것이다.
#   역방향 검사가 없었으면 근거 없는 면제 한 줄이 영구히 남았을 자리다.


def test_every_read_is_produced_by_an_earlier_step():
    """
    ★ 읽는 것은 앞 단계가 만든 것이거나 raw 여야 한다.

    뒤 단계가 만드는 것을 앞 단계가 읽으면 첫 실행에서 죽거나, 더 나쁘게는
    지난 실행의 산출물을 읽어 조용히 돈다. 2026-08-17 의 1093 이 그것이었다.
    """
    m = _steps()
    made = [m.RAW, *m.REPO_INPUTS]
    for s in m.STEPS:
        for r in s.consumes:
            if (s.name, r.name) in BACKWARD:
                continue
            assert any(m.matches(r, d) for d in made), (
                f"{s.name} 이 {r.name} 을 읽는데 앞 단계가 만들지 않는다.\n"
                "  선언이 틀렸거나 STEPS 순서가 틀렸다.\n"
                "  알려진 후진 의존이면 BACKWARD 에 **사유와 해소 조건**을 적어라.")
        made += list(s.produces)


def test_repo_inputs_are_tracked_and_actually_read():
    """`REPO_INPUTS` 는 **양방향**이다 — 실물이 있고, 누군가 읽어야 한다.

    ★ 2026-10-06 (§420-4). 이 목록은 「앞 단계가 안 만든다」를 면제한다. 면제는
      반드시 역방향 검사를 끼고 산다(§69) — 아니면 안 읽는 파일 한 줄이 영구히
      남아 **다음에 진짜 구멍이 생겼을 때 같은 이름으로 조용히 면제된다.**
      `BACKWARD` 가 `test_backward_entries_are_still_real` 을 끼고 사는 것과 같다.
    """
    import subprocess
    m = _steps()
    assert m.REPO_INPUTS, "REPO_INPUTS 가 비었다 — 빈 목록이면 이 검사가 아무것도 안 든다"
    read = {r for s in m.STEPS for r in s.consumes}
    for q in m.REPO_INPUTS:
        assert q.is_file(), f"{q} 가 없다 — REPO_INPUTS 는 실물을 든다"
        rel = q.relative_to(m.ROOT).as_posix()
        r = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                           cwd=m.ROOT, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (
            f"{rel} 이 git 추적 파일이 아니다 — 생성물이면 그것을 내는 단계를 "
            "선언해야 하고 REPO_INPUTS 가 아니다")
        assert any(m.matches(x, q) for x in read), (
            f"{rel} 을 어느 단계도 안 읽는다 — 목록이 낡았다. 그 줄을 지워라")


def test_backward_entries_are_still_real():
    """BACKWARD 가 이미 해소된 것을 들면 목록이 낡은 것이다. **양방향이다.**

    ★ 해제만 검사하면 항상 통과하는 검사가 된다(DECISIONS §69).
      후진 의존을 고쳐 놓고 이 줄을 안 지우면, 다음에 진짜 후진 의존이
      같은 이름으로 생겼을 때 조용히 면제된다.
    """
    m = _steps()
    made = [m.RAW]
    pos = {}
    for s in m.STEPS:
        for r in s.consumes:
            pos[(s.name, r.name)] = any(m.matches(r, d) for d in made)
        made += list(s.produces)
    stale = sorted(k for k in BACKWARD if pos.get(k) is not False)
    assert not stale, (
        f"BACKWARD 가 후진 의존이 아닌 것을 든다 — {stale}\n"
        "  해소됐으면 그 줄을 지워라.")

# ★ 2026-10-08 (DECISIONS §435). **셋째 면이다 — 산문 → 목록.**
#   「후진 의존이다」라고 산문이 적을 수 있는 자리는 둘이다 — 단계 모듈의
#   머리말과 `STEPS` 의 주석. 그 둘을 아무도 안 봤다.
#
#   위 `test_backward_entries_are_still_real` 은 **목록 → 실물**만 묻는다.
#   그래서 2026-09-04 에 ortho 를 고치고 줄을 지웠을 때 산문 둘이 남았고,
#   둘 다 「`test_guards.py::BACKWARD` 와 PLAN 이 든다」고 적었다 —
#   **들지 않는 자를 둘 다 가리켰다.** 죽은 참조보다 조용히 틀린 참조가
#   나쁘다(§205)는 축이고 여기서는 더 나쁘다: 산문이 세운 증인이
#   그 주장이 거짓임을 증명하는 자였다.
#
#   ★ 따라오는 규율 하나 — **산문은 지운 주장을 되뇌지 않는다.** 이 가드를
#     짜고 두 자리를 고치면서 정정문에 옛 문구를 그대로 인용했더니 가드가
#     **제 정정문을 주장으로 셌다.** 「가드가 제 설명문을 센다」의 **여섯 번째**
#     이고(§398-3 · §425-6 · §430-4 · §431-4 · §433), 처음으로 같은 판 안에서
#     저자를 잡았다. 그물을 넓히지 않고 규율을 세운다 — 이력의 정본은
#     DECISIONS 하나다. 산문은 절을 가리키고 문구는 거기 산다. 그러면
#     「정본이 둘」(족 2)이 주석에서 다시 자라지 않는다.
_BACK_CLAIM = re.compile(r"후진 의존(?!.{0,14}아니)")


def _step_prose() -> dict[str, str]:
    """단계마다 **산문 두 조각**을 모은다 — 모듈 머리말 + `STEPS` 주석 블록.

    주석 블록은 `Step(` 호출 바로 위의 이어진 `#` 줄들이다. 사람이 그 자리에
    적고, 그래서 그 자리가 거짓말할 수 있는 자리다.
    """
    src = (ROOT / "src/firelane/pipeline.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    out: dict[str, str] = {}
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "Step"):
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant)):
            continue
        name = node.args[0].value
        i = node.lineno - 2                     # 0-기반 · 호출 바로 윗줄
        block = []
        while i >= 0 and lines[i].lstrip().startswith("#"):
            block.append(lines[i])
            i -= 1
        mod = node.args[1].value if len(node.args) > 1 and isinstance(
            node.args[1], ast.Constant) else name
        head = ROOT / "src/firelane" / f"{mod}.py"
        doc = ""
        if head.is_file():
            doc = ast.get_docstring(ast.parse(head.read_text(encoding="utf-8"))) or ""
        out[name] = "\n".join(reversed(block)) + "\n" + doc
    return out


def test_prose_may_not_claim_a_backward_dependency_the_list_does_not_hold():
    """★ 산문이 후진 의존을 주장하면 목록이 들어야 한다. **양방향이다.**

    `BACKWARD` 가 든 단계는 산문이 사유를 적어야 한다 — 목록만 아는 면제는
    사각지대다(§259-2). 한쪽만 보면 둘이 갈리고, **갈린 쪽이 사람이 읽는 쪽**이다.
    """
    prose = _step_prose()
    assert prose, "STEPS 에서 단계를 하나도 못 읽었다 — 그물이 비었다"
    held = {k[0] for k in BACKWARD}

    claims = {n for n, t in prose.items() if _BACK_CLAIM.search(t)}
    assert not (claims - held), (
        f"산문이 후진 의존을 주장하는데 BACKWARD 가 안 든다 — {sorted(claims - held)}\n"
        "  고쳐서 순방향이 됐으면 **산문도 같이 고쳐라.** 아직 후진이면\n"
        "  BACKWARD 에 사유와 해소 조건을 적어라.\n"
        "  ★ 지운 주장을 정정문에 **인용하지 마라** — 되뇌면 되살아난 주장으로 읽힌다.\n"
        "    이력의 정본은 DECISIONS 다. 산문은 절을 가리켜라.")
    assert not (held - claims), (
        f"BACKWARD 가 드는데 산문이 아무 말도 안 한다 — {sorted(held - claims)}\n"
        "  머리말이나 STEPS 주석에 왜 후진인지 적어라 — 목록만 아는 면제는 사각지대다.")

    # ★ **빈 그물을 막는다.** 부정형을 걸러내는 쪽이 조용히 망가지면 이 검사가
    #   아무것도 안 든다. `display_scope` 가 머리말에 「후진 의존이 **아니다**」를
    #   적고 있고, 그것이 걸러지는지를 실물로 되묻는다.
    ds = (ROOT / "src/firelane/display_scope.py").read_text(encoding="utf-8")
    assert "후진 의존이 아니" in ds, (
        "display_scope.py 의 부정형 문구가 사라졌다 — 이 검사의 부정 걸러내기가\n"
        "  이제 실물로 확인되지 않는다. 다른 부정형을 찾아 여기에 매라.")
    assert not _BACK_CLAIM.search("후진 의존이 아니다"), "부정형 걸러내기가 망가졌다"
    assert _BACK_CLAIM.search("후진 의존이다"), "긍정형을 못 잡는다 — 그물이 비었다"
