#!/usr/bin/env python3
"""
segments.py — 도로구간을 노딩해 통과판정 세그먼트 그래프를 만든다.


IN    processed/{boundary_emd,road_link,road_rw,ngii_road,ngii1k,
              ngii1k_xsec,building,building_entrance,cctv,streetlight}_5186.gpkg
      processed/_manifest.json          ★ 계보 검사. 없으면 시작하지 않는다
      processed/seg_uid_map.csv         직전 실행 키. 유지율 산출용
      $FIRE_LANE_DATA/raw/safety/safety_fire_access_*.csv   외부 대조(선택)
OUT   processed/segments_5186.gpkg · segments.geojson · segments.schema.json
      processed/seg_uid_map.csv · nfa_compare.json · corridor_5186.gpkg
PARAM seg/params.py 가 정본. TRUCK=3.0 PARK=2.0 CCTV_RANGE=25.0 등

전제
  ingest.py 가 먼저 돌아야 한다. data/processed 의 road_link / road_rw /
  building / building_entrance / boundary_emd 를 입력으로 쓴다.

원칙
  1. 계산은 EPSG:5186. 표출만 4326. (ingest.py 와 동일)
  2. 동 경계로 clip 하지 않는다. clip 하면 그래프가 깨진다(연결요소 70개/최대 34%).
     buffer(GRAPH_BUFFER) 로 원본 형상을 유지한 채 넉넉히 담는다.
  3. 노딩은 unary_union 만으로 부족하다. T자 접합(끝점이 본선 '중간'에 접함)이
     밀리미터 단위로 벌어져 있어 위상이 안 생긴다. 끝점 투영 스냅이 필수.
       원본 40개 요소 / 93.3%  →  끝점투영 0.5m  6개 / 99.8%
  4. 폭 파라미터는 원본 도로구간(평균 76m)이 아니라 노딩 세그먼트(중앙 37m)
     기준으로 잡아야 한다. 절대값 필터를 그대로 옮기면 짧은 세그먼트가 전멸한다.

산출
  segments.geojson / segments_5186.gpkg / segments.schema.json
"""
from __future__ import annotations
import sys
from collections import Counter

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree

from firelane.paths import PROCESSED
from firelane.segkey import attach_seg_uid, uid_retention, save_uid_map
# ── 파라미터 · 순수 함수 ──────────────────────────────────────
# ★ 정본은 seg/ 다. 여기서 다시 정의하지 않는다(R3).
from firelane.seg import graph as seg_graph
from firelane.seg import report as seg_report
from firelane.seg.basisno import BasisIntervalIndex
from firelane.seg.geom import _dirv, _join, _seal, verdict
from firelane.seg.roadname import RoadNameIndex
from firelane.seg.width import WidthEngine
from firelane.seg.params import (
    NO_MERGE, DEBUG_SEG, DEBUG_XY, _DBG,
    EMD_CD, GRAPH_BUFFER, KEEP_BUFFER, SNAP_TOL, XSEC_EXCL,
    MIN_SEG_LEN, TRUCK, PARK, NFA_RUN_M, CCTV_RANGE,
)

OUT = PROCESSED
CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"


def _lineage_check():
    """계보 검사. 로직은 guards.py 정본. 여기서는 부르고 죽기만 한다."""
    from firelane.guards import CRITICAL, GuardFailure, lineage_check
    try:
        lineage_check(OUT)
    except GuardFailure as e:
        sys.exit(f"★ {e}")
    print(f"  계보 OK: {' · '.join(CRITICAL)}")


def load(key):
    return gpd.read_file(OUT / f"{key}_5186.gpkg").to_crs(CRS_M)


def endpoint_snap(lines, tol=SNAP_TOL):
    tree, out = STRtree(lines), []
    for i, ln in enumerate(lines):
        c = list(ln.coords)
        for idx in (0, -1):
            p, best, bd = Point(c[idx]), None, tol
            for j in tree.query(p.buffer(tol)):
                if j == i:
                    continue
                d = lines[j].distance(p)
                if 0 < d < bd:
                    bd, best = d, lines[j]
            if best is not None:
                q = nearest_points(best, p)[0]
                c[idx] = (q.x, q.y)
        out.append(LineString(c))
    return out


def main():
    emd = load("boundary_emd")
    poly = shapely.make_valid(emd.loc[emd.EMD_CD == EMD_CD, "geometry"].iloc[0])
    _lineage_check()
    road = load("road_link")
    rw   = load("road_rw")
    # 가로등. 지번 단위 회로 대표점이라 개별 폴 위치가 아니다.
    # 마커 표현은 streetlight.py 가 담당한다(group-by + count, 반경 50m 원).
    # 여기서는 구간 피처 light_count 로만 쓴다. MASTER §6 (2026-08-14 개정)
    # ★ 정본은 processed 다. RAW 를 직접 읽지 않는다.
    #   RAW 를 읽으면 ingest(1786, 스코프 필터 후)와 여기(3805, 전체)가
    #   서로 다른 값을 쓰게 된다. 실제로 그랬다. (2026-08-14)
    _lp = [str(OUT / "streetlight_5186.gpkg")] if (OUT / "streetlight_5186.gpkg").exists() else []
    _light = None
    if _lp:
        _light = gpd.read_file(_lp[0]).to_crs(CRS_M)
        print(f"  가로등 {len(_light)}등 (processed 정본)")
    else:
        # ★ 조용히 넘기지 않는다. 없으면 light_count 가 전 구간 0 이 되는데
        #   파이프라인은 OK 를 찍는다. 2026-08-14 에 실제로 겪었다.
        print("  ! streetlight_5186.gpkg 없음 — light_count 가 전부 0 이 된다")

    ngii = load("ngii_road")
    # 1:1,000 수치지형도 도로경계(도엽 20장 병합). 폭 산출 주 소스.
    try:
        ngii1k = load("ngii1k")
    except Exception:
        ngii1k = None
        print("  ! ngii1k_5186.gpkg 없음 — 1:5,000 으로 대체")       # 결정 63: 폭 주 소스(수치지도 도로경계면)
    bld  = load("building")
    ent  = load("building_entrance")

    G, _dups = seg_graph.build_graph(road, poly, endpoint_snap)

    corr, use = seg_graph.access_corridor(G, ent, poly, out_dir=OUT)

    # CCTV 유효 범위. needs_cv 구간이 이 안에 없으면 영상판정 자체가 불가능하다.
    cctv = gpd.read_file(OUT/"cctv_5186.gpkg").to_crs(CRS_M)
    cctv_u = unary_union(list(cctv.geometry))

    keep = poly.buffer(KEEP_BUFFER)
    if corr:
        keep = keep.union(unary_union([c["geometry"] for c in corr]).buffer(70))

    # 결정 63 — 폭 주 소스 = 수치지도 도로경계면(NF_A_A01000), 폴백 = 실폭도로.
    # 두 소스는 경쟁이 아니라 상보 관계다. 수치지도는 넓은 길을 정확히 그리지만
    # 보행자 통로급 최협소 골목을 도로면으로 아예 그리지 않는다(표본 100 중 커버 70).
    # 나머지를 실폭도로가 메운다.
    _clip = keep.buffer(20)      # 세그먼트 스코프(동명동+회랑)와 일치시킨다

    ngii1k_u = (_seal(ngii1k[ngii1k.intersects(_clip)].geometry)
                if ngii1k is not None and len(ngii1k) else None)
    ngii_u = _seal(ngii[ngii.intersects(_clip)].geometry)
    rw_u   = _seal(rw[rw.intersects(_clip)].geometry)
    bld_u = unary_union([shapely.make_valid(g) for g in bld[bld.intersects(poly.buffer(80))].geometry])
    deg = Counter()
    for a, b in G.edges():
        deg[a] += 1; deg[b] += 1
    xn = unary_union([Point(p) for p, d in deg.items() if d >= 3])

    # ── 교차부 형상 (A0080000 평면교차점) ─────────────────────
    # 종전에는 노드에서 XSEC_EXCL(5.0m) 이내를 일괄 제외했다. 눈대중 반경이라
    # 양쪽으로 틀렸다 — 실제 교차부 등가반경은 중앙 3.2m · p90 7.5m 라
    # 작은 교차부에서는 과하게 도려내 표본을 죽이고, 큰 교차부에서는 부족해
    # 오염이 샜다. 동명로25번길 t=29·31(끝에서 5.1m)이 후자다.
    # NGII 가 실제 교차부 폴리곤을 준다(스코프 내 696건, 구간의 79%를 덮는다).
    # 폴리곤이 없는 교차로는 기존 반경 방식으로 폴백한다.
    _xp = OUT / "ngii1k_xsec_5186.gpkg"
    xsec_poly = None
    if _xp.exists():
        try:
            _xg = gpd.read_file(_xp, layer="ngii1k_xsec").to_crs(CRS_M)
            xsec_poly = unary_union(_xg.geometry.buffer(0))
            print(f"  교차부 폴리곤 {len(_xg)}건 적용")
        except Exception as _e:
            print(f"  ! 교차부 폴리곤 로드 실패 — 반경 {XSEC_EXCL}m 폴백: {_e}")
    else:
        # 조용히 넘기지 않는다. 없으면 판정 기준이 달라진다.
        print(f"  ! ngii1k_xsec_5186.gpkg 없음 — 반경 {XSEC_EXCL}m 폴백")

    # ── 폭 산출 엔진 ─────────────────────────────────────────
    # 폭 소스 3종 + 건물 + 교차부. 실행 내내 불변이므로 한 번 묶는다.
    _wx = WidthEngine(ngii1k_u, ngii_u, rw_u, bld_u, xn, xsec_poly)
    widths = _wx.widths




    # 표출 범위 = 동명동 + 접근 회랑. 회랑도 판정 색상을 가져야
    # "안전센터에서 오는 길이 어떤 상태인가"가 보인다.

    # 폭 소스(rw_u / bld_u)는 poly.buffer(80) 으로 클립돼 있다.
    # 그 밖의 회랑 구간은 "폭을 못 잰 것"이 아니라 "잴 대상이 아닌 것"이다.
    # 둘을 같은 이름으로 부르면 화면이 "골목의 44%를 모른다"로 오독된다.
    # 도로명. 노딩하면 원본 속성이 끊기므로 중점 최근접으로 되붙인다.
    # seg_id(DM00001)만 보이면 사람이 어느 골목인지 알 수 없다.
    _rnx = RoadNameIndex.from_gdf(road)
    # 기초구간 — 도로명주소법 기초번호 정본. 없으면 도로명만 라벨로 쓴다.
    _bnx = None
    try:
        _intrvl = gpd.read_file(PROCESSED / "road_intrvl.geojson")
        if road.crs is not None and _intrvl.crs != road.crs:
            _intrvl = _intrvl.to_crs(road.crs)
        _bnx = BasisIntervalIndex.from_gdf(_intrvl)
        print(f"[기초번호] 기초구간 {len(_intrvl)}개")
    except Exception as _e:                                   # noqa: BLE001
        print(f"[기초번호] 기초구간을 못 읽었다 — seg_label 은 도로명만: {_e}")


    if _dups:
        print(f"\n[병렬 엣지 {len(_dups)}] 같은 노드쌍에 두 형상 — 긴 쪽을 버렸다")
        print("  남긴길이  버린길이   비  위치도로")
        _bad = 0
        for _kl, _ll, _c in sorted(_dups, key=lambda x: -x[1]/max(x[0], 1e-9)):
            _r = _kl and _ll / _kl or 0
            _nm = _rnx.nearest(_c, 15.0)
            if _r > 1.5:
                _bad += 1
            print(f"  {_kl:8.1f}  {_ll:8.1f}  {_r:5.2f}  {_nm or '(미매칭)'}"
                  + ("   ← 별개 경로 의심" if _r > 1.5 else ""))
        print(f"  길이비 1.5 초과 {_bad}건" +
              ("  ★ 병렬 처리 방식 재검토 필요" if _bad else "  — 중복 형상. 무해"))

    # ── 산출 단위 구성 (B2) ──────────────────────────────────
    # 그래프 G 는 라우팅·교차로 노드(xn) 정본이므로 손대지 않는다.
    # 산출 단위만 묶는다. 도로 B 는 교차로 노드에 그대로 붙어 있고
    # 연결성·최단경로가 변하지 않는다.
    #
    # 교차로 안에만 존재하는 조각은 제자리에서 폭을 잴 수 없다. 기하학적으로
    # 정의되지 않는다 — 법선이 교차하는 도로를 따라 길이 방향으로 달려서
    # 폭이 아니라 "옆 도로가 얼마나 뻗어 있나"를 잰다(제봉로 3.3m 구간에서 55m).
    # 그래서 값을 빌려오는 대신 독립 피처로 두지 않는다. 동일선상 이웃과
    # 하나의 산출 단위로 묶고, 그 단위 위에서 XSEC_EXCL 을 유지한 채 정규 측정한다.
    # wmin 이 표본 최솟값인 것은 나머지 세그먼트도 마찬가지다. 파편만 예외였다.
    COLLIN_DEG  = 30.0     # 동일선상 판정. 이 각을 넘으면 다른 도로다
    MERGE_PASS  = 4        # 짧은 것끼리 연쇄로 붙는 경우 대비

    units, node2u = {}, {}
    for i, (a, b, d) in enumerate(G.edges(data=True)):
        units[i] = {"geom": d["geom"], "ends": [a, b], "n": 1,
                    "why": None, "usage": use.get(frozenset((a, b)), 0)}
        node2u.setdefault(a, set()).add(i)
        node2u.setdefault(b, set()).add(i)
    # 산출 범위 밖 단위는 재지 않는다. 병합 상대로만 쓰이고, 흡수되면 재측정된다.
    _ink = {uid for uid, u in units.items() if u["geom"].intersects(keep)}

    # ── 공간 커버리지 (R10) ──────────────────────────────────
    # ★ 건수·컬럼·CRS·인코딩이 전부 맞아도 공간이 안 맞을 수 있다.
    #   2026-08-18 V-WORLD 동구 SHP 판은 계약 검사를 전부 통과하면서
    #   스코프의 69%(755/1091)를 안 덮었다. 폭이 조용히 폴백으로 밀리고
    #   silpok 이 84 → 203 으로 늘었는데, 그것을 "소스가 줄었다"로 오독해
    #   문서까지 고쳤다가 다음 날 되돌렸다. 여기서 먼저 죽는다.
    if ngii1k_u is not None:
        from firelane.guards import GuardFailure, coverage_check
        try:
            _cvr = coverage_check([units[uid]["geom"] for uid in _ink], [ngii1k_u],
                                  label="ngii1k 도로경계")
            print(f"  공간 커버리지 OK · 미커버 {_cvr:.1%}")
            # ★ 비율은 게이트고 목록은 작업 지시다. 둘 다 남긴다.
            #   2026-08-18 까지 비율만 찍혔고 아무도 어느 구간인지 묻지
            #   않았다. 같은 날 정사영상 대조로 중심선이 도로를 안 따라가는
            #   구간을 찾았는데, 이 검사가 이미 그것을 세고 있었다.
            #
            # ★ 여기서 seg_uid 는 못 쓴다. 그것은 노딩·병합이 끝난 뒤에
            #   붙는다. 대신 WGS84 중점 좌표를 낸다. 내부 단위 id 는
            #   저장소 밖에서 무의미하지만 좌표는 네이버지도·거리뷰에
            #   그대로 넣을 수 있다. 목록의 목적은 답사이지 추적이 아니다.
            from firelane.guards import uncovered_indices
            _ordered = sorted(_ink)
            _miss = uncovered_indices([units[uid]["geom"] for uid in _ordered],
                                      [ngii1k_u])
            if _miss:
                import json as _json

                import pyproj as _pyproj
                _to4326 = _pyproj.Transformer.from_crs(
                    "EPSG:5186", "EPSG:4326", always_xy=True).transform
                _rows = []
                for _i in _miss:
                    _g = units[_ordered[_i]]["geom"]
                    _pt = _g.interpolate(0.5, normalized=True)
                    _lon, _lat = _to4326(_pt.x, _pt.y)
                    _rows.append({"unit": _ordered[_i],
                                  "length_m": round(_g.length, 1),
                                  "lat": round(_lat, 6), "lon": round(_lon, 6)})
                _rows.sort(key=lambda r: -r["length_m"])
                print(f"    폴리곤 밖 {len(_rows)}구간 — 답사·재확인 대상"
                      f" (상위 10 · 전체는 uncovered_units.json)")
                for _r in _rows[:10]:
                    print(f"      {_r['length_m']:6.1f}m  "
                          f"{_r['lat']:.6f},{_r['lon']:.6f}")
                (PROCESSED / "uncovered_units.json").write_text(
                    _json.dumps(_rows, ensure_ascii=False, indent=1),
                    encoding="utf-8")
        except GuardFailure as _e:
            sys.exit(f"★ {_e}")

    W = {uid: widths(units[uid]["geom"]) for uid in _ink}
    _fail0 = sum(1 for v in W.values() if v[0] is None)
    print(f"  산출범위 단위 {len(_ink)} / 전체 {len(units)} · 폭 미산출 {_fail0}")



    _cos_lim = -np.cos(np.radians(COLLIN_DEG))
    _mrg = []
    for _pass in range(0 if NO_MERGE else MERGE_PASS):
        _todo = [uid for uid in list(units)
                 if uid in W and W[uid][0] is None]
        if not _todo:
            break
        _n_moved = 0
        for uid in _todo:
            if uid not in units:
                continue
            u = units[uid]
            best = None
            for nd in list(u["ends"]):
                du = _dirv(u["geom"], nd)
                if du is None:
                    continue
                for vid in list(node2u.get(nd, ())):
                    if vid == uid or vid not in units or nd not in units[vid]["ends"]:
                        continue
                    dv = _dirv(units[vid]["geom"], nd)
                    if dv is None:
                        continue
                    dot = du[0]*dv[0] + du[1]*dv[1]
                    if dot <= _cos_lim and (best is None or dot < best[0]):
                        best = (dot, vid, nd)
            if best is None:
                continue                      # 동일선상 이웃 없음. 병합하지 않는다
            _dot, vid, nd = best
            v = units[vid]
            gj = _join(u["geom"], v["geom"])
            if gj is None:
                continue
            ends = [e for e in u["ends"] + v["ends"] if e != nd]
            if len(ends) != 2:
                continue                      # 고리. 건드리지 않는다
            for n2 in set(u["ends"] + v["ends"]):
                node2u.get(n2, set()).discard(uid)
                node2u.get(n2, set()).discard(vid)
            for n2 in ends:
                node2u.setdefault(n2, set()).add(uid)
            _mrg.append((uid, W[uid][5], round(u["geom"].length, 1),
                         round(v["geom"].length, 1), round(np.degrees(np.arccos(
                             max(-1.0, min(1.0, -_dot))))), 1))
            u.update(geom=gj, ends=ends, n=u["n"]+v["n"],
                     why=u["why"] or W[uid][5],
                     usage=max(u["usage"], v["usage"]))
            del units[vid]; W.pop(vid, None)
            W[uid] = widths(gj)
            _n_moved += 1
        print(f"  병합 pass{_pass+1} · 대상 {len(_todo)} · 병합 {_n_moved}"
              f" · 남은 미산출 {sum(1 for x in W.values() if x[0] is None)}")
        if _n_moved == 0:
            break
    print(f"  산출단위 {G.number_of_edges()} → {len(units)}"
          f" · 폭 미산출 {_fail0} → {sum(1 for x in W.values() if x[0] is None)}")
    if _mrg:
        _ml = sorted(((units[u]['geom'].length, units[u]['n'], u)
                      for u, *_ in _mrg if u in units), reverse=True)[:10]
        print("  병합 후 최장 단위:",
              " ".join(f"{l:.0f}m({n})" for l, n, _ in _ml))

    rec = {}
    for i, (uid, u) in enumerate(sorted(units.items())):
        g, (a, b) = u["geom"], u["ends"]
        if not g.intersects(keep):
            continue
        sid = f"DM{i:05d}"
        short = g.length < MIN_SEG_LEN
        if uid not in W:
            W[uid] = widths(g)          # 병합으로 범위 안에 들어온 단위
        wmin, wmax, fb, wsrc, wdis, wfail, (wcov, wnt) = W[uid]
        _road_nm, _road_side, _road_bt = _rnx.match(g)
        v = verdict(wmin, wmax, wnt)
        if short and wmin is None:
            v = "fragment"

        # ── 도로대장 명목폭에 의한 확정 (2026-08-18 적용 범위 확대) ──
        # verdict() 는 blocked 를 wmax 로만 낸다. wmax 가 없으면 아무리 좁아도
        # blocked 로 갈 길이 없다. 결손 496건 중 도로 폭 3.0m 미만이 160건이며
        # 그중 blocked 는 0 이었다(대조군은 24%). 폭 0.38m 짜리가 "CCTV 가 없어
        # 판정 보류"로 표시됐다. 결손이 관대한 쪽으로 해석되고 있었다.
        #
        # 종전에는 아래 `elif v == "unknown"` 가지에만 걸려 적용이 2건이었다.
        # 그 가지는 wmin 조차 없는 구간만 오는데, 실제로 막힌 것은
        # **wmin 은 있고 wmax 가 없는** 구간이다.
        #
        # 두 근거가 독립적으로 일치할 때만 건다.
        #     실측 노면폭 < TRUCK   그리고   도로대장 명목폭 < TRUCK
        # 대장폭 단독으로 실측을 뒤집지 않는다(§3-3 원칙). 실측이 3.0 이상인데
        # 대장이 미만인 모순 6건은 이 규칙에 걸리지 않는다.
        #
        # CCTV 강등보다 앞에 둔다. blocked 는 도면으로 확정되므로 카메라 유무와
        # 무관하다. 뒤에 두면 needs_cv → no_cctv 로 먼저 내려가 이 규칙을 비껴간다.
        if (wmax is None
                and (wmin is None or wmin < TRUCK)
                and _road_bt is not None and _road_bt < TRUCK):
            v = "blocked"

        # 영상판정 가능성. 구간에서 가장 가까운 CCTV 까지의 거리로 판단한다.
        d_cctv = round(g.distance(cctv_u), 1)
        cv_ok = d_cctv <= CCTV_RANGE

        # needs_cv 인데 CCTV 사각이면 영상판정이 성립하지 않는다.
        # 도면으로도 확정 못 하고 영상으로도 확정 못 하므로 unknown 이다.
        # blocked / clear 는 도면만으로 확정되므로 CCTV 와 무관하다.
        # ★ 2026-08-22. unknown 352구간이 전부 "no_cctv" 하나였다.
        #   화면에서 회색 한 덩어리로 보이지만 안에는 성격이 다른 넷이 있다.
        #   판정은 전부 정당하다 — 확인한 결과 오분류는 0건이었다. 다만
        #   "왜 회색인가" 를 화면이 설명하지 못했다.
        #
        #     no_cctv_narrow  62  노면 < 3.0 이고 **대장폭도** < 3.0 이다.
        #                         두 근거가 일치하는데도 blocked 가 아닌 이유는
        #                         담~담이 3.0 이상이기 때문이다. 갓길로 지날
        #                         여지가 있어 도면만으로 확정하지 않는다.
        #                         (62건 전부 wmax >= 3.0 · 최대 17.26m)
        #     no_cctv_thin   128  노면만 < 3.0 이고 대장폭은 3.0 이상이거나
        #                         없다. 근거가 하나뿐이라 더 약하다.
        #                         §3-3 — 대장폭 단독으로 실측을 뒤집지 않는다.
        #     no_cctv_band   152  3.0~7.0 대역. 주정차 여부로 갈린다.
        #                         영상판정의 본래 대상이다.
        #     no_cctv_single  10  wmin >= 7.0 인데 정규표본이 1개라 clear 를
        #                         보류했다. DM02825 사고(2.7m 구간이 표본
        #                         하나로 42.1m → clear)의 방어다.
        #     width          128  폭 산출 자체가 안 됐거나 근거가 하나다.
        #
        #   ★ 색은 바뀌지 않는다. 판정도 바뀌지 않는다. 툴팁만 정확해진다.
        reason = None
        if v == "needs_cv" and not cv_ok:
            if wmin is None:
                reason = "width"
            elif wmin >= TRUCK + 2 * PARK:
                reason = "no_cctv_single"      # 표본 부족으로 clear 보류
            elif wmin < TRUCK:
                # 대장폭이 같이 좁으면 근거 2개, 아니면 1개다. 갈라 적는다.
                reason = ("no_cctv_narrow"
                          if _road_bt is not None and _road_bt < TRUCK
                          else "no_cctv_thin")
            else:
                reason = "no_cctv_band"        # 3~7m. 주정차로 갈린다
            v = "unknown"
        elif v == "unknown":
            # ROAD_BT 에 의한 확정은 위로 올렸다. 여기 남은 unknown 은
            # 대장폭도 없거나 3.0m 이상인 구간이다.
            reason = "width"

        rec[sid] = dict(seg_id=sid, width_min_m=wmin, width_max_m=wmax,
                        verdict=v, unknown_reason=reason,
                        cctv_dist_m=d_cctv, cv_feasible=bool(cv_ok),
                        width_verified=False, midpoint_fallback=fb, inherited=False,
                        width_src=wsrc,
                        width_disagree_m=wdis,
                        width_fail=wfail,          # ★ 진단용. 저장 전 drop
                        road_name=_road_nm, road_side=_road_side, road_bt_m=_road_bt,
                        seg_label=(_bnx.label(_road_nm, g) if _bnx else _road_nm),
                        light_count=(int(_light.intersects(g.buffer(50)).sum())
                                     if _light is not None else None),
                        in_emd=bool(g.intersects(poly)),
                        route_usage=u["usage"],
                        merged_n=u["n"], merge_why=u["why"],
                        cov_ngii1k=wcov["ngii1k"], cov_ngii=wcov["ngii"],
                        cov_silpok=wcov["silpok"], n_sample=wnt,
                        width_cov=(wcov.get(wsrc) if wsrc else None),
                        length_m=round(g.length, 1), _n=(a, b), geometry=g)

    bynode = {}
    for sid, r in rec.items():
        for n in r["_n"]:
            bynode.setdefault(n, []).append(sid)
    # 인접 상속은 하지 않는다. 교차로 파편의 이웃은 사방이라 어느 값을
    # 물려받아도 근거가 없다. 편차가 이웃 자체의 두 배였다(-2.00 vs -1.00).
    # 못 잰 것은 못 잰 것으로 둔다.

    # 소방청 지정 기준의 "구간 100m 이상"은 세그먼트 단위가 아니라 연속 구간 단위다.
    # 같은 판정을 가진 인접 세그먼트를 이어붙여 연속 길이를 잰다.
    import networkx as _nx
    for target in ("blocked", "needs_cv"):
        sub = _nx.Graph()
        for sid, r in rec.items():
            if r["verdict"] == target:
                sub.add_edge(*r["_n"], sid=sid, length=r["length_m"])
        for comp in _nx.connected_components(sub):
            g2 = sub.subgraph(comp)
            run = sum(d["length"] for _, _, d in g2.edges(data=True))
            for _, _, d in g2.edges(data=True):
                rec[d["sid"]]["run_length_m"] = round(run, 1)
                rec[d["sid"]]["nfa_designated"] = bool(run >= NFA_RUN_M)
    # 인접에 폭 있는 세그먼트가 없어 상속에 실패한 파편은 unknown 으로 떨어뜨린다.
    # verdict 어휘에 fragment 는 없다.
    for r in rec.values():
        if r["verdict"] == "fragment":
            r["verdict"] = "unknown"
            r["unknown_reason"] = "width"
    for r in rec.values():
        r.setdefault("run_length_m", None)
        r.setdefault("nfa_designated", False)
        r.pop("_n")

    g = gpd.GeoDataFrame(list(rec.values()), crs=CRS_M)
    # ── seg_uid ──────────────────────────────────────────────
    # seg_id 는 실행 간 유지되지 않는다. 노딩 규칙이 바뀌면서 1266 → 1087 이
    # 되었을 때 번호가 전부 밀렸다. 실측값·관측점·영상판정 반환값·향후 DB PK 는
    # 전부 seg_uid 에 붙는다. seg_id 는 콘솔·디버그 표시용으로만 남긴다.
    g = attach_seg_uid(g)
    _ret = uid_retention(OUT / "seg_uid_map.csv", g)
    print(f"  seg_uid {g.seg_uid.nunique()}개 · 직전 실행 대비 유지율 {_ret:.1%}")
    if _ret < 0.90:
        print("  ! 유지율 90% 미만 — segkey 규칙 재검토 필요")
    save_uid_map(g, OUT / "seg_uid_map.csv")

    seg_report.nfa_compare(g)
    # ── 소스별 커버율 ────────────────────────────────────────
    seg_report.diagnostics(g)

    _dbg_ids = list(DEBUG_SEG)
    if DEBUG_XY:
        _x, _y = (float(v) for v in DEBUG_XY.split(",")[:2])
        _near = g.iloc[g.distance(Point(_x, _y)).values.argmin()]
        print(f"\n[덤프대상] ({_x:.0f},{_y:.0f}) 최근접 = {_near.seg_id} "
              f"{_near.road_name} {_near.length_m}m")
        _dbg_ids.append(_near.seg_id)
    for _sid in _dbg_ids:
        _row = g[g.seg_id == _sid]
        if not len(_row):
            print(f"\n[덤프] {_sid} 없음")
            continue
        _gg = _row.geometry.iloc[0]
        print(f"\n[덤프] {_sid} {_row.road_name.iloc[0]} "
              f"len={_row.length_m.iloc[0]}m merged={_row.merged_n.iloc[0]} "
              f"side={_row.road_side.iloc[0]} bt={_row.road_bt_m.iloc[0]}")
        _DBG["on"] = True
        _r = widths(_gg)
        _DBG["on"] = False
        print(f"  → wmin={_r[0]} wmax={_r[1]} src={_r[3]} fail={_r[5]} cov={_r[6]}")
    seg_report.write_outputs(g)


if __name__ == "__main__":
    main()
