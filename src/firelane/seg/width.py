#!/usr/bin/env python3
"""
seg/width.py — 구간 폭 산출.

이 파일이 `ngii1k 1014 · silpok 84 · ngii 1` 을 만든다. 소스 우선순위(결정 63),
표본 snap, 커버율 자격(COV_MIN), 교차부 제외까지 폭에 관한 판단이 전부 여기 있다.

2026-08-18 Stage 3 에서 `segments.py` 의 `main()` 밖으로 꺼냈다. `measure`(178줄)
와 `widths`(158줄)가 폭 소스 3종 + 건물 + 교차부 5개를 폐포로 잡고 있었고,
그 다섯은 항상 같이 움직인다 — 인자로 흩뿌릴 것이 아니라 하나의 상태다.

로직은 한 글자도 바꾸지 않았다. 폐포 참조를 `self.` 로 바꾼 것이 전부이며,
`tools/golden.py` 로 산출물 동일(1101 · sha 846422a86f541bf1)을 증명한다.

── 왜 클래스인가 ──────────────────────────────────────────────
`measure(s, t)` 를 순수 함수로 만들면 매 호출마다 폴리곤 유니온 5개를 넘겨야
한다. 구간당 표본이 수십 개고 구간이 1,176개다. 상태는 실행 내내 불변이므로
한 번 묶어 두는 편이 읽기도 낫고 실수도 적다.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

from firelane.seg.params import (
    _DBG, COV_MIN, MIN_SEG_LEN, MIX_SRC, OLD_SNAP, SNAP_MAX, SNAP_TRUST,
    WMAX_CAP, XSEC_EXCL,
)


class WidthEngine:
    """폭 산출에 필요한 공간 소스를 한 묶음으로 들고 다닌다.

    ngii1k_u  1:1,000 도로경계면.  주 소스(결정 63)
    ngii_u    1:5,000 도로경계면.  2순위
    rw_u      실폭도로.            3순위(silpok)
    bld_u     건물.                담~담(wmax) 측정용
    xn        교차 노드 점집합.     XSEC_EXCL 폴백용
    xsec_poly 평면교차점 실형상.    있으면 이쪽이 우선
    """

    def __init__(self, ngii1k_u, ngii_u, rw_u, bld_u, xn, xsec_poly):
        self.ngii1k_u = ngii1k_u
        self.ngii_u = ngii_u
        self.rw_u = rw_u
        self.bld_u = bld_u
        self.xn = xn
        self.xsec_poly = xsec_poly

    def measure(self, s, t):
        p0 = s.interpolate(t)
        a, b = s.interpolate(max(t-.5, 0)), s.interpolate(min(t+.5, s.length))
        dx, dy = b.x-a.x, b.y-a.y; L = np.hypot(dx, dy)
        if L == 0:
            return None, None, None, (None, None, None), "L0", {}
        ux, uy = -dy/L, dx/L

        def _pt_for(u):
            """이 소스 기준으로 잴 지점. 소스마다 독립으로 판정한다.

            종전에는 세 소스 중 하나라도 p 를 덮으면 snap 을 통째로 건너뛰었다.
            실폭도로의 1.8m 조각이 p 를 덮고 있으면 주 소스인 1:1,000 이
            p 를 안 덮어도 아무 조치가 없었고, 그 소스는 no_run 으로 조용히
            빠졌다(한 구간 30표본 중 20표본). 결정 63 의 주 소스가 무력화된다.

            중심선이 노면 밖이면 법선이 도로면과 안 만나 폭이 안 나온다.
            도로명주소 중심선은 위상용이라 실측 노면과 어긋난다.
            재는 지점만 가장 가까운 노면 안으로 끌어온다(최대 SNAP_MAX).
            """
            if u is None or u.is_empty:
                return None, None
            if u.covers(p0):
                return p0, 0.0
            d = u.distance(p0)
            if d > SNAP_MAX:
                return None, None
            q = nearest_points(u, p0)[0]
            if d > 1e-9:
                # 경계선 위가 아니라 노면 안쪽으로 들여놔야 한다.
                # interpolate(length+0.2) 는 shapely 가 끝점으로 잘라 경계에 얹히고,
                # 거기서 법선을 그으면 접선이 되어 폭이 안 나온다. 방향벡터로 민다.
                _ux2, _uy2 = (q.x - p0.x) / d, (q.y - p0.y) / d
                for _push in (0.3, 0.8, 1.5):
                    _c = Point(q.x + _ux2 * _push, q.y + _uy2 * _push)
                    if u.covers(_c):
                        return _c, round(d, 2)
            return q, round(d, 2)

        def _span(poly_u, p):
            """법선을 도로면으로 자른 조각들을 이어붙이고 좌우 거리를 잰다.

            실폭도로 폴리곤은 도로 중심선을 따라 좌/우로 쪼개져 있고
            그 경계에 십수 cm 짜리 틈이 남는다(중앙로 실측 0.081m).
            폴리곤을 buffer 로 부풀려 닫으려 하면 좁은 골목이 뭉개지므로
            법선 위에서 좌표로만 이어붙인다. 폭 자체는 손대지 않는다.

            교차로에서는 법선이 교차하는 길을 따라 빠져나가 한쪽이 수십 m 가
            된다. 그 표본은 폭이 아니므로 버린다.
            """
            r = LineString([(p.x-ux*60, p.y-uy*60), (p.x+ux*60, p.y+uy*60)])
            sg = r.intersection(poly_u)
            if sg.is_empty:
                return None, "empty"          # 법선이 이 소스와 아예 안 만난다
            # 교차 결과는 LineString 만이 아니다. 법선이 폴리곤 모서리를 스치면
            # Point 가, 여러 형태가 섞이면 GeometryCollection 이 나온다.
            # geoms 접근을 무조건 하면 Point 에서 AttributeError 로 죽는다.
            if sg.geom_type == "LineString":
                pcs = [sg]
            elif hasattr(sg, "geoms"):
                pcs = [q for q in sg.geoms if q.geom_type == "LineString"]
            else:
                return None, "tangent"        # 점 교차. 법선이 경계에 접함
            if not pcs:
                return None, "tangent"

            # 각 조각을 법선 방향 1차원 구간으로 바꾼다. p 가 원점.
            iv = []
            for q in pcs:
                c = list(q.coords)
                ss = [(x - p.x) * ux + (y - p.y) * uy for x, y in c]
                iv.append((min(ss), max(ss)))
            iv.sort()

            # 0.5m 이내로 벌어진 구간은 같은 노면으로 본다(폴리곤 분할 틈).
            merged = [list(iv[0])]
            for lo, hi in iv[1:]:
                if lo - merged[-1][1] <= 0.5:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])

            run = next((m for m in merged if m[0] <= 0.0 <= m[1]), None)
            if run is None:
                return None, "no_run"         # p 가 이 폴리곤 밖 (snap 실패)
            left, right = -run[0], run[1]
            if left > WMAX_CAP or right > WMAX_CAP:   # 교차로에서 길을 따라 나갔다
                return None, "cap"
            v = left + right
            if not (0.3 < v < WMAX_CAP):
                return None, "range"          # 0.3m 이하 조각
            return v, None

        # ── 측정 지점 결정 ──────────────────────────────────
        _srcs3 = ((self.ngii1k_u, "ngii1k"), (self.ngii_u, "ngii"), (self.rw_u, "silpok"))
        if OLD_SNAP:
            # 종전 방식. 소스 하나라도 덮으면 snap 없음, 아니면 최근접 하나로 전부 이동.
            _live = [u for u, _ in _srcs3 if u is not None and not u.is_empty]
            _pp = p0
            if _live and not any(u.covers(p0) for u in _live):
                _near = min(_live, key=lambda u: u.distance(p0))
                _d = _near.distance(p0)
                if _d <= SNAP_MAX:
                    _q = nearest_points(_near, p0)[0]
                    _pp = _q
                    if _d > 1e-9:
                        _u2, _v2 = (_q.x-p0.x)/_d, (_q.y-p0.y)/_d
                        for _push in (0.3, 0.8, 1.5):
                            _c = Point(_q.x+_u2*_push, _q.y+_v2*_push)
                            if _near.covers(_c):
                                _pp = _c
                                break
            _pts = {nm: (_pp, 0.0) for _, nm in _srcs3}
        else:
            _pts = {nm: _pt_for(u) for u, nm in _srcs3}

        res = {}
        for u, nm in _srcs3:
            pt, sn = _pts[nm][0], _pts[nm][1]
            if u is None or u.is_empty:
                res[nm] = (None, "absent", None, None); continue
            if pt is None:
                res[nm] = (None, "far", None, None); continue
            v, c = _span(u, pt)
            # 자기일관성 검사. 폭 v 인 도로에 속한 점이라면 그 밖으로 벗어난
            # 거리가 반폭을 넘을 수 없다. 4.3m 를 밀어 넣어 1.26m 폭을 쟀다면
            # 원래 점은 그 조각 바깥 4.3m 에 있었던 것이고 1.26m 도로의 점일 수
            # 없다. 다른 폴리곤 조각에 억지로 들어가 그 조각의 좁은 데를 잰 것이다.
            # 45.9m 구간이 이런 표본 하나로 1.26m 판정을 받고 있었다.
            # 측정값 자신으로 검증하므로 임계값을 새로 만들지 않는다.
            if (not OLD_SNAP) and v is not None and sn is not None and sn > v / 2.0:
                v, c = None, f"snap{sn:.1f}>w/2"
            res[nm] = (v, c, pt, sn)

        # 세 소스를 다 재고 신뢰도 순으로 채택한다. 좁은 쪽을 고르지 않는다.
        # 실폭도로는 실측 11.8m 인 동계천로에 1.30m 짜리 측구 조각을 그려 놓았고
        # min() 은 그것을 무조건 채택했다. 틀린 값은 보수적인 게 아니라 틀린 것이다.
        A, src, P = None, None, p0
        for nm in ("ngii1k", "ngii", "silpok"):
            if res[nm][0] is not None:
                A, src, P = res[nm][0], nm, res[nm][2]
                break

        # 담~담(상한)은 폭을 채택한 지점과 같은 곳에서 잰다. 다른 지점에서 재면
        # wmin 과 wmax 가 서로 다른 단면을 기술하게 된다.
        rb = LineString([(P.x-ux*60, P.y-uy*60), (P.x+ux*60, P.y+uy*60)])
        B = None
        sg = rb.intersection(self.bld_u)                    # 담~담 = 상한
        if not sg.is_empty:
            if sg.geom_type == "LineString":
                pr = [sg]
            elif hasattr(sg, "geoms"):
                pr = [q for q in sg.geoms if q.geom_type == "LineString"]
            else:
                pr = []
            s1 = min((q.distance(P) for q in pr
                      if (q.centroid.x-P.x)*ux + (q.centroid.y-P.y)*uy < 0), default=None)
            s2 = min((q.distance(P) for q in pr
                      if (q.centroid.x-P.x)*ux + (q.centroid.y-P.y)*uy > 0), default=None)
            if s1 is not None and s2 is not None and 0.3 < s1+s2 < WMAX_CAP:
                B = s1 + s2
        # 벽 사이 폭은 도로 폭보다 좁을 수 없다. 상한(WMAX_CAP)에 걸려 잘린 경우
        # 역전이 생기므로 도로 폭으로 끌어올린다.
        if A is not None and B is not None and B < A:
            B = A

        a_1k, a_ngii, a_rw = res["ngii1k"][0], res["ngii"][0], res["silpok"][0]
        if _DBG["on"]:
            print("      " + "  ".join(
                f"{nm}={res[nm][0] if res[nm][0] is not None else res[nm][1]}"
                f"(snap{res[nm][3] if res[nm][3] is not None else '-'})"
                for nm in ("ngii1k", "ngii", "silpok"))
                + f" → A={A} src={src} B={B}")
        why = None
        if A is None:
            why = "|".join(f"{k}:{res[n][1]}" for k, n in
                           (("1k", "ngii1k"), ("ng", "ngii"), ("rw", "silpok")))
        return A, B, src, (a_1k, a_ngii, a_rw), why, res

    def widths(self, s):
        A, B, fb = [], [], False
        S, D = [], []
        # 교차로 파편(길이 < MIN_SEG_LEN)은 정의상 전 구간이 교차로 안이다.
        # XSEC_EXCL 을 그대로 적용하면 표본이 0 개가 되어 폭이 안 나온다.
        # 짧은 조각은 교차로 제외를 풀고 중점 한 점이라도 잰다.
        _short = s.length < MIN_SEG_LEN
        _lo = min(1.0, s.length*0.25)
        _ts = list(np.arange(_lo, max(s.length-_lo, s.length*0.5+1e-9), 2.0))
        if not _ts:
            _ts = [s.length/2]
        _nc, _nx_skip, _whys = 0, 0, []
        _cov = {"ngii1k": 0, "ngii": 0, "silpok": 0}
        _by  = {"ngii1k": [], "ngii": [], "silpok": []}
        _n_try = 0

        def _covr():
            """소스별 커버율. 정규 표본 중 그 소스가 값을 낸 비율.

            표본마다 다른 소스가 채택되면 wmin=min(A) 이 소스 혼합 집합에서
            최솟값을 뽑는다. 소스 축에서 폐기한 min() 이 표본 축으로 부활한 것이다.
            구간 단위 채택으로 바꾸기 위한 관측값이다. (STEP 5-1)
            """
            return ({k: (round(v/_n_try, 3) if _n_try else None)
                     for k, v in _cov.items()}, _n_try)
        for t in _ts:
            _nc += 1
            _pt = s.interpolate(t)
            if self.xsec_poly is not None:
                # ★ 폴리곤이 근처에 있으면 폴리곤만 믿는다.
                #   or 로 반경 폴백을 항상 같이 걸면 폴리곤이 무의미해진다.
                #   작은 교차부(등가반경 중앙 3.2m)는 여전히 5m 씩 도려내지고,
                #   큰 교차부(p90 7.5m)는 폴리곤 밖 오염이 그대로 남는다.
                #   폴리곤이 아예 없는 교차로에서만 반경으로 폴백한다.
                if self.xsec_poly.distance(_pt) < XSEC_EXCL * 2:
                    _inx = self.xsec_poly.intersects(_pt)
                else:
                    _inx = self.xn.distance(_pt) < XSEC_EXCL
            else:
                _inx = self.xn.distance(_pt) < XSEC_EXCL
            # ★ 짧은 조각도 교차부 폴리곤 안이면 제외한다.
            #   종전에는 _short 면 교차부 제외를 통째로 건너뛰고 중점 한 점을
            #   쟀는데, 그 한 점이 교차로 한복판이라 길이 1m 조각에서 55m 가
            #   나왔다. 표본 0 을 피하려다 쓰레기 값을 만든 것이다.
            #   MIN_SEG_LEN 주석이 이미 '폭 미산출 후 인접 상속'이라고 적고 있다.
            #   상속 경로가 원래 설계에 있는데 억지 값 때문에 안 쓰이고 있었다.
            #   교차부 폴리곤이 없을 때만 종전 동작(짧으면 재기)을 유지한다.
            _skip = _inx if (self.xsec_poly is not None and not _short) else _inx
            if _short and self.xsec_poly is not None:
                _skip = self.xsec_poly.intersects(_pt)
            elif _short:
                _skip = False
            if _skip:
                _nx_skip += 1
                if _DBG["on"]:
                    _how = "폴리곤" if (self.xsec_poly is not None
                                       and self.xsec_poly.intersects(_pt)) else "반경"
                    print(f"    t={t:7.1f}  교차로 {self.xn.distance(_pt):.1f}m ({_how}) — 제외")
                continue
            if _DBG["on"]:
                _pp = s.interpolate(t)
                print(f"    t={t:7.1f}  ({_pp.x:.1f},{_pp.y:.1f})")
            a, b, sc, pr, _why, _res = self.measure(s, t)
            _n_try += 1

            def _trusted(_nm):
                """이 지점에서 그 소스의 표본을 믿을 수 있는가."""
                _r = _res.get(_nm)
                if _r is None or _r[0] is None:
                    return False
                _sn = _r[3]
                return _sn is None or _sn <= SNAP_TRUST

            for _nm in ("ngii1k", "ngii", "silpok"):
                if _trusted(_nm):
                    _cov[_nm] += 1
            if _why: _whys.append(_why)
            # 채택된 소스의 snap 이 크면 그 표본 자체를 버린다.
            if a and (sc is None or _trusted(sc)):
                A.append(a); S.append(sc); D.append(pr)
            for _nm, _vv in zip(("ngii1k", "ngii", "silpok"), pr):
                if _vv is not None and _trusted(_nm):
                    _by[_nm].append(_vv)
            if b: B.append(b)
        if A:
            _rsn = None
        elif _nc == 0:
            _rsn = "ts_empty"
        elif _nx_skip == _nc:
            _rsn = "all_xsec"            # 표본 전부 교차로 5m 안. 잰 적이 없다
        else:
            _rsn = Counter(_whys).most_common(1)[0][0] if _whys else "unknown"
        # 폴백을 두지 않는다. 정규 샘플(2m 간격)로 한 점도 안 잡히면
        # 중심선이 도로면을 벗어난 것이고, 그때 억지로 낸 값은 근거가 없다.
        # 33m·63m 구간이 표본 1개로 1.3m 판정을 받고 있었다.
        _n_reg = len(A)

        # ── 구간 단위 소스 채택 (STEP 5-1) ──────────────────
        # 종전에는 wmin = min(A) 였는데 A 는 표본마다 다른 소스가 채택된
        # 혼합 집합이다. 표본1 은 1:1,000 의 3.2m, 표본2 는 실폭도로의 1.8m
        # 인데 그 둘의 최솟값을 구간 폭이라고 불렀다. 소스 축에서 폐기한
        # min() 이 표본 축에 그대로 남아 있었던 것이다(1k 부분커버 302 구간).
        #
        # 값을 낸 최우선 소스 하나로 고정하고 그 소스의 표본만으로 최솟값을 낸다.
        # 커버율이 높은 소스를 고르지 않는다 — 실폭도로가 0.955 로 가장 높은데
        # 그것을 채택하면 결정 63(수치지도 주 소스)을 정면으로 뒤집는다.
        # 부분커버 구간은 그 소스가 못 잰 구간을 모르는 채로 판정하는 것이므로
        # width_cov 로 노출해 D-25 실측 우선순위에 쓴다.
        _pick = None
        if not MIX_SRC:
            # 커버율은 소스를 '고르는' 기준이 아니라 '자격'이다.
            # 커버율로 고르면 실폭도로(0.955)가 항상 이겨 결정 63 이 뒤집힌다.
            _covnow = _covr()[0]
            for _nm in ("ngii1k", "ngii", "silpok"):
                if not _by[_nm]:
                    continue
                _cv = _covnow.get(_nm)
                if _cv is not None and _cv < COV_MIN and _n_reg >= 3:
                    continue          # 자격 미달. 다음 순위로 넘긴다
                _pick = _nm
                break
            # 전부 자격 미달이면 우선순위대로 하나는 쓴다(폭을 못 내는 것보다 낫다).
            if _pick is None:
                for _nm in ("ngii1k", "ngii", "silpok"):
                    if _by[_nm]:
                        _pick = _nm
                        break
        wmin = None
        if _pick is not None:
            wmin = round(min(_by[_pick]), 2)
        elif A:
            wmin = round(min(A), 2)
        wmax = round(min(B), 2) if B else None
        # 벽 사이 폭이 도로 폭보다 좁을 수는 없다. 샘플별로는 맞아도
        # 각각 최솟값을 취하면 역전이 생긴다(대로에서 WMAX_CAP 에 걸린 경우).
        if wmin is not None and wmax is not None and wmax < wmin:
            wmax = wmin
        # 폴백 표본만으로 나온 값은 신뢰할 수 없다. 긴 구간에서 정규 샘플이
        # 하나도 안 잡혔다는 것은 중심선이 도로면을 벗어났다는 뜻이다.
        # 그 값으로 판정하면 대로가 1.4m 로 나간다(DM02856 63m 구간).
        if _n_reg == 0 and s.length >= MIN_SEG_LEN * 2:
            return None, None, True, None, None, _rsn, _covr()

        # 채택된 소스를 기록한다(결정 64). 구간 단위 단일 소스다.
        if _pick is not None:
            wsrc = _pick
            _i = A.index(min(A)) if A else None
        else:
            _i = A.index(min(A)) if A else None
            wsrc = S[_i] if _i is not None else None
        # 두 공공 소스가 같은 지점을 얼마나 다르게 기술하는가.
        # 이 값이 큰 순서가 곧 D-25 실측 우선순위다(§7-2 관측점 선정).
        wdis = None
        if _i is not None:
            _vals = [v for v in D[_i] if v is not None]
            if len(_vals) >= 2:
                wdis = round(max(_vals) - min(_vals), 2)
        return wmin, wmax, fb, wsrc, wdis, _rsn, _covr()
