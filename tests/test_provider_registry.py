#!/usr/bin/env python3
"""
test_provider_registry.py — provider 목록의 **사본을 금지한다.**

── 왜 ─────────────────────────────────────────────────────────
`DECISIONS §73` 이 "역산 재발을 막는 강제자는 없다" 고 적어 놨다.
provider 목록도 같았다 — 2026-08-24 에 세 곳이 달라서 정정했는데
정정한 값이 다시 네 곳에 복사됐고, **다시 갈려도 아무도 모르는 상태**
그대로였다. 값을 맞추는 것은 사고를 미루는 것이지 막는 것이 아니다.

이 테스트가 강제자다. 목록을 어딘가에 새로 적으면 여기서 죽는다.

IN    sources.yaml · src/ · tools/ · tests/
OUT   없음
PARAM 없음
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from firelane import providers as P

ROOT = Path(__file__).resolve().parent.parent

#  정본 자체와, 정본을 인용해도 되는 곳.
ALLOWED = {
    "sources.yaml",
    "src/firelane/providers.py",
    "tests/test_provider_registry.py",
}


def test_registry_loads_and_validates():
    spec = P.spec()
    assert len(spec) >= 8
    assert P.active() and P.reserved() | P.active() == P.all()


def test_naming_regex_is_generated_not_handwritten():
    ok, msg = P.naming_matches_registry()
    assert ok, msg


@pytest.mark.parametrize("name", sorted(P.spec()))
def test_every_provider_has_an_org(name):
    assert P.org(name).strip()


def test_no_second_copy_of_the_provider_list():
    """provider 이름 4개 이상을 담은 **리터럴 하나**는 목록의 사본이다.

    ★ 2026-08-27. 강제자를 두 번 고쳤다.

      1차 — 한 줄에 3개 이상으로 셌다. `tools/scan_data.py` 가
            줄당 2개씩 적었다는 이유로 빠져나갔다(5번째 사본).
      2차 — 파일 단위로 셌다. 이번엔 `normalize_raw.RULES` 가 걸렸다.
            거기 `juso` 는 규칙마다의 **목적지**지 목록이 아니다. 오탐이다.

      ★ 오탐은 강제자를 죽인다. 정상을 막으면 사람이 우회하고, 우회가
        습관이 되면 강제자가 없는 것과 같다(DECISIONS §73).

      그래서 형식이 아니라 **구조**로 판정한다 — set·dict·list 리터럴
      하나 안에 provider 이름이 4개 이상 상수로 들어 있으면 사본이다.
      RULES 는 튜플의 리스트라 원소가 상수가 아니므로 안 걸린다.
    """
    names = set(P.all())
    offenders = []
    for f in sorted(ROOT.rglob("*.py")):
        rel = f.relative_to(ROOT).as_posix()
        if rel in ALLOWED or "/.venv/" in rel or rel.startswith("."):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
                items = node.elts
            elif isinstance(node, ast.Dict):
                items = node.keys
            else:
                continue
            hit = {x.value for x in items
                   if isinstance(x, ast.Constant) and x.value in names}
            if len(hit) >= 4:
                offenders.append(f"{rel}:{node.lineno}  {sorted(hit)}")
    assert not offenders, (
        "provider 목록의 사본이다. `firelane.providers` 를 써라 —\n  "
        + "\n  ".join(offenders))


def test_reserved_providers_document_why():
    """reserved 는 빈 폴더에 근거를 붙이는 장치다. 근거가 없으면 의미가 없다.

    ★ 2026-09-24 (DECISIONS §239). `P.reserved()` 가 **빈 집합**이라 이 루프는
      한 번도 안 돌았고, 단언 없이 통과했다. 0건이 청결인지 죽음인지 못 가르는
      상태다 — 사유 주석을 전부 지워도, reserved 를 사유 없이 다시 등재해도
      초록이었다. 판정기를 합성 입력으로 따로 문다(§230).
    """
    y = (ROOT / "sources.yaml").read_text(encoding="utf-8")

    def judge(doc: str, name: str) -> bool:
        i = doc.find(f"      {name}:")
        return i > 0 and "#" in doc[i:i + 700]

    # ★ 머리 한 줄을 둔다 — 실제 `sources.yaml` 처럼 블록이 0번 자리에 안 온다.
    #   (판정기가 `i > 0` 이라 0번 자리 블록은 못 본다. 실물에서는 안 나는 일이다.)
    head = "providers:\n"
    assert judge(head + "      zq7:\n        kind: reserved  # 폴더를 만들지 않는다\n", "zq7")
    assert not judge(head + "      zq7:\n        kind: reserved\n", "zq7"), \
        "사유 없는 선언을 통과시킨다 — 판정기가 죽었다"
    assert not judge(head, "zq7"), "선언이 없는데 통과시킨다"

    for name in sorted(P.reserved()):
        i = y.find(f"      {name}:")
        assert i > 0, f"{name} 선언을 못 찾았다"
        block = y[i:i + 700]
        assert "#" in block, (
            f"{name} 은 reserved 인데 사유 주석이 없다. "
            "reserved 는 '폴더가 없어야 한다' 는 뜻이고, 왜 등재만 해 두는지"
            "가 없으면 다음 사람이 폴더를 다시 만든다")


# ── norm 파일명 꼴 — 시험이 이름을 안 부르고 있었다 (DECISIONS §493) ─
def test_pattern_file_accepts_every_real_raw_name():
    """★ `pattern_file()` 은 `layers.norm.naming` 의 값을 **만든다.**

    그 값이 실물을 거부하면 norm 계층 선언이 제 파일을 위반으로 센다.
    기댓값을 손으로 적지 않고 `data/_acquire.json`(raw 실물)에서 가져온다.

    ★ 이 자리가 까다로운 이유는 **dataset 에 언더스코어가 있다**는 것이다
      (`kfs_pumptruck` · `parking_enforce` · `bldg_ledger`). 왼쪽부터 세면
      필드 경계를 못 찾고, 그래서 꼴이 `\\w+` 의 되돌림에 기대고 있다.
      되돌림이 끊기는 날 여기가 운다.
    """
    import json
    import re as _re

    raw = sorted(json.loads(
        (ROOT / "data/_acquire.json").read_text(encoding="utf-8"))["files"])
    assert len(raw) > 50, "실물 목록이 비었다 — 이 검사가 빈 그물이 됐다"
    rx = _re.compile(P.pattern_file())
    bad = [p for p in raw if not rx.match(p)]
    assert not bad, (
        "norm 파일명 꼴이 실물 이름을 거부한다:\n  " + "\n  ".join(bad)
        + "\n  ★ 고치는 쪽은 꼴이다 — 문법 정본은 `firelane.naming` 이다.")


def test_pattern_file_still_refuses_what_it_is_there_to_refuse():
    """★ 음성 — 아무 경로나 받으면 그 선언은 없는 것과 같다."""
    import re as _re

    rx = _re.compile(P.pattern_file())
    for bad in ("safety/safety_cctv_jngj.csv",            # vintage 없음
                "safety/safety_cctv_20260630.csv",        # 스코프 없음
                "없는기관/safety_cctv_jngj_20260630.csv",   # 선언 밖 폴더
                "safety_cctv_jngj_20260630.csv",          # 폴더 없음
                "safety/Safety_CCTV_jngj_20260630.csv"):  # 대문자
        assert not rx.match(bad), f"{bad!r} 를 받는다 — 꼴이 열렸다"
