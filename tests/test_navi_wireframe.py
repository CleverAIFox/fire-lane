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

#: 와이어프레임에 있었으나 **그 화면이 없어진** 장. 사유를 적는다 — 번호를
#: 그냥 지우면 「왜 없어졌나」가 사라지고, 다음 사람이 다시 그린다.
RETIRED_WF = {
    "01": "출동 차량 선택 — 기사가 차를 고르는 화면이었다. 차량은 관제가 "
          "정해서 지령에 싣는다(DECISIONS §400). 화면째 지웠다",
}

#: 신호가 없어 시연 막대가 넣는 상태. 늘면 여기와 status.ts 를 같이 고친다
#: ★ 2026-09-24 (PLAN §13 W13-2). `gpsWeak` 를 뺐다 — **신호가 생겼다.**
#:   `Fix.accuracy` 를 뚫고 `gps.ts` 가 `coords.accuracy` 를 넘기며
#:   `deriveStatus` 가 `GPS_WEAK_M` 으로 가른다. 종전에는 정확도를 받을
#:   타입조차 없어 50m 로 흔들려도 초록 「안전 경로 안내중」 이었다.
INJECTED = {"offline", "restored", "dataDelayed", "serviceError"}


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
    missing = sorted(WIREFRAME - got - set(RETIRED_WF))
    extra = sorted(got - WIREFRAME)
    assert not missing, (
        f"와이어프레임에 있는데 코드에 자리가 없는 장: {missing}\n"
        "  패널이면 `data-wf=\"번호\"`, 주행 상태면 `domain/status.ts` 의 `wf: [...]` 에 적는다.")
    # ★ 폐지한 장이 **되살아나면** 운다. 사유를 적어 지웠는데 코드가 다시
    #   그리면 그 사유가 거짓이 된 것이고, 사람이 둘 중 하나를 골라야 한다.
    back = sorted(set(RETIRED_WF) & got)
    assert not back, (
        f"폐지한 장이 코드에 돌아왔다: {back}\n"
        + "\n".join(f"  {k} — {RETIRED_WF[k]}" for k in back))
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


def test_the_two_honest_lines_moved_and_are_still_reachable():
    """판정이 **무엇을 안 보는지**가 아직 화면에서 열리는가.  (§86-5 · §441)

    ── 왜 묻는 자리가 바뀌었나 (2026-10-09) ───────────────────
    종전 이름은 `test_bottleneck_keeps_the_two_honest_lines` 였고
    `BottleneckPanel.tsx` 안에서 두 문장을 찾았다. 행이 화면의 설명을 전부
    걷으라고 했고, **걷되 사용 설명서로 보냈다**(§441-1 · §441-2).

    ★ 뜻은 하나도 안 바뀌었다 — 「무엇을 안 보는지가 사라지면 화면이 확정처럼
      읽힌다」. **묻는 자리만 따라간다.** 그리고 하나를 더 문다 —
      옮긴 곳이 화면에서 **안 열리면 사라진 것과 같다.**

    ★ 글자를 그대로 대지 않는다. 옮기면서 세 곳에 조금씩 다르던 문장을 하나로
      합쳤다(족 2). 그래서 **낱말**로 댄다 — 무엇을 안 보는지가 남았는가.
    """
    man = (SRC / "ui" / "Manual.tsx").read_text(encoding="utf-8")
    for need in ("실시간 주정차", "공사", "회전", "높이", "미검증"):
        assert need in man, (
            f"「읽는 법」에서 「{need}」 가 사라졌다.\n"
            "  판정이 무엇을 안 보는지 남기는 자리다(DECISIONS §86-5 · §441).")
    for app in ("OpsApp.tsx", "App.tsx"):
        src = (SRC / app).read_text(encoding="utf-8")
        if "<ManualSheet" not in src:
            continue
        assert "<ManualButton" in src, f"{app} 가 시트만 두고 **여는 단추가 없다**(§441-3)"
        break
    else:
        raise AssertionError("어느 화면도 「읽는 법」을 안 띄운다 — 옮긴 고지가 안 열린다(§441-3)")


def test_the_injected_badge_reads_the_fact_not_the_table():
    """★ 2026-09-24 (PLAN §13 W13-3). 「시연」 표지가 **정적 표**를 보고 있었다.

    `TopBar` 가 `s.injected`(= `STATUS[key].injected`) 를 봤는데 그 칸이 붙은
    것은 18갈래 중 넷뿐이고, 시연 막대는 **18갈래 전부**를 주입할 수 있다.
    `arrived` 를 주입하면 표지 없이 「도착」 이 떴다 — 아직 달리는 중인데.
    표지는 표가 아니라 **실제 주입 여부**를 봐야 한다.
    """
    top = (ROOT / "web/navi/src/ui/TopBar.tsx").read_text(encoding="utf-8")
    assert "{p.injected &&" in top, (
        "「시연」 표지가 주입 **사실**(props)을 안 본다.\n"
        "  `s.injected`(정적 표의 칸)로 되돌아갔으면 주입 18갈래 중 넷만 표지가 붙는다.")
    assert "{s.injected &&" not in top, "옛 판정이 남아 있다"

    app = (ROOT / "web/navi/src/App.tsx").read_text(encoding="utf-8")
    assert "injected={injected != null}" in app, (
        "App 이 상단바에 주입 사실을 안 넘긴다 — 표지가 영원히 안 붙는다")


def test_the_dev_bar_is_off_unless_asked():
    """★ 2026-09-24 (PLAN §13 W13-1). 시연 막대가 배포본에서 **기본 켜짐**이었다.

    `?dev=0` 을 명시하지 않으면 항상 켜졌고, `web/index.html` 의 내비 링크에
    그 인자가 없다. 운전석에서 손이 스치면 ▶ 가 눌려 **모의 주행이 실제 GPS 를
    대체한다** — 화면의 차가 운전자가 아니게 된다.

    ★ 2026-10-04 (§386). 판정이 `domain/handoff.ts` 로 옮겨갔다 — 같은 물음을
    `App.tsx` 안에서 네 번 따로 읽던 것을 한 자리로 모았다. 그래서 여기서
    보는 자리도 옮긴다. **같은 글자를 두 집에 적지 않는다.**
    """
    hand = (ROOT / "web/navi/src/domain/handoff.ts").read_text(encoding="utf-8")
    for flag in ("dev", "demo"):
        m = re.search(rf'get\("{flag}"\)\s*(===|!==)\s*"([01])"', hand)
        assert m, f"`{flag}` 판정식을 못 찾았다 — 이름이 바뀌었으면 여기도 옮겨라"
        assert (m.group(1), m.group(2)) == ("===", "1"), (
            f"`{flag}` 가 `{m.group(1)} \"{m.group(2)}\"` 로 켜진다 — "
            "켜는 쪽을 명시하게 `=== \"1\"` 이어야 한다.\n"
            "  기본 켜짐이면 배포본이 시연 막대를 달고 나간다.")

    app = (ROOT / "web/navi/src/App.tsx").read_text(encoding="utf-8")
    assert "readHandoff(location.search)" in app, (
        "App 이 지령을 그 자리에서 안 읽는다 — 깃발 판정이 다시 흩어졌다")
    assert 'get("dev")' not in app and 'get("incident")' not in app, (
        "App 이 질의 문자열을 **다시 직접** 읽는다. 물음의 집은 `handoff.ts` 다")


def test_the_driver_picks_nothing_at_all():
    """★ 2026-10-05 (DECISIONS §400). 이 내비는 **완전히 수동이다.**

    종전 이름은 `…cannot_pick_a_destination_once_dispatched` 였고 「지령이
    **왔으면** 못 고른다」를 물었다. 그 물음은 「지령이 없으면 고른다」를
    품는다 — 사람이 그 전제를 잘랐다. 그래서 묻는 것이 바뀌었다:
    **묶였는가가 아니라 없는가.** 조건부로 묶는 것은 조건이 틀리면 열리고,
    없는 것은 틀릴 조건이 없다.

    ★ 이 시험은 두 번 제가 결함을 못 박았다 — §393 에서는 「손만 묶는 모양」을
      옳다고 단언했고, 그 전에는 `onSwap` 을 아예 안 봤다. **강제자가 틀린
      모양을 단언하면 그 관문은 지키는 것이 아니라 가둔다.**
    """
    app = (ROOT / "web/navi/src/App.tsx").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in app.splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))

    for gone in ("DispatchPanel.tsx", "SearchPanel.tsx", "VehiclePicker.tsx"):
        assert not (SRC / "ui" / gone).exists(), f"{gone} 가 살아 있다 — 고르는 화면이 돌아왔다"

    for gone in ("canPickDestination", "editHands", "setArmed"):
        assert gone not in code, f"{gone} 는 「고를 수 있는 경우」를 전제한다"

    scr = (SRC / "app" / "useScreens.ts").read_text(encoding="utf-8")
    assert '"wait" | "brief" | "drive"' in scr, "화면 갈래가 셋이 아니다"
    for gone in ("dispatch", "search", "vehicle", "compare"):
        assert f'"{gone}"' not in scr, f"화면 {gone} 는 고르는 자리였다"

    # ★ 목적지와 차량을 **놓는** 자리는 남되 각각 하나다 — 기계가 지령을
    #   적용하는 손이고, 둘이 되는 순간 하나는 사람이 부르는 것이다.
    for once in ("n.setDestAt(", "fleet.select("):
        assert code.count(once) == 1, f"{once} 가 {code.count(once)}곳이다 — 하나여야 한다"

    assert "onSwitchRoute={undefined}" in code, "주행 중에 경로를 바꿀 수 있다"
