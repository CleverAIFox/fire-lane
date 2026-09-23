#!/usr/bin/env python3
"""
render_figures.py — 정본에서 그림을 만든다.

    uv run python tools/render_figures.py            docs/figures/*.svg 생성
    uv run python tools/render_figures.py --check    정본과 어긋나면 종료코드 1

── 왜 생겼나 ───────────────────────────────────────────────────
기획서 그림 24장에 강제자가 **캡션뿐**이었다. `docx_check` 가 캡션 텍스트를
저장소 어휘와 대조하지만 **그림 자체는 아무도 안 본다.** [그림 13] 이 폐기된
반경 5m 원을 그리는데 캡션은 맞아서 안 잡혔다(PLAN §12 #15).

24장 중 **넷은 값이 정본에 있다.** 그리면 되는 것이지 사람이 다시 그릴
이유가 없다 — `web/workflow.html` 이 `MASTER §12` 에서 나오는 것과 같다.

★ 2026-09-24 (DECISIONS §236). 그 [그림 13] 을 여기서 그린다(`fig_xsec`).
  머리말이 석 주 동안 **자기가 못 고치는 예시로 그 그림을 들고 있었다.**

★ 2026-09-23 (DECISIONS §221-1). 종전에는 여기에 「`.docx` 안 이미지를 코드가
  교체하지는 않는다 — 알리기만 하고 넣는 것은 사람이 한다」 고 적혀 있었다.
  그 결정을 뒤집었다. 이 파일은 **SVG 를 만들고 어긋남을 알리고**,
  `tools/docx_figs.py --sync` 가 그것을 기획서 안에 **넣는다.**

IN    data/golden/segments.fingerprint.json · src/firelane/seg/params.py
OUT   docs/figures/*.svg · docs/figures/.lock.json
PARAM --check
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/figures"
LOCK = OUT / ".lock.json"

W, H = 720, 300
FONT = "Pretendard, system-ui, sans-serif"
COLOR = {"clear": "#16a34a", "needs_cv": "#ea580c",
         "blocked": "#dc2626", "unknown": "#94a3b8"}
LABEL = {"clear": "통행 가능", "needs_cv": "판정 보류",
         "blocked": "통행 불가", "unknown": "영상판정 불가"}


def _golden() -> dict:
    p = ROOT / "data/golden/segments.fingerprint.json"
    return json.loads(p.read_text(encoding="utf-8"))["L1"]


def _params() -> dict:
    """`params.py` 를 임포트하지 않고 읽는다 — 도구가 파이프라인에 안 붙는다."""
    src = (ROOT / "src/firelane/seg/params.py").read_text(encoding="utf-8")
    out = {}
    for line in src.splitlines():
        for key in ("TRUCK", "PARK", "CCTV_RANGE", "XSEC_EXCL", "WMAX_CAP", "SNAP_TOL"):
            if line.startswith(key):
                try:
                    out[key] = float(line.split("=")[1].split("#")[0].strip())
                except ValueError:
                    pass
    return out


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
    return bad


def _svg(body: str, *, w: int = W, h: int = H) -> str:
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


def fig_verdict() -> str:
    """판정 4종 분포. 값은 golden 이 정본이다."""
    g = _golden()
    v, n = g["verdict"], g["n"]
    # ★ 2026-09-22 (DECISIONS §218-6) 막대가 x=60 에서 시작하고 범례는 x=12 라
    #   「영상판정 불가」(12px 6자 ≈ 72px)가 막대 위로 번졌다. 범례 자리를 넓힌다.
    x, bars, legend = 110, [], []
    for i, k in enumerate(("clear", "needs_cv", "blocked", "unknown")):
        c = v[k]
        wd = round(480 * c / n, 1)
        bars.append(f'<rect x="{x}" y="{70 + i * 46}" width="{wd}" height="30" '
                    f'fill="{COLOR[k]}" rx="3"/>')
        bars.append(f'<text x="{x + wd + 8}" y="{91 + i * 46}" font-size="13" '
                    f'fill="#0f172a">{c}  ({c * 100 / n:.1f}%)</text>')
        legend.append(f'<text x="12" y="{91 + i * 46}" font-size="12" '
                      f'fill="#475569">{LABEL[k]}</text>')
    head = (f'<text x="12" y="30" font-size="15" font-weight="700" '
            f'fill="#0f172a">판정 4종 분포 — 전체 {n:,}구간</text>'
            f'<text x="12" y="50" font-size="11" fill="#64748b">'
            f'정본 data/golden/segments.fingerprint.json</text>')
    return _svg(head + "".join(bars) + "".join(legend), h=70 + 4 * 46 + 20)


def fig_threshold() -> str:
    """판정 임계. `params.py` 가 정본이다."""
    p = _params()
    truck = p.get("TRUCK", 3.0)
    # ★ 2026-09-22 (DECISIONS §218-6) 여유선을 글자(7.0)로 박아 두었다 — TRUCK 은 정본에서
    #   읽으면서 여유선은 사본이었다. 판정 규칙대로 TRUCK + 2×PARK 로 낸다(양쪽 주차 1대씩).
    clear_at = truck + 2 * p.get("PARK", 2.0)
    x0, x1, span = 60, 660, 10.0
    def px(m: float) -> float:
        return x0 + (x1 - x0) * min(m, span) / span
    bands = [(0, truck, COLOR["blocked"], "통행 불가"),
             (truck, clear_at, COLOR["needs_cv"], "판정 보류"),
             (clear_at, span, COLOR["clear"], "통행 가능")]
    body = [f'<text x="12" y="30" font-size="15" font-weight="700" '
            f'fill="#0f172a">폭 임계 — 통과 하한 {truck}m · 여유 {clear_at}m</text>',
            '<text x="12" y="50" font-size="11" fill="#64748b">'
            '정본 src/firelane/seg/params.py</text>']
    for a, b, c, lab in bands:
        body.append(f'<rect x="{px(a):.1f}" y="90" width="{px(b) - px(a):.1f}" '
                    f'height="42" fill="{c}" rx="3"/>')
        body.append(f'<text x="{(px(a) + px(b)) / 2:.1f}" y="116" font-size="12" '
                    f'fill="#fff" text-anchor="middle">{lab}</text>')
    for m in (0, truck, clear_at, span):
        body.append(f'<line x1="{px(m):.1f}" y1="132" x2="{px(m):.1f}" y2="146" '
                    f'stroke="#94a3b8"/>')
        body.append(f'<text x="{px(m):.1f}" y="164" font-size="11" '
                    f'fill="#475569" text-anchor="middle">{m:g}m</text>')
    body.append('<text x="60" y="196" font-size="11" fill="#64748b">'
                f'최소 폭이 하한 미만이면 통행 불가, {clear_at}m 이상이면 통행 가능. '
                '그 사이는 영상판정 대상이다.</text>')
    return _svg("".join(body), h=220)


def fig_cctv() -> str:
    """유효 측정 범위. `CCTV_RANGE` 가 정본이다.

    ★ 2026-09-23. 원(반경 25m) 그림을 **복도** 그림으로 바꿨다. 이유 둘 —
      ① 부제(`정본 …params.py`)가 원에 덮여 있었다. `_fits()` 는 글자↔사각형만 보고
         **원은 안 본다**(PLAN §1 #37 의 「겹침은 못 잡는다」가 실제로 난 자리).
      ② 이 그림이 기획서 [그림 22] 를 대신한다(`tools/docx_figs.py`). 손그림이 담던
         「확인 구간 / 미확인 구간」 대비를 정본 값으로 다시 그린 것이다. 대신 GSD 수치는
         안 적는다 — `params.py` 에 없는 값을 그림이 지어내면 그림이 또 하나의 손대장이다.
    """
    p = _params()
    r = p.get("CCTV_RANGE", 25.0)
    x0, xm, x1, y, h = 60, 420, 690, 96, 58
    body = [f'<text x="12" y="30" font-size="15" font-weight="700" '
            f'fill="#0f172a">유효 측정 범위 — 카메라에서 {r:g}m</text>',
            '<text x="12" y="50" font-size="11" fill="#64748b">'
            '정본 src/firelane/seg/params.py · CCTV_RANGE</text>',
            '<defs><pattern id="h" width="8" height="8" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" '
            'stroke="#cbd5e1" stroke-width="3"/></pattern></defs>',
            f'<rect x="{x0}" y="{y}" width="{xm - x0}" height="{h}" fill="#dcfce7" '
            f'stroke="{COLOR["clear"]}" rx="3"/>',
            f'<rect x="{xm}" y="{y}" width="{x1 - xm}" height="{h}" fill="url(#h)" '
            f'stroke="#94a3b8" rx="3"/>',
            f'<polygon points="{x0 - 18},{y + h / 2 - 9} {x0 - 2},{y + h / 2} '
            f'{x0 - 18},{y + h / 2 + 9}" fill="#0f172a"/>',
            f'<text x="{x0 - 20}" y="{y - 10}" font-size="11" fill="#0f172a">카메라</text>',
            f'<text x="{(x0 + xm) / 2}" y="{y + 35}" font-size="12" '
            f'fill="#166534" text-anchor="middle">확인 완료 구간 — 판정 유효</text>',
            f'<text x="{(xm + x1) / 2}" y="{y + 35}" font-size="12" '
            f'fill="#475569" text-anchor="middle">미확인 구간 — unknown 으로 출력</text>',
            f'<line x1="{x0}" y1="{y + h + 26}" x2="{xm}" y2="{y + h + 26}" '
            f'stroke="{COLOR["clear"]}" marker-end="url(#a)"/>',
            '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
            f'markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z" '
            f'fill="{COLOR["clear"]}"/></marker></defs>',
            f'<text x="{(x0 + xm) / 2}" y="{y + h + 48}" font-size="12" '
            f'fill="#166534" text-anchor="middle">카메라에서 {r:g}m 까지</text>',
            f'<text x="{(xm + x1) / 2}" y="{y + h + 48}" font-size="12" '
            f'fill="#475569" text-anchor="middle">호모그래피 오차가 급격히 커진다</text>',
            # ★ 2026-09-20 (W4-6). `unknown` 이라고 적었고 **백틱이 그대로 그려졌다.**
            #   SVG `<text>` 는 마크다운을 모른다 — 여기서 백틱은 코드 표기가 아니라
            #   그냥 글자다. 그림에 쓰는 문자열은 마크다운이 아니라는 것이
            #   `tests/test_figure_text.py` 로 강제된다.
            f'<text x="{x0}" y="{y + h + 84}" font-size="12" fill="{COLOR["blocked"]}">'
            '※ 이 경계를 안 정하면 보지도 못한 구간을 통과 가능이라고 말하게 된다 — '
            '밖은 unknown 이지 통과가 아니다.</text>']
    return _svg("".join(body), h=y + h + 104)


def fig_unknown() -> str:
    """영상판정 불가의 사유 분해. golden 이 정본이다."""
    g = _golden()
    rs = g["unknown_reason"]
    tot = sum(rs.values())
    ko = {"no_cctv_band": "대역 밖", "no_cctv_thin": "폭 부족",
          "no_cctv_narrow": "각도 부족", "no_cctv_single": "단일 관측"}
    body = [f'<text x="12" y="30" font-size="15" font-weight="700" '
            f'fill="#0f172a">영상판정 불가 {tot}구간의 사유</text>',
            '<text x="12" y="50" font-size="11" fill="#64748b">'
            '정본 data/golden — 전부 CCTV 사각이며 폭 산출 불가는 0이다</text>']
    x = 80   # ★ 2026-09-22 (DECISIONS §218-6) 60 이면 「각도 부족」이 막대에 닿는다
    for i, (k, c) in enumerate(sorted(rs.items(), key=lambda kv: -kv[1])):
        wd = round(560 * c / tot, 1)
        body.append(f'<rect x="{x}" y="{80 + i * 44}" width="{wd}" height="28" '
                    f'fill="{COLOR["unknown"]}" rx="3"/>')
        body.append(f'<text x="{x + wd + 8}" y="{100 + i * 44}" font-size="13" '
                    f'fill="#0f172a">{c}</text>')
        body.append(f'<text x="12" y="{100 + i * 44}" font-size="11" '
                    f'fill="#475569">{ko.get(k, k)}</text>')
    return _svg("".join(body), h=80 + 4 * 44 + 16)


def _rulesets() -> list[tuple[str, str, str]]:
    """`MASTER §12-1` 룰셋 표에서 (룰셋, 대상, 승인). 정본은 그 표다."""
    txt = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^\|\s*`(\w+)`\s*\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|",
                         txt, re.M):
        out.append((m.group(1), m.group(2), m.group(3)))
    return out


def fig_branch() -> str:
    """브랜치 4계층. `MASTER §12-1` 룰셋 표와 CODEOWNERS 가 정본이다.

    ★ 값이 아니라 **구조**를 그린다. 2026-09-02 에 틀린 것이 그 종류였다 —
      [그림 24] 가 EC2 인데 §12-8 은 ECS 였고, 숫자가 아니라 관계가 갈렸다.
      값 그림은 docnum_check 가 반쯤 잡는데 구조 그림은 아무도 안 봤다.
    """
    rs = {r[0]: r for r in _rulesets()}
    # ★ 파트 목록의 정본은 `tools/branch_tidy.sh` 의 KEEP_RE(지키는 가지)다.
    #   2026-09-22 (DECISIONS §218) — 종전엔 CODEOWNERS 의 `@woongtopia/<파트>` 를 셌는데
    #   2026-09-09 단독 소유 전환 뒤 그 핸들은 **이력 주석**에만 남아, 그림이 주석 한 줄에서
    #   `part/gis` 하나를 그리고 있었다. 가지 목록은 가지를 지키는 도구가 든다.
    keep = re.search(r"KEEP_RE='\^\(([^)]*)\)\$'",
                     (ROOT / "tools/branch_tidy.sh").read_text(encoding="utf-8"))
    parts = sorted(b.split("/", 1)[1] for b in (keep.group(1).split("|") if keep else [])
                   if b.startswith("part/"))

    def box(x, y, w, label, sub_, fill, stroke):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="46" rx="6" '
                f'fill="{fill}" stroke="{stroke}"/>'
                f'<text x="{x + w / 2}" y="{y + 21}" font-size="13" '
                f'font-weight="700" fill="#0f172a" text-anchor="middle">{label}</text>'
                f'<text x="{x + w / 2}" y="{y + 37}" font-size="10" '
                f'fill="#64748b" text-anchor="middle">{sub_}</text>')

    def arrow(x1, y1, x2, y2):
        return (f'<path d="M{x1} {y1} L{x2} {y2}" stroke="#94a3b8" '
                f'fill="none" marker-end="url(#a)"/>')

    body = ['<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto">'
            '<path d="M0 0 L10 5 L0 10 z" fill="#94a3b8"/></marker></defs>',
            '<text x="12" y="28" font-size="15" font-weight="700" '
            'fill="#0f172a">브랜치 4계층 — 정본 MASTER §12-1</text>']

    rel = rs.get("release", ("release", "refs/heads/main", "?"))
    tr = rs.get("trunk", ("trunk", "refs/heads/dev", "?"))
    pt = rs.get("part", ("part", "refs/heads/part/**", "?"))

    body.append(box(280, 50, 160, "main", f"승인 {rel[2]} · 배포", "#fee2e2", "#ef4444"))
    body.append(box(280, 130, 160, "dev", f"승인 {tr[2]} · 통합", "#dbeafe", "#3b82f6"))
    body.append(arrow(360, 130, 360, 100))
    for i, p in enumerate(parts):
        x = 60 + i * 200
        body.append(box(x, 210, 160, f"part/{p}", f"승인 {pt[2]} · 파트", "#dcfce7", "#22c55e"))
        body.append(arrow(x + 80, 210, 360, 180))
        body.append(box(x, 285, 160, f"feat/{p}-*", "당일 · 룰셋 밖", "#f1f5f9", "#cbd5e1"))
        body.append(arrow(x + 80, 285, x + 80, 260))
    body.append('<text x="12" y="352" font-size="11" fill="#64748b">'
                '화살표는 PR 방향이다. 위 셋은 보호 브랜치이며 직푸시가 막힌다 — '
                '자유롭게 만들고 지울 수 있는 것은 feat 뿐이다(§12-4).</text>')
    return _svg("".join(body), h=372)


def fig_deploy() -> str:
    """배포. `MASTER §12-8` · `workflows/*.yml` · `docker-compose.yml` 이 정본."""
    # ★ 2026-09-22 (DECISIONS §218) — `wf[:4]` 자르기를 없앴다. 알파벳순 앞 넷이
    #   contract · deploy-dry 가 되어 **배포가 아닌 것**이 「main 푸시」 칸에 그려졌다.
    # ★ 2026-09-23 (DECISIONS §224) — 배포 여섯을 하나로 합쳤다. 재사용 본문
    #   (`_deploy.yml`)이 없어졌으므로 그 이름으로 고를 수 없다. **사이트를 짓는
    #   것**(`stage-site`)이면서 push 로 도는 것을 센다 — 정본이 그 호출이다.
    #   종전의 `_` 접두사 걸러내기도 같이 없앴다. 거를 대상이 사라졌다.
    #   칸이 넘치면 줄 수만큼 늘린다.
    wf = sorted(p.stem for p in (ROOT / ".github/workflows").glob("*.yml")
                if "./.github/actions/stage-site" in (txt := p.read_text(encoding="utf-8"))
                and "push:" in txt)
    svcs = re.findall(r"^  (\w+):", (ROOT / "docker-compose.yml")
                      .read_text(encoding="utf-8"), re.M)

    def box(x, y, w, h, label, sub_, fill, stroke):
        out = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
               f'fill="{fill}" stroke="{stroke}"/>'
               f'<text x="{x + w / 2}" y="{y + 20}" font-size="12" '
               f'font-weight="700" fill="#0f172a" text-anchor="middle">{label}</text>')
        for i, line in enumerate(sub_):
            out += (f'<text x="{x + w / 2}" y="{y + 38 + i * 15}" font-size="10" '
                    f'fill="#64748b" text-anchor="middle">{line}</text>')
        return out

    body = ['<defs><marker id="b" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto">'
            '<path d="M0 0 L10 5 L0 10 z" fill="#94a3b8"/></marker></defs>',
            '<text x="12" y="28" font-size="15" font-weight="700" '
            'fill="#0f172a">배포 — 정본 MASTER §12-8 · workflows · compose</text>',
            box(20, 55, 170, 40 + 15 * max(3, len(wf)), "main 푸시", wf, "#f1f5f9", "#cbd5e1"),
            box(230, 55, 150, 90, "GitHub Pages",
                ["내비 · 관제(입구)", "협업 방침 · 기획서", "data/ 정적 JSON"],
                "#dbeafe", "#3b82f6"),
            box(420, 55, 150, 90, "ECR", ["이미지 태그 =", "커밋 해시"],
                "#fef3c7", "#f59e0b"),
            box(610, 55, 90, 90, "EC2 한 대", ["Compose"], "#dcfce7", "#22c55e"),
            box(420, 175, 280, 80, "docker compose",
                [" · ".join(svcs) or "web · etl", "restart: unless-stopped"],
                "#f8fafc", "#cbd5e1"),
            '<path d="M190 100 L228 100" stroke="#94a3b8" marker-end="url(#b)"/>',
            '<path d="M380 100 L418 100" stroke="#94a3b8" marker-end="url(#b)"/>',
            '<path d="M570 100 L608 100" stroke="#94a3b8" marker-end="url(#b)"/>',
            '<path d="M655 145 L600 173" stroke="#94a3b8" marker-end="url(#b)"/>',
            '<text x="20" y="285" font-size="11" fill="#64748b">'
            '★ ECS 가 아니다. 상시 서비스가 API 하나이고 ETL 은 배치이며 DB 가 '
            '없다. 되돌릴 조건은 DECISIONS §93-4 가 든다.</text>',
            '<text x="20" y="305" font-size="11" fill="#64748b">'
            '★ 한 대는 단일 장애점이다. 자동 복구는 restart 하나이고 '
            '인스턴스가 죽으면 사람이 띄운다.</text>']
    return _svg("".join(body), h=325)


def fig_xsec() -> str:
    """도로폭 산출 — 법선 트랜섹트와 평면교차점 실형상 제외. 기획서 [그림 13].

    ★ 2026-09-24 (PLAN §12 #15). 기획서 [그림 13] 은 **반경 5m 원 하나만**
      그린다. 캡션은 2026-09-01 에 「평면교차점 실형상 제외」로 고쳐졌는데
      그림은 안 고쳐졌다 — 캡션과 그림이 서로 다른 모델을 말하는 채로
      석 주를 서 있었다. 캡션만 보는 검사(`docx_check`)로는 못 잡는다.

      실제 규칙은 `seg/width.py` 가 든다 — **평면교차점 폴리곤이 가까이
      있으면 폴리곤만 믿고**(`distance < XSEC_EXCL * 2`), 폴리곤이 아예
      없는 교차로에서만 노드 반경으로 폴백한다. 원은 **폴백**이지 규칙이
      아니다. 그림이 폴백만 그리면 읽는 사람은 규칙을 원으로 안다.

    ★ 원이 왜 폴백인가를 그림 자체가 말한다 — 위아래 두 줄이 **같은 길 ·
      같은 표본**인데 버려지는 표본 수가 다르다. 원은 작은 교차부를
      과하게 도려내고, 큰 교차부에서는 오염을 남긴다.

    ★ 교차부 모양은 **모식**이다. 실형상은 교차부마다 다르고 그 정본은
      `ngii1k_xsec_5186.gpkg`(A0080000)다 — 값이 아니라 **규칙**을 그린다.
      값 그림과 구조 그림을 가르는 것은 `fig_branch` 와 같다.
    """
    p = _params()
    # ★ **기본값을 안 둔다.** 다른 그림들은 `p.get(키, 사본)` 으로 적는데
    #   그 사본이 정본과 갈리면 그림이 조용히 옛 값을 그린다 — 이 그림이
    #   바로 그 병으로 났다. 없으면 우는 쪽이 낫다.
    if "XSEC_EXCL" not in p:
        raise SystemExit("★ params.py 에서 XSEC_EXCL 을 못 읽었다 — "
                         "이름이 바뀌었거나 표기가 바뀌었다. 그림을 지어내지 않는다.")
    r_m = p["XSEC_EXCL"]
    px_m = 8.0                  # 1m = 8px. 그림 안에서만 쓰는 축척이다
    r = r_m * px_m
    half = 3.0 * px_m                # 노면 반폭 3m — 모식값
    x0, x1, cx = 44.0, 684.0, 410.0
    poly_half = 26.0                 # 실형상 가로 반폭(모식) — 원보다 작다

    def road(cy: float) -> str:
        """가로 노면 + 세로 노면. 사각형이 아니라 실제로 십자 도형이다."""
        return (f'<path d="M{x0} {cy - half} H{x1} V{cy + half} H{x0} Z" '
                f'fill="#f1f5f9" stroke="#cbd5e1"/>'
                f'<path d="M{cx - half} {cy - 40} H{cx + half} V{cy + 40} '
                f'H{cx - half} Z" fill="#f1f5f9" stroke="#cbd5e1"/>')

    def ticks(cy: float, drop) -> tuple[str, int, int]:
        """법선 트랜섹트. 버린 것은 회색 점선, 잰 것은 초록 실선."""
        out, n, k = [], 0, 0
        t = x0 + 14
        while t <= x1 - 14:
            n += 1
            bad = drop(t)
            k += bad
            style = ('stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="3 3"'
                     if bad else f'stroke="{COLOR["clear"]}" stroke-width="2"')
            out.append(f'<line x1="{t:.0f}" y1="{cy - half - 6:.0f}" '
                       f'x2="{t:.0f}" y2="{cy + half + 6:.0f}" {style}/>')
            t += 2.0 * px_m          # 표본 간격 2m
        return "".join(out), n, k

    a_cy, b_cy = 118.0, 232.0
    a_body, a_n, a_k = ticks(a_cy, lambda t: abs(t - cx) < r)
    b_body, b_n, b_k = ticks(b_cy, lambda t: abs(t - cx) < poly_half)

    # 실형상 모식 — 네 갈래가 만나는 자리라 사각형이 아니다
    ph, pw = 30.0, poly_half
    shape = (f'<path d="M{cx - pw} {b_cy - ph} L{cx + pw - 6} {b_cy - ph + 4} '
             f'L{cx + pw} {b_cy + 2} L{cx + pw - 8} {b_cy + ph} '
             f'L{cx - pw + 4} {b_cy + ph - 3} L{cx - pw - 2} {b_cy - 4} Z" '
             f'fill="#fed7aa" fill-opacity="0.8" stroke="{COLOR["needs_cv"]}" '
             f'stroke-width="2"/>')

    # ★ 그림 → 글자 순서로 쌓는다. 종전 배치에서 세로 노면이 줄머리 라벨을
    #   덮었다 — SVG 는 뒤에 온 것이 위에 그려지고, `_fits()` 는 `<path>` 를
    #   안 본다(도형은 `<rect>` · `<circle>` 만 본다).
    art = [
        road(a_cy), a_body,
        f'<circle cx="{cx:.0f}" cy="{a_cy:.0f}" r="{r:.0f}" fill="none" '
        f'stroke="{COLOR["blocked"]}" stroke-width="2" stroke-dasharray="6 4"/>',
        road(b_cy), shape, b_body,
    ]
    txt = [
        '<text x="12" y="28" font-size="15" font-weight="700" fill="#0f172a">'
        '도로폭 산출 — 법선 트랜섹트와 평면교차점 실형상 제외</text>',
        '<text x="12" y="48" font-size="11" fill="#64748b">'
        '정본 src/firelane/seg/params.py · XSEC_EXCL — 규칙은 seg/width.py</text>',
        f'<text x="{x0:.0f}" y="68" font-size="12" fill="#475569">'
        f'폴백 — 평면교차점 실형상이 없는 교차로에서만. 노드에서 {r_m:g}m</text>',
        f'<text x="676" y="{a_cy - 34:.0f}" font-size="12" fill="#0f172a" '
        f'text-anchor="end">표본 {a_n} · 버림 {a_k}</text>',
        f'<text x="{x0:.0f}" y="182" font-size="12" fill="#475569">'
        '실형상 — 평면교차점 폴리곤 안의 표본만 버린다. 이쪽이 규칙이다</text>',
        f'<text x="676" y="{b_cy - 34:.0f}" font-size="12" fill="#0f172a" '
        f'text-anchor="end">표본 {b_n} · 버림 {b_k}</text>',
        '<text x="12" y="300" font-size="11" fill="#64748b">'
        '세로선 하나가 법선 트랜섹트 한 번이다 — 초록은 잰 것, 회색 점선은 '
        '버린 것이다.</text>',
        f'<text x="12" y="318" font-size="11" fill="{COLOR["blocked"]}">'
        f'※ 원은 규칙이 아니라 폴백이다. 반경 {r_m:g}m 는 작은 교차부를 '
        '과하게 도려내고 큰 교차부에는 오염을 남긴다.</text>',
    ]
    return _svg("".join(art + txt), h=336)


FIGURES = {
    "verdict": fig_verdict,
    "threshold": fig_threshold,
    "cctv": fig_cctv,
    "unknown": fig_unknown,
    # ★ 구조 그림. 값이 아니라 관계를 그린다 — 2026-09-02 에 틀린 것이
    #   그 종류였다(DECISIONS §110).
    "branch": fig_branch,
    "deploy": fig_deploy,
    # ★ 2026-09-24 (PLAN §12 #15). 캡션은 고쳐졌는데 그림이 옛 모델을 그리던
    #   자리다. 값이 아니라 **규칙**을 그린다.
    "xsec": fig_xsec,
}


def main() -> int:
    check = "--check" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, fn in FIGURES.items():
        svg = fn()
        made[name] = hashlib.sha256(svg.encode("utf-8")).hexdigest()[:16]
        if not check:
            (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")

    old = {}
    if LOCK.exists():
        old = json.loads(LOCK.read_text(encoding="utf-8")).get("figures", {})

    drift = [k for k, v in made.items() if old.get(k) not in (None, v)]
    if check:
        if drift:
            print("★ 그림이 정본과 어긋난다 — " + " · ".join(drift))
            print("  값이 바뀌었는데 기획서 그림이 옛 값을 그리고 있다.")
            print("  uv run python tools/render_figures.py         다시 만든다")
            print("  uv run python tools/docx_figs.py --sync       기획서에 넣는다")
            # ★ 2026-09-23 (DECISIONS §221-1). 종전에는 여기서 「사람이 넣는다 — 기획서는
            #   대외 제출본이고 생성물이 아니다」 라고 했다. 그 사이 `docx_fix.py` 가 같은
            #   파일의 문단을 기계로 고치고 있었고, 「사람이 넣는다」 는 곧 「안 넣는다」 였다.
            return 1
        if not old:
            print("! 잠금이 없다 — 한 번 생성해서 기준을 만들어라")
            return 1
        print(f"그림 OK — {len(made)}장 정본과 일치")
        return 0

    # ★ 2026-09-23. 잠금을 **덮어쓰지 않고 합친다.** `docx_figs.py` 가 같은 파일에
    #   `placed`(기획서에 박힌 지문)를 쓴다 — 덮어쓰면 그쪽 기록이 매번 사라지고,
    #   그러면 「기획서가 낡았는가」 를 묻는 관문이 조용히 통과한다.
    keep = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    LOCK.write_text(json.dumps({**keep, "figures": made}, ensure_ascii=False,
                               indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    for k in sorted(made):
        mark = " ★ 바뀜" if k in drift else ""
        print(f"  docs/figures/{k}.svg  {made[k]}{mark}")
    if drift:
        print("\n★ 바뀐 그림을 기획서에 넣는다:  uv run python tools/docx_figs.py --sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
