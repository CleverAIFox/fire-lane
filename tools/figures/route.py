#!/usr/bin/env python3
"""
tools/figures/route.py — 경로 탐색 그림. **장부의 수를 그린다.**

★ 2026-10-11 (DECISIONS §465 · PLAN §1 #71 닫힘). `#71` 은 「A* 대 다익스트라
  실행시간 비교 그래프 한 장」을 들고 있었고, 그 행이 스스로 적은 사유가
  **「A* 를 쓰는 이유는 속도가 아니다」**였다. 그런데 그 말을 뒷받침하는 수가
  어디에도 없었다.

★ **벽시계를 안 그린다.** 밀리초는 그 기계의 부하를 타고, 같은 입력에 다른
  그림이 나오면 그림이 아니다. 그리는 것은 **전개한 상태 수**다 —
  `web/navi/test/astarbench.test.ts` 가 발행 그래프에서 재고 그 수를
  `data/golden/astar.json` 에 적는다. 그 시험이 **매 실행 장부를 대조**하므로
  이 그림은 받아적은 수가 아니라 재서 적은 수를 그린다.

★ 파이썬이 그리는 이유 — `render_figures` 는 node 가 없는 기계에서도 돈다.
  수를 장부에 커밋해 두면 그림은 어디서든 같다.

IN    data/golden/astar.json
OUT   SVG 문자열
PARAM 없음
밖    **왜 그 수인가는 안 말한다** — 측정의 사유는 그 시험 머리말과 §465 가 든다
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
"""
from __future__ import annotations

import json

import svg_fit

from . import ROOT

#: 이득이 있는 쪽 · 없는 쪽. 판정 색을 **안 쓴다** — 판정과 무관한 그림이고
#: 같은 색을 쓰면 읽는 사람이 판정으로 읽는다.
GAIN, FLAT = "#2563eb", "#64748b"


def _bench() -> dict:
    """측정 장부. **없으면 죽는다** — 0 을 그리면 그림이 거짓말을 한다."""
    p = ROOT / "data/golden/astar.json"
    if not p.is_file():
        raise SystemExit(f"★ {p} 가 없다 — `npx vitest run test/astarbench.test.ts`"
                         " 로 먼저 재라")
    d = json.loads(p.read_text(encoding="utf-8"))
    for k in ("nodes", "pairs", "one_to_one", "one_to_all"):
        if k not in d:
            raise SystemExit(f"★ 장부에 `{k}` 가 없다 — 옛 판 장부다")
    return d


#: 막대가 시작하는 칸 · 가장 긴 막대의 폭 · 수를 적는 칸.
#: ★ 수를 **고정 칸**에 적는다. 막대 끝에 붙이면 그 기준점이 막대 안으로
#:   들어가고, `svg_fit` 은 「박스보다 긴 라벨」로 읽는다 — 실제로 네 줄이
#:   그렇게 울었다. `dx` 로 밀어도 안 된다: 그 검사는 `x` 만 본다.
BAR_X, BAR_W, NUM_X = 190, 420.0, 624


def _bar(y: int, w: float, color: str, label: str, num: str) -> list[str]:
    """막대 하나 · 왼쪽 라벨 · 오른쪽 수."""
    return [f'<rect x="{BAR_X}" y="{y}" width="{w:.1f}" height="26" '
            f'fill="{color}" rx="3"/>',
            f'<text x="12" y="{y + 18}" font-size="11" fill="#475569">{label}</text>',
            f'<text x="{NUM_X}" y="{y + 18}" font-size="12" fill="#0f172a">{num}</text>']


def fig_astar() -> str:
    """A* 가 어디서 이득이고 어디서 아닌가. **두 일감을 나란히 둔다.**

    ★ 한 그림에 둘을 같이 두는 것이 이 그림의 전부다. 1→1 만 그리면
      「A* 가 3배 빠르다」로 읽히고, 그 말로 현재 산출을 설명하면 틀린다.
    """
    b = _bench()
    one, allg = b["one_to_one"], b["one_to_all"]
    full = BAR_W

    body = [f'<text x="12" y="30" font-size="15" font-weight="700" fill="#0f172a">'
            f'A* 와 다익스트라 — 전개한 상태 수 (노드 {b["nodes"]:,})</text>',
            '<text x="12" y="50" font-size="11" fill="#64748b">'
            '정본 data/golden/astar.json · web/navi/test/astarbench.test.ts 가 잰다</text>',
            f'<text x="12" y="80" font-size="12" font-weight="700" fill="{GAIN}">'
            f'① 내비 — 출발 1 → 도착 1 (무작위 {b["pairs"]}쌍 합)</text>']

    # ★ **네 막대가 한 자를 쓴다.** 묶음마다 최대로 정규화하면 ② 의 쓸기가
    #   ① 의 A* 만큼 길어 보이고, 그러면 이 그림이 말하려는 것의 반대가 된다.
    #   `tests/test_figure_ink.py` 가 그것을 잡았다 — 교안 「Proportional ink」.
    m1 = m2 = max(one["astar"], one["dijkstra"],
                  allg["astar_sum"], allg["dijkstra_sweep"])
    body += _bar(92, full * one["astar"] / m1, GAIN,
                 "A*", f'{one["astar"]:,}')
    body += _bar(124, full * one["dijkstra"] / m1, FLAT,
                 "다익스트라", f'{one["dijkstra"]:,}')
    body.append(f'<text x="12" y="172" font-size="12" fill="{GAIN}">'
                f'→ A* 가 {one["dijkstra"] / one["astar"]:.1f}배 적게 연다. '
                f'이것이 A* 를 쓰는 이유다</text>')

    body.append(f'<text x="12" y="208" font-size="12" font-weight="700" fill="#0f172a">'
                f'② 현재 산출 — 안전센터 1 → 전 노드 (목표 {allg["goals"]:,})</text>')
    body += _bar(220, full * allg["astar_sum"] / m2, FLAT,
                 "A* 를 목표마다", f'{allg["astar_sum"]:,}')
    body += _bar(252, full * allg["dijkstra_sweep"] / m2, GAIN,
                 "다익스트라 한 번", f'{allg["dijkstra_sweep"]:,}')
    body.append(f'<text x="12" y="300" font-size="12" fill="#0f172a">'
                f'→ 다익스트라는 한 번에 전부 푼다. A* 는 '
                f'{allg["astar_sum"] / allg["dijkstra_sweep"]:.0f}배 더 연다 — '
                f'여기서는 이득이 없다</text>')
    body.append('<text x="12" y="326" font-size="11" fill="#64748b">'
                '휴리스틱은 목표 하나를 향하므로 목표가 바뀌면 다시 열어야 한다. '
                '그래서 일감이 고르는 것이다</text>')
    return svg_fit.svg("".join(body), h=344)
