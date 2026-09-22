#!/usr/bin/env python3
"""
publish_context.py — 경로 **주변 사정**과 **출동 이력**을 낸다. 판정에는 안 쓴다.

IN    data/processed/speedbump.csv · speed_cam.csv
      data/processed/child_zone_std_5186.gpkg · senior_zone_std_5186.gpkg
      data/processed/nfa_dispatch_119.csv · nfa_rescue.csv · nfa_fire_incident.csv
      data/processed/fire_station.geojson (센터 좌표 — 직선 환산 속도)
      web/data/view.json (maxBounds — 자르는 틀)
OUT   web/data/context.geojson · web/data/history.geojson
PARAM 좌표 자릿수 PREC · 크기 상한 SIZE_MAX

── 왜 생겼나 (2026-09-22 · DECISIONS §216-3) ─────────────────────
받은 72종 중 판정에 들어가는 것이 11종이고, 좌표까지 있는데 **아무도 안 읽는** 것이
여럿이었다 — 과속방지턱 342 · 단속카메라 510 · 어린이 · 노인보호구역 · 119 신고 183 ·
구조 212. 사용자 물음 「받은 데이터 다 제대로 활용 중이냐」 에 「아니다」 가 답이었다.

  context.geojson   내비가 경로 위에서 알려 줄 것 — 과속방지턱 · 단속카메라 · 보호구역 시설
  history.geojson   관제가 볼 것 — 신고 · 구조 지점과 **실제 출동→현장 도착 시간**

★ 판정과 무관하다. 폭도 색도 안 바꾼다. golden 지문 밖이다.
★ 보호구역은 **시설 점**이다. 표준데이터에 구역 선형이 없다 — 지정 범위(시설 기준 최대
  300m)를 구역으로 그리지 않는다. 화면 · 음성은 「보호구역 시설 부근」 이라고 말한다.
★ 출동 시간은 **현장 도착 − 출동 지령**이다(초). 신고→지령(접수 처리)은 뺀다 — 내비가
  줄일 수 있는 것은 주행이다. 끝값이 비었거나 음수 · 2시간 초과는 버린다(기록 오류).
★ 화재 현황은 좌표가 없다(동구 단위). 지점으로 안 그리고 요약 수치에만 넣는다.
★ 결정적이어야 한다 — `커밋된 web/data 가 최신인가` 가 재실행과 바이트 대조를 한다.
"""
from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timedelta, timezone

import geopandas as gpd
import pandas as pd

from firelane.paths import ROOT

P = ROOT / "data" / "processed"
W = ROOT / "web" / "data"

PREC = 6
SIZE_MAX = 512 * 1024
MAX_RESP_S = 2 * 3600
#: 소방청 자료의 시각은 한국 표준시다. 차이만 쓰지만 시간대를 명시한다(엄격 린트 DTZ007)
KST = timezone(timedelta(hours=9))


def _frame() -> tuple[float, float, float, float]:
    v = json.loads((W / "view.json").read_text(encoding="utf-8"))
    (x0, y0), (x1, y1) = v["maxBounds"]
    return x0, y0, x1, y1


def _inside(lon, lat, fr) -> bool:
    return fr[0] <= lon <= fr[2] and fr[1] <= lat <= fr[3]


def _pt(lon: float, lat: float, props: dict) -> dict:
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Point", "coordinates": [round(float(lon), PREC), round(float(lat), PREC)]}}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _ts(v) -> datetime | None:
    """14자리 yyyymmddHHMMSS. 소수점 · 빈값을 견딘다."""
    f = _num(v)
    if f is None:
        return None
    try:
        return datetime.strptime(f"{int(f):014d}", "%Y%m%d%H%M%S").replace(tzinfo=KST)
    except ValueError:
        return None


def _ymdhm(ymd, hm) -> datetime | None:
    """구조 현황의 나뉜 칸 — YMD(8) + TM(HHMMSS)."""
    a, b = _num(ymd), _num(hm)
    if a is None or b is None:
        return None
    try:
        return datetime.strptime(f"{int(a):08d}{int(b):06d}", "%Y%m%d%H%M%S").replace(tzinfo=KST)
    except ValueError:
        return None


def _resp(dispatch: datetime | None, arrive: datetime | None) -> int | None:
    if not dispatch or not arrive:
        return None
    s = (arrive - dispatch).total_seconds()
    return int(s) if 0 < s <= MAX_RESP_S else None


def context(fr) -> dict:
    feats = []
    sb = pd.read_csv(P / "speedbump.csv", dtype=str)
    for r in sb.itertuples(index=False):
        lon, lat = _num(r.WGS84경도), _num(r.WGS84위도)
        if lon and lat and _inside(lon, lat, fr):
            feats.append(_pt(lon, lat, {"kind": "speedbump",
                                        "h_m": _num(r.과속방지턱높이), "road": r.도로명 or None}))
    sc = pd.read_csv(P / "speed_cam.csv", dtype=str)
    for r in sc.itertuples(index=False):
        lon, lat = _num(r.경도), _num(r.위도)
        if lon and lat and _inside(lon, lat, fr):
            feats.append(_pt(lon, lat, {"kind": "speedcam", "limit": _num(r.제한속도),
                                        "place": r.설치장소 or None}))
    for key, kind in (("child_zone_std", "child_zone"), ("senior_zone_std", "senior_zone")):
        g = gpd.read_file(P / f"{key}_5186.gpkg").to_crs(4326)
        for _, r in g.iterrows():
            p = r.geometry
            if p is not None and _inside(p.x, p.y, fr):
                feats.append(_pt(p.x, p.y, {"kind": kind, "name": r.get("대상시설명") or None}))
    feats.sort(key=lambda f: (f["properties"]["kind"], f["geometry"]["coordinates"]))
    return {"type": "FeatureCollection", "name": "context", "features": feats}


def history(fr) -> dict:
    feats, by_center, fires = [], {}, []
    d = pd.read_csv(P / "nfa_dispatch_119.csv", dtype=str)
    for r in d.itertuples(index=False):
        lon, lat = _num(r.DCLR_PSTN_LOT), _num(r.DCLR_PSTN_LAT)
        rs = _resp(_ts(r.DSPT_DRTV_DT), _ts(r.GRNDS_ARVL_DT))
        if lon and lat and _inside(lon, lat, fr):
            feats.append(_pt(lon, lat, {"kind": "dispatch", "yr": int(_num(r.DCLR_YR) or 0),
                                        "center": r.CNTR_NM or None, "resp_s": rs}))
            if rs is not None and r.CNTR_NM:
                by_center.setdefault(r.CNTR_NM, []).append(rs)
    q = pd.read_csv(P / "nfa_rescue.csv", dtype=str)
    for r in q.itertuples(index=False):
        lon, lat = _num(r.DCLR_PSTN_LOT), _num(r.DCLR_PSTN_LAT)
        rs = _resp(_ymdhm(r.DSPT_YMD, r.DSPT_TM), _ymdhm(r.GRNDS_ARVL_YMD, r.GRNDS_ARVL_TM))
        if lon and lat and _inside(lon, lat, fr):
            feats.append(_pt(lon, lat, {"kind": "rescue", "yr": int(_num(r.DCLR_YR) or 0),
                                        "center": r.CNTR_NM or None, "resp_s": rs,
                                        "place": r.ACDNT_PLC_DTL_NM or None}))
            if rs is not None and r.CNTR_NM:
                by_center.setdefault(r.CNTR_NM, []).append(rs)
    f = pd.read_csv(P / "nfa_fire_incident.csv", dtype=str)
    for r in f.itertuples(index=False):
        rs = _resp(_ts(r.DSPT_DT), _ts(r.GRNDS_ARVL_DT))
        if rs is not None:
            fires.append(rs)
    feats.sort(key=lambda x: (x["properties"]["kind"], x["properties"]["yr"], x["geometry"]["coordinates"]))

    # ★ 센터 좌표가 있는 곳은 **직선 환산 속도**를 낸다(직선거리 ÷ 도착 시간). 도로 거리는
    #   직선보다 길므로 실제 주행 속도의 **하한**이다. 내비의 속도표(`domain/speed.ts` ·
    #   20~50km/h · 미검증)를 대 볼 첫 실측이다(§216-3).
    st = gpd.read_file(P / "fire_station.geojson")
    home = {}
    for _, r in st.iterrows():
        nm = str(r.get("소방서 및 안전센터명") or "")
        for c in by_center:
            core = c.replace("119안전센터", "").replace("119구조대", "")
            if core and f"-{core}-" in nm:
                home[c] = r.geometry

    def kmh(c):
        h = home.get(c)
        if h is None:
            return None
        v = []
        for x in feats:
            pr = x["properties"]
            if pr["center"] != c or pr["resp_s"] is None:
                continue
            lon, lat = x["geometry"]["coordinates"]
            dx = (lon - h.x) * 111_320 * math.cos(math.radians(lat))
            dy = (lat - h.y) * 110_540
            v.append(math.hypot(dx, dy) / pr["resp_s"] * 3.6)
        return round(statistics.median(v), 1) if v else None

    def med(xs):
        return int(statistics.median(xs)) if xs else None

    all_rs = [x["properties"]["resp_s"] for x in feats if x["properties"]["resp_s"] is not None]
    summary = {
        "points": len(feats),
        "resp_median_s": med(all_rs), "resp_n": len(all_rs),
        "resp_p90_s": int(sorted(all_rs)[int(0.9 * (len(all_rs) - 1))]) if all_rs else None,
        "by_center": {k: {"n": len(v), "median_s": med(v), "straight_kmh": kmh(k)}
                      for k, v in sorted(by_center.items())},
        "fire_donggu": {"n": len(fires), "median_s": med(fires)},
        "note": "현장 도착 − 출동 지령(초). 신고 · 구조는 동명동 지점, 화재는 동구 전체 요약(좌표 없음)",
    }
    return {"type": "FeatureCollection", "name": "history", "summary": summary, "features": feats}


def main() -> None:
    fr = _frame()
    total = 0
    for name, fc in (("context", context(fr)), ("history", history(fr))):
        txt = json.dumps(fc, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        total += len(txt.encode())
        (W / f"{name}.geojson").write_text(txt, encoding="utf-8")
        kinds = {}
        for x in fc["features"]:
            kinds[x["properties"]["kind"]] = kinds.get(x["properties"]["kind"], 0) + 1
        print(f"  {name}.geojson  {' · '.join(f'{k} {n}' for k, n in sorted(kinds.items()))}"
              f" · {len(txt.encode()) / 1024:.0f}KB")
    if total > SIZE_MAX:
        raise SystemExit(f"★ 주변 사정 · 이력이 {total / 1024:.0f}KB — 상한 {SIZE_MAX / 1024:.0f}KB")


if __name__ == "__main__":
    main()
