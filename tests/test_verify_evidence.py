"""증거 수 = 선언 수 — `verify.sh` 가 **선언한 단계마다 한 행씩** 기록하는가 (1족 클래스 가드).

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-22 (DECISIONS §218-5). `TOTAL` 은 진행 표시의 분모로만 쓰였고 실제 기록 행 수와
  대조하는 자리가 없었다. 2026-09-15 · 09-19 에 분모가 두 번 틀렸는데(이름 중복 · `부분 실행`)
  두 번 다 **사람이 화면을 보고** 알았다. 같은 날 실측으로 행을 안 남기는 갈래가 셋 더
  있었다 — npm 없는 갈래(셋 중 하나만) · `--fast` · raw 부재(넷 중 이름도 다른 한 행).

★ 이제 `verify.sh` 끝의 `evidence_check` 가 기록 행 수와 `TOTAL` 을 대조해 다르면 실패를
  올린다. 이 파일은 그 함수가 **살아 있는지**(합성 실행)와 **걸려 있는지**(정적)를 본다.

★ 함수를 여기서 다시 적지 않는다. `verify.sh` 에서 **그대로 떼어다** 돌린다 — 다시 적으면
  이 시험은 자기가 적은 것을 시험하게 된다(`test_verify_scope` 의 `_touches` 와 같은 방식).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify.sh"


def _src() -> str:
    return VERIFY.read_text(encoding="utf-8")


def _prelude() -> str:
    """`hms()` 부터 `evidence_check()` 의 닫는 `}` 까지 — step · note · note_hard 가 여기 산다."""
    src = _src()
    m = re.search(r"^hms\(\) \{.*?^evidence_check\(\) \{.*?^\}", src, re.M | re.S)
    assert m, "verify.sh 에서 hms() … evidence_check() 구간을 못 찾았다 — 이 시험이 빈 그물이 됐다"
    return m.group(0)


def _run(total: int, body: str) -> str:
    script = "\n".join([
        "set -uo pipefail",
        "R=; G=; Y=; C=; D=; Z=",
        "declare -a NAMES RESULTS NOTES SECS",
        'pass=0; fail=0; skip=0; IDX=0; ONLY=""; SINCE=""; SCOPE=""; CHANGED=""',
        f"TOTAL={total}",
        _prelude(),
        body,
        "evidence_check",
        'echo "ROWS=${#NAMES[@]} FAIL=$fail LAST=${NAMES[${#NAMES[@]}-1]}"',
    ])
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]
    return r.stdout.strip().splitlines()[-1]


BODY = 'step "가" true\nnote "나" "npm 이 없다"\nstep "다" false\n'


def test_evidence_check_passes_when_every_step_left_a_row() -> None:
    """행 셋 · 선언 셋 — 증거 실패를 **안** 올린다(실패 1 은 `step "다" false` 몫)."""
    out = _run(3, BODY)
    assert out.startswith("ROWS=3 FAIL=1 "), out
    assert "증거 수" not in out, out


@pytest.mark.parametrize(("total", "why"), [(4, "행을 안 남긴 갈래"), (2, "행이 분모보다 많다")])
def test_evidence_check_fails_on_mismatch(total: int, why: str) -> None:
    """행 수가 선언과 다르면 **실패 한 줄**이 더해진다 — 양방향이다."""
    out = _run(total, BODY)
    assert "FAIL=2" in out and out.endswith("LAST=증거 수 = 선언 수"), (
        f"{why}인데 evidence_check 가 안 울었다 — {out}\n"
        "  분모만 있고 대조가 없으면 빠진 단계가 초록 사이에 묻힌다.")


def test_evidence_check_runs_after_partial_guard_and_before_verdict() -> None:
    """`evidence_check` 가 **걸려 있는가** — `부분 실행` 뒤 · 최종 판정 앞."""
    src = _src()
    calls = [m.start() for m in re.finditer(r"^evidence_check\s*$", src, re.M)]
    assert len(calls) == 1, f"evidence_check 호출이 {len(calls)}개다 — 정확히 하나여야 한다"
    guard = src.find('step "부분 실행"')
    verdict = src.find('if [ "$fail" -gt 0 ]; then\n    printf \'%s실패가 있다')
    assert 0 < guard < calls[0] < verdict, (
        "evidence_check 가 제자리에 없다 — `부분 실행`(분모에 든 단계) 뒤, 최종 판정 앞이어야 한다.")


def _names(kind: str, text: str) -> list[str]:
    return re.findall(rf'^[ \t]*{kind}\s+"([^"]+)"', text, re.M)


def test_skip_rows_use_declared_step_names() -> None:
    """`note` · `note_hard` 가 **단계 이름으로** 행을 남기는가.

    ★ 종전 「파이프라인 전량 + golden」은 어느 단계 이름과도 안 맞았다 — 수가 우연히 맞아도
      무엇이 빠졌는지 표가 말하지 못한다.
    """
    src = _src()
    steps = set(_names("step", src))
    skips = set(_names("note", src)) | set(_names("note_hard", src))
    assert skips, "note 호출을 0개 찾았다 — 프로브가 죽었다"
    stray = sorted(skips - steps)
    assert not stray, f"단계 이름이 아닌 생략 행 — {stray}"


def _top_blocks(src: str) -> list[list[str]]:
    """열 0 의 `if … fi` 블록마다 갈래(if · elif · else) 본문 목록."""
    out: list[list[str]] = []
    cur: list[str] | None = None
    for line in src.splitlines():
        if cur is None:
            # ★ `; then` 으로 끝나는 줄만 — 단계 인자 속 파이썬(`if bad:`)을 셸 블록으로 안 읽는다
            if re.match(r"^if\b.*;\s*then\s*$", line):
                cur = [""]
            continue
        if re.match(r"^(elif|else)\b", line):
            cur.append("")
        elif re.match(r"^fi\b", line):
            out.append(cur)
            cur = None
        else:
            cur[-1] += line + "\n"
    return out


def test_every_branch_records_the_same_steps() -> None:
    """조건 갈래마다 **같은 단계 이름 집합**이 행을 남기는가.

    ★ 한 갈래가 `step` 셋을 돌고 다른 갈래가 `note` 하나만 남기면 분모와 기록이 어긋난다.
      그 상태를 실행 없이 여기서 먼저 잡는다. 갈래 없는 블록에 단계가 있으면 그 조건이
      거짓일 때 행이 안 남는다 — `부분 실행` 하나만 예외다(분모가 같은 조건으로 뺀다).
    """
    bad = []
    blocks = [b for b in _top_blocks(_src())
              if any(_names("step", br) for br in b)]
    assert len(blocks) >= 3, f"단계를 품은 조건 블록을 {len(blocks)}개만 찾았다 — 파서가 죽었다"
    for b in blocks:
        sets = [frozenset(_names("step", br) + _names("note", br) + _names("note_hard", br))
                for br in b]
        if len(b) == 1:
            if sets[0] != {"부분 실행"}:
                bad.append(f"  else 없는 블록이 단계를 품는다 — {sorted(sets[0])}")
        elif len(set(sets)) != 1:
            bad.append("  갈래마다 이름이 다르다 — " + " | ".join(str(sorted(s)) for s in sets))
    assert not bad, "행을 안 남기는 갈래가 있다.\n" + "\n".join(bad)
