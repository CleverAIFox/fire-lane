#!/usr/bin/env bash
# tools/verify.sh — 리팩터링 검증 일괄
#
#   bash tools/verify.sh          전체
#   bash tools/verify.sh --fast   파이프라인 전량(4분) 생략
#
# ★ 손으로 8줄 치지 마라. 중간에 뭐가 깨졌는지 못 짚는다.
#   여기서는 실패해도 끝까지 돌고 마지막에 표로 보여준다.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
FAST=0; [ "${1:-}" = "--fast" ] && FAST=1

R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; C=$'\033[36m'; D=$'\033[90m'; Z=$'\033[0m'
declare -a NAMES RESULTS NOTES
pass=0; fail=0; skip=0

step() {                      # step "이름" "명령..."
    local name="$1"; shift
    printf '%s── %s%s\n' "$C" "$name" "$Z"
    local out rc
    out=$("$@" 2>&1); rc=$?
    if [ $rc -eq 0 ]; then
        printf '%s   OK%s  %s\n' "$G" "$Z" "$(printf '%s' "$out" | tail -1)"
        NAMES+=("$name"); RESULTS+=("OK"); NOTES+=("$(printf '%s' "$out" | tail -1)")
        pass=$((pass+1))
    else
        printf '%s   실패%s\n' "$R" "$Z"
        printf '%s' "$out" | tail -15 | sed 's/^/     /'
        NAMES+=("$name"); RESULTS+=("실패"); NOTES+=("$(printf '%s' "$out" | tail -1)")
        fail=$((fail+1))
    fi
    echo
}

note() { NAMES+=("$1"); RESULTS+=("생략"); NOTES+=("$2"); skip=$((skip+1))
         printf '%s── %s%s\n%s   생략%s  %s\n\n' "$C" "$1" "$Z" "$Y" "$Z" "$2"; }

echo
printf '%s저장소%s  %s\n' "$D" "$Z" "$ROOT"
printf '%s노드  %s  %s\n' "$D" "$Z" "$(node --version 2>/dev/null || echo '없음')"
printf '%suv    %s  %s\n\n' "$D" "$Z" "$(uv --version 2>/dev/null || echo '없음')"

# ── 0. 잠금파일 갱신 ─────────────────────────────────────────
# ★ pyproject 에 [build-system] 이 생겼고 의존성 9개가 extras 로 내려갔다.
#   uv.lock 이 그 전에 만들어진 것이라 다시 풀어야 한다.
step "의존성 동기화 (uv sync)" uv sync

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

# ── 4. 계층 규칙 ─────────────────────────────────────────────
step "계층 강제 (test_layering)" uv run pytest tests/test_layering.py -q

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
step "문서 숫자 대조"   uv run python tools/docnum_check.py
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

# ── 8. 파이프라인 전량 + 판정 불변 ───────────────────────────
# ★ 여기가 진짜 검증이다. 위의 전부가 통과해도 판정이 바뀌면 실패다.
if [ "$FAST" = "1" ]; then
    note "파이프라인 전량 + golden" "--fast 로 생략. 반드시 따로 돌릴 것"
elif [ -z "${FIRE_LANE_DATA:-}${FIRE_LANE_RAW:-}" ] && [ ! -d data/raw/gjcity ]; then
    note "파이프라인 전량 + golden" "raw 가 없다. FIRE_LANE_DATA 설정 후 다시"
else
    step "파이프라인 전량" uv run fire-lane
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

# ── 결과 ─────────────────────────────────────────────────────
echo
printf '%s══════════════════════════════════════════════%s\n' "$D" "$Z"
# ★ printf 의 %-34s 는 글자 수로 센다. 한글은 화면에서 두 칸을 먹으므로
#   그대로 두면 표가 어긋난다. 화면 폭으로 직접 채운다.
pad() {                       # pad <문자열> <목표 화면폭>
    # ★ printf 의 %-34s 는 글자 수로 센다. 한글은 화면에서 두 칸을 먹으므로
    #   그대로 두면 표가 어긋난다.
    # ★ 한글 범위를 regex 로 잡는 방식은 로케일·collation 을 타서 못 쓴다.
    #   바이트로 센다: UTF-8 에서 한글은 3바이트 · 화면 2칸, ASCII 는 1·1.
    #   폭 = 글자수 + (바이트수 - 글자수) / 2  →  한글 한 자당 정확히 +1.
    local s="$1" target="$2" chars bytes w
    chars=${#s}
    bytes=$(LC_ALL=C; printf '%s' "$s" | wc -c)
    w=$(( chars + (bytes - chars) / 2 ))
    printf '%s' "$s"
    while [ "$w" -lt "$target" ]; do printf ' '; w=$((w+1)); done
}
for i in "${!NAMES[@]}"; do
    case "${RESULTS[$i]}" in
        OK)   c="$G" ;;
        실패) c="$R" ;;
        *)    c="$Y" ;;
    esac
    printf '  %s' "$c"; pad "${RESULTS[$i]}" 5; printf '%s ' "$Z"
    pad "${NAMES[$i]}" 34
    printf '%s%s%s\n' "$D" "${NOTES[$i]}" "$Z"
done
printf '%s══════════════════════════════════════════════%s\n' "$D" "$Z"
printf '  통과 %d · 실패 %d · 생략/참고 %d\n\n' "$pass" "$fail" "$skip"

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
