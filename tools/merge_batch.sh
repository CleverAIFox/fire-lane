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

VERSION=2026-09-16.2   # ★ 어느 판이 돌았는지 첫 줄에서 보인다

say() { printf '\n\033[36m── %s\033[0m\n' "$*"; }
die() { printf '\n\033[31m✗ %b\033[0m\n' "$*"; exit 1; }
ok()  { printf '\033[32m✓ %s\033[0m\n' "$*"; }
warn(){ printf '\033[33m! %b\033[0m\n' "$*"; }
ask() { read -r -p "$1 [y/N] " yn; [ "$yn" = "y" ]; }

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

wait_checks() {   # wait_checks <PR번호>
    local n=$1
    say "CI 대기 — PR #$n"
    # 체크가 등록되기 전에 부르면 '없음' 으로 끝난다. 잠깐 기다린다
    for _ in 1 2 3 4 5 6; do
        gh pr checks "$n" -R "$REPO" >/dev/null 2>&1 && break; sleep 10
    done
    gh pr checks "$n" -R "$REPO" --watch --fail-fast \
      || die "PR #$n CI 가 실패했다. 메시지를 끝까지 읽어라:\n  gh pr checks $n -R $REPO"
    ok "PR #$n CI 초록"
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
pr=$(gh pr list -R "$REPO" --base dev --head part/infra --state open --json number --jq '.[0].number // empty')
if [ -z "$pr" ]; then
    warn "열린 part/infra → dev PR 이 없다. 이미 머지됐으면 동기화만 한다"
else
    gh pr view "$pr" -R "$REPO" --json number,title,commits,additions,deletions \
      --jq '"#\(.number)  \(.title)\n  커밋 \(.commits|length) · +\(.additions) −\(.deletions)"'
    ask "PR #$pr 을 dev 에 merge commit 으로 머지한다. 진행?" || { echo 멈춤; exit 0; }
    wait_checks "$pr"
    gh pr merge "$pr" -R "$REPO" --merge
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
out = changed("data/golden", "data/processed", "web/data")
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
    rel=$(gh pr list -R "$REPO" --base main --head dev --state open --json number --jq '.[0].number')
else
    warn "이미 열린 릴리즈 PR #$rel 을 쓴다"
fi
wait_checks "$rel"
ask "PR #$rel 을 main 에 merge commit 으로 머지한다(승인 1 은 --admin 으로 넘는다). 진행?" || { echo 멈춤; exit 0; }
gh pr merge "$rel" -R "$REPO" --merge --admin
git fetch -q origin
git merge-base --is-ancestor origin/dev origin/main || die "main 이 dev 를 안 품는다 — 화면에서 확인하라"
git diff --quiet origin/main origin/dev || die "머지 뒤 main 과 dev 내용이 다르다"
ok "main $(git rev-parse --short origin/main) · dev 와 내용 같음"

# B-3. 태그 — 사람이 정한다(§12-8b)
read -r -p "릴리즈 태그 (예 v0.3 · 비우면 안 붙인다): " tag
if [ -n "$tag" ] && ! [[ "$tag" =~ ^v[0-9]+\.[0-9]+(-[a-z0-9]+)?$ ]]; then
    warn "태그 \"$tag\" 는 형식(v0.3 · v0.1-team5)이 아니다 — 안 붙인다. 손으로: git tag vX.Y origin/main"; tag=""
fi
if [ -n "$tag" ]; then
    git tag "$tag" origin/main && git push -q origin "$tag" && ok "태그 $tag"
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
