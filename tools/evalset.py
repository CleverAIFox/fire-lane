#!/usr/bin/env python3
"""
tools/evalset.py — 0판 평가셋을 **뽑는다**(그리고 사람이 채운 뒤에 채점한다).  (Zm23 · DECISIONS §569)

    uv run python tools/evalset.py              평가셋을 뽑아 data/field/evalset_2610.csv · .key.json 을 쓴다
    uv run python tools/evalset.py --score      ★ 사람이 채운 뒤에만 — 채점한다 (채우기 전에는 거부한다)
    uv run python tools/evalset.py --selftest   판별식이 살아 있나
    uv run python tools/evalset.py --roadview[-check]  거리뷰 가설 판독표(가설 셋 · 최소폭 표본 지점 40곳)를 쓴다 · [-check] 칸 · 허용값 · 좌표를 보고 다 채운 가설을 가른다(키 파일은 안 연다)

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
미리 싣는 칸: `seg_id` · `seg_uid`(안정 키 — Zm27) · `위도` · `경도`(WGS84 · 소수 6자리 — 구간 **중점**) · `도로명` · `length_m`. **우리 측정값 · 대장값 · 판정은 안 싣는다.**
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
  Q8 `width_max_m`(담~담) 대 `w_full_m` — **규칙 [11](폭 급변 `wmax/wmin ≥ SPREAD_MAX`)이 읽는 윗수**를 실제 전폭과 댄다. 담~담이 가장 먼 건물까지 뻗으면 부풀어 [11] 이 멀쩡한 `clear` 를 거둔다(DECISIONS §709 — 판정 범위를 넓히면 27구간이 그렇게 움직인다). 오차(우리 − 실측) 중앙 · 사분위 · 묶음별
  Q7 `clear_med_m` 대 `w_narrow_m` · `w_full_m` — **규칙 [10] 이 읽는 양**(내접원 중앙값)을 실제와 댄다: 오차 중앙 · 사분위 + 「거둔다/안 거둔다」(`< CLEAR_M`)가 실제 전폭의 같은 문턱과 같은 편인가(묶음별 2×2). 지금 거두는 구간 수는 **표에 안 적고 이 채점이 그때 센다**(문서에 적은 수는 재잠금마다 낡는다 — DECISIONS §709)
★ 채워지면 `field.fingerprint.json` 에 박는 경로: `uv run python tools/fieldseal.py --write` (사람이 친다 — 이 도구는 안 한다).

IN    web/data/segments.geojson · data/processed/{segments_5186.gpkg,width_samples.csv}
      (읽는 곳은 이 둘이다 — 레이크도 중간 산출물도 아니다. 유령 55 의 원인은 읽는 곳이 아니라 **쓰는 곳**이었다: DECISIONS §571)
OUT   data/field/evalset_2610.csv · data/field/evalset_2610.key.json
PARAM `SIZES` · 시드(`evalgen.SEED`)
밖    **판정을 안 바꾼다.** 값이 옳은지는 사람이 잰 값이 정한다. 정사영상 자동 측정은 안 한다(타당성만 본다 — DECISIONS §569-8).
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
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
COLS = ("seg_id", "seg_uid", "위도", "경도", "도로명", "length_m", *HUMAN_COLS, "method")
NORMAL_GAP = 1

PROTOCOL = (
    "# 측정 규약 (Zm23 · DECISIONS §569) — 이 머리는 읽는 쪽이 '#' 로 시작하는 줄을 건너뛴다",
    "# 1) 전폭(w_full_m)과 최협부 폭(w_narrow_m)을 같은 구간에서 둘 다 잰다. 하나만 재면 Q1 과 Q2 가 섞인다",
    "# 2) 주차 차량 · 적치물은 빼고 경계(담장 · 건물면) 기준으로 잰다. 통행 가능 폭은 재지 않는다 — CLEAR_M 문턱이 이미 흡수한다",
    "# 3) narrow_s_m = 최협부가 '구간 시작'(표의 위경도가 아니라 seg 시작)에서 대략 몇 m 지점인가. ±5m 면 충분하다",
    "# 4) note = 특이사항 한 줄 (복개천 · 구거 · 아케이드 · 주차 · 공터 등)",
    "# 5) method 칸은 도구가 채운다. 사람이 쓰는 도구는 요청이 정한다",
    "# 6) 구간의 키는 seg_uid 다(Zm27 · DECISIONS §572). seg_id 는 재발행하면 뒤가 밀리는 순번이라 읽는 사람 편의로만 옆에 둔다 — 두 값이 어긋나면 seg_uid 를 믿는다",
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
    rng = random.Random(seed)  # noqa: S311 — 씨앗을 박은 재현용 표집이다. 암호가 아니다
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
    random.Random(seed + 1).shuffle(ids)  # noqa: S311 — 씨앗을 박은 재현용 표집이다. 암호가 아니다
    table = []
    for s in ids:
        r = by_id[s]
        lat, lon = mids.get(s, (None, None))
        table.append({"seg_id": s, "seg_uid": r.get("seg_uid") or "", "위도": "" if lat is None else f"{lat:.6f}", "경도": "" if lon is None else f"{lon:.6f}",
                      "도로명": r.get("road_name") or "", "length_m": r.get("length_m"), "w_full_m": "", "w_narrow_m": "",
                      "narrow_s_m": "", "note": "", "method": ""})
    steps = steps_of([num(r["road_bt_m"]) for r in rows if num(r.get("road_bt_m")) is not None])
    marks = {s: {"regime": regime_of(by_id[s], samples_by.get(s, [])), **marks_of(by_id[s], steps)} for s in ids}
    key = {"seed": seed, "sizes": dict(SIZES if sizes is None else sizes),
           "regime_definition": {"module": "firelane.regime", "ecc_threshold": R.ECC_THRESHOLD, "escape": "w_rule == escape 가 하나 이상"},
           "groups": groups, "marks": marks,
           # seg_id 는 실행 간 유지되지 않는다(`segments.py` 의 `DM{i:05d}`). 같은 구간임을 나중에 대조하려고 안정 키를 같이 봉인한다.
           "uids": {s: by_id[s].get("seg_uid") for s in ids},
           "note": "채점 전에 열지 않는다. 묶음을 보면 측정 눈금이 끌린다."}
    return table, key


def write(table: list[dict], key: dict, csv_path: Path | None = None, key_path: Path | None = None) -> None:
    # ★ Zm26 (DECISIONS §571). 기본 인자를 `OUT_CSV` 로 두면 **정의 시점**에 묶여서, 시험이 `E.OUT_CSV` 를 tmp 로 바꿔도
    #   `main()` 의 `write(table, key)` 는 진짜 `data/field/evalset_2610.*` 로 갔다 — 합성 데이터가 실제 평가셋을 덮은 사고의 원인.
    #   그래서 **호출 시점**에 모듈 전역을 읽는다.
    csv_path = OUT_CSV if csv_path is None else csv_path
    key_path = OUT_KEY if key_path is None else key_path
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
    """Q1~Q6. `key` 는 호출자가 채점 시점에 연다.

    ★ 2026-11-12 (PLAN #190). **구간은 `seg_uid` 로만 찾는다.** 종전에는 `seg_id` 로 찾고 `seg_uid` 는 맞나 확인만 했고, 키의 묶음(`groups`)은 `seg_id` 를 키로 들어
      재발행 뒤 키가 낡으면 **조용히 다른 묶음에 들 수 있었다**(표의 `seg_id` 는 막혔는데 키의 `seg_id` 는 안 막혔다). 키가 든 `uids`(`seg_id` → `seg_uid`)로 묶음을
      `seg_uid` 로 옮겨 쓴다 — 키 파일의 `seg_id` 키는 몰라도 된다. `seg_id` 는 사람이 읽는 보조 칸이라 어긋나도 채점은 맞고 알림만 낸다
      (어긋남 자체는 `tests/test_seg_uid_first_class.py` 가 CI 전에 잡는다)."""
    by_uid = {r["seg_uid"]: r for r in rows if r.get("seg_uid")}
    uid_of = key.get("uids") or {}
    grp: dict[str, str] = {}
    for g, ss in key["groups"].items():
        for sid in ss:
            u = uid_of.get(sid)
            if not u:
                raise SystemExit(f"★ 키가 {sid} 의 seg_uid 를 안 든다(`uids` 칸) — 키를 쓴 판이 낡았다. 채점하지 않는다. "
                                 "사람이 DECISIONS §621-1 의 (가) 순서(seg_uid 로 seg_id 를 다시 매핑)로 키를 고친다 — 채워진 표는 건드리지 않는다.")
            grp[u] = g
    res: dict = {"Q1": {}, "Q2": {}, "Q3": {}, "Q6": {}}
    e1: dict[str, list[float]] = {}
    e2: dict[str, list[float]] = {}
    e3: dict[str, list[float]] = {}
    e7n: dict[str, list[float]] = {}       # Q7 — clear_med_m − 실제 최협부
    e7f: dict[str, list[float]] = {}       # Q7 — clear_med_m − 실제 전폭
    e8: dict[str, list[float]] = {}        # Q8 — width_max_m − 실제 전폭(규칙 [11] 의 윗수)
    t7: dict[str, dict[str, int]] = {}     # Q7 — 규칙 [10] 이 거둔다(clear_med_m < CLEAR_M) × 실제 전폭이 그 문턱 미만인가
    for r in filled:
        s = r["seg_id"]
        uid = r.get("seg_uid")
        if not uid:
            raise SystemExit(f"★ {s} 행에 seg_uid 가 없다 — seg_id 로는 구간을 찾지 않는다(재발행하면 밀린다). 채점하지 않는다.")
        if uid not in by_uid:
            raise SystemExit(f"★ {s} 의 seg_uid {uid} 가 지금 발행본에 없다 — 재발행으로 구간이 바뀌었다. 채점하지 않는다.")
        p, g = by_uid[uid], grp.get(uid, "?")
        if p["seg_id"] != s:
            print(f"  · {s} 는 지금 {p['seg_id']} 다(seg_uid 로 찾았다 — 표의 seg_id 칸이 낡았다)", file=sys.stderr)
        wf, wn, ns = num(r.get("w_full_m")), num(r.get("w_narrow_m")), num(r.get("narrow_s_m"))
        if wf is not None and p.get("width_med_m") is not None:
            e1.setdefault(g, []).append(p["width_med_m"] - wf)
        if wn is not None and p.get("width_min_m") is not None:
            e2.setdefault(g, []).append(p["width_min_m"] - wn)
        wmx = num(p.get("width_max_m"))
        if wmx is not None and wf is not None:
            e8.setdefault(g, []).append(wmx - wf)
        cm = num(p.get("clear_med_m"))
        if cm is not None:
            if wn is not None:
                e7n.setdefault(g, []).append(cm - wn)
            if wf is not None:
                e7f.setdefault(g, []).append(cm - wf)
                from firelane.seg.classify import CLEAR_M
                cell = f"{'거둔다' if cm < CLEAR_M else '안 거둔다'}·실제 {'좁다' if wf < CLEAR_M else '넓다'}"
                t7.setdefault(g, {}).setdefault(cell, 0)
                t7[g][cell] += 1
        idx = p.get("width_min_sample_idx")
        rows_s = samples_by.get(p["seg_id"], [])        # 표본도 seg_uid 로 찾은 구간의 현재 seg_id 로 본다
        if ns is not None and idx is not None and 0 <= int(idx) < len(rows_s):
            e3.setdefault(g, []).append(abs(float(rows_s[int(idx)]["s_m"]) - ns))
        if g == "지명":
            res["Q6"][p["seg_id"]] = r.get("note", "")
    for name, e in (("Q1", e1), ("Q2", e2), ("Q3", e3)):
        res[name] = {g: _err(v) for g, v in sorted(e.items())}
        res[name]["전체"] = _err([x for v in e.values() for x in v])
    from firelane.seg.classify import CLEAR_M as _CM
    live = 0
    for p in rows:
        try:
            live += 1 if was_clear_before_median(p) else 0
        except (KeyError, TypeError):
            pass          # 합성 입력 등 칸이 모자라면 센 것에서 뺀다 — 모르는 것을 0 이나 1 로 안 센다
    res["Q7"] = {"문턱 CLEAR_M": _CM, "지금 규칙 [10] 이 거두는 구간 수": live,
                 "clear_med_m − 최협부": {g: _err(v) for g, v in sorted(e7n.items())} | {"전체": _err([x for v in e7n.values() for x in v])},
                 "clear_med_m − 전폭": {g: _err(v) for g, v in sorted(e7f.items())} | {"전체": _err([x for v in e7f.values() for x in v])},
                 "width_max_m − 전폭(규칙 [11] 의 윗수 · Q8)": {g: _err(v) for g, v in sorted(e8.items())} | {"전체": _err([x for v in e8.values() for x in v])},
                 "거둠 × 실제(전폭)": {g: dict(sorted(t.items())) for g, t in sorted(t7.items())},
                 "읽는 법": "오차 중앙이 0 에서 멀면 규칙 [10] 의 입력이 실제와 어긋난다. 2×2 에서 「거둔다·실제 넓다」가 많으면 멀쩡한 길을 거두고 「안 거둔다·실제 좁다」가 많으면 좁은 길을 놓친다."}
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


# ── 거리뷰 판독표 — 가설 검정 (PLAN #187 · 묶음 ㉘) ─────────────────────
# 전수 조사가 아니다. 데이터만으로 못 가른 가설 셋을, 가설을 가를 최소 표본(가설군 + 대조군)만 뽑아 그 구간의 **최소폭 표본 지점**에서 묻는다.
# ★ 표에 우리 폭 · 대장폭 · 판정 · **어느 행이 대조군인지**를 안 싣는다(눈금이 끌린다). 가설군 · 대조군은 열쇠 파일이 아니라 아래 규칙(`RV_HYPO`)으로 다시 나온다 — `rv_role`.
RV_FILE = "roadview_hypo_2611.csv"
RV_PRE = ("순번", "가설", "seg_id", "seg_uid", "위도", "경도", "도로명", "보는방향", "카카오로드뷰", "네이버지도", "묻는것")
RV_HUMAN = ("거리뷰", "답", "포장폭", "촬영시점", "메모")
RV_COLS = (*RV_PRE, *RV_HUMAN)
RV_NAMED = ("DM-194457-283737-A0DR", "DM-194305-283667-SAGS")     # 밤실로30번길 · 밤실로20번길 — 사람이 짚은 사례다(가설 「가」의 씨앗). 표에 싣되 **검정에서 뺀다**(가설을 낳은 사례로 그 가설을 검정하지 않는다)
RV_ALPHA, RV_TOL_M, RV_MIN_LEN = 0.05, 0.011, 15.0                # 피셔 정확검정(한쪽)의 유의수준 · 표본 폭이 발행 최소폭과 맞아야 하는 허용차(m — 발행본은 소수 2자리다) · 이보다 짧은 구간은 교차부 안의 조각이라 안 뽑는다(m)
RV_ALLOWED = {"거리뷰": ("있다", "없다"), "포장폭": ("좁다", "중간", "넓다", "가림")}
# 가설 → (가설군 수 · 대조군 수 · 가설군 규칙 · 대조군 규칙 · 묻는것 · 허용 답 · 가설이 참이면 가설군에 많을 답 · 가설 한 줄). 규칙의 w · m · b = 우리 최소폭 · 우리 중앙폭 · 대장폭(m)
RV_HYPO = {
    "가": (8, 7, lambda w, m, b: 6 <= b <= 8 and 1 <= w < 3, lambda w, m, b: 6 <= b <= 8 and abs(w - b) <= 1,
          "포장면 끝과 담 · 건물 사이에 차가 못 쓰는 띠(보도 · 수풀 · 화단 · 난간 · 옹벽 · 계단 · 단차 · 비포장)가 있나 — 없다 · 한쪽 · 양쪽 · 가림",
          ("없다", "한쪽", "양쪽", "가림"), ("한쪽", "양쪽"), "경계 정의 — 대장폭과 우리 최소폭이 크게 갈리는 곳은 포장면과 담 사이에 차가 못 쓰는 띠가 있다(대장은 담~담 · 우리는 포장면)"),
    "나": (7, 5, lambda w, m, b: 1 <= w < 3 <= m and m >= 1.5 * w and not 6 <= b <= 8, lambda w, m, b: 3 <= w < 7 and w >= 0.9 * m,
          "이 지점에서 포장면이 앞뒤 10m 보다 눈에 띄게 좁아지나 — 잘록하다 · 그대로다 · 교차부(모퉁이 · 합류부 안이다) · 길끝(막다른 끝 · 차가 다니는 길이 아니다) · 가림",
          ("잘록하다", "그대로다", "교차부", "길끝", "가림"), ("잘록하다",), "병목 실재 — 우리 최소폭이 중앙폭보다 훨씬 좁은 구간의 최소폭 지점은 실제로 잘록한 병목이다(그림의 조각이 아니다)"),
    "다": (6, 5, lambda w, m, b: b < 12 and w - b >= 3, lambda w, m, b: b < 12 and abs(w - b) <= 1 and w >= 3,
          "이 지점의 포장면이 길 한 줄인가 · 주차장 · 광장 · 공터 · 큰길과 턱 없이 터져 있나 — 한 줄 · 터졌다 · 가림",
          ("한 줄", "터졌다", "가림"), ("터졌다",), "터진 포장 — 우리가 대장폭보다 3m 넘게 넓게 잰 곳은 노면 폴리곤이 길과 주차장 · 광장 · 큰길을 한 덩어리로 그린 곳이다(과대 추정)"),
}
RV_N = len(RV_NAMED) + sum(h[0] + h[1] for h in RV_HYPO.values())
RV_RULES = (
    f"# 거리뷰 판독표 — 가설 검정 (PLAN #187). 전수 조사가 아니다 — 데이터만으로 못 가른 가설 셋을 가르는 데 드는 {RV_N}지점만 본다. 한 지점 1~2분 · 재지 않는다",
    "# 1) 좌표 = 그 구간에서 **우리가 최소폭을 잰 바로 그 표본 지점**이다(구간 중점도 도로명도 아니다). data/processed/width_samples.csv 에는 좌표 칸이 없고 「구간 시작에서 몇 m」(s_m)만 있다 —\n"
    "#    발행 최소폭을 낸 표본(width_min_sample_idx)의 s_m ÷ 구간 길이의 비율로 구간 선(web/data/segments.geojson) 위를 보간했다. 표본 간격은 2m 다",
    "# 2) 카카오로드뷰 칸이 그 좌표의 로드뷰를 연다(네이버지도 칸은 좌표 검색이라 지도가 열리고 거리뷰 단추는 손으로 누른다 — 둘 중 하나만 봐도 된다). 보는방향 = 그 지점에서 길이 뻗는 방위다(나침반을 맞춘다 · 돌아서 반대쪽도 본다). 지점의 앞뒤 5m 안에서 본다",
    "# 3) 가설마다 묻는 것이 다르다. 행의 「묻는것」을 읽고 「답」에 그 줄 끝의 낱말 가운데 하나를 적는다. 주차된 차 · 적치물은 없다고 치고 본다 — 그것 때문에 안 보이면 「가림」\n"
    + "\n".join(f"#    {k}  {h[7]}\n#        묻는것: {h[4]}" for k, h in RV_HYPO.items()),
    "# 4) 거리뷰 = 있다 · 없다(그 지점 5m 안에 거리뷰가 없다 — 골목 안 · 막다른 끝). 없다면 답 · 포장폭은 비운다(검정에서 빠진다)",
    "# 5) 포장폭 = 그 지점에서 차가 달릴 수 있는 포장면의 눈대중: 좁다(승용 한 대가 빠듯하다 · 3m 안쪽) · 중간(한 대는 넉넉하고 두 대는 못 비킨다 · 3~5m) · 넓다(두 대가 비킨다 · 5m 넘는다) · 가림. 어느 자가 그 지점에 맞는지 가르는 곁칸이다",
    "# 6) 촬영시점 = 거리뷰 화면의 촬영 연월 YYYY-MM · 메모 = 본 것 한 줄(띠가 무엇이고 어느 쪽인지 · 무엇과 터졌는지 · 왜 좁아지는지)",
    f"# 7) 표에 우리 폭 · 대장폭 · 판정이 없고 **어느 행이 대조군인지도 없다**(눈금이 끌린다). 순서는 시드로 섞었다 — 아무 행부터 채워도 된다. 가르는 법: 가설마다 가설군과 대조군에서 「가설이 참이면 많을 답」의 비율이 같다는 귀무가설을 피셔 정확검정(한쪽 · 유의수준 {RV_ALPHA})으로 본다\n"
    "#    한 가설의 행을 **다 채워야** 검사가 그 가설의 수를 낸다(중간에 내면 어느 행이 대조군인지 샌다). 밤실로30번길 · 밤실로20번길 두 행은 가설을 낳은 사례라 검정에서 뺀다",
    "# 8) 검사 — uv run python tools/evalset.py --roadview-check (칸 · 허용값 · 좌표가 표본 지점인가 · 채운 수 · 다 채운 가설의 판정)",
)


def rv_links(lat: float, lon: float) -> tuple[str, str]:
    """(카카오 로드뷰 바로가기 · 네이버 지도 좌표 검색)."""
    return f"https://map.kakao.com/link/roadview/{lat:.6f},{lon:.6f}", f"https://map.naver.com/p/search/{lat:.6f},{lon:.6f}"


def rv_point(coords: list, frac: float) -> tuple[float, float, str]:
    """구간 선 위에서 길이 비율 `frac` 인 점 — (위도, 경도, 보는방향). 방위는 표본 위치가 느는 쪽이다(접지 않는다)."""
    k = math.cos(math.radians(coords[0][1]))
    pairs = list(zip(coords, coords[1:], strict=False))
    d = [math.hypot((b[0] - a[0]) * k, b[1] - a[1]) for a, b in pairs]
    want, run = max(0.0, min(1.0, frac)) * sum(d), 0.0
    for i, ((a, b), x) in enumerate(zip(pairs, d, strict=True)):
        if x > 0 and (run + x >= want or i == len(d) - 1):
            t = min(1.0, (want - run) / x)
            brg = math.degrees(math.atan2((b[0] - a[0]) * k, b[1] - a[1])) % 360
            name = ("북", "북동", "동", "남동", "남", "남서", "서", "북서")[int((brg + 22.5) // 45) % 8]
            return round(a[1] + (b[1] - a[1]) * t, 6), round(a[0] + (b[0] - a[0]) * t, 6), f"{name} {brg:.0f}°"
        run += x
    raise SystemExit("★ 길이가 0 인 구간이다 — 표본 지점을 못 낸다")


def rv_samples(path: Path | None = None) -> dict[str, list[dict]]:
    """seg_uid → 그 구간의 표본 행(파일 순서 — `width_min_sample_idx` 가 이 순서의 번호다)."""
    by: dict[str, list[dict]] = {}
    with (SAMPLES if path is None else path).open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            by.setdefault(r["seg_uid"], []).append(r)
    return by


def rv_minrow(p: dict, rows: list[dict]) -> dict | None:
    """발행 최소폭을 낸 **그 표본 행**. 번호가 없거나 그 표본의 폭이 발행값과 안 맞거나(`RV_TOL_M`) 구간이 `RV_MIN_LEN` 보다 짧으면 None — 그런 구간은 지점을 댈 수 없어 안 뽑는다."""
    i, w = p.get("width_min_sample_idx"), num(p.get("width_min_m"))
    r = rows[int(i)] if i is not None and 0 <= int(i) < len(rows) else None
    if r is None or w is None or (num(p.get("length_m")) or 0.0) < RV_MIN_LEN or num(p.get("width_med_m")) is None or num(p.get("road_bt_m")) is None or num(r.get("w_m")) is None:
        return None
    return r if abs(num(r["w_m"]) - w) <= RV_TOL_M else None


def rv_role(hyp: str, p: dict, rows: list[dict]) -> str | None:
    """그 구간이 가설 `hyp` 에서 「가설군」인가 「대조군」인가 — 규칙으로만 정한다(표에도 열쇠 파일에도 없다). 지명 둘은 「지명」(검정에서 뺀다)."""
    if rv_minrow(p, rows) is None:
        return None
    if p["seg_uid"] in RV_NAMED:
        return "지명" if hyp == "가" else None
    w, m, b = p["width_min_m"], p["width_med_m"], p["road_bt_m"]
    return "가설군" if RV_HYPO[hyp][2](w, m, b) else "대조군" if RV_HYPO[hyp][3](w, m, b) else None


def rv_draw(feats: list[dict], samples: dict[str, list[dict]], seed: int = SEED) -> list[tuple[str, str]]:
    """(가설, seg_uid) 명단 — 지명 → 가 → 나 → 다 순으로 뽑고 앞에서 쓴 구간은 뒤에서 뺀다. 후보는 seg_uid 순으로 놓고 시드로 뽑은 뒤 시드로 섞는다(폭 · 판정으로 정렬하지 않는다)."""
    props = sorted((f["properties"] for f in feats), key=lambda p: p["seg_uid"])
    out = [("가", p["seg_uid"]) for p in props if rv_role("가", p, samples.get(p["seg_uid"], [])) == "지명"]
    used = set(RV_NAMED)
    for k, (hyp, h) in enumerate(RV_HYPO.items()):
        for j, role in enumerate(("가설군", "대조군")):
            pool = [p["seg_uid"] for p in props if p["seg_uid"] not in used and rv_role(hyp, p, samples.get(p["seg_uid"], [])) == role]
            if len(pool) < h[j]:
                raise SystemExit(f"★ 가설 {hyp} 의 {role} 후보가 {len(pool)} — {h[j]} 을 못 뽑는다")
            got = random.Random(seed + 10 * k + j).sample(pool, h[j])  # noqa: S311 — 씨앗을 박은 재현용 표집이다. 암호가 아니다
            used.update(got)
            out += [(hyp, u) for u in got]
    random.Random(seed + 99).shuffle(out)  # noqa: S311 — 위와 같다(행 순서가 가설군 · 대조군을 흘리지 않게 섞는다)
    return out


def rv_at(f: dict, rows: list[dict]) -> tuple[float, float, str]:
    """그 구간의 최소폭 표본 지점 — s_m ÷ 구간 길이의 비율로 구간 선 위를 보간한다."""
    p = f["properties"]
    return rv_point(f["geometry"]["coordinates"], float(rv_minrow(p, rows)["s_m"]) / float(p["length_m"]))


def rv_build(feats: list[dict], samples: dict[str, list[dict]], picks: list[tuple[str, str]]) -> list[dict]:
    """판독표 행. 좌표는 구간 중점이 아니라 **최소폭 표본 지점**이다. 사람 칸은 비운다."""
    by = {f["properties"]["seg_uid"]: f for f in feats}
    table = []
    for i, (hyp, u) in enumerate(picks, 1):
        p = by[u]["properties"]
        lat, lon, brg = rv_at(by[u], samples[u])
        kk, nv = rv_links(lat, lon)
        table.append({**dict.fromkeys(RV_COLS, ""), "순번": i, "가설": hyp, "seg_id": p["seg_id"], "seg_uid": u, "위도": f"{lat:.6f}", "경도": f"{lon:.6f}",
                      "도로명": p.get("road_name") or "", "보는방향": brg, "카카오로드뷰": kk, "네이버지도": nv, "묻는것": RV_HYPO[hyp][4]})
    return table


def rv_read(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader([ln for ln in f if not ln.startswith("#")])
        return list(rd.fieldnames or []), list(rd)


def rv_write(table: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:               # BOM 없이 · LF (evalset 표와 같은 꼴)
        f.write("\n".join(RV_RULES) + "\n")
        w = csv.DictWriter(f, fieldnames=list(RV_COLS), lineterminator="\n")
        w.writeheader()
        w.writerows(table)


def rv_filled(r: dict) -> bool:
    return any((r.get(c) or "").strip() for c in RV_HUMAN)


def rv_fisher(a: int, n1: int, b: int, n0: int) -> float:
    """피셔 정확검정 한쪽 p — 가설군 n1 중 a · 대조군 n0 중 b 가 「그 답」일 때, 비율이 같다면 가설군에 a 이상이 몰릴 확률."""
    k = a + b
    return sum(math.comb(n1, x) * math.comb(n0, k - x) for x in range(a, min(n1, k) + 1) if 0 <= k - x <= n0) / math.comb(n1 + n0, k)


def rv_check(path: Path, feats: list[dict], samples: dict[str, list[dict]], n: int | None = None) -> tuple[list[str], dict]:
    """(결함 목록, 진행 · 판정). 칸 · 행 수 · 허용값 · 좌표가 최소폭 표본 지점인가 · 가설군/대조군 수 · 앞뒤를 본다. 빈 행은 결함이 아니다(아직 안 본 행). 판정은 **다 채운 가설만** 낸다."""
    import re
    bad: list[str] = []
    cols, rows = rv_read(path)
    if tuple(cols) != RV_COLS:
        return [f"칸이 다르다 — 있어야 할 것 {list(RV_COLS)} · 있는 것 {cols}"], {}
    if len(rows) != (RV_N if n is None else n):
        bad.append(f"행 수 {len(rows)} ≠ {RV_N if n is None else n}")
    by = {f["properties"]["seg_uid"]: f for f in feats}
    if len({r["seg_uid"] for r in rows}) != len(rows):
        bad.append("같은 구간이 두 번 들었다")
    tally: dict[str, dict[str, list[dict]]] = {h: {"가설군": [], "대조군": [], "지명": []} for h in RV_HYPO}
    for i, r in enumerate(rows, 1):
        tag, hyp, f = f"{i}행({r.get('seg_uid')})", r.get("가설"), by.get(r.get("seg_uid"))
        role = rv_role(hyp, f["properties"], samples.get(r["seg_uid"], [])) if f and hyp in RV_HYPO else None
        if role is None:
            bad.append(f"{tag}: 지금 발행본에 없는 구간이거나 가설 「{hyp}」의 규칙 밖이다(재발행으로 밀렸다) — 표를 다시 뽑는다")
            continue
        tally[hyp][role].append(r)
        lat, lon, brg = rv_at(f, samples[r["seg_uid"]])
        if (r["위도"], r["경도"], r["보는방향"]) != (f"{lat:.6f}", f"{lon:.6f}", brg) or (r["카카오로드뷰"], r["네이버지도"]) != rv_links(lat, lon) or r["묻는것"] != RV_HYPO[hyp][4]:
            bad.append(f"{tag}: 좌표가 그 구간의 최소폭 표본 지점({lat:.6f}, {lon:.6f})이 아니거나 링크 · 보는방향 · 묻는것이 안 맞는다")
        cov, ans, wid, when = ((r.get(c) or "").strip() for c in RV_HUMAN[:4])
        for c, v, allowed in (("거리뷰", cov, RV_ALLOWED["거리뷰"]), ("답", ans, RV_HYPO[hyp][5]), ("포장폭", wid, RV_ALLOWED["포장폭"])):
            if v and v not in allowed:
                bad.append(f"{tag}: {c} 「{v}」 — 가설 {hyp} 의 허용값은 {' · '.join(allowed)}")
        if when and not re.fullmatch(r"(19|20)\d\d-(0[1-9]|1[0-2])", when):
            bad.append(f"{tag}: 촬영시점 「{when}」 — YYYY-MM 꼴이 아니다")
        if rv_filled(r) and (not cov or (cov == "없다" and (ans or wid)) or (cov == "있다" and not (ans and wid and when))):
            bad.append(f"{tag}: 채우다 만 행이다 — 거리뷰 「있다」면 답 · 포장폭 · 촬영시점이 다 있어야 하고 「없다」면 답 · 포장폭을 비운다")
    stat: dict = {"행": len(rows), "채운 행": sum(1 for r in rows if rv_filled(r))}
    for hyp, g in tally.items():
        h = RV_HYPO[hyp]
        if (len(g["가설군"]), len(g["대조군"])) != h[:2] and n is None:
            bad.append(f"가설 {hyp}: 가설군 · 대조군 수가 {len(g['가설군'])} · {len(g['대조군'])} — {h[0]} · {h[1]} 이어야 한다")
        every = [r for v in g.values() for r in v]
        if not every or not all(rv_filled(r) for r in every):
            stat[hyp] = f"{sum(1 for r in every if rv_filled(r))}/{len(every)} 채움 — 다 채우면 가른다"
            continue
        seen = {k: [r["답"].strip() for r in v if r["거리뷰"].strip() == "있다" and r["답"].strip() != "가림"] for k, v in g.items()}
        a, n1, b, n0 = sum(x in h[6] for x in seen["가설군"]), len(seen["가설군"]), sum(x in h[6] for x in seen["대조군"]), len(seen["대조군"])
        pv = rv_fisher(a, n1, b, n0) if n1 and n0 else None
        stat[hyp] = {"가설": h[7], "가설군": f"{a}/{n1}", "대조군": f"{b}/{n0}", "못 본 행(거리뷰 없다 · 가림)": len(g["가설군"]) + len(g["대조군"]) - n1 - n0, "p": None if pv is None else round(pv, 4),
                     "판정": "못 가른다 — 볼 수 있는 행이 한쪽에 없다" if pv is None else "귀무가설을 기각한다 — 가설을 받친다" if pv <= RV_ALPHA else "귀무가설을 기각하지 못한다 — 가설을 받칠 근거가 없다(표본이 작아 「가설이 거짓」이라는 뜻은 아니다)",
                     "지명": [r["답"].strip() for r in g["지명"]], "포장폭(가설군 | 대조군)": " | ".join(" ".join(r["포장폭"].strip() or "–" for r in g[k]) for k in ("가설군", "대조군"))}
    return bad, stat


def rv_main(check: bool, force: bool, out_dir: Path | None = None) -> int:
    path = (OUT_CSV.parent if out_dir is None else out_dir) / RV_FILE
    feats, samples = json.loads(SEG.read_text(encoding="utf-8"))["features"], rv_samples()
    if check:
        bad, stat = rv_check(path, feats, samples) if path.exists() else (["없다 — `--roadview` 로 뽑는다"], {})
        print(f"{'✓' if not bad else '✗'} {RV_FILE}: {json.dumps(stat, ensure_ascii=False, indent=1)}" + "".join(f"\n    ✗ {x}" for x in bad))
        return 1 if bad else 0
    if path.exists() and (any(rv_filled(r) for r in rv_read(path)[1]) or not force):
        print(f"{RV_FILE}: 이미 있다 — 채워진 행이 있으면 --force 로도 안 덮는다. 건너뛴다")
        return 0
    rv_write(rv_build(feats, samples, rv_draw(feats, samples)), path)
    print(f"{RV_FILE}: {RV_N}행 → {path}")
    return 0


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
    ap.add_argument("--roadview", action="store_true", help="거리뷰 가설 판독표를 쓴다(PLAN #187) — 있으면 건너뛴다")
    ap.add_argument("--roadview-check", action="store_true", help="거리뷰 가설 판독표의 칸 · 허용값 · 좌표를 보고 다 채운 가설을 가른다")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.roadview or a.roadview_check:
        return rv_main(a.roadview_check, a.force)
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
