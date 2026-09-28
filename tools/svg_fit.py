#!/usr/bin/env python3
"""
svg_fit.py — **손으로 좌표를 박은 SVG 가 화면을 넘지 않는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-24. `tools/render_figures.py` 에서 떼어냈다. 그 파일이 600줄
  상한을 넘었고(663), 넘은 이유는 그림이 늘어서지 배치 검사가 커져서가
  아니다. 둘은 **다른 일**이다 — 이쪽은 「어떤 SVG 든 요소가 화면과 도형
  안에 드는가」이고, 그쪽은 「이 저장소의 정본에서 무엇을 그리는가」다.

★ 검사 자체의 경위는 그대로다 —
    2026-09-02  좌표가 코드에 박혀 있어 노드가 늘면 넘친다. 넘쳐도 SVG 는
                오류 없이 그려진다 — 아무도 모른다(DECISIONS §111)
    2026-09-22  글자를 기준점 한 점으로만 봤다. 라벨 폭을 어림한다(§218-6)
    2026-09-24  `<circle>` 이 검사 밖이었다. 외접 사각형으로 본다(§236-3)

IN    없음 (문자열을 받는다)
OUT   없음 (판정 목록을 돌려준다)
PARAM 없음
밖    **SVG 를 그리지 않는다.** 무엇을 그릴지는 `render_figures` 소관이다.
      그리고 `<path>` · `<line>` · `<polygon>` 은 안 본다 — 임의 도형의
      경계상자를 정확히 내려면 패스 파서가 필요하고, 그것은 이 검사가
      막으려는 것(라벨이 박스를 넘는가)과 값어치가 안 맞는다.
      겹침 판정 대상은 `<rect>` 와 `<circle>` 둘뿐이다.
"""
from __future__ import annotations

import html
import re

from firelane.cli import no_args

W, H = 720, 300
FONT = "Pretendard, system-ui, sans-serif"


_TEXT = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
_RECT = re.compile(r'<rect x="([\d.]+)" y="([\d.]+)" '
                   r'width="([\d.]+)" height="([\d.]+)"')
#: 원. **외접 사각형으로 본다** — 아래 `_boxes()` 가 사각형과 같은 자리에 넣는다.
_CIRCLE = re.compile(r'<circle cx="(-?[\d.]+)" cy="(-?[\d.]+)" r="([\d.]+)"')


def _boxes(body: str) -> list[tuple[float, float, float, float]]:
    """배치 검사가 보는 도형들의 `(x, y, w, h)`.

    ★ 2026-09-24 (PLAN §12 #15). 종전에는 `<rect>` 만 봤다. `fig_cctv` 가
      2026-09-23 에 원 그림을 복도로 바꾼 사유가 바로 **「`_fits()` 는 원을
      안 본다」** 였다 — 그림을 고쳐서 검사의 눈먼 자리를 피해 간 것이고,
      눈먼 자리는 그대로 남았다. 원을 쓰는 그림이 하나 생기는 김에 메운다.

      원은 **외접 사각형**으로 본다. 라벨이 원의 둥근 모서리 옆으로 조금
      비어져 나가는 것까지 우는 쪽이다 — 보수적으로 틀린다.
    """
    out = [tuple(float(g) for g in m.groups()) for m in _RECT.finditer(body)]
    for m in _CIRCLE.finditer(body):
        cx, cy, r = (float(g) for g in m.groups())
        out.append((cx - r, cy - r, 2 * r, 2 * r))
    return out


def _attr(attrs: str, name: str, default: str | None = None) -> str | None:
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return m.group(1) if m else default


def _em(ch: str) -> float:
    """글자 한 자의 폭(em). 한글·한자·전각 1.0 · 나머지 0.6 — 어림이다."""
    o = ord(ch)
    wide = (0x1100 <= o <= 0x11FF or 0x2E80 <= o <= 0x9FFF
            or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF
            or 0xFF00 <= o <= 0xFF60)
    return 1.0 if wide else 0.6


def text_extent(attrs: str, inner: str) -> tuple[float, float, float, str]:
    """`<text>` 하나의 (왼쪽 끝, 오른쪽 끝, 기준선 y, 그려지는 글자).

    폭은 글자 수 × 글꼴 크기 × em 어림이다. `text-anchor` start/middle/end 를 따른다.
    """
    shown = html.unescape(re.sub(r"<[^>]+>", "", inner))
    size = float(_attr(attrs, "font-size", "16") or 16)
    x = float(_attr(attrs, "x", "0") or 0)
    y = float(_attr(attrs, "y", "0") or 0)
    tw = sum(_em(c) for c in shown) * size
    anchor = _attr(attrs, "text-anchor", "start")
    left = x - tw / 2 if anchor == "middle" else x - tw if anchor == "end" else x
    return left, left + tw, y, shown


def _fits(body: str, w: int, h: int) -> list[str]:
    """모든 요소가 `viewBox` 안에 있는가 — 글자는 **폭까지** 본다.

    ★ 2026-09-02. `fig_branch` 는 파트가 셋이라 `x = 60 + i*200` 으로 720
      안에 들어간다. **넷이 되면 넘친다.** 그런데 넘쳐도 SVG 는 오류 없이
      그려진다 — 박스가 화면 밖으로 나갈 뿐이고 **아무도 모른다.**

      `--check` 는 값이 바뀐 것을 잡지 배치가 깨진 것은 못 잡는다.
      좌표가 코드에 박혀 있는 한(레이아웃 엔진이 없다) 이 검사가 그
      자리를 대신한다(DECISIONS §111).

    ★ 2026-09-22 (DECISIONS §218-6) 글자는 기준점 한 점만 보았다. 기준점이 안에
      있으면 라벨이 아무리 길어도 통과했다 — 같은 족(1족)이 글자 쪽에서 무음이었다.
      이제 라벨 폭을 어림해(한글 1.0em · 라틴·숫자 0.6em × font-size, text-anchor
      반영) viewBox 를 넘는지, 기준점이 든 가장 작은 박스를 가로로 넘는지 본다.
      어림은 보수적이다(공백도 0.6em) — 넘치면 줄이거나 줄을 나누거나 박스를 넓힌다.

    ★ 2026-09-24 `<circle>` 도 본다(`_boxes()`). 그 전까지는 원이 검사 밖이었고,
      2026-09-23 에 `fig_cctv` 의 원 그림을 복도로 바꾼 사유가 바로 그것이었다.

    ★ 2026-09-28 (DECISIONS §278-4) **글자끼리 겹치는 것**을 본다. 그전까지 이
      검사는 글자를 화면·박스하고만 견줬고 **글자 둘을 서로 견준 적이 없었다.**
      기획서 [그림 8] 이 라벨 두 개를 같은 자리에 겹쳐 찍은 채 제출본에 있었다 —
      검사 59개가 전부 초록인 채로. 겹쳐도 SVG 는 오류 없이 그려지고, 쪽수도
      글자 수도 그림 수도 안 변한다. 이 검사가 없으면 **사람이 눈으로 볼 때만**
      걸린다.
    """
    bad = []
    rects = []
    for x, y, bw, bh in _boxes(body):
        rects.append((x, y, bw, bh))
        if x < 0 or y < 0 or x + bw > w or y + bh > h:
            bad.append(f"도형 ({x:g},{y:g} {bw:g}x{bh:g}) 가 {w}x{h} 밖이다")
    for m in _TEXT.finditer(body):
        left, right, y, shown = text_extent(m.group(1), m.group(2))
        tag = f"글자 {shown[:24]!r} ({left:.0f}~{right:.0f}, y={y:g})"
        if left < 0 or right > w or y < 0 or y > h:
            bad.append(f"{tag} 가 {w}x{h} 밖이다")
            continue
        ax = float(_attr(m.group(1), "x", "0") or 0)
        inside = [r for r in rects
                  if r[0] <= ax <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]]
        if inside:
            bx, _, bw, _ = min(inside, key=lambda r: r[2] * r[3])
            if left < bx or right > bx + bw:
                bad.append(f"{tag} 가 박스 ({bx:g}~{bx + bw:g}) 를 넘는다")
            continue
        # 어느 박스에도 안 든 라벨(범례·값)이 옆 막대 위로 번지는가.
        # 글자 높이는 기준선 위 0.8em · 아래 0.2em 으로 어림한다.
        size = float(_attr(m.group(1), "font-size", "16") or 16)
        top, bot = y - 0.8 * size, y + 0.2 * size
        for rx, ry, rw, rh in rects:
            if left < rx + rw and right > rx and top < ry + rh and bot > ry:
                bad.append(f"{tag} 가 박스 ({rx:g},{ry:g} {rw:g}x{rh:g}) 를 덮는다")
                break
    bad += _collisions(body)
    return bad


#: 글자끼리 이만큼 겹치는 것은 안 센다. 어림이 보수적이라 스치는 것이 나온다.
OVERLAP_PX = 1.5


def _spans(body: str) -> list[tuple[float, float, float, float, str]]:
    """글자마다 (좌, 우, 위, 아래, 보이는 글). 높이는 기준선 위 0.8em · 아래 0.2em."""
    out = []
    for m in _TEXT.finditer(body):
        left, right, y, shown = text_extent(m.group(1), m.group(2))
        size = float(_attr(m.group(1), "font-size", "16") or 16)
        out.append((left, right, y - 0.8 * size, y + 0.2 * size, shown))
    return out


def _collisions(body: str) -> list[str]:
    """★ 글자 둘이 서로를 덮는가. 겹쳐도 SVG 는 조용히 그린다."""
    sp = _spans(body)
    bad = []
    for i, (l1, r1, t1, b1, s1) in enumerate(sp):
        for l2, r2, t2, b2, s2 in sp[i + 1:]:
            dx = min(r1, r2) - max(l1, l2)
            dy = min(b1, b2) - max(t1, t2)
            if dx > OVERLAP_PX and dy > OVERLAP_PX:
                bad.append(f"글자 {s1[:18]!r} 와 {s2[:18]!r} 가 "
                           f"{dx:.0f}x{dy:.0f}px 겹친다")
    return bad


def svg(body: str, *, w: int = W, h: int = H) -> str:
    """배치를 확인하고 `<svg>` 로 감싼다. 넘치면 **만들지 않는다.**"""
    over = _fits(body, w, h)
    if over:
        raise SystemExit(
            "★ 그림이 화면을 넘는다 — " + " · ".join(over[:4])
            + "\n  노드가 늘어 좌표가 안 맞는다. 배치를 손보거나 폭을 늘려라.\n"
            "  ★ 넘쳐도 SVG 는 오류 없이 그려진다 — 이 검사가 없으면\n"
            "    아무도 모른다(DECISIONS §111).")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" font-family="{FONT}">'
            f'<rect width="{w}" height="{h}" fill="#fff"/>{body}</svg>\n')


def selftest() -> int:
    """넘치는 라벨 · 화면 밖 원을 실제로 잡는가. **빈 그물이 아닌가.**"""
    bad = [
        ('<text x="700" y="40" font-size="14">화면 밖으로 나가는 긴 라벨입니다</text>', "밖이다"),
        ('<circle cx="700" cy="50" r="60"/>', "밖이다"),
        ('<rect x="100" y="10" width="60" height="40"/>'
         '<text x="130" y="35" font-size="12" text-anchor="middle">박스보다 긴 라벨</text>',
         "박스"),
    ]
    for body, want in bad:
        got = _fits(body, 720, 120)
        if not got or want not in got[0]:
            print(f"★ 안 잡았다: {body[:40]} → {got}")
            return 1
    if _fits('<text x="12" y="40" font-size="12">짧다</text>', 720, 120):
        print("★ 멀쩡한 라벨을 잡았다")
        return 1
    # ★ 글자끼리 겹침 — 기획서 [그림 8] 이 이 꼴로 제출본에 있었다.
    dup = ('<text x="60" y="40" font-size="12">① 관측점 선정</text>'
           '<text x="60" y="40" font-size="12">② 판정 결과</text>')
    if not any("겹친다" in b for b in _fits(dup, 720, 120)):
        print("★ 같은 자리에 겹쳐 찍은 라벨 둘을 안 잡았다")
        return 1
    # 같은 박스 안 여러 줄(15px 간격)은 겹침이 아니다 — 오탐이면 못 쓴다.
    lines = "".join(f'<text x="60" y="{40 + i * 15}" font-size="10">줄 {i}</text>'
                    for i in range(4))
    if _fits(lines, 720, 120):
        print("★ 줄 간격이 성한 여러 줄을 겹쳤다고 한다")
        return 1
    print("svg_fit OK — 넘침 셋과 겹침을 잡고 멀쩡한 것은 통과")
    return 0


if __name__ == "__main__":
    no_args(__doc__)          # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
    raise SystemExit(selftest())
