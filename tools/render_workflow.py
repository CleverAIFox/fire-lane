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
`MASTER §12` 를 읽어 **종류별로 갈라** 탭 셋에 나눈다.
판단 근거는 각 절의 `<details>` 안으로 접는다.

    들여쓴 블록 · ``` 블록   → 그림    도식과 명령
    | 표 |                   → 표      룰셋 · 용어 · 충돌 처리
    §12-4 절 전체            → 막히면
    ★ 단락 · 산문            → 왜      판단의 근거

앞 탭일수록 그림, 뒤 탭일수록 글이다. 처음 오는 사람은 그림만 보고,
더 알고 싶은 사람이 뒤로 간다.

★ 탭은 CSS 라디오다. JS 를 쓰지 않는다 — `js_graph_check` 가 `web/` 만
  보므로 여기 스크립트가 들어가면 검사 밖에서 자란다.

IN    docs/MASTER.md §12
OUT   web/workflow.html  (생성물이지만 커밋한다 — .gitignore 주석 참조)
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


PLAYBOOK = ROOT / "web/playbook.html"


def slots() -> None:
    """반대 방향 — **화면이 요구하는 절이 MASTER 에 있는가.**

    ★ `audit()` 은 MASTER → 화면을 본다. 이쪽은 화면 → MASTER 다.
      둘이 있어야 도킹이 닫힌다. 한 방향만 보면 목록을 두 벌 유지해야
      하는데, `data-slot` 하나로 맞추면 목록이 한 벌이다.

    ★ 왜 필요한가. `§12-8b`(릴리즈 4단계)를 MASTER 에서 지우면 플레이북의
      그 카드가 근거 없는 서술이 된다. 지금은 아무도 안 운다 — 화면은
      사람이 쓴 것이라 MASTER 를 안 읽기 때문이다. `data-slot` 이 그
      연결을 만든다.

    ★ 플레이북이 없으면 건너뛴다. 이 렌더러의 산출물은 `workflow.html`
      이고 플레이북은 별개 문서다 — 없다고 렌더가 막힐 이유가 없다.
    """
    if not PLAYBOOK.exists():
        return
    html = PLAYBOOK.read_text(encoding="utf-8", errors="ignore")
    want = sorted(set(re.findall(r'data-slot="([^"]+)"', html)))
    if not want:
        print("  playbook 에 data-slot 이 없다 — 도킹 안 함")
        return
    mst = SRC.read_text(encoding="utf-8")
    miss = [s for s in want
            if not re.search(rf"^#{{2,3}} {re.escape(s)}\. ", mst, re.M)]
    if miss:
        raise SystemExit(
            f"★ web/playbook.html 이 가리키는 절 {len(miss)}개가 MASTER 에 없다 —\n"
            f"    {', '.join('§' + s for s in miss)}\n"
            "  절을 지웠으면 플레이북의 그 카드도 지워라. 근거 없는 서술이 된다.\n"
            "  절 번호를 바꿨으면 data-slot 을 같이 고쳐라.")
    print(f"  playbook 슬롯 {len(want)}개 전건 MASTER 에 실재")


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
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

/* ★ 2026-09-02. 와꾸를 web/playbook.html 과 맞췄다. 종전에는 파란 그라데이션
   헤더에 어두운 코드블록이었고, 같은 사이트에 나란히 배포되는 두 화면이
   서로 다른 디자인이었다. 팀원은 둘을 오가며 읽는다.
   ★ A4 는 흰색이다. 이 문서는 인쇄되거나 PDF 로 돌아다닌다. */
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Pretendard',-apple-system,BlinkMacSystemFont,system-ui,
 "Segoe UI","Noto Sans KR",sans-serif;
 background:#fff;color:#333;padding:32px 0;line-height:1.75;font-size:16px}}
.wrap{{max-width:1100px;margin:0 auto;padding:0 24px}}

header{{border:1px solid #d0d7de;border-left:4px solid #0969da;
 border-radius:10px;padding:26px 28px;background:#f6f8fa}}
h1{{font-size:26px;font-weight:800;letter-spacing:-.5px;color:#0f172a}}
.sub{{font-size:14px;color:#57606a;margin-top:8px}}
.canon{{display:inline-block;margin-top:14px;font-size:12.5px;color:#57606a;
 background:#fff;border:1px solid #d0d7de;padding:7px 14px;border-radius:20px}}
.canon b{{color:#0969da}}

input[name=t]{{display:none}}
/* ★ 탭을 줄바꿈시킨다. 가로 스크롤은 있는 줄도 모르게 만든다. */
.tabs{{display:flex;flex-wrap:wrap;gap:10px;margin:26px 0 24px}}
.tabs label{{flex:1 1 200px;cursor:pointer;padding:13px 14px;border-radius:10px;
 background:#fff;border:1px solid #d0d7de;text-align:center;transition:.15s}}
.tabs label b{{display:block;font-size:15px;color:#24292f;font-weight:700}}
.tabs label span{{display:block;font-size:12px;color:#8c959f;margin-top:4px}}
.tabs label:hover{{border-color:#0969da;background:#f6f8fa}}

section{{display:none}}
#t0:checked~.tabs label[for=t0],#t1:checked~.tabs label[for=t1],
#t2:checked~.tabs label[for=t2],#t3:checked~.tabs label[for=t3]
 {{background:#0969da;border-color:#0969da}}
#t0:checked~.tabs label[for=t0] b,#t1:checked~.tabs label[for=t1] b,
#t2:checked~.tabs label[for=t2] b,#t3:checked~.tabs label[for=t3] b{{color:#fff}}
#t0:checked~.tabs label[for=t0] span,#t1:checked~.tabs label[for=t1] span,
#t2:checked~.tabs label[for=t2] span,#t3:checked~.tabs label[for=t3] span
 {{color:rgba(255,255,255,.85)}}
#t0:checked~.p0,#t1:checked~.p1,#t2:checked~.p2,#t3:checked~.p3{{display:block}}

h3{{font-size:15px;font-weight:800;color:#0f172a;margin:34px 0 14px;
 padding-left:12px;border-left:4px solid #0969da}}
h3:first-child{{margin-top:6px}}

/* 코드블록 — 옅은 회색 + 좌측 3px 색띠. 어두운 배경을 쓰지 않는다. */
pre{{background:#f6f8fa;border:1px solid #d0d7de;border-left:3px solid #0969da;
 border-radius:8px;padding:18px 20px;overflow-x:auto;margin:14px 0;
 font-family:"D2Coding",Consolas,Monaco,monospace;
 font-size:14px;line-height:1.9;color:#24292f}}

table{{width:100%;border-collapse:separate;border-spacing:0;font-size:15px;
 margin:14px 0;background:#fff;border:1px solid #d0d7de;border-radius:8px;
 overflow:hidden}}
th,td{{padding:12px 15px;text-align:left;vertical-align:top;
 border-bottom:1px solid #eaeef2}}
th{{background:#f6f8fa;color:#24292f;font-size:13px;font-weight:800}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover,table tr:hover{{background:#f6f8fa}}

code{{font-family:"D2Coding",Consolas,Monaco,monospace;font-size:14px;
 background:#eff6ff;color:#0550ae;padding:2px 7px;border-radius:5px}}
pre code{{background:none;color:inherit;padding:0}}
b{{color:#0f172a;font-weight:700}}
p{{margin:14px 0;font-size:15.5px;color:#333}}

/* 커밋 접두사 색 — playbook 과 같은 값. 본문 어디에 나오든 같은 색이면
   눈으로 스캔이 빨라진다(§12-6). */
code.p-gis{{color:#0284c7}} code.p-cv{{color:#7c3aed}}
code.p-ui{{color:#db2777}} code.p-api{{color:#059669}}
code.p-fix{{color:#dc2626}} code.p-docs{{color:#475569}}

/* ★ 인쇄. 이 문서는 결국 A4 로 나가거나 PDF 로 돌아다닌다.
   탭이 접힌 채 인쇄되면 넷 중 하나만 보인다. 전부 펼친다. */
@media print{{
  body{{padding:0;font-size:12pt;background:#fff}}
  .wrap{{max-width:none;padding:0}}
  .tabs{{display:none}}
  section{{display:block !important;page-break-inside:auto}}
  section+section{{page-break-before:always}}
  header{{border:1px solid #999;background:#fff}}
  pre,table{{page-break-inside:avoid}}
  a[href]:after{{content:""}}
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
    slots()                         # ★ 반대 방향 — 화면 → MASTER
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
