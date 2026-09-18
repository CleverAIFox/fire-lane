#!/usr/bin/env bash
# .githooks/global-chain.sh — 전역 훅이 이 저장소의 훅을 **실제로 부르는가.**
#
#   bash .githooks/global-chain.sh              = --check
#   bash .githooks/global-chain.sh --check      도달을 **실행으로** 확인한다
#   bash .githooks/global-chain.sh --uninstall  W1 이 전역 훅에 붙인 죽은 블록을 뗀다
#
# ── 2026-09-18 (W1b) 이 파일이 다시 쓰인 이유 ───────────────────
# W1 판은 전역 훅에 스니펫을 **덧붙이고**, `--check` 는 그 스니펫의 마커 문자열이
# 있는지만 봤다. 실제로는 전역 훅의 `exit 0` **뒤에** 붙어 한 번도 안 불렸는데
# `--check` 는 통과했고 `verify.sh` 의 「훅 전역 연결」 단계도 초록이었다.
# 「있는가」를 묻고 「도는가」를 안 물은 것 — 1족이다.
#
# 그리고 덧붙일 필요조차 없었다. 전역 훅은 이미 후보 경로
# (`<repo>/.githooks/pre-commit` · `<repo>/scripts/hooks/pre-commit`) 를 뒤져
# **실행 가능한 것**을 부른다. 그래서 이 저장소가 할 일은 그 자리에 실행 가능한
# 파일을 두는 것뿐이고, 이 도구가 할 일은 **그것이 정말 불리는지 재는 것**뿐이다.
#
# ── 어떻게 재나 ────────────────────────────────────────────────
# `FIRE_LANE_HOOK_PROBE=1` 을 켜고 전역 훅을 돌린다. 저장소 훅은 그 변수를 보면
# 한 줄을 찍고 즉시 끝난다(`.githooks/pre-commit` 머리말). 그 줄이 나오면
# **전역 → 저장소 경로가 실제로 이어져 있다.**
#   · pre-commit 을 돌리지 않으므로 빠르고 부작용이 없다
#   · 문자열 존재가 아니라 실행 결과다 — 죽은 코드는 통과하지 못한다
#
# IN    git config --global core.hooksPath · <전역>/pre-commit · .githooks/pre-commit
# OUT   없음 (--uninstall 일 때만 전역 훅을 고친다. 먼저 백업한다)
set -uo pipefail

SENTINEL='[fire-lane] pre-commit 체인 진입'
MARK='# >>> fire-lane pre-commit chain'
END='# <<< fire-lane pre-commit chain'

hookdir() {
    local d
    d=$(git config --global core.hooksPath 2>/dev/null || true)
    [ -n "$d" ] || return 1
    printf '%s' "${d/#\~/$HOME}"
}

MODE="${1:---check}"

if ! D=$(hookdir); then
    cat >&2 <<'MSG'
✗ 전역 core.hooksPath 가 설정돼 있지 않다 — 커밋 시점 방어가 어느 저장소에도 안 돈다.

  이 저장소는 전역 훅을 주인으로 둔다(dms.py::hook/global-hooksPath 가 강제한다).
    mkdir -p ~/.githooks
    git config --global core.hooksPath ~/.githooks
  전역 훅은 저장소의 .githooks/pre-commit 을 찾아 부르도록 돼 있어야 한다.
MSG
    exit 2
fi
H="$D/pre-commit"

case "$MODE" in
  --uninstall)
      # ★ W1 이 붙인 죽은 블록을 뗀다. 전역 훅은 저장소 밖 파일이므로
      #   반드시 백업하고, 블록이 없으면 아무것도 안 한다.
      if [ ! -f "$H" ]; then
          echo "전역 훅이 없다: $H"; exit 0
      fi
      if ! grep -qF "$MARK" "$H"; then
          echo "✓ 뗄 블록이 없다 — 아무것도 안 바꿨다  ($H)"; exit 0
      fi
      B="$H.bak.$(date +%Y%m%d-%H%M%S)"
      cp "$H" "$B"
      awk -v s="$MARK" -v e="$END" '
          index($0, s) { skip = 1 }
          !skip        { print }
          index($0, e) { skip = 0 }' "$H" > "$H.tmp"
      mv "$H.tmp" "$H"
      chmod +x "$H"
      echo "  백업 $B"
      echo "✓ 죽은 블록을 뗐다 — $H"
      echo "  ★ 전역 훅은 원래대로 후보 경로에서 .githooks/pre-commit 을 부른다."
      echo "    확인:  bash .githooks/global-chain.sh --check"
      ;;

  --check|*)
      if [ ! -x "$H" ]; then
          echo "✗ 전역 훅이 없거나 실행 불가: $H"
          exit 1
      fi
      if [ ! -x .githooks/pre-commit ]; then
          echo "✗ .githooks/pre-commit 에 실행권한이 없다 — 전역 훅이 후보로 안 집는다"
          echo "  chmod +x .githooks/pre-commit"
          exit 1
      fi
      out=$(cd "$(git rev-parse --show-toplevel)" \
            && FIRE_LANE_HOOK_PROBE=1 bash "$H" 2>&1 || true)
      if printf '%s' "$out" | grep -qF "$SENTINEL"; then
          echo "✓ 전역 훅이 이 저장소의 .githooks/pre-commit 을 **실제로 부른다**  ($H)"
          exit 0
      fi
      echo "✗ 전역 훅이 이 저장소의 훅에 도달하지 못한다  ($H)"
      echo
      echo "  전역 훅의 출력 —"
      printf '%s\n' "$out" | sed 's/^/    /' | head -20
      echo
      echo "  흔한 원인 둘 —"
      echo "    ① 전역 훅이 저장소 훅에 도달하기 전에 끝난다 (exit 0 뒤에 뭔가 붙었다)"
      echo "       W1 이 붙인 블록이 남아 있으면:  bash .githooks/global-chain.sh --uninstall"
      echo "    ② 전역 훅이 후보 경로를 안 뒤진다 — 전역 훅 자체를 고쳐야 한다"
      echo "       bash -x '$H' 2>&1 | tail -25   로 추적해라"
      exit 1
      ;;
esac
