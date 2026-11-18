#!/usr/bin/env python3
"""
uidrive.py — **주행 중 화면의 시선 기준을 소스에서 센다.**  (DECISIONS §702 · `tools/uicheck.py` 가 불러 래칫으로 선다)

IN    `web/navi/src` 의 주행 중 화면 파일들(`DRIVE_FILES`)
OUT   (파일 · 말) 쌍의 목록 — 한글이 든 말 중 20자 넘는 것 · `fontSize` 가 24 미만인 선언
      + **분모**(PLAN #259) — `web/navi/src` 전수 중 본 몫 · 안 본 파일의 묶음 선언(`OUT_OF_SCOPE`) · 선언 밖 파일
PARAM `GLANCE_CHARS`(20) · `MIN_FONT_PX`(24) · `PLACEHOLDER_CHARS`(6) · `DRIVE_FILES` · `OUT_OF_SCOPE`
밖    **렌더된 수는 안 잰다** — 꺾인 줄 · 계산된 글자 크기 · 터치 타깃은 브라우저가 있어야 안다(`web/navi/scripts/glance.mjs`).
      **관제 화면은 안 든다** — 운전 중이 아니다.
부류  몸통 — 입구가 없다(`uicheck` 가 부른다). 래칫 값(`DRIVE_LONG` · `DRIVE_SMALL_FONT`)은 `ratchet.py` 가 고쳐 적는 자리인 `uicheck.py` 에 산다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "navi" / "src"
_HANGUL = re.compile(r"[가-힣]")

# ★ 출처(차량 UI 규범 · 2026-11-12 직접 읽었다): NHTSA · Transport Canada — 한 과업은 **한 번에 2초 이하** 시선(들) · 총 12초 미만. 읽기 속도를
#   초당 10자로 가정하면 한 시선에 20자(`GLANCE_CHARS` — 이 가정은 출처 쪽에 없고 사람이 정한 환산이다). Android Auto — 본문 최소 **24dp**,
#   터치 타깃 76×76dp, 자동으로 흐르는 글자 금지, 과업 5화면 이내. CarPlay — 공공안전 앱 범주(소방 · 경찰 · 구급)가 있고 턴바이턴 필수.
# ★ **주행 중 화면만** 센다 — `DRIVE_FILES`. 출발 전 화면(경로 카드 · 대기)은 정차 중이라 2초 룰이 느슨하고, 관제 화면은 **운전 중이 아니다**
#   (앉아서 여러 정보를 동시에 보는 화면이라 규범이 다르다) — 둘 다 이 수에 안 든다.
# ★ **정적 근사다.** 렌더된 줄바꿈 · 계산된 글자 크기는 브라우저가 있어야 안다(`web/navi/e2e/glance.mjs` 가 그것을 잰다). 여기는 소스에서
#   「한글이 든 문자열 리터럴 · JSX 글 중 20자 초과」와 「`fontSize` 가 24 미만인 선언」을 센다 — 늘면 운다. 문장이 줄바꿈으로 둘이 돼도 읽는 양은
#   그대로라 **리터럴 길이가 줄 길이의 맞는 대리값**이다. 글자 크기는 선언 수라 렌더된 줄 수와 일대일이 아니다(방향만 같다).
# ★ 2026-11-18 (DECISIONS §829). **글자 크기 선언의 꼴은 셋을 센다** — ① `fontSize:` ② 약식 `font: "… 24px/…"` 의 크기 ③ **약식 `font:` 위에 긴 이름(`fontSize` · `fontWeight` …)을 덮어 쓰는 꼴** — 둘을 섞으면 React 가 덮은 쪽을
#   지울 때 약식의 크기가 같이 지워져 렌더가 기본 16px 로 떨어진다(`ui/TopBar.tsx` 의 주의 줄 · `reroute` → `noCctv`). 소스의 선언은 24 인데 렌더가 16 이라 ①만 세던 때는 0 이었다.
# ★ 범위(`DRIVE_FILES`) 밖의 사실(2026-11-18 · 같은 판별식을 돌린 수): `web/navi/src` 98파일 중 범위 밖 29파일에 20자 넘는 말 66건 · 24 미만 선언 99건이 있다(관제 `OpsApp.tsx` · 정차 `ui/RouteCompare.tsx` · 정차 중 상세 ·
#   `ui/DemoStrip.tsx` · `domain/demo.ts` …). **`domain/demo.ts`(`GPS 신호가 없다 — …` 27자)는 일부러 안 넣었다** — 그 문장은 측위가 `live` 가 아닐 때만 뜨고(`canStartDemo` · `usePositionSource`) 넣으면 `DRIVE_LONG` 이 0 → 1 로 느슨해진다.
# ★ 못 재는 것: 지도 위 글자(maplibre 캔버스 라벨 — DOM 이 아니다) · `App.tsx` 에 섞인 토스트(출발 전 문구와 한 파일) · 터치 타깃(스타일이
#   계산돼야 안다 — 렌더 측정 몫) · 자동 스크롤(소스에서 `scrollTo` · 마퀴가 없음을 아래 시험이 든다).
DRIVE_FILES = (
    "ui/TopBar.tsx", "ui/StatusCard.tsx", "ui/BottleneckPanel.tsx", "ui/RemainPill.tsx", "ui/MapControls.tsx",
    "ui/Legend.tsx", "ui/ShareChip.tsx", "domain/status.ts", "app/usePositionSource.ts",
    # ★ 2026-11-12 (DECISIONS §703 · §704). `ui/clearanceMeaning.ts`(병목 패널의 사유 문장 · 15개가 20자를 넘는다)는 **뺐다** — 기본 화면이 더는 그 문장을 안 띄운다.
    #   그 문장과 옛 몸통은 `ui/BottleneckDetail.tsx`(자세히 — 정차 중 상세)로 갔고 **둘은 이 수에 안 든다.** 이 분류는 **속도 잠금으로 참이다**(§704) —
    #   달리는 중에는 「자세히」 가 안 열리고 열려 있던 것도 닫힌다(`domain/motion.ts` · `BottleneckPanel` 의 `locked` · `e2e/smoke.spec.ts` 가 문다).
)
# ★ 2026-11-18 (PLAN #259 · DECISIONS §829-마). **본 몫(분모)과 안 본 몫의 선언.** 위 `DRIVE_FILES` 는 `web/navi/src` 의 일부라 「0건」은 **본 파일에서의 0건**이다 —
#   안 본 파일을 이름과 사유 없이 두면 파일이 늘 때 조용히 샌다. 범위 밖 파일은 **전부 한 묶음에 든다** — 묶음마다 「주행 중 화면이 아니다」의 판별식을 적는다.
#   `ops` 만 **기계가 든다**(`App.tsx` 에서 import 로 안 닿고 `OpsApp.tsx` 에서만 닿는다). 나머지는 사람이 가른 것이라 판별식이 문장이다.
#   선언 밖 파일 · 없는 파일 · 두 묶음에 든 파일 · `quiet` 인데 0건이 아닌 파일 · `ops` 인데 `App.tsx` 에 닿는 파일은 `census_faults` 가 낸다.
OUT_OF_SCOPE: dict[str, tuple[str, tuple[str, ...]]] = {
    "ops": ("관제 화면 전용 — 판별식: `OpsApp.tsx` 에서만 import 로 닿고 `App.tsx` 에서는 안 닿는다(시험이 import 도달성으로 든다). 운전 중이 아니다.", (
        "OpsApp.tsx", "components/OpsMap.tsx", "components/opsLayers.ts", "domain/checkpoints.ts", "domain/dispatch.ts", "domain/opsBoard.ts",
        "domain/search.ts", "domain/unitBoard.ts", "ui/OpsBits.tsx", "ui/OpsHistory.tsx", "ui/RouteCheckpoints.tsx", "ui/SegCard.tsx",
        "ui/VehicleArt.tsx", "ui/motion.ts", "ui/opsTheme.ts")),
    "stopped": ("정차 중 · 출발 전 화면 — 판별식: 달리는 동안 안 열린다(속도 잠금 `domain/motion.ts` · 출발 전 경로 카드 · 대기 · 개발 막대). 사람이 가른 것이다(§704).", (
        "ui/BottleneckDetail.tsx", "ui/RouteCompare.tsx", "ui/WaitPanel.tsx", "ui/routeOption.ts", "ui/clearanceMeaning.ts", "ui/verdictMeaning.ts",
        "ui/Sheet.tsx", "ui/appShell.tsx", "ui/DemoStrip.tsx", "ui/DevBar.tsx")),
    "voice": ("귀로 듣는 말 — 판별식: 음성 합성(`useVoice`)이 읽는 문장을 만드는 파일이라 눈이 아니라 귀의 기준이다(시선 2초 룰 밖). 같은 문장이 화면에도 뜨는지는 렌더 측정(`e2e/glance`) 몫이다.", (
        "domain/context.ts", "domain/cv.ts", "domain/reroute.ts", "domain/rules.ts", "domain/turn.ts", "domain/voice.ts")),
    "diag": ("진단 · 오류 문구 — 판별식: 콘솔 · 예외 · 출발 설정 거절 사유 · 정차 중 상세의 부기라 달리는 중에 안 뜬다. 사람이 가른 것이다.", (
        "app/useBundle.ts", "app/useNavigation.ts", "infra/dataSource.ts", "domain/vehicle.ts", "domain/pressure.ts")),
    "hold": ("사람이 정할 때까지 보류 — 판별식: 출발 전 문구와 한 파일에 섞였거나(`App.tsx` 토스트) 측위가 `live` 가 아닐 때만 뜨는 GPS 안내(`domain/demo.ts` · `domain/serviceArea.ts`)라 넣으면 래칫이 느슨해진다(PLAN #258).", (
        "App.tsx", "domain/demo.ts", "domain/serviceArea.ts")),
    "quiet": ("글자 선언이 0건 — 판별식: 이 판별식이 지금 20자 넘는 말도 24 미만 글자 선언도 0건 낸다(훅 · 도메인 · 지도 층 · 입출력). 0건이 아니게 되면 여기 못 남는다 — 이름 붙은 묶음으로 옮기거나 `DRIVE_FILES` 로 들인다.", (
        "app/useDeadReckoning.ts", "app/useDemo.ts", "app/useFading.ts", "app/useFleet.ts", "app/useHudData.ts", "app/useNow.ts", "app/useOpsUplink.ts",
        "app/useScreens.ts", "app/useShare.ts", "app/useVoice.ts", "components/NaviMap.tsx", "components/landuse.ts", "components/layers.ts",
        "components/roadLabels.ts", "config.ts", "domain/access.ts", "domain/adjacency.ts", "domain/clearance.ts", "domain/compare.ts", "domain/edgeSnap.ts",
        "domain/egobox.ts", "domain/fleetName.ts", "domain/geo.ts", "domain/graph.ts", "domain/handoff.ts", "domain/motion.ts", "domain/opsProtocol.ts",
        "domain/phase.ts", "domain/progress.ts", "domain/routeDerive.ts", "domain/routeSolve.ts", "domain/snap.ts", "domain/speed.ts", "domain/track.ts",
        "domain/turning.ts", "domain/types.ts", "infra/dataBase.ts", "infra/mapPitch.ts", "infra/opsLink.ts", "infra/position/gps.ts",
        "infra/position/replay.ts", "infra/position/simulation.ts", "infra/position/types.ts", "infra/speech.ts", "main.tsx", "ui/TurnArrow.tsx", "ui/deferred.tsx",
        "ui/icons.tsx", "ui/tokens.ts", "vite-env.d.ts")),
}
#: 값이 들어갈 자리(`${…}` · `{road}`)가 화면에서 차지하는 글자 수의 근사 — 숫자 · 도로명이 이만큼이라 치고 길이를 잰다
PLACEHOLDER_CHARS = 6
GLANCE_CHARS = 20
MIN_FONT_PX = 24
_LIT = re.compile(r"\"([^\"\n]*)\"|'([^'\n]*)'|`([^`\n]*)`")
_JSXT = re.compile(r">([^<>{}\n]*[가-힣][^<>{}\n]*)<")
_PH = re.compile(r"\$\{[^}]*\}|\{\w+\}")
_FONT = re.compile(r"fontSize:\s*([^,}\n]+)")
_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")


def uncomment(src: str) -> str:
    """`screen_text` 와 같은 주석 걷기(블록 · 줄머리 · 줄 끝) — 글자만 남기지 않고 **소스를 남긴다**."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"^\s*//.*$", "", src, flags=re.M)
    return re.sub(r"(?<!:)//[^\n]*$", "", src, flags=re.M)


def drive_long_lines(root: Path = SRC, limit: int = GLANCE_CHARS, files: tuple[str, ...] = DRIVE_FILES) -> list[tuple[str, str]]:
    """주행 중 화면 파일에서 **한글이 든 말 중 `limit` 자를 넘는 것**(파일 · 말). 문자열 리터럴과 JSX 글을 센다."""
    out: list[tuple[str, str]] = []
    for rel in files:
        p = root / rel
        assert p.is_file(), f"주행 중 화면 파일이 없다: {rel} — 없는 파일을 조용히 건너뛰면 수가 줄어 보인다"
        src = uncomment(p.read_text(encoding="utf-8"))
        for m in _LIT.finditer(src):
            t = _PH.sub("0" * PLACEHOLDER_CHARS, next(g for g in m.groups() if g is not None)).strip()
            if _HANGUL.search(t) and len(t) > limit:
                out.append((rel, t))
        for m in _JSXT.finditer(src):
            t = _PH.sub("0" * PLACEHOLDER_CHARS, m.group(1)).strip()
            if len(t) > limit:
                out.append((rel, t))
    return out


_SHORT = re.compile(r"\bfont:\s*([`\"'])(.*?)\1")
_LONG_KEYS = r"(?:fontSize|fontWeight|fontFamily|lineHeight|fontStyle)"


def _mixed_shorthand(src: str) -> list[str]:
    """약식 `font:` 를 든 **이름 붙은 스타일 객체**(`const NAME = {… font: …}`)를 찾아, 그 위에 긴 이름을 덮어 쓰는 곳(`{ ...NAME, fontSize: … }`)과 한 객체 안에 둘이 같이 든 곳을 낸다."""
    lines, names, cur, hits = src.split("\n"), set(), None, []
    for ln in lines:
        m = re.match(r"\s*(?:export\s+)?const\s+(\w+)\b[^=]*=\s*\{", ln)
        if m:
            cur = m.group(1)
        if cur and re.search(r"\bfont:", ln):
            names.add(cur)
            if re.search(rf"\b{_LONG_KEYS}\s*:", ln):
                hits.append(f"font: 약식과 긴 이름이 한 객체에 같이 있다({cur})")
        if (cur and re.match(r"\s*\};?\s*$", ln)) or (m and ln.rstrip().endswith("};")):
            cur = None
    for n in sorted(names):
        if re.search(rf"\.\.\.\s*{n}\b[^}}]*?\b{_LONG_KEYS}\s*:", src):
            hits.append(f"font: 약식 `{n}` 위에 긴 이름을 덮어 쓴다")
    return hits


def drive_small_fonts(root: Path = SRC, floor: int = MIN_FONT_PX, files: tuple[str, ...] = DRIVE_FILES) -> list[tuple[str, str]]:
    """주행 중 화면 파일의 **글자 크기 선언 중 `floor` 미만**(① `fontSize` ② 약식 `font` 의 크기)과 **약식 위에 긴 이름을 섞는 꼴**(③)(파일 · 식). `F.small` 같은 토큰은 `tokens.ts` 표에서 푼다."""
    tok = {k: int(v) for k, v in re.findall(r"^\s*(\w+):\s*(\d+),", (root / "ui" / "tokens.ts").read_text(encoding="utf-8").split("export const F", 1)[1].split("} as const", 1)[0], re.M)}
    out: list[tuple[str, str]] = []
    for rel in files:
        p = root / rel
        assert p.is_file(), f"주행 중 화면 파일이 없다: {rel} — 없는 파일을 조용히 건너뛰면 수가 줄어 보인다"
        src = uncomment(p.read_text(encoding="utf-8"))
        for m in _FONT.finditer(src):
            e = m.group(1).strip()
            vals = [float(x) for x in _NUM.findall(e)] + [float(tok[k]) for k in re.findall(r"F\.(\w+)", e) if k in tok]
            if vals and min(vals) < floor:
                out.append((rel, e))
        for m in _SHORT.finditer(src):                                           # ② 약식 `font: "800 24px/32px …"` 의 크기
            sz = re.search(r"(\d+(?:\.\d+)?)px", m.group(2))
            if sz and float(sz.group(1)) < floor:
                out.append((rel, "font: " + m.group(2).strip()))
        out += [(rel, h) for h in _mixed_shorthand(src)]                       # ③ 약식 위에 긴 이름을 섞는다
    return out


# ── 분모 (PLAN #259) ─────────────────────────────────────────────────────────

_IMPORT = re.compile(r"""(?:from|import)\s*(?:[^"';]*?from\s*)?["'](\.[^"']*)["']|import\(\s*["'](\.[^"']*)["']\s*\)""")


def src_files(root: Path = SRC) -> list[str]:
    """`web/navi/src` 의 **전수**(상대 경로) — 분모다. 소스가 아닌 것(`.css` · 그림)은 글을 안 만들어 빼지 않고 **같이 센다**: 그림 파일이 들어와도 선언을 요구한다."""
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def reachable(entry: str, root: Path = SRC) -> set[str]:
    """`entry` 에서 상대 import 로 닿는 파일(자기 포함). 없는 진입점은 빈 집합 — 호출한 쪽이 따진다."""
    start = (root / entry).resolve()
    if not start.is_file():
        return set()
    seen, todo = {start}, [start]
    while todo:
        f = todo.pop()
        for m in _IMPORT.finditer(uncomment(f.read_text(encoding="utf-8"))):
            base = (f.parent / (m.group(1) or m.group(2))).resolve()
            for c in (base, base.with_suffix(".ts"), base.with_suffix(".tsx"), base / "index.ts", base / "index.tsx"):
                if c.is_file():
                    if c not in seen:
                        seen.add(c)
                        todo.append(c)
                    break
    return {x.relative_to(root.resolve()).as_posix() for x in seen}


def drive_census(root: Path = SRC, files: tuple[str, ...] = DRIVE_FILES, groups: dict | None = None) -> dict:
    """본 몫 · 안 본 몫. `seen`(범위) · `out`(범위 밖 묶음별 파일) · `undeclared`(어느 묶음에도 없는 범위 밖 파일) 와 범위 밖의 20자 넘는 말 · 24 미만 선언 수를 낸다."""
    groups = OUT_OF_SCOPE if groups is None else groups
    allf = src_files(root)
    declared = {f for _, (_, fs) in groups.items() for f in fs}
    out_all = [f for f in allf if f not in files]
    code = [f for f in out_all if f.endswith((".ts", ".tsx"))]
    return {
        "total": len(allf), "seen": len([f for f in allf if f in files]), "out": {g: list(fs) for g, (_, fs) in groups.items()},
        "undeclared": [f for f in out_all if f not in declared],
        "long": sum(len(drive_long_lines(root, files=(f,))) for f in code), "small": sum(len(drive_small_fonts(root, files=(f,))) for f in code),
    }


def census_faults(root: Path = SRC, files: tuple[str, ...] = DRIVE_FILES, groups: dict | None = None) -> list[str]:
    """선언과 전수가 어긋난 곳 — **선언 밖 파일이 새로 들어오면 여기서 빨갛다**(없는 파일 · 두 묶음 · 범위와 겹침 · `quiet` 이 0건 아님 · `ops` 가 `App.tsx` 에 닿음)."""
    groups = OUT_OF_SCOPE if groups is None else groups
    c, bad, allf, where = drive_census(root, files, groups), [], set(src_files(root)), {}
    if c["undeclared"]:
        bad.append(f"범위 밖인데 선언이 없는 파일 {len(c['undeclared'])}: {', '.join(c['undeclared'][:6])} — 주행 중 화면이면 `DRIVE_FILES` 에 넣고, 아니면 `OUT_OF_SCOPE` 의 묶음에 사유와 함께 적어라")
    for g, (_, fs) in groups.items():
        for f in fs:
            if f not in allf:
                bad.append(f"선언된 파일이 없다: {g} · {f} — 낡은 선언은 지워라")
            if f in files:
                bad.append(f"범위(`DRIVE_FILES`)와 범위 밖 선언에 둘 다 든다: {f}")
            if f in where:
                bad.append(f"두 묶음에 든다: {f} ({where[f]} · {g})")
            where[f] = g
    for f in groups.get("quiet", ("", ()))[1]:
        if f in allf and f.endswith((".ts", ".tsx")) and (drive_long_lines(root, files=(f,)) or drive_small_fonts(root, files=(f,))):
            bad.append(f"`quiet` 인데 글자 선언이 0건이 아니다: {f} — 이름 붙은 묶음으로 옮기거나 `DRIVE_FILES` 로 들여라")
    ops = groups.get("ops", ("", ()))[1]
    if ops:
        app, opsr = reachable("App.tsx", root), reachable("OpsApp.tsx", root)
        bad += [f"`ops` 인데 `App.tsx` 에서 import 로 닿는다: {f} — 관제 전용이 아니다" for f in ops if f in app]
        bad += [f"`ops` 인데 `OpsApp.tsx` 에서 안 닿는다: {f}" for f in ops if f in allf and f not in opsr]
    return bad


def census_line(root: Path = SRC, files: tuple[str, ...] = DRIVE_FILES) -> str:
    """한 줄 요약 — 「98파일 중 9파일(9.2%)을 보고 …」. 안 본 몫의 묶음별 파일 수와 그 안의 수를 같이 낸다."""
    c = drive_census(root, files)
    gs = " · ".join(f"{g} {len(fs)}" for g, fs in c["out"].items())
    return (f"{c['total']}파일 중 {c['seen']}파일({100 * c['seen'] / c['total']:.1f}%)을 보고 · 범위 밖 {c['total'] - c['seen']}파일({gs}) — 범위 밖에 20자 넘는 말 {c['long']} · "
            f"{MIN_FONT_PX}px 미만 선언 {c['small']} · 선언 밖 {len(c['undeclared'])}")


def drive_gate(rec_long: int, rec_small: int) -> list[str]:
    """`uicheck` ㉩ — 실측이 기록과 **양방향**으로 어긋나면(늘면 시선 부담 · 줄면 기록을 내린다) · 범위 밖 선언이 전수와 어긋나면 낸다. 기록은 `uicheck.py` 가 쥔다(`ratchet.py` 가 고쳐 적는 자리)."""
    bad = []
    for name, now, rec, what in (("DRIVE_LONG", len(drive_long_lines()), rec_long, f"주행 중 {GLANCE_CHARS}자 넘는 말"),
                                 ("DRIVE_SMALL_FONT", len(drive_small_fonts()), rec_small, f"주행 중 {MIN_FONT_PX}px 미만 글자 선언")):
        if now != rec:
            bad.append(f"{what} {now} " + (f"> 기록 {rec} — 한 시선 2초(DECISIONS §702): 줄이거나 정차 중에만 뜨는 곳으로 옮겨라" if now > rec
                                            else f"< 기록 {rec} — 줄었다. `tools/uicheck.py` 의 `{name}` 을 {now} 으로 내려라"))
    return bad + census_faults()
