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

import pytest

from firelane import normalize_raw as N
from firelane import providers

ROOT = Path(__file__).resolve().parent.parent

# main() 이 지역 사본에 붙이는 통과 규칙. 값이 갈리면 안 되므로 여기 한 번만 적는다.
#  ★ 목록을 여기 적지 않는다. 정본은 layers.raw.providers 다.
#    test_provider_registry 가 사본을 금지한다.
ORG = providers.all()
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


def test_rules_do_not_reimport_retired_files():
    """★ 대장이 폐기했는데 정규화기가 다시 끌어오면 안 된다.

    2026-08-24. `sources.yaml` 의 `retired` 에 사유까지 적어놓은 둘을
    `normalize_raw.RULES` 가 여전히 raw 로 편입하고 있었다.

        firestation_kr_20250701      좌표가 없다. 활성판은 XY 를 갖는다
        hydrant_point_jngj_20250917  전남 판. 광주 0건

    normalize_raw 주석은 *"좌표 없는 시도 소방서 현황(20250701)은 규칙을
    두지 않는다"* 라고 적고 있었다. **주석과 코드가 정반대였다.**
    landing 에서 파일을 옮겨 우회했더니 다음에 다시 받으면 또 났다.

    정본이 둘이면 반드시 어긋난다(§18-3). 대장이 정본이고 규칙이 따른다.
    """
    import yaml
    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    retired = {Path(str(v["file"])).name
               for v in (cfg.get("retired") or {}).values()
               if isinstance(v, dict) and v.get("file")}
    if not retired:
        return
    # ★ 접두어로 비교하면 활성판까지 걸린다. `safety_firestation_kr_20240901`
    #   (현역)과 `..._20250701`(폐기)은 접두어가 같다. 템플릿을 정규식으로
    #   바꿔 **그 규칙이 실제로 그 이름을 낼 수 있는가**만 본다.
    bad = []
    for pat, folder, tmpl in N.RULES:
        if tmpl is None:
            continue
        rx = re.compile("^" + "(.+)".join(
            re.escape(x) for x in tmpl.split("{0}")) + "$")
        for r in sorted(retired):
            if rx.match(r):
                bad.append(f"  {pat}\n      -> {folder}/{tmpl}  (retired: {r})")
    assert not bad, (
        "폐기 등재된 파일을 규칙이 다시 편입한다. 대장이 정본이다.\n"
        + "\n".join(bad)
        + "\n  규칙을 지우거나, 정말 쓸 것이면 retired 에서 빼고 datasets 로 옮겨라.")


def test_missing_list_is_actually_missing():
    """`MISSING` 에 적힌 것이 raw 에 없는가.

    ★ 2026-08-31. `safety_hydrant_summary_jngj_*` 가 목록에 있는데 실물이
      raw 에 있었다. **받았는데 "못 받았다" 고 적힌 것**이고, 이 파일이
      `docnum_check` 의 소화전 집계(418/171)를 세는 바로 그 원본이다.
      결손 목록이 낡으면 매번 없는 경고가 뜨고, 잦은 오탐은 진짜 경보를
      못 믿게 만든다(MASTER §18-13).

    ★ 글롭이 안 맞아도 같은 자산이면 걸린다 — `jngj_` 대 `jngj-donggu_`.
      실제로 그 형태였다. 그래서 stem 으로 느슨하게 본다.
    """
    from firelane import normalize_raw as nr
    from firelane import paths

    try:
        if not paths.RAW.exists():
            pytest.skip("레이크 미마운트")
    except OSError:
        pytest.skip("레이크 미마운트")

    found = []
    for pat in nr.MISSING:
        stem = pat.split("/")[-1].split("*")[0].rstrip("_")
        hits = sorted(paths.RAW.rglob(f"*{stem}*"))
        if hits:
            found.append(f"  {pat}  ← 실물 있음: {[q.name for q in hits[:2]]}")
    assert not found, (
        "MISSING 에 적힌 것이 raw 에 있다:\n" + "\n".join(found) +
        "\n  받았으면 목록에서 빼라. 결손 목록이 낡으면 없는 경고가 매번 뜬다.")


def test_rules_do_not_redo_the_general_rule():
    """RULES 가 정규명을 다시 받지 않는가. **두 벌 금지.**

    ★ 2026-09-03. RULES 40줄 중 아홉이 `^juso_...` `^safety_...` 처럼
      정규명을 다시 받고 있었다. 정규명은 `main()` 의 일반 규칙 하나가
      전 제공기관에 대해 받으므로 같은 일을 두 벌로 한 것이다.

    ★ 그리고 실제로 어긋났다. 일반 규칙이 `[a-z0-9_]` 라 하이픈을 못 받는
      동안 `^safety_[\\w-]+_...` 는 받고 있었다. 같은 스코프를 쓰는 파일이
      제공기관에 따라 되기도 하고 안 되기도 했다 — 한쪽이 덮어서 안 보였다.

    RULES 는 취득처가 준 이름만 다룬다. 우리가 지은 이름은 일반 규칙이다.
    """
    import re

    from firelane import normalize_raw as n
    bad = [f"  {org:8s} {pat}" for pat, org, tmpl in n.RULES
           if tmpl is None and re.match(rf"\^{re.escape(org)}_", pat)]
    assert not bad, (
        "RULES 가 정규명을 다시 받는다 — 일반 규칙과 두 벌이다.\n"
        + "\n".join(bad)
        + "\n\n  지워라. main() 의 일반 규칙이 덮는다.")


def test_general_rule_accepts_every_scope_alias():
    """일반 규칙이 대장 `scopes` 별칭을 전부 받는가. **양방향이다.**

    ★ 2026-09-03. 대장은 `jngj-donggu` 처럼 하이픈을 쓰는데 일반 규칙이
      `[a-z0-9_]` 라 못 받았다. 대장이 정본인데 코드가 더 좁았고,
      `nfa_*` CSV 넷이 "규칙에 없는 파일" 로 떨어졌다.

    ★ `test_provider_registry` 가 `providers` 로 하는 대조를 `scopes` 에도 한다.
    """
    import re
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parents[1]
    led = yaml.safe_load((root / "sources.yaml").read_text(encoding="utf-8"))
    scopes = list(led.get("scopes") or {})
    assert scopes, "대장에 scopes 가 없다"
    EXT = "zip|csv|tif|xml|hwpx?|pdf|ngi|nda|geojson"
    pat = re.compile(rf"^nfa_[a-z0-9_-]+_\d{{8}}\.({EXT})$")
    bad = [s for s in scopes if not pat.match(f"nfa_x_{s}_20260101.csv")]
    assert not bad, (
        f"일반 규칙이 못 받는 스코프 별칭 — {', '.join(bad)}\n"
        "  normalize_raw.main() 의 문자 클래스를 넓혀라.\n"
        "  대장 scopes 가 정본이고 정규식이 그것을 따라간다.")
