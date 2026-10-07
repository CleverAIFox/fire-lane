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
           if (s := acquire.stale_files_decl(v or {}))}
    assert not bad, (
        "`files:` 가 낡았다 — 파생이 그 글롭 밖 경로를 낸다:\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in bad.items()))


def test_a_source_that_declares_many_vintages_is_not_derived():
    """★ `vintages`(복수)는 「판이 여럿」이라는 선언이다 — 파생하면 **나머지를 잃는다.**"""
    e = {"stem": "x_y", "ext": ["csv"], "scope": "kr", "updated": "2025-02-26",
         "vintages": ["2024-01-08", "2025-02-26"]}
    assert acquire._derive_files(e) == [], "판이 여럿인데 하나로 파생했다"
    assert acquire._derive_files({k: v for k, v in e.items() if k != "vintages"}), \
        "★ 반대 방향 — `vintages` 가 없으면 파생해야 한다"
