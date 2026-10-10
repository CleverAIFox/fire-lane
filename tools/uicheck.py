#!/usr/bin/env python3
"""
uicheck.py — **사람 눈이 마지막 관문이던 자리를 도구가 문다.**

    uv run python tools/uicheck.py --split     소스: 관제와 내비가 다른 화면인가
    uv run python tools/uicheck.py --build     빌드본: 지금 화면이 지금 코드에서 나왔는가
    uv run python tools/uicheck.py --selftest  ★ 판별식이 두 결함을 실제로 가르는가

── 왜 생겼나 (DECISIONS §310) ─────────────────────────────────
2026-09-29, 전수 73단계가 **통과 73 · 실패 0** 으로 끝났다. 그 초록 위에서 사람이
화면을 열었더니 **관제가 아예 안 떠 있었다.** 루트도 내비, `/navi/` 도 내비였다.

원인은 열흘 묵은 빌드본이었다. `tools/serve.py` 는 루트에 `window.__FL_VIEW="ops"`
를 제대로 박아 보냈는데, `web/navi/dist` 가 **그 값을 읽는 코드가 들어오기 전에
지어진 것**이라 번들이 그 말을 몰랐다. 서버는 맞고 받는 쪽이 낡았다.

★ 그런데 결함은 묵은 빌드가 아니다. **아무 관문도 그것을 안 봤다는 것**이 결함이다.

    verify.sh 73단계 중 web/navi/dist 를 보는 단계        0
    .gitignore 에 web/navi/dist/                          있다 (추적 안 된다)
    tests/test_embeddable.py                              serve.py 의 **글자**만 본다
    verify.sh 마지막 줄                                   "WebGL 은 스크립트가 못 본다.
                                                           사람이 눈으로 확인할 것"

마지막 줄이 이 저장소에 남은 마지막 「사람이 본다」였고, 거기가 정확히 샜다.
1족(무음 통과)이고, 그것을 잡으려고 지은 장치들 **바깥**에 있었다.

★ 배운 것을 여기 적어 둔다 — **관문 밖에 남긴 한 가지가 관문 전체의 상한이다.**
  73개가 초록이어도 74번째가 사람이면, 그 체계의 신뢰도는 사람의 주의력이다.

── 두 축 ───────────────────────────────────────────────────────
① `--split`  **관제와 내비가 다른 화면인가.** 소스만 본다 — 어디서나 돈다.
   ㉠ 두 앱이 배타 부품을 쓴다(선언표)
   ㉡ **두 화면이 공유하는 지도 층 수**를 센다 → 래칫(내려가는 쪽으로만)

   ★ ㉡ 이 이 도구의 본체다. 사람이 「닮았다」고 말한 것의 실측이 이 수다.
     지금 17이고, 그중 셋이 건물(12,663동 전부 3D) · 셋이 전 도로 판정색 ·
     셋이 라벨이다. 내비는 주행 화면인데 GIS 바탕을 통째로 깔고 그 위에 경로를
     얹는다. 층을 내리는 일은 배치 P 가 하고, **되돌아오는 것을 여기가 막는다.**

② `--build`  **지금 화면이 지금 코드에서 나왔는가.** 빌드본이 있어야 돈다.
   ㉠ 빌드본이 소스보다 새것인가          ← 오늘의 결함
   ㉡ 입구에 주입 자리(`</head>`)가 있는가
   ㉢ 진입 번들이 전환 깃발을 **읽는가**   ← 오늘의 결함
   ㉣ 서버를 실제로 띄워 `/` 와 `/navi/` 가 다른 문서인가

IN    web/navi/src/** · web/navi/dist/** · tools/serve.py
OUT   표준출력
PARAM 없다. 문턱은 `SHARED_LAYERS` 하나이고 래칫이다
밖    **화면이 예쁜가는 안 본다.** 색·자리·글자 크기는 사람의 판단이다.
      **WebGL 이 실제로 그려지는가는 안 본다** — 브라우저가 있어야 하고, 이 저장소는
      아직 브라우저를 안 들인다. 여기가 드는 것은 그 앞의 둘이다: 「무엇을 그리라고
      시켰는가」(소스)와 「지금 코드가 화면에 갔는가」(빌드본). 오늘의 결함은
      **둘 다 브라우저 없이 잡힌다.**
      **관제 화면의 내용이 옳은가는 안 본다** — 판정값은 `verdictsim` 소관이다.
      **번들 크기는 안 본다**(PLAN W13-3).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "navi" / "src"
DIST = ROOT / "web" / "navi" / "dist"
#: 층 명세가 사는 파일들. **둘 다 읽는다** — 하나만 읽으면 옮겨간 층이 사라진다.
#: ★ 2026-09-29 (§311). `opsLayers.ts` 가 갈라져 나온 날, 이 도구가 `layers.ts` 만
#:   보고 있었다. 공유 수는 우연히 그대로였고(바탕 층이 안 옮겨갔다) **그래서 더
#:   나빴다** — 초록인 채로 그물에 구멍이 났다. 아래 자기검사가 그것을 문다.
LAYER_FILES = ("layers.ts", "opsLayers.ts")
LAYERS = SRC / "components" / "layers.ts"

#: 전환 깃발. `serve.py` 가 루트에 박고, 번들이 읽어야 한다. 한쪽만 있으면 안 된다.
FLAG = "__FL_VIEW"

#: 화면 → 그 화면**만** 쓰는 부품. 한쪽이 남의 것을 쓰면 두 화면이 섞이는 중이다.
#: ★ 목록이 아니라 **경계**다. 새 부품은 여기 안 적어도 되고, 적힌 것이 넘어가면 운다.
EXCLUSIVE = {
    # ★ 2026-10-05 (DECISIONS §400). `SearchPanel` → `WaitPanel`.
    #   목적지 검색은 운전석에서 **사라졌다** — 관제가 정한다. 그 자리에
    #   선 것이 대기 화면이고, 경계로서 같은 일을 한다(관제가 쓰면 운다).
    "App.tsx": ("NaviMap", "WaitPanel", "DevBar"),
    "OpsApp.tsx": ("OpsMap", "SegCard"),
}

#: 두 지도가 부르는 층 묶음. `layers.ts` 의 export 함수 이름이다.
NAVI_FNS = ("baseLayers", "altRouteLayers", "routeLayers", "markerLayers", "stationLayers")
OPS_FNS = ("baseLayers", "hillshadeLayer", "opsHistoryLayers", "opsSegLayers",
           "opsOverlayLayers", "markerLayers", "stationLayers")

# ── 래칫 ────────────────────────────────────────────────────────
# ★ 2026-09-29 (§310). 오늘 실측 그대로 박는다 — 래칫의 값어치는 「지금보다
#   나빠지지 않는다」이지 「지금이 옳다」가 아니다. 17은 옳지 않다.
#   baseLayers 9 + markerLayers 6 + stationLayers 2 = 17.
SHARED_LAYERS = 12

#: 화면에 뜨는 **한글 글자 수**. 내려가는 쪽이다.
#:
#: ★ 2026-10-09 (DECISIONS §445 · PLAN #143 닫힘). 그 행의 자가 **틀려 있었다** —
#:   `web/navi/src/ui` 폴더의 **줄 수**(22파일 2,061줄)를 들었다. 그런데 행이
#:   묻던 것은 「관제 화면이 너무 많이 보여준다」이고, 행을 쓴 사람의 뜻은
#:   **「쓸데없는 텍스트가 많다」**였다. 그래픽·레이아웃 코드는 분모가 아니고
#:   (그쪽은 많아도 된다 — 위계를 주는 일이다) 파일마다의 길이는 `sizecheck` 가
#:   이미 든다. 즉 **폴더 합계 줄 수를 세는 관문은 없었고**, 없는 자로 적힌 수는
#:   래칫이 아니라 메모였다. 그래서 자를 바꿨다.
#: ★ 세는 것 — 주석을 뺀 소스의 **문자열 리터럴 중 한글이 든 것**의 글자 수.
#:   한글을 조건으로 거는 이유는 그것이 **사람에게 읽히는 말**의 표식이기
#:   때문이다(class 이름 · id · 색 코드는 안 걸린다).
#: ★ 실측 — §441 이 「읽는 법」 시트를 만들며 ui 가 3,992자였고, §445 가 그
#:   시트를 걷고 색마다의 한 줄 설명과 뺄셈 식을 지워 **2,877자**가 됐다.
#:   늘면 운다 — 「패널에 문장을 달았다」가 그 뜻이다.
#: 밖  **무엇이 쓸데없는 말인가는 안 고른다** — 그것은 사람이 본다. 여기는 양만 센다.
# ★ 2026-10-09 (DECISIONS §445 · PLAN #143 닫힘). 2877 → **3867. 자를 고쳤다.**
#   종전 자는 `ui/` 의 **문자열 리터럴**만 셌다 — 관제 본체(`OpsApp.tsx`)가 범위
#   밖이었고 JSX 텍스트는 아예 안 세어서, 설명을 걷어도 수가 안 움직였다.
#   새 자는 `web/navi/src` 전부에서 **주석을 뗀 한글 글자**다. 단위가 달라졌으므로
#   두 수를 비교하지 마라. 같은 자로 재면 이 판에서 **4694 → 3867**(827자 · 17.6%)
#   줄었다 — 화면 안 사용설명서 한 장과 범례의 설명 두 덩이다.
# ★ 2026-10-10 (DECISIONS §448 · PLAN #145). 3867 → **3445. 자를 또 고쳤다** —
#   줄머리 주석만 떼고 **줄 끝 주석**은 안 뗐다. 그 422자가 화면 글자로 세어지고
#   있었고, 그러면 이 래칫이 「사유를 줄 끝에 적지 마라」가 된다. 화면 말은 한
#   글자도 안 줄었다 — **세는 법만 바로잡았다.** 3867 과 비교하지 마라.
UI_TEXT = 3445

#: `tools/ratchet.py` 가 **줄었을 때만** 이 수를 고쳐 적는다(§309).
RATCHETS = {"SHARED_LAYERS": "down", "UI_TEXT": "down"}

_HANGUL = re.compile(r"[가-힣]")


def screen_text(src: str) -> str:
    """그 소스가 **사람에게 내는 말**. 주석을 떼고 남은 한글이다.

    ★ 주석을 먼저 떼지 않으면 사유를 길게 적을수록 수가 늘어난다 — 그러면
      이 래칫이 「주석을 줄여라」가 되고, 그것은 이 저장소가 바라는 것의 반대다.

    ★ 2026-10-09 정정 (DECISIONS §445 · PLAN #143). 종전에는 **문자열
      리터럴만** 집었다. 화면 말의 과반은 JSX 텍스트 노드라 그 자가 **본 것을
      안 세고 있었다** — 관제 범례에서 설명 두 덩이를 걷었는데 수가 **한 글자도
      안 움직였다.** 자가 틀리면 그 수는 수가 아니다(§436-8 과 같은 자리).
      그래서 **문법을 덜 따지고 글자를 센다**: 주석을 떼고 남은 한글 전부.
      코드 식별자는 ASCII 라 안 걸리고, JSX 텍스트도 문자열도 다 걸린다.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"^\s*//.*$", "", src, flags=re.M)
    # ★ 2026-10-10 (DECISIONS §448). **줄 끝 주석**도 뗀다. 종전에는 줄머리
    #   주석만 떼서 `[2.4, 1.0],   // 성긴 파선` 의 뒷말이 화면 글자로 세어졌다 —
    #   그러면 이 래칫이 「사유를 줄 끝에 적지 마라」가 되고, 그것은 §445-7 이
    #   고친 것과 **같은 방향의 틀림**이다(자가 안 보는 것을 세거나 보는 것을
    #   안 센다). `https://` 처럼 앞이 `:` 인 것은 주석이 아니라 안 뗀다.
    src = re.sub(r"(?<!:)//[^\n]*$", "", src, flags=re.M)
    return "".join(_HANGUL.findall(src))


def ui_text_chars(root: Path = SRC) -> int:
    """화면이 내는 한글 글자 수. **한 곳에서만 센다.**

    ★ 범위가 `ui/` 하나가 아니다 — 관제 화면 본체(`OpsApp.tsx`)와 지도 조각
      (`components/`)이 밖이었고, 사람이 가리킨 것은 **관제**였다. 화면이 말을
      내는 자리는 `web/navi/src` 전부다.
    """
    n = 0
    for p in sorted(root.rglob("*.ts*")):
        if p.name.endswith(".d.ts"):
            continue
        n += len(screen_text(p.read_text(encoding="utf-8")))
    return n


#: 층의 집. `LAYER` 선언이 여기 산다 — 값이 아니라 **순서**를 본다.
_THEME = SRC / "ui" / "opsTheme.ts"
_LAYER_BLOCK = re.compile(r"export const LAYER = \{(.*?)\n\} as const;", re.S)
_LAYER_ROW = re.compile(r"(\w+):\s*\{[^}]*background:\s*(\"#[0-9a-fA-F]{6}\"|D\.\w+)")
#: `D` 토큰 표 — `D.card` 꼴을 풀려면 값을 알아야 한다. **베끼지 않는다.**
_D_BLOCK = re.compile(r"export const D = \{(.*?)\n\};", re.S)
_D_ROW = re.compile(r"(\w+):\s*\"(#[0-9a-fA-F]{6})\"")


def _lum(hex6: str) -> float:
    """WCAG 상대휘도. **색이 아니라 밝기**를 재는 자다."""
    def ch(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex6[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def layers_declared(txt: str) -> list[tuple[str, str]]:
    """선언된 (층 이름, 배경색). 블록이 없으면 **빈 목록**이다.

    ★ `D.card` 꼴을 **같은 파일의 `D` 표에서 푼다.** 값을 여기 베끼면 토큰을
      고칠 때 이 자가 따라오지 않는다(족 2).
    """
    m = _LAYER_BLOCK.search(txt)
    if not m:
        return []
    dm = _D_BLOCK.search(txt)
    tok = dict(_D_ROW.findall(dm.group(1))) if dm else {}
    out = []
    for name, raw in _LAYER_ROW.findall(m.group(1)):
        v = raw.strip('"') if raw.startswith('"') else tok.get(raw.split(".", 1)[1], "")
        if v:
            out.append((name, v))
    return out


def tier_faults(rows: list[tuple[str, str]], order: tuple[str, ...] = ("act", "pick", "idle")) -> list[str]:
    """층의 **휘도가 선언한 순서대로 내려가는가.** 순수 함수다.

    ★ 왜 순서만 보나 — 값은 디자인이고 사람이 고른다. 기계가 지킬 수 있는 것은
      「`act` 가 `pick` 보다 밝고 `pick` 이 `idle` 보다 밝다」 하나이고, 그것이
      깨지면 **계층이 거꾸로 읽힌다.** 교안 p.25 Note 3 이 말하는 것이 그 순서다.
    """
    got = dict(rows)
    if len(rows) != len(order) or set(got) != set(order):
        return [f"`LAYER` 선언이 {sorted(got)} 다 — {list(order)} 셋이어야 한다 "
                "(블록이 사라지면 이 축이 조용히 통과한다)"]
    lums = [(k, _lum(got[k])) for k in order]
    bad = []
    for (a, la), (b, lb) in zip(lums, lums[1:], strict=False):
        if la <= lb:
            bad.append(f"`{a}`({la:.4f}) 가 `{b}`({lb:.4f}) 보다 안 밝다 — "
                       "계층이 거꾸로 읽힌다(DECISIONS §445)")
    return bad


def ratchet_values() -> dict[str, int]:
    """공유 층의 지금 수 · 화면 글자 수. **판정은 `split()` 소관**이다."""
    return {"SHARED_LAYERS": len(shared_layers()), "UI_TEXT": ui_text_chars()}


# ── ① 소스 ──────────────────────────────────────────────────────
def layer_ids() -> dict[str, list[str]]:
    """층 명세 파일들의 export 함수 → 그 함수가 내는 층 id 들."""
    src = "\n".join((SRC / "components" / f).read_text(encoding="utf-8")
                    for f in LAYER_FILES if (SRC / "components" / f).is_file())
    marks = [(m.start(), m.group(1)) for m in re.finditer(r"^export function (\w+)", src, re.M)]
    marks.append((len(src), ""))
    out: dict[str, list[str]] = {}
    # ★ `strict=False` 다. 뒤 목록이 **일부러** 하나 짧다 — 마지막 함수의 끝을
    #   파일 끝으로 잡으려고 보초를 하나 붙였고, 그 보초가 마지막 짝의 오른쪽이다.
    for (a, name), (b, _) in zip(marks, marks[1:], strict=False):
        ids = re.findall(r'\bid:\s*"([^"]+)"', src[a:b])
        if ids:
            out[name] = ids
    return out


def navi_off() -> list[str]:
    """주행 화면이 끄는 층. **선언은 `layers.ts` 의 `NAVI_OFF` 하나다**(§311).

    ★ 이 도구가 제 목록을 따로 들면 그 순간 정본이 둘이 된다. 실물이 끄는 것과
      관문이 뺀다고 믿는 것이 갈리면, 수는 내려가는데 화면은 그대로인 날이 온다.
    """
    src = LAYERS.read_text(encoding="utf-8")
    m = re.search(r"export const NAVI_OFF\s*=\s*\[(.*?)\]\s*as const", src, re.S)
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


def shared_layers() -> list[str]:
    """**두 화면에 똑같이 깔리는 층.** 이 도구가 재는 것이 이 수다.

    내비가 끄는 것은 안 센다 — 꺼진 층은 화면에 없다. 다만 **끈다고 선언만 하고
    실제로 안 끄는 것**은 아래 `split()` 이 따로 문다(`NaviMap` 이 그 목록을
    실제로 도는가).
    """
    per = layer_ids()
    navi = {i for f in NAVI_FNS for i in per.get(f, ())} - set(navi_off())
    ops = {i for f in OPS_FNS for i in per.get(f, ())}
    return sorted(navi & ops)


def _uses(app: str, part: str) -> bool:
    """그 앱이 그 부품을 **쓰는가**. import 만으로는 안 본다 — 써야 화면에 나온다."""
    t = (SRC / app).read_text(encoding="utf-8")
    return bool(re.search(rf"<{part}\b", t))


#: 문서가 마커 표를 드는 자리. 절 제목으로 찾는다 — **줄 번호로 안 든다**(§217-5).
MARKER_SEC = "### 10-7."


def documented_markers() -> list[str]:
    """`MASTER §10-7` 표의 **층 칸**이 드는 층 id 들.

    ── 왜 이것을 재나 (DECISIONS §337) ─────────────────────────
    §320-1 에서 그 절이 **걷어낸 지도를 서술하고 있었다.** 원기둥 마커 서술과
    가로등 두 줄이 여드레 동안 살아 있었고, 검사 스물이 전부 초록이었다.
    그 절 자신이 이렇게 적었다 —

        「문서가 있다고 적은 마커가 실제로 그려지는가」를 보는 검사는 저장소에
        없었다. 지금도 없다 … **그 대조는 다음 배치의 일이고, 그때까지는
        도장이 유일한 방어다.**

    여기가 그 대조다. 도장은 「다시 보라」를 시키고 사람이 읽어야 풀리는데,
    이것은 **사람 없이 운다.**

    ★ 표의 **둘째 칸만** 읽는다. 첫 칸은 사람이 읽는 이름(「소화전」)이고 넷째
      칸의 백틱은 함수 이름(`hydrantIcon()`)이라 층이 아니다. 칸을 안 가르면
      함수 이름이 층으로 세어지고, 그러면 **영원히 빨갛다.**
    """
    doc = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    i = doc.find(MARKER_SEC)
    if i < 0:
        return []
    j = doc.find("\n### ", i + 1)
    out: list[str] = []
    for line in doc[i:j if j > 0 else len(doc)].splitlines():
        if not line.startswith("|"):
            continue
        cols = line.split("|")
        if len(cols) < 4 or set(cols[1].strip()) <= {"-", ":", " "}:
            continue                      # 표 머리와 구분선
        out += re.findall(r"`([^`]+)`", cols[2])
    return sorted(set(out))


def marker_faults() -> list[str]:
    """③ 문서가 적은 마커 층이 **실제로 그려지는가.**"""
    said = documented_markers()
    if not said:
        return [f"`MASTER {MARKER_SEC.strip('# .')}` 의 마커 표를 못 읽었다 — "
                "절이 옮겼거나 표 꼴이 바뀌었다. **이 검사가 빈 그물이다**"]
    real = {i for v in layer_ids().values() for i in v}
    if not real:
        return ["층 id 를 하나도 못 읽었다 — 훑기가 `layers.ts` 와 갈렸다"]
    return [f"`MASTER {MARKER_SEC.strip('# .')}` 이 층 `{s}` 를 적는데 **그리는 코드가 없다** — "
            "없는 화면을 설명하는 문서다(§320-1 이 여드레 들고 있던 그 꼴)"
            for s in said if s not in real]


def split() -> list[str]:
    """빨간불 사유들. 비면 초록."""
    bad = []

    # ㉧ 화면 글자 수 — **양방향**. 늘면 「패널에 문장을 달았다」이고,
    #   줄면 기록을 내려야 한다(안 내리면 다시 늘어도 안 운다 · §445).
    now = ui_text_chars()
    if now > UI_TEXT:
        bad.append(f"화면 글자 {now}자 > 기록 {UI_TEXT}자 — 패널에 설명이 다시 "
                   "들어왔다. 한계·뜻의 집은 `MASTER §15-4` 다")
    elif now < UI_TEXT:
        bad.append(f"화면 글자 {now}자 < 기록 {UI_TEXT}자 — 줄었다. "
                   f"`tools/uicheck.py` 의 `UI_TEXT` 를 {now} 으로 내려라")

    # ㉨ 층의 휘도 순서 (§445 · #143) — 값은 사람이 고르고 **순서는 기계가 든다**
    bad += tier_faults(layers_declared(_THEME.read_text(encoding="utf-8")))

    # ㉠ 전환 자체가 살아 있는가
    main = (SRC / "main.tsx").read_text(encoding="utf-8")
    if FLAG not in main:
        bad.append(f"`main.tsx` 가 `{FLAG}` 를 안 읽는다 — 루트가 관제를 못 띄운다")
    if not re.search(r'===\s*"ops"', main):
        bad.append("`main.tsx` 에 `view === \"ops\"` 분기가 없다 — 두 화면이 안 갈린다")

    # ㉡ 배타 부품
    for app, parts in EXCLUSIVE.items():
        other = next(a for a in EXCLUSIVE if a != app)
        for p in parts:
            if not _uses(app, p):
                bad.append(f"{app} 이 `<{p}>` 를 안 쓴다 — 선언이 낡았거나 화면이 비었다")
            if _uses(other, p):
                bad.append(f"{other} 가 `<{p}>` 를 쓴다 — **{app} 전용이다.** 두 화면이 섞인다")

    # ㉢ 선언한 것을 실제로 끄는가 — 선언만 하고 안 끄면 수만 내려간다
    off = navi_off()
    if not off:
        bad.append("`layers.ts` 에 `NAVI_OFF` 선언이 없다 — 주행 표출 예산이 사라졌다")
    navimap = (SRC / "components" / "NaviMap.tsx").read_text(encoding="utf-8")
    if off and "NAVI_OFF" not in navimap:
        bad.append("`NaviMap` 이 `NAVI_OFF` 를 안 쓴다 — **선언만 하고 안 끄고 있다.**\n"
                   "       그러면 공유 층 수만 내려가고 화면은 그대로다")
    allids = {i for v in layer_ids().values() for i in v}
    for o in off:
        if o not in allids:
            bad.append(f"`NAVI_OFF` 의 `{o}` 가 실재하지 않는 층이다 — 죽은 선언은 "
                       "**수만 줄이는 말**이 된다")
    opsmap = (SRC / "components" / "OpsMap.tsx").read_text(encoding="utf-8")
    if "NAVI_OFF" in opsmap:
        bad.append("`OpsMap` 이 `NAVI_OFF` 를 쓴다 — 그것은 **주행** 화면의 예산이다")

    # ㉣ 공유 층 — 이 도구의 본체
    sh = shared_layers()
    if len(sh) > SHARED_LAYERS:
        bad.append(f"두 화면이 공유하는 지도 층이 늘었다 — 선언 {SHARED_LAYERS} · 실측 {len(sh)}\n"
                   f"       {' '.join(sh)}\n"
                   "       내비는 주행 화면이다. 바탕을 통째로 깔면 밤에 아무것도 못 읽는다")
    elif len(sh) < SHARED_LAYERS:
        bad.append(f"공유 층이 {len(sh)} 으로 줄었다 — "
                   f"`uv run python tools/ratchet.py --write` 로 조여라 (선언 {SHARED_LAYERS})")

    # ㉤ 문서가 적은 마커가 실제로 그려지는가 (§337)
    bad += marker_faults()

    # ㉥ 강조가 **색을 안 쓴다** (§441)
    bad += emphasis_uses_no_color()
    return bad


#: 색 리터럴. `#rgb` · `#rrggbb` · `rgb(` · `hsl(`.
COLOR_LIT = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


def emphasis_faults(src: str | None) -> list[str]:
    """**강조는 색 채널을 안 쓴다.**  (2026-10-09 · DECISIONS §441)

    ── 왜 세나 ────────────────────────────────────────────────
    관제의 **색 채널은 판정 넷이 이미 다 먹었다**(통행 가능 · 확인 필요 · 통행
    불가 · 미측정). 「이 칸을 봐라」를 색으로 하면 다섯째 색이 생기고, 그 순간
    판정 넷의 뜻이 흐려진다. 교안이 그 자리에서 쓰는 채널을 명시한다 —
    『3 Theoretical issue 3』 p.25 Note 3, **강조는 휘도 대비로 한다.**

    ★ 그래서 `ui/motion.ts` 에는 **투명도와 시간만** 있어야 한다. 한 줄 넣기는
      쉽고(`color: "#f00"`) 지운 사람은 없다 — 그래서 센다.
    ★ **빈 그물을 막는다** — 파일이 없거나 비면 통과가 아니라 실패다.
    """
    if src is None:
        return ["`ui/motion.ts` 가 없다 — 강조 채널 선언이 사라졌다(§441)"]
    if "flpulse" not in src:
        return ["`ui/motion.ts` 에 맥박 선언이 없다 — 빈 그물이다"]
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", src, flags=re.S)
    hits = sorted(set(COLOR_LIT.findall(body)))
    if hits:
        return [f"`ui/motion.ts` 가 색을 쓴다 — {hits}\n"
                "       강조는 휘도와 움직임으로 한다. 색 채널은 판정 넷의 것이다(§441)"]
    return []


def emphasis_uses_no_color() -> list[str]:
    """실물을 읽어 `emphasis_faults` 에 넘긴다. **읽기만 한다.**

    ★ 2026-10-09. 판별식을 순수 함수로 뗐다 — 자기검사가 **실물 파일을 고쳤다가
      되돌리는** 꼴이었고, 그러면 그 짧은 사이에 트리가 더럽다. `selftests.py`
      는 도구를 여럿 돌리고 배달 기계는 「추적 파일에 변경이 있다」를 본다 —
      흔드는 쪽과 재는 쪽이 겹치면 안 된다(§398-6 과 같은 규율).
      이 저장소의 표준 꼴이기도 하다: `judge()` 가 순수라 시험이 합성으로 부른다.
    """
    f = SRC / "ui" / "motion.ts"
    return emphasis_faults(f.read_text(encoding="utf-8") if f.is_file() else None)


# ── ② 빌드본 ────────────────────────────────────────────────────
def _newest(d: Path, *suf: str) -> float:
    return max((p.stat().st_mtime for p in d.rglob("*")
                if p.is_file() and (not suf or p.suffix in suf)), default=0.0)


def _serve_says() -> tuple[str, str] | str:
    """서버를 띄워 `/` 와 `/navi/` 를 받아 온다. 못 띄우면 사유를 돌려준다."""
    port = 8399
    p = subprocess.Popen(  # noqa: S603 — 트리 안의 도구를 인자 없이 부른다
        [sys.executable, str(ROOT / "tools" / "serve.py"), str(port)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        got = {}
        for path in ("/", "/navi/"):
            last = ""
            for _ in range(25):                       # 최대 5초. 뜨는 즉시 나간다
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=1) as r:  # noqa: S310 — 방금 띄운 로컬 서버다
                        got[path] = r.read().decode("utf-8", "replace")
                        break
                except (urllib.error.URLError, OSError) as e:
                    last = str(e)
                    time.sleep(0.2)
            else:
                return f"로컬 서버가 안 뜬다 ({path}) — {last}"
        return got["/"], got["/navi/"]
    finally:
        p.terminate()
        p.wait(timeout=5)


def build() -> list[str]:
    bad = []
    entry = DIST / "index.html"
    if not entry.is_file():
        return ["빌드본이 없다 — `cd web/navi && npm run build`\n"
                "       ★ 건너뛸 사유가 아니다. 다만 `verify.sh` 는 이 앞 단계에서\n"
                "         **직접 짓는다** — 여기서 이 줄이 보이면 그 단계가 빠진 것이다"]

    # ㉠ 신선도 — 오늘의 결함
    d_at, s_at = _newest(DIST), _newest(SRC)
    if d_at < s_at:
        older = int((s_at - d_at) / 86400)
        bad.append(f"**빌드본이 소스보다 낡았다** ({older}일). 화면은 지금 코드가 아니다\n"
                   "       cd web/navi && npm run build\n"
                   "       ★ 2026-09-29 에 이것이 열흘 묵은 채로 73/73 초록을 통과했다")

    # ㉡ 주입 자리
    html = entry.read_text(encoding="utf-8")
    if "</head>" not in html:
        bad.append("입구에 `</head>` 가 없다 — `serve.py` 가 전환 깃발을 박을 자리가 없다")

    # ㉢ 번들이 깃발을 읽는가 — 오늘의 결함
    js = [p for p in (DIST / "assets").glob("*.js")] if (DIST / "assets").is_dir() else []
    if not any(FLAG in p.read_text(encoding="utf-8", errors="ignore") for p in js):
        bad.append(f"진입 번들에 `{FLAG}` 가 없다 — **서버가 박아도 화면이 그 말을 모른다**\n"
                   "       이것이 2026-09-29 에 관제가 안 뜬 사유다. 다시 지어라")

    # ㉣ 두 주소가 다른 문서인가
    r = _serve_says()
    if isinstance(r, str):
        bad.append(r)
    else:
        root, navi = r
        tag = f'{FLAG}="ops"'
        if tag not in root:
            bad.append(f"루트가 `{tag}` 를 안 낸다 — `/` 가 관제가 아니다")
        if tag in navi:
            bad.append(f"`/navi/` 가 `{tag}` 를 낸다 — 내비가 관제로 뜬다")
    return bad


# ── 자기검사 ────────────────────────────────────────────────────
def selftest() -> int:
    """판별식은 **옆집**에 산다 — `tools/uichecktest.py`.

    ★ 함수 안에서 끌어온다. 위에서 끌어오면 `uichecktest → uicheck → uichecktest`
      로 맞물린다(§445-1 에서 `mutate` 가 한 것과 같다).
    """
    from uichecktest import selftest as _s  # noqa: PLC0415  맞물림을 끊는다
    return _s()


def main() -> int:
    ap = argparse.ArgumentParser(description="관제와 내비가 다른 화면인가 · 화면이 지금 코드인가")
    ap.add_argument("--split", action="store_true", help="소스만 본다 (어디서나)")
    ap.add_argument("--build", action="store_true", help="빌드본을 본다 (빌드가 있어야 한다)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    bad: list[str] = []
    if a.split or not a.build:
        sh = shared_layers()
        print(f"화면 분리 — 공유 지도 층 {len(sh)} · 래칫 {SHARED_LAYERS}"
              f" · 화면 글자 {ui_text_chars()}자 · 래칫 {UI_TEXT}자")
        bad += split()
    if a.build:
        print(f"빌드본 — {DIST.relative_to(ROOT)}")
        bad += build()

    if bad:
        print("\n✗ 화면")
        for b in bad:
            print(f"   {b}")
        return 1
    print("✓ 화면")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
