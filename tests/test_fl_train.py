"""배달 열차가 **제 상태를 재는가.**  (DECISIONS §295 · §296)

★ 왜 이 파일이 따로 있나 (2026-09-29). `tools/fl.sh` 는 배치를 적용 · 검증 ·
  머지 · 방송까지 끌고 가는데, **제가 한 일을 재지 않고 주장하고 있었다.**
  실기에서 셋이 한 줄로 이어져 머지 뒤 배달이 멈췄다 —

    §295-1  `git commit` 종료코드를 안 보고 `git rev-parse HEAD` 를 찍었다
    §295-2  `+미커밋` 인 트리로 전수 초록을 받고 push 했다
    §295-3  지문이 무는 `uv.lock` 을 재잠금이 안 올렸다
    §296    포장물을 치운 **뒤** 그 자리를 읽었다

  `tests/test_batch_tools.py` 는 「배치 도구가 어디 사는가 · 무엇을 집는가」를
  든다. 이 파일이 드는 것은 **열차가 제 주장을 재는가**이고 다른 물음이다.

★ 정적 검사다 — 열차를 실제로 돌리지 않는다. 돌리려면 원격 · CI · 머지 권한이
  필요하고 그것은 시험이 가질 것이 아니다. 대신 **고침이 되돌려지면 운다.**

IN    tools/fl.sh
OUT   없음
밖    열차의 흐름(단계 순서 · 인자 해석)은 여기서 판단하지 않는다.
      여기 잠그는 것은 **재는 자리가 있는가**와 그 자리의 순서뿐이다.
"""
from __future__ import annotations

import pathlib

T = pathlib.Path(__file__).resolve().parents[1] / "tools"


def _fl() -> str:
    return (T / "fl.sh").read_text(encoding="utf-8")


def _nocomment(src: str) -> str:
    """주석은 걷는다 — 「왜 그것을 안 쓰는가」를 적은 줄까지 위반으로 세면 사유를 못 적는다."""
    return "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))


# ── §295 · 열차가 「했다」고 주장하지 말고 재는가 ────────────────


def _relock_chain(src: str) -> str:
    """4b 가 사슬을 돌리고 지문을 잠그는 자리 — 커밋을 앉히기 **전**까지."""
    i = src.index('tools/remeasure.py')
    j = src.index('git diff --quiet -- data/golden', i)
    return src[i:j]


def _relock_block(src: str) -> str:
    """4b 재잠금이 커밋을 앉히는 자리."""
    i = src.index('git add data/golden data/processed web/data')
    j = src.index('재잠금 커밋 $(git rev-parse --short HEAD)', i)
    return src[i:j]


def test_재잠금은_종료코드가_아니라_HEAD_가_움직였는지_잰다():
    """★ 실기 2회. 훅이 커밋을 죽였는데 `git rev-parse HEAD` 를 찍어

    「OK 재잠금 커밋 <직전 패치>」가 나왔고, 재잠금 없는 가지가 push 돼
    CI 가 「잠긴 코드 지문과 지금 코드가 다르다」로 죽었다(§295-1).
    종료코드만 봐도 부족하다 — 훅이 0 으로 죽는 경우가 남는다.
    """
    body = _nocomment(_relock_block(_fl()))
    assert "git rev-parse HEAD" in body, (
        "재잠금 앞뒤로 HEAD 를 안 읽는다 — 커밋이 앉았는지 못 잰다")
    assert body.count("git rev-parse HEAD") >= 2, (
        "HEAD 를 한 번만 읽는다 — **움직였는지**를 재려면 앞과 뒤를 봐야 한다")
    assert "die" in body, "커밋이 안 앉았을 때 멈추지 않는다"


def test_재잠금은_uv_lock_도_함께_앉힌다():
    """코드 지문이 `uv.lock` 의 sha 를 물고 있다(`shardseal.code_print`).

    빼면 ① 지문과 잠금이 따로 앉아 CI 가 죽고 ② 미스테이지가 남아
    pre-commit 의 stash 가 훅 자동수정과 충돌해 커밋이 아예 안 앉는다(§295-3).
    """
    body = _nocomment(_relock_block(_fl()))
    assert "git add uv.lock" in body, (
        "`uv.lock` 을 안 올린다 — 지문이 그것을 물고 있어 따로 앉으면 CI 가 죽는다")


def test_재잠금은_깃발이_아니라_지문에게_잠겼는지_묻는다():
    """★ 실기 1회 (§388). 이 자리가 `--measured` 가 붙었는지만 보고

    `RELOCK_DONE=1` 을 세워 `golden.py lock` 을 건너뛰었다. 그런데
    `remeasure.py` 는 산출물이 안 움직이면 사슬을 거절하고 **0 으로**
    돌아선다 — 깃발만 서고 아무도 안 잠갔다. §262 가 PR 산문에서
    걷어낸 판단이 명령줄 깃발로 되살아난 것이다.

    잠그기로 들어선 갈래 안에서는 **지문에게 다시 물어야** 한다.
    """
    body = _nocomment(_relock_chain(_fl()))
    assert "RELOCK_DONE" not in body, (
        "`RELOCK_DONE` 이 되살았다 — 잠겼는지를 깃발로 판단하면 안 된다")
    assert "golden.py stale" in body, (
        "사슬 뒤에 지문을 다시 안 묻는다 — 사슬이 거절했을 때를 못 잡는다")
    assert body.index("remeasure.py") < body.index("golden.py stale"), (
        "사슬보다 먼저 묻는다 — 사슬이 잠갔는지를 재려면 그 뒤여야 한다")
    assert "golden.py lock" in body, "낡았을 때 잠그는 자리가 없다"


def test_초록_뒤_더러운_트리로는_push_하지_않는다():
    """**검증한 트리와 보내는 트리가 같아야 한다.**

    실기에서 새 지문이 작업 트리에만 있었고, verify 는 그것을 보고 72/72
    초록을 냈고, 6단계가 옛 지문이 든 커밋을 push 했다(§295-2).
    """
    src = _fl()
    i = src.index('ok "전수 초록"')
    j = src.index("# ══ 6. PR")
    body = _nocomment(src[i:j])
    assert "git status --porcelain" in body, (
        "초록과 push 사이에서 작업 트리를 안 본다 — 검증한 것과 보내는 것이 갈린다")
    assert "die" in body, "더러운데 멈추지 않는다"


def test_그_관문이_무시_대상_때문에_늘_울지는_않는다():
    """거짓 빨간불이면 사람이 검사를 끈다(§69).

    `--untracked-files=no` 가 없으면 verify 가 쓰는 무시 대상까지 세서
    **매 배치가 막힌다.**
    """
    src = _fl()
    i = src.index('ok "전수 초록"')
    j = src.index("# ══ 6. PR")
    body = _nocomment(src[i:j])
    assert "--untracked-files=no" in body, (
        "미추적까지 세면 verify 산출물에 매번 걸린다 — 추적 파일만 본다")


# ── §296 · 치우는 자리와 읽는 자리의 순서 ───────────────────────


def test_포장물을_치우기_전에_본문을_챙긴다():
    """★ 실기 2026-09-29. 머지는 끝났는데 8단계가 죽었다.

    `archive_inbox` 가 `PR_BODY*.md` 를 `_applied/` 로 옮긴 **뒤** 8단계가
    옮겨진 자리를 읽었다(§296). `--resume` 경로는 `$WORK` 를 안 채우므로
    치우면 손에 남는 것이 없다. 치우기 전에 챙겨야 한다.
    """
    src = _fl()
    i = src.index("archive_inbox() {")
    j = src.index("\n}", i)
    body = _nocomment(src[i:j])
    cp = body.find('cp -f "$f" "$WORK/"')
    mv = body.find('mv -f "$f" "$done_/"')
    assert cp != -1, "본문을 $WORK 로 안 챙긴다 — 치우면 8단계가 읽을 것이 없다"
    assert mv != -1, "본문을 _applied/ 로 옮기는 자리를 못 찾았다 — 시험이 낡았다"
    assert cp < mv, "챙기기가 옮기기보다 **뒤에** 있다 — 순서가 거꾸로다(§296)"


def test_챙긴_뒤_BODY_가_남은_자리를_가리킨다():
    """`$BODY` 가 INBOX 를 가리킨 채로 치우면 매달린 경로가 된다."""
    src = _fl()
    i = src.index("archive_inbox() {")
    j = src.index("\n}", i)
    body = _nocomment(src[i:j])
    assert 'BODY="$WORK/PR_BODY.md"' in body, (
        "치운 뒤 `$BODY` 를 다시 가리키지 않는다 — 8단계의 대체 본문이 매달린다")
