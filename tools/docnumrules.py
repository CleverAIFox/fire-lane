#!/usr/bin/env python3
"""
docnumrules.py — **문서가 적어야 하는 수의 선언 표.** 어느 파일의 어느 라벨인가.

★ 왜 갈랐나 — `docnumtable.py` 와 같은 사유다. `docnum_check` 가 상한(600)을
  다시 넘었고 넘은 만큼이 **이 표**였다. 표가 자라는 것은 좋은 일이고(문서가
  더 많은 수를 책임진다) 재는 코드가 그만큼 읽기 어려워지는 것은 다른 일이다.

★ 2026-10-10 (DECISIONS §452 · PLAN #56 ② 닫힘). 이 축은 `docnum_check.main()`
  **안에만** 있었다 — CLI 에서만 울고 pytest 는 조용했다(족 3). 실제로 당했다:
  `#34` 가 README 를 줄이자 규칙 여섯이 **주장 없는 파일**을 가리켰는데 전수
  pytest 가 초록이었다. 2026-10-08 에 필드표가 같은 사유로 나갔고(§436-13)
  같은 수법으로 옮긴다. 이제 `main()` 과 `tests/test_doc_numbers.py` 가
  **같은 함수**를 민다.

IN    (없음 — 부르는 쪽이 센 값과 파일 읽기를 넘긴다)
OUT   어긋남 줄 목록
부류  몸통   `docnum_check.py` 가 import 한다  (DECISIONS §398)
밖    **무엇을 셀지는 안 정한다** — 세는 것은 `docnum_check.counts` 가 든다.
      **폐기값도 안 본다** — 그쪽은 `docnumtable.RETIRED` 다.
"""
from __future__ import annotations

import re


def fmt(n: int) -> tuple[str, ...]:
    """1101 을 문서가 쓰는 두 표기로 — `1101` 과 `1,101`."""
    return (str(n), f"{n:,}")


def present_faults(c: dict[str, int], read) -> list[str]:
    """문서가 적은 수가 산출물과 같은가.

    ★ 2026-10-10 (DECISIONS §452 · PLAN #56 ② 닫힘). 이 축은 `main()` **안에만**
      있었다 — 그래서 CLI 에서만 울고 pytest 는 조용했다(족 3 · 관문이 갈림).
      실제로 당했다: `#34` 가 README 를 줄이면서 이 축의 규칙 여섯이 **주장 없는
      파일**을 가리키게 됐는데, 전수 pytest 는 초록이었다. 2026-10-08 에
      필드표가 같은 사유로 이 자리에서 나갔고(§436-13), 같은 수법으로 옮긴다.
      **재는 자리는 하나다** — `main()` 도 이 함수를 부른다.
    """
    out: list[str] = []
    RULES = [
        # ★ 2026-10-10 (DECISIONS §452 · PLAN #56). 넷(`clear` · `blocked` ·
        #   `unknown` · 동명동 구간)을 뺐다. **README 가 그 주장을 더는 안 한다** —
        #   `#34` 가 지금 상태를 `MASTER §24-7` 로 내렸고, 규칙은 주장을 따라간다.
        #   남긴 둘은 지금도 README 산문이 든다(1,281구간 · `needs_cv` 225구간).
        #   ★ 낡은 수가 다시 들어오는 쪽은 `RETIRED` 가 그대로 본다 — 그 축은
        #     `README.md` 를 훑는다. 뺀 것은 「있는가」이고 「없어야 하는가」는 산다.
        ("README.md", c["n"], "세그먼트 수"),
        ("README.md", c["needs_cv"], "needs_cv"),
        ("docs/MASTER.md", c["n"], "세그먼트 수"),
        ("docs/MASTER.md", c["clear"], "clear"),
        ("docs/MASTER.md", c["needs_cv"], "needs_cv"),
        ("docs/MASTER.md", c["blocked"], "blocked"),
        ("docs/MASTER.md", c["unknown"], "unknown"),
        ("docs/MASTER.md", c["cctv_in"], "CCTV 유효범위 안"),
        ("docs/MASTER.md", c["nfa"], "소방청 지정 기준 충족"),
        # ★ 2026-10-09 (DECISIONS §440 · PLAN #142). **기획서를 여기 넣었다.**
        #   종전에는 `tools/docx_check.py` 가 `docs/proposal.docx` 를 읽어 같은
        #   축을 봤다. 정본이 `.md` 로 옮겨진 뒤로 그 도구는 **사본을 검사하고
        #   있었다** — 정본이 틀려도 사본이 맞으면 초록이다. 기획서는 문서 넷 중
        #   **유일하게 외부가 읽는 것**이라 어긋나면 비용이 가장 크다.
        ("docs/proposal.md", c["n"], "세그먼트 수"),
        ("docs/proposal.md", c["clear"], "clear"),
        ("docs/proposal.md", c["needs_cv"], "needs_cv"),
        ("docs/proposal.md", c["blocked"], "blocked"),
        ("docs/proposal.md", c["unknown"], "unknown"),
        # ★ 2026-10-09 (DECISIONS §444 · PLAN #142). 회색 **사유별** 수 — 실물에
        #   있는 사유마다 한 줄이 저절로 선다. 기획서가 그 다섯을 한 문장에
        #   나열하므로 하나만 낡아도 그 문장 전체가 거짓이 된다.
        *[("docs/proposal.md", v, f"회색 사유 {k[3:]}")
          for k, v in sorted(c.items()) if k.startswith("ur_")],
        # ★ PLAN 도 본다. 08-18 에 PLAN 만 1,087 로 남아 있었다.
        ("docs/PLAN.md", c["n"], "세그먼트 수"),
        ("docs/PLAN.md", c["unknown"], "unknown"),
        # ★ 2026-08-31. 대장·실물 계열. 위 판정 수와 달리 **사람이 손으로
        #   적던 자리**이고 그래서 실제로 여러 번 틀렸다.
        ("docs/MASTER.md", c.get("hyd_up", 0), "소화전 지상식"),
        ("docs/MASTER.md", c.get("hyd_dn", 0), "소화전 지하식"),
        ("docs/MASTER.md", c.get("hyd_sum", 0), "소화전 합"),
        ("docs/MASTER.md", c.get("water", 0), "소방용수시설 총계"),
        ("sources.yaml", c.get("hyd_up", 0), "소화전 지상식"),
        ("sources.yaml", c.get("hyd_dn", 0), "소화전 지하식"),
        ("sources.yaml", c.get("hyd_sum", 0), "소화전 합"),
        # ★ 2026-08-31. 대장 규모. MASTER 가 세 곳에서 낡아 있었다 —
        #   `datasets 36종 · retired 8종`(실제 41 · 10) · `대장 36종`.
        #   사람이 손으로 세는 숫자는 반드시 낡는다.
        ("docs/MASTER.md", c.get("ds", 0), "대장 datasets 종수"),
        ("docs/MASTER.md", c.get("ds_retired", 0), "대장 retired 종수"),
        ("docs/MASTER.md", c.get("migrated", 0), "norm 이관 종수"),
        # ★ 2026-09-02 에 README 를 넣었다 — `대장 36종`(실물 43)이 살아 있었다.
        #   ★ 2026-10-10 (DECISIONS §452 · PLAN #56). **뺀다.** `#34` 가 그 줄을
        #     `MASTER §24-3` 으로 내렸고 MASTER 쪽 같은 라벨 둘이 그 줄을 읽는다.
        #     주장이 없는 파일에 문맥 패턴을 걸면 「패턴이 낡았다」로 영영 빨갛다.
        # ★ 2026-10-10 (DECISIONS §452 · PLAN #56). 도달 가능 — 세 곳이 한 수를
        #   든다(§3-11 표 · §24-2 · §24-7). 문맥 패턴이 그 셋을 한 번에 읽는다.
        ("docs/MASTER.md", c.get("reach", 0), "도달 가능"),
    ]
    # ★ 2026-09-02. 종전에는 **정답이 파일 어딘가에 있나**만 봤다.
    #   그래서 라벨 옆에 오답이 붙어 있어도 통과했다 — MASTER 가
    #   `datasets 41종`(실물 43)인 채로 초록불이었고, 그 절은 바로 위에
    #   "이 세 숫자는 docnum_check 가 대장에서 세어 대조한다 — 손으로
    #   적으면 낡는다" 고 적고 있었다. `docx_check` 의 `1,102` 와 같은
    #   형태다(DECISIONS §95).
    #
    #   라벨 옆의 수를 직접 읽어 비교한다. 문맥 패턴이 없는 항목은
    #   종전대로 존재 대조로 둔다 — 넓히다 오탐이 나면 사람이 검사를 끈다.
    # 라벨 → 그 수가 실제로 적히는 자리. 여기 있는 것만 문맥 대조한다.
    # ★ 2026-10-08 (DECISIONS §435). 「norm 이관 종수」가 여기 **없었다.** 라벨은
    #   `RULES` 에 9월부터 있었는데 문맥 패턴이 없어 존재 대조로 떨어졌고,
    #   MASTER 어디든 `14` 라는 수가 있으면 통과했다 — `datasets 41종` 이 초록불로
    #   살아 있던 바로 그 꼴이다(위 ★). 문맥 패턴 없는 라벨은 **검사하는 척**한다.
    #   세 자리(§18 계층 표 · 레이크 절 · 대장 규모 절)가 전부 「텍스트 N종 이관」
    #   서식이라 패턴 하나가 셋을 다 읽는다.
    CONTEXT_PAT = {
        "대장 datasets 종수": r"`datasets` (\d+)종",
        "대장 retired 종수": r"`retired` (\d+)종",
        "norm 이관 종수": r"텍스트 \*{0,2}(\d+)종 이관",
        # ★ 2026-10-09 (§444 · #142). `no_cctv_band 183(…` 꼴. 사유 이름이
        #   앵커라 **산문 어디든** 걸리고, 수만 다르면 운다.
        **{f"회색 사유 {k[3:]}": rf"{k[3:]}\s+(\d[\d,]*)"
           for k in c if k.startswith("ur_")},
        # ★ 「도달 가능」 **바로 뒤에 수가 오는 자리**만 읽는다. `도달 가능성` ·
        #   `도달 가능할` · `도달 가능이 957 → 90`(지난 일)은 안 걸린다 —
        #   낱말이 붙으면 수가 안 따라오기 때문이고, 그것이 이 패턴의 울타리다.
        "도달 가능": r"도달 가능\s+\*{0,2}(\d[\d,]*)",
        # ★ 2026-10-11 (DECISIONS §464-2 · PLAN #167 닫힘). 이 라벨은 2026-09-16
        #   부터 `RULES` 에 있었는데 **문맥 패턴이 없어 존재 대조**였다 — MASTER
        #   어디든 `451` 이라는 수가 있으면 초록이다. 2026-10-11 에 그 수가 낡았고
        #   조용히 통과했다. 패턴 없는 라벨은 **검사하는 척**한다(§435 와 같은 자리).
        #   ★ 조사가 붙은 자리는 안 문다 — 「유효범위 안이 **126**」(§7-2 · 폭
        #     3~7m 대역)은 다른 축이고, `안\s+` 이 그 울타리다.
        "CCTV 유효범위 안": r"CCTV 유효범위 안\s+\*{0,2}(\d[\d,]*)",
    }

    for rel, want, label in RULES:
        pat = CONTEXT_PAT.get(label)
        txt = read(rel)
        if pat:
            got = [int(g.replace(",", "")) for g in re.findall(pat, txt)]
            wrong = [g for g in got if g != want]
            if wrong:
                out.append(f"{rel:16s} {label} {wrong} → {want}")
                continue
            if not got:
                out.append(f"{rel:16s} {label} 서술을 못 찾았다 — 패턴이 낡았다")
            continue
        if not any(t in read(rel) for t in fmt(want)):
            out.append(f"{rel:16s} {label} {want} 없음")

    return out

