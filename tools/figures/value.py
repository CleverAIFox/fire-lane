#!/usr/bin/env python3
"""
tools/figures/value.py — 값 그림 — golden · params 의 수를 그린다

정본 목록은 `tools/render_figures.FIGURES` 다.

IN    figures 공용(`__init__`)이 읽는 정본
OUT   SVG 문자열
PARAM 없음
밖    배치(넘침 · 겹침)는 `tools/svg_fit.py` 가 든다.
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
"""
from __future__ import annotations

import svg_fit

from figures import COLOR, LABEL, _golden, _params


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
    return svg_fit.svg(head + "".join(bars) + "".join(legend), h=70 + 4 * 46 + 20)


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
    return svg_fit.svg("".join(body), h=220)


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
    return svg_fit.svg("".join(body), h=y + h + 104)


def fig_unknown() -> str:
    """영상판정 불가의 사유 분해. golden 이 정본이다."""
    g = _golden()
    rs = g["unknown_reason"]
    tot = sum(rs.values())
    # ★ 2026-10-08 (DECISIONS §436-8). 이 표에 `ledger_disputes` 가 없으면
    #   `ko.get(k, k)` 가 **영어 키를 그대로 그린다** — 한글 라벨 넷 사이에
    #   `ledger_disputes` 가 끼어 그림만 보면 빠뜨린 것인지 뜻인지 모른다.
    ko = {"no_cctv_band": "대역 밖", "no_cctv_thin": "폭 부족",
          "no_cctv_narrow": "각도 부족", "no_cctv_single": "단일 관측",
          "ledger_disputes": "대장 반박", "width": "폭 산출 불가"}
    # ★ 머리말이 **「영상판정 불가」였다.** 그 말은 `no_cctv_*` 넷만 참이고
    #   `ledger_disputes` 는 카메라와 무관하다 — 낱말이 늘자 머리말이 거짓이
    #   됐다. 둘째 줄의 「0이다」도 손으로 적은 수였다. 수는 정본에서 읽는다.
    body = [f'<text x="12" y="30" font-size="15" font-weight="700" '
            f'fill="#0f172a">회색(unknown) {tot}구간의 사유</text>',
            f'<text x="12" y="50" font-size="11" fill="#64748b">'
            f'정본 data/golden — {len(rs)}가지 · 폭 산출 불가 '
            f'{rs.get("width", 0)}</text>']
    x = 80   # ★ 2026-09-22 (DECISIONS §218-6) 60 이면 「각도 부족」이 막대에 닿는다
    for i, (k, c) in enumerate(sorted(rs.items(), key=lambda kv: -kv[1])):
        wd = round(560 * c / tot, 1)
        body.append(f'<rect x="{x}" y="{80 + i * 44}" width="{wd}" height="28" '
                    f'fill="{COLOR["unknown"]}" rx="3"/>')
        body.append(f'<text x="{x + wd + 8}" y="{100 + i * 44}" font-size="13" '
                    f'fill="#0f172a">{c}</text>')
        body.append(f'<text x="12" y="{100 + i * 44}" font-size="11" '
                    f'fill="#475569">{ko.get(k, k)}</text>')
    # ★ 높이에 `4` 가 박혀 있었다. 사유가 다섯이 되면 다섯째 막대가 **판 밖에서
    #   그려진다** — SVG 는 안 운다. 넷이던 동안은 보이지 않던 결함이다.
    return svg_fit.svg("".join(body), h=80 + len(rs) * 44 + 16)


