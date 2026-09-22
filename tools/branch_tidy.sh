#!/usr/bin/env bash
# tools/branch_tidy.sh — 가지 · PR 정리.  (DECISIONS §214-1)
#
#   bash tools/branch_tidy.sh              대화형 — 열린 PR 닫기 · 원격 가지 · 로컬 가지 (단계마다 y/N)
#   bash tools/branch_tidy.sh --auto       비대화 — fl.sh 가 배치 끝에 부른다
#   bash tools/branch_tidy.sh --keep feat/x   이 가지(와 그 PR)는 건드리지 않는다
#   bash tools/branch_tidy.sh --auto --close-bots   ★ fl.sh 기본 — 봇(dependabot) PR 은 닫고 가지도 지운다
#
# ★ 2026-09-22 (DECISIONS §217-4) `--close-bots`. 사용자 지적 「PR 도 열린 거 닫고 가지 정리도
#   해야 할 거 아니냐」. 봇 PR 은 흐름(feat → part → dev → main) 밖이라 **그대로 머지할 길이
#   없고**(§212-3), 매 배치 끝에 「열린 PR 5」 경고로 남았다. 봇 것만 자동으로 닫는다 —
#   사람 PR 은 여전히 대화형에서만 닫는다(남의 작업일 수 있다). 메이저 판은 dependabot 이
#   이미 안 내고(§215-3), 보안 업데이트는 닫혀도 다음 주기에 다시 온다.
#
# ★ 지키는 것: main · dev · part/infra · part/gis · part/cv · --keep · 태그 전부.
#
# ★ `--auto` 는 **되돌릴 수 없는 일을 하지 않는다.**
#     · PR 은 닫지 않고 목록만 보고한다 — 남의 PR 일 수 있다
#     · 원격 가지는 지우지 않는다 — 스쿼시 머지가 feat 가지를 이미 지운다
#     · 로컬 가지는 **내용이 origin/main 에 들어간 것만** 지운다
#       (스쿼시라 커밋은 조상이 아니다 → 「가지가 바꾼 파일이 main 에서 같은 내용인가」로 본다)
#     · 지킨 가지는 ff 만. 갈라졌으면 고치지 않고 알린다
#
# ★ 2026-09-22 에 INBOX 에만 있던 tidy.sh 를 정본화했다. 그날 첫 실행이 dependabot PR
#   아홉을 닫았고, 로컬 feat 둘을 지웠고, part/cv 가 갈라진 것을 알렸다.
set -euo pipefail
REPO=CleverAIFox/fire-lane
KEEP_RE='^(main|dev|part/infra|part/gis|part/cv)$'
AUTO=0
BOTS=0
EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --auto) AUTO=1; shift ;;
    --close-bots) BOTS=1; shift ;;
    --keep) EXTRA+=("$2"); shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
keep() {
  [[ "$1" =~ $KEEP_RE ]] && return 0
  local k
  for k in "${EXTRA[@]:-}"; do [ -n "$k" ] && [ "$1" = "$k" ] && return 0; done
  return 1
}
ask() {
  [ "$AUTO" = 1 ] && return 1
  local a; read -r -p "$1 [y/N] " a </dev/tty || a=""
  [ "$a" = y ] || [ "$a" = Y ]
}
say() { printf '\n══ %s\n' "$*"; }
WARN=0

cd "$(git rev-parse --show-toplevel)"
git fetch -q --prune origin
HAVE_GH=1
gh auth status >/dev/null 2>&1 || HAVE_GH=0

# 가지가 바꾼 파일들이 origin/main 에서 같은 내용이면 들어간 것이다
merged_by_content() {
  local b=$1 ch=()
  mapfile -t ch < <(git diff --name-only "origin/main...$b" 2>/dev/null || true)
  [ ${#ch[@]} -eq 0 ] && return 0
  git diff --quiet "$b" origin/main -- "${ch[@]}" 2>/dev/null
}

# 봇 PR 의 묶음 — dependabot 가지는 `dependabot/<생태계>/<묶음·패키지>-<판>` 이다.
#   ★ 독립 검토 2026-09-22 — `${head%/*}` 로 자르면 생태계 하나가 전부 한 묶음이 돼 서로 다른
#   묶음(geo · dev-tools · rest)이 「밀렸다」로 닫혔다. 끝의 판(숫자 · 해시)만 떼어낸다.
bot_group() { printf '%s' "$1" | sed -E 's/-[0-9a-f]{6,}$//; s/-v?[0-9][0-9.]*$//'; }

# ── 1. 열린 PR ──────────────────────────────────────────────────
say "1. 열린 PR"
CLOSE=()
if [ "$HAVE_GH" = 0 ]; then
  echo "   gh 로그인이 없다 — PR 은 못 본다"; WARN=1
else
  mapfile -t PRS < <(gh pr list -R "$REPO" --state open --limit 200 \
    --json number,headRefName,baseRefName,title,author \
    --jq '.[] | "\(.number)\t\(.headRefName)\t\(.baseRefName)\t\(.author.login)\t\(.title)"')
  BOTPR=()
  for l in "${PRS[@]:-}"; do
    [ -z "$l" ] && continue
    IFS=$'\t' read -r n head base who title <<<"$l"
    if keep "$head"; then printf '   지킴  #%s  %s → %s\n' "$n" "$head" "$base"; continue; fi
    printf '   열림  #%-4s %-52s → %-6s %s\n' "$n" "$head" "$base" "$title"
    CLOSE+=("$n")
    case "$who" in *dependabot*) BOTPR+=("$n") ;; esac
  done
  # ★ 2026-09-22 (DECISIONS §218-4 · 토트 모범). 봇 PR 을 **전부** 닫던 것을 **청소(vacuum)** 로 바꿨다.
  #   봇 PR 은 알림이다 — 전부 닫으면 막는 목록(워크플로 정적 검사)과 짝인 「알리는 장치」 가
  #   배치마다 지워진다(setup-node@v4 · setup-uv@v3 가 Node 20 퇴역 목록에 걸린 채 남은 이유).
  #   닫는 것은 둘뿐이다 —
  #     ① 흐름 밖으로 온 것(base 가 part/infra 가 아니다 · target-branch 이전 설정의 잔재)
  #     ② 같은 묶음의 더 새 PR 에 **밀린** 것(head 가 같은 묶음 접두 · 번호가 작다)
  #   나머지는 남기고 목록을 낸다 — 사람이 의존성 배치로 받는다. 닫기 전에 diff 를 보관한다.
  if [ "$AUTO" = 1 ] && [ "$BOTS" = 1 ] && [ ${#BOTPR[@]} -gt 0 ]; then
    ARCH="${FIRE_LANE_INBOX:-}/_applied"
    declare -A NEWEST=()
    for l in "${PRS[@]:-}"; do
      IFS=$'\t' read -r n head base who title <<<"$l"
      case "$who" in *dependabot*) ;; *) continue ;; esac
      grp=$(bot_group "$head")
      [ -z "${NEWEST[$grp]:-}" ] || [ "$n" -gt "${NEWEST[$grp]}" ] && NEWEST[$grp]=$n
    done
    VAC=()
    for l in "${PRS[@]:-}"; do
      IFS=$'\t' read -r n head base who title <<<"$l"
      case "$who" in *dependabot*) ;; *) continue ;; esac
      why=""
      # ★ 보안 업데이트는 target-branch 를 무시하고 기본 가지로 온다(dependabot 규칙) — 닫지 않는다
      case "$title" in *"[security]"*|*[Ss]ecurity*) echo "   봇 보안  #$n  $title  — 닫지 않는다(기본 가지로 오는 것이 정상)"; continue ;; esac
      [ "$base" != "part/infra" ] && why="흐름 밖(base=$base) — target-branch 는 part/infra 다"
      g=$(bot_group "$head")
      [ -z "$why" ] && [ "${NEWEST[$g]}" != "$n" ] && why="같은 묶음의 새 PR #${NEWEST[$g]} 에 밀렸다"
      if [ -z "$why" ]; then echo "   봇 대기  #$n  $title  — 의존성 배치로 받는다"; continue; fi
      if [ -n "${FIRE_LANE_INBOX:-}" ] && mkdir -p "$ARCH" 2>/dev/null; then
        gh pr diff "$n" -R "$REPO" > "$ARCH/deps-$n.patch" 2>/dev/null || true
      fi
      gh pr close "$n" -R "$REPO" --delete-branch \
        --comment "청소 — $why (DECISIONS §218-4). diff 는 INBOX/_applied/deps-$n.patch 에 보관했다." \
        && { echo "   ✓ 봇 #$n 닫음 — $why"; VAC+=("$n"); } || echo "   ! #$n 닫기 실패 — 계속한다"
    done
    mapfile -t CLOSE < <(printf '%s\n' "${CLOSE[@]}" | grep -vxF -f <(printf '%s\n' "${BOTPR[@]}") || true)
  fi
  if [ ${#CLOSE[@]} -eq 0 ] || [ -z "${CLOSE[0]:-}" ]; then echo "   열린 PR 없음(사람 것)"
  elif [ "$AUTO" = 1 ]; then
    echo "   ★ --auto 는 PR 을 닫지 않는다. 닫으려면: bash tools/branch_tidy.sh"; WARN=1
  elif ask "위 ${#CLOSE[@]} 개를 닫고 원격 가지도 지운다. 진행?"; then
    for n in "${CLOSE[@]}"; do
      gh pr close "$n" -R "$REPO" --delete-branch \
        --comment "정리 — 흐름(feat → part → dev → main) 밖의 PR 이다. 필요하면 feat 배치로 다시 낸다 (DECISIONS §212-3)." \
        && echo "   ✓ #$n" || echo "   ! #$n 닫기 실패 — 계속한다"
    done
  fi
fi

# ── 2. 원격 가지 ────────────────────────────────────────────────
say "2. 원격 가지 (main · dev · part/* 밖)"
git fetch -q --prune origin
mapfile -t RB < <(git for-each-ref --format='%(refname:strip=3)' refs/remotes/origin | grep -v '^HEAD$' || true)
DEL=()
for b in "${RB[@]:-}"; do [ -z "$b" ] && continue; keep "$b" || DEL+=("$b"); done
if [ ${#DEL[@]} -eq 0 ]; then echo "   없음"
else
  printf '   %s\n' "${DEL[@]}"
  if [ "$AUTO" = 1 ]; then echo "   ★ --auto 는 원격 가지를 지우지 않는다"; WARN=1
  elif ask "위 ${#DEL[@]} 개를 원격에서 지운다. 진행?"; then
    for b in "${DEL[@]}"; do git push -q origin --delete "$b" && echo "   ✓ $b" || echo "   ! $b 실패"; done
  fi
fi

# ── 3. 로컬 가지 ────────────────────────────────────────────────
say "3. 로컬 가지"
mapfile -t LB < <(git for-each-ref --format='%(refname:short)' refs/heads)
GONE=(); LIVE=()
for b in "${LB[@]:-}"; do
  [ -z "$b" ] && continue; keep "$b" && continue
  ahead=$(git rev-list --count "origin/main..$b" 2>/dev/null || echo "?")
  if merged_by_content "$b"; then
    printf '   %-50s 커밋 %-4s 내용 main 에 있음\n' "$b" "$ahead"; GONE+=("$b")
  else
    printf '   %-50s 커밋 %-4s main 에 없는 변경 있음\n' "$b" "$ahead"; LIVE+=("$b")
  fi
done
TARGET=("${GONE[@]:-}")
if [ "$AUTO" = 0 ] && [ ${#LIVE[@]} -gt 0 ]; then
  echo "   ★ 「main 에 없는 변경 있음」 은 스쿼시 전 커밋이 남은 경우가 대부분이다."
  echo "     머지 안 된 작업이 있으면 N 하고 --keep 으로 다시 돌린다."
  ask "그것까지 ${#LIVE[@]} 개를 함께 지운다(-D). 진행?" && TARGET+=("${LIVE[@]}")
elif [ ${#LIVE[@]} -gt 0 ]; then
  echo "   ★ --auto 는 main 에 없는 변경이 있는 가지를 남긴다: ${LIVE[*]}"; WARN=1
fi
CUR=$(git symbolic-ref --short -q HEAD || echo "")
N=0
for b in "${TARGET[@]:-}"; do
  [ -z "$b" ] && continue
  if [ "$b" = "$CUR" ]; then git switch -q part/infra 2>/dev/null || git switch -q -c part/infra --track origin/part/infra; CUR=part/infra; fi
  if [ "$AUTO" = 1 ] || ask "$b 삭제?"; then git branch -q -D "$b" && { echo "   ✓ $b"; N=$((N+1)); }; fi
done
[ ${#TARGET[@]} -eq 0 ] || [ -n "${TARGET[0]}" ] || echo "   지울 것 없음"

# ── 4. 지킨 가지를 원격에 맞춘다 (ff 만) ─────────────────────────
say "4. 지킨 가지 ff"
for b in main dev part/infra part/gis part/cv; do
  git show-ref -q --verify "refs/heads/$b" || continue
  git show-ref -q --verify "refs/remotes/origin/$b" || continue
  if [ "$(git rev-parse "$b")" = "$(git rev-parse "origin/$b")" ]; then echo "   = $b"; continue; fi
  if ! git merge-base --is-ancestor "$b" "origin/$b"; then
    echo "   ! $b 가 원격과 갈라졌다 — 고치지 않는다. 확인: git log origin/$b..$b"
    echo "       거기서 한 작업이 없으면: git branch -f $b origin/$b"
    WARN=1; continue
  fi
  if [ "$b" = "$(git symbolic-ref --short -q HEAD || true)" ]; then
    git merge -q --ff-only "origin/$b" && echo "   ✓ $b"
  else
    git branch -q -f "$b" "origin/$b" && echo "   ✓ $b"
  fi
done

say "끝"
[ "$HAVE_GH" = 1 ] && echo "   열린 PR  $(gh pr list -R "$REPO" --state open --json number --jq length)"
echo "   원격     $(git for-each-ref --format='%(refname:strip=3)' refs/remotes/origin | grep -v '^HEAD$' | tr '\n' ' ')"
echo "   로컬     $(git for-each-ref --format='%(refname:short)' refs/heads | tr '\n' ' ')"
[ "$WARN" = 0 ] || exit 3
