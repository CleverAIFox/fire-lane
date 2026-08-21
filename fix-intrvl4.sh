#!/usr/bin/env bash
# fix-intrvl4.sh — 잔여 정리 + ngii_road 진단
#
#   저장소 루트에서:  bash fix-intrvl4.sh
#
#   1. basisno_check.py 를 기초구간 기반으로 재작성 (import 가 깨져 있다)
#   2. MASTER §11 데이터 필드 표에 seg_label 등록 (docnum_check 지적)
#   3. ngii_road 실패 원인 진단 (읽기만 함)
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

echo "── 1. basisno_check.py 재작성"
cat > tools/basisno_check.py <<'CHECK_EOF'
#!/usr/bin/env python3
"""
tools/basisno_check.py — seg_label 의 기초번호를 상가 주소와 대조한다.

    uv run python tools/basisno_check.py

── 무엇을 보는가 ──────────────────────────────────────────────
`road_intrvl`(기초구간) 은 도로명주소법의 기초번호를 값으로 갖는다.
그 값이 실제 건물 주소와 맞는지 `poi_store`(소상공인 상가정보) 로 본다.

★ 이 대조는 진짜 독립 검증이다. 이전 판은 poi_store 로 오프셋을
  보정한 뒤 같은 자료로 정확도를 주장했다 — MASTER §4 가 경고한
  fit-vs-검증 함정이었다. 지금은 보정이 없으므로 poi_store 가
  외부 기준으로 남는다.

상가만 담아 표본이 상업지에 치우친다. 절대 정확도보다 **어긋난 도로가
어디인가**를 보는 데 쓴다.
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "etl"))
from seg.basisno import BasisIntervalIndex  # noqa: E402

P = Path("data/processed")


def main() -> int:
    for f in ("road_intrvl.geojson", "poi_store.geojson", "road_link.geojson"):
        if not (P / f).exists():
            print(f"없음: {P / f} — pipeline 을 먼저 돌려라")
            return 1

    road = gpd.read_file(P / "road_link.geojson")
    intrvl = gpd.read_file(P / "road_intrvl.geojson")
    poi = gpd.read_file(P / "poi_store.geojson")
    for g in (intrvl, poi):
        if road.crs is not None and g.crs != road.crs:
            g.to_crs(road.crs, inplace=True)

    ix = BasisIntervalIndex.from_gdf(intrvl)
    n_num = sum(1 for x in ix.odd if x is not None)
    print(f"기초구간 {len(intrvl)}개 · 홀수번호 보유 {n_num}개")

    rows = []
    for rn, num, geom in zip(poi["도로명"], poi["건물본번지"], poi.geometry):
        if rn is None or geom is None or geom.is_empty:
            continue
        try:
            actual = int(num)
        except (TypeError, ValueError):
            continue
        if actual <= 0:
            continue
        # 상가는 점이다. 아주 작은 선으로 만들어 겹침 질의에 태운다.
        hits = ix._hits(geom.buffer(8.0).exterior)
        if not hits:
            continue
        best = min(hits, key=lambda h: abs(h[1] - actual))
        rows.append((str(rn).split()[-1], actual, best[1]))

    if not rows:
        print("대조 가능한 상가가 없다.")
        return 1

    byrn = collections.defaultdict(list)
    for rn, a, c in rows:
        byrn[rn].append(a - c)
    devs = np.array([a - c for _, a, c in rows])

    print(f"\n대조 {len(rows)}건 · 도로명 {len(byrn)}개")
    print(f"  중앙 편차 {np.median(devs):+.0f}"
          f" · 평균 {devs.mean():+.1f}"
          f" · |편차|<=2 비율 {(np.abs(devs) <= 2).mean():.1%}"
          f" · |편차|<=4 비율 {(np.abs(devs) <= 4).mean():.1%}")

    print("\n★ 어긋난 도로 (표본 5건 이상 · |중앙편차| 5 초과)")
    hits = 0
    for rn, ds in sorted(byrn.items(), key=lambda x: -abs(np.median(x[1]))):
        if len(ds) < 5:
            continue
        med = float(np.median(ds))
        if abs(med) > 5:
            print(f"  {rn:24s} n={len(ds):4d}  중앙편차 {med:+6.0f}"
                  f"  IQR {np.percentile(ds, 75) - np.percentile(ds, 25):.0f}")
            hits += 1
        if hits >= 15:
            break
    if not hits:
        print("  없음 — 기초구간 값이 주소와 일치한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
CHECK_EOF
python3 -m py_compile tools/basisno_check.py && echo "  ✓ tools/basisno_check.py"

echo
echo "── 2. MASTER §11 데이터 필드 표에 seg_label 등록"
python3 - <<'DOC'
import re
from pathlib import Path

p = Path("docs/MASTER.md")
s = p.read_text(encoding="utf-8")
if re.search(r"^\|\s*`?seg_label`?\s*\|", s, re.M):
    print("  · 이미 등록됨")
    raise SystemExit(0)

# road_name 이 들어 있는 표 행을 찾아 그 뒤에 같은 열 수로 끼운다.
m = None
for cand in re.finditer(r"^\|.*road_name.*\|.*$", s, re.M):
    m = cand
    break
if not m:
    print("  ✗ road_name 표 행을 못 찾았다. MASTER §11 데이터 필드 표에 수동으로 넣어라:")
    print("    | `seg_label` | 문자열 | 구간 라벨. 도로명 + 기초번호 "
          "(예: 필문대로205번길 11-17). road_intrvl 정본 |")
    raise SystemExit(1)

row = m.group(0)
ncol = row.count("|") - 1
desc = ("구간 라벨. 도로명 + 도로명주소 기초번호 "
        "(예: `필문대로205번길 11-17`). `road_intrvl` 정본. "
        "기초구간을 못 찾으면 도로명만")
if ncol <= 2:
    cells = ["`seg_label`", desc]
else:
    cells = ["`seg_label`", "문자열", desc] + [""] * (ncol - 3)
new = "| " + " | ".join(cells[:ncol]) + " |"
s = s[:m.end()] + "\n" + new + s[m.end():]
p.write_text(s, encoding="utf-8")
print(f"  ✓ docs/MASTER.md — road_name 행 뒤에 삽입 ({ncol}열)")
DOC

echo
echo "── 3. ngii_road 진단 (읽기만 함)"
echo
echo "  ── 격리된 산출물"
ls -la data/processed/.stale_* 2>/dev/null | head -10 || echo "    (없음)"
echo
echo "  ── sources.yaml 등록 내용"
python3 - <<'YML'
import yaml
d = yaml.safe_load(open("sources.yaml", encoding="utf-8"))
for k in ("ngii_road", "ngii_road_center"):
    e = d["datasets"].get(k)
    if not e:
        print(f"    {k}: 대장에 없음")
        continue
    print(f"    {k}:")
    for f in ("kind", "file", "layer", "crs", "encoding"):
        if f in e:
            print(f"      {f}: {e[f]}")
YML
echo
echo "  ── 실제 실행 (여기서 오류가 나온다)"
uv run python src/etl/ingest.py --only ngii_road 2>&1 | tail -25

git add -A
git diff --cached --quiet || {
  git commit -q -m "fix: basisno_check 를 기초구간 기반으로 재작성, MASTER §11 에 seg_label 등록

basisno.py 를 교체하면서 check 의 import 가 깨져 있었다.
docnum_check 가 지적한 '산출물에 있으나 표에 없다' 도 해소한다."
  echo
  echo "  ✓ 커밋"
}
