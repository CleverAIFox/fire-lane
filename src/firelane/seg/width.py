#!/usr/bin/env python3
"""
seg/width.py — 구간 폭 산출.

이 파일이 `ngii1k 1162 · silpok 116 · ngii 1` 을 만든다. 소스 우선순위(결정 63),
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
    COV_MIN,
    ESCAPE_M,
    MIN_SEG_LEN,
    RAY_M,
    SNAP_MAX,
    SNAP_TRUST,
    WIDTH_SRCS,
    WMAX_CAP,
    XSEC_EXCL,
)


def walk_spans(ray, walk_u, p, ux, uy):
    """광선이 **보도면과 겹치는** 1차원 구간들. `p` 가 원점이고 `(ux,uy)` 가 +축이다.

    `_span` 이 노면으로 하는 것과 같은 투영이다. 따로 둔 이유는 하나 —
    노면 교차는 「0 을 담은 조각」 하나를 찾고, 보도 교차는 **전부** 필요하다.
    """
    sg = ray.intersection(walk_u)
    if sg.is_empty:
        return []
    if sg.geom_type == "LineString":
        pcs = [sg]
    elif hasattr(sg, "geoms"):
        pcs = [q for q in sg.geoms if q.geom_type == "LineString"]
    else:
        return []                                    # 점 교차. 보도 턱을 스쳤다
    out = []
    for q in pcs:
        ss = [(x - p.x) * ux + (y - p.y) * uy for x, y in q.coords]
        out.append((min(ss), max(ss)))
    return sorted(out)


def _round_pos(x: float, nd: int = 2) -> float:
    """폭을 자리수로 줄이되 **양수를 0 으로 만들지 않는다**(DECISIONS 534-1).

    ★ `round(0.001, 2)` 은 `0.0` 이다. 0 은 이 저장소에서 「좁다」가 아니라
      **「못 쟀다」**의 자리이고(534), `segcontract` 의 `WIDTH_OUT_OF_RANGE`
      가 0 을 불가능한 수로 문다. 그래서 **참인 관문이 거짓을 물었다** —
      `DM01391`(2순환로 539m)의 표본 110개 중 최솟값이 0.001 이었고,
      그 양수가 반올림 한 번에 0 이 됐다.

    ★ 고침은 **하한이 아니다.** 0.001 을 버리지 않는다 — 버리면 입장이
      바뀌고 구간 수가 움직인다(519 · 523 이 같은 자리에서 쓴 사유).
      자리수만 늘려 **잰 것을 잰 대로** 적는다.
    """
    r = round(x, nd)
    return r if r > 0 else round(x, 6)


def carve_walk(left, right, walk_iv):
    """좌우 거리에서 보도를 깎는다. **0 을 담은 조각 하나만** 남는다.

    ★ 2026-10-14 (DECISIONS §523-2). 재는 점이 **보도 위**면 안 깎고 그대로
      돌려준다. 그 표본을 **버리지도 않는다** — §512-1 이 64구간 전부에서
      버림의 효과가 0 임을 쟀고, 효과 없는 가드는 다음 사람이 무엇을 막는지
      모른 채 영영 남는다. 중심선이 보도 위인 것은 중심선의 결함이고
      그 자리는 `PLAN` 이 든다.
    """
    lo, hi = -left, right
    if any(a <= 0.0 <= b for a, b in walk_iv):
        return left, right
    for a, b in walk_iv:
        if b <= 0.0:
            lo = max(lo, b)              # 왼쪽에서 가장 가까운 보도의 **끝**
        elif a >= 0.0:
            hi = min(hi, a)              # 오른쪽에서 가장 가까운 보도의 **시작**
    return -lo, hi


class WidthEngine:
    """폭 산출에 필요한 공간 소스를 한 묶음으로 들고 다닌다.

    ngii1k_u  1:1,000 도로경계면.  주 소스(결정 63)
    ngii_u    1:5,000 도로경계면.  2순위
    rw_u      실폭도로.            3순위(silpok)
    bld_u     건물.                담~담(wmax) 측정용
    xn        교차 노드 점집합.     XSEC_EXCL 폴백용
    xsec_poly 평면교차점 실형상.    있으면 이쪽이 우선
    walk_u    보도면.               노면에서 **깎는다**(§523). 없으면 안 깎는다
    """

    def __init__(self, ngii1k_u, ngii_u, rw_u, bld_u, xn, xsec_poly,
                 *, walk_u=None, mix_src: bool = False, old_snap: bool = False):
        self.ngii1k_u = ngii1k_u
        self.ngii_u = ngii_u
        self.rw_u = rw_u
        self.bld_u = bld_u
        self.xn = xn
        self.xsec_poly = xsec_poly
        # ★ 2026-10-14 (PLAN #146 · DECISIONS §523). 보도면. **기본이 None** 이고
        #   그때는 종전과 글자까지 같은 경로다 — 자료가 없는 기계에서 조용히
        #   다른 수가 나오지 않는다(`segments.py` 가 없으면 운다).
        self.walk_u = walk_u
        # ★ 2026-09-25 (PLAN §1 #121 · #123). 종전에는 셋 다 `seg/params.py` 의
        #   모듈 전역이었고 그 파일이 `.env` 를 읽었다. 이제 **부르는 쪽이 정한다.**
        #   기본은 전부 꺼짐 — 셋 다 「종전 동작으로 되돌리는」 진단 스위치이고,
        #   기본값이 곧 판정 경로다. 값을 안 넘기면 판정 경로로 돈다.
        self.mix_src = mix_src      # 구간 폭을 표본 혼합 집합의 최솟값으로(종전)
        self.old_snap = old_snap    # snap 을 소스별이 아닌 종전 방식으로
        self.debug = False          # 표본 단위 덤프. `segments.main()` 이 켰다 끈다

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
            r = LineString([(p.x-ux*RAY_M, p.y-uy*RAY_M),
                            (p.x+ux*RAY_M, p.y+uy*RAY_M)])
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
            # ★ 2026-10-13 (DECISIONS §519). **값 규칙만 고친다.**
            #   §510 이 이 자리를 한 번 고쳤다가 §516 이 빼냈다. 빼낸 이유는
            #   고침이 **값 규칙과 입장 규칙을 한꺼번에** 바꿨기 때문이다 —
            #   `2·min` 을 `range` 검사에 먹이면 종전에 버려지던 표본
            #   (`l+r ≥ 60`)이 통과하고, 그러면 덮임 → 소스 채택 → 폭 미산출
            #   집합 → 병합 → **구간 수**가 움직인다(실측 1,281 → 1,285).
            #
            #   그래서 **입장은 좌우합이 정한다.** 아래 `range` 검사가 보는
            #   것은 `l+r` 이고 그것이 종전 코드와 **글자까지 같은 조건**이다.
            #   값만 그 뒤에 고른다 — 입장과 값을 **다른 줄**에 둔다.
            #
            #   ★ 죽은 `cap` 분기를 지웠다. `left` 는 광선 길이(`RAY_M`)를
            #     넘을 수 없고 문턱이 `WMAX_CAP` 이라 **둘이 같은 60.0** 이고
            #     그래서 그 조건은 **한 줄도 실행된
            #     적이 없다**(§510 이 그것을 쟀다). 지우는 것이 입장을 안
            #     바꾼다 — 참이 된 적이 없는 조건이다.
            s = left + right
            if not (0.3 < s < WMAX_CAP):
                return None, "range"      # 입장 규칙 — 종전과 같다
            # 한쪽이 광장·교차로로 샜으면 그 쪽은 이 도로의 반폭이 아니다.
            # ★ `2·min ≤ l+r` 이므로 폭은 **올라가지 않는다** — 틀려도
            #   안전한 쪽으로만 틀린다(MASTER §3-5a).
            # ★ `2·min` 이 0.3 이하로 떨어져도 **버리지 않는다.** 버리면
            #   입장이 바뀌고 구간 수가 움직인다. 그 수가 몇인지는 측정 대장
            #   `escape-tiny` 가 든다 — 재기 전에 판정 기준을 적어 뒀다.
            #
            # ★ 2026-10-14 (DECISIONS 534). **그 측정이 났고 0 이 아니었다.**
            #   `DM01391`(2순환로 539m)의 `width_min_m` 이 **0.00** 으로
            #   발행됐고 `segcontract` 의 `WIDTH_OUT_OF_RANGE` 가 0 → 1 로
            #   울었다. 대로가 폭 0 일 수 없다.
            #
            #   **고침은 하한이 아니다.** 측정 대장이 적은 셋째 규칙(「가까운
            #   쪽의 하한」)은 안 세운다 — 그 구간은 `cov 0.408` 이고 2순환로
            #   고가·교차로라 **지오메트리 결함** 쪽이다(대장의 ③ 가 그때
            #   `SNAP_TRUST` 로 보내라고 적어 뒀다).
            #
            #   가르는 것은 **0 과 좁음이 다른 것**이라는 사실이다 —
            #   `0.3` 은 「좁다」고 `0` 은 「못 쟀다」다. 0 을 결측으로 돌리면
            #   입장 규칙을 **안 건드린다**(입장은 깎지 않은 `s` 가 정했고 이미
            #   통과했다). 구간은 남고 그 표본 하나만 빠진다.
            if max(left, right) >= ESCAPE_M:
                v = 2 * min(left, right)
                if v <= 0:
                    return None, "escape_zero"   # 수가 아니라 결측이다
                return v, None
            # ★ 2026-10-14 (DECISIONS §523). **보도 차감.** 세 줄 위의 입장
            #   검사와 바로 위의 escape 검사는 **깎지 않은** 좌우를 본다 —
            #   순서가 규칙이다.
            #
            #   깎고 나서 escape 를 보면 **샌 광선이 안 샌 것처럼 보인다.**
            #   §512-1 ③ 이 그 사고다 — 필문대로289번길은 2m 안에 보도면이
            #   하나도 없는데 차감으로 6.14 → 0.70 이 됐다. 그 구간의 광선은
            #   escape 100% 로 필문대로 **본선**으로 새 나가고, 본선의 보도를
            #   깎으면 샌 쪽이 짧아져 `max(left,right) ≥ ESCAPE_M` 이 **꺼진다.**
            #   그러면 `2·min` 대신 깎인 좌우합이 폭으로 나간다.
            #
            #   그래서 「보도면을 어느 도로의 것인지 귀속한다」를 **광선으로**
            #   가른다(§523-1) — 제 도로에 머문 광선이 만난 보도는 제 것이고,
            #   샌 광선이 만난 보도는 **남의 것이라 안 깎는다.**
            if self.walk_u is not None and not self.walk_u.is_empty:
                left, right = carve_walk(
                    left, right, walk_spans(r, self.walk_u, p, ux, uy))
                # ★ 깎은 합이 0.3 아래로 떨어져도 **버리지 않는다** — 버리면
                #   입장이 바뀌고 구간 수가 움직인다(§519 가 `2·min` 에 쓴 그
                #   사유와 같다). 그 표본 수는 측정 대장 `walk-tiny` 가 든다.
                return left + right, None
            return s, None

        # ── 측정 지점 결정 ──────────────────────────────────
        _srcs3 = tuple(zip((self.ngii1k_u, self.ngii_u, self.rw_u),
                           WIDTH_SRCS, strict=True))
        if self.old_snap:
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
            if (not self.old_snap) and v is not None and sn is not None and sn > v / 2.0:
                v, c = None, f"snap{sn:.1f}>w/2"
            res[nm] = (v, c, pt, sn)

        # 세 소스를 다 재고 신뢰도 순으로 채택한다. 좁은 쪽을 고르지 않는다.
        # 실폭도로는 실측 11.8m 인 동계천로에 1.30m 짜리 측구 조각을 그려 놓았고
        # min() 은 그것을 무조건 채택했다. 틀린 값은 보수적인 게 아니라 틀린 것이다.
        A, src, P = None, None, p0
        for nm in WIDTH_SRCS:
            if res[nm][0] is not None:
                A, src, P = res[nm][0], nm, res[nm][2]
                break

        # 담~담(상한)은 폭을 채택한 지점과 같은 곳에서 잰다. 다른 지점에서 재면
        # wmin 과 wmax 가 서로 다른 단면을 기술하게 된다.
        rb = LineString([(P.x-ux*RAY_M, P.y-uy*RAY_M),
                         (P.x+ux*RAY_M, P.y+uy*RAY_M)])
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

        a_1k, a_ngii, a_rw = (res[nm][0] for nm in WIDTH_SRCS)
        if self.debug:
            print("      " + "  ".join(
                f"{nm}={res[nm][0] if res[nm][0] is not None else res[nm][1]}"
                f"(snap{res[nm][3] if res[nm][3] is not None else '-'})"
                for nm in WIDTH_SRCS)
                + f" → A={A} src={src} B={B}")
        why = None
        if A is None:
            why = "|".join(f"{k}:{res[n][1]}" for k, n in
                           zip(("1k", "ng", "rw"), WIDTH_SRCS, strict=True))
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
        _cov = dict.fromkeys(WIDTH_SRCS, 0)
        _by  = {nm: [] for nm in WIDTH_SRCS}
        _n_try = 0

        # ★ 2026-08-23. 표본을 버리지 않고 남긴다.
        #
        #   지금까지 `widths()` 는 표본 배열을 만들고 `min` 만 뽑아 버렸다.
        #   그래서 `w(s)` 를 **함수로** 다룰 수가 없었다.
        #
        #   `min` 은 최악의 통계량이다 — 표본 하나가 틀리면 판정이 뒤집힌다.
        #   커버율 0.056 구간에서 `wmin 10.51m` 가 나온 것이 그 예다.
        #   함수로 보면 이런 것들이 열린다.
        #
        #       μ{s : w(s) < 3.0}    막힌 **길이**. 이상치 하나에 안 무너진다
        #       opening(L_car)       차 길이만큼 연속으로 이어지는 폭
        #                            소방펌프차 8m — 병목 0.5m 는 노이즈일 수 있다
        #       w(s) 분포            커버율보다 정확한 신뢰도
        #
        #   ★ 판정은 건드리지 않는다. 산출물 컬럼도 안 더한다.
        #     `width_samples.csv` 를 따로 낼 뿐이라 golden 지문이 그대로다.
        _rows = []

        def _covr():
            """소스별 커버율. 정규 표본 중 그 소스가 값을 낸 비율.

            표본마다 다른 소스가 채택되면 wmin=min(A) 이 소스 혼합 집합에서
            최솟값을 뽑는다. 소스 축에서 폐기한 min() 이 표본 축으로 부활한 것이다.
            구간 단위 채택으로 바꾸기 위한 관측값이다. (STEP 5-1)
            """
            # ★ 2026-08-23. 세 번째로 표본 배열을 같이 낸다.
            #   `widths()` 는 이미 7-튜플이라 여덟 번째를 더하면 호출부가
            #   깨진다. `_covr()` 은 이미 튜플이므로 여기를 늘리는 것이
            #   변경 면적이 제일 작다 — 호출부는 언패킹 한 줄만 바뀐다.
            # ★ 2026-08-24. 네 번째로 **유효표본 수**를 같이 낸다.
            #   `verdict(wmin, wmax, nreg)` 의 세 번째 인자는 이름 그대로
            #   정규 표본 수인데, 호출부가 `_n_try`(시도 수)를 넘기고
            #   있었다. `_n_reg = len(A)` 는 여기보다 아래에서 정의되므로
            #   클로저로 못 잡는다. `A` 를 직접 센다 — 같은 값이다.
            return ({k: (round(v/_n_try, 3) if _n_try else None)
                     for k, v in _cov.items()}, _n_try, _rows, len(A))
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
            # ★ 2026-08-23. 여기 삼항이 하나 있었는데 양쪽 가지가 `_inx` 로
            #   같았다(`_inx if (...) else _inx`). 아무 일도 하지 않는 줄이라
            #   지운다. 실제 분기는 아래 세 줄이 전부이고 동작은 그대로다.
            #   ruff 는 이런 것을 안 잡는다.
            if not _short:
                _skip = _inx
            elif self.xsec_poly is not None:
                _skip = self.xsec_poly.intersects(_pt)
            else:
                _skip = False
            if _skip:
                _nx_skip += 1
                _rows.append({"s": round(t, 2), "w": None, "src": None,
                              "drop": "xsec"})
                if self.debug:
                    _how = "폴리곤" if (self.xsec_poly is not None
                                       and self.xsec_poly.intersects(_pt)) else "반경"
                    print(f"    t={t:7.1f}  교차로 {self.xn.distance(_pt):.1f}m ({_how}) — 제외")
                continue
            if self.debug:
                _pp = s.interpolate(t)
                print(f"    t={t:7.1f}  ({_pp.x:.1f},{_pp.y:.1f})")
            a, b, sc, pr, _why, _res = self.measure(s, t)
            _n_try += 1

            def _trusted(_nm, _res=_res):
                """이 지점에서 그 소스의 표본을 믿을 수 있는가.

                ★ _res 를 기본인자로 묶는다. 그러지 않으면 클로저가 정의
                  시점이 아니라 **호출 시점의** _res 를 읽는다. 지금은 같은
                  반복 안에서만 부르므로 결과가 같지만, 이 함수가 루프 밖으로
                  새거나 지연 평가되는 순간 **다른 표본의 값으로 신뢰도를
                  판정한다**. 폭 채택 소스가 바뀌는 자리다.
                """
                _r = _res.get(_nm)
                if _r is None or _r[0] is None:
                    return False
                _sn = _r[3]
                return _sn is None or _sn <= SNAP_TRUST

            for _nm in WIDTH_SRCS:
                if _trusted(_nm):
                    _cov[_nm] += 1
            if _why: _whys.append(_why)
            # 채택된 소스의 snap 이 크면 그 표본 자체를 버린다.
            if a and (sc is None or _trusted(sc)):
                A.append(a); S.append(sc); D.append(pr)
                _rows.append({"s": round(t, 2), "w": round(float(a), 3),
                              "src": sc, "drop": None})
            else:
                # 잰 시도는 했는데 값이 안 나온 자리. `w(s)` 의 결측이다 —
                # 커버율은 이 개수만 세지만 **어디가** 비었는지는 못 준다.
                _rows.append({"s": round(t, 2), "w": None, "src": None,
                              "drop": _why or "no_value"})
            # ★ pr 은 measure() 가 항상 3-튜플로 준다. strict=True 로
            #   그 계약을 고정한다 — 소스가 늘거나 줄면 여기서 죽어야
            #   조용히 한 소스가 빠지는 일이 없다.
            for _nm, _vv in zip(WIDTH_SRCS, pr, strict=True):
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
        if not self.mix_src:
            # 커버율은 소스를 '고르는' 기준이 아니라 '자격'이다.
            # 커버율로 고르면 실폭도로(0.955)가 항상 이겨 결정 63 이 뒤집힌다.
            _covnow = _covr()[0]
            for _nm in WIDTH_SRCS:
                if not _by[_nm]:
                    continue
                _cv = _covnow.get(_nm)
                # ★ 2026-09-29 (DECISIONS §308). 이 줄에 `and _n_reg >= 3` 이 붙어
                #   있었다 — **정규표본이 3개 미만이면 자격 검사를 건너뛴다.** 즉
                #   근거가 가장 얇은 구간에서 관문이 꺼졌고, 그 면제는 어느 주석에도
                #   적혀 있지 않았다(무음 통과).
                #
                #   실측으로 뗐다. DM02918 필문대로289번길이 **폭 29.91m · clear**
                #   로 발행되고 있었다 — ngii1k 가 표본 8개 중 2개(cov 0.25)로 낸
                #   값이고, 실폭도로는 같은 구간을 **1.4m · cov 1.0** 으로 잰다.
                #   `clear` 는 「영상판정조차 필요 없다」이므로 20배 틀린 값이
                #   미탐 쪽으로 나가 있었다.
                #
                #   ★ §245 가 `COV_MIN` 으로 고친 병이 이 면제 뒤에 살아 있었다.
                #     `verdict()` 주석이 인용하는 그 사고(DM02647 → 지금 DM02678)가
                #     표본 1개짜리라 **바로 그 사례에서** 관문이 꺼졌다.
                if _cv is not None and _cv < COV_MIN:
                    continue          # 자격 미달. 다음 순위로 넘긴다
                _pick = _nm
                break
            # 전부 자격 미달이면 우선순위대로 하나는 쓴다(폭을 못 내는 것보다 낫다).
            if _pick is None:
                for _nm in WIDTH_SRCS:
                    if _by[_nm]:
                        _pick = _nm
                        break
        wmin = None
        if _pick is not None:
            wmin = _round_pos(min(_by[_pick]))
        elif A:
            wmin = _round_pos(min(A))
        wmax = _round_pos(min(B)) if B else None
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
