#!/usr/bin/env python3
"""
desk_check.py — 정사영상 위에 구간과 산출폭을 얹어 책상에서 대조한다.

    uv run python tools/desk_check.py                 # 기본 묶음 전부
    uv run python tools/desk_check.py DM-193339-283611-1GLE
    uv run python tools/desk_check.py --track disagree

왜
    폭 오류를 잡는 유일한 수단이 현장 실측인 것처럼 다뤄 왔다. 아니다.
    저장소에 25cm 급 항공정사영상이 있고 그것은 **폭 산출 알고리즘과
    독립된 관측**이다. 소스 이견 45m 같은 오류는 현장에 나가기 전에
    화면에서 끝난다.

    다만 무엇을 못 잡는지도 분명히 해 둔다.

      잡는다      우리 계산이 틀렸나 — 교차로 물기, 엉뚱한 폴리곤 채택,
                  중심선 이탈, 도엽 경계 결손
      못 잡는다   지도 자체가 틀렸나 — 수치지형도는 항공사진 도화로
                  만들어져 정사영상과 완전히 독립이 아니다

    후자만 D-25 실측이 필요하다. 전자는 오늘 밤에 된다.

출력
    data/desk/<seg_uid>.png
      · 정사영상 위 구간 중심선
      · 중점에서 중심선에 수직으로 width_min · width_max 눈금
      · 축척 막대와 판정·소스·이견을 적은 머리글

★ 눈금은 **중점 한 곳**에만 그린다. width_min 은 구간 전체의 하한이므로
  중점의 실폭과 다를 수 있다. 눈금이 벽을 뚫으면 그것이 신호다.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("! pillow 가 없다 — uv add pillow")

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "web/data/segments.geojson"
ORTHO = ROOT / "web/data/ortho"
OUT = ROOT / "data/desk"
Z = 18          # ortho.py TILE_Z 의 최대값
TILE = 256
PAD_M = 30.0    # 구간 바깥으로 확보할 여백


def deg2px(lon: float, lat: float, z: int) -> tuple[float, float]:
    n = 2.0 ** z * TILE
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def mpp(lat: float, z: int) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)


def stitch(lo: float, la: float, hi_lo: float, hi_la: float):
    """경위도 범위를 덮는 타일을 이어 붙이고 (이미지, 좌상단 픽셀) 반환."""
    x0, y0 = deg2px(lo, hi_la, Z)
    x1, y1 = deg2px(hi_lo, la, Z)
    tx0, ty0 = int(x0 // TILE), int(y0 // TILE)
    tx1, ty1 = int(x1 // TILE), int(y1 // TILE)
    W = (tx1 - tx0 + 1) * TILE
    H = (ty1 - ty0 + 1) * TILE
    canvas = Image.new("RGB", (W, H), (24, 24, 24))
    miss = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            f = ORTHO / str(Z) / str(tx) / f"{ty}.jpg"
            if f.exists():
                canvas.paste(Image.open(f), ((tx - tx0) * TILE, (ty - ty0) * TILE))
            else:
                miss += 1
    return canvas, tx0 * TILE, ty0 * TILE, miss


def render(feat: dict) -> Path | None:
    p = feat["properties"]
    C = feat["geometry"]["coordinates"]
    lons = [c[0] for c in C]
    lats = [c[1] for c in C]
    mid_lat = sum(lats) / len(lats)
    m = mpp(mid_lat, Z)
    dlat = PAD_M / 111_320
    dlon = PAD_M / (111_320 * math.cos(math.radians(mid_lat)))

    img, ox, oy, miss = stitch(min(lons) - dlon, min(lats) - dlat,
                               max(lons) + dlon, max(lats) + dlat)
    if miss:
        print(f"  ! 타일 {miss}장 없음 — 스코프 밖일 수 있다")

    S = 3   # 확대. z18 은 0.49m/px 라 그대로는 눈으로 못 잰다
    img = img.resize((img.width * S, img.height * S), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")

    def P(lon, lat):
        x, y = deg2px(lon, lat, Z)
        return ((x - ox) * S, (y - oy) * S)

    pts = [P(*c) for c in C]
    d.line(pts, fill=(255, 220, 0, 230), width=3)
    for x, y in pts:
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 220, 0, 255))

    # 중점에서 중심선에 수직으로 폭 눈금
    i = len(pts) // 2
    ax, ay = pts[max(0, i - 1)]
    bx, by = pts[min(len(pts) - 1, i + 1)]
    L = math.hypot(bx - ax, by - ay) or 1.0
    nx, ny = -(by - ay) / L, (bx - ax) / L
    cx, cy = pts[i]
    ppm = S / m          # 픽셀 per 미터

    for w, col, lab in ((p.get("width_min_m"), (0, 255, 160, 235), "min"),
                        (p.get("width_max_m"), (255, 90, 90, 200), "max")):
        if not w:
            continue
        h = w * ppm / 2
        d.line([cx - nx * h, cy - ny * h, cx + nx * h, cy + ny * h],
               fill=col, width=3)
        for s in (-1, 1):
            ex, ey = cx + nx * h * s, cy + ny * h * s
            d.line([ex - ny * 7, ey + nx * 7, ex + ny * 7, ey - nx * 7],
                   fill=col, width=3)
        d.text((cx + nx * h + 6, cy + ny * h), f"{lab} {w:.2f}m", fill=col)

    head = (f"{p['seg_uid']}  {p['road_name']} {p.get('seg_no','')}구간   "
            f"{p['verdict']}   L={p['length_m']}m   "
            f"src={p['width_src']}  이견={p.get('width_disagree_m')}  "
            f"대장폭={p.get('road_bt_m')}")

    # 타일 단위로 이어 붙였으니 구간 주변만 잘라낸다.
    # 안 자르면 512m 짜리 그림 한가운데 30m 구간이 놓여 눈으로 못 본다.
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    pad = PAD_M * ppm
    img = img.crop((max(0, int(min(xs) - pad)), max(0, int(min(ys) - pad)),
                    min(img.width, int(max(xs) + pad)),
                    min(img.height, int(max(ys) + pad))))

    OUT.mkdir(parents=True, exist_ok=True)
    d = ImageDraw.Draw(img, "RGBA")
    bar = 5 * ppm
    d.rectangle([10, img.height - 26, 10 + bar, img.height - 20],
                fill=(255, 255, 255, 220))
    d.text((12, img.height - 44), "5 m", fill=(255, 255, 255, 235))
    d.rectangle([0, 0, img.width, 22], fill=(0, 0, 0, 200))
    d.text((6, 6), head, fill=(255, 255, 255, 240))

    out = OUT / f"{p['seg_uid']}.png"
    img.save(out)
    return out


# 기본 묶음 — 손으로 고르지 않는다. 기준은 §7-2 와 같다.
def pick(P: list[dict], track: str) -> list[dict]:
    if track == "disagree":       # 소스 이견 상위. 계산 오류가 가장 잘 드러난다
        c = [f for f in P if (f["properties"].get("width_disagree_m") or 0) > 5]
        c.sort(key=lambda f: -(f["properties"]["width_disagree_m"] or 0))
    elif track == "wmax":         # ROAD_BT 확대로도 못 건진 잔여 결손
        c = [f for f in P if f["properties"]["width_max_m"] is None
             and (f["properties"]["width_min_m"] or 9) < 3.0
             and not ((f["properties"]["road_bt_m"] or 9) < 3.0)]
        c.sort(key=lambda f: -f["properties"]["length_m"])
    elif track == "shoot":        # 촬영 후보. needs_cv + CCTV 안 + 통행량
        c = [f for f in P if f["properties"]["verdict"] == "needs_cv"
             and (f["properties"]["cctv_dist_m"] or 9e9) <= 25
             and f["properties"]["length_m"] >= 25]
        c.sort(key=lambda f: -(f["properties"]["route_usage"] or 0))
    else:
        raise SystemExit(f"! 모르는 track: {track}")
    return c[:6]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("seg_uid", nargs="*")
    ap.add_argument("--track", choices=["disagree", "wmax", "shoot"])
    a = ap.parse_args()

    P = json.loads(SEG.read_text(encoding="utf-8"))["features"]
    if a.seg_uid:
        sel = [f for f in P if f["properties"]["seg_uid"] in a.seg_uid]
        missing = set(a.seg_uid) - {f["properties"]["seg_uid"] for f in sel}
        for m in missing:
            print(f"! 없는 seg_uid: {m}")
    else:
        sel = []
        for t in ([a.track] if a.track else ["disagree", "wmax", "shoot"]):
            print(f"\n[{t}]")
            for f in pick(P, t):
                sel.append(f)
                print(f"  {f['properties']['seg_uid']}  "
                      f"{f['properties']['road_name']}  "
                      f"L={f['properties']['length_m']}m")

    for f in sel:
        out = render(f)
        if out:
            print(f"→ {out.relative_to(ROOT)}")
    print(f"\n{len(sel)}장. 눈금이 벽을 뚫으면 그 구간이 틀린 것이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
