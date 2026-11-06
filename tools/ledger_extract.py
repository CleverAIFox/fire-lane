#!/usr/bin/env python3
"""
ledger_extract.py — 대장 `datasets.<키>.contract` 에 **추출 선언**(normalize_columns · filter · scope_min · scope_max)을 넣는다.

    uv run python tools/ledger_extract.py --key nfa_dispatch_119 --normalize upper_strip \\
        --filter CLMTY_CTPV_NM=광주광역시 --filter CLMTY_SGG_NM=동구 --filter CLMTY_EMD_NM=동명동 \\
        --scope-min 800 --scope-max 1200            계획만
    ... --apply                                      실행

── 왜 있나 ────────────────────────────────────────────────────
`tools/ledger_contract_nfa_ems.py` 가 이 일을 **nfa_ems 하나에 박아서** 했다. 그 도구의 필터는 단일 조건이었고(`sgg_nm=동구`) 그것이
광주 밖 다섯 광역시를 섞어 406,168행을 냈다(§647). 같은 도구를 복사하면 결함이 같이 복사된다 — 그래서 **원천 키와 조건을 인자로 받는다**.
같은 함정은 이름마다 있다(「동명동」은 광주 동구 · 속초 · 목포 셋이다 · §648) — 조건을 **여러 개 거는 것이 기본 꼴**이다.

── 하는 일 ────────────────────────────────────────────────────
대장을 **텍스트로** 고친다(`yaml.dump` 를 안 쓴다 — 주석이 근거를 드는 대장이라 라운드트립이면 그 근거가 날아간다).
 · 그 키에 `contract` 가 없으면 `kind` 줄 뒤에 블록을 끼운다.
 · 한 줄짜리 `contract: {encoding: …}` 면 블록으로 펴고 **기존 칸을 보존**한다.
 · 이미 같은 선언이면 아무것도 안 한다(멱등). **다르면 거절한다**(`--replace` 가 있어야 바꾼다) — 조용히 덮지 않는다.
 · 기존 블록에 **주석이 있으면 거절한다** — 텍스트로 다시 쓰면 주석이 날아간다. 손으로 고친다.
★ **쓰기 전에 결과를 `extract_decl.problems` 에 태운다.** 잘못된 선언(칸 이름 · 어휘 · 상한 < 하한)은 파일에 안 쓴다.

IN    sources.yaml · 인자
OUT   sources.yaml (--apply 일 때만)
PARAM --key · --normalize · --filter(반복) · --one-of(반복) · --scope-min · --scope-max · --replace · --apply
부류  생산   대장을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 대장)
밖    **필터가 실제로 몇 행을 남기는지는 안 본다** — `ingest` 가 돌 때 계보에 남고, 상한·하한은 그때 묻는다.
      `scope` · `files` · `status` 는 안 고친다(그것은 사람의 판단이다 — 전국본을 raw 에 안 두는 것 · scope 전환).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from firelane import extract_decl, ledger

ROOT = Path(__file__).resolve().parent.parent

LEDGER = ROOT / "sources.yaml"
ORDER = ("normalize_columns", "filter", "scope_min", "scope_max")


def _scalar(v) -> str:
    return yaml.safe_dump(v, allow_unicode=True, width=10**6).strip().removesuffix("\n...").strip()


def _flow(vs: list) -> str:
    return "[" + ", ".join(_scalar(v) for v in vs) + "]"


def render(con: dict) -> str:
    """contract dict → 4칸 들여쓴 블록 텍스트. 추출 키가 앞에 오고 나머지는 원래 순서로 뒤에 온다."""
    out = ["    contract:"]
    for k in [*ORDER, *[k for k in con if k not in ORDER]]:
        if k not in con:
            continue
        v = con[k]
        if k == "filter":
            conds = extract_decl.conditions(v)
            if len(conds) == 1:
                c0 = conds[0]
                out += ["      filter:", f"        column: {_scalar(c0['column'])}"]
                out.append(f"        one_of: {_flow(c0['one_of'])}" if "one_of" in c0 else f"        equals: {_scalar(c0['equals'])}")
            else:
                out.append("      filter:")
                out += [f"        - {{column: {_scalar(c['column'])}, one_of: {_flow(c['one_of'])}}}" if "one_of" in c
                        else f"        - {{column: {_scalar(c['column'])}, equals: {_scalar(c['equals'])}}}" for c in conds]
        elif isinstance(v, (list, dict)):
            out.append(f"      {k}: {yaml.safe_dump(v, default_flow_style=True, allow_unicode=True, width=10**6).strip()}")
        else:
            out.append(f"      {k}: {_scalar(v)}")
    return "\n".join(out) + "\n"


def locate(text: str, key: str) -> tuple[int, int]:
    """`datasets` 안 `  <key>:` 항목의 [시작, 끝) 줄 오프셋. 하나여야 한다."""
    heads = [m for m in re.finditer(rf"^  {re.escape(key)}:[ \t]*(#.*)?$", text, re.M)]
    if len(heads) != 1:
        raise SystemExit(f"✗ `  {key}:` 항목이 {len(heads)}개 — 하나여야 한다")
    start = heads[0].start()
    nxt = re.compile(r"^  \S[^\n]*:[ \t]*(#.*)?$", re.M).search(text, heads[0].end())
    return start, (nxt.start() if nxt else len(text))


def find_contract(body: str) -> tuple[int, int, dict] | None:
    """항목 본문에서 `    contract:` 의 [시작, 끝)과 파싱 결과. 없으면 None. 주석이 있으면 거절한다."""
    m = re.search(r"^    contract:(.*)$", body, re.M)
    if not m:
        return None
    end = m.end() + 1
    if m.group(1).strip():                               # 한 줄 `contract: {…}`
        if "#" in m.group(1):
            raise SystemExit("✗ 기존 `contract:` 줄에 주석이 있다 — 텍스트로 다시 쓰면 날아간다. 손으로 고쳐라")
        return m.start(), end, ledger.parse(m.group(1))
    lines = body[end:].splitlines(keepends=True)
    n = 0
    while n < len(lines) and (lines[n].startswith("      ") or not lines[n].strip()):
        n += 1
    while n and not lines[n - 1].strip():                # 꼬리 빈 줄은 블록이 아니다
        n -= 1
    blk = "".join(lines[:n])
    if "#" in blk:
        raise SystemExit("✗ 기존 `contract:` 블록에 주석이 있다 — 텍스트로 다시 쓰면 날아간다. 손으로 고쳐라")
    return m.start(), end + len(blk), ledger.parse("contract:\n" + blk).get("contract") or {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", required=True, help="대장 datasets 의 키")
    ap.add_argument("--normalize", choices=sorted(extract_decl.NORMALIZERS), help="칸 이름 정규화 — 출력 칸 이름이 하류의 이름과 같은 쪽을 고른다")
    ap.add_argument("--filter", action="append", default=[], metavar="COL=VAL", help="반복한다(모두 맞는 행 = AND). 칸 이름은 정규화 **뒤** 꼴")
    ap.add_argument("--one-of", action="append", default=[], metavar="COL=A|B",
                    help="한 칸이 이름이 바뀐 값 여럿을 갖는 경우(예: 광주광역시|전남광주통합특별시). 반복한다 · 다른 조건과 AND · 값은 둘 이상")
    ap.add_argument("--scope-min", type=int)
    ap.add_argument("--scope-max", type=int)
    ap.add_argument("--replace", action="store_true", help="이미 다른 추출 선언이 있어도 바꾼다")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not a.filter and not a.one_of:
        print("✗ --filter 가 하나도 없다 — 추출은 거르는 일이다", file=sys.stderr)
        return 2
    conds = []
    for f in a.filter:
        col, sep, val = f.partition("=")
        if not sep or not col.strip() or not val.strip():
            print(f"✗ --filter `{f}` — COL=VAL 꼴이어야 하고 둘 다 비면 안 된다", file=sys.stderr)
            return 2
        conds.append({"column": col.strip(), "equals": val})
    for f in a.one_of:
        col, sep, val = f.partition("=")
        vs = [v for v in val.split("|")]
        if not sep or not col.strip() or len(vs) < 2 or any(not v.strip() for v in vs):
            print(f"✗ --one-of `{f}` — COL=A|B 꼴이어야 하고 값이 둘 이상이며 비면 안 된다", file=sys.stderr)
            return 2
        conds.append({"column": col.strip(), "one_of": vs})
    want = {"filter": conds if len(conds) > 1 else conds[0]}
    for k, v in (("normalize_columns", a.normalize), ("scope_min", a.scope_min), ("scope_max", a.scope_max)):
        if v is not None:
            want[k] = v

    text = LEDGER.read_text(encoding="utf-8")
    s0, s1 = locate(text, a.key)
    body = text[s0:s1]
    cur = find_contract(body)
    old = cur[2] if cur else {}
    mine = {k: old[k] for k in ORDER if k in old}
    if cur and mine == want:
        print("이미 같은 추출 선언이 있다 — 아무것도 안 한다 (멱등)")
        return 0
    if mine and not a.replace:
        print(f"✗ 다른 추출 선언이 이미 있다 — 조용히 덮지 않는다. 바꾸려면 --replace\n   지금 {mine}\n   요청 {want}", file=sys.stderr)
        return 1
    merged = {**{k: v for k, v in old.items() if k not in ORDER}, **want}
    block = render(merged)
    if cur:
        new_body = body[: cur[0]] + block + body[cur[1]:]
    else:
        m = re.search(r"^    kind: .*\n", body, re.M)
        if not m:
            print("✗ 이 항목에 `kind:` 줄이 없다 — 블록을 끼울 자리를 추측하지 않는다", file=sys.stderr)
            return 1
        new_body = body[: m.end()] + block + body[m.end():]
    new = text[:s0] + new_body + text[s1:]

    entry = ledger.parse(new)["datasets"][a.key]
    bad = extract_decl.problems(a.key, entry)
    print(f"대장   {LEDGER}\n키     {a.key}\n")
    print(block.rstrip())
    if bad:
        print("\n✗ 이 선언은 검사를 못 지난다 — 쓰지 않는다:", file=sys.stderr)
        for b in bad:
            print(f"   · {b}", file=sys.stderr)
        return 1
    if not a.apply:
        print("\n계획만 했다. 쓰려면 --apply")
        return 0
    LEDGER.write_text(new, encoding="utf-8")
    print("\n✓ 썼다. 다음으로 검증한다 —")
    print("    uv run python -m firelane.ledger_check")
    print("    uv run python -m firelane.contract --declared")
    print(f"    uv run python -m firelane.ingest --only {a.key} --extract-from <입력 폴더>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
