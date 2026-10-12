"""관문 동등 — 로컬과 CI 가 같은 검사기를 **같은 인자로** 부르는가 (3족).

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-22 (DECISIONS §218-5). `gate_parity.py` 는 검사기 **이름**(파일)을 맞춘다. 같은 날
  미선언 로컬 전용 11 중 열을 contract.yml 로 옮기면서 인자가 두 곳에 적히게 됐다 —
  `dupcheck --min 40 --max 0`(2026-10-08 까지 `--max 1`) 이 대표다. 2026-09-18 에 `gate_parity --max 19` 가 정확히 이
  모양으로 갈려 **로컬 초록 · CI 빨강**이 났다(W3-11). 이름이 같고 인자가 다르면 같은 검사가
  아니다 — 그러면 관문 동등은 이름만 동등하다.

★ 판정 — CI 가 부르는 인자 조합은 **로컬이 부르는 조합 중 하나**여야 한다. 로컬이 더 많이
  부르는 것은 괜찮다(`golden.py check` · `selftest` 를 둘 다 부르는 식). 의도된 차이는
  `ALLOWED` 에 사유와 함께 적고, 차이가 사라지면 그 줄도 지운다(죽은 면제는 실패).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify.sh"
CI = ROOT / ".github" / "workflows" / "contract.yml"

CALL = re.compile(r"python\s+(?:(tools/\w+\.py)|-m\s+(firelane\.[\w.]+))([^\n'\"|&;)]*)")

# 의도된 차이 — 검사기 → 사유. 사유 없이 늘리지 않는다.
ALLOWED = {
    "tools/navi_env.py": "CI 는 바로 다음 줄이 늘 `npm ci` 라 대조만 한다(`--no-sync`). 로컬은 잠금 지문이"
                         " 바뀌었을 때 설치까지 맞춘다 — 검사 판정은 같다",
}


def _calls(path: Path) -> dict[str, set[str]]:
    lines = path.read_text(encoding="utf-8").replace("\\\n", " ").splitlines()
    body = "\n".join(line.split("#", 1)[0] for line in lines)
    out: dict[str, set[str]] = {}
    for m in CALL.finditer(body):
        out.setdefault(m.group(1) or m.group(2), set()).add(" ".join(m.group(3).split()))
    return out


def test_parser_is_not_an_empty_net() -> None:
    """★ 빈 그물인가. 추출기가 죽으면 아래가 조용히 통과한다."""
    v, c = _calls(VERIFY), _calls(CI)
    assert "--min 40 --max 0" in v.get("tools/dupcheck.py", set()), "verify.sh 의 dupcheck 인자를 못 읽었다"
    assert len(set(v) & set(c)) >= 15, f"공통 검사기를 {len(set(v) & set(c))}개만 찾았다 — 추출기가 죽었다"


def test_ci_calls_checkers_with_local_arguments() -> None:
    v, c = _calls(VERIFY), _calls(CI)
    bad = []
    for tool in sorted(set(v) & set(c)):
        extra = c[tool] - v[tool]
        if extra and tool not in ALLOWED:
            bad.append(f"  {tool}  CI {sorted(extra)} · 로컬 {sorted(v[tool])}")
    assert not bad, (
        "CI 가 로컬과 다른 인자로 부르는 검사기가 있다.\n" + "\n".join(bad)
        + "\n\n  이름이 같고 인자가 다르면 같은 검사가 아니다(W3-11 · 2026-09-18 `--max 19`).\n"
          "  문턱을 한 곳으로 옮기거나(gate_parity 의 RATCHET 처럼), 의도된 차이면 ALLOWED 에 사유를 적어라.")


def test_allowed_differences_are_alive() -> None:
    """면제가 **아직 필요한가.** 차이가 사라졌거나 한쪽이 안 부르면 면제는 거짓이다."""
    v, c = _calls(VERIFY), _calls(CI)
    dead = [t for t in sorted(ALLOWED)
            if t not in v or t not in c or not (c[t] - v[t])]
    blank = [t for t, why in ALLOWED.items() if len(why.strip()) < 5]
    assert not dead and not blank, f"죽은 면제 {dead} · 사유 없음 {blank}"


def test_the_count_axis_sees_the_same_command_twice() -> None:
    """**횟수 축이 무는가.** 집합은 「두 번 도는가」를 못 본다 (§456-6 ⑧).

    ★ 2026-10-11. `gate_parity` 의 네 판정이 전부 `set[str]` 이라 같은 명령을
      열 번 더 붙여도 출력이 한 글자도 안 바뀌었다. 그래서 §456-4 가 센
      중복 여섯을 **이 도구가 하나도 못 봤다.** 세는 단위는 검사기가 아니라
      명령 한 줄이다 — 같은 도구의 다른 하위명령은 묻는 것이 다르다.
    """
    import gateruns as gp

    assert not gp.dup_cmds(), "같은 명령이 두 번 도는 자리가 있다:\n  " + "\n  ".join(gp.dup_cmds())
    assert gp.local_cmds(), "verify.sh 에서 명령을 0줄 읽었다 — 빈 그물이다"
    assert gp.ci_cmds(), "워크플로에서 명령을 0줄 읽었다 — 빈 그물이다"

    # ★ 카나리아 — 양쪽으로 민다.
    _one = "uv run python tools/x.py"
    assert gp.dup_cmds(local=[_one, _one], ci=[]), "글자까지 같은 둘을 안 센다"
    assert not gp.dup_cmds(local=[_one, _one + " --only"], ci=[]), \
        "하위명령이 다른 둘을 중복으로 센다"
    assert gp.dup_cmds(local=[], ci=[("a.yml", _one), ("a.yml", _one)]), \
        "같은 워크플로의 둘을 안 센다"
    assert not gp.dup_cmds(local=[], ci=[("a.yml", _one), ("b.yml", _one)]), \
        "다른 워크플로의 하나씩을 중복으로 센다 — 일이 둘이다"


def test_the_double_run_axis_reads_the_group_key() -> None:
    """`workflow_call` 과 제 트리거를 같이 든 워크플로가 **한 번만 도는가.**

    ★ 2026-10-10 (DECISIONS §457-3). `contract.yml` 이 제 push 와 `deploy.yml`
      의 `gate` 양쪽으로 깨워져 같은 커밋에 **두 벌** 돌았다. 접는 자리는
      `concurrency.group` 하나인데 그 키가 부르는 쪽을 안 갈랐다. 그때는
      사람이 셌고, 이 축이 그 자리를 기계로 센다.
    """
    import gateruns as gp

    assert not gp.double_runs(), "두 벌 도는 워크플로가 있다:\n  " + "\n  ".join(gp.double_runs())

    _head = "on:\n  workflow_call:\n  push:\n    branches: [dev]\n"
    _loose = _head + "concurrency:\n  group: c-${{ github.ref }}\n"
    assert gp.double_runs({"probe.yml": _loose}), "안 가르는 group 키를 통과시킨다"
    assert not gp.double_runs({"probe.yml": _loose.replace("github.ref", "github.workflow")}), \
        "가르는 group 키를 두 벌로 센다"
    # ★ 불리기만 하는 본문은 두 벌이 아니다 — 깨우는 쪽이 하나다.
    assert not gp.double_runs({"probe.yml": "on:\n  workflow_call:\n"}), \
        "제 트리거가 없는 재사용 본문을 센다"
