#!/usr/bin/env python3
"""
tools/survey_queue.py — **다음에 뭘 잴지 정하는 대장**을 낸다 (`data/processed/survey_queue.csv`)

    uv run python tools/survey_queue.py             대장을 쓰고 사유별 현재 수를 찍는다
    uv run python tools/survey_queue.py --selftest  ★ 사유 판별식이 살아 있나

════════════════════════════════════════════════════════════════
★ **PLAN 에 올리지 않는다 — 할 일 목록이 아니다.** 사람이 네이버 거리재기로 재러 갈 때 여는 파일이고, 사유와 좌표와 순서를 든다. (PLAN 에는 `#6` 하나만 남는 규칙 그대로다.)
★ 판정에 닿지 않는다. 칸도 안 만든다. CSV 하나와 이 도구 하나다. 사람이 부른다.

── 사유 태그 — **정의가 이 파일 한 곳에만 있다**(`TAGS` · `reasons_of`) ─────────────────
  nfa_access       소방서 지정 구간인데 `clear` 다(정확 일치 · `len_ratio` 0.5~2.0 안 — Zm8 관문이 막는 그것).  → 소방서가 적은 폭과 맞는지 그 자리를 잰다
  source_conflict  `clear` 였다가 **소스 무관 최솟값 < 7.0m**(`CLEAR_M`)라 내려간 구간(규칙 [8] · [10]).      → 좁은 값을 낸 소스가 맞는지 그 지점을 잰다
  sym_low          `clear` 였다가 **대칭폭 < 3.0m**(`TRUCK`)라 내려간 구간(규칙 [9]).                      → 중심선이 경계에 붙은 그 지점의 실폭을 잰다
  escape_rule      **발행된 최솟값이 `escape` 규칙으로 나왔다**(`width_min_sample_idx` 의 표본이 `w_rule = escape`). 가장 깨진 규칙이다 — 현장 7점에서 배율이 0.32~13.18 로 전부 어긋났다.
  amp_high         단일 소스 구간 안에서 폭이 10m 이상 변한다(유효 표본 3개 이상). 원인 미확인(주차장 · 교차로 · 곡률 기각).  → 그 구간이 도로 면인지 확인한다
  subphys          폭 1.0m 미만 표본이 섞였다(`n_subphys` ≥ 1).                                          → 그 지점이 실제 통로인지 확인한다
  ledger_far       대장폭과 **3배 이상** 다르다(`width_min_m / road_bt_m` ≥ 3 또는 ≤ 1/3).               → 어느 쪽이 현황인지 확인한다
★ 「`clear` 였다가 내려간」 판정은 **`classify()` 에 규칙 [8]~[10] 의 입력 없이** 다시 먹여 `clear` 가 나오는 구간 중 지금 `clear` 가 아닌 것이다 — 판정 문은 하나다(§303). 같은 사유를 여기서 다시 적지 않는다.

── 한 줄 · 좌표 · 순서 ────────────────────────────────────────────
· **한 구간이 여러 사유에 걸리면 사유를 모아 한 줄로 낸다**(`|` 로 이음). 같은 자리를 두 번 가지 않게.
· `lat`·`lon` 은 **한 점**이다: 소스 충돌 → 소스 무관 최솟값이 나온 위치 · 그 밖 사유 → 발행 최솟값 표본 위치 · 둘 다 없으면 구간 중점. 어느 점인지는 `무엇을_잴지` 가 말한다.
· **이미 잰 구간은 `measured_m` 에 값(같은 구간의 현장 측선 중앙값)을 넣고 맨 뒤로 보낸다**(`data/field/naver_width_2610.csv` — `seg_uid` 가 있는 줄만 구간에 붙는다).
· 정렬은 `occ_pressure_rank`(폭 밴드 안 순위 · 작은 것 먼저) → 같으면 `occ_pressure` 큰 것 → `seg_uid`. **rank 가 null 인 구간은 맨 뒤(잰 구간 앞)** 이고 `순서_비고` 칸에 그 이유를 적는다 —
  순서를 못 매긴 것이지 급하지 않은 것이 아니다(동명동 밖은 건축물대장이 없어 β 를 못 잰다).
· **부를 때마다 사유별 현재 수를 찍는다. 수가 바뀌면 판정이 움직였다는 신호다.**

IN    web/data/segments.geojson · data/processed/{segments_5186.gpkg,width_samples.csv} · data/field/naver_width_2610.csv
OUT   data/processed/survey_queue.csv (UTF-8 BOM — processed 산출물이라 커밋 안 한다)
PARAM 없음
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
밖    **무엇이 참인지는 안 정한다** — 어디를 재야 하는지만 낸다. 판정 · 칸을 안 만든다. 사유 문턱(3배 · 10m · 1.0m)은 이 도구가 정한 것이다(측정으로 도출하지 않았다).
"""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import Counter, defaultdict

from firelane.paths import PROCESSED, ROOT
from firelane.seg.classify import CLEAR_M, classify
from firelane.seg.params import TRUCK

AMP_M = 10.0
SUBPHYS_M = 1.0
LEDGER_X = 3.0
TAGS = {
    "nfa_access": "소방서가 적은 폭(지정 구간)과 맞는지 그 자리를 잰다",
    "source_conflict": "좁은 값을 낸 소스가 맞는지 그 지점(소스 무관 최솟값)을 잰다",
    "sym_low": "중심선이 경계에 붙은 그 지점의 실폭을 잰다",
    "escape_rule": "escape 규칙으로 나온 발행 최솟값 — 그 지점의 실폭을 잰다",
    "amp_high": "폭이 10m 이상 변하는 구간 — 그 구간이 도로 면인지 확인한다",
    "subphys": "폭 1.0m 미만 표본 지점이 실제 통로인지 확인한다",
    "ledger_far": "대장폭과 측정 중 어느 쪽이 현황인지 확인한다",
}
COLS = ["seg_id", "seg_uid", "사유", "lat", "lon", "무엇을_잴지", "현재_판정", "width_min_m", "clear_min_m", "clear_med_m",
        "road_bt_m", "cctv_dist_m", "occ_pressure_rank", "measured_m", "순서_비고"]


def was_clear(p: dict) -> bool:
    """규칙 [8]~[11] 없이 `classify()` 가 `clear` 를 내는가 — 「`clear` 였다」의 정의(판정 문은 하나). [11] 은 `spread_max=None` 으로 끈다."""
    return classify(wmin=p["width_min_m"], wmax=p["width_max_m"], nreg=p["n_sample"], road_bt=p["road_bt_m"],
                    length_m=p["length_m"], cctv_dist=p["cctv_dist_m"], spread_max=None)[0] == "clear"


def reasons_of(p: dict, rows: list[dict]) -> list[str]:
    """한 구간의 사유 태그(**정의는 여기 한 곳**). `p` 는 발행 속성, `rows` 는 그 구간의 `width_samples.csv` 행(순서 그대로)."""
    out: list[str] = []
    demoted = p["verdict"] != "clear" and was_clear(p)
    if p["verdict"] == "clear" and p.get("nfa_access_listed") and p.get("nfa_access_loose") is False:
        out.append("nfa_access")
    if demoted and p.get("width_min_any_m") is not None and p["width_min_any_m"] < CLEAR_M:
        out.append("source_conflict")
    if demoted and p.get("width_min_sym_m") is not None and p["width_min_sym_m"] < TRUCK:
        out.append("sym_low")
    i = p.get("width_min_sample_idx")
    if i is not None and 0 <= int(i) < len(rows) and rows[int(i)].get("w_rule") == "escape":
        out.append("escape_rule")
    ok = [r for r in rows if r["w_m"]]
    if len(ok) >= 3 and len({r["src"] for r in ok}) == 1 and max(float(r["w_m"]) for r in ok) - min(float(r["w_m"]) for r in ok) >= AMP_M:
        out.append("amp_high")
    if (p.get("n_subphys") or 0) >= 1:
        out.append("subphys")
    bt, w = p.get("road_bt_m"), p.get("width_min_m")
    if bt and w and (w / bt >= LEDGER_X or w / bt <= 1 / LEDGER_X):
        out.append("ledger_far")
    return out


def pick_s(p: dict, tags: list[str], rows: list[dict]):
    """좌표를 낼 위치 s(m). 소스 충돌 → 소스 무관 최솟값 위치 · 그 밖 → 발행 최솟값 표본 위치 · 없으면 None(중점)."""
    if "source_conflict" in tags and p.get("width_min_any_s_m") is not None:
        return float(p["width_min_any_s_m"])
    i = p.get("width_min_sample_idx")
    if i is not None and 0 <= int(i) < len(rows):
        return float(rows[int(i)]["s_m"])
    return None


def order_key(p: dict):
    rk = p.get("occ_pressure_rank")
    return (rk is None, rk if rk is not None else 0, -(p.get("occ_pressure") or 0.0), str(p.get("seg_uid")))


def order_note(p: dict) -> str:
    if p.get("occ_pressure_rank") is not None:
        return ""
    if not p.get("in_emd"):
        return "rank 없음 — 동명동 밖(건축물대장이 동명동뿐이라 β 를 못 잰다)"
    if p.get("occ_pressure") is None:
        return "rank 없음 — β 를 못 쟀다(수요점 없음)"
    if p["occ_pressure"] == 0:
        return "rank 없음 — 동명동 안인데 수요점이 없다(β = 0)"
    return "rank 없음 — 폭이 없어 밴드를 못 정했다"


def measured_by_uid(path) -> dict[str, float]:
    """이미 잰 구간 → 현장 측선 중앙값(m). `seg_uid` 가 있는 줄만 구간에 붙는다."""
    got: dict[str, list[float]] = defaultdict(list)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("seg_uid") and r.get("w_m"):
                got[r["seg_uid"]].append(float(r["w_m"]))
    return {k: round(statistics.median(v), 2) for k, v in got.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--selftest", action="store_true", help="사유 판별식이 살아 있나")
    if ap.parse_args().selftest:
        return selftest()

    import json

    import geopandas as gpd
    feats = [f["properties"] for f in json.loads((ROOT / "web" / "data" / "segments.geojson").read_text(encoding="utf-8"))["features"]]
    g5186 = gpd.read_file(PROCESSED / "segments_5186.gpkg").set_index("seg_id").geometry
    samples: dict[str, list] = defaultdict(list)
    with (PROCESSED / "width_samples.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            samples[r["seg_id"]].append(r)
    done = measured_by_uid(ROOT / "data" / "field" / "naver_width_2610.csv")

    def lonlat(sid: str, s_m):
        ln = g5186.loc[sid]
        if ln.geom_type != "LineString":
            ln = max(ln.geoms, key=lambda g: g.length)
        pt = ln.interpolate(ln.length / 2 if s_m is None else min(max(s_m, 0.0), ln.length))
        q = gpd.GeoSeries([pt], crs=5186).to_crs(4326).iloc[0]
        return round(q.y, 6), round(q.x, 6)

    tally: Counter = Counter()
    items = []
    for p in feats:
        rows = samples.get(p["seg_id"], [])
        tags = reasons_of(p, rows)
        if not tags:
            continue
        tally.update(tags)
        lat, lon = lonlat(p["seg_id"], pick_s(p, tags, rows))
        meas = done.get(p["seg_uid"])
        items.append(((meas is not None, *order_key(p)), [
            p["seg_id"], p["seg_uid"], "|".join(tags), lat, lon, " / ".join(TAGS[t] for t in tags), p["verdict"],
            p.get("width_min_m"), p.get("clear_min_m"), p.get("clear_med_m"), p.get("road_bt_m"), p.get("cctv_dist_m"),
            "" if p.get("occ_pressure_rank") is None else int(p["occ_pressure_rank"]), "" if meas is None else meas, order_note(p)]))
    items.sort(key=lambda t: t[0])
    dst = PROCESSED / "survey_queue.csv"
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for _, row in items:
            w.writerow(["" if v is None else v for v in row])
    n_meas = sum(1 for k, _ in items if k[0])
    n_null = sum(1 for k, r in items if not k[0] and r[12] == "")
    print(f"survey_queue {len(items)}구간 → {dst}  (이미 잰 {n_meas} 은 맨 뒤 · rank 없는 {n_null} 은 그 앞)")
    print("  사유별 현재 수 — 바뀌면 판정이 움직였다는 신호다: " + " · ".join(f"{t} {tally[t]}" for t in TAGS))
    print(f"  현장 측선이 붙은 구간 {len(done)} (field 파일의 seg_uid 가 있는 줄)")
    return 0


def selftest() -> int:
    bad: list[str] = []
    base = dict(seg_id="D1", seg_uid="u1", verdict="clear", width_min_m=9.0, width_max_m=None, n_sample=20, road_bt_m=8.0, length_m=50.0,
                cctv_dist_m=60.0, width_min_any_m=9.0, width_min_sym_m=9.0, n_subphys=0, nfa_access_listed=False, nfa_access_loose=None,
                width_min_sample_idx=0, occ_pressure_rank=None, occ_pressure=None, in_emd=False)
    rows = [{"w_m": "9.0", "src": "ngii1k", "w_rule": "carve", "s_m": "1.0"}]
    if reasons_of(base, rows):
        bad.append(f"아무 사유가 없는 구간에 사유가 붙었다 — {reasons_of(base, rows)}")
    dem = {**base, "verdict": "unknown", "width_min_any_m": 5.0, "width_min_sym_m": 2.0}          # 규칙 없이는 clear 였다
    if reasons_of(dem, rows) != ["source_conflict", "sym_low"]:
        bad.append(f"내려간 구간 사유가 틀렸다 — {reasons_of(dem, rows)}")
    if "source_conflict" in reasons_of({**dem, "width_min_m": 5.0}, rows):
        bad.append("원래 clear 가 아니었는데 source_conflict 로 셌다")
    if reasons_of({**base, "nfa_access_listed": True, "nfa_access_loose": False}, rows) != ["nfa_access"]:
        bad.append("소방서 지정 clear 가 nfa_access 가 아니다")
    if reasons_of({**base, "nfa_access_listed": True, "nfa_access_loose": True}, rows):
        bad.append("느슨한 매칭이 nfa_access 로 셌다")
    if reasons_of(base, [{**rows[0], "w_rule": "escape"}]) != ["escape_rule"]:
        bad.append("escape 로 나온 발행 최솟값을 못 잡았다")
    if reasons_of({**base, "n_subphys": 2}, rows) != ["subphys"] or reasons_of({**base, "road_bt_m": 2.0}, rows) != ["ledger_far"]:
        bad.append("subphys · ledger_far 판별이 틀렸다")
    amp = [{"w_m": str(w), "src": "a", "w_rule": "carve", "s_m": str(i)} for i, w in enumerate((3.0, 9.0, 14.0))]
    if "amp_high" not in reasons_of({**base, "width_min_sample_idx": None}, amp):
        bad.append("진폭 11m 를 amp_high 로 못 잡았다")
    a, b, c = ({**base, "seg_uid": x, "occ_pressure_rank": r, "occ_pressure": o} for x, r, o in (("a", None, None), ("b", 3, 1.0), ("c", 3, 2.0)))
    if [x["seg_uid"] for x in sorted([a, b, c], key=order_key)] != ["c", "b", "a"] or "동명동 밖" not in order_note(a):
        bad.append("순서 · rank null 사유가 틀렸다")
    if pick_s({**dem}, ["source_conflict"], rows) is not None and pick_s({**dem, "width_min_any_s_m": 7.0}, ["source_conflict"], rows) != 7.0:
        bad.append("좌표 위치 선택이 틀렸다")
    for x in bad:
        print("  ✗", x)
    print("✓ 살아 있다" if not bad else f"✗ {len(bad)}건")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
