#!/usr/bin/env python3
"""
toolclass.py — **도구가 어느 부류인가.** 관문은 도출하고 나머지만 선언한다.

    uv run python tools/toolclass.py            판정 (verify.sh · CI)
    uv run python tools/toolclass.py --table    도구마다 부류와 그 근거
    uv run python tools/toolclass.py --undeclared  선언이 없는 것만
    uv run python tools/toolclass.py --selftest  ★ 판별식이 살아 있나

── 왜 생겼나  (PLAN #157 · DECISIONS §398) ─────────────────────
도구가 139개다. 그 안에는 성질이 아주 다른 둘이 섞여 있다 —

    판정·데이터를 지키는 것        `docseal` · `widthcross` · `scopecheck`
    **우리가 일하는 방식 때문에 있는 것**  `fl.sh` · `inbox_fl.sh` · `tidy.py`

뒤쪽은 WSL 다운로드 폴더에서 패치 zip 을 주고받고 기계 둘을 오가는
**이 저장소만의 배달 절차** 때문에 존재한다. 산출물에 한 바이트도 안 닿는다.
둘을 안 가르면 「도구가 126개」가 「판정에 126개가 걸려 있다」로 읽히고,
그 수로는 **무엇을 흔들어 봐야 하는지**도 못 고른다.

── 관문은 **도출한다**  (이 도구의 핵심) ───────────────────────
목록을 손으로 적으면 도구가 늘 때마다 빠진다 — 이 저장소가 세 번 배운
꼴이다(§285-2 · §284-4 · §286). 「관문인가」는 물어볼 데가 있다:

    `tools/verify.sh` 가 부르는가       →  관문
    `.github/workflows/*.yml` 이 부르는가 →  관문

그래서 **139 중 관문은 선언이 필요 없다.** 나머지만 머리말에 적는다 —

    부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다
    부류  절차   배치·위생. **산출물에 안 닿는다** — 우리 일하는 방식 때문에 있다
    부류  생산   산출물을 만든다. 파이프라인 · 발행 · 그림 · 문서 생성

★ **어긋나면 운다.** 관문인데 `부류 절차` 라고 적으면 둘 중 하나가 틀렸다.
  도출이 이기지 않는다 — 사람이 고를 때까지 빨강이다.

IN    tools/*.py · tools/*.sh (머리말) · tools/verify.sh · .github/workflows/*.yml
OUT   표준출력 (판정) · `classify()` (다른 도구가 부른다)
PARAM VOCAB · UNDECLARED
밖    **부류가 옳은가는 안 본다.** `fl.sh` 를 「생산」이라 적어도 통과한다 —
      이 검사가 드는 것은 「적혀 있는가」와 「도출과 안 어긋나는가」 둘이다.
      **도구가 필요한가도 안 본다** — 그것은 `tools/deadcheck.py` 소관이다.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
VERIFY = TOOLS / "verify.sh"
FLOWS = ROOT / ".github" / "workflows"

#: 부류 어휘. **정본은 여기 하나다** — 머리말은 이 낱말만 쓴다.
VOCAB: dict[str, str] = {
    "관문": "verify.sh · CI 가 돌린다. 빨강이 배치를 막는다 (도출한다 — 안 적는다)",
    "조사": "사람이 손으로 돌린다. 수를 내고 멈춘다",
    "절차": "배치 · 위생. **산출물에 안 닿는다** — 우리 일하는 방식 때문에 있다",
    "생산": "산출물을 만든다. 파이프라인 · 발행 · 그림 · 문서 생성",
}
DECLARABLE = tuple(k for k in VOCAB if k != "관문")

#: 선언이 없는 **비관문** 도구 수. **내려가는 쪽으로만.**
UNDECLARED = 0
RATCHETS = {"UNDECLARED": "down"}

# ★ 셸은 머리 **주석 블록**에 적는다 — `# 부류  절차`. 접두를 안 보면
#   셸 도구 여섯이 통째로 「선언 없음」이 된다(처음 판이 그랬다).
# ★ **들여쓴 줄은 선언이 아니다.** 허용했더니 이 파일의 어휘 **설명**
#   (`    부류  조사   …`)이 선언으로 읽혀 제 관문에 걸렸다. 0열만 선언이다.
_DECL = re.compile(r"^(?:#\s*)?부류\s+(\S+)", re.M)


def tools() -> list[Path]:
    return sorted(p for p in TOOLS.rglob("*")
                  if p.suffix in (".py", ".sh") and "__pycache__" not in p.parts)


def _code(src: str) -> str:
    """주석을 뺀 줄만. **언급은 호출이 아니다.**

    ★ 2026-10-05 (DECISIONS §398-3 ③). 처음 판은 파일 글자 전체를 봤다. 그래서
      `# ci-exempt: tools/mutate.py …` 한 줄이 그 도구를 **관문으로 만들었고**,
      `fl.sh` 는 안내 문구에 이름이 적혔다는 이유로 관문이 됐다.
      §279-1 이 같은 것을 적었다 — 「경로 필터는 방아쇠지 호출이 아니다」.
    """
    return "\n".join(ln for ln in src.split("\n") if not ln.lstrip().startswith("#"))


def _callers() -> str:
    """관문 여부를 묻는 자리 — `verify.sh` 와 워크플로. **주석은 뺀다.**"""
    out = [_code(VERIFY.read_text(encoding="utf-8"))] if VERIFY.exists() else []
    if FLOWS.is_dir():
        out += [_code(f.read_text(encoding="utf-8")) for f in sorted(FLOWS.glob("*.yml"))]
    return "\n".join(out)


def declared(p: Path) -> str | None:
    """머리말의 `부류` 선언. 없으면 `None`, 어휘 밖이면 그 낱말 그대로."""
    m = _DECL.search(p.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def classify() -> dict[str, dict]:
    """도구 → `{부류, 도출, 선언}`. **다른 도구가 부르는 자리다.**"""
    text = _callers()
    out: dict[str, dict] = {}
    for p in tools():
        rel = p.relative_to(ROOT).as_posix()
        gate = rel in text or p.name == VERIFY.name
        dec = declared(p)
        out[rel] = {"부류": "관문" if gate else dec, "도출": gate, "선언": dec}
    return out


def judge(rows: dict[str, dict]) -> tuple[list[str], list[str]]:
    """`(결함, 선언 없음)`. **판정만 한다** — 고치지 않는다."""
    bad, none = [], []
    for rel, r in rows.items():
        dec, gate = r["선언"], r["도출"]
        if dec is not None and dec not in VOCAB:
            bad.append(f"{rel}  어휘 밖 부류 「{dec}」 — {' · '.join(VOCAB)}")
        elif gate and dec is not None and dec != "관문":
            bad.append(f"{rel}  verify · CI 가 부르는데 「{dec}」 라고 적었다 "
                       "— 둘 중 하나가 틀렸다. 도출이 이기지 않는다")
        elif not gate and dec == "관문":
            bad.append(f"{rel}  「관문」이라 적었는데 verify · CI 어디서도 안 부른다")
        elif not gate and dec is None:
            none.append(rel)
    return bad, none


def ratchet_values() -> dict[str, int]:
    """선언 없는 비관문 수. **0 을 내지 않는다** — 수집이 비면 터진다."""
    rows = classify()
    if not rows:
        raise RuntimeError("도구를 하나도 못 찾았다 — 수집이 죽었다")
    return {"UNDECLARED": len(judge(rows)[1])}


def selftest() -> int:
    fails: list[str] = []
    rows = classify()
    if len(rows) < 100:
        fails.append(f"도구를 {len(rows)}개만 찾았다 — 수집이 좁다")
    if not any(r["도출"] for r in rows.values()):
        fails.append("관문을 하나도 도출 못 했다 — 부르는 자리를 못 읽는다")
    if all(r["도출"] for r in rows.values()):
        fails.append("전부 관문이다 — 도출이 늘 참이면 가르는 것이 없다")

    # ★ 판별식을 **꺼냈다**(§17-0) — 합성 행으로 네 갈래를 민다
    probe = {
        "a": {"선언": "없는낱말", "도출": False, "부류": None},
        "b": {"선언": "절차", "도출": True, "부류": "관문"},
        "c": {"선언": "관문", "도출": False, "부류": "관문"},
        "d": {"선언": None, "도출": False, "부류": None},
        "e": {"선언": "조사", "도출": False, "부류": "조사"},
    }
    bad, none = judge(probe)
    want = {"a": "어휘 밖", "b": "둘 중 하나가 틀렸다", "c": "안 부른다"}
    for k, frag in want.items():
        if not any(h.startswith(k) and frag in h for h in bad):
            fails.append(f"합성 {k} 를 안 문다 — {frag}")
    if none != ["d"]:
        fails.append(f"선언 없음이 ['d'] 가 아니다 — {none}")
    if any(h.startswith("e") for h in bad):
        fails.append("멀쩡한 선언에 운다")

    # ★ **언급은 호출이 아니다** — 주석 한 줄이 도구를 관문으로 만들면 안 된다
    if "tools/x.py" in _code("# ci-exempt: tools/x.py 사유\nstep a uv run python tools/y.py\n"):
        fails.append("주석을 호출로 읽는다 — §279-1 과 같은 병이다")
    if "tools/y.py" not in _code("# 주석\nstep a uv run python tools/y.py\n"):
        fails.append("주석을 빼면서 진짜 호출까지 지운다")

    # ★ 빈 그물 — 어휘가 비면 무엇을 적어도 통과한다
    if not VOCAB or "관문" not in VOCAB:
        fails.append("어휘가 비었거나 관문이 없다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 10")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="도구가 어느 부류인가")
    ap.add_argument("--table", action="store_true", help="도구마다 부류와 근거")
    ap.add_argument("--undeclared", action="store_true", help="선언 없는 것만")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    rows = classify()
    bad, none = judge(rows)
    if a.table:
        for rel, r in rows.items():
            src = "도출" if r["도출"] else ("선언" if r["선언"] else "—")
            print(f"  {r['부류'] or '(없음)':<6} {src:<4} {rel}")
        return 0
    if a.undeclared:
        for rel in none:
            print(f"  {rel}")
        return 0

    tally: dict[str, int] = {}
    for r in rows.values():
        tally[r["부류"] or "(없음)"] = tally.get(r["부류"] or "(없음)", 0) + 1
    print(f"── 도구 {len(rows)} · 부류")
    for k in (*VOCAB, "(없음)"):
        if k in tally:
            print(f"    {k:<6} {tally[k]:>4}   {VOCAB.get(k, '머리말에 `부류` 가 없다')}")
    for b in bad:
        print(f"  ✗ {b}")
    if bad:
        print("\n★ 도출과 선언이 어긋난다. **도출이 이기지 않는다** — 사람이 고른다.")
        return len(bad)
    print(f"\n✓ 어긋남 0 · 선언 없는 비관문 {len(none)} = 래칫 {UNDECLARED}"
          if len(none) == UNDECLARED else
          f"\n★ 선언 없는 비관문 {len(none)} · 래칫 {UNDECLARED}"
          " — `ratchet.py` 가 든다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
