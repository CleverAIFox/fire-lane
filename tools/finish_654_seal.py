#!/usr/bin/env python3
"""
finish_654_seal.py — §654 가 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_654_seal.py            계획만
    uv run python tools/finish_654_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
  ① MASTER §23-2 에 `tools/` 파일 둘(`ortho_probe` · 이 파일 자신)을, §23-3 에 시험 `tests/test_ortho_probe.py` 를 등재한다.
  ② MASTER §7-2(아직 검증되지 않은 것)에 「정사영상 판독으로 폭을 못 읽는다」 한 줄을 더한다 — **한계 절의 몫**이다(PLAN #187 · DECISIONS §654).
     `ortho.py` 머리말이 같은 주장을 적고 있었는데 **측정 근거가 없었다** — 이 줄이 그 근거를 든다.

`sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636). 적는 주체가 사람이라는 뜻이지 적는 방법이 손이라는 뜻이 아니다 — `finish_653_seal.py` 가 선례다.
멱등이다. 앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

IN    docs/MASTER.md
OUT   같은 파일 (--apply 일 때만)
PARAM 없음
부류  생산   문서의 줄을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서)
밖    절이 옳은지는 안 본다(`sealcov` 도 안 본다). 수는 DECISIONS §654 의 실행 값이다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MASTER = Path(__file__).resolve().parent.parent / "docs" / "MASTER.md"
TOOLS_ANCHOR = "| `tools/fetch_api.py` |"
TESTS_ANCHOR = "| `tests/test_snap_groups.py` |"
LIMIT_ANCHOR = "- **일방통행 방향은 57구간 중 6 이 확정이다"
TOOL_ROWS = [
    ("tools/ortho_probe.py",
     "| `tools/ortho_probe.py` | **정사영상으로 도로 폭을 읽을 수 있는가를 재는 조사 도구**(읽기 전용 · 판정 불변 · DECISIONS §654). 지점 · 구간 중점을 구간 방향으로 돌려 오려 1m 격자를 얹은 판독용 이미지를 만들고(**구간 벡터의 가장자리는 안 그린다** — 판독이 벡터에 끌리지 않게) "
     "`--montage` 로 여럿을 한 장에 모아 가림을 분류하게 한다. `--compare` 는 사람이 눈가림으로 읽은 값과 `naver_width_2610.csv` 의 오차를 낸다(읽은 값이 없는 지점은 오차를 안 만든다). "
     "**이 대조는 판독 대 참값이 아니라 화면 측정끼리의 일치**다 — 참값은 현장 줄자뿐이다 |"),
    ("tools/finish_654_seal.py",
     "| `tools/finish_654_seal.py` | §654 가 만든 문서 빈 곳을 닫는다 — 이 도구 · 시험 하나 등재와 MASTER §7-2 의 정사영상 판독 한계 한 줄. `sealcov` 는 `--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |"),
]
TEST = ("tests/test_ortho_probe.py",
        "| `tests/test_ortho_probe.py` | 정사영상 판독 조사 도구의 순수 함수 — 세계 → 도엽 영상 좌표(북서 모서리 · 행이 아래로) · **구간 방향으로 돌려 오리는 격자**(길 방향이 가로 · 법선이 세로) · 도엽 가장자리를 건너뛰는 규칙 · "
        "오차 부호와 분포(**둘로는 분포를 말하지 않는다** — 이 조사가 실제로 만난 상황) |")
LIMIT = ("- **정사영상 판독으로 도로 폭을 읽을 수 없다 — 평가셋 55구간의 현장 측정은 줄일 길이 없다**(DECISIONS §654 · PLAN #187). `ortho.py` 가 적던 「그림자 · 처마 · 주차 차량 때문에 정확도가 안 난다」에 실측이 붙었다 — "
         "DECISIONS §569-7 이 이미 「구현하지 않았다」로 적은 결론이다. 구간 중점의 창에서 **양쪽 경계(담장 · 건물면)가 다 보인 구간이 55 중 0**(일부 7 · 지붕 · 처마 · 그늘 35 · 주차 차량 6 · 나무 6 · 개방 1)이고 "
         "`naver_width` 18지점 중 읽힌 것은 2(둘 다 넓은 길이고 정의가 어긋나 오차를 못 쟀다) · **판정 임계가 걸리는 3~7m 대역은 0건**이다. 한계: 구간 중점 한 창 · 한 사람의 눈 · 비교 기준 `naver_width` 가 현장이 아니라 화면 측정(±1.0m)이다 — "
         "그래서 **판독 대 참값이 아니라 가림의 비율**을 쟀다. 정사영상은 TIF 에 좌표가 없어 `ortho.py` 가 도엽 격자로 역산하고(정합은 juso 건물 외곽선 기준 · 도엽 이동 최대 약 1.8m · 절대 오차 미측정) 판정 폐포가 안 읽는다. 판정은 안 움직인다.\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t = MASTER.read_text(encoding="utf-8")
    new = t
    todo = [(k, r) for k, r in TOOL_ROWS if k not in new]
    print(f"① §23-2 — 등재할 줄 {len(todo)} / {len(TOOL_ROWS)}")
    if todo:
        if new.count(TOOLS_ANCHOR) != 1:
            print(f"✗ 앵커가 {new.count(TOOLS_ANCHOR)}번 — 하나여야 한다: {TOOLS_ANCHOR}", file=sys.stderr)
            return 1
        new = new.replace(TOOLS_ANCHOR, "\n".join(r for _, r in todo) + "\n" + TOOLS_ANCHOR, 1)
    if TEST[0] in new:
        print("① §23-3 이미 등재돼 있다 — 건너뛴다")
    elif new.count(TESTS_ANCHOR) != 1:
        print(f"✗ 앵커가 {new.count(TESTS_ANCHOR)}번 — 하나여야 한다: {TESTS_ANCHOR}", file=sys.stderr)
        return 1
    else:
        new = new.replace(TESTS_ANCHOR, TEST[1] + "\n" + TESTS_ANCHOR, 1)
        print("① §23-3 에 tests/test_ortho_probe.py 를 등재한다")
    if LIMIT[:40] in new:
        print("② §7-2 이미 들어가 있다 — 건너뛴다")
    elif new.count(LIMIT_ANCHOR) != 1:
        print(f"✗ 앵커가 {new.count(LIMIT_ANCHOR)}번 — 하나여야 한다: {LIMIT_ANCHOR[:40]}…", file=sys.stderr)
        return 1
    else:
        new = new.replace(LIMIT_ANCHOR, LIMIT + LIMIT_ANCHOR, 1)
        print("② §7-2 에 한계 한 줄을 더한다")
    if new != t and a.apply:
        MASTER.write_text(new, encoding="utf-8")
        print("✓ 썼다")
    elif new != t:
        print("(계획만 — --apply 로 쓴다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
