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
    """번호를 뗀 꼬리가 겹치는가 — 이름이 달라도 같은 커밋이면 두 번 얹는다."""
    seen: dict[str, list[str]] = {}
    for n in names:
        seen.setdefault(re.sub(r"^\d+-", "", n), []).append(n)
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
