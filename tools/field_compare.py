#!/usr/bin/env python3
"""
field_compare.py — 실측 야장을 우리 폭 · 판정과 대조한다.  (DECISIONS §215-4)

    uv run python tools/field_compare.py                    data/field/obs_points.csv
    uv run python tools/field_compare.py --obs 다른.csv
    uv run python tools/field_compare.py --json             기계가 읽는 요약

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-17 멘토링 — 「공공데이터 기반 추천이 맞는지 증명하려면 정답값인 실측이 필요하다.
통과가 불가능한데 가능으로 판정되는 경우가 나오면 보정하라.」 표본 설계(`sample_design.py`
· 25구간 · 관측점 75)와 야장(`fieldsheet.md`)은 8월에 이미 있었는데 **적은 값을 대조하는
도구가 없었다.** 재고 나서 엑셀로 손셈하면 그 숫자는 다시 못 만든다.

── 무엇을 내나 ─────────────────────────────────────────────────
  ① 점 오차   우리 width_min_m − 실측. 측정 종류(wall · curb · passable · corner)별로 따로
              ★ 섞지 않는다. 담~담과 통행폭은 다른 양이고, 섞은 평균은 어느 쪽도 아니다
  ② 구간 판정 실측 최솟값으로 다시 가른 판정 대 우리 판정
              ★ **위험 오판**(우리 초록 · 실측 기준폭 미만)을 맨 위에 센다. 이것이 0 이 아니면
                보정 대상이다. 반대 방향(우리 빨강 · 실측 넉넉)은 손해지만 위험하지 않다
  ③ 보정 제안 위험 오판을 없애는 최소 차감값(m). **제안만 한다** — 판정 코드를 안 바꾼다.
              바꾸는 것은 측정 배치이고 golden 재잠금이 따른다

★ 트랙 C 는 따로 센다. 설계상 **우리 예측을 안 보고 잰 봉인 표본**이라 보정 근거로 쓰면
  외부 검증 수단이 다시 0 이 된다(대장 field_sample.known_issues). 보정 제안은 A · B 로만 낸다.
★ 빈 칸(아직 안 잰 점)은 건너뛴다. 10곳만 재도 돈다.
★ 문턱은 `seg/params.py` 의 TRUCK · PARK 를 그대로 읽는다. 여기서 재선언하지 않는다.

IN    data/field/obs_points.csv (measured_m · kind 를 채운 것)
OUT   없음 (표준출력)
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from firelane.paths import ROOT
from firelane.seg.params import PARK, TRUCK

OBS = ROOT / "data" / "field" / "obs_points.csv"
KINDS = ("wall", "curb", "passable", "corner")


def field_verdict(w: float) -> str:
    """실측 폭 하나로 가른 판정. 파이프라인의 폭 문턱과 같은 두 줄이다."""
    if w < TRUCK:
        return "blocked"
    if w >= TRUCK + 2 * PARK:
        return "clear"
    return "band"            # 주정차에 달린 폭 — 우리 말로 영상판정 대상


def load(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m = (r.get("measured_m") or "").strip()
            if not m:
                continue
            try:
                r["measured"] = float(m)
            except ValueError:
                raise SystemExit(f"★ {r['obs_id']} 실측값이 숫자가 아니다: {m!r}") from None
            r["kind"] = (r.get("kind") or "").strip() or "?"
            w = (r.get("width_min_m") or "").strip()
            r["ours"] = float(w) if w else None
            rows.append(r)
    return rows


def summarize(rows: list[dict]) -> dict:
    out: dict = {"points": len(rows), "by_kind": {}, "segments": [], "tracks": {}}
    for k in sorted({r["kind"] for r in rows}):
        errs = [r["ours"] - r["measured"] for r in rows if r["kind"] == k and r["ours"] is not None]
        if errs:
            out["by_kind"][k] = {
                "n": len(errs), "bias_m": round(statistics.fmean(errs), 2),
                "mae_m": round(statistics.fmean(abs(e) for e in errs), 2),
                "within_05": round(sum(abs(e) <= 0.5 for e in errs) / len(errs), 2),
            }
    segs: dict[str, dict] = {}
    for r in rows:
        s = segs.setdefault(r["seg_uid"], {"seg_uid": r["seg_uid"], "track": r["track"],
                                           "road": r.get("road_name", ""), "verdict": r["verdict"],
                                           "ours": r["ours"], "measured": []})
        s["measured"].append(r["measured"])
    for s in segs.values():
        s["field_min"] = min(s["measured"])
        s["field_verdict"] = field_verdict(s["field_min"])
        # ★ 위험 오판 — 우리는 통과라 했는데 실측은 기준폭도 안 된다
        s["danger"] = s["verdict"] == "clear" and s["field_verdict"] == "blocked"
        s["loss"] = s["verdict"] == "blocked" and s["field_verdict"] == "clear"
        del s["measured"]
        out["segments"].append(s)
    for t in sorted({s["track"] for s in out["segments"]}):
        ss = [s for s in out["segments"] if s["track"] == t]
        out["tracks"][t] = {"segments": len(ss), "danger": sum(s["danger"] for s in ss),
                            "loss": sum(s["loss"] for s in ss)}
    # 보정 제안 — A · B 만. 위험 오판 구간에서 (우리 폭 − 실측 최소) 의 최댓값만큼 빼면 없어진다
    open_ = [s for s in out["segments"] if s["track"] != "C" and s["danger"] and s["ours"] is not None]
    out["suggest_shrink_m"] = round(max((s["ours"] - s["field_min"] for s in open_), default=0.0), 2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--obs", type=Path, default=OBS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not a.obs.exists():
        raise SystemExit(f"★ 야장이 없다: {a.obs}  (uv run python -m firelane.sample_design)")
    rows = load(a.obs)
    if not rows:
        print(f"아직 잰 점이 없다 — {a.obs} 의 measured_m · kind 를 채운다(fieldsheet.md 참조)")
        return 0
    s = summarize(rows)
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0

    print(f"실측 {s['points']}점 · 구간 {len(s['segments'])} · 문턱 TRUCK {TRUCK} · PARK {PARK} (seg/params.py)\n")
    print("① 점 오차 — 우리 width_min_m − 실측 (양수 = 우리가 넓게 봤다)")
    for k, v in s["by_kind"].items():
        tag = "" if k in KINDS else "   ★ 종류가 비었거나 모르는 값 — 야장 규칙 위반"
        print(f"   {k:9} {v['n']:3}점  치우침 {v['bias_m']:+.2f}m  평균절대 {v['mae_m']:.2f}m"
              f"  ±0.5m 안 {v['within_05']:.0%}{tag}")
    print("\n② 구간 판정 — 트랙별")
    for t, v in s["tracks"].items():
        seal = "   (봉인 — 보정 근거로 안 쓴다)" if t == "C" else ""
        print(f"   트랙 {t}  {v['segments']:2}구간  위험 오판 {v['danger']}  손해 오판 {v['loss']}{seal}")
    bad = [x for x in s["segments"] if x["danger"]]
    if bad:
        print("\n   ★ 위험 오판 — 우리 초록 · 실측 기준폭 미만")
        for x in bad:
            print(f"     {x['seg_uid']}  {x['road']}  우리 {x['ours']}m · 실측 최소 {x['field_min']}m  (트랙 {x['track']})")
    print(f"\n③ 보정 제안 (A·B)  폭 {s['suggest_shrink_m']:.2f}m 차감이면 위험 오판 0")
    print("   ★ 제안이다. 판정을 바꾸는 것은 측정 배치이고 golden 재잠금이 따른다")
    return 1 if any(v["danger"] for t, v in s["tracks"].items() if t != "C") else 0


if __name__ == "__main__":
    raise SystemExit(main())
