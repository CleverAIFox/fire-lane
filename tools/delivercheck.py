#!/usr/bin/env python3
"""
delivercheck.py — 배달물이 **나가도 되는가.** 이름 · 커밋 메시지 · PR 본문의 판별식.  (DECISIONS §276-1)

── 왜 갈랐나 (2026-09-27) ─────────────────────────────────────
`deliver.py` 가 656줄로 상한(600)을 넘었다. 넘은 만큼이 **판별식 묶음**이고,
그것은 `deliver` 가 하는 다른 일(워크트리를 떠서 재는 것)과 성질이 다르다 —
여기 것들은 **파일 이름과 글자만 보는 순수 함수**라 레이크도 git 도 안 든다.
그래서 시험이 그냥 부를 수 있고, `deliver` 의 자기검사가 재는 것이 대부분 이것들이다.
★ 여기에는 자기검사를 두지 않는다 — 판별식이 순수해서 `tests/` 가 직접 부른다.

★ `bodies_bad` 만 바깥을 탄다(검사기를 돌려야 한다). **실행기를 주입으로 받는다** —
  여기서 subprocess 를 또 만들면 `deliver._run` 과 두 벌이 된다.

IN    패치 파일 이름 목록 · 패치 본문 · 배달 디렉터리
OUT   결함 문장 목록 (비면 통과)
밖    **패치가 붙는지는 안 본다** — 그것은 워크트리를 떠야 알고 `deliver.dryrun` 이 든다.
      **본문의 내용이 옳은지도 안 본다** — 템플릿을 채웠는가만 `pr_body_check` 에 묻는다.
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
"""
from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 열차가 반드시 쓰는 본문. 없으면 2단계가 죽는다(2026-09-27 오전 실제 사고).
NEED_BODY = "PR_BODY.md"
#: 본문 검사기. 저장소에 이미 있었는데 **배달 예습이 안 불렀다**(§276-1).
BODY_CHECK = "tools/pr_body_check.py"


# ── ⑤ 배달물에 있으면 안 되는 것 ────────────────────────────────
FORBIDDEN = ("Co-Authored-By: Claude", "Claude-Session:")


# ── ⑥ 스윕 채집과 기준선 대조 ───────────────────────────────────
# ★ 2026-09-28 (DECISIONS §290-6). `deliver.py` 가 **또** 상한(600)을 넘었다 —
#   657줄. 넘은 만큼이 이 블록이고, 이 파일의 머리말이 적은 기준과 꼭 맞는다:
#   **파일 이름과 글자만 보는 순수 함수**라 레이크도 git 도 안 든다. 저쪽에
#   남은 것은 「워크트리를 떠서 실제로 돌리는 일」뿐이고, 그 둘이 갈리면
#   시험이 판별식을 직접 부를 수 있다.
#
#: 화면 색. 이름을 정규식으로 잡으려면 먼저 걷어야 한다.
ANSI = re.compile(r"\x1b\[[0-9;]*m")
#: `verify.sh` 요약의 빨간 줄.
#: ★ 2026-09-30 (DECISIONS §319-3). 종전 판은 `(?:\s{2,}|$)` 였고 **`\s` 가 줄바꿈을
#:   먹었다.** 이름과 힌트 사이가 한 칸뿐인 줄(예: 「의존성 동기화 (uv sync …)
#:   (v0.1.0) depends on `actionlint-py`」)에서는 끝맺음이 `\n` + 다음 줄 들여쓰기를
#:   삼켰고, 그러면 **다음 `✗` 줄이 통째로 안 잡힌다.** 실측 — 밑동 스윕에서
#:   「선언 ↔ 실물」이 그렇게 빠졌고, 배치 쪽에서는 앞 줄이 달라 잡혀서 **없던
#:   「새 빨간불」이 생겼다.** 빠지는 쪽이 더 나쁘다 — 빨간 축을 **조용히 떨군다.**
#: ★ 그래서 끝맺음을 **줄 안으로 가둔다**(`[ \t]`). `$` 는 `re.M` 에서 줄 끝이다.
FAIL_LINE = re.compile(r"^[ \t]+✗[ \t]+(.+?)(?:[ \t]{2,}.*)?$", re.M)
#: ★ 2026-10-08 (DECISIONS §431). **요약 블록만 본다.** `verify.sh` 는 끝에
#:   `  실패 N` 을 찍고 그 아래 `    ✗ <축>` 을 단계 수만큼 쓴 뒤 **빈 줄**로 닫는다.
#:   종전에는 출력 전체에서 `✗` 를 주웠다 — 도구가 제 안에서 찍는
#:   `✗ 상한 0 을 넘었다 (37). 늘었다.` 같은 줄이 **축 이름으로 둔갑**했고,
#:   수가 37 → 36 으로 좋아져도 **다른 축**이라 「새 빨간불」이 됐다.
#:   이번 판에서만 세 번 배달을 막았다.
SUMMARY_BLOCK = re.compile(
    r"^[ \t]*실패[ \t]+\d+[ \t]*$\n(.*?)(?=^[ \t]*$|\Z)", re.M | re.S)
#: 합계 줄 — `  19분13초 · 통과 99 · 실패 2 · 생략 0`. **수를 따로 든다.**
TOTALS = re.compile(r"·[ \t]*통과[ \t]+(\d+)[ \t]*·[ \t]*실패[ \t]+(\d+)[ \t]*·[ \t]*생략[ \t]+(\d+)")
#: `verify.sh` 의 `note()` 가 찍는 두 줄 — `── <이름>` 다음 줄이 `생략  <사유>`.
SKIP_LINE = re.compile(r"^── (.+?)\s*\n\s+생략\s+(.+?)\s*$", re.M)

#: 레이크 없는 기계에서만 빨갛다고 인정하는 것.
#: (노드 id 조각, 사유, 판별식). **판별식이 거짓인데 빨갛다면 거부한다.**
LAKE_ONLY: dict[str, tuple[str, str]] = {
    "test_published_polygons_are_well_formed":
        ("커밋된 web/data 가 낡았다 — 발행은 레이크 기계에서만 된다", "no_lake"),
}

#: 재잠금이 선언된 배치에서 **빨간 것이 결과인** 축. 사유를 함께 든다.
RELOCK_AXES = {
    "golden 판정 불변":
        "판정 폐포의 코드 지문이 움직였다는 뜻이고, 그것이 곧 재잠금이 필요한 이유다. "
        "`golden.py stale` 이 rc 로 말할 때만 받는다 — 사람이 적는 값이 아니다",
    "커밋된 web/data 가 최신인가":
        "재잠금은 상류를 다시 돌리므로 커밋본이 그 뒤에 온다. 같은 실행에서 커밋된다",
    # ★ 2026-10-08 (DECISIONS §436-6). **축 둘로는 모자랐다.** 종전 둘은 「지문이
    #   움직였다」와 「커밋본이 낡았다」만 받는다. 판정 **값**이 움직이는 배치에서는
    #   그 값에서 유도되는 수가 전부 재잠금 전에 어긋난다 — 선언은 재잠금 뒤의 값이고
    #   실측은 재잠금 전의 값이다. 그 사이의 빨강은 결함이 아니라 **순서**다.
    #
    #   ★ §290-1 이 적은 그대로다 — 「관문을 붙이는 배치는 구조적으로 예습을 통과할
    #     수 없었다. 그러면 사람은 예습을 건너뛰고, 건너뛴 예습이 빨간 채로 내보냈다.」
    #     재잠금 배치도 같은 자리에 있었다. 끄는 쪽이 아니라 **받는 쪽**으로 고친다.
    #
    #   ★ 넓은 축인 것을 숨기지 않는다. 「래칫 정합」은 래칫 **전부**를 덮으므로,
    #     이 배치와 무관한 래칫이 깨져도 여기서는 안 운다. 그것을 받는 근거는
    #     **받는 쪽의 전수 verify 가 재잠금 뒤에 돈다**는 사실 하나다 — 열차는
    #     적용 → 재잠금 → 전수 순서이고, 진짜 관문은 거기다. 여기는 예습이다.
    "래칫 정합":
        "판정 값에서 유도되는 래칫은 재잠금 뒤에야 선언과 같아진다. 열차는 "
        "적용 → 재잠금 → 전수 순서이므로 받는 쪽에서는 재잠금 뒤에 이 축이 돈다",
    "발행 판정 계약":
        "발행된 판정에서 세는 축이다. 재잠금 전에는 커밋된 공개본이 옛 값이라 "
        "선언과 어긋난다 — 같은 실행에서 공개본이 다시 나고 그 뒤에 맞는다",
    # ★ 2026-10-08 (DECISIONS §436-13). 넷으로도 **모자랐다.** 첫 재잠금 배치를
    #   예습에 걸어보니 축 다섯이 새로 빨갰고 **셋이 재잠금 때문**이었다. 둘은
    #   진짜 결함이었다(기획서 표지 날짜 · `web/proposal.html`) — 그 둘을 고쳤다.
    #   선언은 **겪은 만큼만** 넓힌다: 안 겪은 축을 미리 적으면 그것이 사각지대다.
    #
    #   ★ 아래 셋은 **넓은 축**이고, 받는 근거는 각각 **더 좁게 세는 짝**이 있다는
    #     것이다. 짝이 없으면 안 받는다 — 「문서 숫자 대조」의 필드표 감사는 짝이
    #     없어서 `tests/test_doc_numbers.py` 에 **먼저 만들고** 나서 받았다.
    "pytest":
        "재잠금 대기 시험이 빨갛다. 이 축은 넓지만 **같은 실행의 `diff_tests` 가 "
        "시험 id 를 정확히 세고** `RELOCK_TESTS` 에 없는 빨강은 거기서 운다",
    "문서 숫자 대조":
        "문서가 적은 수를 golden·발행물과 댄다. 문서는 **재잠금 뒤의 수**를 적으므로 "
        "그 사이 어긋난다(§436-7). 좁은 짝 — `test_unknown_reason_counts_match_the_"
        "fingerprint` 와 `test_the_field_table_names_exactly_the_published_fields`",
    "판정 재현":
        "공개본을 `classify()` 로 되먹여 1,281건을 전부 댄다. 사유 한 칸이라도 "
        "움직이면 재잠금 전에는 깨진다 — 좁은 짝은 `test_every_reason_is_reproduced`",
}

#: 재잠금이 선언된 배치에서 **빨간 것이 결과인** 시험. 사유를 함께 든다.
#: ★ 2026-10-08 (DECISIONS §436-6). `diff_sweep` 에만 있던 면제를 시험 쪽에도 둔다 —
#:   스윕과 시험이 같은 사실을 양쪽에서 보는데 한쪽만 받아주면 배달이 못 선다.
RELOCK_TESTS = {
    "test_every_reason_is_reproduced":
        "공개본을 `classify()` 로 되먹여 댄다. 규칙을 고치면 공개본도 함께 다시 나는데 "
        "그 재생은 재잠금이 한다 — 재잠금 전에는 **한쪽만 움직인 상태**가 정상이다",
    "test_every_verdict_is_reproduced":
        "위와 같은 자리. 판정 열을 되먹여 댄다",
    "test_unknown_reason_counts_match_the_fingerprint":
        "문서가 적은 사유 수를 golden 지문과 댄다. 지문은 재잠금이 다시 쓴다 — "
        "문서는 재잠금 뒤의 수를 적어야 하고, 그 사이에는 어긋나 보인다",
    "test_the_real_tree_is_at_its_ratchets":
        "위 「래칫 정합」 축의 pytest 쪽 짝이다. 같은 사실을 두 번 본다",
    "test_the_field_table_names_exactly_the_published_fields":
        "MASTER §11 필드표 ↔ 발행된 속성. 칸을 하나 실으면 표가 **앞서 가고** "
        "산출물은 재잠금에서 따라온다. 이 시험은 그 면제를 받으려고 §436-13 에서 "
        "새로 세웠다 — 종전에는 `docnum_check.main()` 안에만 있어 **CLI 에서만** 울었다",
    "test_schema_verdict_rule_matches_code":
        "발행 스키마의 `verdict_rule` 을 `seg/geom.VERDICT_RULE` 과 댄다. 그 스키마는 "
        "`seg/report.py` 가 **낳는 것**이라 재잠금 전에는 옛 규칙표를 든다 — "
        "매개변수가 스키마 파일 둘이므로 이 이름 하나가 둘을 받는다",
}


def no_lake(root: Path) -> bool:
    """레이크가 없는 기계인가. `LAKE_ONLY` 의 판별식이다."""
    return not (root / "data" / "raw").is_dir()


PREDICATES = {"no_lake": no_lake}


def sweep_verdict(rc: int, out: str) -> tuple[set[str], dict[str, str]]:
    """`verify.sh` 의 출력에서 **빨간 축**과 **이 기계에서 아예 못 돈 축**을 걷는다.

    ★ 2026-09-28 (DECISIONS §290-3). F 배치가 빨갛게 머지 직전까지 갔고 실패 셋 중
      **둘이 「이 기계에서 못 도는 단계」였다** — 취입 계약 실물(레이크 필요)과
      CLI 표면(레이크가 없으면 도구가 일을 시작하기 전에 죽어 초록으로 보였다).
      기준선 대조는 그것을 못 잡는다: 밑동에서도 안 돌고 배치에서도 안 도니
      **새 빨간불 0** 이 정직하게 나온다. 빠진 것은 비교가 아니라 **범위**다.

    ★ 그래서 **못 돈 목록을 배달물에 적는다.** 없는 것을 있다고 하지 않기 위해서고,
      받는 쪽이 「이 배치는 이 다섯 축을 증명하지 않았다」를 읽고 시작하게 하려고다.
      `note_hard` 로 덮개 없는 생략은 이미 실패로 찍히므로 여기 남는 것은
      **덮개가 선언된 생략**뿐이다 — 그래도 이 배치가 증명한 것은 아니다.
    """
    out = ANSI.sub("", out)

    # ★ 2026-10-08 (DECISIONS §431). **축 목록은 `verify.sh` 가 선언한 것이지
    #   도구가 찍은 것이 아니다.** 요약 블록 안에서만 줍는다.
    blocks = SUMMARY_BLOCK.findall(out)
    names = {n for b in blocks for n in FAIL_LINE.findall(b)}

    # ★ 수가 둘이다 — 합계 줄이 든 수와 우리가 주운 수. **대조한다.**
    #   어긋나면 파서가 거짓말하는 것이고, 그것은 조용히 지나가면 안 된다.
    if tot := TOTALS.search(out):
        declared = int(tot.group(2))
        if declared and not blocks:
            names.add(f"★ `verify.sh` 가 실패 {declared} 을 선언했는데 "
                      "요약 블록을 못 읽었다 — delivercheck 의 파서가 낡았다")
        elif declared != len(names):
            names.add(f"★ 선언된 실패 {declared} 과 읽은 축 {len(names)} 이 다르다 — "
                      "delivercheck 의 파서가 거짓말한다")
    elif rc and not names:
        # ★ 죽었는데 이름도 합계도 못 읽었다. **0건으로 세면 빈 그물이다.**
        names.add(f"verify.sh 가 rc={rc} 로 죽었는데 요약을 못 읽었다 — {out.strip()[-300:]}")

    return names, dict(SKIP_LINE.findall(out))


def excused(name: str, wt: Path) -> str | None:
    """**판별식이 참일 때만** 면제다. 거짓이면 사유가 있어도 안 봐준다."""
    for frag, (why, pred) in LAKE_ONLY.items():
        if frag in name:
            return why if PREDICATES[pred](wt) else None
    return None


def new_red(base: set[str], after: set[str], wt: Path, label: str) -> list[str]:
    """**이 배치가 새로 빨갛게 만든 것**만. 면제는 판별식이 참일 때만 붙는다."""
    fresh = sorted(after - base)
    un = [f for f in fresh if not excused(f, wt)]
    if un:
        raise SystemExit(f"★ 이 배치가 {label} 를 새로 빨갛게 만들었다 — 배달하지 않는다\n  "
                         + "\n  ".join(un))
    return fresh


def diff_sweep(base: set[str], after: set[str], wt: Path,
               relock: bool = False) -> str:
    # ★ 재잠금을 **도구가 필요하다고 말한** 배치에서는 위 축이 빨간 것이 결과다.
    #   사람이 「재잠금 배치니까요」라고 적어서 넘기는 것이 아니라, `golden.py stale`
    #   의 rc 가 참일 때만 받는다. 거짓이면 그대로 운다.
    if relock:
        after = after - set(RELOCK_AXES)
    fresh = new_red(base, after, wt, "스윕")
    bits = [f"새 빨간불 {len(fresh)}"]
    if base:
        bits.append(f"밑동에서 이미 빨감 {len(base)}({' · '.join(sorted(base))})")
    if fixed := sorted(base - after):
        bits.append(f"이 배치가 고침 {len(fixed)}({' · '.join(fixed)})")
    if relock:
        bits.append(f"재잠금 선언으로 받은 축 {len(RELOCK_AXES)}")
    return " · ".join(bits)


def func_name(nodeid: str) -> str:
    """pytest id 에서 **함수 이름**만. `RELOCK_TESTS` 가 그 이름으로 선언한다.

    ★ 2026-10-08 (DECISIONS §436-6). 처음에 `RELOCK_TESTS` 를 함수 이름으로
      적고 **실물 id 집합에서 그대로 뺐다.** pytest 는 `tests/x.py::name[매개]`
      로 적으므로 그 차집합은 **한 번도 아무것도 안 뺐다** — 선언이 죽은
      그물이었다. 자기검사는 내가 **함수 이름을 먹였기 때문에** 통과했다.
      그물의 범위가 곧 그물의 뜻이다: 검사에 먹이는 꼴이 실물과 달라지면
      그 검사는 제 그물을 재는 게 아니라 **내 손을** 잰다.

    ★ 매개변수를 떼는 것은 의도다. 하나의 시험이 입력 여럿을 도는 것이고,
      선언은 **그 시험**에 걸린다. 파일 경로가 매개변수인 자리가 있어
      (`[data/processed/segments.schema.json]`) 꼬리까지 적으면 선언이
      부서지기 쉽다. 부분 문자열은 쓰지 않는다 — 이름은 **정확히** 맞춘다.
    """
    return nodeid.rsplit("::", 1)[-1].split("[", 1)[0]


def diff_tests(base: tuple[set[str], str], after: tuple[set[str], str],
               wt: Path, relock: bool = False) -> str:
    # ★ 2026-10-08 (DECISIONS §436-6). 스윕과 같은 규율이다 — `golden.py stale` 의
    #   rc 가 참일 때만 받는다. 사람이 「재잠금 배치니까요」라고 적어서 넘기는 것이
    #   아니다. 면제는 넓히면 사각지대가 되므로 `func_name()` 이 정확히 맞춘다.
    held = {n for n in after[0] if func_name(n) in RELOCK_TESTS}
    after_set = after[0] - held if relock else after[0]
    fresh = new_red(base[0], after_set, wt, "시험")
    bits = [after[1], f"새 빨간불 {len(fresh)}"]
    if base[0]:
        bits.append(f"밑동에서 이미 빨감 {len(base[0])}")
    if fixed := sorted(base[0] - after[0]):
        bits.append(f"이 배치가 고침 {len(fixed)}")
    if relock and held:
        bits.append(f"재잠금 선언으로 받은 시험 {len(held)}"
                    f"({' · '.join(sorted(held))})")
    return " · ".join(bits)


def bodies_missing(names: list[str]) -> list[str]:
    """배달물에 `PR_BODY.md` 가 있는가.

    ★ 2026-09-27 오전. `--body-file ""` 로 열차 8단계가 죽었다. 그날 고친 것은
      **본문이 빈 경우**였고, **본문이 아예 없는 경우**는 2단계가 죽는다.
      둘 다 보내기 전에 알 수 있었다.
    """
    return [] if NEED_BODY in names else [
        f"{NEED_BODY} 가 없다 — 열차 2단계가 이것으로 죽는다. "
        f"`--extra <경로>/{NEED_BODY}` 로 넣어라"]


def bodies_bad(out: Path, run: Callable[[list[str]], tuple[int, str]],
               py: str) -> list[str]:
    """PR 본문이 템플릿 검사를 넘는가. **보내기 전에** 본다.

    ── 왜 생겼나 (2026-09-27 저녁 · §276-1) ────────────────────
    이 도구가 밑동·폐포·산출물·스윕·pytest 를 다 재면서 **PR 본문만 안 쟀다.**
    검사기는 저장소에 있었고 그날 아침에 그것을 고치기까지 했다 — 그런데
    **보내기 전 예습에는 안 걸었다.** 배치 B 에서 본문 둘이 체크박스를 안
    골라 왕복 둘을 태웠다.

    ★ 이것이 §273-8 이 적은 그 형태다 — 배달물이 제 성질을 주장하고, 그 주장을
      사람이 썼다. 그때 「밑동」을 고쳤고 「본문」은 그대로 뒀다. **족을 하나만
      고치면 나머지가 남는다.**
    """
    bad = []
    for f in sorted(out.glob("PR_BODY*.md")):
        rc, o = run([py, str(ROOT / BODY_CHECK), "--body-file", str(f)])
        if rc:
            head = [x for x in o.strip().splitlines() if x.strip()][:6]
            bad.append(f.name + "\n      " + "\n      ".join(head))
    return bad


def collide(names: list[str]) -> list[str]:
    """같은 basename 이 둘 이상인가. 오늘 `0001-` 과 `0003-` 이 그랬다."""
    seen: dict[str, int] = {}
    for n in names:
        seen[n] = seen.get(n, 0) + 1
    return sorted(k for k, v in seen.items() if v > 1)


def tails(names: list[str]) -> list[str]:
    """번호를 뗀 꼬리가 겹치는가 — 이름이 달라도 같은 커밋이면 두 번 얹는다.

    ★ 2026-09-28 (§278-5). 접두사(`fire-lane-`)도 같이 뗀다. 안 떼면 접두사 붙은
      것과 안 붙은 것이 **다른 꼬리**로 보여 같은 커밋 둘을 못 잡는다.
    """
    seen: dict[str, list[str]] = {}
    for n in names:
        seen.setdefault(re.sub(r"^(?:[a-z-]+-)?\d+-", "", n), []).append(n)
    return sorted(f"{k}: {' · '.join(v)}" for k, v in seen.items() if len(v) > 1)


def _message_of(p: Path, text: str) -> str:
    """패치에서 **커밋 메시지**만. diff 는 뺀다.

    ★ 2026-09-27. 첫 배달에서 이 검사가 **제 금지 목록 선언**을 잡았다 —
      `FORBIDDEN = ("Co-Authored-By: Claude", …)` 이 diff 에 들어 있었기 때문이다.
      규약은 「**커밋 메시지**에 서명이 없어야 한다」이지 「저장소 어디에도 그 글자가
      없어야 한다」가 아니다. 그렇게 넓히면 그 규약을 **무는 검사 자체**를 못 쓴다.
    ★ `git format-patch` 는 메시지와 diff 를 `---` 한 줄로 가른다.
    """
    if p.suffix != ".patch":
        return text
    out = []
    for line in text.splitlines():
        if line.rstrip() == "---":
            break
        out.append(line)
    return "\n".join(out)


def forbidden(paths: list[Path]) -> list[str]:
    bad = []
    for p in paths:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        head = _message_of(p, t)
        for s in FORBIDDEN:
            if s in head:
                bad.append(f"{p.name}: {s}")
    return bad


def zip_items(out: Path, z: Path) -> list[Path]:
    """zip 에 넣을 파일. **zip 자신은 뺀다.**

    ── 왜 생겼나 (2026-09-29 · §294) ───────────────────────────
    종전 코드는 `ZipFile(z, "w")` 로 파일을 **만든 뒤** `out.iterdir()` 를
    불렀다. `--zip` 이 `--out` 안을 가리키면 그 목록에 zip 자신이 들어가고,
    `zf.write` 가 그것을 읽는 동안 파일이 자란다 — **끝나지 않는다.**
    실기에서 4.5GB 까지 갔고 멈춘 것은 도구가 아니라 사람이다.

    ★ `--zip $OUT/x.zip` 은 **자연스러운 씀씀이다.** 배달물 한 자리에 모아
      두는 것이 이 도구의 뜻이다. 사람이 피하게 하지 않고 도구가 막는다.

    ★ 목록을 **열기 전에** 고정하는 것이 고침의 핵이다. 이름으로만 빼면
      `--zip ../h/x.zip` 처럼 같은 파일을 다른 글자로 가리킬 때 다시 샌다.
      `resolve()` 로 실물을 대고, 열기 전에 목록을 뜬다.
    """
    zr = z.resolve()
    return [f for f in sorted(out.iterdir())
            if f.is_file() and f.resolve() != zr]


def zip_items_broken() -> list[str]:
    """`zip_items` 가 죽었나. 양방향으로 잰다 — 자신은 빠지고 나머지는 안 빠진다.

    ★ 한쪽만 재면 「전부 빼기」가 통과한다. 경로 꼴(`resolve()`)까지 재는
      전수는 `tests/test_delivercheck.py` 가 든다.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        o = Path(td)
        for n in ("fire-lane-0001-x.patch", "EXPECT", "PR_BODY.md"):
            (o / n).write_text("x", encoding="utf-8")
        z = o / "fire-lane-batch.zip"
        z.write_text("", encoding="utf-8")
        got = [f.name for f in zip_items(o, z)]
    bad = []
    if z.name in got:
        bad.append("zip 이 제 목록에 든다 — 자기를 압축한다(§294)")
    if len(got) != 3:
        bad.append(f"zip 목록이 3개여야 하는데 {len(got)}개다 — 멀쩡한 것을 뺐다")
    return bad
