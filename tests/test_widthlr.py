#!/usr/bin/env python3
"""
test_widthlr.py — 좌우 분해가 **두 고장을 가르는가**.  (DECISIONS §509)

★ 이 파일이 미는 주장은 하나다 — 「법선이 맞나 내접원이 맞나」는 **구간마다
  답이 다르고**, 그 답을 정하는 것은 비대칭이 아니라 **광선이 갇혔나 샜나**다.
  합성 도형으로 그 둘을 각각 만들어 보이고, 실물에서 그 꼴이 실재함을 든다.

밖    **어느 폭이 참인가는 안 본다.** 여기가 드는 것은 ① 분해가 치우침과 샘을
      각각 집어내는가 ② 그 둘이 **다른 축**인가(겹치지 않는 구간이 있는가)
      둘이다. 참값 대조는 `data/field` 실측과 `clearance_cross` 의 현장 칸이
      들고, 그 수를 판정으로 옮기는 것은 측정 배치의 일이다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import widthlr as W
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parent.parent

STRIP = Polygon([(0, 0), (40, 0), (40, 4), (0, 4)])      # 폭 4m 띠
OPEN = Polygon([(0, 0), (40, 0), (40, 40), (0, 40)])     # 한쪽이 광장


def test_a_centered_line_reads_the_same_width_both_ways():
    """가운데면 좌우합과 2×가까운쪽이 **같다** — 둘이 갈릴 자리가 없다."""
    d = W.lr_profile(LineString([(2, 2), (38, 2)]), STRIP)
    assert d["lr_med"] == pytest.approx(4.0)
    assert d["narrow_med"] == pytest.approx(4.0)
    assert d["asym_med"] == pytest.approx(0.0)
    assert d["escape"] == 0


def test_an_offset_line_keeps_the_sum_but_halves_the_near_side():
    """**치우쳐도 폭은 그대로다.** 2×가까운쪽만 줄어든다 — 그것이 과소의 정체다."""
    d = W.lr_profile(LineString([(2, 1), (38, 1)]), STRIP)
    assert d["lr_med"] == pytest.approx(4.0), "좌우합은 치우침에 안 흔들린다"
    assert d["narrow_med"] == pytest.approx(2.0), "2×가까운쪽은 절반이 된다"
    assert d["asym_med"] == pytest.approx(0.5)
    assert d["escape"] == 0, "막혀 있으면 안 샌다"


def test_an_open_side_escapes_and_then_the_sum_is_not_a_width():
    """광장이 붙으면 **좌우합이 폭이 아니다.** 가까운 쪽은 아직 맞다."""
    d = W.lr_profile(LineString([(2, 2), (38, 2)]), OPEN)
    assert d["escape"] == pytest.approx(1.0)
    assert d["lr_med"] > 20, "샌 쪽이 합을 통째로 키운다"
    assert d["narrow_med"] == pytest.approx(4.0), "가까운 쪽은 안 흔들린다"
    assert d["blind"] == 0, "한쪽만 샌 것은 눈먼 것이 아니다"


def test_both_sides_open_is_blind_not_wide():
    """양쪽이 다 새면 **폭이 없다.** 2×상한을 폭으로 읽으면 광장이 제일 넓어진다."""
    d = W.lr_profile(LineString([(50, 50), (90, 50)]),
                     Polygon([(0, 0), (200, 0), (200, 200), (0, 200)]))
    assert d["blind"] == pytest.approx(1.0)
    assert d["narrow_med"] == pytest.approx(2 * W.RAY_CAP_M), "상한이지 폭이 아니다"


def test_a_line_outside_the_polygon_gets_no_number():
    """0 은 폭이 아니다 — 회색이 숫자로 굳는 자리를 막는다."""
    assert W.lr_profile(LineString([(2, 2), (38, 2)]),
                        Polygon([(100, 100), (101, 100), (101, 101)])) == {}


@pytest.mark.parametrize(("fn", "key", "lo", "hi"),
                         [(W.off_center, "asym_med", 0.1, 0.3),
                          (W.escaped, "escape", 0.2, 0.7)])
def test_the_two_counters_cut_at_their_threshold(fn, key, lo, hi):
    """문턱 양쪽으로 **둘 다** 민다. 한쪽만 밀면 빈 그물과 구별이 안 된다."""
    assert not fn([{key: lo}])
    assert fn([{key: hi}])


def test_the_tool_passes_its_own_selftest():
    assert W.selftest() == 0


def test_the_published_data_actually_contains_both_shapes():
    """**실물에 그 꼴이 둘 다 있다.** 없으면 이 파일은 합성만 미는 빈 그물이다.

    ★ 발행물(`data/processed/clearance_cross.json`)을 **안 읽는다.** 그 파일은
      다른 단계가 쓰고, 그 단계가 옛 코드로 돌았으면 낡은 것을 읽게 된다 —
      2026-10-13 배달 예습에서 실제로 그 꼴로 빨갰다. 여기서 **직접 잰다.**
    ★ 두 구간만 잰다(`load(only=)`). 전수는 1분이고 값은 같다 — 구간마다
      독립으로 재기 때문이다.
    """
    import clearance_cross as C

    # 치우쳤는데 안 새는 자리 · 새는 자리. 둘 다 2026-10-13 네이버 실측이 있다.
    OFF = "DM-193346-284095-4S4P"   # 동명로67번길 22 — 대장 8.0 · 실측 6.4~9.7
    ESC = "DM-194336-283557-X6GR"   # 밤실로4번길 1-11 — 대장 6.0 · 실측 5.4
    try:
        rows = C.load(only={OFF, ESC})
    except RuntimeError as e:
        pytest.skip(f"환경skip(산출물) — 발행본이 없다: {e}")
    by = {r["seg_uid"]: r for r in rows}
    assert set(by) == {OFF, ESC}, "지목한 구간이 발행본에서 사라졌다"

    off, esc = by[OFF], by[ESC]
    assert off["asym_med"] > 0.2, "치우친 자리가 안 치우쳤다고 나온다"
    assert off["escape"] <= 0.1, "그 자리는 **안 새야** 한다 — 그래야 좌우합이 폭이다"
    assert off["lr_med"] > 2 * off["narrow_med"], \
        "치우쳤는데 좌우합과 2×가까운쪽이 안 벌어진다 — 축이 빈 그물이다"

    assert esc["escape"] > 0.5, "광장이 붙은 자리가 안 샌다고 나온다"
    # ★ 2026-10-19. **종전 단정을 뺀다** — `wmin > 3 × narrow_med` 였다.
    #   그 꼴이 **전수에서 사라졌다.** `escape > 0.5` 이면서 그 부등식을
    #   만족하는 구간이 1,281 중 **0개**다(`probe_three_reds.py` 로 셌다).
    #   이 자리의 수가 `wmin 53.290 → 3.380` 으로 내려갔고 `narrow_med`
    #   5.861 은 **안 움직였다** — 보도 차감 재잠금이 고친 것이 법선이다.
    #
    #   ★ 예시를 갈아 끼울 수가 없다. **갈아 끼울 구간이 없다**는 것이
    #     이 판의 성과이고, 그 사실을 단정으로 세운다 — 그 꼴이 다시
    #     생기면 이 시험이 운다.
    #   ★ 「새는데 고장이 안 보인다」를 묻는 자리는 `inversion()` 이
    #     받는다(`wmin < carr_min` · 현장 5구간 중 3). 이 파일이 그것을
    #     다시 묻지 않는다 — `tests/test_clearance_cross.py` 가 든다.
    leaky = [r for r in C.load()
             if isinstance(r.get("escape"), (int, float))
             and isinstance(r.get("wmin"), (int, float))
             and isinstance(r.get("narrow_med"), (int, float))
             and r["narrow_med"] > 0
             and r["escape"] > 0.5
             and r["wmin"] > 3 * r["narrow_med"]]
    assert not leaky, (
        "새면서 법선이 가까운쪽의 3배를 넘는 구간이 다시 생겼다 — "
        f"{len(leaky)}건 · {sorted(r['seg_uid'] for r in leaky)[:5]}. "
        "보도 차감 재잠금이 되돌아갔는지 본다(봉인 20261015-width-root-walk)")
    assert esc["wmin"] and esc["wmin"] < esc["narrow_med"], (
        f"이 자리의 법선({esc['wmin']})이 가까운쪽({esc['narrow_med']}) 아래로 "
        "안 내려왔다 — 보도 차감이 안 걸렸다")

    # ★ **둘이 다른 축이다** — 하나가 다른 하나를 함의하지 않는다.
    assert C.off_center(rows) and C.escaped(rows)
    assert {d["seg"] for d in C.off_center(rows)} != {d["seg"] for d in C.escaped(rows)}
