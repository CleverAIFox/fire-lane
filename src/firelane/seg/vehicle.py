#!/usr/bin/env python3
"""
firelane/seg/vehicle.py — 소방차 제원과 통행 비용

════════════════════════════════════════════════════════════════
★ 이 모듈은 **순수 함수만** 담는다. 파일도 경로도 모른다.
  `seg/graph.py` 가 인프라를 모르게 만든 것과 같은 이유다(2026-08-21).

── 왜 만들었나 ─────────────────────────────────────────────────
경로 탐색은 이미 있다 — `graph.access_corridor()` 가 119안전센터 2곳에서
건물 출입구까지 Dijkstra 를 돌리고 `route_usage` 를 낸다(579구간).

**없는 것은 비용 함수다.** 지금은 `weight="length"` 라 거리만 본다.
통행 불가 구간도 최단이면 지나간다. 그러면 "소방차가 갈 수 있는 길" 이
아니라 "제일 짧은 선" 이다.

── 두 가지를 넣는다 ────────────────────────────────────────────
**① 폭.** 차폭보다 좁으면 못 간다. 여유가 없으면 느리다.
**② 내륜차.** 회전할 때 뒷바퀴가 앞바퀴보다 안쪽으로 돈다.
   그만큼 폭이 더 필요하다.

       내륜차 Δ = R − √(R² − L²)     L = 축거 · R = 회전반경

   L=4.0m · R=8.0m 이면 1.072m 다. 직선에서 3.0m 로 통과하던 길이
   급커브에서는 4.07m 를 요구한다.

   ★ 1차 근사 `L²/(2R)` 를 쓰지 않는다. 같은 조건에서 1.000 이 나와
     7cm 가 어긋나고, 그것이 3.0m 임계 근처에서 판정을 가른다.

── 제원 출처 ───────────────────────────────────────────────────
소방청 「소방장비 기본규격」 소방펌프차 **KFS-1-0073-2025-00 §3.3**
(2025-12-24 고시). 원문 표기는 "or less"(이하)다.

    구분   전장(m)    전폭(m)    전고(m)
    대형   8.5 이하   2.5 이하   3.4 이하
    중형   8.0 이하   2.5 이하   3.2 이하      ← 현재 기준
    소형   6.8 이하   2.2 이하   2.8 이하
    경형   5.2 이하   1.9 이하   2.8 이하

★ **규격은 상한만 정한다.** 실제 차폭은 그보다 작을 수 있고, 그 경우
  판정이 안전한 쪽으로 틀린다. 그래서 상한을 그대로 쓴다.

★ **축거와 최소회전반경은 공식 규격에 없다.** KFS-1-0073 ·
  KFS-1-0030(소형사다리차) · 2025년 MAS 차종별 제작규격 셋을 전수
  확인했으나 규정하지 않는다. 내륜차 계산에 그 둘이 필요하므로 지금 값은
  **추정**이고 `wheelbase_verified: false` 가 그 표시다.

★ **차종이 결과를 크게 바꾼다.** 폭 3m 골목에 중형(2.5m)은 여유가 0.5m
  뿐이다. 실제로는 소형(2.2m)·경형(1.9m)이 나갈 수 있고 그러면 통과
  구간이 늘어난다. D-30 동부소방서 인터뷰에서 보유 차종을 확인해야 한다.

── 왜 대장에서 읽나 ────────────────────────────────────────────
2026-08-23 에 이 모듈을 만들면서 제원을 **출처 없이 상수로 박았다.**
같은 날 `CCTV_RANGE = 25.0` 을 두고 *"계산으로 예상한 값을 그대로 상수에
박으면 그 순간 근거 없는 상수가 하나 더 생긴다"* 고 적어놓고 어긴 것이다.

그래서 기본값을 두지 않는다. `sources.yaml` 의 `vehicle_spec` 이 없으면
이 모듈은 죽는다. 기본값이 있으면 아무도 채우지 않고 그 값이 판정에
들어간다 — `feeds` 21종이 비어 있던 것과 같은 이유다.

`params.py` 의 `TRUCK = 3.0` 은 **직선 통과 하한**이고 여기 값들은
**회전을 포함한 동적 요구폭**을 낸다. 둘은 다른 것이므로 정본도 다르다.
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[3]


class SpecMissing(RuntimeError):
    """차량 제원이 대장에 없다."""


def _spec() -> dict:
    """`sources.yaml` 의 `vehicle_spec` 을 읽는다.

    ★ 기본값을 두지 않는다. 없으면 죽는다.
      기본값을 두면 아무도 안 채우고, 그 값이 판정에 들어간다.
      `feeds` 21종이 비어 있던 것과 같은 이유다 — 규칙만 있고
      강제가 없으면 안 채운다.
    """
    p = _ROOT / "sources.yaml"
    d = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("vehicle_spec")
    if not d:
        raise SpecMissing(
            "sources.yaml 에 vehicle_spec 이 없다.\n"
            "  차량 제원은 판정을 바꾸므로 출처와 함께 대장에 적어야 한다.\n"
            "  출처 후보: 소방청 소방력 기준에 관한 규칙 · 제조사 제원표 ·\n"
            "            D-30 동부소방서 인터뷰(보유 차종)")
    need = ("width_m", "length_m", "wheelbase_m", "turn_radius_m",
            "clearance_m", "source")
    miss = [k for k in need if d.get(k) in (None, "")]
    if miss:
        raise SpecMissing(f"vehicle_spec 에 {miss} 가 비었다. source 도 필수다.")
    return d


_S = None


def spec() -> dict:
    global _S
    if _S is None:
        _S = _spec()
    return _S


def __getattr__(name: str):
    """`V.WIDTH` 처럼 쓰던 이름을 대장 값으로 잇는다."""
    m = {"WIDTH": "width_m", "LENGTH": "length_m", "WHEELBASE": "wheelbase_m",
         "TURN_R": "turn_radius_m", "CLEARANCE": "clearance_m"}
    if name in m:
        return float(spec()[m[name]])
    if name == "STRAIGHT_R":
        # 내륜차가 5cm 미만이 되는 반경
        wb = float(spec()["wheelbase_m"])
        return wb * wb / (2 * 0.05)
    raise AttributeError(name)


def offtracking(radius_m: float) -> float:
    """내륜차 — 회전 시 앞바퀴와 뒷바퀴 궤적의 폭 차이(m).

        Δ = R − √(R² − L²)

    ★ **1차 근사 `L²/(2R)` 를 쓰지 않는다.** R 이 L 에 가까워지면 근사가
      무너진다 — R=8 · L=4 에서 근사 1.000 대 정확 1.072 로 7cm 차이가
      나고, 그것이 3.0m 임계 근처에서 판정을 가른다. 골목에서 R < 8m 인
      곳이 실제로 있다.

    ★ **L 이 클수록 Δ 가 크다.** 축거를 작게 잡으면 필요폭이 작게 나오고
      그것은 미탐 방향이다. `wheelbase_verified: false` 인 지금 값 4.0 은
      통상 범위(4.2~4.5)의 하한 밖이다 — `can_turn()` 이 미검증 반경으로
      막지 않는 것과 방향이 반대다(DECISIONS 86-4).
    """
    if radius_m is None or radius_m <= 0:
        return 0.0
    s = spec()
    # ★ 2026-09-03. **미검증 축거로는 내륜차를 계산하지 않는다.**
    #   `can_turn()` 이 `turn_radius_verified` 를 보는 것과 같은 구조다.
    #
    #   범주 최대는 그 범주 전량을 알 때만 최대다. 한 대라도 모르면
    #   나머지가 그보다 클 수 있다. 판정 단위는 **센터 × 차종**이고
    #   그 조합의 보유 대수만큼 차종을 전부 알 때만 확정된다.
    #   확정 여부는 `web/config.js` 의 `CONFIG.fleet` 항목이 들고,
    #   대장은 `vehicle_spec.wheelbase_verified` 로 전역 기본을 든다.
    #
    #   ★ 0.0 을 돌려주면 필요폭이 직선 하한(전폭+여유)만 남는다.
    #     그것은 미탐 방향이다 — 근거 없이 **막지 않는** 쪽이고
    #     `can_turn` 과 같은 선택이다(DECISIONS §81 · §86-4).
    if not s.get("wheelbase_verified", False):
        return 0.0
    wb = float(s["wheelbase_m"])
    if radius_m >= wb * wb / (2 * 0.05):
        return 0.0
    if radius_m <= wb:
        # 축거보다 작은 반경은 물리적으로 못 돈다. 최대값을 준다.
        return wb
    return float(radius_m - math.sqrt(radius_m * radius_m - wb * wb))


def required_width(radius_m: float | None = None) -> float:
    """그 곡률에서 소방차가 지나가려면 필요한 최소 노면 폭(m).

        직선   전폭 + 여유              = 3.0m
        곡선   전폭 + 여유 + 내륜차

    ★ `params.TRUCK` 은 이 함수의 `radius_m=None` 인 경우다.
      직선 하한을 바꾸려면 거기가 아니라 `WIDTH`·`CLEARANCE` 를 바꾼다.
    """
    s = spec()
    return (float(s["width_m"]) + float(s["clearance_m"])
            + offtracking(radius_m))


def can_turn(radius_m: float | None) -> bool:
    """그 곡률을 이 차가 돌 수 있는가.

    ★ 폭과 무관하다. 아무리 넓어도 최소회전반경보다 급하면 못 돈다 —
      후진해서 여러 번 꺾으면 되지만 출동 중에 그럴 시간이 없다.

    ★ 2026-09-01. **미검증 반경으로는 막지 않는다.** 대장의
      `turn_radius_verified` 가 false 면 항상 True 를 돌려준다.

      지금 `turn_radius_m: 12.0` 은 자동차규칙 제9조① 의 **법정 상한**이다.
      "12m 를 초과해서는 안 된다" 는 제조 규제이므로 실제 차량은 그보다
      작게 돈다. 그것을 성능값으로 쓰면 R=11.2m 코너를 못 돈다고 낸다 —
      근거 없이 39구간을 막고 있었다.

      PLAN §4-5 도 같은 결론이다 — "전 구간 적용 시 골목 대부분 탈락 →
      그래프 붕괴". 회전은 시연 경로 코너에서 `corner_probe` 로 검증한다.

      ★ 2026-09-03 정정. **해소는 D-30 인터뷰가 아니다.** 최소회전반경은
        제작사 제원표에 실린 공개 수치이고, 관내 보유 차종은
        `gjfire_fleet_dongbu`(2026-05-14) 가 이미 든다. 종전 서술이 이것을
        인터뷰 대기로 걸어 **닫을 수 있는 항목을 병목으로 남겼다.**

        차종별 실값을 넣고 `turn_radius_verified: true` 로 올리면 켜진다.
        코드는 안 고친다. ★ 켜면 판정이 움직이므로 `golden.py lock`
        재잠금이 붙는다 — 별 PR 로 낸다.

    ★ 2026-09-01. **이 플래그가 화면까지 흐르지 않았다.** 판정은 "못 믿는
      값" 으로 아는데 `web/js/ui/vehicle.js` 는 `profiles.json` 의 7.30m 을
      그대로 띄운다. 관제사는 그 숫자를 보고 시스템이 회전을 반영한다고
      읽는다 — 반영하지 않는다. `§84-3` 이 사다리차 둘에 `turnUnknown` 을
      건 것과 같은 자리이며 펌프차만 예외로 남아 있었다.
      화면 조치는 `web/` 소관이다(DECISIONS 86-5).
    """
    if not spec().get("turn_radius_verified"):
        return True
    return radius_m is None or radius_m >= float(spec()["turn_radius_m"])


def edge_cost(length_m: float,
              width_m: float | None,
              verdict: str | None = None,
              radius_m: float | None = None,
              *,
              lenient: bool = False) -> float:
    """엣지 하나의 통행 비용. `math.inf` 면 못 간다.

    ── 왜 거리만으로는 안 되나 ──────────────────────────────────
    지금 `access_corridor()` 는 `weight="length"` 로 돈다. **통행 불가
    구간도 최단이면 지나간다.** 그러면 "소방차가 갈 수 있는 길" 이 아니라
    "제일 짧은 선" 이다.

    ── lenient ─────────────────────────────────────────────────
    `unknown` 354구간(32%)과 `needs_cv` 191구간은 **모른다** 는 뜻이지
    못 간다는 뜻이 아니다. 그것을 막으면 그래프가 끊겨 경로가 아예 안 나온다.

        lenient=False   모르는 곳은 비싸다 (보수적 · 발표 기본)
        lenient=True    모르는 곳도 통과로 본다 (연결성 확인용)

    ★ 어느 쪽이든 **`blocked` 는 막는다.** 그것만은 판정이 확정이다.

    ── 비용 ────────────────────────────────────────────────────
    거리에 배수를 곱한다. 소방차는 좁은 길에서 실제로 느리다.

        여유 충분        ×1.0
        여유 0~0.5m      ×1.8      서행 · 접이식 미러
        필요폭 미만      막힘
        회전 불가        막힘
        모름             ×2.5 (lenient 면 ×1.2)
    """
    if length_m is None or length_m <= 0:
        return math.inf
    if verdict == "blocked":
        return math.inf
    if not can_turn(radius_m):
        return math.inf

    need = required_width(radius_m)

    if width_m is None:
        # 폭을 모른다. 판정 어휘가 남은 정보다.
        if verdict in ("needs_cv", "unknown"):
            return length_m * (1.2 if lenient else 2.5)
        return length_m * (1.5 if lenient else 3.0)

    if width_m < need:
        return math.inf
    margin = width_m - need
    if margin < 0.5:
        return length_m * 1.8
    return float(length_m)
