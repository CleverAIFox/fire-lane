#!/usr/bin/env python3
"""
uidrive.py — **주행 중 화면의 시선 기준을 소스에서 센다.**  (DECISIONS §702 · `tools/uicheck.py` 가 불러 래칫으로 선다)

IN    `web/navi/src` 의 주행 중 화면 파일들(`DRIVE_FILES`)
OUT   (파일 · 말) 쌍의 목록 — 한글이 든 말 중 20자 넘는 것 · `fontSize` 가 24 미만인 선언
PARAM `GLANCE_CHARS`(20) · `MIN_FONT_PX`(24) · `PLACEHOLDER_CHARS`(6) · `DRIVE_FILES`
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
# ★ 못 재는 것: 지도 위 글자(maplibre 캔버스 라벨 — DOM 이 아니다) · `App.tsx` 에 섞인 토스트(출발 전 문구와 한 파일) · 터치 타깃(스타일이
#   계산돼야 안다 — 렌더 측정 몫) · 자동 스크롤(소스에서 `scrollTo` · 마퀴가 없음을 아래 시험이 든다).
DRIVE_FILES = (
    "ui/TopBar.tsx", "ui/StatusCard.tsx", "ui/BottleneckPanel.tsx", "ui/RemainPill.tsx", "ui/MapControls.tsx",
    "ui/Legend.tsx", "ui/ShareChip.tsx", "domain/status.ts", "app/usePositionSource.ts",
    # 병목 패널이 「왜 막히나 · 무엇을 하나」를 이 파일의 문장으로 띄운다(관제 `SegCard` 도 쓰지만 이 수는 주행 중 화면이 낸 말만 센다)
    "ui/clearanceMeaning.ts",
)
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


def drive_small_fonts(root: Path = SRC, floor: int = MIN_FONT_PX, files: tuple[str, ...] = DRIVE_FILES) -> list[tuple[str, str]]:
    """주행 중 화면 파일의 **`fontSize` 선언 중 `floor` 미만을 하나라도 든 것**(파일 · 식). `F.small` 같은 토큰은 `tokens.ts` 표에서 푼다."""
    tok = {k: int(v) for k, v in re.findall(r"^\s*(\w+):\s*(\d+),", (root / "ui" / "tokens.ts").read_text(encoding="utf-8").split("export const F", 1)[1].split("} as const", 1)[0], re.M)}
    out: list[tuple[str, str]] = []
    for rel in files:
        p = root / rel
        assert p.is_file(), f"주행 중 화면 파일이 없다: {rel} — 없는 파일을 조용히 건너뛰면 수가 줄어 보인다"
        for m in _FONT.finditer(uncomment(p.read_text(encoding="utf-8"))):
            e = m.group(1).strip()
            vals = [float(x) for x in _NUM.findall(e)] + [float(tok[k]) for k in re.findall(r"F\.(\w+)", e) if k in tok]
            if vals and min(vals) < floor:
                out.append((rel, e))
    return out
