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

wait_checks() {   # wait_checks <PR번호> [since ISO8601]
    local n=$1 since=${2:-} sha cnt
    say "CI 대기 — PR #$n"
    # ★ 2026-09-17 (DECISIONS §182-8 · G-23). "체크가 하나라도 있으면" 기다림을 끝냈다. 본문을 고친 직후(edited)에는
    #   **옛 실행**의 결과가 이미 있어서, 새 실행이 등록되기 전에 옛 실패 · 옛 초록으로 판정했다(#59 가 본문 검사
    #   실패인 채 스쿼시됐다). PR 머리 커밋의 check-run 을 보고, since 가 주어지면 그 뒤에 **시작된** 실행이
    #   생길 때까지 기다린다.
    sha=$(gh pr view "$n" -R "$REPO" --json headRefOid --jq '.headRefOid // empty')
    [ -n "$sha" ] || die "PR #$n 의 머리 커밋을 못 읽었다"
    for _ in $(seq 1 30); do
        cnt=$(gh api "repos/$REPO/commits/$sha/check-runs" \
              --jq "[.check_runs[] | select(\"$since\" == \"\" or .started_at >= \"$since\")] | length" 2>/dev/null || echo 0)
        [ "${cnt:-0}" -gt 0 ] && break
        sleep 10
    done
    [ "${cnt:-0}" -gt 0 ] || die "PR #$n 머리 ${sha:0:7} 에 ${since:+$since 이후 }시작된 검사가 5분 동안 없다"
    gh pr checks "$n" -R "$REPO" --watch --fail-fast \
      || die "PR #$n CI 가 실패했다. 메시지를 끝까지 읽어라:\n  gh pr checks $n -R $REPO"
    ok "PR #$n CI 초록 · 머리 ${sha:0:7}"
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
openfeat=$(gh pr list -R "$REPO" --base part/infra --state open --json number,headRefName --jq '.[] | "#\(.number) \(.headRefName)"')
if [ -n "$openfeat" ]; then
    die "part/infra 로 가는 PR 이 아직 열려 있다 — squash 머지부터:\n$openfeat"
fi
pr=$(gh pr list -R "$REPO" --base dev --head part/infra --state open --json number --jq '.[0].number // empty')
if [ -z "$pr" ]; then
    # ★ 2026-09-17 (DECISIONS §180 · G-10). 종전에는 경고만 하고 넘어갔다. part/infra 가 dev 보다
    #   앞서 있는데 PR 이 없으면 **PR 을 빠뜨린 것**이다 — 동기화도 건너뛰어 배치 D 가 part 에만 머물렀다.
    if ! git merge-base --is-ancestor origin/part/infra origin/dev; then
        die "part/infra 가 dev 보다 앞서 있는데 열린 part/infra → dev PR 이 없다 — PR 을 빠뜨렸다\n  gh pr create -R $REPO --base dev --head part/infra --title ... --body-file ..."
    fi
    ok "열린 part/infra → dev PR 없음 · part/infra 가 dev 에 들어 있다 — 동기화만 한다"
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
# ★ 2026-09-17 (G-11). 종전에는 data/processed 까지 봐서 대장 · 매니페스트만 바뀐 릴리즈(datasets 65 → 66)도
#   "바뀐다" 로 체크했다. 산출물 변경 = 판정 지문(golden) 또는 발행물(web/data, 매니페스트 제외)이다
out = changed("data/golden", "web/data", ":(exclude)web/data/_manifest.json")
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
wait_checks "$rel"
ask "PR #$rel 을 main 에 merge commit 으로 머지한다(승인 1 은 --admin 으로 넘는다). 진행?" || { echo 멈춤; exit 0; }
gh pr merge "$rel" -R "$REPO" --merge --admin
git fetch -q origin
git merge-base --is-ancestor origin/dev origin/main || die "main 이 dev 를 안 품는다 — 화면에서 확인하라"
git diff --quiet origin/main origin/dev || die "머지 뒤 main 과 dev 내용이 다르다"
ok "main $(git rev-parse --short origin/main) · dev 와 내용 같음"

# B-3. 태그 — 사람이 정한다(§12-8b)
tag=$(read_answer "릴리즈 태그 (예 v0.3 · 비우면 안 붙인다): ")
# ★ 2026-09-17 (G-12). 한글 입력기 상태에서 치면 앞에 깨진 바이트가 붙어 형식 검사에 걸렸다 — 인쇄 가능한 ASCII 만 남긴다
tag=$(printf '%s' "$tag" | LC_ALL=C tr -cd 'A-Za-z0-9.-')
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
