#!/usr/bin/env python3
"""
naviweight.py — **출동 중에 끊기는 것이 없는가.**

    uv run python tools/naviweight.py             선언 대조 (소스 · 어디서나)
    uv run python tools/naviweight.py --build     빌드본 무게 래칫 (빌드가 있어야 한다)
    uv run python tools/naviweight.py --selftest

── 왜 생겼나 (DECISIONS §312) ──────────────────────────────────
PLAN §13 W13-3 · W13-4 둘이 같은 자리를 가리켰다 — **4G 첫 진입 시간이 곧 출동
시각이고, 지하·산간에서는 그 진입조차 안 된다.**

    W13-3  단일 청크 1,386kB(gzip 392kB). 판정 한 줄을 고쳐도 전부 다시 받는다
    W13-4  글자가 `demotiles.maplibre.org` 에 있다. 오프라인에서 **도로 이름이 사라진다**

둘 다 「무게」의 문제로 보이지만 실은 **의존의 문제**다. 그래서 이 도구가 재는
것도 바이트가 아니라 둘이다 —

    ① 밖에 기대는 것이 몇 개인가        절대 URL 래칫 (내려가는 쪽으로만)
    ② 첫 화면이 받아야 하는 것이 얼마인가  진입 청크 무게 래칫
    ③ 지도 워커가 산출물에 **있고 참조되는가**  (DECISIONS §323)

★ ①이 본체다. 1MB 를 받는 것은 느린 것이고, **못 받는 것은 없는 것**이다.
  출동은 통신이 제일 먼저 끊기는 곳으로 간다.

★ 남은 외부 하나(`api.mapbox.com`)는 **선언한다.** 지도 정합(map matching)은
  없어도 내비가 도는 곁다리이고, 끊기면 그 기능만 죽는다. 지우는 것이 아니라
  「끊겨도 되는 것」으로 적고 그 목록이 늘지 않게 붙든다.

IN    web/navi/src/** · web/navi/index.html · web/navi/dist/**
OUT   표준출력
PARAM 없다. 문턱 둘 다 래칫이고, `EXTERNAL` 만 `ratchet.py` 가 조인다
밖    **바이트를 줄이는 방법은 안 고른다.** 무엇을 쪼갤지는 사람이 정한다 —
      이 도구는 분모만 센다(원칙 ⑥).
      **글자 파일이 옳은가는 안 본다** — `npm run glyphs -- --check` 가 든다.
      **런타임에 만든 URL 은 못 본다.** 문자열을 이어 붙여 만든 주소는 정적으로
      안 보인다 — 그 몫은 서비스 워커의 `url.origin !== location.origin` 이
      막는다(밖은 안 건드린다). 여기가 드는 것은 **소스에 적힌 것**이다.
      **중개자 주소도 못 본다**(2026-10-01 · DECISIONS §343-3). 둘 다 그렇다 —
      ① `wss://` 라 위 정규식(`https?://`)에 안 걸리고, ② 소스에 없다. 빌드가
      `VITE_OPS_URL` 로 **박아 넣는다.** 그 자리를 드는 것은
      `.github/actions/build-navi/action.yml` 이고, 그것이 `wss://` 가 아니면
      빌드를 죽인다. 정규식을 넓히지 않는 이유 — 소스에 없는 값이라 넓혀도
      안 보이고, 넓히면 **본다는 거짓 신호**만 생긴다.
      **어느 청크에 있어야 하는가는 안 본다** — 번들러가 정한다. ③이 묻는 것은
      「산출물 **어딘가**에 있는가」 하나다(§323 이 그 반대로 물어서 죽었다).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAVI = ROOT / "web" / "navi"
DIST = NAVI / "dist"

#: 밖에 기대도 되는 것 — **사유와 함께**. 비우는 것이 목표다.
#: ★ 적는 순간 세어진다. 사유 없는 이름은 선언이 아니다.
#: ★ 2026-10-03 (DECISIONS §366-2). **비었다.** 걷은 하나 — `api.mapbox.com`.
#:   사유가 「없어도 내비가 돈다 (`infra/matching.ts` 가 실패하면 원래 점을
#:   쓴다)」였는데, 그 파일을 **아무도 import 하지 않았다.** 번들에 없는 코드의
#:   런타임 되돌림이 바깥 의존 하나의 근거였다 — 사유가 거짓인 면제다.
#:   그 파일을 지우면서 같이 걷었다. 내비는 이제 **소스에도 바깥 호스트가 없다.**
ALLOWED: dict[str, str] = {}

#: 래칫. 오늘 값. **내려가는 쪽으로만.**
#: ★ 2026-09-29 (§312). 3 → 1. 걷은 둘 — `demotiles.maplibre.org`(글자) ·
#:   `cdn.jsdelivr.net`(글꼴 CSS). 앞은 저장소 안으로 옮겼고(`web/fonts/`),
#:   뒤는 걷었다 — 오프라인에서 그 링크는 어차피 실패하고, 실패한 뒤 쓰이는 것이
#:   기기 글꼴이라 **있으나 없으나 같은 화면**이었다.
EXTERNAL = 0

#: 진입 청크 상한(KB). 첫 화면이 **앱 코드로** 받아야 하는 양이다.
#: ★ 2026-09-29 (§312). 1390 → 150. 지도 엔진과 React 를 갈랐다 — 무게가 준 것이
#:   아니라 **다시 받는 양**이 줄었다. 판정을 고쳐도 maplibre 1MB 는 캐시에 남는다.
#:
#: ★ **2026-09-30. 137 → 138 로 올렸다**(DECISIONS §329). 올리는 것은 이 수의
#:   방향이 아니라 사람이 손으로 올리고 **왜**를 여기 적는다 —
#:
#:   `useVoice` 의 우선순위 사슬(이탈 > 재동기화 > 회전 > 규칙 > 사정 > 판정)을
#:   `domain/voice.ts` 로 내렸다. 값은 **정책**인데 자리가 React 라 물으려면
#:   렌더러가 필요했고, `vitest` 환경이 `node` 다. 정책 하나를 물자고 의존성을
#:   늘리는 대신 정책을 내렸고, 그 대가가 **모듈 경계 하나**다.
#:
#:       raw   140.53KB → 141.01KB   (+0.48)
#:       gzip   47.56KB →  47.75KB   (+0.19)   ← 4G 를 실제로 건너는 쪽
#:
#:   산 것은 그 사슬의 시험 26개다. 이 사슬은 세 번 고쳐졌고 세 번 다 시험이
#:   없었다. 0.19KB 와 「회전 실행 안내가 판정에 밀리는 것을 아무도 못 보는
#:   상태」를 맞바꿨다.
#: ★ 상수를 `export` 에서 내려 접히게도 해 봤다 — **0.02KB 였다.** 는 몫은
#:   상수가 아니라 모듈 경계 자체다. 재 보고 적는다.
#:
#: ★ **2026-10-03. 138 → 141 로 올렸다**(DECISIONS §372-6). 커밋마다 재서
#:   어디서 늘었는지 못박았다 — 짐작으로 올리지 않는다.
#:
#:       §361 뒤   raw 138.14KB · gzip 46.04KB   ← 138 과 같다(초록)
#:       §363      raw 138.83KB · gzip 46.26KB   +0.69 / +0.22
#:       §366      raw 141.23KB · gzip 47.10KB   +2.40 / +0.84
#:       합                                      **+3.09 / +1.06**
#:
#:   §363 이 산 것 — 턴바이턴의 **셋째 방아쇠**(영상 통과폭이 안내에 들어오는
#:   자리). §366 이 산 것 — `domain/reroute.ts`(CV 가 막힘을 보면 경로를 다시
#:   짜는 네 규율)와 `adjacency` 의 CV 가중, 시험 44개.
#:
#:   **4G 에서 건너는 쪽은 gzip 이고 +1.06KB 다.** 실효 10Mbps 로 약 1ms 다 —
#:   이 관문이 막으려는 것은 그 1ms 가 아니라 **아무도 안 보는 사이의 표류**이고,
#:   그래서 수를 올리고 **무엇을 사서 올렸는지**를 적는 것이 규약이다.
#:
#: ★ **이 수는 raw 다**(`entry_kb()` 가 `stat().st_size` 를 KB 로 반올림한다).
#:   §329 가 산문에 `raw 141.01KB` 를 적고 이 상수를 138 로 둔 것은 **단위가
#:   갈린 것**이다 — 그 배치의 빌드와 지금 빌드가 다른 수를 냈다. 지금은
#:   산문의 수와 이 상수가 **같은 측정**이다(둘 다 raw · 둘 다 반올림 전 값 병기).
#:
#: ★ **2026-10-03. 141 → 142 로 올렸다**(PLAN §1 #71). 한 번 더 잰 값이다 —
#:
#:       §366 뒤   raw 141.23KB · gzip 47.10KB
#:       #71       raw 141.61KB · gzip 47.22KB   **+0.38 / +0.12**
#:
#:   산 것 — A* 휴리스틱이 **조율값을 따라간다.** 종전에는 「배수 최솟값이
#:   1.0 이다」가 `graph.ts` 머리말의 **선언**이었고 강제자가 0 이었다. 그
#:   선언이 깨지면 A* 가 최적해를 안 낸다(실측: 배수를 0.2 로 내리고 옛
#:   휴리스틱으로 돌리면 쌍 456 중 **19개가 더 나쁜 답** · 최대 +34.94).
#:   늘어난 0.38KB 는 `minCostFactor` · `pressureIsSane` ·
#:   `minDirectionFactor` · `adjacencyMinFactor` 와 그 WeakMap 이다.
#:
#:   ★ **지금 경로는 한 글자도 안 달라진다.** 하한이 1 이라 휴리스틱이 종전과
#:     같은 값이다. 바뀌는 것은 **누가 배수를 1.0 아래로 내리는 날**이다.
ENTRY_KB = 142

#: ★ `ENTRY_KB` 는 **안 태운다.** `tools/ratchet.py` 의 규약은 「어디서나 잴 수 있는
#:   수」를 전제하는데, 진입 청크는 **빌드본이 있어야** 재진다. 빌드본이 없는 기계
#:   (새 클론 · 배달 검증 작업트리)에서 `ratchet_values()` 가 그 이름을 못 내고,
#:   그러면 래칫 도구가 「이름을 안 낸다」로 운다 — 빈 값을 채워 넣으면 그것은
#:   재지 않은 수를 선언에 적는 것이라 더 나쁘다. 그 수는 `--build` 가 직접 든다.
RATCHETS = {"EXTERNAL": "down"}


def ratchet_values() -> dict[str, int]:
    """실측. **판정은 `check()` 소관**이다."""
    return {"EXTERNAL": len(hosts())}


# ── ① 밖에 기대는 것 ────────────────────────────────────────────
def hosts() -> dict[str, list[str]]:
    """소스가 부르는 **바깥 호스트** → 그것이 적힌 자리들."""
    out: dict[str, list[str]] = {}
    files = [*(NAVI / "src").rglob("*.ts"), *(NAVI / "src").rglob("*.tsx"),
             NAVI / "index.html"]
    for p in files:
        if not p.is_file():
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("*", "//", "<!--")):
                continue          # 주석의 주소는 호출이 아니다
            for m in re.finditer(r"https?://([A-Za-z0-9.-]+)", line):
                # ★ 저장소 밖(시험의 임시 트리)에서도 죽지 않는다 — 자리를 못
                #   적는 것과 **판정을 못 하는 것**은 다르다.
                try:
                    where = p.relative_to(ROOT).as_posix()
                except ValueError:
                    where = p.as_posix()
                out.setdefault(m.group(1), []).append(f"{where}:{n}")
    return out


# ── ② 첫 화면 무게 ──────────────────────────────────────────────
def entry_kb() -> int | None:
    """진입 청크(앱 코드) 크기. 빌드본이 없으면 None."""
    d = DIST / "assets"
    if not d.is_dir():
        return None
    got = sorted(d.glob("index-*.js"))
    if not got:
        return None
    return round(max(p.stat().st_size for p in got) / 1024)


# ── ③ 지도 워커가 산출물에 있는가 ───────────────────────────────
#: 워커 자산 이름의 뿌리. `maplibre-gl-worker-<해시>.js` 로 나온다.
WORKER = "maplibre-gl-worker"


def worker_faults(assets: Path | None = None) -> list[str]:
    """빌드본이 워커를 **파일로 내고** **자산 경로로 참조하는가.**

    ── 왜 이것을 재나 (DECISIONS §323) ─────────────────────────
    maplibre-gl 6 은 워커 URL 을 런타임에 만든다 —

        new URL(`./${t}`, import.meta.url)

    템플릿 문자열이라 번들러가 정적으로 못 보고 워커를 산출물에 안 넣는다.
    그러면 `vite build` 는 종료코드 0, `dist/index.html` 도 있고,
    **브라우저에서 워커만 404** 다. 타일 파싱이 워커에서 도니 지도 껍데기만
    뜨고 내용이 안 그려진다. 타입 검사도 빌드도 이것을 못 봤다 — **산출물을
    세는 검사만이 봤다.**

    ★ 종전에 이 검사는 `.github/actions/build-navi` 의 셸 한 줄이었고 **진입
      청크(`index-*.js`)만** 읽었다. §313 이 청크를 가르자 워커 참조가
      `maplibre-*.js` 로 옮겨갔고 검사가 울었다 — 없어진 것은 워커가 아니라
      **검사의 시야**였다. 어느 청크에 놓을지는 번들러가 정하므로 여기서는
      **산출물 전체**를 본다.

    ★ 파일과 참조를 **따로** 든다. 파일만 있고 참조가 없으면 브라우저가 안
      부르고, 참조만 있고 파일이 없으면 404 다 — 둘은 다른 고장이다.
    """
    d = assets if assets is not None else DIST / "assets"
    if not d.is_dir():
        return [f"`{d}` 가 없다 — `cd web/navi && npm run build`"]

    got = sorted(p.name for p in d.iterdir() if WORKER in p.name)
    # ★ 참조는 **자산 경로로** 적혀 있어야 한다. 고장난 상태에서는 번들에
    #   `maplibre-gl-worker.mjs` 만 남고 `assets/` 접두가 없어 안 걸린다.
    rx = re.compile(r"assets/" + re.escape(WORKER) + r"[\w.\-]*")
    seen: dict[str, list[str]] = {}
    for p in sorted(d.glob("*.js")):
        if WORKER in p.name:
            continue              # 워커가 제 이름을 적은 것은 참조가 아니다
        for m in rx.finditer(p.read_text(encoding="utf-8", errors="replace")):
            seen.setdefault(m.group(0).split("/", 1)[1], []).append(p.name)

    bad = []
    if not got:
        bad.append(f"산출물에 `{WORKER}*` 파일이 없다 — **브라우저에서 워커만 404** 다\n"
                   "       `NaviMap.tsx` · `OpsMap.tsx` 의 `?worker&url` 임포트를 확인할 것")
    if not seen:
        bad.append(f"번들이 워커를 `assets/{WORKER}…` 로 참조하지 않는다\n"
                   "       `setWorkerUrl(workerUrl)` 이 살아 있는지 확인할 것")
    for name in sorted(set(seen) - set(got)):
        bad.append(f"번들이 없는 워커 `{name}` 를 가리킨다 ({' · '.join(seen[name])}) — 404")
    if got and seen and not bad:
        where = sorted({c for v in seen.values() for c in v})
        print(f"워커 {' · '.join(got)} ← {' · '.join(where)}")
    return bad


def check(build: bool) -> list[str]:
    bad = []
    h = hosts()
    print(f"바깥 호스트 {len(h)} · 래칫 {EXTERNAL} · 선언된 예외 {len(ALLOWED)}")
    for host, where in sorted(h.items()):
        mark = "선언됨" if host in ALLOWED else "★ 선언에 없다"
        print(f"  {host:<24} {mark}   {where[0]}")
    for host in h:
        if host not in ALLOWED:
            bad.append(f"`{host}` 가 선언에 없다 — 출동 중에 끊기면 무엇이 죽는지 적어라\n"
                       f"       {' · '.join(h[host])}")
    for host in ALLOWED:
        if host not in h:
            bad.append(f"`{host}` 는 이제 안 부른다 — `ALLOWED` 에서 지우고 래칫을 내려라")
    if len(h) > EXTERNAL:
        bad.append(f"바깥 의존이 늘었다 — 선언 {EXTERNAL} · 실측 {len(h)}")
    elif len(h) < EXTERNAL:
        bad.append(f"바깥 의존이 {len(h)} 로 줄었다 — "
                   "`uv run python tools/ratchet.py --write` 로 조여라")

    # 오프라인 셋 — 있어야 도는 것들
    for want, why in (("public/sw.js", "서비스 워커가 없으면 캐시가 안 산다"),
                      ("public/manifest.webmanifest", "설치형으로 못 연다")):
        if not (NAVI / want).is_file():
            bad.append(f"`web/navi/{want}` 가 없다 — {why}")
    if not (ROOT / "web" / "404.html").is_file():
        bad.append("`web/404.html` 이 없다 — 오타 난 주소가 흰 화면이 된다")
    glyphs = ROOT / "web" / "fonts"
    if not glyphs.is_dir() or not list(glyphs.rglob("*.pbf")):
        bad.append("`web/fonts/**.pbf` 가 없다 — **오프라인에서 도로 이름이 사라진다**\n"
                   "       cd web/navi && npm run glyphs")
    if "serviceWorker" not in (NAVI / "src" / "main.tsx").read_text(encoding="utf-8"):
        bad.append("`main.tsx` 가 서비스 워커를 등록하지 않는다 — 파일만 있고 안 돈다")

    if build:
        kb = entry_kb()
        if kb is None:
            bad.append("빌드본이 없다 — `cd web/navi && npm run build`")
        else:
            print(f"진입 청크 {kb}KB · 래칫 {ENTRY_KB}KB")
            if kb > ENTRY_KB:
                bad.append(f"진입 청크가 {kb}KB 로 늘었다 (래칫 {ENTRY_KB}KB)\n"
                           "       **4G 첫 진입 시간이 곧 출동 시각이다**")
            elif kb < ENTRY_KB:
                bad.append(f"진입 청크가 {kb}KB 로 줄었다 — `ratchet.py --write` 로 조여라")
        bad += worker_faults()
    return bad


def selftest() -> int:
    fails = []
    h = hosts()
    if not isinstance(h, dict):
        fails.append("호스트 수집이 표가 아니다")
    # ★ 빈 그물 방어 — 선언된 예외는 실제로 소스에 있어야 한다
    for a in ALLOWED:
        if a not in h:
            fails.append(f"선언된 `{a}` 를 소스에서 못 찾는다 — 훑기가 비었거나 선언이 죽었다")
    # ★ 주석의 주소를 호출로 세면 안 된다
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        q = Path(d) / "t.ts"
        q.write_text(" * 종전에는 https://example.com 였다\nconst A = 1;\n", encoding="utf-8")
        found = [m for n, line in enumerate(q.read_text(encoding="utf-8").splitlines(), 1)
                 if not line.lstrip().startswith(("*", "//", "<!--"))
                 for m in re.finditer(r"https?://([A-Za-z0-9.-]+)", line)]
        if found:
            fails.append("주석에 적힌 옛 주소를 호출로 센다 — 사유를 적을 수가 없게 된다")
    # ★ 걷은 둘이 정말 없는가 — 이 배치의 결과다
    for gone in ("demotiles.maplibre.org", "cdn.jsdelivr.net"):
        if gone in h:
            fails.append(f"`{gone}` 가 아직 있다 — 오프라인에서 글자가 사라진다")

    # ★ ③ 워커 — **역방향으로 묻는다.** 「초록이 나오나」가 아니라 「고장을
    #   정말 잡나」다. 2026-09-30 에 죽은 것은 판정이 아니라 **시야**였다.
    with tempfile.TemporaryDirectory() as d:
        a = Path(d) / "assets"
        a.mkdir()
        ok = f"{WORKER}-BbFVVOSM.js"
        (a / ok).write_text("// 워커\n", encoding="utf-8")

        # ⓐ 참조가 **진입 청크가 아닌 청크**에 있어도 통과해야 한다 —
        #    이것이 §313 이 청크를 가른 뒤의 실제 모양이다
        (a / "maplibre-DWQEZNJQ.js").write_text(f'u="assets/{ok}";', encoding="utf-8")
        (a / "index-CBuyQVHW.js").write_text("// 워커 얘기 없다\n", encoding="utf-8")
        if worker_faults(a):
            fails.append("워커가 진입 청크 밖에 있으면 운다 — 청크 배치는 번들러가 정한다")

        # ⓑ 접두 없는 참조는 참조가 아니다
        (a / "maplibre-DWQEZNJQ.js").write_text(f'u="{ok}";', encoding="utf-8")
        if not worker_faults(a):
            fails.append("`assets/` 접두 없는 이름을 참조로 센다 — 고장난 상태가 이 꼴이다")

        # ⓒ 파일이 사라지면 운다
        (a / "maplibre-DWQEZNJQ.js").write_text(f'u="assets/{ok}";', encoding="utf-8")
        (a / ok).unlink()
        if not worker_faults(a):
            fails.append("워커 파일이 없는데 통과한다 — **브라우저에서 404** 다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 8")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="출동 중에 끊기는 것이 없는가")
    ap.add_argument("--build", action="store_true", help="빌드본 무게까지 본다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    bad = check(a.build)
    if bad:
        print("\n✗ 내비 의존")
        for b in bad:
            print(f"   {b}")
        return 1
    print("✓ 내비 의존")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
