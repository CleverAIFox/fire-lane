"""
raw_ext.py — **대장이 쓰는 확장자.** 손목록이 아니라 유도다.

★ 2026-10-14 (DECISIONS 535-4). `normalize_raw` 안에 있던 유도를 여기로
  뺀다. 그 파일이 선언 예외(668줄)를 넘어 722줄이 됐고, **느슨해지는 쪽으로
  예외를 올리는 것은 받아적을 일이 아니다**(§431). 옮기면 둘 다 제자리다 —
  `normalize_raw` 는 「규칙 표」, 이 파일은 「대장이 쓰는 확장자」 하나씩 든다.

★ 옮긴 것과 고친 것을 한 커밋에 섞지 않는다(원칙 ⑤) — 로직은 한 글자도
  안 바꿨다. 바뀐 것은 **자리와 이름**(`_ext_alt` → `ext_alt`)뿐이다.

IN    sources.yaml (대장) — `acquire_rules.dataset_globs()` 를 거쳐 읽는다
OUT   확장자 집합 · 정규식 교대 문자열
PARAM 없음
밖    대장을 읽는다. **import 시점에는 안 읽는다** — 부르는 쪽이 읽는다.
"""
from __future__ import annotations

#: **압축 안에서 나오는** 확장자. 대장 글롭에 안 적히므로 유도가 못 낸다.
#: ★ 이 넷은 **자산이 늘어도 안 는다** — `ngi`·`nda` 는 수치지형도가 zip
#:   안에 담아 오는 꼴이고 `geojson`·`xls` 는 그 안에서 풀려 나온다.
INNER_EXT = frozenset({"geojson", "nda", "ngi", "xls"})


def ledger_ext() -> frozenset[str]:
    """**대장이 쓰는 확장자.** `files` 글롭의 꼬리에서 유도한다.

    ★ 2026-10-14 (DECISIONS 535-4). 종전에는 이 목록이 **손으로** 적혀 있었고
      그 상수 주석이 「hwp·pdf·ngi·nda 가 없어 왕복 멱등이 거짓이었던 이력」을
      적고 있었다. 2026-10-14 에 `xlsx` 가 빠져 **네 번째**가 났다.

      손목록은 자산이 늘 때마다 빠진다. **대장이 이미 그 답을 들고 있다** —
      `gjcity/..._20261008.xlsx` 라고 적혀 있으면 `xlsx` 는 거기서 나온다.
      따로 적을 이유가 없고, 적으면 갈린다(§18-3).

    ★ 유도가 못 내는 것만 `INNER_EXT` 가 받는다 — 그 집합은 **자산과 무관**해서
      자산이 늘어도 안 큰다. 그것이 손목록을 남겨도 되는 유일한 꼴이다.

    ★ `acquire_rules.dataset_globs()` 를 쓴다 — 그것이 「대장이 어떤 파일을
      기다리는가」의 **정본**이고, `files` 만 읽으면 16개밖에 안 보인다
      (`stem`·`parts` 에서 유도되는 것이 나머지다).
    """
    from firelane.acquire_rules import dataset_globs

    out = set()
    for gs in dataset_globs().values():
        for g in (gs if isinstance(gs, list) else [gs]):
            name = str(g or "").rsplit("/", 1)[-1]
            if "." not in name:
                continue
            ext = name.rsplit(".", 1)[-1].lower()
            if not any(c in ext for c in "*?["):
                out.add(ext)
    return frozenset(out | INNER_EXT)


def ext_alt() -> str:
    """통과 규칙에 박을 **정규식 교대**. `ledger_ext()` 를 정렬해 잇는다.

    ★ 이름을 `PASSTHROUGH_EXT` 로 유지한다 — 소비자 넷(`normalize_raw` 자신과
      시험 셋)이 그 이름을 쓰고, 그것이 **정본의 이름**이다. 바뀐 것은
      「손으로 적는다」에서 「대장에서 유도한다」뿐이다.
    """
    return "|".join(sorted(ledger_ext()))
