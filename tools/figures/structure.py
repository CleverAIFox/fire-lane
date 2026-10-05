#!/usr/bin/env python3
"""
tools/figures/structure.py — 구조 그림 — 값이 아니라 관계를 그린다

정본 목록은 `tools/render_figures.FIGURES` 다.

IN    figures 공용(`__init__`)이 읽는 정본
OUT   SVG 문자열
PARAM 없음
밖    배치(넘침 · 겹침)는 `tools/svg_fit.py` 가 든다.
부류  생산   산출물·대장·그림을 만든다  (DECISIONS §398)
"""
from __future__ import annotations

import re

import svg_fit

from figures import COLOR, LABEL, ROOT, _golden, _params


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
    return svg_fit.svg("".join(body), h=372)


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
    return svg_fit.svg("".join(body), h=325)


def _contract_fields() -> dict[str, list[str]]:
    """`src/contracts/vision.py` 의 두 계약 모델 필드. **임포트하지 않는다** —
    도구가 파이프라인에 안 붙는다(`_params()` 와 같은 이유). AST 로 읽는다."""
    import ast
    src = (ROOT / "src/contracts/vision.py").read_text(encoding="utf-8")
    out: dict[str, list[str]] = {}
    for c in ast.parse(src).body:
        if isinstance(c, ast.ClassDef) and c.name in ("ObsSpec", "VisionResult"):
            out[c.name] = [n.target.id for n in c.body
                           if isinstance(n, ast.AnnAssign)
                           and isinstance(n.target, ast.Name)
                           and not n.target.id.startswith("model_")]
    return out


def fig_boundary() -> str:
    """GIS ↔ 비전 모듈 경계. 기획서 [그림 8]. 정본은 `src/contracts/vision.py`.

    ★ 2026-09-28 (DECISIONS §278-4). 종전 [그림 8] 은 저장소 밖에서 그려
      `.docx` 안에만 있는 PNG 였고, **접점 라벨 둘이 같은 자리에 겹쳐** 찍혀
      있었다. 래스터라 고칠 수가 없었다 — 다시 그리는 수밖에 없었다.
      기획서 그림 24장 중 21장이 그 상태다(정본 없음).

    ★ 접점의 필드는 **손으로 안 적는다.** 계약 모델에서 읽는다. 계약이 늘거나
      줄면 그림이 따라 바뀐다 — 두 곳에 적으면 갈린다(R3·R14). 캡션이 주장하는
      「접점은 둘뿐이다」 도 여기서 센다.
    """
    f = _contract_fields()
    obs, res = f["ObsSpec"], f["VisionResult"]
    half = (len(res) + 1) // 2

    def box(x, y, w, h, title, lines, fill, stroke):
        out = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
               f'fill="{fill}" stroke="{stroke}"/>'
               f'<text x="{x + w / 2}" y="{y + 22}" font-size="13" font-weight="700" '
               f'fill="#0f172a" text-anchor="middle">{title}</text>')
        for i, ln in enumerate(lines):
            out += (f'<text x="{x + w / 2}" y="{y + 44 + i * 15}" font-size="10" '
                    f'fill="#64748b" text-anchor="middle">{ln}</text>')
        return out

    body = ['<defs><marker id="m8" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0 0 L10 5 L0 10 z" fill="#64748b"/></marker></defs>',
            '<text x="12" y="24" font-size="15" font-weight="700" fill="#0f172a">'
            'GIS ↔ 비전 모듈 경계 — 정본 src/contracts/vision.py</text>',
            box(14, 44, 165, 100, "GIS 모듈",
                ["세그먼트 도형", "width_min_m", "tier · 커버리지", "그래프 · 경로탐색"],
                "#dcfce7", "#22c55e"),
            box(541, 44, 165, 100, "비전 모듈",
                ["호모그래피", "세그멘테이션", "유효 통행폭 측정"],
                "#fee2e2", "#ef4444"),
            # ── 접점은 둘뿐이다. 화살표는 이름만 지고, 필드는 아래 줄이 진다.
            #    한 줄에 다 실으면 박스를 덮는다 — `svg_fit` 이 그것으로 운다.
            '<path d="M183 76 L537 76" stroke="#64748b" marker-end="url(#m8)"/>',
            '<text x="360" y="68" font-size="11" font-weight="700" fill="#0f172a" '
            'text-anchor="middle">① 관측점 선정</text>',
            '<path d="M537 120 L183 120" stroke="#64748b" marker-end="url(#m8)"/>',
            '<text x="360" y="112" font-size="11" font-weight="700" fill="#0f172a" '
            'text-anchor="middle">② 판정 결과</text>',
            f'<text x="14" y="172" font-size="10" font-weight="700" fill="#0f172a">'
            f'① GIS → 비전 · ObsSpec ({len(obs)})</text>',
            f'<text x="14" y="187" font-size="9" fill="#64748b">'
            f'{" · ".join(obs)}</text>',
            f'<text x="14" y="211" font-size="10" font-weight="700" fill="#0f172a">'
            f'② 비전 → GIS · VisionResult ({len(res)})</text>',
            f'<text x="14" y="226" font-size="9" fill="#64748b">'
            f'{" · ".join(res[:half])}</text>',
            f'<text x="14" y="239" font-size="9" fill="#64748b">'
            f'{" · ".join(res[half:])}</text>',
            '<rect x="14" y="254" width="692" height="64" rx="6" '
            'fill="#fffbeb" stroke="#f59e0b"/>',
            '<text x="26" y="274" font-size="11" fill="#78350f">'
            '※ 반대 방향이 없다. GIS 도로폭은 호모그래피 입력으로 안 들어간다.</text>',
            '<text x="26" y="290" font-size="11" fill="#78350f">'
            '   흐름이 있다고 보면 지적도 캘리브레이션 시도로 되돌아간다(§19-2).</text>',
            '<text x="26" y="308" font-size="11" fill="#78350f">'
            '※ 비전은 판정(verdict)을 안 넘긴다 — 임계값이 두 군데에 박힌다(§19-1).</text>',
            '<text x="14" y="338" font-size="10" fill="#94a3b8">'
            '★ 접점은 이 둘뿐이다. 필드는 계약 모델에서 읽는다 — '
            '계약이 바뀌면 이 그림이 따라 바뀐다.</text>']
    return svg_fit.svg("".join(body), h=352)


def _verdict_rules() -> list[tuple[str, str, str]]:
    """`seg/geom.py` 의 `VERDICT_RULE` — (조건, 판정, 사유). **문언의 정본**이다.

    임포트하지 않고 AST 로 읽는다(`_params()` 와 같은 사유 — 도구가 파이프라인에
    안 붙는다). 규칙이 바뀌면 그림이 따라 바뀐다. 손으로 옮겨 적으면 두 곳이
    되고, 실제로 그 병이 있었다 — `nreg <= 1` 보류 규칙이 코드 · 시험 · 화면에
    있고 **스키마에만 없었다**(그 사고가 이 상수를 만든 이유다).
    """
    # 함수 안 import — 이 그림 하나만 쓰고 모듈 적재를 무겁게 하지 않는다
    import ast  # noqa: PLC0415  지연 import 는 의도다
    import re as _re  # noqa: PLC0415  지연 import 는 의도다
    src = (ROOT / "src/firelane/seg/geom.py").read_text(encoding="utf-8")
    lit: tuple = ()
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and getattr(n.targets[0], "id", "") == "VERDICT_RULE"):
            lit = ast.literal_eval(n.value)
    out = []
    import html as _h  # noqa: PLC0415  지연 import 는 의도다
    for t in lit:
        # ★ 꼬리에 말이 더 붙는 줄이 있다 — "… (reason=width). 폭 산출 불가".
        #   종전 패턴은 닫는 괄호를 줄 끝에 고정해서 **그 둘을 조용히 흘렸다.**
        #   7개 중 5개만 그려졌고 그림은 멀쩡해 보였다. 아래 수 대조가 그 자리다.
        m = _re.match(r"^(.*?)\s*->\s*(\w+)\s*(?:\((.*?)\))?\s*\.?\s*(.*)$", t)
        if not m:
            continue
        note = " ".join(x for x in (m.group(3), m.group(4)) if x).strip()
        # ★ 규칙 문언에 `<` 가 들어 있다("wmax < 3.0"). 그대로 넣으면 SVG 가
        #   **XML 로 안 읽힌다** — 렌더러가 태그 시작으로 본다.
        out.append((_h.escape(m.group(1).strip()), m.group(2), _h.escape(note)))
    if len(out) != len(lit):
        raise SystemExit(
            f"★ 판정 규칙 {len(lit)}개 중 {len(out)}개만 읽었다 — 파서가 흘렸다.\n"
            "  그림은 멀쩡해 보이고 규칙만 사라진다. 흘린 줄:\n    "
            + "\n    ".join(t for t in lit
                            if not any(_h.unescape(o[0]) in t for o in out)))
    return out


def fig_verdict_flow() -> str:
    """등급 판정 규칙과 그 결과. 기획서 [그림 14].

    정본 셋 — `seg/geom.py::VERDICT_RULE`(문언) · `seg/params.py`(임계값) ·
    `data/golden/segments.fingerprint.json`(구간 수). **셋 다 읽어서 그린다.**

    ★ 2026-09-28 (§281-1). 종전 [그림 14] 는 저장소 밖 래스터였다. 규칙이
      바뀌어도 그림은 안 바뀐다 — [그림 13] 이 폐기된 반경 5m 원을 석 주 동안
      그리고 있던 것(§236)과 같은 자리다.
    """
    P, G = _params(), _golden()
    rules = _verdict_rules()
    cnt = G["verdict"]
    why = G["unknown_reason"]
    col_of = {k: COLOR[k] for k in COLOR}

    body = ['<text x="12" y="24" font-size="15" font-weight="700" fill="#0f172a">'
            '등급 판정 — 정본 seg/geom.py VERDICT_RULE · seg/params.py · golden</text>',
            f'<text x="12" y="44" font-size="11" fill="#64748b">'
            f'임계 TRUCK {P["TRUCK"]:.1f}m · PARK {P["PARK"]:.1f}m · '
            f'CCTV 유효 {P["CCTV_RANGE"]:.0f}m · 구간 {G["n"]:,}</text>']
    y = 68
    for i, (cond, verd, note) in enumerate(rules, 1):
        c = col_of.get(verd, "#94a3b8")
        body += [
            f'<text x="14" y="{y + 13}" font-size="10" fill="#94a3b8">{i}</text>',
            f'<text x="30" y="{y + 13}" font-size="11" fill="#0f172a">{cond[:52]}</text>',
            f'<rect x="392" y="{y}" width="96" height="19" rx="4" fill="{c}"/>',
            f'<text x="440" y="{y + 13}" font-size="10" font-weight="700" '
            f'fill="#fff" text-anchor="middle">{LABEL.get(verd, verd)}</text>',
            f'<text x="498" y="{y + 13}" font-size="10" fill="#64748b">{note[:34]}</text>',
        ]
        y += 25

    y += 8
    body.append(f'<text x="14" y="{y + 12}" font-size="11" font-weight="700" '
                f'fill="#0f172a">결과 — golden 이 정본이다</text>')
    y += 24
    x = 14
    for k in ("clear", "needs_cv", "blocked", "unknown"):
        n = cnt[k]
        body += [f'<rect x="{x}" y="{y}" width="168" height="34" rx="5" '
                 f'fill="#fff" stroke="{COLOR[k]}"/>',
                 f'<text x="{x + 10}" y="{y + 15}" font-size="11" font-weight="700" '
                 f'fill="{COLOR[k]}">{LABEL[k]}</text>',
                 f'<text x="{x + 10}" y="{y + 29}" font-size="10" fill="#64748b">'
                 f'{n:,}구간 · {n / G["n"] * 100:.0f}%</text>']
        x += 176
    y += 58
    body.append(f'<text x="14" y="{y}" font-size="11" font-weight="700" fill="#0f172a">'
                f'영상판정 불가 {cnt["unknown"]:,}의 사유 — 넷으로 갈라 적는다</text>')
    y += 18
    x = 14
    for k, n in sorted(why.items(), key=lambda kv: -kv[1]):
        body.append(f'<text x="{x}" y="{y}" font-size="10" fill="#64748b">'
                    f'{k} {n}</text>')
        x += 176
    return svg_fit.svg("".join(body), h=y + 16)


