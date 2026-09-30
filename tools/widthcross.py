#!/usr/bin/env python3
"""
widthcross.py — 폭을 **방법이 다른 원천끼리** 댄다. 오염되지 않은 외부 증인.

    uv run python tools/widthcross.py            대조 (레이크·산출물 필요)
    uv run python tools/widthcross.py --json OUT 표를 파일로
    uv run python tools/widthcross.py --selftest ★ 판별식이 살아 있나

── 왜 생겼나 (DECISIONS §289) ──────────────────────────────────
지금 우리 폭에 대한 외부 대조는 `nfa_compare` **하나**이고 그것은
**오염돼 있다** — 절대편차를 12.6 → 7.24 로 줄이는 데 그 표를 게이트로
썼다(MASTER §4-1). 게이트로 쓴 자료는 그 순간부터 검증 수단이 아니다.

그런데 **방법이 독립인 증인이 이미 셋 있다.** 전부 대장에 있고 전부
파이프라인이 읽고 있으며 **아무도 대조하지 않는다** —

    ngii1k_center.도로폭   1:1,000 수치지형도 **측량 성과**
                           `ngii1k.py` 주석: 「우리 기하 계산과 독립이라
                           대조 검증에 쓴다」 ← 뽑아만 놓고 대조가 없다
    road_bt_m              도로명주소 도로대장 명목폭. **구간마다 이미
                           붙어 있다.** 스키마: 「참고용. 판정에는 안 쓴다」
    node_link.LANES        표준노드링크 차로수

★ 지금 있는 `width_disagree_m` 는 **우리 세 소스끼리만** 잰다 —
  `ngii1k` · `ngii` · `silpok` 셋 다 **같은 방법**(폴리곤에 법선 긋기)이다.
  셋이 맞아도 그 방법이 맞다는 증거가 못 된다. 같은 자로 세 번 잰 것이다.

★ 이 대조는 **한 번 손으로 이미 했다.** `segments.py:413` 주석에 남아 있다 —
  「측량 도로폭과 대조하니 판정이 바뀐 64구간 중 **36구간이 노면·대장폭·
  측량폭이 전부 3m 미만인데 blocked 에서 빠졌다**. 법선이 먼 건물까지 뻗어
  벽 사이를 3.3~25m 로 잡았다. **미탐 쪽으로의 이동이다**」.
  실측이었고 값이 컸는데 **산문으로만 남아 상설 검사가 되지 못했다.**
  이 도구가 그것을 상설로 만든다.

── 무엇을 세나 ────────────────────────────────────────────────
**문턱을 발명하지 않는다.** 1판은 두 가지만 한다 —

    ① 분포     원천 쌍마다 차이의 사분위. 「얼마나 다른가」를 먼저 센다
    ② 모순     문턱 없이 **논리적으로 불가능한 것**만 센다
    ③ 과대주장  `clear` 가 대장 명목폭과 **서로를 부정**하는 구간. 래칫 둘

  모순 둘은 임의 상수가 없다 —
    · `wmin > survey`    우리 **최솟값**이 측량 **명목폭**을 넘는다
    · `wmax < wmin`      담~담이 노면보다 좁다

  「얼마 이상 다르면 이상한가」는 ①의 분포를 보고 **다음 배치에서** 정한다.
  지금 정하면 그 수는 근거가 없다.

★ ③ 도 문턱을 발명하지 않는다 (2026-09-29 · DECISIONS §299). `clear` 자신이
  주장하는 값(`TRUCK` · `TRUCK + 2·PARK`)과 대장이 이미 든 명목폭을 대는 것이고,
  두 주장이 동시에 참일 수 없는 경우만 센다. **어느 쪽이 옳은지는 안 말한다.**
  고치려면 판정이 움직이고 그것은 측정 배치의 일이므로(PLAN §13-5 규칙 2)
  그 배치가 오기 전까지 **수가 늘지 않게** 래칫으로 막는다.

IN    processed/segments_5186.gpkg · processed/ngii1k_center_5186.gpkg
OUT   processed/width_cross.json (--json 이면 지정 경로)
PARAM OVERCLAIM_HARD · OVERCLAIM_SOFT (래칫. 문턱은 판정기 상수에서 온다)
밖    **판정을 안 바꾼다.** `nfa_compare` 와 같은 자리다 — 판정이 끝난 것을
      읽어 외부 자료와 댈 뿐이고, 판정 지문 밖이다(§247 과 같은 사유).
      **어느 원천이 옳은가도 안 본다.** 측량폭이 진실이라는 근거가 없다 —
      그것도 사람이 잰 값이다. 여기가 드는 것은 「서로 얼마나 다른가」다.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# ★ `clear` 의 문턱은 **판정기가 정본이다**(`seg/params.py`). 여기서 수를 적으면
#   같은 사실이 두 집에 살고, 그 둘은 반드시 갈린다(2족).
from firelane.seg.params import PARK, TRUCK

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

#: 이름 → (무엇인가, 우리 기하 계산과 방법이 독립인가)
SOURCES: dict[str, tuple[str, bool]] = {
    "wmin":   ("우리 노면폭 하한 — 폴리곤에 법선을 그어 잰 최솟값", False),
    "wmax":   ("담~담 폭 — 건물 사이", False),
    "survey": ("1:1,000 수치지형도 도로중심선 `도로폭` — 측량 성과", True),
    "ledger": ("도로명주소 도로대장 명목폭 `ROAD_BT`", True),
}

#: 반올림 여유. 측량 도로폭은 0.1m 단위로 기록되고 대장폭은 정수다.
#: **이것은 문턱이 아니라 표기 단위다** — 모순 판정이 표기 오차에 걸리지
#: 않게 하는 값이고, 「얼마나 다르면 이상한가」와는 다른 축이다.
ROUNDING_M = 0.5


def _num(v) -> float | None:
    """수로 읽는다. 결측 · 빈칸 · NaN 은 전부 None 이다. **0 은 수다.**"""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def contradictions(row: dict) -> list[str]:
    """그 구간에서 **논리적으로 불가능한 것**. 문턱이 없다.

    차이가 큰 것은 여기서 안 센다 — 「크다」의 기준이 아직 없다.
    """
    out: list[str] = []
    wmin, wmax = _num(row.get("wmin")), _num(row.get("wmax"))
    survey = _num(row.get("survey"))

    # ① 우리 **최솟값**이 측량 **명목폭**을 넘는다. 명목폭은 그 길의 대표값이고
    #    최솟값이 그보다 크려면 길이 어디서도 명목폭만큼 좁지 않다는 뜻이다.
    if wmin is not None and survey is not None and wmin > survey + ROUNDING_M:
        out.append(f"wmin {wmin:.2f} > 측량 {survey:.2f} — 최솟값이 명목폭을 넘는다")

    # ② 담~담이 노면보다 좁다. 벽은 노면 밖에 있다.
    if wmin is not None and wmax is not None and wmax + ROUNDING_M < wmin:
        out.append(f"wmax {wmax:.2f} < wmin {wmin:.2f} — 벽 사이가 노면보다 좁다")
    return out


def evidence(row: dict) -> dict:
    """모순 한 건의 **근거.** 판정은 안 한다 — 사람이 가를 재료만 낸다.

    ★ 왜 생겼나 (2026-09-29 · DECISIONS §299). 종전에는 모순을 `seg` 와 `why`
      두 칸으로만 냈다. 열일곱 건을 보고 「조인 인공물인가 실결함인가」를 가르려면
      **사람이 산출물을 다시 열어야 했다.** 관문이 사람에게 조사를 미룬 것이고,
      미룬 조사는 미뤄진다(§290-2 가 같은 말을 도장에서 했다).

    ★ 재료는 **이미 산출물에 다 있었다.** 새로 재지 않는다 —
        road_name  ↔ survey_name    이름이 다르면 **다른 길을 물었다**(조인 인공물)
        n_sample · width_cov         표본이 적거나 덮임이 낮으면 우리 값이 약하다
        length_m                     짧은 구간은 겹침 매칭이 옆 길을 집기 쉽다
        width_src                    어느 원천이 우리 값을 냈나
    """
    return {k: row.get(k) for k in
            ("road_name", "survey_name", "n_sample", "width_cov",
             "length_m", "width_src", "wmin", "wmax", "survey", "ledger",
             "verdict")}


#: `clear` 가 주장하는 문턱. **이 도구가 정하지 않는다** — 판정기가 쓰는 그 값이다.
CLEAR_M = TRUCK + 2 * PARK

#: `clear` 가 대장과 모순인 구간 수. **오늘 값에서 시작해 내린다.**
#:
#:   딱딱한 층   대장 < TRUCK    대장이 「소방차가 물리적으로 못 들어간다」고 적었다
#:   부드러운 층 대장 < CLEAR_M  대장이 「주차가 있으면 못 지나간다」고 적었다
#:
#: ★ **층을 왜 나눴나** (DECISIONS §299-2). 한 수로 세니 40건이 「대장 6.0 대 wmin
#:   7.0」 같은 경계 사례에 묻혔다 — 그것은 표기·정의 차이로 설명되는 1m 이고, 같은
#:   목록에 있는 「대장 2.0 대 wmin 29.91」과 성격이 전혀 다르다. **구분 없는 목록은
#:   신호를 묻는다** — 모순 열일곱 건이 그래서 한 달 동안 안 갈렸다.
#: ★ 경계 둘 다 **기존 상수다.** 새로 발명하지 않았다.
#: ★ 이력 — 09-29 §299-2 층 분리(9 · 40) · 09-30 §318 8 · 39.
#:   두 수 모두 **실측이 내려가서** 조였다. 판정을 안 움직였는데 왜 내려갔나 —
#:   §308 이 커버율 관문을 켜면서 근거가 얇은 `clear` 가 `needs_cv` 로 갔고,
#:   그 몫이 이 목록에서도 빠졌다. **한 배치가 두 곳을 조인다.**
OVERCLAIM_HARD = 8
OVERCLAIM_SOFT = 39

#: ★ 이 둘을 `ratchet.py` 규약에 태운다(§309). 종전에는 도구가 「그 수로
#:   내려라」를 찍고 **사람이 받아적었다** — 09-30 실기에서 그 두 줄이 그대로
#:   남아 배치 하나를 통째로 다시 만들게 했다.
#:
#: ★ 이 도구는 `ci-exempt` 다(파이프라인 산출물을 읽는다). 래칫이 레이크에
#:   기대므로 CI 에서는 실측이 불가능하고, `ratchet.py` 가 그 선언을 물려받아
#:   **사유와 함께 건너뛴다** — 조용히 빠지는 것이 아니다(§318).
RATCHETS = {"OVERCLAIM_HARD": "down", "OVERCLAIM_SOFT": "down"}


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. **판정은 안 한다**(`show()` 소관).

    산출물이 없으면 `RuntimeError` 를 던진다. **0 을 내지 않는다** — 0 은
    「모순이 없다」는 뜻이고, 그것을 선언에 적으면 래칫이 조용히 최대로
    조여져 다음 실행이 무조건 빨개진다(§313-1 ① 과 같은 족).
    """
    rows = _load()
    if rows is None:
        raise RuntimeError(
            f"{PROCESSED.name}/segments_5186.gpkg 가 없다 — 실측 못 한다")
    res = cross(rows)
    return {"OVERCLAIM_HARD": len(res["과대주장 딱딱"]),
            "OVERCLAIM_SOFT": len(res["과대주장 부드러움"])}


def overclaim(rows: list[dict], floor: float) -> list[dict]:
    """`clear` 가 **대장 명목폭과 모순**인 구간. 새 상수를 쓰지 않는다.

    ★ `clear` 는 「wmin ≥ CLEAR_M」을 주장한다 — *양쪽에 주차가 있어도 통과하므로
      영상판정조차 필요 없다*. 대장이 그 길을 `floor` 보다 **좁다**고 하면 두 주장은
      동시에 참일 수 없다.

    ★ 왜 이것이 제일 나쁜 방향인가 (§299). 이 제품은 「소방차가 들어갈 수 있나」를
      답한다. `clear` 는 **가장 강한 주장**이고 거짓 `clear` 는 못 들어가는 길로 차를
      보낸다. 반대 방향(거짓 blocked)은 우회를 낳고 이쪽은 사고를 낳는다.
      §289 가 손으로 잰 「셋 다 3m 미만인데 blocked 에서 빠진 36구간 · 미탐 쪽
      이동이다」와 같은 족이고, 그 실측이 산문으로만 남아 상설이 못 됐다.

    ★ **어느 쪽이 옳은지 말하지 않는다.** 대장 명목폭을 판정에 쓰는 것이 아니고
      (스키마가 「참고용. 판정에는 안 쓴다」라고 적은 그대로다), 대장이 틀린 사례도
      실재한다 — `필문대로289번길` 은 기하가 틀려 사람이 손으로 보정한 길이다(§170-2).
      이 도구가 세는 것은 **두 주장이 서로를 부정하는가**이고, 가르는 것은 사람이다.
    """
    out = []
    for r in rows:
        if r.get("verdict") != "clear":
            continue
        bt = _num(r.get("ledger"))
        if bt is None or bt >= floor:
            continue
        out.append({"seg": r.get("seg_uid") or r.get("seg_id"),
                    "why": f"clear 인데 대장 명목폭 {bt:.1f} < {floor:.1f}",
                    "증거": evidence(r)})
    return out


def quartiles(xs: list[float]) -> dict[str, float]:
    """사분위. numpy 를 안 쓴다 — 이 도구는 표를 읽을 뿐이고 의존을 안 늘린다."""
    if not xs:
        return {}
    s = sorted(xs)

    def q(p: float) -> float:
        if len(s) == 1:
            return s[0]
        i = p * (len(s) - 1)
        lo, hi = int(i), min(int(i) + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (i - lo)

    return {"n": len(s), "min": s[0], "q25": q(.25), "median": q(.5),
            "q75": q(.75), "max": s[-1]}


#: 대 볼 쌍. **방법이 독립인 짝을 먼저 둔다** — 그것이 이 도구의 이유다.
PAIRS = (("wmin", "survey"), ("wmin", "ledger"), ("survey", "ledger"),
         ("wmax", "survey"))


def cross(rows: list[dict]) -> dict:
    """전수 대조. (분포, 모순, 덮임)"""
    diffs: dict[str, list[float]] = {}
    for a, b in PAIRS:
        xs = [va - vb for r in rows
              if (va := _num(r.get(a))) is not None
              and (vb := _num(r.get(b))) is not None]
        diffs[f"{a}-{b}"] = xs

    bad = [{"seg": r.get("seg_uid") or r.get("seg_id"), "why": w,
            "증거": evidence(r)}
           for r in rows for w in contradictions(r)]

    have = {k: sum(1 for r in rows if _num(r.get(k)) is not None)
            for k in SOURCES}
    return {
        "구간": len(rows),
        "원천별 값 있음": have,
        "차이 분포": {k: quartiles(v) for k, v in diffs.items()},
        "모순": bad,
        "과대주장 딱딱": overclaim(rows, TRUCK),
        "과대주장 부드러움": overclaim(rows, CLEAR_M),
    }


def show(res: dict) -> int:
    n = res["구간"]
    print(f"── 폭 교차대조  구간 {n}")
    print("\n  원천별 값 있음")
    for k, c in res["원천별 값 있음"].items():
        what, indep = SOURCES[k]
        mark = "★독립" if indep else "  우리"
        pct = f"{c / n:6.1%}" if n else "    —"
        print(f"    {mark} {k:7} {c:>5} {pct}  {what}")

    print("\n  차이 분포 (m) — **문턱을 안 건다. 분포를 먼저 본다**")
    for k, q in res["차이 분포"].items():
        if not q:
            print(f"    {k:16} 겹치는 구간이 없다")
            continue
        print(f"    {k:16} n={q['n']:>5}  "
              f"25% {q['q25']:+6.2f} · 중앙 {q['median']:+6.2f} · "
              f"75% {q['q75']:+6.2f}   [{q['min']:+.2f} ~ {q['max']:+.2f}]")

    bad = res["모순"]
    print(f"\n  모순 {len(bad)}건 — 문턱 없이 **불가능한 것**만")
    # ★ §299. 근거를 같이 찍는다. 종전에는 `seg` 와 `why` 만 찍어서 사람이
    #   산출물을 다시 열어야 했다 — 관문이 조사를 미루면 그 조사는 미뤄진다.
    for b in bad:
        e = b.get("증거") or {}
        rn, sn = e.get("road_name") or "—", e.get("survey_name") or "—"
        print(f"    {b['seg']}  {b['why']}")
        print(f"        이름  우리 {rn} · 측량 {sn}  → "
              f"{'같다' if rn == sn else '★다르다'}")
        print(f"        표본  n={e.get('n_sample')} · 덮임 {e.get('width_cov')} · "
              f"길이 {e.get('length_m')} · 판정 {e.get('verdict')}")
    if not bad:
        print("    없음")
    hard = res.get("과대주장 딱딱") or []
    soft = res.get("과대주장 부드러움") or []
    print("\n  과대주장 — `clear` 가 대장과 모순인 구간. **새 상수가 없다**")
    print(f"    딱딱     {len(hard):>3}건 · 래칫 {OVERCLAIM_HARD:<3} "
          f"대장 < TRUCK {TRUCK:.1f} — 대장이 「소방차가 못 들어간다」고 적었다")
    print(f"    부드러움  {len(soft):>3}건 · 래칫 {OVERCLAIM_SOFT:<3} "
          f"대장 < {CLEAR_M:.1f} — 「주차가 있으면 못 지나간다」")
    for b in hard:
        e = b.get("증거") or {}
        print(f"      {e.get('road_name') or '—':<16} 대장 {e.get('ledger')} · "
              f"wmin {e.get('wmin')} · 측량 {e.get('survey')} · n={e.get('n_sample')}")
    if not hard:
        print("      딱딱한 층 없음")

    print("\n★ 이 표는 **판정을 안 바꾼다.** 어느 원천이 옳은가도 안 본다.")
    print("  ①②는 분포와 논리적 불가능만 센다. ③은 **래칫**이다 — 고치려면 판정이")
    print("  움직이고 그것은 측정 배치의 일이다(PLAN §13-5 규칙 2).")

    rc = 0
    for name, got, want in (("딱딱", len(hard), OVERCLAIM_HARD),
                            ("부드러움", len(soft), OVERCLAIM_SOFT)):
        if got > want:
            print(f"\n✗ 과대주장({name}) {got} > 래칫 {want} — **늘었다.**")
            print("  거짓 `clear` 는 못 들어가는 길로 차를 보낸다. 늘리지 않는다.")
            rc = 1
        elif got < want:
            print(f"\n✗ 과대주장({name}) {got} < 래칫 {want} — "
                  f"**래칫을 그 수로 내려라.** 안 내리면 다시 는다.")
            rc = 1
    return rc


def _load() -> list[dict] | None:
    """산출물에서 구간별 네 값을 모은다. 없으면 None."""
    seg = PROCESSED / "segments_5186.gpkg"
    ctr = PROCESSED / "ngii1k_center_5186.gpkg"
    if not seg.exists():
        return None
    import geopandas as gpd

    from firelane.seg.roadname import RoadNameIndex
    g = gpd.read_file(seg)
    rows = [{"seg_uid": r.get("seg_uid"), "seg_id": r.get("seg_id"),
             "wmin": r.get("width_min_m"), "wmax": r.get("width_max_m"),
             "ledger": r.get("road_bt_m"), "survey": None, "survey_name": None,
             # ★ §299. 모순의 **근거**가 될 칸들. 새로 재지 않고 산출물에서 그대로 든다.
             "verdict": r.get("verdict"), "road_name": r.get("road_name"),
             "n_sample": r.get("n_sample"), "width_cov": r.get("width_cov"),
             "length_m": r.get("length_m"), "width_src": r.get("width_src")}
            for _i, r in g.iterrows()]
    if not ctr.exists():
        print(f"  ! {ctr.name} 없음 — 측량 도로폭 없이 낸다")
        return rows

    # ★ 겹침 매칭은 `RoadNameIndex` 가 정본이다. **두 번째 매처를 만들지
    #   않는다**(2족). 그 클래스가 하는 일은 「겹침 길이가 가장 긴 선의 속성을
    #   고른다」이고 컬럼 이름은 부수적이다 — 이름 자리에 도로폭을 넣어 같은
    #   논리를 쓴다. 클래스를 일반화하지 않는 이유는 그것이 **판정 폐포**
    #   안이기 때문이다(§266). 대조 도구 때문에 폐포를 건드리지 않는다.
    #
    # ★ **덮임이 낮을 수 있고 그것도 결과다.** 구간은 `road_link` 위에 놓여
    #   있고 NGII 중심선은 측량 성과라 서로 어긋나 있다 — `centerline_correction`
    #   이 존재하는 이유가 그 어긋남이다(§170-2). 몇 %가 맞는지를 `원천별 값
    #   있음` 이 그대로 낸다. 낮으면 낮다고 보고한다.
    c = gpd.read_file(ctr).to_crs(g.crs)
    if "도로폭" not in c.columns:
        print(f"  ! {ctr.name} 에 `도로폭` 칸이 없다 — 측량 도로폭 없이 낸다")
        return rows
    idx = RoadNameIndex(list(c.geometry), list(c["도로폭"]),
                        [""] * len(c), [None] * len(c))
    # ★ §299. 측량 쪽 **도로명**도 받는다. 두 번째 매처를 만들지 않는다 — 같은
    #   클래스에 payload 만 바꿔 넣는다. 그 클래스가 하는 일은 「겹침이 가장 긴 선의
    #   값을 고른다」이고 값이 무엇인지는 부수적이다. 우리 구간이 `중앙로` 인데 물린
    #   측량선이 다른 이름이면 **다른 길을 물었다**는 뜻이고, 그것이 조인 인공물이다.
    nidx = RoadNameIndex(list(c.geometry), list(c.get("도로명", [""] * len(c))),
                         [""] * len(c), [None] * len(c))
    for row, geom in zip(rows, g.geometry, strict=True):
        row["survey"] = idx.match(geom)[0]
        row["survey_name"] = nidx.match(geom)[0]
    return rows


def selftest() -> int:
    """★ 판별식이 실제로 무는가. 데이터 없이 합성으로 문다."""
    bad = []
    if contradictions({"wmin": 2.0, "wmax": 5.0, "survey": 5.0}):
        bad.append("멀쩡한 구간을 모순이라 한다")
    if not contradictions({"wmin": 7.0, "survey": 5.0}):
        bad.append("최솟값이 명목폭을 넘는 것을 못 잡는다")
    if contradictions({"wmin": 5.3, "survey": 5.0}):
        bad.append("표기 반올림을 모순으로 센다")
    if not contradictions({"wmin": 5.0, "wmax": 2.0}):
        bad.append("벽 사이가 노면보다 좁은 것을 못 잡는다")
    if contradictions({"wmin": None, "survey": None}):
        bad.append("결측을 모순으로 센다")
    if contradictions({"wmin": 0.0, "survey": 0.0}):
        bad.append("0 을 결측으로 본다 — 0 은 수다")

    q = quartiles([1.0, 2.0, 3.0, 4.0])
    if not (q["median"] == 2.5 and q["min"] == 1.0 and q["max"] == 4.0):
        bad.append(f"사분위가 틀렸다 — {q}")
    if quartiles([]):
        bad.append("빈 목록에서 값을 낸다")

    r = cross([{"seg_uid": "A", "wmin": 7.0, "survey": 5.0},
               {"seg_uid": "B", "wmin": 3.0, "survey": 5.0}])
    if len(r["모순"]) != 1 or r["모순"][0]["seg"] != "A":
        bad.append(f"전수 집계가 모순을 못 모은다 — {r['모순']}")
    if r["차이 분포"]["wmin-survey"]["n"] != 2:
        bad.append("차이 분포가 짝을 못 센다")

    # ★ §299. 축 ③ 이 양방향으로 무는가. 한쪽만 재면 「전부 세기」와 「아무것도 안
    #   세기」가 둘 다 통과한다.
    if overclaim([{"seg_uid": "A", "verdict": "clear", "ledger": 8.0}], TRUCK):
        bad.append("대장이 넉넉한데 과대주장이라 한다")
    if not overclaim([{"seg_uid": "A", "verdict": "clear", "ledger": 2.0}], TRUCK):
        bad.append("대장이 TRUCK 미만인데 clear 인 것을 못 잡는다")
    if overclaim([{"seg_uid": "A", "verdict": "needs_cv", "ledger": 2.0}], TRUCK):
        bad.append("clear 가 아닌 판정을 과대주장으로 센다 — 그 주장을 안 했다")
    if overclaim([{"seg_uid": "A", "verdict": "clear", "ledger": None}], TRUCK):
        bad.append("대장이 결측인데 모순이라 한다 — 회색은 모순이 아니다")
    if not overclaim([{"seg_uid": "A", "verdict": "clear", "ledger": 6.0}], CLEAR_M):
        bad.append("부드러운 층이 대장 6.0 을 안 잡는다")
    if overclaim([{"seg_uid": "A", "verdict": "clear", "ledger": 6.0}], TRUCK):
        bad.append("딱딱한 층이 대장 6.0 을 잡는다 — 층이 안 갈렸다")
    if CLEAR_M <= TRUCK:
        bad.append("두 층의 경계가 뒤집혔다 — 부드러운 층이 딱딱한 층을 안 덮는다")

    if not any(indep for _w, indep in SOURCES.values()):
        bad.append("독립 원천이 하나도 선언 안 돼 있다 — 이 도구의 이유가 없다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 모순 판별 · 사분위 · 전수 집계 "
          f"(원천 {len(SOURCES)} · 독립 "
          f"{sum(1 for _w, i in SOURCES.values() if i)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="표를 이 경로에 쓴다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    rows = _load()
    if rows is None:
        print("✗ 산출물이 없다 — data/processed/segments_5186.gpkg")
        print("  파이프라인을 먼저 돌려라. **없는 것은 통과가 아니다.**")
        return 2
    res = cross(rows)
    out = a.json or (PROCESSED / "width_cross.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    rc = show(res)
    print(f"\n→ {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
