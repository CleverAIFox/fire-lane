#!/usr/bin/env bash
# 계정 단위 pre-push (git config --global core.hooksPath ~/.githooks). **정본은 이 파일이다** — `~/.githooks/pre-push` 로 복사한다:
#     install -m 755 .githooks/global-pre-push.sh ~/.githooks/pre-push
#
# 저장소가 자기 pre-push 를 가지면 그것을 부른다. `~/.githooks/pre-commit` 과 **같은 이음**이다 — `core.hooksPath` 는 한 곳만
# 가리키므로 전역이 이 이음을 안 두면 저장소의 pre-push 는 **조용히 안 돈다.** 인자와 stdin 을 그대로 넘긴다(git 이 줄을 stdin 으로 준다).
# 우회:  git push --no-verify
set -uo pipefail
root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$root" ] || exit 0
for candidate in "$root/.githooks/pre-push" "$root/scripts/hooks/pre-push"; do
    [ -x "$candidate" ] || continue
    [ "$(readlink -f "$candidate")" = "$(readlink -f "$0")" ] && continue
    cd "$root" && exec "$candidate" "$@"
done
exit 0
