"""
test_classify.py — 판정 사슬의 분기를 잠근다. (DECISIONS §303)

`seg/geom.py` 의 `verdict()` 를 보는 시험은 이미 있다. 이 파일이 새로 무는
것은 **`verdict()` 가 판정의 전부가 아니라는 것**이다 — `VERDICT_RULE` 일곱
줄 중 둘은 `verdict()` 가 안 낸다. 그 둘이 `segments.main()` 안에 있던 동안
아무 시험도 그것을 직접 보지 않았고, 그래서 산출물 스키마가 그 둘을 부정하는
서술을 달고 나가는 것을 아무도 못 봤다(§305).

IN    src/firelane/seg/classify.py · seg/geom.py(VERDICT_RULE)
OUT   없음
밖    **폭이 옳은가는 안 본다.** `wmin` · `wmax` 를 만드는 일은 `seg/width.py`
      이고 이 파일은 폭이 정해진 뒤의 분기만 든다 — 폭이 전부 틀려도 초록이다.
      **출하된 판정과 대지 않는다.** 그쪽은 `test_classify_published.py` 다.
      임계값이 **옳은 수인가**도 안 본다(3.0 · 7.0 · 25.0 의 근거는 MASTER §18-5).
      분기가 그 상수를 **쓰는가**만 든다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from firelane.seg.classify import CLEAR_M, IMPLEMENTS, LEDGER_BLOCK_M, REASONS, VERDICTS, classify
from firelane.seg.geom import VERDICT_RULE, verdict
from firelane.seg.params import CCTV_RANGE, MIN_SEG_LEN, TRUCK

SRC = Path(__file__).resolve().parents[1] / "src" / "firelane"

#: CCTV 안. 강등 규칙을 끄고 앞쪽 분기만 보려는 자리에서 쓴다.
NEAR = 0.0
FAR = CCTV_RANGE + 0.1


def c(**kw):
    """기본값을 채워 `classify` 를 부른다 — 보려는 인자만 적게 한다."""
    kw.setdefault("wmin", None)
    kw.setdefault("wmax", None)
    kw.setdefault("nreg", 9)
    kw.setdefault("road_bt", None)
    kw.setdefault("length_m", 50.0)
    kw.setdefault("cctv_dist", NEAR)
    return classify(**kw)


# ── 선언과 구현이 맞는가 ────────────────────────────────────────

def test_covers_every_declared_rule():
    """`VERDICT_RULE` 에 줄을 더 적고 구현을 안 하면 운다."""
    assert len(IMPLEMENTS) == len(VERDICT_RULE), (
        f"규칙 문언 {len(VERDICT_RULE)}줄 · 구현 선언 {len(IMPLEMENTS)}줄. "
        "규칙을 적었으면 `classify()` 가 그것을 실행하고 `IMPLEMENTS` 에 번호를 적어라"
    )
    assert tuple(IMPLEMENTS) == tuple(range(len(VERDICT_RULE)))


def test_verdict_alone_is_not_a_verdict():
    """`verdict()` 와 `classify()` 가 갈리는 실례가 있다.

    이 시험이 통과하는 동안은 「`verdict()` 를 부르면 판정이 나온다」가 거짓이다.
    갈리지 않게 되는 날 — 즉 대장폭 규칙과 CCTV 강등이 없어지는 날 — 이
    시험이 울고, 그때 §303 의 근거가 사라졌으므로 지우면 된다.
    """
    # 대장폭 규칙: 담~담이 없고 노면이 좁고 대장도 좁다
    kw = dict(wmin=0.4, wmax=None, nreg=9, road_bt=2.0, length_m=50.0, cctv_dist=NEAR)
    assert verdict(kw["wmin"], kw["wmax"], kw["nreg"]) == "needs_cv"
    assert classify(**kw)[0] == "blocked"
    # CCTV 강등: needs_cv 인데 카메라가 멀다
    kw2 = dict(kw, road_bt=None, cctv_dist=FAR)
    assert verdict(kw2["wmin"], kw2["wmax"], kw2["nreg"]) == "needs_cv"
    assert classify(**kw2)[0] == "unknown"


def test_src_has_exactly_one_judgment_door():
    """`src/` 안에서 `verdict` 를 **부르는** 모듈은 `classify.py` 하나다.

    ★ 이것이 §303 의 본론이다. 실행이 둘이었던 상태로 돌아가는 길을 막는다.
      `geom.verdict()` 를 지우지 않은 대신 그것을 부를 수 있는 자리를 하나로
      잠근다.
    """
    callers = []
    for p in sorted(SRC.rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "verdict"):
                callers.append(p.relative_to(SRC).as_posix())
                break
    assert callers == ["seg/classify.py"], (
        f"판정 문을 여는 자리가 {callers} — 하나여야 한다(§303). "
        "새 자리가 필요하면 `classify()` 를 불러라"
    )


def test_vocabulary_matches_the_schema_enum():
    """산출물 스키마가 열거하는 판정 어휘와 같다. fragment 는 안 나간다."""
    assert set(VERDICTS) == {"blocked", "clear", "needs_cv", "unknown"}
    assert "fragment" not in VERDICTS
    assert set(REASONS) == {"no_cctv_narrow", "no_cctv_thin", "no_cctv_band",
                            "no_cctv_single", "width"}


# ── VERDICT_RULE[1] · 대장폭에 의한 확정 ────────────────────────

def test_ledger_confirms_blocked_when_both_agree():
    assert c(wmin=0.4, wmax=None, road_bt=2.0) == ("blocked", None)
    assert c(wmin=None, wmax=None, road_bt=2.0) == ("blocked", None)


def test_ledger_alone_never_overturns_a_measurement():
    """§3-3 — 대장폭 단독으로 실측을 뒤집지 않는다."""
    # 실측이 3.0 이상이면 대장이 좁아도 blocked 가 아니다
    assert c(wmin=5.0, wmax=None, road_bt=2.0)[0] == "needs_cv"
    # 담~담이 있으면 그것이 이미 판정했다 — 대장이 끼어들지 않는다
    assert c(wmin=0.4, wmax=9.0, road_bt=2.0)[0] == "needs_cv"


def test_ledger_at_the_threshold_does_not_confirm():
    """문턱은 미만이다. 정확히 3.0 인 대장은 확정하지 않는다."""
    assert c(wmin=0.4, wmax=None, road_bt=LEDGER_BLOCK_M)[0] != "blocked"
    assert c(wmin=0.4, wmax=None, road_bt=LEDGER_BLOCK_M - 0.01)[0] == "blocked"


def test_ledger_runs_before_the_cctv_downgrade():
    """★ 순서가 판정을 바꾼다. 뒤에 두면 needs_cv → unknown 으로 먼저 내려가
    이 규칙을 비껴간다 — blocked 는 도면으로 확정되므로 카메라와 무관하다."""
    assert c(wmin=0.4, wmax=None, road_bt=2.0, cctv_dist=FAR) == ("blocked", None)


# ── VERDICT_RULE[6] · CCTV 사각에 의한 강등 ─────────────────────

@pytest.mark.parametrize("wmin,road_bt,want", [
    (None, None, "width"),            # 폭을 아예 못 냈다
    (9.0, None, "no_cctv_single"),    # 7m 이상인데 표본이 하나
    (1.0, 2.0, "no_cctv_narrow"),     # 노면·대장 둘 다 좁다 — 근거 둘
    (1.0, None, "no_cctv_thin"),      # 노면만 좁다 — 근거 하나
    (1.0, 8.0, "no_cctv_thin"),       # 대장은 넓다 — 역시 근거 하나
    (5.0, None, "no_cctv_band"),      # 3~7m. 주정차로 갈린다
])
def test_reason_splits_the_grey(wmin, road_bt, want):
    nreg = 1 if want == "no_cctv_single" else 9
    # wmax 를 넉넉히 줘 대장폭 규칙이 끼어들지 않게 한다
    v, r = c(wmin=wmin, wmax=99.0, nreg=nreg, road_bt=road_bt, cctv_dist=FAR)
    assert (v, r) == ("unknown", want)


def test_clear_and_blocked_ignore_the_camera():
    """도면만으로 확정되는 둘은 CCTV 거리에 안 움직인다."""
    for dist in (NEAR, FAR, 9999.0):
        assert c(wmin=CLEAR_M, wmax=99.0, nreg=9, cctv_dist=dist) == ("clear", None)
        assert c(wmax=1.0, cctv_dist=dist) == ("blocked", None)


def test_the_threshold_is_exclusive():
    """정확히 25.0m 는 사각이 아니다."""
    assert c(wmin=5.0, wmax=99.0, cctv_dist=CCTV_RANGE)[0] == "needs_cv"
    assert c(wmin=5.0, wmax=99.0, cctv_dist=CCTV_RANGE + 0.1)[0] == "unknown"


# ── 중간 상태 fragment ──────────────────────────────────────────

def test_fragment_needs_both_short_and_no_width():
    assert c(wmin=None, length_m=MIN_SEG_LEN - 0.1)[0] == "fragment"
    # 짧지만 폭이 있으면 파편이 아니다
    assert c(wmin=5.0, wmax=99.0, length_m=MIN_SEG_LEN - 0.1)[0] == "needs_cv"
    # 폭이 없지만 길면 파편이 아니다 — unknown/width 다
    assert c(wmin=None, length_m=MIN_SEG_LEN) == ("unknown", "width")


def test_fragment_can_still_be_confirmed_blocked_by_the_ledger():
    """★ 순서의 결과다. 파편 표시가 대장 확정을 막지 않는다 — 막으면
    3m 미만 조각이 상속에 실패했을 때 unknown 으로 떨어져, 대장이 좁다고
    말하는 근거가 버려진다."""
    assert c(wmin=None, road_bt=2.0, length_m=1.0) == ("blocked", None)


# ── 상수가 흩어지지 않았는가 ────────────────────────────────────

def test_constants_come_from_the_single_source():
    assert LEDGER_BLOCK_M == TRUCK
    assert CLEAR_M == 7.0
    # clear 문턱이 대장 문턱보다 넓다. 같아지면 두 규칙이 구별되지 않는다.
    assert CLEAR_M > LEDGER_BLOCK_M
