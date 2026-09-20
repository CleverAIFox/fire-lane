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
import subprocess
import sys
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
# ★ 정본은 **선언 한 줄**이다. 값을 명령줄에 직접 적지 않는다.
COV_HOME = re.compile(r"^COV_MIN=(\d+)\s*$", re.M)
# ★ 명령줄에 박힌 **리터럴**. 하나라도 있으면 집이 둘이다.
COV_LITERAL = re.compile(r"fail[-_]under[=\s]+(\d+)")


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
    ★ 2026-09-19 **범위를 넓혔다.** 종전 이 시험은 `--fail-under=<숫자>`
      리터럴만 셌다. 그래서 **단계 이름**(「커버리지 래칫 14%」)과
      `pyproject` 주석에 같은 숫자가 또 살아 있는 것을 못 봤다 —
      이 시험 자신이 「범위가 이름보다 좁은」 그 족이었다(W3-8 · W4-8 ·
      W3-16 · W4-9 와 같은 형태). 지금은 **선언 한 줄(`COV_MIN=`)만
      허용하고 명령줄 리터럴을 금지한다.**
    """
    homes: list[tuple[str, int]] = []
    literals: list[str] = []
    for pat in EXEC_GLOBS:
        for p in sorted(ROOT.glob(pat)):
            body = _strip_comments(p.read_text(encoding="utf-8"))
            rel = str(p.relative_to(ROOT))
            for m in COV_HOME.finditer(body):
                homes.append((rel, int(m.group(1))))
            for m in COV_LITERAL.finditer(body):
                literals.append(f"  {rel}  {m.group(0)}")

    assert not literals, (
        "커버리지 문턱을 명령줄에 **리터럴로** 적었다.\n"
        + "\n".join(literals)
        + "\n  정본은 `COV_MIN=<숫자>` 선언 한 줄이다. 명령줄은 그것을 읽는다.\n"
        + "  리터럴을 허용하면 집이 둘이 되고, 한쪽만 올라간다(PLAN §13 W3-11).")

    assert len(homes) == 1, (
        "커버리지 래칫의 정본 선언(`COV_MIN=`)이 하나가 아니다.\n"
        + "".join(f"  {where}  COV_MIN={n}\n" for where, n in homes)
        + "  없으면 문턱이 사라진 것이고, 둘이면 한쪽만 올라간다.")

    where, n = homes[0]

    # ★ 단계 이름에 숫자를 되돌려 박는 것도 막는다. 이름은 검사 대상이
    #   아니라 **조용히 낡는다** — 실제로 9/15 에 14 로 박아두고 실물이
    #   24% 가 되도록 나흘간 아무도 몰랐다.
    named = re.findall(r'step "커버리지 래칫[^"]*?(\d+)[^"]*"',
                       VERIFY.read_text(encoding="utf-8"))
    assert not named, (
        f"단계 이름에 래칫 숫자({named[0]})를 적었다.\n"
        "  이름은 아무도 검사하지 않으므로 조용히 낡는다.\n"
        f"  숫자는 {where} 의 `COV_MIN` 한 곳에만 둔다.")
    bad = []
    for doc in LIVE_DOCS:
        text = doc.read_text(encoding="utf-8")
        for m in re.finditer(
                r"COV_MIN\s*=\s*(\d+)|fail[-_]under[=\s]+(\d+)|커버리지 래칫\s*(\d+)\s*%",
                text):
            if _exempt(text, m.start()):
                continue                       # 날짜 붙은 실측 기록이라 선언했다
            said = int(m.group(1) or m.group(2) or m.group(3))
            if said != n:
                line = text[: m.start()].count("\n") + 1
                bad.append(f"  {doc.relative_to(ROOT)}:{line}  "
                           f"「{m.group(0)}」 인데 {where} 는 {n} 이다")

    assert not bad, (
        "문서가 적은 커버리지 래칫이 실행형과 다르다.\n"
        + "\n".join(bad)
        + f"\n  정본은 {where} 하나다. 올릴 때 문서도 같이 움직인다.")


def test_gate_parity_ratchet_has_one_home() -> None:
    """`gate_parity` 래칫이 **한 곳**에 사는가 (W3-11).

    ★ 2026-09-18 에 `refcheck` 를 CI 에서 빼며 래칫을 19 로 올렸는데
      `verify.sh` 만 고쳤다. `contract.yml` 은 18 인 채였고 **로컬 초록 ·
      CI 빨강**이 났다. 숫자가 두 곳에 살면 한쪽만 올라간다.
    ★ 지금 집은 `gate_parity.py` 의 `RATCHET` 하나이고 부르는 쪽은 인자를
      안 적는다. 커버리지 래칫(`COV_MIN`)과 같은 구조다.
    """
    gp = ROOT / "tools" / "gate_parity.py"
    homes = re.findall(r"^RATCHET\s*=\s*(\d+)\s*$", gp.read_text(encoding="utf-8"), re.M)
    assert len(homes) == 1, (
        f"`gate_parity.py` 의 `RATCHET` 선언이 {len(homes)}개다.\n"
        "  없으면 문턱이 사라진 것이고, 둘이면 한쪽만 올라간다.")

    # ★ 부르는 쪽이 숫자를 적으면 그 순간 집이 둘이 된다.
    bad = []
    for pat in ("tools/*.sh", ".github/workflows/*.yml"):
        for p in sorted(ROOT.glob(pat)):
            body = _strip_comments(p.read_text(encoding="utf-8"))
            for m in re.finditer(r"gate_parity\.py[^\n|&;]*?--max\s+(\d+)", body):
                bad.append(f"  {p.relative_to(ROOT)}  {m.group(0).strip()}")
    assert not bad, (
        "`gate_parity` 래칫을 부르는 쪽에 숫자로 적었다.\n" + "\n".join(bad)
        + f"\n  정본은 `tools/gate_parity.py` 의 `RATCHET`({homes[0]}) 하나다.\n"
        + "  인자 없이 부르면 그 값을 쓴다. 적으면 한쪽만 올라간다(W3-11).")

    # ★ 단계 이름에 숫자를 되돌려 박는 것도 막는다 — 이름은 아무도 검사하지
    #   않으므로 조용히 낡는다(커버리지 래칫이 그렇게 나흘간 낡았다).
    named = re.findall(r'step "관문 동등[^"]*?(\d+)[^"]*"',
                       VERIFY.read_text(encoding="utf-8"))
    assert not named, (
        f"「관문 동등」 단계 이름에 래칫 숫자({named[0]})를 적었다.\n"
        "  이름은 검사 대상이 아니라 조용히 낡는다.")


def test_ci_exemptions_are_declared_with_reasons() -> None:
    """면제가 **사유와 함께** 선언돼 있는가 (W3-10).

    ★ 판정을 여기서 다시 구현하지 않는다 — `gate_parity.py` 가 정본이고
      이 시험은 그것을 부를 뿐이다. 파싱 규칙을 두 곳에 적으면 2족이 된다.
    ★ `gate_parity` 는 죽은 면제(없는 검사기 · CI 가 이미 도는 것 · 사유가
      너무 짧은 것)에서 rc=1 을 낸다. 여기서는 그 rc 와 출력만 본다.
    """
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gate_parity.py")],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, (
        "`gate_parity` 가 빨갛다 — 미선언 차집합이 래칫과 다르거나 죽은 면제가 있다.\n"
        + r.stdout[-1800:])
    assert "선언된 면제" in r.stdout, (
        "면제 선언을 0개 읽었다 — `# ci-exempt:` 파서가 죽었을 수 있다.\n"
        + r.stdout[-800:])


def test_discrete_ratchets_fail_when_slack() -> None:
    """이산 래칫이 **미달에서도 실패**하는가 (W4-9).

    ★ 2026-09-19 에 커버리지 래칫이 14 인데 실물이 24% 인 것을 **나흘간
      아무도 몰랐다.** 게이트는 그동안 계속 초록이었다 — 초록은 「문턱을
      지켰다」는 뜻이지 「문턱이 아직 의미 있다」는 뜻이 아니다.
      **느슨해진 래칫은 초록으로 위장한다.**
    ★ 여기서 실제로 돌리는 것은 `dupcheck` **하나**다. 나머지 셋 중
      `vintage_check` · `firelane.prep` 는 레이크를 요구해 이 자리에서도
      CI 에서도 못 돈다(`verify.sh` 의 `# ci-exempt:` 가 그 사유를 든다),
      `gate_parity` 는 처음부터 양방향이라 위 시험들이 이미 덮는다.
      **범위가 좁고 그것을 여기 선언한다** — 좁은 것 자체보다 선언 안 된
      것이 나쁘다(W3-8 · W4-8 과 같은 족).
    """
    dup = ROOT / "tools" / "dupcheck.py"
    base = [sys.executable, str(dup), "--min", "40"]

    tight = subprocess.run([*base, "--max", "1"], capture_output=True,
                           text=True, cwd=ROOT, timeout=300)
    assert tight.returncode == 0, (
        "`dupcheck --min 40 --max 1` 이 빨갛다 — 사본군이 움직였다.\n"
        + tight.stdout[-800:])

    slack = subprocess.run([*base, "--max", "9"], capture_output=True,
                           text=True, cwd=ROOT, timeout=300)
    assert slack.returncode != 0, (
        "이산 래칫이 **미달에서 통과했다.**\n"
        f"  `dupcheck --max 9` 가 rc={slack.returncode} 로 끝났다.\n"
        "  느슨한 상한은 되돌아갈 자리를 남기고, 그것이 초록으로 위장한다.\n"
        "  미달이면 실패해야 한다(W4-9).\n" + slack.stdout[-500:])


def test_coverage_advice_floors_instead_of_rounding() -> None:
    """래칫을 「조여라」고 권할 때 **반올림한 값을 권하지 않는가.**

    ★ 2026-09-20 실물. 메시지가 `coverage report --format=total` 을 그대로
      읽어 「COV_MIN 을 24 로 조여라」라고 말했다. 그런데 그 값은 **반올림**
      이고 실측은 **23.75%** 였다. 시키는 대로 조이면 `--fail-under=24` 가
      23.75 를 떨어뜨려 **다음 실행부터 빨갛다.**

    ★ 바로 위 주석은 「화면의 24% 는 반올림이라 실제가 23.5 일 수 있다」를
      이미 알고 있었다. **아는 것이 강제되는 자리에 없으면 없는 것과 같다**
      (MASTER §17). 그래서 주석이 아니라 여기가 든다.
    """
    src = VERIFY.read_text(encoding="utf-8")
    m = re.search(r'step "커버리지 래칫".*?\n(?=scope |step |\n#)', src, re.S)
    assert m, "커버리지 래칫 단계를 못 읽었다"
    body = m.group(0)

    assert "--precision" in body, (
        "래칫 권고가 `--precision` 없이 `--format=total` 을 읽는다.\n"
        "  그 값은 반올림이라 실측 23.75% 가 24 로 보이고,\n"
        "  그대로 조이면 `--fail-under` 가 다음 실행을 떨어뜨린다.")
    assert "%%.*" in body, (
        "소수를 **내림**하는 자리가 없다.\n"
        "  `FLOOR=${PCT%%.*}` 처럼 정수부만 취해야 권고가 안전하다.")
    # ★ 되돌림 — 내림한 값이 아니라 원래 값을 권하면 안 된다.
    assert 'COV_MIN 을 ${FLOOR}' in body, (
        "권고가 내림값(`$FLOOR`)이 아닌 것을 가리킨다.\n"
        "  반올림된 `$PCT` 를 권하면 2026-09-20 의 사고가 그대로 돌아온다.")
