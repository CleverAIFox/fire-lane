#!/usr/bin/env python3
"""
test_fleet_turn_radius.py — **회전반경 숫자는 그 차의 값일 때만 화면에 간다.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22 (DECISIONS §212). 「회전반경은 되는 제원만 숫자로」. 종전에는 전
차종이 등급만 띄웠다(§86-5). 숫자를 풀면 두 사고가 다시 열린다 —

    · 사다리차 둘은 제원표 값이 **있지만 그 차의 값이 아니다**(§84-3). 값이
      있다고 띄우면 11.89m 가 실제보다 작은 채로 확정처럼 보인다.
    · 숫자가 판정 코드로 새면 「참고」 가 거짓말이 된다.

그리고 `fleet.json` 은 파이프라인이 안 불러 손으로만 돌았다(§170-5 와 같은 모양).

── 무엇을 보는가 ───────────────────────────────────────────────
    1. `fleet.json` 의 `turn_radius_ref_m` 이 규칙(제원표 값 ∧ ¬turnUnknown)과 같다
    2. `turn_unknown` 인 차는 null — 사다리차 둘이 여기 걸린다
    3. 화면은 숫자를 `turn_radius_ref_m` 에서만 가져오고 「참고」 · 판정 미반영 고지가 있다
    4. 판정 쪽(domain · app · infra)은 `turn_radius_ref_m` 을 읽지 않는다 —
       판정용 `VehicleSpec.turn_radius_m` 과 이름을 일부러 갈랐다
    5. publish_web 이 publish_fleet 을 부른다(배선)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from firelane import publish_fleet

ROOT = Path(__file__).resolve().parents[1]
FLEET = ROOT / "web" / "data" / "fleet.json"
NAVI = ROOT / "web" / "navi" / "src"


def _fleet() -> list[dict]:
    return json.loads(FLEET.read_text(encoding="utf-8"))["vehicles"]


def test_committed_radii_follow_the_rule():
    radii = publish_fleet._turn_radii()
    cfg = {f["id"]: f for f in publish_fleet._fleet_from_config()}
    vs = _fleet()
    assert len(vs) == len(cfg) >= 10, f"차종 {len(vs)} · 설정 {len(cfg)} — 추출이 죽었다"
    for v in vs:
        f = cfg[v["id"]]
        want = None if f.get("turnUnknown") else radii.get(str(f.get("profile", "")))
        assert v.get("turn_radius_ref_m") == want, (
            f"`{v['id']}` 회전반경 커밋본 {v.get('turn_radius_ref_m')} ↔ 규칙 {want}.\n"
            "  `uv run python -m firelane.publish_fleet` 로 다시 낸다.")


def test_unknown_turn_never_gets_a_number():
    vs = _fleet()
    unknown = [v for v in vs if v["turn_unknown"]]
    assert unknown, "turn_unknown 차가 하나도 없다 — 사다리차 표지가 사라졌나(§84-3)"
    for v in unknown:
        assert v.get("turn_radius_ref_m") is None, (
            f"`{v['id']}` 는 turn_unknown 인데 숫자 {v['turn_radius_ref_m']} 가 나간다.\n"
            "  제원표 값이 그 차의 값이 아니라서 건 표지다(§84-3).")
    # 숫자가 하나도 없으면 결정(§212)이 화면에서 죽은 것이다
    assert any(v.get("turn_radius_ref_m") for v in vs), "숫자로 나가는 차가 0대다"


def test_picker_takes_the_number_only_from_fleet():
    s = (NAVI / "ui" / "VehiclePicker.tsx").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", s, flags=re.S)
    assert "turn_radius_ref_m" in code, "차량 선택이 turn_radius_ref_m 을 안 읽는다"
    assert not re.search(r"\b\d{1,2}\.\d\s*m\b", code), (
        "차량 선택 코드에 회전반경 숫자가 박혀 있다 — 숫자는 fleet.json 에서만 온다")
    for need in ("참고", "판정에 반영하지 않으며"):
        assert need in code, f"차량 선택에서 「{need}」 가 사라졌다(§86-5 · §212)"


def test_judgment_never_reads_the_reference_radius():
    """참고값은 ui 에서만 읽는다. domain(판정) · app(판정 제원 조립)은 못 읽는다."""
    hits = [p.relative_to(ROOT).as_posix()
            for d in ("domain", "app", "infra") for p in (NAVI / d).rglob("*.ts")
            if p.name != "types.ts" and "turn_radius_ref_m" in p.read_text(encoding="utf-8")]
    assert not hits, (
        f"판정 코드가 참고 회전반경을 읽는다: {hits}\n"
        "  켜려면 대장의 turn_radius_verified 를 올리고 golden 재잠금 PR 로 낸다.")


def test_publish_calls_publish_fleet():
    src = (ROOT / "src" / "firelane" / "publish_web.py").read_text(encoding="utf-8")
    assert "_fleet.main()" in src, (
        "publish_web 이 publish_fleet 을 안 부른다 — fleet.json 이 손으로만 돈다(§212).")
