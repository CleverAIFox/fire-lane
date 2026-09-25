#!/usr/bin/env bash
# tools/inbox_go.sh — **INBOX 에 `go.sh` 라는 이름으로 두는 한 줄 진입점.**  (DECISIONS §256)
#
#   cd ~/projects/fire-lane && bash tools/inbox_go.sh     ← 저장소에 들어온 뒤로는 이 한 줄
#   bash "$FIRE_LANE_INBOX/go.sh"                         ← 아직 안 들어왔을 때(zip 안 사본)
#
# ★ **`~/Downloads` 가 아니다.** WSL 에서 `~` 는 리눅스 홈(`/home/fox`)이고 브라우저
#   다운로드는 윈도우 쪽(`/mnt/c/Users/Fox/Downloads`)에 떨어진다. 그 경로가
#   `.env` 의 `$FIRE_LANE_INBOX` 다 — **경로를 손으로 쓰지 말고 그 변수를 쓴다.**
#   2026-09-25 에 안내에 `~/Downloads` 라 적어 실제로 `unzip` 이 못 찾았다.
#
# 이것이 하는 일은 넷이고, 종전에는 **사람이 매번 손으로 쳤다** —
#
#   ① 저장소로 들어간다            cd ~/projects/fire-lane
#   ② `.env` 를 적재한다           set -a; . ./.env; set +a
#   ③ 브랜치 이름을 정한다          PR_TITLE 에서 뽑는다
#   ④ 배치를 돌린다                bash "$FIRE_LANE_INBOX/fl.sh" <브랜치> --all [--relock]
#
# ★ 왜 이것이 도구가 되어야 하나 (2026-09-25). 네 줄을 손으로 치는 동안 매번
#   같은 세 가지가 틀릴 수 있다 — `.env` 를 안 태워서 `$FIRE_LANE_INBOX` 가
#   비거나, 브랜치 이름을 이전 배치 것으로 재사용하거나, **`--relock` 을 잊는
#   것**이다. 셋째가 제일 비싸다: 판정 지문이 바뀌는 배치에서 재잠금을 빼면
#   `golden check` 가 다음 실행부터 계속 울고, 그 빨간불을 습관으로 만든다
#   (DECISIONS §69). 그래서 **필요 여부를 사람이 기억하지 않는다** — zip 이
#   자기 PR 본문에 적어 두고 이 스크립트가 그것을 읽는다.
#
# ★ 이 파일 자신은 INBOX 에 `go.sh` 로 복사돼 배포된다. `tools/inbox_fl.sh` 와
#   같은 규율이다 — INBOX 에만 사는 스크립트는 버전 관리·시험·리뷰 밖이고
#   INBOX 를 비우는 순간 사라진다(그날 실제로 사라졌다).
#
# IN    $FIRE_LANE_INBOX/fire-lane-*.zip (최신) · $FIRE_LANE_INBOX/fl.sh
#       $FIRE_LANE_REPO/.env
# OUT   없음 (`fl.sh` 가 낸다)
# PARAM 인자 하나를 주면 그것을 브랜치 이름으로 쓴다. 없으면 PR_TITLE 에서 뽑는다.
# 밖    배치 내용을 판단하지 않는다 — 적용·검증·PR 은 전부 `tools/fl.sh` 소관이다.
#       여기서 하는 일은 「사람이 매번 틀리는 네 줄」을 없애는 것뿐이다.
set -euo pipefail

REPO="${FIRE_LANE_REPO:-$HOME/projects/fire-lane}"
IN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

c() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }

[ -d "$REPO/.git" ] || { c 31 "✗ 저장소가 없다: $REPO"; echo "  FIRE_LANE_REPO 로 알려줘라"; exit 1; }
cd "$REPO"

# ① .env — `$FIRE_LANE_INBOX` · `$VWORLD_KEY` 가 여기서 온다.
#    ★ 값을 찍지 않는다. 있는지만 본다.
if [ -f .env ]; then
  set -a; . ./.env; set +a
  c 90 "· .env 적재 ($(grep -c '=' .env 2>/dev/null || echo 0)줄)"
else
  c 33 "! .env 가 없다 — INBOX 경로를 인자나 환경변수로 줘야 한다"
fi
INBOX="${FIRE_LANE_INBOX:-$IN}"

# ② 최신 zip 을 풀어 둔다. `fl.sh` 는 zip 안을 직접 보지만, `PR_TITLE` 은
#    풀려 있어야 읽는다.
# shellcheck disable=SC2012  # 최신 하나만 고른다
ZIP=$(ls -t "$INBOX"/fire-lane-*.zip 2>/dev/null | head -1 || true)
if [ -n "$ZIP" ]; then
  unzip -oq "$ZIP" -d "$INBOX"
  c 90 "· 풀었다 $(basename "$ZIP")"
else
  c 33 "! zip 이 없다 — 풀린 패치를 쓴다"
fi

[ -f "$INBOX/fl.sh" ] || { c 31 "✗ $INBOX/fl.sh 가 없다 — zip 에 들어 있어야 한다"; exit 1; }

# ③ 브랜치 — 인자가 없으면 PR_TITLE 에서 뽑는다.
#    ★ 날짜를 붙인다. 같은 이름을 재사용하면 `fl.sh` 가 이전 가지를 만나 멈춘다.
BR="${1:-}"
if [ -z "$BR" ]; then
  SLUG=feat/batch
  if [ -f "$INBOX/PR_TITLE" ]; then
    case "$(cat "$INBOX/PR_TITLE")" in
      *봉인*)   SLUG=feat/seal ;;
      *아키텍처*|*폐포*) SLUG=feat/arch ;;
      *감사*)   SLUG=feat/audit ;;
    esac
  fi
  BR="$SLUG-$(date +%m%d)"
fi

# ④ 재잠금 — **사람이 기억하지 않는다.** PR 본문이 요구하면 붙인다.
#    ★ PR_BODY 의 「재잠금은 필요하다」가 그 선언이다. 없으면 안 붙인다 —
#      필요 없는 재잠금은 파이프라인 전량을 한 번 더 돌린다(몇 분).
RELOCK=()
if [ -f "$INBOX/PR_BODY.md" ] && grep -q '재잠금은 필요하다' "$INBOX/PR_BODY.md"; then
  RELOCK=(--relock)
  c 33 "· PR 본문이 재잠금을 요구한다 — --relock 을 붙인다"
fi

c 96 "▶ $BR  --all ${RELOCK[*]:-}"
echo
exec bash "$INBOX/fl.sh" "$BR" --all "${RELOCK[@]}"
