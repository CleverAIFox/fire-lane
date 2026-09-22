#!/usr/bin/env bash
# tools/inbox_fl.sh — **INBOX 에 `fl.sh` 라는 이름으로 두는 부트스트랩.**  (DECISIONS §214-1)
#
#   bash "$FIRE_LANE_INBOX/fl.sh" feat/x --all
#
# 이것은 배치 도구가 아니다. 진짜 도구(`tools/fl.sh`)를 **어느 판으로 돌릴지** 고르고 넘긴다.
#
#   1. 저장소의 origin/part/infra 판 tools/fl.sh 를 씨앗으로 깐다 (있으면)
#   2. INBOX 의 패치(zip 안 · 밖)가 tools/fl.sh 를 만들거나 고치면 그것을 씨앗 위에 얹는다
#   3. 그 결과를 실행한다
#
# ★ 왜 2 가 있나 — 배치 도구를 고치는 배치는 **자기 새 판으로** 돌아야 한다. 옛 판으로
#   돌면 그 배치가 고친 결함이 그 배치를 막는다. 이 파일 자신은 거의 안 바뀌게 짧게 둔다.
# ★ 저장소 판은 체크아웃이 아니라 `origin/part/infra` 에서 꺼낸다 — 체크아웃은 어느
#   가지에 서 있는지 모른다.
set -euo pipefail
IN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${FIRE_LANE_REPO:-$HOME/projects/fire-lane}"
T=$(mktemp -d /tmp/fl-boot.XXXXXX)
mkdir -p "$T/tools"
if git -C "$REPO" cat-file -e origin/part/infra:tools/fl.sh 2>/dev/null; then
  git -C "$REPO" show origin/part/infra:tools/fl.sh > "$T/tools/fl.sh"
  chmod +x "$T/tools/fl.sh"   # ★ 저장소 판은 755 다. 안 맞추면 git apply 가 「type 100644, expected 100755」 로 운다
  SRC="저장소 origin/part/infra"
else
  SRC=""
fi
# shellcheck disable=SC2012  # 최신 하나만 고른다
ZIP=$(ls -t "$IN"/fire-lane-*.zip 2>/dev/null | head -1 || true)
if [ -n "$ZIP" ]; then mkdir -p "$T/z"; unzip -oq "$ZIP" -d "$T/z"; fi
# ★ 평소 절차(`unzip -o zip -d INBOX`)는 zip 과 풀린 패치를 **둘 다** INBOX 에 남긴다.
#   같은 패치를 두 번 얹으면 두 번째가 실패한다 — 내용 지문으로 한 번만 본다.
SEEN=" "
# ★ INBOX 는 공용 다운로드 폴더다 — 남의 저장소 패치가 있다. zip 이 있으면 zip 안만,
#   없으면 `0001-….patch` 꼴만 본다(tools/fl.sh 의 pick_patches 와 같은 규칙).
LOOSE=()
if [ -z "$ZIP" ]; then
  for p in "$IN"/*.patch; do [[ "$(basename "$p")" =~ ^[0-9]{4}-.+\.patch$ ]] && LOOSE+=("$p"); done
fi
for p in "$T"/z/*.patch "${LOOSE[@]:-}"; do
  [ -e "$p" ] || continue
  h=$(sha256sum "$p" | cut -c1-16)
  case "$SEEN" in *" $h "*) continue ;; esac
  SEEN="$SEEN$h "
  if grep -q '^+++ b/tools/fl.sh$' "$p"; then
    ( cd "$T" && git apply --include=tools/fl.sh "$p" ) \
      || { echo "✗ $(basename "$p") 의 tools/fl.sh 가 씨앗에 안 붙는다 — 옛 패치가 INBOX 에 남았나"; exit 1; }
    SRC="패치 $(basename "$p")"
  fi
done
[ -n "$SRC" ] || { echo "✗ tools/fl.sh 를 어디서도 못 찾았다 (저장소: $REPO · INBOX: $IN)"; exit 1; }
printf '\033[90mfl 부트스트랩 — %s\033[0m\n' "$SRC"
export FIRE_LANE_REPO="$REPO" FL_CMD="bash $IN/fl.sh"
exec bash "$T/tools/fl.sh" "$@"
