#!/usr/bin/env python3
"""
nfa_out_20260818.py — 소방서 지정 구간 대조를 파일로 남긴다.

    uv run python tools/nfa_out_20260818.py --check
    uv run python tools/nfa_out_20260818.py

왜
    이 대조는 우리 폭에 대한 **유일한 외부 대조 수단**인데 지금까지
    두 번 소실됐다.

      2026-08-13 까지  경로 오류로 블록 자체가 죽어 있었다(if fa.exists() 항상 거짓)
      2026-08-17 까지  살아났으나 print 만 해서 터미널에만 존재했다

    8/17 봉인 때 7.24m 를 문서 §4 에서 손으로 옮겨 적어야 했던 이유가 이것이다.
    파일로 남기면 tools/baseline.py 가 실행 간 자동 비교할 수 있다.

무엇을 바꾸나
    print 를 지우지 않는다. 사람이 보는 출력은 그대로 두고 파일을 추가한다.
    산출물은 data/processed/nfa_compare.json 이며 baseline 봉인 형식과 같다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "src/etl/segments.py"

OLD = '''        print("\\n[소방서 지정 구간 대조]")
        for r in rows:
            for rn in set(re.findall(r"[가-힣]+로\\d*번?길", r["지역명"])):
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
                      + " ".join(f"{k}:{v}" for k, v in hit.verdict.value_counts().items()))'''

NEW = '''        print("\\n[소방서 지정 구간 대조]")
        # ★ 2026-08-18. print 만 하던 것을 파일로도 남긴다.
        #   이 대조는 우리 폭에 대한 유일한 외부 대조 수단인데 두 번 소실됐다.
        #   경로 오류로 죽어 있던 것이 8/13, 터미널에만 있던 것이 8/17 이다.
        #   8/17 봉인 때 7.24m 를 문서에서 손으로 옮겨 적어야 했다.
        _nfa_rows = []
        for r in rows:
            for rn in set(re.findall(r"[가-힣]+로\\d*번?길", r["지역명"])):
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
                _nfa_rows.append({
                    "road": rn,
                    "nfa_m": wf,
                    "nfa_raw": str(w_nfa),
                    "ours_median_m": round(float(med), 2),
                    "dev_m": round(float(med) - wf, 2),
                    "n_seg": int(len(hit)),
                    "verdict": {k: int(v) for k, v in hit.verdict.value_counts().items()},
                })

        if _nfa_rows:
            import json as _json
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            _abs = round(sum(abs(x["dev_m"]) for x in _nfa_rows), 2)
            _out = {
                "as_of": _dt.now(_tz(_td(hours=9))).isoformat(timespec="seconds"),
                "source": str(fa.name),
                "ref": "동부소방서 소방통로확보대상 지역 현황 (20구간 7,120m)",
                "match_by": "도로명. 소방서 자료에 좌표가 없다",
                "compare": "구간 대표폭이므로 중앙값과 비교. 최솟값이면 -3~-7m 로 벌어진다",
                "caveat": ("★ 이것은 검증이 아니라 적합(fit)일 수 있다. 12.6 → 7.24 로 "
                           "줄이는 과정에서 이 표를 게이트로 썼다. 게이트로 쓴 자료는 "
                           "그 순간부터 외부 검증 수단이 아니다. MASTER 4절 참조."),
                "abs_dev_sum_m": _abs,
                "n_road": len(_nfa_rows),
                "rows": sorted(_nfa_rows, key=lambda x: abs(x["dev_m"])),
            }
            (OUT / "nfa_compare.json").write_text(
                _json.dumps(_out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  절대편차 합 {_abs}m · {len(_nfa_rows)}구간"
                  f"  → {(OUT / 'nfa_compare.json').name}")
        else:
            # 없으면 소리를 낸다. 조용한 결측을 만들지 않는다.
            print("  ★ 매칭 0구간. 도로명 매칭이 깨졌다 — RN 컬럼과 지역명 형식 확인")'''


def main() -> int:
    check = "--check" in sys.argv
    t = S.read_text(encoding="utf-8")
    if "_nfa_rows" in t:
        print("  이미 적용됨 — 건너뜀")
        return 0
    n = t.count(OLD)
    if n != 1:
        print(f"! 앵커 {n}회. 아무것도 쓰지 않았다.")
        return 1
    if check:
        print("앵커 일치. --check 이므로 쓰지 않았다.")
        return 0
    S.write_text(t.replace(OLD, NEW, 1), encoding="utf-8")
    print("  src/etl/segments.py — nfa_compare.json 출력 추가")
    print("\n다음(SSD 연결 후):")
    print("  uv run python src/etl/pipeline.py --from segments")
    print("  cat data/processed/nfa_compare.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
