"""
intake_name.py — **이름이 무엇을 말하나.** 원본명에서 정규명 후보를 낸다.

── 왜 생겼나 (2026-10-08 · DECISIONS §431 · PLAN #157) ────────
`tools/intake.py` 가 **609줄**로 상한 600 을 넘었다. 2026-10-05 에 같은 이유로
**본문 단서**를 `intake_body.py` 로 뗐고(656 → 아래로), §430 이 세 벌이던
고르기를 `_pick` 하나로 합치면서 다시 넘었다. 이 덩이는 「**이름**으로 대장
항목을 고른다」 한 물음이라 혼자 선다 — 본문을 뗀 그 수술의 거울상이다.

단서를 넷 본다. 강한 순서다 — ① KFS 문서번호 ② 취득 규칙 ③ 대장 `stem`
④ 본문(`intake_body`). ①②③ 이 여기 살고 ④ 는 옆 파일이다.

IN    원본 파일 경로 · `sources.yaml::datasets`
OUT   없음 — **후보와 사유만 돌려준다. 채택하지 않는다**
PARAM `DOC_NO`
밖    **옮기지 않는다.** 고르기만 하고 멈춘다 — 옮기는 것은 `intake --stage` 다.
      그리고 **고른 것이 맞는지도 안 본다** — 그 판정은 `acquire --verify` 다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from firelane import naming as nm
from firelane.intake_body import body_file_of, body_match, body_text

DOC_NO = re.compile(r"(KFS-\d-\d{4}-\d{4}(?:-\d{2})?)", re.IGNORECASE)


def rule_path(name: str) -> str | None:
    """`normalize_raw.RULES` 가 이 원본명을 배치할 수 있나 → raw 상대경로.

    ★ 2026-08-27 신설. 종전에는 **KFS 문서번호로만** 매칭했다. 그래서
      문서번호가 없는 일반 데이터가 전부 "대장에 없다" 로 막혔다 —
      `전남광주통합특별시 동구_불법 주정차 단속현황_20240108.csv` 가
      그랬다. `enforcement` 는 대장에 있고 RULES 도 이 이름을 잡는데,
      `propose()` 가 RULES 를 안 봐서 난 오탐이다.

      **관문은 정확해야 한다.** 정상 파일을 막으면 사람이 `--force` 를
      습관처럼 쓰게 되고, 그러면 관문이 없는 것과 같아진다.
    """
    import re as _re

    from firelane.normalize_raw import RULES
    # ★ 2026-09-07. `normalize_raw.main()` 은 `low = f.name.lower()` 로
    #   매칭한다. 여기가 원본 그대로 매칭해서 **대문자가 든 파일명만**
    #   관문에 막혔다(건물DB · CCTV정보 · GJBG_LSI…). 08-24 KFS 사고의
    #   거울상이다 — 그때는 규칙이 대문자였고 이번엔 매칭이 소문자를
    #   안 했다. 두 곳이 같은 방식으로 매칭해야 한다.
    low = name.lower()
    for pat, folder, tmpl in RULES:
        m = _re.search(pat, low)
        if not m:
            continue
        return f"{folder}/{tmpl.format(*m.groups()) if tmpl else name}"
    return None


def stem_of(rel: str) -> str:
    """raw 상대경로 → provider_dataset. 스코프·날짜 뒤를 떨어낸다."""
    import re as _re

    from firelane import scope as sc
    stem = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    toks = "|".join(_re.escape(x) for x in
                    sorted(list(sc.spec()) + list(sc.LEGACY),
                           key=len, reverse=True))
    return _re.sub(rf"_(?:{toks})?_?\d{{4,8}}.*$", "", stem).rstrip("_")



def propose(src: Path, ds: dict) -> dict:
    """정규명 후보를 낸다. **채택하지 않는다.**

    단서를 넷 본다. 강한 순서다 —
      ① KFS 문서번호   대장 본문에 그대로 적혀 있다. 제일 확실하다
      ③ 대장 stem      파일명이 이미 정규명인가
      ② 취득 규칙      `normalize_raw.RULES` 가 배치할 수 있는가
      ④ **본문**       앞 셋이 전부 **파일 이름**을 본다. 이름이 아무 말도
                       안 하면(브라우저가 붙인 이름) 내용을 연다 (§399)
      없으면           사람이 정한다

    ★ 2026-09-03. ③을 신설했다. **`intake` 가 대장 `stem` 을 안 봤다.**
      2026-08-31 에 `file`/`files` 를 37종에서 빼고 `stem`+`ext` 로 뒤집었는데
      (PLAN #46) 이 소비자가 이관에서 빠졌다 — `scan_data §4` 와 같은 자리다.

      그래서 파일명이 대장 규칙(`<stem>_<scope>_<날짜>.<ext>`)과 완전히
      일치해도 "대장에 없다" 로 걸렀다. 2026-09-03 에 `nfa_*` 15개가
      전부 그렇게 막혔다. 대장에 등재돼 있었는데도.

      ★ `RULES` 는 **취득처가 준 이름**을 다루는 규칙이고, `stem` 은
        **우리가 정한 이름**이다. 둘은 다른 단계라 ②로는 못 잡는다.
    """
    stem, ext = nm.split_ext(src.name)
    out = {"origin_name": src.name, "ext": ext, "doc_no": None,
           "matched_key": None, "suggest": None, "why": []}

    m = DOC_NO.search(stem)
    if m:
        out["doc_no"] = m.group(1).upper()

    # ① 문서번호
    if out["doc_no"]:
        for k, v in ds.items():
            blob = json.dumps(v, ensure_ascii=False, default=str)
            if out["doc_no"] in blob.upper():
                out["matched_key"] = k
                pat = v.get("file", "")
                base = pat.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if "*" not in base:
                    out["suggest"] = f"{pat.split('/')[0]}/{base}.{ext}"
                    out["why"].append(
                        f"문서번호 {out['doc_no']} 가 대장 {k} 에 있다")
                break

    # ③ 대장 stem — 파일명이 이미 정규명인 경우
    #    ★ ②보다 먼저 본다. 이미 우리 규칙으로 지은 이름이면 RULES 를
    #      거칠 이유가 없고, RULES 가 옛 이름을 만들어 오히려 어긋난다.
    if out["matched_key"] is None:
        for k, v in ds.items():
            st = (v or {}).get("stem")
            if st and stem.startswith(f"{st}_"):
                out["matched_key"] = k
                org = (v or {}).get("provider") or st.split("_", 1)[0]
                out["suggest"] = f"{org}/{src.name}"
                out["why"].append(f"파일명이 대장 {k} 의 stem 으로 시작한다")
                break

    # ② 취득 규칙 — 규칙이 배치할 수 있으면 그 결과로 대장 항목을 찾는다
    if out["matched_key"] is None:
        placed = rule_path(src.name)
        if placed:
            out["suggest"] = placed
            # ★ RULES 는 **옛 이름**을 만든다(`..._dongu_...`). 그대로
            #   stem 을 조회하면 어긋난다. `normalize_raw` 가 그러듯
            #   여기서도 파서를 거쳐 provider_dataset 만 뽑는다.
            pstem = stem_of(placed)
            for k, v in ds.items():
                st = v.get("stem") or ""
                stems = v.get("stems") or ([st] if st else [])
                if pstem in stems:
                    out["matched_key"] = k
                    out["why"].append(
                        f"취득 규칙이 {placed} 로 배치한다 → 대장 {k}")
                    break
            else:
                out["why"].append(
                    f"취득 규칙은 {placed} 로 배치하는데 대장 항목이 없다 — "
                    "stem 이 맞는지 확인하라")

    # ④ 본문 — 이름이 아무 말도 안 할 때만 연다
    if out["matched_key"] is None:
        key, why = body_match(body_text(src), ds)
        out["why"].append(why)
        if key:
            rel, why2 = body_file_of(body_text(src), ds.get(key) or {})
            out["why"].append(why2)
            if rel:
                out["matched_key"] = key
                out["suggest"] = rel

    if out["matched_key"] is None:
        slug = nm.slugify(stem)
        out["why"].append(
            f"대장 매칭 실패. 후보 토큰 — {slug!r} (사람이 정한다)")
    return out
