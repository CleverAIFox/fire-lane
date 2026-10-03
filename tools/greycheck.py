#!/usr/bin/env python3
"""
greycheck.py — **회색 어휘가 설명하지 못하는 자리.** (DECISIONS §369 · PLAN §1 #140)

    uv run python tools/greycheck.py            센다
    uv run python tools/greycheck.py --rows     후보 전수
    uv run python tools/greycheck.py --selftest

── 무엇을 재나 ─────────────────────────────────────────────────
`PLAN §1 #140` 이 적은 구멍이다 — 「`unknown_reason` 다섯은 전부 **폭이
어떠하다** 또는 **표본이 얇다**를 말한다. 폭도 표본도 충분한데 대장·측량이
반박해 `clear` 를 못 주는 구간을 부를 낱말이 없다」.

그 구멍의 크기를 **지금 발행된 판정에서** 센다. 분모는 §299 계열 후보다 —
`clear` 인데 **대장 명목폭이 문턱 미만**인 구간. 그 후보를 (언젠가) 회색으로
내리면 화면이 사유를 뭐라고 적을지 지금 규칙으로 돌려 본다.

```
없음   넷(`no_cctv_*`)이 다 안 걸리고 `width` 도 아니다 → 화면이 빈칸을 띄운다
거짓   낱말이 **붙기는 하는데 뜻이 틀리다** → 「표본이 하나라서」라고 적는데
       실제 사유는 「대장이 반박한다」다
```

★ **거짓이 없음보다 나쁘다.** 빈칸은 「모른다」를 말하지만 틀린 낱말은
  **아는 척한다** — 읽는 사람이 그 구간을 다시 안 본다. 이 저장소가
  「죽은 참조보다 조용히 틀린 참조가 나쁘다」로 반복해 배운 그 축이다(§205).

★ **판정을 안 내린다.** 후보를 회색으로 내릴지는 측정 배치의 일이고
  (`§13-5` 규칙 2 · 전량 재실행 + baseline 대조가 필요하다), 이 도구는
  **그 배치 전에 어휘가 준비됐는가**만 든다. #140 이 「이것을 먼저 늘려야
  §299 계열 후보를 채택할 수 있다」고 적은 그 순서다.

★ 레이크를 **안 읽는다.** `data/processed/segments.geojson` 은 커밋돼 있고
  (`.gitignore` 예외), 그래서 이 관문이 CI 에서 선다 — `widthcross.py` 가
  같은 축을 들지만 그쪽은 `processed/*.gpkg` 를 읽어 CI 에서 건너뛴다.

RATCHETS  GREY_NOWORD · GREY_WRONGWORD — 둘 다 내려가는 쪽으로만

IN    data/processed/segments.geojson · firelane.seg.classify(REASONS · 문턱)
OUT   표준출력
밖    **판정을 안 바꾼다.** 어휘를 안 늘린다 — 늘리는 것은 판정 폐포를
      건드리는 일이고 `golden` 재잠금이 따라온다.
      **어느 후보가 옳은가도 안 본다** — 그 수는 `widthcross` 의 래칫이 든다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "data" / "processed" / "segments.geojson"

#: 사유를 못 적는 후보. **0 이 목표다** — 어휘 하나가 늘면 둘 다 0 이 된다.
#: ★ 이력 — 2026-10-03 §369 첫 실측 3 (없음) · 5 (거짓).
GREY_NOWORD = 3
#: 사유가 **틀리게** 붙는 후보. 없음보다 나쁘다.
GREY_WRONGWORD = 5

RATCHETS = {"GREY_NOWORD": "down", "GREY_WRONGWORD": "down"}


def _params() -> tuple[float, float, float, float, tuple[str, ...]]:
    from firelane.seg.classify import CLEAR_M, LEDGER_BLOCK_M, REASONS
    from firelane.seg.params import CCTV_RANGE, TRUCK
    return TRUCK, CLEAR_M, LEDGER_BLOCK_M, CCTV_RANGE, REASONS


def rows() -> list[dict]:
    if not SEG.is_file():
        raise RuntimeError(f"{SEG.relative_to(ROOT)} 가 없다 — 커밋돼 있어야 한다")
    g = json.loads(SEG.read_text(encoding="utf-8"))
    return [f["properties"] for f in g["features"]]


def word_for(p: dict, truck: float, clear_m: float, cctv_range: float) -> str:
    """이 구간을 **회색으로 내린다면** 지금 규칙이 줄 낱말.

    `seg/classify.classify` 의 분기를 그대로 따른다 — 그 함수를 못 부르는
    이유는 그것이 **판정까지** 내리기 때문이다. 여기 묻는 것은 「판정이 이미
    회색이라고 치고, 사유 분기가 무엇을 주나」다.

    ★ 분기 순서가 뜻이다. `no_cctv_single` 이 **먼저** 걸리므로, 어휘를
      늘릴 때 새 낱말을 그 앞에 두지 않으면 **거짓 낱말이 계속 이긴다.**
    """
    far = (p.get("cctv_dist_m") if p.get("cctv_dist_m") is not None else 1e9) > cctv_range
    wmin = p.get("width_min_m")
    if not far:
        # CCTV 안이다 — 넷이 다 안 걸린다. 그리고 폭을 알므로 `width` 도 아니다
        return "없음" if wmin is not None else "width"
    if wmin is None:
        return "width"
    if wmin >= clear_m:
        return "거짓:no_cctv_single"
    if wmin < truck:
        return "no_cctv_narrow/thin"
    return "no_cctv_band"


def findings() -> dict:
    truck, clear_m, ledger_block, cctv_range, reasons = _params()
    P = rows()
    clear = [p for p in P if p.get("verdict") == "clear"]
    cand = [p for p in clear
            if p.get("road_bt_m") is not None and p["road_bt_m"] < ledger_block]
    tagged = [(p, word_for(p, truck, clear_m, cctv_range)) for p in cand]
    return {
        "segments": len(P),
        "clear": len(clear),
        "cand": cand,
        "tagged": tagged,
        "noword": [p for p, w in tagged if w == "없음"],
        "wrong": [p for p, w in tagged if w.startswith("거짓")],
        "reasons": reasons,
        "emitted": {p.get("unknown_reason") for p in P} - {None},
        "thresholds": (truck, clear_m, ledger_block, cctv_range),
    }


def ratchet_values() -> dict[str, int]:
    f = findings()
    return {"GREY_NOWORD": len(f["noword"]), "GREY_WRONGWORD": len(f["wrong"])}


def selftest() -> int:
    """★ 합성 구간으로 **분기마다** 민다. 실물이 0 이 되는 날에도 산다."""
    bad = []
    truck, clear_m, cctv = 3.0, 7.0, 25.0
    cases = [
        # CCTV 안 · 폭 안다 → **없음**. 이것이 #140 이 말한 구멍이다
        ({"cctv_dist_m": 3.0, "width_min_m": 7.85}, "없음"),
        # CCTV 밖 · 폭이 clear 문턱 이상 → `no_cctv_single` 이 **거짓으로** 붙는다
        ({"cctv_dist_m": 76.8, "width_min_m": 9.13}, "거짓:no_cctv_single"),
        # CCTV 밖 · 폭이 좁다 → 참인 낱말
        ({"cctv_dist_m": 50.0, "width_min_m": 2.4}, "no_cctv_narrow/thin"),
        # CCTV 밖 · 3~7m → 참인 낱말
        ({"cctv_dist_m": 50.0, "width_min_m": 4.0}, "no_cctv_band"),
        # 폭을 모른다 → `width` 가 맞다(CCTV 안팎 둘 다)
        ({"cctv_dist_m": 50.0, "width_min_m": None}, "width"),
        ({"cctv_dist_m": 3.0, "width_min_m": None}, "width"),
        # cctv 를 안 잰 것은 **멀다로 본다** — 못 잰 것을 가깝다로 치지 않는다
        ({"cctv_dist_m": None, "width_min_m": 9.0}, "거짓:no_cctv_single"),
    ]
    for p, want in cases:
        got = word_for(p, truck, clear_m, cctv)
        if got != want:
            bad.append(f"{p} → {got!r} (기대 {want!r})")
    # ★ 빈 그물 — 실물에서 후보를 0개 찾으면 래칫이 늘 0 이다
    f = findings()
    if f["segments"] < 1000:
        bad.append(f"구간을 {f['segments']}개밖에 못 읽었다 — 수집기를 의심하라")
    if not f["cand"]:
        bad.append("§299 후보가 0 이다 — 분모가 비면 이 관문이 언제나 초록이다")
    # ★ 어휘 닫힘 — 발행된 값이 선언 밖이면 그것이 먼저 결함이다
    out = f["emitted"] - set(f["reasons"])
    if out:
        bad.append(f"발행된 사유가 선언 밖이다: {sorted(out)}")
    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 판별식 {len(cases) + 3}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", action="store_true", help="후보 전수")
    ap.add_argument("--ratchet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    f = findings()
    truck, clear_m, ledger_block, cctv_range = f["thresholds"]
    if a.ratchet:
        print(f"GREY_NOWORD {len(f['noword'])} · GREY_WRONGWORD {len(f['wrong'])}")
        return 0

    print(f"구간 {f['segments']:,} · clear {f['clear']} · 사유 어휘 {len(f['reasons'])}개")
    print(f"문턱  TRUCK {truck} · CLEAR_M {clear_m} · 대장차단 {ledger_block}"
          f" · CCTV {cctv_range}\n")
    print(f"§299 후보 — `clear` 인데 대장 명목폭 < {ledger_block}   **{len(f['cand'])}건**"
          f"  (경로에 쓰임 {sum(1 for p in f['cand'] if p.get('route_usage'))})")
    print("  ★ 이 후보를 회색으로 내린다면 화면이 적을 사유 —")
    for w, n in Counter(w for _, w in f["tagged"]).most_common():
        mark = "  ✗" if (w == "없음" or w.startswith("거짓")) else "   "
        print(f"  {mark} {n:>3}  {w}")

    if a.rows:
        print("\n── 후보 전수 ───────────────────────────────────────────")
        for p, w in sorted(f["tagged"], key=lambda x: x[0].get("road_bt_m") or 0):
            print(f"  {p['seg_uid']:<22} {str(p.get('road_name'))[:14]:<15}"
                  f" wmin {p.get('width_min_m')!s:>7} 대장 {p.get('road_bt_m')!s:>5}"
                  f" 표본 {p.get('n_sample')!s:>4} cctv {p.get('cctv_dist_m')!s:>6}"
                  f" 경로 {p.get('route_usage')!s:>3}  → {w}")

    rc = 0
    print()
    for name, now in (("GREY_NOWORD", len(f["noword"])), ("GREY_WRONGWORD", len(f["wrong"]))):
        want = globals()[name]
        sign = "=" if now == want else ("↑" if now > want else "↓")
        print(f"  {name:<15} 실측 {now:>3} {sign} 래칫 {want:>3}")
        if now > want:
            print("    ✗ **늘었다.** 어휘로 설명 못 하는 자리가 는 것이고,"
                  " 그러면 §299 계열 채택이 더 멀어진다")
            rc = 1
    if rc == 0 and (len(f["noword"]) or len(f["wrong"])):
        print("\n  ★ 0 이 아니다. 고침은 **어휘를 하나 늘리는 것**이고 그것은 판정 폐포를")
        print("    건드리므로 `golden` 재잠금이 따라온다 — 측정 배치의 일이다(§13-5 규칙 2).")
        print("    ★ 늘릴 때 **`no_cctv_single` 분기 앞에** 둬라. 뒤에 두면 거짓 낱말이")
        print("      계속 이긴다 — 이 도구가 센 「거짓」이 바로 그 분기다.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
