#!/usr/bin/env python3
"""
test_acquire.py — **두 파생기가 같은 답을 내는가.**  (DECISIONS §431)

── 왜 생겼나 ──────────────────────────────────────────────────
대장 항목의 raw 경로를 내는 자가 둘이었고 **우선순위가 서로 반대**였다 —
`ledger.globs()` 는 「`files` 가 정본」, `acquire.dataset_globs()` 는
「재료가 이긴다」. 그래서 파생으로 못 만드는 이름(`_a29`·`_a30`, 판이 둘)이
**같은 파일인데 「결손」과 「대장에 없다」 양쪽에** 떴다.

순서를 `ledger.globs()` 쪽으로 맞추고, 종전 주석이 걱정한 「`files` 가 낡는다」는
우선순위가 아니라 **대조**로 막는다.

IN    tools/acquire.py · sources.yaml
OUT   없음 (검사)
PARAM 없음
밖    **레이크를 안 본다.** 대장과 코드만 읽으므로 어느 기계에서도 같은 답이다.
      실물이 실제로 거기 있는지는 `acquire --verify` 와 `lakecheck` 가 든다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from firelane import acquire_rules as ar

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("acquire", ROOT / "tools/acquire.py")
assert _spec and _spec.loader
acquire = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = acquire
_spec.loader.exec_module(acquire)

# ── `files` 와 파생이 어긋나지 않는다 (DECISIONS §431) ──────────
def test_the_declared_files_cover_every_derived_path():
    """★ **같은 파일이 「결손」과 「대장에 없다」 양쪽에 뜨던 자리.**

    `dataset_globs()` 가 `files` 를 정본으로 올렸으니 그것이 낡으면 조용히
    파일을 잃는다. 파생이 `files` 글롭 밖 경로를 내면 그게 낡았다는 뜻이다.
    """
    from firelane import ledger

    bad = {k: s for k, v in ledger.load_sources()["datasets"].items()
           if (s := ar.stale_files_decl(v or {}))}
    assert not bad, (
        "`files:` 가 낡았다 — 파생이 그 글롭 밖 경로를 낸다:\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in bad.items()))


def test_a_source_that_declares_many_vintages_is_not_derived():
    """★ `vintages`(복수)는 「판이 여럿」이라는 선언이다 — 파생하면 **나머지를 잃는다.**"""
    e = {"stem": "x_y", "ext": ["csv"], "scope": "kr", "updated": "2025-02-26",
         "vintages": ["2024-01-08", "2025-02-26"]}
    assert ar.derive_files(e) == [], "판이 여럿인데 하나로 파생했다"
    assert ar.derive_files({k: v for k, v in e.items() if k != "vintages"}), \
        "★ 반대 방향 — `vintages` 가 없으면 파생해야 한다"


# ── 대장의 stem 이 파서를 통과하는가 (DECISIONS §537) ───────────
def _stem_mismatches(ds: dict, globs: dict) -> list[tuple[str, str, str]]:
    """대장이 적은 stem 과 **그 이름을 파서가 읽은 stem** 이 어긋나는 자리.

    ★ 글롭은 못 잰다 — 구체 이름이 있어야 파서를 태운다. 그래서 `globs` 는
      `acquire_rules.dataset_globs()`(구체 경로)를 받는다. `ledger.globs()`
      쪽을 받으면 `**/stem_*` 가 와서 **이 자가 눈이 먼다** (실제로 그랬다).
    """
    from firelane.intake_name import stem_of

    out = []
    for k in sorted(globs):
        v = ds.get(k) or {}
        st = v.get("stem")
        if not st:
            continue
        stems = v.get("stems") or [st]
        for g in globs[k]:
            if any(c in g for c in "*?["):
                continue
            if (got := stem_of(g)) not in stems:
                out.append((k, st, got))
    return out


def test_every_ledger_stem_is_read_back_the_same_by_the_parser():
    """★ **반입이 「대장 항목이 없다」로 멈춘 자리.** 대장에 있었는데도.

    `intake_name.propose` 는 규칙이 지은 정규명을 `stem_of` 로 되읽어 대장을
    조회한다. 그러므로 대장의 `stem` 은 **파서를 통과해 자기 자신으로
    돌아와야** 한다. 2026-10-14 에 `safety_dongmyeong_fires_2022_2025` 로
    적었더니 파서가 연도를 제원으로 떼어내 `safety_dongmyeong_fires` 를
    돌려줬고, 조회가 어긋나 반입이 5단계에서 섰다.

    손으로 쓰는 것은 대장 하나다. 그러므로 **손이 미끄러지는 자리마다 자가
    있어야 한다** — 그러면 다음 사람은 반입하는 날이 아니라 적는 날에 안다.
    """
    from firelane import ledger

    bad = _stem_mismatches(ledger.load_sources()["datasets"], ar.dataset_globs())
    assert not bad, (
        "대장의 stem 을 파서가 다르게 읽는다 — 그 항목은 반입에서 "
        "「대장 항목이 없다」로 막힌다:\n  "
        + "\n  ".join(f"{k}: 대장 {st!r} ↔ 파서 {got!r}" for k, st, got in bad))


def test_the_stem_round_trip_probe_bites():
    """카나리아 — 연도를 끼운 stem 을 **실제로 잡는가.**"""
    ds = {"safety_x": {"stem": "safety_x_2022_2025"}}
    g = {"safety_x": ["safety/safety_x_2022_2025_jngj-dongmyeong_20261012.xlsx"]}
    assert _stem_mismatches(ds, g), "연도가 끼인 stem 을 안 잡았다"

    ok = {"safety_x": {"stem": "safety_x"}}
    g2 = {"safety_x": ["safety/safety_x_jngj-dongmyeong_20261012.xlsx"]}
    assert not _stem_mismatches(ok, g2), "★ 반대 방향 — 멀쩡한 것을 잡았다"

    blind = {"safety_x": ["**/safety_x_2022_2025_*"]}
    assert not _stem_mismatches(ds, blind), \
        "글롭으로는 못 잰다 — 이 자가 글롭을 받으면 눈이 먼다는 것을 밝힌다"
