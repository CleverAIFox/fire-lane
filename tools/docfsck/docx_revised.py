"""`doc_fsck ⑥` — 기획서를 고쳤는데 최종 수정일이 그대로인가.  (§258-19)

IN    docs/proposal.docx · 그 안의 최종 수정일 표기 · git 이력 · origin/dev 의 사본
OUT   결함 문장 목록 (비면 통과)
밖    기획서 **내용**이 산출물과 맞는가는 `tools/docx_check.py` 소관이다.
      **스쿼시 뒤의 다른 검사들은 안 본다** — 열차가 만드는 상태를 통틀어 다시
      보는 것은 `tools/fl.sh` 의 「7b. 열차 뒤 검사」 소관이다.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, timeout: int = 10) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout)
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"
    return r.returncode, r.stdout.strip()


def _cover_dates(f: Path) -> tuple[list[str], str | None]:
    """표지 앞 40단락의 날짜 표기와, 못 읽었으면 그 사유."""
    try:
        import docx as _dx
        txt = "\n".join(x.text for x in _dx.Document(str(f)).paragraphs[:40])
    except Exception as e:
        return [], f"{f.name} 표지를 못 읽었다 — {type(e).__name__}: {e}"
    return re.findall(r"20\d\d\.\s*\d{1,2}\.\s*\d{1,2}", txt), None


def _norm(s: str) -> str:
    return re.sub(r"[.\s-]", "", s)


# ── 6b. 스쿼시가 날짜를 옮긴다 ─────────────────────────────────
BASES = ("origin/part/infra", "origin/dev")


def check_docx_ready_for_squash(bases: tuple[str, ...] = BASES) -> list[str]:
    """기획서를 **이 배치에서 고쳤는데** 표지가 오늘 날짜가 아닌가.  (§273-5)

    ── 왜 생겼나 (2026-09-27) ──────────────────────────────────
    ⑥ 은 `git log -1 -- proposal.docx` 의 **저자 날짜**를 표지와 견준다. 그런데
    **스쿼시가 그 날짜를 머지일로 바꾼다** — 커밋 여럿이 한 개로 접히면서 파일별
    저자 날짜가 사라지고 스쿼시 커밋의 날짜 하나만 남는다.

    그래서 이 배치에서 실제로 일어난 일이 이렇다.

        feat/batch-0926 (4986e7b)   기획서의 마지막 커밋 09-24 · 표지 09-24  → 초록
        part/infra (0a4dd53, 스쿼시) 같은 파일의 커밋이 09-27 로 바뀜        → 빨강

    **로컬 전수 verify 가 볼 수 없는 빨간불이다.** 스쿼시는 CI 뒤에 일어나므로
    사람이 미리 잴 방법이 ⑥ 에는 없었다. 그 결과 왕복 하나를 태웠다.

    ★ 그래서 팔을 하나 더 단다 — **짜는 동안** 운다. 기획서가 `base` 의 사본과
      내용이 다르면 그 배치는 기획서를 고친 것이고, 그러면 표지는 **머지일**을
      들어야 한다. 같은 날 머지하는 것이 이 저장소의 실측 전부이므로 「오늘」로
      본다. 날이 넘어가면 `fl.sh` 의 7b 가 스쿼시 직후에 다시 운다 —
      **두 팔이 각각 다른 시점을 든다.**

    ★ `base` 를 못 읽으면 **재지 않는다.** 얕은 클론 · 원격 없는 사본에서
      거짓으로 빨개지는 것이 진짜 경보를 죽인다(§18-13 · ⑥ 머리말과 같은 규율).
    """
    docs = list(ROOT.glob("docs/*.docx"))
    if not docs:
        return []
    f = docs[0]
    rel = f.relative_to(ROOT).as_posix()

    # ★ 스쿼시가 일어나는 곳이 기준이다 — `feat` → `part/infra` 다. `dev` 를 기준으로
    #   잡으면 `part/infra` 가 `dev` 보다 앞선 동안 **남의 배치의 변경**까지 내 것으로
    #   세서 거짓으로 빨개진다. 실제로 그렇게 짰다가 바로 걸렸다.
    #
    # ★ 2026-10-02 (DECISIONS §355). 종전에는 **이름이 있는가**만 봤다
    #   (`rev-parse --verify`). 얕은 클론에서는 `origin/part/infra` 라는 ref 가
    #   있어도 **커밋이 없다** — 그래서 통과한 뒤 아래 `base...HEAD` 가
    #   공통 조상을 못 찾아 죽었고, stderr 가 비어 「판별하지 못했다: .」 라는
    #   사유 없는 빨강이 CI 에 섰다(PR #266).
    #   필요한 것은 이름이 아니라 **공통 조상**이므로 그것으로 고른다.
    #   바로 위 `check_docx_revised` 가 2026-09-18 에 선언한 전제와 같은 것이고,
    #   이 팔만 그것을 안 물려받고 있었다.
    base = next((b for b in bases
                 if _git("merge-base", "HEAD", b)[0] == 0), None)
    if base is None:
        return []                     # 기준을 모른다 — 모를 때 막지 않는다
    rc, out = _git("diff", "--name-only", f"{base}...HEAD", "--", rel, timeout=30)
    if rc != 0:
        return [f"{rel} 이 {base} 와 다른지 판별하지 못했다: {out[:120]}. "
                f"못 잰 것을 통과로 세지 않는다"]
    if not out:
        return []                     # 이 배치가 기획서를 안 고쳤다

    shown, why = _cover_dates(f)
    if why:
        return [why]
    # ★ 시간대 없는 `date.today()` 는 CI(`DTZ011`)가 문다. 이 검사의 「오늘」은
    #   **한국 시각의 오늘**이다 — 배치를 그 시각으로 스쿼시하기 때문이다.
    today = datetime.now(tz=timezone(timedelta(hours=9))).date().isoformat()
    if _norm(today) in {_norm(s) for s in shown}:
        return []
    return [f"{rel} 을 이 배치에서 고쳤는데(기준 {base}) 표지는 "
            f"{' · '.join(shown) or '날짜 없음'} 만 든다.\n"
            f"      ★ 스쿼시가 파일의 커밋 날짜를 머지일로 바꾸므로 지금 초록이어도 "
            f"머지 뒤 ⑥ 이 운다.\n"
            f"      고치는 법 — uv run python tools/docx_fix.py --touch {today} --write"]


# ── 6. 기획서 최종 수정일 ──────────────────────────────────────
def check_docx_revised() -> list[str]:
    """기획서를 고쳤는데 표지의 최종 수정일이 그대로인가.

    ★ 2026-09-02. 표지가 `2026. 08. 14.` 하나만 들고 있었고 그 뒤로 다섯 번
      고쳤다. **외부가 읽는 유일한 문서라 날짜가 곧 신뢰다** — 심사위원이
      8월 문서를 받으면 그동안 아무것도 안 한 것으로 읽는다.

    ★ 파일 mtime 이 아니라 **git 이 아는 마지막 수정 커밋일**과 비교한다.
      mtime 은 clone 하면 전부 오늘이 된다.

    ★ 2026-09-18. **얕은 저장소에서는 재지 않는다.** `actions/checkout@v4` 는
      `fetch-depth: 1` 이라 커밋이 하나뿐이고, 그러면 `git log -1 -- <파일>` 이
      모든 파일에 대해 **HEAD 의 날짜**를 돌려준다. 실제 마지막 수정일이 아니다.
      W2 가 이 검사를 CI 에 넣었다가 그대로 빨개졌다(DECISIONS §191-5).
      이 절의 나머지 일곱(①~⑤·⑦·⑧)은 히스토리가 필요 없어 CI 에서 그대로 돈다 —
      **검사 하나가 자기 전제를 선언하면 나머지를 같이 뺄 필요가 없다.**
    """
    import subprocess
    docs = list(ROOT.glob("docs/*.docx"))
    if not docs:
        return []
    f = docs[0]
    # ★ 전제 선언. 못 재는 것을 못 잰다고 말한다 — 조용히 통과하지도, 거짓으로
    #   빨개지지도 않는다.
    # ★ 2026-09-24 (§239). `sh.returncode` 를 안 봤다. 판별이 실패하면 stdout 이
    #   비어 **얕지 않다고 판단**하고 except 가 삼켰다 — 아래 `git log` 가 빈
    #   결과를 내 「수정일 미상」이 정상값으로 흐른다. 못 잰 것은 못 잰다고 말한다.
    try:
        sh = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    except Exception as e:
        return [f"{f.name} — 얕은 저장소인지 판별하지 못했다: {type(e).__name__}: {e}"]
    if sh.returncode != 0:
        return [f"{f.name} — 얕은 저장소 판별 실패(rc={sh.returncode}): "
                f"{sh.stderr.strip()[:120]}. 못 잰 것을 통과로 세지 않는다"]
    if sh.stdout.strip() == "true":
        print("   (건너뜀 — 얕은 저장소라 마지막 수정 커밋일을 못 잰다)")
        return []
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ad", "--date=short", "--", str(f)],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        last = r.stdout.strip()
    except Exception as e:
        # ★ 2026-09-22 (PLAN §13 W10-1 · deadcheck ③). 종전에는 `return []` —
        #   git 이 죽으면 이 검사가 **초록**이었다. 얕은 저장소처럼 전제를
        #   선언한 경우가 아니라 **못 잰 것**이므로 못 쟀다고 말한다.
        return [f"{f.name} 의 마지막 수정 커밋일을 못 쟀다 — git log 실패: "
                f"{type(e).__name__}: {e}"]
    if not last:
        return []
    try:
        import docx as _dx
        txt = "\n".join(x.text for x in _dx.Document(str(f)).paragraphs[:40])
    except Exception as e:
        # ★ 2026-09-22 (W10-1 · deadcheck ③). `python-docx` 는 선언된 의존성이다
        #   (pyproject). 그것이 없거나 기획서가 안 열리면 표지를 못 읽은 것이지
        #   표지가 맞는 것이 아니다 — 종전 `return []` 은 그 둘을 같게 읽었다.
        return [f"{f.name} 표지를 못 읽었다 — {type(e).__name__}: {e}"]
    shown = re.findall(r"20\d\d\.\s*\d{1,2}\.\s*\d{1,2}", txt)
    if not shown:
        return [f"{f.name} 표지에 날짜가 없다. 작성일과 최종 수정일을 적어라"]
    norm = {re.sub(r"[.\s]", "", s) for s in shown}
    if re.sub(r"-", "", last) not in norm:
        return [f"{f.name} 의 마지막 수정 커밋은 {last} 인데 표지는 "
                f"{' · '.join(shown)} 만 든다. 최종 수정일을 갱신해라"]
    return []
