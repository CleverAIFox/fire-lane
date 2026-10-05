#!/usr/bin/env bash
# ci_wait.sh — PR 검사가 끝날 때까지 **조용히** 기다린다. (DECISIONS §278-6)
# 부류  절차   배치를 옮기고 기계를 치운다. **산출물에 안 닿는다**  (DECISIONS §398)
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
# 밖    **옛 실행의 결과를 새 것으로 읽는 문제**(§182-8 · G-23)는 여기가 안 든다 —
#       머리 커밋의 check-run 을 세는 쪽(`merge_batch.wait_checks`)이 든다.
#       ★ 2026-09-30 (DECISIONS §335) 정정. 종전에 이 칸은 「검사가 등록되기를
#         기다리지 않는다」였고, 그 말이 **「등록 전이면 빨강」으로 굳어 있었다.**
#         기다리지 않는 것과 빨강이라 말하는 것은 다르다. 이제 줄이 0개면
#         `CI_WAIT_MAX` 까지 기다리고, 그래도 안 뜨면 **2(모름)** 로 낸다.
#         묵는 실행을 새 것으로 읽는 위험은 안 는다 — `gh pr checks` 는 그 PR 의
#         머리에 매인다. **머지하지 않는다**: 판단은 호출부가 한다.
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

# ★ 2026-09-30 (DECISIONS §335). **검사 줄이 하나라도 있는가.**
#   푸시 직후에는 GitHub 이 check-run 을 아직 안 만들고, 그때 `gh pr checks` 는
#   **1 로 나가면서 줄을 0개** 낸다. 그 상태는 「빨강」이 아니라 「아직 안 떴다」다.
rows() { printf '%s\n' "$1" | awk -F'\t' 'NF>=2' ; }

# ★ 2026-09-28 (DECISIONS §282-1). **「빨강이 없다」와 「밑동이 받아준다」는 다르다.**
#   2026-09-28 배치 D 에서 이 도구가 「초록 3 · 빨강 0」을 찍고 초록이라 말했는데
#   스쿼시가 거부됐다 — `the base branch policy prohibits the merge`.
#   원인: `push` 와 `pull_request` 가 같은 워크플로를 깨워 **같은 SHA 에
#   `contract-shared` check-run 이 둘** 생겼고, 그중 하나가 **결론이 없었다.**
#   GitHub 은 필수 검사의 결론 없는 실행을 미충족으로 본다. `gh pr checks` 는
#   그것을 안 세므로 초록이라 말한다 — 어제 배치에서 난 것과 **같은 결함**이다.
#
#   그래서 초록의 정의를 바꾼다: 빨강이 없고 **필수 검사가 전부 결론이 났을 때**.
#   결론 없는 필수 검사가 남아 있으면 그것은 초록이 아니라 **아직 대기**다 —
#   대개 도는 중이고 기다리면 풀린다. 안 풀리면 시간 초과가 2(모름)로 낸다.
#
# ★ 2026-10-06 (DECISIONS §403). **한 겹이 모자랐다.** 위 고침은 「생겼는데 결론이
#   없는 실행」을 잡는다. 그날 막힌 것은 그 앞 단계였다 — `contract` 실행이
#   **아직 만들어지지도 않았다.** 결론 없는 실행이 하나도 없으니 교집합이 비고,
#   보이는 것(12초에 끝난 `secret-scan`)이 전부 초록이라 초록이라 말했다.
#   스쿼시가 또 `the base branch policy prohibits the merge` 로 거부됐다 —
#   §282-1 과 **같은 증상이 한 겹 더 이른 자리에서** 났다.
#
#   교집합을 **차집합**으로 바꾼다. 필수 중 결론이 난 것을 빼고 남는 것이 막는
#   것이다 — 그러면 「없는 실행」도 자동으로 남는다. 안 생긴 것을 세려고 목록을
#   더 만들지 않는다. **없는 것을 세는 유일한 방법은 있는 것을 빼는 것이다.**
#
#   ★ 「승인이 없어 BLOCKED」와 섞지 않는다. `mergeStateStatus` 하나만 보면
#     `main` 처럼 승인 1 이 필요한 가지에서 영원히 기다린다(릴리즈가 멈춘다).
#     **검사 쪽만** 본다 — 필수 검사 목록과 결론 없는 실행의 교집합.
#   ★ **차집합이다, 교집합이 아니다**(§403). 필수 목록에서 결론 난 것을 뺀다.
#     그러면 두 가지가 함께 남는다 — 결론 없는 실행(§282-1)과 **아예 없는 실행**.
#   ★ 필수 목록을 못 읽으면 **아무것도 안 막는다.** 모르는 것을 근거로 멈추면
#     룰셋이 없는 가지에서 영원히 기다린다.
unsettled() {           # unsettled <필수목록> <결론난목록> → 차집합
    local req=$1 done_=$2
    [ -n "$req" ] || return 0
    printf '%s\n' "$req" | sort -u | while read -r n; do
        [ -n "$n" ] || continue
        printf '%s\n' "$done_" | grep -qxF "$n" || printf '%s\n' "$n"
    done
}

required_of() {         # required_of <REPO> <base가지> → 필수 검사 이름들
    local repo=$1 base=$2
    gh api "repos/$repo/rules/branches/${base//\//%2F}" \
       --jq '[.[]|select(.type=="required_status_checks")
              |.parameters.required_status_checks[].context]|.[]' 2>/dev/null
}

#   ★ `생략`(skipped)도 결론이다 — 조건으로 건너뛴 작업은 GitHub 이 충족으로
#     본다. 여기서 안 세면 건너뛰는 검사가 있는 가지가 영원히 기다린다.
settled_runs() {        # settled_runs <REPO> <PR> → 결론이 **난** check-run 이름들
    local repo=$1 n=$2 sha
    sha=$(gh pr view "$n" -R "$repo" --json headRefOid --jq .headRefOid 2>/dev/null) || return 0
    [ -n "$sha" ] || return 0
    gh api "repos/$repo/commits/$sha/check-runs" --paginate \
       --jq '.check_runs[]|select(.conclusion!=null)|.name' 2>/dev/null
}

blocking() {            # blocking <REPO> <PR> → 아직 결론 없는 **필수** 검사
    local repo=$1 n=$2 base
    base=$(gh pr view "$n" -R "$repo" --json baseRefName --jq .baseRefName 2>/dev/null) || return 0
    [ -n "$base" ] || return 0
    unsettled "$(required_of "$repo" "$base")" "$(settled_runs "$repo" "$n")"
}

# ★ 한 번 물은 결과를 어떻게 읽는가. **순수 함수** — 합성 입력으로 부를 수 있다.
#   0 초록 · 1 빨강 · 3 아직 돈다 · 2 못 읽음
verdict() {                     # verdict <gh 종료코드> <출력>
    local rc=$1 out=$2
    [ "$rc" = 0 ] && return 0
    [ -n "$(reds "$out")" ] && return 1        # fail-fast — 남은 것을 안 기다린다
    [ "$rc" = 8 ] && return 3                  # gh 규약: 8 = 아직 대기 중
    unreadable "$out" && return 2
    # ★ 2026-09-30 (DECISIONS §335). **줄이 0개면 빨강이 아니다.**
    #   종전에는 여기가 없어 아래 `return 1` 로 떨어졌다 — 푸시 직후 검사가
    #   아직 안 뜬 상태를 빨강으로 읽었고, 6단계가 「CI 가 빨갛다」로 죽었다.
    #   이 파일이 제 머리말에 「안 끝난 것과 빨간 것은 다르다」고 적어 두고도
    #   **catch-all 한 줄이 그것을 뚫고 있었다**(§225-1 · §282-1 과 같은 족).
    [ -z "$(rows "$out")" ] && return 3
    return 1
}

wait_ci() {                     # wait_ci <PR> <REPO> → 0 · 1 · 2
    local n=$1 repo=$2 t=0 out rc v last="" line miss
    while [ "$t" -lt "$CI_WAIT_MAX" ]; do
        if out=$(gh pr checks "$n" -R "$repo" 2>&1); then rc=0; else rc=$?; fi
        verdict "$rc" "$out"; v=$?
        # ★ 초록이라고 나와도 **필수 검사에 결론 없는 실행**이 남아 있으면
        #   그것은 초록이 아니다(§282-1). 초록일 때만 묻는다 — 매 회 물으면
        #   API 를 세 번씩 더 친다.
        if [ "$v" = 0 ]; then
            miss=$(blocking "$repo" "$n")
            if [ -n "$miss" ]; then
                [ "$last" != "wait:$miss" ] && {
                    printf '     필수 검사가 아직 결론이 없다 — %s\n' \
                           "$(printf '%s' "$miss" | tr '\n' ' ')"
                    last="wait:$miss"; }
                sleep "$CI_WAIT_POLL"; t=$((t + CI_WAIT_POLL)); continue
            fi
        fi
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
    miss=$(blocking "$repo" "$n")
    [ -n "$miss" ] && printf '    결론이 안 난 필수 검사: %s\n      셋 중 하나다 — 아직 도는 중 · 같은 이름이 두 번 돌아(push · pull_request) 한쪽이 안 끝났다 · **아예 안 생겼다.**\n      어느 쪽인지 보고 한쪽을 다시 돌려라:  gh pr checks <PR> -R %s\n' \
        "$(printf '%s' "$miss" | tr '\n' ' ')" "$repo"
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
    # ★ §282-1 · §403. 필수 − 결론 난 것.
    [ "$(unsettled $'contract-shared\nsecret-scan' $'secret-scan')" = "contract-shared" ] \
        || bad+=("결론 없는 **필수** 검사를 안 잡는다 — 배치 D 를 세운 그 자리다")
    [ "$(unsettled $'contract-shared' "")" = "contract-shared" ] \
        || bad+=("**아예 안 생긴** 필수 검사를 안 잡는다 — 봉인 PR #297 을 세운 그 자리다")
    [ -z "$(unsettled $'contract-shared' $'contract-shared\ndry')" ] \
        || bad+=("필수가 다 끝났는데 막는 것으로 본다 — 그러면 영원히 기다린다")
    [ -z "$(unsettled "" $'contract-shared')" ] \
        || bad+=("필수 목록을 못 읽었는데 막는 것으로 본다 — 모르면 안 막는다")
    # ★ §335. **줄이 0개인 것은 빨강이 아니다.** 2026-09-30 에 배치 O 의 6단계가
    #   여기서 죽었다 — 푸시 직후 `gh pr checks` 가 1 로 나가며 줄을 0개 냈다.
    ( verdict 1 "no checks reported on the 'feat/x' branch" ); [ $? = 3 ] \
        || bad+=("검사가 아직 안 뜬 것을 **빨강으로 읽는다** — 배치 O 를 세운 그 자리다")
    ( verdict 1 "" ); [ $? = 3 ] || bad+=("빈 출력을 빨강으로 읽는다")
    #   ★ 반대 방향 — 줄이 있으면서 판독 불가인 것까지 대기로 흘리면 빨강이 통과한다
    ( verdict 1 "$red" ); [ $? = 1 ] || bad+=("줄이 있는 빨강을 대기로 흘린다")
    [ -n "$(rows "$busy")" ] || bad+=("검사 줄을 못 센다 — 위 판별식이 언제나 초록이 된다")
    [ -z "$(rows "안내 한 줄")" ] || bad+=("탭 없는 안내문을 검사 줄로 센다")
    # ★ 시간 초과가 2 인가. 1 이면 호출부가 PR 을 지운다.
    ( CI_WAIT_MAX=0; wait_ci 1 x/y >/dev/null ); [ $? = 2 ] || bad+=("시간 초과를 2 로 안 낸다")
    if [ ${#bad[@]} -gt 0 ]; then
        printf '★ 자기검사 실패\n'; printf '  %s\n' "${bad[@]}"; return 1
    fi
    printf '✓ ci_wait — 초록 · 대기 · 빨강 · 조회실패 · 시간초과 · 결론 안 난 필수검사(**없는 것까지**) · 아직 안 뜬 검사를 다 가른다\n'
}

case "${1:-}" in
    --selftest) selftest; exit $? ;;
esac
# ★ 저장소 이름에 **기본값을 두지 않는다.** 여기 적으면 그 문자열의 세 번째
#   사본이 되고(`fl.sh` · `merge_batch.sh` 가 정본), 셋 중 하나만 고쳐지는 날이
#   온다. 안 주면 모르는 것이고, 모르는 채로 남의 저장소를 묻지 않는다.
[ $# -ge 2 ] || { printf '쓰기: bash tools/ci_wait.sh <PR번호> <owner/repo>\n' >&2; exit 2; }
wait_ci "$1" "$2"
