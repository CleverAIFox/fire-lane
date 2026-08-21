#!/usr/bin/env bash
# fix-lineage3.sh — mutates 자가대조 오탐 제거
#
#   저장소 루트에서:  bash fix-lineage3.sh
#
# ── 원인 (lineage.py verify ③) ─────────────────────────────
#   mine = lg.get(step.name, {}).get("inputs", {}).get(k)
#   if mine is not None and not _same(mine, now): 실패
#
#   terrain 은 segments.geojson 을 mutates 한다 — 읽고 z 를 덧쓴다.
#   그래서 terrain 이 기억하는 지문은 **z 가 든 상태**(32dd6aac)다.
#   segments 가 재실행되면 z 없는 새 파일(372ee587)이 된다.
#   구조적으로 매번 다르다. 이것은 오탐이다.
#
#   _manifest.json 도 같다 — terrain 이 자기 기록을 덧쓴다.
#
# ── 무엇을 남기고 무엇을 빼나 ★ ────────────────────────────
#   ② 상류가 쓴 것과 지금 디스크 대조   → **그대로 둔다**
#      08-18 사고(ngii1k 14336 기록 vs 옛 레이어 6675)를 잡는 것이 이쪽이다.
#      mutates 여도 상류 기록과는 대조해야 한다.
#
#   ③ 자기가 지난번에 읽은 것과 대조     → mutates 만 제외
#      자기가 덧쓴 것을 자기가 다시 읽으면 다른 게 당연하다.
#      reads 는 아무도 덧쓰지 않으므로 ③ 이 그대로 작동한다.
#
#   즉 방어는 유지되고 오탐만 사라진다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

python3 - <<'PATCH'
import sys
from pathlib import Path

p = Path("src/etl/lineage.py")
s = p.read_text(encoding="utf-8")
if "_mutated_keys" in s:
    print("  · 이미 적용됨")
    sys.exit(0)

# 1) mutates 키 집합을 만드는 지점 — consumes 순회 직전
old_loop = '''    problems: list[str] = []
    unknown: list[str] = []
    for p in expand(step.consumes):'''
new_loop = '''    problems: list[str] = []
    unknown: list[str] = []

    # ★ mutates 는 이 단계가 읽고 그 자리에 덧쓰는 대상이다. 그래서 이 단계가
    #   기억하는 지문은 '덧쓴 뒤' 상태이고, 상류가 재실행되면 '덧쓰기 전'
    #   상태가 된다. 구조적으로 매번 다르다 — ③ 자가대조의 오탐이다.
    #
    #   terrain 이 segments.geojson 에 z 를 넣는 것이 그 사례다.
    #   기억 32dd6aac(z 있음) vs 디스크 372ee587(z 없음).
    #
    #   ② 상류 대조는 그대로 둔다. 08-18 사고를 잡는 것이 그쪽이다.
    _mutated_keys = {_key(root, m) for m in expand(step.mutates)}

    for p in expand(step.consumes):'''
if old_loop not in s:
    print("  ✗ consumes 순회 앵커 없음")
    sys.exit(1)
s = s.replace(old_loop, new_loop, 1)

# 2) ③ 에서 mutates 제외
old3 = '''        # ③ 자기가 지난번에 읽은 것과 다른가 — 상류가 없는 raw 도 여기서 걸린다
        mine = lg.get(step.name, {}).get("inputs", {}).get(k)
        if mine is not None and not _same(mine, now):'''
new3 = '''        # ③ 자기가 지난번에 읽은 것과 다른가 — 상류가 없는 raw 도 여기서 걸린다
        #   단, mutates 는 제외한다. 자기가 덧쓴 것을 자기가 다시 읽으면
        #   다른 것이 정상이다. reads 는 아무도 덧쓰지 않으므로 그대로 본다.
        if k in _mutated_keys:
            continue
        mine = lg.get(step.name, {}).get("inputs", {}).get(k)
        if mine is not None and not _same(mine, now):'''
if old3 not in s:
    print("  ✗ ③ 앵커 없음")
    sys.exit(1)
s = s.replace(old3, new3, 1)

p.write_text(s, encoding="utf-8")
print("  ✓ src/etl/lineage.py — ③ 에서 mutates 제외")
PATCH

python3 -m py_compile src/etl/lineage.py && echo "  ✓ 문법"

echo
echo "── 회귀 확인"
uv run python -m pytest tests/test_guards.py tests/test_reproducibility.py -q 2>&1 | tail -4

git add -A
git diff --cached --quiet || {
  git commit -q -m "fix: 계보 ③ 자가대조에서 mutates 제외 — 구조적 오탐

terrain 은 segments.geojson 을 읽고 z 를 덧쓴다(mutates). 그래서 terrain 이
기억하는 지문은 'z 있음'(32dd6aac) 이고, segments 가 재실행되면 'z 없음'
(372ee587) 이 된다. 매번 다르다. _manifest.json 도 같다.

② 상류 대조는 그대로 둔다 — 08-18 사고(ngii1k 14336 기록 vs 옛 레이어
6675 사용)를 잡는 것이 그쪽이다. reads 는 아무도 덧쓰지 않으므로 ③ 도
계속 작동한다. 방어는 유지되고 오탐만 사라진다."
  echo "  ✓ 커밋"
}

cat <<'NEXT'

── 확인

  flrun --from segments

  terrain 이 계보 통과해야 한다. 전량 실행 직후 이 조합은
  오늘 한 번도 성공한 적이 없다.
NEXT
