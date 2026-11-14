"""`tools/evalset.py` — 0판 평가셋을 뽑는 규칙이 지켜지는가.  (Zm23)

IN    tools/evalset.py · 발행본
OUT   없음 (검사)
PARAM 없음
밖    **체제 정의가 옳은가**는 안 본다 — 사람이 세운 정의를 그대로 쓰는지, 묶음이 안 겹치는지, 표가 눈금을 안 끄는지만 본다.
      진짜 평가셋을 뽑아 채점하는 일은 안 한다(체제 정의가 박히면 사람이 `tools/evalset.py` 를 돌린다).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import evalgen
import evalset as E
import pytest

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"지명": 2, "편심만": 3, "escape만": 3, "둘다멀쩡": 3, "둘다발동": 3, "A 확인": 3, "대조군": 3}


def _data():
    rows = []
    for i in range(600):
        rows.append({"seg_id": f"DM{i:05d}", "seg_uid": f"UID{i:05d}", "road_name": "가로", "length_m": 30.0 + i % 7, "ecc_rel_med_m": (i % 10) / 10,
                     "road_bt_m": 8.0, "width_min_m": 7.4 + (i % 3) * 0.1, "width_med_m": 7.8, "width_min_sample_idx": 0,
                     "width_max_m": None, "n_sample": 10, "cctv_dist_m": 5.0, "width_min_any_m": 7.5, "width_min_sym_m": 7.5,
                     "clear_med_m": 5.0 if i % 5 == 0 else 20.0, "verdict": "clear"})
    rows += [{**rows[0], "seg_id": n, "seg_uid": f"UID-{n}"} for n in E.NAMED]
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
    assert out["Q1"]["전체"]["n"] == len(table) and set(out) == {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}
    assert set(out["Q6"]) == set(E.NAMED)


def test_q7_scores_the_quantity_rule_10_reads_against_the_field_value() -> None:
    """★ `#222` — 규칙 [10] 이 읽는 `clear_med_m` 을 실제와 대는 채점이 **있다.** 문서에 적은 수(62 → 지금 58)는 재잠금마다 낡으므로 그 수는 채점이 그때 센다."""
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    filled = [{**r, "w_full_m": "6.0", "w_narrow_m": "5.0", "narrow_s_m": "2.0", "note": "합성"} for r in table]
    q7 = E.score(rows, samples, filled, key)["Q7"]
    cells: dict[str, int] = {}
    for t in q7["거둠 × 실제(전폭)"].values():
        for c, n in t.items():
            cells[c] = cells.get(c, 0) + n
    # 합성 입력: clear_med_m 은 5.0(거둔다) 또는 20.0(안 거둔다) · 실제 전폭 6.0 은 문턱(CLEAR_M) 미만 = 좁다
    assert set(cells) <= {"거둔다·실제 좁다", "안 거둔다·실제 좁다"} and sum(cells.values()) == len(table), cells
    assert q7["clear_med_m − 전폭"]["전체"]["n"] == len(table) and q7["clear_med_m − 최협부"]["전체"]["n"] == len(table)
    # 오차 부호(우리 − 실제): 5.0 − 6.0 = −1.0 · 20.0 − 6.0 = +14.0 — 중앙이 둘 사이에 있다
    assert -1.0 <= q7["clear_med_m − 전폭"]["전체"]["median"] <= 14.0
    assert isinstance(q7["지금 규칙 [10] 이 거두는 구간 수"], int) and q7["문턱 CLEAR_M"] > 0


def test_q8_scores_the_upper_quantity_rule_11_reads_and_skips_the_unmeasured() -> None:
    """★ 판정이 읽는 양 셋 — `wmin`(Q2 · Q3) · `clear_med_m`(Q7) · 폭 급변의 윗수 `width_max_m`(Q8). 윗수가 None(결손)이면 오차로 안 센다."""
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    filled = [{**r, "w_full_m": "6.0", "w_narrow_m": "5.0", "narrow_s_m": "2.0", "note": "합성"} for r in table]
    q = E.score(rows, samples, filled, key)["Q7"]["width_max_m − 전폭(규칙 [11] 의 윗수 · Q8)"]
    assert q["전체"]["n"] == 0, "합성 행의 width_max_m 은 None 이다 — 결손을 오차로 셌다"
    rows2 = [{**r, "width_max_m": 30.0} for r in rows]
    q2 = E.score(rows2, samples, filled, key)["Q7"]["width_max_m − 전폭(규칙 [11] 의 윗수 · Q8)"]
    assert q2["전체"]["n"] == len(table) and q2["전체"]["median"] == 24.0, q2        # 30.0 − 6.0


def test_q7_skips_rows_without_clear_med_instead_of_counting_them_as_zero() -> None:
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    gone = [{**r, "clear_med_m": None} for r in rows]
    filled = [{**r, "w_full_m": "6.0", "w_narrow_m": "5.0", "narrow_s_m": "2.0", "note": "합성"} for r in table]
    q7 = E.score(gone, samples, filled, key)["Q7"]
    assert q7["clear_med_m − 전폭"]["전체"]["n"] == 0, "모르는 값(None)이 오차로 셌다"
    assert q7["거둠 × 실제(전폭)"] == {}


def test_the_a_check_pool_reproduces_the_median_rule_count() -> None:
    seg = ROOT / "web/data/segments.geojson"
    if not seg.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    rows = [f["properties"] for f in json.loads(seg.read_text(encoding="utf-8"))["features"]]
    # ★ 2026-11-01 (Zm56). 62 → 57. 보도 적재(§594-1 · 14구간)로 폭이 줄어 다섯이 「중앙값 규칙 없이 clear」에서 빠졌다.
    #   유입 0 — 보도 차감도 가름도 폭을 줄이기만 하므로 단방향이다.
    #     DM00095 서석로85번길   width_min 7.22 → 6.09   sym 6.866 → 5.304
    #     DM00897 동명로20번길         9.33 → 5.53             5.938 → 2.222
    #     DM00970 제봉로110번길       20.06 → 12.84            7.622 → 2.332
    #     DM01072 동명로70번길         7.31 → 5.21             5.298 → 0.984
    #     DM01073 동명로70번길         7.99 → 5.81             4.44  → 0.6
    #   §594-1 의 clear→needs_cv 5 와 같은 다섯이다. clear→unknown 10 은 폭 산출이 실패해 clear_med_m 이 없어
    #   이 분모에 처음부터 들지 않았다.
    #   ★ 62 는 설계 목표가 아니다 — PLAN §10-5 A행이 「#17 은 현장 실측 없이 실행됐고 F 에서 사후 검증한다.
    #     그 전까지 #17 의 근거는 비어 있다」(§573). 산출물은 20261101-a-lock 시점에 이미 57 이었다.
    # ★ 2026-11-02 (#180 · DECISIONS §598). 57 → 58. 가름을 내접원에 붙여 `DM01876` 의 `clear_med_m` 이 25.63 → 2.46 으로 내려갔고 중앙값 규칙이
    #   그 구간의 clear 를 거둔다(clear → unknown · needs_survey). 「중앙값 규칙 없이는 clear」 풀에 이 하나가 들었다 — 유입은 이 하나뿐이다.
    assert sum(1 for p in rows if E.was_clear_before_median(p)) == 58, "중앙값 규칙이 거두는 58구간이 재현되지 않는다"
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


# ── Zm26 · 유령 55 — 합성 데이터가 실제 평가셋 자리에 박혔던 사고(DECISIONS §571) ─────────────────
# 원인: `write()` 의 기본 인자 `csv_path=OUT_CSV` 는 **정의 시점**에 묶인다. 위의 시험이 `E.OUT_CSV` 를 tmp 로 바꿔도
#       `main()` 이 부르는 `write(table, key)` 는 진짜 `data/field/evalset_2610.csv` 로 갔고, 그 자리에 합성 600행에서 뽑은
#       55구간(도로명 「가로」 · 길이 30~36)이 들어갔다. 「뽑은 seg_id 가 공개본에 있다」는 시험이 없어서 아무도 못 봤다.
SEG_PUB = ROOT / "web/data/segments.geojson"
REAL_FILES = (ROOT / "data/field/evalset_2610.csv", ROOT / "data/field/evalset_2610.key.json")


def _published() -> dict[str, dict]:
    if not SEG_PUB.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    return {f["properties"]["seg_id"]: f["properties"] for f in json.loads(SEG_PUB.read_text(encoding="utf-8"))["features"]}


def _table_rows(path: Path) -> list[dict]:
    import csv
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(ln for ln in f if not ln.startswith("#")))


def _assert_rows_are_published(table_rows: list[dict], pub: dict[str, dict]) -> None:
    missing = [r["seg_id"] for r in table_rows if r["seg_id"] not in pub]
    assert not missing, f"공개본에 없는 seg_id {len(missing)}개: {missing[:5]}"
    # id 만 맞고 **다른 구간**일 수 있다 — seg_id 는 실행 간 유지되지 않는다(`segments.py` 의 `DM{i:05d}`). 도로명 · 길이로 같은 구간인지 본다.
    other = [r["seg_id"] for r in table_rows
             if (pub[r["seg_id"]].get("road_name") or "") != r["도로명"] or abs(pub[r["seg_id"]]["length_m"] - float(r["length_m"])) > 0.05]
    assert not other, f"seg_id 는 있으나 도로명 · 길이가 공개본과 다른 {len(other)}개(다른 구간): {other[:5]}"


def test_the_committed_evalset_rows_are_all_published_segments() -> None:
    """표에 실린 seg_id 가 **전부 공개본에 있고 같은 구간**이다. 키 파일은 안 연다."""
    if not REAL_FILES[0].exists():
        pytest.skip("환경skip(산출물) — 평가셋 data/field/evalset_2610.csv 가 아직 없다(뽑기 전)")
    _assert_rows_are_published(_table_rows(REAL_FILES[0]), _published())


def test_a_fresh_draw_from_the_published_file_picks_only_published_ids() -> None:
    pub = _published()
    # ★ Zm35. `E.load()` 는 커밋 안 되는 `data/processed/width_samples.csv` 도 읽는다 — 깨끗한 체크아웃(CI)에서는 없어 이 시험이 FileNotFoundError 로 **죽었다**
    #   (원격에서만 빨강). 환경이 없는 것은 통과도 실패도 아니라 skip 이다.
    if not E.SAMPLES.exists():
        pytest.skip("환경skip(산출물) — data/processed/width_samples.csv 가 없다(커밋 안 되는 파일)")
    rows, by = E.load()
    table, key = E.build(rows, by, mids={})
    _assert_rows_are_published([{**r, "length_m": r["length_m"]} for r in table], pub)
    assert {s: u for s, u in key["uids"].items()} == {s: pub[s].get("seg_uid") for s in key["uids"]}, "key 의 seg_uid 가 공개본과 다르다"
    assert set(key["uids"]) == {r["seg_id"] for r in table}


def test_main_writes_only_to_the_patched_paths_and_never_to_the_real_ones(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """★ 사고의 재현 — `E.OUT_CSV` 를 바꿔도 `write()` 가 진짜 자리로 가면 합성 데이터가 실제 평가셋을 덮는다."""
    import hashlib

    def snap() -> list:
        return [hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in REAL_FILES]
    before = snap()
    rows, samples, mids = _data()
    c, k = tmp_path / "e.csv", tmp_path / "e.key.json"
    monkeypatch.setattr(E, "OUT_CSV", c)
    monkeypatch.setattr(E, "OUT_KEY", k)
    monkeypatch.setattr(E, "load", lambda: (rows, samples))
    monkeypatch.setattr(E, "_midpoints", lambda: mids)
    assert E.main([]) == 0 and c.exists() and k.exists()
    assert snap() == before, "시험이 진짜 data/field/evalset_2610.* 를 덮어썼다"


# ── PLAN #190 — 채점은 구간을 seg_uid 로만 찾는다 · 키의 seg_id 가 낡아도 묶음이 맞는다 ─────────────────────────────

def _filled(table):
    return [{**r, "w_full_m": "6.0", "w_narrow_m": "5.0", "narrow_s_m": "2.0", "note": "합성"} for r in table]


def test_score_groups_by_seg_uid_so_a_republish_that_shifts_every_seg_id_does_not_change_the_groups(capsys) -> None:
    """★ 재발행하면 순번 seg_id 가 밀린다. 표(채워진 행)도 키(`groups`)도 옛 seg_id 를 들고 있어도 seg_uid 로 찾으면 같은 구간 · 같은 묶음이다."""
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    plain = E.score(rows, samples, _filled(table), key)
    shifted = [{**r, "seg_id": "ZZ" + r["seg_id"]} for r in rows]                        # 발행본의 번호가 전부 바뀌었다 — seg_uid 는 그대로다
    samples2 = {("ZZ" + k): [{**x, "seg_id": "ZZ" + k} for x in v] for k, v in samples.items()}
    out = E.score(shifted, samples2, _filled(table), key)                                # 표 · 키는 옛 seg_id 그대로
    for q in ("Q1", "Q2", "Q3"):
        assert out[q] == plain[q], f"{q}: seg_id 가 밀렸는데 채점이 달라졌다 — 구간을 seg_id 로 찾고 있다"
    assert "표의 seg_id 칸이 낡았다" in capsys.readouterr().err, "낡은 보조 칸을 알리지 않았다"


def test_score_refuses_a_row_without_seg_uid_and_a_dead_seg_uid_and_a_key_without_uids() -> None:
    rows, samples, mids = _data()
    table, key = E.build(rows, samples, sizes=SIZES, mids=mids)
    nouid = [{**r, "seg_uid": ""} if i == 0 else r for i, r in enumerate(_filled(table))]
    with pytest.raises(SystemExit, match="seg_uid 가 없다"):
        E.score(rows, samples, nouid, key)
    dead = [{**r, "seg_uid": "UID-없는구간"} if i == 0 else r for i, r in enumerate(_filled(table))]
    with pytest.raises(SystemExit, match="발행본에 없다"):
        E.score(rows, samples, dead, key)
    with pytest.raises(SystemExit, match="`uids` 칸"):
        E.score(rows, samples, _filled(table), {**key, "uids": {}})


def test_score_never_looks_a_segment_up_by_seg_id() -> None:
    """회귀 — 구간 찾기가 `by_id[...]` 로 돌아가면 이 줄이 우는 것이 아니라 위 시험이 운다. 여기서는 글자로도 못박는다."""
    body = (ROOT / "tools/evalset.py").read_text(encoding="utf-8")
    body = body[body.index("def score("):body.index("# ── 거리뷰 판독표")]      # score 의 몸통만(뒤의 판독표 절은 아래 시험이 따로 든다)
    assert "by_id[" not in body and "by_id =" not in body, "score 가 seg_id 로 구간을 찾는다(재발행하면 밀린다)"


# ── 거리뷰 판독표 — 가설 검정 (묶음 ㉘ · PLAN #187) ────────────────────────────────────────────────
# IN tools/evalset.py 의 rv_* · data/field/roadview_hypo_2611.csv · 발행본 · data/processed/width_samples.csv   OUT 없음(검사)   PARAM 없음
# 밖 사람의 판독이 **옳은가** · 가설이 **좋은 가설인가**는 안 본다 — 칸 · 허용값 · 행마다 묻는 것이 있는가 · 좌표가 최소폭 표본 지점인가 · 대조군이 표에 안 드러나는가 · 검정이 다 채운 뒤에만 나오는가를 본다. 키 파일은 안 연다.
FIELD = ROOT / "data/field"
HY_M = 0.0004 / 44.0            # 합성 구간(북쪽으로 44m)의 1m 가 위도로 몇 도인가


def _hy_world(extra: dict | None = None) -> tuple[list[dict], dict[str, list[dict]]]:
    """합성 구간과 표본. 구간마다 북쪽으로 44m 곧은 선 · 표본 22개(s = 1, 3, …, 43) · 최소폭은 표본 #1(s = 3m)이다."""
    kinds = [(u, 8.0, 2.6, 4.8) for u in E.RV_NAMED] + [(f"A{i}", 6.0, 2.5, 3.0) for i in range(10)] + [(f"C{i:02d}", 6.0, 5.5, 5.6) for i in range(24)] \
        + [(f"B{i}", 3.0, 2.0, 4.0) for i in range(9)] + [(f"D{i}", 4.0, 9.0, 9.5) for i in range(8)]
    feats, samples = [], {}
    for i, (u, b, w, m) in enumerate(kinds):
        x = 126.9 + i * 1e-3
        p = {"seg_id": f"DM{i:05d}", "seg_uid": u, "road_name": "가로", "length_m": 44.0, "width_min_m": w, "width_med_m": m, "road_bt_m": b,
             "width_min_sample_idx": 1, "verdict": "unknown", **(extra or {}).get(u, {})}
        feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[x, 35.1], [x, 35.1004]]}, "properties": p})
        samples[u] = [{"seg_uid": u, "seg_id": p["seg_id"], "s_m": f"{2 * k + 1}.0", "w_m": str(w if k == 1 else m)} for k in range(22)]
    return feats, samples


def _hy_sheet(tmp_path: Path, fill: dict[str, dict] | None = None, extra: dict | None = None):
    """합성 판독표를 쓴다. `fill` = seg_uid → 채울 칸."""
    feats, samples = _hy_world(extra)
    table = E.rv_build(feats, samples, E.rv_draw(feats, samples))
    for r in table:
        r.update((fill or {}).get(r["seg_uid"], {}))
    path = tmp_path / E.RV_FILE
    E.rv_write(table, path)
    return path, feats, samples, table


def _hy_real():
    if not E.SAMPLES.exists() or not SEG_PUB.exists():
        pytest.skip("환경skip(산출물) — data/processed/width_samples.csv 또는 web/data/segments.geojson 이 없다")
    return json.loads(SEG_PUB.read_text(encoding="utf-8"))["features"], E.rv_samples(), _table_rows(FIELD / E.RV_FILE)


def _roles(feats: list[dict], samples: dict, rows: list[dict]) -> list[tuple[str, str | None]]:
    by = {f["properties"]["seg_uid"]: f["properties"] for f in feats}
    return [(r["가설"], E.rv_role(r["가설"], by[r["seg_uid"]], samples[r["seg_uid"]])) for r in rows]


SEEN = {"거리뷰": "있다", "포장폭": "중간", "촬영시점": "2025-04"}


def test_the_hypothesis_sheet_is_whole_and_blank_or_valid() -> None:
    """실물 — 칸 · 행 수 · 허용값 · 가설군/대조군 수가 맞다. 전수표 셋(55 · 27 · 64행)은 지웠다 — 돌아오면 운다(64지점 표는 119 출동 위치가 드러난다)."""
    feats, samples, rows = _hy_real()
    bad, stat = E.rv_check(FIELD / E.RV_FILE, feats, samples)
    assert not bad and stat["행"] == E.RV_N == len(rows) and 25 <= E.RV_N <= 40, (bad[:3], stat)
    assert not [n for n in ("roadview_evalset_2611.csv", "roadview_wmax_2611.csv", "roadview_blocked_2611.csv") if (FIELD / n).exists()], "전수 판독표가 돌아왔다"
    assert all(5 <= h[0] <= 10 and 5 <= h[1] <= 10 for h in E.RV_HYPO.values()), "한 가설의 가설군 · 대조군은 각각 5~10 이다"


def test_the_sheet_carries_the_rule_in_words_and_nothing_that_drags_the_eye() -> None:
    text = (FIELD / E.RV_FILE).read_text(encoding="utf-8")
    head = "\n".join(ln for ln in text.splitlines() if ln.startswith("#"))
    for word in ("전수 조사가 아니다", "최소폭을 잰 바로 그 표본 지점", "구간 중점도 도로명도 아니다", "s_m ÷ 구간 길이", "width_min_sample_idx", "피셔 정확검정", "유의수준 0.05", "귀무가설",
                 "대조군인지도 없다", "가림", "YYYY-MM", "--roadview-check", *(h[7] for h in E.RV_HYPO.values()), *(h[4] for h in E.RV_HYPO.values())):
        assert word in head, f"머리말에 「{word}」가 없다"
    cols = text[len(head):].strip().splitlines()[0].split(",")
    rows = _table_rows(FIELD / E.RV_FILE)
    assert tuple(cols) == E.RV_COLS and not {"width_min_m", "width_med_m", "road_bt_m", "verdict", "length_m", "s_m", "역할", "묶음", "group", "대조군", "가설군"} & set(cols), cols
    assert all(r["카카오로드뷰"] == f"https://map.kakao.com/link/roadview/{r['위도']},{r['경도']}" and r["네이버지도"].endswith(f"/{r['위도']},{r['경도']}") for r in rows)
    assert [int(r["순번"]) for r in rows] == list(range(1, len(rows) + 1))


def test_every_row_asks_what_its_hypothesis_asks() -> None:
    """행마다 「그 점에서 묻는 것」이 있고 가설마다 다르다 — 「3m 넘나」 하나로 뭉개지 않는다. 답의 허용값은 묻는 줄 끝에 다 적혀 있다."""
    rows = _table_rows(FIELD / E.RV_FILE)
    assert all(r["묻는것"].strip() and r["묻는것"] == E.RV_HYPO[r["가설"]][4] for r in rows)
    assert len({h[4] for h in E.RV_HYPO.values()}) == len(E.RV_HYPO) == len({r["가설"] for r in rows}) >= 3, "가설마다 묻는 것이 달라야 한다"
    for k, h in E.RV_HYPO.items():
        tail = h[4].split("—")[-1]
        assert "—" in h[4] and all(a in tail for a in h[5]) and set(h[6]) < set(h[5]) and "가림" in h[5] and "가림" not in h[6], f"가설 {k}: 묻는 줄 끝에 허용 답이 다 없다"
        assert "," not in h[4], "묻는 줄에 쉼표가 있으면 CSV 칸이 따옴표로 싸여 손으로 채우기 어렵다"


def test_the_coordinate_is_the_min_width_sample_point_not_the_midpoint() -> None:
    feats, samples, rows = _hy_real()
    by = {f["properties"]["seg_uid"]: f for f in feats}
    far = 0
    for r in rows:
        f = by[r["seg_uid"]]
        p, got = f["properties"], samples[r["seg_uid"]][int(f["properties"]["width_min_sample_idx"])]
        assert abs(float(got["w_m"]) - p["width_min_m"]) <= E.RV_TOL_M, f"{r['seg_uid']}: 그 표본이 발행 최소폭을 낸 표본이 아니다"
        lat, lon, brg = E.rv_point(f["geometry"]["coordinates"], float(got["s_m"]) / p["length_m"])
        assert (r["위도"], r["경도"], r["보는방향"]) == (f"{lat:.6f}", f"{lon:.6f}", brg), f"{r['seg_uid']}: 좌표가 최소폭 표본 지점이 아니다"
        mlat, mlon, _ = E.rv_point(f["geometry"]["coordinates"], 0.5)
        far += math.hypot((lon - mlon) * math.cos(math.radians(lat)) * 111_320, (lat - mlat) * 110_950) > 5.0
    assert far >= len(rows) // 2, f"중점에서 5m 넘게 떨어진 행이 {far}/{len(rows)} — 좌표가 구간 중점으로 돌아갔다"
    feats, samples = _hy_world()                                   # 합성 — 최소폭 표본은 s = 3m(44m 구간의 시작 쪽)이다. 중점(22m)이 아니다
    row = E.rv_build(feats, samples, [("가", "A0")])[0]
    assert float(row["위도"]) == pytest.approx(35.1 + 3 * HY_M, abs=2e-6) and abs(float(row["위도"]) - 35.1002) > 1e-4, row["위도"]


def test_the_control_rows_do_not_show_and_the_draw_is_reproducible() -> None:
    """대조군 여부는 표에 없다 — 열쇠 파일도 없다. 규칙(`rv_role`)과 시드로 다시 나온다. 행 순서도 가설군 · 대조군을 흘리지 않는다."""
    feats, samples, rows = _hy_real()
    assert [(r["가설"], r["seg_uid"]) for r in rows] == E.rv_draw(feats, samples), "실물 표가 지금 발행본 · 시드에서 다시 뽑은 명단과 다르다"
    roles = _roles(feats, samples, rows)
    for k, h in E.RV_HYPO.items():
        assert (roles.count((k, "가설군")), roles.count((k, "대조군"))) == h[:2], (k, roles)
    assert roles.count(("가", "지명")) == len(E.RV_NAMED) == 2 and {r["seg_uid"] for r in rows} >= set(E.RV_NAMED)
    seq = [role for _, role in roles if role != "지명"]
    assert seq != sorted(seq) and seq != sorted(seq, reverse=True), "행 순서가 가설군 · 대조군 순이다"
    text = (FIELD / E.RV_FILE).read_text(encoding="utf-8")
    body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
    assert "대조군" not in body and "가설군" not in body and "지명" not in body, "표 본문에 묶음이 실렸다"
    assert not list(FIELD.glob("roadview_hypo*key*")), "열쇠 파일을 따로 두지 않는다 — 규칙으로 다시 나온다"
    pub = {f["properties"]["seg_uid"]: f["properties"] for f in feats}
    leak = {str(pub[r["seg_uid"]][c]) for r in rows for c in ("width_min_m", "width_med_m", "road_bt_m")} & {r[c] for r in rows for c in E.RV_PRE if c != "순번"}
    assert not leak, f"표의 칸에 우리 폭 · 대장폭이 실렸다 {sorted(leak)[:3]}"


def test_rv_role_follows_the_written_rules() -> None:
    rows = [{"s_m": "1.0", "w_m": "9.9"}, {"s_m": "3.0", "w_m": "2.5"}]
    p = {"seg_uid": "X", "length_m": 44.0, "width_min_m": 2.5, "width_med_m": 3.0, "road_bt_m": 6.0, "width_min_sample_idx": 1}
    role = lambda hyp, **kw: E.rv_role(hyp, {**p, **kw}, [rows[0], {**rows[1], "w_m": str(kw.get("width_min_m", 2.5))}])  # noqa: E731 — 시험 안의 한 줄 도우미다
    assert role("가") == "가설군" and role("가", width_min_m=3.0) is None and role("가", road_bt_m=8.01) is None and role("가", width_min_m=0.99) is None
    assert role("가", width_min_m=5.0) == "대조군" and role("가", width_min_m=4.99) is None
    assert role("나", road_bt_m=3.0, width_med_m=3.75) == "가설군" and role("나", road_bt_m=3.0, width_med_m=3.7) is None and role("나") is None, "가설 가의 구간이 나에 겹쳐 들었다"
    assert role("나", width_min_m=4.5, width_med_m=5.0) == "대조군" and role("나", width_min_m=4.4, width_med_m=5.0) is None
    assert role("다", width_min_m=9.0) == "가설군" and role("다", width_min_m=8.99) is None and role("다", width_min_m=15.0, road_bt_m=12.0) is None
    assert role("다", width_min_m=6.5, width_med_m=6.6) == "대조군" and role("다", road_bt_m=2.0, width_min_m=2.5) is None, "거리뷰가 안 들어가는 3m 미만을 대조군으로 뽑았다"
    assert role("가", length_m=14.9) is None, "교차부 안의 짧은 조각을 뽑았다"
    assert E.rv_role("가", p, [rows[0], {**rows[1], "w_m": "2.6"}]) is None and E.rv_role("가", {**p, "width_min_sample_idx": None}, rows) is None, "최소폭 표본을 못 대는 구간을 뽑았다"
    assert E.rv_role("가", {**p, "seg_uid": E.RV_NAMED[0]}, rows) == "지명" and E.rv_role("나", {**p, "seg_uid": E.RV_NAMED[0]}, rows) is None


def test_rv_point_interpolates_along_the_line_and_keeps_the_travel_bearing() -> None:
    lat, lon, brg = E.rv_point([[126.9, 35.1004], [126.9, 35.1]], 0.25)       # 남쪽으로 그은 선의 1/4 지점
    assert (lat, lon, brg) == (35.1003, 126.9, "남 180°"), (lat, lon, brg)     # 방위를 북쪽 반원으로 접지 않는다 — 표본 위치가 느는 쪽이다
    lat, lon, brg = E.rv_point([[126.9, 35.1], [126.9, 35.1002], [126.9002, 35.1002]], 1.0)
    assert (lat, lon) == (35.1002, 126.9002) and brg.startswith("동 "), (lat, lon, brg)
    assert E.rv_point([[126.9, 35.1], [126.9, 35.1004]], -1.0)[0] == 35.1 and E.rv_point([[126.9, 35.1], [126.9, 35.1004]], 9.0)[0] == 35.1004


def test_rv_check_passes_a_good_row_and_catches_each_break(tmp_path: Path) -> None:
    in_a = next(r["seg_uid"] for r in _hy_sheet(tmp_path)[3] if r["seg_uid"].startswith("A"))     # 가설 「가」의 가설군 한 행
    path, feats, samples, table = _hy_sheet(tmp_path, {in_a: {**SEEN, "답": "한쪽"}})
    bad, stat = E.rv_check(path, feats, samples)
    assert not bad and stat["채운 행"] == 1 and stat["행"] == E.RV_N, bad
    breaks = {"허용값": {"답": "터졌다"}, "허용값 ": {"포장폭": "3.2"}, "허용값  ": {"거리뷰": "예"}, "YYYY-MM": {"촬영시점": "2025.4"}, "채우다 만": {"포장폭": ""},
              "채우다 만 ": {"거리뷰": "없다"}, "채우다 만  ": {"거리뷰": ""}, "채우다 만   ": {"촬영시점": ""}, "최소폭 표본 지점": {"위도": "35.100200"}, "최소폭 표본 지점 ": {"묻는것": ""},
              "최소폭 표본 지점  ": {"보는방향": "남 180°"}, "규칙 밖": {"가설": "다"}}
    for want, cell in breaks.items():
        path, feats, samples, _ = _hy_sheet(tmp_path, {in_a: {**SEEN, "답": "한쪽", **cell}})
        bad, _ = E.rv_check(path, feats, samples)
        assert any(want.strip() in b for b in bad), f"{cell} 를 못 잡는다 — {bad}"
    path, feats, samples, _ = _hy_sheet(tmp_path, {in_a: {"거리뷰": "없다"}})            # 거리뷰가 없으면 그 한 칸으로 온전한 행이다
    assert E.rv_check(path, feats, samples)[0] == []
    assert any("행 수" in b for b in E.rv_check(path, feats, samples, n=55)[0]), "행 수가 다른데 안 운다"
    moved, _ = _hy_world({in_a: {"road_bt_m": 20.0}})                                    # 재발행으로 그 구간이 규칙 밖으로 나갔다
    assert any("규칙 밖" in b for b in E.rv_check(path, moved, samples)[0]) and any("가설군 · 대조군 수" in b for b in E.rv_check(path, moved, samples)[0])
    assert any("규칙 밖" in b for b in E.rv_check(path, feats[1:], samples)[0]), "발행본에 없는 구간인데 안 운다"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([*lines[:-1], lines[-2]]) + "\n", encoding="utf-8")
    assert any("두 번" in b for b in E.rv_check(path, feats, samples)[0]), "같은 구간이 두 번 든 것을 못 잡는다"
    path.write_text(path.read_text(encoding="utf-8").replace("순번,가설", "순번,묶음", 1), encoding="utf-8")
    assert any("칸이 다르다" in b for b in E.rv_check(path, feats, samples)[0])


def test_the_verdict_comes_only_when_a_hypothesis_is_fully_answered(tmp_path: Path) -> None:
    """중간에 가설군/대조군 수를 내면 어느 행이 대조군인지 샌다 — 다 채운 가설만 가른다. 피셔 정확검정의 수도 댄다."""
    assert E.rv_fisher(4, 4, 0, 4) == pytest.approx(1 / 70) and E.rv_fisher(0, 5, 0, 5) == 1.0 and E.rv_fisher(3, 6, 3, 6) == pytest.approx(0.7164502)
    n1, n0 = E.RV_HYPO["가"][:2]
    assert E.rv_fisher(n1, n1, 0, n0) <= E.RV_ALPHA < E.rv_fisher(n1 // 2, n1, n0 // 2, n0), "이 표본 수로는 완전히 갈려도 기각하지 못한다"
    feats, samples = _hy_world()
    picks = E.rv_draw(feats, samples)
    role = dict(zip([u for _, u in picks], [r for _, r in _roles(feats, samples, [{"가설": h, "seg_uid": u} for h, u in picks])], strict=True))
    ans = {u: {**SEEN, "답": "양쪽" if role[u] == "가설군" else "없다"} for h, u in picks if h == "가"}
    part = dict(list(ans.items())[:-1])
    path, feats, samples, _ = _hy_sheet(tmp_path, part)
    bad, stat = E.rv_check(path, feats, samples)
    assert not bad and isinstance(stat["가"], str) and "다 채우면" in stat["가"] and "가설군" not in json.dumps(stat, ensure_ascii=False), stat
    path, feats, samples, _ = _hy_sheet(tmp_path, ans)
    bad, stat = E.rv_check(path, feats, samples)
    assert not bad and stat["가"]["가설군"] == f"{n1}/{n1}" and stat["가"]["대조군"] == f"0/{n0}" and "기각한다" in stat["가"]["판정"] and len(stat["가"]["지명"]) == 2, stat
    assert isinstance(stat["나"], str), "안 채운 가설의 수가 나왔다"
    blind = {u: ({"거리뷰": "없다"} if role[u] == "대조군" else {**SEEN, "답": "가림"} if role[u] == "지명" else v) for u, v in ans.items()}
    path, feats, samples, _ = _hy_sheet(tmp_path, blind)
    stat = E.rv_check(path, feats, samples)[1]
    assert stat["가"]["p"] is None and "못 가른다" in stat["가"]["판정"] and stat["가"]["지명"] == ["가림", "가림"], stat
    same = {u: {**SEEN, "답": "한쪽"} for u in ans}
    path, feats, samples, _ = _hy_sheet(tmp_path, same)
    assert "기각하지 못한다" in E.rv_check(path, feats, samples)[1]["가"]["판정"]


def test_rv_main_never_overwrites_a_filled_sheet_and_never_opens_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    feats, samples = _hy_world()
    seg, smp = tmp_path / "segments.geojson", tmp_path / "width_samples.csv"
    seg.write_text(json.dumps({"features": feats}), encoding="utf-8")
    smp.write_text("seg_uid,seg_id,s_m,w_m\n" + "".join(f"{r['seg_uid']},{r['seg_id']},{r['s_m']},{r['w_m']}\n" for v in samples.values() for r in v), encoding="utf-8")
    monkeypatch.setattr(E, "SEG", seg)
    monkeypatch.setattr(E, "SAMPLES", smp)
    monkeypatch.setattr(E, "OUT_KEY", tmp_path / "없는.key.json")
    assert E.rv_main(False, False, tmp_path) == 0 and E.rv_main(True, False, tmp_path) == 0
    path = tmp_path / E.RV_FILE
    blank = path.read_text(encoding="utf-8")
    assert E.rv_main(False, False, tmp_path) == 0 and E.rv_main(False, True, tmp_path) == 0 and path.read_text(encoding="utf-8") == blank, "같은 입력 · 같은 시드인데 표가 달라졌다"
    table = _table_rows(path)
    table[0].update({"거리뷰": "없다"})
    E.rv_write(table, path)
    before = path.read_text(encoding="utf-8")
    assert E.rv_main(False, True, tmp_path) == 0 and path.read_text(encoding="utf-8") == before, "채워진 판독표를 덮어썼다"
    src = (ROOT / "tools/evalset.py").read_text(encoding="utf-8")
    body = src[src.index("# ── 거리뷰 판독표"):src.index("def selftest(")]
    assert "OUT_KEY" not in body and "key.json" not in body and "by_id" not in body, "판독표 절이 키 파일을 건드리거나 seg_id 로 구간을 찾는다"
    short, _ = _hy_world({f"A{i}": {"length_m": 10.0} for i in range(5)})
    with pytest.raises(SystemExit, match="못 뽑는다"):
        E.rv_draw(short, samples)
