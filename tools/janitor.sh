#!/usr/bin/env bash
# tools/janitor.sh — 청소 도구 셋의 **입구 하나.** 읽기만 한다.
#
#   bash tools/janitor.sh            층별 건수를 한 표로
#   bash tools/janitor.sh --verbose  각 도구의 출력을 그대로
#
# ══ 왜 묶고, 왜 안 합치나 ═════════════════════════════════════════
# 셋은 **층이 다르다.** 합쳐서 한 도구로 만들면 층 구분이 사라지고,
# 어느 층이 더러운지를 못 가린다.
#
#   hygiene.sh   기계    ~/projects · 홈 · 마운트 · .venv 셔뱅 · .env
#   tidy.py      저장소  .work · 캐시 · 격리 산출물 · 루트 잔재
#   sweep.py     레이크  다운로드·레이크에서 근거 없는 것
#
# ★ **하나가 죽어도 나머지는 돈다.** 이것이 묶는 유일한 이유다.
#   `/mnt/f` 가 빠지면 `sweep` 이 실패하는데, 그때 `tidy` 까지 안 돌면
#   저장소를 못 치운다. 2026-09-12~13 에 그 상황을 여러 번 겪었다.
#   그래서 각 단계는 **실패해도 다음으로 넘어간다.**
#
# ★ **여기서 지우지 않는다.** `--yes` 같은 것을 받지 않는다.
#   지우는 것은 각 도구가 자기 근거로 한다 — 무엇을 왜 지우는지는
#   그 도구가 알고 이 껍데기는 모른다. 근거를 찾고 지우는 것과
#   지울 만해 보여서 지우는 것은 다르다.
#
# ★ `hygiene.sh` 만 저장소 밖(`~/.local/bin`)에 있다. 기계를 보는 도구라
#   저장소에 두면 저장소마다 사본이 생긴다. 없으면 그 줄만 건너뛴다.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
VERBOSE=0; [ "${1:-}" = "--verbose" ] && VERBOSE=1
C=$'\033[36m'; G=$'\033[32m'; Y=$'\033[33m'; D=$'\033[90m'; R=$'\033[31m'; Z=$'\033[0m'
PY=${PY:-"uv run python"}

printf '\n%s══ 청소 — 층별 ══%s\n\n' "$C" "$Z"
ROWS=()

run() {   # run <층> <이름> <건수를 뽑는 정규식> <명령...>
    local layer=$1 name=$2 rx=$3; shift 3
    local out rc n
    out=$("$@" 2>&1); rc=$?
    if [ "$VERBOSE" = 1 ]; then
        printf '%s── %s%s\n%s\n' "$C" "$name" "$Z" "$out"
    fi
    if [ $rc -ne 0 ]; then
        # ★ 실패를 0건으로 적지 않는다. 못 잰 것과 깨끗한 것은 다르다.
        ROWS+=("$layer|$name|${R}못 잼${Z}|$(printf '%s' "$out" | tail -1 | cut -c1-52)")
        return
    fi
    n=$(printf '%s' "$out" | grep -oP "$rx" | tail -1)
    ROWS+=("$layer|$name|${n:-?}|$(printf '%s' "$out" | tail -1 | cut -c1-52)")
}

# ── 기계 ─────────────────────────────────────────────────────────
if [ -x "$HOME/.local/bin/hygiene.sh" ]; then
    run 기계 hygiene '[0-9]+(?=건)' bash "$HOME/.local/bin/hygiene.sh"
else
    ROWS+=("기계|hygiene|${D}없음${Z}|~/.local/bin/hygiene.sh 를 설치하면 돈다")
fi

# ── 저장소 ───────────────────────────────────────────────────────
run 저장소 tidy '[0-9]+(?=건)' $PY tools/tidy.py

# ── 레이크 ───────────────────────────────────────────────────────
run 레이크 sweep '[0-9]+(?=건)' $PY tools/sweep.py

# ── 표 ───────────────────────────────────────────────────────────
printf '  %-6s %-9s %-8s %s\n' 층 도구 건수 마지막줄
printf '  %s\n' "$(printf '─%.0s' {1..70})"
bad=0
for r in "${ROWS[@]}"; do
    IFS='|' read -r a b c d <<< "$r"
    printf '  %-6s %-9s %-8b %s%s%s\n' "$a" "$b" "$c" "$D" "$d" "$Z"
    [ "$c" = "0" ] || bad=$((bad+1))
done

printf '\n'
if [ "$bad" -eq 0 ]; then
    printf '  %s✓ 세 층 전부 0건%s\n\n' "$G" "$Z"
else
    printf '  %s실제로 지우려면 각 도구를 직접 부른다 — 근거는 그쪽에 있다%s\n' "$Y" "$Z"
    printf '%s    uv run python tools/tidy.py --yes\n' "$D"
    printf '    uv run python tools/sweep.py --sweep --yes\n'
    printf '    bash ~/.local/bin/hygiene.sh          ★ 읽기 전용. 지우지 않는다%s\n\n' "$Z"
fi
