"""`web/navi/package.json` 의 npm `overrides` 가 **대장(`sources.yaml` 의 `pending`)에 걷을 조건과 함께 올라 있다** — 조용한 override 를 막는다.  (DECISIONS §802-E)

override 는 lock 이 조용히 거짓말하게 만드는 자리다 — 상류가 못 받는 판을 가린다. 그래서 override 하나마다 「언제 걷는가」 를 적은 열린 항목이 있어야 하고,
열린 항목은 실재하는 override 를 가리켜야 하며, **해소로 적은 항목의 override 는 없어야 한다**(걷었다고 적고 남겼거나 그 반대).

묻는 것: ① override 마다 열린 `npm_override_*` 항목이 있다 ② 열린 항목마다 override 가 실재한다 ③ 해소 항목의 override 는 없다 ④ 열린 항목은 걷을 조건(`blocking`)과 `fallback` 을 든다
IN    `web/navi/package.json` · `sources.yaml` 의 `pending`
밖    **걷을 조건이 참인지는 안 본다**(그것은 상류 릴리스를 읽어야 해서 망이 필요하다 — 항목의 확인 명령이 든다) · lock 이 override 를 지키는지는 안 본다
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from firelane import ledger

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "web" / "navi" / "package.json"


def _flat(ov: dict, prefix: str = "") -> list[str]:
    """`{"a": "1", "b": {"c": "2"}}` → `["a", "b>c"]`."""
    out: list[str] = []
    for k, v in ov.items():
        if isinstance(v, dict):
            out += _flat(v, f"{prefix}{k}>")
        else:
            out.append(f"{prefix}{k}")
    return out


def _slug(path: str) -> str:
    return "npm_override_" + re.sub(r"[^a-z0-9]+", "_", path.lower().replace("@typescript-eslint/", "")).strip("_")


def _pending() -> dict[str, dict]:
    d = ledger.load_sources()        # 대장은 한 문으로 읽는다 — 직접 yaml 로 열면 `test_lake` 의 읽는 문 래칫(MAX_LEDGER_LOADERS)이 는다
    return {e["key"]: e for e in d.get("pending", []) if str(e.get("key", "")).startswith("npm_override_")}


def _overrides() -> list[str]:
    return _flat(json.loads(PKG.read_text(encoding="utf-8")).get("overrides") or {})


def _closed(e: dict) -> bool:
    return str(e.get("status", "")).startswith("해소")


def test_every_override_has_an_open_entry_with_its_condition():
    pend = _pending()
    open_keys = {k for k, e in pend.items() if not _closed(e)}
    for path in _overrides():
        # 중첩 override 는 부모 아래 자식이라 이름이 `@typescript-eslint/typescript-estree>minimatch` — 항목 키는 부모와 자식을 이은 이름이다
        want = _slug(path.replace(">", "_"))
        assert want in open_keys, f"override `{path}` 가 대장에 열린 항목으로 없다 — `pending` 에 `key: {want}` 를 걷을 조건과 함께 올려라"
        e = pend[want]
        assert str(e.get("blocking", "")).strip() and str(e.get("fallback", "")).strip(), f"`{want}` 에 걷을 조건(blocking)이나 fallback 이 없다"


def test_every_open_entry_points_at_a_real_override():
    real = {_slug(p.replace(">", "_")) for p in _overrides()}
    dead = sorted(k for k, e in _pending().items() if not _closed(e) and k not in real)
    assert not dead, f"열린 항목인데 override 가 없다(걷었으면 status 를 해소로 고친다): {dead}"


def test_a_resolved_entry_has_no_override_left():
    real = {_slug(p.replace(">", "_")) for p in _overrides()}
    back = sorted(k for k, e in _pending().items() if _closed(e) and k in real)
    assert not back, f"해소로 적었는데 override 가 남았다: {back}"


def test_the_declared_slug_matches_the_real_names():
    """자기 검사 — 키 이름 규칙이 실제 override 이름에서 기대한 키를 낸다(빈 그물 방지)."""
    assert _slug("@typescript-eslint/typescript-estree>minimatch".replace(">", "_")) == "npm_override_typescript_estree_minimatch"
    assert _slug("source-map-js") == "npm_override_source_map_js"
    assert _overrides(), "override 가 하나도 없다 — 이 시험이 빈 그물이다(전부 걷었으면 시험도 같이 걷는다)"
