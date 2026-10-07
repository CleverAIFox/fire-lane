#!/usr/bin/env python3
"""
build_proposal.py — 정본 `docs/proposal.md` 를 화면 `web/proposal.html` 로 굽는다.

    uv run python tools/build_proposal.py           굽는다
    uv run python tools/build_proposal.py --check   **굽지 않고** 커밋된 것과 댄다

── 왜 생겼나 (PLAN #142) ───────────────────────────────────────
기획서는 문서 넷 중 **유일하게 외부가 읽는 것**인데 `.docx` 손글씨였다. 그래서
낡았고, 낡은 것을 잡으려고 `docx_check` · `docstyle` · `docx_figs` · `docx_fix` ·
`proposal_pdf` 다섯이 생겼다 — **다섯 다 「손으로 쓴 것이 틀렸나」를 묻는 도구**다.
정본을 md 로 옮기면 그 물음 자체가 없어진다.

토트와 하토르가 **독립으로 같은 결론**에 닿았고 공통부가 여섯이다. 그중 이
파일이 드는 것은 넷이다 —

    ① 기획서는 **빌드 산출물**이다. 생성물을 손으로 고치지 않는다
    ② **정본의 지문**을 생성물에 심고 검사가 견준다
    ③ 로컬 **경고** / 배포 **실패** 를 종료 코드로 가른다 (3번 코드)
    ④ **완전성 자**를 바이트 대조와 **따로** 둔다

★ ④ 가 왜 따로인가 — 바이트 대조는 「손으로 안 바뀌었나」만 본다. 생성기가
  **처음부터** 빠뜨리면 커밋된 것과 재생성 결과가 **같이 틀려서** 영원히
  조용하다. 하토르 D-0370 에서 그림 28장이 통째로 빠졌는데 관문 넷이 전부
  초록이었다. 그래서 수를 **정본과** 맞댄다.

── 종료 코드 ───────────────────────────────────────────────────
    0   같다
    1   도구가 고장났다 (정본이 없다 · 와꾸에 자리가 없다)
    2   생성물이 정본과 다르다 — 다시 구워라
    3   **지금은 통과, 배포는 막힌다** — `CI=true` 면 2 로 올린다

★ 상태를 **문자열로 내지 않는다.** §415 가 그 족이다 — `WARN` 을 stdout 에
  찍었더니 부르는 쪽의 `0) ok` 가지가 통째로 버렸고, 「로컬 초록 → CI 빨강」이
  났다. 상태는 종료 코드다.

IN    docs/proposal.md · web/proposal.template.html · web/proposal/fig/*.png
OUT   web/proposal.html   ★ 커밋한다
PARAM 없음
밖    **글이 옳은가는 안 본다.** 문장·수치·논리는 정본 `docs/proposal.md` 소관이고
      그 수치의 정본은 `data/golden/segments.fingerprint.json` 이다 — `--check` 가
      드는 것은 「화면이 정본과 같은가」 하나다. 예쁜가도 안 본다(사람이 본다).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import re
import sys
from pathlib import Path

import proposal_source as PS  # 읽는 법은 한 집에만 산다

from firelane import paths as _paths  # 환경변수의 유일한 독자다(§222-3)

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "web" / "proposal.template.html"
OUT = ROOT / "web" / "proposal.html"

#: 와꾸가 반드시 들어야 하는 자리. 하나라도 없으면 **터진다** — 조용히
#: 반쪽짜리를 굽느니 안 굽는 쪽이 낫다.
SLOTS = ("title", "stamp", "built", "tabs", "toc", "panes", "script")

#: 와꾸가 제 몫으로 더하는 제목 수. 완전성 자가 이것을 알고 뺀다.
FRAME_HEADS = 0

#: 바닥. 표가 비거나 절이 비면 「전부 맞다」가 거짓 초록이 된다.
FLOOR_PANES, FLOOR_HEADS, FLOOR_TABLES = 3, 60, 40

SCRIPT = """<script>
// ★ 83줄 넘기지 않는다. 화면이 하는 일은 둘뿐 — 칸 전환(CSS 가 한다)과
//   현재 절 표시다. 검색은 안 넣는다: 브라우저의 Ctrl+F 가 더 낫고,
//   넣으면 `check_script` 같은 관문을 하나 더 져야 한다.
(function () {
  var links = [].slice.call(document.querySelectorAll('nav a[href^="#"]'));
  if (!links.length || !('IntersectionObserver' in window)) return;
  var byId = {};
  links.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
  var seen = new Set();
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (e.isIntersecting) seen.add(e.target.id); else seen.delete(e.target.id);
    });
    links.forEach(function (a) { a.style.color = ''; });
    var first = links.filter(function (a) {
      return seen.has(a.getAttribute('href').slice(1));
    })[0];
    if (first) first.style.color = 'var(--accent)';
  }, { rootMargin: '-10% 0px -80% 0px' });
  Object.keys(byId).forEach(function (id) {
    var el = document.getElementById(id);
    if (el) io.observe(el);
  });
})();
</script>"""


def slug(s: str, seen: dict[str, int]) -> str:
    """제목 → 닻. 같은 제목이 또 오면 번호를 붙인다 — **닻이 겹치면 목차가 거짓말한다.**"""
    base = re.sub(r"[^0-9A-Za-z가-힣]+", "-", s).strip("-").lower() or "s"
    seen[base] = seen.get(base, 0) + 1
    return base if seen[base] == 1 else f"{base}-{seen[base]}"


def inline(s: str) -> str:
    """글 안의 꾸밈. **아는 것만** 바꾼다 — 모르는 것은 글자 그대로 남는다."""
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def render_table(rows: list[list[str]]) -> str:
    head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                   for r in rows[1:])
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render(md: str) -> tuple[list[tuple[str, str]], list[tuple[int, str, str]]]:
    """(칸 이름, 칸 HTML) 목록과 (깊이, 글, 닻) 목차를 같이 낸다."""
    lines = md.splitlines()
    seen: dict[str, int] = {}
    panes: list[tuple[str, list[str]]] = []
    toc: list[tuple[int, str, str]] = []
    buf: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = PS.HEAD.match(ln)
        if m:
            d, text = len(m.group(1)), m.group(2)
            if d == 1:
                i += 1
                continue                       # 문서 제목은 머리가 든다
            a = slug(text, seen)
            if d == 2:
                panes.append((text, []))
                buf = panes[-1][1]
                buf.append(f'<h2 id="{a}">{inline(text)}</h2>')
            else:
                if not panes:                  # Part 앞의 표지 글
                    panes.append(("표지", []))
                    buf = panes[-1][1]
                buf.append(f'<h{d} id="{a}">{inline(text)}</h{d}>')
            toc.append((d, text, a))
            i += 1
            continue
        if PS.ROW.match(ln):
            blk = []
            while i < len(lines) and PS.ROW.match(lines[i]):
                blk.append(lines[i]); i += 1
            rows = PS.tables("\n".join(blk) + "\n\n")
            if not panes:
                panes.append(("표지", [])); buf = panes[-1][1]
            if rows:
                buf.append(render_table(rows[0]))
            continue
        fm = PS.FIGURE.match(ln)
        if fm:
            if not panes:
                panes.append(("표지", [])); buf = panes[-1][1]
            buf.append(f'<img src="proposal/fig/{fm.group(1)}" alt="">')
            i += 1
            continue
        if ln.strip():
            if not panes:
                panes.append(("표지", [])); buf = panes[-1][1]
            buf.append(f"<p>{inline(ln.strip())}</p>")
        i += 1
    return [(n, "\n".join(b)) for n, b in panes], toc


def build() -> str:
    md = PS.source()
    panes, toc = render(md)
    tpl = TPL.read_text(encoding="utf-8")

    tabs, bodies = [], []
    for k, (name, body) in enumerate(panes):
        chk = " checked" if k == 0 else ""
        tabs.append(f'<input type="radio" name="pane" id="t{k}"{chk}>'
                    f'<label for="t{k}">{html.escape(name)}</label>')
        bodies.append(f'<section class="pane" id="p{k}">{body}</section>')
    # 칸 전환은 CSS 가 한다 — 자바스크립트가 꺼져도 선다
    css = "<style>" + "".join(
        f"#t{k}:checked~main #p{k}{{display:block}}"
        f"#t{k}:checked~header .tabs label[for=t{k}]{{background:#fff;color:var(--ink);"
        f"border-bottom:2px solid #fff;margin-bottom:-1px}}" for k in range(len(panes))
    ) + "</style>"

    nav = "".join(
        f'<a class="d{d}" href="#{a}">{html.escape(t)}</a>'
        for d, t, a in toc if d in (2, 3, 4))

    title = next((t for d, t in PS.heads(md) if d == 1), "Fire-Lane 기획서")
    out = tpl
    for name, value in (
        ("title", html.escape(title)),
        ("stamp", PS.FINGERPRINT + PS.fingerprint()),
        # ★ `date.today()` 가 아니다 — `.ruff-strict.toml` 의 DTZ011 이 문다.
        #   저장소 관례는 `now(UTC).astimezone()` 이다(`guards.py` · `ingest.py`).
        ("built", _dt.datetime.now(_dt.UTC).astimezone().date().isoformat()),
        ("tabs", "".join(tabs)),
        ("toc", nav),
        ("panes", "".join(bodies)),
        ("script", css + SCRIPT),
    ):
        mark = "{" + name + "}"
        if mark not in out:
            raise PS.SourceError(f"와꾸에 `{mark}` 자리가 없다 — 와꾸가 바뀌었다")
        out = out.replace(mark, value)
    return out


def carried(made: str, md: str) -> list[str]:
    """**정본이 든 것을 생성물이 다 담았나.** 바이트 대조와 **따로** 서는 자다."""
    bad = []
    hs = [(d, t) for d, t in PS.heads(md) if d >= 2]
    # ★ 태그를 떼고 **엔티티를 되돌린 뒤** 댄다. 안 되돌리면 `&` 를 든 제목이
    #   `&amp;` 와 안 맞아 「잃었다」로 잡힌다 — 실제로 넷이 그렇게 걸렸다.
    flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", made)))
    lost = [t for _d, t in hs if re.sub(r"\s+", " ", t) not in flat]
    if lost:
        bad.append(f"제목 {len(lost)}개가 화면에 없다 — 첫 셋: "
                   + " / ".join(t[:30] for t in lost[:3]))
    nt, nf = len(PS.tables(md)), len(PS.figures(md))
    gt, gf = made.count("<table>"), made.count("<img ")
    if gt != nt:
        bad.append(f"화면의 표가 {gt}개다 (정본 {nt})")
    if gf != nf:
        bad.append(f"화면의 그림이 {gf}개다 (정본 {nf})")
    # 바닥 — 비어서 전부 통과하는 것을 막는다
    np_ = made.count('class="pane"')
    if np_ < FLOOR_PANES:
        bad.append(f"칸이 {np_}개다 — 바닥 {FLOOR_PANES}")
    if len(hs) < FLOOR_HEADS:
        bad.append(f"정본 제목이 {len(hs)}개다 — 바닥 {FLOOR_HEADS}")
    if nt < FLOOR_TABLES:
        bad.append(f"정본 표가 {nt}개다 — 바닥 {FLOOR_TABLES}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="굽지 않고 댄다")
    a = ap.parse_args(argv)

    try:
        md = PS.source()
        made = build()
    except PS.SourceError as e:
        print(f"✗ {e}")
        return 1

    bad = carried(made, md)
    for b in bad:
        print(f"✗ {b}")

    if not a.check:
        if bad:
            print("  굽지 않았다 — 완전성 자가 울었다")
            return 2
        OUT.write_text(made, encoding="utf-8")
        print(f"✓ {OUT.relative_to(ROOT)}  {len(made.encode()):,} byte · "
              f"칸 {made.count('class=\"pane\"')} · 표 {made.count('<table>')} · "
              f"그림 {made.count('<img ')}")
        print(f"  지문 {PS.fingerprint()[:16]}…")
        return 0

    if bad:
        return 2
    if not OUT.is_file():
        print("✗ web/proposal.html 이 없다 — 구운 적이 없다")
        return 2
    cur = OUT.read_text(encoding="utf-8")
    # ★ 구운 날짜 한 줄은 대조에서 뺀다. 그 줄 때문에 **날마다 빨개지면**
    #   사람이 이 관문을 끈다 — 오탐이 본문을 덮는다(§18-13).
    norm = lambda s: re.sub(r"구운 날 \d{4}-\d{2}-\d{2}", "구운 날 —", s)
    if norm(cur) != norm(made):
        print("✗ web/proposal.html 이 정본과 다르다 — `uv run python tools/build_proposal.py`")
        # ★ 환경변수의 **유일한 독자는 `paths.py`** 다(§222-3). `env_check` 가
        #   「paths.py 밖에서 os.environ 금지」를 문법으로 강제한다 — 첫 판이
        #   그것을 몰라 verify 의 「환경변수 선언↔실물」을 빨갛게 만들었다.
        return 3 if _paths.env("CI") != "true" else 2
    print(f"✓ 화면이 정본과 같다 · 지문 {PS.fingerprint()[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
