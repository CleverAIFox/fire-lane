#!/usr/bin/env python3
"""
b3_palette.py — **색 사본. 진짜 둘을 닫고, 가짜 둘은 가짜라고 적는다.**

    uv run python tools/batches/b3_palette.py            무엇을 할지만
    uv run python tools/batches/b3_palette.py --apply    실제로

★ 감사가 "색 사본 5벌" 로 셌다. 열어보니 **셋만 사본이고 둘은 아니다.**

  ① mask ↔ theme          진짜다. 다크 색값이 레이어 생성부와 테마 전환부에
                          두 벌씩 있다. `#05070b` · `#5c6b82` · `#0a0d13` ·
                          건물 램프 4색. 값이 같으니 지문 불변.
  ② minimap 생성부 4색     진짜다. `#ff4d3d` · `#ffab2e` · `#4ad18f` · `#5a6272`
                          를 손으로 박아놓고, 바로 아래 `styleMiniTheme()` 은
                          `vColor()` 로 같은 것을 다시 칠한다.
                          파일 머리말이 이미 약속해놨다 —
                          *"판정 4색은 큰 지도와 같은 값을 써야 한다. vColor() 로 맞춘다."*
                          약속을 생성부가 안 지키고 있었다.
  ③ Legend ↔ layers        진짜다. 단 **값이 아니라 유도**의 사본이다.
                          `segments.js` 와 `minimap.js` 가 똑같은
                          `["match",["get","verdict"],…]` 를 각자 조립한다.
                          소비자를 하나씩 고치지 않고 유도를 정본으로 만든다
                          (원칙 ⑤ · `ledger.provider_of` 와 같은 수).

  ④ 핀(markers.js)         **사본이 아니다.** 이미 `CONFIG.markers` 의
                          `s.c` · `s.cl` 을 읽는다. 고칠 것이 없다.
  ⑤ render_figures.py      **사본이 아니다.** 아예 다른 팔레트다 —
                          `#16a34a` · `#ea580c` · `#dc2626` · `#94a3b8`.
                          지도색(`#4ad18f` …)과 한 값도 안 겹친다.
                          인쇄·문서용 그림이라 배경이 흰색이고, 지도색을
                          흰 종이에 올리면 대비가 무너진다. 통일하면
                          `그림 ↔ 정본` 검사가 운다 — 즉 **판정 변경**이다.
                          인코딩 후보 4벌과 같은 종류의 오분류다.

★ **새 모듈을 만들지 않는다.** 처음엔 `web/js/palette.js` 를 새로 낼 생각이었다.
  값을 치르는 쪽이 너무 크다 —

      CODEOWNERS 줄 추가 (`test_codeowners_covers_every_web_path`)
      `29개 모듈` 이 docs/MASTER.md 두 곳 · docs/PLAN.md · README.md 에 적혀 있다
      `test_declaration_reality` 가 그 숫자를 코드와 대조한다
      treecheck T1 — git 이 모르는 파일

  색의 정본은 **이미 있다.** `web/config.js` 다. `cctvCov` 가
  `colorDark`/`colorLight` 쌍을 그 안에 들고 있고, `markers` 도 거기 있다.
  거기에 `chrome` 블록을 더하는 것이 새 파일을 내는 것보다 맞다.
  ★ 배선 비용이 0 이다 — config.js 는 이미 CODEOWNERS 에 있고 이미 커밋돼 있다.

★ 생성부는 `.dark` 를 쓴다. `.light` 가 아니라.
  지도는 다크로 만들어지고 `setTheme()` 이 그 위에 실제 테마를 덮는다.
  생성부에서 `vColor()`(현재 테마)를 쓰면 라이트에서 값이 달라져 **불변이 깨진다.**
  `VERDICT[k].c`(다크 고정)를 쓴다. 화면 결과는 어차피 같지만,
  **같은 결과와 같은 값은 다르다.**
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

# ── ① config.js 에 chrome 정본을 심는다 ──────────────────────────
CFG_ANCHOR = '  lightTint: { color:"#cfe0ee", opacity:0 },\n'

CFG_BLOCK = '''  lightTint: { color:"#cfe0ee", opacity:0 },

  /* 지도 크롬 색. 판정 4색(verdict)이 아닌 것 — 배경 · 가리개 · 경계 · 건물.
     ★ 2026-09-11 (B3). 여기 모으기 전에는 **같은 값이 두 벌**이었다.
       레이어 생성부(`layers/mask.js` · `ui/minimap.js`)가 다크값을 박고,
       테마 전환부(`ui/theme.js`)가 다크·라이트를 또 박았다. 다크를 고치면
       전환 한 번에 되돌아오는 종류의 버그가 나온다.

     dark 는 레이어를 만들 때, light 는 setTheme() 이 쓴다.
     ★ 지도는 항상 다크로 만들어지고 setTheme() 이 그 위를 덮는다.
       생성부에서 '현재 테마' 를 읽으면 안 된다 — 값이 흔들린다. */
  chrome: {
    bg:      { dark:"#0a0d13", light:"#dfe3ea" },   /* 큰 지도 배경 */
    bgMini:  { dark:"#0a0d13", light:"#e8ebef" },   /* 미니맵 배경. 라이트만 다르다 */
    /* 스코프 밖 가리개.
       ★ 라이트에서 흰색(#eef1f5)을 쓰면 지면보다 '밝아서' 죽은 영역으로 안 읽힌다.
         #b8c0cc(대비 1.36)는 밖이 무거워 시선을 뺏었고 #d8dce2(1.08)는 티가 안 났다. */
    mask:    { dark:"#05070b", light:"#ccd2da" },
    /* 동명동 경계. 안과 밖을 가르는 유일한 선이라 라이트에서 더 진하게 간다. */
    bnd:     { dark:"#5c6b82", light:"#4a5568" },
    /* 건물 3D 층수 램프. flo 1 · 3 · 6 · 12 에 대응하는 네 값이다. */
    bldRamp: { dark:["#1d2430","#2b3545","#3b4759","#4d5a6f"],
               light:["#d3d9e2","#c3cad6","#b2bbc9","#9fa9ba"] },
    /* 미니맵 '지금 보는 영역' 사각형. 테마를 안 탄다(양쪽 배경에서 다 읽힌다).
       ★ 값이 blocked 와 같지만 **파생이 아니다.** 판정색을 바꿔도 이건
         따라가면 안 된다 — 여기 빨강은 '판정' 이 아니라 '현재 위치' 다.
         모르는 것을 아는 척 묶지 않는다(원칙 ⑥). */
    view:     "#ff4d3d",
    /* 어두운 배경 위 얇은 빨강은 도로망에 묻힌다. 테두리를 먼저 깔고 그 위에 얹는다. */
    viewHalo: { dark:"#000000", light:"#ffffff" },
  },
'''

# ── ③ verdict.js 에 유도 정본을 심는다 ──────────────────────────
VJS_ANCHOR = ("export const vColor = k => (S.lightTheme ? VERDICT[k].cl : VERDICT[k].c);\n")

VJS_BLOCK = '''export const vColor = k => (S.lightTheme ? VERDICT[k].cl : VERDICT[k].c);

/* MapLibre 판정색 match 식. **유도의 정본이다.**
   ★ 2026-09-11 (B3). `layers/segments.js` 와 `ui/minimap.js` 가 똑같은 식을
     각자 조립하고 있었다. 판정이 하나 늘면 두 곳을 고쳐야 하고, 한 곳만
     고치면 미니맵과 큰 지도가 다른 색이 된다 — 같은 구간인데 색이 다르면
     화면이 거짓말을 한다.
   ★ 소비자를 하나씩 고치지 않고 유도를 정본으로 만든다(HANDOFF 원칙 ⑤).

   pick 은 판정키 → 색배열. 기본은 현재 테마(`vColor`)이고, 레이어를 만들 때는
   다크 고정(`k => VERDICT[k].c`)을 넘긴다. 지도는 항상 다크로 만들어지고
   setTheme() 이 그 위를 덮기 때문이다. */
export const verdictMatch = (pick = vColor) => [
  "match", ["get", "verdict"],
  "blocked",  `rgb(${pick("blocked")})`,
  "needs_cv", `rgb(${pick("needs_cv")})`,
  "clear",    `rgb(${pick("clear")})`,
  `rgb(${pick("unknown")})`,
];

/* 레이어 생성 시점용. 테마를 안 탄다. */
export const vDark = k => VERDICT[k].c;
'''

EDITS: list[tuple[str, str, str, str]] = [
    ("web/config.js", CFG_ANCHOR, CFG_BLOCK, "  chrome: {"),
    ("web/js/verdict.js", VJS_ANCHOR, VJS_BLOCK, "export const verdictMatch"),

    # ── mask.js — 생성부가 CONFIG.chrome 를 읽는다 ───────────
    ("web/js/layers/mask.js",
     'import { S } from "../state.js";\n',
     'import { CONFIG } from "../config-access.js";\nimport { S } from "../state.js";\n\n'
     "/* 크롬 색 정본은 config.js 의 chrome 이다. 생성은 다크로 하고\n"
     "   setTheme() 이 그 위를 덮는다(ui/theme.js). */\n"
     "const CH = CONFIG.chrome;\n",
     "const CH = CONFIG.chrome;"),
    ("web/js/layers/mask.js",
     '    paint:{"fill-color":"#05070b","fill-opacity":.42}});\n',
     '    paint:{"fill-color":CH.mask.dark,"fill-opacity":.42}});\n',
     '"fill-color":CH.mask.dark,"fill-opacity":.42'),
    ("web/js/layers/mask.js",
     '    paint:{"fill-color":"#05070b","fill-opacity":.9}});\n',
     '    paint:{"fill-color":CH.mask.dark,"fill-opacity":.9}});\n',
     '"fill-color":CH.mask.dark,"fill-opacity":.9'),
    ("web/js/layers/mask.js",
     '    paint:{"line-color":"#5c6b82","line-width":1.4,"line-dasharray":[3,2],"line-opacity":.75}});\n',
     '    paint:{"line-color":CH.bnd.dark,"line-width":1.4,"line-dasharray":[3,2],"line-opacity":.75}});\n',
     '"line-color":CH.bnd.dark,"line-width":1.4'),
    ("web/js/layers/mask.js",
     '      "fill-extrusion-color":["interpolate",["linear"],["get","flo"],\n'
     '        1,"#1d2430", 3,"#2b3545", 6,"#3b4759", 12,"#4d5a6f"],\n',
     '      "fill-extrusion-color":["interpolate",["linear"],["get","flo"],\n'
     "        1,CH.bldRamp.dark[0], 3,CH.bldRamp.dark[1],\n"
     "        6,CH.bldRamp.dark[2], 12,CH.bldRamp.dark[3]],\n",
     "1,CH.bldRamp.dark[0]"),

    # ── theme.js — 전환부도 같은 정본을 읽는다 ───────────────
    ("web/js/ui/theme.js",
     'import { vColor } from "../verdict.js";\n',
     'import { vColor } from "../verdict.js";\n\n'
     "/* 크롬 색 정본. 생성부(layers/mask.js · ui/minimap.js)와 같은 것을 본다. */\n"
     "const CH = CONFIG.chrome;\n",
     "const CH = CONFIG.chrome;"),
    ("web/js/ui/theme.js",
     '  S.map.setPaintProperty("bg","background-color", light ? "#dfe3ea" : "#0a0d13");\n',
     '  S.map.setPaintProperty("bg","background-color", light ? CH.bg.light : CH.bg.dark);\n',
     "light ? CH.bg.light : CH.bg.dark"),
    ("web/js/ui/theme.js",
     '    light ? ["interpolate",["linear"],["get","flo"],1,"#d3d9e2",3,"#c3cad6",6,"#b2bbc9",12,"#9fa9ba"]\n'
     '          : ["interpolate",["linear"],["get","flo"],1,"#1d2430",3,"#2b3545",6,"#3b4759",12,"#4d5a6f"]);\n',
     "    ((r)=>[\"interpolate\",[\"linear\"],[\"get\",\"flo\"],1,r[0],3,r[1],6,r[2],12,r[3]])(\n"
     "      light ? CH.bldRamp.light : CH.bldRamp.dark));\n",
     "light ? CH.bldRamp.light : CH.bldRamp.dark"),
    ("web/js/ui/theme.js",
     '    S.map.setPaintProperty(l,"fill-color", light ? "#ccd2da" : "#05070b");\n',
     '    S.map.setPaintProperty(l,"fill-color", light ? CH.mask.light : CH.mask.dark);\n',
     "light ? CH.mask.light : CH.mask.dark"),
    ("web/js/ui/theme.js",
     '  S.map.setPaintProperty("bnd-l","line-color",   light ? "#4a5568" : "#5c6b82");\n',
     '  S.map.setPaintProperty("bnd-l","line-color",   light ? CH.bnd.light : CH.bnd.dark);\n',
     "light ? CH.bnd.light : CH.bnd.dark"),

    # ── minimap.js — 생성부 4색 · 크롬 · match 식 ────────────
    ("web/js/ui/minimap.js",
     'import { vColor } from "../verdict.js";\n',
     'import { vColor, vDark, verdictMatch } from "../verdict.js";\n\n'
     "/* 크롬 색 정본. 큰 지도(layers/mask.js)와 같은 것을 본다. */\n"
     "const CH = CONFIG.chrome;\n",
     "const CH = CONFIG.chrome;"),
    ("web/js/ui/minimap.js",
     '      layers:[ {id:"mbg",type:"background",paint:{"background-color":"#0a0d13"}},\n',
     '      layers:[ {id:"mbg",type:"background",paint:{"background-color":CH.bgMini.dark}},\n',
     '"background-color":CH.bgMini.dark'),
    ("web/js/ui/minimap.js",
     '      paint:{"line-color":"#5c6b82","line-width":1,"line-dasharray":[2,1.5]}});\n',
     '      paint:{"line-color":CH.bnd.dark,"line-width":1,"line-dasharray":[2,1.5]}});\n',
     '"line-color":CH.bnd.dark,"line-width":1,'),
    ("web/js/ui/minimap.js",
     '      paint:{"line-color":["match",["get","verdict"],\n'
     '        "blocked","#ff4d3d","needs_cv","#ffab2e","clear","#4ad18f","#5a6272"],\n'
     '        "line-width":1.3,"line-opacity":.9}});\n',
     "      /* ★ 머리말의 약속을 생성부도 지킨다 — 판정 4색은 큰 지도와 같은 값이다.\n"
     "         vDark 는 다크 고정. 지도는 다크로 만들어지고 styleMiniTheme() 이 덮는다. */\n"
     '      paint:{"line-color":verdictMatch(vDark),\n'
     '        "line-width":1.3,"line-opacity":.9}});\n',
     "verdictMatch(vDark)"),
    ("web/js/ui/minimap.js",
     '      paint:{"fill-color":"#ff4d3d","fill-opacity":.20}});\n',
     '      paint:{"fill-color":CH.view,"fill-opacity":.20}});\n',
     '"fill-color":CH.view'),
    ("web/js/ui/minimap.js",
     '      paint:{"line-color":"#000000","line-width":5,"line-opacity":.55,"line-blur":1}});\n',
     '      paint:{"line-color":CH.viewHalo.dark,"line-width":5,"line-opacity":.55,"line-blur":1}});\n',
     '"line-color":CH.viewHalo.dark'),
    ("web/js/ui/minimap.js",
     '      paint:{"line-color":"#ff4d3d","line-width":2.6}});\n',
     '      paint:{"line-color":CH.view,"line-width":2.6}});\n',
     '"line-color":CH.view,"line-width":2.6'),
    ("web/js/ui/minimap.js",
     '  const light = S.lightTheme, rgb = k => `rgb(${vColor(k)})`;\n',
     "  const light = S.lightTheme;\n",
     "  const light = S.lightTheme;\n"),
    ("web/js/ui/minimap.js",
     '  S.miniMap.setPaintProperty("mbg","background-color", light ? "#e8ebef" : "#0a0d13");\n',
     '  S.miniMap.setPaintProperty("mbg","background-color", light ? CH.bgMini.light : CH.bgMini.dark);\n',
     "light ? CH.bgMini.light : CH.bgMini.dark"),
    ("web/js/ui/minimap.js",
     '    S.miniMap.setPaintProperty("mroute-l","line-color",["match",["get","verdict"],\n'
     '      "blocked",rgb("blocked"),"needs_cv",rgb("needs_cv"),"clear",rgb("clear"),rgb("unknown")]);\n',
     '    S.miniMap.setPaintProperty("mroute-l","line-color", verdictMatch());\n',
     '"line-color", verdictMatch());'),
    ("web/js/ui/minimap.js",
     '    S.miniMap.setPaintProperty("mbnd-l","line-color", light ? "#4a5568" : "#5c6b82");\n',
     '    S.miniMap.setPaintProperty("mbnd-l","line-color", light ? CH.bnd.light : CH.bnd.dark);\n',
     "light ? CH.bnd.light : CH.bnd.dark"),
    ("web/js/ui/minimap.js",
     '    S.miniMap.setPaintProperty("mview-halo","line-color", light ? "#ffffff" : "#000000");\n',
     '    S.miniMap.setPaintProperty("mview-halo","line-color", light ? CH.viewHalo.light : CH.viewHalo.dark);\n',
     "light ? CH.viewHalo.light : CH.viewHalo.dark"),

    # ── segments.js — 같은 유도를 쓴다 ───────────────────────
    ("web/js/layers/segments.js",
     'import { vColor } from "../verdict.js";\n',
     'import { verdictMatch } from "../verdict.js";\n',
     "import { verdictMatch }"),
    ("web/js/layers/segments.js",
     '  return ["match",["get","verdict"],\n'
     '    "blocked", rgb(vColor("blocked")), "needs_cv", rgb(vColor("needs_cv")),\n'
     '    "clear",   rgb(vColor("clear")),   rgb(vColor("unknown"))];\n',
     "  /* 유도의 정본은 verdict.js 다. 미니맵도 같은 것을 쓴다(B3 2026-09-11). */\n"
     "  return verdictMatch();\n",
     "  return verdictMatch();\n"),
]


def _literals(text: str) -> list[str]:
    """남아 있는 색 리터럴. 전후 대조용."""
    return sorted(re.findall(r"#[0-9a-fA-F]{6}\b", text))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    by_file: dict[str, list[tuple[str, str, str]]] = {}
    for rel, old, new, done in EDITS:
        by_file.setdefault(rel, []).append((old, new, done))

    changed = skipped = 0
    for rel, pairs in by_file.items():
        p = ROOT / rel
        if not p.exists():
            sys.exit(f"★ {rel} 이 없다. 저장소 루트에서 돌리고 있나")
        before = p.read_text(encoding="utf-8")
        text = before
        for old, new, done in pairs:
            if done in text:
                skipped += 1
                continue
            if text.count(old) != 1:
                sys.exit(f"★ {rel} — 대상이 {text.count(old)}곳이다. 멈춘다.\n{old!r}")
            text = text.replace(old, new)
            changed += 1
        if text == before:
            print(f"  = {rel}  이미 적용됨")
            continue
        print(f"  {'✓' if a.apply else '·'} {rel}"
              f"   색 리터럴 {len(_literals(before))} → {len(_literals(text))}")
        if a.apply:
            p.write_text(text, encoding="utf-8")

    print(f"\n변경 {changed} · 건너뜀 {skipped}"
          + ("" if a.apply else "   ★ dry-run. --apply 를 붙일 것"))
    if a.apply:
        print("\n다음 — node tools/js_graph_check.mjs; node tools/web_boot_check.mjs")
        print("       ★ 부팅 스모크가 필수 레이어 16개를 다 만드는지 본다.")
        print("         색을 잘못 끼우면 MapLibre 가 레이어 생성에서 죽는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
