#!/usr/bin/env bash
# tools/verify.sh — 리팩터링 검증 일괄
#
#   bash tools/verify.sh            전체
#   bash tools/verify.sh --fast     파이프라인 전량(4분) 생략
#   bash tools/verify.sh --table    통과한 것까지 전부 표로
#   bash tools/verify.sh --only=pytest   ★ 이름이 맞는 단계만. 부분 실행이다
#   bash tools/verify.sh --since=origin/dev  ★ 바뀐 경로가 닿는 단계만. 부분 실행이다
#   bash tools/verify.sh --scope-list    단계별 영향 범위 선언을 표로 (안 돈다)
#
# ★ `--since` 의 규율 넷 (W7-2 · PLAN §13)
#
#   1. **미선언은 항상 돈다.** 범위를 안 적은 단계는 `--since` 에서도 전부
#      돈다. 안전한 기본값이 아니라 **유일하게 안전한 기본값**이다 —
#      손으로 적은 목록은 반드시 빠지고(deadcheck ②), 빠진 것이 조용히
#      건너뛰어지면 그것이 1족이다.
#   2. **건너뛴 것은 통과가 아니다.** 범위 밖이라 안 돈 단계는 `건너뜀` 으로
#      찍히고 아래 `부분 실행` 안전장치가 **이 실행 전체를 실패로 만든다.**
#      그래서 `--since` 로 돈 로그로는 `dms.py seal` 이 봉인할 수 없다.
#   3. **수용 조건이 아니다.** `--since` 는 고치는 중에 빨리 되먹임을 받는
#      도구다. 머지 전 수용은 전수 verify + CI 다(§13-5 규약 6).
#   4. **범위는 그 단계 옆에 적는다.** 별도 등록부로 빼면 단계 이름이 두
#      곳에 살고, 그것이 곧 2족이다. `scope` 는 **바로 다음 `step` 하나**
#      에만 걸린다.
#
# ★ `--only` 로 돈 결과는 전수가 아니다. 건너뛴 것은 통과가 아니므로
#   마지막에 `부분 실행` 단계를 일부러 실패시킨다 — 그래야 `dms.py seal`
#   이 반쪽 실행을 봉인하지 않는다.
#
# ★ 손으로 8줄 치지 마라. 중간에 뭐가 깨졌는지 못 짚는다.
#   여기서는 실패해도 끝까지 돌고 마지막에 표로 보여준다.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
FAST=0; [ "${1:-}" = "--fast" ] && FAST=1

# ── .env 를 셸로 올린다 ──────────────────────────────────────
# ★ `.env` 는 `paths.py`(파이썬)가 읽는다. **bash 는 안 읽는다.**
#   그래서 FIRE_LANE_DATA 를 .env 에만 적어두면 8번 파이프라인 단계가
#   영영 `생략` 으로 빠진다. 생략은 실패로 안 세므로 verify.sh 는
#   "전부 통과했다" 고 말한다 — 조용한 통과다(deadcheck ③).
# ★ 셸이 이긴다. paths.py 와 같은 규칙이다(빈 값은 미설정).
if [ -f .env ]; then                                    # dotenv
    while IFS='=' read -r k v; do
        case "$k" in ''|\#*) continue;; esac
        k="${k%"${k##*[![:space:]]}"}"; v="${v%$'\r'}"
        [ -n "$v" ] && [ -z "$(eval "printf '%s' \"\${$k:-}\"")" ] \
            && export "$k=$v"
    done < .env
fi

R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; C=$'\033[36m'; D=$'\033[90m'; Z=$'\033[0m'
declare -a NAMES RESULTS NOTES SECS
pass=0; fail=0; skip=0

# ── 진행 표시 ────────────────────────────────────────────────
# ★ 어디까지 왔는지 안 보이면 멈춘 건지 도는 건지 모른다.
# ★ 2026-09-15. 종전에는 `step "` 줄을 그냥 셌다. 그런데 `JS 부팅 스모크`
#   와 `내비 타입 검사` 는 if/elif 두 갈래에 같은 이름으로 적혀 있어
#   **둘 다 세졌다.** 41 로 찍히고 실제로는 38 이 돌아 "[38/41] 통과 38"
#   이 됐다 — 보는 사람은 셋이 빠졌다고 읽는다. 갈래는 하나만 돈다.
#   이름으로 유일화한다.
IDX=0; T_ALL=$(date +%s)
ONLY=""; TABLE=0; SINCE=""; SCOPELIST=0
for arg in "$@"; do
    case "$arg" in
        --only=*)  ONLY="${arg#--only=}" ;;
        --since=*) SINCE="${arg#--since=}" ;;
        --scope-list) SCOPELIST=1 ;;
        --table)   TABLE=1 ;;
    esac
done

# ── 영향 범위 (W7-2) ────────────────────────────────────────
# ★ 바뀐 경로를 **한 번만** 센다. 커밋된 차이와 아직 안 커밋한 것을 둘 다
#   본다 — 고치는 중에 쓰는 도구이므로 작업 트리가 진실이다.
# ★ 기준을 못 찾으면 **아무것도 건너뛰지 않는다.** 모를 때 건너뛰는 것은
#   검사를 끄는 것과 같다(「파이프라인 전량」의 rawdiff 와 같은 규율).
CHANGED=""
if [ -n "$SINCE" ]; then
    if ! git rev-parse --verify --quiet "$SINCE" >/dev/null 2>&1; then
        printf '%s✗ --since=%s 를 못 찾았다. 건너뛰지 않고 전수로 돈다.%s\n\n' "$R" "$SINCE" "$Z"
        SINCE=""
    else
        CHANGED=$(
            { git diff --name-only "$SINCE"...HEAD 2>/dev/null || true
              git status --porcelain 2>/dev/null | sed 's/^...//' | sed 's/.* -> //'
            } | sort -u)
        printf '%s바뀐 경로%s  %s개 (기준 %s)\n' "$D" "$Z" \
               "$(printf '%s' "$CHANGED" | grep -c . || true)" "$SINCE"
    fi
fi

SCOPE=""
# scope "패턴 ..." — **바로 다음 `step` 하나**에만 걸린다.
scope() { SCOPE="$*"; }

# ★ 2026-09-20 (W7-3). 「파이프라인 산출에 닿을 수 있는 것 전부」. 이 한 줄을
#   여러 단계가 공유한다 — **집이 하나여야** 한쪽만 넓히는 사고가 안 난다
#   (W3-11 과 같은 자리).
# ★ **좁게 적지 않았다.** 고친 것을 안 보고 초록이 뜨는 쪽이 훨씬 나쁘므로
#   과하게 넓힌다. 이 범위가 안 걸리는 배치는 사실상 문서·시험·CI·프런트
#   JS 만 만진 배치뿐이다. 그때 7분30초가 돌아온다.
# ★ `--since` 는 **수용이 아니다**(부분 실행 안전장치가 항상 빨갛게 끝낸다).
#   그러니 이 선언이 틀려도 머지가 통과하지는 않는다 — 되먹임만 빨라진다.
CODE_SCOPE="src/* tools/* data/* web/data/* sources.yaml pyproject.toml uv.lock .python-version"

# ── --scope-list — 선언을 **정적으로** 읽는다 ────────────────
# ★ 이 모드는 **아무것도 실행하지 않는다.** 처음엔 `step` 안에서 표를
#   찍게 했는데, 그러면 `if command -v npm` 갈래의 `npm install` ·
#   `npm ci` 가 **표를 보려고 돌린 것만으로 실행됐다.** 읽기 전용이라고
#   적어놓고 남의 기계에 패키지를 까는 것은 조용한 부작용이다.
#   `TOTAL` 이 자기 소스를 세는 것과 같은 방식으로 파일에서 읽는다.
# ★ 선언이 **어느 단계에도 안 붙은 채 떠 있으면** 그것을 말한다.
#   붙지 않은 선언은 아무 일도 안 하면서 「범위를 적었다」고 믿게 만든다.
if [ "$SCOPELIST" = "1" ]; then
    printf '\n%s단계별 영향 범위 선언%s\n\n' "$C" "$Z"
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$0" <<'PY'
import re, sys, unicodedata

def w(s): return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

src = open(sys.argv[1], encoding="utf-8").read().splitlines()
rows, dangling, pend, seen = [], [], None, set()
for i, line in enumerate(src, 1):
    s = line.strip()
    if s.startswith("#") or not s:
        continue
    m = re.match(r'scope "([^"]*)"', s)
    if m:
        if pend:
            dangling.append((pend[1], pend[0]))
        pend = (m.group(1), i)
        continue
    m = re.match(r'step "([^"]*)"', s)
    if m:
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            rows.append((name, pend[0] if pend else ""))
        pend = None
        continue
    if pend and not s.startswith(("fi", "else", "elif", "then", "}")):
        dangling.append((pend[1], pend[0]))
        pend = None
if pend:
    dangling.append((pend[1], pend[0]))

width = max((w(n) for n, _ in rows), default=0)
declared = sum(1 for _, sc in rows if sc)
for name, sc in rows:
    pad = " " * (width - w(name) + 2)
    print(f"  {name}{pad}" + (sc if sc else "\033[90m★ 미선언 — 항상 돈다\033[0m"))
print()
print(f"  선언 {declared} · 미선언 {len(rows) - declared} · 단계 {len(rows)}")
if dangling:
    print()
    print("\033[31m  ✗ 어느 단계에도 안 붙은 선언\033[0m")
    for ln, sc in dangling:
        print(f"      {sys.argv[1]}:{ln}  scope \"{sc}\"")
    print("      붙지 않은 선언은 아무 일도 안 하면서 범위를 적었다고 믿게 만든다.")
    sys.exit(1)
PY
        _rc=$?
    else
        grep -nE '^[[:space:]]*(scope|step) "' "$0" | sed 's/^/  /'
        _rc=0
    fi
    printf '\n  %s미선언은 --since 에서도 항상 돈다. 그것이 안전한 기본값이다.%s\n\n' "$D" "$Z"
    exit $_rc
fi

_touches() {                  # _touches "패턴 ..."  바뀐 것이 하나라도 닿는가
    local f pat rc=1
    # ★ 2026-09-19 실측 버그. 종전에는 `_touches $_scope` 로 **안 따옴표로**
    #   넘겼다. 그러면 셸이 `web/navi/*` 를 **실제 파일 목록으로 펼쳐서**
    #   패턴이 패턴으로 도착하지 않는다 — `web/navi/*` 가 직계 자식만
    #   펼쳐지므로 `web/navi/src/App.tsx` 를 **못 잡았다.**
    #   즉 내비를 고쳤는데 내비 타입 검사가 조용히 건너뛰어진다. 1족이다.
    # ★ `set -f` 로 globbing 을 끄고 IFS 분리만 쓴다. `case` 의 패턴 자리는
    #   경로 확장을 안 하므로 거기서는 따옴표를 안 쓰는 것이 맞다.
    # ★ `case` 의 `*` 는 `/` 도 먹는다. 그래서 `src/*` 가 `src/a/b.py` 를 잡는다.
    set -f
    for f in $CHANGED; do
        for pat in $1; do
            case "$f" in $pat) rc=0; break 2 ;; esac
        done
    done
    set +f
    return $rc
}
TOTAL=$(grep -oE '^[[:space:]]*step "[^"]*"' "$0" | sed 's/.*step //' | sort -u | wc -l)
# ★ 2026-09-19. 같은 사고가 **다른 원인으로 재발했다.** 위 2026-09-15 항은
#   이름 중복을 고쳤는데, 이번에는 `부분 실행` 이 분모에만 있고 실행에는
#   없었다 — `--only` · `--fast` 에서만 도는 안전장치라 전수 실행에서는
#   한 번도 안 돈다. 그래서 전수로 돌려도 끝까지 **[44/45]** 가 찍혔고,
#   보는 사람은 하나가 빠졌다고 읽는다.
# ★ 분모는 **이 실행에서 실제로 돌 수 있는 것**이어야 한다. 조건부 단계를
#   손목록으로 빼지 않고, 그 단계를 켜는 조건과 같은 조건으로 뺀다 —
#   조건이 한 곳에 있으므로 갈리지 않는다.
if [ -z "$ONLY" ] && [ "$FAST" != "1" ] && [ -z "$SINCE" ]; then TOTAL=$((TOTAL - 1)); fi

hms() {                       # 초 → "51초" · "2분41초"
    if [ "$1" -lt 60 ]; then printf '%d초' "$1"
    else printf '%d분%02d초' $(( $1 / 60 )) $(( $1 % 60 )); fi
}

step() {                      # step "이름" "명령..."
    local name="$1"; shift
    local _scope="$SCOPE"; SCOPE=""     # ★ 선언은 이 한 단계에만 걸린다
    IDX=$((IDX+1))
    # ★ --only 로 뺀 것은 `건너뜀` 이다. **통과가 아니다.**
    if [ -n "$ONLY" ] && ! printf '%s' "$name" | grep -qE "$ONLY"; then
        NAMES+=("$name"); RESULTS+=("건너뜀"); NOTES+=("--only 로 뺐다"); SECS+=(0)
        skip=$((skip+1)); return
    fi
    # ★ --since 로 뺀 것도 `건너뜀` 이다. 미선언(`_scope` 가 빈 값)은 안 뺀다.
    if [ -n "$SINCE" ] && [ -n "$_scope" ] && ! _touches "$_scope"; then
        NAMES+=("$name"); RESULTS+=("건너뜀"); SECS+=(0)
        NOTES+=("--since 범위 밖 ($_scope)")
        skip=$((skip+1)); return
    fi
    # ★ `── 이름` 형식은 건드리지 않는다. dms.py 의 봉인 파서가 이 줄로
    #   단계를 가른다. 진행 표시는 아래 별도 줄에 둔다.
    printf '%s── %s%s\n' "$C" "$name" "$Z"
    local t0 tmp out rc pid e
    t0=$(date +%s); tmp=$(mktemp)
    # ★ 2026-09-14. `</dev/null` 이 없어서 `verify.sh | tee` 로 돌리면
    #   자식이 파이프 stdin 을 물려받았다. 큰 zip 을 푸는 단계가 뭔가
    #   읽으려는 순간 죽었고 `ngii_road` · `jijeok` 이 그렇게 FAIL 났다.
    #   단독 실행은 stdin 이 터미널이라 멀쩡했다 — **여기서만 죽었다.**
    #   배치 파이프라인은 대화형 입력을 기대하지 않는다. 막는 것이 맞다.
    "$@" >"$tmp" 2>&1 </dev/null &
    pid=$!
    if [ -t 1 ]; then         # 파이프로 넘길 때는 \r 을 안 쓴다
        while kill -0 "$pid" 2>/dev/null; do
            e=$(( $(date +%s) - t0 ))
            printf '\r%s   [%2d/%2d]  %s%s\033[K' "$D" "$IDX" "$TOTAL" "$(hms $e)" "$Z"
            sleep 1
        done
    fi
    wait "$pid"; rc=$?
    e=$(( $(date +%s) - t0 ))
    printf '\r%s   [%2d/%2d]  %s%s\033[K\n' "$D" "$IDX" "$TOTAL" "$(hms $e)" "$Z"
    out=$(cat "$tmp"); rm -f "$tmp"
    SECS+=("$e")
    if [ $rc -eq 0 ]; then
        printf '%s   OK%s  %s\n' "$G" "$Z" "$(printf '%s' "$out" | tail -1)"
        NAMES+=("$name"); RESULTS+=("OK"); NOTES+=("$(printf '%s' "$out" | tail -1)")
        pass=$((pass+1))
    else
        printf '%s   실패%s\n' "$R" "$Z"
        # ★ 2026-09-14. 전문을 파일로 남긴다. `tail -15` 만 찍다가
        #   `jijeok` 의 진짜 사유를 못 봐서 전량(20분)을 **다섯 번** 돌렸다.
        #   실패한 단계를 다시 돌려야만 사유를 볼 수 있는 보고는
        #   보고가 아니다 — 그것이 이 저장소의 진짜 병목이었다.
        # ★ 한글 이름은 전부 `_` 가 되어 서로 겹친다. 단계 번호를 앞에 붙인다.
        _flog="/tmp/verify-$(printf '%02d' "$IDX")-$(printf '%s' "$name"                | tr -c 'A-Za-z0-9' '_' | cut -c1-24).log"
        printf '%s\n' "$out" > "$_flog"
        printf '%s' "$out" | tail -15 | sed 's/^/     /'
        printf '%s     전문 %s%s\n' "$D" "$_flog" "$Z"
        NAMES+=("$name"); RESULTS+=("실패"); NOTES+=("$(printf '%s' "$out" | tail -1)")
        fail=$((fail+1))
    fi
    echo
}

# ── 생략 두 종 ───────────────────────────────────────────────
# ★ 2026-09-18. `note` 하나로는 이 파일 머리(22~25행)가 스스로 적은 사고를
#   막지 못한다 — "생략은 실패로 안 세므로 verify.sh 는 '전부 통과했다' 고
#   말한다". 실측으로 그대로였다: raw 없는 기계에서 8단계가 `생략` 으로
#   빠지고 최종 판정은 `fail>0` 만 보므로 초록이 뜬다.
#
#   생략에는 두 종류가 있고 둘을 같은 칸에 두면 안 된다.
#
#     note        다른 관문이 덮는다 — CI 가 같은 검사를 돈다(JS 넷).
#                 여기서 빠져도 증거는 다른 데서 나온다. skip 이 맞다.
#     note_hard   덮는 관문이 **없다.** 빠지면 이 실행은 아무것도 증명하지
#                 못한다. 그러면 생략이 아니라 실패다.
#
# ★ 판정 기준은 "중요한가" 가 아니라 **"다른 데서 같은 검사가 도는가"** 다.
#   중요도는 사람마다 다르고 덮개 여부는 실측된다(§가드 3).
note() { NAMES+=("$1"); RESULTS+=("생략"); NOTES+=("$2"); SECS+=(0); skip=$((skip+1))
         printf '%s── %s%s\n%s   생략%s  %s\n\n' "$C" "$1" "$Z" "$Y" "$Z" "$2"; }

note_hard() { NAMES+=("$1"); RESULTS+=("실패"); NOTES+=("생략 — $2"); SECS+=(0); fail=$((fail+1))
              printf '%s── %s%s\n%s   실패%s  생략 — %s\n' "$C" "$1" "$Z" "$R" "$Z" "$2"
              printf '%s     이 단계를 덮는 관문이 없다. 생략하면 이 실행은 판정을 증명하지 않는다.%s\n\n' "$D" "$Z"; }

# ── 증거 수 = 선언 수 (1족 클래스 가드) ──────────────────────
# ★ 2026-09-22 (DECISIONS §218-5). `TOTAL` 은 분모로 **화면에만** 쓰였다. 실제로
#   몇 행이 기록됐는지와 대조하는 자리가 없어서, 갈래 하나가 행을 안 남기면
#   「[38/41] 통과 38」처럼 **빠진 것이 초록 사이에 묻혔다**(위 2026-09-15 · 09-19 항).
#   종전 실측으로 셋이 그랬다 — npm 없는 갈래는 셋 중 하나만, `--fast` · raw 부재
#   갈래는 넷 중 이름도 다른 한 행만 남겼다.
# ★ 행의 종류(OK · 실패 · 생략 · 건너뜀)는 안 가린다. 묻는 것은 「선언된 단계마다
#   **무엇이든** 증거가 한 행 있는가」 하나다. 건너뛴 것이 통과가 아닌 것은 위
#   `부분 실행` 이 따로 든다.
# ★ `step` 으로 부르지 않는다 — 부르면 자기가 분모에 들어가 제 자신을 센다.
#   `tests/test_verify_evidence.py` 가 이 함수를 그대로 떼어 합성 실행으로 시험한다.
evidence_check() {
    local rows=${#NAMES[@]}
    if [ "$rows" -ne "$TOTAL" ]; then
        NAMES+=("증거 수 = 선언 수"); RESULTS+=("실패"); SECS+=(0)
        NOTES+=("기록 ${rows}행 ≠ 선언 ${TOTAL}단계 — 행을 안 남긴 갈래가 있다")
        fail=$((fail+1))
        printf '%s── 증거 수 = 선언 수%s\n%s   실패%s  기록 %d행 ≠ 선언 %d단계\n' \
               "$C" "$Z" "$R" "$Z" "$rows" "$TOTAL"
        printf '%s     건너뛰는 갈래(note · note_hard)도 **단계 이름마다** 한 행을 남겨야 한다.%s\n\n' "$D" "$Z"
    fi
}

echo
printf '%s저장소%s  %s\n' "$D" "$Z" "$ROOT"
# ★ 2026-09-14. HEAD 를 찍는다. `dms.py seal --log` 가 이 줄을 읽어
#   로그가 지금 나무를 말하는지 판정한다. 종전에는 파일 mtime 으로
#   봤는데 **내용이 안 바뀌어도 잡혀서** 30분짜리 재실행을 시켰다.
printf 'HEAD    %s%s\n' \
  "$(git rev-parse --short HEAD 2>/dev/null || echo '(git 밖)')" \
  "$(git status --porcelain 2>/dev/null \
       | grep -v '^.. \(web/data/\|data/processed/\|data/dms/\)' \
       | grep -q . && echo ' +미커밋' || true)"
printf '%s노드  %s  %s\n' "$D" "$Z" "$(node --version 2>/dev/null || echo '없음')"
printf '%suv    %s  %s\n\n' "$D" "$Z" "$(uv --version 2>/dev/null || echo '없음')"

# ── 0. 잠금파일 갱신 ─────────────────────────────────────────
# ★ pyproject 에 [build-system] 이 생겼고 의존성 9개가 extras 로 내려갔다.
#   uv.lock 이 그 전에 만들어진 것이라 다시 풀어야 한다.
# ★ 2026-09-18 (W2). `--frozen` 을 더했다. 종전에는 이 단계가 `uv.lock` 을
#   **갱신할 수 있었다** — 검증 도구가 검증 대상을 변형하는 유일한 자리였고,
#   Dockerfile · 워크플로 전부가 `--frozen` 인데 여기만 아니었다.
#   그것이 "로컬은 초록 · CI 는 빨강" 을 만드는 구조다(5b 와 같은 축).
# ★ extras 는 여전히 안 깐다(CI 는 `--all-extras`). torch 를 로컬에 받게 하는 것이
#   비싸서 남긴 **선언된 차이**이고, gate_parity 가 그 차집합을 센다.
step "의존성 동기화 (uv sync --frozen --dev)" uv sync --frozen --dev

# ── 1. 패키지가 실제로 import 되는가 ─────────────────────────
step "패키지 import" uv run python -c '
import importlib, sys
mods = ["paths","manifest","quiet_gdal","krgis.crs","seg.params","seg.geom","seg.width",
        "seg.roadname","seg.basisno","seg.graph","seg.report","segkey","guards",
        "lineage","ngi","ngii1k","probe","contract","inventory","datalog",
        "normalize_raw","sample_design","ingest","segments","streetlight",
        "terrain","ortho","publish_web","pipeline","shardseal"]
bad = []
for m in mods:
    try: importlib.import_module("firelane." + m)
    except Exception as e: bad.append(f"{m}: {type(e).__name__}: {e}")
if bad:
    print("\n".join(bad)); sys.exit(1)
print(f"import {len(mods)}/{len(mods)}")'

# ── 2. 진입점 · cwd 독립성 ───────────────────────────────────
# ★ 종전 `python src/etl/pipeline.py` 는 cwd 에 의존했다. 이제 안 그런지 본다.
step "진입점 · cwd 독립성" bash -c \
  'cd /tmp && uv run --project "'"$ROOT"'" fire-lane --check >/dev/null && echo "cwd 독립 확인"'

# ── 3. 파이썬 테스트 ─────────────────────────────────────────
# ★ 2026-09-19 (W7-1). `--cov` 를 **여기서** 켠다. 종전에는 이 단계가 맨몸으로
#   돌고 36단계 뒤 「커버리지 래칫」이 **같은 732개를 다시** 돌았다 —
#   실측 1분21초 + 1분46초 = 3분07초로 verify 8분05초의 **38%** 였다.
#   커버리지는 테스트 실행의 **부산물**이지 별도의 실행이 아니다. 여기서
#   한 번 재고 래칫 단계는 그 데이터를 **읽기만** 한다(1초 미만).
# ★ 두 단계를 하나로 **합치지 않는다.** 합치면 「테스트가 깨졌다」와
#   「커버리지가 문턱 아래다」가 같은 빨강 한 줄로 찍혀 사람이 오진한다.
#   실행은 하나, 판정은 둘이다. 단계 수가 유지되므로 문서가 든 단계 번호도
#   안 밀린다.
# ★ `--cov-report=` 는 보고를 끄고 데이터만 남긴다. 화면에 표를 두 번
#   찍지 않기 위해서다 — 표는 래칫 단계가 한 번 낸다.
step "pytest" uv run pytest tests/ -q --cov=src --cov=tools --cov-report=

# ── 4. (삭제) 계층 규칙 ──────────────────────────────────────
# ★ 2026-09-03. `pytest tests/ -q` 가 이미 test_layering 을 돌린다.
#   같은 환경에서 두 번 돌아 표에 줄만 하나 더 찍혔다. 아래 'CI 환경
#   재현' 은 모듈을 가린 **다른 환경**이라 그것은 남긴다.

# ── 5. 린트 ─────────────────────────────────────────────────
# ★ 2026-08-22 에 155 → 0 으로 정리했다. 이제 참고가 아니라 게이트다.
#   되돌아가면 여기서 죽는다. 스타일 규칙 6종은 pyproject 에서 껐고
#   끄는 근거를 각각 적어뒀다.
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope "src/* tools/* tests/* pyproject.toml .ruff-strict.toml"
step "ruff" uv run ruff check src tools tests

# ── 5a. 엄격 린트 — CI 의 contract-strict 와 같은 것 ─────────
# ★ 2026-09-02. 여기가 비어 있었다. 위 5번은 pyproject 기본 규칙만 돌고,
#   CI 의 `contract-strict` 는 `--select B,RUF,PTH,I,UP,DTZ` 를 켠다.
#   그래서 로컬 14/15 초록 · CI 빨간불이 하루에 두 번 났다 —
#   `DTZ011`(시간대 없는 date.today) 이 그중 하나였고 실제 버그였다.
#
# ★ **인자를 여기 복사하지 않는다.** 정본은 `.github/workflows/contract.yml`
#   이고 아래에서 뽑아 쓴다. 복사하면 또 갈린다 — 이 파일 5b 가 적은
#   "로컬 검증이 CI 의 부분집합이면" 과 같은 사고를 인자 층에서 반복하는 것이다.
#
# ★ 대상 파일은 CI 와 같은 도구가 낸다(`owned_paths.py --py-only`).
#   CODEOWNERS 단독 소유 경로만이라, 공동 소유 파일에는 엄격 규칙을 안 건다.
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope "src/* tools/* tests/* pyproject.toml .ruff-strict.toml"
step "엄격 린트 (CI 와 같은 인자)" bash -c '
    # ★ 인자를 여기 적지 않는다. 정본은 .ruff-strict.toml 이고 CI 도 같은
    #   파일을 읽는다. 종전에는 contract.yml 을 grep 으로 긁었는데 주석의
    #   "손대장 110 → 8" 을 규칙 이름으로 물어 죽었다 — 텍스트를 긁는 것
    #   자체가 또 하나의 사본이었다(2026-09-02).
    test -f .ruff-strict.toml || { echo ".ruff-strict.toml 가 없다"; exit 1; }
    FILES=$(uv run python tools/owned_paths.py --py-only)
    [ -n "$FILES" ] || { echo "엄격 검사 대상이 0건이다"; exit 1; }
    echo "대상 $(echo "$FILES" | wc -l)개 · 인자 .ruff-strict.toml"
    uv run ruff check $FILES --config .ruff-strict.toml
'

# ── 5c. 의존성 선언 ↔ import (4족 클래스 가드) ──────────────
# ★ 2026-09-22 (DECISIONS §218-5). 선언은 있는데 아무도 import 안 하는 것 · import 는
#   하는데 선언이 없는 것 · 전이 의존성에 기대는 것을 **두 방향으로** 센다. 종전 강제자
#   (`test_etl_imports_are_declared`)는 src/firelane 의 누락 한 방향만 봤다.
# ★ 잠금에 안 넣는다 — `--with` 로 이 자리에서만 얹고 `--no-sync` 로 환경을 안 건드린다.
#   uv.lock 이 움직이면 샤드 봉인 · golden 지문이 찢어진다. 설정 · 알려진 예외는
#   pyproject.toml 의 `[tool.deptry]` 한 곳이다. 판은 contract.yml 과 같아야 한다
#   (`tests/test_deptry_config.py`).
scope "pyproject.toml src/* tools/*"
step "의존성 선언↔import (deptry)" uv run --no-sync --with deptry==0.25.1 deptry src tools


# ── 5b. 저장소 위생 — CI 와 같은 것을 본다 ───────────────────
# ★ 2026-08-23. 여기가 CI 검사 다섯을 안 돌고 있었다. README 는 "받자마자
#   이것 하나면 된다" 고 하는데, verify.sh 초록불이어도 CI 는 빨간불이 될 수
#   있었다 — 커밋 정책 · 인코딩 · web/data 계보 · 문서 숫자 · 용량 상한.
#   로컬 검증이 CI 의 부분집합이면 "내 기계에서는 됐는데" 가 나온다.
# ★ 2026-09-18 (W2) 삭제 — 「CI 환경 재현」. **존재하지 않는 CI 를 검사했다.**
#   전제는 "CI 가 `pip install pytest shapely numpy ruff pyyaml` + `--no-deps`
#   로만 깐다" 였고, 그래서 pandas · geopandas · pyogrio · pyproj · rasterio ·
#   PIL · ruamel 일곱을 일부러 가리고 돌렸다. 실측 —
#     · CI 는 `uv sync --frozen --all-extras` 를 쓴다. `pip install` 은 워크플로에
#       0건이고 `tests/test_ci_env.py` 가 그것을 금지한다
#     · 가려진 일곱은 전부 `pyproject.toml` 의 **코어 의존성**이라 CI 에 다 있다
#   통과해도 CI 정합을 보증하지 않고 실패하면 오탐이다. 허구를 지키는 검사는
#   없는 것보다 나쁘다 — 검사가 있다는 사실이 정합을 검증한 것처럼 보이게 한다.
#   정합을 **실제로** 묻는 것은 `gate_parity.py` 다(아래 「관문 동등」).

# ★ 2026-09-20 (W3-15). 워크플로는 **머지되기 전에는 문법조차 안 본다** —
#   배포 넷은 push+paths 로만 돌아 PR 에서 안 보이고, `_deploy.yml` 이 하루
#   동안 깨진 채로 main 까지 갔다(DECISIONS §196). actionlint 는 YAML 파싱
#   너머의 것을 본다 — 표현식 · 액션 참조 · 셸 인젝션.
#   커밋된 잠금으로 깔리므로 CI 에서도 같은 판이 돈다(면제 아님).
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope ".github/* pyproject.toml uv.lock"
step "워크플로 린트"    uv run actionlint
step "커밋 정책"        uv run python tools/commit_policy.py --tracked
step "인코딩·개행"      uv run python tools/encoding_check.py
# ★ 2026-09-18 (W1). 로컬 훅과 CI 가 이 한 파일을 읽는다 — 정본이 하나다.
#   `.ruff-strict.toml` 과 같은 모양이고, 그것이 5a 의 교훈이다.
# ★ 위 `인코딩·개행` 을 안 지운다. 표준 훅은 BOM · CRLF 만 도맡았고
#   나머지 둘(비UTF-8 · 끝개행)은 대입물이 없다. `end-of-file-fixer` 는 더
#   엄걱해서 추적 파일 15개를 고치고, 그중 `web/workflow.html` 은 생성기와
#   무한 왔부에 들어간다(.pre-commit-config.yaml 의 ★★).
step "pre-commit 전수"  uv run pre-commit run --all-files
# ★ 2026-09-18 (W1). 전역 훅이 이 저장소를 이어서 부르는가.
#   `.pre-commit-config.yaml` 이 있어도 전역 훅이 그것을 안 부르면
#   **커밋 시점 방어가 0 이다** — 종전 `.githooks/pre-commit` 이 정확하게
#   그 상태여서 구조적으로 못 도는 코드였다.
#   ★ 2026-09-19 정정. 종전 이 줄은 「미설정이면 한 명령으로 끝난다 —
#     `global-chain.sh --install`」이라고 적었다. **그 모드는 없다.**
#     `global-chain.sh:41` 은 `--check` 와 `--uninstall` 둘뿐이고 `:80` 의
#     `--check|*)` 가 catch-all 이라 `--install` 은 **오류 없이 --check 로
#     떨어졌다.** 안내가 거짓인데 아무것도 안 울었다 — 도구가 모르는 인자를
#     조용히 삼키면 틀린 안내가 영원히 산다.
#     ★ 2026-09-20 (W3-19) 닫았다 — 이제 모르는 인자는 쓰는 법을 찍고
#       **exit 2** 다. 인자 검증이 환경 검사보다 먼저라 훅이 없는 기계에서도
#       「모르는 인자」와 「훅 미설정」이 안 겹친다.
#     전역 훅은 저장소 밖 파일이라 이 저장소가 설치할 수 없다. 실제 절차는
#     `global-chain.sh --check` 가 미설정일 때 직접 찍는다(`:44-51`).
# ci-exempt: .githooks/global-chain.sh 전역 훅(~/.githooks)은 기계 설정이다. CI 러너에는 없다
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope ".githooks/*"
step "훅 전역 연결"    bash .githooks/global-chain.sh --check
# ★ 2026-09-18 (W2). 3족의 클래스 가드. 로컬에만 있는 검사기를 센다.
#   CI 도 같은 명령을 돈다 — 규칙을 두 곳에 적는 것이 아니라 같은 도구가
#   같은 나무를 읽으므로 정본은 코드 하나다.
# ★ 2026-09-20 (W3-10 · W3-11). **면제 칸이 생겼고 숫자가 한 곳으로 갔다.**
#   종전에는 ① 래칫이 「로컬 전용 수」만 세서 레이크를 요구해 CI 에서 원리적으로
#   못 도는 검사까지 옮기라고 압박했고(2026-09-18 에 `refcheck` 를 넣었다 되돌렸다),
#   ② `--max 19` 가 여기와 `contract.yml` 둘에 손으로 적혀 있어 한쪽만 고쳐
#   **로컬 초록 · CI 빨강**이 났다.
#   ★ 2026-09-22 (DECISIONS §218-5). 미선언 11 중 열을 CI 로 옮기고 dms.py 하나를 면제로
#     선언해 래칫이 11 → 0 이 됐다. 면제 선언은 열이다.
#   이제 면제는 `# ci-exempt:` 선언들이 들고, 숫자는 `gate_parity.py` 의
#   `RATCHET` 한 곳에만 산다. **부르는 쪽은 인자를 안 적는다.**
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope "tools/* .github/* tests/* .pre-commit-config.yaml"
step "관문 동등"  uv run python tools/gate_parity.py
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope "src/* tools/* .env.example"
step "환경변수 선언↔실물" uv run python tools/env_check.py
step "문서 숫자 대조"   uv run python tools/docnum_check.py
# ★ 2026-09-03 배선. 여덟 중 다섯만 tests/test_doc_fsck.py 가 걸고 있었고
#   ⑥ 기획서 수정일 · ⑦ 셸 명령 · ⑧ 기한은 **사람이 손으로 칠 때만**
#   돌았다. 그 사람이 나가면 아무도 안 친다.
step "문서 ↔ 문서"     uv run python tools/doc_fsck.py
# ★ 2026-09-02 배선. 오늘 캡션 절까지 붙여놓고 **어디서도 안 부르고
#   있었다.** 사람이 손으로 칠 때만 도는 도구는 이탈 후 아무도 안 부른다.
# ★ 2026-09-22 — ⑤⑥ 이 golden · 발행 구간 · 대장을 읽는다(W4-2). 범위를 좁게 두면 조용히 건너뛴다
scope "docs/* tools/* data/* web/* src/* tests/* .github/* sources.yaml"
step "기획서 대조"     uv run python tools/docx_check.py
# ★ 캡션만 보던 것을 그림 자체로 넓혔다. 값이 바뀌면 그림이 낡는다.
scope "docs/* tools/* src/* data/*"
step "그림 ↔ 정본"     uv run python tools/render_figures.py --check
# ★ 2026-09-17 (DECISIONS §180-9). `흡수 대상`(release_brief 한 줄)을 뺐다. 검사가 아니라 보고였고 매 실행 "생략" 으로
#   찍혀 생략 칸을 채웠다 — 진짜 생략(npm 없음 · --fast)이 그 옆에 묻힌다. 표는 릴리즈 PR 본문에서 쓰인다(merge_batch --release).
# ★ 2026-09-17 (DECISIONS §182-2 · G-14). 대장 필드 검사를 아무도 안 불렀다. `python -m firelane.ledger` 는
#   FAIL 9 로 종료코드 1 을 내고 있었는데 verify · 테스트 · CI 어디에도 없어서 초록이었다.
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope "sources.yaml src/* tools/*"
step "대장 필드 검사"   uv run python -m firelane.ledger
# ★ 선언이 가리키는 것이 실재하는가. 같은 이유로 안 걸려 있었다.
# ci-exempt: tools/refcheck.py 대장 file/files 를 raw 실물과 대조한다. CI 에 레이크가 없다(DECISIONS §191-4)
step "선언 ↔ 실물"     uv run python tools/refcheck.py
# ★ 전수 스캔. `--repo` 는 데이터 레이크 없이 저장소 트리만 본다 —
#   항목에서 출발하는 검사는 **항목이 없는 것을 영원히 못 본다.**
step "트리 전수 대조"   uv run python tools/treecheck.py --repo
scope "web/* data/*"
step "web/data 계보"    uv run python tools/web_manifest.py --check
# ★ 2026-09-20 (PLAN §1 #62). 출동 대상지는 동명동 하나다. 이 단계가 생기기
#   전까지 「스코프가 얼마나 벗어났나」를 **세는 검사가 하나도 없었다** —
#   `tests/test_station_scope.py` 는 「안전센터를 덮는가」만 보고 넓을수록
#   통과한다. 방향이 반대인 검사만 있었다.
#   커밋된 발행물의 속성만 읽으므로 CI 에서도 돈다(면제 아님).
scope "web/data/* tools/*"
step "스코프 벗어남"    uv run python tools/scopecheck.py
# ci-exempt: tools/tidy.py 로컬 작업 트리의 찌꺼기를 센다. CI 는 매번 새 트리라 물음이 성립하지 않는다
step "로컬 찌꺼기"      uv run python tools/tidy.py
scope "web/data/* tools/*"
step "web/data 용량"    bash -c '
    SIZE=$(du -sm web/data | cut -f1)
    LIM=$(grep -oP "MAX_WEBDATA_MB\s*=\s*\K\d+" tools/commit_policy.py)
    echo "web/data ${SIZE}MB / 상한 ${LIM}MB"
    [ "$SIZE" -lt "$LIM" ]'

# ── 6·7. (철거) JS 모듈 그래프 · JS 부팅 ─────────────────────
# ★ 2026-09-22. 옛 GIS 지도(web/js 30모듈 · index.html 패널)를 걷어냈다 — 관제 화면
#   (web/navi ?view=ops)이 넘겨받았다. 「JS 문법·순환·import」(js_graph_check.mjs) ·
#   「JS 부팅 스모크」(web_boot_check.mjs · jsdom)는 그 지도만 봤으므로 도구째 지웠다.
#   영향 범위 선언 둘이 함께 빠져 tests/test_verify_scope.py 의 SCOPE_FLOOR 를 내렸다.
#   화면 검사는 아래 7b(내비 타입 · 단위 시험)가 든다.

# ── 7b. 내비 타입 검사 (web/navi) ────────────────────────────
# ★ 2026-09-15 신설. (철거된) 6·7 은 `web/js` 옛 지도만 봤다. 내비는
#   React/TS 라 그 셋에 안 걸렸고, 컴파일하는 곳은 배포 액션 하나뿐이었다.
#   그래서 maplibre-gl 6 이 로컬 39단계 전부 초록인 채로 main 까지 갔다.
#   **여기가 비어 있어서 로컬이 CI 의 부분집합도 아니었다**(5b 와 같은 사고).
# ★ 타입만 본다. `vite build` 는 토큰이 필요하고, 이번 사고는 타입에서
#   잡혔다. 토큰 없는 빌드는 배포 액션이 맡는다.
# ★ 2026-09-22 (DECISIONS §213-1). CI 가 `Cannot find namespace 'GeoJSON'` 으로
#   죽었는데 여기는 초록이었다. 여기는 **있던 node_modules** 로 검사했고 CI 는
#   잠금대로 새로 깐다 — 설치물이 잠금과 어긋나도 몰랐다. 노드 판도 달랐다
#   (CI 20 · 로컬 22). 그래서 타입 검사 **앞에** 환경부터 CI 와 맞춘다:
#   잠금 지문이 바뀌었으면 npm ci, 로컬 노드 = .nvmrc, 잠금 engines 전부 만족.
#   종전의 「node_modules 가 있으면 그대로 · 없으면 npm ci」 두 갈래는 그 첫
#   갈래가 구멍이었다.
if command -v npm >/dev/null 2>&1; then
    scope "web/navi/*"
    step "내비 환경 = CI" uv run python tools/navi_env.py
    scope "web/navi/*"
    step "내비 타입 검사" bash -c 'cd web/navi && npm run -s typecheck'
    # ★ 2026-09-22 (§213-3). 위치 추정 · 턴바이턴은 화면으로 검수가 안 된다 —
    #   시뮬레이션이 경로 자체를 따라 걸어서 폐루프가 한 번도 안 돌았다.
    scope "web/navi/*"
    step "내비 단위 시험" bash -c 'cd web/navi && npm run -s test'
else
    # ★ 2026-09-22 (DECISIONS §218-5). 종전에는 셋 중 「내비 타입 검사」 한 행만 남겼다.
    #   갈래가 건너뛰는 단계는 **이름마다** 한 행이다 — 아래 `evidence_check` 가 센다.
    note "내비 환경 = CI" "npm 이 없다"
    note "내비 타입 검사" "npm 이 없다"
    note "내비 단위 시험" "npm 이 없다"
fi

# ── 8. 파이프라인 전량 + 판정 불변 ───────────────────────────
# ★ 여기가 진짜 검증이다. 위의 전부가 통과해도 판정이 바뀌면 실패다.
if [ "$FAST" = "1" ]; then
    # ★ `--fast` 는 `note` 로 둔다. 아래 `부분 실행` 단계가 `--fast` 를 이미
    #   **실패로** 잡으므로(405~418행) 여기서 또 올리면 같은 사실을 두 번 센다.
    # ★ 2026-09-22 (DECISIONS §218-5). 종전에는 「파이프라인 전량 + golden」 **한 행**이었다 —
    #   아래 갈래의 단계 넷 중 어느 이름과도 안 맞아 분모와 기록이 셋 어긋났다.
    #   건너뛰는 단계마다 제 이름으로 한 행이다(`evidence_check`).
    #   이름을 루프 변수로 감추지 않는다 — 시험이 리터럴로 읽어 단계 이름과 대조한다.
    _why="--fast 로 생략. 반드시 따로 돌릴 것"
    note "파이프라인 전량" "$_why"
    note "golden 판정 불변" "$_why"
    note "golden 게이트 해제 경로" "$_why"
    note "커밋된 web/data 가 최신인가" "$_why"
elif [ -z "${FIRE_LANE_DATA:-}${FIRE_LANE_RAW:-}" ] && [ ! -d data/raw/gjcity ]; then
    # ★ 2026-09-18. 여기가 `note` 였다. 그래서 레이크 없는 기계에서
    #   **이 저장소의 유일한 판정 검증이 빠진 채 「전부 통과했다」가 찍혔다.**
    #   `--only` · `--fast` 는 `부분 실행` 이 잡는데 raw 부재는 아무도 안 잡았다.
    #   CI 도 이 단계를 안 돈다(실측: verify 42단계 중 CI 10단계) — 덮개가 없다.
    # ★ 2026-09-22 (DECISIONS §218-5). 한 행이던 것을 단계 이름마다 한 행으로 편다.
    #   덮개 여부로 가른다(위 「생략 두 종」) — golden 둘은 이제 CI 가 **커밋본으로**
    #   돈다(contract.yml 「golden 판정 불변」). 파이프라인과 freshcheck 는 덮개가 없다.
    _why="raw 가 없다. FIRE_LANE_DATA 를 설정하고 다시 돌려라 (paths.require_lake)"
    note_hard "파이프라인 전량" "$_why"
    note "golden 판정 불변" "파이프라인이 안 돌아 새 산출이 없다. 커밋본 대조는 CI 가 돈다"
    note "golden 게이트 해제 경로" "파이프라인이 안 돌았다. 같은 selftest 를 CI 가 돈다"
    note_hard "커밋된 web/data 가 최신인가" "$_why"
else
    # ★ --no-test. 계약 테스트는 위 pytest 가 이미 돌렸다. 파이프라인이
    #   끝에서 또 부르면 한 번의 verify 에 test_contract 가 세 번 돈다.
    # ★ **raw 와 코드가 봉인과 같으면 판정도 같다.** 전량 4분30초를
    #   근거 있게 생략한다. raw 만 보던 때는 코드만 바꾼 배치가 옛 산출물로
    #   초록을 냈다(DECISIONS §164). 종전 서술 —
    #   근거 있게 생략한다. 지금 `--fast` 는 근거 없이 전부/전무로
    #   건너뛰고 그 로그로 봉인하면 반쪽 증표다 — 이쪽은 입력이 같다는
    #   증거가 있다.
    #
    # ★ `note` 를 쓰지 않는다. `note` 는 `생략` 으로 찍히고 `seal` 이
    #   그것을 닫힘으로 읽는다(PLAN #70). 여기는 건너뛴 것이 아니라
    #   **대조를 통과한 것**이므로 한 단계로 묶어 초록을 낸다.
    #   무엇을 근거로 생략했는지는 아래 echo 가 로그에 남긴다.
    #
    # ★ 모르면 안 건너뛴다. 봉인이 없거나 지문을 못 재면 `rawdiff` 가
    #   1 을 내고 전량이 돈다. 의심스러울 때 생략하는 것은 검사를
    #   끄는 것과 같다.
    scope "$CODE_SCOPE"
    step "파이프라인 전량" bash -c '
        if uv run python tools/dms.py rawdiff; then
            echo "★ raw 와 파이프라인 코드가 봉인과 같아 전량을 생략했다 (DECISIONS §164)."
        else
            uv run fire-lane --no-test --split
        fi'
    scope "$CODE_SCOPE"
    step "golden 판정 불변" uv run python tools/golden.py check
    # ★ 게이트가 울고 또 풀리는가. check 가 통과하는 것만으로는
    #   해제 경로가 있는지 알 수 없다(DECISIONS §69).
    scope "$CODE_SCOPE"
    step "golden 게이트 해제 경로" uv run python tools/golden.py selftest
    # ★ 생산자를 돌린 직후에만 알 수 있다. 커밋된 web/data 가 낡아도
    #   web_manifest 는 **있는 것의 해시**를 뜰 뿐이고 golden 은
    #   segments.geojson 만 본다. 2026-09-02 에 route_vehicle.json 이
    #   08-31 산출인 채로 전 게이트를 통과했다(PLAN #70 · DECISIONS §39).
    # ★ 2026-09-19. 범위가 `data/processed/segments.geojson` **한 파일**이었다.
    #   같은 디렉터리의 `_manifest.json`(계보 정본)과 **`seg_uid_map.csv`**
    #   (구간 uid 사상표)는 추적되는 생성물인데 **아무도 안 봤다.** 그날
    #   매니페스트가 걸린 것은 그 해시가 web/data/_manifest.json 안에 박혀
    #   있어서 **간접적으로, 우연히** 드러난 것이다. `dms.py` 의
    #   `SEAL_MAY_BE_DIRTY` 는 그 파일을 이미 알고 있었다 — 같은 사실이
    #   저장소에 있는데 이 자리가 손으로 다시 적으며 틀렸다(DECISIONS §192).
    #   디렉터리로 넓힌다. 추적되는 것은 넷이고 전부 결정적이다
    #   (`_manifest.json` 은 `write_stable` 이 시각만 바뀌면 안 쓴다).
    #   ★ 단계 이름은 안 고쳤다 — DECISIONS §179 가 이 이름을
    #     인용한다. W3-13(2026-09-22 닫힘)은 목록만 등록부로 옮겼고 이름은 그대로 둔다.
    #   ★ 2026-09-20 (W4-10). 종전에는 여기서 `git diff --quiet` 한 줄이
    #     돌았고 **파일 이름까지만** 말했다. 그날 두 매니페스트가 48줄씩
    #     움직였는데 그중 45자리가 `datasets.*.seal.code` 였다 — 그 배치가
    #     `src/firelane/prep.py` 를 고쳤으니 **움직이는 것이 옳다.** 그런데
    #     화면에서는 판정값이 드리프트한 경우와 구분이 안 됐고, 안내문은
    #     「생성물이므로 그대로 커밋하면 된다」라 사람에게 도장 찍는 법을
    #     가르쳤다. 2026-09-19 의 재커밋에는 봉인 `cfg` 가 실제로 바뀐 것이
    #     섞여 있었고 48줄 사이에 묻혔다.
    #   ★ **경계는 안 바꿨다.** 시각만 움직인 경우는 `manifest.write_stable`
    #     이 이미 안 쓴다(그것을 「구조적 빨강」으로 잘못 읽은 등재를
    #     정정했다 — DECISIONS §200). 바뀐 것은 빨강일 때 사람이 보는 것이다.
    # ci-exempt: tools/freshcheck.py 파이프라인 재실행 산출과 커밋본을 견준다. CI 는 파이프라인을 안 돈다
    scope "$CODE_SCOPE"
    step "커밋된 web/data 가 최신인가" uv run python tools/freshcheck.py
fi

# ── 데이터 레이크 정합 ──────────────────────────────────────────
# ★ 선언과 실물이 갈리는 것을 fsck 가 다 보지 못했다 — 제공기관 state ·
#   격리 잔재 · landing 우회 · ext 어휘 · norm 계보 다섯 축이 밖에 있었다.
#   lakecheck 이 그 축을 든다. FIRE_LANE_INBOX 를 기본 스캔 대상으로 쓴다.
# ci-exempt: tools/lakecheck.py 레이크(2.5GB 외장)를 직접 훑는다. CI 에 없다
scope "$CODE_SCOPE"
step "레이크 선언↔실물" uv run python tools/lakecheck.py

# ★ 스캔만 한다. 지우려면 --sweep --yes 를 사람이 친다.
#   "정리는 사람이 한다" 를 도구가 대신하되 삭제는 명시적으로.
# ci-exempt: tools/sweep.py 레이크와 INBOX 를 훑는다. 둘 다 CI 에 없다
scope "$CODE_SCOPE"
step "레이크 정리 대상" uv run python tools/sweep.py

# ★ 2026-09-17 (DECISIONS §176). 레이크 해석기의 관문 — 두주인 · 주인없음 · 선언밖 · 폐지층 0.
#   봉인 조건이다. lakecheck 가 축별로 보고, 이것은 파일마다 주인이 하나인지를 본다.
# ci-exempt: firelane.lake 레이크 해석기의 관문이다. 레이크가 없으면 물음이 성립하지 않는다
scope "$CODE_SCOPE"
step "레이크 관문" uv run python -m firelane.lake gate

# ★ 검사가 죽었는지를 검사한다. 프로브 다섯이 정적으로 센다 —
#   빈 그물 · 손목록 · 조용한 통과 · 죽은 게이트 · 좁은 범위.
#
# ★ 2026-09-20 (DECISIONS §202). **`--selftest` 였다.** 그것이 묻는 것은
#   「프로브가 한 건이라도 내는가」고, 그래서 **결함이 쌓일수록 더 확실히
#   초록**이었다. 단계 이름은 「검사가 죽었는가」인데 실제로는 프로브의
#   생사만 봤다 — 이름이 약속한 범위가 실제보다 넓고 그것이 선언돼
#   있지 않았다(W3-8 · W4-8 과 같은 족의 여섯 번째, 그리고 제일 위쪽).
#   그 사이 148건이 REDLIST.json 에 조용히 앉아 있었고 그중 하나가
#   `golden.py:151 WATCH` — **W3-8 로 따로 등재해 사람이 다시 발견했다.**
#   `--ratchet` 은 프로브별 수를 `CEILING` 과 대조하고 양성 대조도 함께 든다.
step "검사가 죽었는가" uv run python tools/deadcheck.py --ratchet

# ── 소급 · 사본 (B5 ⓪ · 원칙 ⑥) ────────────────────────────────
# ★ `delta` 는 봉인 뒤 바뀐 절만 센다. 전수는 `seal` 이 한 번 돈다.
#   기준선이 없으면 전수가 곧 분모라고 스스로 말한다.
# ★ 2026-09-22 (DECISIONS §218-5). 관문 동등의 미선언 11 을 정리하며 dms.py 는 면제로 선언했다.
#   `delta` 는 봉인 커밋과의 차이를, `ancestry` 는 봉인 커밋이 조상인가를 **git 역사로** 잰다.
# ci-exempt: tools/dms.py 봉인 커밋과의 증분·조상을 git 역사로 잰다. CI 클론은 얕다(fetch-depth 1)
step "강제자 소급 증분" uv run python tools/dms.py delta
# ★ 2026-09-21 (PLAN §13 W11-1 · DECISIONS §210). **봉인이 가리키는 커밋이 이 트리의 조상인가.**
#   `delta` 는 봉인 **뒤**를 센다. 그런데 봉인이 없는 커밋을 가리키면 `delta` 는
#   「전수 재검사다」만 찍고 rc=0 을 낸다(자기참조를 피하려고 일부러). 그래서
#   2026-09-18~09-21 에 봉인이 `2130b14`(스쿼시로 사라진 커밋)를 가리키는 동안
#   이 단계가 세 번 연속 초록이었고, 그 틈으로 §202~§208 의 blank 39 가 들어왔다.
#   **`delta` 의 전제를 이 단계가 든다** — 전제가 무너지면 여기서 운다.
# ★ 로컬 전용이다. CI 클론은 얕아(`fetch-depth: 1`) 조상을 잴 역사가 없다.
#   `tools/dms.py` 는 이미 미선언 로컬 전용 목록에 있으므로 관문 동등 래칫은 안 움직인다.
#   ★ 2026-09-22 (DECISIONS §218-5). 이제 미선언이 아니라 위 `# ci-exempt:` 가 사유와 함께 든다.
step "봉인 조상" uv run python tools/dms.py ancestry

# ★ 2026-09-19 정정 — 실측 **5군**이다(`--min 25` · 함수 13). 종전 이 줄은
#   「25 로 내리면 10군」이라고 적었는데 그 값은 낡았다. `SEAL.json` 의
#   `dup_groups: 5` 가 이미 옳은 값을 들고 있었다 — 같은 사실이 저장소에
#   있는데 주석이 손으로 다시 적으며 틀렸다(DECISIONS §192 와 같은 형태).
# ★ 문턱 40 에서 시작한다. 검사를 무르게 만드는
#   것이 아니라 **지금 값에서 시작해 내리는 것**이 일이다(env_check 선례).
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope "src/* tools/* tests/*"
step "사본군" uv run python tools/dupcheck.py --min 40 --max 1

# ★ 2026-09-22 (DECISIONS §218-5 · 하토르 check_file_size.py 모범). 파일 길이 **양방향** 래칫.
#   상한(코드 600 · 시험 700)을 넘는 것은 `EXCEPTIONS` 에 오늘 줄 수로 박혀 있고, 늘면
#   실패 · 줄면 「예외를 내려라」로 실패 · 없어지면 「예외를 지워라」로 실패다.
scope "src/* tools/* tests/*"
step "파일 길이 래칫" uv run python tools/sizecheck.py

# ★ 파일명의 날짜가 자료 기준일인가 내려받은 날인가. `naming` 규약은
#   "다운로드일이 아니다" 라고 적었는데 `_plausible_date` 는 형식만 본다 —
#   규약은 있고 강제자가 그 규약을 안 지켰다(원칙 ①·②). 대가가
#   `its_nodelink` 258MB 두 벌이었다.
# ★ 대장 글롭으로 보면 안 보인다. `files:` 가 한 벌을 못박아놔서 두 번째
#   벌은 대장 밖이다. 이 도구는 **레이크를 직접 훑는다.**
# ci-exempt: tools/vintage_check.py 레이크를 직접 훑어 파일명 날짜를 본다. 대장 글롭으로는 안 보인다
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope "sources.yaml src/* tools/* data/*"
step "vintage 정합" uv run python tools/vintage_check.py --max 0

# ★ norm 이 지금의 raw 에서 나온 것인가. **재현성 게이트다.**
#   2026-09-14 까지 이 축은 verify.sh 밖에 있었다 — 손상이 늘어도 우는
#   곳이 없었다. `--check` 를 고쳐 미등록까지 세게 만들어놓고 배선을
#   안 했다. **세는 것과 거는 것은 다른 일이다.**
# ★ 상한 래칫이다. 0 을 요구하면 영영 빨갛고, 빨간 게이트는 안 읽힌다.
# ci-exempt: firelane.prep RAW 와 NORM 을 대조하는 재현성 게이트다. 둘 다 CI 에 없다
scope "$CODE_SCOPE"
step "norm 계보 재현" uv run python -m firelane.prep --check --max 0


# ── 배치가 세운 상태가 유지되는가 (B1/W4) ───────────────────────
# ★ 적용 뒤 no-op 이 되는 배치 도구를 EXEMPT 로 재우면, 상태가 되돌아가도
#   우는 곳이 없어진다. 지우는 대신 `--check` 를 달아 강제자로 승격했다.
#   넷은 각자 다른 것을 본다 — 공통 껍데기를 씌우지 않았다.
# ★ 2026-09-22 (DECISIONS §217-5 · 옛 PLAN W7-3) 영향 범위 — 과하게 넓게
scope "sources.yaml src/* tools/* data/*"
step "대장 별칭 이관 유지" uv run python tools/ledger_fields.py --check
# ★ 2026-09-15 배선. 종전에는 `test_declaration_sync` 의 실패 메시지 안에
#   안내문으로만 있었다 — 결번이 생겨야 울고, 그 전에 참조가 썩는 것은
#   아무도 안 봤다. 이 도구는 인자 없이 돌면 검사다.
# ★ 이 도구의 REF 정규식이 `\\d` 로 적혀 있어 **만든 날부터 참조를 0건
#   찾았다.** 죽은 참조 안전장치도 참조 치환도 둘 다 안 돌았다. 고치고
#   나니 그 자리에서 죽은 참조 셋이 나왔다(DECISIONS §159).
scope "docs/* tools/*"
step "PLAN 번호·참조 정합" uv run python tools/plan_renumber.py
# ★ 2026-09-15 신설. 커버리지 래칫.
# ★ 2026-09-19 (W7-1). **테스트를 다시 돌리지 않는다.** 종전 이 줄은
#   `pytest tests/ -q --cov ...` 로 4단계와 같은 732개를 통째로 재실행했다.
#   지금은 4단계가 `--cov` 로 남긴 `.coverage` 를 읽기만 한다.
# ★ **이 검사는 자기 전제를 스스로 선언한다**(§3-2 규약). 전제는 「4단계가
#   돌아 `.coverage` 를 남겼다」이고, 그 전제가 안 서면 **조용히 통과하지
#   않는다.** 커버리지는 실행의 부산물이라 단독으로는 못 잰다 —
#   여기서 `note` 로 빠지면 `seal` 이 그것을 닫힘으로 읽는다(PLAN #70).
#
# ★ 2026-09-20 (W4-9). **래칫에는 두 종류가 있고 행동이 달라야 한다.**
#
#     이산  gate_parity(검사기 수) · dupcheck(사본군) · vintage(건수)
#           · firelane.prep(낡음+손상).  세는 것이 **선언된 개수**라
#           같음이 의미를 갖는다 → **양방향 실패.** 미달이면 조여라.
#     연속  커버리지(%).  실측이 어느 테스트가 도는가에 따라 움직이는
#           **부동소수**라 같음을 요구하면 오차로 빨개진다 → 미달은
#           실패, 초과는 **소리내어 경고**.
#
#   셋을 억지로 같게 만들지 않는다 — 다른 것을 같게 만들면 그 검사가
#   무뎌진다. 대신 **어느 쪽인지 선언한다.** 이 단계는 연속 쪽이다.
# ★ 2026-09-19 실측 — **래칫이 14 인데 실물이 24% 였다.** 9/15 에 14 로 걸고
#   나흘 동안 아무도 몰랐다. 왜 몰랐나 — `--fail-under` 는 **미달만** 보고
#   초과를 **말하지 않는다.** `dupcheck --max` 는 미달일 때 「조여라」를
#   찍는데 이쪽은 안 찍었다. 그래서 같은 어휘를 쓰면서 행동이 달랐다
#   (PLAN §13 W4-9 가 예고한 그 족의 네 번째 인스턴스이고, 이것이 그 실측
#   증거다). 아래에서 초과를 **소리내어 말하게** 했다.
#
# ★ 숫자는 `COV_MIN` **한 곳**에만 산다. 단계 이름에서도 뺐다 — 종전 이름이
#   「커버리지 래칫 14%」라 숫자의 집이 하나 더 있었고, 이름은 검사 대상이
#   아니라 조용히 낡는다. `tests/test_verify_citations.py` 가 집이 하나인지와
#   문서가 그 값을 따르는지를 본다.
# ★ 2026-09-20 정정. 종전 이 자리는 「23 은 실측 24% 아래 한 칸」이라 적었고
#   아래 메시지는 「COV_MIN 을 24 로 조여라」라고 말했다. **메시지가 틀렸다** —
#   `coverage report --format=total` 은 **반올림**이라 실측 23.75% 가 `24` 로
#   보인다. 그 말을 듣고 24 로 조이면 `--fail-under=24` 가 23.75 를 떨어뜨려
#   **다음 실행이 빨개진다.** 주석은 반올림을 알고 있었는데 메시지가 몰랐다 —
#   아는 것이 강제되는 자리에 없으면 없는 것과 같다(MASTER §17).
#   이제 `--precision=2` 로 받아 **내림**한 값만 권한다. 실측 23.75 → 권고 23.
# ★ 올린 뒤에는 안 내린다.
# ★ 2026-09-20 — **래칫이 시켜서 올린다.** 배치 W10 이 시험 16개를 더해 실측이
#   23.75% → **24.28%** 가 됐고, 그 실행의 권고가 「COV_MIN 을 24 로 조여라」였다.
#   내림값이라 안전하다. 래칫은 조이라고 말한 다음 배치에서 조인다 — 미루면
#   권고 줄이 매번 뜨고, 매번 뜨는 줄은 곧 안 읽히는 줄이 된다.
COV_MIN=26
step "커버리지 래칫" bash -c '
    if [ ! -f .coverage ]; then
        echo "★ .coverage 가 없다 — 4단계 pytest 가 안 돌았다(--only 로 뺐는가)."
        echo "  커버리지는 테스트 실행의 부산물이라 단독으로 잴 수 없다."
        exit 1
    fi
    MIN='"$COV_MIN"'
    uv run coverage report --fail-under="$MIN" | tail -1
    rc=${PIPESTATUS[0]}
    [ "$rc" -eq 0 ] || exit "$rc"
    # ★ 반올림한 값으로 권하지 않는다. --precision=2 로 받아 **내림**한다.
    PCT=$(uv run coverage report --format=total --precision=2 2>/dev/null || echo "")
    FLOOR=${PCT%%.*}
    case "$FLOOR" in
        ""|*[!0-9]*) exit 0 ;;          # 못 재면 아무 말도 안 한다
    esac
    if [ "$FLOOR" -gt "$MIN" ]; then
        echo "★ 실측 ${PCT}% · 래칫 ${MIN}% — COV_MIN 을 ${FLOOR} 로 조여라. 안 조이면 되돌아간다."
    else
        echo "실측 ${PCT}% · 래칫 ${MIN}% — 내림하면 같다. 조일 것이 없다."
    fi'
scope "web/* .github/* tools/*"
step "내비 소스 목록"      uv run python tools/install_navi.py --check
scope "web/* .github/* tools/*"
step "배포에 내비 빌드"    uv run python tools/pages_add_navi.py --check
scope "web/* tools/* .github/*"
step "루트 잔재·유령 면제" uv run python tools/navi_setup.py --check
scope "docs/*"
step "문서 제목 무결"      uv run python tools/docpatch.py check \
     docs/MASTER.md docs/PLAN.md docs/DECISIONS.md


# ── 결과 ─────────────────────────────────────────────────────
echo
# ── 부분 실행이면 전수가 아니다 ──────────────────────────────
# ★ 건너뛴 것은 통과가 아니다. 여기서 울지 않으면 `dms.py seal` 이
#   반쪽 실행을 전수로 착각하고 봉인한다 — 가짜 증표가 된다.
# ★ 2026-09-15. `--fast` 도 여기 걸린다. 종전에는 `--only` 만 봤는데
#   `--fast` 는 `파이프라인 전량` 을 통째로 생략하면서도 전수처럼
#   통과했다 — 건너뛴 것은 통과가 아니다. 같은 자리에 같은 규율이다.
if [ -n "$ONLY" ] || [ "$FAST" = "1" ] || [ -n "$SINCE" ]; then
    # ★ 이 단계 자신이 --only 에 걸려 건너뛰면 안전장치가 무력해진다.
    #   면제를 만들 때 자기 자신을 면제하는 것과 같은 형태다.
    # ★ 2026-09-19 (W7-2). `--since` 도 여기 건다. 범위 기반 실행은 **빠른
    #   되먹임 도구지 수용이 아니다.** 여기서 안 울면 `dms.py seal` 이
    #   반쪽 실행을 전수로 착각하고 봉인한다 — `--fast` 때와 같은 자리다.
    _only_keep="$ONLY"; ONLY=""
    _sc_keep="$SCOPE"; SCOPE=""
    step "부분 실행" bash -c 'echo "--only · --fast · --since 중 하나로 돌았다. 전수가 아니다."; exit 1'
    ONLY="$_only_keep"; SCOPE="$_sc_keep"
fi
# ★ 2026-09-22 (DECISIONS §218-5). `부분 실행` 뒤에 둔다 — 그것도 분모에 든 단계다.
evidence_check


printf '%s══════════════════════════════════════════════%s\n' "$D" "$Z"
# ★ printf 의 %-34s 는 글자 수로 센다. 한글은 화면에서 두 칸을 먹으므로
#   그대로 두면 표가 어긋난다. 화면 폭으로 직접 채운다.
# ★ 화면폭은 바이트로 못 잰다. UTF-8 3바이트 중 두 칸인 것은 한글·한자뿐이고
#   `↔ · — ─ ★` 는 3바이트인데 한 칸이다. 종전 식은 그것들을 두 칸으로 쳐서
#   이름이 비고를 밀고 들어갔다.
# ★ `grep -o '[가-힣]'` 로 세는 방식은 C 로케일에서 범위가 바이트로 풀려
#   개수가 튄다. 로케일에 의존하는 판정은 기계마다 답이 다르다 — 안 쓴다.
# ★ `east_asian_width` 는 유니코드 표준값이라 로케일을 안 탄다.
#   이름 35개를 **한 번의 호출로** 다 재서 담는다.
declare -A WIDE NOTECUT
measure() {
    command -v python3 >/dev/null 2>&1 || return 0
    local i
    while IFS=$'\t' read -r w s; do WIDE["$s"]=$w; done < <(
        printf '%s\n' "${NAMES[@]}" | python3 -c '
import sys, unicodedata
for line in sys.stdin.read().split("\n")[:-1]:
    print(sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
              for c in line), line, sep="\t")')
    # ★ 비고 자르기도 글자 단위로. 바이트로 자르면 한글이 반토막 난다.
    # ★ 앞공백도 턴다. 도구가 `  저장소가 아니거나…` 처럼 들여쓴 줄을 내는데
    #   그대로 찍으면 이름 칸은 맞는데 비고가 두세 칸씩 밀려 보인다 —
    #   정렬이 틀린 것처럼 보이는 진짜 원인이 이것이었다(pad 는 맞았다).
    i=0
    while IFS= read -r line; do NOTECUT["$i"]="$line"; i=$((i+1)); done < <(
        printf '%s\n' "${NOTES[@]}" | python3 -c '
import sys
for line in sys.stdin.read().split("\n")[:-1]:
    print(line.strip()[:64])')
}

pad() {                       # pad <문자열> <목표 화면폭>
    local s="$1" target="$2" w
    w=${WIDE["$s"]:-${#s}}
    printf '%s' "$s"
    while [ "$w" -lt "$target" ]; do printf ' '; w=$((w+1)); done
}
# ★ 실패를 먼저, 통과는 숫자로 접는다. 통과 29줄이 실패 6줄을 덮으면
#   실패를 안 읽는다 — 원칙 ③ 의 화면판이다. 전체는 `--table`.
row() {
    local c="$1" mark="$2" i="$3"
    printf '    %s%s%s ' "$c" "$mark" "$Z"; pad "${NAMES[$i]}" 34; printf ' '
    printf '%s%s%s\n' "$D" "${NOTECUT[$i]:-${NOTES[$i]}}" "$Z"
}
measure                       # ★ row 를 부르기 전에 한 번
printf '  %s · 통과 %d · 실패 %d · 생략 %d\n\n' \
       "$(hms $(( $(date +%s) - T_ALL )))" "$pass" "$fail" "$skip"

if [ "$fail" -gt 0 ]; then
    printf '  %s실패 %d%s\n' "$R" "$fail" "$Z"
    for i in "${!NAMES[@]}"; do
        [ "${RESULTS[$i]}" = "실패" ] && row "$R" "✗" "$i"
    done
    echo
fi
if [ "$skip" -gt 0 ]; then
    printf '  %s생략·건너뜀 %d%s\n' "$Y" "$skip" "$Z"
    for i in "${!NAMES[@]}"; do
        case "${RESULTS[$i]}" in 생략|건너뜀) row "$Y" "-" "$i" ;; esac
    done
    echo
fi
if [ "$TABLE" = "1" ]; then
    printf '  %s전체%s\n' "$D" "$Z"
    for i in "${!NAMES[@]}"; do
        case "${RESULTS[$i]}" in
            OK)   row "$G" "✓" "$i" ;;
            실패) row "$R" "✗" "$i" ;;
            *)    row "$Y" "-" "$i" ;;
        esac
    done
    echo
else
    printf '  %s통과 %d — 전부 보려면 --table%s\n\n' "$D" "$pass" "$Z"
fi

# ★ 어디서 시간이 가는지 모르면 줄일 데를 못 고른다.
printf '  %s오래 걸린 것%s\n' "$D" "$Z"
for i in "${!NAMES[@]}"; do
    printf '%06d\t%s\n' "${SECS[$i]:-0}" "${NAMES[$i]}"
done | sort -rn | head -5 | while IFS=$'\t' read -r s n; do
    [ "$((10#$s))" -gt 0 ] || continue
    printf '    '; pad "$n" 34; printf ' %s%s%s\n' "$D" "$(hms $((10#$s)))" "$Z"
done
echo
printf '%s══════════════════════════════════════════════%s\n' "$D" "$Z"

if [ "$fail" -gt 0 ]; then
    printf '%s실패가 있다. 머지하지 마라.%s\n' "$R" "$Z"
    printf '  되돌리려면 git 을 쓴다:  git checkout -- <경로>\n\n'
    exit 1
fi

# ★ 2026-09-18. 종전에는 `skip` 을 안 보고 무조건 「전부 통과했다」를 찍었다.
#   `note_hard` 가 덮개 없는 생략을 실패로 올리므로 여기 오는 생략은 전부
#   "다른 관문이 덮는다" 는 것이지만, **그래도 이 실행이 전수는 아니다.**
#   문구가 전수를 주장하면 사람은 그렇게 읽고, `dms.py seal` 이 그 로그로
#   봉인하면 반쪽 증표가 된다. 전수 주장은 생략 0 일 때만 한다.
if [ "$skip" -gt 0 ]; then
    printf '%s실패는 없다. 다만 생략 %d 건이 있어 이 실행은 전수가 아니다.%s\n' "$Y" "$skip" "$Z"
    printf '  %s위 「생략·건너뜀」 목록을 보고, 덮는 관문(CI 등)이 실제로 돌았는지 확인할 것.%s\n\n' "$D" "$Z"
else
    printf '%s자동 검증은 전부 통과했다.%s\n\n' "$G" "$Z"
fi
printf '  %s아직 사람이 봐야 하는 것 하나:%s\n' "$Y" "$Z"
printf '    uv run python tools/serve.py\n'
printf '    %sWebGL 렌더링은 스크립트가 못 본다. 지도가 실제로 그려지는지,%s\n' "$D" "$Z"
printf '    %s판정 색·표지판·미니맵·검색이 눈으로 멀쩡한지 확인할 것.%s\n\n' "$D" "$Z"
