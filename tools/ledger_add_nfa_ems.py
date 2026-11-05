#!/usr/bin/env python3
"""
ledger_add_nfa_ems.py — sources.yaml 에 datasets.nfa_ems 를 등재한다.

    uv run python ledger_add_nfa_ems.py            계획만 (아무것도 안 쓴다)
    uv run python ledger_add_nfa_ems.py --apply    실행

── 왜 손으로 안 고치나 ────────────────────────────────────────
대장은 주석이 근거를 든다. `yaml.dump()` 로 다시 뽑으면 그 근거가 통째로
날아간다(tools/docnum_check.py:528 · tools/depgroups_check.py:85 가 같은 이유로
라운드트립 쓰기를 포기했다). 그래서 **원문 줄을 보존하는 텍스트 삽입**만 한다.

── 멱등 ───────────────────────────────────────────────────────
`  nfa_ems:` 가 이미 있으면 아무것도 안 한다. 두 번 돌려도 결과가 같다.
삽입 자리는 `  nfa_fire_incident:` 바로 앞이다 — 앵커를 못 찾으면 **실패한다.**
자리를 추측해서 아무 데나 넣지 않는다.

IN    sources.yaml
OUT   sources.yaml (--apply 일 때만)
PARAM 없음
부류  생산   대장을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 대장)
밖    레이크를 안 본다 — 파일이 실제로 있는지는 `acquire.py` 의 세 판정이 묻는다.
      대장 문법·스키마도 안 본다 — `ledger_schema` · `ledger_fields` · `ledger_stem` 의 일이다.
      이 도구는 **블록 하나를 정해진 자리에 끼워 넣는 것**만 한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "sources.yaml"
KEY = "  nfa_ems:\n"
ANCHOR = "  nfa_fire_incident:\n"

BLOCK = '''  nfa_ems:
    feeds: []
    feeds_why: |
      ★ 미투입이다. 2026-11-05 반입. 쓸 곳은 cost 의 거리-시간 관계 검증과
        발표 논거이고, **구간에는 못 붙는다** — 행정구역이 sgg_nm(시군구)까지이고
        좌표 칸이 71칸 전수에 없다(활용가이드 column_info 전수 확인 · DECISIONS §645).
      ★ 쓰는 칸 — grnds_dstnc(센터→현장 거리 · 단위 km) ·
        dclr_tm · dspt_tm · grnds_arvl_tm · ptn_cntc_tm · grnds_dptre_tm · cbk_tm.
        ptn_cntc_tm − grnds_arvl_tm 이 「차에서 내려 환자까지 간 시간」이다.
    stem: nfa_ems
    ext: [csv]
    scope: kr
    authority: 소방청 소방안전 빅데이터 플랫폼
    updated: '2026-11-05'   # ★ 내려받은 날. 플랫폼이 데이터 기준일을 표기하지 않는다
    files:
      - nfa/nfa_ems_kr_2019.csv
      - nfa/nfa_ems_kr_2020.csv
      - nfa/nfa_ems_kr_2021.csv
      - nfa/nfa_ems_kr_2022.csv
      - nfa/nfa_ems_kr_2023.csv
      - nfa/nfa_ems_kr_2024.csv
      - nfa/nfa_ems_kr_2025.csv
    origin_name: 구급 현황_<연도>_전국.csv
    what: |
      전국 구급 현황 2019~2025 · 7파일 8.4GB. 광주 동구 47,632행.
      연도별 동구 3,391 · 6,226 · 7,089 · 8,164 · 7,969 · 7,616 · 7,177.
    kind: csv_table
    encoding: utf-8
    coords:
      none: 「좌표 칸이 없다 — 거리를 칸으로 든다(grnds_dstnc)」
    note: |
      ★ **단위가 km 다.** 활용가이드는 「출동한 기관, 센터, 관서등과 목적한 곳의 거리」
        라고만 적고 단위를 안 준다 — 분포로 확정했다(중앙 1.0 · 99분위 7.3 · 최대 400).
        원천 문서가 단위를 빠뜨린 자리이므로 **실측 교차로만 근거가 된다**(§642-6 과 같은 꼴).
      ★★ **grnds_dstnc 의 0 은 거리가 아니라 결측이다.** 2019~2023 은 40~53% 가 0 이고
        2024~2025 는 0% 다. 0km 사건의 주행 중앙 237초가 0<d<1km 의 223초보다 **길다** —
        진짜 0 이면 가장 짧아야 한다. 거리 분석은 2024~2025 전용이다(DECISIONS §645-1).
      ★★ **칸 이름 케이스가 2024 에서 갈린다** — 2019~2023 대문자 71/71 · 2024~2025 소문자 0/71.
        읽을 때 strip().strip('"').lower() 로 정규화해야 한다. 이 함정을 안 밟아서
        nfa_fire_incident 파생본이 139행을 잃었다(DECISIONS §644-3).
      ★ 동구 필터는 sgg_nm == '동구' 다(환자 발생지 · 전수 47,632행이 동구).
        센터는 구를 넘나든다 — 동부 38,879 · 북부 4,649 · 남부 3,896 ·
        서부 93 · 광산 48 · 항공구조대 21.
      ★ 2023~2025 는 플랫폼이 제공한다. 구조 현황(nfa_rescue)은 2019~2022 뿐이다.
    verified: false
'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다")
    a = ap.parse_args()

    if not LEDGER.is_file():
        print(f"✗ 대장이 없다: {LEDGER}", file=sys.stderr)
        return 2

    text = LEDGER.read_text(encoding="utf-8")

    if KEY in text:
        print("이미 등재돼 있다 — 아무것도 안 한다 (멱등)")
        return 0

    if ANCHOR not in text:
        print(f"✗ 앵커를 못 찾았다: {ANCHOR!r}", file=sys.stderr)
        print("  자리를 추측해서 넣지 않는다. 대장 구조가 바뀌었으면 이 도구를 고쳐라.",
              file=sys.stderr)
        return 1

    if text.count(ANCHOR) != 1:
        print(f"✗ 앵커가 {text.count(ANCHOR)}번 나온다 — 하나여야 한다", file=sys.stderr)
        return 1

    at = text.index(ANCHOR)
    line_no = text[:at].count("\n") + 1
    new = text[:at] + BLOCK + text[at:]

    print(f"대장   {LEDGER}")
    print(f"앵커   {ANCHOR.strip()}  ({line_no}행)")
    print(f"삽입   {BLOCK.count(chr(10))}줄 · datasets.nfa_ems")
    print(f"결과   {text.count(chr(10))}줄 → {new.count(chr(10))}줄")

    if not a.apply:
        print()
        print("계획만 했다. 쓰려면 --apply")
        return 0

    LEDGER.write_text(new, encoding="utf-8")
    print()
    print("✓ 썼다. 다음을 돌려 검증한다 —")
    print("    uv run python tools/ledger_schema.py")
    print("    uv run python tools/ledger_fields.py")
    print("    uv run python tools/ledger_stem.py")
    print("    uv run python tools/doc_fsck.py")
    print("    uv run python tools/acquire.py          # 세 판정")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
