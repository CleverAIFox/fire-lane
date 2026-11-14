#!/usr/bin/env python3
"""
themecheck.py — **「면이 들어갔다」가 아니라 「화면에서 구분된다」를 문다.**

    uv run python tools/themecheck.py             소스에서 두 화면의 바탕 면 · 판정 색 · 층 짝을 문다
    uv run python tools/themecheck.py --selftest  ★ 판별식이 합성 입력에서 실제로 우는가

── 왜 생겼나 (2026-11-13 · DECISIONS §775) ─────────────────────
빈 공간을 「45% → 2.3%」(칠해진 면적)로 세어 행을 닫으려 했다. 그 수는 거짓이 아니었으나
사람이 배포본을 열자 **어두운 화면에는 층이 아예 없었고 밝은 화면은 바탕 면이 배경과 ΔE76 1.1~4.6**
이라 안 보였다. 면적은 「칠해졌나」를 묻고 **「배경과 구분되나」를 안 물었다.** 이 도구가 그 둘째 물음이다.

── 무엇을 무나 ────────────────────────────────────────────────
① 바탕 면(토지이용 8갈래)이 **배경과 구분되는가** — 두 화면 각각 ΔE76 ≥ `LAND_DE_MIN`.
② 판정 색(`navi_graph.json` 의 `style.*.color`)이 바탕 면 위에서도 **배경 위 값의 `VERDICT_RETAIN_PCT`% 이상**을
   지키는가 — 바탕을 진하게 하면 판정이 먼저 묻힌다. 구분만 올리고 판정을 죽이는 길을 막는다.
③ **두 화면이 같은 면 층을 깔고 있는가** — 관제는 내비의 `landuseLayers()` 명세를 받아 색만 바꾼다. 그 배선이
   끊기면(층이 한 화면에서만 빠지면) 운다. 색표는 갈래마다 밝은 쪽 · 어두운 쪽이 **다 있어야** 한다.
④ **라벨 · 지점 층의 비대칭이 선언되어 있는가** — 두 화면은 일이 달라 같은 층을 안 깐다(주행 화면은 상가 이름 · 지점 핀을
   안 둔다). 그 비대칭은 `ROLES` 에 사유와 함께 있어야 하고, **선언 없는 새 라벨 층은 운다**(어느 한 화면에서만 조용히
   빠지는 일을 막는다).

PARAM `LAND_DE_MIN` · `VERDICT_RETAIN_PCT` — 둘 다 **올라가는 쪽으로만** 래칫이다(`tools/ratchet.py`).
IN    web/navi/src/ui/tokens.ts · components/OpsMap.tsx · components/layers.ts 등(소스) · web/data/navi_graph.json
OUT   표준출력 · 종료 코드
밖    **화면이 예쁜가는 안 본다**(수가 하한을 넘는다는 것이 구분된다는 보증이다 · 어느 색이 좋은지는 사람의 판단).
      **WebGL 에 실제로 그려졌는가는 안 본다** — 그것은 브라우저 스모크(`web/navi/e2e`)와 사람 눈이다.
      **건물 · 도로의 색은 안 본다**(바탕 면만 — 건물은 층 순서와 높이로 갈린다).
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import srgb  # 색 변환은 한 집이다(sRGB 감마 · L*a*b*) — 스크립트 폴더가 경로에 있다
import uicheck  # 층 id · `NAVI_OFF` 를 읽는 정본은 그 도구다

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "navi" / "src"
NAVI_GRAPH = ROOT / "web" / "data" / "navi_graph.json"

#: 바탕 면이 배경과 **구분된다**고 보는 ΔE76 하한(두 화면 · 갈래마다). 6 은 보도(7.3)보다 한 단 약한 값이다.
LAND_DE_MIN = 6
#: ★ 2026-11-14 (DECISIONS §778 D). 어두운 화면은 **따로** 하한을 둔다 — 같은 ΔE76 도 어두운 바탕에서는 덜 보인다(사람이 6 짜리를 「여전히 약하다」고 했다). 12 는 명도를 올리지 않고 **채도로** 닿는다
#:   (명도를 올리면 판정 색 대비가 깎여 `VERDICT_RETAIN_PCT` 가 먼저 운다 — 실측: 명도로 ΔE 10 이면 유지 80.9% · 채도로 ΔE 12 면 85.0%).
LAND_DE_MIN_DARK = 12
#: 판정 색이 바탕 면 위에서 배경 위 대비의 몇 %를 지켜야 하나(정수 %). 바탕을 진하게 할 때 판정이 묻히는 것을 막는다.
VERDICT_RETAIN_PCT = 84

#: `tools/ratchet.py` 가 읽는다. 둘 다 올라가는 쪽으로만 — 내리면 「구분된다」의 뜻이 약해진다.
RATCHETS = {"LAND_DE_MIN": "up", "LAND_DE_MIN_DARK": "up", "VERDICT_RETAIN_PCT": "up"}

#: 토지이용 갈래 — 두 화면이 **같은 표**를 쓴다(`tokens.ts` 의 `land*` 키 · 관제 `LAND_DARK` 의 `[MAP.land*]` 키).
LAND_KEYS = ("landDaeji", "landPlaza", "landGreen", "landInst", "landForest", "landFarm", "landWater", "landPaved")

#: 라벨 · 지점 · 맥락 층의 두 화면 몫 — (관제, 내비) = 켜짐 / 끔 / 없음 / 토글 + 사유. **여기 없는 라벨 층은 운다.**
#: ★ 비대칭은 일의 차이다(DECISIONS §311 · §444). 어느 쪽이 정본이 아니다 — 이 표가 정본이다.
ROLES: dict[str, tuple[str, str, str]] = {
    "lbl-road":     ("켜짐", "켜짐", "도로 이름 — 둘 다 필요하다"),
    "lbl-station":  ("켜짐", "켜짐", "안전센터 이름 — 둘 다 필요하다"),
    "lbl-bldg":     ("켜짐", "끔",   "건물 이름 12,663 — 주행 화면은 읽을 것을 줄인다(`NAVI_OFF` · §311)"),
    "lbl-poi":      ("켜짐", "끔",   "상가 이름 2,106 — 같은 사유(`NAVI_OFF`)"),
    "lbl-landmark": ("켜짐", "없음", "지점 이름(광주 인공지능사관학교 등) — 운전석에서는 목적지를 안 고른다(§444 · #148)"),
    "landmark-ring": ("켜짐", "없음", "지점 핀의 고리 — 위와 같다"),
    "ctx":          ("토글", "켜짐", "과속방지턱 · 카메라 · 보호구역 — 관제는 범례 토글(기본 꺼짐) · 주행 화면은 늘 켠다"),
}


# ── 색 읽기 ─────────────────────────────────────────────────────
def to_rgb(c: str) -> tuple[int, int, int]:
    """`#rrggbb` 또는 `rgb(r,g,b)`."""
    c = c.strip()
    if c.startswith("#"):
        return srgb.hex_rgb(c)
    m = re.findall(r"\d+", c)
    return (int(m[0]), int(m[1]), int(m[2]))


def contrast(a: str, b: str) -> float:
    return srgb.lum_ratio(to_rgb(a), to_rgb(b))


def de(a: str, b: str) -> float:
    return srgb.delta_e(to_rgb(a), to_rgb(b))


# ── 소스에서 값을 읽는다 ─────────────────────────────────────────
def light_palette(tokens_src: str) -> tuple[str, dict[str, str]]:
    """(밝은 배경, {갈래키: 색}). `tokens.ts` 의 `MAP`."""
    m = re.search(r"bg:\s*\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", tokens_src)
    if not m:
        raise SystemExit("★ tokens.ts 에서 MAP.bg 를 못 읽었다")
    bg = f"rgb({m.group(1)},{m.group(2)},{m.group(3)})"
    land = dict(re.findall(r"\b(land[A-Z]\w*):\s*\"(#[0-9a-fA-F]{6})\"", tokens_src))
    return bg, land


def dark_palette(ops_src: str) -> tuple[str, dict[str, str]]:
    """(어두운 배경, {갈래키: 색}). `OpsMap.tsx` 의 `DARK.bg` 와 `LAND_DARK` 의 `[MAP.land*]` 키."""
    m = re.search(r"\bbg:\s*\"(#[0-9a-fA-F]{6})\"", ops_src)
    if not m:
        raise SystemExit("★ OpsMap.tsx 에서 DARK.bg 를 못 읽었다")
    land = dict(re.findall(r"\[MAP\.(land[A-Z]\w*)\]:\s*\"(#[0-9a-fA-F]{6})\"", ops_src))
    return m.group(1), land


def verdict_colors() -> dict[str, str]:
    st = json.loads(NAVI_GRAPH.read_text(encoding="utf-8"))["style"]
    return {k: v["color"] for k, v in st.items()}


# ── 판별식(순수 · 합성 입력으로 직접 부른다) ──────────────────────
def land_faults(name: str, bg: str, land: dict[str, str], de_min: float) -> list[str]:
    """① 갈래마다 배경과 ΔE76 ≥ de_min · 갈래 표가 빠짐없이 있다."""
    bad = []
    for k in LAND_KEYS:
        if k not in land:
            bad.append(f"{name}: 갈래 `{k}` 의 색이 없다 — 두 화면이 같은 갈래 표를 써야 한다")
            continue
        d = de(land[k], bg)
        if d < de_min:
            bad.append(f"{name}: `{k}` {land[k]} 가 배경 {bg} 과 ΔE76 {d:.1f} < {de_min:g} — **화면에서 안 구분된다**")
    return bad


def retention(bg: str, land: dict[str, str], verdict: dict[str, str]) -> tuple[float, str]:
    """② 판정 색 × 갈래의 (바탕 면 위 대비 / 배경 위 대비) 의 최솟값과 그 자리."""
    worst, where = math.inf, ""
    for v, vc in verdict.items():
        base = contrast(vc, bg)
        for k, c in land.items():
            if k not in LAND_KEYS:
                continue
            r = contrast(vc, c) / base
            if r < worst:
                worst, where = r, f"{v} × {k}"
    return worst, where


def verdict_faults(name: str, bg: str, land: dict[str, str], verdict: dict[str, str], pct: float) -> list[str]:
    worst, where = retention(bg, land, verdict)
    if worst * 100 < pct:
        return [f"{name}: 판정 색이 바탕 면 위에서 배경 위 대비의 {worst * 100:.1f}% 로 묻힌다({where}) — 하한 {pct:g}%"]
    return []


def wiring_faults(ops_src: str) -> list[str]:
    """③ 관제가 내비의 `landuseLayers()` 명세를 받아 `bg` 바로 뒤에 `ops-` 접두로 끼우는가."""
    bad = []
    if "landuseLayers(" not in ops_src and "withLanduse(" not in ops_src:
        bad.append("관제(OpsMap.tsx)가 내비의 토지이용 명세(`landuseLayers`/`withLanduse`)를 안 받는다 — 어두운 화면에 바탕 면이 없다(2026-11-13 의 결함 그 자체)")
    if '"ops-"' not in ops_src:
        bad.append("관제의 토지이용 층 id 에 `ops-` 접두가 없다 — 내비와 같은 id 가 되어 공유 층 래칫이 틀어진다")
    if not re.search(r'findIndex\(\(l\) => l\.id === "bg"\)\s*\+\s*1', ops_src):
        bad.append("관제가 토지이용 층을 `bg` 바로 뒤에 끼우지 않는다 — 길 · 건물 아래가 아니면 바탕이 길을 덮는다")
    return bad


#: 바탕 면이 **그 아래**여야 하는 층(건물 · 길 · 보도 · 판정 색 층) — `bg` · `hillshade` 만 바탕 면 밑에 올 수 있다.
UNDER_LAND_OK = ("bg", "hillshade")


def stack_faults(base_ids: list[str], insert_after: str, land_types: list[str]) -> list[str]:
    """⑤ 바탕 면이 건물 · 길 · 판정 색 **위로 올라오지 않는가**(DECISIONS §778 C). 면은 `insert_after` 바로 뒤에 낀다 — 그 앞에 `bg`(와 지형 음영) 말고 층이 있으면 면이 그 층을 **덮는다**.
    면의 종류가 `fill-extrusion` 이어도 운다(바탕이 3D 로 솟아 건물을 삼킨다)."""
    bad = []
    if insert_after not in base_ids:
        return [f"바탕 면을 끼우는 기준 층 `{insert_after}` 가 층 목록에 없다"]
    above = [i for i in base_ids[:base_ids.index(insert_after) + 1] if i not in UNDER_LAND_OK]
    if above:
        bad.append(f"바탕 면이 `{', '.join(above)}` 위에 깔린다 — 건물 · 길 · 판정 색을 덮는다(면은 그 아래여야 한다)")
    if any(t == "fill-extrusion" for t in land_types):
        bad.append("바탕 면에 `fill-extrusion`(3D 돌출)이 있다 — 면은 `fill` 이어야 한다")
    return bad


def land_stack() -> tuple[list[str], str, list[str]]:
    """실물: `baseLayers` 의 층 순서 · `withLanduse` 가 끼우는 기준 층 · `landuseLayers` 가 내는 층의 종류."""
    import re as _re
    src = (SRC / "components" / "layers.ts").read_text(encoding="utf-8")
    base = uicheck.layer_ids().get("baseLayers", [])
    m = _re.search(r"export function withLanduse.*?findIndex\(\(l\) => l\.id === \"([\w-]+)\"\)", src, _re.S)
    block = src[src.index("export function landuseLayers"):src.index("export function withLanduse")]
    return base, (m.group(1) if m else ""), _re.findall(r'type: "([\w-]+)"', block)


def land_state() -> str:
    """바탕 면이 지금 켜져 있나(되돌린 상태를 말해 준다 — 실패가 아니다)."""
    navi = (SRC / "components" / "NaviMap.tsx").read_text(encoding="utf-8")
    ops = (SRC / "components" / "OpsMap.tsx").read_text(encoding="utf-8")
    return ("내비 " + ("켜짐" if "withLanduse(" in navi else "꺼짐")
            + " · 관제 " + ("꺼짐" if "const LAND_ON = false" in ops else "켜짐"))


def role_faults(label_ids: set[str], navi_off: set[str], roles: dict[str, tuple[str, str, str]]) -> list[str]:
    """④ 라벨 · 지점 · 맥락 층마다 두 화면 몫이 선언돼 있고, `끔` 선언이 `NAVI_OFF` 와 맞는가."""
    bad = []
    for i in sorted(label_ids):
        if i not in roles:
            bad.append(f"층 `{i}` 의 두 화면 몫이 `themecheck.ROLES` 에 없다 — 어느 화면에서 보이는지 사유와 함께 적어라")
    for i, (_o, n, _why) in roles.items():
        if (n == "끔") != (i in navi_off):
            bad.append(f"`{i}` 의 내비 몫이 「{n}」 인데 `NAVI_OFF` 와 어긋난다 — 한쪽만 고쳐졌다")
    return bad


# ── 실물 ────────────────────────────────────────────────────────
def label_ids() -> set[str]:
    """층 명세 파일들이 내는 라벨 · 지점 · 맥락 층 id(`lbl-*` · `landmark-*` · `ctx`)."""
    ids: set[str] = set()
    for lst in uicheck.layer_ids().values():
        ids |= {i for i in lst if i.startswith(("lbl-", "landmark-")) or i == "ctx"}
    return ids


def navi_off() -> set[str]:
    return set(uicheck.navi_off())


def measure() -> dict[str, float]:
    tk = (SRC / "ui" / "tokens.ts").read_text(encoding="utf-8")
    ops = (SRC / "components" / "OpsMap.tsx").read_text(encoding="utf-8")
    lbg, lland = light_palette(tk)
    dbg, dland = dark_palette(ops)
    v = verdict_colors()
    de_light = min(de(c, lbg) for k, c in lland.items() if k in LAND_KEYS)
    de_dark = min(de(c, dbg) for k, c in dland.items() if k in LAND_KEYS)
    ret = min(retention(lbg, lland, v)[0], retention(dbg, dland, v)[0])
    return {"LAND_DE_MIN": de_light, "LAND_DE_MIN_DARK": de_dark, "VERDICT_RETAIN_PCT": ret * 100}


def ratchet_values() -> dict[str, int]:
    """`tools/ratchet.py` 용 — 정수로 **내림**(선언은 하한이라 내림이 안전한 쪽이다)."""
    return {k: math.floor(v) for k, v in measure().items()}


def faults() -> list[str]:
    tk = (SRC / "ui" / "tokens.ts").read_text(encoding="utf-8")
    ops = (SRC / "components" / "OpsMap.tsx").read_text(encoding="utf-8")
    lbg, lland = light_palette(tk)
    dbg, dland = dark_palette(ops)
    v = verdict_colors()
    bad = land_faults("밝은 화면(내비)", lbg, lland, LAND_DE_MIN) + land_faults("어두운 화면(관제)", dbg, dland, LAND_DE_MIN_DARK)
    bad += verdict_faults("밝은 화면(내비)", lbg, lland, v, VERDICT_RETAIN_PCT)
    bad += verdict_faults("어두운 화면(관제)", dbg, dland, v, VERDICT_RETAIN_PCT)
    bad += wiring_faults(ops)
    bad += role_faults(label_ids(), navi_off(), ROLES)
    bad += stack_faults(*land_stack())
    m = measure()
    if math.floor(m["LAND_DE_MIN_DARK"]) > LAND_DE_MIN_DARK:
        bad.append(f"어두운 화면 바탕 면 구분이 ΔE76 {m['LAND_DE_MIN_DARK']:.1f} 로 선언 {LAND_DE_MIN_DARK} 보다 높다 — `uv run python tools/ratchet.py --write` 로 올려라")
    if math.floor(m["LAND_DE_MIN"]) > LAND_DE_MIN:
        bad.append(f"바탕 면 구분이 ΔE76 {m['LAND_DE_MIN']:.1f} 로 선언 {LAND_DE_MIN} 보다 높다 — `uv run python tools/ratchet.py --write` 로 올려라")
    if math.floor(m["VERDICT_RETAIN_PCT"]) > VERDICT_RETAIN_PCT:
        bad.append(f"판정 색 유지가 {m['VERDICT_RETAIN_PCT']:.1f}% 로 선언 {VERDICT_RETAIN_PCT} 보다 높다 — `tools/ratchet.py --write` 로 올려라")
    return bad


# ── 자기검사 — 합성 입력으로 실제로 우는가 ─────────────────────────
def selftest() -> int:
    bg, land = "rgb(232,228,218)", {k: "#c8d9b9" for k in LAND_KEYS}
    v = {"clear": "rgb(74,209,143)", "needs_cv": "rgb(255,171,46)", "blocked": "rgb(255,77,61)", "unknown": "rgb(90,98,114)"}
    ok = True

    def expect(label: str, got: list[str], want_fail: bool) -> None:
        nonlocal ok
        failed = bool(got)
        good = failed == want_fail
        ok &= good
        print(f"  {'✓' if good else '✗'} {label} — {'울었다' if failed else '조용했다'}{'' if good else ' (기대와 반대)'}")

    print("themecheck 자기검사")
    expect("정상 입력은 조용하다", land_faults("밝", bg, land, 6) + verdict_faults("밝", bg, land, v, 80), False)
    expect("하한과 같은 값은 조용하다(경계 — `<` 이지 `<=` 가 아니다)", land_faults("밝", bg, land, de("#c8d9b9", bg)), False)
    # ① 바탕을 배경색과 같게 — 구분이 안 되면 울어야 한다
    same = dict(land, landDaeji="rgb(232,228,218)")
    expect("바탕 면을 배경색과 같게(밝은 화면)", land_faults("밝", bg, same, 6), True)
    dbg = "#0b1220"
    expect("어두운 화면의 면을 어두운 배경과 같게", land_faults("어두", dbg, dict(land, landGreen=dbg), 6), True)
    # ② 구분만 올리고 판정을 죽인다 — 면을 판정 색 가까이로 밀면 울어야 한다
    near_verdict = {k: "#ffb43a" for k in LAND_KEYS}      # needs_cv(주황) 와 휘도가 거의 같아 대비가 무너진다
    expect("면이 판정 색과 휘도가 가까울 때", verdict_faults("밝", bg, near_verdict, v, 84), True)
    # ③ 한 화면에서만 층을 뺀다
    expect("관제가 내비의 토지이용 명세를 안 받는다", wiring_faults('"ops-" findIndex((l) => l.id === "bg") + 1'), True)
    expect("관제 배선이 온전하면 조용하다", wiring_faults('landuseLayers() "ops-" findIndex((l) => l.id === "bg") + 1'), False)
    expect("갈래 하나의 색이 한 화면에서 빠졌다", land_faults("어두", dbg, {k: "#182235" for k in LAND_KEYS if k != "landFarm"}, 6), True)
    # ④ 선언 없는 새 라벨 층 · 사유와 NAVI_OFF 어긋남
    expect("선언 없는 새 라벨 층", role_faults({"lbl-new"}, {"lbl-bldg"}, ROLES), True)
    expect("끔 선언인데 NAVI_OFF 에 없다", role_faults(set(ROLES), {"lbl-poi"}, ROLES), True)
    expect("선언과 NAVI_OFF 가 맞으면 조용하다", role_faults(set(ROLES), {"lbl-bldg", "lbl-poi"}, ROLES), False)
    # ⑤ 바탕 면이 건물 · 길 위로 올라오는가 — 합성 층 목록
    ids = ["bg", "sidewalk", "road-area", "bldg"]
    expect("바탕 면이 `bg` 바로 뒤(건물 아래)면 조용하다", stack_faults(ids, "bg", ["fill", "line"]), False)
    expect("녹지를 건물 위 레이어에 놓으면 운다", stack_faults(ids, "bldg", ["fill"]), True)
    expect("길 위에 놓으면 운다", stack_faults(ids, "road-area", ["fill"]), True)
    expect("바탕 면에 3D 돌출이 들어가면 운다", stack_faults(ids, "bg", ["fill", "fill-extrusion"]), True)
    # 선언한 하한이 실물보다 높으면 실제 트리가 운다 — 하한을 몰래 올려도 이 자기검사가 잡는다(변이: 하한 6 → 7 이 살아남았었다)
    m = measure()
    got = (floors_ok(m, LAND_DE_MIN, VERDICT_RETAIN_PCT) and math.floor(m["LAND_DE_MIN_DARK"]) >= LAND_DE_MIN_DARK and not floors_ok(m, LAND_DE_MIN + 10, VERDICT_RETAIN_PCT)
           and not floors_ok(m, LAND_DE_MIN, VERDICT_RETAIN_PCT + 50))   # 둘 중 하나만 틀려도 운다
    ok &= got
    print(f"  {'✓' if got else '✗'} 선언한 하한이 실측 안이다 — ΔE {m['LAND_DE_MIN']:.1f} ≥ {LAND_DE_MIN} · 어두운 ΔE {m['LAND_DE_MIN_DARK']:.1f} ≥ {LAND_DE_MIN_DARK} · 유지 {m['VERDICT_RETAIN_PCT']:.1f}% ≥ {VERDICT_RETAIN_PCT}%")
    # 종료 코드의 두 갈래 — 성공은 0 · 실패는 1 (변이: main 의 성공 반환 0 → 1 이 살아남았었다)
    good = exit_code([]) == 0 and exit_code(["x"]) == 1
    ok &= good
    print(f"  {'✓' if good else '✗'} 종료 코드 — 조용하면 0 · 울면 1")
    print("✓ 자기검사 통과" if ok else "✗ 자기검사 실패")
    return exit_code([] if ok else ["selftest"])


def floors_ok(m: dict[str, float], de_min: float, pct: float) -> bool:
    """선언한 두 하한이 실측 안인가(둘 다)."""
    return math.floor(m["LAND_DE_MIN"]) >= de_min and math.floor(m["VERDICT_RETAIN_PCT"]) >= pct


def exit_code(bad: list[str]) -> int:
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="두 화면의 바탕 면이 화면에서 구분되는가")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    m = measure()
    print(f"바탕 면 ΔE76 최소 {m['LAND_DE_MIN']:.1f}(하한 {LAND_DE_MIN}) · 어두운 {m['LAND_DE_MIN_DARK']:.1f}(하한 {LAND_DE_MIN_DARK}) · 판정 색 유지 최소 {m['VERDICT_RETAIN_PCT']:.1f}%(하한 {VERDICT_RETAIN_PCT}%)"
          f" · 라벨 층 몫 선언 {len(ROLES)} · 바탕 면 {land_state()}")
    bad = faults()
    if bad:
        print("\n✗ 화면 구분")
        for b in bad:
            print(f"  · {b}")
        return exit_code(bad)
    print("✓ 화면 구분")
    return exit_code(bad)


if __name__ == "__main__":
    raise SystemExit(main())
