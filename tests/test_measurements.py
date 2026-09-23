#!/usr/bin/env python3
"""
test_measurements.py — 측정 대장(PLAN §1-27)이 형식을 지키는가 (PLAN §13-4 가드 6).

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22 (DECISIONS §218-6). 측정은 강제할 수 없어서 **재기 전에** 물음 · 판정 기준 ·
봉인 자리를 적게 한다. 기준을 재고 나서 적으면 그것은 판정이 아니라 사후 합리화다.

── 대장이 어디 사나 (2026-09-23) ───────────────────────────────
★ 종전에는 `docs/MEASUREMENTS.yaml` 이 대장이었다. **저장소의 문서는 넷이다**
  (MASTER · PLAN · DECISIONS · 기획서). 대장을 PLAN §1-27 표로 옮겼다 — 측정은
  판정을 움직이므로 6족만 §1 에 살고(PLAN §13-2), 「§1 행」 칸이 가리키는 표가
  바로 그 절의 표다. §13 은 「판정을 **안** 움직이는 일」의 정본이라 거기 앉히면
  그 절이 자기 선언을 어긴다.

── 무엇을 보는가 ───────────────────────────────────────────────
  ① 행마다 칸 다섯(측정 · §1 행 · 물음 · 판정 기준 · 봉인 자리)이 다 찼다 · id 가 안 겹친다
  ② 「§1 행」 이 수면 PLAN §1 표에 그 행이 실재한다(행이 지워졌는데 측정이 남으면 운다)
     `—` 는 **PLAN 에 행이 없는 외부 의존**이다(정보공개 청구) — 그것만 면제다
  ③ 오염된 지표를 판정 기준에 되쓰지 않는다(적합에 쓴 지표는 검증 수단이 아니다)
  ④ 대장도 오염 칸도 비지 않았다 — **빈 그물이면 ①②③ 이 전부 조용히 통과한다**

IN    docs/PLAN.md §1-27 · docs/PLAN.md §1
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "PLAN.md"

COLS = ("측정", "§1 행", "물음", "판정 기준", "봉인 자리")
NO_ROW = "—"                       # PLAN 에 행이 없는 외부 의존
_ID = re.compile(r"^`([\w-]+)`$")
_METRIC = re.compile(r"`([a-z][a-z0-9_]+)`")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def ledger_block(text: str) -> str:
    """PLAN §1-27 본문. 절이 사라지면 빈 문자열이 아니라 실패다."""
    m = re.search(r"^### 1-27\.[^\n]*\n(.*?)(?=^#{2,3} )", text, re.M | re.S)
    assert m, ("docs/PLAN.md 에 `### 1-27.` 측정 대장 절이 없다.\n"
               "  절을 되살리거나 이 시험이 보는 자리를 같이 옮긴다(PLAN §13-4 가드 6).")
    return m.group(1)


def ledger_rows(text: str) -> list[dict[str, str]]:
    """대장 표의 행 목록. 첫 칸이 `` `id` `` 인 줄만 행으로 센다."""
    out: list[dict[str, str]] = []
    for line in ledger_block(text).splitlines():
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        hit = _ID.match(cells[0]) if cells else None
        if hit:
            assert len(cells) == len(COLS), (
                f"측정 {hit.group(1)!r} 의 칸이 {len(cells)}개다 — {len(COLS)}개여야 한다 "
                f"({' · '.join(COLS)})")
            row = dict(zip(COLS, cells, strict=True))
            row["측정"] = hit.group(1)          # 백틱을 벗긴 id 가 이 행의 이름이다
            out.append(row)
    return out


def contaminated(text: str) -> set[str]:
    """오염 칸에 적힌 지표 이름. 적합에 쓴 지표는 그 순간부터 검증 수단이 아니다."""
    return {m for line in ledger_block(text).splitlines()
            if line.startswith("★ **오염 칸")
            for m in _METRIC.findall(line)}


def plan_section1_rows(text: str) -> set[int]:
    """PLAN §1 **본표**의 행 번호. 하위 절(§1-23~)은 안 본다 — 거기 표는 다른 표다."""
    lines = text.splitlines()
    start = next(k for k, x in enumerate(lines) if x.startswith("## 1. 남은 일"))
    stop = next(k for k in range(start + 1, len(lines)) if lines[k].startswith("### "))
    return {int(m.group(1)) for x in lines[start:stop]
            if (m := re.match(r"\| (\d+) \|", x))}


def _plan() -> str:
    return PLAN.read_text(encoding="utf-8")


def test_ledger_rows_are_complete():
    """칸 다섯이 다 찼는가 · 측정 id 가 겹치지 않는가."""
    rows = ledger_rows(_plan())
    ids = [r["측정"] for r in rows]
    assert len(ids) == len(set(ids)), f"측정 id 가 겹친다: {sorted(ids)}"
    bad = [f"{r['측정']}: 「{c}」 칸이 비었다 — 재기 **전에** 적는다"
           for r in rows for c in COLS
           if c != "§1 행" and not r[c].replace(NO_ROW, "").strip("` ")]
    bad += [f"{r['측정']}: 「§1 행」 칸이 비었다 — 수를 적거나 `{NO_ROW}` 를 적는다"
            for r in rows if not r["§1 행"]]
    assert not bad, "측정 대장(PLAN §1-27)이 덜 찼다:\n  " + "\n  ".join(bad)


def test_plan_rows_exist():
    """「§1 행」이 PLAN §1 본표에 실재하는가. `—` 는 PLAN 에 행이 없는 외부 의존이다."""
    plan = _plan()
    rows, have = ledger_rows(plan), plan_section1_rows(plan)
    assert have, "PLAN §1 본표에서 행 번호를 하나도 못 읽었다 — 표 파서가 죽었다"
    bad = []
    for r in rows:
        cell = r["§1 행"]
        if cell == NO_ROW:
            continue
        if not cell.isdigit():
            bad.append(f"{r['측정']}: §1 행 {cell!r} 이 수도 `{NO_ROW}` 도 아니다")
        elif int(cell) not in have:
            bad.append(f"{r['측정']}: PLAN §1 에 없는 행 #{cell} 을 잇는다")
    assert not bad, ("측정이 가리키는 §1 행이 어긋난다:\n  " + "\n  ".join(bad)
                     + "\n  행을 지웠으면 측정도 같이 정리한다(PLAN §13-5 규약 4).")


def test_contaminated_metrics_are_not_gates():
    """적합에 쓴 지표를 판정 기준으로 되쓰지 않는가 (MASTER §17)."""
    plan = _plan()
    dirty = contaminated(plan)
    assert dirty, ("오염 칸이 비었다 — 이 검사는 그물이 비면 영원히 통과한다.\n"
                   "  PLAN §1-27 의 `★ **오염 칸` 줄에 지표 이름을 백틱으로 적는다.")
    bad = [(r["측정"], k) for r in ledger_rows(plan) for k in dirty
           if k in r["판정 기준"] or k in r["물음"]]
    assert not bad, (f"오염된 지표를 게이트로 되쓴다: {bad}\n"
                     "  적합(보정)에 한 번 쓴 지표는 그 순간부터 검증 수단이 아니다.")


def test_the_ledger_is_not_empty():
    """카나리아 — 대장이 비면 위 셋이 전부 조용히 통과한다.

    ★ 2026-09-23. 종전 YAML 대장에도 같은 구멍이 있었다. 표를 지우거나 서식을
      바꾸면 파서가 0행을 내고, 0행은 「깨끗함」이 아니라 「아무것도 안 본다」다.
    """
    rows = ledger_rows(_plan())
    assert len(rows) >= 1, ("PLAN §1-27 측정 대장에서 행을 하나도 못 읽었다 — "
                            "표가 비었거나 서식이 바뀌었다.")
    assert any(r["§1 행"] == NO_ROW for r in rows), (
        f"PLAN 에 행이 없는 외부 의존(`{NO_ROW}`)을 담을 자리가 사라졌다 — "
        "일방통행 정보공개 청구가 그것이다(DECISIONS §218-6).")


# ── 검사가 무는가 ──────────────────────────────────────────────

def test_ledger_parser_bites():
    """덜 찬 칸 · 없는 §1 행 · 오염 지표 되쓰기가 각각 잡힌다."""
    fake = (
        "## 1. 남은 일 — 1행\n"
        "| # | 항목 |\n"
        "| 4 | D-25 레이저 실측 |\n"
        "\n"
        "### 1-27. 측정 대장\n"
        "| 측정 | §1 행 | 물음 | 판정 기준 | 봉인 자리 |\n"
        "|---|---|---|---|---|\n"
        "| `ok-one` | 4 | 묻는다 | 0 이면 유지 | data/x.csv |\n"
        "| `no-row` | 99 | 묻는다 | 0 이면 유지 | data/y.csv |\n"
        "| `dirty` | — | 묻는다 | `nfa_compare_abs_dev` 가 줄면 통과 | data/z.csv |\n"
        "★ **오염 칸 — `nfa_compare_abs_dev`.** 적합에 썼다\n"
        "\n"
        "## 2. 다음\n")
    rows = ledger_rows(fake)
    assert [r["측정"] for r in rows] == ["ok-one", "no-row", "dirty"], rows
    assert contaminated(fake) == {"nfa_compare_abs_dev"}, contaminated(fake)
    assert plan_section1_rows(fake) == {4}, plan_section1_rows(fake)
    assert 99 not in plan_section1_rows(fake), "없는 §1 행이 안 드러난다"
    dirty = [r["측정"] for r in rows
             if any(k in r["판정 기준"] for k in contaminated(fake))]
    assert dirty == ["dirty"], dirty
