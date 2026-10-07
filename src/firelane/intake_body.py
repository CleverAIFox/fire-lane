"""intake_body.py — **단서 ④ 본문.** 이름이 아무 말도 안 할 때 연다.  (DECISIONS §399)

`tools/intake.py` 의 단서 ①②③ 은 전부 **파일 이름**을 본다 — KFS 문서번호 ·
대장 `stem` · 취득 규칙. 브라우저가 떨구는 이름(`★(4.29. 즉시 보도자료) 119패스
전국 확대…`)에는 그 셋이 하나도 없다. 그래서 내용을 연다.

★ 2026-10-05 에 `tools/intake.py` 에서 **떼어 냈다.** 그 파일이 656줄이 됐고,
  이 덩이는 「본문으로 대장 항목을 고른다」 한 물음이라 혼자 선다. 떼면
  시험이 레이크 없이 돈다 — `intake.py` 는 `require_lake` 를 건다.

IN    PDF 경로 · `sources.yaml::datasets`
OUT   `(대장 키, 사유)` · `(파일 상대경로, 사유)`
PARAM BODY_MIN_HITS · BODY_MARGIN · BODY_PAGES · BODY_STOP
밖    **옮기지 않는다.** 고르기만 하고 멈춘다 — 옮기는 것은 `intake --stage` 다.
      그리고 **PDF 만 연다**. 그 밖은 글자가 0 이라 「모른다」로 간다.
"""
from __future__ import annotations

import re
from pathlib import Path

# ★ 2026-10-05 (DECISIONS §399). 단서 ①~③ 은 전부 **파일 이름**을 본다.
#   그런데 브라우저가 떨구는 이름은 `★(4.29. 즉시 보도자료) 119패스 전국
#   확대…` 꼴이고 거기엔 문서번호도 stem 도 취득 규칙도 없다. 2026-10-05 에
#   자료 넷이 그 꼴로 와서 전부 「사람이 정한다」로 떨어졌다.
#   **이름이 아무 말도 안 하면 내용을 연다.**
#: 1등이 최소 이만큼은 맞아야 한다.
BODY_MIN_HITS = 2
#: 1등과 2등의 차이가 이보다 작으면 **모른다**.
BODY_MARGIN = 2
#: 본문을 몇 쪽까지 읽는가. 법령 인쇄본은 발 밑 URL 이 마지막 쪽에 있다.
BODY_PAGES = 3
#: 점수에 안 넣는 낱말. 대장 **전체**에 흔해서 구별을 못 한다.
BODY_STOP = frozenset({"미투입", "현행", "시행", "전국", "자료", "기준", "제작",
                       "대상", "지역", "확대", "발표", "대책", "우리", "그것",
                       "국가법령정보센터", "법제처", "소방청", "pdf"})
_BODY_TOKEN = re.compile(r"[가-힣A-Za-z][가-힣A-Za-z0-9]{1,}")
_JONO = re.compile(r"joNo=0*(\d+)")


def body_text(path: Path, pages: int = BODY_PAGES) -> str:
    """앞 `pages` 쪽의 글자. 못 읽으면 빈 문자열 — **터지지 않는다.**

    ★ 여기서 예외를 올리면 다운로드 폴더에 PDF 아닌 것이 하나만 있어도 취입
      전체가 멈춘다. 못 읽는 것은 「모른다」로 가야 하고 그것이 안전한 쪽이다.
    """
    if path.suffix.lower() != ".pdf":
        return ""
    try:
        import pypdf

        r = pypdf.PdfReader(str(path))
        return "\n".join(q.extract_text() or "" for q in r.pages[:pages])
    except Exception:
        return ""


def _body_tokens(s: str) -> set[str]:
    return {t for t in _BODY_TOKEN.findall(s or "") if t not in BODY_STOP}


def body_marks(ds: dict) -> dict[str, set[str]]:
    """대장 키 → **구별 낱말.** 둘 이상에 나오는 낱말은 뺀다.

    ★ 목록을 손으로 안 적는다. 대장이 자라면 다시 계산된다 — 그리고 **다른
      항목과 겹치는 낱말은 구별을 못 하므로** 자동으로 빠진다.
    """
    own = {k: _body_tokens(f"{(v or {}).get('what', '')}\n"
                           f"{(v or {}).get('authority', '')}")
           for k, v in ds.items()}
    seen: dict[str, int] = {}
    for toks in own.values():
        for t in toks:
            seen[t] = seen.get(t, 0) + 1
    return {k: {t for t in toks if seen[t] == 1} for k, toks in own.items()}


def body_match(body: str, ds: dict) -> tuple[str | None, str]:
    """본문 → `(대장 키, 사유)`. 애매하면 `(None, 사유)`.

    ★ **애매하면 안 고른다.** 틀린 이름으로 landing 에 넣는 것이 안 넣는
      것보다 나쁘다 — landing 은 raw 의 상류다.
    """
    got = _body_tokens(body)
    if not got:
        return None, "본문을 못 읽었다 (PDF 가 아니거나 글자가 없다)"
    board = sorted(((len(v & got), k) for k, v in body_marks(ds).items()),
                   reverse=True)
    if not board:
        return None, "대장이 비었다"
    top, key = board[0]
    runner = board[1][0] if len(board) > 1 else 0
    if top < BODY_MIN_HITS:
        return None, f"본문 점수가 {top} — 바닥 {BODY_MIN_HITS} 에 못 미친다"
    if top - runner < BODY_MARGIN:
        return None, (f"본문 1등 {key} {top} · 2등 {board[1][1]} {runner} — "
                      f"벌어짐 {BODY_MARGIN} 에 못 미친다")
    return key, f"본문 낱말이 대장 {key} 와 {top}개 맞는다 (2등 {runner})"


def body_file_of(body: str, entry: dict) -> tuple[str | None, str]:
    """그 항목이 파일 여럿을 선언했을 때 **어느 것인가.**

    ★ 조문 둘을 선언한 법령은 **점수가 같다** — 같은 인쇄본이라 낱말이 같다.
      가르는 것은 인쇄 URL 의 `joNo` 하나뿐이고, 그것이 없으면 안 고른다.
    """
    from firelane import ledger as _led

    # ★ 2026-10-07 (DECISIONS §430). 종전에는 `entry.get("files")` 를 **직접**
    #   읽었다. 2026-08-31 에 대장을 `stem`+`ext` 로 뒤집으면서(PLAN #46)
    #   `files` 는 **글롭 예외 열넷**만 남았는데 이 소비자가 이관에서 빠졌다 —
    #   나머지 **예순여섯 종이 "대장이 파일을 안 적는다"** 로 떨어졌다.
    #   정본 접근자는 `ledger.globs()` 하나다. 그것만 쓴다.
    files = list(_led.globs(entry or {}))
    if len(files) == 1:
        return files[0], "선언 파일이 하나다"
    if not files:
        return None, "대장이 파일을 안 선언한다"
    m = _JONO.search(body)
    if m:
        want = f"_a{int(m.group(1))}."
        hit = [f for f in files if want in f]
        if len(hit) == 1:
            return hit[0], f"인쇄 URL 의 joNo 가 제{int(m.group(1))}조다"
    return None, f"선언 파일이 {len(files)}개인데 어느 것인지 못 가른다"
