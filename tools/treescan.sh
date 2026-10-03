#!/usr/bin/env bash
# treescan.sh — 비밀값을 **작업 트리 전수**로 훑는다. 이력도 범위도 아니다.
#
#   bash tools/treescan.sh              훑는다 (0 깨끗 · 1 걸림 · 2 못 훑음)
#   bash tools/treescan.sh --available  훑을 수 있나만 본다 (0/2)
#   bash tools/treescan.sh --selftest   판별식이 살아 있나
#
# ── 왜 생겼나 (DECISIONS §376 · §381) ──────────────────────────
# §376 이 트리 전수를 세웠다. 비밀값 방어 셋이 전부 **변화량**만 봐서
# (훅=스테이지 · 액션=커밋 범위 · 트리=없었다) 훅보다 먼저 들어온 값은
# 셋 모두에게 영원히 안 보였고, V-World 키가 `sources.yaml` 에 55일 있었다.
#
# ★ 2026-10-04 (§381). 그 단계가 **사람 기계에서 실패했다** —
#       1:13AM FTL unknown command "dir"
#   `gitleaks dir` 은 8.19 에서 생긴 하위명령이고 `apt` 가 주는 것은 8.16 이다.
#   그 전에는 같은 일을 `gitleaks detect --no-git` 가 했다. **검사가 아니라
#   호출 꼴이 틀렸고**, 그래서 멀쩡한 트리에서 빨간불이 났다.
#   근거 없이 우는 검사는 사람이 끄게 되고, 끄는 습관은 진짜 경보를
#   같이 죽인다(§73). 그래서 **부르는 쪽을 버전에 맞춘다.**
#
# ★ 정본을 여기 하나로 둔다. 종전에는 이 호출이 `verify.sh` 안에 있었고
#   `secret-scan.yml` 이 같은 일을 액션으로 했다 — 같은 물음을 두 집이
#   들면 둘은 갈린다(2족). 이제 로컬은 이 파일을 부른다.
#
# IN    .gitleaks.toml · 작업 트리
# OUT   없음 (종료코드)
# PARAM 없음
# 밖    **이력은 안 본다.** 이력 전수는 `gitleaks git --log-opts` 이고
#       §146 이 감수한 셋이 거기 있다. 여기가 드는 것은 「지금 디스크에
#       있나」 하나다 — 복제하면 같이 가는 것이 그것이다.
#       **값이 비밀인지도 안 가른다.** 그 규칙은 `.gitleaks.toml` 이 든다.
set -uo pipefail
cd "$(dirname "$0")/.."

have() { command -v gitleaks >/dev/null 2>&1; }
# 하위명령이 있는가. `--help` 로 묻는다 — 버전 문자열을 파싱하면 배포판마다 갈린다.
has_sub() { gitleaks "$1" --help >/dev/null 2>&1; }
# 깃발이 있는가. 8.16 에 없는 것을 주면 그 자체로 빨간불이 난다.
has_flag() { gitleaks "$1" --help 2>&1 | grep -q -- "$2"; }

# ★ **부르는 꼴의 정본.** 자기검사와 본 경로가 같은 인자를 쓰게 한다 —
#   둘이 갈리면 자기검사만 통과하고 진짜 호출이 터진다(§381 이 그 모양이다).
pick() {
    ARGS=(--config .gitleaks.toml --redact --exit-code 1)
    if has_sub dir; then
        SUB=(dir .)
        has_flag dir --no-banner && ARGS+=(--no-banner)
    elif has_sub detect; then
        SUB=(detect --source . --no-git)        # 8.18 이전의 같은 일
        has_flag detect --no-banner && ARGS+=(--no-banner)
    else
        return 1
    fi
    return 0
}

case "${1:-}" in
--available)
    have || exit 2
    exit 0
    ;;
--selftest)
    if ! have; then
        echo "✓ 자기검사 — gitleaks 가 없다. 「못 훑음(2)」로 센다"
        exit 0
    fi
    if ! pick; then
        echo "★ 자기검사 실패 — gitleaks 는 있는데 dir · detect 둘 다 없다"
        exit 1
    fi
    # ★ **합성 양성 대조를 여기 두지 않는다.** 심을 값이 UUID 라 이 파일에
    #   적는 순간 추적 파일에 비밀값 꼴이 남고, 그러면 이 검사가 자기 자신을
    #   문다. 그 대조는 `tests/test_gitleaks_allowlist.py` 가 이미 든다 —
    #   값을 조립해서 임시 자리에 심고 양방향으로 잰다(§376 ③). 정본이 거기다.
    echo "✓ 자기검사 — 하위명령 ${SUB[0]} · 인자 ${#ARGS[@]}개를 한 함수가 만든다"
    exit 0
    ;;
esac

have || { echo "gitleaks 가 없다"; exit 2; }
pick || { echo "gitleaks 가 dir · detect 둘 다 모른다 — 버전이 너무 낡았다"; exit 2; }

gitleaks "${SUB[@]}" "${ARGS[@]}"
