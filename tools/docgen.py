#!/usr/bin/env python3
"""
docgen.py — 문서가 **흐르는 숫자**를 글자로 들지 않는다. 도구가 채운다.

    uv run python tools/docgen.py            생성 블록을 실물 값으로 채운다
    uv run python tools/docgen.py --check    대조만 — 어긋나면 rc≠0 (verify.sh · 시험)
    uv run python tools/docgen.py --list     축 · 실물 값 · 블록이 몇 곳인가

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-25 (DECISIONS §246). 축은 섰는데 **울기만 하고 고쳐주지 않았다.**
  하루 사이에 사람이 손으로 맞춘 것 —

      전수 절 수      1,004 → 1,017 → 1,030 → 1,033 → 1,036   (하루 네 번)
      봉인 소스 종수   64 → 71
      PLAN §1 행수     114 → 108

  §246-1 이 「숫자를 고치는 것은 처방이 아니다」라고 적고 축을 박았다. 그
  다음 칸이 비어 있었다 — **축이 아는 값을 문서에 넣어주는 자리.** 검사는
  사람을 부르고 사람은 매번 같은 줄을 고친다. 고치는 일이 사람에게 남아
  있으면 그 일은 갈린다 — 문서가 숫자를 **들지 않게** 하는 것이 처방이다.

★ **정본은 실물이다.** 이 도구는 문서를 문서로 대조하지 않는다. 대장은
  `ledger.load()`, 절은 `dms.scan()`, PLAN §1 행은 `plan_renumber` 가 낸다 —
  판별식을 여기서 다시 쓰지 않는다(R3). 같은 이유로 `tests/test_repo_numbers.py`
  가 `AXES` · `truth()` 를 **여기서 받아 간다**. 축의 집은 이 파일 하나다.

★ **정본이 없는 값은 블록으로 만들지 않는다.** §246-2 가 봉인 시점 절 수를
  문서에서 뺐다 — 다음 봉인이 덮어쓰므로 정본이 될 수 없다. 같은 판단을
  둘에 더 했다(아래 `밖` ③④).

── 블록 문법 ──────────────────────────────────────────────────
    <!--gen: 축 축 …-->
    … 생성 줄 …
    <!--/gen-->

★ 마크다운에서 **안 보인다** — `<!--stale-ok-->` · `<!--voice-ok-->` 와 같은
  자리다(MASTER §0-3). 블록 안에서 그 축의 표기를 찾아 **수만** 갈아 넣는다.
  표기 자체는 안 건드리므로 `docnum_check` · `test_repo_numbers` 의 정규식이
  계속 문다. 값을 지우고 자리표를 넣는 판을 쓰지 않은 이유가 그것이다 —
  문서는 사람이 읽는 것이고, 자리표는 읽히지 않는다.

★ 여는 줄이 **제목 밖**에 있다. 제목에 주석을 붙이면
  `test_declaration_sync::test_plan_section1_count_agrees` 의 `\\s*$` 가 깨진다 —
  생성물 문법이 기존 강제자를 깨면 그것은 문법이 틀린 것이다.

── 판정 ──────────────────────────────────────────────────────
    블록 값이 실물과 다르다              실패(`--check`) · 인자 없이 돌면 채운다
    블록이 그 축의 표기를 0곳 찾았다      실패 — 표기가 바뀌었다
    축이 어느 블록에도 안 걸렸다          실패 — **0건은 통과가 아니다**
    정본이 죽었다(대장 0종 · 절 0개)      실패 — 값이 0이면 블록이 통째로 거짓이다

★ 셋째가 `deadcheck` ③ 과 같은 물음이다. 블록을 하나도 못 찾은 초록은
  「깨끗하다」가 아니라 **「안 봤다」**다.

IN    docs/MASTER.md · docs/PLAN.md · README.md · `ledger.load()` · `dms.scan()`
OUT   위 문서 셋(인자 없이 돌 때) · 표준출력
PARAM AXES · DOCS · `--root`
밖    ① **블록 밖의 같은 표기는 안 고친다.** 문서 어디에 적힌 수든 찾는 일은
         `tests/test_repo_numbers.py` 가 한다 — 이 도구는 블록만 연다. 둘은
         일부러 갈랐다: 고치는 자리는 좁아야 하고 보는 자리는 넓어야 한다.
      ② **`docs/DECISIONS.md` 는 안 연다.** append-only 역사라 그때의 수가
         옳다. 회고를 고치면 회고가 아니다.
      ③ **PLAN §13-3 건수는 축이 아니다.** 판별식 정본이
         `tests/test_declaration_sync.py::_ledger_rows` 안에만 있어 여기서
         다시 쓰면 정본이 둘이 된다(R3). 문 하나가 먼저 나야 한다.
      ④ **`retired` 종수는 축이 아니다.** 세려면 대장의 폐기 블록을 직접
         읽어야 하고 그것은 `test_lake.py::test_file_owners_are_resolved_in_one_place`
         래칫이 세는 사본이다(§246 밖 ②). 축 하나를 위해 다른 강제자를
         깨지 않는다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

import dms
import plan_renumber

from firelane import ledger

ROOT = Path(__file__).resolve().parents[1]

#: 블록이 사는 문서. **`DECISIONS` 는 없다**(머리말 `밖` ②).
DOCS = ("docs/MASTER.md", "docs/PLAN.md", "README.md")


class Axis(NamedTuple):
    """한 축 — 표기를 찾는 정규식과 사람이 읽을 뜻."""

    pat: re.Pattern[str]
    what: str


#: 축 이름 → (정규식, 뜻). **정규식은 그 수 하나만** 잡는다.
#:
#: ★ 앵커를 정본 이름(`datasets` · `inherit`)이나 `raw` 로 잡는다. 넓게 잡으면
#:   「소스 21종」 같은 부분집합이 걸리고, 한 번 오탐이 나면 사람이 검사를
#:   끈다(§246-1). `1` 번 그룹이 **수 하나**여야 한다 — 이 도구가 그 그룹의
#:   자리만 갈아 넣는다.
AXES: dict[str, Axis] = {
    "datasets": Axis(re.compile(r"`datasets`\s+([\d,]+)\s*종"),
                     "대장 전체 — `ledger.load()` 의 `datasets` 종수"),
    "sealable": Axis(re.compile(r"소스\s+([\d,]+)\s*종의\s+raw"),
                     "봉인 대상 — 대장에서 `on_demand` 를 뺀 수"),
    "sections": Axis(re.compile(r"절\s+([\d,]+)\s*전수"),
                     "지금 세는 절 — `dms.scan()` 행 수"),
    "inherit": Axis(re.compile(r"물림\(inherit\)\s+([\d,]+)\s*절"),
                    "부모 칸을 물려받는 절 — `dms.inherit_split()` 합"),
    "blank": Axis(re.compile(r"분모\(blank\)\s+([\d,]+)\s*절"),
                  "제 칸도 부모 칸도 없는 절 — `dms.scan()` 의 `blank`"),
    "plan_open": Axis(re.compile(r"^## 1\. 남은 일 — ([\d,]+)행$", re.M),
                      "PLAN §1 표 행 수 — `plan_renumber` 가 세는 것"),
    # ★ 2026-09-25 (§258). 커버리지 래칫. 정본은 `tools/verify.sh` 의 `COV_MIN=`
    #   한 줄이고(`test_coverage_ratchet_has_one_home`), 문서가 그 수를 손으로
    #   들면 올릴 때마다 한쪽만 움직인다 — 2026-09-25 에 실제로 그랬다.
    #   ★ 앵커가 「로 걸려 있」이다. 맨 표기(`` `COV_MIN=28` ``)만 잡으면
    #     DECISIONS 의 **회고 인용**을 같이 잡고, 그러면 역사를 고치게 된다
    #     (다른 축들이 `종의 raw` · 줄머리 `## 1.` 로 앵커를 다는 것과 같다).
    "cov_min": Axis(re.compile(r"`COV_MIN=(\d+)` 로 걸려 있"),
                    "커버리지 래칫 — `tools/verify.sh` 의 `COV_MIN=` 선언"),
}

OPEN = re.compile(r"^<!--gen:\s*([\w ]+?)\s*-->$")
CLOSE = re.compile(r"^<!--/gen-->$")


# ── 실물 ────────────────────────────────────────────────────────
def _cov_min() -> int:
    """`tools/verify.sh` 의 `COV_MIN=` 한 줄. **정본은 거기다.**

    ★ 정규식을 여기서 또 쓰는 것이 R3 처럼 보이지만 아니다 —
      `tests/test_verify_citations.py` 는 「집이 하나인가」를 묻고 이 함수는
      「그 집의 값이 얼마인가」를 묻는다. 같은 줄을 다른 질문으로 읽는다.
    """
    m = re.search(r"^COV_MIN=(\d+)\s*$",
                  (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8"), re.M)
    return int(m.group(1)) if m else 0


def truth() -> dict[str, int]:
    """축마다의 **실물**. 문서를 한 줄도 안 읽는다 — PLAN §1 표만 예외다.

    ★ 대장은 `ledger.load()` 로 읽는다. yaml 로 직접 열면
      `test_lake.py::test_ledger_is_loaded_through_one_door` 래칫이 오른다
      (§246 이 이 실수를 실제로 두 번 했다). 강제자를 만드는 배치가 다른
      강제자를 깨는 것이 이 저장소가 반복한 형태다.

    ★ PLAN §1 행 수의 정본은 **그 표 자신**이다(`test_declaration_sync` 가
      「정본은 표다」라고 적는다). 세는 판별식은 `plan_renumber` 가 이미
      들고 있으므로 여기서 다시 쓰지 않는다 — 범위가 갈리면 도구와 검사가
      다른 것을 세고, 그러면 고쳐도 계속 운다(그 도구 `_span` 주석).
    """
    ds = ledger.load()["datasets"]
    rows = dms.scan()["rows"]
    said, mute = dms.inherit_split({"rows": rows})
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    return {
        "datasets": len(ds),
        "sealable": sum(1 for v in ds.values() if not (v or {}).get("on_demand")),
        "sections": len(rows),
        "inherit": len(said) + len(mute),
        "blank": sum(1 for r in rows if r["state"] == "blank"),
        # ★ 밑줄 이름을 그대로 부른다. 같은 범위를 세는 판별식이 이미 거기
        #   있고, 여기서 다시 쓰면 도구와 검사가 다른 것을 센다(R3).
        "plan_open": len(plan_renumber._rows(plan)),
        "cov_min": _cov_min(),
    }


def alive(want: dict[str, int]) -> list[str]:
    """정본이 살아 있는가. 비면 산다.

    ★ 값이 0이면 블록이 통째로 거짓이 되고, 그 거짓은 **조용하다** — 도구가
      0을 채우고 검사가 0을 통과시킨다. 그래서 여기서 죽인다.
      `tests/test_repo_numbers.py` 가 같은 함수를 부른다(정본은 하나다).
    """
    bad = []
    # ★ 2026-09-25. 축을 더하면서 이 함수가 `KeyError` 로 죽었다. **없는 축은
    #   에러가 아니라 결함이다** — 죽으면 「왜 우는가」가 안 보이고, 이 함수의
    #   일은 우는 것이다. 빠진 축을 먼저 낸다.
    if missing := [a for a in AXES if a not in want]:
        bad.append(f"축 {missing} 의 실물이 없다 — `truth()` 가 그 축을 안 센다")
    want = {a: want.get(a, 0) for a in AXES}
    if want["datasets"] <= 50:
        bad.append(f"대장 {want['datasets']}종 — 대장을 못 읽었다")
    if want["sections"] <= 500:
        bad.append(f"절 {want['sections']} — `dms.scan()` 이 죽었다")
    if want["plan_open"] <= 0:
        bad.append("PLAN §1 표 행이 0 — 표를 못 찾았다")
    if want["cov_min"] <= 0:
        bad.append("`COV_MIN` 을 못 읽었다 — `tools/verify.sh` 의 선언 한 줄이 사라졌다")
    if want["sealable"] > want["datasets"]:
        bad.append("봉인 대상이 대장보다 많다")
    if want["sealable"] >= want["datasets"]:
        bad.append("`on_demand` 소스가 0이다 — 970MB 인 `jijeok` 이 빠져 있어야 한다.\n"
                   "  정말 0이 됐으면 이 판별식을 고쳐라. 지금은 축이 낡았다는 신호다")
    return bad


def render(v: int) -> str:
    """문서에 적히는 꼴. 천 단위 쉼표는 문서 관례다(`절 1,036 전수`)."""
    return f"{v:,}"


def claims(axis: str, text: str) -> list[int]:
    """`axis` 표기가 이 문자열에서 말하는 수들. 시험과 이 도구가 같은 문을 쓴다."""
    return [int(m.replace(",", "")) for m in AXES[axis].pat.findall(text)]


# ── 블록 ────────────────────────────────────────────────────────
class Result(NamedTuple):
    """채운 본문 · 값 어긋남 · 구조 결함 · 축별 치환 건수."""

    texts: dict[str, str]
    drift: list[str]
    broken: list[str]
    seen: dict[str, int]


def _swap(pat: re.Pattern[str], line: str, want: str) -> tuple[str, int, list[str]]:
    """그 줄에서 `pat` 의 1번 그룹 자리만 `want` 로 갈아 넣는다.

    ★ **표기를 안 건드린다.** 앵커까지 새로 쓰면 이 도구가 문서의 문장을
      쓰게 되고, 그러면 사람이 쓴 산문이 배치마다 되돌려진다.
    """
    out: list[str] = []
    pos, hits, stale = 0, 0, []
    for m in pat.finditer(line):
        hits += 1
        if m.group(1) != want:
            stale.append(m.group(1))
        out.append(line[pos:m.start(1)])
        out.append(want)
        pos = m.end(1)
    out.append(line[pos:])
    return "".join(out), hits, stale


def apply_all(texts: dict[str, str], want: dict[str, int]) -> Result:
    """블록을 채운다. **순수 함수**다 — 시험이 합성 문서로 직접 부른다."""
    out: dict[str, str] = {}
    drift: list[str] = []
    broken: list[str] = []
    seen = dict.fromkeys(AXES, 0)
    for rel, text in texts.items():
        lines = text.split("\n")
        new = list(lines)
        i = 0
        while i < len(lines):
            mo = OPEN.match(lines[i])
            if mo is None:
                i += 1
                continue
            axes = mo.group(1).split()
            j = i + 1
            while j < len(lines) and CLOSE.match(lines[j]) is None:
                j += 1
            if j >= len(lines):
                broken.append(f"{rel}:{i + 1}  `<!--gen:-->` 가 안 닫혔다 "
                              "— `<!--/gen-->` 를 붙여라")
                break
            for a in axes:
                if a not in AXES:
                    broken.append(f"{rel}:{i + 1}  모르는 축 `{a}` — `AXES` 에 없다")
                    continue
                v = render(want[a])
                hits = 0
                for k in range(i + 1, j):
                    new[k], n, stale = _swap(AXES[a].pat, new[k], v)
                    hits += n
                    drift += [f"{rel}:{k + 1}  `{a}` {g} → 실물 {v}" for g in stale]
                if hits == 0:
                    broken.append(
                        f"{rel}:{i + 1}  블록이 `{a}` 표기를 0곳 찾았다 — 표기가"
                        f" 바뀌었다({AXES[a].what}).\n"
                        "    **0건은 통과가 아니다** — 블록을 지우거나 표기를 맞춰라")
                seen[a] += hits
            i = j + 1
        out[rel] = "\n".join(new)
    dead = sorted(a for a, n in seen.items() if n == 0)
    if dead:
        broken.append(
            f"이 축에 생성 블록이 **한 곳도 없다**: {dead}\n"
            "    잡힌 곳: " + " · ".join(f"{a} {n}" for a, n in sorted(seen.items())) + "\n"
            "    축을 내리거나 블록을 세워라. **0건은 통과가 아니다**(deadcheck ③)")
    return Result(out, drift, broken, seen)


def read_docs(root: Path = ROOT) -> dict[str, str]:
    return {rel: (root / rel).read_text(encoding="utf-8") for rel in DOCS}


# ── 출력 ────────────────────────────────────────────────────────
def _say(res: Result) -> None:
    for b in res.broken:
        print(f"    ✗ {b}")
    for d in res.drift:
        print(f"    ✗ {d}")


def main() -> int:
    ap = argparse.ArgumentParser(description="문서 생성 블록 ↔ 실물")
    ap.add_argument("--check", action="store_true", help="대조만 — 고치지 않는다")
    ap.add_argument("--list", action="store_true", help="축 · 실물 값 · 블록 수")
    # ★ **문서를 어디서 읽나만 바꾼다.** 실물(대장 · `dms.scan()`)은 언제나 이
    #   저장소다 — 그래서 복사한 트리에 틀린 값을 심어 「이 도구가 무는가」를
    #   물을 수 있다(`tests/test_docgen.py`). 추적 파일을 흔들지 않고 묻는
    #   길이 없으면 그 물음은 결국 안 묻게 된다.
    ap.add_argument("--root", type=Path, default=ROOT,
                    help="문서를 읽고 쓸 트리 (기본: 이 저장소)")
    a = ap.parse_args()

    want = truth()
    dead = alive(want)
    if dead:
        print("✗ 정본이 죽었다 — 블록을 채우면 거짓이 박힌다")
        for d in dead:
            print(f"    {d}")
        return 1

    res = apply_all(read_docs(a.root), want)

    if a.list:
        print(f"{'축':10} {'실물':>8}  {'블록':>4}  뜻")
        for name, ax in AXES.items():
            print(f"{name:10} {render(want[name]):>8}  {res.seen[name]:>4}  {ax.what}")
        _say(res)
        return 0

    if a.check:
        if res.broken or res.drift:
            print(f"✗ 생성 블록 {len(res.broken) + len(res.drift)}건")
            _say(res)
            print("  ★ 손으로 고치지 마라 — `uv run python tools/docgen.py` 가 채운다.")
            return 1
        print(f"✓ 생성 블록 {sum(res.seen.values())}곳이 실물과 같다 · "
              + " · ".join(f"{k} {render(v)}" for k, v in want.items()))
        return 0

    for rel, text in res.texts.items():
        p = a.root / rel
        if p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8")
            print(f"  채움 {rel}")
    if res.drift:
        print(f"✓ {len(res.drift)}곳을 실물로 채웠다")
        for d in res.drift:
            print(f"    {d}")
    else:
        print("✓ 고칠 것이 없다 — 블록이 이미 실물과 같다")
    if res.broken:
        print(f"✗ 구조 결함 {len(res.broken)}건 — 값만으로는 못 고친다")
        for b in res.broken:
            print(f"    {b}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
