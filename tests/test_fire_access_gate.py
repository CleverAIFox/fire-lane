#!/usr/bin/env python3
"""
test_fire_access_gate.py — 소방서가 소방통로 확보 대상으로 지정한 구간을 「양쪽 주차해도 통과」(clear)로 **발표하지 않는다.** (Zm8 · DECISIONS §550)

── 왜 이 관문인가 ──────────────────────────────────────────────
`fire_access` 는 동부소방서가 직접 지정·관리하는 20구간(7,120m · 3,452세대)이다 — 대장이 「사실상 정답 데이터」라 적어 두었다. 그 지정과 우리 `clear` 가 겹치면 둘 중 하나가 틀렸다.
관문: `nfa_access_listed` 이고 `nfa_access_loose` 가 아니고(`len_ratio` 0.5~2.0 안) `verdict == clear` 면 막는다. **느슨한 매칭(ratio 밖)은 경고로만 세고 막지 않는다.**
★ **폭 숫자를 직접 비교하지 않는다.** 소방서 폭은 구간 대표값이고 우리 `wmin` 은 지점 최솟값이다 — 다른 물리량이다. 「소방서보다 넓으면 과대판정」 같은 규칙을 만들지 않았다(근거가 없다).
★ 매칭은 **정확 일치**다(부분 문자열이 아니다) — 처음 안은 본선 경양로가 「경양로 247번길」 골목 행에 걸려 22구간이 오탐이었다. 걸린 구간의 `nfa_access_token`(소방서 지역명 원문)을 같이 출력한다 — 본선인지 번길인지는 사람이 읽고 판단한다.

IN    web/data/segments.geojson · firelane.fireaccess
OUT   없음 (검사)
PARAM 없음
밖    **소방서 지정이 옳은가는 안 본다** — 지정과 `clear` 가 겹치는지만 본다. 지정은 「폭이 좁다」가 아니라 「세대가 많고 소방활동이 곤란하다」는 복합 판단이다(폭만으로 CLEAR 를 올리는 근거로 삼지 않는다).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from firelane.fireaccess import RATIO_HI, RATIO_LO, columns, match

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "web" / "data" / "segments.geojson"

ROWS = [
    dict(text="대인시장 : 제봉로184번길 10(대인동) 일대(구, 동계천1로)", norm="대인시장:제봉로184번길10(대인동)일대(구,동계천1로)", len=750.0, width="5", hh=118),
    dict(text="남광주 시장 : 제봉로17번길 9-9(학동) 일대", norm="남광주시장:제봉로17번길9-9(학동)일대", len=50.0, width="2.7~3.2", hh=54),
    dict(text="계림동주민센터 일대 : 경양로 247번길 26(계림동)", norm="계림동주민센터일대:경양로247번길26(계림동)", len=1000.0, width="6", hh=194),
    dict(text="계림동, 산수동 고지대일대 동구 경양로 333외(산수동)", norm="계림동,산수동고지대일대동구경양로333외(산수동)", len=230.0, width="6", hh=114),
]


def test_match_is_exact_not_a_substring():
    assert match("제봉로", ROWS) is None                                   # 본선은 「제봉로184번길」 · 「제봉로17번길」 행에 안 걸린다(부분 문자열이 아니다)
    row = match("제봉로184번길", ROWS)
    assert row["len"] == 750.0 and row["width"] == "5"
    assert match("제봉로17번길", ROWS)["width"] == "2.7~3.2"                 # 범위는 문자열 그대로
    assert match("없는길", ROWS) is None and match(None, ROWS) is None


def test_a_main_road_does_not_hit_an_alley_row_but_does_hit_its_own_row():
    """`경양로 247번길 26` 은 번길이다 — 본선 `경양로`(대로)는 거기 안 걸리고 `경양로 333외` 행에만 걸린다(경양로 22구간 오탐의 원인)."""
    row = match("경양로", ROWS)
    assert row["len"] == 230.0 and "333외" in row["text"]                   # 1000m 골목 행이 아니다
    alley = match("경양로247번길", ROWS)                                     # 띄어 써도 같은 번길이다
    assert alley["len"] == 1000.0 and "247번길" in alley["text"]


def test_len_ratio_and_loose_flag():
    cols = columns(["제봉로184번길", "제봉로184번길", "경양로", None], [400.0, 5.0, 3000.0, 1.0], ROWS)
    assert cols["nfa_access_listed"] == [True, True, True, False]
    assert cols["nfa_access_token"][0].startswith("대인시장") and "333외" in cols["nfa_access_token"][2]   # 원문을 남긴다
    assert cols["nfa_access_len_ratio"][0] == cols["nfa_access_len_ratio"][1] == 0.54          # 405 / 750 — 같은 도로명은 연장을 합친다
    assert cols["nfa_access_loose"][:3] == [False, False, True]                                # 0.54 안 · 경양로 3000/230 = 13.04 밖
    assert cols["nfa_access_len_ratio"][2] == 13.04 and cols["nfa_access_width"][3] is None
    assert (RATIO_LO, RATIO_HI) == (0.5, 2.0)


def _need():
    if not SEG.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 이 없다")
    return [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]


def test_published_segments_carry_the_fire_access_columns():
    feats = _need()
    assert all(k in feats[0] for k in ("nfa_access_listed", "nfa_access_width", "nfa_access_len_m", "nfa_access_hh",
                                       "nfa_access_len_ratio", "nfa_access_loose", "nfa_access_token"))
    assert sum(1 for p in feats if p["nfa_access_listed"]) >= 100, "소방서 지정이 거의 안 붙었다 — 매칭이 죽었다"
    # ★ 형을 본다. `None` 이 섞인 열이 문자열('True' · 'False')로 써지면 관문의 `is False` 가 **조용히 전부 통과**한다(2026-10-23 실제로 겪었다).
    assert all(p["nfa_access_listed"] in (True, False) and isinstance(p["nfa_access_listed"], bool) for p in feats)
    assert all(p["nfa_access_loose"] is None or isinstance(p["nfa_access_loose"], bool) for p in feats), "nfa_access_loose 가 불리언이 아니다 — 문자열로 써졌다"
    assert all(p["nfa_access_hh"] is None or isinstance(p["nfa_access_hh"], int) for p in feats), "nfa_access_hh 가 정수가 아니다"


#: **알려진 예외** — `seg_uid` → 한 줄 이름. ★ `seg_id` 가 아니라 `seg_uid` 로 적는다(`seg_id` 는 판마다 밀린다 · DECISIONS §572).
#: 목록에 **없는** 새 구간이 걸리면 이 관문은 빨갛다(네 번째가 생기면 운다).
#:
#: ★ 2026-10-26 (Zm55 · DECISIONS §591-3 · §592). 동계로9번길 세 구간(소방서 「동명파크맨션 주변 … 12(동명동) 일대」 · 구간거리 220m · 폭 6m · 세대 320)을 예외로 둔다. 두 방향 다 세울 수 없어서다 —
#:   ① 「폭 때문에 지정됐다」를 세울 수 없다: 소방서 원자료는 6칸(연번 · 지역명 · 구간거리 · 폭 · 세대수 · 기준일)뿐이고 **지정 사유 칸이 없다**.
#:   ② 「우리가 틀렸다」도 세울 수 없다: `wmin` 8.52~9.97 · 내접원 7.2~8.0(중앙값 7.26~8.00) · 대장 9.0 이 전부 `clear` 문턱 7.0 위이고 소방서의 6 만 외톨이다 — 그리고 6 은 구간 **대표값**이고 우리 `wmin` 은
#:      지점 **최솟값**이라 다른 물리량이다.
#:   MASTER §2-2a 의 진입곤란 지정 기준 ②(상습 주·정차 등으로 상시 지장)로 지정됐다면 **정적 폭 판정 `clear` 와 소방서 지정이 동시에 참일 수 있다.** 그 몫은 `needs_cv` 가 본다.
#:   이 관문은 「둘 중 하나가 틀렸다」를 증명하는 **관문**이 아니라 「지정 ∧ 엄격 매칭 ∧ clear 면 사람이 본다」는 **경보**로 타당하다 — 그래서 관문은 유지하되 사람이 본 세 구간을 명시한다.
#: **거둘 조건(이 중 하나가 생기면 예외를 지운다):** ⓐ 소방서 자료에 지정 사유 칸이 생겨 사유가 읽힌다 ⓑ 현장 실측(`data/field`)이 이 세 구간에서 7.0 아래를 보인다(그러면 판정을 고친다) ⓒ 소방서 「일대」의 위치가
#:   좌표로 주어져 세 구간(74.7m · 220m 의 34%)이 일대 밖이라고 확인된다.
KNOWN_EXCEPTIONS: dict[str, str] = {
    "DM-193089-284028-D27G": "동계로9번길 DM00838 (23.0m · wmin 8.52)",
    "DM-193055-284037-D27G": "동계로9번길 DM00841 (16.1m · wmin 9.86)",
    "DM-193031-284044-D27G": "동계로9번길 DM00843 (35.6m · wmin 9.97)",
}


def violations(feats: list[dict]) -> list[dict]:
    """엄격 매칭(`loose` 가 False)된 소방서 지정 구간 중 `clear` 로 발표된 것 — **알려진 예외를 뺀다.**"""
    return [p for p in feats if p["verdict"] == "clear" and p["nfa_access_listed"] and p["nfa_access_loose"] is False
            and p["seg_uid"] not in KNOWN_EXCEPTIONS]


def test_no_clear_is_published_on_a_tightly_matched_fire_access_road():
    """관문. 걸린 구간 전량을 목록으로 출력한다(느슨한 매칭의 clear 는 경고로만 센다). **알려진 예외 셋은 안 걸린다** — 넷째가 생기면 걸린다."""
    feats = _need()
    bad = violations(feats)
    warn = sum(1 for p in feats if p["verdict"] == "clear" and p["nfa_access_listed"] and p["nfa_access_loose"])
    print(f"\n경고(느슨한 매칭 · 막지 않는다): clear {warn}구간")
    assert not bad, (
        f"소방서가 소방통로 확보 대상으로 지정한 구간(len_ratio {RATIO_LO}~{RATIO_HI} 안)을 clear 로 발표했다 — {len(bad)}구간 "
        f"(정확 일치 · len_ratio 범위 안 · 알려진 예외 {len(KNOWN_EXCEPTIONS)}건 제외):\n  "
        + "\n  ".join(f"{p['seg_id']} {p['seg_uid']} {p['road_name']} wmin={p['width_min_m']} any={p['width_min_any_m']} clear_min={p['clear_min_m']} "
                      f"소방서폭={p['nfa_access_width']} ratio={p['nfa_access_len_ratio']} 원문={p['nfa_access_token']}" for p in bad))


def _synth(uid: str, verdict: str = "clear", listed: bool = True, loose: bool | None = False) -> dict:
    return {"seg_uid": uid, "seg_id": "DM99999", "verdict": verdict, "nfa_access_listed": listed, "nfa_access_loose": loose}


def test_the_known_exceptions_are_skipped_and_a_fourth_clear_is_caught():
    """합성: 예외 셋은 안 걸리고 목록에 없는 넷째는 걸린다 — 그리고 `clear` 가 아니거나 느슨하거나 지정이 아니면 안 걸린다(관문이 다른 것까지 막지 않는다)."""
    three = [_synth(u) for u in KNOWN_EXCEPTIONS]
    assert violations(three) == []
    assert [p["seg_uid"] for p in violations([*three, _synth("DM-000000-000000-ZZZZ")])] == ["DM-000000-000000-ZZZZ"]
    assert violations([_synth("DM-1", verdict="needs_cv"), _synth("DM-2", loose=True), _synth("DM-3", listed=False)]) == []


def test_the_exceptions_are_keyed_by_seg_uid_and_exist_in_the_published_segments():
    """예외 키가 `seg_uid`(`DM-<x>-<y>-<hash>` 꼴)이고 발행본에 실재한다 — `seg_id`(판마다 밀린다)로 적으면 예외가 다른 구간을 덮는다."""
    import re
    feats = _need()
    uids = {p["seg_uid"] for p in feats}
    for u in KNOWN_EXCEPTIONS:
        assert re.fullmatch(r"DM-\d+-\d+-[0-9A-Z]{4}", u), f"seg_uid 꼴이 아니다: {u}"
        assert u in uids, f"예외 {u} 가 발행본에 없다 — 판이 바뀌었으면 예외를 다시 본다"


def test_a_zero_length_row_does_not_divide_by_zero() -> None:
    """소방서 표의 구간거리가 0 이어도 죽지 않는다.  (감사 N10 · Zm20)

    `ratio = total / row["len"]` 이 0 으로 나눠 파이프라인을 세웠다. 비교가 안 되는 줄이므로
    비율은 `None` 이고 **느슨하다**(`loose = True`) — 「정확 일치」로 읽히면 안 된다.
    """
    from firelane import fireaccess as fa

    rows = [dict(text="가나다로", norm="가나다로", len=0.0, width="3.0", hh=1)]
    got = fa.columns(["가나다로"], [50.0], rows)
    assert got["nfa_access_listed"] == [True]
    assert got["nfa_access_len_ratio"] == [None]
    assert got["nfa_access_loose"] == [True]
