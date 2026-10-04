#!/usr/bin/env bash
# treescan.sh — 비밀값을 **작업 트리 전수**로 훑는다. 이력도 범위도 아니다.
#
#   bash tools/treescan.sh              훑는다 (0 깨끗 · 1 걸림 · 2 못 훑음)
#   bash tools/treescan.sh --available  훑을 수 있나만 본다 (0/2)
#   bash tools/treescan.sh --selftest   판별식이 살아 있나
#
# ── 왜 생겼나 (DECISIONS §376 · §381 · §389) ───────────────────
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
# ★ 2026-10-04 (§389). 호출 꼴을 맞추자 셋이 걸렸고 **셋 다 오탐**이었다 —
#   `.venv` 의 남의 패키지 둘과 `tests/__pycache__` 의 바이트코드 하나다.
#   `--no-git` 은 `.gitignore` 를 **안 본다.** 그래서 범위가 「디스크에 있는
#   것 전부」로 넓어졌고, §376 이 든 물음은 그것이 아니었다 —
#
#       「복제하면 같이 가나」
#
#   그 답은 git 이 들고 있다. **경로를 열거하지 않고 git 에게 묻는다**
#   (`git check-ignore`). 열거하면 새 무시 자리가 생길 때마다 낡고, 낡은
#   목록은 오탐을 다시 낳는다. 묻는 쪽은 안 낡는다.
#
# IN    .gitleaks.toml · 작업 트리 · .gitignore (git 이 해석한다)
# OUT   없음 (종료코드 · 걸린 자리의 규칙·경로·줄만 찍는다)
# PARAM 없음
# 밖    **이력은 안 본다.** 이력 전수는 `gitleaks git --log-opts` 이고
#       §146 이 감수한 셋이 거기 있다. 여기가 드는 것은 「지금 트리에
#       있나」 하나다 — 복제하면 같이 가는 것이 그것이다.
#       **값이 비밀인지도 안 가른다.** 그 규칙은 `.gitleaks.toml` 이 든다.
#       **값은 안 찍는다.** 찍으면 그 자체가 둘째 유출이다 — 그래서
#       보고서에서 **칸 셋만 이름으로 꺼낸다**(규칙 · 경로 · 줄).
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

# ★ **거르는 자리의 정본.** 보고서를 읽어 **무시되는 경로를 떨어낸다.**
#   자기검사도 이 코드를 쓴다 — 둘이 갈리면 자기검사만 통과한다(§381).
#   `git check-ignore --stdin` 에게 묻는다. 목록을 여기 안 적는다.
#   값을 담는 칸(`Secret`·`Match`·`Line`·`Snippet`·`Entropy`)은 **안 읽는다.**
read -r -d '' FILTER <<'PY'
import json, subprocess, sys

# ★ **금지 목록이 아니라 허용 목록이다.** 처음에는 값을 담는 칸 이름을 모아
#   빼려고 했는데, 찍는 줄이 칸 셋만 꺼내 쓰므로 그 목록은 비워도 아무것도
#   안 바뀌는 **죽은 짐**이었다 — 「값이 찍혔다」 자기검사가 빈 그물이 된다.
#   셋만 이름으로 꺼내면 넷째 칸은 들어올 길이 없다. 자기검사는 **찍는 줄을
#   넓히는 날** 울라고 남겨 둔다.
SHOW = ("RuleID", "File", "StartLine")

def ignored(paths):
    """git 이 무시하는 경로만 돌려준다. 못 물으면 **빈 집합으로 안 바꾼다.**"""
    if not paths:
        return set()
    r = subprocess.run(["git", "check-ignore", "--stdin"],
                       input="\n".join(paths), capture_output=True, text=True)
    # 0 = 무시되는 것이 있다 · 1 = 하나도 없다 · 그 밖 = 못 물었다
    if r.returncode not in (0, 1):
        sys.exit("★ git 에게 무시 여부를 못 물었다 — 거르지 않고 멈춘다\n"
                 "  빈 집합으로 바꾸면 오탐이 그대로 빨갛고, 전부 무시로\n"
                 "  바꾸면 진짜가 조용해진다. 둘 다 틀렸다(§372)")
    return {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}

def surviving(rows):
    skip = ignored([f.get("File", "") for f in rows if f.get("File")])
    return [f for f in rows if f.get("File", "") not in skip], skip

def show(rows):
    for f in rows:
        rule, path, line = (f.get(k, "?") for k in SHOW)
        print(f"    {rule}  {path}:{line}")

rows = json.load(open(sys.argv[1], encoding="utf-8")) or []
left, skip = surviving(rows)
if skip:
    print(f"  무시되는 자리 {len(skip)}건은 떨어냈다 — 복제하면 같이 안 간다")
if not left:
    print("✓ 비밀값 — 추적 범위에 걸린 것이 없다")
    sys.exit(0)
print(f"★ 비밀값이 걸렸다 {len(left)}건 — 값은 안 찍는다")
show(left)
sys.exit(1)
PY

case "${1:-}" in
--available)
    have || exit 2
    exit 0
    ;;
--selftest)
    # ★ 거르는 자리는 **바이너리 없이도** 잰다 — 합성 보고서를 먹여 양방향으로.
    #   `.venv/x.py` 는 `.gitignore` 에 있으니 떨어지고, `sources.yaml` 은 추적
    #   되니 남아야 한다. 이것이 §389 가 고친 그 판별식이다.
    TMP="$(mktemp)"
    cat > "$TMP" <<'JSON'
[{"RuleID":"aws-access-token","File":".venv/x.py","StartLine":1,
  "Secret":"MUST-NOT-PRINT-THIS","Match":"MUST-NOT-PRINT-THIS"},
 {"RuleID":"github-pat","File":"sources.yaml","StartLine":2,
  "Secret":"MUST-NOT-PRINT-THIS","Match":"MUST-NOT-PRINT-THIS"}]
JSON
    OUT="$(python3 -c "$FILTER" "$TMP" 2>&1)"; RC=$?
    rm -f "$TMP"
    if [ "$RC" -ne 1 ]; then
        echo "★ 자기검사 실패 — 추적 파일의 걸림을 1 로 안 냈다 ($RC)"; exit 1
    fi
    case "$OUT" in
        *".venv/x.py"*) echo "★ 자기검사 실패 — 무시되는 자리를 찍었다"; exit 1 ;;
    esac
    case "$OUT" in
        *MUST-NOT-PRINT-THIS*) echo "★ 자기검사 실패 — 값이 찍혔다"; exit 1 ;;
    esac
    case "$OUT" in
        *"sources.yaml:2"*) : ;;
        *) echo "★ 자기검사 실패 — 추적 파일의 걸림을 안 찍었다"; exit 1 ;;
    esac
    if ! have; then
        echo "✓ 자기검사 — 거르는 자리 양방향 OK · gitleaks 는 없다. 「못 훑음(2)」로 센다"
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
    echo "✓ 자기검사 — 거르는 자리 양방향 OK (무시 떨어냄 · 추적 남김 · 값 안 찍음)"
    exit 0
    ;;
esac

have || { echo "gitleaks 가 없다"; exit 2; }
pick || { echo "gitleaks 가 dir · detect 둘 다 모른다 — 버전이 너무 낡았다"; exit 2; }

REPORT="$(mktemp)"
trap 'rm -f "$REPORT"' EXIT
# ★ `--exit-code 1` 은 그대로 둔다 — gitleaks 가 **걸렸다고 말하는 것**과
#   이 문이 **그것을 받아들이는 것**은 다른 판단이다. 2 이상은 못 훑은 것이다.
gitleaks "${SUB[@]}" "${ARGS[@]}" --report-format json --report-path "$REPORT"
RC=$?
[ "$RC" -le 1 ] || { echo "gitleaks 가 $RC 로 끝났다 — 못 훑었다"; exit 2; }
[ -s "$REPORT" ] || { echo "✓ 비밀값 — 걸린 것이 없다"; exit 0; }

python3 -c "$FILTER" "$REPORT"
