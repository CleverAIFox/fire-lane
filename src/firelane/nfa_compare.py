#!/usr/bin/env python3
"""
nfa_compare.py — 소방서 지정 구간과 우리 폭을 대조한다. **판정 지문 밖이다.**

── 왜 꺼냈나 (2026-09-25 · PLAN §1 #124 · DECISIONS §247) ──────────
`seg/report.py::_fire_access_csv` 안의 `from firelane import ledger` **한 줄**이
`ledger`(509) · `naming`(440) · `scope`(188) = **1,137줄**을 판정 지문에 넣고
있었다. 거기에 `kinds`(93)까지 따라왔다 — `kinds` 는 `ledger` 를 통해서만
폐포에 들어오기 때문이다. 넷 다 **판정에 한 톨도 기여하지 않는다**: 파일명
문법 파서와 행정범위 어휘다.

    폐포  21파일 → 17파일   (`ledger` · `naming` · `scope` · `kinds` 가 빠진다)

그래서 `naming.py` 의 정규식 하나만 고쳐도 `golden check` 가 울고 재잠금이
따라왔다. 정당한 경보가 아니면서 반복되는 빨간불은 `--allow-stale` 을 습관으로
만든다(DECISIONS §69). 게다가 그것을 끌어들이는 이 대조 자체가 판정이 아니다 —
`seg/report.py` 머리말이 「판정이 끝난 것을 받는다. 계산은 안 한다」고 적는다.

**선례를 그대로 따랐다** — `segments._write_scope()` 를 같은 이유로
`display_scope` 단계로 내렸다(2026-09-23 · W3-6).

★ **로직을 한 글자도 안 바꿨다.** `seg/report.py:40~149` 를 그대로 옮겼다.
  달라진 것은 **`g` 를 어디서 받는가** 하나다 — 종전에는 `segments.main()` 이
  메모리에서 넘겼고, 이제 직전 단계가 낸 `segments_5186.gpkg` 를 읽는다.
  그 왕복이 등가임을 `tests/test_nfa_compare.py` 가 **세 칸(`geometry` ·
  `width_min_m` · `verdict`)에 대해 실물로** 증명한다. 이 대조가 읽는 칸은
  그 셋뿐이다.

★ **판정 산출물을 안 건드린다.** 이 단계가 쓰는 것은 `nfa_compare.json` 하나다.
  `segments` 단계의 `writes` 에서 그 파일을 뺐다 — 안 빼면 `segments` 가
  자기가 안 쓰는 파일을 선언하는 것이 되고 계보 검사가 그것을 본다.

★ **`firelane.segments` · `firelane.ingest` 가 이 모듈을 import 하면 그 순간
  다시 지문 안이다.** 강제자 —
  `tests/test_golden_fp.py::test_the_external_comparison_is_outside_the_judgment_closure`

★ 이 대조는 우리 폭에 대한 **유일한 외부 대조 수단**이고 두 번 소실됐다 —
  경로 오류로 죽어 있던 것이 2026-08-13, 터미널에만 있던 것이 08-17 이다.
  `MASTER §4` 가 그 사실을 든다. 그래서 단계로 꺼내되 **조용히 건너뛰지 않게**
  원본의 `print` 다섯을 그대로 남겼다.

★ 대조표가 **적합(fit)에 오염돼 있다** — 절대편차 합 12.6 → 7.24 로 줄이는
  과정에서 이 표를 게이트로 썼다. 게이트로 쓴 자료는 그 순간부터 외부 검증
  수단이 아니다(`MASTER §4` · `PLAN §1 #14`). 산출물의 `caveat` 칸이 그것을
  적는다. 여기서 바꾸지 않는다.

IN    processed/segments_5186.gpkg   ★ 직전 단계 `segments` 가 낸 것
      processed/road_link_5186.gpkg
      raw/<대장 `fire_access` 가 가리키는 CSV>   ★ 없으면 건너뛴다
OUT   processed/nfa_compare.json
PARAM 없음
밖    판정을 안 만든다. 판정이 끝난 것을 읽어 **외부 자료와 댄다.**
      좌표가 없어 도로명 단위로만 매칭되므로 참고값이다.
"""
from __future__ import annotations

import geopandas as gpd
from shapely.ops import unary_union

from firelane.paths import PROCESSED

OUT = PROCESSED
CRS_M = "EPSG:5186"


def _fire_access_csv():
    """소방서 지정 구간 CSV 를 **대장에서** 찾는다.

    ★ 못 찾으면 `None` 을 주되 **왜 못 찾았는지 찍는다.** 조용히 넘기면
      대조가 0건인 채로 초록불이 되고, 그것이 이 저장소가 두 번 겪은
      사고다 — 경로 오류로 죽어 있던 것이 2026-08-13, 터미널에만 있던 것이
      08-17 이다. `MASTER §4` 는 이 대조를 **우리 폭에 대한 유일한 외부
      대조 수단**이라고 든다.
    """
    from firelane import ledger
    from firelane.paths import RAW as _RAW

    e = (ledger.load().get("datasets") or {}).get("fire_access")
    if e is None:
        print("  [소방서 대조] 대장에 `fire_access` 가 없다 — 건너뛴다")
        return None
    hits = [p for p in ledger.paths_of(e, _RAW) if p.exists()]
    if not hits:
        print("  [소방서 대조] 대장은 `fire_access` 를 들지만 raw 에 실물이 "
              "없다 — 건너뛴다")
        return None
    if len(hits) > 1:
        print(f"  [소방서 대조] 후보 {len(hits)}개 — 최신을 쓴다: {hits[-1].name}")
    return sorted(hits)[-1]


def _agg(a: list[float], by_src: list[tuple[str, str, float]]) -> dict:
    """절대편차 목록과 (도로, 출처, 편차) 에서 MAE · 중앙 · 출처별을 낸다."""
    from statistics import median

    out = {"mae_m": round(sum(a) / len(a), 2) if a else None,
           "median_abs_dev_m": round(float(median(a)), 2) if a else None, "by_source": {}}
    for src in sorted({s for _, s, _ in by_src}):
        d = [abs(x) for _, s, x in by_src if s == src]
        out["by_source"][src] = {"n_pair": len(d), "n_road": len({r for r, s, _ in by_src if s == src}),
                                 "mae_m": round(sum(d) / len(d), 2), "median_abs_dev_m": round(float(median(d)), 2)}
    return out


def summarize(rows: list[dict], by_src: list[tuple[str, str, float]],
              by_src_name: list[tuple[str, str, float]] | None = None) -> dict:
    """대조 집계 — **MAE · 중앙값**이 지표이고 합은 참고다 (PLAN #93).

    절대편차 합은 표본 수에 비례해 커져 실행 간 · 소스 간 비교가 안 된다.
    `rows` 는 도로 행(`dev_m`), `by_src` 는 `(도로, 폭 출처, 그 도로 안 그 출처의
    편차)` — 편차의 정의는 도로 행과 같다(`width_min_m` 중앙값 − 소방서 폭).
    """
    a = [abs(float(r["dev_m"])) for r in rows]
    out = {"abs_dev_sum_m": round(sum(a), 2), **_agg(a, by_src)}
    # ★ PLAN #66(닫힘) — 이름이 같은 구간만의 값. 정본이 아니다(`dev_m` 이 정본 · nfa_compare 의 ★ 참조)
    n = [abs(float(r["dev_name_m"])) for r in rows if r.get("dev_name_m") is not None]
    out["name_only"] = {"n_road": len(n), **_agg(n, by_src_name or [])}
    return out


def nfa_compare(g):
    """소방서 지정 구간과 우리 폭을 도로명 단위로 대조하고 파일로 남긴다."""
    # ── 소방서 지정 구간 대조 ────────────────────────────────
    # 동부소방서 소방통로확보대상 지역 현황(2025-07-31)의 폭과 비교한다.
    # 좌표가 없어 도로명 단위로만 매칭되므로 참고값이다.
    # ★ 2026-11-10 (PLAN #66(닫힘)). 이 자리가 「소방서가 지정한 것은 가장 좁은 구간이므로 최솟값 쪽으로 비교한다」고
    #   적고 있었으나 **코드는 이미 중앙값과 비교한다**(아래) — 주석이 코드와 반대였다. 그 가정은 데이터가 기각한다:
    #   소방서 폭이 우리 이름 기준 구간 폭 분포의 어디에 놓이는지 보면 백분위 22 · 25 · 33 · 64 · 68 · 70 · 85 이고
    #   최솟값 근처(하위 10%)인 도로가 7곳 중 0 이다. 소방서 폭은 **자기 구간의 대표값**으로 읽는다(그 구간이 어디인지는 좌표가 없어 모른다).
    # ★ RAW 는 $FIRE_LANE_RAW 다. ROOT/"data"/"raw" 로 박아두면 exists() 가
    #   항상 거짓이라 이 블록이 통째로 죽는다. 실제로 한 번도 실행된 적이 없었다.
    #   소방서 지정 구간은 우리 폭에 대한 유일한 외부 대조 수단이다.
    # ★ 2026-09-02. 경로를 직접 조립하지 않는다. 대장이 `stem` + `ext` 로
    #   실물을 찾고 코드는 그 결과만 받는다 — 개명하면 대장·sha대장·실물
    #   셋이 함께 움직이는데, 코드가 그 셋 밖에서 경로를 만들면 혼자
    #   남는다. 2026-08-13 에 그 사고가 있었고 그때는 **한 번도 실행된 적이
    #   없었다.** 예외가 안 나고 블록이 통째로 조용히 죽는다(DECISIONS §98).
    fa = _fire_access_csv()
    if fa is not None and fa.exists():
        import csv
        import re
        rows = list(csv.DictReader(fa.open(encoding="cp949")))
        road = gpd.read_file(OUT/"road_link_5186.gpkg").to_crs(CRS_M)
        print("\n[소방서 지정 구간 대조]")
        # ★ 2026-08-18. print 만 하던 것을 파일로도 남긴다.
        #   이 대조는 우리 폭에 대한 유일한 외부 대조 수단인데 두 번 소실됐다.
        #   경로 오류로 죽어 있던 것이 8/13, 터미널에만 있던 것이 8/17 이다.
        #   8/17 봉인 때 7.24m 를 문서에서 손으로 옮겨 적어야 했다.
        _nfa_rows = []
        _by_src: list[tuple[str, str, float]] = []
        _by_src_name: list[tuple[str, str, float]] = []
        for r in rows:
            for rn in set(re.findall(r"[가-힣]+로\d*번?길", r["지역명"])):
                sel = road[road.RN == rn]
                if not len(sel):
                    continue
                ru = unary_union(list(sel.geometry))
                hit = g[g.geometry.buffer(1).intersects(ru)].dropna(subset=["width_min_m"])
                if not len(hit):
                    continue
                w_nfa = r["폭(m)"]
                try:
                    wf = float(str(w_nfa).split("~")[0])
                except ValueError:
                    continue
                # 소방서 기록폭은 구간 대표폭으로 보인다. 최솟값이 아니라 중앙값과 비교한다.
                # (하위10% 로 비교하면 교차로 근처 극협소 지점을 잡아 -3~-7m 로 벌어진다)
                med = hit.width_min_m.median()
                print(f"  {rn:14s} 소방서 {w_nfa:>7s}m │ 우리 중앙 {med:5.2f}m "
                      f"({med - wf:+.2f}) │ 세그 {len(hit):3d} │ "
                      + " ".join(f"{k}:{v}" for k, v in hit.verdict.value_counts().items()))
                # ★ 2026-11-10 (PLAN #66(닫힘)). `hit` 은 도로 형상 1m 안에 닿는 구간이라 **교차하는 이웃 도로의 구간이 섞인다**
                #   (필문대로289번길 20 → 31). 이름이 같은 구간만의 값을 `*_name` 으로 **나란히** 낸다.
                #   정본은 `dev_m`(교차 모집단)이다 — 봉인 14벌 · MASTER §4 표 · 적합 이력이 그 정의이고, 이름만 보면 오히려 더 벌어진다
                #   (289번길 -3.76 → -5.98). 어느 쪽이 참인지는 소방서에 좌표가 없어 가릴 수 없다.
                _nm = hit[hit["road_name"].fillna("").str.replace(" ", "") == rn]
                _row_name = ({"n_seg_name": len(_nm),
                              "ours_median_name_m": round(float(_nm.width_min_m.median()), 2),
                              "dev_name_m": round(float(_nm.width_min_m.median()) - wf, 2)}
                             if len(_nm) else
                             {"n_seg_name": 0, "ours_median_name_m": None, "dev_name_m": None})
                _nfa_rows.append({
                    "road": rn,
                    "nfa_m": wf,
                    "nfa_raw": str(w_nfa),
                    "ours_median_m": round(float(med), 2),
                    "dev_m": round(float(med) - wf, 2),
                    "n_seg": len(hit),
                    **_row_name,
                    "n_foreign": len(hit) - len(_nm),
                    "verdict": {k: int(v) for k, v in hit.verdict.value_counts().items()},
                })
                # 폭 출처별 — 도로 행과 같은 정의를 그 출처의 구간만으로
                for _src, _grp in hit.groupby("width_src"):
                    _by_src.append((rn, str(_src), round(float(_grp.width_min_m.median()) - wf, 2)))
                for _src, _grp in _nm.groupby("width_src"):
                    _by_src_name.append((rn, str(_src), round(float(_grp.width_min_m.median()) - wf, 2)))

        if _nfa_rows:
            from datetime import datetime as _dt
            from datetime import timedelta as _td
            from datetime import timezone as _tz
            _sm = summarize(_nfa_rows, _by_src, _by_src_name)
            _abs = _sm["abs_dev_sum_m"]
            _out = {
                "as_of": _dt.now(_tz(_td(hours=9))).isoformat(timespec="seconds"),
                "source": str(fa.name),
                "ref": "동부소방서 소방통로확보대상 지역 현황 (원천 20행 · 고유 19구간 6,370m)",
                "match_by": "도로명. 소방서 자료에 좌표가 없다",
                "compare": ("구간 대표폭이므로 중앙값과 비교. 최솟값이면 -3~-7m 로 벌어진다. 정본 `dev_m` 은 도로 형상에 닿는 구간(이웃 도로 포함)의 "
                            "중앙값이고, 이름이 같은 구간만의 값은 `dev_name_m` · `name_only` 로 나란히 둔다"),
                "caveat": ("★ 이것은 검증이 아니라 적합(fit)일 수 있다. 12.6 → 7.24 로 "
                           "줄이는 과정에서 이 표를 게이트로 썼다. 게이트로 쓴 자료는 "
                           "그 순간부터 외부 검증 수단이 아니다. MASTER 4절 참조."),
                "abs_dev_sum_m": _abs,   # 참고 — 표본 수에 비례한다. 지표는 아래 둘
                "mae_m": _sm["mae_m"],
                "median_abs_dev_m": _sm["median_abs_dev_m"],
                "by_source": _sm["by_source"],
                "name_only": _sm["name_only"],   # 이름이 같은 구간만 — 정본이 아니다(위 ★)
                "n_road": len(_nfa_rows),
                "rows": sorted(_nfa_rows, key=lambda x: abs(x["dev_m"])),
            }
            # ★ 수가 그대로면 안 쓴다 — `as_of` 만 흔들려 봉인이 더러워진다(§445).
            from firelane.manifest import write_stable as _ws
            _ws(OUT / "nfa_compare.json", _out, tail="\n")
            print(f"  MAE {_sm['mae_m']}m · 절대편차 중앙 {_sm['median_abs_dev_m']}m"
                  f" (합 {_abs}m 은 참고 · 이름만 MAE {_sm['name_only']['mae_m']}m) · {len(_nfa_rows)}구간"
                  f"  → {(OUT / 'nfa_compare.json').name}")
        else:
            # 없으면 소리를 낸다. 조용한 결측을 만들지 않는다.
            print("  ★ 매칭 0구간. 도로명 매칭이 깨졌다 — RN 컬럼과 지역명 형식 확인")


def main() -> None:
    """`segments_5186.gpkg` 를 읽어 대조하고 `nfa_compare.json` 을 낸다.

    ★ 직전 단계가 방금 낸 파일을 읽는다 — STEPS 순서가 segments → nfa_compare
      이므로 지난 실행 것을 읽을 수 없다(`test_every_read_is_produced_by_an_earlier_step`).

    ★ 2026-10-08 (DECISIONS §436 · PLAN #104) 정정. `width_fail` 은 이제 gpkg 에도
      **있다** — `write_outputs` 가 더 이상 떨구지 않는다. 이 대조에는 차이가
      없다: 읽는 칸은 `geometry` · `width_min_m` · `verdict` 셋뿐이고
      `tests/test_nfa_compare.py` 가 그 셋의 왕복 등가를 본다.
    """
    src = OUT / "segments_5186.gpkg"
    if not src.exists():
        print(f"  [소방서 대조] {src.name} 이 없다 — segments 를 먼저 돌려라")
        return
    g = gpd.read_file(src).to_crs(CRS_M)
    nfa_compare(g)


if __name__ == "__main__":
    from firelane.guards import warn_direct_call

    warn_direct_call(__name__, doc=__doc__)   # doc → 모르는 깃발도 거절(§283-2)
    main()
