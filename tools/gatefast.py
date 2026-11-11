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
★ **면제는 갈래를 안 바꾼다** — 사유가 붙어도 「안 덮인다」는 그대로 센다(사유는 의도임을 적을 뿐 CI 가 막게 되는 것이 아니다). 면제는 따로 세어 「사유 없음」이 0 인지를 본다.

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
from gate_parity import (  # 열쇠를 읽는 자리는 `gate_parity` 한 곳이다(다시 구현하지 않는다)
    gate_commands,
    keys,
)

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "contract.yml"
JOB = "contract-fast"

# ── 층 선언표 — 「CI 빠른 잡의 이 검사는 어느 층이 막나」를 **한 곳에** 적는다  (PLAN #216 · 반대 방향 + 단일 선언) ──────────
# ★ 세 층은 **pushready < 훅 < CI** 다. CI 빠른 잡의 열쇠 76 중 훅에 같은 열쇠가 있는 것 21 · 없는 것 55 였다(2026-11-11 실측). 그 55 를 **하나씩 돌려 재고** 층을 갈랐다:
#     훅      `pre-push.gates` 가 든다 — 선언은 그 파일이다(이 표에 안 적는다). 훅 예산 30초가 경계를 정한다.
#     ready   푸시 전에 막되 훅에 못 든다 — `pushready` ㉨ 가 **CI 의 명령 글자 그대로**(`fast_commands`) 돈다(두 번째 사본이 없다).
#     ci      CI 에만 둔다 — 망 · npm · CI 문맥이 필요하거나 다른 층이 이미 든다.
# ★ 가른 기준은 셋이다 — 느린가 · **레이크가 필요한가**(55 전부 레이크 없이 돌아 같은 결과다 — 이 기계는 `FIRE_LANE_DATA` 가 붙어 있어 레이크 없이도 한 번 더 쟀다) · 망이 필요한가.
# ★ **훅은 하나만 들었다**(`env_check`): 싼 37개를 한꺼번에 더하면 훅 30.2~33.3초(중앙 31.1)로 예산을 넘는다(5회 · 한가한 기계 · 한 개씩은 0.1~2.7초지만 CPU 가 합쳐진다).
#   `env_check` 하나는 +0.7초(중앙)다 — 오늘 CI 가 이것 때문에 빨갰다(`FIRE_LANE_PUSH_RANGES`).
# ★ 2026-11-11 (⓯-① · #216 닫음). **표의 열쇠를 (열쇠, 인자)로 바꾸고 CI 의 다섯 잡을 전부 읽는다** — 같은 `ruff` 가 기본 룰셋(fast)과 `.ruff-strict.toml`(strict)로 둘이고, 열쇠만 쓰면 둘째가 첫째 뒤에 숨었다.
#   층이 하나 늘었다: `axis` = `pushready` 의 다른 축(㉠ · ㉥)이 같은 도구를 이미 돈다.
# ★ 이 표가 **다시 안 열리게 하는 법** — 새 CI 검사는 이 표에 층을 안 적으면 `tests/test_gatefast.py` 가 빨갛다(미선언). 표에 적고 CI 에서 지워진 것도 빨갛다(죽은 선언).
_BUDGET = "훅 예산 — 한 개씩은 싸지만(0.1~2.7초) 싼 37개를 한꺼번에 들이면 훅 30.2~33.3초(5회 · 중앙 31.1 · 예산 30)"
_SLOW1 = "느리다 — 단독 20.5초"
_SLOW2 = "느리다 — 단독 10.6초"
_SLOW3 = "훅 예산 — 단독 3.8~4.9초(싼 37개 + 이 셋이면 훅 중앙 33.6초)"
_NET = "망이 필요하다(패키지 내려받기 · GitHub API)"
_NPM = "npm · node_modules 가 필요하다(`npm ci` 는 망)"
_PRECOMMIT = "다른 층이 이미 든다 — 커밋 훅이 같은 `pre-commit` 설정을 돈다(`--all-files` 전수는 느리다)"
_CTX = "CI 문맥이 필요하다(PR 본문 · 기준 커밋 `$BASE`)"
_WRITES1 = "읽기 전용이 아니다 — `data/interim/lineage.mmd`(추적 밖 산출물)를 쓴다 · 0.6초"
_WRITES2 = "느리고(단독 58초) 읽기 전용이 아니다 — `data/processed/clearance_cross.json` 을 쓴다"
_AXIS_A = "㉠ 이 같은 도구(`tools/ratchet.py` 전수)를 이미 돈다"
_AXIS_T = "㉥ 이 시험 묶음을 돈다 — CI 는 전수를 네 조각으로 나눠 돌고 ㉥ 은 그 부분집합(바뀐 파일에 닿는 것 + 예산 묶음)이다"
_STRICT = "엄격 잡(`contract-strict`)의 검사 — 싸고(0.1~0.9초) 읽기만 한다. 훅 예산에 안 넣고 ㉨ 가 든다"
LAYERS: dict[tuple[str, str], tuple[str, str]] = {
    ("deptry", "src tools"): ("ci", _NET),
    ("firelane.contract", "--declared"): ("ready", _BUDGET),
    ("firelane.datalog", "graph"): ("ci", _WRITES1),
    ("firelane.jsonkeys", ""): ("ready", _BUDGET),
    ("firelane.ledger_check", ""): ("ready", _BUDGET),
    ("navi:lint", ""): ("ci", _NPM),
    ("navi:test", ""): ("ci", _NPM),
    ("navi:typecheck", ""): ("ci", _NPM),
    ("pre-commit", "run --all-files --show-diff-on-failure"): ("ci", _PRECOMMIT),
    ("pytest", "${files[@]} -q"): ("axis", _AXIS_T),
    ("ruff", "check $FILES --config .ruff-strict.toml"): ("ready", _STRICT),
    ("ruff", "check src tools tests"): ("ready", _BUDGET),
    ("tests/test_contract.py", "-v"): ("ready", _BUDGET),
    ("tests/test_ownership.py", "-q"): ("ready", _BUDGET),
    ("tools/actionpin.py", ""): ("ci", _NET),
    ("tools/archcost.py", ""): ("ready", _BUDGET),
    ("tools/argcheck.py", ""): ("ready", _BUDGET),
    ("tools/clearance_cross.py", ""): ("ci", _WRITES2),
    ("tools/colorsim.py", ""): ("ready", _BUDGET),
    ("tools/countcheck.py", ""): ("ready", _BUDGET),
    ("tools/depgroups_check.py", ""): ("ready", _BUDGET),
    ("tools/docnum_check.py", ""): ("ready", _STRICT),
    ("tools/dupcheck.py", "--min 40 --max 0"): ("ready", _SLOW3),
    ("tools/fixable.py", ""): ("ready", _BUDGET),
    ("tools/fixture_recut.py", "--check"): ("ready", _BUDGET),
    ("tools/gate_parity.py", ""): ("ready", _BUDGET),
    ("tools/greycheck.py", ""): ("ready", _BUDGET),
    ("tools/htmlfigs.py", "--check"): ("ready", _BUDGET),
    ("tools/install_navi.py", "--check"): ("ready", _BUDGET),
    ("tools/ledger_cross.py", ""): ("ready", _BUDGET),
    ("tools/ledger_fields.py", "--check"): ("ready", _BUDGET),
    ("tools/ledgercols.py", ""): ("ready", _BUDGET),
    ("tools/localgeo.py", ""): ("ready", _BUDGET),
    ("tools/mergecheck.py", ""): ("ci", _NET),
    ("tools/mutate_guard.py", "--pending"): ("ready", _BUDGET),
    ("tools/navi_env.py", "--no-sync"): ("ready", _BUDGET),
    ("tools/navi_setup.py", "--check"): ("ready", _BUDGET),
    ("tools/navicheck.py", ""): ("ready", _BUDGET),
    ("tools/navicov.py", ""): ("ready", _BUDGET),
    ("tools/naviweight.py", ""): ("ready", _BUDGET),
    ("tools/owned_paths.py", "--py-only"): ("ready", _STRICT),
    ("tools/pages_add_navi.py", "--check"): ("ready", _BUDGET),
    ("tools/pr_body_check.py", ""): ("ci", _CTX),
    ("tools/probeledger.py", ""): ("ready", _BUDGET),
    ("tools/ratchet.py", ""): ("axis", _AXIS_A),
    ("tools/redoscheck.py", ""): ("ready", _BUDGET),
    ("tools/release_brief.py", "--base $BASE --md"): ("ci", _CTX),
    ("tools/scopecheck.py", ""): ("ready", _BUDGET),
    ("tools/scopedecl.py", ""): ("ready", _SLOW3),
    ("tools/segcontract.py", ""): ("ready", _BUDGET),
    ("tools/selftests.py", ""): ("ready", _SLOW1),
    ("tools/sizecheck.py", ""): ("ready", _BUDGET),
    ("tools/srccov.py", ""): ("ready", _SLOW2),
    ("tools/suppress.py", ""): ("ready", _BUDGET),
    ("tools/svg_fit.py", ""): ("ready", _BUDGET),
    ("tools/toolclass.py", ""): ("ready", _BUDGET),
    ("tools/toolindex.py", "--check"): ("ready", _BUDGET),
    ("tools/treecheck.py", ""): ("ready", _SLOW3),
    ("tools/uicheck.py", "--split"): ("ready", _BUDGET),
    ("tools/unusedcheck.py", ""): ("ready", _STRICT),
    ("tools/verdictsim.py", ""): ("ready", _BUDGET),
    ("tools/web_manifest.py", "--check"): ("ready", _BUDGET),
}
LAYER_KINDS = ("ready", "ci", "axis")   # axis = `pushready` 의 다른 축이 같은 도구를 이미 돈다(사유의 첫 낱말이 그 축의 열쇠)


def hook_entries(gates: list[tuple[str, str]] | None = None) -> set[tuple[str, str]]:
    """훅 게이트의 (열쇠, 인자) 집합 — `pre-push.gates` 가 정본이다."""
    gates = gate_commands() if gates is None else gates
    out: set[tuple[str, str]] = set()
    for _n, cmd in gates:
        ks = keys(cmd)
        if ks:
            out.add((ks[0], " ".join(args_of(cmd, ks[0]))))
    return out


def layer_report(ents: dict[tuple[str, str], dict] | None = None, hook: set[tuple[str, str]] | None = None,
                 layers: dict[tuple[str, str], tuple[str, str]] | None = None) -> dict[str, list]:
    """반대 방향 — CI(다섯 잡) → 훅 · ready · axis · ci. 문제: `미선언` · `죽은 선언` · `훅과 겹친다` · `사유 부족` · `층 이름`. 항목은 (열쇠, 인자)."""
    ents = entries() if ents is None else ents
    hook = hook_entries() if hook is None else hook
    layers = LAYERS if layers is None else layers
    rep: dict[str, list] = {"훅": sorted(k for k in ents if k in hook), "ready": [], "axis": [], "ci": [], "미선언": [], "죽은 선언": [], "훅과 겹친다": [], "사유 부족": [], "층 이름": []}
    for k in sorted(ents):
        if k in hook:
            if k in layers:
                rep["훅과 겹친다"].append(k)
            continue
        if k not in layers:
            rep["미선언"].append(k)
            continue
        layer, why = layers[k]
        if layer not in LAYER_KINDS:
            rep["층 이름"].append(k)
        else:
            rep[layer].append(k)
        if len(why.strip()) < GP.MIN_REASON:
            rep["사유 부족"].append(k)
    rep["죽은 선언"] = sorted(k for k in layers if k not in ents)
    return rep


def ready_commands(ents: dict[tuple[str, str], dict] | None = None,
                   layers: dict[tuple[str, str], tuple[str, str]] | None = None) -> list[tuple[tuple[str, str], str]]:
    """`ready` 층의 ((열쇠, 인자), **단계 스크립트 전문**) — CI 의 글자 그대로다(`pushready` ㉨ 가 돈다). 사본이 아니라 CI 에서 도출한다."""
    ents = entries() if ents is None else ents
    layers = LAYERS if layers is None else layers
    return [(k, ents[k]["script"]) for k in sorted(layers) if layers[k][0] == "ready" and k in ents]


def hook_vs_pushready() -> dict[str, list[str]]:
    """훅 게이트 → `pushready`: ㉨ 가 도는 것(`돈다`)과 더 센 축이 대신하는 것(`대신`)을 센다 — 훅 24게이트 중 `pushready` 가 안 보던 15개가 0이 됐는지(PLAN #216).

    `pushready` 를 **함수 안에서** 부른다 — 그쪽이 이 모듈을 import 하므로 위에서 부르면 순환이다."""
    import pushready as PR
    jobs, skipped = PR.mirror_commands()
    return {"돈다": [j[1] for j in jobs if j[0] == "훅"], "대신": [f"{k} — {why}" for k, why in sorted(skipped.items())]}


def fmt_id(k: tuple[str, str]) -> str:
    return f"{k[0]} {k[1]}".strip()


def render_reverse(rep: dict[str, list]) -> str:
    total = sum(len(rep[k]) for k in ("훅", "ready", "axis", "ci", "미선언", "층 이름"))
    L = [f"CI 다섯 잡의 검사 {total}(열쇠 · 인자) → 훅 {len(rep['훅'])} · pushready(ready) {len(rep['ready'])} · 다른 축이 든다(axis) {len(rep['axis'])} · CI 만 {len(rep['ci'])} · **미선언 {len(rep['미선언'])}**"]
    for k in ("미선언", "죽은 선언", "훅과 겹친다", "사유 부족", "층 이름"):
        if rep[k]:
            L.append(f"  ✗ {k}: {', '.join(fmt_id(x) for x in rep[k])}")
    return "\n".join(L)


JOBS = ("contract-fast", "contract-heavy", "contract-tests", "contract-shared", "contract-strict")   # CI 의 다섯 잡 전부 — 하나만 읽으면 다른 잡의 검사가 층 표에서 숨는다(PLAN #216)


def _steps(workflow: Path, job: str) -> list[dict]:
    return (yaml.safe_load(workflow.read_text(encoding="utf-8")).get("jobs", {}).get(job) or {}).get("steps", [])


def _logical_lines(run: str) -> list[str]:
    """`run:` 한 덩어리의 명령 줄들(역슬래시 이음 · 줄머리 주석 정리)."""
    out: list[str] = []
    buf = ""
    for ln in str(run).splitlines():
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


def step_script(run: str) -> str:
    """단계 하나의 `run:` 본문 — 주석 · 빈 줄을 뺀 **글자 그대로**(여러 줄이 변수를 주고받는 단계는 한 덩어리로 돌아야 한다: 엄격 린트의 `FILES=$(…)`)."""
    return "\n".join(ln.rstrip() for ln in str(run).splitlines() if ln.strip() and not ln.strip().startswith("#"))


def fast_commands(workflow: Path = WORKFLOW, job: str = JOB) -> list[str]:
    """한 잡(기본 `contract-fast`)의 `run:` 명령 줄들."""
    return [c for s in _steps(workflow, job) for c in _logical_lines(s.get("run", ""))]


def all_commands(workflow: Path = WORKFLOW, jobs: tuple[str, ...] = JOBS) -> list[str]:
    """다섯 잡 전부의 명령 줄들(훅 → CI 방향이 「아무 잡에든 있나」를 묻는다)."""
    return [c for j in jobs for c in fast_commands(workflow, j)]


def entries(workflow: Path = WORKFLOW, jobs: tuple[str, ...] = JOBS) -> dict[tuple[str, str], dict]:
    """CI 의 검사 하나 = **(열쇠, 인자)**. 값은 처음 나온 잡 · 명령 줄 · 그 단계의 스크립트 전문.

    ★ 열쇠 하나가 아니다 — 같은 `ruff` 가 `contract-fast` 에서는 기본 룰셋으로, `contract-strict` 에서는 `.ruff-strict.toml` 로 돈다(인자가 다르다).
      열쇠만 키로 쓰면 둘째가 첫째 뒤에 숨는다(2026-11-11 PR 이 그것으로 빨갰다)."""
    out: dict[tuple[str, str], dict] = {}
    for j in jobs:
        for st in _steps(workflow, j):
            script = step_script(st.get("run", ""))
            for cmd in _logical_lines(st.get("run", "")):
                ks = keys(cmd)
                if ks:
                    out.setdefault((ks[0], " ".join(args_of(cmd, ks[0]))), {"job": j, "cmd": cmd, "script": script if _needs_step(cmd) else cmd})
    return out


_VAR = re.compile(r"\$[A-Za-z_{]")


def _needs_step(cmd: str) -> bool:
    """명령이 **같은 단계의 앞 줄이 준 셸 변수**를 쓰는가(`ruff check $FILES …` — `FILES=$(…)` 가 앞 줄에 있다). 그러면 단계 전문이 한 덩어리로 돌아야 한다.

    ★ 아니면 **그 줄만** 돈다. 단계 전문을 늘 돌면 안 된다 — `navi_env` 줄은 같은 단계에 `npm ci` · `npm run build` 를 달고 있어(망 · 44초) 줄 하나를 돌리려고 내려받기까지 하게 된다
      (2026-11-11 ㉨ 가 64초가 된 원인이었다). 변수 대입 줄(`N=$(…)`)은 자기 완결이라 줄 그대로 돈다."""
    return bool(_VAR.search(cmd)) and not re.match(r"^[A-Za-z_]\w*=", cmd)


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
            return _trim(toks[i + 1:])
    return _trim(toks[toks.index(key.split(".")[-1]) + 1:]) if key.split(".")[-1] in toks else []


_SHELL_STOP = {"|", "||", "&&", ";", ")", ">", ">>", "2>&1"}


def _trim(toks: list[str]) -> list[str]:
    """인자에서 **셸 문법**을 뗀다 — 파이프 · 명령 치환의 닫는 괄호는 인자가 아니다(`owned_paths --py-only | wc -l)` 가 세 가지 인자로 갈렸다)."""
    out: list[str] = []
    for t in toks:
        if t in _SHELL_STOP:
            break
        out.append(t.rstrip(")") if t.endswith(")") and "(" not in t else t)
    return out


def classify(gates: list[tuple[str, str]] | None = None, fast: list[str] | None = None,
             exempt: dict[str, str] | None = None) -> dict[str, dict]:
    """게이트 이름 → {`갈래`: 덮인다 · 인자가 다르다 · 안 덮인다 · 열쇠 없음, `열쇠`, `CI`(다른 인자 목록), `면제`(사유)}."""
    gates = gate_commands() if gates is None else gates
    fast = all_commands() if fast is None else fast
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
    gone = [v for v in res.values() if v["갈래"] != "덮인다"]
    ex = sum(1 for v in gone if v["면제"])
    L = [f"훅 {len(res)}게이트 → CI `{JOB}` : 덮인다 {n['덮인다']} · **인자가 다르다 {n['인자가 다르다']}** · 안 덮인다 {n['안 덮인다']}"
         + (f" · 열쇠 없음 {n['열쇠 없음']}(못 잰 것)" if n["열쇠 없음"] else "")
         + f"   (안 덮인 것과 인자가 다른 것 {len(gone)} 중 면제 {ex} · **사유 없음 {len(gone) - ex}**)"]
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
    ap.add_argument("--check", action="store_true", help="반대 방향(CI → 훅 · ready · ci)만 본다 — 미선언 · 죽은 선언이 있으면 rc 1")
    a = ap.parse_args(argv)
    rep = layer_report()
    bad = any(rep[k] for k in ("미선언", "죽은 선언", "훅과 겹친다", "사유 부족", "층 이름"))
    if a.check:
        print(render_reverse(rep))
        return 1 if bad else 0
    res = classify()
    hp = hook_vs_pushready()
    line = f"훅 {len(hp['돈다']) + len(hp['대신'])}게이트 → pushready: ㉨ 가 돈다 {len(hp['돈다'])} · 더 센 축이 대신한다 {len(hp['대신'])}(사유 있음) · 안 보는 것 0"
    print(json.dumps({"훅 → CI": res, "CI → 층": rep, "훅 → pushready": hp}, ensure_ascii=False, indent=1) if a.json else render(res) + "\n\n" + render_reverse(rep) + "\n" + line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
