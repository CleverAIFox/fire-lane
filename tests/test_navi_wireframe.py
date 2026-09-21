#!/usr/bin/env python3
"""
test_navi_wireframe.py — **지혜님 와이어프레임 28장이 전부 코드에 자리가 있는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-21 (DECISIONS §211). 와이어프레임 09-21 판 28장을 내비에 반영했다.
18장은 화면이 아니라 **상태**라 `domain/status.ts` 의 표 한 줄씩이고,
나머지는 패널 · 칩이다. 반영이 끝났다고 말하려면 28장 각각이 **어디에
있는지** 대야 한다 — 사람이 눈으로 세면 한 장은 빠진다.

★ 화면마다 `data-wf="번호"` 를 달거나(패널 · 칩), 상태표에 `wf: [...]` 로
  적는다. 이 검사는 그 번호를 모아 와이어프레임 목록과 **양방향**으로 댄다 —
  빠진 장도, 목록에 없는 번호(오타 · 폐기된 장)도 운다.

★ 와이어프레임이 바뀌면 `WIREFRAME` 을 고친다. 그것이 곧 「새 판이 왔다」는
  기록이다. 22 는 원본에 없다(20 → 21 → 23) — 결번을 지어내지 않는다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 28장 전부 코드에 번호가 있는가 · 없는 번호를 코드가 쓰지 않는가
    2. 상태표의 키가 전부 시연 순서(`STATUS_ORDER`)에 있는가 — 빠지면 검수 때 못 넘겨 본다
    3. 신호가 없는 상태에 `injected: true` 가 붙어 있는가 — 주입인 줄 모르고 보면 거짓 화면이다
    4. 병목 상세에 정직함의 두 줄이 살아 있는가 — 09-05 판 우측 패널에서 옮겨 왔다
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "navi" / "src"
STATUS = SRC / "domain" / "status.ts"

#: 와이어프레임 09-21 판 파일 번호 (지혜님, 2026-09-21 17:30~17:32)
WIREFRAME = {
    "00", "01", "02", "03", "03A", "03B", "04", "04.5", "05", "06", "07", "08",
    "09", "09A", "10", "11", "12", "13", "14", "15", "16", "17", "17A",
    "18", "19", "20", "21", "23",
}

#: 신호가 없어 시연 막대가 넣는 상태. 늘면 여기와 status.ts 를 같이 고친다
INJECTED = {"gpsWeak", "offline", "restored", "dataDelayed", "serviceError"}


def _src_files() -> list[Path]:
    fs = sorted(p for p in SRC.rglob("*.ts*") if p.is_file())
    assert len(fs) > 20, f"내비 소스가 {len(fs)}개뿐이다 — 이 검사가 빈 그물이 됐다"
    return fs


def _code_wf() -> set[str]:
    """`wf` 가 적힌 **줄**에서 따옴표 친 번호를 전부 모은다.

    ★ 줄 단위로 본다. `wf: ["03", "03A"]` · `wf="00"` · `data-wf="04"` ·
      `wf: kind === "arrival" ? "23" : "21"` 이 모양이 다 달라서, 모양마다
      정규식을 두면 새 모양 하나에 조용히 빠진다(처음 짰을 때 00·01·02·21 이
      그렇게 빠졌다). 번호 꼴(`"12"` · `"04.5"` · `"17A"`)만 따옴표로 거른다.
    """
    out: set[str] = set()
    num = re.compile(r'"([0-9]{2}(?:\.[0-9])?[A-Z]?)"')
    for p in _src_files():
        for line in p.read_text(encoding="utf-8").splitlines():
            if re.search(r"\b(?:data-)?wf\b\s*[:=]", line):
                out |= set(num.findall(line))
    return out


def test_every_wireframe_screen_has_a_home():
    got = _code_wf()
    assert got, "코드에서 와이어프레임 번호를 하나도 못 찾았다 — 추출이 죽었다"
    missing = sorted(WIREFRAME - got)
    extra = sorted(got - WIREFRAME)
    assert not missing, (
        f"와이어프레임에 있는데 코드에 자리가 없는 장: {missing}\n"
        "  패널이면 `data-wf=\"번호\"`, 주행 상태면 `domain/status.ts` 의 `wf: [...]` 에 적는다.")
    assert not extra, (
        f"와이어프레임 09-21 판에 없는 번호를 코드가 쓴다: {extra}\n"
        "  오타이거나 폐기된 장이다. 새 판이 왔으면 이 파일의 `WIREFRAME` 부터 고친다.")


def _status_keys() -> tuple[list[str], list[str], str]:
    s = STATUS.read_text(encoding="utf-8")
    body = s[s.index("export const STATUS:"):s.index("export const STATUS_ORDER")]
    keys = re.findall(r"^  (\w+): \{", body, re.M)
    order_blk = s[s.index("export const STATUS_ORDER"):]
    order_blk = order_blk[:order_blk.index("];")]
    order = re.findall(r'"(\w+)"', order_blk)
    return keys, order, body


def test_status_table_is_fully_walkable():
    keys, order, _ = _status_keys()
    assert len(keys) >= 16, f"상태표 키가 {len(keys)}개다 — 추출이 죽었다"
    assert sorted(keys) == sorted(order), (
        f"상태표와 시연 순서가 갈렸다 — 표에만 {sorted(set(keys) - set(order))} · "
        f"순서에만 {sorted(set(order) - set(keys))}\n"
        "  시연 막대로 못 넘기는 상태는 검수에서 빠진다.")


def test_signalless_states_are_marked_injected():
    """신호가 없는 상태는 `injected: true` — 상단바가 「시연」 표지를 단다."""
    keys, _, body = _status_keys()
    for k in keys:
        blk = body[body.index(f"  {k}: {{"):]
        blk = blk[:blk.index("},") + 2]
        marked = "injected: true" in blk
        assert marked == (k in INJECTED), (
            f"`{k}` 의 주입 표지가 선언과 다르다 (표지 {marked}, 선언 {k in INJECTED}).\n"
            "  신호가 생겼으면 주입을 떼고 이 파일의 `INJECTED` 에서도 뺀다.\n"
            "  신호가 없는데 표지가 없으면 시연 화면이 실제 상태처럼 보인다.")


def test_bottleneck_keeps_the_two_honest_lines():
    s = (SRC / "ui" / "BottleneckPanel.tsx").read_text(encoding="utf-8")
    for need in ("실시간 주정차 · 공사 · 이동 장애물은 반영되지 않았습니다",
                 "회전 및 높이 통과 여부는 판정하지 않습니다"):
        assert need in s, (
            f"병목 상세에서 「{need}」 가 사라졌다.\n"
            "  판정이 무엇을 안 보는지 화면에 남기는 유일한 장치다(DECISIONS §86-5).")
