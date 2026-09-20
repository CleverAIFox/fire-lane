#!/usr/bin/env python3
"""
test_scope_tiers.py — 지도의 세 층이 **검사와 같은 기준**을 쓰는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §1 #62). 발행 구간 1,281 은 성질이 셋으로 갈린다 —
동명동 안 416 · 동 밖인데 출동경로가 쓰는 219 · 어떤 경로도 안 쓰는 646.
그런데 지도에서 **셋이 같은 진하기**로 그려져 「어디가 대상지인가」가
화면에서 안 보였다.

★ 같은 갈래를 **세 곳**이 쓴다 — `tools/scopecheck.py`(래칫) ·
  `web/js/layers/segments.js`(진하기) · `web/js/ui/stats.js`(카운트).
  손으로 세 번 적으면 한 곳만 고치는 날이 오고, 그때 **지도와 검사가
  다른 것을 말한다.** 그것이 이 저장소가 반복해 당한 2족이다.
  합칠 수가 없다(파이썬과 JS 다) — 그래서 **같은지를 강제한다.**
  W3-18 의 노드 판, freshcheck 의 `STAMP_KEYS` 와 같은 답이다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 세 곳이 전부 `in_emd` 와 `route_usage` 두 속성만 쓴다
    2. 새 속성을 안 만든다 (발행물에 이미 있는 것으로 가른다)
    3. 색을 안 쓴다 — 범례 밖 색이 지도에만 남는 것을 막는다
    4. 층 투명도가 대상지 > 회랑 > 참고 순이다
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEG_JS = ROOT / "web" / "js" / "layers" / "segments.js"
STATS_JS = ROOT / "web" / "js" / "ui" / "stats.js"
CONFIG_JS = ROOT / "web" / "config.js"
SEGMENTS = ROOT / "web" / "data" / "segments.geojson"

TIER_KEYS = ("in_emd", "route_usage")


def test_map_tier_uses_the_same_two_properties():
    """지도 진하기가 `in_emd` · `route_usage` 로 가르는가."""
    src = SEG_JS.read_text(encoding="utf-8")
    m = re.search(r"export const scopeTier = \(\) => (\[.*?\];)", src, re.S)
    assert m, "`scopeTier` 표현식을 못 찾았다 — 이름이 바뀌었으면 이 시험도 옮겨라"
    body = m.group(1)
    for k in TIER_KEYS:
        assert f'"{k}"' in body, (
            f"`scopeTier` 가 `{k}` 를 안 본다.\n"
            "  tools/scopecheck.py 와 같은 두 속성으로 갈라야 지도와 검사가\n"
            "  같은 것을 말한다.")


def test_stats_counts_with_the_same_rule():
    """좌측 카운트도 같은 기준인가."""
    src = STATS_JS.read_text(encoding="utf-8")
    for k in TIER_KEYS:
        assert k in src, f"통계가 `{k}` 를 안 쓴다 — 지도와 다른 수를 찍게 된다"


def test_tiers_do_not_invent_a_property():
    """발행물에 **이미 있는** 속성만 쓰는가.

    ★ 새 속성을 만들면 파이프라인을 다시 돌려야 지도가 맞고, 그 사이
      지도는 조용히 틀린다. 있는 것으로 가르면 그 창이 없다.
    """
    with open(SEGMENTS, encoding="utf-8") as f:
        props = json.load(f)["features"][0]["properties"]
    for k in TIER_KEYS:
        assert k in props, f"`{k}` 가 발행물에 없다 — 지도가 못 읽는다"


def test_tier_uses_opacity_not_colour():
    """색을 안 늘리는가.

    ★ 색은 판정 4종의 것이다. 범례에 없는 색이 지도에만 남는 상태가
      제일 나쁘다(`layers/segments.js` 머리말). 층은 진하기로만 가른다.
    """
    src = SEG_JS.read_text(encoding="utf-8")
    m = re.search(r"export const scopeTier = \(\) => (\[.*?\];)", src, re.S)
    assert m
    body = m.group(1)
    assert not re.search(r"#[0-9a-fA-F]{3,6}|rgb\(", body), (
        "`scopeTier` 가 색을 만든다. 층은 진하기로만 가른다 —\n"
        "  범례에 없는 색이 지도에만 남는 것이 제일 나쁜 상태다.")


def test_tier_alphas_are_ordered():
    """대상지 > 회랑 > 참고 순으로 옅어지는가."""
    src = CONFIG_JS.read_text(encoding="utf-8")
    m = re.search(r"scope:\s*\{(.*?)\}", src, re.S)
    assert m, "`config.js` 에 `scope` 블록이 없다"
    got = dict(re.findall(r"(\w+)\s*:\s*([0-9.]+)", m.group(1)))
    corr, aside = float(got["corridorAlpha"]), float(got["asideAlpha"])
    assert 1.0 > corr > aside > 0.0, (
        f"층 투명도 순서가 틀렸다 — 대상지 1.0 > 회랑 {corr} > 참고 {aside} > 0\n"
        "  참고 층이 회랑보다 진하면 「무엇이 대상지인가」가 다시 안 보인다.")
