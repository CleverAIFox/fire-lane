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
# ★ 이 표가 **다시 안 열리게 하는 법** — 새 CI 검사는 이 표에 층을 안 적으면 `tests/test_gatefast.py` 가 빨갛다(미선언). 표에 적고 CI 에서 지워진 것도 빨갛다(죽은 선언).
_BUDGET = "훅 예산 — 한 개씩은 싸지만(0.1~2.7초) 싼 37개를 한꺼번에 들이면 훅 30.2~33.3초(5회 · 중앙 31.1 · 예산 30)"
_SLOW1 = "느리다 — 단독 20.5초"
_SLOW2 = "느리다 — 단독 10.6초"
_SLOW3 = "훅 예산 — 단독 3.8~4.9초(싼 37개 + 이 셋이면 훅 중앙 33.6초)"
_NET = "망이 필요하다(패키지 내려받기 · GitHub API)"
_NPM = "npm · node_modules 가 필요하다(`npm ci` 는 망)"
_PRECOMMIT = "다른 층이 이미 든다 — 커밋 훅이 같은 `pre-commit` 설정을 돈다(`--all-files` 전수는 느리다)"
_CTX = "CI 문맥이 필요하다(PR 본문 · 기준 커밋 `$BASE`)"
LAYERS: dict[str, tuple[str, str]] = {
    "firelane.contract": ("ready", _BUDGET),
    "firelane.jsonkeys": ("ready", _BUDGET),
    "firelane.ledger_check": ("ready", _BUDGET),
    "ruff": ("ready", _BUDGET),
    "tests/test_contract.py": ("ready", _BUDGET),
    "tests/test_ownership.py": ("ready", _BUDGET),
    "tools/archcost.py": ("ready", _BUDGET),
    "tools/argcheck.py": ("ready", _BUDGET),
    "tools/colorsim.py": ("ready", _BUDGET),
    "tools/countcheck.py": ("ready", _BUDGET),
    "tools/depgroups_check.py": ("ready", _BUDGET),
    "tools/dupcheck.py": ("ready", _SLOW3),
    "tools/fixable.py": ("ready", _BUDGET),
    "tools/fixture_recut.py": ("ready", _BUDGET),
    "tools/gate_parity.py": ("ready", _BUDGET),
    "tools/greycheck.py": ("ready", _BUDGET),
    "tools/htmlfigs.py": ("ready", _BUDGET),
    "tools/install_navi.py": ("ready", _BUDGET),
    "tools/ledger_cross.py": ("ready", _BUDGET),
    "tools/ledger_fields.py": ("ready", _BUDGET),
    "tools/ledgercols.py": ("ready", _BUDGET),
    "tools/localgeo.py": ("ready", _BUDGET),
    "tools/mutate_guard.py": ("ready", _BUDGET),
    "tools/navi_env.py": ("ready", _BUDGET),
    "tools/navi_setup.py": ("ready", _BUDGET),
    "tools/navicheck.py": ("ready", _BUDGET),
    "tools/navicov.py": ("ready", _BUDGET),
    "tools/naviweight.py": ("ready", _BUDGET),
    "tools/pages_add_navi.py": ("ready", _BUDGET),
    "tools/probeledger.py": ("ready", _BUDGET),
    "tools/redoscheck.py": ("ready", _BUDGET),
    "tools/scopecheck.py": ("ready", _BUDGET),
    "tools/scopedecl.py": ("ready", _SLOW3),
    "tools/segcontract.py": ("ready", _BUDGET),
    "tools/selftests.py": ("ready", _SLOW1),
    "tools/sizecheck.py": ("ready", _BUDGET),
    "tools/srccov.py": ("ready", _SLOW2),
    "tools/suppress.py": ("ready", _BUDGET),
    "tools/svg_fit.py": ("ready", _BUDGET),
    "tools/toolclass.py": ("ready", _BUDGET),
    "tools/toolindex.py": ("ready", _BUDGET),
    "tools/treecheck.py": ("ready", _SLOW3),
    "tools/uicheck.py": ("ready", _BUDGET),
    "tools/verdictsim.py": ("ready", _BUDGET),
    "tools/web_manifest.py": ("ready", _BUDGET),
    "deptry": ("ci", _NET),
    "navi:lint": ("ci", _NPM),
    "navi:test": ("ci", _NPM),
    "navi:typecheck": ("ci", _NPM),
    "pre-commit": ("ci", _PRECOMMIT),
    "tools/actionpin.py": ("ci", _NET),
    "tools/mergecheck.py": ("ci", _NET),
    "tools/pr_body_check.py": ("ci", _CTX),
    "tools/release_brief.py": ("ci", _CTX),
}
LAYER_KINDS = ("ready", "ci")


def ci_keys(fast: list[str] | None = None) -> dict[str, str]:
    """CI 빠른 잡의 열쇠 → 그 열쇠를 처음 부르는 명령(글자 그대로). 열쇠가 안 나오는 셸 조각 · `npm` 줄은 뺀다(센 것이 아니다)."""
    fast = fast_commands() if fast is None else fast
    out: dict[str, str] = {}
    for c in fast:
        ks = keys(c)
        if ks:
            out.setdefault(ks[0], c)
    return out


def layer_report(fast: list[str] | None = None, hook: set[str] | None = None, layers: dict[str, tuple[str, str]] | None = None) -> dict[str, list[str]]:
    """반대 방향 — CI → 훅 · ready · ci. 문제 목록: `미선언`(CI 에 있고 훅에도 표에도 없다) · `죽은 선언`(표에 있는데 CI 에 없다) · `훅과 겹친다`(훅에 있는데 표에도 있다) · `사유 부족` · `층 이름`."""
    ck = ci_keys(fast)
    hook = GP.hook_keys() if hook is None else hook
    layers = LAYERS if layers is None else layers
    rep: dict[str, list[str]] = {"훅": sorted(k for k in ck if k in hook), "ready": [], "ci": [], "미선언": [], "죽은 선언": [], "훅과 겹친다": [], "사유 부족": [], "층 이름": []}
    for k in sorted(ck):
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
    rep["죽은 선언"] = sorted(k for k in layers if k not in ck)
    return rep


def ready_commands(fast: list[str] | None = None, layers: dict[str, tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    """`ready` 층의 (열쇠, 명령) — **명령은 CI 의 글자 그대로**다(`pushready` ㉨ 가 돈다). 사본이 아니라 CI 에서 도출한다."""
    ck = ci_keys(fast)
    layers = LAYERS if layers is None else layers
    return [(k, ck[k]) for k in sorted(layers) if layers[k][0] == "ready" and k in ck]


def render_reverse(rep: dict[str, list[str]]) -> str:
    total = len(rep["훅"]) + len(rep["ready"]) + len(rep["ci"]) + len(rep["미선언"]) + len(rep["층 이름"])
    L = [f"CI `{JOB}` 열쇠 {total} → 훅 {len(rep['훅'])} · pushready(ready) {len(rep['ready'])} · CI 만 {len(rep['ci'])} · **미선언 {len(rep['미선언'])}**"]
    for k in ("미선언", "죽은 선언", "훅과 겹친다", "사유 부족", "층 이름"):
        if rep[k]:
            L.append(f"  ✗ {k}: {', '.join(rep[k])}")
    return "\n".join(L)


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
    print(json.dumps({"훅 → CI": res, "CI → 층": rep}, ensure_ascii=False, indent=1) if a.json else render(res) + "\n\n" + render_reverse(rep))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
