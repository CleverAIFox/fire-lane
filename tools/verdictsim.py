#!/usr/bin/env python3
"""
verdictsim.py — 판정 규칙을 **배달 전에** 잰다. 호수 없이.

    uv run python tools/verdictsim.py                 후보 대장 + 전부 계측
    uv run python tools/verdictsim.py --list           후보 대장만
    uv run python tools/verdictsim.py --rule NAME      하나만, 증거까지
    uv run python tools/verdictsim.py --json OUT       표를 파일로
    uv run python tools/verdictsim.py --selftest       ★ 판별식이 살아 있나

── 왜 생겼나 (DECISIONS §304) ──────────────────────────────────
PLAN §1 #4 는 「판정 규칙을 고치면 **전후를 재라**」고 적는다. 반년째
미결이었다. 이유는 게으름이 아니라 **못 쟀기 때문**이다 — 판정 사슬 일곱
줄 중 둘이 1,041줄 `segments.main()` 안에 있어서, 규칙 하나를 건드리려면
호수(`data/raw`, 수 GB)를 다시 돌려야 이동이 보였다. 호수가 없는 기계에서는
아예 못 쟀다. 그래서 규칙 논의가 전부 **산문**으로 끝났다.

§303 이 사슬을 `seg/classify.py` 로 꺼냈다. 그 함수의 인자는 전부
**산출물에 실재하는 열**이다. 그러면 공개본 1,281행을 그 함수에 **다시
먹여** 규칙 변경의 이동을 잴 수 있다 — 파이프라인 없이, 호수 없이, 1초에.

★ 이 도구는 규칙을 **고치지 않는다.** 수를 낸다. 고치는 것은 그 수를 보고
  사람이 결정해 `classify()` 를 바꾸는 별개의 일이고, 그때 재잠금이 따라온다.

★ 재기 전에 **재현부터 증명한다.** `classify()` 가 공개본의 `verdict` ·
  `unknown_reason` 을 1,281/1,281 로 다시 내지 못하면 이 도구는 아무 수도
  안 내고 죽는다. 재현이 깨진 상태에서 낸 「전후」는 전후가 아니다
  (§293 과 같은 규율 — 못 쟀으면 0건이 아니라 **못 쟀다**고 말한다).

── 후보를 발명하지 않는다 ──────────────────────────────────────
후보 대장은 **이 저장소가 이미 적어둔 미결 질문**만 담는다. 각 후보는
어디서 왔는지(§ 번호)를 들고 있고, 그것 없이는 등재하지 않는다. 문턱을
새로 지어내면 그 수는 근거가 없다(`widthcross` 와 같은 규율).

IN    web/data/segments.geojson (추적됨 · 판정 입력 전부를 들고 있다)
OUT   화면. `--json` 이면 지정 경로
PARAM 없다. **문턱은 전부 `seg/classify.py` · `seg/params.py` 에서 온다.**
      후보가 쓰는 수도 그 상수들의 조합이거나 이미 문서에 적힌 값뿐이다.
밖    **판정을 안 바꾼다.** 읽기만 한다 — `classify()` 를 부르지만 결과를
      어디에도 쓰지 않으므로 판정 지문 밖이다(§247 과 같은 사유).
      **어느 후보가 옳은지 안 말한다.** 이동량과 증거를 내고 멈춘다.
      길이 근사가 하나 있다 — 파이프라인은 `g.length` 를 넘기고 여기는
      공개본의 `round(g.length, 1)` 을 넘긴다. 길이가 정확히 `MIN_SEG_LEN`
      경계에 걸린 구간에서만 갈리고, 그런 구간은 현재 0개다(아래
      `_check_repro` 가 그것을 재현 실패로 잡는다).
      **회색 사유를 못 낸다.** 후보가 clear 를 내린 구간의 사유는 `NO_WORD`
      로 나간다 — 어휘에 그 낱말이 없기 때문이고, 발명하지 않는다(§304-1).
      **폭이 옳은가는 안 본다.** `wmin` 을 만드는 일은 `seg/width.py` 이고
      그 구멍(§306 커버율 자격 면제)은 이 도구로 못 잰다 — 공개본에는
      바뀐 뒤의 `wmin` 이 없다.
"""
from __future__ import annotations

import argparse
import collections
import json
from collections.abc import Callable
from pathlib import Path

from firelane.seg.classify import CLEAR_M, LEDGER_BLOCK_M, classify

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "web" / "data" / "segments.geojson"
ORDER = ("blocked", "needs_cv", "clear", "unknown")

#: 후보 하나의 모양. `(판정, 사유)` 를 받아 바꿔 낸다. 안 바꾸면 그대로 반환.
Hook = Callable[[dict, str, "str | None"], "tuple[str, str | None]"]


def _gap(p: dict) -> float | None:
    """우리 노면폭이 대장 명목폭보다 얼마나 넓다고 주장하는가."""
    if p["width_min_m"] is None or p["road_bt_m"] is None:
        return None
    return p["width_min_m"] - p["road_bt_m"]


#: 후보가 clear 를 내린 구간의 회색 사유. **낱말이 없어서** 이렇게 적는다.
#:
#: ★ 이것이 이 도구가 낸 첫 발견이다(§304-1). `REASONS` 다섯은 전부 「폭이
#:   어떠하다」 또는 「표본이 얇다」를 말한다. 「폭도 표본도 충분한데 **다른
#:   원천이 반박했다**」는 회색을 부를 낱말이 없다. 즉 네 후보 중 무엇을
#:   택하든 화면이 그 구간을 설명하지 못한다 — 후보를 실제로 채택하려면
#:   어휘를 먼저 늘려야 하고, 그것은 규칙 변경과 **별개의 일**이다.
#:   §251-2 의 `can_turn`(회전반경 부족을 부를 낱말이 없다)과 같은 모양이다.
NO_WORD = "(어휘 없음)"


# ── 모르는 값을 어느 쪽으로 읽는가  (DECISIONS §396 · PLAN #149) ──────────
#
# ★ 2026-10-05 실측. 돌연변이 관문이 `verdictsim` 에서 생존 넷을 냈고 **셋이
#   같은 모양**이었다 — `(X or 0)`. 그 꼴은 **「없다」와 「0」을 같은 것으로**
#   읽는다. 여기서는 둘 다 우연히 맞는 답을 냈지만, 맞는 이유가 적혀 있지
#   않으면 다음 사람이 `or 0` 을 `or 999` 로 바꿔도 아무도 안 운다. 실제로
#   돌연변이 셋이 그 자리에서 살아남았다.
#
# ★ 두 방향이 다르고, 다른 이유가 있다.
#
#     주장을 **들 때**     모르면 **안 든다**. 「어긋난다」는 적극적 주장이고
#                          근거가 없으면 못 한다 (§392 와 같은 규율)
#     clear 를 **줄 때**   모르면 **안 준다**. 통행 가능 선언은 안전 주장이고
#                          「표본이 몇 개인지 모른다」는 「충분하다」가 아니다
#
#   한 줄로 적으면 — **모르는 값은 한 번도 유리하게 쓰이지 않는다.**

def _claims_at_least(v: float | None, threshold: float) -> bool:
    """`v` 가 문턱 이상이라고 **주장할 수 있는가.** 모르면 거짓이다."""
    return v is not None and v >= threshold


def _fewer_than(v: float | None, threshold: float) -> bool:
    """표본이 문턱 미만인가. **모르면 참** — 모르는 것은 충분하다는 뜻이 아니다."""
    return v is None or v < threshold


def _veto_clear(test: Callable[[dict], bool]) -> Hook:
    """`clear` 만 거부하는 후보를 만든다.

    ★ 내린 뒤 CCTV 강등이 **다시 걸린다.** 그래서 이동이 `clear → needs_cv`
      에서 끝나지 않고 일부가 unknown 까지 간다 — 그것이 실제 결과이고,
      후보를 산문으로 논할 때 늘 빠지던 부분이다. 강등을 여기서 다시 적지
      않고 `classify()` 를 또 부르는 이유는 하나다 — 판정 문은 하나다(§303).

    ★ 되먹일 때 `wmin` 을 clear 문턱 아래로 낮춘다. **판정은 그것으로 옳게
      나오지만 사유는 그렇지 않다** — 낮춘 값이 `no_cctv_band`(3~7m 대역)를
      부르는데 그 구간은 3~7m 가 아니다. 그래서 사유를 `NO_WORD` 로 덮는다.
      거짓 낱말을 내는 것보다 낱말이 없다고 적는 것이 맞다(회색 = NULL).
    """
    def hook(p: dict, v: str, reason: str | None) -> tuple[str, str | None]:
        if v != "clear" or not test(p):
            return v, reason
        v2, _ = classify(
            wmin=CLEAR_M - 0.01,          # clear 문턱 바로 아래로 낮춰 다시 먹인다
            wmax=p["width_max_m"], nreg=p["n_sample"], road_bt=p["road_bt_m"],
            length_m=p["length_m"], cctv_dist=p["cctv_dist_m"],
        )
        return v2, (NO_WORD if v2 == "unknown" else None)
    return hook


#: 후보 대장. 각 항은 **이 저장소가 이미 적은 질문**이어야 한다.
CANDIDATES: dict[str, dict] = {
    "clear-ledger-truck": {
        "왜": "clear 인데 대장이 「트럭이 아예 못 지난다」고 말한다. 두 주장이 "
              "동시에 참일 수 없다. `widthcross` 의 OVERCLAIM_HARD 가 세는 것.",
        "근거": "DECISIONS §299 · §305",
        "hook": _veto_clear(lambda p: p["road_bt_m"] is not None
                            and p["road_bt_m"] < LEDGER_BLOCK_M),
    },
    "clear-ledger-clear": {
        "왜": "clear 인데 대장 명목폭이 clear 문턱 미만이다. OVERCLAIM_SOFT.",
        "근거": "DECISIONS §299",
        "hook": _veto_clear(lambda p: p["road_bt_m"] is not None
                            and p["road_bt_m"] < CLEAR_M),
    },
    "clear-gap-clear": {
        "왜": "우리가 대장보다 clear 문턱만큼 더 넓다고 주장한다. 대장이 좁은지가 "
              "아니라 **둘이 어긋나는지**를 본다 — §299 의 바닥이 놓치는 축이다.",
        "근거": "DECISIONS §307",
        "hook": _veto_clear(lambda p: _claims_at_least(_gap(p), CLEAR_M)),
    },
    "clear-samples-3": {
        "왜": "clear 를 표본 2개로 낸다. `verdict()` 는 「표본 1개로는 안 준다」까지만 "
              "막는다. DM02825·DM02647 사고는 둘 다 표본이 얇았다.",
        "근거": "seg/geom.py verdict() 주석 · DECISIONS §245",
        "hook": _veto_clear(lambda p: _fewer_than(p["n_sample"], 3)),
    },
}


def load() -> list[dict]:
    if not PUB.exists():
        raise SystemExit(f"★ 공개본이 없다: {PUB.relative_to(ROOT)}")
    return [f["properties"] for f in
            json.loads(PUB.read_text(encoding="utf-8"))["features"]]


def base(p: dict) -> tuple[str, str | None]:
    return classify(
        wmin=p["width_min_m"], wmax=p["width_max_m"], nreg=p["n_sample"],
        road_bt=p["road_bt_m"], length_m=p["length_m"], cctv_dist=p["cctv_dist_m"],
    )


def _check_repro(rows: list[dict]) -> None:
    """★ 재현이 안 되면 아무 수도 내지 않는다."""
    bad = [p["seg_id"] for p in rows
           if (base(p)[0], base(p)[1]) != (p["verdict"], p["unknown_reason"])]
    if bad:
        raise SystemExit(
            f"★ 재현이 깨졌다 — {len(bad)}/{len(rows)} 건이 공개본과 다르다.\n"
            f"  처음 다섯: {bad[:5]}\n"
            f"  이 상태에서 낸 「전후」는 전후가 아니므로 **아무 수도 내지 않는다.**\n"
            f"  `classify()` 와 공개본 중 하나가 낡았다. 재현:\n"
            f"    uv run python -m pytest tests/test_classify_published.py -q"
        )


def measure(rows: list[dict], hook: Hook) -> dict:
    moved, flow = [], collections.Counter()
    for p in rows:
        v0, r0 = base(p)
        v1, r1 = hook(p, v0, r0)
        flow[(v0, v1)] += 1
        if (v1, r1) != (v0, r0):
            moved.append({
                "seg": p["seg_id"], "도로명": p["road_name"],
                "전": v0, "후": v1, "사유": r1,
                "wmin": p["width_min_m"], "wmax": p["width_max_m"],
                "대장": p["road_bt_m"], "표본": p["n_sample"],
                "cov": p["width_cov"], "길이": p["length_m"],
                "CCTV": p["cctv_dist_m"], "src": p["width_src"],
            })
    after = collections.Counter()
    for (_, v1), n in flow.items():
        after[v1] += n
    return {
        "전": {k: sum(n for (v0, _), n in flow.items() if v0 == k) for k in ORDER},
        "후": {k: after[k] for k in ORDER},
        "이동": len(moved),
        "간선": {f"{a}→{b}": n for (a, b), n in sorted(flow.items()) if a != b},
        "구간": moved,
    }


def _fmt(name: str, cand: dict, res: dict, detail: bool) -> str:
    out = [f"── {name} " + "─" * max(0, 56 - len(name)),
           f"   왜   {cand['왜']}",
           f"   근거 {cand['근거']}",
           f"   이동 {res['이동']}건"]
    if res["간선"]:
        out.append("        " + " · ".join(f"{k} {v}" for k, v in res["간선"].items()))
    b, a = res["전"], res["후"]
    out.append("        " + "  ".join(
        f"{k} {b[k]}" + (f"→{a[k]}" if a[k] != b[k] else "") for k in ORDER))
    if detail and res["구간"]:
        out.append(f"   {'구간':9s} {'도로명':16s} {'wmin':>7s} {'대장':>5s} "
                   f"{'표본':>4s} {'cov':>6s} {'CCTV':>6s}  후")
        for m in sorted(res["구간"], key=lambda m: -(m["wmin"] or 0)):
            out.append(f"   {m['seg']:9s} {str(m['도로명'])[:16]:16s} "
                       f"{(m['wmin'] if m['wmin'] is not None else float('nan')):7.2f} "
                       f"{(m['대장'] if m['대장'] is not None else float('nan')):5.1f} "
                       f"{m['표본']:4d} {m['cov']!s:>6s} {m['CCTV']:6.1f}  "
                       f"{m['후']}{'/' + m['사유'] if m['사유'] else ''}")
    return "\n".join(out)


def selftest() -> int:
    """판별식이 살아 있는가. 실제 자료 없이 도는 것만 본다."""
    fails = []
    row = dict(seg_id="DM00000", road_name="시험길", width_min_m=9.0,
               width_max_m=20.0, n_sample=2, road_bt_m=2.0, length_m=50.0,
               cctv_dist_m=0.0, width_cov=1.0, width_src="ngii1k",
               verdict="clear", unknown_reason=None)
    if base(row)[0] != "clear":
        fails.append("기준선이 clear 를 안 낸다 — 시험 행이 낡았다")

    # ① 후보가 실제로 판정을 내리는가
    r = measure([row], CANDIDATES["clear-ledger-truck"]["hook"])
    if r["이동"] != 1 or r["후"]["clear"] != 0:
        fails.append("대장 2.0m 인 clear 를 후보가 안 내렸다")

    # ② 해당 없는 행은 안 건드리는가 — 이것이 없으면 후보가 전부를 내려도 통과한다
    wide = dict(row, road_bt_m=20.0)
    if measure([wide], CANDIDATES["clear-ledger-truck"]["hook"])["이동"] != 0:
        fails.append("대장이 넓은 clear 를 후보가 건드렸다")

    # ③ 내린 뒤 CCTV 강등이 다시 걸리는가 — 이동이 needs_cv 에서 안 멈춘다
    far = dict(row, cctv_dist_m=9999.0)
    got = measure([far], CANDIDATES["clear-ledger-truck"]["hook"])
    if got["후"]["unknown"] != 1:
        fails.append(f"CCTV 밖인데 unknown 으로 안 갔다 — {got['후']}")
    if got["구간"] and got["구간"][0]["사유"] != NO_WORD:
        fails.append(f"강등 사유가 {NO_WORD} 가 아니다 — 후보가 거짓 낱말을 냈다 "
                     f"({got['구간'][0]['사유']})")

    # ④ 재현 검사가 실제로 죽이는가 — 이것이 없으면 재현이 깨져도 수가 나간다
    liar = dict(row, verdict="blocked")
    try:
        _check_repro([liar])
    except SystemExit:
        pass
    else:
        fails.append("공개본과 어긋나는 행을 재현 검사가 통과시켰다")

    # ⑤ 후보마다 근거가 있는가
    for nm, cand in CANDIDATES.items():
        if "§" not in cand["근거"]:
            fails.append(f"{nm} 에 § 근거가 없다 — 문턱을 발명한 것이다")

    # ⑥ 모르는 값을 **한 번도 유리하게** 안 쓰는가
    #    ★ 돌연변이 셋이 이 자리에서 살아남았다(§396). `(X or 0)` 은 「없다」와
    #      「0」을 같은 것으로 읽었고, 맞는 답이 나오는 이유가 어디에도 없었다.
    if _claims_at_least(None, 7.0):
        fails.append("모르는 어긋남으로 「어긋난다」를 주장한다")
    if not _claims_at_least(7.0, 7.0) or _claims_at_least(6.9, 7.0):
        fails.append("문턱 판단이 경계에서 틀렸다")
    if not _fewer_than(None, 3):
        fails.append("표본 수를 모르는데 **충분하다**고 읽는다 — clear 가 나간다")
    if _fewer_than(3, 3) or not _fewer_than(2, 3):
        fails.append("표본 문턱이 경계에서 틀렸다")

    # ⑦ 그 정책이 후보에 **실제로 꽂혀 있는가** — 함수만 맞고 안 쓰면 소용없다
    blind = dict(row, n_sample=None)
    if measure([blind], CANDIDATES["clear-samples-3"]["hook"])["이동"] != 1:
        fails.append("표본 수가 없는 clear 를 `clear-samples-3` 이 안 내렸다")
    nogap = dict(row, road_bt_m=None)
    if measure([nogap], CANDIDATES["clear-gap-clear"]["hook"])["이동"] != 0:
        fails.append("대장이 없는데 `clear-gap-clear` 가 어긋남을 주장했다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 7")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="판정 규칙 변경을 공개본으로 잰다")
    ap.add_argument("--rule", help="후보 이름 하나. 증거 표까지 낸다")
    ap.add_argument("--list", action="store_true", help="후보 대장만")
    ap.add_argument("--json", metavar="OUT", help="표를 파일로")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    if a.list:
        print("── 후보 대장 ──")
        for nm, c in CANDIDATES.items():
            print(f"  {nm:22s} {c['근거']}\n  {'':22s} {c['왜']}")
        return 0

    rows = load()
    _check_repro(rows)
    print(f"공개본 {len(rows)}구간 · 재현 {len(rows)}/{len(rows)} — 전후를 잴 수 있다\n")

    names = [a.rule] if a.rule else list(CANDIDATES)
    if a.rule and a.rule not in CANDIDATES:
        raise SystemExit(f"★ 모르는 후보: {a.rule}\n  대장: {', '.join(CANDIDATES)}")

    out = {}
    for nm in names:
        res = measure(rows, CANDIDATES[nm]["hook"])
        out[nm] = res
        print(_fmt(nm, CANDIDATES[nm], res, detail=bool(a.rule)))
        print()

    print("★ 이 도구는 어느 후보가 옳은지 말하지 않는다. 이동량과 증거를 내고 멈춘다.")
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")
        print(f"   → {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
