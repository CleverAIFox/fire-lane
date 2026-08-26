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

import re

import pytest

# 개명 과도기 동안 양쪽을 받는다. 개명이 끝나면 위 줄만 남긴다.
try:
    from firelane import place_raw as M
except ImportError:  # pragma: no cover
    from firelane import normalize_raw as M


# 규칙이 만들어내는 대표 목적지 파일명. 왕복 입력으로 쓴다.
# 실제 raw 에 있는 이름에서 가져왔다.
PRODUCED = [
    "safety/safety_hydrant_point_kr_20240207.csv",
    "safety/safety_firestation_kr_20240901.csv",
    "safety/safety_cctv_jngj_20260630.csv",
    "safety/safety_fire_access_gj_dong_20250731.csv",
    "safety/safety_kfs_pumptruck_20251224.hwpx",
    "safety/safety_kfs_ladder_small_20251224.pdf",
    "safety/safety_kfs_watertank_20251224.hwpx",
    "safety/safety_mas_vehicle_spec_20241111.hwpx",
    "gjcity/gjcity_parking_enforce_dongu_20250226.csv",
    "gjcity/gjcity_streetlight_dongu_20240415.csv",
    "juso/juso_elctrnmap_jngj_20260711.zip",
    "its/its_nodelink_kr_20260812.zip",
    "its/its_nodelink_changelog_20260812.csv",
    "ngii/ngii_basemap_gj9708_20260812.zip",
    "ngii/ngii_ortho_gj048_20251231.tif",
    "ngii/ngii_dem_gj35616_20251117.zip",
    "vworld/vworld_map1k_gjdonggu_20260307.zip",
    "vworld/vworld_map1k_ngi_gjdonggu_20260307.zip",
    "sbiz/sbiz_store_kr_20260630.zip",
    "eais/eais_bldg_ledger_gjdonggu_20260817.csv",
]

ORG = {"juso", "ngii", "its", "sbiz", "safety", "gjcity",
       "nsdi", "vworld", "eais"}
EXT = "zip|csv|tif|xml|hwpx?|pdf|ngi|nda|geojson"


def rules():
    """main() 이 조립하는 것과 같은 규칙 표.

    ★ main() 안에서 조립하므로 여기서 재현한다. 이 이중화 자체가 냄새다 —
      규칙 조립을 함수로 빼면 이 블록이 사라진다. TODO.
    """
    return M.RULES + [
        (rf"^{org}_[a-z0-9_]+_\d{{8}}\.({EXT})$", org, None)
        for org in sorted(ORG)
    ]


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
    """규칙이 만든 이름이 layers.raw.naming 을 만족한다.

    대장의 naming 은 `^(juso|its|...)/` 로 폴더만 본다.
    파일명 규약(MASTER §18-2)은 여기서 따로 잠근다.
    """
    folder, name = rel.split("/", 1)
    assert folder in ORG, f"{folder} 는 선언된 기관 폴더가 아니다"
    assert re.match(rf"^{folder}_[a-z0-9_]+_\d{{8}}\.({EXT})$", name), (
        f"{name} 이 명명규칙을 어긴다\n"
        f"  {{기관}}_{{데이터}}_{{범위}}_{{기준일 8자리}}.{{확장자}}\n"
        f"  접두사는 폴더명과 같아야 한다")


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
