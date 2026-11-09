#!/usr/bin/env python3
"""
gatefast.py — `pre-push.gates` 의 게이트가 **CI 빠른 잡(`contract-fast`)이 막는 것에 덮이는가**를 세 갈래로 센다.  (PLAN #210)

    uv run python tools/gatefast.py            세 수와 이름 · 사유(면제)
    uv run python tools/gatefast.py --json     같은 것을 JSON 으로

── 왜 있나 ─────────────────────────────────────────────────────
「푸시해도 되는가」는 한 명령이 아니라 **셋의 합집합**(`pre-push.gates` · `pushready` · CI)이고 셋 사이의 포함 관계를 아무도 안 쟀다(#210).
이 도구가 그 중 하나 — **훅이 막는 것 가운데 CI 빠른 잡이 같이 막는 것은 무엇인가** — 를 센다.

★ **세 갈래다**(사람이 정했다 · 인자 차이를 말하지 않는 한계를 안 받았다):
    덮인다        이름도 인자도 같다
    인자가 다르다  이름은 같고 인자가 다르다 — **세 번째 수로 따로 낸다**(같은 검사기를 훅은 `--ratchet` 만, CI 는 전수로 돌 수 있다)
    안 덮인다      이름이 CI 빠른 잡에 없다
  「덮인다」가 거짓이면 안 세는 것보다 나쁘다 — 그래서 이름만 맞는 것을 덮인다에 넣지 않는다.

★ **사본이 아니다.** 선언을 복사하지 않는다 — 훅의 명령(`pre-push.gates`)과 CI 의 명령(`contract.yml`)을 **각자의 자리에서 읽어 맞대기만** 한다.
  인자를 어디에도 적지 않는다. 「인자가 다르다」가 결함인지 의도인지 기계는 모른다 — 의도면 이미 있는 `# ci-exempt:`(`tools/verify.sh`)로 사유를 적는다(새 형식을 안 만든다).
  면제는 **검사기 경로**로 맞는다(`gate_parity.exemptions()` 를 그대로 부른다).

★ **이름의 열쇠는 검사기 경로다.** 워크플로의 단계 이름과 게이트 이름은 같지 않다 — 둘이 공통으로 쥔 것은 `tools/x.py` · `-m firelane.x`(`gate_parity.tokens`) ·
  pytest 게이트는 시험 파일 경로다. 2026-11-09 실측: 훅 24줄은 모두 열쇠가 하나씩 나온다.

IN    `.githooks/pre-push.gates`(첫 두 열만 — 셋째 열이 생겨도 안 깬다) · `.github/workflows/contract.yml` 의 `contract-fast` 잡 · `tools/verify.sh` 의 `# ci-exempt:`
OUT   표준출력(세 수 · 이름). 파일은 안 쓴다.
PARAM 없음
밖    **인자가 다른 것이 결함인지 의도인지는 안 가린다.** 같은 인자인데 환경이 달라 결과가 다른 경우도 못 본다(`contract-fast` 가 레이크 없이 돈다 등).
      `contract-heavy` · `contract-tests` 잡은 안 본다 — 빠른 잡만 묻는다(그 둘이 막는 것은 이 도구의 물음이 아니다).
부류  조사   사람이 손으로 돌려 수를 내고 멈춘다(DECISIONS §398 — 어느 관문에도 안 올렸다)
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

import gate_parity as GP
import yaml

ROOT = Path(__file__).resolve().parent.parent
GATES = ROOT / ".githooks" / "pre-push.gates"
WORKFLOW = ROOT / ".github" / "workflows" / "contract.yml"
JOB = "contract-fast"

_PYTEST_TARGET = re.compile(r"(tests/[A-Za-z0-9_./-]+\.py)")


def gate_commands(path: Path = GATES) -> list[tuple[str, str]]:
    """(이름, 명령) — **첫 두 열만** 읽는다. 셋째 열(실측 초 등)이 생겨도 명령에 안 섞인다."""
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        cols = ln.split("\t")
        out.append((cols[0], cols[1] if len(cols) > 1 else ""))
    return out


def fast_commands(workflow: Path = WORKFLOW, job: str = JOB) -> list[str]:
    """`contract-fast` 잡의 `run:` 명령 줄들(`\\` 이음 · 줄머리 주석 정리)."""
    steps = (yaml.safe_load(workflow.read_text(encoding="utf-8")).get("jobs", {}).get(job) or {}).get("steps", [])
    out: list[str] = []
    for s in steps:
        buf = ""
        for ln in str(s.get("run", "")).splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            buf += (" " if buf else "") + ln.rstrip("\\").strip()
            if not ln.endswith("\\"):
                out.append(buf)
                buf = ""
        if buf:
            out.append(buf)
    return out


def keys(cmd: str) -> list[str]:
    """명령의 열쇠 — 검사기 경로(`tools/x.py` · `firelane.x`) 또는 pytest 가 가리킨 시험 파일. 없으면 빈 목록."""
    ks = sorted(GP.tokens(cmd))
    targets = _PYTEST_TARGET.findall(cmd) if "pytest" in cmd else []
    if targets:
        ks = [k for k in ks if k != "pytest"] + targets      # 시험 파일을 가리킨 pytest 는 그 파일이 열쇠다(맨 `pytest` 는 열쇠가 못 된다)
    return ks


def args_of(cmd: str, key: str) -> list[str]:
    """열쇠 **뒤**의 인자(셸 낱말로). pytest 시험 파일은 열쇠가 인자 자리에 있으므로 **옵션만** 비교한다(경로는 열쇠다)."""
    try:
        toks = shlex.split(cmd)
    except ValueError:
        toks = cmd.split()
    if key.startswith("tests/"):
        return sorted(t for t in toks if t.startswith("-") or t == "no:cacheprovider")
    base = key.removeprefix("tools/")
    for i, t in enumerate(toks):
        if t.endswith(base) or t == key:
            return toks[i + 1:]
    return toks[toks.index(key.split(".")[-1]) + 1:] if key.split(".")[-1] in toks else []


def classify(gates: list[tuple[str, str]] | None = None, fast: list[str] | None = None,
             exempt: dict[str, str] | None = None) -> dict[str, dict]:
    """게이트 이름 → {`갈래`: 덮인다 · 인자가 다르다 · 안 덮인다 · 열쇠 없음, `열쇠`, `CI`(다른 인자 목록), `면제`(사유)}."""
    gates = gate_commands() if gates is None else gates
    fast = fast_commands() if fast is None else fast
    ex = GP.exemptions() if exempt is None else exempt
    out: dict[str, dict] = {}
    for name, cmd in gates:
        ks = keys(cmd)
        if not ks:
            out[name] = {"갈래": "열쇠 없음", "열쇠": None, "CI": [], "면제": None}      # 닫힌 쪽 — 센 것이 아니다
            continue
        k = ks[0]
        cands = [c for c in fast if k in keys(c)]
        mine = args_of(cmd, k)
        if not cands:
            kind, other = "안 덮인다", []
        elif any(args_of(c, k) == mine for c in cands):
            kind, other = "덮인다", []
        else:
            kind, other = "인자가 다르다", [" ".join(args_of(c, k)) for c in cands]
        out[name] = {"갈래": kind, "열쇠": k, "CI": other, "면제": ex.get(k)}
    return out


def render(res: dict[str, dict]) -> str:
    n = {k: sum(1 for v in res.values() if v["갈래"] == k) for k in ("덮인다", "인자가 다르다", "안 덮인다", "열쇠 없음")}
    L = [f"훅 {len(res)}게이트 → CI `{JOB}` : 덮인다 {n['덮인다']} · **인자가 다르다 {n['인자가 다르다']}** · 안 덮인다 {n['안 덮인다']}"
         + (f" · 열쇠 없음 {n['열쇠 없음']}(못 잰 것)" if n["열쇠 없음"] else "")]
    for kind in ("인자가 다르다", "안 덮인다", "열쇠 없음"):
        rows = [(nm, v) for nm, v in res.items() if v["갈래"] == kind]
        if rows:
            L += ["", f"  {kind}"]
            for nm, v in rows:
                why = f"  — 면제: {v['면제']}" if v["면제"] else "  — **면제 사유 없음**"
                extra = f"  (CI 인자: {' | '.join(v['CI'])})" if v["CI"] else ""
                L.append(f"    · {nm}  [{v['열쇠']}]{extra}{why if kind != '열쇠 없음' else ''}")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pre-push 게이트가 CI 빠른 잡에 덮이는가 — 세 갈래")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = classify()
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
