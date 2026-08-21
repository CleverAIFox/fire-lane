#!/usr/bin/env bash
# doc-audit.sh — 4축 문서가 이번 PR 과 어긋난 지점을 뽑는다
#
#   저장소 루트에서:  bash doc-audit.sh
#
# 아무것도 고치지 않는다. 어디를 고쳐야 하는지만 찍는다.
# 문서끼리 충돌하면 대참사이므로 손대기 전에 전수 파악이 먼저다.
set -uo pipefail   # grep 무매칭이 스크립트를 죽이지 않게 -e 는 뺀다
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

BASE="${1:-origin/gis}"

echo "══ 0. 이번 PR 이 바꾼 것"
echo
echo "  코드·설정"
git diff --stat "$BASE"...HEAD -- src tools .github sources.yaml \
    Dockerfile docker-compose.yml .gitignore .gitattributes 2>/dev/null | tail -20 || true
echo
echo "  문서 (여기가 비어 있으면 문서를 하나도 안 고친 것이다)"
git diff --stat "$BASE"...HEAD -- docs README.md 2>/dev/null | tail -10 || echo "    (변경 없음)"

echo
echo "══ 1. 새로 생긴 파일 — 문서에 등재됐나"
echo
for f in src/etl/seg/basisno.py src/etl/quiet_gdal.py tools/encoding_check.py \
         tools/web_manifest.py; do
    [ -f "$f" ] || continue
    n=$(grep -rl "$(basename "$f")" docs README.md 2>/dev/null | tr '\n' ' ' || true)
    printf "  %-32s %s\n" "$(basename "$f")" "${n:-★ 어느 문서에도 없다}"
done

echo
echo "══ 2. 사라진 파일 — 문서에 아직 남아 있나"
echo
for f in basisno_calibrate.py basisno_check.py basisno_offset.json; do
    n=$(grep -rl "$f" docs README.md sources.yaml 2>/dev/null | tr '\n' ' ' || true)
    [ -n "$n" ] && printf "  %-32s ★ 아직 언급됨: %s\n" "$f" "$n"
done
echo "  (출력 없으면 정상)"

echo
echo "══ 3. 숫자 드리프트"
echo
python3 - <<'PY'
import json
import re
import subprocess
from pathlib import Path

# 산출물이 정본이다
seg = json.load(open("data/processed/segments.geojson", encoding="utf-8"))
n_seg = len(seg["features"])
props = seg["features"][0]["properties"]

man = json.load(open("data/processed/_manifest.json", encoding="utf-8"))
n_ds = len(man.get("datasets", []))

print(f"  산출물 정본: 구간 {n_seg} · 데이터셋 {n_ds}종")
print()

DOCS = ["README.md", "docs/MASTER.md", "docs/PLAN.md", "docs/DECISIONS.md"]
pats = {
    "구간 수": rf"\b(?!{n_seg}\b)(109\d|110\d|1266|641|222)\b",
    "데이터셋 종수": rf"\b(?!{n_ds}\b)(1[5-9]|2[0-9])종\b",
}
for label, pat in pats.items():
    print(f"  ── {label}")
    hit = 0
    for d in DOCS:
        p = Path(d)
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(pat, line) and "stale-ok" not in line:
                print(f"    {d}:{i}  {line.strip()[:88]}")
                hit += 1
                if hit > 12:
                    break
        if hit > 12:
            print("    ...")
            break
    if not hit:
        print("    없음")
    print()
PY

echo "══ 4. 필드 목록 — 산출물 vs MASTER §11"
echo
python3 - <<'PY'
import json
import re
from pathlib import Path

seg = json.load(open("data/processed/segments.geojson", encoding="utf-8"))
fields = set(seg["features"][0]["properties"].keys())

m = Path("docs/MASTER.md").read_text(encoding="utf-8")
documented = set(re.findall(r"^\|\s*`(\w+)`\s*\|", m, re.M))

miss = sorted(fields - documented)
extra = sorted(documented - fields - {"seg_id", "seg_uid"})
print(f"  산출물 필드 {len(fields)}개 · MASTER 표에 {len(documented)}개")
if miss:
    print(f"  ★ 문서에 없는 필드: {miss}")
else:
    print("  ✓ 산출물 필드 전부 문서화됨")
if extra:
    print(f"  · 문서에만 있는 항목(다른 표일 수 있음): {extra[:10]}")
PY

echo
echo "══ 5. 문서 간 충돌 후보"
echo
echo "  ── web/data 커밋 여부 (README main 판 vs MASTER §6-2)"
grep -rn "web/data" README.md docs/MASTER.md 2>/dev/null | grep -iE "커밋|금지|제외" | head -6 || true
echo
echo "  ── 경로 표기"
grep -rn "mnt/ssd\|mnt/f/" README.md docs/*.md 2>/dev/null | head -6 || true
echo
echo "  ── 문서 개수 규약 (셋? 넷?)"
grep -rn "문서는 셋\|문서 셋\|4개만 유지\|넷이 된" README.md docs/*.md 2>/dev/null | head -6 || true

echo
echo "══ 6. PLAN 남은 일 — 이번에 해소된 항목"
echo
grep -n "^| *[0-9]" docs/PLAN.md 2>/dev/null | head -20 || true

echo
echo "══ 7. 어조·표현 점검 (개인 표현 · 비공식 어투)"
echo
grep -rniE "내가 |우리가 |했음ㅋ|ㅇㅋ|같음|듯|ㅠ|ㅋㅋ|씨발|개소리" \
    docs/*.md README.md 2>/dev/null | head -12 || echo "  없음"

cat <<'NEXT'

══ 다음

  위 출력을 그대로 보여주면 4축 문서 갱신안을 만든다.
  원칙:
    · 산출물이 정본이다. 문서를 산출물에 맞춘다
    · 한 항목은 한 문서에만 산다 (PLAN 미래 · MASTER 현재 · DECISIONS 과거)
    · 완료된 것은 PLAN 에서 지우고 MASTER 에 결과를 쓴다
    · DECISIONS 는 append-only
NEXT
