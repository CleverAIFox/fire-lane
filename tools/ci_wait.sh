#!/usr/bin/env bash
# ci_wait.sh — PR 검사가 끝날 때까지 **조용히** 기다린다. (DECISIONS §278-6)
#
#   bash tools/ci_wait.sh <PR번호>        0 초록 · 1 빨강 · 2 못 읽음(시간 초과 포함)
#   bash tools/ci_wait.sh --selftest      ★ 판별식이 살아 있나
#
# ── 왜 생겼나 (2026-09-28) ─────────────────────────────────────
# `gh pr checks --watch` 는 10초마다 **표 전체를 다시 찍는다.** 2026-09-28 배치
# 로그가 853줄이었고 그중 **564줄(66%)이 같은 표의 반복**이었다. 실패는 0건인데
# 사람이 로그를 열고 「여기저기서 문제가 쏟아진다」고 읽었다 — 소음이 그 자체로
# 결함이다. 읽을 수 없는 로그는 안 읽히고, 안 읽히는 로그에서는 진짜 실패도
# 안 보인다.
#
# ★ **두 곳이 따로 기다리고 있었다.** `merge_batch.sh` 는 §225-1 에서 「빨강」과
#   「못 읽음」을 가르도록 고쳤는데(503 을 빨강으로 읽고 PR 을 지운 사고),
#   `fl.sh` 는 같은 `gh pr checks --watch` 를 부르고 **비영(非零)이면 전부
#   빨강으로** 읽고 있었다. 같은 물음을 두 곳이 다르게 답하고 있었던 것이다.
#   고치는 자리를 하나로 만든다 — 두 곳을 각각 고치면 또 갈린다.
#
# ── 무엇을 하나 ────────────────────────────────────────────────
# ① `gh pr checks` 를 `--watch` 없이 되묻는다. 상태 **요약 한 줄**을 만들고
#    **바뀔 때만** 찍는다. 안 바뀌면 아무것도 안 찍는다.
# ② 빨강이 하나라도 나오면 남은 것을 안 기다린다(fail-fast).
# ③ `MAX` 를 넘으면 **2**(모름)로 나간다. 1(빨강)이 아니다 — 안 끝난 것과
#    빨간 것은 다르고, 섞으면 호출부가 PR 을 지운다.
# ④ 네트워크·서버 오류는 빨강이 아니다(`unreadable`). §225-1 의 규칙 그대로다.
#
# IN    gh (PR 검사 상태) · 인자로 받은 <owner/repo>
# OUT   종료코드 0·1·2 · 진행 한 줄
# PARAM CI_WAIT_MAX · CI_WAIT_POLL
# 밖    **검사가 등록되기를 기다리지 않는다.** 「옛 실행의 결과를 새 것으로
#       읽는」 문제(§182-8 · G-23)는 머리 커밋의 check-run 을 세는 쪽 —
#       `merge_batch.wait_checks` — 가 든다. 여기는 이미 도는 것이 끝나기를
#       기다릴 뿐이다. **머지하지 않는다**: 판단은 호출부가 한다.
set -uo pipefail

: "${CI_WAIT_MAX:=1800}"      # 30분. 넘으면 모름(2) — 빨강이 아니다
: "${CI_WAIT_POLL:=15}"

# ★ 이름이 아니라 **글자**로 가른다(§225-1). 종료코드는 「빨강」과 「못 읽음」을
#   안 가르므로 출력을 본다. 못 가르면 또 지운다.
unreadable() {                  # unreadable <출력>
    printf '%s' "$1" | grep -qiE 'HTTP (4[0-9][0-9]|5[0-9][0-9])|Service Unavailable|Bad Gateway|timeout|timed out|connection reset|EOF|could not resolve|dial tcp|rate limit'
}

# `gh pr checks` 는 비대화형에서 탭으로 가른 «이름 상태 시간 URL» 을 낸다.
tally() {                       # tally <출력> → "초록 N · 빨강 N · 대기 N · 생략 N"
    printf '%s\n' "$1" | awk -F'\t' '
        NF >= 2 { c[$2]++ }
        END { printf "초록 %d · 빨강 %d · 대기 %d · 생략 %d",
                     c["pass"], c["fail"] + c["cancel"],
                     c["pending"], c["skipping"] }'
}

reds() { printf '%s\n' "$1" | awk -F'\t' 'NF>=2 && ($2=="fail" || $2=="cancel")' ; }

# ★ 한 번 물은 결과를 어떻게 읽는가. **순수 함수** — 합성 입력으로 부를 수 있다.
#   0 초록 · 1 빨강 · 3 아직 돈다 · 2 못 읽음
verdict() {                     # verdict <gh 종료코드> <출력>
    local rc=$1 out=$2
    [ "$rc" = 0 ] && return 0
    [ -n "$(reds "$out")" ] && return 1        # fail-fast — 남은 것을 안 기다린다
    [ "$rc" = 8 ] && return 3                  # gh 규약: 8 = 아직 대기 중
    unreadable "$out" && return 2
    return 1
}

wait_ci() {                     # wait_ci <PR> <REPO> → 0 · 1 · 2
    local n=$1 repo=$2 t=0 out rc v last="" line
    while [ "$t" -lt "$CI_WAIT_MAX" ]; do
        if out=$(gh pr checks "$n" -R "$repo" 2>&1); then rc=0; else rc=$?; fi
        verdict "$rc" "$out"; v=$?
        if [ "$v" != 3 ]; then
            line=$(tally "$out")
            [ "$line" != "$last" ] && printf '     %s\n' "$line"
            [ "$v" = 1 ] && printf '%s\n' "$(reds "$out")"
            [ "$v" = 2 ] && printf '  ! 검사 상태를 못 읽었다 — %s\n' "$(printf '%s' "$out" | head -1)"
            return "$v"
        fi
        line=$(tally "$out")
        # ★ **바뀔 때만** 찍는다. 이 한 줄이 로그 564줄을 없앤다.
        [ "$line" != "$last" ] && { printf '     %s\n' "$line"; last=$line; }
        sleep "$CI_WAIT_POLL"; t=$((t + CI_WAIT_POLL))
    done
    printf '  ! PR #%s 검사가 %s초 안에 안 끝났다 — **빨간불이 아니라 모름이다.**\n' "$n" "$CI_WAIT_MAX"
    return 2
}

selftest() {
    local bad=() t
    local green=$'a\tpass\t1s\tu\nb\tskipping\t0\tu'
    local red=$'a\tpass\t1s\tu\nb\tfail\t9s\tu'
    local busy=$'a\tpass\t1s\tu\nb\tpending\t0\tu'
    t=$(tally "$busy")
    [ "$t" = "초록 1 · 빨강 0 · 대기 1 · 생략 0" ] || bad+=("요약이 틀렸다: $t")
    ( verdict 0 "$green" ); [ $? = 0 ] || bad+=("초록을 초록으로 안 읽는다")
    ( verdict 8 "$busy"  ); [ $? = 3 ] || bad+=("대기를 대기로 안 읽는다")
    ( verdict 8 "$red"   ); [ $? = 1 ] || bad+=("대기 중에 난 빨강을 안 잡는다 — fail-fast 가 죽었다")
    ( verdict 1 "$red"   ); [ $? = 1 ] || bad+=("빨강을 빨강으로 안 읽는다")
    ( verdict 1 "HTTP 503 Service Unavailable" ); [ $? = 2 ] \
        || bad+=("503 을 **빨강으로 읽는다** — §225-1 이 PR 을 지운 그 결함이다")
    ( verdict 1 "could not resolve host" ); [ $? = 2 ] || bad+=("이름 풀이 실패를 빨강으로 읽는다")
    unreadable "$red" && bad+=("평범한 빨강을 «못 읽음» 으로 읽는다 — 그러면 빨강이 통과한다")
    # ★ 시간 초과가 2 인가. 1 이면 호출부가 PR 을 지운다.
    ( CI_WAIT_MAX=0; wait_ci 1 x/y >/dev/null ); [ $? = 2 ] || bad+=("시간 초과를 2 로 안 낸다")
    if [ ${#bad[@]} -gt 0 ]; then
        printf '★ 자기검사 실패\n'; printf '  %s\n' "${bad[@]}"; return 1
    fi
    printf '✓ ci_wait — 초록 · 대기 · 빨강 · 조회실패 · 시간초과를 다 가른다\n'
}

case "${1:-}" in
    --selftest) selftest; exit $? ;;
esac
# ★ 저장소 이름에 **기본값을 두지 않는다.** 여기 적으면 그 문자열의 세 번째
#   사본이 되고(`fl.sh` · `merge_batch.sh` 가 정본), 셋 중 하나만 고쳐지는 날이
#   온다. 안 주면 모르는 것이고, 모르는 채로 남의 저장소를 묻지 않는다.
[ $# -ge 2 ] || { printf '쓰기: bash tools/ci_wait.sh <PR번호> <owner/repo>\n' >&2; exit 2; }
wait_ci "$1" "$2"
