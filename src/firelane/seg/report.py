#!/usr/bin/env python3
"""
seg/report.py — 대조 · 진단 · 산출물 기록.

판정이 끝난 GeoDataFrame 하나만 받는다. 계산은 하지 않는다.
2026-08-18 Stage 4 에서 `segments.py` 의 `main()` 밖으로 꺼냈다.

`nfa_compare` 는 우리 폭에 대한 **유일한 외부 대조 수단**이다. 두 번 소실됐다 —
경로 오류로 죽어 있던 것이 08-13, 터미널에만 존재하던 것이 08-17. 이제 모듈로
분리돼 있으니 세 번째로 조용히 사라지기 어렵다.

로직은 한 글자도 바꾸지 않았다. `tools/golden.py` 로 산출물 동일을 증명한다.
"""
from __future__ import annotations

import hashlib
import json

import geopandas as gpd
from shapely.ops import unary_union

from firelane.paths import PROCESSED, RAW
from firelane.seg.geom import VERDICT_RULE
from firelane.seg.params import (
    CCTV_RANGE,
    MIN_SEG_LEN,
    NFA_RUN_M,
    OLD_SNAP,
    PARK,
    SNAP_TOL,
    TRUCK,
    WMAX_CAP,
    XSEC_EXCL,
)

OUT = PROCESSED
CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"


def nfa_compare(g):
    """소방서 지정 구간과 우리 폭을 도로명 단위로 대조하고 파일로 남긴다."""
    # ── 소방서 지정 구간 대조 ────────────────────────────────
    # 동부소방서 소방통로확보대상 지역 현황(2025-07-31)의 폭과 비교한다.
    # 좌표가 없어 도로명 단위로만 매칭되므로 참고값이다.
    # 소방서가 지정한 것은 그 도로명 중 가장 좁은 구간이므로,
    # 우리 값도 최솟값 쪽으로 비교하는 것이 타당하다.
    # ★ RAW 는 $FIRE_LANE_RAW 다. ROOT/"data"/"raw" 로 박아두면 exists() 가
    #   항상 거짓이라 이 블록이 통째로 죽는다. 실제로 한 번도 실행된 적이 없었다.
    #   소방서 지정 구간은 우리 폭에 대한 유일한 외부 대조 수단이다.
    fa = RAW / "safety" / "safety_fire_access_jngj-dong_20250731.csv"
    if fa.exists():
        import csv
        import re
        rows = list(csv.DictReader(fa.open(encoding="cp949")))
        road = gpd.read_file(OUT/"road_link_5186.gpkg").to_crs(CRS_M)
        print("\n[소방서 지정 구간 대조]")
        # ★ 2026-08-18. print 만 하던 것을 파일로도 남긴다.
        #   이 대조는 우리 폭에 대한 유일한 외부 대조 수단인데 두 번 소실됐다.
        #   경로 오류로 죽어 있던 것이 8/13, 터미널에만 있던 것이 8/17 이다.
        #   8/17 봉인 때 7.24m 를 문서에서 손으로 옮겨 적어야 했다.
        _nfa_rows = []
        for r in rows:
            for rn in set(re.findall(r"[가-힣]+로\d*번?길", r["지역명"])):
                sel = road[road.RN == rn]
                if not len(sel):
                    continue
                ru = unary_union(list(sel.geometry))
                hit = g[g.geometry.buffer(1).intersects(ru)].dropna(subset=["width_min_m"])
                if not len(hit):
                    continue
                w_nfa = r["폭(m)"]
                try:
                    wf = float(str(w_nfa).split("~")[0])
                except ValueError:
                    continue
                # 소방서 기록폭은 구간 대표폭으로 보인다. 최솟값이 아니라 중앙값과 비교한다.
                # (하위10% 로 비교하면 교차로 근처 극협소 지점을 잡아 -3~-7m 로 벌어진다)
                med = hit.width_min_m.median()
                print(f"  {rn:14s} 소방서 {w_nfa:>7s}m │ 우리 중앙 {med:5.2f}m "
                      f"({med - wf:+.2f}) │ 세그 {len(hit):3d} │ "
                      + " ".join(f"{k}:{v}" for k, v in hit.verdict.value_counts().items()))
                _nfa_rows.append({
                    "road": rn,
                    "nfa_m": wf,
                    "nfa_raw": str(w_nfa),
                    "ours_median_m": round(float(med), 2),
                    "dev_m": round(float(med) - wf, 2),
                    "n_seg": int(len(hit)),
                    "verdict": {k: int(v) for k, v in hit.verdict.value_counts().items()},
                })

        if _nfa_rows:
            import json as _json
            from datetime import datetime as _dt
            from datetime import timedelta as _td
            from datetime import timezone as _tz
            _abs = round(sum(abs(x["dev_m"]) for x in _nfa_rows), 2)
            _out = {
                "as_of": _dt.now(_tz(_td(hours=9))).isoformat(timespec="seconds"),
                "source": str(fa.name),
                "ref": "동부소방서 소방통로확보대상 지역 현황 (20구간 7,120m)",
                "match_by": "도로명. 소방서 자료에 좌표가 없다",
                "compare": "구간 대표폭이므로 중앙값과 비교. 최솟값이면 -3~-7m 로 벌어진다",
                "caveat": ("★ 이것은 검증이 아니라 적합(fit)일 수 있다. 12.6 → 7.24 로 "
                           "줄이는 과정에서 이 표를 게이트로 썼다. 게이트로 쓴 자료는 "
                           "그 순간부터 외부 검증 수단이 아니다. MASTER 4절 참조."),
                "abs_dev_sum_m": _abs,
                "n_road": len(_nfa_rows),
                "rows": sorted(_nfa_rows, key=lambda x: abs(x["dev_m"])),
            }
            (OUT / "nfa_compare.json").write_text(
                _json.dumps(_out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  절대편차 합 {_abs}m · {len(_nfa_rows)}구간"
                  f"  → {(OUT / 'nfa_compare.json').name}")
        else:
            # 없으면 소리를 낸다. 조용한 결측을 만들지 않는다.
            print("  ★ 매칭 0구간. 도로명 매칭이 깨졌다 — RN 컬럼과 지역명 형식 확인")


def diagnostics(g):
    """산출물을 사람이 읽을 수 있게 요약한다. 아무것도 바꾸지 않는다."""
    # 표본 축 소스 혼합이 어디서 얼마나 일어나는지. 채택 규칙(STEP 5-1) 근거.
    _gv = g[g.n_sample > 0]
    print(f"\n[소스 커버율] 표본 있는 단위 {len(_gv)}"
          f" · 소스별 snap {'OFF(종전)' if OLD_SNAP else 'ON'}")
    print(_gv[["cov_ngii1k", "cov_ngii", "cov_silpok"]]
          .describe(percentiles=[.25, .5, .75]).round(3).to_string())
    _mix = _gv[(_gv.cov_ngii1k > 0) & (_gv.cov_ngii1k < 1)]
    print(f"  1k 부분커버(0<cov<1) {len(_mix)} · 그중 채택소스가 1k 아닌 것 "
          f"{int((_mix.width_src != 'ngii1k').sum())}")
    print("  채택 소스 분포:",
          dict(g.width_src.value_counts(dropna=False).items()))
    _wc = g.width_cov.dropna()
    print(f"  채택소스 커버율 — 1.0 인 구간 {int((_wc >= 1.0).sum())}"
          f" · 0.5 미만 {int((_wc < 0.5).sum())} · 평균 {_wc.mean():.3f}")
    _thin = g[(g.width_cov.notna()) & (g.width_cov < 0.5)]
    if len(_thin):
        print("  커버율 0.5 미만 상위 (실측 우선순위)")
        print(_thin.nsmallest(10, "width_cov")[
            ["seg_id", "road_name", "length_m", "width_min_m",
             "width_src", "width_cov", "n_sample"]].to_string(index=False))

    # ── 폭 미산출 진단 ───────────────────────────────────────
    # STEP 4-1. 사유별 분포를 보고 원인을 특정한다. 추정 금지.
    _w = g[g.unknown_reason == "width"]
    print(f"\n[폭 미산출 진단] {len(_w)}구간")
    if len(_w):
        print(_w.width_fail.fillna("(none)").value_counts().to_string())
        print("\n사유별 길이")
        print(_w.groupby(_w.width_fail.fillna("(none)")).length_m
              .agg(["count", "median", "max"]).round(1).to_string())
        print("\n전체 목록")
        print(_w[["seg_id", "road_name", "length_m", "in_emd", "width_fail"]]
              .sort_values(["width_fail", "length_m"]).to_string(index=False))
    _mg = g[g.merged_n > 1]
    print(f"\n[병합 단위] {len(_mg)}개 · 흡수된 엣지 합 {int(_mg.merged_n.sum())}")
    if len(_mg):
        print(_mg.groupby(_mg.merge_why.fillna("(none)")).agg(
            n=("seg_id", "size"), 길이중앙=("length_m", "median"),
            길이최대=("length_m", "max")).round(1).to_string())
        print(_mg.verdict.value_counts().to_string())
        print("\n  병합으로 blocked 이 된 단위 — run_length 부풀림 점검")
        _mb = _mg[_mg.verdict == "blocked"]
        print(_mb[["seg_id", "road_name", "road_side", "length_m", "merged_n",
                   "width_min_m", "width_max_m", "width_src", "road_bt_m",
                   "run_length_m"]].to_string(index=False)
              if len(_mb) else "  없음")
    _susp = g[(g.verdict == "blocked") & (g.length_m > 30)]
    print(f"\n[blocked 의심] 길이 30m 초과인데 통행불가 {len(_susp)}구간")
    if len(_susp):
        print(_susp[["seg_id", "road_name", "road_side", "length_m", "merged_n",
                     "width_min_m", "width_max_m", "width_src", "road_bt_m"]]
              .sort_values("length_m", ascending=False).to_string(index=False))
    print(f"\n[연속구간장] nfa_designated {int(g.nfa_designated.sum())}구간"
          f" · 최대 run {g.run_length_m.max()}m")
    print(f"[길이분포] 중앙 {g.length_m.median():.1f}m · 최대 {g.length_m.max():.1f}m"
          f" · 100m초과 {(g.length_m > 100).sum()}")


def write_outputs(g):
    """gpkg · geojson · schema 를 쓰고 sha 를 돌려준다."""

    # 진단 컬럼은 산출물에 넣지 않는다. 스키마·sha 를 바꾸면 안 된다.
    g = g.drop(columns=["width_fail"])

    g.to_file(OUT / "segments_5186.gpkg", driver="GPKG", layer="segments")
    g.to_crs(CRS_W).to_file(OUT / "segments.geojson", driver="GeoJSON")
    h = hashlib.sha256((OUT / "segments.geojson").read_bytes()).hexdigest()
    (OUT / "segments.schema.json").write_text(json.dumps({
        "crs": CRS_W, "sha256": h, "count": len(g), "width_verified": False,
        "note": "width_* 는 D-25 레이저 실측 전 미검증 값. verdict 문자열만 참조하고 임계값을 하드코딩하지 말 것.",
        "fields": {
            "seg_uid": "str, 실행 간 유지되는 키. {지역}-{중점X}-{중점Y}-{도로명해시}. 실측·관측점·영상판정·DB PK 는 전부 이 키를 쓴다",
            "seg_id": "str, 실행 내 표시용 일련번호. ★불변이 아니다. 노딩 규칙이 바뀌면 번호가 전부 밀린다. 외부 참조 금지",
            "width_min_m": "float|null 노면폭(하한). 트랜섹트 최솟값",
            "width_src": "null|ngii|silpok 채택된 폭 소스 (결정 63/64)",
            "width_disagree_m": "float|null 두 폭 소스의 차이. 실측 우선순위",
            "road_name": "str|null 도로명. 겹침길이 최대 매칭",
            # ★ 2026-08-23 추가. seg_label 은 2026-08-21 에 만들고 08-22 에
            #   툴팁 정본으로 승격시켰는데 스키마에 없었다(R7 위반).
            #   화면이 쓰는 값이 계약에 없으면 UI 를 새로 짜는 사람이 못 찾는다.
            "seg_label": "str|null 구간 라벨. 도로명 + 도로명주소법 기초번호 "
                         "(예: 필문대로205번길 11-17). road_intrvl 이 정본이고 "
                         "기초구간을 못 찾으면 도로명만, 도로명도 없으면 null. "
                         "★ 화면 표기는 이것을 쓴다 — seg_no 는 정렬 순번이라 "
                         "노딩이 바뀌면 밀리고 seg_uid 는 사람이 읽을 정보가 없다",
            "z": "float|null 표고(m). ★ 선택 컬럼 — terrain 단계 산출물이라 "
                 "DEM 없이 돌리면 아예 생기지 않는다. 표현용이며 판정에 쓰지 않는다",
            "road_side": "0=주도로 1=부속(측도). 같은 도로명이라도 폭이 다르다",
            "road_bt_m": "float|null 도로대장 명목폭. 참고용. 판정에는 쓰지 않는다",
            "in_emd": "bool 동명동 안인가. false 는 접근 회랑",
            "light_count": "int|null 반경 50m 가로등 수. 지번 단위 집계라 근사다",
            "width_max_m": "float|null 담~담(상한). building 트랜섹트. 대로는 null(건물이 40m 밖)",
            "verdict": "clear|needs_cv|blocked|unknown",
            "width_verified": "bool",
            "midpoint_fallback": "bool 교차로 제외로 샘플 0 → 중점 측정",
            "inherited": "bool 사용하지 않는다. 항상 false",
            "merged_n": "★ processed 전용(web 미발행) int 이 산출단위가 묶은 그래프 엣지 수. 1 이면 병합 없음",
            "cov_ngii1k": "★ processed 전용(web 미발행) float|null 정규표본 중 1:1,000 이 값을 낸 비율",
            "cov_ngii": "★ processed 전용(web 미발행) float|null 정규표본 중 1:5,000 이 값을 낸 비율",
            "cov_silpok": "★ processed 전용(web 미발행) float|null 정규표본 중 실폭도로가 값을 낸 비율",
            "n_sample": "int 정규표본 수(교차로 제외 후). verdict 가 이것을 본다",
            "n_try": "int 시도한 표본 수. n_sample/n_try 가 곧 커버율이다",
            "width_cov": "float|null 채택 소스가 이 구간 표본을 덮은 비율. "
                         "1 미만이면 못 잰 구간이 있다. D-25 실측 우선순위",
            "merge_why": "★ processed 전용(web 미발행) str|null 병합을 유발한 최초 폭 미산출 사유",
            "route_usage": "int 안전센터 2곳 → 건물출입구 최단경로 사용횟수",
            "length_m": "float 이 구간의 수평거리(m). 경사 보정 전이다. 동명동 평균경사 1.8도 기준 실주행거리는 약 0.05% 길고 최대 9도 구간에서 1.2% 길다. 보정에는 5m DEM 이 필요하다",
            "run_length_m": "float|null 같은 판정이 이어지는 연속 구간장(m)",
            "nfa_designated": "bool 소방청 지정 기준(연속 100m 이상) 충족",
            "cctv_dist_m": "float 가장 가까운 CCTV 까지의 거리(m)",
            "cv_feasible": "bool CCTV 유효범위(25m) 안. 영상판정 성립 여부",
            # ★ 2026-08-23 정정. 08-22 에 no_cctv 를 넷으로 쪼갰는데 스키마는
            #   옛 어휘를 그대로 적고 있었다(R7 위반). UI 가 이 표를 보고
            #   분기하면 없는 키로 분기한다 — web/config.js 의 reason 표는
            #   이미 넷을 갖고 있어 화면은 멀쩡했고, 그래서 아무도 몰랐다.
            "unknown_reason": ("null|no_cctv_narrow|no_cctv_thin|no_cctv_band"
                               "|no_cctv_single|width — 회색(unknown)이 된 이유. "
                               "narrow=노면·대장폭 둘 다 3m 미만이나 담~담은 여유 있음 / "
                               "thin=노면만 3m 미만(근거 하나) / "
                               "band=3~7m 대역, 주정차로 갈림 / "
                               "single=7m 이상이나 정규표본 1개라 clear 보류 / "
                               "width=폭 산출 불가(현재 0건)")},
        "standard": "소방청 2025 화재현장 골든타임 확보 종합대책 (구간 100m) + 2026-08-06 현장 답사 (통과 하한 3.0m)",
        "params": {"truck_width_m": TRUCK, "park_occupancy_m": PARK, "nfa_run_m": NFA_RUN_M, "cctv_range_m": CCTV_RANGE,
                   "intersection_exclusion_m": XSEC_EXCL, "wmax_cap_m": WMAX_CAP,
                   "min_seg_len_m": MIN_SEG_LEN, "snap_tol_m": SNAP_TOL},
        "verdict_rule": list(VERDICT_RULE),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(g.verdict.value_counts().to_string())
    print(f"\n→ segments {len(g)} · 경로사용 {(g.route_usage>0).sum()} · sha {h[:16]}")
