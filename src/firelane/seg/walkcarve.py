"""
seg/walkcarve.py — 노면 폭에서 **보도를 깎는** 두 순수 함수. (DECISIONS §523 · Zm56 에서 `seg/width.py` 의 파일 길이 상한을 지키려고 옮겼다 — 동작은 한 글자도 안 바뀌었다)

IN    광선 · 보도면 · 좌우 거리
OUT   보도와 겹치는 1차원 구간들 · 깎인 좌우 거리
PARAM 없음
밖    `seg/width.py` 가 쓴다(`from firelane.seg.width import carve_walk, walk_spans` 도 그대로 된다 — 재수입한다).
"""


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
