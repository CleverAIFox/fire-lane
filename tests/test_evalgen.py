#!/usr/bin/env python3
"""
test_evalgen.py — 평가지표 산출기의 강제자. **게이트가 정말로 막는가.**

── 왜 이 모양인가 ──────────────────────────────────────────────
`tools/evalgen.py` 의 값은 게이트가 살아 있을 때만 뜻이 있다. 게이트가
죽으면 낡은 산출물에서 뽑은 숫자가 나오고, 그 숫자는 「지표」라는 이름
때문에 아무도 의심하지 않는다(PLAN §1 #91). 그래서 이 파일이 세는 것은
지표값이 아니라 **게이트가 합성 결함에 빨개지는가**다.

★ 실제 트리에서 0건이면 그것은 청결이지 생사가 아니다(`deadcheck` 머리말과
  같은 규율). 생사는 **일부러 어긋낸 합성 트리**에서 묻는다 — 게이트 셋을
  하나씩 따로 깨서, 깬 그 팔만 우는지까지 본다. 셋이 한꺼번에 울면
  「어느 팔이 살아 있나」를 모른다.

★ 「목표에 닿는 날 빨개지는 검사」가 둘 있다.
  ① `test_spec_guard_wakes_when_turn_radius_is_verified`
     회전반경이 검증되는 날 게이트 ③ 의 통행 가능 대조가 낡는다. 그날 운다.
  ② `test_scenario_corner_condition_is_declared_vacuous`
     지금 코너 조건은 아무것도 안 거른다. 거르기 시작하면 선언이 거짓이 되고
     그날 운다.

IN    tools/evalgate.py · tools/evalgen.py · 합성 트리(tmp_path) · 실제 data/ (있을 때만)
OUT   없음 (검사)
PARAM LON0 · LAT0 · 합성 구간 셋
밖    **지표값이 옳은지는 안 본다.** 「진입 실패 81%」가 참인지는 이 검사가
      못 판정한다 — 그것을 판정하려면 정답이 있어야 하고, 정답이 있으면
      지표가 필요 없다. 여기가 보는 것은 ① 게이트가 합성 결함에 우는가
      ② 역산 규칙이 문턱·우회로·CCTV 셋을 실제로 거르는가 ③ 같은 입력이
      같은 산출을 내는가 셋이다. **성능도 안 본다.**
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import evalgate as gt
import evalgen as ev
import pytest
from localgeo import MX, MY

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data"
TAG = "synth-0001"

#: 합성 트리의 기준점. 대인119안전센터 바로 옆이라 스냅이 A 노드로 간다.
LON0, LAT0 = 126.9150, 35.1546

HAVE_REAL = ((REAL / "processed" / "segments.geojson").is_file()
             and (REAL / "golden" / "segments.fingerprint.json").is_file())
need_real = pytest.mark.skipif(
    not HAVE_REAL,
    reason="환경skip(산출물) — data/processed · data/golden 이 없다. 파이프라인 전이다")


# ── 합성 트리 ──────────────────────────────────────────────────
def _east(m: float) -> float:
    return LON0 + m / MX


def _north(m: float) -> float:
    return LAT0 + m / MY


def _feat(uid: str, seg_id: str, coords: list, verdict: str, wmin: float | None,
          length: float, *, cv: bool = True, label: str = "", usage: int = 0) -> dict:
    """구간 하나. 필드는 `golden.FIELDS` · `baseline.tally` 가 보는 것 전부다."""
    return {
        "type": "Feature",
        "properties": {
            "seg_uid": uid, "seg_id": seg_id, "verdict": verdict,
            "width_min_m": wmin, "width_max_m": None, "width_src": "ngii1k",
            "unknown_reason": None if verdict != "unknown" else "no_cctv_band",
            "length_m": length, "route_usage": usage,
            "cv_feasible": cv, "cctv_dist_m": 10.0 if cv else 90.0,
            "seg_label": label or seg_id, "road_name": "합성로",
            "in_emd": True, "nfa_designated": False, "width_verified": False,
        },
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def _three(detour_m: float, *, pinch_cv: bool, with_detour: bool) -> list[dict]:
    """A—C 직통은 못 지나가고, A—B—C 우회는 지나간다.

        d1 = 100m (직통)   ·   d2 = detour_m (우회)   ·   비율 = detour_m / 100
    """
    a = [LON0, LAT0]
    b = [_east(50), _north(40)]
    c = [_east(100), LAT0]
    feats = [_feat("SY-0001", "SY00001", [a, c], "needs_cv", 1.2, 100.0,
                   cv=pinch_cv, label="목 구간", usage=7)]
    if with_detour:
        feats += [
            _feat("SY-0002", "SY00002", [a, b], "clear", 8.0, detour_m / 2, label="우회 앞"),
            _feat("SY-0003", "SY00003", [b, c], "clear", 8.0, detour_m / 2, label="우회 뒤"),
        ]
    return feats


def _write_tree(root: Path, feats: list[dict]) -> Path:
    """`processed` · `golden` · `baseline/<태그>` 를 갖춘 트리를 짓는다."""
    proc, gold, base = root / "processed", root / "golden", root / "baseline" / TAG
    for d in (proc, gold, base):
        d.mkdir(parents=True, exist_ok=True)
    _put_segments(proc, feats)
    (base / "segments.geojson").write_text(
        (proc / "segments.geojson").read_text(encoding="utf-8"), encoding="utf-8")
    (proc / "_manifest.json").write_text(json.dumps({
        "generated_at": "2026-09-25T00:00:00+09:00",
        "standard_crs": {"metric": "EPSG:5186", "display": "EPSG:4326"},
        "datasets": [{"key": "synth", "status": "OK", "outputs": ["segments.geojson"]}],
    }, ensure_ascii=False), encoding="utf-8")
    (gold / "segments.fingerprint.json").write_text(
        json.dumps(gt.fingerprint(proc), ensure_ascii=False), encoding="utf-8")
    return root


def _put_segments(proc: Path, feats: list[dict]) -> None:
    """`segments.geojson` 과 짝이 맞는 `route_vehicle.csv` 를 같이 쓴다."""
    (proc / "segments.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
        encoding="utf-8")
    lines = ["seg_uid,seg_id,route_vehicle,cost,passable,reachable"]
    for f in feats:
        p = f["properties"]
        c = gt.edge_cost_of(p)
        ok = 0 if c == math.inf else 1
        lines.append(f"{p['seg_uid']},{p['seg_id']},0,"
                     f"{10000000.0 if not ok else round(c, 1)},{ok},1")
    (proc / "route_vehicle.csv").write_text(
        "﻿" + "\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """정상 합성 트리. 게이트 셋이 전부 초록인 자리에서 출발한다."""
    return _write_tree(tmp_path, _three(200.0, pinch_cv=True, with_detour=True))


def _gate(root: Path) -> list[str]:
    return gt.gate(root / "processed", root / "golden", root / "baseline", TAG)[1]


def _build(root: Path) -> tuple[dict, list[str]]:
    return ev.build(root / "processed", root / "golden", root / "baseline", TAG)


# ── 양성 대조 — 정상 트리에서는 안 운다 ────────────────────────
def test_clean_synthetic_tree_passes_the_gate(tree):
    """정상 입력에서 우는 게이트는 사람이 끈다. 먼저 이것부터 본다."""
    assert _gate(tree) == []


def test_clean_tree_yields_metrics(tree):
    """게이트가 통과하면 지표가 나온다. 세 블록이 다 있어야 한다."""
    doc, why = _build(tree)
    assert why == []
    assert {"E1", "E3", "scenarios", "tally", "gate", "sha256"} <= set(doc)


# ── ① 지문 ─────────────────────────────────────────────────────
def test_fingerprint_arm_cries_alone(tree):
    """잠근 뒤 구간 값을 바꾸면 **지문 팔만** 운다.

    `width_max_m` 을 고른 이유 — L2 에는 들고 L1 집계·판정 전이·통행 가능
    대조에는 안 든다. 한 팔만 깨야 그 팔이 살아 있는지 알 수 있다.
    """
    p = tree / "processed" / "segments.geojson"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["features"][0]["properties"]["width_max_m"] = 12.34
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    why = _gate(tree)
    assert why, "지문이 갈렸는데 게이트가 조용하다"
    assert any("L2" in w for w in why), why
    assert not any("판정이 움직인" in w or "passable" in w for w in why), (
        "지문 말고 다른 팔까지 울었다 — 어느 팔이 산 것인지 알 수 없다", why)


def test_missing_lock_is_not_a_silent_pass(tree):
    """지문 파일이 아예 없으면 **통과가 아니라 실패**다."""
    (tree / "golden" / "segments.fingerprint.json").unlink()
    why = _gate(tree)
    assert any("지문이 없다" in w for w in why), why


def test_geometry_change_trips_l3(tree):
    """좌표만 흔들어도 L3 가 운다. 판정 값은 그대로다."""
    p = tree / "processed" / "segments.geojson"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["features"][0]["geometry"]["coordinates"][1][0] += 0.0005
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert any("L3" in w for w in _gate(tree)), _gate(tree)


# ── ② 전이행렬 ────────────────────────────────────────────────
def test_transition_arm_cries_alone(tree):
    """**봉인 쪽** 판정을 바꾸면 전이 팔만 운다. 현재 산출물은 안 건드린다."""
    p = tree / "baseline" / TAG / "segments.geojson"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["features"][0]["properties"]["verdict"] = "blocked"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    why = _gate(tree)
    assert any("판정이 움직인 구간" in w for w in why), why
    assert not any("L1" in w or "L2" in w or "L3" in w for w in why), why


def test_transition_sees_a_changed_seg_uid(tree):
    """`seg_uid` 가 갈리면 실행 간 비교가 성립하지 않는다 — 그것도 불일치다."""
    p = tree / "baseline" / TAG / "segments.geojson"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["features"][0]["properties"]["seg_uid"] = "SY-9999"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert any("seg_uid 가 갈렸다" in w for w in _gate(tree)), _gate(tree)


def test_no_baseline_is_not_a_silent_pass(tmp_path):
    """봉인이 하나도 없으면 전이 대조가 **없는 것**이고, 없는 것은 통과가 아니다."""
    root = _write_tree(tmp_path, _three(200.0, pinch_cv=True, with_detour=True))
    for f in (root / "baseline" / TAG).iterdir():
        f.unlink()
    assert gt.newest_tag(root / "baseline") is None
    why = gt.gate(root / "processed", root / "golden", root / "baseline", None)[1]
    assert any("봉인이 하나도 없다" in w for w in why), why


def test_newest_tag_picks_the_latest(tmp_path):
    """태그는 `YYYYMMDD-…` 라 사전순이 곧 시간순이다."""
    base = tmp_path / "baseline"
    for t in ("20260814-a", "20260918-z", "20260901-m"):
        (base / t).mkdir(parents=True)
        (base / t / "segments.geojson").write_text("{}", encoding="utf-8")
    assert gt.newest_tag(base) == "20260918-z"


def test_a_tag_without_segments_is_not_a_tag(tmp_path):
    """봉인 폴더만 있고 산출물이 없으면 대조 대상이 아니다."""
    (tmp_path / "baseline" / "20260999-empty").mkdir(parents=True)
    assert gt.newest_tag(tmp_path / "baseline") is None


# ── ③ 매니페스트 · 산출물 신선도 ──────────────────────────────
def test_manifest_missing_output_cries(tree):
    """매니페스트가 냈다고 적은 파일이 없으면 processed 가 반쪽이다."""
    p = tree / "processed" / "_manifest.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["datasets"][0]["outputs"].append("없는파일.geojson")
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert any("산출물 1개가 없다" in w for w in _gate(tree)), _gate(tree)


def test_manifest_without_generated_at_cries(tree):
    """언제 만든 것인지 모르는 매니페스트는 신선도를 증명하지 못한다."""
    p = tree / "processed" / "_manifest.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    del d["generated_at"]
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert any("generated_at" in w for w in _gate(tree)), _gate(tree)


def test_missing_manifest_is_not_a_silent_pass(tree):
    (tree / "processed" / "_manifest.json").unlink()
    assert any("매니페스트가 없다" in w for w in _gate(tree)), _gate(tree)


def test_stale_route_vehicle_cries(tree):
    """`passable` 이 `edge_cost` 와 갈리면 두 파일이 다른 실행의 것이다."""
    p = tree / "processed" / "route_vehicle.csv"
    txt = p.read_text(encoding="utf-8-sig").replace(",0,1\n", ",1,1\n", 1)
    p.write_text("﻿" + txt, encoding="utf-8")
    why = _gate(tree)
    assert any("passable" in w for w in why), why


def test_route_vehicle_missing_a_segment_cries(tree):
    """구간 집합이 갈리면 경로 지표가 조용히 일부만 센다."""
    p = tree / "processed" / "route_vehicle.csv"
    rows = p.read_text(encoding="utf-8-sig").splitlines()
    p.write_text("﻿" + "\n".join(rows[:-1]) + "\n", encoding="utf-8")
    assert any("구간 집합이 갈렸다" in w for w in _gate(tree)), _gate(tree)


def test_missing_route_vehicle_is_not_a_silent_pass(tree):
    (tree / "processed" / "route_vehicle.csv").unlink()
    assert any("경로 산출물이 없다" in w for w in _gate(tree)), _gate(tree)


def test_spec_guard_wakes_when_turn_radius_is_verified(tree, monkeypatch):
    """★ **목표에 닿는 날 빨개지는 검사.**

    `turn_radius_verified` 가 켜지는 순간 `edge_cost` 가 곡률을 보기 시작하고,
    곡률을 안 넣는 게이트 ③ 의 통행 가능 대조는 그날로 낡는다. 지금 조용한
    이유는 플래그가 false 라서이지 대조가 옳아서가 아니다 — 그 구별을
    사람 기억에 맡기지 않는다.
    """
    real = dict(gt.V.spec())
    monkeypatch.setattr(gt.V, "spec", lambda: dict(real, turn_radius_verified=True))
    why = _gate(tree)
    assert any("곡률이 들기 시작" in w for w in why), why


def test_spec_guard_is_quiet_while_both_flags_are_false():
    """플래그가 false 인 동안은 조용해야 한다. 늘 우는 경보는 꺼진다."""
    assert gt.spec_guard() == []


# ── 산출기가 **안 쓰고 죽는가** ────────────────────────────────
def test_generator_writes_nothing_when_the_gate_cries(tree, tmp_path):
    """게이트가 울면 파일이 **생기지 않는다.** 경고만 찍고 계속 가지 않는다."""
    p = tree / "processed" / "segments.geojson"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["features"][0]["properties"]["verdict"] = "blocked"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    out = tmp_path / "eval-out.json"
    rc = ev.main(["--data", str(tree), "--out", str(out), "--baseline", TAG])
    assert rc == 2, "게이트가 울었는데 산출기가 0 으로 끝났다"
    assert not out.exists(), "게이트가 울었는데 파일을 썼다"


def test_build_returns_no_metrics_when_the_gate_cries(tree):
    """실패 반환값에 지표 블록이 섞여 있으면 호출자가 그것을 쓴다."""
    (tree / "processed" / "_manifest.json").unlink()
    doc, why = _build(tree)
    assert why
    assert set(doc) == {"gate"}, doc.keys()


def test_generator_writes_when_the_gate_passes(tree, tmp_path):
    out = tmp_path / "eval-out.json"
    assert ev.main(["--data", str(tree), "--out", str(out), "--baseline", TAG]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["gate"]["passed"] is True
    assert doc["produced_by"] == "tools/evalgen.py"


def test_gate_tool_returns_two_on_mismatch(tree, capsys):
    """`evalgate.py` 는 불일치에서 2 로 끝난다. **종료코드가 곧 관문이다.**"""
    (tree / "processed" / "_manifest.json").unlink()
    assert gt.main(["--data", str(tree), "--baseline", TAG]) == 2
    assert "게이트 불일치" in capsys.readouterr().out


def test_gate_tool_returns_zero_when_clean(tree):
    assert gt.main(["--data", str(tree), "--baseline", TAG]) == 0


def test_gate_tool_json_is_machine_readable(tree, capsys):
    """`--json` 은 사람 문장이 아니라 보고를 낸다 — 다른 도구가 읽는 자리다."""
    assert gt.main(["--data", str(tree), "--baseline", TAG, "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["passed"] is True
    assert rep["transition"]["moved"] == 0


# ── #120 역산 규칙 ────────────────────────────────────────────
def _sites(root: Path) -> dict:
    doc, why = _build(root)
    assert why == [], why
    return doc["scenarios"]


def test_inversion_finds_the_pinch(tree):
    """d2/d1 = 2.0 인 자리는 잡힌다. 목은 통행 불가 구간이다."""
    s = _sites(tree)
    assert s["sites"] >= 1, s
    row = s["rows"][0]
    assert row["pinch_seg_uid"] == "SY-0001"
    assert row["ratio"] == pytest.approx(2.0, abs=0.01)
    assert row["d1_m"] == pytest.approx(100.0, abs=0.5)
    assert row["dest_lon"] == pytest.approx(_east(100), abs=1e-4)


def test_inversion_respects_the_threshold(tmp_path):
    """비율 1.2 는 문턱 아래다. **문턱이 사문이면 전 구간이 시나리오가 된다.**"""
    root = _write_tree(tmp_path, _three(120.0, pinch_cv=True, with_detour=True))
    assert _sites(root)["sites"] == 0


def test_inversion_needs_a_detour(tmp_path):
    """우회로가 없으면 `d2 = inf` 다. 갇힌 것은 「우리가 없었으면」이 아니라 지금도 못 간다."""
    root = _write_tree(tmp_path, _three(200.0, pinch_cv=True, with_detour=False))
    s = _sites(root)
    assert s["pairs"] == 0, s
    assert s["sites"] == 0


def test_cctv_condition_filters_but_does_not_hide(tmp_path):
    """CCTV 가 없으면 **조건 충족에서 빠질 뿐** 자리 목록에서 사라지지 않는다.

    ★ 걸러서 지우면 「왜 그 골목이 아닌가」에 답할 자료가 없어진다.
      결손은 분모에서 빼지 말고 따로 적는다(PLAN §1 #94 와 같은 규율).
    """
    root = _write_tree(tmp_path, _three(200.0, pinch_cv=False, with_detour=True))
    s = _sites(root)
    assert s["sites"] >= 1
    assert s["sites_meeting_conditions"] == 0
    assert s["rows"][0]["cctv_covered"] is False


def test_scenario_corner_condition_is_declared_vacuous(tree):
    """★ **목표에 닿는 날 빨개지는 검사.**

    지금 `can_turn` 은 항상 참이라 코너 조건이 아무것도 안 거른다.
    `corner_vacuous` 가 그 사실의 선언이고, 회전반경이 검증되는 날
    선언이 거짓이 된다 — 그날 이 검사가 운다.
    """
    s = _sites(tree)
    vacuous = not gt.V.spec().get("turn_radius_verified")
    assert s["corner_vacuous"] is vacuous
    if vacuous:
        assert all(r["detour_corner_ok"] for r in s["rows"]), (
            "코너 조건이 무언가를 걸렀다 — `corner_vacuous: true` 가 거짓말이 됐다")


def test_rule_string_carries_the_threshold(tree):
    """규칙 문장이 상수와 갈리면 `eval.json` 을 읽는 사람이 틀린 규칙을 인용한다."""
    assert _sites(tree)["rule"] == f"d2/d1 > {ev.RATIO_MIN} and d2 < inf"


# ── 결손 항 ───────────────────────────────────────────────────
def test_gap_is_reported_not_subtracted(tmp_path):
    """접속 노드가 섬이면 **쌍을 0 으로 세지 말고 결손 항으로** 낸다."""
    root = _write_tree(tmp_path, _three(200.0, pinch_cv=True, with_detour=False))
    doc, why = _build(root)
    assert why == []
    assert doc["E1"]["gaps"], "통행 가능 성분이 비었는데 결손 항이 없다"
    assert doc["E1"]["pairs"] > 0, "결손을 분모에서 빼버렸다"


def test_e1_counts_unreachable_separately(tmp_path):
    root = _write_tree(tmp_path, _three(200.0, pinch_cv=True, with_detour=False))
    e = _build(root)[0]["E1"]
    assert e["pairs"] == e["pairs_with_route"] + e["unreachable"]


# ── 재현성 ────────────────────────────────────────────────────
VOLATILE = {"as_of", "git_sha"}


def test_two_runs_agree(tree):
    """같은 입력이면 같은 산출이다. 시각과 커밋 말고 흔들리는 칸이 있으면 안 된다.

    ★ 실행 간 비교가 이 산출물의 존재 이유다. 칸 하나라도 매 실행 바뀌면
      `baseline.py diff` 가 그 칸을 영원히 「바뀌었다」로 낸다.
    """
    a, b = _build(tree)[0], _build(tree)[0]
    for k in VOLATILE:
        a.pop(k), b.pop(k)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_shape_matches_the_seal(tree):
    """봉인 `meta.json` 과 같은 칸 이름을 쓴다 — 그래야 실행 간 자동 비교가 붙는다."""
    doc = _build(tree)[0]
    assert set(doc) >= {"as_of", "git_sha", "tally", "sha256", "known_limits"}
    assert set(doc["tally"]) >= {"n", "verdict", "length_total_m", "width_src"}


def test_e3_agrees_with_the_tally(tree):
    """E-3 의 분자·분모가 같은 산출물의 집계와 맞는가. **두 곳이 갈리면 둘 다 못 믿는다.**"""
    doc = _build(tree)[0]
    assert doc["E3"]["n"] == doc["tally"]["n"]
    assert doc["E3"]["cv_impossible"] == doc["tally"]["verdict"]["unknown"]
    assert doc["E3"]["length_total_m"] == round(doc["tally"]["length_total_m"])


# ── 실제 트리 ─────────────────────────────────────────────────
@need_real
def test_real_tree_passes_the_gate():
    """실제 산출물에서 게이트가 통과하는가. **0건은 청결이다**(생사는 위에서 물었다)."""
    tag = gt.newest_tag(REAL / "baseline")
    why = gt.gate(REAL / "processed", REAL / "golden", REAL / "baseline", tag)[1]
    assert why == [], "실제 트리가 게이트에 걸렸다 — 산출물이 낡았거나 게이트가 틀렸다"


@need_real
def test_real_e3_matches_the_locked_fingerprint():
    """E-3 의 분모·분자가 **잠긴 지문**과 맞는가. 문서 숫자를 여기 박지 않는다.

    ★ 값을 손으로 적으면 판정이 움직이는 날 이 검사가 거짓으로 운다.
      정본(`data/golden/segments.fingerprint.json`)과 대조하면 그럴 일이 없다.
    """
    lock = json.loads((REAL / "golden" / "segments.fingerprint.json")
                      .read_text(encoding="utf-8"))["L1"]
    doc = ev.build(REAL / "processed", REAL / "golden", REAL / "baseline",
                   gt.newest_tag(REAL / "baseline"))[0]
    assert doc["E3"]["n"] == lock["n"]
    assert doc["E3"]["cv_impossible"] == lock["verdict"]["unknown"]
    assert doc["E3"]["length_total_m"] == round(lock["length_total_m"])


@need_real
def test_gate_cli_runs_on_the_real_tree():
    """`tools/evalgate.py` 를 프로세스로 돌린다 — 배선이자 연기 시험이다."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "evalgate.py"), "--json"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["passed"] is True


@need_real
def test_cli_runs_end_to_end(tmp_path):
    """`tools/evalgen.py` 를 프로세스로 돌린다 — 배선이자 연기 시험이다."""
    out = tmp_path / "eval.json"
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "evalgen.py"), "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["scenarios"]["rule"].startswith("d2/d1 >")
    assert doc["E1"]["pairs"] > 0
