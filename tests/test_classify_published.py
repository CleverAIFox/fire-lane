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

PUB = Path(__file__).resolve().parents[1] / "web" / "data" / "segments.geojson"

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
    bad = [(p["seg_id"], p["unknown_reason"], _again(p)[1])
           for p in rows if _again(p)[1] != p["unknown_reason"]]
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


def test_the_ledger_rule_is_load_bearing(rows):
    """★ 이 수가 §305 의 근거다 — 「판정에 쓰지 않는다」고 서술된 열 하나가
    blocked 의 과반을 **혼자** 만든다. 이 시험은 그 사실이 조용히 사라지는
    것을 막는다(규칙을 지우면 여기서 0 이 되어 운다).
    """
    from firelane.seg.geom import verdict as pure
    forced = [p for p in rows
              if p["verdict"] == "blocked"
              and pure(p["width_min_m"], p["width_max_m"], p["n_sample"]) != "blocked"]
    n_blocked = sum(1 for p in rows if p["verdict"] == "blocked")
    assert forced, "대장폭 규칙이 만드는 blocked 가 0 이다 — 규칙이 죽었거나 데이터가 바뀌었다"
    share = len(forced) / n_blocked
    assert share > 0.5, (
        f"대장폭 규칙이 만드는 blocked 가 {len(forced)}/{n_blocked} ({share:.0%}). "
        "과반 아래로 내려갔으면 §305 의 서술을 다시 재라"
    )
    # 그 구간들은 전부 담~담이 없다 — 규칙의 전제다
    assert all(p["width_max_m"] is None for p in forced)


def test_counts_are_stated_not_assumed(rows):
    """판정 네 갈래의 수를 적어둔다. 바뀌면 운다 — 재잠금과 함께 고칠 값이다.

    ★ 이 수를 여기 적는 이유는 PR 본문·문서가 매번 이 넷을 인용하는데
      그 인용이 낡는 것을 아무도 못 봤기 때문이다. 이제 여기가 정본이고
      `docs/` 는 이것을 베낀다.
    """
    c = collections.Counter(p["verdict"] for p in rows)
    assert len(rows) == 1281
    assert dict(c) == {"clear": 465, "needs_cv": 226, "blocked": 191, "unknown": 399}
