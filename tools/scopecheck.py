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
두 층에 **상한**을 둔다. 래칫이다 — 지금 값에서 시작해 **내린다.** (2026-11-04 · PLAN #189 · DECISIONS §620 — `#62` 가
수집 · 판정 범위와 발행 범위를 갈라 세웠고 가드가 둘 다 잰다.)

    판정 범위 (수집 · 판정이 도는 전 구간 — `in_emd` · `route_usage` 로 잰다. 「넓어졌는가」)
      판정 범위 밖 구간 비율     개수 기준
      판정 범위 밖 연장 비율     length_m 기준
      판정 범위 무용 연장 비율   동명동 밖 + route_usage == 0 인 구간의 연장 / 전체 연장
    발행 범위 (화면이 **보여줄 것** — `scope_tier` 로 잰다. 「보여줄 것이 넓어졌는가」)
      발행 범위 안 구간 비율     `scope_tier != reference` 인 구간 / 전체
      발행 범위 안 연장 비율     같은 구간의 length_m / 전체

★ 발행 범위 쪽은 **안** 비율에 상한을 건다 — 「보여줄 것」이 커지는 것이 확산이고 상한을 넘는다는 말이 그 뜻으로 읽힌다.
  (밖 비율은 그 보수다: 구간 41.1% · 연장 45.3%. 출력에 참고로 찍는다.) 상한이 둘이어야 하는 이유는 **서로 다른 물음**이기 때문이다 —
  판정 범위는 수집 · 판정의 비용이 늘었는가이고 발행 범위는 책임 범위가 늘었는가다. 한 쪽이 올라도 다른 쪽은 그대로일 수 있다.
  `scope_tier` 가 없는 발행물(옛 판)에서는 발행 범위 축을 **건너뛴다**(판정 범위 축만 잰다).

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
# ★ 2026-11-04 (DECISIONS §618). **67.6 / 69.0 / 54.7 → 67.7 / 69.2 / 54.9 로 올린다**(사람이 친다 — 아래 CAP 의 값).
#   이유는 **넓어진 것이 아니라 종전이 좁았다**는 것이다. 접속선 배선(DECISIONS §616)이 목적지 노드를 원천의 선언대로 잡았다 —
#   직선 최근접이 `RM` 1,313 중 19% 를 **틀린 노드**에 붙이고 있었고, 그것을 고치니 회랑이 +152m · 판정 범위 구간이 +6(1,281 → 1,287)
#   늘었다. 새 실측 67.6768 / 69.1533 / 54.8908 — 위쪽 두 눈금 안(0.3%p)에 든다.
# ★ **되돌릴 조건.** 다음에 또 넘으면 **원인이 정확도인지 확산인지 먼저 가른다** — 목적지 노드의 변화(`access_targets` 가 틀린 노드를
#   고쳤는가)와 회랑의 가지 수(`route_usage` 가 새로 양수가 된 동 밖 구간이 어디서 왔는가)를 DECISIONS §616-3 의 방식으로 잰다.
#   정확도면 올리고 근거를 적는다. 확산이면 올리지 않고 `PLAN #62` 가 적었던 길(목적지 · usage 하한)로 간다.
# ★ 이 가드는 **판정 범위**(수집)와 **발행 범위**(보여줄 것)를 **둘 다** 잰다(DECISIONS §620 · 위 위쪽 설명). 아래 위쪽 셋이 판정 범위, 마지막 둘이 발행 범위다.
CAP = {
    "판정 범위 밖 구간 비율": 67.7,       # 실측 67.5254 → 67.7 (실측 67.6768 · §618)
    "판정 범위 밖 연장 비율": 69.2,       # 실측 68.8820 → 69.2 (실측 69.1533 · §618)
    "판정 범위 무용 연장 비율": 54.9,     # 실측 54.6135 → 54.9 (실측 54.8908 · §618)
    # ★ 2026-11-04 (#189 · §620). 발행 범위 축 — 실측 위 0.3%p 안에서 시작한다(58.8967 · 54.7358).
    "발행 범위 안 구간 비율": 56.7,       # 실측 56.4880 — 727/1,287 (58.9 → 56.7 · #186 으로 조였다)
    "발행 범위 안 연장 비율": 52.7,       # 실측 52.5191 (54.8 → 52.7 · #186 으로 조였다)
    # ★ 2026-11-10 (PLAN #186). 본선 번지 행을 번지 위치로 좁혔다 — 발행 범위 758 → 727(지산로 −17 · 중앙로 −14).
    #   **조인 것이지 올린 것이 아니다.** 판정은 안 움직였다.
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
    got = {
        "판정 범위 밖 구간 비율": len(out) / n * 100,
        "판정 범위 밖 연장 비율": sum(p.get("length_m") or 0.0 for p in out) / total * 100,
        "판정 범위 무용 연장 비율": sum(p.get("length_m") or 0.0 for p in idle) / total * 100,
    }
    # 발행 범위 축 — `scope_tier` 가 **모든 구간에** 있을 때만 잰다(옛 발행물이면 건너뛴다)
    if all("scope_tier" in p for p in props):
        shown = [p for p in props if p["scope_tier"] != "reference"]
        got["발행 범위 안 구간 비율"] = len(shown) / n * 100
        got["발행 범위 안 연장 비율"] = sum(p.get("length_m") or 0.0 for p in shown) / total * 100
    return got


def judge(got: dict[str, float], cap: dict[str, float] = CAP) -> list[str]:
    """상한 대조. **양방향이다.**"""
    bad = []
    for k, v in cap.items():
        if k not in got:       # 옛 발행물 — `scope_tier` 가 없어 그 축을 건너뛴다
            continue
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
        print(f"  {k:<20} {v:>5.1f}%   상한 {CAP[k]}%")
    if "발행 범위 안 구간 비율" in got:      # 참고 — 안의 보수. 상한은 없다
        print(f"  (참고) 발행 범위 밖 구간 {100 - got['발행 범위 안 구간 비율']:.1f}% · "
              f"밖 연장 {100 - got['발행 범위 안 연장 비율']:.1f}%")
    if a.show:
        return 0

    bad = judge(got)
    if not bad:
        print("스코프 벗어남이 상한 안이다.")
        return 0
    print()
    for b in bad:
        print(f"  {b}")
    print("\n  ★ 출동 대상지는 동명동 하나다. 회랑만 더하는 것이 의도였다. 넘었으면 **먼저 원인이 정확도인지")
    print("    확산인지 가른다**(DECISIONS §618) — 어느 축이 울었는가에 따라 줄이는 법이 다르다.")
    if any("판정 범위" in b for b in bad):
        print("    · 판정 범위 축 — `seg/graph.py` 의 목적지 선정(`access_targets`)과 회랑 가지(usage 하한). 판정을 움직이므로")
        print("      불변이 아니라 **대조**로 받는다(DECISIONS §558-22 · §616).")
    if any("발행 범위" in b for b in bad):
        print("    · 발행 범위 축 — 정의(DECISIONS §613)나 지정 매칭이 넓힌 것이다. 본선 번지 하나가 본선 전체를 끌어오는")
        print("      과대는 `PLAN #186` 이 든다. 판정은 안 움직인다(`scopetier.py` 는 판정 폐포 밖).")
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
