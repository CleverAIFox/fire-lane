#!/usr/bin/env python3
"""
test_map_colour_keys.py — 지도 색표의 키가 **발행물에 실재하는 값인가**.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §13 W9-1). `web/config.js` 의 `poles.color` 키가
`"보안등"` 이었다. 실물 `lightpoles.geojson` 의 값은 `"보안(방범)등"` 이고
그것이 **664점 — 1,188점 중 55.9%** 다. `poles.js` 의 `match` 는 정확
일치라 664점이 전부 `other` 회색으로 떨어졌고, **파랑은 화면에 한 점도
나오지 않았다.**

★ **아무것도 안 울었다.** 색이 틀린 것은 예외가 아니라 `match` 의
  fallback 으로 흡수된다. 화면은 멀쩡해 보이고 검사는 전부 초록이다 —
  이 저장소가 1족(무음 통과)이라 부르는 그 자리이고, fallback 이 그 문이다.

★ 키를 고치는 것은 인스턴스다. **이 검사가 족이다.** 값 집합이 늘거나
  표기가 바뀌면(`보안등` → `보안(방범)등` 같은 일은 공공데이터에서 흔하다)
  여기서 운다. `tests/test_scope_tiers.py` 와 같은 답 — 파이썬과 JS 라
  합칠 수가 없으니 **같은지를 강제한다.**

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 색표의 모든 키가 발행물에 실제로 있는 값인가 (죽은 키 금지)
    2. `other` 로 떨어지는 값이 있으면 `otherLabel` 이 있고,
       하나도 없으면 `otherLabel` 도 없는가 (사체 금지)

★ **범위를 선언한다.** 이 검사는 `web/js/layers/*.js` 에서
  `CONFIG.<블록>.color` 와 `["get","<속성>"]` 이 **같은 식 안에** 있고,
  `main.js` 가 `add<레이어>(D.<이름>)` 로 자료를 넘기는 층만 본다.
  지금 걸리는 것은 `poi` · `poles` 둘이다. 손으로 적지 않는다 — 셋째 층이
  같은 꼴로 생기면 자동으로 들어온다. 다른 꼴(색을 코드가 계산하는 층)은
  **이 검사 밖이고 그 사실이 여기 적혀 있다.**
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ROOT / "web" / "js" / "layers"
CONFIG_JS = ROOT / "web" / "config.js"
MAIN_JS = ROOT / "web" / "js" / "main.js"
DATA = ROOT / "web" / "data"

# `CONFIG.poles.color` … `["get","pole_kind"]` 가 한 식 안에 있는 꼴
PAIR = re.compile(r'CONFIG\.(\w+)\.color\b.{0,400}?\["get"\s*,\s*"(\w+)"\]', re.S)
# `addPoles(D.lightpoles)` → 층이 읽는 발행물
FEED = re.compile(r'\badd(\w+)\s*\(\s*D\.(\w+)\s*\)')


def _blocks() -> list[tuple[str, str, str, Path]]:
    """(설정블록, 매칭속성, 층파일이름, 발행물경로) 목록. 전부 유도한다."""
    feeds = {fn.lower(): name for fn, name in FEED.findall(MAIN_JS.read_text(encoding="utf-8"))}
    out = []
    for p in sorted(LAYERS.glob("*.js")):
        for blk, prop in PAIR.findall(p.read_text(encoding="utf-8")):
            # `poles.js` → `addPoles` → `D.lightpoles` → web/data/lightpoles.geojson
            feed = feeds.get(p.stem.lower())
            if not feed:
                continue
            g = DATA / f"{feed}.geojson"
            if g.is_file():
                out.append((blk, prop, p.name, g))
    return out


def _colour_table(block: str) -> dict[str, str]:
    """`config.js` 의 `<block>: { … color: { … } … }`."""
    src = CONFIG_JS.read_text(encoding="utf-8")
    m = re.search(rf"\b{re.escape(block)}:\s*\{{(.*?)\n  \}},", src, re.S)
    assert m, f"`config.js` 에 `{block}` 블록이 없다"
    body = m.group(1)
    c = re.search(r"color:\s*\{(.*?)\}", body, re.S)
    assert c, f"`{block}` 에 `color` 표가 없다"
    return dict(re.findall(r'"([^"]+)"\s*:\s*"(#[0-9a-fA-F]+)"', c.group(1)))


def _values(g: Path, prop: str) -> set[str]:
    with open(g, encoding="utf-8") as f:
        feats = json.load(f).get("features") or []
    return {v for v in ((x.get("properties") or {}).get(prop) for x in feats) if v}


def test_the_probe_is_not_an_empty_net():
    """짝을 한 건도 못 찾으면 **이 파일 전체가 조용히 통과한다**(deadcheck ①).

    ★ 정규식 하나가 낡는 것만으로 아래 둘이 전부 무력해진다. 그것이
      이 저장소가 반복해 당한 모양이라, 그물이 비었는지를 먼저 묻는다.
    """
    got = _blocks()
    assert len(got) >= 2, (
        f"색표 짝을 {len(got)}건밖에 못 찾았다 — 정규식이 낡았거나 층이 사라졌다.\n"
        "  이 검사가 아무것도 안 보는 상태로 초록이 되는 것을 막는다.")


@pytest.mark.parametrize("block,prop,layer,feed", _blocks(),
                         ids=lambda v: v if isinstance(v, str) else getattr(v, "name", ""))
def test_every_colour_key_exists_in_the_published_data(block, prop, layer, feed):
    """색표의 키가 발행물에 실재하는가. **없는 키는 아무 점도 못 칠한다.**"""
    table = _colour_table(block)
    keys = {k for k in table if k != "other"}
    vals = _values(feed, prop)
    dead = sorted(keys - vals)
    assert not dead, (
        f"`config.{block}.color` 의 키 {dead} 가 `{feed.name}` 의 `{prop}` 에 없다.\n"
        f"  발행물 실제 값: {sorted(vals)}\n"
        f"  키가 값과 안 맞으면 그 점들은 전부 `other` 로 떨어진다 —\n"
        f"  `{layer}` 의 match 는 정확 일치이고, 틀린 색은 예외가 아니라 조용한 통과다.\n"
        "  (2026-09-20 에 `보안등` 이 그래서 664점 55.9% 를 회색으로 떨궜다)")


@pytest.mark.parametrize("block,prop,layer,feed", _blocks(),
                         ids=lambda v: v if isinstance(v, str) else getattr(v, "name", ""))
def test_other_bucket_has_a_label_exactly_when_it_has_members(block, prop, layer, feed):
    """회색으로 떨어지는 값이 있을 때만 `otherLabel` 이 있는가.

    ★ 두 방향 다 결함이다. 떨어지는데 라벨이 없으면 **보는 사람이 회색을
      무엇으로 읽을 근거가 없고**, 안 떨어지는데 라벨이 있으면 그것은 사체다
      (W9-3 의 `sat` 레이어와 같은 형태 — 있는데 아무도 안 부른다).
    """
    table = _colour_table(block)
    keys = {k for k in table if k != "other"}
    spill = sorted(_values(feed, prop) - keys)
    src = CONFIG_JS.read_text(encoding="utf-8")
    blk = re.search(rf"\b{re.escape(block)}:\s*\{{(.*?)\n  \}},", src, re.S).group(1)
    labelled = "otherLabel" in blk
    if spill:
        assert labelled, (
            f"`{feed.name}` 의 {prop} 값 {spill} 이 `other` 로 떨어지는데 "
            f"`config.{block}.otherLabel` 이 없다.\n"
            "  회색을 무엇으로 읽어야 하는지 화면이 말해주지 않는다.")
    else:
        assert not labelled, (
            f"`config.{block}.otherLabel` 이 있는데 `other` 로 떨어지는 값이 0개다 — 사체다.\n"
            "  지워라. 죽은 채로 두면 다음 사람이 「그 외가 있구나」라고 읽는다.")
