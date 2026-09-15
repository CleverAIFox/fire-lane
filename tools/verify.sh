#!/usr/bin/env bash
# tools/verify.sh — 리팩터링 검증 일괄
#
#   bash tools/verify.sh            전체
#   bash tools/verify.sh --fast     파이프라인 전량(4분) 생략
#   bash tools/verify.sh --table    통과한 것까지 전부 표로
#   bash tools/verify.sh --only=pytest   ★ 이름이 맞는 단계만. 부분 실행이다
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
TOTAL=$(grep -oE '^[[:space:]]*step "[^"]*"' "$0" | sed 's/.*step //' | sort -u | wc -l)
IDX=0; T_ALL=$(date +%s)
ONLY=""; TABLE=0
for arg in "$@"; do
    case "$arg" in
        --only=*) ONLY="${arg#--only=}" ;;
        --table)  TABLE=1 ;;
    esac
done

hms() {                       # 초 → "51초" · "2분41초"
    if [ "$1" -lt 60 ]; then printf '%d초' "$1"
    else printf '%d분%02d초' $(( $1 / 60 )) $(( $1 % 60 )); fi
}

step() {                      # step "이름" "명령..."
    local name="$1"; shift
    IDX=$((IDX+1))
    # ★ --only 로 뺀 것은 `건너뜀` 이다. **통과가 아니다.**
    if [ -n "$ONLY" ] && ! printf '%s' "$name" | grep -qE "$ONLY"; then
        NAMES+=("$name"); RESULTS+=("건너뜀"); NOTES+=("--only 로 뺐다"); SECS+=(0)
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

note() { NAMES+=("$1"); RESULTS+=("생략"); NOTES+=("$2"); SECS+=(0); skip=$((skip+1))
         printf '%s── %s%s\n%s   생략%s  %s\n\n' "$C" "$1" "$Z" "$Y" "$Z" "$2"; }

echo
printf '%s저장소%s  %s\n' "$D" "$Z" "$ROOT"
# ★ 2026-09-14. HEAD 를 찍는다. `dms.py seal --log` 가 이 줄을 읽어
#   로그가 지금 나무를 말하는지 판정한다. 종전에는 파일 mtime 으로
#   봤는데 **내용이 안 바뀌어도 잡혀서** 30분짜리 재실행을 시켰다.
printf 'HEAD    %s%s\n' \
  "$(git rev-parse --short HEAD 2>/dev/null || echo '(git 밖)')" \
  "$(git status --porcelain 2>/dev/null | grep -q . && echo ' +미커밋' || true)"
printf '%s노드  %s  %s\n' "$D" "$Z" "$(node --version 2>/dev/null || echo '없음')"
printf '%suv    %s  %s\n\n' "$D" "$Z" "$(uv --version 2>/dev/null || echo '없음')"

# ── 0. 잠금파일 갱신 ─────────────────────────────────────────
# ★ pyproject 에 [build-system] 이 생겼고 의존성 9개가 extras 로 내려갔다.
#   uv.lock 이 그 전에 만들어진 것이라 다시 풀어야 한다.
step "의존성 동기화 (uv sync --dev)" uv sync --dev

# ── 1. 패키지가 실제로 import 되는가 ─────────────────────────
step "패키지 import 29종" uv run python -c '
import importlib, sys
mods = ["paths","manifest","quiet_gdal","krgis.crs","seg.params","seg.geom","seg.width",
        "seg.roadname","seg.basisno","seg.graph","seg.report","segkey","guards",
        "lineage","ngi","ngii1k","probe","contract","inventory","datalog",
        "normalize_raw","sample_design","ingest","segments","streetlight",
        "terrain","ortho","publish_web","pipeline"]
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
step "pytest" uv run pytest tests/ -q

# ── 4. (삭제) 계층 규칙 ──────────────────────────────────────
# ★ 2026-09-03. `pytest tests/ -q` 가 이미 test_layering 을 돌린다.
#   같은 환경에서 두 번 돌아 표에 줄만 하나 더 찍혔다. 아래 'CI 환경
#   재현' 은 모듈을 가린 **다른 환경**이라 그것은 남긴다.

# ── 5. 린트 ─────────────────────────────────────────────────
# ★ 2026-08-22 에 155 → 0 으로 정리했다. 이제 참고가 아니라 게이트다.
#   되돌아가면 여기서 죽는다. 스타일 규칙 6종은 pyproject 에서 껐고
#   끄는 근거를 각각 적어뒀다.
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


# ── 5b. 저장소 위생 — CI 와 같은 것을 본다 ───────────────────
# ★ 2026-08-23. 여기가 CI 검사 다섯을 안 돌고 있었다. README 는 "받자마자
#   이것 하나면 된다" 고 하는데, verify.sh 초록불이어도 CI 는 빨간불이 될 수
#   있었다 — 커밋 정책 · 인코딩 · web/data 계보 · 문서 숫자 · 용량 상한.
#   로컬 검증이 CI 의 부분집합이면 "내 기계에서는 됐는데" 가 나온다.
# ★ 2026-08-23. CI 는 `pip install pytest shapely numpy ruff pyyaml` +
#   `--no-deps` 로만 깐다. 로컬은 `uv sync` 로 전부 깔려 있어
#   **로컬 초록불 · CI 빨간불**이 난다. 실제로 `import yaml` 을 쓰는
#   테스트 둘이 그렇게 죽었다.
#   CI 가 없는 패키지를 가려서 그 환경을 흉내낸다. 30초면 된다.
step "CI 환경 재현"     bash -c '
    B=$(mktemp -d)
    # CI 가 안 까는 것들. contract.yml 의 pip install 목록에 없는 것.
    for m in pandas geopandas pyogrio pyproj rasterio PIL ruamel; do
        printf "raise ModuleNotFoundError(\"No module named %s\")\n" "$m" > "$B/$m.py"
    done
    PYTHONPATH="$B" uv run python -m pytest \
        tests/test_guards.py tests/test_static.py \
        tests/test_reproducibility.py tests/test_layering.py -q'

step "커밋 정책"        uv run python tools/commit_policy.py --tracked
step "인코딩·개행"      uv run python tools/encoding_check.py
step "환경변수 선언↔실물" uv run python tools/env_check.py
step "문서 숫자 대조"   uv run python tools/docnum_check.py
# ★ 2026-09-03 배선. 여덟 중 다섯만 tests/test_doc_fsck.py 가 걸고 있었고
#   ⑥ 기획서 수정일 · ⑦ 셸 명령 · ⑧ 기한은 **사람이 손으로 칠 때만**
#   돌았다. 그 사람이 나가면 아무도 안 친다.
step "문서 ↔ 문서"     uv run python tools/doc_fsck.py
# ★ 2026-09-02 배선. 오늘 캡션 절까지 붙여놓고 **어디서도 안 부르고
#   있었다.** 사람이 손으로 칠 때만 도는 도구는 이탈 후 아무도 안 부른다.
step "기획서 대조"     uv run python tools/docx_check.py
# ★ 캡션만 보던 것을 그림 자체로 넓혔다. 값이 바뀌면 그림이 낡는다.
step "그림 ↔ 정본"     uv run python tools/render_figures.py --check
# ★ 막는 검사가 아니라 **보여주는** 것이다. 승인이 형식이 되지 않게
#   리뷰어에게 무엇이 움직였는지 준다(DECISIONS §109).
note "흡수 대상" "$(uv run python tools/release_brief.py 2>&1 | tail -1)"
# ★ 선언이 가리키는 것이 실재하는가. 같은 이유로 안 걸려 있었다.
step "선언 ↔ 실물"     uv run python tools/refcheck.py
# ★ 전수 스캔. `--repo` 는 데이터 레이크 없이 저장소 트리만 본다 —
#   항목에서 출발하는 검사는 **항목이 없는 것을 영원히 못 본다.**
step "트리 전수 대조"   uv run python tools/treecheck.py --repo
step "web/data 계보"    uv run python tools/web_manifest.py --check
step "로컬 찌꺼기"      uv run python tools/tidy.py
step "web/data 용량"    bash -c '
    SIZE=$(du -sm web/data | cut -f1)
    LIM=$(grep -oP "MAX_WEBDATA_MB\s*=\s*\K\d+" tools/commit_policy.py)
    echo "web/data ${SIZE}MB / 상한 ${LIM}MB"
    [ "$SIZE" -lt "$LIM" ]'

# ── 6. JS 모듈 그래프 ────────────────────────────────────────
step "JS 문법·순환·import" node tools/js_graph_check.mjs

# ── 7. JS 부팅 (jsdom 필요) ──────────────────────────────────
if [ -d node_modules/jsdom ]; then
    step "JS 부팅 스모크" node tools/web_boot_check.mjs
elif command -v npm >/dev/null 2>&1; then
    printf '%s── JS 부팅 스모크%s\n%s   jsdom 설치 중...%s\n' "$C" "$Z" "$D" "$Z"
    if npm install --no-save jsdom >/dev/null 2>&1; then
        step "JS 부팅 스모크" node tools/web_boot_check.mjs
    else
        note "JS 부팅 스모크" "jsdom 설치 실패 — npm install --no-save jsdom"
    fi
else
    note "JS 부팅 스모크" "npm 이 없다"
fi

# ── 7b. 내비 타입 검사 (web/navi) ────────────────────────────
# ★ 2026-09-15 신설. 6·7 은 `web/*.js` 클래식 스크립트만 본다. 내비는
#   React/TS 라 그 셋에 안 걸리고, 컴파일하는 곳은 배포 액션 하나뿐이다.
#   그래서 maplibre-gl 6 이 로컬 39단계 전부 초록인 채로 main 까지 갔다.
#   **여기가 비어 있어서 로컬이 CI 의 부분집합도 아니었다**(5b 와 같은 사고).
# ★ 타입만 본다. `vite build` 는 토큰이 필요하고, 이번 사고는 타입에서
#   잡혔다. 토큰 없는 빌드는 배포 액션이 맡는다.
if [ -d web/navi/node_modules ]; then
    step "내비 타입 검사" bash -c 'cd web/navi && npm run -s typecheck'
elif command -v npm >/dev/null 2>&1; then
    printf '%s── 내비 타입 검사%s\n%s   npm ci 중...%s\n' "$C" "$Z" "$D" "$Z"
    if (cd web/navi && npm ci --no-audit --no-fund >/dev/null 2>&1); then
        step "내비 타입 검사" bash -c 'cd web/navi && npm run -s typecheck'
    else
        note "내비 타입 검사" "npm ci 실패 — cd web/navi && npm ci"
    fi
else
    note "내비 타입 검사" "npm 이 없다"
fi

# ── 8. 파이프라인 전량 + 판정 불변 ───────────────────────────
# ★ 여기가 진짜 검증이다. 위의 전부가 통과해도 판정이 바뀌면 실패다.
if [ "$FAST" = "1" ]; then
    note "파이프라인 전량 + golden" "--fast 로 생략. 반드시 따로 돌릴 것"
elif [ -z "${FIRE_LANE_DATA:-}${FIRE_LANE_RAW:-}" ] && [ ! -d data/raw/gjcity ]; then
    note "파이프라인 전량 + golden" "raw 가 없다. FIRE_LANE_DATA 설정 후 다시"
else
    # ★ --no-test. 계약 테스트는 위 pytest 가 이미 돌렸다. 파이프라인이
    #   끝에서 또 부르면 한 번의 verify 에 test_contract 가 세 번 돈다.
    # ★ PLAN #68. **raw 가 봉인과 같으면 판정도 같다.** 전량 4분30초를
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
    step "파이프라인 전량" bash -c '
        if uv run python tools/dms.py rawdiff; then
            echo "★ raw 가 봉인과 같아 전량을 생략했다 (PLAN #68)."
        else
            uv run fire-lane --no-test --split
        fi'
    step "golden 판정 불변 (1,101구간)" uv run python tools/golden.py check
    # ★ 게이트가 울고 또 풀리는가. check 가 통과하는 것만으로는
    #   해제 경로가 있는지 알 수 없다(DECISIONS §69).
    step "golden 게이트 해제 경로" uv run python tools/golden.py selftest
    # ★ 생산자를 돌린 직후에만 알 수 있다. 커밋된 web/data 가 낡아도
    #   web_manifest 는 **있는 것의 해시**를 뜰 뿐이고 golden 은
    #   segments.geojson 만 본다. 2026-09-02 에 route_vehicle.json 이
    #   08-31 산출인 채로 전 게이트를 통과했다(PLAN #70 · DECISIONS §39).
    step "커밋된 web/data 가 최신인가" bash -c '
        if git diff --quiet -- web/data data/processed/segments.geojson; then
            echo "생산자 재실행과 커밋본이 같다"
        else
            echo "★ 낡았다 — 파이프라인 산출이 커밋본과 다르다:"
            git diff --name-only -- web/data data/processed/segments.geojson
            echo "  생성물이므로 그대로 커밋하면 된다. 다만 무엇이 왜"
            echo "  움직였는지 먼저 본다 — golden 이 불변이면 값이 아니라"
            echo "  커밋본이 뒤처진 것이다(PLAN #70)."
            exit 1
        fi'
fi

# ── 데이터 레이크 정합 ──────────────────────────────────────────
# ★ 선언과 실물이 갈리는 것을 fsck 가 다 보지 못했다 — 제공기관 state ·
#   격리 잔재 · landing 우회 · ext 어휘 · norm 계보 다섯 축이 밖에 있었다.
#   lakecheck 이 그 축을 든다. FIRE_LANE_INBOX 를 기본 스캔 대상으로 쓴다.
step "레이크 선언↔실물" uv run python tools/lakecheck.py

# ★ 스캔만 한다. 지우려면 --sweep --yes 를 사람이 친다.
#   "정리는 사람이 한다" 를 도구가 대신하되 삭제는 명시적으로.
step "레이크 정리 대상" uv run python tools/sweep.py

# ★ 검사가 죽었는지를 검사한다. 프로브 다섯이 정적으로 센다 —
#   빈 그물 · 손목록 · 조용한 통과 · 죽은 게이트 · 좁은 범위.
#   --selftest 는 프로브가 살아 있는지 먼저 본다(양성 대조).
step "검사가 죽었는가" uv run python tools/deadcheck.py --selftest

# ── 소급 · 사본 (B5 ⓪ · 원칙 ⑥) ────────────────────────────────
# ★ `delta` 는 봉인 뒤 바뀐 절만 센다. 전수는 `seal` 이 한 번 돈다.
#   기준선이 없으면 전수가 곧 분모라고 스스로 말한다.
step "강제자 소급 증분" uv run python tools/dms.py delta

# ★ 문턱 40 에서 시작한다. 25 로 내리면 10군이다. 검사를 무르게 만드는
#   것이 아니라 **지금 값에서 시작해 내리는 것**이 일이다(env_check 선례).
step "사본군" uv run python tools/dupcheck.py --min 40 --max 1

# ★ 파일명의 날짜가 자료 기준일인가 내려받은 날인가. `naming` 규약은
#   "다운로드일이 아니다" 라고 적었는데 `_plausible_date` 는 형식만 본다 —
#   규약은 있고 강제자가 그 규약을 안 지켰다(원칙 ①·②). 대가가
#   `its_nodelink` 258MB 두 벌이었다.
# ★ 대장 글롭으로 보면 안 보인다. `files:` 가 한 벌을 못박아놔서 두 번째
#   벌은 대장 밖이다. 이 도구는 **레이크를 직접 훑는다.**
step "vintage 정합" uv run python tools/vintage_check.py --max 0

# ★ norm 이 지금의 raw 에서 나온 것인가. **재현성 게이트다.**
#   2026-09-14 까지 이 축은 verify.sh 밖에 있었다 — 손상이 늘어도 우는
#   곳이 없었다. `--check` 를 고쳐 미등록까지 세게 만들어놓고 배선을
#   안 했다. **세는 것과 거는 것은 다른 일이다.**
# ★ 상한 래칫이다. 0 을 요구하면 영영 빨갛고, 빨간 게이트는 안 읽힌다.
step "norm 계보 재현" uv run python -m firelane.prep --check --max 0


# ── 배치가 세운 상태가 유지되는가 (B1/W4) ───────────────────────
# ★ 적용 뒤 no-op 이 되는 배치 도구를 EXEMPT 로 재우면, 상태가 되돌아가도
#   우는 곳이 없어진다. 지우는 대신 `--check` 를 달아 강제자로 승격했다.
#   넷은 각자 다른 것을 본다 — 공통 껍데기를 씌우지 않았다.
step "대장 별칭 이관 유지" uv run python tools/ledger_fields.py --check
# ★ 2026-09-15 배선. 종전에는 `test_declaration_sync` 의 실패 메시지 안에
#   안내문으로만 있었다 — 결번이 생겨야 울고, 그 전에 참조가 썩는 것은
#   아무도 안 봤다. 이 도구는 인자 없이 돌면 검사다.
# ★ 이 도구의 REF 정규식이 `\\d` 로 적혀 있어 **만든 날부터 참조를 0건
#   찾았다.** 죽은 참조 안전장치도 참조 치환도 둘 다 안 돌았다. 고치고
#   나니 그 자리에서 죽은 참조 셋이 나왔다(DECISIONS §159).
step "PLAN 번호·참조 정합" uv run python tools/plan_renumber.py
step "내비 소스 목록"      uv run python tools/install_navi.py --check
step "배포에 내비 빌드"    uv run python tools/pages_add_navi.py --check
step "루트 잔재·유령 면제" uv run python tools/navi_setup.py --check
step "문서 제목 무결"      uv run python tools/docpatch.py check \
     docs/MASTER.md docs/PLAN.md docs/DECISIONS.md


# ── 결과 ─────────────────────────────────────────────────────
echo
# ── 부분 실행이면 전수가 아니다 ──────────────────────────────
# ★ 건너뛴 것은 통과가 아니다. 여기서 울지 않으면 `dms.py seal` 이
#   반쪽 실행을 전수로 착각하고 봉인한다 — 가짜 증표가 된다.
if [ -n "$ONLY" ]; then
    # ★ 이 단계 자신이 --only 에 걸려 건너뛰면 안전장치가 무력해진다.
    #   면제를 만들 때 자기 자신을 면제하는 것과 같은 형태다.
    _only_keep="$ONLY"; ONLY=""
    step "부분 실행" bash -c 'echo "--only 로 돌았다. 전수가 아니다."; exit 1'
    ONLY="$_only_keep"
fi


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

printf '%s자동 검증은 전부 통과했다.%s\n\n' "$G" "$Z"
printf '  %s아직 사람이 봐야 하는 것 하나:%s\n' "$Y" "$Z"
printf '    uv run python tools/serve.py\n'
printf '    %sWebGL 렌더링은 스크립트가 못 본다. 지도가 실제로 그려지는지,%s\n' "$D" "$Z"
printf '    %s판정 색·표지판·미니맵·검색이 눈으로 멀쩡한지 확인할 것.%s\n\n' "$D" "$Z"
