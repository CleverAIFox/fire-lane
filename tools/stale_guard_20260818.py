#!/usr/bin/env python3
"""
stale_guard_20260818.py — FAIL 난 단계의 옛 산출물이 하류에 조용히 먹히는 것을 막는다.

    uv run python tools/stale_guard_20260818.py --check
    uv run python tools/stale_guard_20260818.py

같은 병으로 두 번 물렸다.

    2026-08-17  ngii1k FAIL (FileNotFoundError) → 8/13 구 NGI gpkg 가 남아
                segments 가 그것을 읽고 1093 을 냈다. EXPECT 에 박히고 커밋됐다.
    2026-08-18  광인사에서 1091 이 나와 "기계 간 재현성 붕괴"로 오인.
                진단에 반나절 — 실은 낡은 gpkg 잡종 vs 진짜 실행의 차이였다.

원인은 하나다. **ingest 가 FAIL 을 찍어도 그 데이터셋의 옛 산출물이
data/processed 에 그대로 남고, segments 는 파일이 있으면 읽는다.**
_manifest.json 에 FAIL 이 적히지만 아무도 안 읽는다 — EXPECT.unknown_reason
이 그랬듯, 적어두고 대조하지 않으면 기록이 아니라 장식이다.

방어 2겹:

    1. ingest  FAIL 시 해당 key 의 기존 산출물을 <이름>.stale_YYYYMMDD 로 개명.
       삭제가 아니라 개명이다 — 진단할 때 옛 파일을 봐야 할 수 있다(오늘 그랬다).
       하류가 읽으려 하면 FileNotFoundError 로 즉시 죽는다. 조용히 못 집는다.
    2. segments  시작 시 _manifest.json 계보 검사. 읽을 입력의 마지막 ingest 가
       OK 가 아니면 어떤 파일이 있든 정지한다. 개명이 실패했거나 사람이 손으로
       파일을 만들어 둔 경우까지 잡는 이중 안전이다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 1. ingest: FAIL 산출물 개명 ─────────────────────────────
ING_OLD = '''        try:
            r = build(key, e, tmp)
        except Exception as ex:                             # noqa: BLE001
            r = {"key": key, "status": "FAIL", "error": f"{type(ex).__name__}: {ex}"}
        print(f"[{r.get('status','-'):7}] {key:20} {r.get('features',''):>8} feat")
        results.append(r)'''

ING_NEW = '''        try:
            r = build(key, e, tmp)
        except Exception as ex:                             # noqa: BLE001
            r = {"key": key, "status": "FAIL", "error": f"{type(ex).__name__}: {ex}"}
            # ★ FAIL 이면 이 key 의 기존 산출물을 개명해 하류에서 떼어낸다.
            #   2026-08-17 ngii1k FAIL 때 8/13 gpkg 가 남아 segments 가 그것으로
            #   판정을 냈고(1093), 다음 날 진짜 실행(1091)과 갈려 "기계 간
            #   재현성 붕괴"로 오인해 반나절을 태웠다. 삭제가 아니라 개명이다 —
            #   진단할 때 옛 파일이 증거가 된다.
            from datetime import date as _date
            _tag = _date.today().strftime("%Y%m%d")
            _stale = []
            for _p in sorted(OUT.glob(f"{key}_5186.gpkg")) + sorted(OUT.glob(f"{key}.geojson")) \\
                    + sorted(OUT.glob(f"{key}_*_5186.gpkg")) + sorted(OUT.glob(f"{key}_*.geojson")):
                _dst = _p.with_name(_p.name + f".stale_{_tag}")
                _dst.unlink(missing_ok=True)
                _p.rename(_dst)
                _stale.append(_p.name)
            if _stale:
                r["staled"] = _stale
                print(f"          ★ 옛 산출물 {len(_stale)}개 격리(.stale_{_tag}) — 하류가 못 읽는다")
        print(f"[{r.get('status','-'):7}] {key:20} {r.get('features',''):>8} feat")
        results.append(r)'''

# ── 2. segments: 계보 검사 ──────────────────────────────────
SEG_ANCHOR = '''def load(key):
    return gpd.read_file(OUT / f"{key}_5186.gpkg").to_crs(CRS_M)'''

SEG_NEW = '''def _lineage_check():
    """읽을 입력의 마지막 ingest 가 OK 인지 본다. 아니면 정지한다.

    ★ 파일이 존재하는 것과 이번 계보에 속하는 것은 다르다.
      2026-08-17/18 이틀 연속, FAIL 난 ngii1k 의 낡은 gpkg 를 segments 가
      조용히 집어 판정 숫자가 갈렸다. _manifest.json 은 FAIL 을 알고
      있었지만 아무도 읽지 않았다 — 여기서 읽는다.
    """
    import json as _json
    mp = OUT / "_manifest.json"
    if not mp.exists():
        sys.exit("★ _manifest.json 없음 — ingest 를 먼저 돌려라")
    m = _json.loads(mp.read_text(encoding="utf-8"))
    st = {d.get("key"): d.get("status") for d in m.get("datasets", [])}
    # 폭·골격·판정에 실제로 읽히는 핵심 입력.
    critical = ["ngii1k", "road_link", "road_rw", "node_link", "cctv"]
    bad = [k for k in critical if st.get(k) not in ("OK", "SKIP")]
    if bad:
        detail = ", ".join(f"{k}={st.get(k)}" for k in bad)
        sys.exit(f"★ 계보 검사 실패: {detail}\\n"
                 f"  마지막 ingest 가 이 입력들을 만들지 못했다. 디스크에 파일이\\n"
                 f"  있어도 그것은 옛 실행의 잔재다. 낡은 입력으로 판정하지 않는다.\\n"
                 f"  → uv run python src/etl/pipeline.py --only ingest 를 먼저 통과시켜라")
    print(f"  계보 OK: {' · '.join(critical)}")


def load(key):
    return gpd.read_file(OUT / f"{key}_5186.gpkg").to_crs(CRS_M)'''

# main 진입 직후 호출
SEG_CALL_ANCHOR = '''    road = load("road_link")'''
SEG_CALL_NEW = '''    _lineage_check()
    road = load("road_link")'''


def apply(rel: str, pairs, check: bool) -> int:
    p = ROOT / rel
    t = p.read_text(encoding="utf-8")
    mark = pairs[0][1].splitlines()[0]
    bad = 0
    for i, (old, new) in enumerate(pairs, 1):
        if new in t:
            print(f"  {rel} #{i} 이미 적용")
            continue
        n = t.count(old)
        if n != 1:
            print(f"! {rel} #{i} 앵커 {n}회 — {old.splitlines()[0][:55]}")
            bad += 1
    if bad or check:
        return bad
    for old, new in pairs:
        if new not in t:
            t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print(f"  {rel} 적용")
    return 0


def main() -> int:
    check = "--check" in sys.argv
    bad = apply("src/etl/ingest.py", [(ING_OLD, ING_NEW)], check)
    bad += apply("src/etl/segments.py",
                 [(SEG_ANCHOR, SEG_NEW), (SEG_CALL_ANCHOR, SEG_CALL_NEW)], check)
    if bad:
        print(f"\n★ 앵커 {bad}건 실패. 해당 파일은 쓰지 않았다.")
        return 1
    print("\n검사 통과." if check else "\n적용 완료. 구문 확인:\n"
          "  uv run python -c \"import ast;[ast.parse(open(f).read()) "
          "for f in ('src/etl/ingest.py','src/etl/segments.py')];print('OK')\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
