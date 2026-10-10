#!/usr/bin/env bash
# tools/fix.sh — **수리 문.** 기계적으로 답이 하나인 것만 고친다.
# 부류  절차   배치를 옮기고 기계를 치운다. **산출물에 안 닿는다**  (DECISIONS §398)
#
#   bash tools/fix.sh            고친다
#   bash tools/fix.sh --dry      무엇을 돌지만 보여준다
#
# ── 왜 따로인가 (DECISIONS §362) ───────────────────────────────
# `verify.sh` 는 수리를 안 한다. 그 파일이 그 사유를 적는다 —
#
#     ★ `--write` 를 여기서 안 돈다. 쓰고 나서 재면 이 관문은 영영 초록이다.
#
# 그 판단은 **옳다.** 검사기가 자기를 고치면 검사가 아니다. 빠진 것은 그
# 판단이 아니라 **수리 문**이었다 — 검사 문만 있고 수리 문이 없으니 수리가
# 전부 사람 손으로 흘러갔다. 실측 2026-10-03: `tools/` 120개 중 **74개가
# 울기만 한다.** 검출은 기계가 하고 수리는 100% 사람이었다.
#
# ★ **이 문은 재지 않는다.** 고치고 나서 「이제 verify 를 돌려라」 하고 멈춘다.
#   고친 뒤에 같은 자리에서 재면 904줄 규율을 어기는 것이다.
#
# ★ **판단이 필요한 것은 손도 안 댄다.** 그 목록과 사유는
#   `tools/fixable.py` 의 `HUMAN_FIRST` 가 든다 — golden 재잠금 · 도장 ·
#   실측 지문 · 레이크가 필요한 것 · 지우는 것 · 네트워크.
#   마지막에 그 이름들을 찍는다. **그게 네가 볼 것의 전부다.**
#
# ★ 순서가 뜻이 있다. 코드·문서를 먼저 고치고, 생성 블록을 실물로 채우고,
#   **래칫을 맨 뒤에** 조인다 — 앞의 수리가 실측값을 바꾸기 때문이다.
#
# IN    tools/*.py 의 수리 깃발 (목록은 아래 fix 호출이 정본)
# OUT   저장소 파일 (고친다) · 표준출력 (무엇을 고쳤나)
# 밖    **아무것도 재지 않는다.** 고친 뒤에 같은 자리에서 재면 그 관문은 영영
#       초록이다 — 그것이 `verify.sh` 가 수리를 안 하는 사유이고 여기도 같다.
#       **판단이 필요한 것은 안 돈다.** 목록과 사유는 `fixable.HUMAN_FIRST` 다.
#       **수리 경로가 있는지는 안 센다** — 그것은 `tools/fixable.py` 가 든다.
#       **커밋하지 않는다.** 무엇이 왜 움직였는지는 사람이 적는다.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DRY=0; [ "${1:-}" = "--dry" ] && DRY=1

R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; D=$'\033[90m'; Z=$'\033[0m'
declare -a NAMES RESULTS
ok=0; bad=0; nop=0

fix() {                       # fix "<이름>" <명령…>
    local name="$1"; shift
    if [ "$DRY" = 1 ]; then
        printf '  %s·%s %-26s %s%s%s\n' "$D" "$Z" "$name" "$D" "$*" "$Z"
        return
    fi
    local out rc
    out=$("$@" 2>&1); rc=$?
    NAMES+=("$name")
    if [ $rc -ne 0 ]; then
        RESULTS+=("빨강"); bad=$((bad+1))
        printf '  %s✗%s %-26s %s\n' "$R" "$Z" "$name" "$(printf '%s' "$out" | tail -2 | tr '\n' ' ')"
        return
    fi
    # 「고칠 것이 없다」와 「고쳤다」를 가른다 — 둘을 섞으면 무엇이 움직였는지 모른다
    if printf '%s' "$out" | grep -qE '고쳐 적었다|채웠다|고쳤다|조였다|^Fixed|Found .* error'; then
        RESULTS+=("고침"); ok=$((ok+1))
        printf '  %s✎%s %-26s %s\n' "$G" "$Z" "$name" "$(printf '%s' "$out" | tail -1)"
    else
        RESULTS+=("그대로"); nop=$((nop+1))
        printf '  %s·%s %-26s %s%s%s\n' "$D" "$Z" "$name" "$D" "고칠 것이 없다" "$Z"
    fi
}

echo
echo "══ 수리 문 — 기계적으로 답이 하나인 것만"
echo

# ① 코드 · 서식 ────────────────────────────────────────────────
fix "린트"            uv run ruff check --fix .
fix "인코딩·개행"      uv run python tools/encoding_check.py --fix
fix "문서 말투 서식"    uv run python tools/docstyle.py --write
# ★ 수만 빼고 꾸밈말은 남긴다(§366-4). `(15 — 양방향)` 의 「양방향」은 정보다.
fix "손으로 적은 시험 수" uv run python tools/countcheck.py --fix

# ② 선언 ↔ 실물 ───────────────────────────────────────────────
# ★ `plan_renumber --apply` 는 **안 부른다.** 폐지된 깃발이고(§205) 그 도구는
#   이제 검사만 한다. 사유는 `fixable.NO_REPAIR` 에 있다.
fix "의존성 그룹"      uv run python tools/depgroups_check.py --fix
fix "대장 별칭 이관"    uv run python tools/ledger_fields.py --apply
fix "죽은 강제자 참조"  uv run python tools/dms.py --apply
# ★ 문서가 **줄면** 북마크가 없는 절을 든다. 더하기만 있던 자리에 뺄 문을
#   달았다(§365). 떨어낸 ID 는 화면에 적힌다 — 조용히 줄면 봉인 분자가 샌다.
fix "북마크 죽은 절"    uv run python tools/dms.py prune --apply

# ③ 생성물 ← 정본 ─────────────────────────────────────────────
fix "기획서 그림"      uv run python tools/docx_figs.py --sync
# ★ 같은 다섯 그림이 **화면 자리로도** 간다(§440 · PLAN #142). 둘을 같이 돌린다 —
#   docx 가 은퇴하면 위 줄이 지워지고 이 줄만 남는다. 변환기는 같은 하나다.
fix "기획서 화면 그림"  uv run python tools/htmlfigs.py --sync
fix "문서 생성 블록"    uv run python tools/docgen.py

# ④ 래칫 — **맨 뒤.** 위 수리가 실측값을 바꾼다 ────────────────
fix "래칫"            uv run python tools/ratchet.py --write

if [ "$DRY" = 1 ]; then
    echo
    echo "  ★ --dry 였다. 아무것도 안 고쳤다."
    exit 0
fi

echo
printf '  고침 %s%d%s · 그대로 %d · 빨강 %s%d%s\n' "$G" "$ok" "$Z" "$nop" "$R" "$bad" "$Z"

# ── 사람이 먼저인 것 ──────────────────────────────────────────
echo
echo "══ 이 문이 **손도 안 댄 것** — 판단이 먼저다"
uv run python - <<'PY'
import sys
sys.path.insert(0, "tools")
from fixable import HUMAN_FIRST, split_rows
for t, why in HUMAN_FIRST.items():
    print(f"  · {t}")
    print(f"      {' '.join(why.split())}")

# ★ 2026-10-03 (DECISIONS §374). **문이 돌았는데도 안 덮이는 자리.** 위 목록은
#   「문이 없는 도구」이고 이것은 「문은 있는데 관문이 **다른 모드**를 본다」다.
#   그 구별이 어디에도 없어서, 문을 다 돌리고 「방강 0」을 본 뒤 전수 verify 가
#   발간 일이 났다(§372 의 강제자 지목). 이제 그 사실을 여기서 찍는다.
rows = split_rows()
if rows:
    print()
    print("══ 문은 **돌았지만** 그 관문은 안 덮는다 — verify 가 따로 들다")
    for tool, mode, why in rows:
        print(f"  · {tool}  관문 모드 `{mode}`")
        print(f"      {' '.join(why.split())}")
PY

echo
if [ "$bad" -gt 0 ]; then
    echo "  ${R}✗${Z} 수리 중 빨강 ${bad}건 — 위를 읽어라. 그 자리는 기계가 못 고친다."
fi
echo "  ${Y}★${Z} 이 문은 **재지 않는다.** 이제 검사 문을 돌려라 —"
echo "        bash tools/verify.sh"
echo
echo "  ${D}고친 것이 있으면 커밋에 **왜 움직였는지**를 적어라. 수리는 기계가 했고"
echo "  그 사유는 사람만 안다.${Z}"
echo
[ "$bad" -gt 0 ] && exit 1
exit 0
