"""차량 제원 배선이 **조용히 기준차로 떨어지지 않는가.**

★ 2026-09-25 (PLAN §1 #38 · DECISIONS §253). `web/config.js` 의 `fleet` 열 항목 중
  **여섯**이 대장 `vehicle_profiles.items` 에 **없는 이름**을 가리키고 있었다 —
  `tanker_large` · `ladder_33m_plus` · `ladder_under_33m` · `rescue_5t` ·
  `ambulance_current_example`(둘). `publish_fleet` 이
  `profiles.get(id, {})` → `p.get("width_m", spec["width_m"])` 로 받아
  **전폭은 기준차 2.5 로 떨어지고 전장·전고는 통째로 null** 이 됐다.

  그중 하나가 **물탱크차**다. 대장은 `water_large`(물탱크차 대형 · 전장 10.0m)를
  들고 있는데 config 가 `tanker_large` 를 불렀다. 2026-08-24 전북소방 인터뷰의
  「물탱크차는 커서 못 들어간다」가 **폭이 아니라 전장**이라고 대장이 적어 두었고
  (`vehicle_profiles.notes`), 정작 그 전장이 비어 있었다.

★ **전폭이 열 차종 전부 2.5인 것은 결함이 아니다.** 대장이 적는다 —
  「전폭은 경형·소형펌프차(1.9 · 2.2)를 빼면 전 차종 2.5 로 같다」. 소방청
  기본규격이 그렇고 동구에는 경형·소형이 없다. **갈리는 것은 전장이다.**
  그래서 이 파일은 전폭이 같은 것을 문제 삼지 않고, **전장이 같아지면** 운다.

IN    web/config.js · sources.yaml · web/data/fleet.json
OUT   없음
PARAM 없음
밖    전장을 **판정에 쓰는지**는 안 본다 — 지금 판정은 폭만 본다(`seg/vehicle.py`).
      전장이 통과 가부를 가르게 하는 것은 `PLAN §1 #38` 이 들고, 그 전에
      축거·회전반경(D-30)이 있어야 한다. 여기서 보는 것은 「값이 화면까지
      오는가」뿐이다. 오지도 않는 값은 판정에 넣을 수도 없다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from firelane import ledger

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "web/config.js"
FLEET = ROOT / "web/data/fleet.json"


def _profiles() -> dict:
    """★ `ledger.load()` 로 읽는다. yaml 로 대장을 직접 열면
    `test_lake.py::test_ledger_is_loaded_through_one_door` 래칫이 오른다 —
    **이 파일을 처음 쓸 때 실제로 깼다.** 오늘 두 번째다(§246 에 한 번 적었다)."""
    return (ledger.load().get("vehicle_profiles") or {}).get("items") or {}


def _config_fleet() -> list[tuple[str, str | None]]:
    """`(차량 id, profile 이름 또는 None)`. `config.js` 를 정규식으로 읽는다."""
    src = CONFIG.read_text(encoding="utf-8")
    i = src.index("fleet: [")
    blk = src[i:src.index("\n  ],", i)]
    out = []
    for m in re.finditer(r'\{\s*id:"([^"]+)"[\s\S]{0,400}?profile:\s*(?:"([^"]*)"|(null))', blk):
        out.append((m.group(1), m.group(2) if m.group(2) else None))
    return out


# ── 배선 ────────────────────────────────────────────────────────
def test_every_profile_name_exists_in_the_ledger():
    """**없는 이름을 가리키면 조용히 기준차로 떨어진다.** 그것이 여섯 달 숨었다."""
    prof, bad = _profiles(), []
    for vid, pid in _config_fleet():
        if pid and pid not in prof:
            bad.append(f"{vid} → {pid}")
    assert not bad, (
        "config.js 의 fleet 이 대장에 없는 profile 을 가리킨다:\n  " + "\n  ".join(bad) + "\n"
        f"  대장에 있는 이름: {sorted(prof)}\n"
        "  대응이 있으면 그 이름으로 고치고, **없으면 `profile: null` 로 적어라** —\n"
        "  억지로 비슷한 것에 붙이면 그 값이 판정까지 간다.")


def test_the_fleet_parser_is_alive():
    """카나리아 — 정규식이 낡으면 위 검사가 **빈 목록**을 훑고 초록이 된다."""
    got = _config_fleet()
    assert len(got) >= 8, f"fleet 에서 {len(got)}대만 읽었다 — 정규식이 낡았다"
    assert any(p is None for _, p in got), "null profile 을 하나도 못 읽는다"
    assert any(p for _, p in got), "이름 있는 profile 을 하나도 못 읽는다"
    ids = [v for v, _ in got]
    assert len(ids) == len(set(ids)), f"id 중복: {ids}"


def test_the_publisher_refuses_an_unknown_profile():
    """발행기가 **죽는가.** 시험만 울고 발행이 통과하면 산출물은 여전히 거짓이다."""
    src = (ROOT / "src/firelane/publish_fleet.py").read_text(encoding="utf-8")
    assert "raise SystemExit" in src and "대장에 없는 profile" in src, (
        "`publish_fleet` 이 없는 이름을 조용히 넘긴다.\n"
        "  `profiles.get(id, {})` 는 **빈 dict 를 주고 아무 말도 안 한다** — 그것이\n"
        "  열 차종 중 여섯을 기준차 값으로 만든 자리다(§253).")


# ── 값이 화면까지 오는가 ────────────────────────────────────────
@pytest.fixture(scope="module")
def fleet() -> list[dict]:
    assert FLEET.exists(), f"{FLEET.relative_to(ROOT)} 가 없다 — 발행 대상이다"
    return json.loads(FLEET.read_text(encoding="utf-8"))["vehicles"]


def test_the_lengths_are_not_all_the_same(fleet):
    """**전장이 갈려야 한다.** 이것이 차종 차이의 정본이다.

    ★ 전폭은 전 차종 2.5 라 차이가 안 난다(대장 `notes`). 인터뷰가 지목한
      「물탱크차는 커서 못 들어간다」의 근거는 **전장** 10.0m 대 8.0m 다.
      전장까지 같아지면 차종을 고르는 의미가 통째로 사라진다.
    """
    got = sorted({r["length_m"] for r in fleet if r.get("length_m") is not None})
    assert len(got) >= 2, (
        f"발행된 전장이 {got} 하나뿐이다 — 차종이 구별되지 않는다.\n"
        "  대장 `vehicle_profiles.items` 는 5.2~13.0m 를 든다. 배선이 끊겼는지 봐라\n"
        "  (없는 profile 이름을 가리키면 null 로 떨어진다).")


def test_the_water_tanker_carries_the_length_the_interview_named(fleet):
    """**인터뷰가 지목한 차의 값이 실제로 있는가.** 이 한 줄이 §253 의 이유다."""
    t = next((r for r in fleet if r["id"] == "tanker"), None)
    assert t is not None, "물탱크차가 발행물에 없다"
    assert t["length_m"] == 10.0, (
        f"물탱크차 전장이 {t['length_m']} 다 — 대장 `water_large` 는 10.0m 를 든다.\n"
        "  2026-08-24 전북소방 인터뷰의 「물탱크차는 커서 못 들어간다」가 이 값이다.\n"
        "  null 이면 `profile` 이 대장에 없는 이름(`tanker_large`)으로 돌아간 것이다.")


def test_a_null_profile_says_so_instead_of_pretending(fleet):
    """대응이 없는 차는 **없다고 적는가.** 조용히 기준차 값을 쓰면 안 된다."""
    prof = dict(_config_fleet())
    for r in fleet:
        if prof.get(r["id"]) is None:
            assert r.get("length_m") is None, (
                f"{r['id']} 는 profile 이 null 인데 전장 {r['length_m']} 이 나왔다 — "
                "어디선가 값을 지어내고 있다")
            assert (r.get("note") or ""), (
                f"{r['id']} 는 대장에 대응이 없는데 **사유가 없다.**\n"
                "  없는 것은 없다고 적는다 — 화면이 그 사실을 말할 수 있어야 한다(§212).")


def test_the_widths_being_equal_is_recorded_not_an_accident():
    """전폭이 전부 같은 것은 **결함이 아니라 규격**이다 — 대장이 그렇게 적는가.

    ★ 이 검사가 없으면 다음 사람이 전폭 동일을 버그로 보고 「고치려」 든다.
      실제로 2026-09-25 에 그 오진이 한 번 나왔다.
    """
    notes = str((ledger.load().get("vehicle_profiles") or {}).get("notes") or "")
    assert "전 차종 2.5 로 같다" in notes, (
        "대장이 「전폭은 전 차종 2.5 로 같다」를 안 적는다.\n"
        "  그 줄이 없으면 전폭 동일이 결함으로 오진된다 — 실제로 한 번 그랬다.")
    assert "전장" in notes, "「갈리는 것은 전장」이라는 사실이 대장에 없다"
