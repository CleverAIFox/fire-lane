"""
acquire_rules.py — **대장이 어디를 주장하나.** 선언 → raw 경로.

── 왜 생겼나 (2026-10-08 · DECISIONS §431 · PLAN #157) ────────
`tools/acquire.py` 가 **621줄**로 상한 600 을 넘었다. 그 파일의 일은 명령 넷
(`judge` · `verify` · `stage` · `prune-landing`)이고, 이 덩이는 그 넷이 **쓰는**
것이다 — 물음이 다르다. 쪼개면 「대장 선언에서 경로를 뽑는 규칙」이 혼자 서고,
시험이 명령을 안 깨우고 그 규칙만 민다.

★ **파생기가 둘이다**(§430-3 · `test_ledger_accessor.py` 가 대조한다) —

    `ledger.globs()`     느슨한 글롭. 「있나 없나」를 판정한다 (intake)
    `derive_files()`     정확한 경로. 「어디에 둘까」를 정한다 (acquire)

  둘 다 **파일 우선**이다. 선언이 있으면 그것이 정본이고, 파생은 없을 때만
  돈다. 둘 중 하나가 빈 목록을 내면 **반입이 중간에서 끊긴다.**

IN    `sources.yaml` (`datasets` · `retired`)
OUT   없음 — 경로 문자열만 돌려준다. **아무것도 안 옮긴다**
PARAM 없음
밖    **실물을 안 본다.** 「선언이 어디를 가리키나」만 답하고, 거기 파일이
      정말 있는지는 `acquire --verify` 와 `lakecheck` 가 든다. 그래서 이
      파일의 시험은 레이크 없이 돈다.
"""
from __future__ import annotations

import re

from firelane import lake
from firelane import ledger as _led

ledger = _led

def _yaml() -> dict:
    # ★ 2026-09-14. 종전에는 `or {}` 가 없어 빈 파일에서 None 을 냈다.
    #   같은 일을 하는 다섯 함수의 동작이 갈려 있었다.
    return ledger.load_sources()


def dataset_globs() -> dict[str, list[str]]:
    """대장 키 → 이 소스가 주장하는 raw 경로 **전부**.

    ★ 2026-08-27. 종전에는 `file` 단수만 냈다. 그래서 `ext: [hwp, pdf]`
      처럼 양판을 가진 소스의 `.pdf` 가 **영원히 고아**로 남아 매번
      격리 대상이 됐다. 2026-08-25 에 근거로 인용한 PDF 두 건이 그렇게
      내려갔다.

      대장이 `files` 리스트를 갖고 있는데 소비자가 안 읽는 상태였다 —
      **선언은 갱신됐는데 읽는 쪽이 안 따라간** 것이고, 오늘 반복된
      바로 그 형태다.

    ★ 2026-10-08 (DECISIONS §431). **순서를 뒤집었다.** 종전 주석은
      「재료가 있으면 재료가 이긴다」였는데, 같은 저장소의
      `ledger.globs()` 는 정반대로 「`files` 는 stem 으로 표현할 수 **없는**
      항목만 남는 명시적 글롭 예외」라고 적고 있었다 — **정본이 둘이고
      서로 반대였다.**

      실측이 갈랐다. 어긋나는 셋 중 **둘에서 파생이 파일을 잃는다** —
      `parking_enforce` 의 2024판, `roadtraffic_act` 의 `_a29`·`_a30`.
      잃은 파일은 「대장에 없다」로 판단 대기에 뜨고, 동시에 파생이 만든
      없는 이름이 「결손」으로 뜬다. **같은 파일이 양쪽에 있었다.**

      그래서 `ledger.globs()` 쪽으로 통일한다 — **`files` 가 있으면 정본**이고
      파생은 그것이 없을 때만. 「`files` 가 낡는다」는 종전의 걱정은
      우선순위가 아니라 **가드**가 든다(`test_acquire.py` · 어긋남 0).
    """
    out: dict[str, list[str]] = {}
    for k, v in _yaml().get("datasets", {}).items():
        v = v or {}
        out[k] = ledger.files_decl(v) or derive_files(v)
    return out


def derive_files(e: dict) -> list[str]:
    """재료(stem·scope·vintage·ext·parts) → raw 경로. 없으면 빈 목록.

    ★ [B] 의 핵심. `file` 은 파생값이고 재료가 정본이다. 재료가 갖춰진
      항목은 여기서 만들며, 그러면 대장과 실물이 어긋날 수 없다.
    """
    stems = e.get("stems") or ([e["stem"]] if e.get("stem") else [])
    exts = e.get("ext") or []
    scope = e.get("scope")
    if not (stems and exts and scope):
        return []
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", str(e.get("updated") or ""))
    vt = "".join(m.groups()) if m else str(e.get("vintage") or "")
    # ★ **8자리만 파생한다.** `vintage: 2025` 처럼 연도만 있으면 판이
    #   특정되지 않는다. 그런데도 파생하면 `..._2025.csv` 한 개를 만들고,
    #   실물 두 판(20240108 · 20250226)이 통째로 고아가 된다 —
    #   그러면 `--quarantine` 이 **살아 있는 파일을 내리려 든다**(08-27).
    #
    #   판이 여럿인 소스(`csv_table_multi`)는 글롭이 정답이다. 앞으로도
    #   판이 늘어나므로 목록을 손으로 유지하는 편이 더 나쁘다.
    if not re.fullmatch(r"\d{8}", vt):
        return []
    # ★ 2026-10-08 (DECISIONS §431). `vintages`(복수)는 **「판이 여럿」이라는
    #   선언**이다. 그런데도 `updated` 하나로 파생하면 **나머지 판을 전부
    #   잃는다** — `parking_enforce` 의 2024판이 그렇게 고아가 됐다.
    #   바로 위 주석이 이미 적고 있다: 「판이 여럿인 소스는 글롭이 정답이다」.
    if e.get("vintages"):
        return []
    parts = e.get("parts") or [None]
    out = []
    for st in stems:
        prov = str(st).split("_", 1)[0]
        for x in exts:
            for pt in parts:
                bits = [str(st), str(scope), vt] + ([str(pt)] if pt else [])
                out.append(f"{prov}/{'_'.join(bits)}.{x}")
    return sorted(set(out))


def stale_files_decl(e: dict) -> list[str]:
    """`files:` 가 **낡았나.**  (DECISIONS §431)

    `files` 를 정본으로 올렸으니(`dataset_globs`) 그것이 낡으면 조용히 파일을
    잃는다. 종전 주석이 걱정한 것이 바로 그것이고, 종전 답은 **우선순위**였다 —
    그런데 그 답이 `parking_enforce` 2024판과 `_a29`·`_a30` 을 잃게 만들었다.

    답은 우선순위가 아니라 **대조**다. 파생이 `files` 글롭 **밖**의 경로를 내면
    `files` 가 그 판을 모르는 것이다. 문자열이 같은지는 안 본다 —
    `ngii1k` 처럼 글롭 하나가 파생 둘을 덮는 것은 **같은 주장의 다른 꼴**이다.
    """
    from fnmatch import fnmatch

    fs = ledger.files_decl(e)
    if not fs:
        return []
    return [x for x in derive_files(e) if not any(fnmatch(x, g) for g in fs)]


def retired_names() -> dict[str, str]:
    """폐기 등재된 파일 이름 → 사유 첫 줄.

    ★ 2026-09-17 (DECISIONS §180). 해석을 `firelane.lake.retired_reasons` 로 옮겼다. 종전 판은 대장
      retired 블록을 직접 읽고, stem 글롭을 RAW 에 풀고, "활성이 이긴다" 땜질(§172-5)을 따로 들었다.
      지금 폐기 항목은 전부 파일 이름으로 적혀 있고(글롭 0 — `test_lake`) 해석기는 이름 주장이
      글롭 주장을 이긴다(§174-2). 두 규칙이 두 곳에 살면 다시 갈린다.
    """
    from firelane import ledger as _led
    return lake.retired_reasons(_led.load())
