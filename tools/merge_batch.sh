#!/usr/bin/env bash
# tools/merge_batch.sh — 배치 PR 머지 → 파트 동기화 → (선택) 릴리즈
#
#   bash tools/merge_batch.sh              A  part/infra → dev 머지 · part/* 동기화
#   bash tools/merge_batch.sh --release    A + B  dev → main 릴리즈 · 흡수 · 동기화
#
# ★ 2026-09-16 저장소에 들였다. 매 배치 다시 쓰는 도구라 일회성이 아니다
#   (README — 내년에도 돌리나). INBOX 에 받아 쓰던 판은 브라우저가
#   `merge_batch (1).sh` 로 저장해 **옛 판이 조용히 돌았다**(DECISIONS §164-3).
#
# 정본은 MASTER §12-8b(릴리즈) · §12-8c(통합) · §12-1(룰셋)이다.
#   trunk(dev)     merge commit 만     승인 0
#   release(main)  merge commit 만     승인 1 → 1인이라 --admin (§12-1c bypass)
#
# ★ 스쿼시로 머지하지 않는다. EXPECT 가 dev · main 을 merge 만 허용한다.
#   2026-09-15 PR #23 을 스쿼시로 넣어 main 이 dev 조상에서 빠졌고, 그래서
#   "dev → main 전에 git merge origin/main" 이 필요해졌다. B 단계가 그 분기를
#   한 번 풀고, 이후로는 merge commit 이라 다시 안 생긴다.
# ★ 흡수(main → dev)와 dev → part 동기화는 **내용이 같은 fast-forward** 라
#   PR 대신 직푸시한다(1인 bypass). MASTER §12-8b 는 "3·4단계는 PR" 이라
#   적는데 그것은 bypass 회수 기간(09-03~09-12)의 서술이다 — 다음 문서
#   배치에서 고친다 → 2026-09-16 MASTER §12-8b 에 반영했다.
#   ff 가 안 되면 dev 를 합쳐 보고, 내용이 dev 와 같을 때만 merge commit 으로 올린다.
# ★ PR 번호는 짐작하지 않는다. gh pr list 로 찾고 화면에 보여준 뒤 묻는다.
set -euo pipefail

VERSION=2026-09-17.1   # ★ 어느 판이 돌았는지 첫 줄에서 보인다

say() { printf '\n\033[36m── %s\033[0m\n' "$*"; }
die() { printf '\n\033[31m✗ %b\033[0m\n' "$*"; exit 1; }
ok()  { printf '\033[32m✓ %s\033[0m\n' "$*"; }
warn(){ printf '\033[33m! %b\033[0m\n' "$*"; }
# >>> tty — 대화형 입력. tests/test_k2.py 가 이 구간을 떼어 가상 터미널로 흔든다
# ★ 2026-09-17 (DECISIONS §180-6 · G-17). `gh ... --watch` 가 터미널에 배경색을 묻는다(OSC 11). 응답 바이트
#   (`^[]11;rgb:…^[\^[[30;1R`)가 입력 버퍼에 남아, 다음 `read` 가 사람의 y 대신 그것을 읽고 "멈춤" 했다(run_chain L2d).
#   입력이 터미널이면 **읽기 직전에 버퍼를 비우고** 터미널에서 읽는다. 파이프로 답을 넘기면(run_final) 그대로 stdin 을 읽는다.
#   답은 글자만 남겨 판정한다 — 비운 뒤에 도착한 응답 조각이 섞여도 y 한 글자로 본다.
flush_tty() {
    [ -t 0 ] || return 0
    local junk
    while IFS= read -r -s -t 0.05 -n 4096 junk </dev/tty 2>/dev/null; do :; done
    return 0
}
read_answer() {   # read_answer <프롬프트> — 답을 표준출력으로
    local a
    if [ -t 0 ]; then flush_tty; IFS= read -r -p "$1" a </dev/tty || a=""
    else IFS= read -r a || a=""; fi
    printf '%s' "$a"
}
ask() {
    local yn
    yn=$(read_answer "$1 [y/N] " | LC_ALL=C tr -cd 'A-Za-z')
    [ "$yn" = "y" ] || [ "$yn" = "Y" ]
}
# <<< tty

printf '\033[2mmerge_batch %s\033[0m\n' "$VERSION"

REPO=CleverAIFox/fire-lane
PARTS="part/infra part/gis part/cv"
RELEASE=0; [ "${1:-}" = "--release" ] && RELEASE=1

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "저장소 안에서 실행하라"
cd "$ROOT"
[ -f tools/verify.sh ] || die "fire-lane 루트가 아니다: $ROOT"
command -v gh >/dev/null || die "gh 가 없다"
gh auth status -h github.com >/dev/null 2>&1 || die "gh 인증이 없다 — gh auth login"
[ -z "$(git status --porcelain --untracked-files=no)" ] || die "추적 파일에 변경이 있다"

# ── 오류를 알아본다 ────────────────────────────────────────────
# ★ 2026-09-24 (DECISIONS §225-1). 도구가 **모르는 것을 안다고 우겼다.**
#   `gh pr checks` 는 「검사가 빨갛다」와 「API 를 못 읽었다」에 똑같이 0 아닌
#   값을 낸다. 2026-09-23 에 GitHub 이 503 을 뱉었고, 이 스크립트는 그것을
#   빨간불로 읽어 **PR 을 닫고 가지를 지웠다.** 못 읽은 것을 근거로 파괴적
#   동작을 했다 — `ruleset_check.py` 가 자기 머리말에 「못 읽은 것을 '없다' 로
#   적지 않는다」고 써 둔 바로 그 원칙을 옆 도구가 어겼다.
#
# ★ 이름이 아니라 **글자**로 가른다. 종료코드는 둘을 안 가르므로 출력을 본다 —
#   여기서는 그것 말고 가를 방법이 없고, 못 가르면 또 지운다.
unreadable() {    # unreadable <출력>  — 네트워크·서버 문제인가
    printf '%s' "$1" | grep -qiE 'HTTP (4[0-9][0-9]|5[0-9][0-9])|Service Unavailable|Bad Gateway|timeout|timed out|connection reset|EOF|could not resolve|dial tcp|rate limit'
}

# ★ 아는 실패에는 처방을 찍는다. 「메시지를 끝까지 읽어라」만 찍으면 그 메시지가
#   `Permission denied (publickey)` 일 때 사람이 40분을 버린다(2026-09-23).
diagnose() {      # diagnose <출력>
    local o=$1
    case "$o" in
      *"Permission denied (publickey)"*)
        printf '  ★ ssh 키가 에이전트에 없다 — wsl --shutdown 뒤에 흔하다.\n'
        printf '      eval "$(ssh-agent -s)" && ssh-add ~/.ssh/id_ed25519\n'
        printf '      ssh -T git@github.com     # Hi <너> 가 나와야 한다\n' ;;
      *"Head branch is out of date"*)
        printf '  ★ 머리가 밀렸다 — 방금 누가(또는 이 도구가) 그 가지에 밀었다.\n'
        printf '      git fetch origin && 다시 실행하면 새 머리로 시도한다.\n' ;;
      *"workflow scope"*|*"refusing to allow"*)
        printf '  ★ 토큰에 workflow 스코프가 없다.\n'
        printf '      gh auth refresh -h github.com -s workflow\n' ;;
    esac
}

wait_checks() {   # wait_checks <PR번호> [since ISO8601]  → 0 초록 · 1 빨강 · 2 못 읽음
    local n=$1 since=${2:-} sha cnt out rc try
    say "CI 대기 — PR #$n"
    # ★ 2026-09-17 (DECISIONS §182-8 · G-23). "체크가 하나라도 있으면" 기다림을 끝냈다. 본문을 고친 직후(edited)에는
    #   **옛 실행**의 결과가 이미 있어서, 새 실행이 등록되기 전에 옛 실패 · 옛 초록으로 판정했다(#59 가 본문 검사
    #   실패인 채 스쿼시됐다). PR 머리 커밋의 check-run 을 보고, since 가 주어지면 그 뒤에 **시작된** 실행이
    #   생길 때까지 기다린다.
    # ★ 2026-09-24. 아래 둘은 **조회 실패**다 — `die`(코드 1)로 나가면 호출부가
    #   그것을 「CI 빨강」으로 읽고 PR 을 지운다. 2 로 나간다.
    sha=$(gh pr view "$n" -R "$REPO" --json headRefOid --jq '.headRefOid // empty')
    [ -n "$sha" ] || { warn "PR #$n 의 머리 커밋을 못 읽었다 — 검사 상태 미상"; return 2; }
    for _ in $(seq 1 30); do
        cnt=$(gh api "repos/$REPO/commits/$sha/check-runs" \
              --jq "[.check_runs[] | select(\"$since\" == \"\" or .started_at >= \"$since\")] | length" 2>/dev/null || echo 0)
        [ "${cnt:-0}" -gt 0 ] && break
        sleep 10
    done
    [ "${cnt:-0}" -gt 0 ] || {
        warn "PR #$n 머리 ${sha:0:7} 에 ${since:+$since 이후 }시작된 검사가 5분 동안 없다 — 미상"
        return 2; }
    # ★ 세 번까지 다시 묻는다. 503 은 대개 한 번이고, 세 번 다 못 읽으면
    #   그것은 **못 읽은 것**이지 빨간불이 아니다 — 종료코드 2 로 가른다.
    # ★ `set -e` 아래서는 `x=$(cmd); rc=$?` 가 **rc 를 읽기 전에 죽는다** —
    #   대입의 종료코드가 곧 cmd 의 종료코드이기 때문이다. if 로 감싼다.
    for try in 1 2 3; do
        if out=$(gh pr checks "$n" -R "$REPO" --watch --fail-fast 2>&1); then rc=0; else rc=$?; fi
        printf '%s\n' "$out"
        [ "$rc" = 0 ] && { ok "PR #$n CI 초록 · 머리 ${sha:0:7}"; return 0; }
        if unreadable "$out"; then
            warn "검사 상태를 못 읽었다 ($try/3) — 20초 뒤 다시 묻는다"
            sleep 20; continue
        fi
        diagnose "$out"
        warn "PR #$n CI 가 **빨갛다**:  gh pr checks $n -R $REPO"
        return 1
    done
    diagnose "$out"
    warn "PR #$n 의 검사 상태를 세 번 물어도 못 읽었다 — **빨간불이 아니다.**
  모르는 것을 근거로 아무것도 지우지 않는다. 손으로 보고 판단해라:
    gh pr checks $n -R $REPO"
    return 2
}

# ★ 2026-09-24 (DECISIONS §225-1). 머지 직전의 판정. `wait_checks` 가 셋을 내므로
#   호출부가 셋을 다 다뤄야 한다 — 종전에는 `die` 하나에 기대서 「못 읽음」이 없었다.
#     0 초록 → 간다        1 빨강 → 멈춘다        2 미상 → **멈춘다.** 지우지도 밀지도 않는다
require_green() {  # require_green <PR번호>
    local n=$1 rc
    if wait_checks "$n"; then rc=0; else rc=$?; fi
    [ "$rc" = 0 ] && return 0
    [ "$rc" = 1 ] && die "PR #$n CI 가 빨갛다 — 머지하지 않는다.\n  gh pr checks $n -R $REPO"
    die "PR #$n 의 검사 상태를 못 읽었다 — **빨간불이 아니라 모르는 것이다.**\n\
  모르는 채로 머지하지 않는다. 손으로 보고 다시 돌려라:\n    gh pr checks $n -R $REPO"
}

sync_parts() {    # dev 를 파트로 fast-forward
    say "파트 동기화 — dev → part/* (ff 만)"
    git fetch -q origin
    for p in $PARTS; do
        if ! git rev-parse -q --verify "origin/$p" >/dev/null; then
            warn "$p 가 원격에 없다 — 건너뜀"; continue
        fi
        if [ "$(git rev-parse "origin/$p")" = "$(git rev-parse origin/dev)" ]; then
            ok "$p = dev"
        elif git merge-base --is-ancestor "origin/$p" origin/dev; then
            git push -q origin "origin/dev:refs/heads/$p" 2>&1 | grep -v "^remote:" || true
            ok "$p → dev 로 ff"
        else
            # ff 가 안 되면 dev 를 합쳐 본다. 결과 내용이 dev 와 같으면 파트에만 있는
            # 것은 머지 커밋뿐이다 — merge commit 으로 올린다. 다르면 파트 고유 내용이
            # 있는 것이라 손대지 않는다. ★ 강제 푸시로 맞추지 않는다 — 옛 조직 PR
            # 머지 기록(woongtopia #132~#159)이 그 브랜치에만 남아 있다.
            local wt; wt=$(mktemp -d)
            git worktree add -q --detach "$wt" "origin/$p"
            if git -C "$wt" merge -q --no-ff --no-edit -m "Merge branch 'dev' into $p" origin/dev >/dev/null 2>&1 \
               && git -C "$wt" diff --quiet HEAD origin/dev; then
                git -C "$wt" push -q origin "HEAD:refs/heads/$p" 2>&1 | grep -v "^remote:" || true
                ok "$p ← dev merge commit (파트 고유 내용 0 · 머지 커밋만 있었다)"
            else
                git -C "$wt" merge --abort >/dev/null 2>&1 || true
                warn "$p 에 dev 에 없는 **내용**이 있다 — 손대지 않는다\n  git diff --stat origin/dev origin/$p"
            fi
            git worktree remove --force "$wt"
        fi
    done
    git switch -q part/infra && git merge -q --ff-only origin/part/infra
}

# ══ A. part/infra → dev ═══════════════════════════════════════
say "A. part/infra → dev PR"
git fetch -q origin
# ★ 2026-09-17 (DECISIONS §180 · G-2). feat → part/infra PR 이 열려 있으면 squash 를 빠뜨린 것이다. 그대로 가면
#   part/infra 에 그 배치가 없는 채로 dev 에 올리고 "끝" 을 찍는다. 경고가 아니라 멈춘다.
# ★ 2026-09-23 (DECISIONS §221-2). 작성자를 본다. `fl.sh` 1단계에서 같은 결함을 고치면서
#   **여기 두 번째 인스턴스를 놓쳤고**, 같은 날 방송이 dependabot PR 넷으로 멈췄다.
#   봇 PR 은 「알림」으로 일부러 남긴다(§218-4) — 그것이 방송을 막으면 규칙 둘이 서로를 막는다.
#   사람 PR 만 멈춘다. 그것이 열려 있다는 것은 squash 를 빠뜨렸다는 뜻이고,
#   그대로 가면 part/infra 에 그 배치가 없는 채로 dev 에 올리고 "끝" 을 찍는다(§180 · G-2).
openfeat=""; openbot=""
while IFS=$'\t' read -r n head who; do
    [ -z "$n" ] && continue
    case "$who" in *[Dd]ependabot*|*[Bb]ot) openbot="$openbot#$n $head"$'\n' ;;
                   *) openfeat="$openfeat#$n $head ($who)"$'\n' ;; esac
done <<<"$(gh pr list -R "$REPO" --base part/infra --state open --json number,headRefName,author \
           --jq '.[] | "\(.number)\t\(.headRefName)\t\(.author.login)"')"
if [ -n "$openfeat" ]; then
    die "part/infra 로 가는 **사람** PR 이 아직 열려 있다 — squash 머지부터:\n$openfeat"
fi
[ -n "$openbot" ] && say "   봇 PR $(printf '%s' "$openbot" | grep -c .) 개 — 막지 않는다(§218-4 청소가 맡는다)"
# ══ A-0. 봉인 — **스쿼시 뒤 `part/infra` 에서 찍는다** ══════════
# ★ 2026-09-21 (PLAN §13 W11-1 · DECISIONS §207). 종전에는 사람이 feat 가지에서
#   `dms seal` 을 찍었다. 그 가지는 **스쿼시로 머지되고 지워진다.** 봉인이 적은
#   커밋 해시는 그 순간 어느 브랜치에도 없는 것이 되고, `git clone` 만 한 사람에겐
#   **존재하지 않는 커밋**이 된다. 2026-09-20 실측 — 봉인이 `2130b14` 를 가리켰고
#   그것은 `refs/pull/108/head` 에만 살아 있었다(`main` 조상 아님).
#
#   불변이 `봉인 == HEAD^` 인데 **그 `HEAD^` 가 스쿼시로 반드시 사라진다.**
#   다시 찍어도 다음 배치에 또 난다 — 구조가 그렇게 만든다. 그래서 찍는 자리를 옮긴다.
#   여기서 찍으면 **봉인이 가리키는 커밋**(part/infra 머리)은 `part/infra` →
#   (merge commit) → `dev` → `main` 을 타고 가므로 **영원히 main 의 조상**이다.
#   (봉인 파일을 싣는 커밋은 아래 §209 대로 PR 스쿼시를 탄다 — 그것은 사라져도 된다.)
#
# ★ `--quick`(pytest + 프로브)을 쓴다. 전수 verify 는 **같은 트리**에서 방금 돌았다
#   (fl.sh 5단계). 스쿼시는 트리를 안 바꾸고 커밋만 합치므로 다시 7분을 돌릴 이유가 없다.
#   `--log` 를 못 쓰는 이유는 가지를 옮기면서 파일 mtime 이 전부 바뀌어
#   `_log_is_fresh` 가 「그 로그는 옛 상태다」로 막기 때문이다.
#
# ★ 봉인이 안 바뀌면 커밋도 안 한다. 매 배치 빈 커밋이 쌓이면 그것이 곧 소음이다.
#
# ★ 2026-09-21 (DECISIONS §209). **봉인 커밋은 PR 로 들어간다. `part/infra` 에 직접 밀지 않는다.**
#   처음(§207)에는 `git push origin part/infra` 로 밀었다. 룰셋 bypass 로 들어갔다 ——
#       remote: Bypassed rule violations for refs/heads/part/infra:
#       remote: - Changes must be made through a pull request.
#       remote: - Required status check "contract-shared" is expected.
#   **검사를 한 번도 안 받은 커밋이 part/infra 에 앉았고**, 그 커밋이 secret-scan 에
#   걸렸다(`"src/firelane/segkey.py": "<sha256>"` 를 generic-api-key 로 읽었다).
#   거짓 경보였지만 요지는 그것이 아니다 — **PR 로 들어갔으면 part/infra 에 앉기 전에 걸렸다.**
#   관문을 우회한 자리에서 관문이 잡을 것이 났다.
#
# ★ 스쿼시해도 된다 — §207 이 피하려던 것과 **모양이 다르다.** 그때 사라진 것은
#   봉인이 가리키는 커밋 **자신**이었다(feat 가지 위에서 찍었으니까). 여기서 봉인이
#   가리키는 것은 **이미 part/infra 에 있는 머리 H** 이고, 봉인 PR 은 H 위에 한 칸을
#   더할 뿐이다. 스쿼시는 그 한 칸만 갈아엎고 H 는 건드리지 않는다.
#
# ★ 봉인 PR 의 CI 가 빨가면 **릴리즈는 계속한다**(§207-2 — 봉인은 기준선이지 관문이 아니다).
#   다만 이번에는 빨간 봉인이 part/infra 에 **안 들어간다** — PR 을 닫고 가지를 지운다.
#   `wait_checks` 는 0 초록 · 1 빨강 · 2 미상을 낸다. `set -e` 를 피하려고 서브셸에서 부른다.
say "A-0. 봉인 — 스쿼시 뒤 part/infra 에서 (PR 로)"
git switch -q part/infra 2>/dev/null || git switch -q -c part/infra origin/part/infra
git merge -q --ff-only origin/part/infra || die "로컬 part/infra 가 원격과 갈렸다 — git reset --hard origin/part/infra"
if uv run python tools/dms.py seal --quick; then
    # ★ 2026-09-21 (DECISIONS §210). 본문을 **템플릿으로** 쓰고, 가지를 만들기 **전에**
    #   로컬에서 관문에 넣어 본다. 처음엔 한 줄로 썼고 CI 의 `pr_body_check.py` 가 25초 만에
    #   빨갰다(PR #141) — 자동 절차가 여는 PR 도 사람이 여는 PR 과 같은 관문을 지난다.
    #   본문이 관문을 못 넘으면 **아무것도 안 만들고** 말하고 넘어간다(§207-2 · §208-6 —
    #   자동 절차가 남긴 가지·PR·더러운 파일이 다음 배치를 막는다).
    head=$(git rev-parse --short HEAD)
    body=$(mktemp)
    sed "s/{HEAD}/$head/g" .github/seal_pr_template.md > "$body"
    if [ -z "$(git status --porcelain -- data/dms/SEAL.json)" ]; then
        ok "봉인이 이미 최신이다 — 커밋할 것 없음"
    elif ! uv run python tools/pr_body_check.py --body-file "$body" >/dev/null; then
        git checkout -q -- data/dms/SEAL.json
        warn "봉인 PR 본문이 관문(pr_body_check)을 못 넘는다 — 봉인을 되돌리고 넘어간다.
  .github/seal_pr_template.md 를 고쳐라. 릴리즈는 계속한다."
    else
        sb="feat/seal-$head"
        git switch -q -c "$sb"
        git add data/dms/SEAL.json
        git commit -q -m "seal: $head 기준선 (판정 불변)"
        git push -q -u origin "$sb" || die "봉인 가지 $sb 를 못 밀었다"
        gh pr create -R "$REPO" --base part/infra --head "$sb" \
            --title "seal: $head 기준선 (판정 불변)" --body-file "$body" \
            >/dev/null || die "봉인 PR 을 못 열었다"
        spr=$(gh pr list -R "$REPO" --head "$sb" --state open --json number --jq '.[0].number // empty')
        [ -n "$spr" ] || die "봉인 PR 번호를 못 읽었다"
        if ( wait_checks "$spr" ); then wrc=0; else wrc=$?; fi
        if [ "$wrc" = 0 ]; then
            gh pr merge "$spr" -R "$REPO" --squash --delete-branch >/dev/null \
                || die "봉인 PR #$spr 을 스쿼시하지 못했다"
            git switch -q part/infra
            git fetch -q origin
            git merge -q --ff-only origin/part/infra || die "봉인 스쿼시 뒤 part/infra 를 못 당겼다"
            git branch -q -D "$sb" 2>/dev/null || true
            ok "봉인 갱신 · PR #$spr · part/infra $(git rev-parse --short origin/part/infra)"
        elif [ "$wrc" = 2 ]; then
            # ★ 2026-09-24 (DECISIONS §225-1). **모르면 안 지운다.** 종전에는 여기서
            #   PR 을 닫고 가지를 지웠는데, 2026-09-23 에 그 「빨강」이 GitHub 의
            #   503 이었다. 못 읽은 것을 근거로 되돌릴 수 없는 일을 했다.
            git switch -q part/infra
            warn "봉인 PR #$spr 의 검사 상태를 못 읽었다 — **PR 과 가지를 남긴다.**
  빨간불이 아니라 모르는 것이다. 사람이 보고 정한다:
    gh pr checks $spr -R $REPO
    gh pr merge $spr -R $REPO --squash --delete-branch   # 초록이면
    gh pr close $spr -R $REPO --delete-branch            # 진짜 빨강이면
  릴리즈는 계속한다 — 봉인은 기준선이지 관문이 아니다(§207-2)."
        else
            gh pr close "$spr" -R "$REPO" --delete-branch >/dev/null 2>&1 || true
            git switch -q part/infra
            git branch -q -D "$sb" 2>/dev/null || true
            warn "봉인 PR #$spr 의 CI 가 빨갰다 — 봉인은 part/infra 에 안 들어갔다. 릴리즈는 계속한다.
  PR 을 닫고 가지를 지웠다. 왜 빨갰는지:  gh pr checks $spr -R $REPO"
        fi
    fi
    rm -f "$body"
else
    # ★ 멈추지 않는다. 봉인은 기준선이지 관문이 아니다 — 여기서 die 하면
    #   빨간 강제자 하나 때문에 릴리즈 전체가 막히고, 그러면 사람이 이 단계를
    #   지우게 된다. 못 찍었다는 사실을 **말하고** 넘어간다.
    #
    # ★ 2026-09-21 (DECISIONS §208-6). **실패한 봉인이 남긴 것을 되돌린다.**
    #   `cmd_seal` 은 사유 없는 빨강을 만나면 `data/dms/RED.txt` 에 빈 사유
    #   줄(`이름 | `)을 **써놓고** 거부한다. 사람이 터미널에서 손으로 찍을 때는
    #   그 줄이 사유를 적을 자리표라 값이 있다. 그러나 **릴리즈 스크립트 안에서는
    #   아무도 그것을 안 채우고**, 추적 파일이 더러워진 채 남아 **다음 `fl.sh` 가
    #   1단계에서 거부당한다** — v0.28 뒤에 실제로 그랬다.
    #   자동 절차가 남긴 자리표는 선언이 아니라 찌꺼기다.
    git checkout -q -- data/dms/RED.txt 2>/dev/null || true
    warn "봉인을 못 찍었다 — 릴리즈는 계속한다. 사유를 위에서 읽고 따로 처리해라.
  ★ RED.txt 는 되돌렸다(자동 절차가 남긴 빈 사유 줄은 선언이 아니다).
  수동:  uv run python tools/dms.py seal --quick --red <아는빨강>"
fi
pr=$(gh pr list -R "$REPO" --base dev --head part/infra --state open --json number --jq '.[0].number // empty')
if [ -z "$pr" ]; then
    # ★ 2026-09-17 (DECISIONS §180 · G-10). 종전에는 경고만 하고 넘어갔다. part/infra 가 dev 보다
    #   앞서 있는데 PR 이 없으면 **PR 을 빠뜨린 것**이다 — 동기화도 건너뛰어 배치 D 가 part 에만 머물렀다.
    if ! git merge-base --is-ancestor origin/part/infra origin/dev; then
        # ★ 2026-09-24 (DECISIONS §225-3). **도구가 자기가 깨뜨린 전제를 사람 탓했다.**
        #   바로 위 A-0 이 part/infra 에 봉인 커밋을 얹어 dev 보다 앞세워 놓고,
        #   여기서 「PR 을 빠뜨렸다」며 죽었다. 빠뜨린 것은 사람이 아니라 A-0 이다.
        #   2026-09-23 에 이 한 줄 때문에 배치가 세 번 왕복했다.
        #   **커밋을 만든 쪽이 PR 도 연다.** 본문은 봉인 PR 과 같은 템플릿을 쓰고,
        #   열기 전에 로컬에서 관문(`pr_body_check`)에 넣어 본다 — 자동 절차가 여는
        #   PR 도 사람이 여는 PR 과 같은 관문을 지난다(§210).
        say "part/infra → dev PR 이 없다 — 이 도구가 만든 커밋이니 이 도구가 연다"
        _h=$(git rev-parse --short origin/part/infra)
        _b=$(mktemp)
        sed "s/{HEAD}/$_h/g" .github/seal_pr_template.md > "$_b"
        if uv run python tools/pr_body_check.py --body-file "$_b" >/dev/null 2>&1; then
            gh pr create -R "$REPO" --base dev --head part/infra \
                --title "파트 동기화 — part/infra $_h" --body-file "$_b" >/dev/null \
                && ok "파트 동기화 PR 을 열었다" \
                || die "파트 동기화 PR 을 못 열었다 — 손으로:\n  gh pr create -R $REPO --base dev --head part/infra"
            pr=$(gh pr list -R "$REPO" --base dev --head part/infra --state open \
                 --json number --jq '.[0].number // empty')
            [ -n "$pr" ] || die "PR 을 열었는데 목록에 없다 — 화면에서 확인하라"
        else
            rm -f "$_b"
            die "part/infra 가 dev 보다 앞서 있는데 PR 이 없고, 본문 템플릿이 관문을 못 넘는다.\n\
  .github/seal_pr_template.md 를 고치거나 손으로 열어라:\n\
    gh pr create -R $REPO --base dev --head part/infra --title ... --body-file ..."
        fi
        rm -f "$_b"
    else
        ok "열린 part/infra → dev PR 없음 · part/infra 가 dev 에 들어 있다 — 동기화만 한다"
    fi
fi

# ★ 2026-09-24 (DECISIONS §225-3). 갈래가 아니라 **한 줄**이다. 위에서 PR 을 새로
#   열었으면 그것도 여기로 떨어진다 — 종전 구조는 `else` 갈래에만 머지가 있어서,
#   A-0 이 연 PR 이 그 실행에서 머지되지 않고 다음 실행을 기다렸다.
if [ -n "$pr" ]; then
    gh pr view "$pr" -R "$REPO" --json number,title,commits,additions,deletions \
      --jq '"#\(.number)  \(.title)\n  커밋 \(.commits|length) · +\(.additions) −\(.deletions)"'
    ask "PR #$pr 을 dev 에 merge commit 으로 머지한다. 진행?" || { echo 멈춤; exit 0; }
    require_green "$pr"
    # ★ 2026-09-24 (DECISIONS §225-4). **머리를 다시 읽고 그 머리로 머지한다.**
    #   종전에는 `wait_checks` 가 A-0 의 push **이전** 머리를 읽고 그것으로 머지를
    #   걸어, GitHub 이 `Head branch is out of date` 로 거부했다(2026-09-23).
    #   `--match-head-commit` 으로 **무엇을 머지하는지 명시**한다 — 그 사이에 또
    #   움직였으면 조용히 엉뚱한 것을 머지하는 대신 거부당하는 편이 낫다.
    git fetch -q origin
    _head=$(gh pr view "$pr" -R "$REPO" --json headRefOid --jq '.headRefOid // empty')
    for _try in 1 2 3; do
        if [ -n "$_head" ]; then
            if _out=$(gh pr merge "$pr" -R "$REPO" --merge --match-head-commit "$_head" 2>&1)
            then _rc=0; else _rc=$?; fi
        else
            if _out=$(gh pr merge "$pr" -R "$REPO" --merge 2>&1); then _rc=0; else _rc=$?; fi
        fi
        printf '%s\n' "$_out"
        [ "$_rc" = 0 ] && break
        case "$_out" in
          *"out of date"*|*"not mergeable"*|*"Base branch was modified"*)
            warn "머리가 그 사이 움직였다 ($_try/3) — 다시 읽고 시도한다"
            sleep 8; git fetch -q origin
            _head=$(gh pr view "$pr" -R "$REPO" --json headRefOid --jq '.headRefOid // empty')
            continue ;;
        esac
        diagnose "$_out"
        die "PR #$pr 을 머지하지 못했다 — 위 메시지를 읽어라"
    done
    [ "$_rc" = 0 ] || die "PR #$pr 을 세 번 시도해도 머지하지 못했다 — 화면에서 확인하라"
    git fetch -q origin
    git merge-base --is-ancestor origin/part/infra origin/dev \
      || die "머지했다는데 origin/dev 가 part/infra 를 안 품는다 — 화면에서 확인하라"
    ok "PR #$pr 머지 · dev $(git rev-parse --short origin/dev)"
fi
sync_parts

[ "$RELEASE" = 1 ] || { ok "A 끝. 릴리즈는 --release"; exit 0; }

# ══ B. dev → main 릴리즈 ══════════════════════════════════════
say "B. 릴리즈 — dev → main"
uv run python tools/ruleset_check.py || die "룰셋 실물이 §12-1 과 어긋난다 — 릴리즈 전에 고친다(§12-8b)"

if git diff --quiet origin/main origin/dev; then
    warn "main 과 dev 내용이 같다. 릴리즈할 것이 없다"; exit 0
fi

# B-1. 스쿼시로 갈라진 main 을 dev 가 먼저 품는다
if ! git merge-base --is-ancestor origin/main origin/dev; then
    say "B-1. main 이 dev 조상이 아니다(스쿼시 흔적) — dev 에 origin/main 을 먼저 합친다"
    git switch -q dev 2>/dev/null || git switch -q -c dev origin/dev
    git merge -q --ff-only origin/dev
    if ! git merge --no-ff --no-edit origin/main; then
        left=$(git diff --name-only --diff-filter=U)
        [ "$left" = "data/dms/SEAL.json" ] \
          || { git merge --abort; die "SEAL.json 밖에서 충돌했다:\n$left\n  손으로 푼다"; }
        git checkout --ours data/dms/SEAL.json   # dev 의 봉인이 최신이다
        git add data/dms/SEAL.json
        git commit -q --no-edit
        ok "충돌은 SEAL.json 하나 — dev 쪽으로 풀었다"
    fi
    git diff --quiet HEAD origin/dev \
      || die "main 을 합쳤더니 dev 내용이 바뀌었다 — 스쿼시 차이가 아니라 실제 차이다. 멈춘다"
    git push -q origin dev
    git fetch -q origin
    ok "dev 가 main 을 품었다 · 내용 변화 0"
fi

# B-2. PR 본문 — 템플릿 원본 + release_brief
say "B-2. 릴리즈 PR"
BODY=$(mktemp --suffix=.md)
# release_brief 는 base 에 origin/ 을 스스로 붙이고, 작업트리와 비교한다 — dev 를 띄우고 부른다
git switch -q dev 2>/dev/null || git switch -q -c dev origin/dev
git merge -q --ff-only origin/dev
uv run python tools/release_brief.py --base main --md > /tmp/brief.md \
  || die "release_brief 가 실패했다 — 표 없이 릴리즈 PR 을 열지 않는다"
uv run python - "$BODY" <<'PY'
import subprocess, sys
from pathlib import Path
def changed(*paths):
    return subprocess.run(["git","diff","--quiet","origin/main","origin/dev","--",*paths]).returncode != 0
t = Path(".github/pull_request_template.md").read_text(encoding="utf-8")
log = subprocess.run(["git","log","--oneline","--no-merges","origin/main..origin/dev"],
                     capture_output=True, text=True).stdout.strip()
brief = Path("/tmp/brief.md").read_text(encoding="utf-8").strip() if Path("/tmp/brief.md").exists() else ""
def put(after, text):
    global t
    i = t.index(after) + len(after); t = t[:i] + text + t[i:]
put("<!-- 한두 줄. 커밋 메시지 접두사와 맞춘다: gis / cv / api / ui / docs / fix -->\n",
    "\ndocs: 릴리즈 — dev 를 main 으로. 흡수하는 커밋:\n\n```\n" + (log or "(없음)") + "\n```\n\n" + brief + "\n")
put("  예)  src/firelane/seg/width.py:212  — 횡단선 간격을 0.5 → 0.25 로\n-->\n",
    "\ndata/golden/segments.fingerprint.json — 판정 4수치가 움직였는가. 위 release_brief 표의 `판정` 줄\n")
# ★ 2026-09-17 (G-11). 종전에는 data/processed 까지 봐서 대장 · 매니페스트만 바뀐 릴리즈(datasets 65 → 66)도
#   "바뀐다" 로 체크했다. 산출물 변경 = 판정 지문(golden) 또는 발행물(web/data, 매니페스트 제외)이다
# ★ 2026-09-18. `data/golden` 을 디렉터리째 보던 것을 판정 지문 파일 하나로 좁혔다.
#   PR #73 실물에서 release_brief 는 「넷 다 불변이다」를 계산해놓고 체크박스는
#   「바뀐다」에 찍혔다. 원인은 G-24 가 `data/golden/.code_fingerprint` 를
#   ast-dump → tokens-v1 로 옮긴 것이다 — 판정 4수치는 한 칸도 안 움직였는데
#   같은 디렉터리의 다른 파일이 바뀌어 체크박스가 뒤집혔다.
#   바로 위 put() 이 이 체크박스 옆에 「판정 4수치가 움직였는가. 위 release_brief
#   표의 `판정` 줄」을 적어 넣는다 — 물음은 4수치이고 측정은 디렉터리였다.
#   원칙 ② 그 형태다: 잘못된 것을 정확히 지킨다.
# ★ 2026-09-23 (DECISIONS §220). `web/data` 를 같이 보던 것을 **판정 지문 하나**로 좁혔다.
#   v0.35 에서 옛 지도 전용 발행 다섯을 멈춘 릴리즈가 「바뀐다 → golden 재잠금」에 찍혔다 —
#   판정 4수치는 한 칸도 안 움직였는데 표출 파일 수가 줄어서다. 물음은 「판정이 움직였나」다.
#   발행물 변화는 위 release_brief 표의 `계보` 줄이 이미 말한다.
out = changed("data/golden/segments.fingerprint.json")
t = t.replace("- [ ] 바뀐다" if out else "- [ ] 안 바뀐다", "- [x] 바뀐다" if out else "- [x] 안 바뀐다", 1)
con = changed("src/contracts", "tests/test_contract.py", "web/config.js")
t = t.replace("- [ ] `src/contracts/`" if con else "- [ ] 안 건드린다",
              "- [x] `src/contracts/`" if con else "- [x] 안 건드린다", 1)
t = t.replace("- [ ] base 브랜치가 맞다", "- [x] base 브랜치가 맞다")
Path(sys.argv[1]).write_text(t, encoding="utf-8")
PY
uv run python tools/pr_body_check.py --body-file "$BODY" || die "릴리즈 PR 본문이 검사를 못 넘는다: $BODY"
sed -n '/## 무엇을/,/## 계약을/p' "$BODY" | head -60

rel=$(gh pr list -R "$REPO" --base main --head dev --state open --json number --jq '.[0].number // empty')
if [ -z "$rel" ]; then
    ask "위 본문으로 dev → main PR 을 연다. 진행?" || { echo 멈춤; exit 0; }
    gh pr create -R "$REPO" --base main --head dev --title "릴리즈 — $(date +%F)" --body-file "$BODY"
    # ★ 2026-09-17 (DECISIONS §182-3 · G-16). `// empty` 가 없으면 PR 이 안 보일 때 jq 가 `null` 을 **글자로** 낸다.
    #   `[ -z ]` 가 못 걸러 `wait_checks null` · `gh pr merge null` 로 흘렀다(chain.2 의 `PR #null`).
    rel=$(gh pr list -R "$REPO" --base main --head dev --state open --json number --jq '.[0].number // empty')
    [ -n "$rel" ] || die "릴리즈 PR 을 열었는데 목록에 없다 — 화면에서 확인하라"
else
    warn "이미 열린 릴리즈 PR #$rel 을 쓴다"
fi
require_green "$rel"
ask "PR #$rel 을 main 에 merge commit 으로 머지한다(승인 1 은 --admin 으로 넘는다). 진행?" || { echo 멈춤; exit 0; }
gh pr merge "$rel" -R "$REPO" --merge --admin
git fetch -q origin
git merge-base --is-ancestor origin/dev origin/main || die "main 이 dev 를 안 품는다 — 화면에서 확인하라"
git diff --quiet origin/main origin/dev || die "머지 뒤 main 과 dev 내용이 다르다"
ok "main $(git rev-parse --short origin/main) · dev 와 내용 같음"

# B-3. 태그 · 릴리즈 — 다음 번호를 **계산해서 묻는다**(§12-8b · DECISIONS §218-4 · 하토르 release.yml 모범)
# ★ 2026-09-22. 종전엔 태그를 손으로 **쳤다** — 한글 입력기 바이트가 붙는 사고(G-12)가 그 자리였고,
#   GitHub Release 는 한 번도 안 만들어져 「v0.34 에 무엇이 들었나」 를 PR 을 뒤져야 알았다.
#   지금은 마지막 `v0.N` 의 다음을 내고 y/N 만 받는다. 아니면 종전처럼 직접 친다.
last=$(git tag -l 'v[0-9]*.[0-9]*' | { grep -E '^v[0-9]+\.[0-9]+$' || true; } | sort -V | tail -1)
next=""
if [ -n "$last" ]; then next="${last%.*}.$(( ${last##*.} + 1 ))"; fi
# ★ 2026-09-23 (DECISIONS §220). y/N 자리에 **태그를 그대로 치는** 사람이 있다(실제로 그랬다).
#   제안한 태그를 치면 그것은 「예」다 — 다시 묻지 않는다.
tag=""
if [ -n "$next" ]; then
    a=$(read_answer "릴리즈 태그 $next (직전 $last) 를 붙이고 GitHub Release 를 만든다. [y/N/태그] ")
    a=$(printf '%s' "$a" | LC_ALL=C tr -cd 'A-Za-z0-9.-')
    case "$a" in
        y|Y|"$next") tag="$next" ;;
        # ★ 2026-09-23. [y/N/태그] 를 읽고 `n` 이라고 답하면 종전에는 태그 이름 `n` 으로 새어
        #   형식 검사에서 경고가 났다 — 거절은 거절로 받는다(빈 답과 같다).
        ""|n|N|no|No|NO) tag="" ;;
        *) tag="$a" ;;
    esac
else
    tag=$(read_answer "릴리즈 태그를 직접 (예 v0.3 · 비우면 안 붙인다): ")
fi
# ★ 2026-09-17 (G-12). 한글 입력기 상태에서 치면 앞에 깨진 바이트가 붙어 형식 검사에 걸렸다 — 인쇄 가능한 ASCII 만 남긴다
tag=$(printf '%s' "$tag" | LC_ALL=C tr -cd 'A-Za-z0-9.-')
if [ -n "$tag" ] && ! [[ "$tag" =~ ^v[0-9]+\.[0-9]+(-[a-z0-9]+)?$ ]]; then
    warn "태그 \"$tag\" 는 형식(v0.3 · v0.1-team5)이 아니다 — 안 붙인다. 손으로: git tag vX.Y origin/main"; tag=""
fi
if [ -n "$tag" ]; then
    git tag "$tag" origin/main && git push -q origin "$tag" && ok "태그 $tag"
    # 릴리즈 노트는 릴리즈 PR 본문 그대로다(release_brief 표 포함) — 한 벌을 두 곳에 두지 않는다
    gh release create "$tag" -R "$REPO" --title "$tag — $(date +%F)" --notes-file "$BODY" --verify-tag \
        && ok "GitHub Release $tag" || warn "Release 를 못 만들었다 — 태그는 붙었다. 손으로: gh release create $tag --notes-file <본문>"
fi

# B-4. 흡수 — main 의 머지 커밋을 dev 로 ff
say "B-4. 흡수 — main → dev (ff)"
git merge-base --is-ancestor origin/dev origin/main || die "dev 가 main 조상이 아니다 — ff 불가"
git push -q origin "origin/main:refs/heads/dev" 2>&1 | grep -v "^remote:" || true
git fetch -q origin
[ "$(git rev-parse origin/dev)" = "$(git rev-parse origin/main)" ] || die "흡수 뒤 dev ≠ main"
ok "dev = main $(git rev-parse --short origin/main)"
git switch -q dev 2>/dev/null && git merge -q --ff-only origin/dev || true

sync_parts
say "끝 — 상태"
for b in main dev $PARTS; do
    printf '  %-12s %s\n' "$b" "$(git rev-parse --short "origin/$b" 2>/dev/null || echo 없음)"
done
