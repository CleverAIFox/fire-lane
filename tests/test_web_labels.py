"""
test_web_labels.py — 패널 토글 이름이 지도 동작과 **같은 선언**을 읽는가.

2026-09-22 (PLAN §13 W9-4). `web/index.html` 이 `항공영상 25cm (줌 15↑)` 를
문자열로 들고 있었다. `줌 15↑` 는 `map.js` 의 `minzoom:15` 와 잇는 코드가 없었고
`25cm` 는 `sources.yaml` 의 「지상표본거리 25cm」를 사람이 베낀 것이었다.
하나를 고치면 다른 하나가 조용히 거짓이 된다.

이제 선언은 `web/config.js` 의 `CONFIG.layers` 한 곳이다.
    index.html      토글 행은 자리(data-t)만 둔다. 이름을 적지 않는다
    ui/toggles.js   layerLabel() 이 CONFIG.layers 로 이름을 조립한다
    map.js          ortho minzoom = CONFIG.layers.ortho.zoom
    layers/poles.js minzoom       = CONFIG.layers.poles.zoom
    layers/poi.js   상호 minzoom  = CONFIG.layers.poi.labelZoom
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def _read(rel: str) -> str:
    return (WEB / rel).read_text(encoding="utf-8")


def _layers_block() -> str:
    cfg = _read("config.js")
    m = re.search(r"^  layers\s*:\s*\{(.*?)^  \},", cfg, re.S | re.M)
    assert m, "`config.js` 에 `layers:` 블록이 없다 — 이 검사가 빈 그물이 됐다"
    return m.group(1)


def _layer_keys() -> set[str]:
    return set(re.findall(r"^\s*(\w+)\s*:\s*\{", _layers_block(), re.M))


def test_toggle_rows_carry_no_hand_written_names():
    """index.html 의 레이어 토글 행에 이름이 손으로 적혀 있지 않은가."""
    html = _read("index.html")
    rows = re.findall(r'<div class="row[^"]*" data-t="([^"]+)"><span>([^<]*)</span>', html)
    assert rows, "index.html 에서 토글 행을 못 찾았다 — 이 검사가 빈 그물이 됐다"
    written = [(t, s) for t, s in rows if s.strip()]
    assert not written, (
        f"index.html 토글 행에 이름이 박혀 있다: {written}\n"
        "  이름·줌·해상도는 config.js 의 CONFIG.layers 에 선언한다(PLAN §13 W9-4).")
    visible = re.sub(r"<!--.*?-->", "", html, flags=re.S)   # 주석 속 인용은 화면에 안 뜬다
    assert not re.search(r"줌\s*\d+\s*↑", visible), "index.html 에 「줌 N↑」 문구가 남아 있다"


def test_every_toggle_row_is_declared():
    """자리만 있고 선언이 없는 행 → 이름 없는 빈 스위치가 뜬다."""
    html = _read("index.html")
    rows = set(re.findall(r'data-t="([^"]+)"', html))
    missing = rows - _layer_keys()
    assert not missing, f"CONFIG.layers 에 선언이 없는 토글 행: {sorted(missing)}"


def test_layers_read_the_declared_zoom():
    """지도 레이어의 minzoom 이 토글 문구와 같은 값을 읽는가."""
    assert re.search(r"minzoom\s*:\s*CONFIG\.layers\.ortho\.zoom", _read("js/map.js")), \
        "map.js 의 ortho minzoom 이 CONFIG.layers.ortho.zoom 을 안 읽는다"
    assert "CONFIG.layers.poles.zoom" in _read("js/layers/poles.js")
    assert "CONFIG.layers.poi.labelZoom" in _read("js/layers/poi.js")
    blk = _layers_block()
    assert re.search(r"^\s*ortho\s*:\s*\{[^}\n]*\bzoom\s*:\s*\d+", blk, re.M)
    # 옛 사본이 되살아나면 다시 두 곳이 된다.
    cfg = _read("config.js")
    assert not re.search(r"^\s*fromZoom\s*:", cfg, re.M), "poles.fromZoom 사본이 되살아났다"
    assert not re.search(r"^\s*labelFromZoom\s*:", cfg, re.M), "poi.labelFromZoom 사본이 되살아났다"


def test_ortho_resolution_matches_the_ledger():
    """`res` 는 사본이다. 정본(sources.yaml 「지상표본거리 NNcm」)과 같은가."""
    m = re.search(r"^\s*ortho\s*:\s*\{[^}\n]*\bres\s*:\s*\"([^\"]+)\"", _layers_block(), re.M)
    assert m, "CONFIG.layers.ortho.res 가 없다"
    ledger = (ROOT / "sources.yaml").read_text(encoding="utf-8")
    gsd = set(re.findall(r"지상표본거리\s*(\d+\s*cm)", ledger))
    assert gsd, "sources.yaml 에서 「지상표본거리」를 못 찾았다 — 이 검사가 빈 그물이 됐다"
    assert {g.replace(" ", "") for g in gsd} == {m.group(1).replace(" ", "")}, (
        f"토글의 해상도 {m.group(1)!r} 가 대장의 {sorted(gsd)} 와 다르다")


def test_toggles_js_fills_names_from_config():
    js = _read("js/ui/toggles.js")
    assert "export function layerLabel" in js and "CONFIG.layers" in js
