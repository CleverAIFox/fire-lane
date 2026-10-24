#!/usr/bin/env python3
"""
tools/evalset.py — 0판 평가셋을 **뽑는다**(그리고 사람이 채운 뒤에 채점한다).  (Zm23 · DECISIONS §569)

    uv run python tools/evalset.py              평가셋을 뽑아 data/field/evalset_2610.csv · .key.json 을 쓴다
    uv run python tools/evalset.py --score      ★ 사람이 채운 뒤에만 — 채점한다 (채우기 전에는 거부한다)
    uv run python tools/evalset.py --selftest   판별식이 살아 있나

── 목적 — 이 표 하나로 여섯 물음에 답한다 ─────────────────────
  Q1  `width_med_m` 이 실제 대표폭(전폭)과 맞나
  Q2  `width_min_m` 이 실제 최협부와 맞나
  Q3  우리 측선이 최협부를 잡나 (위치가 맞나)
  Q4  규칙 [12](대장 괴리)가 거두는 구간이 실제로 의심스러운가
  Q5  체제 분류(편심 · escape · 둘 다 멀쩡 · 둘 다 발동)가 실제 형태와 맞나
  Q6  DM01876 · DM00562 가 왜 어느 규칙에도 안 걸리나

── 구성 — 55구간을 **한 표**로 ──────────────────────────────────
  체제별 31      편심만 10 · escape만 8 · 둘다멀쩡 8 · 둘다발동 5          (Q5)
  A 확인용 10    `#17` 이 내접원 중앙값으로 거두는 62구간에서 무작위         (Q4)
  대조군 12      정상군(|d| ≤ 1)에서 무작위                                (Q1 · Q2 기준선)
  지명 2         DM01876 · DM00562                                         (Q6)
  ※ 같은 구간이 두 묶음에 들지 않는다. 묶음은 **지명 → 체제 → A 확인 → 대조군** 순으로 뽑고 앞 묶음이 쓴 구간은 뒤에서 뺀다.

★ **표에 묶음을 적지 않는다**(사람이 보면 눈금이 끌린다). 묶음은 `evalset_2610.key.json` 에 봉인하고 **채점 전에 열지 않는다.**
★ **뽑는 코드가 판정 · d · 폭으로 정렬하지 않는다.** 후보는 `seg_id` 순으로 놓고 시드로 뽑고, 마지막에 시드로 섞는다.
★ **체제 정의는 이 도구가 짓지 않는다.** `firelane.regime`(2×2 · 판정 폐포 밖)을 그대로 쓴다. 폭 급변(`SPREAD_MAX`)과 대장 괴리(`|d|`)는 체제가 아니라 **별도 표시**이고 봉인 키에 체제와 따로 적는다 — 섞어서 여섯으로 만들지 않는다.
★ 시드는 기존 규약이다(`tools/evalgen.py` 의 `SEED`).

── 표 ────────────────────────────────────────────────────────
미리 싣는 칸: `seg_id` · `위도` · `경도`(WGS84 · 소수 6자리 — 구간 **중점**) · `도로명` · `length_m`. **우리 측정값 · 대장값 · 판정은 안 싣는다.**
사람이 채울 칸(넷): `w_full_m`(전폭 — 한쪽 경계에서 반대편 경계까지) · `w_narrow_m`(그 구간에서 가장 좁은 곳의 폭) ·
`narrow_s_m`(그 최협부가 **구간 시작**에서 몇 m 지점인가 · ±5m 면 충분) · `note`(특이사항 한 줄). `method` 는 도구가 채운다.
측정 규약은 csv 머리의 `#` 주석에 박는다.

── 채점 (`--score`) ───────────────────────────────────────────
사람이 채운 뒤에 돈다. 채워진 행이 없으면 **키 파일을 열지 않고 거부한다.**
  Q1 `w_full_m` 대 `width_med_m` · Q2 `w_narrow_m` 대 `width_min_m` : 오차(우리 − 실측) 중앙 · 사분위, 묶음별로 따로
  Q3 `narrow_s_m` 대 `width_min_sample_idx` 가 가리키는 표본 위치 : 거리 차
  Q4 대조군 대 규칙 [12] 가 거둘 구간의 Q1 · Q2 오차가 다른가(맨-휘트니) — 다르면 [12] 에 근거가 서고 같으면 근거가 없다
  Q5 체제별 Q1 · Q2 오차가 다른가(크러스컬-월리스) — 체제 규칙의 반증 가능성
  Q6 지명 둘의 `note`
★ 채워지면 `field.fingerprint.json` 에 박는 경로: `uv run python tools/fieldseal.py --write` (사람이 친다 — 이 도구는 안 한다).

IN    web/data/segments.geojson · data/processed/{segments_5186.gpkg,width_samples.csv}
OUT   data/field/evalset_2610.csv · data/field/evalset_2610.key.json
PARAM `SIZES` · 시드(`evalgen.SEED`)
밖    **판정을 안 바꾼다.** 값이 옳은지는 사람이 잰 값이 정한다. 정사영상 자동 측정은 안 한다(타당성만 본다 — DECISIONS §569-8).
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from evalgen import SEED
from ledgercross import _midpoints, gap, is_step, steps_of
from statkit import num, quartiles

from firelane import regime as R
from firelane.paths import PROCESSED, ROOT, WEB

OUT_CSV = ROOT / "data" / "field" / "evalset_2610.csv"
OUT_KEY = ROOT / "data" / "field" / "evalset_2610.key.json"
SEG = WEB / "segments.geojson"
SAMPLES = PROCESSED / "width_samples.csv"

REGIMES = (R.ECC_ONLY, R.ESCAPE_ONLY, R.NONE_, R.BOTH)     # 요청의 순서: 편심 · escape · 둘다멀쩡 · 둘다발동
SIZES = {"지명": 2, R.ECC_ONLY: 10, R.ESCAPE_ONLY: 8, R.NONE_: 8, R.BOTH: 5, "A 확인": 10, "대조군": 12}
NAMED = ("DM01876", "DM00562")
HUMAN_COLS = ("w_full_m", "w_narrow_m", "narrow_s_m", "note")
COLS = ("seg_id", "위도", "경도", "도로명", "length_m", *HUMAN_COLS, "method")
NORMAL_GAP = 1

PROTOCOL = (
    "# 측정 규약 (Zm23 · DECISIONS §569) — 이 머리는 읽는 쪽이 '#' 로 시작하는 줄을 건너뛴다",
    "# 1) 전폭(w_full_m)과 최협부 폭(w_narrow_m)을 같은 구간에서 둘 다 잰다. 하나만 재면 Q1 과 Q2 가 섞인다",
    "# 2) 주차 차량 · 적치물은 빼고 경계(담장 · 건물면) 기준으로 잰다. 통행 가능 폭은 재지 않는다 — CLEAR_M 문턱이 이미 흡수한다",
    "# 3) narrow_s_m = 최협부가 '구간 시작'(표의 위경도가 아니라 seg 시작)에서 대략 몇 m 지점인가. ±5m 면 충분하다",
    "# 4) note = 특이사항 한 줄 (복개천 · 구거 · 아케이드 · 주차 · 공터 등)",
    "# 5) method 칸은 도구가 채운다. 사람이 쓰는 도구는 요청이 정한다",
)


# ── 체제 · 묶음 ─────────────────────────────────────────────────
def regime_of(p: dict, samples: list[dict]) -> str | None:
    """체제 이름(`firelane.regime` 의 2×2). 편심 값이 없으면 `None`."""
    return R.regime_of(num(p.get("ecc_rel_med_m")), [r.get("w_rule") for r in samples if r.get("w_m")])


def marks_of(p: dict, steps: list[float]) -> dict:
    """체제 **위에 덧씌우는 표시** — 체제가 아니다. 폭 급변(`SPREAD_MAX`)과 대장 괴리(`|d| ≥ 3`, 중앙값 기준 · 규칙 [12] 의 정의)."""
    from firelane.seg.classify import SPREAD_MAX

    wmx, wmn, lg, wm = num(p.get("width_max_m")), num(p.get("width_min_m")), num(p.get("road_bt_m")), num(p.get("width_med_m"))
    return {"spread": bool(wmx and wmn and wmn > 0 and wmx / wmn >= SPREAD_MAX),
            "ledger_gap": bool(lg is not None and wm is not None and is_step(lg) and abs(gap(lg, wm, steps)[0]) >= 3)}


def was_clear_before_median(p: dict) -> bool:
    """`#17` 의 「중앙값으로 거두는 62구간」의 전제 — 중앙값 규칙 **없이** `clear` 였는데 내접원 중앙값이 문턱 미만."""
    from firelane.seg.classify import CLEAR_M, classify

    v = classify(wmin=p["width_min_m"], wmax=p["width_max_m"], nreg=p["n_sample"], road_bt=p["road_bt_m"], length_m=p["length_m"],
                 cctv_dist=p["cctv_dist_m"], wmin_any=p["width_min_any_m"], wsym=p["width_min_sym_m"], clear_med=None, spread_max=None)[0]
    return v == "clear" and p.get("clear_med_m") is not None and p["clear_med_m"] < CLEAR_M


def normal_group(rows: list[dict]) -> set[str]:
    """정상군 — 대장 계단과의 차 `|d| ≤ 1`(최솟값 기준 · `ledgercross` 와 같은 정의)."""
    steps = steps_of([num(r["road_bt_m"]) for r in rows if num(r.get("road_bt_m")) is not None])
    out = set()
    for r in rows:
        lg, w = num(r.get("road_bt_m")), num(r.get("width_min_m"))
        if lg is not None and w is not None and is_step(lg) and abs(gap(lg, w, steps)[0]) <= NORMAL_GAP:
            out.add(r["seg_id"])
    return out


def draw(rows: list[dict], samples_by: dict[str, list[dict]], seed: int = SEED,
         sizes: dict[str, int] | None = None) -> dict[str, list[str]]:
    """묶음 → seg_id 목록. 정렬 키가 판정 · d · 폭이 아니다 — 후보는 `seg_id` 순, 뽑기는 시드."""
    sz = SIZES if sizes is None else sizes
    rng = random.Random(seed)
    by_id = {r["seg_id"]: r for r in sorted(rows, key=lambda r: r["seg_id"])}
    taken: set[str] = set()
    out: dict[str, list[str]] = {}

    def take(name: str, pool: list[str]) -> None:
        pool = [s for s in pool if s not in taken]
        k = sz[name]
        if len(pool) < k:
            raise SystemExit(f"{name}: 후보 {len(pool)} < 필요 {k}")
        got = rng.sample(pool, k)
        taken.update(got)
        out[name] = got

    out["지명"] = [s for s in NAMED if s in by_id][: sz["지명"]]
    taken.update(out["지명"])
    reg = {s: regime_of(r, samples_by.get(s, [])) for s, r in by_id.items()}
    for name in REGIMES:
        take(name, [s for s, g in reg.items() if g == name])
    take("A 확인", [s for s, r in by_id.items() if was_clear_before_median(r)])
    nm = normal_group(rows)
    take("대조군", [s for s in by_id if s in nm])
    return out


def load() -> tuple[list[dict], dict[str, list[dict]]]:
    rows = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    by: dict[str, list[dict]] = {}
    with SAMPLES.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            by.setdefault(r["seg_id"], []).append(r)
    return rows, by


def build(rows: list[dict], samples_by: dict[str, list[dict]], seed: int = SEED,
          sizes: dict[str, int] | None = None, mids: dict | None = None) -> tuple[list[dict], dict]:
    """(섞인 표 행들, 봉인 키). 표 행에는 묶음 정보가 없다."""
    groups = draw(rows, samples_by, seed, sizes)
    by_id = {r["seg_id"]: r for r in rows}
    mids = _midpoints() if mids is None else mids
    ids = [s for g in groups.values() for s in g]
    random.Random(seed + 1).shuffle(ids)
    table = []
    for s in ids:
        r = by_id[s]
        lat, lon = mids.get(s, (None, None))
        table.append({"seg_id": s, "위도": "" if lat is None else f"{lat:.6f}", "경도": "" if lon is None else f"{lon:.6f}",
                      "도로명": r.get("road_name") or "", "length_m": r.get("length_m"), "w_full_m": "", "w_narrow_m": "",
                      "narrow_s_m": "", "note": "", "method": ""})
    steps = steps_of([num(r["road_bt_m"]) for r in rows if num(r.get("road_bt_m")) is not None])
    marks = {s: {"regime": regime_of(by_id[s], samples_by.get(s, [])), **marks_of(by_id[s], steps)} for s in ids}
    key = {"seed": seed, "sizes": dict(SIZES if sizes is None else sizes),
           "regime_definition": {"module": "firelane.regime", "ecc_threshold": R.ECC_THRESHOLD, "escape": "w_rule == escape 가 하나 이상"},
           "groups": groups, "marks": marks, "note": "채점 전에 열지 않는다. 묶음을 보면 측정 눈금이 끌린다."}
    return table, key


def write(table: list[dict], key: dict, csv_path: Path = OUT_CSV, key_path: Path = OUT_KEY) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:           # BOM 없이 · LF (커밋 훅과 같은 꼴)
        f.write("\n".join(PROTOCOL) + "\n")
        w = csv.DictWriter(f, fieldnames=list(COLS), lineterminator="\n")
        w.writeheader()
        w.writerows(table)
    key_path.write_text(json.dumps(key, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# ── 채점 ────────────────────────────────────────────────────────
def read_filled(csv_path: Path | None = None) -> list[dict]:
    """채워진 행만. `#` 머리는 건너뛴다. 키 파일은 여기서 안 연다."""
    csv_path = OUT_CSV if csv_path is None else csv_path
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return [r for r in csv.DictReader(lines) if num(r.get("w_full_m")) is not None or num(r.get("w_narrow_m")) is not None]


def _err(vals: list[float]) -> dict:
    q = quartiles(vals)
    return {"n": len(vals), **{k: round(v, 3) for k, v in q.items() if k != "n"}} if vals else {"n": 0}


def score(rows: list[dict], samples_by: dict[str, list[dict]], filled: list[dict], key: dict) -> dict:
    """Q1~Q6. `key` 는 호출자가 채점 시점에 연다."""
    by_id = {r["seg_id"]: r for r in rows}
    grp = {s: g for g, ss in key["groups"].items() for s in ss}
    res: dict = {"Q1": {}, "Q2": {}, "Q3": {}, "Q6": {}}
    e1: dict[str, list[float]] = {}
    e2: dict[str, list[float]] = {}
    e3: dict[str, list[float]] = {}
    for r in filled:
        s = r["seg_id"]
        p, g = by_id[s], grp.get(s, "?")
        wf, wn, ns = num(r.get("w_full_m")), num(r.get("w_narrow_m")), num(r.get("narrow_s_m"))
        if wf is not None and p.get("width_med_m") is not None:
            e1.setdefault(g, []).append(p["width_med_m"] - wf)
        if wn is not None and p.get("width_min_m") is not None:
            e2.setdefault(g, []).append(p["width_min_m"] - wn)
        idx = p.get("width_min_sample_idx")
        rows_s = samples_by.get(s, [])
        if ns is not None and idx is not None and 0 <= int(idx) < len(rows_s):
            e3.setdefault(g, []).append(abs(float(rows_s[int(idx)]["s_m"]) - ns))
        if g == "지명":
            res["Q6"][s] = r.get("note", "")
    for name, e in (("Q1", e1), ("Q2", e2), ("Q3", e3)):
        res[name] = {g: _err(v) for g, v in sorted(e.items())}
        res[name]["전체"] = _err([x for v in e.values() for x in v])
    from scipy.stats import kruskal, mannwhitneyu

    ctrl, a_chk = e1.get("대조군", []), e1.get("A 확인", [])
    res["Q4"] = {"대조군_n": len(ctrl), "A확인_n": len(a_chk),
                 "Q1_p": None if min(len(ctrl), len(a_chk)) < 3 else float(mannwhitneyu(ctrl, a_chk).pvalue),
                 "Q2_p": None if min(len(e2.get("대조군", [])), len(e2.get("A 확인", []))) < 3
                 else float(mannwhitneyu(e2["대조군"], e2["A 확인"]).pvalue),
                 "읽는 법": "p 가 작으면 두 묶음의 오차가 다르다 → 규칙 [12] 에 근거가 선다. 같으면 근거가 없다."}
    reg_groups = [e1[g] for g in REGIMES if len(e1.get(g, [])) >= 2]
    res["Q5"] = {"Q1_p": None if len(reg_groups) < 2 else float(kruskal(*reg_groups).pvalue), "체제_n": {g: len(e1.get(g, [])) for g in REGIMES}}
    return res


def selftest() -> int:
    bad: list[str] = []
    rows = [{"seg_id": f"DM{i:05d}", "road_name": "x", "length_m": 30.0, "ecc_rel_med_m": (i % 10) / 10, "road_bt_m": 8.0,
             "width_min_m": 7.5, "width_med_m": 7.8, "width_min_sample_idx": 0, "width_max_m": None, "n_sample": 10,
             "cctv_dist_m": 5.0, "width_min_any_m": 7.5, "width_min_sym_m": 7.5, "clear_med_m": 5.0 if i % 5 == 0 else 20.0} for i in range(400)]
    rows += [{**rows[0], "seg_id": n} for n in NAMED]
    samples = {r["seg_id"]: [{"seg_id": r["seg_id"], "s_m": "1.0", "w_m": "5.0", "w_rule": "escape" if int(r["seg_id"][2:7] or 0) % 4 == 0 else "carve"}
                             for _ in range(4)] for r in rows if r["seg_id"].startswith("DM0")}
    mids = {r["seg_id"]: (35.1, 126.9) for r in rows}
    sz = {"지명": 2, R.ECC_ONLY: 3, R.ESCAPE_ONLY: 3, R.NONE_: 3, R.BOTH: 3, "A 확인": 3, "대조군": 3}
    try:
        t, k = build(rows, samples, sizes=sz, mids=mids)
    except SystemExit as e:
        bad.append(f"합성 입력에서 뽑기가 죽었다 — {e}")
        t, k = [], {"groups": {}}
    flat = [s for g in k["groups"].values() for s in g]
    if len(flat) != len(set(flat)):
        bad.append("같은 구간이 두 묶음에 들었다")
    if any(set(r) & {"verdict", "width_min_m", "width_med_m", "road_bt_m", "group"} for r in t):
        bad.append("표에 측정값 · 판정 · 묶음이 실렸다")
    for x in bad:
        print("  ✗", x)
    print("✓ 살아 있다" if not bad else f"✗ {len(bad)}건")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--score", action="store_true", help="채점 — 사람이 채운 뒤에만")
    ap.add_argument("--selftest", action="store_true", help="판별식이 살아 있나")
    ap.add_argument("--force", action="store_true", help="이미 뽑은 표를 다시 뽑는다 — 채워진 행이 있으면 그래도 거부한다")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rows, by = load()
    if a.score:
        filled = read_filled()
        if not filled:
            print("채워진 행이 없다 — 채점을 거부한다(키 파일은 열지 않았다).")
            return 2
        key = json.loads(OUT_KEY.read_text(encoding="utf-8"))
        print(json.dumps(score(rows, by, filled, key), ensure_ascii=False, indent=1))
        return 0
    # ★ 사람이 채운 표를 **덮어쓰지 않는다.** 이미 있으면 거부하고, 채워진 행이 있으면 `--force` 로도 거부한다.
    if OUT_CSV.exists():
        if read_filled():
            print("채워진 행이 있다 — 덮어쓰기를 거부한다(--force 로도 안 된다).")
            return 3
        if not a.force:
            print(f"{OUT_CSV.name} 이 이미 있다 — 다시 뽑으려면 --force")
            return 3
    table, key = build(rows, by)
    write(table, key)
    print(f"평가셋 {len(table)}구간 → {OUT_CSV} · 묶음 키 → {OUT_KEY} (채점 전에 열지 않는다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
