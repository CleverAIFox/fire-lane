"""외부 대조 단계가 **판정 지문 밖에 있고**, 옮긴 것이 위치뿐인가.

★ 2026-09-25 (PLAN §1 #124 · DECISIONS §247). `seg/report.py` 안의
  `from firelane import ledger` 한 줄이 `ledger`(509) · `naming`(440) ·
  `scope`(188) · `kinds`(93) = **1,137줄 넷**을 판정 지문에 넣고 있었다.
  넷 다 판정에 한 톨도 기여하지 않는다 — 파일명 문법 파서와 행정범위 어휘다.
  그래서 **`naming.py` 의 정규식 하나만 고쳐도 `golden check` 가 울었다.**

      폐포  21파일 → 17파일

★ 이 검사의 값어치는 **되돌아오는 것을 막는 데** 있다. import 한 줄이면
  넷이 통째로 돌아오고, 그때 울어야 할 것은 판정 게이트가 아니라 이 파일이다.
  판정 게이트가 울면 사람은 「또 그 소리」로 읽고 `--allow-stale` 을 배운다
  (DECISIONS §69).

★ 옮기면서 달라진 것은 **`g` 를 어디서 받는가** 하나다 — 종전에는
  `segments.main()` 이 메모리에서 넘겼고, 이제 직전 단계가 낸
  `segments_5186.gpkg` 를 읽는다. 그 왕복이 등가인지는 추론이 아니라
  **실물로** 봐야 한다: gpkg 는 좌표를 배정밀도로 저장하지만 그것을 믿는 것과
  확인하는 것은 다르고, 이 저장소가 반복해 배운 형태가 정확히 그것이다.

밖   대조 결과값이 옳은지는 안 본다 — 그것은 외부 자료가 정하고, 게다가
     이 표는 **적합(fit)에 오염돼 있다**(`MASTER §4` · `PLAN §1 #14`).
     여기서 보는 것은 「같은 입력에 같은 출력인가」뿐이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent

#: 이 대조가 `g` 에서 실제로 읽는 칸. 셋뿐이다 —
#: `geometry`(buffer·intersects) · `width_min_m`(dropna·median) · `verdict`(value_counts).
READS = ("geometry", "width_min_m", "verdict")


def _imports(rel: str) -> set[str]:
    """`rel` 이 모듈 수준에서 import 하는 이름. 함수 안의 늦은 import 도 센다."""
    out: set[str] = set()
    for node in ast.walk(ast.parse((ROOT / rel).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.add(node.module)
            out |= {f"{node.module}.{a.name}" for a in node.names}
    return out


# ── 폐포 ────────────────────────────────────────────────────────
def test_the_external_comparison_is_outside_the_judgment_closure():
    """대조 모듈이 판정 지문에 들면 **그 한 줄에 재잠금이 따라온다.**"""
    from firelane.shardseal import code_closure

    files = {p.relative_to(ROOT).as_posix() for p in code_closure("firelane.segments")}
    assert "src/firelane/nfa_compare.py" not in files, (
        "외부 대조 모듈이 판정 지문 안이다 — segments 쪽에서 import 했다.\n"
        "  대조는 `pipeline.STEPS` 의 `nfa_compare` 단계가 한다. 판정 코드는\n"
        "  그것을 몰라야 한다(PLAN §1 #124).")


def test_the_ledger_parsers_stay_out_of_the_judgment_closure():
    """넷이 돌아오면 여기서 운다. **판정 게이트가 울기 전에.**"""
    from firelane.shardseal import code_closure

    files = {p.relative_to(ROOT).as_posix() for p in code_closure("firelane.segments")}
    banned = {
        "src/firelane/ledger.py": "대장 파서",
        "src/firelane/naming.py": "파일명 문법",
        "src/firelane/scope.py": "행정범위 어휘",
        "src/firelane/kinds.py": "소스 종류 표 (ledger 를 통해서만 들어온다)",
    }
    back = sorted(f"{f} ({why})" for f, why in banned.items() if f in files)
    assert not back, (
        "판정에 기여하지 않는 모듈이 지문으로 돌아왔다:\n  " + "\n  ".join(back) + "\n"
        "  이 넷은 2026-09-25 에 1,137줄로 빠졌다(21 → 17파일). import 한 줄이면\n"
        "  통째로 돌아온다 — 대장을 읽어야 하는 일은 **모듈이 아니라 단계**로 만들어라.")


def test_the_closure_does_not_quietly_grow():
    """래칫. 17에서 늘면 **무엇이 왜 들어왔는지** 적게 만든다."""
    from firelane.shardseal import code_closure

    n = len(code_closure("firelane.segments"))
    assert n <= 17, (
        f"판정 폐포가 {n}파일이다 — 기록은 17이다.\n"
        "  폐포가 늘면 그 파일을 고칠 때마다 판정 재실행과 재잠금이 따라온다.\n"
        "  정말 판정에 기여하는 파일이면 이 수를 올리고 사유를 적어라.")
    assert n >= 15, (
        f"폐포가 {n}파일로 줄었다 — 기록 17보다 작다. 좋은 일일 수 있지만\n"
        "  **판정 코드가 빠져나간 것**일 수도 있다. 수를 내리고 무엇이 왜 빠졌는지 적어라.")


def test_the_report_module_no_longer_reaches_the_ledger():
    """`seg/report.py` 가 다시 대장을 읽으면 넷이 함께 온다 — 늦은 import 까지 본다."""
    bad = sorted(m for m in _imports("src/firelane/seg/report.py")
                 if m.split(".")[:2] in (["firelane", "ledger"], ["firelane", "naming"],
                                         ["firelane", "scope"], ["firelane", "kinds"])
                 or m in ("firelane.ledger", "firelane.naming", "firelane.scope",
                          "firelane.kinds"))
    assert not bad, (
        f"`seg/report.py` 가 대장 쪽을 다시 import 한다: {bad}\n"
        "  **함수 안의 늦은 import 도 폐포에 든다** — 그것이 2026-09-25 에 고친 결함이다.")


# ── 옮긴 것이 위치뿐인가 ────────────────────────────────────────
@pytest.fixture
def synthetic() -> gpd.GeoDataFrame:
    """대조가 읽는 세 칸을 가진 작은 판정 결과. 레이크가 없어도 돈다.

    ★ 값은 **경계에 붙여** 골랐다 — `dropna` 가 걸리는 결측, `median` 이
      짝수 개에서 두 값의 평균을 내는 자리, 소수점이 긴 좌표.
    """
    return gpd.GeoDataFrame(
        {
            "width_min_m": [3.049999999999999, None, 7.125, 2.5],
            "verdict": ["needs_cv", "unknown", "clear", "blocked"],
            "road_name": ["필문대로205번길", None, "제봉로213번길", "동계천로85번길"],
        },
        geometry=[
            LineString([(194256.12345678901, 283663.98765432109),
                        (194266.12345678901, 283673.98765432109)]),
            LineString([(194300.5, 283700.5), (194310.5, 283710.5)]),
            LineString([(194400.0, 283800.0), (194460.0, 283860.0)]),
            LineString([(194500.333333333, 283900.666666667),
                        (194505.333333333, 283905.666666667)]),
        ],
        crs=5186,
    )


def test_the_gpkg_round_trip_preserves_every_column_the_comparison_reads(tmp_path, synthetic):
    """**gpkg 왕복이 세 칸을 보존하는가.** 이것이 이 배치의 유일한 실질 변경이다."""
    dst = tmp_path / "segments_5186.gpkg"
    synthetic.to_file(dst, driver="GPKG", layer="segments")
    back = gpd.read_file(dst).to_crs("EPSG:5186")

    assert len(back) == len(synthetic), "행 수가 달라졌다"
    assert str(back.crs) == str(synthetic.crs), f"CRS 가 달라졌다: {back.crs}"

    # ① width_min_m — 결측과 긴 소수를 그대로
    a = [None if x != x else x for x in synthetic.width_min_m]
    b = [None if x != x else x for x in back.width_min_m]
    assert a == b, f"width_min_m 이 왕복에서 변했다:\n  전 {a}\n  후 {b}"

    # ② verdict — 문자열
    assert list(back.verdict) == list(synthetic.verdict), "verdict 가 변했다"

    # ③ geometry — 좌표를 **그대로**. 마지막 자리까지 본다
    for i, (x, y) in enumerate(zip(synthetic.geometry, back.geometry, strict=True)):
        assert list(x.coords) == list(y.coords), (
            f"{i}번 형상이 왕복에서 변했다 — 대조는 `buffer(1).intersects` 를 쓴다\n"
            f"  전 {list(x.coords)}\n  후 {list(y.coords)}")


def test_the_comparison_operations_give_the_same_answer_after_the_round_trip(tmp_path, synthetic):
    """칸이 같은 것과 **연산 결과가 같은 것**은 다르다. 대조가 쓰는 넷을 직접 돈다."""
    dst = tmp_path / "segments_5186.gpkg"
    synthetic.to_file(dst, driver="GPKG", layer="segments")
    back = gpd.read_file(dst).to_crs("EPSG:5186")

    # 대조가 도로 형상에 대해 하는 일 그대로
    ru = unary_union([LineString([(194250.0, 283660.0), (194600.0, 284000.0)])])
    for name, g in (("전", synthetic), ("후", back)):
        hit = g[g.geometry.buffer(1).intersects(ru)].dropna(subset=["width_min_m"])
        got = (len(hit),
               None if not len(hit) else round(float(hit.width_min_m.median()), 10),
               {k: int(v) for k, v in hit.verdict.value_counts().items()})
        if name == "전":
            want = got
    assert got == want, (
        f"왕복 뒤 대조 연산의 답이 다르다:\n  전 {want}\n  후 {got}\n"
        "  이 셋이 곧 `nfa_compare` 의 출력이다 — n_seg · ours_median_m · verdict 분포.")


def test_the_comparison_reads_only_those_three_columns():
    """카나리아 — 넷째 칸을 읽기 시작하면 위 두 검사가 **눈이 먼다.**"""
    src = (ROOT / "src/firelane/nfa_compare.py").read_text(encoding="utf-8")
    body = src[src.index("def nfa_compare"):]
    used = {c for c in ("width_max_m", "n_sample", "width_cov", "route_usage",
                        "length_m", "in_emd", "seg_uid", "width_src", "merged_n")
            if c in body}
    assert not used, (
        f"대조가 새 칸을 읽는다: {sorted(used)}\n"
        f"  위 왕복 검사는 {READS} 셋만 본다 — 읽는 칸이 늘면 그 검사도 늘려라.")
    for c in READS:
        assert c in body or c == "geometry", f"`{c}` 를 안 읽는다 — 대조가 바뀌었다"


def test_the_step_is_wired_into_the_pipeline():
    """단계가 선언에 없으면 **아무도 안 부른다.** 조용히 사라지는 것이 이 대조의 이력이다."""
    from firelane import pipeline

    names = [s.name for s in pipeline.STEPS]
    assert "nfa_compare" in names, (
        "`nfa_compare` 단계가 STEPS 에 없다.\n"
        "  이 대조는 우리 폭에 대한 **유일한 외부 대조 수단**이고 이미 두 번\n"
        "  소실됐다 — 2026-08-13 경로 오류, 08-17 터미널에만(MASTER §4).")
    assert names.index("nfa_compare") > names.index("segments"), (
        "판정보다 먼저 돈다 — 대조할 것이 아직 없다")
    st = next(s for s in pipeline.STEPS if s.name == "nfa_compare")
    assert any(p.name == "nfa_compare.json" for p in st.writes), "산출물 선언이 없다"
    seg = next(s for s in pipeline.STEPS if s.name == "segments")
    assert not any(p.name == "nfa_compare.json" for p in seg.produces), (
        "`segments` 가 아직 `nfa_compare.json` 을 낸다고 선언한다 — 이제 안 쓴다.\n"
        "  안 쓰는 산출물을 선언하면 계보 검사가 그것을 기다린다.")
