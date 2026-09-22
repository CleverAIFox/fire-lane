#!/usr/bin/env python3
"""
freshcheck.py — 커밋된 생성물이 왜 낡았는지를 **자리로** 말한다.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §13 W4-10). 종전 검사는 `verify.sh` 안의 한 줄이었다.

    git diff --quiet -- web/data data/processed

이것은 **파일 이름까지만** 말한다. 실물을 보면 그것으로는 모자란다 —
2026-09-20 배치에서 두 매니페스트가 48줄씩 움직였고, 그중 47줄이
`datasets.*.seal.code`(ingest 코드 닫힘 지문)였다. `src/firelane/prep.py`
를 고쳤으니 **움직이는 것이 옳다.** 나머지 한 줄은 `generated_at` 이다.

문제는 그 48줄이 **판정값이 드리프트한 경우와 화면에서 똑같이 보인다**는
것이다. 검사가 내놓는 것은 파일 이름 둘과 「생성물이므로 그대로 커밋하면
된다」는 문장뿐이고, 그 문장은 사람에게 **도장을 찍는 법**을 가르친다.
2026-09-19 의 재커밋에는 봉인 `cfg` 가 실제로 바뀐 것이 섞여 있었는데
48줄 사이에 묻혀 아무도 안 봤다.

★ **이 도구는 관대해지려고 있는 것이 아니다.** 시각만 움직인 경우는
  `firelane.manifest.write_stable()` 이 **이미 안 쓴다** — 그래서 실무에서
  거의 안 생긴다. 이 도구가 바꾸는 것은 통과·빨강의 경계가 아니라
  **빨강일 때 사람이 보는 것**이다. 경계는 종전과 같게 둔다.

★ 2026-09-20 정정 — 이 자리에 처음 적었던 결함 서술은 **틀렸다.**
  「`generated_at` 때문에 구조적으로 빨갛다」고 적었는데, `write_stable`
  이 그것을 이미 막고 있었다. 저장소가 답을 들고 있는데 안 읽고 새로
  만들려 한 것이고 DECISIONS §198 이 적은 형태의 세 번째 인스턴스다.

── 무엇을 보는가 ───────────────────────────────────────────────
바뀐 자리마다 이름을 붙여 센다.

    시각      `generated_at`                    — 통과 사유가 된다
    코드봉인  `*.seal.code`                     — 파이프라인 코드가 바뀌었다
    설정봉인  `*.seal.cfg`                      — 대장 설정이 바뀌었다
    원본봉인  `*.seal.raw`                      — 원자료가 바뀌었다
    파생      **함께 바뀐 다른 파일**의 `sha256`·`bytes`
    산출값    그 밖의 모든 자리                 — ★ 여기가 진짜다

시각·파생만이면 통과, 그 밖에는 빨강이다. 빨강일 때 **자리 이름을
전부 적는다** — 사람이 도장을 찍을 수 없게 한다.

IN    git (HEAD 대 작업 트리) · 경로 인자
OUT   없음 (검사). 시각·파생 밖의 차이가 있으면 종료코드 1
PARAM --paths     검사할 경로들 (기본: web/data data/processed)
      --selftest  자체시험만 돌고 끝낸다
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from firelane.generated import for_role

# 실행마다 반드시 달라지는 필드. 내용이 아니다.
# ★ `firelane.manifest.STAMP_KEYS` 와 같은 뜻이다. 합치지 않은 이유 —
#   그쪽은 「쓸까 말까」를 정하고 이쪽은 「왜 바뀌었나」를 말한다. 같은
#   상수를 두 물음이 쓰는 것이라 정본화하면 한쪽 변경이 다른 쪽 판정을
#   조용히 움직인다. 대신 `tests/test_freshcheck.py` 가 둘이 같은지를 든다.
NONDET = frozenset({"generated_at"})

DERIVED_BLOCKS = frozenset({"source"})
DERIVED_KEYS = frozenset({"sha256", "bytes"})

# 봉인 칸의 이름 → 사람이 읽을 분류. `shardseal.make()` 가 내는 네 칸이다.
SEAL_KIND = {"code": "코드봉인", "cfg": "설정봉인", "raw": "원본봉인", "out": "산출봉인"}


def canon(obj: Any) -> Any:
    """비결정 필드를 뺀 정규형."""
    if isinstance(obj, dict):
        return {k: canon(v) for k, v in obj.items() if k not in NONDET}
    if isinstance(obj, list):
        return [canon(v) for v in obj]
    return obj


def diff_spots(a: Any, b: Any, trail: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """canon 끼리 다른 자리들의 키 경로. 값은 안 담는다."""
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[tuple[str, ...]] = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append((*trail, k))
            else:
                out += diff_spots(a[k], b[k], (*trail, k))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [trail]
        out = []
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            out += diff_spots(x, y, (*trail, str(i)))
        return out
    return [] if a == b else [trail]


def kind_of(spot: tuple[str, ...], changed_names: frozenset[str]) -> str:
    """한 자리의 분류. 모르는 것은 전부 `산출값` 이다 — 모름을 통과로 안 둔다.

    ★ `source.<이름>.sha256` 은 **독립된 정보가 아니다** — 그 이름의 파일에서
      계산된 값이다. 그래서 그 파일이 이번에 **함께 바뀌었으면** 이 자리는
      파생이고, 파일 자신의 분류가 진실을 든다(그 파일이 빨가면 전체가 빨갛다).
      반대로 **그 파일은 안 바뀌었는데 여기 sha 만 움직였다면** 둘이 어긋난
      것이므로 산출값이다 — 그쪽이 훨씬 무겁다.
    """
    if len(spot) >= 2 and spot[-2] == "seal" and spot[-1] in SEAL_KIND:
        return SEAL_KIND[spot[-1]]
    if (len(spot) == 3 and spot[0] in DERIVED_BLOCKS and spot[2] in DERIVED_KEYS
            and spot[1] in changed_names):
        return "파생"
    return "산출값"


def classify(old: Any, new: Any, changed_names: frozenset[str]) -> dict[str, list[str]]:
    """자리들을 분류별로 모은다. 시각만 움직였으면 빈 dict."""
    groups: dict[str, list[str]] = {}
    for spot in diff_spots(canon(old), canon(new)):
        groups.setdefault(kind_of(spot, changed_names), []).append(".".join(spot))
    return groups


def is_clean(groups: dict[str, list[str]]) -> bool:
    """통과 경계. 종전과 같다 — 파생 밖의 자리가 하나라도 있으면 빨강."""
    return not (set(groups) - {"파생"})


def _head_bytes(path: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def run(paths: list[str]) -> int:
    out = subprocess.run(["git", "diff", "--name-only", "--", *paths],
                         capture_output=True, text=True, check=True).stdout
    changed = [ln for ln in out.splitlines() if ln]
    if not changed:
        print("생산자 재실행과 커밋본이 같다")
        return 0

    # ── 1차 — 이번에 함께 바뀐 파일 이름을 모은다. 2차의 `파생` 이 여기에 기댄다.
    loaded: dict[str, tuple[Any, Any]] = {}
    names: set[str] = set()
    for p in changed:
        raw_old = _head_bytes(p)
        if raw_old is None or not p.endswith(".json"):
            continue
        try:
            old = json.loads(raw_old)
            with open(p, "rb") as f:
                new = json.loads(f.read())
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        loaded[p] = (old, new)
        names.add(p.rsplit("/", 1)[-1])

    red = False
    print("★ 파이프라인 산출이 커밋본과 다르다. 자리마다 무엇인지 —\n")
    for p in changed:
        if p not in loaded:
            red = True
            print(f"  ✗ {p}\n        JSON 이 아니거나 새로 생겼거나 못 읽는다 — 손으로 봐라")
            continue
        groups = classify(*loaded[p], frozenset(names))
        clean = is_clean(groups)
        red = red or not clean
        if not groups:
            print(f"  · {p}\n        시각만 움직였다")
            continue
        print(f"  {'·' if clean else '✗'} {p}")
        for kind in sorted(groups):
            spots = groups[kind]
            head = ", ".join(spots[:3])
            more = f" … 외 {len(spots) - 3}" if len(spots) > 3 else ""
            print(f"        [{kind}] {len(spots)}자리 — {head}{more}")

    if not red:
        print("\n내용은 같다 — 시각·파생만 움직였다.")
        return 0

    print("\n  분류가 코드·설정·원본 봉인뿐이면, 그 배치가 그 층을 고쳤다는 뜻이다.")
    print("  ★ `산출값` 이 하나라도 있으면 멈춰라 — 판정이 움직였을 수 있다.")
    print("    golden 이 불변인지 먼저 보고, 불변이면 커밋본이 뒤처진 것이다(PLAN #70).")
    return 1


def selftest() -> int:
    """긍정·부정 대조. **덮어주는 쪽을 특히 본다.**"""
    bad = []
    base = {"generated_at": "A", "v": 1,
            "datasets": [{"seal": {"code": "c1", "cfg": "g1"}}],
            "source": {"x.json": {"sha256": "aa", "bytes": 3}}}

    # ① 시각만 — 통과
    if not is_clean(classify(base, {**base, "generated_at": "B"}, frozenset())):
        bad.append("시각만인데 빨갛다")

    # ② 산출값 — 울고, 분류가 `산출값` 이어야 한다
    g = classify(base, {**base, "v": 2}, frozenset())
    if is_clean(g) or "산출값" not in g:
        bad.append(f"내용 변경을 산출값으로 안 봤다: {g}")

    # ③ 봉인은 이름이 붙는다 — 여전히 빨강이되 무엇인지 말한다
    nb = json.loads(json.dumps(base)); nb["datasets"][0]["seal"]["code"] = "c2"
    g = classify(base, nb, frozenset())
    if is_clean(g) or list(g) != ["코드봉인"]:
        bad.append(f"코드봉인을 그렇게 안 불렀다: {g}")

    # ④ 파생 — 가리킨 파일이 **이번에 함께 바뀌었을** 때만
    nd = {**base, "source": {"x.json": {"sha256": "bb", "bytes": 3}}}
    if not is_clean(classify(base, nd, frozenset({"x.json"}))):
        bad.append("함께 바뀐 원본의 sha 를 파생으로 안 봤다")

    # ⑤ ★ 되돌림 — 그 파일이 **안 바뀌었는데** 여기 sha 만 움직였으면 산출값이다.
    #   둘이 어긋난 것이고, 이 대조가 없으면 검사가 그 어긋남을 덮는다.
    if is_clean(classify(base, nd, frozenset())):
        bad.append("안 바뀐 원본의 sha 가 움직였는데 덮었다")

    # ⑥ 모르는 키는 산출값이다
    nu = json.loads(json.dumps(base)); nu["source"]["x.json"]["새키"] = 1
    if "산출값" not in classify(base, nu, frozenset({"x.json"})):
        bad.append("source 안의 모르는 키를 덮었다")

    # ⑦ 중첩 generated_at
    if canon({"a": {"generated_at": "A", "b": 1}}) != {"a": {"b": 1}}:
        bad.append("중첩 generated_at 을 안 뺐다")

    for b in bad:
        print(f"  ✗ {b}")
    print("selftest 통과 — 대조 일곱" if not bad else f"\nselftest 실패 {len(bad)}건")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    # 기본값의 정본은 firelane/generated.py 의 역할 "fresh" 다(W3-13).
    ap.add_argument("--paths", nargs="*", default=list(for_role("fresh")))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if selftest() != 0:
        print("★ 자체시험이 빨갛다 — 검사 자신을 못 믿는다.")
        return 1
    return run(a.paths)


if __name__ == "__main__":
    sys.exit(main())
