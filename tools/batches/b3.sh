#!/usr/bin/env bash
# tools/batches/b3.sh — B3(사본 제거) 일괄 적용. **스냅샷 기반.**
#
#   bash tools/batches/b3.sh              무엇이 바뀌는지만 (기본값)
#   bash tools/batches/b3.sh --apply      적용 + 검증
#   bash tools/batches/b3.sh --verify     적용 없이 검증만
#   bash tools/batches/b3.sh --rollback   직전 --apply 를 통째로 되돌린다
#
# ══ 왜 .sh 인가 ═══════════════════════════════════════════════════
# 배치 넷을 손으로 순서대로 치면 중간에 하나가 죽었을 때 저장소가
# **반만 적용된 상태**로 남는다. 그 상태는 어느 배치의 것도 아니라
# 다음 세션이 읽을 수 없다. 여기서는 셋을 묶는다 —
#
#   ⒜ 스냅샷    손대기 전 대상 파일의 sha256 을 적고 원본을 통째로 보관
#   ⒝ 일괄      배치 넷을 순서대로. 하나라도 죽으면 **그 자리에서 멈춘다**
#   ⒞ 되돌리기  --rollback 이 ⒜ 의 보관본으로 되돌린다. git 없이도 된다
#
# ★ 이 파일은 **일회성**이다(HANDOFF 원칙 ②). 판별식 — "내년에도 이걸
#   돌릴 일이 있나". 없다. B3 는 한 번 닫으면 끝이고, 사본이 다시 생기는지
#   보는 일은 `widen W2` 같은 **재현적 도구**가 맡는다. 그래서
#   `tools/batches/` 에 있고 `tools/` 에 있지 않다.
#
# ★ 검사를 두 벌 만들지 않는다. 아래 검증 단계는 전부 기존 도구를 부른다 —
#   `deadcheck` · `widen` · `verify.sh` · `pytest`. 여기서 새로 세지 않는다.
# ══════════════════════════════════════════════════════════════════
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1
ROOT=$(pwd)
# ★ 저장소 **밖**에 둔다. 두 번 옮겼다 —
#   ⒜ `.work/b3` 에 뒀더니 `tools/tidy.py` 가 `.work` 를 "파이프라인 임시" 로
#      알고 지운다. verify.sh 를 돌리고 나면 보관본이 사라져 --rollback 이
#      "보관본이 없다" 를 냈다. 실측으로 잡았다.
#   ⒝ 저장소 루트에 두면 `루트 잔재` 검사가 운다(원칙 ③ — 검사가 우는 걸
#      닫는 것까지가 배치인데, 여기서는 애초에 울릴 이유가 없다).
#   그래서 $TMPDIR 다. 재부팅하면 날아가지만 일회성 배치에는 충분하다.
WORK="${TMPDIR:-/tmp}/fire-lane-b3"
KEEP="$WORK/rollback"

# ★ WSL. `uv run python` 이 기본이고, uv 가 없는 곳(컨테이너·CI)에서는
#   PY 로 갈아끼운다:  PY="python3" bash tools/batches/b3.sh --apply
PY=${PY:-"uv run python"}

R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; C=$'\033[36m'; D=$'\033[90m'; Z=$'\033[0m'

MODE=${1:-"--dry-run"}

# ── B3 배치. 순서가 있다 ──────────────────────────────────────────
#   params → const → rules.  앞의 것이 뒤의 것의 전제는 아니지만,
#   순서를 고정해야 전이표가 매번 같은 모양으로 나온다.
BATCHES=(
    "tools/batches/b3_params.py|임계값 3벌 — COV_MIN · NODE_TOL · TRUCK"
    "tools/batches/b3_const.py|인코딩 후보 4벌 · TEXT_EXT 3벌 — 모으되 합치지 않는다"
    "tools/batches/b3_rules.py|규칙 조립 4벌 — passthrough_rules() 정본화"
)

# ── 스냅샷 대상. 배치가 건드리는 파일 전부 ────────────────────────
TARGETS=(
    tools/jijeok_probe.py
    tools/route_probe.py
    tools/wmax_audit.py
    tools/encoding_check.py
    src/firelane/encoding.py
    src/firelane/ingest.py
    src/firelane/inventory.py
    src/firelane/contract.py
    src/firelane/prep.py
    src/firelane/normalize_raw.py
    tests/test_normalize_rules.py
    tests/test_place_idempotent.py
)

snapshot() {                  # snapshot <파일명>
    local out="$WORK/$1"
    : > "$out"
    for f in "${TARGETS[@]}"; do
        if [ -f "$ROOT/$f" ]; then
            printf '%s  %s\n' "$(sha256sum "$ROOT/$f" | cut -d' ' -f1)" "$f" >> "$out"
        else
            printf '%s  %s\n' "................................................................" "$f" >> "$out"
        fi
    done
}

# ══ --rollback ════════════════════════════════════════════════════
if [ "$MODE" = "--rollback" ]; then
    [ -d "$KEEP" ] || { printf '%s★ 보관본이 없다 — %s%s\n' "$R" "$KEEP" "$Z"; exit 1; }
    n=0
    for f in "${TARGETS[@]}"; do
        [ -f "$KEEP/$f" ] && { mkdir -p "$(dirname "$ROOT/$f")"; cp "$KEEP/$f" "$ROOT/$f"; n=$((n+1)); }
    done
    printf '%s되돌렸다 — %d 파일%s\n' "$G" "$n" "$Z"
    printf '%s  ★ 배치가 새로 만든 파일은 여기서 안 지운다. 지금 B3 는 새 파일을\n'  "$D"
    printf '    만들지 않으므로 문제 없다. 나중에 만드는 배치를 넣으면 이 줄을 고쳐라.%s\n' "$Z"
    exit 0
fi

mkdir -p "$WORK"
printf '\n%s╔══ B3 · 사본 제거 ══════════════════════════════════════════%s\n' "$C" "$Z"
printf '%s║  모드 %s   PY=%s%s\n' "$C" "$MODE" "$PY" "$Z"
printf '%s╚════════════════════════════════════════════════════════════%s\n\n' "$C" "$Z"

# ══ ⒜ 스냅샷 ══════════════════════════════════════════════════════
snapshot before.sha
if [ "$MODE" = "--apply" ]; then
    rm -rf "$KEEP"
    for f in "${TARGETS[@]}"; do
        [ -f "$ROOT/$f" ] && { mkdir -p "$KEEP/$(dirname "$f")"; cp "$ROOT/$f" "$KEEP/$f"; }
    done
    printf '%s스냅샷%s  %d 파일 · 보관 %s\n\n' "$G" "$Z" "${#TARGETS[@]}" "$KEEP"
else
    printf '%s스냅샷%s  %d 파일 (dry-run — 보관 안 함)\n\n' "$D" "$Z" "${#TARGETS[@]}"
fi

# ══ ⒝ 배치 ════════════════════════════════════════════════════════
if [ "$MODE" != "--verify" ]; then
    FLAG=""; [ "$MODE" = "--apply" ] && FLAG="--apply"
    for row in "${BATCHES[@]}"; do
        script=${row%%|*}; desc=${row#*|}
        printf '%s── %s%s\n%s   %s%s\n' "$C" "$(basename "$script")" "$Z" "$D" "$desc" "$Z"
        if ! $PY "$script" $FLAG 2>&1 | sed 's/^/   /'; then
            printf '\n%s★ %s 가 죽었다. 여기서 멈춘다.%s\n' "$R" "$script" "$Z"
            [ "$MODE" = "--apply" ] && printf '%s  되돌리려면 — bash tools/batches/b3.sh --rollback%s\n' "$Y" "$Z"
            exit 1
        fi
        echo
    done
fi

# ══ ⒞ 전이표 ══════════════════════════════════════════════════════
snapshot after.sha
printf '%s── 전이표%s\n' "$C" "$Z"
moved=0
while read -r h1 f1 && read -r h2 _ <&3; do
    if [ "$h1" != "$h2" ]; then
        printf '   %s변경%s  %s\n' "$Y" "$Z" "$f1"
        moved=$((moved+1))
    fi
done < "$WORK/before.sha" 3< "$WORK/after.sha"
[ "$moved" -eq 0 ] && printf '   %s변경 없음%s (이미 적용됐거나 dry-run)\n' "$D" "$Z"
printf '   %d / %d 파일\n\n' "$moved" "${#TARGETS[@]}"

# ══ ⒟ 검증 — 전부 기존 도구다. 새로 세지 않는다 ═══════════════════
printf '%s── 검증%s\n' "$C" "$Z"

printf '%s   deadcheck%s\n' "$D" "$Z"
$PY tools/deadcheck.py 2>&1 | tail -3 | sed 's/^/     /'

printf '%s   widen  ★ W2(임계값 정본)가 0건이어야 한다%s\n' "$D" "$Z"
$PY tools/widen.py 2>&1 | grep -E 'W[1-6]|합계' | sed 's/^/     /'

printf '%s   pytest%s\n' "$D" "$Z"
$PY -m pytest tests -q 2>&1 | tail -4 | sed 's/^/     /'

printf '%s   verify.sh%s\n' "$D" "$Z"
bash tools/verify.sh 2>&1 | tail -6 | sed 's/^/     /'

echo
printf '%s다음%s\n' "$C" "$Z"
printf '   · widen W2 가 0건이면 → `--selftest` 대신 사본을 한 줄 되박아\n'
printf '     프로브가 살아 있는지 본다. 0건이 청결인지 죽음인지는\n'
printf '     그것 말고 가르는 방법이 없다(HANDOFF 원칙 ④).\n'
printf '   · B3 남은 것(union-find 5벌 · 등거리 근사 3벌 · 색 사본 5벌)은\n'
printf '     tools/batches/README.md 의 B3 표를 볼 것.\n'
printf '   · 되돌리기 — bash tools/batches/b3.sh --rollback\n\n'
