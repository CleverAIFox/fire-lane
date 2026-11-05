#!/usr/bin/env python3
"""
valueprofile.py — 표 자료의 **값의 성질**을 재서 대장 `schema.profile` 에 적는다.  (DECISIONS §631-4 · §634 · PLAN #193)

    uv run python -m firelane.valueprofile            계획만(재서 보여 준다)
    uv run python -m firelane.valueprofile --apply    대장 `schema.profile` 에 기록
    uv run python -m firelane.valueprofile --check    커밋된 프로필이 실물과 같은가 + 실물 방언이 `none:` 선언 안인가
    uv run python -m firelane.valueprofile --only nfa_dispatch_119

── 무엇을 적나 ────────────────────────────────────────────────
칸마다 **집계**만 적는다 — `empty`(빈 셀) · `ws`(공백 문자열) · `sentinel`(좌표 칸의 `0` · `0.0`) · `text_none`(`미상` · `없음` …) · `range`(좌표 칸의
최소 · 최대). **표본값은 한 줄도 안 적는다**(`ledger_schema` 의 「값은 안 읽는다」는 규칙이 지키려던 것 — 개인정보 — 을 집계는 해치지 않는다).
기본은 「없음 꼴이 있는 칸」과 좌표 칸뿐이라 대장이 안 부푼다. `none:` 이 `by: <칸>` 을 선언한 칸은 그 칸의 값(연도 · 판)별로 한 번 더 쪼갠다 —
연도로 갈리는 방언(2022 · 2023 은 빈 셀 / 2024 · 2025 는 공백)은 이 쪼갬에서만 보인다.

★ 왜 필요한가 — 대장이 이름만 적어서 `notna()` 가 공백 문자열을 「있음」으로 세고(구급 가르기 · `#39` 측정 572쌍 무효) 신고자 휴대폰 위치를 재해 위치로 쓴
  사고가 하루에 났다. 이 프로필은 **사실**(AUTO)이고 `none:` · `coords:` 는 **규범**(사람)이다 — 사실이 규범보다 넓으면 `ledger.profile_problems` 가 운다.

IN    $FIRE_LANE_DATA/raw · sources.yaml
OUT   sources.yaml (datasets[*].schema.profile)
밖    **`json_table` · zip 안의 표는 안 잰다**(csv 표만). **「없음」 방언이 의미 차이인지**(`미상` 과 빈 셀이 같은 뜻인가)는 사람이 정한다.
"""
from __future__ import annotations

import argparse
import re
import sys

import pandas as pd

from firelane import ledger as led
from firelane import paths

KINDS = ("csv_table", "csv_table_multi")
SENTINELS = ("0", "0.0")
TEXT_NONE = ("미상", "없음", "해당없음", "N/A", "NULL", "null")


def measure(df: pd.DataFrame, none: dict | None = None, xy: set[str] = frozenset()) -> dict:
    """모든 칸이 문자열인 표 → `{n, cols}`. 「없음 꼴」이 있는 칸과 좌표 칸만 든다."""
    none, cols = none or {}, {}
    for c in df.columns:
        s = df[c].astype(str)
        st = s.str.strip()
        coordish = c in xy or bool(led.COORD_COL.search(str(c)))
        sent = {f: int((st == f).sum()) for f in SENTINELS} if coordish else {}
        tn = {f: int((st == f).sum()) for f in TEXT_NONE}
        d = {"empty": int((s == "").sum()), "ws": int(((s != "") & (st == "")).sum()),
             "sentinel": {k: v for k, v in sent.items() if v}, "text_none": {k: v for k, v in tn.items() if v}}
        if not (d["empty"] or d["ws"] or d["sentinel"] or d["text_none"] or coordish):
            continue
        if coordish:
            num = pd.to_numeric(st[(st != "") & ~st.isin(SENTINELS)], errors="coerce").dropna()
            if len(num):
                d["range"] = [round(float(num.min()), 6), round(float(num.max()), 6)]
        if (by := (none.get(c) or {}).get("by")) and by in df.columns:
            b = {}
            for v, g in df.groupby(by):
                gs = g[c].astype(str)
                one = {"empty": int((gs == "").sum()), "ws": int(((gs != "") & (gs.str.strip() == "")).sum())}
                if any(one.values()):
                    b[str(v)] = {k: n for k, n in one.items() if n}
            d["by"] = b
        cols[str(c)] = {k: v for k, v in d.items() if v or k in ("empty", "ws")}
    return {"n": int(len(df)), "cols": cols}


def read(e: dict) -> pd.DataFrame:
    """대장 항목의 표를 **한 글자도 안 고치고** 읽는다(`na_filter=False` — 빈 셀도 공백도 그대로)."""
    ps = led.paths_of(e, paths.DATA / "raw")
    if not ps:
        raise FileNotFoundError("실물 없음")
    return pd.concat([pd.read_csv(p, dtype=str, na_filter=False, low_memory=False, sep=led.delimiter_of(e),
                                  encoding=e.get("encoding") or "utf-8") for p in ps], ignore_index=True)


def _v(x) -> str:
    if isinstance(x, dict):
        return "{" + ", ".join(f"'{k}': {_v(v)}" if not isinstance(v, dict) or v else f"'{k}': {{}}" for k, v in x.items()) + "}"
    return "[" + ", ".join(map(str, x)) + "]" if isinstance(x, list) else str(x)


def fmt(pf: dict) -> str:
    """`schema:` 블록 안에 붙는 `profile:` 줄들(들여쓰기 6). **손으로 고치지 말라는 표시**를 단다."""
    out = ["      profile:                    # AUTO — firelane.valueprofile 이 쓴다(집계만 · 표본값 없음)", f"        n: {pf['n']}", "        cols:" if pf["cols"] else "        cols: {}"]
    out += [f"          '{c}': {_v(d)}" for c, d in pf["cols"].items()]
    return "\n".join(out) + "\n"


def splice(s: str, key: str, pf: dict) -> str:
    """원문 `s` 의 `key` 항목 `schema:` 끝에 프로필을 붙인다(있으면 갈아 끼운다). 주석 · 다른 칸은 그대로다."""
    st, en, body = led.yaml_span(s, key)
    m = re.search(r"^    schema:.*\n(?:      .*\n|\n)*", body, re.M)
    if st < 0 or not m:
        raise KeyError(f"{key}: schema 블록이 없다")
    blk = re.sub(r"^      profile:.*\n(?:        .*\n)*", "", m.group(0), flags=re.M).rstrip("\n") + "\n"
    return s[:st] + body[:m.start()] + blk + fmt(pf) + body[m.end():] + s[en:]


def run(*, apply: bool, check: bool, only: str | None = None) -> int:
    s = led.raw_text()
    ds = led.load_sources().get("datasets") or {}
    bad = 0
    for key, e in ds.items():
        if e.get("kind") not in KINDS or (only and key != only):
            continue
        try:
            xy = {str(d[a]) for d in (led.coords_decl(e) or {}).values() if isinstance(d, dict) for a in ("x", "y") if a in d}
            pf = measure(read(e), e.get("none"), xy)
        except Exception as ex:                       # 실물이 없는 기계(CI)는 건너뜀이지 초록이 아니다 — 센다
            print(f"  ! {key:24} 못 쟀다 — {type(ex).__name__}: {ex}")
            bad += 1
            continue
        print(f"  {key:24} n={pf['n']:6} 칸 {len(pf['cols'])}개")
        if check:
            old = (e.get("schema") or {}).get("profile")
            if old != pf:
                print("      ★ 커밋된 프로필이 실물과 다르다 — `--apply` 로 다시 적고 diff 를 읽는다")
                bad += 1
            for m in led.profile_problems({**e, "schema": {**(e.get("schema") or {}), "profile": pf}}):
                print(f"      ★ {m}")
                bad += 1
        elif apply:
            s = splice(s, key, pf)
    if apply:
        led.parse(s)
        (paths.ROOT / "sources.yaml").write_text(s, encoding="utf-8")
        print("\n적용 · YAML 파싱 OK")
    elif not check:
        print("\n아무것도 바꾸지 않았다.  --apply 로 기록한다.")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="표 자료의 값의 성질 프로필")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args(argv)
    return run(apply=a.apply, check=a.check, only=a.only)


if __name__ == "__main__":
    sys.exit(main())
