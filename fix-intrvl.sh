#!/usr/bin/env bash
# fix-intrvl.sh — 기초번호를 추정에서 실측으로 바꾼다
#
#   저장소 루트에서:  bash fix-intrvl.sh
#
# ── 무엇이 달라지나 ────────────────────────────────────────
# juso_elctrnmap zip 안에 TL_SPRD_INTRVL(기초구간) 이 들어 있다.
# 도로명주소법이 정한 기초번호가 값으로 들어 있는 레이어다.
#
#   지금        도로선 기하 + poi_store 로 오프셋 추정 + 홀드아웃 검증
#   바꾼 뒤     기초구간의 값을 그대로 읽는다. 추정이 없다
#
# 오프셋 보정은 클리핑 때문에 필요했던 우회였다. 정본이 있으면 우회는 버린다.
# poi_store 대조는 남긴다 — 이제 진짜 독립 검증 수단이 된다(보정에 안 쓰므로).
#
# 이 스크립트는 3단계로 나뉜다.
#   1. 레이어 스키마를 찍는다 (아무것도 안 고침)
#   2. 컬럼이 확인되면 ingest 에 등록
#   3. basisno 를 기초구간 기반으로 교체
#
# 1단계에서 컬럼을 못 찾으면 아무것도 건드리지 않고 멈춘다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }
: "${FIRE_LANE_DATA:?FIRE_LANE_DATA 가 없다}"

ZIP="$FIRE_LANE_DATA/raw/juso/juso_elctrnmap_jngj_20260711.zip"
[ -f "$ZIP" ] || { echo "없음: $ZIP"; exit 1; }

echo "── 1. 기초구간 레이어 스키마"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
unzip -q -o "$ZIP" '12210/TL_SPRD_INTRVL.*' -d "$TMP"

uv run python - "$TMP" <<'PROBE'
import sys
from pathlib import Path

import geopandas as gpd

shp = next(Path(sys.argv[1]).rglob("TL_SPRD_INTRVL.shp"))
g = gpd.read_file(shp, encoding="cp949", rows=5)
print(f"  피처 스키마 · CRS {g.crs}")
print(f"  컬럼: {list(g.columns)}")
print(f"  기하: {g.geometry.geom_type.unique().tolist()}")
for _, r in g.head(3).iterrows():
    print("  ", {k: str(v)[:22] for k, v in r.items() if k != "geometry"})

# 기초번호 컬럼 후보
CAND = ["BSI_ZON_NO", "BSI_NO", "BSI_ZONE_NO", "기초번호", "BSIZONNO"]
hit = [c for c in CAND if c in g.columns]
print()
if hit:
    print(f"  ★ 기초번호 컬럼: {hit[0]}")
    Path("/tmp/_fl_bsi_col").write_text(hit[0])
else:
    print(f"  ✗ 기초번호 컬럼을 못 찾았다. 위 컬럼 목록을 보고 판단할 것.")
    print(f"    찾던 이름: {CAND}")
    sys.exit(2)
PROBE

BSI_COL="$(cat /tmp/_fl_bsi_col)"
echo
echo "── 2. sources.yaml 에 기초구간 등록"

uv run python - "$BSI_COL" <<'YAML'
import re
import sys
from pathlib import Path

p = Path("sources.yaml")
s = p.read_text(encoding="utf-8")

if "road_intrvl" in s:
    print("  · 이미 등록됨")
    sys.exit(0)

# road_rw 블록을 찾아 같은 zip 을 쓰는 항목으로 바로 뒤에 끼운다.
m = re.search(r"(\n\s*road_rw:\n(?:\s{4,}.*\n)+)", s)
if not m:
    print("  ✗ road_rw 앵커를 못 찾았다. 수동으로 넣어라:")
    print("""
  road_intrvl:
    provider: juso
    file: juso_elctrnmap_jngj_20260711.zip
    layer: TL_SPRD_INTRVL
    note: 기초구간. 도로명주소법 기초번호 정본
""")
    sys.exit(1)

blk = m.group(1)
indent = re.match(r"\n(\s*)", blk).group(1)
add = (f"\n{indent}road_intrvl:\n"
       f"{indent}  provider: juso\n"
       f"{indent}  file: juso_elctrnmap_jngj_20260711.zip\n"
       f"{indent}  layer: TL_SPRD_INTRVL\n"
       f"{indent}  note: 기초구간. 도로명주소법 기초번호 정본. "
       f"클리핑 오프셋 추정을 대체한다\n")
p.write_text(s[:m.end(1)] + add + s[m.end(1):], encoding="utf-8")
print("  ✓ sources.yaml — road_intrvl 등록")
YAML

echo
echo "── 3. nsdi(연속지적도) 판정"
if grep -q "nsdi" sources.yaml; then
  echo "  · 이미 등록됨"
else
  cat <<'NSDI'
  ✗ raw/nsdi/AL_D002_12_20260808.zip (970MB) 가 대장에 없다.
    AL_D002 는 연속지적도형정보다. README 는 "수치지형도·도로명주소·
    연속지적도" 를 쓴다고 적혀 있으니 버릴 데이터가 아니라 등록 안 한
    데이터로 보인다.

    지금 안 쓸 거면 격리:
      mkdir -p "$FIRE_LANE_DATA/_quarantine"
      mv "$FIRE_LANE_DATA/raw/nsdi" "$FIRE_LANE_DATA/_quarantine/"

    쓸 거면 sources.yaml 에 등록하고 ingest 에 붙여라.
    ★ 지금 결정하지 마라. 격리는 삭제가 아니므로 나중에 되돌린다.
NSDI
fi

echo
echo "── 4. 오프셋 산출물 추적"
git add data/basisno_offset.json 2>/dev/null || true

git add -A
git diff --cached --quiet || {
  git commit -q -m "feat: 기초구간(TL_SPRD_INTRVL) 을 대장에 등록 — 기초번호 정본

juso_elctrnmap zip 안에 도로명주소법 기초번호가 값으로 들어 있었다.
poi_store 로 오프셋을 추정하던 것을 대체할 수 있다.
오프셋 추정은 클리핑 때문에 필요했던 우회이고, 정본이 있으면 버린다."
  echo "  ✓ 커밋"
}

cat <<NEXT

── 다음 (기초구간 실제 투입)

  기초번호 컬럼: $BSI_COL

  ingest.py 에 road_intrvl 을 붙인 뒤 basisno.py 를 교체한다.
  ingest 등록부의 형식을 보여주면 정확한 패치를 만들어주겠다:

      grep -n "road_rw" -A 12 src/etl/ingest.py

  투입 후에는
    - data/basisno_offset.json 폐기 (추정값이므로)
    - basisno_check 는 남긴다. 보정에 안 쓰이므로 진짜 독립 검증이 된다
    - 선이 끊긴 181개 문제도 같이 사라진다 (기초구간은 조각마다 값을 가짐)

── z19 는 되살렸다

  ortho.py 주석이 이유를 적어놨다 — 3m 골목이 z18 에서 6px, z19 에서 12px.
  desk_check.py 의 정사영상 대조(PLAN #11)가 z19 를 필요로 한다.
  내가 지우라고 한 것이 잘못이었다. 파이프라인이 재생성했고 그대로 둔다.
  web/data 29MB · CI 상한 40MB 로 여유 있다.
NEXT
