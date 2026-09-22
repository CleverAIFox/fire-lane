#!/usr/bin/env bash
# tools/fl.sh — fire-lane 배치를 **명령 하나로.** 적용 → 전수 verify → PR → 머지 → 방송 → 정리
#
#   bash "$FIRE_LANE_INBOX/fl.sh" <브랜치> --all     ← 평소. INBOX 의 부트스트랩이 이 파일을 부른다
#   bash tools/fl.sh <브랜치>              적용 + 전수 verify 까지 (멈춘다)
#   bash tools/fl.sh <브랜치> --all        위 + PR + CI 대기 + 스쿼시 + dev PR + 릴리즈 + 가지 정리
#   bash tools/fl.sh <브랜치> --undo       가지를 지우고 원상복구
#   bash tools/fl.sh <브랜치> --resume     끊긴 자리부터 잇는다 (PR · CI · 스쿼시 · 방송 · 정리)
#
# ★ 2026-09-22 (DECISIONS §214-1). **정본이 저장소로 들어왔다.** 종전에는 이 파일이
#   INBOX(다운로드 폴더)에만 살았다 — 버전 관리 · 시험 · 리뷰 밖이었고, INBOX 를
#   비우는 순간 사라졌다(그날 실제로 사라졌다). 이제 INBOX 에는 `tools/inbox_fl.sh`
#   (부트스트랩) 사본만 두고, 그것이 **패치 안의** 이 파일(없으면 저장소 판)을 꺼내 돈다.
#   그래서 도구를 고치는 배치도 자기 새 판으로 돈다.
#
# ★ 실행 중에 가지를 바꾼다(적용 · 스쿼시 · 방송). bash 는 스크립트를 줄 단위로 읽으므로
#   **도는 파일이 체크아웃 안에 있으면** 가지가 바뀌는 순간 다른 판을 읽는다. 그래서
#   맨 앞에서 자기를 /tmp 로 복사해 그 사본으로 다시 실행한다.
#
# ★ **왜 합쳤나.** 종전에는 배치마다 네 번 쳤다 —
#     fl-apply <br>  ·  fl-apply <br> --pr  ·  fl-merge <br> --go  ·  (태그 입력)
#   2026-09-20 에 그 사슬이 **두 번** 끊겼다. ① `fl-merge.sh` 가 INBOX 에 없어서
#   #129 가 안 머지됐고, 그걸 모른 채 다음 패치를 적용해 `does not apply` 로 터졌다.
#   ② 그 뒤 zip 을 치우다가 새 패치까지 지워 「패치를 못 찾았다」가 났다.
#   **끊긴 자리가 둘 다 「사람이 순서를 기억해야 하는 자리」였다.** 순서를 글로
#   적는 대신 스크립트가 든다.
#
# ★ **이 스크립트는 일을 새로 하지 않는다.** 저장소의 재현적 도구를 순서대로 부를 뿐이다 —
#     tools/verify.sh        전수 검증
#     tools/pr_body_check.py 본문 검사
#     tools/merge_batch.sh   방송 (part/infra → dev → main · 태그 · 동기화)
#     tools/branch_tidy.sh   정리 (--auto — 머지된 로컬 가지 · 열린 PR 보고)
#   붙일 값어치가 있는 기능은 여기가 아니라 그쪽으로 간다. 여기 있는 것은
#   **순서와 전제 확인**뿐이고, 그것이 이 파일이 존재하는 유일한 이유다.
set -uo pipefail
VERSION=2026-09-22.5

# ── 자기 복사 → 재실행 ────────────────────────────────────────
if [ -z "${FL_RELOCATED:-}" ]; then
    _self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
    # 저장소 안에서 부르면 그 저장소, 아니면 FIRE_LANE_REPO, 아니면 기본 경로
    _top=$(git -C "$(dirname "$_self")" rev-parse --show-toplevel 2>/dev/null || true)
    [ -n "$_top" ] && [ -f "$_top/tools/verify.sh" ] && export FIRE_LANE_REPO="${FIRE_LANE_REPO:-$_top}"
    # 안내문에 찍을 명령. /tmp 사본 경로를 보여 주면 사람이 그것을 다시 친다
    export FL_CMD="${FL_CMD:-bash $_self}"
    _run=$(mktemp /tmp/fl-run.XXXXXX.sh)
    cp "$_self" "$_run"
    FL_RELOCATED=1 exec bash "$_run" "$@"
fi

REPO_DIR="${FIRE_LANE_REPO:-$HOME/projects/fire-lane}"     # ★ ~/fire-lane 아니다
GH_REPO=CleverAIFox/fire-lane
BASE=part/infra
# ★ 2026-09-22 (§214-1). 실행마다 새 자리다. 종전의 고정 경로 `/tmp/fl-patches` 는
#   verify 안의 pytest(`fl.sh --pick` 시험)가 같은 자리를 비워 **PR_BODY.md 가 7분 뒤
#   사라졌다**(6단계 FileNotFoundError). 도구와 그 시험이 한 자리를 나눠 쓰면 안 된다.
WORK=$(mktemp -d /tmp/fl-patches.XXXXXX)
trap 'rm -rf "$WORK"; case "$0" in /tmp/fl-run.*) rm -f "$0";; esac' EXIT

R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; C=$'\033[36m'; D=$'\033[90m'; Z=$'\033[0m'
step() { printf '\n%s══ %s%s\n' "$C" "$1" "$Z"; }
sub()  { printf '%s── %s%s\n' "$C" "$1" "$Z"; }
ok()   { printf '%s   OK%s  %s\n' "$G" "$Z" "${1:-}"; }
warn() { printf '%s   ! %s%s\n' "$Y" "${1:-}" "$Z"; }
die()  { printf '\n%s✗ %s%s\n' "$R" "$1" "$Z"; shift; for l in "$@"; do printf '   %s\n' "$l"; done; echo; exit 1; }
ask()  {
    local a
    if [ -t 0 ]; then
        while IFS= read -r -s -t 0.05 -n 4096 _ </dev/tty 2>/dev/null; do :; done
        IFS= read -r -p "$1 [y/N] " a </dev/tty || a=""
    else IFS= read -r a || a=""; fi
    a=$(printf '%s' "$a" | LC_ALL=C tr -cd 'A-Za-z')
    [ "$a" = "y" ] || [ "$a" = "Y" ]
}

printf '%sfl %s%s\n' "$D" "$VERSION" "$Z"

BR="${1:-}"
MODE="${2:-}"
case "$BR" in
    ""|-*) die "브랜치 이름이 없다." "  $FL_CMD feat/burndown --all" ;;
    feat/*) : ;;
    *) die "브랜치는 반드시 \`feat/**\` 다 — $BR" \
        "contract.yml 트리거가 main · dev · part/** · feat/** 뿐이다." \
        "그 밖에서 작업하면 CI 가 안 돌고, 2026-09-18 에 그래서 네 번 빨개졌다." ;;
esac

# ══ 0. 저장소 · INBOX ═════════════════════════════════════════
step "0. 저장소"
[ -d "$REPO_DIR/.git" ] || die "저장소가 없다 — $REPO_DIR"
cd "$REPO_DIR" || exit 1
_IN_ENV="${FIRE_LANE_INBOX:-}"          # 명시한 환경변수가 .env 를 이긴다
if [ -f .env ]; then set -a; . ./.env; set +a; fi
IN="${_IN_ENV:-${FIRE_LANE_INBOX:-}}"
[ -n "$IN" ] || die ".env 에 FIRE_LANE_INBOX 가 없다"

# ── 패치 고르기 ───────────────────────────────────────────────
# ★ 2026-09-22 (DECISIONS §214-1). INBOX 는 **다운로드 폴더라 공용이다.** 종전에는
#   `$IN/*.patch` 를 전부 집어서 다른 저장소 세션의 패치(hathor `D0216.patch` ·
#   thoth `thoth-105-….patch`)까지 적용 후보에 올렸고 3단계에서 멈췄다.
#   규칙 —
#     · 최신 `fire-lane-*.zip` 이 있으면 **그 안의 패치만** 쓴다. INBOX 에 풀린
#       같은 패치는 내용 지문으로 한 번만 센다
#     · zip 이 없으면 `git format-patch` 이름(`0001-….patch`)만 쓴다
#     · 그 밖의 `.patch` 는 **남의 것**이다 — 이름만 보여 주고 건드리지 않는다
pick_patches() {                        # pick_patches <INBOX> <WORK> → WORK 에 채운다
    local in=$1 work=$2 zip f h seen=" "
    rm -rf "$work"; mkdir -p "$work"
    # shellcheck disable=SC2012  # 최신 하나만 고른다
    zip=$(ls -t "$in"/fire-lane-*.zip 2>/dev/null | head -1)
    if [ -n "$zip" ]; then
        unzip -oq "$zip" -d "$work/z" || die "unzip 실패 — $zip"
        for f in "$work"/z/*.patch; do [ -e "$f" ] || continue
            h=$(sha256sum "$f" | cut -c1-16); seen="$seen$h "; cp -f "$f" "$work/"; done
        for f in "$work"/z/PR_*; do [ -e "$f" ] && cp -f "$f" "$work/"; done
    fi
    for f in "$in"/*.patch; do
        [ -e "$f" ] || continue
        h=$(sha256sum "$f" | cut -c1-16)
        case "$seen" in *" $h "*) continue ;; esac
        if [ -z "$zip" ] && [[ "$(basename "$f")" =~ ^[0-9]{4}-.+\.patch$ ]]; then
            cp -f "$f" "$work/"; seen="$seen$h "
        else
            printf '     %s(무시 — 이 배치 것이 아니다: %s)%s\n' "$D" "$(basename "$f")" "$Z"
        fi
    done
    ZIP="$zip"
}
# 소비한 포장물을 INBOX 에서 `_applied/` 로. ★ 남의 패치는 옮기지 않는다 — 우리가 쓴 것과
# **같은 이름**만 옮긴다. 지우지 않고 옮긴다 — PR 본문 · 패치는 나중에 볼 일이 있다.
archive_inbox() {
    local done_ p f
    done_="$IN/_applied/$(date +%Y%m%d-%H%M)-${BR//\//_}"
    mkdir -p "$done_"
    [ -n "${ZIP:-}" ] && mv -f "$ZIP" "$done_/" 2>/dev/null
    for p in "${PATCHES[@]}"; do [ -e "$IN/$(basename "$p")" ] && mv -f "$IN/$(basename "$p")" "$done_/"; done
    for f in "$IN"/PR_BODY*.md "$IN"/PR_TITLE*; do [ -e "$f" ] && mv -f "$f" "$done_/"; done
    ok "소비한 포장물 → ${done_#"$IN"/}"
}
if [ "$MODE" = "--pick" ]; then          # 시험 · 점검용 — 무엇을 집는지만 보고 끝낸다
    pick_patches "$IN" "$WORK"
    # shellcheck disable=SC2012
    ls -1 "$WORK"/*.patch 2>/dev/null | xargs -r -n1 basename
    exit 0
fi

command -v gh >/dev/null || die "gh 가 없다"
ok "$(pwd) · INBOX=$IN"

# ── --undo ────────────────────────────────────────────────────
if [ "$MODE" = "--undo" ]; then
    step "원상복구"
    git am --abort 2>/dev/null
    git switch -q "$BASE" 2>/dev/null || git switch -q dev 2>/dev/null || git switch -q main
    CUR=$(git rev-parse --abbrev-ref HEAD)
    [ "$CUR" != "$BR" ] || die "$BR 위에 서 있는데 다른 가지로 못 옮겼다." \
        "  git status 로 작업 트리를 먼저 정리해라."
    if git rev-parse -q --verify "$BR" >/dev/null; then
        git branch -D "$BR" && ok "$BR 삭제"
    else
        ok "$BR 는 이미 없다"
    fi
    exit 0
fi

# ══ 1. 전제 ═══════════════════════════════════════════════════
step "1. 전제"
[ -z "$(git status --porcelain --untracked-files=no)" ] \
  || die "추적 파일에 변경이 있다." "$(git status --short | head -8)"
gh auth status -h github.com >/dev/null 2>&1 || die "gh 인증이 없다 — gh auth login"
# ★ workflow 스코프를 **맨 앞에서** 본다. 방송 중간(흡수·동기화의 git push)에서
#   막히면 태그까지 붙인 뒤에 죽는다 — 사슬에서 제일 비싼 자리다.
if gh auth status -h github.com 2>&1 | grep -q "Token scopes:.*workflow"; then
    ok "workflow 스코프"
else
    die "gh 토큰에 workflow 스코프가 없다." \
        "  gh auth refresh -h github.com -s workflow" "  그 뒤 이 명령을 다시 실행."
fi
git fetch -q --prune origin
ok "origin/$BASE = $(git rev-parse --short "origin/$BASE")"

# ★ **다른 배치가 열려 있으면 여기서 멈춘다.** 2026-09-20 에 #129 가 안 머지된 채
#   다음 패치를 적용해 `does not apply` 로 터졌다. 순서를 사람이 기억하는 대신 여기서 본다.
OPEN=$(gh pr list -R "$GH_REPO" --base "$BASE" --state open --json number,headRefName \
       --jq '.[] | "#\(.number) \(.headRefName)"' 2>/dev/null)
if [ -n "$OPEN" ] && ! printf '%s' "$OPEN" | grep -q " ${BR#refs/heads/}$"; then
    die "$BASE 로 가는 **다른** PR 이 열려 있다 — 그것부터 끝내라:" "$OPEN" \
        "  그 PR 이 머지되기 전에 다음 패치를 얹으면 base 가 달라 git am 이 터진다."
fi
ok "$BASE 로 열린 다른 PR 0"

# ── --resume ──────────────────────────────────────────────────
# ★ 2026-09-22 실제 사고 (§215-3). 8단계(dev PR 개설) 중에 Ctrl-C 가 눌렸다. 패치는 이미
#   part/infra 에 스쿼시됐고 포장물은 `_applied/` 로 치워져, `--all` 을 다시 치면 2단계에서
#   「패치를 못 찾았다」 로 멈춘다. 남은 명령을 손으로 쳐야 했다.
#   어디까지 됐는지는 **GitHub 이 안다** — feat PR 이 열려 있으면 CI 대기부터, 머지됐으면
#   dev PR 부터 잇는다. 로컬 기억(상태 파일)을 두지 않는다: 기계를 옮기거나 /tmp 가 비면
#   거짓말을 한다.
RESUME=""
if [ "$MODE" = "--resume" ]; then
    step "이어가기 — 어디까지 됐나"
    FEAT_OPEN=$(gh pr list -R "$GH_REPO" --head "${BR#refs/heads/}" --base "$BASE" --state open \
                --json number --jq '.[0].number // empty')
    FEAT_DONE=$(gh pr list -R "$GH_REPO" --head "${BR#refs/heads/}" --base "$BASE" --state merged \
                --json number,mergedAt --jq 'sort_by(.mergedAt) | last | .number // empty')
    if [ -n "$FEAT_OPEN" ]; then
        RESUME=ci; PR=$FEAT_OPEN
        ok "PR #$PR 이 열려 있다 — CI 대기부터"
        pick_patches "$IN" "$WORK"
        mapfile -t PATCHES < <(ls -1 "$WORK"/*.patch 2>/dev/null | sort)
    elif [ -n "$FEAT_DONE" ]; then
        RESUME=dev
        ok "PR #$FEAT_DONE 이 $BASE 에 머지됐다 — dev PR 부터"
        # ★ 스쿼시 직후 · 포장물을 치우기 전에 끊겼으면 INBOX 에 이 배치 패치가 남는다. 남기면
        #   다음 --all 이 또 집는다(2026-09-20 「does not apply」). zip 의 PR_TITLE 이 머지된 PR
        #   제목과 같을 때만 이 배치 것으로 보고 치운다(독립 검토 2026-09-22).
        pick_patches "$IN" "$WORK" >/dev/null
        mapfile -t PATCHES < <(ls -1 "$WORK"/*.patch 2>/dev/null | sort)
        MTITLE=$(gh pr view "$FEAT_DONE" -R "$GH_REPO" --json title --jq .title 2>/dev/null)
        if [ "${#PATCHES[@]}" -gt 0 ] && [ -f "$WORK/PR_TITLE" ] \
           && [ "$(head -1 "$WORK/PR_TITLE")" = "$MTITLE" ]; then
            archive_inbox
        fi
    else
        die "$BR 로 연 PR 이 없다 — 이을 것이 없다." \
            "  처음부터:  $FL_CMD $BR --all   (가지에 이미 얹힌 패치는 건너뛴다)"
    fi
    # 본문 · 제목은 치운 포장물에서 찾는다. 없으면 INBOX
    # shellcheck disable=SC2012
    LASTDONE=$(ls -1dt "$IN"/_applied/*-"${BR//\//_}" 2>/dev/null | head -1)
    # shellcheck disable=SC2012
    BODY=$(ls -t "$WORK"/PR_BODY.md "${LASTDONE:-/nonexistent}"/PR_BODY.md "$IN"/PR_BODY.md 2>/dev/null | head -1)
    TITLE=$(head -1 "$WORK/PR_TITLE" 2>/dev/null || head -1 "${LASTDONE:-/nonexistent}/PR_TITLE" 2>/dev/null \
            || gh pr view "${FEAT_OPEN:-$FEAT_DONE}" -R "$GH_REPO" --json title --jq .title)
    [ -n "$BODY" ] && ok "PR_BODY.md  $BODY"
    if [ "$RESUME" = dev ] && git merge-base --is-ancestor "origin/$BASE" origin/main; then
        ok "$BASE 가 이미 main 에 들어 있다 — 방송은 끝났다. 정리만 한다"
        RESUME=tidy
    fi
fi

# ══ 2. 패치 찾기 ══════════════════════════════════════════════
if [ -z "$RESUME" ]; then     # ── 2 ~ 6(PR 개설) 은 처음 돌 때만 ──
step "2. 패치"
pick_patches "$IN" "$WORK"
# shellcheck disable=SC2012  # 우리가 방금 만든 디렉터리다. 이름이 이상할 수 없다
mapfile -t PATCHES < <(ls -1 "$WORK"/*.patch 2>/dev/null | sort)
N=${#PATCHES[@]}
[ "$N" -ge 1 ] || die "패치를 못 찾았다." "찾아본 곳: $IN/fire-lane-*.zip · $IN/0001-*.patch"
for p in "${PATCHES[@]}"; do printf '     %s\n' "$(basename "$p")"; done

# shellcheck disable=SC2012  # 후보 둘뿐이고 이름이 고정이다
BODY=$(ls -t "$WORK"/PR_BODY.md "$IN"/PR_BODY.md 2>/dev/null | head -1)
if [ -n "$BODY" ]; then ok "PR_BODY.md  $BODY"; else warn "PR_BODY.md 가 없다 — --all 은 못 간다"; fi

# ══ 3. 붙는지 먼저 본다 ═══════════════════════════════════════
# ★ **이것이 오늘 없어서 터진 단계다.** `git am` 은 반쯤 적용한 뒤에 멈추고,
#   그 상태에서 사람이 --abort 를 잊으면 다음 실행이 또 이상해진다.
#   붙는지는 **건드리기 전에** 알 수 있다.
step "3. base 대조 (건드리기 전에)"
# ★ 2026-09-22. 같은 가지로 **다시** 돌면(6단계 이후에서 멈췄을 때) 패치가 이미 얹혀
#   있다. 그것을 base 에 또 대 보면 「안 붙는다」 로 멈추고, 4단계는 두 번 얹는다.
#   가지에 이미 있는 패치(patch-id 가 같은 것)는 건너뛴다.
HAVE=""
if git rev-parse -q --verify "$BR" >/dev/null; then
    HAVE=$(git log --format=%H "origin/$BASE..$BR" | while read -r c; do
               git show "$c" | git patch-id --stable | cut -d' ' -f1; done)
fi
applied() { local id; id=$(git patch-id --stable < "$1" | cut -d' ' -f1)
            [ -n "$id" ] && printf '%s\n' "$HAVE" | grep -qx "$id"; }
BAD=""; MISSING=0
for p in "${PATCHES[@]}"; do
    if applied "$p"; then printf '     %s — %s 에 이미 있다\n' "$(basename "$p")" "$BR"; continue; fi
    MISSING=$((MISSING + 1))
    git apply --check --3way "$p" 2>/dev/null || BAD="$BAD $(basename "$p")"
done
# ★ 2026-09-22 실제 사고. 6단계에서 멈춘 가지가 남은 채로 **고친 판** 패치를 받았다.
#   patch-id 가 달라 「이미 있다」 에 안 걸렸고, 4단계가 옛 커밋 **위에** 새 판을
#   얹으려다 파일마다 「already exists」 로 멈췄다. 3단계는 base 에 대 봤으니 통과했다 —
#   대 본 자리와 얹는 자리가 달랐다.
#   가지에 이 배치 것이 아닌 커밋이 있고 얹을 패치가 남았으면 **base 에서 새로 짓는다.**
REBUILD=0
if [ -n "$HAVE" ] && [ "$MISSING" -gt 0 ]; then
    if git rev-parse -q --verify "origin/$BR" >/dev/null; then
        die "$BR 가 원격에 이미 올라가 있고, 거기 없는 새 판 패치가 왔다." \
            "  새 판으로 갈아 끼우려면 원격 가지 · PR 을 먼저 정리해라:" \
            "    gh pr close --delete-branch $BR   (또는 git push origin --delete $BR)" \
            "  그 뒤  $FL_CMD $BR --undo  →  --all"
    fi
    REBUILD=1
    warn "$BR 에 옛 판 커밋이 있다 ($(git rev-parse --short "$BR")) — base 에서 새로 짓는다"
fi
if [ -n "$BAD" ]; then
    die "이 패치는 현재 $BASE ($(git rev-parse --short "origin/$BASE")) 에 안 붙는다:" \
        "  $BAD" "" \
        "  흔한 원인 — 앞 배치가 아직 안 머지됐거나, INBOX 에 옛 패치가 남아 있다." \
        "  INBOX 를 확인해라:  ls -la $IN/*.patch $IN/fire-lane-*.zip"
fi
ok "패치 $N 개 전부 $BASE 에 붙는다"

if ! ask "이 $N 개를 $BR 에 적용하고 전수 verify 를 돌린다 (7분). 진행?"; then echo 멈춤; exit 0; fi

# ══ 4. 적용 ═══════════════════════════════════════════════════
step "4. 적용"
if [ "$REBUILD" = 1 ]; then
    git switch -q -C "$BR" "origin/$BASE" || die "$BR 를 base 에서 새로 못 지었다"
    HAVE=""                              # 새 가지 — 이미 얹힌 것이 없다
    ok "$BR 를 origin/$BASE 에서 새로 지었다 (옛 끝은 git reflog 에 남는다)"
else git switch -q -c "$BR" "origin/$BASE" 2>/dev/null || {
    git switch -q "$BR" || die "$BR 로 못 옮겼다"
    warn "$BR 가 이미 있다 — 이어서 붙인다"
}; fi
for p in "${PATCHES[@]}"; do
    applied "$p" && continue
    git am -q "$p" || {
        git am --abort 2>/dev/null
        die "git am 이 멈췄다 — $(basename "$p")" \
            "  되돌리려면:  $FL_CMD $BR --undo"
    }
done
git log --oneline "origin/$BASE..HEAD" | sed 's/^/     /'
ok "$(git rev-list --count "origin/$BASE..HEAD") 커밋"

# ══ 5. 전수 verify ════════════════════════════════════════════
step "5. 전수 verify"
if ! bash tools/verify.sh; then
    die "전수 verify 가 빨갛다. **메시지를 끝까지 읽어라** — 고치는 법이 그 안에 있다." \
        "  되돌리려면:  $FL_CMD $BR --undo"
fi
ok "전수 초록"

if [ "$MODE" != "--all" ]; then
    step "여기까지"
    printf '  이어서:  %s %s --all\n\n' "$FL_CMD" "$BR"
    exit 0
fi

# ══ 6. PR ═════════════════════════════════════════════════════
step "6. PR"
[ -n "$BODY" ] || die "PR_BODY.md 가 없다 — --all 은 본문 없이 안 간다"
uv run python tools/pr_body_check.py --body-file "$BODY" || die "PR 본문이 템플릿 검사를 못 넘는다: $BODY"
TITLE=$(head -1 "$WORK/PR_TITLE" 2>/dev/null || head -1 "$IN/PR_TITLE" 2>/dev/null \
        || git log -1 --format=%s)
git push -q -u origin "$BR" || die "push 실패"
PR=$(gh pr list -R "$GH_REPO" --head "${BR#refs/heads/}" --state open --json number --jq '.[0].number // empty')
if [ -z "$PR" ]; then
    gh pr create -R "$GH_REPO" --base "$BASE" --head "${BR#refs/heads/}" \
        --title "$TITLE" --body-file "$BODY" || die "PR 개설 실패"
    PR=$(gh pr list -R "$GH_REPO" --head "${BR#refs/heads/}" --state open --json number --jq '.[0].number // empty')
fi
[ -n "$PR" ] || die "PR 을 열었는데 목록에 없다 — 화면에서 확인해라"
ok "PR #$PR"
fi                            # ── 처음 돌 때만 끝 ──

if [ -z "$RESUME" ] || [ "$RESUME" = ci ]; then     # ── CI 대기 · 스쿼시 ──

sub "CI 대기"
gh pr checks "$PR" -R "$GH_REPO" --watch --fail-fast \
  || die "PR #$PR CI 가 빨갛다." "  gh pr checks $PR -R $GH_REPO"
ok "CI 초록"

# ══ 7. 스쿼시 ═════════════════════════════════════════════════
step "7. $BR → $BASE 스쿼시"
if ! ask "PR #$PR 을 $BASE 에 스쿼시 머지하고 브랜치를 지운다. 진행?"; then
    printf '  멈춤. 나중에:  %s %s --resume\n\n' "$FL_CMD" "$BR"; exit 0
fi
gh pr merge "$PR" -R "$GH_REPO" --squash --delete-branch || die "스쿼시 머지 실패"
git fetch -q --prune origin
if ! { git switch -q "$BASE" && git merge -q --ff-only "origin/$BASE"; }; then
    die "로컬 $BASE 가 원격과 갈렸다." "  git switch $BASE && git reset --hard origin/$BASE"
fi
git branch -D "$BR" >/dev/null 2>&1
ok "$BASE $(git rev-parse --short "origin/$BASE")"

# ★ 2026-09-22 (§214-1). 소비한 포장물을 치운다. INBOX 에 옛 패치가 남으면 다음
#   실행이 그것을 또 집는다(2026-09-20 「does not apply」). 지우지 않고 옮긴다 —
#   PR 본문 · 패치는 나중에 볼 일이 있다.
archive_inbox
fi                            # ── CI 대기 · 스쿼시 끝 ──

if [ "$RESUME" != tidy ]; then                      # ── dev PR · 방송 ──

# ══ 8. part/infra → dev PR ════════════════════════════════════
step "8. $BASE → dev PR"
if git merge-base --is-ancestor "origin/$BASE" origin/dev; then
    ok "$BASE 가 이미 dev 에 들어 있다 — 건너뛴다"
else
    DEVPR=$(gh pr list -R "$GH_REPO" --base dev --head "$BASE" --state open --json number --jq '.[0].number // empty')
    if [ -n "$DEVPR" ]; then
        warn "이미 열린 PR #$DEVPR 을 쓴다"
    else
        # shellcheck disable=SC2012  # 후보 둘뿐이고 이름이 고정이다
        DBODY=$(ls -t "$WORK"/PR_BODY_DEV.md "$IN"/PR_BODY_DEV.md 2>/dev/null | head -1)
        # ★ 없으면 **지어내지 않는다.** feat PR 본문을 그대로 쓴다 — 같은 배치이므로
        #   내용이 맞고, 지어낸 요약보다 낫다. 배치마다 다른 본문을 원하면 넣어라.
        [ -n "$DBODY" ] || { DBODY="$BODY"; warn "PR_BODY_DEV.md 가 없다 — feat 본문을 그대로 쓴다"; }
        uv run python tools/pr_body_check.py --body-file "$DBODY" || die "dev 본문이 검사를 못 넘는다: $DBODY"
        DTITLE=$(head -1 "$WORK/PR_TITLE_DEV" 2>/dev/null || head -1 "$IN/PR_TITLE_DEV" 2>/dev/null \
                 || echo "파트 동기화 — $TITLE")
        gh pr create -R "$GH_REPO" --base dev --head "$BASE" --title "$DTITLE" --body-file "$DBODY" \
          || die "dev PR 개설 실패"
        DEVPR=$(gh pr list -R "$GH_REPO" --base dev --head "$BASE" --state open --json number --jq '.[0].number // empty')
    fi
    ok "PR #${DEVPR:-?}"
fi

# ══ 9. 방송 ═══════════════════════════════════════════════════
step "9. 방송 — tools/merge_batch.sh --release"
LAST=$(git tag -l 'v0.*' | sort -V | tail -1)
printf '  ★ 지금 붙은 마지막 태그: %s%s%s  → 다음은 그 +1 이다.\n' "$G" "$LAST" "$Z"
printf '  ★ 한/영 입력기가 한글이면 앞에 깨진 바이트가 붙는다(G-12) — 영문으로 치고 확인해라.\n'
# ★ 2026-09-22 (§214-1). `exec` 가 아니다 — 방송 뒤에 정리가 남아 있다.
bash tools/merge_batch.sh --release || die "방송이 멈췄다 — 위 메시지를 읽어라." \
    "  다시:  $FL_CMD $BR --resume"
fi                            # ── dev PR · 방송 끝 ──

# ══ 10. 정리 ══════════════════════════════════════════════════
# ★ 2026-09-22 (§214-1). 배치마다 로컬 feat 가지가 쌓였다(원격은 스쿼시가 지운다).
#   `--auto` 는 **내용이 main 에 들어간 것만** 지우고, PR 은 닫지 않고 보고만 한다.
step "10. 정리 — tools/branch_tidy.sh --auto"
git fetch -q --prune origin
git switch -q "$BASE" 2>/dev/null && git merge -q --ff-only "origin/$BASE" 2>/dev/null
bash tools/branch_tidy.sh --auto || warn "정리가 경고를 냈다 — 위를 읽어라"
