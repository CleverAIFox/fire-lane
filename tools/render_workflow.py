#!/usr/bin/env python3
"""
render_workflow.py — MASTER §12 를 협업 방침 화면으로 렌더한다.

    uv run python tools/render_workflow.py          web/workflow.html 생성
    uv run python tools/render_workflow.py --check  재생성 결과와 다르면 종료코드 1

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-31. `docs/workflow.html` 을 손으로 썼다. 그 순간 규약 정본이 둘이
됐고, 같은 날 `MASTER §12-1` 만 낡은 채로 `dev` 흡수 머지를 통과했다 —
**작업 하나가 소리 없이 사라졌고 아무도 몰랐다.**

사본을 대조로 지키는 것보다 **사본을 만들지 않는 것**이 싸다.
`web/data` 가 생성물인 것과 같은 관계다(R2).

★ 정본이 `.md` 라서 얻는 것 — `test_doc_style` 이 평어체·어조를 걸고,
  `test_docref` 가 절 참조를 걸고, `docnum_check` 가 숫자를 건다.
  손으로 쓴 HTML 에는 그 셋 중 무엇도 안 걸렸다.

── 무엇을 하는가 ───────────────────────────────────────────────
`MASTER §12` 를 읽어 **종류별로 갈라** 탭 넷에 나눈다.

    들여쓴 블록 · ``` 블록   → 그림    도식과 명령
    | 표 |                   → 표      룰셋 · 용어 · 충돌 처리
    §12-4 절 전체            → 막히면
    ★ 단락 · 산문            → 왜      판단의 근거

앞 탭일수록 그림, 뒤 탭일수록 글이다. 처음 오는 사람은 그림만 보고,
더 알고 싶은 사람이 뒤로 간다.

★ 탭은 CSS 라디오다. JS 를 쓰지 않는다 — `js_graph_check` 가 `web/` 만
  보므로 여기 스크립트가 들어가면 검사 밖에서 자란다.

IN    docs/MASTER.md §12
OUT   web/workflow.html  (생성물. gitignore)
PARAM --check
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/MASTER.md"
OUT = ROOT / "web/workflow.html"

TROUBLE = "12-4"          # 이 절은 통째로 '막히면' 탭


def section12(text: str) -> list[str]:
    """`## 12.` ~ `## 13.` 사이.

    ★ 2026-09-01. 종전에는 `next()` 두 개였고 못 찾으면 `StopIteration` 이
      맨몸으로 터졌다. 값이 낡는 것은 `--check` 가 잡지만 **구조가 바뀌는
      것**은 아무도 설명해 주지 않았다. 제목이 바뀌었는지 절이 사라졌는지
      추적 하나만 보고는 안 갈린다.
    """
    lines = text.splitlines()
    s = next((i for i, l in enumerate(lines) if l.startswith("## 12. 협업")), None)
    if s is None:
        raise SystemExit(
            "★ MASTER 에 `## 12. 협업` 절이 없다.\n"
            "  제목이 바뀌었으면 이 파서도 같이 고쳐라. 화면만 비는 것이\n"
            "  제일 나쁘다 — 규약이 사라진 줄 아무도 모른다.")
    e = next((i for i in range(s + 1, len(lines))
              if lines[i].startswith("## 13.")), None)
    if e is None:
        raise SystemExit("★ MASTER 에 `## 13.` 이 없다. §12 의 끝을 못 찾는다.")
    return lines[s:e]


def audit(lines: list[str], groups: dict) -> None:
    """파싱 결과가 원문과 어긋나지 않는지 센다. 어긋나면 죽는다.

    ★ 여기서 보는 것은 **값이 아니라 구조**다. `--check` 는 "생성물이
      MASTER 와 다른가" 를 보고, 이쪽은 "MASTER 를 제대로 읽었는가" 를 본다.
      전자는 사람이 HTML 을 손으로 고쳤을 때 울고, 후자는 MASTER 의 절
      구성이 바뀌었을 때 운다. 2026-09-01 에 후자가 없었다.
    """
    subs = [m.group(1) for ln in lines
            if (m := re.match(r"^### (12-[0-9a-z]+)\.", ln))]
    if not subs:
        raise SystemExit("★ §12 에 `### 12-x.` 하위 절이 하나도 없다. "
                         "제목 형식이 바뀌었는지 봐라.")
    picked = {t.split()[0].lstrip("§")
              for xs in groups.values() for t, _ in xs
              if t.startswith("§")}
    lost = [s for s in subs if s not in picked]
    if lost:
        raise SystemExit(
            f"★ §12 하위 절 {len(lost)}개가 화면에 안 담겼다 — {', '.join(lost)}\n"
            "  그 절의 내용이 표도 그림도 산문도 아닌 형태라 분류에서 빠졌다.\n"
            "  classify() 를 고치거나 MASTER 쪽 형식을 맞춰라.")
    print(f"  §12 하위 절 {len(subs)}개 전건 반영")


def classify(lines: list[str]) -> dict[str, list[tuple[str, str]]]:
    """(제목, 조각) 을 탭별로 모은다."""
    out = {"pic": [], "tbl": [], "trb": [], "why": []}
    cur = "시작 — 구조와 방향"
    fence = False
    buf: list[str] = []
    kind = None

    def flush():
        nonlocal buf, kind
        if buf and kind:
            out[kind].append((cur, "\n".join(buf)))
        buf, kind = [], None

    for ln in lines:
        m = re.match(r"^### (12-[0-9a-z]+)\. (.+)$", ln)
        if m:
            flush()
            cur = f"§{m.group(1)}  {m.group(2)}"
            continue
        if ln.startswith("## 12."):
            continue

        if ln.startswith("```"):
            fence = not fence
            if not fence:
                flush()
            else:
                flush(); kind = "pic"
            continue

        trouble = cur.startswith(f"§{TROUBLE}")
        want = "trb" if trouble else None

        if fence:
            kind = kind or "pic"
            buf.append(ln); continue
        if ln.startswith("    ") and ln.strip():
            tgt = want or "pic"
            if kind != tgt: flush(); kind = tgt
            buf.append(ln[4:]); continue
        if ln.startswith("|"):
            tgt = want or "tbl"
            if kind != tgt: flush(); kind = tgt
            buf.append(ln); continue
        if not ln.strip():
            flush(); continue
        if kind not in (None, "why", "trb"): flush()
        kind = want or "why"
        buf.append(ln)
    flush()
    return out


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def as_table(md: str) -> str:
    rows = [r for r in md.splitlines() if not re.match(r"^\|[-\s|]+\|$", r)]
    body = []
    for i, r in enumerate(rows):
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        tag = "th" if i == 0 else "td"
        body.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
    return "<table>" + "".join(body) + "</table>"


def as_prose(md: str) -> str:
    out = []
    for para in re.split(r"\n(?=★)", md):
        p = inline(para.strip()).replace("\n", " ")
        cls = " class=\"star\"" if para.lstrip().startswith("★") else ""
        out.append(f"<p{cls}>{p}</p>")
    return "".join(out)


# ── 전처리 · 컴포넌트 ────────────────────────────────────────
# ★ ASCII 를 `<pre>` 에 그대로 넣으면 md 원문과 똑같아 보인다. 그것은
#   뷰어이지 렌더가 아니다. 구조를 읽어 **컴포넌트로 다시 조립한다.**

BRANCH_RE = re.compile(
    r"^\s*(?:[└├│]\s*)*(main|dev|part/[a-z]+|feat/\*)\s*[─\-]*\s*(.*)$")


def as_tree(md: str) -> str:
    """브랜치 ASCII 트리 → 계층 카드."""
    rows = []
    for ln in md.splitlines():
        m = BRANCH_RE.match(ln)
        if not m:
            return ""
        name, desc = m.group(1), m.group(2).strip()
        depth = (len(ln) - len(ln.lstrip())) // 3
        rows.append((depth, name, desc))
    if len(rows) < 3:
        return ""
    kind = {"main": "n-main", "dev": "n-dev", "feat/*": "n-tmp"}
    out = ['<div class="tree">']
    for d, name, desc in rows:
        cls = kind.get(name, "n-part")
        out.append(
            f'<div class="tnode {cls}" style="margin-left:{d * 34}px">'
            f'<span class="tname">{html.escape(name)}</span>'
            f'<span class="tdesc">{inline(desc)}</span></div>')
    out.append("</div>")
    return "".join(out)


FLOW_RE = re.compile(r"^\s*(\S+)\s+(.+?)\s*-+>\s*(.+?)\s{2,}(.+)$")


def as_flow(md: str) -> str:
    """`받는다 A ---> B  설명` → 화살표 카드 두 장."""
    items = []
    for ln in md.splitlines():
        m = FLOW_RE.match(ln)
        if not m:
            return ""
        items.append(tuple(x.strip() for x in m.groups()))
    if len(items) != 2:
        return ""
    out = ['<div class="flow">']
    for i, (label, src, dst, note) in enumerate(items):
        tone = "f-in" if i == 0 else "f-out"
        out.append(
            f'<div class="frow {tone}">'
            f'<span class="flabel">{html.escape(label)}</span>'
            f'<span class="fbox">{html.escape(src)}</span>'
            f'<span class="farrow">&rarr;</span>'
            f'<span class="fbox">{html.escape(dst)}</span>'
            f'<span class="fnote">{html.escape(note)}</span></div>')
    out.append("</div>")
    return "".join(out)


def as_rules(md: str) -> str:
    """룰셋 표 → 브랜치 카드. 첫 열이 룰셋 이름인 표에만 쓴다."""
    rows = [r for r in md.splitlines() if not re.match(r"^\|[-\s|]+\|$", r)]
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    if not cells or cells[0][:2] != ["룰셋", "대상"]:
        return ""
    head, body = cells[0], cells[1:]
    out = ['<div class="cards">']
    for row in body:
        out.append(f'<div class="card"><div class="cname">{inline(row[0])}</div>')
        for k, v in zip(head[1:], row[1:], strict=False):
            free = v.strip() in ("—", "-", "")
            out.append(
                f'<div class="crow"><span class="ck">{html.escape(k)}</span>'
                f'<span class="cv{" free" if free else ""}">{inline(v)}</span></div>')
        out.append("</div>")
    out.append("</div>")
    return "".join(out)


def anchor(num: str) -> str:
    """`12-1` → `#12-1-룰셋`. GitHub 이 헤딩에서 만드는 앵커 규칙을 따른다.

    ★ 소문자화 · 공백을 하이픈 · 마침표와 백틱 등 구두점 제거.
      제목이 바뀌면 앵커도 바뀐다. 그래서 실물 제목에서 만든다.
    """
    m = re.search(rf"^#+\s*{re.escape(num)}\.\s*(.+)$", SRC.read_text(encoding="utf-8"), re.M)
    if not m:
        return ""
    slug = m.group(1).strip().lower()
    slug = re.sub(r"[`*_\[\]().,·—:/]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return f"#{num}-{slug}"


def render(groups: dict) -> str:
    # 절별 산문을 미리 모은다. 각 절 끝에 <details> 로 붙는다.
    prose: dict[str, list[str]] = {}
    for title, md in groups["why"]:
        prose.setdefault(title, []).append(md)

    def detail(title: str) -> str:
        """그 절의 '왜' — 접힌 채로 둔다. 층 2다."""
        md = prose.get(title)
        if not md:
            return ""
        sec = re.match(r"§(12-[0-9a-z]+)", title)
        link = ""
        if sec:
            link = (f'<a class="more" target="_blank" rel="noopener"'
                    f' href="https://github.com/woongtopia/fire-lane/blob/main/'
                    f'docs/MASTER.md{anchor(sec.group(1))}">MASTER §{sec.group(1)} 전문 →</a>')
        # ★ 내용을 div 하나로 감싼다. CSS 가 이 div 만 띄우면 되므로
        #   문단이 여럿이어도 서로 포개지지 않는다.
        return ('<details class="why"><summary>왜 이렇게 정했나</summary>'
                '<div class="pop">'
                + "".join(as_prose(m) for m in md) + link + "</div></details>")

    def block(kind: str) -> str:
        parts, last = [], None
        for title, md in groups[kind]:
            if title != last:
                if last:
                    parts.append(detail(last))
                parts.append(f"<h3>{html.escape(title)}</h3>"); last = title
            if kind == "pic":
                parts.append(as_tree(md) or as_flow(md)
                             or f"<pre>{html.escape(md)}</pre>")
            else:
                parts.append(as_rules(md) or as_table(md))
        if last:
            parts.append(detail(last))
        return "".join(parts) or "<p>없음</p>"

    tabs = [("pic", "1 · 그림", "브랜치 구조와 하루 흐름"),
            ("tbl", "2 · 표", "룰셋 · 용어 · 커밋 접두사"),
            ("trb", "3 · 막히면", "충돌 · 자주 겪는 것")]

    radios = "".join(
        f'<input type="radio" name="t" id="t{i}"{" checked" if i == 0 else ""}>'
        for i, _ in enumerate(tabs))
    labels = "".join(
        f'<label for="t{i}"><b>{t}</b><span>{d}</span></label>'
        for i, (_, t, d) in enumerate(tabs))
    panes = "".join(
        f'<section class="p{i}">{block(k)}</section>'
        for i, (k, _, _) in enumerate(tabs))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fire-Lane 협업 방침</title>
<!-- ★ 생성물이다. 손으로 고치지 마라. 정본은 docs/MASTER.md §12 이고
     tools/render_workflow.py 가 만든다. 고치면 다음 배포에 덮인다. -->
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Pretendard","Noto Sans KR",sans-serif;
 background:#f6f8fb;color:#1e293b;padding:32px 20px;line-height:1.75;font-size:16px}}
.wrap{{max-width:1040px;margin:0 auto}}

header{{background:linear-gradient(135deg,#2563eb,#0891b2);border-radius:16px;
 padding:30px 32px;color:#fff;box-shadow:0 10px 30px rgba(37,99,235,.22)}}
h1{{font-size:28px;font-weight:800;letter-spacing:-.6px}}
.sub{{font-size:14px;opacity:.9;margin-top:8px}}
.canon{{display:inline-block;margin-top:14px;font-size:12.5px;
 background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);
 padding:7px 14px;border-radius:20px}}
.canon b{{color:#fff}}

input[name=t]{{display:none}}
.tabs{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:26px 0 24px}}
.tabs label{{cursor:pointer;padding:14px 12px;border-radius:12px;background:#fff;
 border:2px solid #e2e8f0;text-align:center;transition:.18s;
 box-shadow:0 1px 3px rgba(15,23,42,.05)}}
.tabs label b{{display:block;font-size:16px;color:#475569;font-weight:700}}
.tabs label span{{display:block;font-size:12px;color:#94a3b8;margin-top:4px}}
.tabs label:hover{{border-color:#93c5fd;transform:translateY(-1px)}}

section{{display:none}}
#t0:checked~.tabs label[for=t0],#t1:checked~.tabs label[for=t1],
#t2:checked~.tabs label[for=t2],#t3:checked~.tabs label[for=t3]
 {{background:linear-gradient(135deg,#2563eb,#0891b2);border-color:transparent;
   box-shadow:0 6px 16px rgba(37,99,235,.3)}}
#t0:checked~.tabs label[for=t0] b,#t1:checked~.tabs label[for=t1] b,
#t2:checked~.tabs label[for=t2] b,#t3:checked~.tabs label[for=t3] b{{color:#fff}}
#t0:checked~.tabs label[for=t0] span,#t1:checked~.tabs label[for=t1] span,
#t2:checked~.tabs label[for=t2] span,#t3:checked~.tabs label[for=t3] span
 {{color:rgba(255,255,255,.82)}}
#t0:checked~.p0,#t1:checked~.p1,#t2:checked~.p2,#t3:checked~.p3{{display:block}}

h3{{font-size:15px;font-weight:800;color:#0f172a;margin:34px 0 14px;
 padding-left:12px;border-left:4px solid #2563eb}}
h3:first-child{{margin-top:6px}}

pre{{background:#0f172a;border-radius:12px;padding:22px 24px;overflow-x:auto;
 margin:14px 0;font-family:"D2Coding",Consolas,Monaco,monospace;
 font-size:14.5px;line-height:2;color:#e0f2fe;
 box-shadow:0 4px 14px rgba(15,23,42,.14)}}

table{{width:100%;border-collapse:separate;border-spacing:0;font-size:15px;
 margin:14px 0;background:#fff;border-radius:12px;overflow:hidden;
 box-shadow:0 2px 10px rgba(15,23,42,.07)}}
th,td{{padding:13px 16px;text-align:left;vertical-align:top;
 border-bottom:1px solid #eef2f7}}
th{{background:#f1f5f9;color:#334155;font-size:13px;font-weight:800;
 letter-spacing:.3px}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover,table tr:hover{{background:#f8fafc}}

code{{font-family:"D2Coding",Consolas,Monaco,monospace;font-size:14px;
 background:#eff6ff;color:#1d4ed8;padding:2px 7px;border-radius:5px}}
pre code{{background:none;color:inherit;padding:0}}
b{{color:#0f172a;font-weight:700}}
p{{margin:14px 0;font-size:15.5px;color:#334155}}
p.star{{background:#eff6ff;border-left:4px solid #2563eb;
 padding:15px 20px;border-radius:0 10px 10px 0;color:#1e3a8a}}
p.star b{{color:#1e3a8a}}

footer{{margin-top:44px;padding:20px 24px;background:#fff;border-radius:12px;
 font-size:13px;color:#64748b;box-shadow:0 1px 4px rgba(15,23,42,.06)}}
footer b{{color:#334155}}
@media(max-width:720px){{.tabs{{grid-template-columns:repeat(2,1fr)}}
 body{{font-size:15px;padding:20px 14px}}h1{{font-size:23px}}}}

/* 트리 */
.tree{{background:#fff;border-radius:14px;padding:22px;margin:14px 0;
 box-shadow:0 2px 10px rgba(15,23,42,.07)}}
.tnode{{display:flex;align-items:center;gap:12px;padding:11px 16px;margin:7px 0;
 border-radius:10px;border-left:5px solid}}
.tname{{font-family:Consolas,monospace;font-weight:800;font-size:15px;min-width:104px}}
.tdesc{{font-size:13.5px;color:#475569}}
.n-main{{background:#eef2ff;border-color:#6366f1}}.n-main .tname{{color:#4338ca}}
.n-dev{{background:#ecfdf5;border-color:#10b981}}.n-dev .tname{{color:#047857}}
.n-part{{background:#eff6ff;border-color:#3b82f6}}.n-part .tname{{color:#1d4ed8}}
.n-tmp{{background:#f8fafc;border-color:#cbd5e1;border-left-style:dashed}}
.n-tmp .tname{{color:#64748b}}
/* 방향 */
.flow{{display:grid;gap:12px;margin:14px 0}}
.frow{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:16px 20px;
 border-radius:12px;background:#fff;box-shadow:0 2px 10px rgba(15,23,42,.07);
 border-left:5px solid}}
.f-in{{border-color:#10b981}}.f-out{{border-color:#6366f1}}
.flabel{{font-weight:800;font-size:16px;min-width:64px}}
.f-in .flabel{{color:#047857}}.f-out .flabel{{color:#4338ca}}
.fbox{{font-family:Consolas,monospace;font-size:14px;background:#f1f5f9;
 padding:7px 13px;border-radius:8px;color:#334155}}
.farrow{{font-size:20px;color:#94a3b8}}
.fnote{{margin-left:auto;font-size:13px;color:#64748b}}
/* 룰셋 카드 */
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(238px,1fr));
 gap:14px;margin:14px 0}}
.card{{background:#fff;border-radius:14px;padding:20px;
 box-shadow:0 2px 12px rgba(15,23,42,.08);border-top:4px solid #2563eb}}
.cname{{font-family:Consolas,monospace;font-weight:800;font-size:17px;
 color:#1d4ed8;margin-bottom:14px}}
.crow{{display:flex;justify-content:space-between;gap:10px;padding:7px 0;
 border-bottom:1px solid #f1f5f9;font-size:13.5px}}
.crow:last-child{{border:none}}
.ck{{color:#94a3b8;font-weight:600}}
.cv{{color:#0f172a;font-weight:700;text-align:right}}
.cv.free{{color:#cbd5e1;font-weight:400}}
/* 각주 */
/* ★ 2026-09-01. <details> 는 열면 아래 내용을 밀어낸다. 읽던 자리를
   잃으므로 각주는 제자리에 뜬다 — 위치는 그대로 두고 겹쳐 띄운다.
   details 그대로 쓰므로 JS 없이 동작하고 키보드·스크린리더도 그대로다. */
details.why[open]{{position:relative;overflow:visible}}
details.why[open]>.pop{{position:absolute;z-index:40;left:0;right:0;
  top:100%;background:#fff;border:1px solid #cbd5e1;border-radius:12px;
  box-shadow:0 12px 32px rgba(15,23,42,.18);padding:4px 0 14px;
  max-height:60vh;overflow-y:auto}}
details.why[open]>.pop>p:first-of-type{{padding-top:18px}}
details.why{{margin:16px 0 26px;background:#fff;border-radius:12px;
 border:1px solid #e2e8f0;overflow:hidden}}
details.why summary{{cursor:pointer;padding:14px 20px;font-size:14px;
 font-weight:700;color:#2563eb;background:#f8fafc;list-style:none;user-select:none}}
details.why summary::before{{content:"▸ ";color:#94a3b8}}
details.why[open] summary::before{{content:"▾ "}}
details.why summary:hover{{background:#eff6ff}}
details.why>p{{padding:0 20px}}
details.why>p:first-of-type{{padding-top:14px}}
a.more{{display:inline-block;margin:8px 20px 18px;font-size:13px;
 color:#2563eb;text-decoration:none;font-weight:600}}
a.more:hover{{text-decoration:underline}}

@media print{{
  input[name=t]~section{{display:block !important}}
  .tabs{{display:none}}
  details.why{{page-break-inside:avoid}}
}}
</style>
</head>
<body><div class="wrap">
<header>
  <h1>Fire-Lane · 협업 방침</h1>
  <div class="sub">5인 · 4계층 브랜치 · main 단독 배포 · 승인 대신 검사</div>
  <div class="canon">정본은 <b>docs/MASTER.md §12</b> — 이 화면은 생성물이다</div>
</header>
{radios}
<div class="tabs">{labels}</div>
{panes}
<footer>
  생성 <b>tools/render_workflow.py</b> · 정본 <b>docs/MASTER.md §12</b><br>
  이 파일을 손으로 고치면 다음 배포에 덮인다. 정본을 고쳐라.
</footer>
</div></body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    _lines = section12(SRC.read_text(encoding="utf-8"))
    _groups = classify(_lines)
    audit(_lines, _groups)          # ★ 구조가 바뀌면 여기서 죽는다
    doc = render(_groups)

    if a.check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != doc:
            print("★ web/workflow.html 이 MASTER §12 와 다르다.")
            print("  uv run python tools/render_workflow.py  로 재생성하라.")
            print("  손으로 고쳤다면 그 수정을 MASTER §12 로 옮겨라 —")
            print("  이 파일은 생성물이고 다음 배포에 덮인다.")
            return 1
        print("workflow.html OK — MASTER §12 와 일치")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"→ {OUT}  ({len(doc):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
