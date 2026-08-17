#!/usr/bin/env python3
"""
docnum_check.py — 문서에 적힌 숫자가 산출물과 같은지 본다.

    uv run python tools/docnum_check.py

왜 필요한가
    2026-08-14 재실행으로 segments 1087 → 1102 가 됐다. `EXPECT` 와 MASTER §2
    표는 갱신됐으나 README · MASTER 산문 · PLAN 이 나흘간 옛 숫자를 말했다.
    계약 테스트 14종은 필드명과 `verdict` 어휘를 지키지만 숫자는 안 본다.
    사람이 문서를 고치는 것에 의존하면 같은 일이 반복된다.

무엇을 보나
    산출물에서 센 값이 문서에 **문자열로 존재하는지**만 본다.
    문서의 모든 숫자를 파싱하지 않는다. 갱신을 빠뜨리기 쉬운 지점만 고정한다.

무엇을 안 보나
    §13 데이터 이력 · §16 결정 사유의 옛 숫자. 작성 시점 기록이므로 옳다.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "data/processed/segments.geojson"


def counts() -> dict[str, int]:
    P = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    v = collections.Counter(p["verdict"] for p in P)
    return {
        "n": len(P),
        "clear": v["clear"],
        "needs_cv": v["needs_cv"],
        "blocked": v["blocked"],
        "unknown": v["unknown"],
        "in_emd": sum(1 for p in P if p["in_emd"]),
        "cctv_in": sum(1 for p in P if (p["cctv_dist_m"] or 9e9) <= 25),
    }


def fmt(n: int) -> tuple[str, ...]:
    """1102 를 문서가 쓰는 두 표기로 — `1102` 와 `1,102`."""
    return (str(n), f"{n:,}")


def main() -> int:
    if not SEG.exists():
        print(f"! {SEG} 없음 — pipeline 을 먼저 돌려라")
        return 1
    c = counts()

    # (파일, 있어야 할 숫자, 설명)
    RULES = [
        ("README.md", c["n"], "세그먼트 수"),
        ("README.md", c["clear"], "clear"),
        ("README.md", c["needs_cv"], "needs_cv"),
        ("README.md", c["blocked"], "blocked"),
        ("README.md", c["unknown"], "unknown"),
        ("README.md", c["in_emd"], "동명동 구간"),
        ("docs/MASTER.md", c["n"], "세그먼트 수"),
        ("docs/MASTER.md", c["clear"], "clear"),
        ("docs/MASTER.md", c["needs_cv"], "needs_cv"),
        ("docs/MASTER.md", c["blocked"], "blocked"),
        ("docs/MASTER.md", c["unknown"], "unknown"),
        ("docs/MASTER.md", c["cctv_in"], "CCTV 유효범위 안"),
    ]

    cache: dict[str, str] = {}
    bad = 0
    for rel, want, label in RULES:
        text = cache.setdefault(rel, (ROOT / rel).read_text(encoding="utf-8"))
        if not any(t in text for t in fmt(want)):
            print(f"! {rel:16s} {label} {want} 없음")
            bad += 1

    # EXPECT 자기모순 — verdict.unknown 과 unknown_reason 합이 달라선 안 된다
    src = (ROOT / "src/etl/pipeline.py").read_text(encoding="utf-8")
    for k in ("clear", "needs_cv", "blocked", "unknown"):
        if f'"{k}": {c[k]}' not in src:
            print(f"! pipeline.EXPECT   {k} {c[k]} 아님")
            bad += 1
    if f'"no_cctv": {c["unknown"]}' not in src:
        print(f"! pipeline.EXPECT   unknown_reason.no_cctv 가 unknown({c['unknown']}) 과 다르다")
        bad += 1

    if bad:
        print(f"\n★ {bad}건. 산출물이 정본이다. 문서를 고쳐라.")
        return 1
    print(f"문서·EXPECT 일치. segments {c['n']} · "
          f"clear {c['clear']} · needs_cv {c['needs_cv']} · "
          f"blocked {c['blocked']} · unknown {c['unknown']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
