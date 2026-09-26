#!/usr/bin/env python3
"""
test_scopedecl.py — 메타 강제자가 **빈 그물이 아닌가.**

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-24 (DECISIONS §226). `tools/scopedecl.py` 는 「강제자가 자기 범위를
  선언하는가」를 본다. 그런데 **그 도구 자신이 죽으면 저장소 전체가 조용히
  초록이 된다** — 메타 강제자일수록 자기검사가 없으면 위험하다.
  `dms` 가 417 을 재현 못 해 분모를 갈아탄 것과 같은 자리다(2026-09-13).

★ 이 파일이 드는 것은 셋이다 —
  ① 판정기가 다섯 갈래를 전부 운다        (`--selftest` 를 여기서도 돈다)
  ② 수집기가 저장소에서 실제로 뭔가를 센다 (0건이 청결인지 죽음인지 가른다)
  ③ 면제가 살아 있다                        (죽은 면제는 사각지대다)

IN    tools/scopedecl.py
OUT   없음 (검사)
밖    **`밖` 칸의 내용이 참인가는 안 본다.** 문장이 있는지만 본다 —
      참·거짓은 사람이 읽고 판단한다. 그리고 이 파일은 `scopedecl` 의
      ② 자동 탐지가 **옳은 짝을 찾았는가**까지는 안 본다. 그쪽은
      `scopedecl --selftest` 의 합성 입력이 든다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import scopedecl

ROOT = Path(__file__).resolve().parents[1]


def test_selftest_passes():
    """판정기가 다섯 갈래를 전부 운다."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "scopedecl.py"),
                        "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, f"자기검사 실패\n{r.stdout}{r.stderr}"


def test_collector_is_alive():
    """수집기가 실제로 강제자를 모은다. 0건은 청결이 아니라 죽음이다."""
    ens = scopedecl.enforcers()
    assert len(ens) >= 100, f"강제자를 {len(ens)}개밖에 못 모았다"
    names = {p.name for p in ens}
    for must in ("verify.sh", "fl.sh", "golden.py", "test_guards.py"):
        assert must in names, f"{must} 를 강제자로 안 본다 — 수집기가 좁다"


def test_suffix_census_is_alive():
    """실물 접미사 수집기가 죽으면 ② 가 통째로 0건이 된다."""
    assert scopedecl.real_suffixes("tools") >= {".py", ".sh"}
    assert scopedecl.real_suffixes("src") == {".py"}
    assert scopedecl.real_suffixes("없는디렉터리") == set()


def test_ratchets_match_reality():
    """래칫 둘이 실물과 같은가. 갈리면 초록으로 위장한다(W4-9)."""
    ens, missing, st, gap = scopedecl.measure()
    assert len(missing) == scopedecl.NO_DECL, (
        f"`밖` 칸 없는 강제자 — 선언 {scopedecl.NO_DECL} · 실측 {len(missing)}")
    assert len(st) == scopedecl.SELFTEST_MIN, (
        f"`--selftest` — 선언 {scopedecl.SELFTEST_MIN} · 실측 {len(st)}")
    assert gap == [], "이름보다 좁은 범위가 선언 없이 있다:\n  " + "\n  ".join(
        f"{a} — {b}/ 의 {c}" for a, b, c in gap)


def test_gap_exemptions_are_alive():
    """죽은 면제는 사각지대다. 면제한 짝이 실제로 탐지 대상이어야 한다."""
    dead = []
    for (rel, d, suf), why in scopedecl.GAP_EXEMPT.items():
        p = ROOT / rel
        if not p.exists():
            dead.append(f"{rel} — 파일이 없다")
            continue
        if not why.strip():
            dead.append(f"{rel} — 사유가 비었다")
        if d not in {x for x, _ in scopedecl.scopes(p)}:
            dead.append(f"{rel} — 더 이상 `{d}/` 를 훑지 않는다")
        if suf in scopedecl.real_suffixes(d) and suf in p.read_text(
                encoding="utf-8", errors="ignore"):
            dead.append(f"{rel} — 이제 `{suf}` 를 본다. 면제를 지워라")
    assert not dead, "죽은 ② 면제:\n  " + "\n  ".join(dead)


def test_declaration_reader_needs_the_column_not_the_word():
    """산문 속 「안 보는 것」은 칸이 아니다. 줄머리 `밖` 두 칸만 칸이다."""
    assert scopedecl.DECL_RE.search("밖    셸은 안 본다")
    assert scopedecl.DECL_RE.search("IN  x\n밖    셸은 안 본다\n")
    assert not scopedecl.DECL_RE.search("이 검사는 셸을 안 보는 것이 맞다")
    assert not scopedecl.DECL_RE.search("밖 한칸은아니다")
