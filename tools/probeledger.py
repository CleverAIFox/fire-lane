#!/usr/bin/env python3
"""
probeledger.py — **판정을 낸 조사 도구가 측정 대장에 행을 갖는가.**

    uv run python tools/probeledger.py
    uv run python tools/probeledger.py --selftest

── 왜 생겼나 (2026-10-13 · DECISIONS §513) ────────────────────
`tools/jijeok_probe.py` 가 2026-08-23 에 여섯 가설을 밀어 둘을 맞혔고,
그 결론을 **제 머리말에** 적었다 — ④ 중심선이 지적 중앙이 아니다 ·
⑤ 법선 포화 · ⑥ 거대 도로구역 필지. 그 셋이 DECISIONS §509 · §510 이
**두 달 뒤에 다시 찾은** 바로 그것이다.

왜 다시 찾았나. 저장소의 그물은 DECISIONS 와 PLAN 을 읽고, 도구 머리말은
**부류 · IN · OUT · PARAM · 밖** 다섯 칸만 읽는다(§398). 「무엇을 알아냈나」는
그 다섯에 없으므로 **아무 그물도 안 본다.** 사람이 기억으로 지키던 자리였고
기억은 두 달을 못 간다(§390: 「규약을 되풀이하는 것은 강제자가 아니다」).

규모가 그 병을 설명한다 — 부류 **조사** 도구가 24개인데 측정 대장은 5행이다.

★ **전부에 요구하지 않는다.** 조사 도구 스물넷 중 대부분은 진단이고, 수가
  결정에 닿지 않는다. 전부에 요구하면 그 빨강은 아무도 안 읽는다
  (§284-6 「우는 관문은 없는 관문보다 나쁘다」). 그래서 묻는 것을 좁혔다 —
  **머리말이 제 손으로 「★ 맞음」 · 「진짜 원인」 같은 판정을 적은 도구**만
  본다. 그것은 「나는 결론을 냈다」를 도구가 스스로 선언한 자리다.
  실측으로 그런 도구는 **하나**다(2026-10-13).

IN    tools/*.py 머리말(부류 **조사** + 판정 표시) · docs/PLAN.md 측정 대장
OUT   `orphans()` · `ORPHAN_PROBES`
PARAM VERDICT_MARKS · ORPHAN_PROBES
밖    **판정이 옳은가는 안 본다.** 「★ 맞음」이 실제로 맞는지는 사람이 안다.
      여기가 드는 것은 **그 수가 다시 재지 않아도 되는 자리에 적혔는가**다.
      대장 행의 내용(물음 · 판정 기준 · 봉인 자리 셋을 갖췄는가)은
      `tests/test_measurements.py` 소관이고, 도구 부류를 도출하는 일은
      `tools/toolclass.py` 소관이다.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from firelane.cli import no_args

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
PLAN = ROOT / "docs" / "PLAN.md"

#: 도구가 **제 손으로 판정을 적은** 표시. 가설을 밀어 결론을 낸 자리다.
#: ★ 「무엇을 알아냈나」 같은 **제목**은 안 센다 — 제목은 결론이 아니라 칸이고,
#:   결론 없이 제목만 둔 도구를 울리면 그 빨강이 안 읽힌다.
VERDICT_MARKS = ("★ 맞음", "★ 틀림", "진짜 원인")

#: 조사 도구가 판정을 냈는데 측정 대장에 행이 없는 수. **내려가는 쪽.**
#: 2026-10-13 실측 1 → **0**(`jijeok_probe` 에 `jijeok-width` 행을 달았다).
ORPHAN_PROBES = 0

RATCHETS = {"ORPHAN_PROBES": "down"}

#: 측정 대장 행의 키. `| \`r4-ngii-pieces\` | 77 | …` 꼴의 첫 칸이다.
_ROW = re.compile(r"^\|\s*`([a-z0-9][a-z0-9-]*)`\s*\|")
_CLASS = re.compile(r"^부류\s+(\S+)", re.M)


def ledger_keys(src: str | None = None) -> list[str]:
    """측정 대장이 든 행의 키."""
    text = PLAN.read_text(encoding="utf-8") if src is None else src
    return [m.group(1) for ln in text.splitlines() if (m := _ROW.match(ln))]


def stem(name: str) -> str:
    """`jijeok_probe.py` → `jijeok`. 대장 행과 맞추는 열쇠다.

    ★ 접미 `_probe` · `_review` · `_audit` · `_compare` 는 **도구의 역할**이고
      재는 대상이 아니다. 대장 행은 대상으로 이름이 붙으므로 떼고 맞춘다.
    """
    s = name[:-3] if name.endswith(".py") else name
    for suf in ("_probe", "_review", "_audit", "_compare", "_check", "_tally"):
        if s.endswith(suf):
            return s[: -len(suf)]
    return s


def probes(root: Path | None = None) -> list[tuple[str, list[str]]]:
    """부류 **조사** 이고 머리말에 판정을 적은 도구 — (파일명, 표시)."""
    out = []
    for p in sorted((root or TOOLS).glob("*.py")):
        try:
            doc = ast.get_docstring(ast.parse(p.read_text(encoding="utf-8"))) or ""
        except SyntaxError:
            continue
        m = _CLASS.search(doc)
        if not m or m.group(1) != "조사":
            continue
        if marks := [k for k in VERDICT_MARKS if k in doc]:
            out.append((p.name, marks))
    return out


def orphans(found: list[tuple[str, list[str]]] | None = None,
            keys: list[str] | None = None) -> list[str]:
    """판정을 냈는데 대장에 **그 대상을 든 행이 없는** 도구. 순수하다."""
    ks = ledger_keys() if keys is None else keys
    bad = []
    for name, marks in (probes() if found is None else found):
        s = stem(name)
        if not any(s in k for k in ks):
            bad.append(f"  tools/{name}  머리말이 {' · '.join(marks)} 로 판정을 "
                       f"적었는데 측정 대장에 `{s}` 를 든 행이 없다 — "
                       f"그 수는 **다시 재야 한다**")
    return bad


def ratchet_values() -> dict[str, int]:
    return {"ORPHAN_PROBES": len(orphans())}


def selftest() -> int:
    """합성 머리말과 합성 대장으로 **양방향**을 민다(§405 의 규율)."""
    bad: list[str] = []
    mine = [("jijeok_probe.py", ["★ 맞음"])]
    if not orphans(mine, keys=["width-cross", "parallel-edges"]):
        bad.append("판정을 낸 도구에 대장 행이 없는데 통과시킨다 — 그물이 비었다")
    if orphans(mine, keys=["jijeok-width"]):
        bad.append("대장 행이 있는데 울린다 — 언제나 빨강이다")
    # ★ 역할 접미를 떼고 맞춘다 — `jijeok_review` 도 `jijeok` 행이 받는다
    if orphans([("jijeok_review.py", ["진짜 원인"])], keys=["jijeok-width"]):
        bad.append("`_review` 접미를 안 뗀다 — 역할은 재는 대상이 아니다")
    # ★ 거르는 일은 `probes()` 가 한다 — 합성 도구 셋을 임시 폴더에 써서 민다.
    #   `orphans()` 에 물으면 안 된다: 그 함수는 **이미 걸러진 것**을 받는다.
    import tempfile  # noqa: PLC0415  이 함수 하나만 쓴다

    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        (t / "a_probe.py").write_text(
            '"""재는 것.\n\n부류  조사\n\n  ① 가설   ★ 맞음\n"""\n', encoding="utf-8")
        (t / "b_probe.py").write_text(
            '"""재는 것.\n\n부류  조사\n\n  무엇을 알아냈나 — 아직 없다\n"""\n',
            encoding="utf-8")
        (t / "c.py").write_text(
            '"""만드는 것.\n\n부류  생산\n\n  ① 가설   ★ 맞음\n"""\n', encoding="utf-8")
        got = {n for n, _ in probes(t)}
    if "a_probe.py" not in got:
        bad.append("판정을 적은 조사 도구를 안 집는다 — 그물이 비었다")
    if "b_probe.py" in got:
        bad.append("판정 표시가 없는 도구까지 집는다 — 그 빨강은 안 읽힌다")
    if "c.py" in got:
        bad.append("부류가 **조사**가 아닌 도구까지 집는다 — 부류를 안 본다")
    # ★ 대장 행 읽기 — 키만 든다
    ks = ledger_keys("| `a-b` | 4 | 물음 |\n문단\n| `c` | — | 물음 |\n| 판 | 성질 |\n")
    if ks != ["a-b", "c"]:
        bad.append(f"대장 행 키를 잘못 읽는다 — {ks}")
    # ★ 실물 — 래칫과 같아야 한다
    n = len(orphans())
    if n != ORPHAN_PROBES:
        bad.append(f"실측 {n} ≠ 래칫 {ORPHAN_PROBES} — 선언이 낡았다")
    if bad:
        print("★ 자기검사 실패")
        for b in bad:
            print(" ", b)
        return 1
    print("selftest 초록")
    return 0


def main() -> int:
    found = probes()
    bad = orphans(found)
    print(f"판정을 낸 조사 도구 {len(found)}개 · 측정 대장 {len(ledger_keys())}행 · "
          f"행 없는 것 {len(bad)} (래칫 {ORPHAN_PROBES})")
    if len(bad) > ORPHAN_PROBES:
        print(f"\n✗ 행 없는 판정 {len(bad)} — 래칫 {ORPHAN_PROBES} 보다 늘었다.")
        for b in bad:
            print(b)
        print("\n  머리말에만 둔 수는 그물이 안 읽고, 다음 사람이 **다시 만든다**")
        print("  (DECISIONS §513 — §509 · §510 이 두 달 전 머리말을 다시 찾았다).")
        print("  대장 행은 「물음 · 판정 기준(재기 전에 적는다) · 봉인 자리」 셋을 든다.")
        return 1
    if len(bad) < ORPHAN_PROBES:
        print(f"\n✗ 행 없는 판정 {len(bad)} < 래칫 {ORPHAN_PROBES} — 줄었다. "
              f"ORPHAN_PROBES 를 {len(bad)} 으로 내려라")
        return 1
    print("✓ 판정을 낸 조사 도구가 전부 대장에 행을 갖는다")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    no_args(__doc__)
    sys.exit(main())
