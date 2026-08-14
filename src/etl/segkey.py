#!/usr/bin/env python3
"""
segkey.py — 실행 간 유지되는 구간 키(seg_uid)와 관측점 국소 방위각(bearing)

    from segkey import make_seg_uid, attach_seg_uid, bearing_at, obs_context

── 왜 필요한가 ────────────────────────────────────────────────
seg_id(DM00082)는 실행마다 번호가 밀린다. 노딩 규칙이 한 번 바뀌면서
1266 → 1087 이 되었을 때 전부 갈렸다. 그래서 실측값·관측점·비전 반환값을
seg_id 에 붙이면 다음 파이프라인 실행에 전부 미아가 된다.

★ segments.py 의 스키마 주석에 seg_id 가 "str, 불변 키" 라고 적혀 있다.
  이건 사실이 아니다(MASTER §5 와 정면으로 어긋난다). seg_uid 를 넣을 때
  그 문구도 같이 고쳐라. 문서와 코드가 어긋난 채로 두면 다음 사람이 속는다.

── 키 형식 ────────────────────────────────────────────────────
증권 티커처럼 고정 폭이라 파싱만으로 정보가 나온다.

    DM-192741-283615-7K3A
    │   │      │      └ road_name 해시 4자리(base36). 같은 좌표 다른 도로 구분
    │   │      └ 중점 Y (EPSG:5186, m 단위 정수, 6자리)
    │   └ 중점 X (EPSG:5186, m 단위 정수, 6자리)
    └ 지역 코드(동명동)

중점을 쓰는 이유: 구간 끝점은 노딩 규칙에 직접 흔들리지만 중점은 덜 흔들린다.
1m 로 반올림하는 이유: 좌표를 그대로 쓰면 소수점 끝자리가 바뀔 때마다 키가 갈린다.

── 한계 ───────────────────────────────────────────────────────
불변이 아니라 "웬만하면 유지되는" 키다. 병합 규칙이 바뀌어 두 구간이 하나로
합쳐지면 중점이 이동해 키가 바뀐다. 그래서 seg_uid_map.csv 로 런 간 겹침
매칭 이력을 남긴다. 유지율이 게이트다(목표 90%).
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

CRS_M = "EPSG:5186"
REGION = "DM"                 # 동명동. 스코프가 넓어지면 여기서 분기한다
COORD_DIGITS = 6              # 5186 광주 일대는 X·Y 모두 6자리다
HASH_LEN = 4
BEARING_SPAN_M = 4.0          # 접선을 잡을 전후 거리(m). ±2m


# ──────────────────────────────────────────────────────────────
# seg_uid
# ──────────────────────────────────────────────────────────────
def _b36(n: int, width: int) -> str:
    """정수를 base36 고정폭 문자열로. 대문자만 써서 육안 대조가 쉽다."""
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = chars[r] + s
    return s.rjust(width, "0")[-width:]


def _road_hash(road_name: str | None) -> str:
    """
    도로명 해시.

    ★ 도로명만으로 구간을 특정할 수 없다. 필문대로289번길 하나에 세그먼트가
      30개 넘게 달린다. 그래서 좌표가 주 키이고 도로명은 충돌 방지용 보조다.
    ★ None 을 빈 문자열로 접지 않고 별도 토큰을 준다. 도로명이 없는 구간과
      도로명이 "" 인 구간이 같은 키를 받으면 안 된다.
    """
    src = (road_name or "\x00NONAME").strip()
    h = hashlib.blake2s(src.encode("utf-8"), digest_size=4).digest()
    return _b36(int.from_bytes(h, "big"), HASH_LEN)


def make_seg_uid(geom: LineString, road_name: str | None,
                 region: str = REGION) -> str:
    """구간 하나의 seg_uid. geom 은 반드시 CRS_M(미터) 좌표계여야 한다."""
    mid = geom.interpolate(0.5, normalized=True)
    x = int(round(mid.x))
    y = int(round(mid.y))
    if not (10 ** (COORD_DIGITS - 1) <= x < 10 ** COORD_DIGITS):
        # 좌표계를 잘못 넣은 것이다(4326 을 넣으면 여기서 걸린다). 조용히 넘기면
        # 전부 같은 접두사를 받아 키가 무의미해진다.
        raise ValueError(f"seg_uid: X 좌표 자릿수 이상 ({x}). CRS_M 인지 확인")
    return f"{region}-{x:0{COORD_DIGITS}d}-{y:0{COORD_DIGITS}d}-{_road_hash(road_name)}"


def parse_seg_uid(uid: str) -> dict:
    """키를 되돌려 읽는다. 로그에서 좌표만 보고 위치를 짚을 때 쓴다."""
    region, x, y, rh = uid.split("-")
    return {"region": region, "x": int(x), "y": int(y), "road_hash": rh}


def attach_seg_uid(g: gpd.GeoDataFrame, road_col: str = "road_name") -> gpd.GeoDataFrame:
    """
    segments GeoDataFrame 에 seg_uid 컬럼을 붙인다.

    충돌(같은 uid 가 둘 이상)이 나면 중점이 1m 안에 겹치고 도로명도 같은 것이다.
    그런 구간은 애초에 분리돼 있으면 안 되므로 경고를 띄운다. 조용히 접미사를
    붙이면 다음 실행에 접미사 순서가 바뀌어 키가 또 갈린다.
    """
    if g.crs is None or g.crs.to_string() != CRS_M:
        g = g.to_crs(CRS_M)
    g = g.copy()
    g["seg_uid"] = [
        make_seg_uid(geom, rn)
        for geom, rn in zip(g.geometry, g.get(road_col, pd.Series([None] * len(g))))
    ]
    dup = g.seg_uid[g.seg_uid.duplicated(keep=False)]
    if len(dup):
        print(f"  ! seg_uid 충돌 {dup.nunique()}건 / {len(dup)}행 — 병합 규칙 점검 필요")
        print(g[g.seg_uid.isin(dup)][["seg_id", "seg_uid", "road_name", "length_m"]]
              .head(10).to_string(index=False))
    return g


def uid_retention(prev_csv: Path, g: gpd.GeoDataFrame) -> float:
    """
    직전 실행 대비 seg_uid 유지율. 계약 테스트의 게이트다.

    NODE_TOL 을 0.5 → 0.6 으로 흔들었을 때 90% 미만이면 키 규칙을 다시 만든다.
    """
    if not prev_csv.exists():
        return 1.0
    prev = set(pd.read_csv(prev_csv).seg_uid)
    if not prev:
        return 1.0
    return len(prev & set(g.seg_uid)) / len(prev)


def save_uid_map(g: gpd.GeoDataFrame, out_csv: Path) -> None:
    """런 간 대조용 이력. git 에 커밋한다(작다). 유지율 회귀를 눈으로 잡는다."""
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in ("seg_uid", "seg_id", "road_name", "length_m") if c in g.columns]
    g[cols].sort_values("seg_uid").to_csv(out_csv, index=False, encoding="utf-8")


# ──────────────────────────────────────────────────────────────
# bearing
# ──────────────────────────────────────────────────────────────
def bearing_at(geom: LineString, offset_m: float,
               span_m: float = BEARING_SPAN_M) -> float:
    """
    구간 위 offset_m 지점의 국소 방위각(도, 북=0, 시계방향).

    ★ 구간 하나에 방위각 하나를 주면 안 된다.
      굽은 골목은 지점마다 도로가 뻗은 방향이 다르다. 시작점 방향으로 횡단선을
      그으면 끝부분에서 폭이 실제보다 넓게 나온다(비스듬히 자르므로).
      그래서 관측점 단위로 계산한다.

    ★ 새 데이터가 필요 없다. 중심선에서 나오는 값이다.

    span_m: 전후 ±span/2 두 점의 할선을 접선으로 쓴다. 너무 짧으면 좌표
            노이즈를 타고, 너무 길면 커브를 뭉갠다. 4m 가 골목 스케일에 맞다.
    """
    L = geom.length
    half = span_m / 2
    # 끝단에서는 구간 밖으로 나가지 않게 창을 안쪽으로 민다.
    a = max(0.0, min(offset_m - half, L - span_m))
    b = min(L, a + span_m)
    p0, p1 = geom.interpolate(a), geom.interpolate(b)
    dx, dy = p1.x - p0.x, p1.y - p0.y
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(dx, dy)) % 360.0


def offset_of(geom: LineString, pt: Point) -> float:
    """관측점 좌표 → 구간 시점 기준 거리(m). 실측 지점을 구간에 붙일 때 쓴다."""
    return geom.project(pt)


def obs_context(g: gpd.GeoDataFrame, seg_uid: str, offset_m: float) -> dict:
    """
    영상판정 모듈에 내려보낼 관측점 맥락.

    ★ 폭을 넣지 않는다. 넣는 순간 영상이 GIS 값으로 수렴해서 대조가 무의미해진다.
      GIS 폭은 아직 실측 검증이 0건이라 더 위험하다.
      방위각은 폭이 아니므로 순환이 아니다.
    """
    row = g[g.seg_uid == seg_uid]
    if row.empty:
        raise KeyError(f"seg_uid 없음: {seg_uid}")
    geom = row.geometry.iloc[0]
    return {
        "seg_uid": seg_uid,
        "bearing_deg": round(bearing_at(geom, offset_m), 1),
        "length_m": round(float(geom.length), 1),
        "offset_m": round(float(offset_m), 1),
        "road_name": row.road_name.iloc[0] if "road_name" in row else None,
    }


# ──────────────────────────────────────────────────────────────
# segments.py 통합 (아래 두 줄을 g 생성 직후에 넣는다)
#
#   from segkey import attach_seg_uid, uid_retention, save_uid_map
#   g = attach_seg_uid(g)
#   ret = uid_retention(OUT/"seg_uid_map.csv", g); print(f"  seg_uid 유지율 {ret:.1%}")
#   save_uid_map(g, OUT/"seg_uid_map.csv")
#
# publish_web.py 의 _cols 에 "seg_uid" 를 추가한다.
# tests/test_contract.py 에 유일성 + 유지율 90% 게이트를 넣는다.
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 자체 점검. 실제 데이터 없이도 형식이 맞는지 본다.
    ln = LineString([(192740, 283600), (192750, 283640)])
    uid = make_seg_uid(ln, "동명로82번길")
    print(uid, parse_seg_uid(uid))
    for o in (0, 10, 20, 41):
        print(f"  offset {o:>3}m → bearing {bearing_at(ln, o):.1f}°")
