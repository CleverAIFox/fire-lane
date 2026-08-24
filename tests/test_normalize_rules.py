#!/usr/bin/env python3
"""
test_normalize_rules.py — `normalize_raw.RULES` 전수 검사.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-24. `kfs_pumptruck` · `kfs_ladder_small` 두 종이 3주 동안 MISSING
이었다. 원인은 규칙 두 줄이 **대문자 `KFS`** 로 쓰인 것이다.

    low = f.name.lower()                        ← 매칭은 소문자로
    r"소방펌프차[_ ]?\\(?KFS.*\\.(hwpx?|pdf)$"     ← 규칙만 대문자

RULES 38줄 중 대문자를 포함한 정규식이 이 둘뿐이었고 MISSING 도 정확히
이 둘이었다. 같은 날 같은 폴더에서 받은 `mas` 두 종은 규칙이 전부 한글이라
통과했다.

**3주 동안 안 보인 이유는 이것이 실패가 아니었기 때문이다.**
`규칙에 없는 파일 N건 (건너뜀)` 을 찍고 종료코드 0 으로 끝난다.
`ingest` 는 뒤에서 `MISSING` 을 대장에 적지만 그것도 `FAIL` 이 아니다.
사람이 두 로그를 이어 붙여야만 보이는 사고였다.

이 저장소가 반복해 배운 그것이다 — **측정은 하는데 대조가 없다.**

IN    src/firelane/normalize_raw.py
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

from firelane import normalize_raw as N

ROOT = Path(__file__).resolve().parent.parent

# main() 이 지역 사본에 붙이는 통과 규칙. 값이 갈리면 안 되므로 여기 한 번만 적는다.
ORG = {"juso", "ngii", "its", "sbiz", "safety", "gjcity",
       "nsdi", "vworld", "eais"}
EXT = "zip|csv|tif|xml|hwpx?|pdf|ngi|nda|geojson"


def _rules(passthrough: bool):
    r = list(N.RULES)
    if passthrough:
        r += [(rf"^{o}_[a-z0-9_]+_\d{{8}}\.({EXT})$", o, None)
              for o in sorted(ORG)]
    return r


def _match(name: str, passthrough: bool = False):
    """normalize_raw.main() 과 같은 방식으로 규칙을 찾는다."""
    low = name.lower()
    for pat, folder, tmpl in _rules(passthrough):
        if m := re.search(pat, low):
            out = name if tmpl is None else (
                tmpl.format(*m.groups()) if m.groups() else tmpl)
            return folder, out
    return None


def test_rules_contain_no_uppercase():
    """매칭이 `.lower()` 이므로 규칙에 대문자가 있으면 영원히 안 걸린다."""
    bad = N.assert_rules_are_lowercase()
    assert not bad, (
        "규칙에 대문자 ASCII 가 있다. `low = f.name.lower()` 로 매칭하므로\n"
        "이 규칙은 어떤 파일에도 걸리지 않는다.\n  " + "\n  ".join(bad))


# 제공기관이 실제로 주는 이름. 규칙을 고칠 때 여기부터 늘린다.
SAMPLES = {
    "소방펌프차(KFS-1-0073-2025-00).hwp":
        ("safety", "safety_kfs_pumptruck_20251224.hwp"),
    "소형사다리차(KFS-1-0030-2025-01).hwp":
        ("safety", "safety_kfs_ladder_small_20251224.hwp"),
    "전남광주통합특별시_동구.zip":
        ("juso", "juso_elctrnmap_jngj_20260711.zip"),
    "동구_불법 주정차_20250226.csv":
        ("gjcity", "gjcity_parking_enforce_dongu_20250226.csv"),
    "동구_불법 주정차 단속현황_20240108.csv":
        ("gjcity", "gjcity_parking_enforce_dongu_20240108.csv"),
    "동구_가로등현황_20240415.csv":
        ("gjcity", "gjcity_streetlight_dongu_20240415.csv"),
    "2MAP1000_SHP_광주_동구.zip":
        ("vworld", "vworld_map1k_gjdonggu_20260307.zip"),
    "내역서.csv":
        ("its", "its_nodelink_changelog_20260812.csv"),
}


def test_provider_filenames_are_matched():
    bad = []
    for src, want in SAMPLES.items():
        got = _match(src)
        if got != want:
            bad.append(f"  {src}\n      기대 {want}\n      실제 {got}")
    assert not bad, ("제공기관 파일명이 규칙에 안 걸린다.\n" + "\n".join(bad))


def test_normalized_names_round_trip():
    """★ 한 번 정리한 이름을 다시 넣어도 같은 자리에 간다(멱등).

    독스트링이 *"--in-place 로 한 번 정리한 폴더를 다시 원본으로 쓸 수
    있어야 한다"* 고 약속한다. 통과 규칙의 확장자 화이트리스트에
    `hwp`·`pdf`·`ngi`·`nda` 가 없어 그 약속이 거짓이었다.
    """
    bad = []
    for folder, name in SAMPLES.values():
        again = _match(name, passthrough=True)
        if again != (folder, name):
            bad.append(f"  {folder}/{name}  →  {again}")
    assert not bad, (
        "정리된 이름을 다시 넣으면 제자리로 안 간다. 멱등하지 않다.\n"
        + "\n".join(bad))


def test_main_uses_a_local_rule_copy():
    """RULES 는 모듈 전역이다. main() 안에서 append 하면 누적된다."""
    src = (ROOT / "src/firelane/normalize_raw.py").read_text(encoding="utf-8")
    assert "RULES.append" not in src, \
        "main() 이 모듈 전역 RULES 를 부풀린다. 지역 사본을 써라."


def test_required_and_missing_lists_use_declared_folders():
    """`REQUIRED` · `MISSING` 의 폴더가 기관 목록 안에 있는가."""
    bad = [r for r in (*N.REQUIRED, *N.MISSING) if r.split("/")[0] not in ORG]
    assert not bad, ("기관 목록에 없는 폴더를 쓴다: " + ", ".join(bad))
