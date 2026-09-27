"""`doc_fsck ⑥` — 기획서를 고쳤는데 최종 수정일이 그대로인가.  (§258-19)

IN    docs/proposal.docx · 그 안의 최종 수정일 표기
OUT   결함 문장 목록 (비면 통과)
밖    기획서 **내용**이 산출물과 맞는가는 `tools/docx_check.py` 소관이다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
    except Exception as e:                                # noqa: BLE001
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
    except Exception as e:                                # noqa: BLE001
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
    except Exception as e:                                # noqa: BLE001
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
