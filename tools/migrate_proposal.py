#!/usr/bin/env python3
"""
migrate_proposal.py — `docs/proposal.docx` 를 **내용 정본** `docs/proposal.md` 로 옮긴다.

    uv run python tools/migrate_proposal.py            재 보기만 (아무것도 안 쓴다)
    uv run python tools/migrate_proposal.py --write    옮긴다

── 왜 한 번만 쓰는 도구인가 ────────────────────────────────────
옮기고 나면 정본이 `docs/proposal.md` 다. 이 파일은 **그 한 번의 이사**를
증명하는 자이고, 이사가 끝나면 `docs/proposal.docx` 와 함께 은퇴한다.
남겨 두는 이유는 하나다 — **옮기면서 무엇을 잃었는지 다시 셀 수 있어야 한다.**

── 무엇을 보는가 ───────────────────────────────────────────────
★ **옮긴 것이 다 담겼는가**를 센다. 「옮겼다」는 주장이 아니라 수다.

    문단   비어있지 않은 <w:p> 의 글이 md 안에 **전부** 있는가
    표     표 수 · 칸 수 · 칸의 글
    그림   inline shape 수 ↔ 뽑아낸 파일 수

  하나라도 모자라면 **죽는다.** 「대충 옮겼다」가 통과할 자리를 없앤다.

★ 이 자가 필요한 이유는 hathor D-0370 이다 — 그림 28장이 통째로 빠졌는데
  바이트 대조 · 정본 대조 5건 · 절 대조 · 단위시험이 **전부 초록**이었다.
  생성기가 **처음부터** 빠뜨리면 커밋된 것과 재생성 결과가 **같이 틀려서**
  대조가 영원히 조용하다. 그래서 수를 **상류와** 맞댄다.

── 제목을 무엇으로 아는가 ──────────────────────────────────────
이 docx 는 **스타일이 하나도 없다**(649 문단 전부 `style=None`). 그래서
굵기와 글자 크기로 유도한다 — 실측한 층이 다섯이다.

    28pt 굵게   표지 제목         → `# `
    20 · 17pt   Part 머리         → `## `
    13pt 굵게   절 제목 (`1.` …)  → `### `
    10pt 굵게   소제목 (`□` …)    → `#### `
    그 밖        본문 · 주석(`※`)  → 문단

★ **유도는 틀릴 수 있다.** 그래서 층을 바꾸는 것이 아니라 **글을 잃는 것**만
  막는다 — 층이 틀려도 글은 남고, 사람이 md 에서 고치면 그만이다.

IN    docs/proposal.docx
OUT   docs/proposal.md · web/proposal/fig/*.png
PARAM 없음
밖    **한 번만 돈다.** 상류 `.docx` 가 바뀌어도 다시 안 돈다 — 이 뒤로 정본은
      `docs/proposal.md` 고, 글을 고치는 자리는 그 파일이다. 서식(굵기·색·칸
      너비)은 안 옮긴다: 옮기는 것은 **글과 구조와 그림**이고, 보이는 꼴은
      `web/proposal.template.html` 이 정한다.
부류  생산   산출물·대장·그림을 만든다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "proposal.docx"
DST = ROOT / "docs" / "proposal.md"
FIG = ROOT / "web" / "proposal" / "fig"

#: 제목은 **번호 꼴**로 가른다. 글자 크기로는 못 가른다 — 실측하니 Part 마다
#: 절 제목 크기가 다르고(Ⅰ 13pt · Ⅱ 11pt · Ⅲ 12pt), Part Ⅲ 에서는 **절(12pt)과
#: 소제목 `□`(12pt)이 같은 크기**다. 문서 자신이 쓰는 규약이 더 믿을 만하다.
#:
#:     Part N.   → ##     1. …  → ###     □ …  → ####     a. …  → #####
#:
#: ★ 28pt 굵게 하나(`Fire-Lane`)만 크기로 가른다 — 문서 제목이고 번호가 없다.
HEAD = (
    (re.compile(r"^Part\s+[IVX]+\."), 2),
    (re.compile(r"^\d+\.\s"), 3),
    (re.compile(r"^□\s"), 4),
    (re.compile(r"^[a-z]\.\s"), 5),
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _runs_sig(p) -> tuple[int, float | None]:
    """(굵은 run 수, 가장 큰 글자 크기). 둘로 층을 가른다."""
    bold = sum(1 for r in p.runs if r.bold)
    sizes = [r.font.size.pt for r in p.runs if r.font.size is not None]
    return bold, (max(sizes) if sizes else None)


def _depth(p) -> int:
    """제목 깊이. 0 이면 본문이다.

    ★ **굵지 않으면 제목이 아니다.** 본문에도 `1. …` 로 시작하는 줄이 있고
      그것까지 제목으로 올리면 목차가 산문으로 채워진다.
    """
    bold, size = _runs_sig(p)
    if not bold:
        return 0
    if size is not None and size >= 24.0:
        return 1                       # 문서 제목 하나. 번호가 없어 크기로 가른다
    t = p.text.strip()
    for rx, d in HEAD:
        if rx.match(t):
            return d
    return 0                           # 굵지만 번호가 없다 — 강조 본문이다


def _cell_text(c) -> str:
    """칸의 글. **공백을 전부 접는다.**

    ★ 칸 안에 `<w:br/>` 이 있으면 `p.text` 에 `\n` 이 그대로 들어온다. 그걸 안
      접으면 마크다운 행이 **두 줄로 쪼개져 표가 깨진다** — 실제로 「STP 전략」
      표 하나가 그렇게 사라졌고, 문단 대조는 공백을 접고 비교해서 **못 봤다**.
    """
    raw = " ".join(t for t in (q.text for q in c.paragraphs) if t.strip())
    return re.sub(r"\s+", " ", raw).strip()


def _table_md(t) -> list[str]:
    """표 → 마크다운. **칸을 하나도 안 버린다** — 빈 칸은 빈 칸으로 남긴다."""
    rows = [[_cell_text(c).replace("|", r"\|") for c in r.cells] for r in t.rows]
    if not rows:
        return []
    wide = max(len(r) for r in rows)
    rows = [r + [""] * (wide - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "---|" * wide]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return out


def walk(doc):
    """본문을 **순서대로** 돈다. `paragraphs` 와 `tables` 를 따로 읽으면 순서를 잃는다."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    for child in doc.element.body.iterchildren():
        if child.tag == f"{W}p":
            yield ("p", Paragraph(child, doc))
        elif child.tag == f"{W}tbl":
            yield ("t", Table(child, doc))


def extract_figures(doc, write: bool) -> list[str]:
    """inline shape 를 파일로 뽑는다. 이름은 **나온 순서**다."""
    names = []
    for i, sh in enumerate(doc.inline_shapes, 1):
        rid = sh._inline.graphic.graphicData.pic.blipFill.blip.embed
        part = doc.part.related_parts[rid]
        ext = Path(part.partname).suffix.lower() or ".png"
        name = f"fig{i:02d}{ext}"
        if write:
            FIG.mkdir(parents=True, exist_ok=True)
            (FIG / name).write_bytes(part.blob)
        names.append(name)
    return names


def build(doc) -> tuple[list[str], dict]:
    """md 줄과 **상류 수**를 같이 낸다. 수를 따로 세면 두 집이 생긴다."""
    figs = [n for n in (f"fig{i:02d}" for i in range(1, len(doc.inline_shapes) + 1))]
    fi = iter(figs)
    out: list[str] = []
    seen_p, seen_t, cells, padded = [], 0, 0, 0
    for kind, el in walk(doc):
        if kind == "t":
            seen_t += 1
            # ★ 상류를 **생성물과 같은 방식으로** 센다. 마크다운은 병합 칸을 못
            #   들어서 좁은 행을 가장 넓은 행에 맞춰 채운다 — 상류를 날것으로
            #   세면 「27개가 늘었다」로 보이고, 그것은 잃은 것이 아니라 **채운
            #   것**이다. 채운 수는 따로 든다.
            raw = [len(r.cells) for r in el.rows]
            wide = max(raw) if raw else 0
            cells += wide * len(raw)
            padded += wide * len(raw) - sum(raw)
            out += ["", *_table_md(el), ""]
            continue
        text = el.text.strip()
        # 그림만 든 문단은 글이 없다 — 그림 자리로 바꾼다
        if not text:
            if el._element.findall(f".//{W}drawing"):
                try:
                    out += ["", f"![]({next(fi)}.png)", ""]
                except StopIteration:
                    pass
            continue
        seen_p.append(text)
        d = _depth(el)
        out.append(("#" * d + " " + text) if d else text)
        out.append("")
    return out, {"문단": seen_p, "표": seen_t, "칸": cells, "채운칸": padded,
                 "그림": len(doc.inline_shapes)}


def carried(md: str, up: dict, figs: list[str]) -> list[str]:
    """**상류가 든 것을 생성물이 다 담았나.** 수가 아니라 글로 맞댄다."""
    bad = []
    flat = re.sub(r"\s+", " ", md)

    def _in(t: str) -> bool:
        # ★ `|` 는 **표 칸에서만** 이스케이프한다. 본문 문단은 그대로 쓴다 —
        #   그래서 두 꼴을 다 본다. 한 꼴만 보면 `|` 를 든 문단이 「잃었다」로 잡힌다.
        s = re.sub(r"\s+", " ", t)
        return s in flat or s.replace("|", r"\|") in flat

    lost = [t for t in up["문단"] if not _in(t)]
    if lost:
        bad.append(f"문단 {len(lost)}개를 잃었다 — 첫 셋: " +
                   " / ".join(t[:40] for t in lost[:3]))
    # ★ 표를 **생성물의 파서로** 센다. 여기서 따로 세면 두 집이 생기고,
    #   실제로 그랬다 — `md.count("\n|---")` 는 56 을 내고 `proposal_source`
    #   는 55 를 냈다. 구는 쪽이 보는 수가 맞는 수다.
    import proposal_source as PS
    got = PS.tables(md)
    if len(got) != up["표"]:
        bad.append(f"표가 {len(got)}개다 (상류 {up['표']})")
    got_c = sum(len(r) for tb in got for r in tb)
    if got_c != up["칸"]:
        bad.append(f"표 칸이 {got_c}개다 (상류 {up['칸']})")
    got_f = len(re.findall(r"!\[]\(fig\d+\.png\)", md))
    if got_f != up["그림"]:
        bad.append(f"그림 자리가 {got_f}개다 (상류 {up['그림']})")
    if len(figs) != up["그림"]:
        bad.append(f"뽑아낸 그림 파일이 {len(figs)}개다 (상류 {up['그림']})")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="실제로 옮긴다")
    a = ap.parse_args(argv)

    import docx
    doc = docx.Document(str(SRC))
    lines, up = build(doc)
    md = "\n".join(lines).rstrip() + "\n"
    md = re.sub(r"\n{3,}", "\n\n", md)
    figs = extract_figures(doc, a.write)

    print(f"상류  문단 {len(up['문단'])} · 표 {up['표']}(칸 {up['칸']} · "
          f"그중 병합 보정 {up['채운칸']}) · 그림 {up['그림']}")
    print(f"생성  {len(md.splitlines())}줄 · {len(md.encode())} byte")

    # ★ 중복은 **옮기는 쪽이 고치지 않는다.** 보이게만 한다 — 고치는 것은 사람이다.
    dup = [(n, t) for t, n in collections.Counter(up["문단"]).items() if n > 1]
    if dup:
        print(f"\n  ★ 상류에 **같은 글이 여러 번** 있다 {len(dup)}종 — md 에서 사람이 지운다")
        for n, t in sorted(dup, key=lambda x: -x[0])[:6]:
            print(f"      ×{n}  {t[:68]}")

    bad = carried(md, up, figs)
    if bad:
        print("\n✗ 옮기면서 잃었다")
        for b in bad:
            print(f"    {b}")
        return 1
    print("\n✓ 상류가 든 것을 **전부** 담았다 — 문단 · 표 · 그림")

    if a.write:
        DST.write_text(md, encoding="utf-8")
        print(f"→ {DST.relative_to(ROOT)}  sha256 {hashlib.sha256(md.encode()).hexdigest()[:16]}")
    else:
        print("  (--write 를 줘야 쓴다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
