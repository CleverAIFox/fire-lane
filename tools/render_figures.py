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
        for key in ("TRUCK", "CCTV_RANGE", "XSEC_EXCL", "WMAX_CAP", "SNAP_TOL"):
            if line.startswith(key):
                try:
                    out[key] = float(line.split("=")[1].split("#")[0].strip())
                except ValueError:
                    pass
    return out


def _fits(body: str, w: int, h: int) -> list[str]:
    """모든 요소가 `viewBox` 안에 있는가.

    ★ 2026-09-02. `fig_branch` 는 파트가 셋이라 `x = 60 + i*200` 으로 720
      안에 들어간다. **넷이 되면 넘친다.** 그런데 넘쳐도 SVG 는 오류 없이
      그려진다 — 박스가 화면 밖으로 나갈 뿐이고 **아무도 모른다.**

      `--check` 는 값이 바뀐 것을 잡지 배치가 깨진 것은 못 잡는다.
      좌표가 코드에 박혀 있는 한(레이아웃 엔진이 없다) 이 검사가 그
      자리를 대신한다(DECISIONS §111).
    """
    bad = []
    for m in re.finditer(r'<rect x="([\d.]+)" y="([\d.]+)" '
                         r'width="([\d.]+)" height="([\d.]+)"', body):
        x, y, bw, bh = (float(g) for g in m.groups())
        if x < 0 or y < 0 or x + bw > w or y + bh > h:
            bad.append(f"박스 ({x:g},{y:g} {bw:g}x{bh:g}) 가 {w}x{h} 밖이다")
    for m in re.finditer(r'<text x="([\d.]+)" y="([\d.]+)"', body):
        x, y = float(m.group(1)), float(m.group(2))
        if x < 0 or y < 0 or x > w or y > h:
            bad.append(f"글자 ({x:g},{y:g}) 가 {w}x{h} 밖이다")
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
    # ★ 파트 목록은 CODEOWNERS 가 정본이다. 파트가 늘면 그림도 따라온다 —
    #   그리고 넷이 되면 `_fits()` 가 넘침을 잡는다(DECISIONS §111).
    parts = sorted(set(re.findall(
        r"@woongtopia/(\w+)",
        (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8"))))

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
    wf = sorted(p.stem for p in (ROOT / ".github/workflows").glob("*.yml"))
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
            box(20, 55, 170, 90, "main 푸시", wf[:4], "#f1f5f9", "#cbd5e1"),
            box(230, 55, 150, 90, "GitHub Pages",
                ["지도 · 협업 방침", "플레이북 · 기획서", "정적 파일"],
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


FIGURES = {
    "verdict": fig_verdict,
    "threshold": fig_threshold,
    "cctv": fig_cctv,
    "unknown": fig_unknown,
    # ★ 구조 그림. 값이 아니라 관계를 그린다 — 2026-09-02 에 틀린 것이
    #   그 종류였다(DECISIONS §110).
    "branch": fig_branch,
    "deploy": fig_deploy,
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
