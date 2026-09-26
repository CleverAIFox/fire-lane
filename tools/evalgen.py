#!/usr/bin/env python3
"""
evalgen.py — 평가지표 산출기. **게이트를 먼저 통과해야 숫자가 나온다.**

    uv run python tools/evalgen.py                     게이트 → data/processed/eval.json
    uv run python tools/evalgen.py --scenarios         역산 결과를 표로도 찍는다
    uv run python tools/evalgen.py --baseline <태그>   대조 봉인을 고른다 (기본 가장 최근)
    uv run python tools/evalgen.py --out <경로>        다른 자리에 쓴다
    uv run python tools/evalgen.py --data <트리>       저장소 `data/` 대신 그 트리를 본다

── 왜 생겼나 ───────────────────────────────────────────────────
**지표는 값이 아니라 실행이다 — 터미널에만 있는 숫자는 소실된다**(PLAN §1 #91).
E-3 값 셋(불가 399 · 연장 17,168m · 유효범위 밖 830)이 이미 한 번 계산됐는데
산출기가 없어 문서에 손으로 옮겨 적혀 있다. 판정이 움직이면 그 숫자는 그날로
거짓이 되고, 「지표」라는 이름 때문에 아무도 의심하지 않는다.

★ 그래서 **첫 줄이 게이트다**(`tools/evalgate.py`). 지문 · 전이행렬 ·
  매니페스트 셋 중 하나라도 불일치면 파일을 **안 쓰고 죽는다** — 경고를 찍고
  계속 가지 않는다. 그것이 이 저장소가 계속 잡는 「조용한 통과」다.

── 형식 ────────────────────────────────────────────────────────
`tally` · `sha256` · `as_of` · `git_sha` · `known_limits` 는 봉인 `meta.json` 과
**같은 칸 이름**이다. `tally` 는 `baseline.tally()` 가 직접 낸 것이라 모양이
갈릴 수가 없다. ★ 다만 `baseline.py` 의 `FILES` 에 `eval.json` 을 넣는 한 줄은
여기서 안 친다 — 그 파일은 이 작업 범위 밖이다. 넣는 순간 `freeze` · `diff` 가
지표까지 실행 간 대조한다.

── #120 과 한 몸이다 ───────────────────────────────────────────
「우리가 없었으면 갇혔을 쌍」 역산(PLAN §1 #120)은 **E-1 과 같은 코드다.**
E-1 이 쌍마다 내는 (d1, d2) 를 그대로 `d2/d1 > 1.5 and d2 < inf` 로 거르면
그것이 역산 결과다. 두 번 재지 않는다 — 두 번 재면 두 답이 나온다.

    d1  제약 없는 경로. 폭을 모르는 현행 내비게이션의 대역
    d2  제약 있는 경로. 통행 가능 구간만으로 간 실거리. 없으면 inf

선정 조건 셋도 같은 자리에서 나온다 — 우회로 존재(d2 < inf) · CCTV 커버
(목 구간의 `cv_feasible`) · 코너 통과 가능(우회 경로 전 구간의 `can_turn`).

IN    data/processed/segments.geojson · route_vehicle.csv · _manifest.json
      data/golden/segments.fingerprint.json · data/baseline/<태그>/segments.geojson
      seg/params.py (STATIONS · NODE_TOL) · sources.yaml (vehicle_spec)
OUT   data/processed/eval.json · 표준출력
PARAM --baseline · --out · --scenarios · --data · RATIO_MIN · 분모(노드)
밖    **게이트를 여기서 판정하지 않는다.** 셋은 `tools/evalgate.py` 가 든다.
      **표본 설계를 안 정한다** — 층화 · 표본 수 · 시드 · E-1 분모(건물이냐
      노드냐)는 PLAN §1 #94 가 미정으로 들고 있다. 여기서는 노드를 분모로 쓰고
      그 사실을 `eval.json` 에 적을 뿐이며, 정해지면 이 도구가 아니라 #94 가 바꾼다.
      **E-2 · E-4 도 안 낸다** — E-2 는 오류 비대칭(#117)이 미정이고 E-4 는
      D-25 실측(#4)이 전건이다. 없는 전건을 이 도구가 대신 정하지 않는다.
      **답사 계획도 안 세운다** — 역산은 「어느 골목인가」까지다. 관측점과
      촬영은 의존 사슬의 다음 칸이고 이 도구 밖이다.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics as st
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ★ 그래프 유틸은 `tools/kpi.py` 것을 그대로 쓴다. 같은 동네를 두 번 노딩하면
#   두 그래프가 생기고, 그러면 「진입 실패율(kpi)」과 「E-1(여기)」이 서로 다른
#   도로망 위에서 나온 숫자가 된다 — 발표에서 둘을 나란히 읽는다.
#   이름 앞의 `_` 는 kpi 가 공개할 생각이 없었다는 뜻이고, 공개 이름으로
#   올리는 것은 `kpi.py` 소관이라 여기서 안 고친다.
import baseline
import evalgate as G
import kpi
import route_probe
from localgeo import MX, MY
from shapely.geometry import LineString

from firelane.hashing import sha256 as _sha256
from firelane.seg import vehicle as V
from firelane.seg.params import NODE_TOL, STATIONS

KST = timezone(timedelta(hours=9))

#: 역산 문턱. PLAN §1 #120 이 적은 값이다. 여기가 정본이다.
RATIO_MIN = 1.5

# ── 그래프 · 쌍 거리 ───────────────────────────────────────────
def build_nodes(feats: list[dict]) -> tuple[dict, dict]:
    """끝점을 `NODE_TOL` 로 접합한다. 반환 (끝점색인→노드, 노드→미터좌표)."""
    nid, ends = kpi._node_index(feats, NODE_TOL)
    pos: dict = {}
    for i in range(len(feats)):
        pos.setdefault(nid[2 * i], ends[2 * i])
        pos.setdefault(nid[2 * i + 1], ends[2 * i + 1])
    return nid, pos


def build_graph(feats: list[dict], nid: dict, passable: set[int] | None) -> dict:
    """인접표. `passable` 을 주면 그 구간색인만 쓴다(제약 있는 경로)."""
    g: dict = collections.defaultdict(list)
    for i, f in enumerate(feats):
        u, v = nid[2 * i], nid[2 * i + 1]
        if u == v:
            continue
        if passable is not None and i not in passable:
            continue
        ln = f["properties"].get("length_m") or 1.0
        g[u].append((v, ln, i))
        g[v].append((u, ln, i))
    return g


def curvatures(feats: list[dict]) -> dict[int, float | None]:
    """구간별 최소 곡률반경(m). 계산은 `route_probe.curvature` 가 든다.

    ★ 좌표를 국소 평면(`localgeo`)으로 옮겨 넘긴다. 파이프라인은 EPSG:5186
      으로 재므로 값이 정확히 같지 않다 — 이 값은 시나리오 선정 조건에만 쓰고
      게이트 대조에는 안 쓴다(머리말 `밖`).
    """
    out: dict[int, float | None] = {}
    for i, f in enumerate(feats):
        co = [(x * MX, y * MY) for x, y in kpi._coords(f["geometry"])]
        out[i] = route_probe.curvature(LineString(co)) if len(co) > 2 else None
    return out


def _snap(pos: dict, graph: dict, lon: float, lat: float) -> tuple[int, float]:
    """안전센터에 가장 가까운 노드와 그 거리(m)."""
    x, y = lon * MX, lat * MY
    n = min(graph, key=lambda k: (pos[k][0] - x) ** 2 + (pos[k][1] - y) ** 2)
    return n, math.dist(pos[n], (x, y))


def station_pairs(pos: dict, naive: dict, safe: dict) -> tuple[dict, list[dict]]:
    """안전센터마다 모든 목적지 노드까지 (d1, d2) 를 낸다.

    ★ 출발 노드는 **제약 없는 그래프에서** 고른다. 두 그래프에서 따로 고르면
      두 거리가 서로 다른 출발점에서 잰 값이 되고, 비율이 그만큼 거짓말한다.
    """
    per: dict = {}
    rows: list[dict] = []
    for name, (lon, lat) in STATIONS.items():
        src, dist = _snap(pos, naive, lon, lat)
        d1, prev1 = kpi._dijkstra(naive, src)
        if src in safe:
            d2, prev2 = kpi._dijkstra(safe, src)
        else:
            d2, prev2 = {}, {}
        for t, a in d1.items():
            if a <= 0:
                continue
            b = d2.get(t, math.inf)
            rows.append({"station": name, "node": t, "d1_m": a, "d2_m": b,
                         "ratio": (b / a) if b != math.inf else math.inf,
                         "prev1": prev1, "prev2": prev2, "src": src})
        per[name] = {"snap_node": src, "snap_dist_m": round(dist, 1),
                     "d1_reach": len(d1), "d2_reach": len(d2),
                     "unreachable": len(d1) - len(d2)}
    return per, rows


# ── 지표 ──────────────────────────────────────────────────────
def _pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def e1(per: dict, rows: list[dict], feats, rv) -> dict:
    """E-1 — 현행 내비게이션(폭 미인지) 대비 개선.

    두 항이다. **진입 실패**는 「현행이 못 가는 길로 보내는가」이고
    **실거리비**는 「우리 길이 얼마나 도는가」다. 둘은 서로 대체하지 않는다 —
    실거리비만 보면 우리가 늘 손해로 읽히고, 진입 실패만 보면 우회 비용이 숨는다.
    """
    ratios = sorted(r["ratio"] for r in rows if r["ratio"] != math.inf)
    fail = sum(1 for r in rows if _pinch(r, feats, rv) is not None)
    out = {
        "what": "현행 내비게이션(폭 미인지) 대비 개선. d1 제약 없음 · d2 제약 있음",
        "denominator": "node",
        "unresolved": "PLAN §1 #94 — 분모를 건물로 할지 노드로 할지 미정. 표본 수·시드도 미정",
        "pairs": len(rows),
        "pairs_with_route": len(ratios),
        "unreachable": len(rows) - len(ratios),
        "entry_fail": fail,
        "entry_fail_pct": _pct(fail, len(rows)),
        "ratio_median": round(st.median(ratios), 3) if ratios else None,
        "ratio_p90": round(ratios[int(len(ratios) * 0.9)], 3) if ratios else None,
        "ratio_max": round(max(ratios), 3) if ratios else None,
        "over_ratio_min": sum(1 for x in ratios if x > RATIO_MIN),
        "per_station": per,
        "gaps": _gaps(per),
    }
    return out


def _gaps(per: dict) -> list[dict]:
    """결손 항. ★ 분모에서 빼지 않고 **따로** 적는다(PLAN §1 #94)."""
    out = []
    for name, s in per.items():
        if s["d1_reach"] and s["d2_reach"] / s["d1_reach"] < 0.05:
            out.append({
                "station": name,
                "what": f"통행 가능 그래프에서 {s['d2_reach']}/{s['d1_reach']} 노드만 닿는다",
                "why": ("접속 노드가 통행 가능 성분의 섬에 있다. 이 출발점에서는 "
                        "역산이 성립하지 않는다 — 쌍을 0 으로 세지 말고 이 항으로 읽어라"),
            })
    return out


def e3(feats: list[dict]) -> dict:
    """E-3 — 판정 가능률. **재산출만 한다**(PLAN §1 #92). 값을 새로 정하지 않는다."""
    n = len(feats)
    props = [f["properties"] for f in feats]
    ln_all = sum(p.get("length_m") or 0 for p in props)
    unk = [p for p in props if p["verdict"] == "unknown"]
    ln_unk = sum(p.get("length_m") or 0 for p in unk)
    nocv = [p for p in props if not p.get("cv_feasible")]
    use_all = sum(p.get("route_usage") or 0 for p in props)
    use_unk = sum(p.get("route_usage") or 0 for p in unk)
    return {
        "what": "영상판정 가능률. 분모는 1,281구간 전수다",
        "n": n,
        "cv_impossible": len(unk),
        "cv_impossible_pct": _pct(len(unk), n),
        "cv_impossible_length_m": round(ln_unk),
        "length_total_m": round(ln_all),
        "cv_impossible_length_pct": _pct(round(ln_unk), round(ln_all)),
        "outside_cctv_range": len(nocv),
        "outside_cctv_range_pct": _pct(len(nocv), n),
        "unknown_reason": dict(collections.Counter(
            p.get("unknown_reason") for p in unk)),
        "mitigation": {
            "what": "영상판정 불가 구간이 담당하는 통행량 몫",
            "route_usage_unknown": use_unk,
            "route_usage_total": use_all,
            "pct": _pct(use_unk, use_all),
        },
    }


# ── #120 역산 ─────────────────────────────────────────────────
def _pinch(row: dict, feats, rv) -> int | None:
    """제약 없는 경로가 처음 만나는 **통행 불가 구간**. 없으면 None."""
    path = kpi._path(row["prev1"], row["src"], row["node"])
    if not path:
        return None
    for i in path:
        if int(rv[feats[i]["properties"]["seg_uid"]]["passable"]) == 0:
            return i
    return None


def _lonlat(pos: dict, node: int) -> tuple[float, float]:
    """노드 번호는 실행 안에서만 뜻이 있다. **답사는 좌표로 간다.**"""
    x, y = pos[node]
    return round(x / MX, 6), round(y / MY, 6)


def scenarios(rows: list[dict], feats, rv, rad: dict, pos: dict) -> dict:
    """`d2/d1 > 1.5 and d2 < inf` 인 쌍을 찾고, 자리 단위로 묶는다.

    선정 조건 셋은 PLAN §1 #120 이 적은 그대로다 —
    **우회로 존재**(d2 < inf · 비율 문턱과 함께 이미 걸러진다) ·
    **CCTV 커버**(목 구간의 `cv_feasible`) · **코너 통과 가능**(우회 경로 전
    구간의 `can_turn`). ★ 코너 조건은 `turn_radius_verified: false` 인 동안
    아무것도 안 거른다 — 그 사실을 `corner_vacuous` 로 같이 적는다.
    """
    hits = []
    for r in rows:
        if r["ratio"] <= RATIO_MIN or r["d2_m"] == math.inf:
            continue
        i0 = _pinch(r, feats, rv)
        if i0 is None:
            continue
        p = feats[i0]["properties"]
        det = kpi._path(r["prev2"], r["src"], r["node"]) or []
        rs = [rad[i] for i in det if rad[i] is not None]
        lon, lat = _lonlat(pos, r["node"])
        hits.append({
            "station": r["station"], "node": r["node"],
            "dest_lon": lon, "dest_lat": lat,
            "d1_m": round(r["d1_m"], 1), "d2_m": round(r["d2_m"], 1),
            "ratio": round(r["ratio"], 3),
            "pinch_seg_uid": p["seg_uid"], "pinch_label": p.get("seg_label"),
            "pinch_road": p.get("road_name"), "pinch_verdict": p["verdict"],
            "pinch_width_min_m": p.get("width_min_m"),
            "cctv_covered": bool(p.get("cv_feasible")),
            "cctv_dist_m": p.get("cctv_dist_m"),
            "detour_corner_ok": all(V.can_turn(x) for x in rs),
            "detour_min_radius_m": round(min(rs), 1) if rs else None,
            "detour_segments": len(det),
        })

    sites: dict[tuple[str, str], dict] = {}
    for h in sorted(hits, key=lambda h: -h["ratio"]):
        sites.setdefault((h["station"], h["pinch_seg_uid"]), dict(h, n_dest=0))
        sites[(h["station"], h["pinch_seg_uid"])]["n_dest"] += 1
    rows_out = sorted(sites.values(), key=lambda h: -h["ratio"])
    picked = [h for h in rows_out if h["cctv_covered"] and h["detour_corner_ok"]]
    return {
        "rule": f"d2/d1 > {RATIO_MIN} and d2 < inf",
        "conditions": ["우회로 존재 (d2 < inf)", "CCTV 커버 (cv_feasible)",
                       "코너 통과 가능 (can_turn)"],
        "corner_vacuous": not V.spec().get("turn_radius_verified"),
        "corner_vacuous_why": ("`turn_radius_verified: false` 인 동안 `can_turn` 이 "
                               "항상 참이라 코너 조건은 아무것도 안 거른다"),
        "pairs": len(hits),
        "sites": len(rows_out),
        "sites_meeting_conditions": len(picked),
        "rows": rows_out,
    }


# ── 산출 ──────────────────────────────────────────────────────
def build(proc: Path, gold: Path, base: Path, tag: str | None) -> tuple[dict, list[str]]:
    """게이트 → 지표. **게이트가 울면 지표를 안 만들고 사유만 돌려준다.**"""
    rep, why = G.gate(proc, gold, base, tag)
    if why:
        return {"gate": rep}, why

    feats = G.segments(proc)
    rv = G.route_rows(proc)
    nid, pos = build_nodes(feats)
    ok = {i for i, f in enumerate(feats)
          if int(rv[f["properties"]["seg_uid"]]["passable"]) == 1}
    naive, safe = build_graph(feats, nid, None), build_graph(feats, nid, ok)
    rad = curvatures(feats)
    per, rows = station_pairs(pos, naive, safe)

    spec = V.spec()
    doc = {
        "as_of": datetime.now(KST).isoformat(timespec="seconds"),
        "git_sha": baseline.git_sha(),
        "produced_by": "tools/evalgen.py",
        "gate": rep,
        "tally": baseline.tally(baseline.load(proc / G.SEG_NAME)),
        "sha256": {n: _sha256(p) for n, p in (
            (G.SEG_NAME, proc / G.SEG_NAME),
            ("route_vehicle.csv", proc / "route_vehicle.csv"),
            ("_manifest.json", proc / "_manifest.json"),
            ("segments.fingerprint.json", gold / "segments.fingerprint.json"),
        ) if p.is_file()},
        "params": {
            "node_tol_m": NODE_TOL,
            "required_width_m": V.required_width(),
            "ratio_min": RATIO_MIN,
            "stations": sorted(STATIONS),
            "vehicle_spec_verified": {k: bool(spec.get(k)) for k in
                                      ("verified", "turn_radius_verified",
                                       "wheelbase_verified")},
        },
        "E1": e1(per, rows, feats, rv),
        "E3": e3(feats),
        "scenarios": scenarios(rows, feats, rv, rad, pos),
        "known_limits": [
            "폭 실측 검증 0건. 모든 지표가 미검증 폭 위에서 나온다(D-25 · PLAN §1 #4)",
            "E-2(오류 비대칭 · #117) · E-4(폭 정확도 · #93)는 전건이 없어 안 낸다",
            "E-1 분모는 노드다. 건물이냐 노드냐는 PLAN §1 #94 가 미정으로 든다",
            "거리는 국소 평면 근사(localgeo)로 잰다. 투영이 아니다",
            "`node` 는 실행 안에서만 뜻이 있는 번호다. 실행 간 인용은 `dest_lon`·`dest_lat` 로 한다",
        ],
    }
    return doc, []


def _print(doc: dict) -> None:
    g, e, s = doc["gate"], doc["E1"], doc["scenarios"]
    t = doc["tally"]
    print(f"게이트 통과 — 봉인 {g['transition']['tag']} · 전이 대각선 밖 {g['transition']['moved']}"
          f" · 지문 L1/L2/L3 일치 · 매니페스트 산출물 결손 {g['manifest']['outputs_missing']}")
    print(f"  구간 {t['n']} · " + " · ".join(f"{k} {v}" for k, v in t["verdict"].items()))
    print(f"\nE-1  쌍 {e['pairs']} · 경로 있는 쌍 {e['pairs_with_route']} · "
          f"도달 불가 {e['unreachable']}")
    print(f"     진입 실패 {e['entry_fail']} ({e['entry_fail_pct']}%) · "
          f"실거리비 중앙 {e['ratio_median']} · p90 {e['ratio_p90']} · 최대 {e['ratio_max']}")
    for gap in e["gaps"]:
        print(f"     ★ 결손 {gap['station']} — {gap['what']}")
    x = doc["E3"]
    print(f"\nE-3  영상판정 불가 {x['cv_impossible']}/{x['n']} ({x['cv_impossible_pct']}%) · "
          f"연장 {x['cv_impossible_length_m']:,}m/{x['length_total_m']:,}m "
          f"({x['cv_impossible_length_pct']}%)")
    print(f"     CCTV 유효범위 밖 {x['outside_cctv_range']}/{x['n']} "
          f"({x['outside_cctv_range_pct']}%) · 완화 항 통행량 몫 {x['mitigation']['pct']}%")
    print(f"\n#120 역산  {s['rule']}  쌍 {s['pairs']} → 자리 {s['sites']} → "
          f"조건 충족 {s['sites_meeting_conditions']}")


def _table(doc: dict) -> None:
    print("\n  출발  목의 구간            판정        폭    CCTV  d1     d2      비율  목적지")
    for r in doc["scenarios"]["rows"]:
        print(f"  {r['station'][:2]}   {str(r['pinch_label'])[:20]:22}{r['pinch_verdict']:10}"
              f"{r['pinch_width_min_m']!s:6}{'있음' if r['cctv_covered'] else '없음':6}"
              f"{r['d1_m']:7.0f}{r['d2_m']:8.0f}{r['ratio']:7.2f}{r['n_dest']:5d}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="평가지표 산출기 — 게이트가 먼저다")
    ap.add_argument("--baseline", default=None, help="대조 봉인 태그 (기본 가장 최근)")
    ap.add_argument("--out", default=None, help="쓸 자리 (기본 data/processed/eval.json)")
    ap.add_argument("--scenarios", action="store_true", help="역산 결과를 표로도 찍는다")
    ap.add_argument("--data", default=None,
                    help="저장소 `data/` 대신 이 트리를 본다 (processed · golden · baseline)")
    a = ap.parse_args(argv)

    proc, gold, base = G.resolve(a.data)
    tag = a.baseline or G.newest_tag(base)

    # ★ 첫 줄이 게이트다. 사유를 찍고 **파일을 안 쓰고** 끝낸다.
    doc, why = build(proc, gold, base, tag)
    if why:
        G.explain(why)
        return 2

    out = Path(a.out) if a.out else (proc / "eval.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    _print(doc)
    if a.scenarios:
        _table(doc)
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
