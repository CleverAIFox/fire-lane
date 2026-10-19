"""`doc_fsck ⑥` — 기획서를 고쳤는데 최종 수정일이 그대로인가.  (§258-19)

IN    docs/proposal.md · 그 안의 최종 수정일 표기 · git 이력 · origin/dev 의 사본
OUT   결함 문장 목록 (비면 통과)
밖    기획서 **내용**이 산출물과 맞는가는 `tools/docnum_check.py`(수) ·
      `tools/proposalcheck.py`(참조 · 폐기 어휘 · 캡션 · 긴 칸) 소관이다.
      **스쿼시 뒤의 다른 검사들은 안 본다** — 열차가 만드는 상태를 통틀어 다시
      보는 것은 `tools/fl.sh` 의 「7b. 열차 뒤 검사」 소관이다.
★ 2026-10-09 (DECISIONS §444 · PLAN #142). 파일 이름이 `docx_revised.py` 였다.
  보던 것이 `docs/proposal.docx` 였고 그 파일이 은퇴했다 — **이름이 사라진
  형식을 들고 있으면 다음 사람이 없는 파일을 찾는다**(§312 와 같은 교훈).
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
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


def covers() -> list[Path]:
    """표지 날짜를 드는 기획서 전부.

    ★ 2026-10-09 (§440-8). 종전에는 `docs/*.docx` **하나**였다. §425 가 정본을
      `docs/proposal.md` 로 옮겼는데 **이 그물은 안 따라갔다** — 실측하니 md 표지가
      `2026. 10. 01.` 에 멈춰 여드레 낡아 있었고 아무도 안 울었다. 사람이 읽는
      화면(`web/proposal.html`)이 그 줄을 그대로 띄우므로 **낡은 날짜가 밖으로
      나간다.** §440-5 가 숫자에서 같은 구멍을 메웠고 이쪽은 날짜다.
    ★ 2026-10-09 (§444). **docx 가 은퇴했으므로 md 하나다** — §440-8 이 「그때
      줄만 준다」고 적어 둔 그대로다. 목록으로 남긴다: 기획서가 둘이 되는
      날(국문·영문 따위)이 오면 여기 한 줄이다.
    """
    md = ROOT / "docs" / "proposal.md"
    return [md] if md.is_file() else []


def _cover_dates(f: Path) -> tuple[list[str], str | None]:
    """표지 앞머리의 날짜 표기와, 못 읽었으면 그 사유."""
    try:
        txt = "\n".join(f.read_text(encoding="utf-8").splitlines()[:40])
    except OSError as e:
        return [], f"{f.name} 표지를 못 읽었다 — {type(e).__name__}: {e}"
    return re.findall(r"20\d\d\.\s*\d{1,2}\.\s*\d{1,2}", txt), None


def _norm(s: str) -> str:
    return re.sub(r"[.\s-]", "", s)


# ── 6b. 스쿼시가 날짜를 옮긴다 ─────────────────────────────────
BASES = ("origin/part/infra", "origin/dev")


def check_ready_for_squash(bases: tuple[str, ...] = BASES) -> list[str]:
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
    out: list[str] = []
    for f in covers():
        out += _ready_one(f, bases)
    return out


def _ready_one(f: Path, bases: tuple[str, ...]) -> list[str]:
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
    #   바로 위 `check_revised` 가 2026-09-18 에 선언한 전제와 같은 것이고,
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
    today = squash_day()
    if _norm(today) in {_norm(s) for s in shown}:
        return []
    return [f"{rel} 을 이 배치에서 고쳤는데(기준 {base}) 표지는 "
            f"{' · '.join(shown) or '날짜 없음'} 만 든다.\n"
            f"      ★ 스쿼시가 파일의 커밋 날짜를 머지일로 바꾸므로 지금 초록이어도 "
            f"머지 뒤 ⑥ 이 운다.\n"
            f"      고치는 법 — uv run python tools/build_proposal.py --touch {today} --write"]


def squash_day() -> str:
    """이 배치가 스쿼시될 날. **표지가 들어야 하는 날짜의 정본이다.**

    ★ 시간대 없는 `date.today()` 는 CI(`DTZ011`)가 문다. 이 검사의 「오늘」은
      **한국 시각의 오늘**이다 — 배치를 그 시각으로 스쿼시하기 때문이다.

    ★ 2026-10-11 (DECISIONS §468-3). 함수로 꺼냈다. 종전에는 이 식이 위
      `check_ready_for_squash` **안**에 있었고, 그래서 `fix.sh` 가 그 날짜를
      쓰려면 **같은 식을 한 번 더 적어야** 했다. 검사가 유도하는 수를 수리
      쪽이 다시 유도하면 그 둘이 갈리는 날이 온다(족 2).
    """
    return datetime.now(tz=timezone(timedelta(hours=9))).date().isoformat()


# ── 6. 기획서 최종 수정일 ──────────────────────────────────────
def check_revised() -> list[str]:
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
    # ★ 전제 선언. 못 재는 것을 못 잰다고 말한다 — 조용히 통과하지도, 거짓으로
    #   빨개지지도 않는다.
    # ★ 2026-09-24 (§239). `sh.returncode` 를 안 봤다. 판별이 실패하면 stdout 이
    #   비어 **얕지 않다고 판단**하고 except 가 삼켰다 — 아래 `git log` 가 빈
    #   결과를 내 「수정일 미상」이 정상값으로 흐른다. 못 잰 것은 못 잰다고 말한다.
    try:
        sh = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    except Exception as e:
        return [f"얕은 저장소인지 판별하지 못했다: {type(e).__name__}: {e}"]
    if sh.returncode != 0:
        return [f"얕은 저장소 판별 실패(rc={sh.returncode}): "
                f"{sh.stderr.strip()[:120]}. 못 잰 것을 통과로 세지 않는다"]
    if sh.stdout.strip() == "true":
        print("   (건너뜀 — 얕은 저장소라 마지막 수정 커밋일을 못 잰다)")
        return []
    out: list[str] = []
    for f in covers():
        out += _revised_one(f)
    return out


def _revised_one(f: Path) -> list[str]:
    import subprocess
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
    # ★ 2026-09-22 (W10-1 · deadcheck ③). 표지를 못 읽은 것과 표지가 맞는 것은
    #   다르다 — 종전 `return []` 은 그 둘을 같게 읽었다. `_cover_dates` 가
    #   사유를 들고 온다(2026-10-09 · md 와 docx 를 같이 읽는다).
    shown, why = _cover_dates(f)
    if why:
        return [why]
    if not shown:
        return [f"{f.name} 표지에 날짜가 없다. 작성일과 최종 수정일을 적어라"]
    # ★ 2026-10-14 (DECISIONS §522). **묻는 것은 「표지가 낡았나」다.**
    #   종전에는 마지막 커밋 날짜가 표지 날짜 **집합에 있는가**를 봤고, 그래서
    #   표지가 커밋보다 **앞서면** 빨갰다. 그 조합이 자정에 난다 — 표지를
    #   채우는 `docgen` 은 **지금 시계의 오늘**을 쓰고 커밋 날짜는 어제다.
    #   2026-10-14 00:5x 에 열차가 그 자리에서 멈췄고, 고치려면 표지를 되돌려
    #   **어제 날짜로** 커밋해야 했다 — 오늘 날짜로 커밋하면 관문이 다시 오늘을
    #   요구해 **돌림**이 된다. 돌림이 나는 관문은 사람이 날짜를 손으로 고르게
    #   만든다(PLAN `#172`).
    #   ★ 느슨해지지 않는다. 막는 것은 **표지가 뒤처진 경우** 하나고 그것이
    #     이 검사의 뜻이다(「고쳤는데 최종 수정일이 그대로인가」). 표지가
    #     앞선 것은 낡은 것이 아니다 — `docgen` 이 오늘을 쓰므로 미래로는
    #     못 간다.
    newest = max(re.sub(r"[.\s]", "", s) for s in shown)
    if newest < re.sub(r"-", "", last):
        return [f"{f.name} 의 마지막 수정 커밋은 {last} 인데 표지는 "
                f"{' · '.join(shown)} 만 든다 — **표지가 뒤처졌다.** "
                f"최종 수정일을 갱신해라 (uv run python tools/docgen.py)"]
    return []
