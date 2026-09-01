#!/usr/bin/env python3
"""
test_crosswalk.py — 팀 문서 축이 `DECISIONS §83` 에 전건 등재됐는가.

── 왜 생겼나 ───────────────────────────────────────────────────
회의록 8건 · 진행일지 11건이 결정 85건과 미결 56건을 만들었는데 이 저장소는
그중 어느 것도 인용한 적이 없었다. `P-` 참조가 문서 셋과 코드 전체에 0곳이다.
그리고 번호가 실제로 충돌한다 — 회의록 결정 44·63·80·81 과 `DECISIONS §44`
`§63` `§80` `§81` 이 전부 다른 내용이다(§83-1).

★ 대응표를 만드는 것만으로는 사흘이면 낡는다. `MASTER §17` — *새 규칙을 적을
  때는 강제자를 같이 만든다.* 이 검사가 그것이다.

── 무엇을 보는가 ───────────────────────────────────────────────
`§83-3`(결정) · `§83-5`(미결) 의 분류 표에서 백틱 안 번호를 뽑아 넷을 본다.

    1  전건 등재    M-01~M-90(결번 08~12) · P-01~P-60(결번 06~09)
    2  중복 없음    한 번호가 두 처리 유형에 있으면 실패
    3  결번 유지    없는 번호를 등재하면 실패
    4  참조 유효    본문이 가리키는 `PLAN §1 #nn` 이 실재하는가

★ 안 보는 것 — **분류가 옳은가는 못 본다.** 흡수로 적어놓고 실제로는 저장소에
  없어도 통과한다. 그것은 사람이 읽어야 한다(R23).

IN    docs/DECISIONS.md §83 · docs/PLAN.md §1
OUT   없음 (검사)
PARAM MISSING_M · MISSING_P — 결번 선언
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "docs/DECISIONS.md"
PLAN = ROOT / "docs/PLAN.md"

# ★ 결번은 누락이 아니다. 회의록 실측으로 확인했다(§83-3 · §83-5).
MISSING_M = {8, 9, 10, 11, 12}
MISSING_P = {6, 7, 8, 9}
M_RANGE = range(1, 91)
P_RANGE = range(1, 61)

SEC = re.compile(r"^### 83-(\d)\.", re.M)
TOKEN = re.compile(r"`([MP])-(\d{2})`")


def _section(body: str, n: int) -> str:
    """`### 83-n.` 의 본문. 다음 `###` 또는 `##` 앞까지."""
    m = re.search(rf"^### 83-{n}\..*$", body, re.M)
    assert m, f"DECISIONS §83-{n} 을 찾을 수 없다"
    rest = body[m.end():]
    nxt = re.search(r"^#{2,3} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _decisions_83() -> str:
    t = DECISIONS.read_text(encoding="utf-8")
    i = t.find("## 83. ")
    assert i >= 0, (
        "DECISIONS 에 §83(팀 문서 축 대응표)이 없다.\n"
        "  회의록·일지가 저장소 축으로 번역되지 않은 상태다.")
    j = t.find("\n## 84. ", i)
    return t[i:] if j < 0 else t[i:j]


def _classified(sec: str) -> dict[str, list[str]]:
    """표 행에서만 뽑는다. 산문·코드블록의 인용은 세지 않는다."""
    out: dict[str, list[str]] = {}
    for line in sec.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= {"-", ":", " "}:
            continue
        label = re.sub(r"[*`]|\s*\d+건$", "", cells[0]).strip()
        for kind, num in TOKEN.findall(line):
            out.setdefault(label, []).append(f"{kind}-{num}")
    return out


def _flat(d: dict[str, list[str]]) -> list[str]:
    return [v for vs in d.values() for v in vs]


def test_every_meeting_number_is_registered():
    """★ 전건 등재. 하나라도 빠지면 그 항목은 문서 밖에서 자란다."""
    body = _decisions_83()
    got = set(_flat(_classified(_section(body, 3))))
    want = {f"M-{n:02d}" for n in M_RANGE if n not in MISSING_M}
    miss, extra = sorted(want - got), sorted(got - want)
    assert not miss and not extra, (
        "DECISIONS §83-3 결정 대응표가 회의록과 안 맞는다.\n"
        f"  미등재 {len(miss)}건: {miss}\n"
        f"  결번인데 등재 {len(extra)}건: {extra}\n"
        "  새 회의록이 나왔으면 그 번호를 표에 한 줄 더한다(§83-7).")


def test_every_open_item_is_registered():
    body = _decisions_83()
    got = set(_flat(_classified(_section(body, 5))))
    want = {f"P-{n:02d}" for n in P_RANGE if n not in MISSING_P}
    miss, extra = sorted(want - got), sorted(got - want)
    assert not miss and not extra, (
        "DECISIONS §83-5 미결 대응표가 회의록·일지와 안 맞는다.\n"
        f"  미등재 {len(miss)}건: {miss}\n"
        f"  결번인데 등재 {len(extra)}건: {extra}")


def test_no_number_is_classified_twice():
    """한 번호가 두 처리 유형에 있으면 어느 쪽이 정본인지 갈린다."""
    body = _decisions_83()
    bad: list[str] = []
    for n in (3, 5):
        d = _classified(_section(body, n))
        seen: dict[str, str] = {}
        for label, nums in d.items():
            for v in nums:
                if v in seen:
                    bad.append(f"  §83-{n}  {v} — '{seen[v]}' 과 '{label}' 둘 다")
                else:
                    seen[v] = label
    assert not bad, "한 번호가 두 처리 유형에 있다\n" + "\n".join(bad)


def test_plan_rows_the_crosswalk_points_at_exist():
    """★ 참조가 낡는 것이 이 저장소의 두 형태 중 하나다(§78-1)."""
    body = _decisions_83()
    plan = PLAN.read_text(encoding="utf-8")
    rows = {m.group(1) for m in re.finditer(r"^\|\s*(\d+)\s*\|", plan, re.M)}
    bad = [f"  PLAN §1 #{n}" for n in
           sorted({m.group(1) for m in re.finditer(r"PLAN §1 #(\d+)", body)},
                  key=int) if n not in rows]
    assert not bad, (
        "§83 이 가리키는 PLAN 행이 실재하지 않는다\n" + "\n".join(bad))
