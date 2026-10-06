#!/usr/bin/env python3
"""
verdict_tally.py — 판정 네 수를 **한 줄로** 센다. 이동을 적기 위한 도구다.

    uv run python tools/verdict_tally.py data/processed/segments.geojson
    git show HEAD:data/processed/segments.geojson | uv run python tools/verdict_tally.py -
    uv run python tools/verdict_tally.py --selftest

── 왜 생겼나 (DECISIONS §319) ──────────────────────────────────
판정이 움직이는 배치는 **전후 값을 PR 본문에 적는다**(§13-5 규칙 2). 그 「전」은
`git show HEAD:…` 안에 있고 「후」는 작업 트리에 있다 — 둘 다 같은 셈이다.
그런데 그 셈을 적는 자리가 없어서 사람이 두 번 눈으로 세었고, 2026-09-30
실기에서 **그 수가 문서와 안 맞은 채로** 여덟 단계가 빨갰다.

★ 파일 경로 하나만 받는다. 「어느 판인가」는 부르는 쪽이 정한다 — `git show` 든
  작업 트리든 여기는 모른다. 그래야 전후를 같은 도구로 잴 수 있다.

IN    GeoJSON 하나 (경로 또는 `-` 로 표준입력)
OUT   표준출력 한 줄  `구간 1281 · clear 465 · needs_cv 226 · blocked 191 · unknown 399`
PARAM 없다
밖    **판정을 안 한다.** 어느 수가 옳은가도, 움직여도 되는가도 안 본다 —
      그것은 사람의 판단이고(§13-5 규칙 2) 여기는 세기만 한다.
      **문서를 안 고친다.** 생성 블록을 채우는 것은 `tools/docgen.py` 다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

#: 발행 어휘. 여기 없는 값이 나오면 **조용히 빠지지 않고** 따로 찍는다.
VERDICTS = ("clear", "needs_cv", "blocked", "unknown")


def tally(src: str | Path) -> dict[str, int]:
    """`{"n": 구간수, "clear": …}`. `-` 면 표준입력."""
    raw = sys.stdin.read() if str(src) == "-" else Path(src).read_text(encoding="utf-8")
    feats = json.loads(raw)["features"]
    v = collections.Counter(f["properties"]["verdict"] for f in feats)
    out = {"n": len(feats), **{k: v[k] for k in VERDICTS}}
    # ★ 모르는 어휘를 **숨기지 않는다.** 네 수의 합이 구간 수와 다르면
    #   「전부 셌다」가 거짓이고, 그 거짓은 이동표를 통째로 못 믿게 만든다.
    if (extra := {k: n for k, n in v.items() if k not in VERDICTS}):
        out["★모르는 판정"] = sum(extra.values())
        out |= {f"★{k}": n for k, n in sorted(extra.items())}
    return out


def line(t: dict[str, int]) -> str:
    return (f"구간 {t['n']} · " + " · ".join(f"{k} {t[k]}" for k in VERDICTS)
            + "".join(f" · {k} {n}" for k, n in t.items()
                      if k.startswith("★") and k != "★모르는 판정"))


def selftest() -> int:
    """**모르는 어휘가 조용히 빠지지 않는가.** 그것이 이 도구의 유일한 위험이다."""
    import tempfile
    fails = []
    doc = {"features": [{"properties": {"verdict": v}} for v in
                        ("clear", "clear", "blocked", "구멍")]}
    with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False,
                                     encoding="utf-8") as f:
        json.dump(doc, f)
        q = f.name
    try:
        t = tally(q)
        if t["n"] != 4 or t["clear"] != 2 or t["blocked"] != 1:
            fails.append(f"세는 것이 틀렸다 — {t}")
        if t.get("★모르는 판정") != 1:
            fails.append("모르는 어휘를 조용히 흘렸다 — 합이 구간 수와 안 맞는다")
        if "구멍" not in line(t):
            fails.append("모르는 어휘를 한 줄에 안 적는다")
    finally:
        Path(q).unlink(missing_ok=True)
    for f in fails:
        print(f"  ✗ {f}")
    print("✓ 자기검사 통과" if not fails else f"✗ {len(fails)}건")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    rest = list(sys.argv[1:] if argv is None else argv)
    if rest == ["--selftest"]:
        return selftest()
    if len(rest) != 1 or rest[0].startswith("--"):
        print(__doc__.strip())
        return 2
    print(line(tally(rest[0])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
