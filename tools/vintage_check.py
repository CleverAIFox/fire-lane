#!/usr/bin/env python3
"""
vintage_check.py — 파일명의 날짜가 **자료 기준일인가, 내려받은 날인가.**

    uv run python tools/vintage_check.py            전수
    uv run python tools/vintage_check.py --max 3    상한. 넘으면 빨강
    uv run python tools/vintage_check.py --json
    uv run python tools/vintage_check.py --selftest  ★ 프로브가 살아 있나

── 왜 ─────────────────────────────────────────────────────────
`naming` 의 규약은 이렇게 적혀 있다 —

    vintage    ★ 데이터 기준일. 다운로드일이 아니다. YYYYMMDD|YYYYMM|YYYY

그런데 그것을 강제하는 `_plausible_date` 는 **형식만 본다.** 달력에
있는 날이면 통과한다. 무엇을 뜻하는 날인지는 아무도 안 본다.

    규약이 있고 강제자가 그 규약을 안 지킨다(원칙 ①·②).

대가는 실물로 나왔다 —

    its_nodelink   20260810 · 20260812 두 이름으로 **258MB 두 벌**
    hydrant_point  본체 20240207 인데 사이드카가 20260830

대장은 소스마다 `updated` 를 들고 있다. **그것이 자료 기준일의 정본이다.**
파일명의 vintage 와 대조하면 위 둘이 다 걸린다.

── 무엇을 보나 ────────────────────────────────────────────────
    V1  파일명 vintage ≠ 대장 updated      어느 쪽이 틀렸는지는 사람이 정한다
    V2  같은 stem 에 vintage 가 둘 이상     두 벌이다. 용량을 같이 낸다
    V3  대장에 없는 stem                   참고. 결함으로 안 센다(lakecheck 소관)

★ V1 을 자동으로 고치지 않는다. 파일명이 맞고 대장이 낡았을 수도 있다.
  어느 쪽이 정본인지는 **자료를 받은 사람만** 안다. 이 도구는 센다.

★ 레이크가 없으면 **실패다.** 0건이 아니다 — 못 쟀는데 깨끗하다고 하면
  안 된다(`lakecheck` 와 같은 방침).

IN    $FIRE_LANE_DATA/raw · sources.yaml
OUT   종료코드 = 결함 수 (--max 를 주면 상한 초과분)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from firelane import ledger as _led
from firelane import naming as nm
from firelane import paths  # noqa: F401  ★ import 만으로 .env 를 환경에 얹는다

ROOT = Path(__file__).resolve().parent.parent
DASH = re.compile(r"[^0-9]")


def _norm(v: str) -> str:
    """`2026-08-12` · `20260812` · `202608` 을 비교 가능한 꼴로."""
    return DASH.sub("", str(v or ""))


def _sources() -> dict:
    return _led.load_sources()


def _ledger_index() -> dict[str, tuple[str, str]]:
    """`provider_dataset` → (대장 키들, updated). 대장이 자료 기준일의 정본이다.

    ★ 한 stem 을 여러 항목이 나눠 쓴다 — `its_nodelink` 를 `node_link` ·
      `node_point` · `turn_restriction` 셋이 같이 본다. 덮어쓰면 마지막
      하나만 남아 보고가 엉뚱한 키를 가리킨다.
    """
    keys: dict[str, list[str]] = defaultdict(list)
    upd: dict[str, str] = {}
    for key, e in (_sources().get("datasets") or {}).items():
        stem = e.get("stem")
        if not stem:
            continue
        keys[str(stem)].append(key)
        upd.setdefault(str(stem), _norm(e.get("updated")))
    return {s: (" · ".join(sorted(ks)), upd[s]) for s, ks in keys.items()}


def scan(raw: Path) -> list[dict]:
    """★ **레이크를 직접 훑는다.** 대장 글롭으로만 보면 안 된다 —

    `node_link` 는 `files: [its/its_nodelink_kr_20260812.zip]` 로 한 벌을
    못박아놨다. 그래서 `paths_of` 로 보면 20260810 두 번째 벌이 **안 보인다.**
    대장이 안 가리키는 파일은 대장으로 못 찾는다. 258MB 가 그렇게 숨었다.
    """
    idx = _ledger_index()
    bucket: dict[str, dict[str, list[Path]]] = defaultdict(
        lambda: defaultdict(list))
    unknown: set[str] = set()
    for p in sorted(raw.rglob("*")):
        if not p.is_file() or _led.is_acquisition_meta(p):
            continue
        try:
            n = nm.parse(p.name, strict=False)
        except Exception:          # noqa: BLE001  이름이 규약 밖이면 fsck 소관
            continue
        stem = f"{n.provider}_{n.dataset}"
        if stem not in idx:
            unknown.add(stem)
            continue
        bucket[stem][_norm(n.vintage)].append(p)

    def mb(fs):
        return round(sum(f.stat().st_size for f in fs) / 2**20, 1)

    out = []
    for stem, seen in sorted(bucket.items()):
        key, want = idx[stem]
        for got, files in sorted(seen.items()):
            # ★ 길이가 다르면 앞자리로 견준다 — `202608` 과 `20260812` 는
            #   어긋난 것이 아니라 정밀도가 다른 것이다.
            k = min(len(got), len(want)) or 1
            if want and got[:k] != want[:k]:
                out.append({"kind": "V1", "key": key, "stem": stem,
                            "vintage": got, "updated": want,
                            "files": [str(f.relative_to(raw)) for f in files],
                            "mb": mb(files)})
        if len(seen) > 1:
            out.append({"kind": "V2", "key": key, "stem": stem,
                        "vintages": sorted(seen),
                        "mb": {v: mb(fs) for v, fs in sorted(seen.items())}})
    for stem in sorted(unknown):
        out.append({"kind": "V3", "key": "(대장 밖)", "stem": stem})
    return out


def selftest() -> int:
    """★ 0건은 레이크가 깨끗할 때도, 프로브가 죽었을 때도 나온다."""
    bad = []
    if _norm("2026-08-12") != "20260812":
        bad.append("날짜 정규화가 깨졌다")
    if _norm("2026-08-12") == _norm("2026-08-10"):
        bad.append("다른 날짜를 같다고 한다")
    try:
        if nm.parse("its_nodelink_kr_20260810.zip", strict=False).vintage \
                != "20260810":
            bad.append("파일명에서 vintage 를 못 뽑는다")
    except Exception as exc:       # noqa: BLE001
        bad.append(f"파일명 파싱이 터진다: {exc}")
    # 앞자리 비교가 정밀도 차이를 오탐하지 않는가
    got, want = "202608", "20260812"
    if got[:min(len(got), len(want))] != want[:min(len(got), len(want))]:
        bad.append("정밀도가 다른 날짜를 어긋난 것으로 센다")
    for line in bad:
        print(f"  {line}")
    print("selftest " + ("빨강" if bad else "초록"))
    return len(bad)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None,
                    help="허용 상한. ★ 지금 값에서 시작해 내린다")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    raw = paths.DATA and Path(paths.DATA) / "raw"
    if not raw or not raw.is_dir():
        print("✗ FIRE_LANE_DATA 가 없거나 폴더가 아니다 — 아무것도 못 잰다")
        print("  ★ 0건이 아니라 실패다. 프로브가 조용히 통과하면 안 된다")
        return 1

    hits = scan(raw)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return min(len(hits), 255)

    v1 = [h for h in hits if h["kind"] == "V1"]
    v2 = [h for h in hits if h["kind"] == "V2"]
    v3 = [h for h in hits if h["kind"] == "V3"]
    hits = v1 + v2                       # ★ V3 는 참고다. 결함으로 안 센다
    print(f"vintage 결함 {len(hits)}  (V1 어긋남 {len(v1)} · V2 두 벌 {len(v2)})"
          f"  · 대장 밖 stem {len(v3)}\n")
    for h in v1:
        print(f"  V1  {h['key']}   파일명 {h['vintage']} ↔ 대장 {h['updated']}"
              f"   {h['mb']}MB")
        for f in h["files"][:3]:
            print(f"        {f}")
    for h in v2:
        print(f"  V2  {h['key']}   vintage {len(h['vintages'])}벌")
        for v in h["vintages"]:
            print(f"        {v}   {h['mb'][v]}MB")
    for h in v3[:10]:
        print(f"  참고  {h['stem']}   대장에 없다")
    if hits:
        print("\n★ 어느 쪽이 정본인지는 자료를 받은 사람만 안다. 도구는 센다.")
        print("  대장 `updated` 를 고치든 파일을 버리든, 고친 뒤 다시 돌려라.")
    if a.max is None:
        return min(len(hits), 255)
    if len(hits) > a.max:
        print(f"\n✗ 상한 {a.max} 을 넘었다 ({len(hits)}). 늘었다.")
        return min(len(hits) - a.max, 255)
    if len(hits) < a.max:
        print(f"\n★ 상한 {a.max} 보다 {a.max - len(hits)} 적다. "
              f"`--max {len(hits)}` 로 조여라 — 안 조이면 되돌아간다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
