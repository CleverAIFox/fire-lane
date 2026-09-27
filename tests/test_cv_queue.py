#!/usr/bin/env python3
"""
test_cv_queue.py — 측량폭이 **순서에만 닿고 판정에는 안 닿는가.**  (PLAN §1 #54 · §273-6)

── 왜 이 모양인가 ──────────────────────────────────────────────
#54 는 교환이었다 — 측량폭을 판정에 넣으면 CV 자원을 아끼지만 **MASTER §2 의
유일한 독립 검증축이 사라진다.** 2026-09-27 에 「판정에는 안 넣고 순서에만」으로
정했고, 그 결정이 지켜지는지는 **규율이 아니라 검사**가 들어야 한다.

★ 그래서 여기가 보는 것은 큐의 순서가 예쁜가가 아니다. 둘이다 —
  ① 층이 실제로 갈리는가 (하나로 뭉개지면 순서가 없는 것과 같다)
  ② **판정 경로가 이 도구를 안 읽는가** (읽는 순간 결정이 뒤집힌다)

IN    tools/cv_queue.py · `shardseal.code_closure`(판정 폐포) · 실제 segments.geojson(있을 때만)
OUT   없음 (검사)
밖    **측량폭이 옳은지는 안 본다** — 그것은 `#4` D-25 실측이 전건이다.
      **큐의 순서가 최선인지도 안 본다** — 통행량 우선이 옳다는 근거는 아직 없다.
      여기가 강제하는 것은 경계 하나와 층의 생사뿐이다.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "data" / "processed" / "segments.geojson"


@pytest.fixture
def q():
    spec = importlib.util.spec_from_file_location("cvq_t", ROOT / "tools" / "cv_queue.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _f(w, usage=0, verdict="needs_cv", feasible=True, length=10.0):
    return {"properties": {"width_min_m": w, "route_usage": usage, "verdict": verdict,
                           "cv_feasible": feasible, "length_m": length}}


# ── ① 층이 갈리는가 ───────────────────────────────────────────
def test_the_three_tiers_are_real(q):
    got = {q.tier(_f(w)["properties"]) for w in (4.0, None, 1.0, 9.0)}
    assert got == set(q.TIERS), f"층이 안 갈린다: {got}"


def test_the_band_edges_are_closed_and_open_the_way_they_are_written(q):
    """3.0 은 띠 **안**, 6.0 은 띠 **밖**. 경계를 뒤집으면 층이 조용히 섞인다."""
    assert q.tier(_f(3.0)["properties"]) == "임계 인접"
    assert q.tier(_f(5.999)["properties"]) == "임계 인접"
    assert q.tier(_f(6.0)["properties"]) == "이미 답함"
    assert q.tier(_f(2.999)["properties"]) == "이미 답함"


def test_segments_that_cannot_get_cv_are_not_in_the_queue(q):
    """CCTV 가 없으면 순서를 매겨도 못 붙인다. 세면 큐가 거짓으로 길어진다."""
    got = q.targets([_f(4.0), _f(4.0, feasible=False), _f(4.0, verdict="clear"),
                     _f(4.0, verdict="blocked")])
    assert len(got) == 1, f"대상 고르기가 샌다: {len(got)}"


def test_within_a_tier_the_busier_segment_comes_first(q):
    got = q.order(q.targets([_f(4.0, 1), _f(4.0, 7), _f(4.0, 3)]))
    assert [p["route_usage"] for p in got] == [7, 3, 1]


def test_the_summary_survives_an_empty_queue(q):
    """★ 실물에서 0 이 될 수 있다(CV 를 다 붙인 날). 그날 도구가 죽으면 안 된다."""
    s = q.summarize([])
    assert s["queue"] == 0 and s["already_answered_pct"] == 0.0


def test_the_selftest_is_not_an_empty_net(q):
    assert q.selftest() == 0


# ── ② 경계 — 판정이 이 도구를 읽는가 ──────────────────────────
def test_no_judgment_module_reads_the_cv_queue(q):
    """★ 이 시험이 이 파일의 본체다.

    측량폭이 판정에 드는 길은 둘뿐이다 — 판정 코드가 `cv_queue` 를 import 하거나,
    그 산출물(CSV)을 읽거나. 둘 다 막는다. 막지 않으면 「순서에만 쓴다」는
    결정이 **주석으로만 남고** 다음 사람이 한 줄로 뒤집는다.
    """
    # ★ 폴더를 훑지 않는다. **폐포에 직접 묻는다** — `src/` 가 곧 판정이라는 것은
    #   추측이고, `golden` 이 지문을 뜨는 범위가 사실이다. 판정에 드는 파일이
    #   늘거나 줄면 이 시험의 범위가 **자동으로** 따라간다.
    from firelane.shardseal import code_closure
    files = set(code_closure("firelane.segments")) | set(code_closure("firelane.ingest"))
    assert len(files) > 10, f"폐포가 {len(files)}개다 — 범위를 못 읽었다면 이 시험은 빈 그물이다"
    bad = []
    for p in sorted(files):
        t = p.read_text(encoding="utf-8")
        for needle in ("cv_queue", "cv_queue.csv"):
            if needle in t:
                bad.append(f"{p.relative_to(ROOT)} 가 `{needle}` 를 든다")
    assert not bad, (
        "판정 폐포가 CV 큐를 읽는다 — 그 순간 측량폭이 판정 입력이 되고 "
        "MASTER §2 의 독립 검증축이 사라진다(PLAN §1 #54).\n  " + "\n  ".join(bad))


def test_the_tool_declares_that_it_does_not_touch_the_verdict(q):
    """선언이 머리말에 있는가. `scopedecl` 의 `밖` 칸과 같은 규율이다."""
    head = (ROOT / "tools" / "cv_queue.py").read_text(encoding="utf-8")[:4000]
    assert "판정을 안 바꾼다" in head, "「판정을 안 바꾼다」 선언이 머리말에 없다"
    assert "밖" in head


# ── 실물 ──────────────────────────────────────────────────────
need_real = pytest.mark.skipif(not SEG.is_file(), reason="산출물이 없다")


@need_real
def test_on_the_real_tree_the_queue_is_not_degenerate(q):
    """실물에서 층이 하나로 몰리면 이 도구는 아무 순서도 안 낸다."""
    rows = q.targets(q.load(SEG))
    assert rows, "판정 대상이 0 이다 — 그러면 #54 는 문제가 아니었다"
    per = q.summarize(rows)["per_tier"]
    nonzero = [t for t in q.TIERS if per[t]]
    assert len(nonzero) >= 2, f"층이 하나뿐이다 — 순서가 없는 것과 같다: {per}"


@need_real
def test_the_queue_only_holds_segments_that_are_still_undecided(q):
    seen = {p["verdict"] for p in q.targets(q.load(SEG))}
    assert seen <= {"needs_cv", "unknown"}, f"판정이 선 구간이 큐에 있다: {seen}"


@need_real
def test_the_csv_is_written_in_queue_order(q, tmp_path):
    out = tmp_path / "q.csv"
    assert q.main(["--out", str(out), "--seg", str(SEG)]) == 0
    lines = out.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) > 1
    rank = {t: i for i, t in enumerate(q.TIERS)}
    tiers = [rank[ln.split(",")[1]] for ln in lines[1:]]
    assert tiers == sorted(tiers), "CSV 가 층 순서대로 안 나온다"


@need_real
def test_the_published_segments_carry_no_queue_column(q):
    """큐가 발행물로 새면 그때부터 화면이 측량폭으로 판정을 읽는다."""
    props = json.loads(SEG.read_text(encoding="utf-8"))["features"][0]["properties"]
    assert not [k for k in props if "queue" in k or "cv_rank" in k], \
        f"발행물에 큐 칸이 있다: {sorted(props)}"
