#!/usr/bin/env python3
"""
evalgate.py — 평가지표를 뽑아도 되는가. **게이트는 지표가 아니라 통과 조건이다.**

    uv run python tools/evalgate.py                    판정 (통과 0 · 불일치 2)
    uv run python tools/evalgate.py --baseline <태그>  대조 봉인을 고른다 (기본 가장 최근)
    uv run python tools/evalgate.py --data <트리>      저장소 `data/` 대신 그 트리를 본다
    uv run python tools/evalgate.py --json             기계용

── 왜 도구가 따로 있나 ─────────────────────────────────────────
PLAN §1 #91 이 둘을 갈라 적는다 — *"게이트는 지표가 아니라 **통과 조건**이다."*
`tools/evalgen.py` 가 첫 줄에서 이것을 부르고, 불일치면 지표를 안 뽑고 죽는다.
갈라 둔 이유는 하나 더 있다. 게이트는 **지표를 안 뽑을 때도 물을 수 있어야**
한다 — 파이프라인을 돌린 직후 "지금 산출물로 지표를 뽑아도 되나" 가 지표
계산과 같은 비용일 이유가 없다.

── 셋을 본다 ───────────────────────────────────────────────────
① 지문      `data/golden/segments.fingerprint.json` L1·L2·L3 대 현재 산출물.
            계산은 `tools/golden.py` 가 든다 — 지문 정본이 둘이 되면 안 된다.
② 전이행렬  봉인 `segments.geojson` 대 현재. **`seg_uid` 1:1 로만 본다.**
            `baseline.py diff` 는 안 맞는 것을 중점 15m 로 다시 맞추지만 여기서는
            그 폴백을 안 쓴다 — 폴백으로 맞춘 쌍은 「판정이 안 움직였다」와
            「경계가 움직였다」를 구별 못 하고, 지표는 실행 간 비교가 목적이라
            그 구별이 곧 전부다(DECISIONS §187).
            ★ 「숫자가 바뀌는 것 자체는 정상이다」는 `baseline.py` 의 말이고
              그것은 **대조 보고서**의 규칙이다. 지표는 다르다 — 기준이 움직인
              채로 뽑으면 두 실행의 숫자가 서로 다른 것을 잰 값이 된다.
③ 매니페스트 `_manifest.json` 이 낸다고 적은 산출물이 실제로 있는가. 더해서
            `route_vehicle.csv` 가 **같은 실행의 것인가** — 구간 집합이 같고
            `passable` 이 `vehicle.edge_cost` 와 한 건도 안 갈리는가. 경로
            지표는 이 두 파일을 겹쳐 읽으므로 한쪽만 낡으면 조용히 틀린다.

★ 셋 중 하나만 울어도 **지표를 안 뽑는다.** 낡은 산출물로 뽑은 틀린 숫자는
  숫자가 없는 것보다 나쁘다 — 「지표」라는 이름 때문에 아무도 의심하지 않는다.

IN    data/processed/segments.geojson · route_vehicle.csv · _manifest.json
      data/golden/segments.fingerprint.json · data/baseline/<태그>/segments.geojson
      sources.yaml (vehicle_spec)
OUT   표준출력 (판정) · --json
PARAM --baseline · --data · --json
밖    **지표를 안 낸다.** 값은 `tools/evalgen.py` 가 낸다.
      **입력 계층은 안 본다** — raw · norm 이 옳은가는 `doctor` · `lakecheck`
      소관이고 여기는 `processed` 와 봉인만 본다. 레이크 없이 돌아야 하기 때문이다.
      **곡률을 통행 가능 대조에 안 넣는다** — `turn_radius_verified` 와
      `wheelbase_verified` 가 둘 다 false 인 동안 곡률은 `edge_cost` 에 들지
      않는다. 켜지는 날 게이트가 그 사실을 알리고 멈춘다(`spec_guard`).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import sys
from pathlib import Path

import baseline
import golden

from firelane import paths as _p
from firelane.seg import vehicle as V

#: 판정 정본 파일 이름. 봉인에도 현재 산출물에도 같은 이름으로 있다.
SEG_NAME = "segments.geojson"

# ── 공통 적재 ──────────────────────────────────────────────────
def segments(proc: Path) -> list[dict]:
    """`segments.geojson` 의 feature 목록."""
    return json.loads((proc / SEG_NAME).read_text(encoding="utf-8"))["features"]


def route_rows(proc: Path) -> dict[str, dict]:
    """`route_vehicle.csv` 를 `seg_uid` 로 건다. BOM 이 있으므로 utf-8-sig 다."""
    with (proc / "route_vehicle.csv").open(encoding="utf-8-sig", newline="") as f:
        return {r["seg_uid"]: r for r in csv.DictReader(f)}


def fingerprint(proc: Path) -> dict:
    """`golden.fingerprint()` 를 다른 트리에도 쓴다.

    ★ `golden.py` 는 대상 경로를 모듈 상수 `SEG` 로 든다. 지문 계산을 여기서
      다시 쓰면 **정본이 둘**이 되고, 둘이 갈리는 날 게이트가 거짓 초록을 낸다.
      그래서 상수를 잠깐 바꿔 끼운다. 제대로 된 모양은 `golden.fingerprint(seg)`
      이고 그 한 줄은 `tools/golden.py` 소관이라 여기서 안 고친다.
    """
    keep = golden.SEG
    golden.SEG = proc / SEG_NAME
    try:
        return golden.fingerprint()
    finally:
        golden.SEG = keep


# ── 게이트 ① 지문 ─────────────────────────────────────────────
def gate_fingerprint(proc: Path, gold: Path) -> tuple[dict, list[str]]:
    """잠긴 지문과 지금 산출물이 같은가. L1 집계 · L2 구간별 · L3 기하."""
    lock_p = gold / "segments.fingerprint.json"
    if not lock_p.is_file():
        return {"locked": False}, [f"지문이 없다: {lock_p} — `golden.py lock` 이 먼저다"]
    lock = json.loads(lock_p.read_text(encoding="utf-8"))
    cur = fingerprint(proc)

    why: list[str] = []
    l1 = lock.get("L1") == cur["L1"]
    if not l1:
        why.append(f"L1 집계가 다르다 — 잠금 {lock.get('L1')} · 현재 {cur['L1']}")

    a, b = lock.get("L2") or {}, cur["L2"]
    moved = [u for u in sorted(a.keys() & b.keys())
             if any(not golden._same(a[u].get(k), b[u].get(k), golden.TOL.get(k))
                    for k in golden.FIELDS)]
    gone, new = sorted(a.keys() - b.keys()), sorted(b.keys() - a.keys())
    if moved or gone or new:
        why.append(f"L2 구간별이 다르다 — 값 변동 {len(moved)} · 소멸 {len(gone)} · 신설 {len(new)}")

    l3 = lock.get("L3") == cur["L3"]
    if not l3:
        why.append("L3 기하 해시가 다르다")

    return {"locked": True, "L1": l1, "L2_moved": len(moved), "L2_gone": len(gone),
            "L2_new": len(new), "L3": l3}, why


# ── 게이트 ② 전이행렬 ─────────────────────────────────────────
VERDICTS = ("clear", "needs_cv", "blocked", "unknown")


def newest_tag(base: Path) -> str | None:
    """가장 최근 봉인 태그. 태그는 `YYYYMMDD-...` 라 사전순이 곧 시간순이다."""
    if not base.is_dir():
        return None
    tags = sorted(d.name for d in base.iterdir() if (d / SEG_NAME).is_file())
    return tags[-1] if tags else None


def gate_transition(proc: Path, base: Path, tag: str | None) -> tuple[dict, list[str]]:
    """봉인 대 현재 판정 전이행렬. **대각선 밖이 하나라도 있으면 실패다.**

    ★ 「숫자가 바뀌는 것 자체는 정상이다」가 `baseline.py` 의 말이고 그것은
      **대조 보고서**의 규칙이다. 지표는 다르다 — 실행 간 비교가 목적이므로
      기준이 움직인 채로 뽑으면 두 실행의 숫자가 서로 다른 것을 잰 값이 된다.
      판정을 정말로 바꿨으면 새로 봉인하고 그 태그를 가리켜야 한다.
    """
    if tag is None:
        return {"tag": None}, ["봉인이 하나도 없다 — `baseline.py freeze <태그>` 가 먼저다"]
    old_p = base / tag / SEG_NAME
    if not old_p.is_file():
        return {"tag": tag}, [f"봉인 산출물이 없다: {old_p}"]

    old, new = baseline.load(old_p), baseline.load(proc / SEG_NAME)
    oi = {u: p for u, _xy, p in old if u}
    ni = {u: p for u, _xy, p in new if u}
    both = oi.keys() & ni.keys()
    trans = collections.Counter((oi[u]["verdict"], ni[u]["verdict"]) for u in both)
    moved = sum(v for (x, y), v in trans.items() if x != y)
    lost, added = sorted(oi.keys() - both), sorted(ni.keys() - both)
    keep_pct = round(100 * len(both) / max(1, len(oi)), 1)

    why: list[str] = []
    if moved:
        why.append(f"판정이 움직인 구간 {moved} — 봉인 {tag} 과 지금이 같은 판정이 아니다")
    if lost or added:
        why.append(f"seg_uid 가 갈렸다 — 봉인에만 {len(lost)} · 지금만 {len(added)}")

    matrix = {f"{x}->{y}": trans[(x, y)] for x in VERDICTS for y in VERDICTS if trans[(x, y)]}
    return {"tag": tag, "old_n": len(oi), "new_n": len(ni), "matched": len(both),
            "uid_keep_pct": keep_pct, "moved": moved, "matrix": matrix,
            "old_tally": baseline.tally(old), "new_tally": baseline.tally(new)}, why


# ── 게이트 ③ 매니페스트 · 산출물 신선도 ───────────────────────
def spec_guard() -> list[str]:
    """회전이 판정에 들기 시작했는가. **들기 시작하면 이 게이트가 낡은 것이다.**

    ★ `edge_cost` 는 `can_turn` 과 `offtracking` 을 통해서만 곡률을 본다.
      둘 다 `*_verified` 가 false 인 동안 곡률을 무시하므로, 아래 대조는
      곡률 없이도 정확하다. 플래그가 켜지는 날 그 전제가 깨진다 —
      그날 조용히 통과하지 않고 여기서 멈춘다.
    """
    s = V.spec()
    on = [k for k in ("turn_radius_verified", "wheelbase_verified") if s.get(k)]
    if not on:
        return []
    return [f"{on} 가 켜졌다 — `edge_cost` 에 곡률이 들기 시작했으므로 "
            "게이트 ③ 의 통행 가능 대조도 곡률을 봐야 한다. 이 도구를 먼저 고쳐라"]


def gate_manifest(proc: Path) -> tuple[dict, list[str]]:
    """매니페스트가 낸다고 한 것이 있는가 · 경로 산출물이 같은 실행의 것인가."""
    mp = proc / "_manifest.json"
    if not mp.is_file():
        return {"present": False}, [f"매니페스트가 없다: {mp}"]
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"present": True}, [f"매니페스트를 못 읽는다 — {e}"]

    why: list[str] = []
    for k in ("generated_at", "standard_crs", "datasets"):
        if not man.get(k):
            why.append(f"매니페스트에 `{k}` 가 없다")
    rows = man.get("datasets") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    declared = [o for r in rows for o in ((r or {}).get("outputs") or [])]
    missing = sorted({o for o in declared if not (proc / o).is_file()})
    if missing:
        why.append(f"매니페스트가 냈다고 적은 산출물 {len(missing)}개가 없다 — {missing[:5]}")

    why += spec_guard()
    info = {"present": True, "generated_at": man.get("generated_at"),
            "datasets": len(rows), "outputs_declared": len(declared),
            "outputs_missing": len(missing)}
    info["route_vehicle"], rw = _gate_route(proc)
    return info, why + rw


def _gate_route(proc: Path) -> tuple[dict, list[str]]:
    """`route_vehicle.csv` 가 `segments.geojson` 과 같은 실행에서 나왔는가."""
    rp = proc / "route_vehicle.csv"
    if not rp.is_file():
        return {"present": False}, [f"경로 산출물이 없다: {rp}"]
    feats, rv = segments(proc), route_rows(proc)
    uids = {f["properties"]["seg_uid"] for f in feats}
    only_seg, only_rv = sorted(uids - set(rv)), sorted(set(rv) - uids)
    why: list[str] = []
    if only_seg or only_rv:
        why.append(f"구간 집합이 갈렸다 — segments 에만 {len(only_seg)} · "
                   f"route_vehicle 에만 {len(only_rv)}")
    disagree = 0
    for f in feats:
        p = f["properties"]
        r = rv.get(p["seg_uid"])
        if r is None:
            continue
        mine = 0 if edge_cost_of(p) == math.inf else 1
        if mine != int(r["passable"]):
            disagree += 1
    if disagree:
        why.append(f"`passable` 이 `edge_cost` 와 {disagree}건 갈린다 — "
                   "둘 중 하나가 낡았다. 파이프라인을 다시 돌려라")
    return {"present": True, "rows": len(rv), "uid_only_segments": len(only_seg),
            "uid_only_route": len(only_rv), "passable_disagree": disagree}, why


def edge_cost_of(p: dict) -> float:
    """구간 하나의 통행 비용. 곡률은 안 넣는다 — `_spec_guard` 가 그 전제를 지킨다."""
    return V.edge_cost(p.get("length_m"), p.get("width_min_m"), p.get("verdict"), None)


def gate(proc: Path, gold: Path, base: Path, tag: str | None) -> tuple[dict, list[str]]:
    """게이트 셋. **한 곳이라도 불일치면 사유를 전부 모아 돌려준다.**"""
    fp, w1 = gate_fingerprint(proc, gold)
    tr, w2 = gate_transition(proc, base, tag)
    mf, w3 = gate_manifest(proc)
    why = w1 + w2 + w3
    return {"passed": not why, "fingerprint": fp, "transition": tr,
            "manifest": mf, "why": why}, why




def resolve(data: str | None) -> tuple[Path, Path, Path]:
    """`(processed, golden, baseline)`. `--data` 를 준 도구 둘이 같은 해석을 쓴다."""
    if data:
        root = Path(data)
        return root / "processed", root / "golden", root / "baseline"
    return _p.PROCESSED, _p.GOLDEN, _p.BASELINE


def explain(why: list[str]) -> None:
    """불일치 사유와 **다음 행동**을 같이 찍는다. 사유만 찍으면 사람이 게이트를 끈다."""
    print("★ 게이트 불일치 — 지표를 안 뽑는다\n  " + "\n  ".join(why))
    print("\n  낡은 산출물로 뽑은 숫자는 「지표」라는 이름 때문에 아무도 의심하지 않는다.")
    print("  파이프라인을 다시 돌리거나(`uv run fire-lane`), 판정을 바꿨으면")
    print("  `golden.py lock` 과 `baseline.py freeze <태그>` 를 다시 해라.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="평가지표 재현성 게이트")
    ap.add_argument("--baseline", default=None, help="대조 봉인 태그 (기본 가장 최근)")
    ap.add_argument("--data", default=None, help="저장소 `data/` 대신 이 트리를 본다")
    ap.add_argument("--json", action="store_true", help="판정 보고를 JSON 으로")
    a = ap.parse_args(argv)

    proc, gold, base = resolve(a.data)
    rep, why = gate(proc, gold, base, a.baseline or newest_tag(base))
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 2 if why else 0
    if why:
        explain(why)
        return 2
    t = rep["transition"]
    print(f"게이트 통과 — 봉인 {t['tag']} · 전이 대각선 밖 {t['moved']} · "
          f"seg_uid 유지 {t['uid_keep_pct']}% · 지문 L1/L2/L3 일치 · "
          f"매니페스트 산출물 결손 {rep['manifest']['outputs_missing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
