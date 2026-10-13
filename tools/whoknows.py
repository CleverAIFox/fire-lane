#!/usr/bin/env python3
"""
whoknows.py — **이 파일을 아는 절이 어디인가.** 건드리기 전에 그것부터 연다.

    uv run python tools/whoknows.py src/firelane/seg/width.py
    uv run python tools/whoknows.py src/firelane/seg/width.py tools/widthcross.py
    uv run python tools/whoknows.py --grep 폭          이름에 그 글자가 든 파일 전부
    uv run python tools/whoknows.py --selftest

── 왜 생겼나 (2026-10-13 · DECISIONS §515) ────────────────────
봉인은 **절 → 파일** 방향으로만 조회된다. `docseal.json` 이 「§510 은 이 파일
넷을 본다」를 적고, 묻고 싶은 것은 **반대**다 — 「`width.py` 를 고치려는데
누가 이 파일을 두고 이미 판단을 적었나」.

그 방향이 없어서 같은 자리를 다시 풀었다. §513 이 조사 도구 머리말에서,
§515 가 반입 체계에서 그것을 겪었다. 사람이 「디시즌 먼저 읽어라」를 되풀이
하는 것은 강제자가 아니다(§390) — **한 번 치면 나오는 자리**가 강제자다.

★ **관문이 아니다.** 래칫도 없고 빨강도 없다. 「읽어라」는 강제할 수 없고,
  강제할 수 있는 것은 **읽기가 싸지는 것**이다. 우는 관문을 하나 더 세우면
  그 빨강은 안 읽힌다(§284-6).

부류  조사
IN    data/golden/docseal.json(절 → 파일) · docs/*.md(절 제목)
OUT   파일 → 그 파일을 **본문이 지목한** 절 목록
PARAM 없음
밖    **절이 맞는가는 안 본다** — 봉인이 낡았는가는 `docseal check` 소관이고
      덮임 수는 `sealcov` 소관이다. 여기는 **조회 방향 하나**를 돌려준다.
      강제자 칸(`강제자  ...`)에 이름이 적힌 것은 안 센다 — `sealcov` 와
      같은 규율이다(「누가 지킨다」지 「읽고 판단했다」가 아니다).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEAL = ROOT / "data" / "golden" / "docseal.json"

#: 절 제목 한 줄. `## 515. 엑셀은 …` · `### 515-2. 값의 규율 …`
_HEAD = re.compile(r"^#{2,3}\s+(\d+(?:-\d+)?)\.\s+(.*?)\s*$")


def seals(src: dict | None = None) -> dict[str, dict]:
    """봉인 대장. 절 id → 항목."""
    return json.loads(SEAL.read_text(encoding="utf-8")) if src is None else src


def titles(doc: Path) -> dict[str, str]:
    """`docs/<DOC>.md` → {절 번호: 제목}. 없는 문서는 빈 표다."""
    if not doc.exists():
        return {}
    out = {}
    for ln in doc.read_text(encoding="utf-8").splitlines():
        if m := _HEAD.match(ln):
            out[m.group(1)] = m.group(2)
    return out


def index(src: dict | None = None) -> dict[str, list[str]]:
    """**파일 → 그 파일을 본 절들.** 이 함수가 이 도구의 전부다. 순수하다.

    ★ 항목 이름을 `seal` 로 둔다. `e`·`v`·`entry` 로 두면
      `tests/test_ledger_accessor.py` 가 **대장을 직접 읽는 자**로 센다 —
      여기 `files` 는 봉인 대장의 칸이고 `sources.yaml` 의 것이 아니다.
      그 관문의 분모가 둘을 못 가르므로 **이름이 가른다**.
    """
    out: dict[str, list[str]] = {}
    for sec, seal in (src if src is not None else seals()).items():
        for f in (seal or {}).get("files") or []:
            out.setdefault(f, []).append(sec)
    return {f: sorted(v, key=_order) for f, v in out.items()}


def _order(sec: str) -> tuple:
    """`DECISIONS/513-5` → 정렬 열쇠. 숫자를 글자로 세면 100 이 2 앞에 선다."""
    doc, _, num = sec.rpartition("/")
    head, _, sub = num.partition("-")
    return (doc, int(head) if head.isdigit() else 10**9,
            int(sub) if sub.isdigit() else -1)


def report(paths: list[str]) -> int:
    idx = index()
    cache: dict[str, dict[str, str]] = {}
    missing = 0
    for p in paths:
        secs = idx.get(p, [])
        print(f"\n── {p}  —  아는 절 {len(secs)}")
        # ★ 2026-10-13. **없는 경로와 찬 파일이 같은 화면이었다.** 첫 질문으로
        #   당시 `src/firelane/width.py`(없는 경로다) 를 물었는데 실물은 `src/firelane/seg/
        #   width.py` 였고, 도구가 「아무 절도 안 본다」로 답했다 — 저장소에서
        #   제일 많이 다툰 파일이 차다는 뜻이 되므로 **거짓을 자신 있게**
        #   말한 것이다. 오타가 발견으로 읽히면 그 도구는 덫이다.
        if not (ROOT / p).exists():
            print(f"   ✗ **그런 파일이 없다.** 이름을 확인해라 — `{p}`")
            if near := [f for f in idx if Path(f).name == Path(p).name]:
                print(f"     이름이 같은 것 — {' · '.join(near)}")
            continue
        if not secs:
            missing += 1
            print("   **아무 절도 이 파일을 안 본다.** 고치기 전에 한 번 더 "
                  "생각해라 — 판단이 적힌 적이 없다는 뜻이고, 그래서 "
                  "되풀이하기 쉬운 자리다.")
            continue
        for sec in secs:
            doc, _, num = sec.rpartition("/")
            if doc not in cache:
                cache[doc] = titles(ROOT / "docs" / f"{doc}.md")
            print(f"   {doc} §{num:<8} {cache[doc].get(num, '(제목 없음)')}")
    # ★ 모르는 파일은 **실패가 아니다.** 이것은 조회지 관문이 아니다.
    if missing:
        print(f"\n  아는 절이 없는 파일 {missing}개 — 덮임 수는 `sealcov` 가 든다")
    return 0


def selftest() -> int:
    """합성 대장으로 **양방향**을 민다(§405 의 규율)."""
    bad: list[str] = []
    src = {"DECISIONS/510": {"files": ["a.py", "b.py"]},
           "DECISIONS/9": {"files": ["a.py"]},
           "DECISIONS/513-5": {"files": ["a.py"]},
           "MASTER/3": {"files": ["b.py"]},
           "DECISIONS/7": {}}
    got = index(src)
    if got.get("a.py") != ["DECISIONS/9", "DECISIONS/510", "DECISIONS/513-5"]:
        bad.append(f"절 정렬이 숫자가 아니다 — {got.get('a.py')}")
    if got.get("b.py") != ["DECISIONS/510", "MASTER/3"]:
        bad.append(f"문서가 둘인 파일을 못 모은다 — {got.get('b.py')}")
    if "c.py" in got:
        bad.append("없는 파일을 든다")
    if index({"X/1": {"files": None}}) != {}:
        bad.append("`files` 가 비면 터진다 — 봉인 항목은 그 칸이 없을 수 있다")
    # ★ 제목 읽기 — 표가 아니라 **제목 줄**에서만 집는다
    tmp = ROOT / "docs" / "DECISIONS.md"
    t = titles(tmp)
    if "515" not in t:
        bad.append("§515 제목을 못 읽는다 — 제목 정규식이 실물과 다르다")
    if any(k.startswith("|") for k in t):
        bad.append("표 행을 절 제목으로 읽는다")
    # ★ 실물 — 이 도구 자신을 아는 절이 있어야 한다(§515 가 그 절이다)
    if "tools/whoknows.py" not in index():
        bad.append("이 도구를 아는 절이 봉인에 없다 — 도장을 안 찍었다")
    # ★ 없는 경로 카나리아 — 2026-10-13 의 실제 사고(`seg/` 를 빼고 물었다)
    if (ROOT / "src/firelane/width.py").exists():   # 당시 없던 경로다
        bad.append("당시 없던 `src/firelane/width.py` 가 생겼다 — "
                   "아래 카나리아를 다시 골라라")
    if "src/firelane/seg/width.py" not in index():
        bad.append("`seg/width.py` 를 아는 절이 없다 — 봉인이 낡았거나 자가 틀렸다")
    if bad:
        print("★ 자기검사 실패")
        for b in bad:
            print(" ", b)
        return 1
    print("selftest 초록")
    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("경로", nargs="*", help="저장소 상대 경로")
    ap.add_argument("--grep", help="이름에 이 글자가 든 파일 전부")
    a = ap.parse_args()
    paths = list(a.경로)
    if a.grep:
        paths += [f for f in sorted(index()) if a.grep in f]
    if not paths:
        ap.error("경로나 --grep 이 필요하다")
    return report(sorted(dict.fromkeys(paths)))


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    sys.exit(main())
