"""dms_fix_inherit.py — 부모 칸의 「하위 N」을 **판정기가 세는 그 수**로 다시 쓴다.

`tests/test_dms_ids.py::test_every_inherited_section_is_declared_with_a_count` 가 울면
손으로 세지 않고 이것을 돌린다. 수는 `dms.inherit_counts` 가 세는 규칙 그대로
(`scan()` 의 `inherit` 행을 부모별로 센다)에서 얻는다 — 두 벌로 세지 않는다.

    .venv/bin/python tools/dms_fix_inherit.py          # 무엇을 바꿀지 보인다
    .venv/bin/python tools/dms_fix_inherit.py --write  # 쓴다

IN    docs/*.md (`dms.DOCS` 가 든 문서) — `dms.scan()` 이 읽는 그대로
OUT   그 문서의 부모 칸 한 줄(「하위 일곱」 같은 수 낱말) — `--write` 일 때만
PARAM 없음
부류  생산   문서의 줄을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서) — 새 절을 쓸 때마다 수가 어긋난다(§648~§656 에서 여섯)
밖    **새 하위 절을 읽었는가는 안 본다.** 수만 맞춘다 — 그 새 절을 사람이 보게 하려고 판정기가
      우는 것인데, 이 도구가 그 울음을 지운다. 돌린 뒤 늘어난 절을 읽는 것은 사람 몫이다.
      「하위 N」 줄이 없는 부모는 안 만든다(수 없는 옛 표기는 판정기도 안 센다).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dms():
    spec = importlib.util.spec_from_file_location("_dms_fix", ROOT / "tools" / "dms.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    d = _dms()
    data = d.scan()
    kids: dict[str, int] = {}
    for r in data["rows"]:
        if r["state"] != "inherit":
            continue
        doc, _, tail = r["id"].partition("/")
        parent = f"{doc}/{tail.split('/')[0].split('-')[0]}"
        kids[parent] = kids.get(parent, 0) + 1
    word = {}
    for w, n in d.WORD_N.items():
        word.setdefault(n, w)
    word[1] = "하나"
    rows = {r["id"]: r for r in data["rows"]}
    edits: dict[str, list[tuple[int, str, str]]] = {}
    for pid, n in sorted(kids.items()):
        r = rows.get(pid)
        said = d._said_count(r.get("field", "")) if r else None
        if said is None or said == n:
            continue
        if n not in word:
            print(f"✗ {pid}: 수 {n} 을 말로 적을 수 없다 — 손으로 본다", file=sys.stderr)
            return 1
        lines = (ROOT / r["doc"]).read_text(encoding="utf-8").split("\n")
        for i in range(r["at"] - 1, len(lines)):
            if i > r["at"] - 1 and d.FIELD_END.match(lines[i]) and not lines[i].strip() == "":
                break
            m = d.SAID_N.search(lines[i])
            if m:
                edits.setdefault(r["doc"], []).append((i, pid, f"{said}→{n}"))
                new = _swap(d, m, lines[i], word[n], n)
                lines[i] = new
                (ROOT / r["doc"]).write_text("\n".join(lines), encoding="utf-8") if "--write" in sys.argv else None
                print(f"{r['doc']}:{i + 1}  {pid}  하위 {said} → {n}")
                break
        else:
            print(f"✗ {pid}: 「하위 N」 줄을 못 찾았다", file=sys.stderr)
            return 1
    return 0


def _swap(d, m: re.Match, line: str, w: str, n: int) -> str:
    """매치의 수 부분만 바꾼다 — 말이면 말로, 숫자면 숫자로."""
    for g in (1, 2, 3):
        if m.group(g):
            return line[:m.start(g)] + (w if g == 1 else str(n)) + line[m.end(g):]
    return line


if __name__ == "__main__":
    raise SystemExit(main())
