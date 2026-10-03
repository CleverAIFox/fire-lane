#!/usr/bin/env python3
"""
constbasis.py — 판정 상수가 **어디서 왔는지** 댈 수 있는가.

    uv run python tools/constbasis.py            대조
    uv run python tools/constbasis.py --list      근거 없는 것만 나열
    uv run python tools/constbasis.py --selftest  판별식이 살아 있나

── 왜 생겼나 (DECISIONS §380) ──────────────────────────────────
2026-10-03 에 폭이 열 배 틀린 자리를 파다가 같은 모양이 셋 나왔다 —

    WMAX_CAP  = 60.0   # 담~담 상한. 15m로 잡으면 대로가 전멸한다
    XSEC_EXCL =  5.0   # 교차로 노드 제외 반경. blob 폭 폭발 방지
    층고 3.3           (`publish_web.py` 의 맨숫자. 주석도 없다)

셋 다 **「제일 큰 경우가 안 죽게」** 정한 수다. 그래서 나머지 전부가 그 문을
무사통과한다. 실측한 교차로 650개 중 **231개(36%)가 `XSEC_EXCL` 보다 크다.**

★ 숫자가 틀렸다는 말이 아니다. **어디서 왔는지 아무도 못 댄다**는 말이다.
  차량 쪽 `height_m: 3.2` 에는 `KFS-1-0073 §3.3` 이 붙어 있다. 같은 저장소
  안에서 어떤 수는 출처를 들고 어떤 수는 안 든다 — 그 차이를 센다.

── 무엇을 근거로 치나 (넷) ─────────────────────────────────────
    ① 문서    `§n` · DECISIONS · PLAN · MASTER — 판단이 어디 적혔나
    ② 규격    KFS- · NFPA · IFC · 소방청 · 국토지리정보원 · 시행령 · 고시
    ③ 유도    주석이 산술을 적는다 (`2.5m + 여유` 꼴)
    ④ 실측    실측 · 쟀다 · 측정 · 조사

★ **값이 옳은가는 안 본다.** `WMAX_CAP` 이 60 이어야 하는지는 이 도구가 모른다.
  드는 것은 「댈 수 있는가」 하나다. 근거를 붙이는 것은 판정을 안 바꾸고,
  값을 고치는 것은 판정을 바꾼다 — 둘은 다른 배치다.

IN    src/firelane/seg/params.py   (**읽기만 한다** — 판정 지문을 안 건드린다)
OUT   없음 (검사)
PARAM CONST_NO_BASIS (래칫. 문턱이 아니라 지금 수다)
밖    **판정 상수의 집 밖은 안 본다.** `publish_web.py` 의 층고 3.3 처럼
      표출 전용 상수는 여기 분모가 아니다 — 그것은 판정에 안 들고,
      이 도구가 드는 물음은 「판정을 떠받치는 수의 출처」다.
      그 셋 밖의 맨숫자를 세는 일은 `widen.py` 가 따로 든다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "firelane" / "seg" / "params.py"

#: 근거 표지 넷. 하나라도 걸리면 「댈 수 있다」로 센다.
BASIS = re.compile(
    r"§\s*\d|DECISIONS|PLAN|MASTER"                       # ① 문서
    r"|KFS-|NFPA|IFC|소방청|소방서|국토지리정보원|시행령|고시|표준"   # ② 규격
    r"|\d+(?:\.\d+)?\s*(?:m|km|분|초)\s*[+×*]"              # ③ 유도
    r"|실측|쟀다|쟀고|측정|조사"                              # ④ 실측
)

#: 출처를 못 대는 판정 상수 수. **문턱이 아니라 지금 수다.**
#: 줄이는 길은 둘 — 근거를 적거나(판정 불변), 값을 재서 고치거나(측정 배치).
CONST_NO_BASIS = 13

RATCHETS = {"CONST_NO_BASIS": "down"}

#: `= ` 뒤가 수 하나인 줄만 본다. 표·튜플·문자열은 상수가 아니라 자료다.
_ASSIGN = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*=\s*(-?\d+(?:\.\d+)?)\s*(#.*)?$")
#: 이어지는 들여쓴 주석. 값 옆 한 줄로 못 적은 사유가 아래 붙는다.
_CONT = re.compile(r"^\s{10,}#")


def scan(text: str) -> list[dict]:
    """상수 이름 → (값, 주석 전문, 근거 있음). 파일을 **고치지 않는다.**"""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = _ASSIGN.match(line)
        if not m:
            continue
        note = (m.group(3) or "").lstrip("# ")
        j = i + 1
        while j < len(lines) and _CONT.match(lines[j]):
            note += " " + lines[j].strip().lstrip("# ")
            j += 1
        out.append({"name": m.group(1), "value": m.group(2),
                    "note": note.strip(), "basis": bool(BASIS.search(note))})
    return out


def ungrounded(rows: list[dict]) -> list[dict]:
    """출처를 못 대는 것들. 주석이 **비어 있어도** 여기 든다."""
    return [r for r in rows if not r["basis"]]


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. 파일이 없으면 `RuntimeError`.

    **0 을 내지 않는다** — 0 은 「전부 근거가 있다」는 뜻이고, 그것을 선언에
    적으면 래칫이 조용히 최대로 조여진다(§313-1 ① 과 같은 족).
    """
    if not PARAMS.exists():
        raise RuntimeError(f"{PARAMS} 가 없다 — 판정 상수의 집이다")
    return {"CONST_NO_BASIS": len(ungrounded(scan(PARAMS.read_text(encoding="utf-8"))))}


def show(rows: list[dict], only_bad: bool) -> int:
    bad = ungrounded(rows)
    print(f"── 판정 상수의 출처  {PARAMS.relative_to(ROOT)}")
    print(f"   수치 상수 {len(rows)} · 댈 수 있음 {len(rows) - len(bad)} · "
          f"**못 댐 {len(bad)}** · 래칫 {CONST_NO_BASIS}")
    print("\n   근거로 치는 것 — ① 문서 §  ② 규격·기관  ③ 산술 유도  ④ 실측\n")
    for r in rows:
        if only_bad and r["basis"]:
            continue
        mark = "  " if r["basis"] else "✗ "
        print(f"   {mark}{r['name']:<16} {r['value']:>8}   {r['note'][:58]}")

    print("\n★ **값이 옳은가는 안 본다.** 드는 것은 「어디서 왔는지 댈 수 있는가」다.")
    print("  근거를 적는 것은 판정을 안 바꾸고, 값을 고치는 것은 바꾼다.")

    if len(bad) > CONST_NO_BASIS:
        print(f"\n✗ 못 대는 상수 {len(bad)} > 래칫 {CONST_NO_BASIS} — **늘었다.**")
        print("  새 상수를 들일 때 출처를 같이 적어라. 안 적으면 영원히 못 적는다.")
        return 1
    if len(bad) < CONST_NO_BASIS:
        print(f"\n✗ 못 대는 상수 {len(bad)} < 래칫 {CONST_NO_BASIS} — "
              "**래칫을 그 수로 내려라.** 안 내리면 다시 는다.")
        return 1
    return 0


def selftest() -> int:
    """★ 판별식이 양방향으로 무는가. 파일 없이 합성 글로 문다."""
    bad = []
    g = scan("A = 1.0  # 근거 없는 수\nB = 2.0  # DECISIONS §12 가 정했다\n")
    if len(g) != 2:
        bad.append(f"상수를 {len(g)}개만 읽었다")
    elif g[0]["basis"] or not g[1]["basis"]:
        bad.append("문서 참조를 근거로 안 친다")

    if not scan("C = 3.2  # KFS-1-0073 §3.3")[0]["basis"]:
        bad.append("규격 번호를 근거로 안 친다")
    if not scan("D = 3.0  # 전폭 2.5m + 여유")[0]["basis"]:
        bad.append("산술 유도를 근거로 안 친다")
    if not scan("E = 5.0  # 교차로 650개를 쟀다")[0]["basis"]:
        bad.append("실측을 근거로 안 친다")
    if scan("F = 60.0  # 15m로 잡으면 대로가 전멸한다")[0]["basis"]:
        bad.append("정책 문장을 근거로 친다 — 그것은 사유지 출처가 아니다")
    if scan("G = 1.0")[0]["basis"]:
        bad.append("주석이 없는 상수를 근거 있다고 한다")

    # 이어지는 들여쓴 주석을 모으는가. 사유가 아래 줄에 있는 꼴이 실재한다.
    two = scan("H = 0.5  # 노드 동일시 반경\n" + " " * 12 + "# MASTER §3 가 정했다\n")
    if not two[0]["basis"]:
        bad.append("아래 줄로 이어진 주석을 안 읽는다")

    # 표·튜플은 상수가 아니라 자료다.
    if scan('I = {"a": 1}\nJ = ("x",)\n'):
        bad.append("표와 튜플을 수치 상수로 센다")
    # 음수와 정수도 수다.
    if len(scan("K = -1\nL = 7\n")) != 2:
        bad.append("음수나 정수를 상수로 안 센다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — 근거 표지 넷 · 정책 문장 거부 · 이어진 주석 · 자료 제외")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="근거 없는 것만")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not PARAMS.exists():
        print(f"✗ {PARAMS} 가 없다 — 판정 상수의 집이다")
        return 2
    return show(scan(PARAMS.read_text(encoding="utf-8")), a.list)


if __name__ == "__main__":
    sys.exit(main())
