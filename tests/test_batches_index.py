"""`docs/batches/` — 지시문 원본의 자리와 인용 규약.  (감사 C · Zm20)

원본은 사용자가 복원해 넣는다(에이전트는 안 쓴다). 이 시험이 보는 것은 셋이다 —
① README 표가 Zm03 ~ Zm20 을 빠짐없이 든다 ② 표의 상태가 실물과 같다
③ DECISIONS 가 「지시문」을 파일 없이 인용하는 줄이 **늘지 않는다**(래칫).

IN    이 파일의 대상 모듈 · 실물
OUT   없음 (검사)
PARAM 없음
밖    **원본의 내용**은 안 본다 — 표 · 파일 · 인용 수만 본다. 원본은 사용자가 복원한다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCHES = ROOT / "docs" / "batches"
README = BATCHES / "README.md"
FIRST, LAST = 3, 23

#: 「지시문」을 가리키면서 `docs/batches/` · 「원본 없음」 · 「요지」 중 아무것도 안 적은 DECISIONS 줄 수.
#: ★ 2026-10-24 (Zm20 · Zm22). **줄이는 쪽으로만 움직인다** — 새 인용은 처음부터 색인을 가리킨다.
#:   Zm22 에서 「요지만 있음」이 정상 상태가 되어(원문을 기다리지 않는다) 표 모양이 바뀌었다.
UNCITED = 77

ROW = re.compile(r"^\|\s*(Zm\d\d)\s*\|\s*(요지만 있음 — DECISIONS (?:§\d+(?: · §\d+)*)|절 없음 — .+?)\s*\|\s*(\S.*?)\s*\|\s*$", re.M)


def test_readme_lists_every_batch_once() -> None:
    rows = ROW.findall(README.read_text(encoding="utf-8"))
    names = [r[0] for r in rows]
    want = [f"Zm{n:02d}" for n in range(FIRST, LAST + 1)]
    assert names == want, f"표가 Zm{FIRST:02d} ~ Zm{LAST:02d} 를 순서대로 한 줄씩 들지 않는다: {names}"


def test_every_cited_section_exists_in_decisions() -> None:
    """표가 가리키는 절 번호는 DECISIONS 에 실재한다 — 가리키는 곳이 죽지 않는다."""
    heads = set(re.findall(r"^## (\d+)\.", (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8"), re.M))
    missing = []
    for name, what, _f in ROW.findall(README.read_text(encoding="utf-8")):
        for n in re.findall(r"§(\d+)", what):
            if n not in heads:
                missing.append(f"{name}: §{n}")
    assert not missing, f"DECISIONS 에 없는 절을 가리킨다: {missing}"


def test_a_listed_file_must_exist_and_an_existing_file_must_be_listed() -> None:
    """원문 칸이 `—` 가 아니면 그 파일이 있어야 하고, 파일이 있으면 표가 가리킨다. 원문이 없는 것이 정상이다."""
    listed = {}
    for name, _what, f in ROW.findall(README.read_text(encoding="utf-8")):
        listed[name] = f
    bad = []
    for name, f in listed.items():
        exists = (BATCHES / f"{name}.md").is_file()
        if f == "—" and exists:
            bad.append(f"{name}: 파일이 있는데 표가 안 가리킨다")
        if f != "—" and not exists:
            bad.append(f"{name}: 표가 {f} 를 가리키는데 파일이 없다")
    assert not bad, "표와 실물이 다르다:\n  " + "\n  ".join(bad)


def test_no_stray_batch_files() -> None:
    """표에 없는 판 이름의 파일이 놓이지 않는다 — 이름이 곧 색인이다."""
    listed = {r[0] for r in ROW.findall(README.read_text(encoding="utf-8"))}
    stray = sorted(p.name for p in BATCHES.glob("*.md") if p.name != "README.md" and p.stem not in listed)
    assert not stray, f"표에 없는 파일: {stray}"


def test_decisions_do_not_cite_the_instruction_without_a_file() -> None:
    n = sum(1 for ln in (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8").splitlines()
            if "지시문" in ln and "docs/batches/" not in ln and "원본 없음" not in ln and "요지" not in ln)
    assert n <= UNCITED, (
        f"파일 없이 「지시문」을 인용한 줄이 {n} 로 늘었다(기록 {UNCITED}) — "
        "`(지시문 docs/batches/Zm19.md)` 로 가리키거나 `(지시문 원본 없음 · Zm19)` 로 없다고 적어라")
    assert n >= UNCITED, f"인용이 {n} 로 줄었다 — UNCITED 를 {n} 으로 내려라(래칫은 내리는 쪽으로만 움직인다)"
