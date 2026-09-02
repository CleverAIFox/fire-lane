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

★ `.docx` 안 이미지를 코드가 교체하지는 않는다. 기획서는 대외 제출본이고
  생성물이 아니다(4축 표). 여기서는 **SVG 를 만들고 어긋남을 알린다** —
  교체는 사람이 한다. 알기만 해도 오늘 나온 문제는 다 잡힌다.

IN    data/golden/segments.fingerprint.json · src/firelane/seg/params.py
OUT   docs/figures/*.svg · docs/figures/.lock.json
PARAM --check
"""
from __future__ import annotations

import hashlib
import json
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
        for key in ("TRUCK", "CCTV_RANGE", "XSEC_EXCL", "WMAX_CAP", "SNAP_TOL"):
            if line.startswith(key):
                try:
                    out[key] = float(line.split("=")[1].split("#")[0].strip())
                except ValueError:
                    pass
    return out


def _svg(body: str, *, w: int = W, h: int = H) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" font-family="{FONT}">'
            f'<rect width="{w}" height="{h}" fill="#fff"/>{body}</svg>\n')


def fig_verdict() -> str:
    """판정 4종 분포. 값은 golden 이 정본이다."""
    g = _golden()
    v, n = g["verdict"], g["n"]
    x, bars, legend = 60, [], []
    for i, k in enumerate(("clear", "needs_cv", "blocked", "unknown")):
        c = v[k]
        wd = round(560 * c / n, 1)
        bars.append(f'<rect x="{x}" y="{70 + i * 46}" width="{wd}" height="30" '
                    f'fill="{COLOR[k]}" rx="3"/>')
        bars.append(f'<text x="{x + wd + 8}" y="{91 + i * 46}" font-size="13" '
                    f'fill="#0f172a">{c}  ({c * 100 / n:.1f}%)</text>')
        legend.append(f'<text x="{x - 48}" y="{91 + i * 46}" font-size="12" '
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
    x0, x1, span = 60, 660, 10.0
    def px(m: float) -> float:
        return x0 + (x1 - x0) * min(m, span) / span
    bands = [(0, truck, COLOR["blocked"], "통행 불가"),
             (truck, 7.0, COLOR["needs_cv"], "판정 보류"),
             (7.0, span, COLOR["clear"], "통행 가능")]
    body = [f'<text x="12" y="30" font-size="15" font-weight="700" '
            f'fill="#0f172a">폭 임계 — 통과 하한 {truck}m · 여유 7.0m</text>',
            '<text x="12" y="50" font-size="11" fill="#64748b">'
            '정본 src/firelane/seg/params.py</text>']
    for a, b, c, lab in bands:
        body.append(f'<rect x="{px(a):.1f}" y="90" width="{px(b) - px(a):.1f}" '
                    f'height="42" fill="{c}" rx="3"/>')
        body.append(f'<text x="{(px(a) + px(b)) / 2:.1f}" y="116" font-size="12" '
                    f'fill="#fff" text-anchor="middle">{lab}</text>')
    for m in (0, truck, 7.0, span):
        body.append(f'<line x1="{px(m):.1f}" y1="132" x2="{px(m):.1f}" y2="146" '
                    f'stroke="#94a3b8"/>')
        body.append(f'<text x="{px(m):.1f}" y="164" font-size="11" '
                    f'fill="#475569" text-anchor="middle">{m:g}m</text>')
    body.append('<text x="60" y="196" font-size="11" fill="#64748b">'
                '최소 폭이 하한 미만이면 통행 불가, 7.0m 이상이면 통행 가능. '
                '그 사이는 영상판정 대상이다.</text>')
    return _svg("".join(body), h=220)


def fig_cctv() -> str:
    """유효 측정 범위. `CCTV_RANGE` 가 정본이다."""
    p = _params()
    r = p.get("CCTV_RANGE", 25.0)
    cx, cy, rr = 200, 150, 110
    body = [f'<text x="12" y="30" font-size="15" font-weight="700" '
            f'fill="#0f172a">유효 측정 범위 — 반경 {r:g}m</text>',
            '<text x="12" y="50" font-size="11" fill="#64748b">'
            '정본 src/firelane/seg/params.py · CCTV_RANGE</text>',
            f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="#eff6ff" '
            f'stroke="#3b82f6" stroke-dasharray="5 4"/>',
            f'<circle cx="{cx}" cy="{cy}" r="5" fill="#1d4ed8"/>',
            f'<text x="{cx}" y="{cy - 14}" font-size="11" fill="#1e3a8a" '
            f'text-anchor="middle">CCTV</text>',
            f'<line x1="{cx}" y1="{cy}" x2="{cx + rr}" y2="{cy}" '
            f'stroke="#1d4ed8"/>',
            f'<text x="{cx + rr / 2}" y="{cy - 6}" font-size="11" '
            f'fill="#1d4ed8" text-anchor="middle">{r:g}m</text>',
            '<text x="360" y="120" font-size="12" fill="#0f172a">'
            '이 안에 든 구간만 영상으로 판정한다.</text>',
            '<text x="360" y="142" font-size="12" fill="#64748b">'
            '밖은 `unknown` — 모른다고 적지 통과로 보지 않는다.</text>',
            '<text x="360" y="164" font-size="12" fill="#64748b">'
            '거리에 따라 픽셀당 실거리가 커져 오차가 늘어난다.</text>']
    return _svg("".join(body), h=290)


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
    x = 60
    for i, (k, c) in enumerate(sorted(rs.items(), key=lambda kv: -kv[1])):
        wd = round(560 * c / tot, 1)
        body.append(f'<rect x="{x}" y="{80 + i * 44}" width="{wd}" height="28" '
                    f'fill="{COLOR["unknown"]}" rx="3"/>')
        body.append(f'<text x="{x + wd + 8}" y="{100 + i * 44}" font-size="13" '
                    f'fill="#0f172a">{c}</text>')
        body.append(f'<text x="{x - 48}" y="{100 + i * 44}" font-size="11" '
                    f'fill="#475569">{ko.get(k, k)}</text>')
    return _svg("".join(body), h=80 + 4 * 44 + 16)


FIGURES = {
    "verdict": fig_verdict,
    "threshold": fig_threshold,
    "cctv": fig_cctv,
    "unknown": fig_unknown,
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
            print("  uv run python tools/render_figures.py  로 다시 만들고")
            print("  docs/figures/*.svg 를 기획서에 넣어라. **사람이 넣는다** —")
            print("  기획서는 대외 제출본이고 생성물이 아니다(4축 표).")
            return 1
        if not old:
            print("! 잠금이 없다 — 한 번 생성해서 기준을 만들어라")
            return 1
        print(f"그림 OK — {len(made)}장 정본과 일치")
        return 0

    LOCK.write_text(json.dumps({"figures": made}, ensure_ascii=False,
                               indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    for k in sorted(made):
        mark = " ★ 바뀜" if k in drift else ""
        print(f"  docs/figures/{k}.svg  {made[k]}{mark}")
    if drift:
        print("\n★ 바뀐 그림을 기획서에 다시 넣어라. 사람이 넣는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
