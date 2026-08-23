#!/usr/bin/env python3
"""
tools/jijeok_review.py — 도면 두 계보가 갈리는 구간을 정사영상 위에서 판정한다

    uv run python tools/jijeok_review.py          # web/review.html 생성
    uv run python tools/serve.py                  # http://localhost:8000/review.html

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 읽고 HTML 하나를 만든다.

── 왜 만들었나 ─────────────────────────────────────────────────
`jijeok_probe.py` 가 3.0m 임계에서 갈리는 구간을 뽑아줬지만, 그것을
**좌표 목록으로 주면 찾아가는 것부터가 일이다.** 한 곳당 지도를 열고
좌표를 붙여넣고 축척을 맞추는 데 1분씩 든다. 27곳이면 30분이 이동에만
간다 — 정작 봐야 할 것은 담장 사이 거리 하나인데.

`naver_page.py` 가 같은 이유로 만들어졌다(§ 한 행이 클릭 두 번과 숫자
하나로 끝나야 한다). 그 방식을 우리 지도에 적용한다.

    · 왼쪽 목록에서 누르면 그 구간으로 날아간다
    · 정사영상 25cm 배경 + 우리 세그먼트 + 지적 도로 필지가 겹쳐 있다
    · 승용차 1.8m 자가 화면에 떠 있다
    · A/B/C/D 를 키보드 한 글자로 찍는다
    · 판정은 브라우저에 저장된다. 창을 닫아도 남는다
    · 다 하면 CSV 로 내려받아 결론을 낸다

★ 데이터를 HTML 에 구워 넣는다. fetch 가 없으므로 타일만 있으면 된다.

── 판정 어휘 ───────────────────────────────────────────────────
    A  우리가 맞다     지적이 도로구역을 넓게 잡은 것
    B  지적이 맞다     ★ 우리 폭 산출에 문제가 있다
    C  둘 다 아니다    영상에서 잰 값이 따로 있다 (숫자를 적는다)
    D  못 보겠다       나무 · 그늘 · 화질

**B 가 몇 개인가가 핵심이다.** 하나도 없으면 지적 축은 교차검증용으로만
쓰고, 여럿이면 `width.py` 를 봐야 한다.

IN    $FIRE_LANE_DATA/../jijeok_width.gpkg   (jijeok_probe.py --save)
      web/data/view.json · segments.geojson
OUT   web/review.html
PARAM 아래 상수
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import sys

import geopandas as gpd

from firelane.paths import RAW, ROOT, WEB

TH = 3.0            # 판정 임계. seg/params.py TRUCK 과 같아야 한다
MAX_W = 25.0        # 이보다 크면 도로구역 필지 잔재다(§ jijeok_probe ⑥)
MIN_COV = 0.6       # 표본이 이보다 적으면 신뢰가 낮다
EDGE = 0.5          # 양쪽 다 임계 ±이 값 안이면 어차피 애매하다

SRC = "jijeok_width.gpkg"
OUT = "review.html"


def main() -> int:
    src = RAW.parent.parent / SRC
    if not src.exists():
        print(f"\033[31m{src} 가 없다.\033[0m")
        print("  uv run python tools/jijeok_probe.py --save 를 먼저 돌려라.")
        return 1

    g = gpd.read_file(src, layer="seg")
    f = g[((g.width_min_m >= TH) & (g.jj_w < TH)) |
          ((g.width_min_m < TH) & (g.jj_w >= TH))].copy()
    n0 = len(f)
    f = f[(f.jj_w <= MAX_W) & (f.jj_cov >= MIN_COV)]
    f = f[~(((f.jj_w - TH).abs() < EDGE) & ((f.width_min_m - TH).abs() < EDGE))]
    print(f"갈리는 구간 {n0} → 볼 것 {len(f)}"
          f"  (도로구역 잔재 · 표본 부족 · 양쪽 경계선 제외)")

    f = f.to_crs(4326)
    f["side"] = ["막았다" if w < TH else "열었다" for w in f.width_min_m]
    f = f.sort_values(["side", "jj_cov"], ascending=[True, False])

    items = []
    for i, r in enumerate(f.itertuples(), 1):
        geom = r.geometry
        co = list(geom.coords) if geom.geom_type == "LineString" \
            else list(max(geom.geoms, key=lambda q: q.length).coords)
        items.append({
            "n": i,
            "label": str(r.seg_label or r.road_name or r.seg_uid),
            "uid": r.seg_uid,
            "side": r.side,
            "verdict": r.verdict,
            "ours": round(float(r.width_min_m), 2),
            "jj": round(float(r.jj_w), 2),
            "cov": round(float(r.jj_cov), 2),
            "len": round(float(r.length_m)),
            "line": [[round(x, 6), round(y, 6)] for x, y in co],
        })

    view = json.loads((WEB / "view.json").read_text(encoding="utf-8"))
    html = TEMPLATE.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
    html = html.replace("__VIEW__", json.dumps(view, ensure_ascii=False))
    html = html.replace("__BUILD__", str(view.get("build", "")))

    dst = WEB / OUT
    dst.write_text(html, encoding="utf-8")
    print(f"\033[32m→\033[0m {dst.relative_to(ROOT)}  ({len(items)}곳)")
    print("\n  uv run python tools/serve.py")
    print("  http://localhost:8000/review.html")
    return 0


TEMPLATE = r"""<!doctype html>
<meta charset="utf-8">
<title>지적 대조 — 정사영상</title>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  *{box-sizing:border-box} html,body{margin:0;height:100%;font:13px/1.5 system-ui}
  #wrap{display:flex;height:100%}
  #side{width:330px;overflow:auto;border-right:1px solid #ddd;background:#fafafa}
  #map{flex:1;position:relative}
  h1{font-size:14px;margin:0;padding:10px 12px;background:#222;color:#fff}
  .it{padding:8px 12px;border-bottom:1px solid #eee;cursor:pointer}
  .it:hover{background:#fff8d0} .it.on{background:#ffe9a8}
  .it b{font-size:13px} .m{color:#666;font-size:12px}
  .blk{border-left:4px solid #d33} .opn{border-left:4px solid #36c}
  .done{opacity:.45}
  .tag{display:inline-block;min-width:16px;text-align:center;border-radius:3px;
       padding:0 4px;font-weight:700;color:#fff}
  .A{background:#2a2} .B{background:#d33} .C{background:#e90} .D{background:#999}
  #bar{position:absolute;top:10px;left:10px;z-index:5;background:#fff;
       padding:8px 12px;border-radius:6px;box-shadow:0 1px 6px #0004;max-width:520px}
  #bar b{font-size:14px} kbd{background:#eee;border:1px solid #bbb;border-radius:3px;
       padding:0 4px;font-family:inherit}
  #ruler{position:absolute;bottom:24px;left:50%;transform:translateX(-50%);z-index:5;
         background:#fff;padding:6px 10px;border-radius:6px;box-shadow:0 1px 6px #0004}
  #foot{position:absolute;bottom:10px;right:10px;z-index:5;background:#fff;
        padding:8px 12px;border-radius:6px;box-shadow:0 1px 6px #0004}
  button{font:inherit;padding:4px 10px;cursor:pointer}
</style>
<div id="wrap">
  <div id="side"><h1>갈리는 구간 <span id="cnt"></span></h1><div id="list"></div></div>
  <div id="map">
    <div id="bar"></div>
    <div id="ruler"></div>
    <div id="foot">
      <button onclick="dump()">CSV 내려받기</button>
      <button onclick="if(confirm('판정을 전부 지운다'))reset()">초기화</button>
    </div>
  </div>
</div>
<script>
const ITEMS = __ITEMS__, VIEW = __VIEW__, BUILD = "__BUILD__";
const KEY = "jijeok_review_" + BUILD;
let ans = JSON.parse(localStorage.getItem(KEY) || "{}");
let cur = 0;

const map = new maplibregl.Map({
  container: "map", hash: false,
  center: VIEW.center, zoom: 18, maxZoom: 22,
  style: {
    version: 8, glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      /* ★ 우리 정사영상. 25cm GSD · z19 까지 구웠고 그 위는 확대만 한다.
         네이버를 안 쓰는 이유 — 같은 국토지리정보원 항공사진이고,
         우리 것은 도엽 원본이라 재압축이 덜하다. */
      ortho: { type: "raster", tiles: ["data/ortho/{z}/{x}/{y}.jpg"],
               tileSize: 256, minzoom: 15, maxzoom: 19,
               bounds: VIEW.orthoBounds, attribution: "국토정보플랫폼 정사영상 2025" }
    },
    layers: [{ id: "bg", type: "background", paint: { "background-color": "#111" } },
             { id: "ortho", type: "raster", source: "ortho" }]
  }
});

map.on("load", () => {
  map.addSource("seg", { type: "geojson", data: fc(ITEMS) });
  map.addLayer({ id: "seg-l", type: "line", source: "seg",
    paint: { "line-width": 3, "line-opacity": .9,
             "line-color": ["case", ["==", ["get", "side"], "막았다"], "#f44", "#4af"] } });
  map.addLayer({ id: "seg-hi", type: "line", source: "seg",
    filter: ["==", "n", -1],
    paint: { "line-width": 8, "line-color": "#ff0", "line-opacity": .55 } });
  go(0);
});

function fc(list) {
  return { type: "FeatureCollection", features: list.map(d => ({
    type: "Feature", properties: { n: d.n, side: d.side },
    geometry: { type: "LineString", coordinates: d.line } })) };
}

function bounds(line) {
  const b = new maplibregl.LngLatBounds();
  line.forEach(c => b.extend(c));
  return b;
}

function go(i) {
  cur = i;
  const d = ITEMS[i];
  map.fitBounds(bounds(d.line), { padding: 140, duration: 500, maxZoom: 21 });
  map.setFilter("seg-hi", ["==", "n", d.n]);
  document.getElementById("bar").innerHTML =
    `<b>${d.n}/${ITEMS.length} · ${d.label}</b> <span class=m>(${d.verdict})</span><br>` +
    `우리 <b>${d.ours}m</b> ↔ 지적 <b>${d.jj}m</b> · 커버 ${d.cov} · 길이 ${d.len}m<br>` +
    `<span class=m>담장~담장이 어느 쪽인가 &nbsp; ` +
    `<kbd>A</kbd>우리 <kbd>B</kbd>지적 <kbd>C</kbd>둘다아님 <kbd>D</kbd>못보겠음 ` +
    `&nbsp;<kbd>←</kbd><kbd>→</kbd>이동</span>`;
  draw();
}

/* ★ 화면 축척자. 승용차 폭 1.8m 를 자로 쓴다 —
   숫자로 3m 라고 적어도 감이 안 오지만 차 한 대와 비교하면 바로 보인다. */
function ruler() {
  const c = map.getCenter(), y = map.getContainer().clientHeight / 2;
  const a = map.unproject([0, y]), b = map.unproject([100, y]);
  const m = a.distanceTo(b) / 100;                    // m per px
  const px18 = 1.8 / m, px3 = 3.0 / m;
  document.getElementById("ruler").innerHTML =
    `<div style="width:${px18}px;height:9px;background:#0f0;outline:1px solid #000"></div>` +
    `<div class=m>승용차 1.8m</div>` +
    `<div style="width:${px3}px;height:9px;background:#ff0;outline:1px solid #000;margin-top:4px"></div>` +
    `<div class=m>임계 3.0m</div>`;
}
map.on("move", ruler);

function draw() {
  const L = document.getElementById("list");
  L.innerHTML = ITEMS.map((d, i) => {
    const a = ans[d.uid] || {};
    const t = a.v ? `<span class="tag ${a.v}">${a.v}</span> ` : "";
    return `<div class="it ${d.side === "막았다" ? "blk" : "opn"}` +
      `${i === cur ? " on" : ""}${a.v ? " done" : ""}" onclick="go(${i})">` +
      `${t}<b>${d.n}. ${d.label}</b><br>` +
      `<span class=m>${d.side} · 우리 ${d.ours} ↔ 지적 ${d.jj} · 커버 ${d.cov}</span></div>`;
  }).join("");
  const done = Object.keys(ans).length;
  const b = Object.values(ans).filter(a => a.v === "B").length;
  document.getElementById("cnt").textContent = `${done}/${ITEMS.length} · B ${b}`;
}

function mark(v) {
  const d = ITEMS[cur];
  let w = null;
  if (v === "C") {
    const s = prompt("영상에서 잰 폭(m)");
    if (s === null) return;
    w = parseFloat(s);
  }
  ans[d.uid] = { v, w, label: d.label };
  localStorage.setItem(KEY, JSON.stringify(ans));
  draw();
  if (cur < ITEMS.length - 1) go(cur + 1); else draw();
}

addEventListener("keydown", e => {
  const k = e.key.toUpperCase();
  if ("ABCD".includes(k)) { mark(k); e.preventDefault(); }
  if (e.key === "ArrowRight" && cur < ITEMS.length - 1) go(cur + 1);
  if (e.key === "ArrowLeft" && cur > 0) go(cur - 1);
});

function dump() {
  const rows = [["seg_uid","seg_label","side","verdict","ours_m","jijeok_m",
                 "cov","length_m","judgement","measured_m"]];
  ITEMS.forEach(d => {
    const a = ans[d.uid] || {};
    rows.push([d.uid, d.label, d.side, d.verdict, d.ours, d.jj, d.cov, d.len,
               a.v || "", a.w == null ? "" : a.w]);
  });
  const csv = "\ufeff" + rows.map(r => r.map(x =>
    /[",]/.test(String(x)) ? `"${String(x).replace(/"/g, '""')}"` : x).join(",")).join("\n");
  const u = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = u; a.download = "jijeok_review.csv"; a.click();
}

function reset() { ans = {}; localStorage.removeItem(KEY); draw(); }
</script>
"""


if __name__ == "__main__":
    sys.exit(main())
