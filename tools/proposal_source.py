#!/usr/bin/env python3
"""
proposal_source.py — 기획서 **정본을 읽는 자리 하나**.

    uv run python tools/proposal_source.py           구간 · 절 · 표 · 지문을 찍는다

── 왜 따로인가 ─────────────────────────────────────────────────
굽는 쪽(`build_proposal.py`)과 무는 쪽이 정본을 **따로 파싱하면 반드시 갈린다.**
이 저장소가 여러 번 배운 형태다 — `normalize_raw` 와 `ingest` 가 같은 산출을
두 곳에서 만들다 갈렸고(§`ngii1k.build()` 머리말), 제공기관 목록은 한때 다섯
벌이었다(§73). **읽는 법은 한 집에만 둔다.**

표준 라이브러리만 쓴다. 이 파일이 무거워지면 굽는 쪽이 못 부른다.

── 지문 ────────────────────────────────────────────────────────
`fingerprint()` 는 **정본 글의 sha256** 이다. 생성물에 심고 검사가 견준다.

★ 왜 생성물의 바이트가 아니라 **입력의 지문**인가 — 생성물은 글꼴 · 날짜 ·
  도구 판에 따라 바이트가 흔들릴 수 있다. 입력은 안 흔들린다. 토트는 생성기
  파일별 지문(`build.lock.json`)을, 하토르는 정본 구간 지문을 썼고 **둘 다
  「산출물이 생성기보다 낡았다」를 같은 방법으로 잡는다.**

IN    docs/proposal.md
OUT   없음 (읽기만 한다)
PARAM 없음
밖    **글의 뜻은 안 본다.** 제목 · 표 · 그림의 **개수와 글자**만 센다 — 어느 절이
      어디 붙어야 하는가는 사람이 정하고, 그 결과를 이 파일이 그대로 읽는다.
      보이는 꼴도 안 본다 — 굵기와 색은 와꾸가 정한다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs" / "proposal.md"

#: 사람이 보는 보고(`--main`)에만 쓰는 접두. **생성물에 안 심는다.**
#: ★ 2026-10-09 (§440-8). 종전 주석은 「검사가 이 꼴로 찾는다」였고 **거짓이었다**
#:   — 찾는 쪽이 없다. 화면에 심어 두고 아무도 안 읽었으므로 심는 쪽을 지웠다.
#:   `build_proposal --check` 는 화면을 **다시 구워** 통째로 대고, 그 대조가
#:   지문보다 넓다.
FINGERPRINT = "firelane-proposal-sha256:"

HEAD = re.compile(r"^(#{1,5})\s+(.+?)\s*$", re.M)
FIGURE = re.compile(r"^!\[]\((fig\d+\.png)\)\s*$", re.M)
ROW = re.compile(r"^\|.*\|\s*$")
RULE = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+\s*$")

#: ★ **이스케이프한 `\|` 는 칸을 안 가른다.** 쓰는 쪽(`migrate_proposal._table_md`)이
#:   칸 안의 `|` 를 `\|` 로 바꾸는데 읽는 쪽이 그것을 모르면 **한 칸이 둘로
#:   쪼개진다.** 실측에서 칸이 1,317 → 1,336 으로 열아홉 늘어 보였다.
CELL = re.compile(r"(?<!\\)\|")


def _trim(ln: str) -> str:
    """양 끝의 칸 구분자를 뗀다. 안쪽의 `\\|` 는 건드리지 않는다."""
    s = ln.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith(r"\|"):
        s = s[:-1]
    return s


class SourceError(RuntimeError):
    """정본이 기대한 모양이 아니다. **조용히 빈 결과를 내지 않는다.**"""


def source(root: Path = ROOT) -> str:
    """정본 글. 없으면 터진다 — 빈 문자열은 「기획서가 비었다」를 통과시킨다."""
    p = root / "docs" / "proposal.md"
    if not p.is_file():
        raise SourceError(f"{p.relative_to(root)} 가 없다 — 정본이 없으면 구울 것이 없다")
    t = p.read_text(encoding="utf-8")
    if not t.strip():
        raise SourceError("정본이 비었다")
    return t


def fingerprint(root: Path = ROOT) -> str:
    return hashlib.sha256(source(root).encode("utf-8")).hexdigest()


def heads(text: str | None = None) -> list[tuple[int, str]]:
    """(깊이, 글). 목차와 **완전성 자**가 같이 쓴다."""
    t = source() if text is None else text
    return [(len(m.group(1)), m.group(2)) for m in HEAD.finditer(t)]


def figures(text: str | None = None) -> list[str]:
    t = source() if text is None else text
    return FIGURE.findall(t)


def tables(text: str | None = None) -> list[list[list[str]]]:
    """표 → 행 → 칸. 구분선(`|---|`)이 있어야 표로 본다."""
    t = source() if text is None else text
    out, cur, saw_rule = [], [], False
    for ln in t.splitlines():
        if ROW.match(ln):
            if RULE.match(ln):
                saw_rule = True
                continue
            cur.append([c.replace(r"\|", "|").strip() for c in CELL.split(_trim(ln))])
            continue
        if cur:
            if saw_rule:
                out.append(cur)
            cur, saw_rule = [], False
    if cur and saw_rule:
        out.append(cur)
    return out


def parts(text: str | None = None) -> list[tuple[str, list[str]]]:
    """`## Part …` 하나에 그 밑 `### N.` 들. 화면의 칸을 가르는 선언이다."""
    t = source() if text is None else text
    out: list[tuple[str, list[str]]] = []
    for d, h in heads(t):
        if d == 2:
            out.append((h, []))
        elif d == 3 and out:
            out[-1][1].append(h)
    return out


def main() -> int:
    # 깃발을 거절하는 법은 저장소에 한 집이다 — `argparse` 를 안 쓰는 도구의 몫.
    # ★ 머리말이 「표준 라이브러리만」이라 적은 것과 안 어긋난다: 이 import 는
    #   `main()` 안에 있어 **굽는 쪽이 모듈로 부를 때는 안 탄다.**
    from firelane.cli import no_args
    no_args(__doc__)
    t = source()
    hs, tb, fg = heads(t), tables(t), figures(t)
    print(f"정본   {MD.relative_to(ROOT)}  {len(t.encode())} byte · {len(t.splitlines())}줄")
    print(f"지문   {FINGERPRINT}{fingerprint()[:16]}…")
    print(f"제목   {len(hs)}  (" + " · ".join(
        f"h{d} {sum(1 for x, _ in hs if x == d)}" for d in range(1, 6)) + ")")
    print(f"표     {len(tb)}  칸 {sum(len(r) for t_ in tb for r in t_)}")
    print(f"그림   {len(fg)}")
    for p, ss in parts(t):
        print(f"  {p}  — 절 {len(ss)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
