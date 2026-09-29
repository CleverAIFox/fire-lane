#!/usr/bin/env python3
"""
unusedcheck.py — **미배선 자료가 몇이고, 늘지 않는가.** 래칫.

    uv run python tools/unusedcheck.py
    uv run python tools/unusedcheck.py --selftest

── 왜 생겼나 (DECISIONS §317) ──────────────────────────────────
2026-09-30. 「미활용 25」가 한 달 동안 25 였다. 대장 검사는 그 수를 **찍기만**
했고 목표가 없었다 — 목표 없는 수는 아무도 안 본다.

수를 뜯어 보니 25 가 **셋으로 쪼개졌다** —

    ①  9  `raw_only` 인데 `feeds` 가 비어 미사용으로 뒤집혔다
          → `grade()` 의 갈래 순서 결함. 그 함수의 주석이 이미 경고하고
            있었는데 코드 순서로는 안 지켰다(§317).
    ②  4  「참조용 · 대조용 · 근거 자료」 — **소비자가 사람**이고 `feeds` 가
          생길 일이 없다. 0 이 되면 안 되는 것을 0 으로 가는 수에 섞었다.
    ③ 12  「미투입 · 미배선」 — **이것만 진짜 미배선**이고, 내릴 대상이다.

★ 그래서 이 도구가 무는 것은 ③ **하나**다. 래칫이라 늘면 운다. 그리고
  줄었으면 선언을 같이 내려야 한다 — 안 내리면 래칫이 낡고, **낡은 래칫은
  초록으로 위장한다**(`sizecheck` 머리말이 적은 그 병).

★ 어휘는 새로 만들지 않았다. `feeds_why` 에 사람이 이미 쓰던 표기를 선언으로
  올렸고(`firelane.ledger.REFERENCE_WHY` · `PENDING_WHY`), 그것이 정본이다.

IN    sources.yaml (`firelane.ledger` 를 통해서만 읽는다)
OUT   표준출력 (판정)
PARAM PENDING_MAX (래칫)
밖    **배선을 안 한다.** 어느 자료를 언제 붙일지는 PLAN 이 든다.
      **은퇴를 안 시킨다.** `retired:` 로 내리는 것은 사람의 판단이고
      `firelane.lake gate` 가 그 뒤를 든다.
      **참조용이 옳은 분류인가는 안 본다.** 낱말을 고른 것은 사람이고,
      여기가 드는 것은 「낱말이 선언된 것인가」와 「③이 늘었는가」다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from firelane import ledger  # noqa: E402 — 위 경로 삽입 뒤여야 한다

#: 미배선 자료 수. **오늘 값에서 시작해 내린다.**
#:
#: ★ 이력 — 09-30 §317 첫 실측 12(종전 표기 25 중 아홉은 등급 결함 · 넷은 영구 참조).
PENDING_MAX = 12

RATCHETS = {"PENDING_MAX": "down"}


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. **판정은 안 한다**(`check()` 소관)."""
    return {"PENDING_MAX": len(pending())}


def pending() -> dict[str, str]:
    """미배선 자료 → 그 사유의 첫 줄. `grade()` 가 정본이다."""
    out: dict[str, str] = {}
    for k, e in (ledger.load().get("datasets") or {}).items():
        e = e or {}
        if ledger.grade(e) != "unused":
            continue
        w = str(e.get("feeds_why") or "").lstrip("★ *·\n").split("\n", 1)[0]
        out[k] = w or "— 사유 없음"
    return dict(sorted(out.items()))


def undeclared() -> dict[str, str]:
    """`unused` 인데 선언 낱말이 없는 것. **`check_entry` 와 같은 판정을 쓴다.**"""
    out: dict[str, str] = {}
    for k, e in (ledger.load().get("datasets") or {}).items():
        e = e or {}
        if ledger.grade(e) == "unused" and ledger.why_token(e) is None:
            out[k] = str(e.get("feeds_why") or "")[:60] or "(없음)"
    return out


def check() -> int:
    got = pending()
    bad = undeclared()
    tally = ledger.summary()
    print(f"활용도 — {tally}")
    print(f"\n미배선 {len(got)} · 래칫 {PENDING_MAX}")
    for k, w in got.items():
        print(f"  · {k:<24s} {w[:70]}")

    rc = 0
    if bad:
        print(f"\n✗ 선언 낱말이 없는 항목 {len(bad)}")
        for k, w in bad.items():
            print(f"    {k} — {w}")
        print(f"  `feeds_why` 는 {' · '.join(ledger.REFERENCE_WHY + ledger.PENDING_WHY)}")
        print("  중 하나로 시작한다. 산문으로 흐리면 영구 참조와 미배선이 한 수에 섞인다.")
        rc = 1
    if len(got) > PENDING_MAX:
        print(f"\n✗ 미배선 {len(got)} > 래칫 {PENDING_MAX} — **늘었다.**")
        print("  새로 반입한 자료에 소비자가 없다. 붙이거나 `retired:` 로 내려라.")
        rc = 1
    elif len(got) < PENDING_MAX:
        print(f"\n✗ 미배선 {len(got)} < 래칫 {PENDING_MAX} — "
              "**래칫을 그 수로 내려라.** 안 내리면 다시 는다.")
        print("  uv run python tools/ratchet.py --write")
        rc = 1
    if rc == 0:
        print("\n✓ 미배선이 래칫과 같다")
    return rc


def selftest() -> int:
    """★ 셋을 실제로 가르는가. 대장을 안 읽고 합성 항목으로 본다."""
    fails = []
    cases = (
        ({"kind": "csv_table", "feeds": ["src/firelane/normalize_raw.py"],
          "feeds_why": "대조용 — 관할 654 를 API 실측과 맞췄다"}, "reference",
         "영구 참조를 미배선으로 센다 — 그 수는 영원히 0 이 못 된다"),
        ({"kind": "csv_table", "feeds": [], "feeds_why": "미배선 — 지오코딩 필요"},
         "unused", "미배선을 미배선이라 안 한다"),
        ({"kind": "raw_only", "feeds": None, "feeds_why": "참조용"}, "reference",
         "`raw_only` 인데 feeds 가 비면 미사용으로 뒤집는다 — §317 의 그 결함이다"),
        ({"kind": "csv_table", "feeds": ["src/firelane/seg/geom.py"]}, "active",
         "소비자가 있는데 활성이 아니다"),
        ({"kind": "csv_table", "feeds": [], "feeds_why": "안 쓴다"}, "unused",
         "선언 낱말 없는 산문을 등급에 반영한다 — 낱말은 등급이 아니라 검사가 든다"),
    )
    for e, want, why in cases:
        if ledger.grade(e) != want:
            fails.append(f"{why} (실측 {ledger.grade(e)})")

    # ★ 낱말 판별식. `★` 장식을 건너뛰는가 · 본문의 우연한 낱말을 안 집는가.
    if ledger.why_token({"feeds_why": "★ 미투입 — 후보다"}) != "미투입":
        fails.append("`★` 장식 뒤의 낱말을 못 읽는다")
    if ledger.why_token({"feeds_why": "쓸 데가 없다\\n참조용으로 볼 수도"}) is not None:
        fails.append("첫 줄 밖의 낱말을 집는다 — 본문에 우연히 든 것까지 선언으로 읽는다")

    # ★ 반대 방향. 래칫이 실물과 같은가는 `check()` 가 들고, 여기서는
    #   **실측 함수가 살아 있는가**만 본다(0 이면 빈 그물이다).
    if ratchet_values()["PENDING_MAX"] <= 0:
        fails.append("실측이 0 — 대장을 못 읽었다. 빈 그물이다")

    for f in fails:
        print(f"  ✗ {f}")
    print("✓ 자기검사 통과 · 판별식 8" if not fails else f"✗ {len(fails)}건")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    rest = list(sys.argv[1:] if argv is None else argv)
    if rest == ["--selftest"]:
        return selftest()
    if rest:
        print((__doc__ or "").strip())
        return 2
    return check()


if __name__ == "__main__":
    sys.exit(main())
