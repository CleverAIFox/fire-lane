"""관문 동등 — 로컬과 CI 가 같은 검사기를 **같은 인자로** 부르는가 (3족).

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-22 (DECISIONS §218-5). `gate_parity.py` 는 검사기 **이름**(파일)을 맞춘다. 같은 날
  미선언 로컬 전용 11 중 열을 contract.yml 로 옮기면서 인자가 두 곳에 적히게 됐다 —
  `dupcheck --min 40 --max 1` 이 대표다. 2026-09-18 에 `gate_parity --max 19` 가 정확히 이
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
    assert "--min 40 --max 1" in v.get("tools/dupcheck.py", set()), "verify.sh 의 dupcheck 인자를 못 읽었다"
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
