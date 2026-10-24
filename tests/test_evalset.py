"""`tools/evalset.py` — 0판 평가셋을 뽑는 규칙이 지켜지는가.  (Zm23)

IN    tools/evalset.py · 발행본
OUT   없음 (검사)
PARAM 없음
밖    **체제 정의가 옳은가**는 안 본다 — 사람이 세운 정의를 그대로 쓰는지, 묶음이 안 겹치는지, 표가 눈금을 안 끄는지만 본다.
      진짜 평가셋을 뽑아 채점하는 일은 안 한다(체제 정의가 박히면 사람이 `tools/evalset.py` 를 돌린다).
"""
from __future__ import annotations

import json
from pathlib import Path

import evalgen
import evalset as E
import pytest

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"지명": 2, "편심만": 3, "escape만": 3, "둘다멀쩡": 3, "둘다발동": 3, "A 확인": 3, "대조군": 3}


def _data():
    rows = []
    for i in range(600):
        rows.append({"seg_id": f"DM{i:05d}", "road_name": "가로", "length_m": 30.0 + i % 7, "ecc_rel_med_m": (i % 10) / 10,
                     "road_bt_m": 8.0, "width_min_m": 7.4 + (i % 3) * 0.1, "width_med_m": 7.8, "width_min_sample_idx": 0,
                     "width_max_m": None, "n_sample": 10, "cctv_dist_m": 5.0, "width_min_any_m": 7.5, "width_min_sym_m": 7.5,
                     "clear_med_m": 5.0 if i % 5 == 0 else 20.0, "verdict": "clear"})
    rows += [{**rows[0], "seg_id": n} for n in E.NAMED]
    samples = {r["seg_id"]: [{"seg_id": r["seg_id"], "s_m": "1.0", "w_m": "5.0",
                              "w_rule": "escape" if (int(r["seg_id"][2:]) // 3) % 2 else "carve"} for _ in range(4)] for r in rows}
    mids = {r["seg_id"]: (35.1, 126.9) for r in rows}
    return rows, samples, mids


def test_it_uses_the_regime_module_and_never_defines_a_regime_itself() -> None:
    assert E.R.REGIMES == ("둘다멀쩡", "편심만", "escape만", "둘다발동")
    assert set(E.REGIMES) == set(E.R.REGIMES)
    src = (ROOT / "tools/evalset.py").read_text(encoding="utf-8")
    assert "REGIME =" not in src and "ecc_min" not in src, "체제 문턱을 이 도구가 다시 박았다"


def test_marks_are_separate_axes_not_regimes() -> None:
    rows, samples, mids = _data()
    _, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    m = next(iter(key["marks"].values()))
    assert set(m) == {"regime", "spread", "ledger_gap"}
    assert m["regime"] in E.R.REGIMES and isinstance(m["spread"], bool) and isinstance(m["ledger_gap"], bool)
    assert not any(v["regime"] in ("폭급변", "대장괴리") for v in key["marks"].values()), "표시가 체제로 섞였다"


def test_groups_do_not_overlap_and_sizes_hold() -> None:
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    flat = [s for g in key["groups"].values() for s in g]
    assert len(flat) == len(set(flat)) == sum(SIZES.values()) == len(table)
    assert {g: len(v) for g, v in key["groups"].items()} == SIZES
    assert set(E.NAMED) <= set(flat)


def test_the_table_carries_no_group_no_measurement_and_no_verdict() -> None:
    rows, samples, mids = _data()
    table, _ = E.build(rows, samples, sizes=SIZES, mids=mids)
    assert set(table[0]) == set(E.COLS)
    assert not ({"verdict", "width_min_m", "width_med_m", "road_bt_m", "group", "묶음", "d"} & set(table[0]))
    pre = {"seg_id", "위도", "경도", "도로명", "length_m"}
    assert all(r[c] == "" for r in table for c in E.HUMAN_COLS), "사람이 채울 칸이 미리 차 있다"
    assert all(r[c] != "" for r in table for c in pre)
    assert all(len(r["위도"].split(".")[1]) == 6 for r in table), "위경도는 소수 6자리"


def test_the_draw_is_deterministic_and_order_hides_the_groups() -> None:
    rows, samples, mids = _data()
    a, ka = E.build(rows, samples, sizes=SIZES, mids=mids)
    b, kb = E.build(rows, samples, sizes=SIZES, mids=mids)
    assert [r["seg_id"] for r in a] == [r["seg_id"] for r in b] and ka == kb
    order = [r["seg_id"] for r in a]
    first_group = {s for g in ("지명",) for s in ka["groups"][g]}
    assert order[: len(first_group)] != sorted(first_group, key=order.index) or len(set(order[:3]) & first_group) < 3


def test_the_seed_is_the_existing_convention() -> None:
    assert E.SEED == evalgen.SEED
    assert json.loads(json.dumps(E.build(*_data()[:2], sizes=SIZES, mids=_data()[2])[1]))["seed"] == evalgen.SEED


def test_the_code_never_sorts_by_judgment_or_width() -> None:
    src = (ROOT / "tools/evalset.py").read_text(encoding="utf-8")
    body = src[src.index("def draw("):src.index("def load(")]
    for field in ("verdict", "width_min_m", "width_med_m", "road_bt_m", "gap(", "ecc_rel_med_m"):
        assert f"key=lambda r: r[\"{field}\"]" not in body and "sorted(" not in body.replace('sorted(rows, key=lambda r: r["seg_id"])', "")


def test_score_refuses_before_anything_is_filled_and_does_not_open_the_key(tmp_path: Path) -> None:
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    c, k = tmp_path / "e.csv", tmp_path / "e.key.json"
    E.write(table, key, c, k)
    assert not E.read_filled(c), "비어 있는데 채워진 것으로 읽었다"
    k.unlink()                                   # 키가 없어도 read_filled 는 돈다 = 키를 안 연다
    assert E.read_filled(c) == []


def test_score_runs_on_filled_synthetic_rows() -> None:
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    filled = [{**r, "w_full_m": "6.0", "w_narrow_m": "5.0", "narrow_s_m": "2.0", "note": "합성"} for r in table]
    out = E.score(rows, samples, filled, key)
    assert out["Q1"]["전체"]["n"] == len(table) and set(out) == {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"}
    assert set(out["Q6"]) == set(E.NAMED)


def test_the_a_check_pool_reproduces_the_median_rule_count() -> None:
    seg = ROOT / "web/data/segments.geojson"
    if not seg.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    rows = [f["properties"] for f in json.loads(seg.read_text(encoding="utf-8"))["features"]]
    assert sum(1 for p in rows if E.was_clear_before_median(p)) == 62, "중앙값 규칙이 거두는 62구간이 재현되지 않는다"
    assert 800 < len(E.normal_group(rows)) < 1000


def test_main_never_overwrites_an_existing_or_filled_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """사람이 채운 표를 덮어쓰지 않는다 — 있으면 거부하고, 채워졌으면 `--force` 로도 거부한다."""
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    c, k = tmp_path / "e.csv", tmp_path / "e.key.json"
    E.write(table, key, c, k)
    monkeypatch.setattr(E, "OUT_CSV", c)
    monkeypatch.setattr(E, "OUT_KEY", k)
    monkeypatch.setattr(E, "load", lambda: (rows, samples))
    assert E.main([]) == 3 and E.main(["--force"]) == 0         # 있으면 거부 · --force 면 (안 채워졌을 때) 다시 뽑는다
    text = c.read_text(encoding="utf-8-sig").replace(",,,,,", ",6.0,5.0,2.0,x,", 1)
    c.write_text(text, encoding="utf-8-sig")
    before = c.read_text(encoding="utf-8-sig")
    assert E.main(["--force"]) == 3 and c.read_text(encoding="utf-8-sig") == before, "채워진 표를 덮어썼다"
