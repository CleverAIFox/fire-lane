#!/usr/bin/env python3
"""
tools/naver_page.py — 네이버 대조 입력 페이지를 만든다

    uv run python tools/naver_page.py

════════════════════════════════════════════════════════════════
★ 왜 CSV 가 아니라 페이지인가.

  46구간을 엑셀로 열어 셀을 오가며 URL 을 복사하고 붙여넣는 것은 고문이다.
  한 행에 여섯 칸이니 276번 클릭한다. 그러다 행이 밀리면 조용히 틀린다.

  한 행이 **클릭 두 번과 숫자 하나**로 끝나야 한다. 그래서 화면을 만든다.
    · 링크는 버튼 하나 (새 탭)
    · Y/N · H/M/L 은 키보드 한 글자
    · 폭은 숫자만 치고 Enter → 다음 구간
    · 입력은 브라우저에 자동 저장. 창을 닫아도 남는다
    · 다 하면 CSV 로 내려받아 tools/naver_join.py 에 넣는다

★ 데이터를 HTML 에 구워 넣는다. fetch 가 없으므로 file:// 로 열어도
  동작한다. 서버를 띄울 필요가 없다.

★ 46개를 다 안 해도 된다. 10개만 하고 내려받아 naver_join 을 돌려라.
  산포가 크면 나머지 36개는 결론을 안 바꾼다.
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import csv
import json

from firelane.paths import ROOT

FIELD = ROOT / "data" / "field"

# ── 지도와 같은 팔레트를 쓴다. 같은 프로젝트의 도구다. ──────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --void:#0a0d13; --panel:#141922; --line:#232b38; --dim:#7c8798;
  --text:#e6ebf2; --acc:#4ad18f; --warn:#ffab2e; --bad:#ff4d3d;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
body{background:var(--void);color:var(--text);
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif;
  display:flex;flex-direction:column;min-height:100vh}

/* 진행률이 곧 남은 일이다. 화면 맨 위에 항상 둔다. */
header{position:sticky;top:0;z-index:9;background:var(--panel);
  border-bottom:1px solid var(--line);padding:10px 18px;
  display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.bar{flex:1;min-width:160px;height:5px;background:var(--line);border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--acc);width:0;transition:width .25s}
.cnt{font-family:var(--mono);font-size:12px;color:var(--dim);white-space:nowrap}
button{font:inherit;cursor:pointer;border:1px solid var(--line);border-radius:6px;
  background:var(--panel);color:var(--text);padding:7px 13px;transition:.12s}
button:hover{border-color:var(--dim)}
button:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.ghost{font-size:12px;color:var(--dim);padding:6px 11px}

main{flex:1;display:flex;align-items:flex-start;justify-content:center;padding:26px 18px 60px}
.card{width:100%;max-width:620px;background:var(--panel);
  border:1px solid var(--line);border-radius:10px;padding:22px}

.eyebrow{font-family:var(--mono);font-size:11px;color:var(--dim);
  letter-spacing:.04em;display:flex;gap:10px;align-items:center}
.band{border:1px solid var(--line);border-radius:4px;padding:1px 7px}
h1{font-size:21px;font-weight:700;margin:7px 0 3px;letter-spacing:-.01em}
.sub{font-family:var(--mono);font-size:12px;color:var(--dim);margin-bottom:16px}

/* 미니맵 — 배경 지도는 없다. 형상과 방위만 알면 네이버에서 찾는다. */
.map{background:#0d1219;border:1px solid var(--line);border-radius:8px;
  margin-bottom:14px;overflow:hidden}
.map svg{display:block;width:100%;height:190px}
.near{stroke:#2b3648;stroke-width:2;fill:none;stroke-linecap:round}
.self{stroke:var(--acc);stroke-width:4;fill:none;stroke-linecap:round}
.cap{fill:var(--acc)}
.dir{font-family:var(--mono);font-size:12px;color:var(--dim);
  display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.dir b{color:var(--text);font-weight:600}

.open{width:100%;background:#1b2330;border-color:#2e3a4d;padding:11px;
  font-weight:600;margin-bottom:20px}
.open:hover{background:#212b3a}

fieldset{border:0;border-top:1px solid var(--line);padding-top:15px;margin-top:15px}
legend{display:none}
.q{font-size:12px;color:var(--dim);margin-bottom:8px}
.q b{color:var(--text);font-weight:600}
.row{display:flex;gap:8px;align-items:center;margin-bottom:11px;flex-wrap:wrap}
.pick{padding:7px 15px;font-family:var(--mono);font-size:13px}
.pick.on{background:var(--acc);color:#08110c;border-color:var(--acc);font-weight:700}
.pick.on[data-v="N"],.pick.on[data-v="L"]{background:var(--bad);color:#fff;border-color:var(--bad)}
.pick.on[data-v="M"]{background:var(--warn);color:#1a1205;border-color:var(--warn)}
kbd{font-family:var(--mono);font-size:10px;color:var(--dim);
  border:1px solid var(--line);border-radius:3px;padding:0 4px;margin-left:5px}
input{font:inherit;background:var(--void);color:var(--text);
  border:1px solid var(--line);border-radius:6px;padding:8px 11px;width:100%}
input:focus{outline:none;border-color:var(--acc)}
input.num{font-family:var(--mono);max-width:130px}
.hint{font-size:11px;color:var(--dim);margin-top:5px}
.warn{color:var(--warn)}

nav{display:flex;gap:8px;margin-top:22px;padding-top:16px;border-top:1px solid var(--line)}
nav button{flex:1}
.done{border-color:var(--acc);color:var(--acc)}

footer{position:fixed;bottom:0;left:0;right:0;background:var(--panel);
  border-top:1px solid var(--line);padding:8px 18px;font-size:11px;color:var(--dim);
  display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = r"""
const D = DATA__;
const NEAR = NEAR__;

/* 방위 8방향. "동서로 뻗은 짧은 토막" 을 알면 네이버에서 즉시 찾는다. */
function bearing(a, b) {
  const dy = b[1] - a[1], dx = (b[0] - a[0]) * Math.cos(a[1] * Math.PI / 180);
  let d = (Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360;
  if (d > 180) d -= 180;                       // 선이라 방향은 반주기
  const n = ["남북", "북북동-남남서", "북동-남서", "동북동-서남서",
             "동서", "동남동-서북서", "북서-남동", "북북서-남남동"];
  return n[Math.round(d / 22.5) % 8];
}

/* 배경 지도 없이 선만 그린다. 형상과 상대 위치만 있으면 충분하다. */
function drawMini(d) {
  const g = document.getElementById("mg");
  g.innerHTML = "";
  const self = [[+d.start_lon, +d.start_lat], [+d.end_lon, +d.end_lat]];
  const lines = (NEAR[d.seg_uid] || []).concat([self]);
  const pts = lines.flat();
  if (!pts.length) return;

  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const k = Math.cos(cy * Math.PI / 180);      // 경도 축척 보정
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  const W = 600, H = 190, PAD = 14;
  const w = Math.max((x1 - x0) * k, 1e-9), h = Math.max(y1 - y0, 1e-9);
  const s = Math.min((W - PAD * 2) / w, (H - PAD * 2) / h);
  const px = p => [(p[0] - x0) * k * s + (W - w * s) / 2,
                   H - ((p[1] - y0) * s + (H - h * s) / 2)];   // y 뒤집기(북쪽 위)
  const path = l => "M" + l.map(p => px(p).map(v => v.toFixed(1)).join(",")).join("L");

  const ns = "http://www.w3.org/2000/svg";
  for (const l of NEAR[d.seg_uid] || []) {
    const e = document.createElementNS(ns, "path");
    e.setAttribute("d", path(l)); e.setAttribute("class", "near"); g.appendChild(e);
  }
  const me = document.createElementNS(ns, "path");
  me.setAttribute("d", path(self)); me.setAttribute("class", "self"); g.appendChild(me);
  for (const p of self) {
    const c = document.createElementNS(ns, "circle");
    const [X, Y] = px(p);
    c.setAttribute("cx", X); c.setAttribute("cy", Y); c.setAttribute("r", 4);
    c.setAttribute("class", "cap"); g.appendChild(c);
  }
  document.getElementById("dirv").textContent = bearing(self[0], self[1]);
  document.getElementById("lenv").textContent = d.length_m + " m";
}
const KEY = "naver_check_v1";
let i = 0, ans = JSON.parse(localStorage.getItem(KEY) || "{}");

const $ = s => document.querySelector(s);
const save = () => localStorage.setItem(KEY, JSON.stringify(ans));
const cur = () => (ans[D[i].seg_uid] ||= {});

/* 폭이 채워졌으면 그 행은 끝난 것으로 본다. 기초번호만 볼 수도 있으므로
   둘 중 하나라도 있으면 진행에 넣는다. */
const filled = u => { const a = ans[u]; return a && (a.naver_w_m || a.label_ok); };

function draw(){
  const d = D[i], a = cur();
  $("#band").textContent = d.band;
  $("#no").textContent = `${i+1} / ${D.length}`;
  $("#label").textContent = d.seg_label_ours;
  $("#sub").textContent = `${d.road_name} · ${d.length_m}m · ${d.seg_uid}`;
  $("#open").onclick = () => window.open(d.naver_mid, "_blank", "noopener");
  drawMini(d);

  document.querySelectorAll(".pick").forEach(b =>
    b.classList.toggle("on", a[b.dataset.k] === b.dataset.v));
  $("#seen").value = a.label_seen || "";
  $("#w").value    = a.naver_w_m  || "";
  $("#at").value   = a.naver_w_at || "";
  $("#note").value = a.note       || "";

  const n = D.filter(x => filled(x.seg_uid)).length;
  $("#bar").style.width = (n / D.length * 100) + "%";
  $("#cnt").textContent = `${n} / ${D.length} 완료`;
  $("#prev").disabled = i === 0;
  $("#next").classList.toggle("done", !!filled(d.seg_uid));
}

const go = n => { i = Math.max(0, Math.min(D.length - 1, n)); draw(); };
const set = (k, v) => { const a = cur(); a[k] = a[k] === v ? "" : v; save(); draw(); };

document.querySelectorAll(".pick").forEach(b =>
  b.onclick = () => set(b.dataset.k, b.dataset.v));
["seen:label_seen","w:naver_w_m","at:naver_w_at","note:note"].forEach(p => {
  const [id, k] = p.split(":");
  $("#" + id).oninput = e => { cur()[k] = e.target.value; save();
    if (k === "naver_w_m") draw(); };
});
$("#prev").onclick = () => go(i - 1);
$("#next").onclick = () => go(i + 1);

/* 키보드만으로 끝나게 한다. 입력칸 안에서는 Enter 로만 넘어간다. */
addEventListener("keydown", e => {
  const typing = /INPUT/.test(e.target.tagName);
  if (e.key === "Enter") { e.preventDefault(); return go(i + 1); }
  if (typing) return;
  const m = {y:["label_ok","Y"], n:["label_ok","N"],
             h:["confident","H"], m:["confident","M"], l:["confident","L"]};
  const k = e.key.toLowerCase();
  if (m[k]) { e.preventDefault(); set(...m[k]); }
  else if (e.key === "ArrowRight") go(i + 1);
  else if (e.key === "ArrowLeft")  go(i - 1);
  else if (k === "w") { e.preventDefault(); $("#w").focus(); }
  else if (k === "o") { e.preventDefault(); $("#open").click(); }
});

/* 내려받기 — naver_join.py 가 기대하는 열 순서 그대로. */
$("#dl").onclick = () => {
  const cols = Object.keys(D[0]).concat(
    ["label_ok","label_seen","naver_w_m","naver_w_at","confident","note"]);
  const q = v => { v = (v ?? "") + "";
    return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  const body = D.map(d => cols.map(c =>
    q(c in d ? d[c] : (ans[d.seg_uid] || {})[c])).join(",")).join("\n");
  const blob = new Blob(["\uFEFF" + cols.join(",") + "\n" + body],
                        {type:"text/csv;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "naver_check.csv"; a.click();
};
$("#reset").onclick = () => {
  if (confirm("입력한 것을 전부 지운다. 되돌릴 수 없다.")) {
    ans = {}; save(); draw();
  }
};
draw();
"""


def build(rows: list[dict], near: dict) -> str:
    data = json.dumps(rows, ensure_ascii=False)
    nearj = json.dumps(near, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>네이버 대조 — {len(rows)}구간</title>
<style>{CSS}</style></head><body>

<header>
  <strong style="font-size:13px">네이버 대조</strong>
  <div class="bar"><i id="bar"></i></div>
  <span class="cnt" id="cnt"></span>
  <button class="ghost" id="dl">CSV 내려받기</button>
  <button class="ghost" id="reset">지우기</button>
</header>

<main><div class="card">
  <div class="eyebrow"><span class="band" id="band"></span><span id="no"></span></div>
  <h1 id="label"></h1>
  <div class="sub" id="sub"></div>

  <div class="map"><svg id="mini" viewBox="0 0 600 190" preserveAspectRatio="xMidYMid meet">
    <g id="mg"></g></svg></div>
  <div class="dir">
    <span>방향 <b id="dirv">—</b></span>
    <span>길이 <b id="lenv">—</b></span>
    <span style="color:var(--acc)">━━ 이 구간</span>
    <span>━━ 주변</span>
  </div>

  <button class="open" id="open">네이버 지도에서 열기 <kbd>O</kbd></button>

  <fieldset>
    <div class="q"><b>기초번호</b> — 그 구간 건물번호가 위 라벨과 맞나</div>
    <div class="row">
      <button class="pick" data-k="label_ok" data-v="Y">맞다<kbd>Y</kbd></button>
      <button class="pick" data-k="label_ok" data-v="N">아니다<kbd>N</kbd></button>
      <input id="seen" placeholder="실제로 보인 번호 범위 (예: 9-14)" style="flex:1;min-width:200px">
    </div>
  </fieldset>

  <fieldset>
    <div class="q"><b>폭</b> — 거리 도구로 잰다.
      <span class="warn">구간에서 가장 좁아 보이는 곳</span>을 재라. 중점이 아니다.</div>
    <div class="row">
      <input id="w" class="num" inputmode="decimal" placeholder="3.42"><span class="cnt">m</span>
      <kbd>W</kbd>
      <input id="at" placeholder="어디를 쟀나 (예: 시점에서 20m)" style="flex:1;min-width:180px">
    </div>
    <div class="q" style="margin-top:6px">두 점을 얼마나 정확히 찍었나</div>
    <div class="row">
      <button class="pick" data-k="confident" data-v="H">정확<kbd>H</kbd></button>
      <button class="pick" data-k="confident" data-v="M">보통<kbd>M</kbd></button>
      <button class="pick" data-k="confident" data-v="L">애매<kbd>L</kbd></button>
    </div>
    <div class="hint">우리 산출 폭은 가려져 있다. 먼저 보면 그 값 근처로 수렴한다.</div>
  </fieldset>

  <fieldset>
    <div class="q"><b>비고</b> — 주차 상태, 애매했던 이유 등</div>
    <div class="row"><input id="note" placeholder="선택"></div>
  </fieldset>

  <nav>
    <button id="prev">← 이전</button>
    <button id="next">다음 →</button>
  </nav>
</div></main>

<footer>
  <span>Enter · → 다음</span><span>← 이전</span>
  <span>Y/N 기초번호</span><span>H/M/L 신뢰도</span>
  <span>W 폭 입력</span><span>O 지도 열기</span>
  <span>입력은 이 브라우저에 자동 저장된다</span>
</footer>

<script>const DATA__ = {data};
const NEAR__ = {nearj};
{JS}</script>
</body></html>"""


def main() -> int:
    src = FIELD / "naver_check.csv"
    if not src.exists():
        print(f"::error::{src} 없다. tools/naver_check.py 를 먼저 돌려라")
        return 1
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))
    # 사람이 채울 칸은 페이지가 관리한다. 데이터에서 뺀다.
    fill = {"label_ok", "label_seen", "naver_w_m", "naver_w_at", "confident", "note"}
    rows = [{k: v for k, v in r.items() if k not in fill} for r in rows]

    nf = FIELD / "naver_near.json"
    near = json.loads(nf.read_text(encoding="utf-8")) if nf.exists() else {}
    if not near:
        print("  ! naver_near.json 없다 — 미니맵이 대상 구간만 그린다.")
        print("    tools/naver_check.py 를 다시 돌리면 주변도 나온다.")

    dst = FIELD / "naver_check.html"
    dst.write_text(build(rows, near), encoding="utf-8")
    print(f"→ {dst}  ({len(rows)}구간)")
    print("  브라우저로 열어라. 서버 필요 없다.")
    print("  10개만 하고 CSV 내려받아 naver_join 을 돌려도 결론이 나온다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
