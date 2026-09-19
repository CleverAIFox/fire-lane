"""영향 범위 선언 — `verify.sh --since` 가 **조용히 건너뛰지 않는가** (W7-2).

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-19. `--since=REF` 를 만들면서 **만든 그 자리에서 1족을 냈다.**

    _touches $_scope          ← 안 따옴표

셸이 `web/navi/*` 를 **실제 파일 목록으로 펼쳐버린다.** 패턴이 패턴으로
도착하지 않고 직계 자식 목록이 되므로 `web/navi/src/App.tsx` 를 **못 잡는다.**
즉 내비를 고쳤는데 「내비 타입 검사」가 조용히 건너뛰어진다 —
**초록불인데 아무것도 안 본** 상태다. 실측으로 잡았고 `set -f` 로 고쳤다.

★ 이 파일이 존재하는 이유가 그것이다. 범위 기반 실행은 **빨라지는 대신
  안 도는 것이 생기는** 기능이라, 「안 돈 것이 안 돌아야 했던 것인가」를
  기계가 물어야 한다. 사람이 읽어서 맞히는 것은 한 번은 되고 두 번은 안 된다.

★ 안전망은 셋이다.
    ① 미선언은 항상 돈다 — 손목록이 빠져도 안전한 쪽으로 틀린다
    ② `--since` 는 `부분 실행` 안전장치를 켠다 — 봉인·수용이 불가능하다
    ③ 이 파일 — 선언이 떠 있거나, 없는 경로를 가리키거나,
       매칭이 죽으면 운다
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify.sh"

SCOPE_LINE = re.compile(r'^\s*scope "([^"]*)"', re.M)


def _patterns() -> set[str]:
    out: set[str] = set()
    for m in SCOPE_LINE.finditer(VERIFY.read_text(encoding="utf-8")):
        out.update(m.group(1).split())
    return out


def test_scope_declarations_are_all_attached() -> None:
    """떠 있는 선언이 없는가.

    ★ 판정을 **여기서 다시 구현하지 않는다.** `verify.sh --scope-list` 가
      정본이고 이 시험은 그것을 부를 뿐이다 — 파싱 규칙을 두 곳에 적으면
      그 순간 2족이 된다.
    ★ `--scope-list` 는 아무것도 실행하지 않는다(정적 읽기).
    """
    r = subprocess.run(["bash", str(VERIFY), "--scope-list"],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, (
        "어느 단계에도 안 붙은 `scope` 선언이 있다.\n"
        + r.stdout[-1500:]
        + "\n  붙지 않은 선언은 아무 일도 안 하면서 「범위를 적었다」고\n"
        + "  믿게 만든다 — 있다고 적혀 있으면 사람이 안 본다.")


def test_scope_patterns_point_at_real_paths() -> None:
    """선언이 **실재하는 뿌리**를 가리키는가.

    ★ `web/nav/*` 처럼 한 글자만 틀려도 그 단계는 `--since` 에서 **영원히
      건너뛰어진다.** 아무것도 안 울고, 빨라졌다고 느낀다. 최악의 형태다.
    """
    bad = []
    for pat in sorted(_patterns()):
        root = pat.split("*", 1)[0].rstrip("/")
        if root and not (ROOT / root).exists():
            bad.append(f"  scope \"{pat}\" — `{root}` 가 저장소에 없다")
    assert not bad, (
        "영향 범위 선언이 없는 경로를 가리킨다.\n" + "\n".join(bad)
        + "\n  한 글자만 틀려도 그 단계는 --since 에서 영영 안 돈다.")


@pytest.mark.parametrize(
    ("changed", "pattern", "want"),
    [
        # ★ 회귀 — 이것이 2026-09-19 에 실제로 틀렸던 조합이다.
        ("web/navi/src/App.tsx", "web/navi/*", True),
        ("web/navi/src/ui/Panel.tsx", "web/* tools/*.mjs", True),
        ("src/firelane/seg/width.py", "src/* tools/*", True),
        ("docs/PLAN.md", "docs/*", True),
        ("docs/PLAN.md", "web/navi/*", False),
        ("web/data/x.json", "data/*", False),
        (".github/workflows/contract.yml", ".github/*", True),
    ],
)
def test_touches_matches_nested_paths(changed: str, pattern: str, want: bool) -> None:
    """`_touches` 가 **깊은 경로**를 잡는가 — 프로브가 살아 있는가.

    ★ 함수를 `verify.sh` 에서 **그대로 떼어다** 돌린다. 여기에 같은 로직을
      다시 적으면 이 시험은 자기가 적은 것을 시험하게 된다 — 그러면 진짜
      `verify.sh` 가 고장나도 초록이다(`deadcheck ①` 가 묻는 그 물음).
    """
    src = VERIFY.read_text(encoding="utf-8")
    m = re.search(r"^_touches\(\) \{.*?^\}", src, re.M | re.S)
    assert m, "verify.sh 에서 _touches 를 못 찾았다 — 이 시험이 빈 그물이 됐다"

    script = f'CHANGED="{changed}"\n{m.group(0)}\n_touches "{pattern}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    got = r.returncode == 0
    assert got is want, (
        f"_touches 가 틀렸다 — 바뀐 것 {changed!r} · 범위 {pattern!r}\n"
        f"  기대 {'돈다' if want else '건너뜀'} · 실제 {'돈다' if got else '건너뜀'}\n"
        "  범위가 좁으면 고친 것을 검사하지 않고 초록이 뜬다.\n"
        "  (2026-09-19: 인자를 안 따옴표로 넘겨 셸이 패턴을 파일 목록으로\n"
        "   펼쳤고 `web/navi/*` 가 `web/navi/src/App.tsx` 를 못 잡았다)")


def test_since_forces_partial_run_safety_net() -> None:
    """`--since` 가 `부분 실행` 안전장치를 켜는가.

    ★ 이것이 없으면 `--since` 로 돈 반쪽 로그를 `dms.py seal` 이 전수로
      착각하고 봉인한다 — `--fast` 가 2026-09-15 에 그랬던 자리다.
    ★ 문자열로 본다. 실제로 돌리려면 레이크와 의존성이 필요하고, 여기서
      묻는 것은 「조건에 `--since` 가 들어 있는가」 하나다.
    """
    src = VERIFY.read_text(encoding="utf-8")
    m = re.search(r'^if \[ -n "\$ONLY" \].*$', src, re.M)
    assert m, "`부분 실행` 안전장치의 조건줄을 못 찾았다"
    assert '-n "$SINCE"' in m.group(0), (
        "`--since` 가 `부분 실행` 안전장치에 안 걸려 있다.\n"
        f"  지금: {m.group(0).strip()}\n"
        "  건너뛴 것은 통과가 아니다 — 범위 기반 실행은 수용이 아니라\n"
        "  고치는 중에 쓰는 되먹임 도구다(§13-5 규약 6).")
