#!/usr/bin/env python3
"""
test_place_idempotent.py — 배치가 멱등인가.

── 왜 생겼나 ───────────────────────────────────────────────────
`normalize_raw.py`(→ `place_raw.py`) 의 docstring 이 왕복 멱등을 약속한다:

    ★ 이미 규칙에 맞는 이름이면 그대로 배치한다.
      --in-place 로 한 번 정리한 폴더를 다시 원본으로 쓸 수 있어야 한다.

2026-08-24 오전에 이 약속이 **hwp·pdf·ngi·nda 에 대해 거짓**이었다.
`EXT` 화이트리스트에 그 넷이 없어서, 규칙명으로 한 번 정리한
`safety_kfs_pumptruck_20251224.hwp` 를 다시 넣으면 "규칙에 없는 파일" 로
떨어졌다. 주석이 약속한 것을 코드가 안 지켰고 아무도 몰랐다.

멱등이 깨지면 두 번 돌린 사람과 한 번 돌린 사람의 raw 가 갈린다.
기기 간 재현성 문제이므로 사고 등급이다.

★ 디스크를 쓰지 않는다. 규칙 표만 본다 — CI 에 SSD 가 없다.
"""
from __future__ import annotations

import pathlib
import re

import pytest

# 개명 과도기 동안 양쪽을 받는다. 개명이 끝나면 위 줄만 남긴다.
from firelane import naming as nm
from firelane import providers

try:
    from firelane import place_raw as M
except ImportError:  # pragma: no cover
    from firelane import normalize_raw as M


# ── 왕복 입력 — **실물에서 유도한다** (DECISIONS §494) ────────
# ★ 2026-10-12. 여기 손으로 적은 20줄이 있었고 머리말에 「실제 raw 에 있는
#   이름에서 가져왔다」고 적혀 있었다. **거짓이었다 — 20 중 15 가 raw 에
#   없는 이름이다.** 2026-08~09 의 개명(스코프 별칭 · 도엽→part)이 이 표에
#   안 따라왔고, 그 사이 이 파일은 **낡은 이름들끼리의 멱등**을 검사하고
#   있었다. 실물이 통과하는지는 아무도 안 물었다.
#
#   그중 하나(`eais_bldg_ledger_gjdonggu_20260817.csv`)는 대장이 **폐기**한
#   자산이다. 폐기한 것의 배치 멱등을 지키고 있었던 셈이다.
#
# ★ 그래서 목록을 지웠다. `data/_acquire.json` 이 raw 실물의 sha 대장이고,
#   거기서 전수를 가져온다 — 20줄 대표가 아니라 **89건 전부**다. 받는 것이
#   늘면 검사도 같이 는다. 손으로 적는 자리를 하나 줄이는 것이 §18-3 이다.
def _acquired() -> list[str]:
    import json
    f = pathlib.Path(__file__).resolve().parents[1] / "data" / "_acquire.json"
    return sorted(json.loads(f.read_text(encoding="utf-8"))["files"])


PRODUCED = _acquired()


def test_the_roundtrip_input_is_not_empty():
    """★ 빈 그물 — 목록이 비면 아래 전부가 **0건으로 초록**이다."""
    assert len(PRODUCED) > 50, (
        f"raw 실물 목록이 {len(PRODUCED)}건이다. `data/_acquire.json` 의 "
        "`files` 키가 바뀌었으면 여기도 옮겨라")


#  ★ 목록을 여기 적지 않는다. 정본은 layers.raw.providers 다.
#    test_provider_registry 가 사본을 금지한다.
ORG = providers.all()
EXT = M.PASSTHROUGH_EXT          # 정본. 이 사본에는 json 이 빠져 있었다


def rules():
    """main() 이 조립하는 것과 **같은** 규칙 표. 이제 진짜로 같다.

    ★ 2026-09-11 (B3). 위 TODO 를 닫았다. 재현하던 사본은 두 축에서
      낡아 있었다 — `[a-z0-9_]`(하이픈 없음) · EXT 에 json 없음.
      그래서 하이픈 별칭 파일과 json 이 **멱등 검사를 안 탔다.**
    """
    return M.passthrough_rules(ORG)


def place(basename: str):
    """규칙을 적용해 (폴더, 목적지명) 을 낸다. 매칭 실패면 None."""
    low = basename.lower()
    for pat, folder, tmpl in rules():
        m = re.search(pat, low)
        if not m:
            continue
        name = basename if tmpl is None else (
            tmpl.format(*m.groups()) if m.groups() else tmpl)
        return folder, name
    return None


@pytest.mark.parametrize("rel", PRODUCED)
def test_roundtrip_is_idempotent(rel):
    """규칙이 만든 이름을 다시 넣으면 같은 자리에 그대로 간다."""
    folder, name = rel.split("/", 1)
    got = place(name)
    assert got is not None, (
        f"{name} 이 규칙에 안 걸린다 — 이 파일은 규칙이 **만든** 이름이다.\n"
        f"  왕복 멱등이 깨졌다. EXT 화이트리스트나 폴백 규칙을 확인하라.\n"
        f"  (2026-08-24: hwp·pdf·ngi·nda 누락으로 같은 증상이 있었다)")
    assert got == (folder, name), (
        f"{name} 왕복 불일치\n"
        f"  1회차 → {folder}/{name}\n"
        f"  2회차 → {got[0]}/{got[1]}\n"
        f"  두 번 돌린 기계와 한 번 돌린 기계의 raw 가 갈린다")


@pytest.mark.parametrize("rel", PRODUCED)
def test_produced_name_matches_raw_naming(rel):
    """규칙이 만든 이름이 **파일명 문법 정본**을 만족한다.

    ★ 2026-10-12 (DECISIONS §494). 종전에는 여기서 정규식을 손으로 짰다 —
      기관 접두 뒤를 `[a-z0-9_]+` 로 받고 vintage 를 여덟 자리로 못박은
      한 줄이었다. 그 사본은 두 축에서 낡아 있었다: **하이픈을 안 받고**
      (`jngj-donggu` 가 전부 위반이 된다) YYYYMM vintage 도 안 받는다. 그래서 실물 이름을 넣으면 **정상 파일이
      위반으로** 나왔고, 그 때문에 위의 표를 낡은 이름으로 둬야 했다.

      문법의 정본은 `firelane.naming` 이다(§18-2). 다섯 번째 사본을 지운다.
    """
    folder, name = rel.split("/", 1)
    assert folder in ORG, f"{folder} 는 선언된 기관 폴더가 아니다"
    ok, warns = nm.check(name, folder=folder)
    assert ok, f"{rel} 이 파일명 문법 밖이다 —\n  " + "\n  ".join(warns)


def test_the_passthrough_whitelist_still_holds_the_four_that_broke_it():
    """★ 이 파일의 창립 축을 **직접** 든다 (DECISIONS §494).

    2026-08-24 의 증상은 `EXT` 화이트리스트에 `hwp`·`pdf`·`ngi`·`nda` 가
    없어서 규칙이 만든 이름을 규칙이 다시 못 잡는 것이었다. 종전에는 그
    화이트리스트를 **손으로 짠 정규식에 끼워** 간접으로 들었는데, 그
    정규식을 §494 가 걷어냈다. 그래서 여기서 직접 적어 둔다 — 간접으로
    들던 축은 중간 것을 치우는 날 **같이 사라진다.**
    """
    # ★ `PASSTHROUGH_EXT` 는 **정규식 교대**다(`hwpx?` 한 조각이 둘을 덮는다).
    #   그래서 목록으로 쪼개 보지 않고 **정규식에게 묻는다** — 쪼개면
    #   `hwp` 가 없다고 거짓으로 운다.
    for e in ("hwp", "hwpx", "pdf", "ngi", "nda", "json", "csv", "zip", "tif"):
        assert re.fullmatch(EXT, e), f"{e!r} 가 통과 확장자에서 빠졌다 — 멱등이 그만큼 깨진다"
    # ★ 음성 — 아무 확장자나 받으면 그 화이트리스트는 없는 것과 같다
    for e in ("exe", "dll", "part", "crdownload"):
        assert not re.fullmatch(EXT, e), f"{e!r} 를 통과시킨다 — 화이트리스트가 열렸다"


def test_rules_are_lowercase():
    """규칙에 대문자가 있으면 영원히 안 걸린다.

    매칭이 f.name.lower() 이므로 규칙도 소문자여야 한다.
    이 불변식을 깬 것이 KFS 2종 3주 누락의 원인이었다.
    """
    bad = M.assert_rules_are_lowercase()
    assert not bad, f"대문자 포함 규칙 {len(bad)}건: {bad}"


def test_extension_is_lowercase():
    """규칙이 만드는 이름에 대문자 확장자가 없다.

    SSD 스캔에서 .ZIP 이 나온 적이 있다. 대소문자 혼재는
    exFAT 과 ext4 사이에서 다른 파일이 되기도, 같은 파일이 되기도 한다.
    """
    bad = [n for n in PRODUCED
           if (s := n.rsplit(".", 1)[-1]) != s.lower()]
    assert not bad, f"대문자 확장자: {bad}"


def test_no_whitespace_in_produced_names():
    """규칙이 만드는 이름에 공백이 없다.

    landing 은 공백을 허용한다(원본 보존). raw 는 허용하지 않는다.
    """
    bad = [n for n in PRODUCED if " " in n]
    assert not bad, f"공백 포함: {bad}"


def test_every_required_file_is_reachable_by_rules():
    """REQUIRED 전건이 규칙으로 배치 가능하다.

    필수 파일인데 규칙이 없으면 재취득 때 landing 에 갇힌다.
    2026-08-23 의 `동구_불법 주정차_20250226.csv` 2.9MB 가 그랬다.
    """
    dead = [r for r in M.REQUIRED if place(r.split("/", 1)[1]) is None]
    assert not dead, (
        "REQUIRED 인데 규칙이 못 잡는 파일:\n  " + "\n  ".join(dead) +
        "\n  재취득하면 landing 에 갇힌다")
