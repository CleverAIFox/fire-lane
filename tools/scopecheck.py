#!/usr/bin/env python3
"""
scopecheck.py — 발행된 판정 스코프가 **출동 대상지에서 얼마나 벗어났는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §1 #62). 출동 대상지는 **동명동 하나**(0.429km²)다. 안전센터가
동 밖이라 「접근 회랑」만 불가피하게 더하는 것이 원래 의도였다. 실물은 그렇지
않았고, 그 사실을 **세는 검사가 저장소에 하나도 없었다.**

기존 `tests/test_station_scope.py` 는 「스코프가 안전센터를 덮는가」만 본다 —
**넓을수록 통과한다.** 방향이 반대인 검사만 있었다.

★ 2026-09-20 실측. `web/data/segments.geojson` 의 속성만으로 난다.

    구간 1,281 · 동명동 밖 865 (67.5%) · 연장 58,309m 중 40,164m 밖 (68.9%)

★ **더 나쁜 것은 그 다음이다.** `route_usage` 는 「안전센터 2곳 → 건물 출입구
  최단경로 사용횟수」다(`seg/report.py`). 동명동 밖 865 중 **646개(31,844m)가
  0** 이다 — 어떤 출동 경로도 안 쓴다. 즉 **총연장의 54.6% 가 동명동도 아니고
  회랑도 아니다.** #62 는 회랑이 「최단경로 나무」라고 적었는데, 이 부분은
  나무조차 아니다.

  비교 — 동명동 **안**에서 usage 0 은 416 중 55(3,365m)뿐이다. 안과 밖의
  성질이 다르다는 뜻이고, 사상 오류로는 설명이 안 된다.

── 무엇을 보는가 ───────────────────────────────────────────────
세 값에 **상한**을 둔다. 래칫이다 — 지금 값에서 시작해 **내린다.**

    밖 구간 비율      개수 기준
    밖 연장 비율      length_m 기준
    무용 연장 비율    동명동 밖 + route_usage == 0 인 구간의 연장 / 전체 연장

★ 양방향이다. 실측이 상한보다 **낮아도** 운다 — 좋아졌는데 상한을 안 내리면
  되돌아갈 자리가 남고, 느슨한 래칫은 초록으로 위장한다(DECISIONS §199-1).

★ **이 검사는 판정을 옳다고 말하지 않는다.** 「벗어남이 늘지 않았다」만 말한다.
  줄이는 일은 `seg/graph.py` 의 목적지 선정을 고치는 것이고 그것은 판정을
  움직이므로 수용 조건이 다르다(PLAN §1 #62 · §13-5 규칙 2).

IN    web/data/segments.geojson  (커밋된 발행물. 레이크도 geopandas 도 안 쓴다)
OUT   없음 (검사). 상한 초과 또는 미달이면 종료코드 1
PARAM --show      수치만 찍고 통과
      --selftest  자체시험만
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEGMENTS = ROOT / "web" / "data" / "segments.geojson"

# ── 래칫 ──────────────────────────────────────────────────────
# ★ 2026-09-20 실측값 그대로다. **목표가 아니라 지금이다.** 목표를 크게 잡으면
#   못 지키고, 못 지키는 문턱은 끄게 된다(DECISIONS §199-1 과 같은 자리).
# ★ 숫자는 여기 한 곳에만 산다. 단계 이름에도 문서에도 복사하지 않는다.
CAP = {
    "밖 구간 비율": 67.6,       # 실측 67.5254
    "밖 연장 비율": 69.0,       # 실측 68.8820
    "무용 연장 비율": 54.7,     # 실측 54.6135
}
# 실측과 상한 사이에 둔 여유. 부동소수 반올림으로 빨개지지 않게 한다.
# ★ 이 여유가 **래칫의 최소 눈금**이다. 0.3%p 넘게 좋아지면 조이라고 운다.
#   0.1 로 두면 지금 값(상한 -0.12)에서 이미 울어 래칫이 자기 출발점을
#   거부한다 — 세우는 순간 빨간 검사는 세워지지 않는다.
SLACK = 0.3


def measure(path: Path = SEGMENTS) -> dict[str, float]:
    """발행물에서 세 비율을 낸다. 속성만 읽는다 — 지오메트리 계산이 없다."""
    with open(path, encoding="utf-8") as f:
        feats = json.load(f)["features"]
    props = [x["properties"] for x in feats]
    if not props:
        raise SystemExit("✗ segments.geojson 이 비었다 — 발행이 안 됐다")

    n = len(props)
    total = sum(p.get("length_m") or 0.0 for p in props)
    if total <= 0:
        raise SystemExit("✗ length_m 합이 0 이다 — 속성이 안 실렸다")

    out = [p for p in props if not p.get("in_emd")]
    idle = [p for p in out if not (p.get("route_usage") or 0)]
    return {
        "밖 구간 비율": len(out) / n * 100,
        "밖 연장 비율": sum(p.get("length_m") or 0.0 for p in out) / total * 100,
        "무용 연장 비율": sum(p.get("length_m") or 0.0 for p in idle) / total * 100,
    }


def judge(got: dict[str, float], cap: dict[str, float] = CAP) -> list[str]:
    """상한 대조. **양방향이다.**"""
    bad = []
    for k, v in cap.items():
        x = got[k]
        if x > v:
            bad.append(f"✗ {k}  {x:.1f}% > 상한 {v}% — 스코프가 넓어졌다.")
        elif x < v - SLACK:
            bad.append(
                f"✗ {k}  {x:.1f}% 가 상한 {v}% 보다 {v - x:.1f}%p 낮다 — "
                f"CAP 을 {x + SLACK:.1f} 로 조여라. 안 조이면 되돌아간다.")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    if not SEGMENTS.is_file():
        print(f"✗ {SEGMENTS.relative_to(ROOT)} 가 없다 — 발행을 먼저 돌려라.")
        return 1
    got = measure()
    for k, v in got.items():
        print(f"  {k:<14} {v:>5.1f}%   상한 {CAP[k]}%")
    if a.show:
        return 0

    bad = judge(got)
    if not bad:
        print("스코프 벗어남이 상한 안이다.")
        return 0
    print()
    for b in bad:
        print(f"  {b}")
    print("\n  ★ 출동 대상지는 동명동 하나다. 회랑만 더하는 것이 의도였다.")
    print("    줄이는 법은 PLAN §1 #62 — `seg/graph.py` 의 목적지를 출입구")
    print("    전수가 아니라 동 경계 진입점으로 바꾸거나 usage 하한을 둔다.")
    print("    그 변경은 **판정을 움직인다** — 불변이 아니라 대조로 받는다.")
    return 1


def selftest() -> int:
    """긍정·부정 대조. 되돌림(느슨해짐)을 특히 본다."""
    bad = []
    cap = {"a": 50.0}
    if judge({"a": 50.0}, cap):
        bad.append("상한과 같은데 울었다")
    if not judge({"a": 50.1}, cap):
        bad.append("상한을 넘었는데 안 울었다")
    if judge({"a": 49.95}, cap):
        bad.append("여유 안쪽인데 울었다")
    if not judge({"a": 49.0}, cap):
        bad.append("상한보다 크게 낮은데 안 울었다 — 느슨한 래칫을 놓쳤다")
    # ★ 실물이 읽히는가. 속성 이름이 바뀌면 여기서 걸린다.
    try:
        got = measure()
        if set(got) != set(CAP):
            bad.append(f"측정 키가 상한 키와 다르다 — {sorted(got)} vs {sorted(CAP)}")
    except (OSError, KeyError, SystemExit) as e:
        bad.append(f"실물을 못 읽었다 — {e}")
    for b in bad:
        print(f"  ✗ {b}")
    print("selftest 통과 — 대조 다섯" if not bad else f"\nselftest 실패 {len(bad)}건")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
