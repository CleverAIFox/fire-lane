"""`doc_fsck ⑤` — 한시로 정한 것이 한시로 끝났는가.  (§258-19)

IN    docs/* · tools/* 의 한시 표기(배너 · TODO)
OUT   결함 문장 목록 (비면 통과)
밖    기한 **안**에 끝났는가는 `check_deferred`(⑧) 가 든다. 여기는 지난 것만 본다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from docfsck import _today

# ── 5. 만료 — 한시가 한시로 끝나는가 ──────────────────────────
# ★ 2026-09-03. 회수 완료. bypass_actors 를 비우고 ADMINS 를 줄이고
#   BYPASS 카드를 지웠으므로 이 게이트는 걸 대상이 없다.
#
# ★ **절과 기계는 남긴다.** 번호는 자산이고(MASTER §0-2), 다음 한시
#   예외가 생기면 아래 두 줄만 채우면 즉시 시계가 돈다. 코드를 지우면
#   다음 사람이 `§80` 처럼 회수를 사람 기억에 맡긴다.
#
#     DEPARTURE = "YYYY-MM-DD"   회수 기한
#     LEAVING   = "<핸들>"        ruleset_check.ADMINS 에서 빠져야 하는 사람
DEPARTURE: str | None = None
LEAVING: str | None = None

_BANNER = """
  ████████████████████████████████████████████████████████████
  ██                                                        ██
  ██   기한이 지난 예외가 살아 있다. 이건 경고가 아니다.      ██
  ██   회수하기 전에는 이 검사가 안 풀린다.                  ██
  ██                                                        ██
  ████████████████████████████████████████████████████████████
"""


_TODO = """
  ── 할 일 (전부 끝나야 초록이 된다) ─────────────────────────
   1  GitHub 룰셋에서 bypass_actors 를 전부 비운다
        Settings → Rules → main · dev · part/* → Bypass list 비우기
        확인:  uv run python tools/ruleset_check.py
   2  tools/ruleset_check.py 의 ADMINS 에서 이탈자를 뺀다
   3  @woongtopia/gis 팀에서 이탈자를 뺀다
        CODEOWNERS 파일은 고치지 않는다 — 팀에서 빼면 리뷰가 자동으로
        남은 gis 팀원에게 넘어간다(MASTER §8)
   4  web/playbook.html 의 BYPASS 카드를 통째로 지운다
   5  MASTER §12-1 의 회수일 서술을 지운다
   6  doc_fsck.py 의 DEPARTURE · LEAVING 두 줄을 지운다  ← 이 검사를 끈다
  ────────────────────────────────────────────────────────────
"""


def check_expiry() -> list[str]:
    """기한이 지난 예외가 남아 있는가.

    ★ 2026-09-02. `§80` 이 bypass 를 **한시** 부여하고 회수를 사람 기억에
      맡겼다. 한시가 한시로 끝나려면 시계가 있어야 한다. 여기 있는 것은
      알림이 아니라 **게이트**다 — 날짜가 지나면 CI 가 빨간불이 되고
      회수하기 전에는 안 풀린다.

    ★ 날짜만 보지 않는다. **회수됐는지까지 본다** —
      `ruleset_check.ADMINS` 에 이탈자가 남아 있으면 실패한다. 날짜만
      보면 "카드를 지웠으니 됐다" 로 끝나고 룰셋은 그대로 남는다.
      룰셋 실물은 관리자 토큰이 있어야 읽으므로 `ruleset_check` 가 보고,
      이쪽은 **그 도구가 무엇을 기대하는지**를 본다.

    ★ 실패 메시지를 크게 낸다. 빨간 줄 하나면 다른 팀원이 무슨 일인지
      모르고 당황한다. 무엇을 해야 하는지가 화면에 다 있어야 한다.
    """
    if DEPARTURE is None:
        # ★ 걸 대상이 없다. 그래도 **화면에 남은 만료 뱃지는 잡는다** —
        #   회수했는데 카드가 남으면 지난 날짜가 지침처럼 읽힌다.
        stray = []
        for g in ("web/*.html", "docs/*.md"):
            for f in ROOT.glob(g):
                if 'data-expires="' in f.read_text(encoding="utf-8", errors="ignore"):
                    stray.append(f"{f.relative_to(ROOT)} 에 data-expires 가 남았다 — "
                                 "회수가 끝났으면 그 카드를 지운다")
        return stray

    today = _today()
    bad, seen = [], {}

    for g in ("web/*.html", "docs/*.md"):
        for f in ROOT.glob(g):
            txt = f.read_text(encoding="utf-8", errors="ignore")
            for d in re.findall(r'data-expires="(\d{4}-\d{2}-\d{2})"', txt):
                seen.setdefault(d, []).append(str(f.relative_to(ROOT)))

    # 화면과 MASTER 가 같은 날짜를 드는가 — 지나기 전에도 본다
    mst = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s*[에]?\s*회수", mst)
    if seen and DEPARTURE not in seen:
        bad.append(f"화면의 data-expires 는 {' · '.join(sorted(seen))} 인데 "
                   f"이탈일은 {DEPARTURE} 다. 하나로 맞춰라")
    if m and m.group(1) != DEPARTURE:
        bad.append(f"MASTER 는 회수일을 {m.group(1)} 로 적는데 "
                   f"이탈일은 {DEPARTURE} 다")

    if today <= DEPARTURE:
        return bad

    # ── 기한이 지났다. 여기서부터는 크게 운다 ──────────────────
    bad.append(_BANNER.rstrip())
    bad.append(f"이탈일 {DEPARTURE} 이 지났다 (오늘 {today}).")

    rs = ROOT / "tools/ruleset_check.py"
    if rs.exists() and LEAVING in rs.read_text(encoding="utf-8"):
        bad.append(f"★ ruleset_check.ADMINS 에 {LEAVING} 이 아직 있다 — "
                   "룰셋을 회수하지 않았거나 명단을 안 고쳤다")
    for d, where in sorted(seen.items()):
        if d <= DEPARTURE:
            bad.append(f"★ {' · '.join(where)} 의 BYPASS 카드가 남아 있다")
    if m:
        bad.append("★ MASTER §12-1 에 회수일 서술이 남아 있다")
    bad.append(_TODO.rstrip())
    return bad
