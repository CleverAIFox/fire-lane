"""
test_classify_published.py — 공개된 판정을 `classify()` 로 **되풀어** 댄다.
(DECISIONS §303)

── 이 시험이 무는 것 ──────────────────────────────────────────
§303 은 사슬 일곱 줄을 `segments.main()` 밖으로 옮겼다. 「로직을 한 줄도
안 바꿨다」는 주장이고, 주장은 재야 한다. 보통 그 증거는
`tools/golden.py` 의 산출물 동일이지만 그것은 **호수가 있는 기계에서만**
난다.

여기서는 다른 증거를 쓴다 — 공개본 `web/data/segments.geojson` 은 판정의
**입력 전부**를 들고 있다(`width_min_m` · `width_max_m` · `n_sample` ·
`road_bt_m` · `length_m` · `cctv_dist_m`). 그래서 파이프라인 없이 1,281행을
다시 먹여 `verdict` · `unknown_reason` 두 열과 댈 수 있다.

★ 골든보다 약한 증거가 아니다. 골든은 「같은 입력으로 같은 파일이 나오는가」
  이고 이것은 「**출하된 답이 규칙으로 설명되는가**」다. 후자는 사슬 밖의
  손질(사후 덮어쓰기·특례)까지 잡는다 — 실제로 `fragment` 의 사후 전환이
  이 시험에 걸려 드러났다.

★ 그리고 이 시험은 **규칙이 바뀌어도 산다.** 규칙을 고치면 공개본도 함께
  다시 나므로 양쪽이 같이 움직인다. 한쪽만 움직이면 운다 — 즉 이것은
  「판정 규칙」과 「출하된 판정」 사이의 정합 관문이다.

── 안 무는 것 ────────────────────────────────────────────────
`width_min_m` 이 **옳은가**는 안 본다. 폭을 만드는 일은 `seg/width.py` 이고
이 시험은 폭이 정해진 뒤의 분기만 든다. 폭이 전부 틀려도 이 시험은 초록이다.

IN    web/data/segments.geojson (추적됨) · src/firelane/seg/classify.py
OUT   없음
밖    **폭·표본·CCTV 거리의 값이 옳은가는 안 본다.** 공개본이 든 값을 그대로
      되먹인다 — 입력이 틀렸어도 「규칙으로 설명되는가」는 참일 수 있다.
      **`data/processed/` 를 안 읽는다.** 그쪽은 추적되지 않아 CI 에 없다.
      **골든을 대신하지 않는다.** 같은 입력으로 같은 파일이 나오는가는
      `tools/golden.py` 가 든다.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from firelane.seg.classify import REASONS, VERDICTS, classify

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "web" / "data" / "segments.geojson"

#: 사슬이 낸 뒤 `segments.main()` 이 **사후에** 손대는 전환.
#: 파편은 인접 상속을 시도하고 실패하면 unknown/width 로 떨어진다. 그래서
#: 공개본에 fragment 는 없고, 이 시험은 그 전환을 알고 있어야 한다.
POST = {"fragment": ("unknown", "width")}


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    d = json.loads(PUB.read_text(encoding="utf-8"))
    r = [f["properties"] for f in d["features"]]
    assert r, "공개본이 비었다"
    return r


def _again(p: dict) -> tuple[str, str | None]:
    v, reason = classify(
        wmin=p["width_min_m"], wmax=p["width_max_m"], nreg=p["n_sample"],
        road_bt=p["road_bt_m"], length_m=p["length_m"], cctv_dist=p["cctv_dist_m"],
        wmin_any=p.get("width_min_any_m"), wsym=p.get("width_min_sym_m"), clear_med=p.get("clear_med_m"),      # 규칙 [8] · [9] · [10] · [11]
    )
    return POST.get(v, (v, reason))


def test_every_verdict_is_reproduced(rows):
    bad = [(p["seg_id"], p["verdict"], _again(p)[0])
           for p in rows if _again(p)[0] != p["verdict"]]
    assert not bad, (
        f"출하된 판정 {len(bad)}/{len(rows)} 건이 규칙으로 설명되지 않는다. "
        f"처음 다섯: {bad[:5]}"
    )


def test_every_reason_is_reproduced(rows):
    """회색 사유(`unknown_reason`)와 needs_cv 의 이유(`cv_reason`)를 **각자의 칸**에서 되풀이해 댄다 — 두 칸을 섞지 않는다(Zm6)."""
    def pub(p):
        return p["unknown_reason"] if p["verdict"] == "unknown" else p.get("cv_reason")
    bad = [(p["seg_id"], pub(p), _again(p)[1]) for p in rows if _again(p)[1] != pub(p)]
    assert not bad, f"회색 사유 {len(bad)}/{len(rows)} 건 불일치. 처음 다섯: {bad[:5]}"


def test_published_vocabulary_is_the_declared_one(rows):
    """공개본에 선언 밖의 낱말이 없다."""
    assert set(p["verdict"] for p in rows) <= set(VERDICTS)
    seen = set(p["unknown_reason"] for p in rows) - {None}
    assert seen <= set(REASONS)


def test_grey_always_carries_a_reason(rows):
    """회색인데 사유가 없으면 화면이 「왜 회색인가」를 못 말한다."""
    assert [p["seg_id"] for p in rows
            if p["verdict"] == "unknown" and p["unknown_reason"] is None] == []
    assert [p["seg_id"] for p in rows
            if p["verdict"] != "unknown" and p["unknown_reason"] is not None] == []


#: 대장폭 규칙(`VERDICT_RULE[1]`)이 만든 `blocked` 구간 수의 **천장**(양방향 래칫). DECISIONS §718.
#: ★ 이 수는 「문서에 적힌 폭(대장)에 기대어 막은 구간」이다. **늘면 판정이 문서 의존으로 되돌아간 것**이라 운다. **줄면 기록을 내린다**(측정 의존으로 옮겼다는 뜻 — 좋은 쪽).
#:   올리지 않는다 — 올릴 일이 생기면 그 재잠금이 왜 문서 의존을 늘렸는지가 먼저다.
LEDGER_FORCED = 62


def _ledger_forced(rows):
    """공개된 `blocked` 중 순수 폭 판정(`verdict()`)이 안 내는 구간 = 대장폭 규칙이 만든 것. 규칙 둘뿐이라(`classify`) 정의가 정확하다."""
    from firelane.seg.geom import verdict as pure
    blocked = [p for p in rows if p["verdict"] == "blocked"]
    forced = [p for p in blocked if pure(p["width_min_m"], p["width_max_m"], p["n_sample"]) != "blocked"]
    return forced, len(blocked)


def test_the_ledger_rule_is_alive(rows):
    """★ **규칙이 죽지 않았는가.** 0 이면 대장폭을 아무도 안 읽는다 — 그것도 결함이다(노면이 안 재진 좁은 길을 문서 한 줄이 막던 자리다).

    이 시험은 §305 의 사실 — 「판정에 쓰지 않는다」고 서술된 열이 판정에 쓰인다 — 이 **조용히 사라지는 것**을 막는다(규칙을 지우면 0 이 되어 운다).
    ★ 몫(`> 0.5`)은 과녁이 아니었다 — §305 의 「과반」 서술에서 온 파생이다. **높을수록 좋다는 전제는 뒤집혔다**(DECISIONS §718): 측정이 더 막고 문서가 덜 막는 쪽이 좋다.
    """
    forced, n_blocked = _ledger_forced(rows)
    assert forced, "대장폭 규칙이 만드는 blocked 가 0 이다 — 규칙이 죽었거나 데이터가 바뀌었다"
    assert n_blocked, "blocked 가 하나도 없다"


def test_document_dependence_does_not_grow(rows):
    """★ **문서 의존이 늘지 않는가**(양방향 래칫). 대장폭(문서에 적힌 수)에 기대어 막은 구간 수가 천장 `LEDGER_FORCED` 와 같아야 한다.

    ★ 몫이 아니라 **개수**다: 몫은 분모(`blocked` 총수)가 측정으로 늘면 문서 의존이 **늘어도** 내려가 나쁜 방향을 가린다
      (예: 문서 62 → 90, 측정 122 → 250 이면 몫은 34% → 26% 로 내려간다). 문서에 기댄 구간의 **절대 수**가 노출이다.
    ★ 올라가면 우는 것이 방향이다 — 그리고 **내려가도 기록을 안 내리면 운다**(느슨해진 래칫은 초록으로 위장한다). 몫은 메시지에만 싣는다.
    """
    forced, n_blocked = _ledger_forced(rows)
    n = len(forced)
    assert n <= LEDGER_FORCED, (
        f"대장폭 규칙이 만든 blocked 가 {n} 로 늘었다 — 천장 {LEDGER_FORCED} (몫 {n}/{n_blocked} = {n / n_blocked:.0%}). "
        "판정이 측정에서 문서로 되돌아갔다. 올리지 않는다 — 왜 늘었는지를 먼저 적는다(DECISIONS §718)")
    assert n >= LEDGER_FORCED, (
        f"대장폭 규칙이 만든 blocked 가 {n} 으로 줄었다(몫 {n / n_blocked:.0%}) — 측정 의존으로 옮긴 것이다. "
        f"{Path(__file__).name} 의 LEDGER_FORCED 를 {n} 으로 내려 기록을 조여라")
    # 그 구간들은 전부 담~담이 없다 — 규칙의 전제다
    assert all(p["width_max_m"] is None for p in forced)


def test_the_forced_count_separates_measurement_from_the_ledger():
    """★ 합성 입력으로 **정의를 문다** — 담~담이 3m 미만이라 측정이 막은 구간은 세지 않고, 담~담이 없어 대장폭이 막은 구간만 센다.

    실물만 먹이면 초록인 채로 정의가 틀려도 모른다(위 두 시험은 지금 값에서 초록이다) — 두 시험이 **무엇을 세는지**를 여기서 따로 댄다.
    """
    measured = {"verdict": "blocked", "width_min_m": 2.0, "width_max_m": 2.5, "n_sample": 5}      # 담~담 2.5m — 측정이 막았다
    ledger = {"verdict": "blocked", "width_min_m": 2.0, "width_max_m": None, "n_sample": 5}       # 담~담 없음 — 대장폭 규칙이 막았다
    not_blocked = {"verdict": "clear", "width_min_m": 8.0, "width_max_m": None, "n_sample": 5}
    forced, n_blocked = _ledger_forced([measured, ledger, ledger, not_blocked])
    assert len(forced) == 2 and n_blocked == 3, (len(forced), n_blocked)
    assert _ledger_forced([measured, not_blocked])[0] == [], "측정이 막은 구간을 문서 의존으로 셌다"


def test_counts_are_stated_not_assumed(rows):
    """판정 네 갈래의 수와 구간 수가 **골든 지문과 같다.** 발행본이 낡았든 지문이 낡았든 운다.

    ★ 이 수를 PR 본문·문서가 매번 인용하는데 인용이 낡는 것을 아무도 못 봤다. 정본은 `data/golden/segments.fingerprint.json`
      이고 `docs/` 는 그것을 베낀다(`docgen`). 종전에는 여기에도 손으로 적었다 — 아래 주석이 그 경위다.
    """
    c = collections.Counter(p["verdict"] for p in rows)
    # ★ 2026-11-04 (DECISIONS §621). 수를 **손으로 적지 않는다** — 골든 지문(`segments.fingerprint.json` L1)이 정본이다.
    #   종전에는 `1281` · `{192, 274, 283, 532}` 를 여기 적었고 재잠금마다 손으로 고쳤다(2026-11-04 접속선 재판정이 또 낡게 했다).
    #   지문은 `golden.py lock`(사람)이 찍고 `golden.py check` 가 발행본과 대므로, 이 시험은 **발행본 == 지문**을 한 번 더 문다 —
    #   어느 쪽이 낡든 운다. 수 자체의 옳음은 지문의 몫이다.
    fp = json.loads((Path(__file__).resolve().parents[1] / "data" / "golden" / "segments.fingerprint.json").read_text(encoding="utf-8"))["L1"]
    assert len(rows) == fp["n"]
    assert dict(c) == fp["verdict"]


# ── 이름과 실물 (DECISIONS §320) ────────────────────────────────

def test_the_published_building_number_is_not_used_as_a_join_key():
    """★ **이름이 거짓말하는 칸**(DECISIONS §320). 아무도 아직 안 믿고 있는가.

    도로명주소 전자지도의 `BUL_MAN_NO`(건물관리번호)는 25자리 문자열이다.
    발행본의 같은 이름 칸은 **정수 20~38,762**(고유 12,663)다 — 원천 키가
    아니라 발행본 안에서만 유효한 지역 번호이고, 다시 발행하면 달라진다.

    ★ `route_usage` 와 같은 족이다(아래 시험). 스키마는 거짓을 안 적었지만
      **이름이 읽는 사람을 속인다.** 지금은 쓰는 곳이 0곳이라 사고가 안 났고,
      그것을 지키는 것이 이 시험이다 — 이름을 고치는 일은 발행 스키마를
      움직이므로 측정 배치의 것이다(§13-5 규칙 2 · PLAN 이 든다).
    """
    seen = []
    for d in ("web/navi/src", "web/navi/test", "src/firelane", "tools"):
        for f in sorted((ROOT / d).rglob("*")):
            if f.suffix not in (".ts", ".tsx", ".py") or "__pycache__" in f.parts:
                continue
            for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if "BUL_MAN_NO" not in ln:
                    continue
                # 발행하는 자리 하나와 이 시험 자신은 뺀다 — 거기가 그 칸을 **만든다**.
                if f.name in ("publish_web.py", Path(__file__).name):
                    continue
                seen.append(f"{f.relative_to(ROOT)}:{i}  {ln.strip()[:70]}")
    assert not seen, (
        "발행본의 `BUL_MAN_NO` 를 읽는 자리가 생겼다 — **원천 건물관리번호가 아니다.**\n  "
        + "\n  ".join(seen)
        + "\n  재발행하면 값이 달라진다. 조인이 필요하면 도로명주소를 써라(§320).")
