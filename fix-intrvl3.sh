#!/usr/bin/env bash
# fix-intrvl3.sh — 기초구간을 파이프라인에 배선한다
#
#   저장소 루트에서:  bash fix-intrvl3.sh
#
# sources.yaml 의 kind: shp_zip 은 ingest 가 제네릭하게 처리하므로
# ingest.py 코드는 건드리지 않는다. 대장에 한 항목 추가하면 된다.
#
# ★ 산출물이 19종 → 20종이 된다. docnum_check 가 문서의 "19종" 을
#   잡을 수 있다. 이 스크립트가 docs 도 같이 고친다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

echo "── 사전 확인"
grep -q "PROCESSED" src/etl/segments.py || { echo "✗ segments.py 에 PROCESSED 가 없다"; exit 1; }
grep -q "^import geopandas\|^import geopandas as gpd\|import geopandas as gpd" src/etl/segments.py \
  || { echo "✗ segments.py 에 geopandas 임포트가 없다"; exit 1; }
echo "  ✓ PROCESSED · geopandas 확인"

echo
echo "── 1. sources.yaml 에 road_intrvl 등록"
python3 - <<'YAML'
import re
from pathlib import Path

p = Path("sources.yaml")
s = p.read_text(encoding="utf-8")
if "road_intrvl:" in s:
    print("  · 이미 등록됨")
    raise SystemExit(0)

# road_rw 블록 전체(다음 최상위 키 직전까지)를 찾아 그 뒤에 끼운다.
m = re.search(r"\n(  road_rw:\n(?:(?:    .*)?\n)*?)(?=  \w+:\n)", s)
if not m:
    print("  ✗ road_rw 블록 경계를 못 찾았다. 아래를 수동으로 넣어라.")
    raise SystemExit(1)

blk = """  road_intrvl:
    what: 도로명주소 기초구간 (선형). 기초번호 정본
    crs_native: 5179
    vintage: 2026
    license: TODO
    desc: |
      도로명주소법의 기초번호가 값으로 들어 있는 레이어.
      ODD_BSI_MN 홀수측 본번 · EVE_BSI_MN 짝수측 본번 ·
      RDS_MAN_NO 도로구간 관리번호 · BSI_INT_SN 기초구간 일련번호.
    kind: shp_zip
    file: juso/juso_elctrnmap_jngj_20260711.zip
    layer: TL_SPRD_INTRVL.shp
    crs: EPSG:5179
    encoding: cp949
    retrieved: 2026-08-21
    note: |
      ★ .prj 가 없다(CRS None). crs 값으로 set_crs 한 뒤 변환해야 한다.
      segments 의 seg_label 이 이것을 쓴다. 이전에는 도로선을 linemerge 해서
      기점부터 20m 씩 세었으나, road_link 가 스코프로 클리핑돼 본선의 진짜
      기점이 선 밖에 있었다(무등로 +420 · 중앙로 +186 · 동일부호 100%).
      클리핑으로 끊긴 도로도 181개였다. 정본이 raw 안에 있으므로 추정을 버렸다.
    contract:
      encoding: cp949
      layer_must_exist: true

"""
p.write_text(s[:m.end(1)] + blk + s[m.end(1):], encoding="utf-8")
print("  ✓ sources.yaml — road_intrvl 등록")
YAML

echo
echo "── 2. segments.py 배선"
python3 - <<'PATCH'
import sys
from pathlib import Path

p = Path("src/etl/segments.py")
s = p.read_text(encoding="utf-8")
fail = []


def sub(label, old, new, required=True):
    global s
    if new.strip().splitlines()[0].strip() in s and old not in s:
        print(f"  · {label} — 이미 적용됨")
        return
    if old not in s:
        (fail.append if required else print)(f"{label} — 앵커 없음: {old[:60]!r}")
        return
    if s.count(old) != 1:
        fail.append(f"{label} — 앵커가 {s.count(old)}번 나온다")
        return
    s = s.replace(old, new, 1)
    print(f"  ✓ {label}")


sub("import",
    "from seg.basisno import BasisNumberIndex  # noqa: E402",
    "from seg.basisno import BasisIntervalIndex  # noqa: E402")

old_idx = """    _bnx = BasisNumberIndex.from_gdf(road)
    if _bnx.unmerged:
        print(f"[기초번호] 선이 끊긴 도로명 {len(_bnx.unmerged)}개 — "
              f"해당 구간 번호는 어긋날 수 있다: {sorted(_bnx.unmerged)[:5]}")"""
new_idx = """    # 기초구간 — 도로명주소법 기초번호 정본. 없으면 도로명만 라벨로 쓴다.
    _bnx = None
    try:
        _intrvl = gpd.read_file(PROCESSED / "road_intrvl.geojson")
        if road.crs is not None and _intrvl.crs != road.crs:
            _intrvl = _intrvl.to_crs(road.crs)
        _bnx = BasisIntervalIndex.from_gdf(_intrvl)
        print(f"[기초번호] 기초구간 {len(_intrvl)}개")
    except Exception as _e:                                   # noqa: BLE001
        print(f"[기초번호] 기초구간을 못 읽었다 — seg_label 은 도로명만: {_e}")"""
sub("인덱스 생성", old_idx, new_idx)

sub("라벨 필드",
    "                        seg_label=_bnx.label(_road_nm, g),",
    "                        seg_label=(_bnx.label(_road_nm, g) if _bnx else _road_nm),")

if fail:
    print("\n\033[31m패치 실패\033[0m")
    for f in fail:
        print("  ✗ " + f)
    sys.exit(1)

p.write_text(s, encoding="utf-8")
PATCH

echo
echo "── 3. 문서의 '19종' 갱신"
python3 - <<'DOCS'
import re
from pathlib import Path

n = 0
for f in ("README.md", "docs/MASTER.md", "docs/PLAN.md", "src/etl/ingest.py"):
    p = Path(f)
    if not p.exists():
        continue
    s = p.read_text(encoding="utf-8")
    t = re.sub(r"(?<![0-9])19종", "20종", s)
    t = t.replace("표준 산출물 (19종)", "표준 산출물 (20종)")
    t = t.replace("raw → processed (19종)", "raw → processed (20종)")
    if t != s:
        p.write_text(t, encoding="utf-8")
        print(f"  ✓ {f}")
        n += 1
if n == 0:
    print("  · 바꿀 곳 없음 (docnum_check 가 잡으면 그때 고쳐라)")
DOCS

python3 -m py_compile src/etl/segments.py src/etl/seg/basisno.py && echo "  ✓ 문법"

git add -A
git diff --cached --quiet || {
  git commit -q -m "feat: 기초구간을 대장에 등록하고 seg_label 에 배선

kind: shp_zip 은 ingest 가 제네릭 처리하므로 코드 변경 없이 대장 등록만.
기초구간을 못 읽으면 seg_label 은 도로명만 준다 — 번호를 지어내지 않는다.
산출물 19종 → 20종."
  echo "  ✓ 커밋"
}

cat <<'NEXT'

── 검증 순서

  flrun --from ingest
      [OK] road_intrvl  ~1900 feat  가 뜨는지
      [기초번호] 기초구간 N개        segments 단계에서

  flgold
      ★ L1/L2/L3 전부 OK 여야 한다.
        seg_label 은 지문에 없는 필드이므로 판정이 바뀌면 안 된다.
        깨지면 road_intrvl 이 다른 것을 건드린 것이다.

  uv run python tools/basisno_check.py
      이제 poi_store 가 보정에 안 쓰이므로 진짜 독립 검증이다.
      |편차|<=4 비율이 크게 오르고, '선이 끊긴 도로명' 항목은 사라진다.

  uv run python tools/docnum_check.py
      문서 숫자가 산출물과 맞는지

  uv run pytest tests/ -q
NEXT
