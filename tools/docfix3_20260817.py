#!/usr/bin/env python3
"""
docfix3_20260817.py — 베이스라인 봉인을 MASTER · sources.yaml 에 등재한다.

    uv run python tools/docfix3_20260817.py --check
    uv run python tools/docfix3_20260817.py

★ 이 저장소는 2026-08-15 데이터 관리 체계 개편으로 MASTER §18 과
  sources.yaml 이 크게 바뀌었다. 그래서 파일을 통째로 덮어쓰지 않고
  앵커 문자열을 assert 로 확인한 뒤 삽입만 한다.
  앵커가 없으면 아무것도 쓰지 않고 멈춘다. 그때는 손으로 넣어라.

이미 들어가 있으면 건너뛴다(재실행 안전).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MASTER_ANCHOR = "## 18-9. DB 확장"
MASTER_MARK = "## 18-8-1. 베이스라인 봉인"
MASTER_BLOCK = """## 18-8-1. 베이스라인 봉인 — `processed` 의 예외

`processed` 를 보관하지 않는 규칙(§18-1)은 **raw 가 살아 있을 때만** 참이다.
raw + 코드 + 대장으로 결정론적 재생성이 되기 때문이다. 원본이 사라지면
그 산출물은 재생성 불가가 되고 `field`(실측 원자료)와 같은 등급이 된다.

2026-08-15 원본 전량 재취득으로 수치지형도가 교체됐다.

```
전   국토정보플랫폼  NGI 텍스트  2020·2022 혼합  20도엽
후   V-WORLD         SHP         2026-03-07      74도엽
```

구 원본이 없으므로 1102/386/210/62/444 는 다시 만들 수 없다. 봉인했다.

```
data/baseline/20260814-ngii-ngi20/
  segments.geojson  segments.schema.json  _manifest.json
  seg_uid_map.csv   nfa_compare.json      meta.json  README.md
```

```bash
uv run python tools/baseline.py freeze <태그> --note "..."
uv run python tools/baseline.py diff <태그>      # 새 실행과 대조
```

`diff` 는 `seg_uid` 로 먼저 맞추고 안 맞는 것은 중점 최근접(15m)으로 맞춘다.
`seg_uid` 는 중점 좌표 + 도로명 해시라 소스가 바뀌면 흔들린다.
특히 V-WORLD 는 `A0020000` 도로명이 채워져 있는데 구 NGII 는 전부
빈 문자열이었다. 도로명 해시가 갈릴 수 있어 공간 매칭이 폴백으로 필요하다.

### ★ 소방서 대조는 파일로 남지 않는다

`segments.py:962` 가 `print` 만 한다. **우리 폭에 대한 유일한 외부 대조인데
터미널 출력으로만 존재했다.** 7.24m 는 문서 §4 에서 옮겨 적어
`nfa_compare.json` 으로 봉인했다. 파서 교체 시 파일 출력을 붙일 것.

봉인은 언제 하나 — **원본을 교체하기 전에** 한다. 파이프라인을 한 번이라도
돌리면 덮어써진다.

---

## 18-9. DB 확장"""

YAML_ANCHOR = "  ngii1k_center:\n"
YAML_MARK = "  baseline_20260814:"
YAML_BLOCK = """  baseline_20260814:
    produced_by: tools/baseline.py
    path: data/baseline/20260814-ngii-ngi20/
    inputs: [ngii1k, ngii_road, road_rw, road_link]
    consumers: [tools/baseline.py]
    what: |
      국토정보플랫폼 NGI 20도엽(2020·2022) 기준 마지막 판정 산출물.
      1102 / clear 386 · needs_cv 210 · blocked 62 · unknown 444
    verified: false
    regenerable: false
    known_issues:
      - 구 원본이 2026-08-15 재취득으로 소실. 재생성 불가다
      - width_verified 전건 false
      - nfa_compare.json 은 검증이 아니라 적합(fit). MASTER 4절
      - ngii1k 는 ingest 에서 FAIL 이었고 gpkg 는 손으로 만든 것이다

"""


def run(rel: str, anchor: str, mark: str, block: str, check: bool) -> int:
    p = ROOT / rel
    if not p.exists():
        print(f"! 없다: {rel}")
        return 1
    t = p.read_text(encoding="utf-8")
    if mark in t:
        print(f"  {rel} 이미 있음 — 건너뜀")
        return 0
    n = t.count(anchor)
    if n != 1:
        print(f"! {rel} 앵커 {n}회: {anchor.strip()[:40]}")
        return 1
    if not check:
        p.write_text(t.replace(anchor, block, 1), encoding="utf-8")
        print(f"  {rel} 등재")
    return 0


def main() -> int:
    check = "--check" in sys.argv
    bad = run("docs/MASTER.md", MASTER_ANCHOR, MASTER_MARK, MASTER_BLOCK, check)
    bad += run("sources.yaml", YAML_ANCHOR, YAML_MARK,
               YAML_BLOCK + YAML_ANCHOR, check)
    if bad:
        print(f"\n★ {bad}건 실패. 해당 파일은 쓰지 않았다. 손으로 넣어라.")
        return 1
    print("\n완료." if not check else "\n앵커 확인됨.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
