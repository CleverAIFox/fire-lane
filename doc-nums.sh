#!/usr/bin/env bash
# doc-nums.sh — 문서에 넣을 정확한 수치를 산출하고 편집 위치를 확보한다
#
#   저장소 루트에서:  bash doc-nums.sh
#
# 아무것도 고치지 않는다.
# "종" 이 문서마다 다른 것을 가리키고 있어 먼저 확정해야 한다.
#
#   MASTER 439   data/processed/ 20종      ← 산출물 종수?
#   MASTER 472   test_contract.py 20종     ← 계약 테스트 개수? (실제 19 passed)
#   MASTER 512   확보 (21종)                ← raw 데이터셋?
#   MASTER 1450  ingest.py (15종)          ← 또 다른 것?
set -uo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

echo "══ 1. '종' 의 후보값들"
echo
python3 - <<'PY'
import json
from pathlib import Path

P = Path("data/processed")

import yaml
_y = yaml.safe_load(Path("sources.yaml").read_text(encoding="utf-8"))
n_yaml = len(_y.get("datasets", {}))

man = json.loads((P / "_manifest.json").read_text(encoding="utf-8"))
ds = man.get("datasets", [])
ok = [d for d in ds if d.get("status") == "OK"]
skip = [d for d in ds if d.get("status") not in ("OK", None)]

outs = set()
for d in ok:
    for o in d.get("outputs", []):
        outs.add(o)
layers = set()
for d in ok:
    for lay in d.get("layers", []) or []:
        layers.add(lay)

gpkg = sorted(p.name for p in P.glob("*_5186.gpkg"))
gj = sorted(p.name for p in P.glob("*.geojson"))

print(f"  sources.yaml 대장 항목        {n_yaml}")
print(f"  _manifest.json datasets       {len(ds)}   (OK {len(ok)} · 그 외 {len(skip)})")
print(f"  ingest 산출 파일(outputs)      {len(outs)}")
print(f"  gpkg 레이어 종수               {len(layers)}")
print(f"  data/processed/*_5186.gpkg    {len(gpkg)}")
print(f"  data/processed/*.geojson      {len(gj)}")
print()
print(f"  OK 가 아닌 것: {[d['key'] for d in skip]}")
PY

echo
echo "  계약 테스트 실제 개수"
uv run python -m pytest tests/test_contract.py -q 2>&1 | tail -2

echo
echo "══ 2. web/data 실제 용량 (MASTER 1580 은 '1.2MB' 라고 적혀 있다)"
du -sh web/data
du -sh web/data/ortho
python3 -c "
from pathlib import Path
n=sum(1 for p in Path('web/data').rglob('*') if p.is_file())
b=sum(p.stat().st_size for p in Path('web/data').rglob('*') if p.is_file())
print(f'  파일 {n}개 · {b/1e6:.1f}MB')
"

echo
echo "══ 3. 편집 위치 — 앞뒤 문맥"
echo
for spec in "README.md:73:78" "README.md:167:171" "README.md:233:237" \
            "docs/MASTER.md:437:441" "docs/MASTER.md:470:474" \
            "docs/MASTER.md:510:514" "docs/MASTER.md:605:613" \
            "docs/MASTER.md:1448:1452" "docs/MASTER.md:1578:1582" \
            "docs/MASTER.md:2110:2116"; do
    f="${spec%%:*}"; rest="${spec#*:}"; a="${rest%%:*}"; b="${rest##*:}"
    echo "── $f  $a~$b"
    sed -n "${a},${b}p" "$f" 2>/dev/null | sed 's/^/    /'
    echo
done

echo "══ 4. MASTER §5 시스템 구성 — 신규 모듈을 넣을 자리"
echo
grep -n -A 22 "^## 5. 시스템 구성" docs/MASTER.md | head -30

echo
echo "══ 5. MASTER §11 필드 표 — seg_label 주변"
echo
grep -n -B 4 -A 10 '^| `seg_label`' docs/MASTER.md | head -24

echo
echo "══ 6. PLAN 에서 이번에 손댈 항목 (11 · 12 · 14)"
echo
sed -n '70,78p' docs/PLAN.md | sed 's/^/    /'

echo
echo "══ 7. DECISIONS 마지막 항목 (append 위치)"
echo
tail -14 docs/DECISIONS.md | sed 's/^/    /'
echo
echo "  총 줄수: $(wc -l < docs/DECISIONS.md)"

cat <<'NEXT'

══ 다음

  이 출력을 그대로 보여주면 4축 문서 갱신 패치를 만든다.
  앵커를 눈으로 확인하고 짜야 문서 충돌이 안 난다.
NEXT
