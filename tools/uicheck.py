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
    "App.tsx": ("NaviMap", "SearchPanel", "DevBar"),
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

#: `tools/ratchet.py` 가 **줄었을 때만** 이 수를 고쳐 적는다(§309).
RATCHETS = {"SHARED_LAYERS": "down"}


def ratchet_values() -> dict[str, int]:
    """공유 층의 지금 수. **판정은 `split()` 소관**이다."""
    return {"SHARED_LAYERS": len(shared_layers())}


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
    return bad


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
    """★ 「0건이 청결인가 죽음인가」(§230). 판별식이 두 결함을 실제로 가르는가."""
    fails = []
    per = layer_ids()
    if not per:
        fails.append("층을 하나도 못 읽었다 — 빈 그물이다")
    if "baseLayers" not in per:
        fails.append("`baseLayers` 를 못 찾았다 — 공유 층 계산이 0 이 된다")
    # ★ 파일이 갈라져도 그물이 덮는가. 한 파일만 읽으면 여기서 걸린다(§311).
    for fn in NAVI_FNS + OPS_FNS:
        if fn not in per:
            fails.append(f"`{fn}` 을 못 찾았다 — 층 명세 파일이 갈라졌는데 "
                         "`LAYER_FILES` 에 안 넣었을 수 있다")
    for f in LAYER_FILES:
        if not (SRC / "components" / f).is_file():
            fails.append(f"`{f}` 가 없다 — 선언이 낡았다")

    sh = shared_layers()
    if not sh:
        fails.append("공유 층이 0 이다 — 두 지도가 `baseLayers` 를 같이 부르는데 0 일 수 없다")
    # ★ 주행에도 값이 있어 **남긴** 것들. 이것이 사라지면 세는 법이 틀린 것이다.
    for want in ("bg", "seg-road", "lbl-road", "hydrant"):
        if want not in sh:
            fails.append(f"공유 층에 `{want}` 가 없다 — 세는 법이 틀렸다")
    # ★ 반대 방향 — 끈 것이 공유에 남아 있으면 빼기가 안 먹은 것이다(§311).
    off = set(navi_off())
    if not off:
        fails.append("`NAVI_OFF` 를 못 읽었다 — 빼기가 통째로 안 먹는다")
    for gone in ("lbl-poi", "lbl-bldg", "seg-tint"):
        if gone in sh:
            fails.append(f"`{gone}` 가 아직 공유다 — 내비가 그것을 안 끈다")
        if gone not in off:
            fails.append(f"`{gone}` 가 `NAVI_OFF` 에서 빠졌다 — 주행 예산이 헐거워졌다")

    # 배타 판별식이 **거짓을 거짓이라 하는가**
    if _uses("OpsApp.tsx", "NaviMap"):
        fails.append("관제가 내비 지도를 쓴다고 나온다 — 실물과 다르면 판별식이 틀렸다")
    if not _uses("App.tsx", "NaviMap"):
        fails.append("내비가 `<NaviMap>` 을 안 쓴다고 나온다 — 판별식이 못 찾는다")

    # 신선도 판별식이 **반대 방향도 잡는가**
    if _newest(SRC) <= 0:
        fails.append("소스 시각을 못 읽는다 — 신선도 판정이 늘 통과한다")

    for f in fails:
        print(f"  ✗ {f}")
    # ★ ③ 마커 대조 (§337). **문서를 읽기는 하는가** — 못 읽으면 언제나 초록이다.
    said = documented_markers()
    if not said:
        fails.append(f"`MASTER {MARKER_SEC.strip('# .')}` 의 마커 표를 못 읽는다 — 빈 그물이다")
    # ★ 칸을 가르는가. 둘째 칸이 층이고 넷째 칸의 백틱은 **함수 이름**이다 —
    #   안 가르면 `hydrantIcon()` 이 층으로 세어져 영원히 빨갛다.
    if any(s.endswith("()") for s in said):
        fails.append(f"표의 함수 이름을 층으로 센다 — {[s for s in said if s.endswith('()')]}")
    if "hydrant" not in said:
        fails.append("표에서 `hydrant` 를 못 찾는다 — 둘째 칸을 안 읽고 있다")
    # ★ 반대 방향 — 없는 층을 적으면 정말 우는가
    if not [s for s in ("streetlight-dot", "lightpole")
            if s not in {i for v in per.values() for i in v}]:
        fails.append("걷어낸 가로등 층이 아직 코드에 있다 — 주입 판별식이 헛돈다")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 19")
    return 1 if fails else 0


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
        print(f"화면 분리 — 공유 지도 층 {len(sh)} · 래칫 {SHARED_LAYERS}")
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
