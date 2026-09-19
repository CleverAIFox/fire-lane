"""문서 ↔ `verify.sh` — 단계 인용과 래칫 숫자의 집.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-19. 같은 병의 인스턴스 셋이 한 자리에서 나왔다.

  1. **총수가 셋으로 갈렸다.** `README.md` 와 `MASTER §12` 는 「42단계 전부」
     라고 적는데 실물은 **44** 였고, 핸드오프는 44, 진행 표시의 분모는 45 를
     찍었다. 단계를 더한 사람이 문서를 안 고쳤고 우는 곳이 없었다.

  2. **문서가 단계를 「위치」로 인용했다.** `MASTER §12` 의 **강제자 칸**이
     「`tools/verify.sh` 42단계 「배포에 내비 빌드」」라고 적는다. 그 앞에
     단계를 하나 끼우거나 빼면 **강제자 칸이 다른 검사를 가리킨다.**
     ★ 이것은 `PLAN §13 W3-5`(`dms` 절 ID 가 위치 기반)와 **같은 족**이다 —
     키가 위치면 중간에 하나를 끼운 순간 뒤가 전부 밀린다. `dms` 는 그것이
     49절로 드러났고, 여기서는 **강제자가 조용히 다른 것을 가리키는 것**으로
     드러난다. 후자가 더 나쁘다 — 아무것도 안 울기 때문이다.

  3. **커버리지 래칫 숫자가 집이 둘이었다.** 실행형은 `verify.sh` 한 곳,
     그런데 `MASTER §12` 산문이 같은 숫자를 손으로 또 적는다. `W3-11` 이
     「래칫 숫자가 두 곳에 산다」로 적은 것과 같은 형태다.

★ 인스턴스가 아니라 **클래스**를 본다. 「42 를 44 로 고쳤는가」를 묻지 않고
  **「문서가 위치로 인용하는가」** 와 **「숫자의 집이 하나인가」** 를 묻는다.
  그래서 다음에 단계를 더해도 사람이 기억할 필요가 없다.

★ `DECISIONS.md` 와 `tools/**` 의 주석은 **대상이 아니다.** 거기 적힌
  「39단계」·「42단계」는 날짜가 붙은 **작성 시점 기록**이라 지금 틀린 것이
  옳다. `docnum_check` 가 §13~§16 을 `HIST` 로 잘라내는 것과 같은 원리다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify.sh"

# ★ 현재형 문서만 본다. 머리말 ★ 참조.
LIVE_DOCS = [ROOT / "README.md", ROOT / "docs" / "MASTER.md", ROOT / "docs" / "PLAN.md"]

# `42단계` · `42 단계`
ORDINAL = re.compile(r"(\d+)\s*단계")
# 그 인용이 verify.sh 를 가리키는가 — 앞뒤 창으로 본다
NEAR = 90
# 총수 주장 형태. 이것만 허용하고 나머지 위치 인용은 막는다.
TOTAL_FORM = re.compile(r"(\d+)\s*단계\s*전부")

# 래칫 숫자가 실행형으로 사는 곳
EXEC_GLOBS = ("tools/*.sh", "tools/*.py", ".github/workflows/*.yml")
FAIL_UNDER = re.compile(r"fail[-_]under[=\s]+(\d+)")


def _strip_comments(text: str) -> str:
    """`#` 주석을 걷는다. 주석의 단계 번호는 인용이 아니라 기록이다."""
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _exempt(text: str, pos: int) -> bool:
    """그 줄이 `<!--stale-ok-->` 로 면제를 선언했는가.

    ★ 새 마커를 만들지 않는다. `docnum_check` 가 「이 옛 숫자는 실수가
      아니다」를 적는 데 이미 쓰는 것을 그대로 쓴다 — 마커를 다는 일 자체가
      기록이 된다. **미선언이 실패다**(`doc_fsck ⑥` · `W3-10` 과 같은 규율).
    """
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    line = text[start:] if end < 0 else text[start:end]
    return "<!--stale-ok-->" in line


def _steps() -> tuple[list[str], list[str]]:
    """(전수 실행에서 도는 단계, 조건부로만 도는 단계).

    ★ 손목록을 두지 않는다. 조건부 단계는 **그 단계를 켜는 조건과 같은
      구조**로 가른다 — `if [ -n "$ONLY" ] || [ "$FAST" = "1" ]` 블록 안에
      있는 `step` 은 전수 실행에서 안 돈다.
    ★ 같은 이름이 if/elif 두 갈래에 적힌 것은 **하나만 돈다.** 이름으로
      유일화한다(verify.sh 자신이 TOTAL 을 그렇게 센다).
    """
    raw = VERIFY.read_text(encoding="utf-8")
    guard_at = raw.find('if [ -n "$ONLY" ] || [ "$FAST" = "1" ]')
    assert guard_at > 0, "verify.sh 의 `부분 실행` 안전장치를 못 찾았다"

    full: list[str] = []
    conditional: list[str] = []
    for m in re.finditer(r'^[ \t]*step "([^"]*)"', raw, re.M):
        name = m.group(1)
        bucket = conditional if m.start() > guard_at else full
        if name not in bucket:
            bucket.append(name)
    return full, conditional


def test_step_parser_is_not_an_empty_net() -> None:
    """★ 빈 그물인가(`deadcheck` ①). 추출기가 죽으면 아래 둘이 조용히 통과한다."""
    full, conditional = _steps()
    assert len(full) > 30, f"verify.sh 에서 단계를 {len(full)}개만 찾았다 — 추출기가 죽었다"
    assert "pytest" in full, "verify.sh 가 pytest 를 부르는데 못 잡았다"
    assert conditional, "조건부 단계를 0개 찾았다 — `부분 실행` 안전장치가 사라졌거나 못 읽는다"


def test_documented_step_total_matches_reality() -> None:
    """문서가 적은 「N단계 전부」가 실물과 같은가."""
    full, _ = _steps()
    actual = len(full)

    bad: list[str] = []
    for doc in LIVE_DOCS:
        text = doc.read_text(encoding="utf-8")
        for m in TOTAL_FORM.finditer(text):
            window = text[max(0, m.start() - NEAR): m.end() + NEAR]
            if "verify" not in window:
                continue
            if int(m.group(1)) != actual:
                line = text[: m.start()].count("\n") + 1
                bad.append(f"  {doc.relative_to(ROOT)}:{line}  "
                           f"「{m.group(0)}」 인데 실물은 {actual}단계다")

    assert not bad, (
        "문서가 적은 verify 단계 총수가 실물과 다르다.\n"
        + "\n".join(bad)
        + f"\n  실물 = `step \"…\"` 이름 유일화 {actual}개 (조건부 단계 제외).\n"
        + "  단계를 더하거나 빼면 이 숫자도 같이 움직인다.\n"
        + "  낡은 총수는 「전부 돌았는가」를 아무도 못 세게 만든다.")


def test_docs_do_not_cite_verify_steps_by_position() -> None:
    """현재형 문서가 verify 단계를 **위치 번호**로 인용하는가.

    ★ `PLAN §13 W3-5` 와 같은 족이다. 키가 위치면 중간에 하나를 끼운 순간
      뒤가 전부 밀리고, **강제자 칸이 다른 검사를 가리켜도 안 운다.**
    ★ 닫는 법은 `W3-5` 와 같다 — 위치가 아니라 **이름**으로 든다.
    """
    full, conditional = _steps()
    known = set(full) | set(conditional)

    bad: list[str] = []
    for doc in LIVE_DOCS:
        text = doc.read_text(encoding="utf-8")
        for m in ORDINAL.finditer(text):
            if TOTAL_FORM.match(text, m.start()):
                continue                       # 총수 주장은 위 시험이 본다
            window = text[max(0, m.start() - NEAR): m.end() + NEAR]
            if "verify.sh" not in window and "verify " not in window:
                continue
            if _exempt(text, m.start()):
                continue                       # 날짜 붙은 실측 기록이라 선언했다
            line = text[: m.start()].count("\n") + 1
            bad.append(f"  {doc.relative_to(ROOT)}:{line}  「{m.group(0)}」")

    assert not bad, (
        "현재형 문서가 verify 단계를 **위치 번호**로 인용한다.\n"
        + "\n".join(bad)
        + "\n  위치는 키가 아니다 — 앞에 단계를 하나 끼우면 뒤가 전부 밀리고,\n"
        + "  그때 **강제자 칸이 다른 검사를 가리켜도 아무것도 안 운다.**\n"
        + "  (PLAN §13 W3-5 와 같은 족)\n"
        + "  이름으로 들어라 — 예: `verify.sh` 의 「배포에 내비 빌드」 단계.\n"
        + f"  지금 있는 이름 {len(known)}개는 `grep 'step \"' tools/verify.sh` 로 본다.\n"
        + "  날짜가 붙은 실측 기록이면 DECISIONS 에 적는다(그 파일은 대상이 아니다).")


def test_coverage_ratchet_has_one_home() -> None:
    """커버리지 래칫 숫자가 실행형으로 **한 곳**에 살고, 문서가 그것과 같은가.

    ★ `PLAN §13 W3-11` 의 커버리지 쪽이다. 실행형이 둘이면 한쪽만 고쳐
      「로컬 초록 · CI 빨강」이 난다 — 2026-09-18 에 실제로 났다.
    """
    homes: list[tuple[str, int]] = []
    for pat in EXEC_GLOBS:
        for p in sorted(ROOT.glob(pat)):
            for m in FAIL_UNDER.finditer(_strip_comments(p.read_text(encoding="utf-8"))):
                homes.append((str(p.relative_to(ROOT)), int(m.group(1))))

    assert len(homes) == 1, (
        "커버리지 래칫의 실행형 집이 하나가 아니다.\n"
        + "".join(f"  {where}  --fail-under={n}\n" for where, n in homes)
        + "  숫자가 두 곳에 살면 한쪽만 올라가고, 그것이 곧\n"
        + "  「로컬 초록 · CI 빨강」이다(PLAN §13 W3-11).")

    where, n = homes[0]
    bad = []
    for doc in LIVE_DOCS:
        text = doc.read_text(encoding="utf-8")
        for m in re.finditer(r"fail[-_]under[=\s]+(\d+)|커버리지 래칫\s*(\d+)\s*%", text):
            if _exempt(text, m.start()):
                continue                       # 날짜 붙은 실측 기록이라 선언했다
            said = int(m.group(1) or m.group(2))
            if said != n:
                line = text[: m.start()].count("\n") + 1
                bad.append(f"  {doc.relative_to(ROOT)}:{line}  "
                           f"「{m.group(0)}」 인데 {where} 는 {n} 이다")

    assert not bad, (
        "문서가 적은 커버리지 래칫이 실행형과 다르다.\n"
        + "\n".join(bad)
        + f"\n  정본은 {where} 하나다. 올릴 때 문서도 같이 움직인다.")
