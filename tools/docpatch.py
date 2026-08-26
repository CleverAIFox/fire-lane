#!/usr/bin/env python
"""문서 절 단위 멱등 교체기.

`docfix_20260817.py` 계열이 일회성이라 아홉 번 다시 만들어진 것과,
`PLAN §7-5` 가 두 벌이 된 것(DECISIONS §18)이 이 도구의 존재 이유다.

원칙 — **넣기 전에 이미 넣었는지 검사한다.** 앵커가 있는지가 아니라
넣을 내용이 있는지를 본다. 두 번 실행해도 결과가 같다.

    python tools/docpatch.py ensure-section docs/PLAN.md '### 8-5.' \
        docs/_patch/PLAN.8-5.md --after '### 8-4.'
    python tools/docpatch.py append-rows docs/PLAN.md '## 1.' \
        docs/_patch/PLAN.1.rows.md
    python tools/docpatch.py check docs/PLAN.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

H = re.compile(r"^(#{1,4})\s+(.*)$")


def _level(line: str) -> int:
    m = H.match(line)
    return len(m.group(1)) if m else 0


def _find_block(lines: list[str], key: str) -> tuple[int, int] | None:
    """`key` 로 시작하는 제목 줄부터 같거나 상위 제목 직전까지."""
    for i, line in enumerate(lines):
        if not line.startswith(key):
            continue
        lv = _level(line)
        for j in range(i + 1, len(lines)):
            k = _level(lines[j])
            if k and k <= lv:
                return i, j
        return i, len(lines)
    return None


def _trim(block: list[str]) -> list[str]:
    while block and not block[-1].strip():
        block.pop()
    return block


def ensure_section(doc: Path, key: str, frag: Path, after: str | None) -> str:
    lines = doc.read_text(encoding="utf-8").splitlines()
    new = _trim(frag.read_text(encoding="utf-8").splitlines())
    if not new or not new[0].startswith(key):
        sys.exit(f"조각의 첫 줄이 '{key}' 로 시작하지 않는다: {frag}")

    span = _find_block(lines, key)
    if span:
        i, j = span
        if _trim(lines[i:j]) == new:
            return f"변경 없음 — {doc}:{key}"
        lines[i:j] = new + [""]
        doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return f"교체 — {doc}:{key} ({j - i} → {len(new)}줄)"

    if not after:
        sys.exit(f"'{key}' 가 없고 --after 도 없다. 삽입 위치를 정할 수 없다")
    anchor = _find_block(lines, after)
    if not anchor:
        sys.exit(f"앵커 '{after}' 를 찾지 못했다")
    at = anchor[1]
    lines[at:at] = new + [""]
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"삽입 — {doc}:{key} ({after} 뒤, {len(new)}줄)"


ROW = re.compile(r"^\|\s*([^|]+?)\s*\|")


def append_rows(doc: Path, key: str, frag: Path) -> str:
    lines = doc.read_text(encoding="utf-8").splitlines()
    span = _find_block(lines, key)
    if not span:
        sys.exit(f"절 '{key}' 를 찾지 못했다")
    i, j = span

    rows = [x for x in frag.read_text(encoding="utf-8").splitlines() if x.startswith("|")]

    # ★ 절 안에 표가 여럿일 수 있다. 대상은 **첫 하위절 앞의 표** 하나다.
    #   이 제한이 없으면 `## 1.` 의 행이 `### 1-23a.` 의 표 끝에 붙는다.
    #   2026-08-26 에 실제로 그랬다 — 넣을 자리를 좁히지 않은 것이 원인이다.
    stop = next((k for k in range(i + 1, j) if lines[k].startswith("###")), j)

    have = {m.group(1) for x in lines[i:stop] if (m := ROW.match(x))}
    todo = [x for x in rows if (m := ROW.match(x)) and m.group(1) not in have]
    if not todo:
        return f"변경 없음 — {doc}:{key} (행 {len(rows)}개 모두 존재)"

    tbl = [k for k in range(i, stop) if lines[k].startswith("|")]
    if not tbl:
        sys.exit(f"절 '{key}' 의 첫 하위절 앞에 표가 없다")
    last = max(tbl)
    lines[last + 1 : last + 1] = todo
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"행 추가 — {doc}:{key} ({len(todo)}개)"


def check(doc: Path) -> str:
    """제목 중복과 번호 불연속을 본다. 규약 강제자는 tests 쪽이 정본이다."""
    lines = doc.read_text(encoding="utf-8").splitlines()
    heads = [x for x in lines if _level(x)]
    dup = {x for x in heads if heads.count(x) > 1}
    if dup:
        return "중복 제목: " + " · ".join(sorted(dup))
    return f"{doc} — 제목 {len(heads)}개, 중복 없음"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ensure-section")
    a.add_argument("doc")
    a.add_argument("key")
    a.add_argument("fragment")
    a.add_argument("--after")

    b = sub.add_parser("append-rows")
    b.add_argument("doc")
    b.add_argument("key")
    b.add_argument("fragment")

    c = sub.add_parser("check")
    c.add_argument("doc")

    ns = p.parse_args()
    if ns.cmd == "ensure-section":
        print(ensure_section(Path(ns.doc), ns.key, Path(ns.fragment), ns.after))
    elif ns.cmd == "append-rows":
        print(append_rows(Path(ns.doc), ns.key, Path(ns.fragment)))
    else:
        print(check(Path(ns.doc)))


if __name__ == "__main__":
    main()
