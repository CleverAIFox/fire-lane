#!/usr/bin/env python3
"""
gateruns.py — **관문이 같은 것을 몇 번 도는가.** 횟수를 보는 축이다.

**진입점이 아니다.** `tools/gate_parity.py` 가 부르고 판정을 찍는다 —
프로브(합성 결함을 양쪽으로 미는 자리)도 그쪽 `--selftest` 하나다. 두 벌을
두면 갈린다(2족).

── 왜 생겼나 (2026-10-11 · DECISIONS §456-6 ⑧) ────────────────
`tools/gate_parity.py` 가 「로컬 관문과 CI 가 **같은 것을 보는가**」를 묻는데
자료형이 `set[str]` 이다. 워크플로 전부를 읽어 합집합을 만들므로 **횟수는
판정에 닿기 전에 접힌다** — 같은 pytest 를 열 개 더 붙여도 출력이 한 글자도
안 바뀌고, §456-4 가 센 중복 여섯을 그 도구가 하나도 못 봤다.

그 도구의 머리말이 한계를 스스로 적어 뒀다 — 「단계 **이름**이 아니라
**검사기**를 맞춘다」. 이름을 버리는 설계라 **단계를 단위로 세는 축이 애초에
없다.** 그래서 2026-10-10 의 중복 셋은 사람이 손으로 셌다(§344 · §457-3).

★ 묻는 것이 다르므로 도구가 다르다. 판정을 찍는 것은 여전히
  `gate_parity.report()` 이고, 여기는 **세는 일**만 한다 — `tools/dms.py` 의
  `verify` 와 `scan` 이 갈려 있는 것과 같은 자리.

★ 세는 단위는 검사기가 아니라 **명령 한 줄**이다. 같은 도구의 다른 하위명령은
  묻는 것이 달라 중복이 아니다(ruff 룰셋 둘 · golden check/selftest). 단계가
  무엇을 묻는지는 `verify.sh` 의 `# asks:` 와 `tools/scopedecl.py` 가 든다.

부류  몸통   진입점이 **아니다.** 부류는 부르는 쪽에서 물려받는다  (DECISIONS §398)

IN    tools/verify.sh · .github/workflows/*.yml · .github/actions/**/*.yml
OUT   `dup_cmds()` · `double_runs()` · `ratchet_values()` (부르는 쪽이 찍는다)
PARAM DUP_CMD · DOUBLE_RUN
밖    **중복이 나쁜가는 안 본다.** 글자까지 같은 명령 둘은 같은 일을 두 번
      하는 것이지만, 그것이 의도된 자리인지는 사람이 본다 — 여기가 드는 것은
      「수가 늘었는가」다. **검사기 이름의 동등**은 `gate_parity` 소관이다.
"""
from __future__ import annotations

import collections
import re
from pathlib import Path

#: 검사기 추출과 주석 걷기는 `gate_parity` 하나다. 여기서 또 적으면 두 그물이
#: 같은 글을 다르게 읽는다 — §425 에서 한 번 겪었다. 같은 `tools/` 안이라
#: 경로를 얹을 일이 없다 — 이 파일을 부르는 쪽이 이미 그 자리에 있다.
from gate_parity import _nocomment, _verify_src, tokens

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
ACT = ROOT / ".github" / "actions"

# ★ 2026-10-11 (DECISIONS §456-6 ⑧). **횟수를 보는 축.** 위의 두 수는 집합의
#   차집합이라 「같은 명령을 두 번 부르는가」가 판정에 닿기 전에 접힌다 —
#   머리말이 적은 「단계 이름이 아니라 검사기를 맞춘다」의 값이다. 그래서
#   §456-4 가 센 중복 여섯을 이 도구가 **하나도 못 봤다.** 세는 단위는
#   검사기가 아니라 **명령 한 줄**이다 — 같은 도구의 다른 하위명령은 묻는 것이
#   달라 중복이 아니고(ruff 룰셋 둘 · golden check/selftest), 글자까지 같은 것은
#   같은 일을 두 번 하는 것이다.
DUP_CMD = 0

# ★ 같은 자리의 형제. 「같은 커밋에 **워크플로 한 벌이 두 번** 깨워지는가」는
#   명령 줄로는 안 보인다 — 글은 한 번 적혀 있고 깨우는 쪽이 둘이다.
#   2026-10-10 에 그 모양으로 셋이 돌았고(§457-3), 그때는 사람이 셌다.
DOUBLE_RUN = 0

#: ★ 이 도구의 래칫 중 **꺼낼 수 있는 것만** 여기 든다. `RATCHET` 과
#:   `CI_ONLY_RATCHET` 은 `report()` 안에서 인쇄와 함께 계산돼 값만 못 꺼낸다 —
#:   `tools/ratchet.py` 머리말이 그 사실을 든다.
RATCHETS = {"DUP_CMD": "down", "DOUBLE_RUN": "down"}


def ratchet_values() -> dict[str, int]:
    return {"DUP_CMD": len(dup_cmds()), "DOUBLE_RUN": len(double_runs())}


_STEP_CMD = re.compile(r'^\s*step\s+"[^"]*"\s*(.*)$')
#: CI 의 명령 줄. 들여쓰기 · `- ` · `run:` 을 떼고 본다.
#: ★ `run:` 을 안 떼면 한 줄짜리 `run: uv run pytest …` 가 **안 보인다** —
#:   처음 쟀을 때 contract 의 pytest 셋이 그렇게 빠졌다.
_RUNNER = ("uv run", "python", "python3", "bash", "sh ", "node", "npm", "npx")
_RUN_KEY = re.compile(r"^-?\s*run:\s*")


def _norm(cmd: str) -> str:
    """공백만 고른다. 줄바꿈과 들여쓰기는 같은 명령을 다르게 보이게 한다."""
    return " ".join(cmd.split())


def local_cmds(src: str | None = None) -> list[str]:
    """`verify.sh` 의 단계가 **실제로 부르는 명령**. 검사기를 든 줄만 든다."""
    out = []
    for ln in _nocomment(_verify_src() if src is None else src).splitlines():
        if m := _STEP_CMD.match(ln):
            cmd = _norm(m.group(1))
            if cmd and tokens(cmd):
                out.append(cmd)
    return out


def ci_cmds(srcs: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """CI 가 부르는 명령 — (워크플로, 명령). **워크플로 안에서** 센다.

    ★ 재사용 본문을 두 곳이 부르는 것은 중복이 아니다. 그 본문 파일 안에서
      명령은 한 번이고, 부르는 쪽이 둘인 것은 **일이 둘**이기 때문이다.
    """
    if srcs is None:
        srcs = {str(p.relative_to(ROOT)): p.read_text(encoding="utf-8")
                for p in sorted(WF.glob("*.yml")) + sorted(ACT.rglob("*.yml"))}
    out = []
    for name, raw in srcs.items():
        for ln in _nocomment(raw).splitlines():
            cmd = _norm(_RUN_KEY.sub("", ln.strip()))
            if cmd.startswith(_RUNNER) and tokens(cmd):
                out.append((name, cmd))
    return out


def double_runs(srcs: dict[str, str] | None = None) -> list[str]:
    """**한 커밋에 두 벌 도는 워크플로.** `④` 가 다시 생기는 것을 여기서 센다.

    `workflow_call` 로 불리면서 제 트리거(`push` · `pull_request`)도 가진
    워크플로는 같은 커밋에 두 번 깨워진다. 접히는 자리는 `concurrency.group`
    하나뿐이고, 그 키가 **부르는 쪽을 가르지 못하면**(`github.workflow` 가
    없으면) 두 벌이 나란히 돈다 — 2026-10-10 에 그 모양으로 셋이 돌았다
    (DECISIONS §457-3).
    """
    import yaml  # noqa: PLC0415  이 함수 하나만 쓴다

    if srcs is None:
        srcs = {p.name: p.read_text(encoding="utf-8") for p in sorted(WF.glob("*.yml"))}
    bad = []
    for name, raw in srcs.items():
        doc = yaml.safe_load(raw) or {}
        on = doc.get(True) or doc.get("on") or {}
        if not isinstance(on, dict) or "workflow_call" not in on:
            continue
        own = [k for k in ("push", "pull_request") if k in on]
        if not own:
            continue
        group = str(((doc.get("concurrency") or {}) or {}).get("group") or "")
        if "github.workflow" not in group:
            bad.append(f"{name}: workflow_call + {' · '.join(own)} 인데 "
                       f"group 키가 부르는 쪽을 안 가른다 — {group or '없다'}")
    return bad


def dup_cmds(local: list[str] | None = None,
             ci: list[tuple[str, str]] | None = None) -> list[str]:
    """**글자까지 같은 명령**을 한 자리에서 두 번 이상 부르는가. 순수하다."""
    rows = [("로컬", "verify.sh", c) for c in (local_cmds() if local is None else local)]
    rows += [("CI", w, c) for w, c in (ci_cmds() if ci is None else ci)]
    n = collections.Counter(rows)
    return [f"{side} {w}: {cmd}  — {k}번"
            for (side, w, cmd), k in sorted(n.items()) if k > 1]



