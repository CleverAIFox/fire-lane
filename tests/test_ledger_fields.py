#!/usr/bin/env python3
"""
test_ledger_fields.py — 대장 별칭 이관기를 **합성 대장으로** 민다. (§484)

── 왜 생겼나 ───────────────────────────────────────────────────
§481 이 「부류 관문인데 아무도 안 미는 것」을 다섯 세고 셋을 갚았다. 남은
둘 중 하나가 이 도구였고, 사유는 **「실물 대장을 고치는 도구라 합성 대장을
지어야 밀 수 있다」**였다. 그 합성을 여기서 짓는다.

★ 미는 것이 둘이다 —

      check()   **역방향 관문.** 폐기된 별칭이 되살아났는가
      run()     이관 — 별칭 통합 · `updated` 채우기

★ `run(apply=True)` 가 **글자를 직접 고친다**(YAML 왕복을 안 한다). 그
  사유가 그 도구에 적혀 있다 — 「round-trip 하면 주석 1,500줄이 날아간다」.
  그 주장을 미는 자가 없었다. 주석을 지키는지는 **합성 대장으로만** 물을 수
  있다: 실물로 돌리면 실물이 바뀐다.

IN    없음 (합성 `sources.yaml`)
OUT   없음 (검사)
PARAM 없음
밖    **값이 옳은가는 안 본다** — 기준일이 실물과 맞는지는 `freshcheck` ·
      `vintage_check` 의 일이고 레이크가 있어야 돈다. 여기가 드는 것은
      **스키마 이관**이다. `provider` 후보도 안 든다(그 도구가 자동 적용을
      안 하고 제시만 한다 — 제시의 내용은 사람 판단이다).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def lf():
    """경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering)."""
    spec = importlib.util.spec_from_file_location(
        "ledger_fields", ROOT / "tools/ledger_fields.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


#: 합성 대장. **주석을 일부러 넣는다** — 그것을 지키는가가 본체다.
LEDGER = """# 대장 머리 주석 — 이 줄이 살아남아야 한다
datasets:
  gamma_pure:
    # 항목 안 주석 — 이것도 살아남아야 한다
    what: 한 줄 설명
    acquired: '2026-07-11'
    updated: '2026-07-11'
    scope: kr
    files:
      - safety/gamma_20260711.csv
  alpha_alias:
    desc: 같은 뜻 다른 이름
    retrieved: '2026-07-11'
    updated: '2026-07-11'
    scope: kr
    files:
      - safety/alpha_20260711.csv

# 블록 사이 주석
retired: {}
outputs: {}
raw_only: {}
"""


def _led(tmp_path: Path, text: str = LEDGER) -> Path:
    p = tmp_path / "sources.yaml"
    p.write_text(text, encoding="utf-8")
    return p


# ── ① 역방향 관문 — 폐기된 별칭이 되살아났는가 ─────────────────
def test_the_real_ledger_has_no_retired_alias(lf, capsys):
    """실물은 **조용하다.** 여기가 빨간불이면 이관이 되돌아갔다."""
    assert lf.check() == 0, capsys.readouterr().out


def test_a_clean_synthetic_ledger_is_silent(lf, tmp_path):
    """★ 합성의 **멀쩡한 꼴**도 조용해야 한다 — 아니면 아래 갈래들이
    「합성이라서」 우는 것이 되고, 그 시험은 아무것도 안 민다."""
    assert lf.check(_led(tmp_path, _clean())) == 0


@pytest.mark.parametrize("field", ["file", "vintage", "retrieved", "desc"])
def test_every_retired_field_is_caught(lf, tmp_path, field: str):
    """★ 넷을 **하나씩** 심는다. 한 꾸러미로 심으면 하나만 잡혀도 초록이다."""
    bad = LEDGER.replace("    scope: kr\n    files:\n      - safety/gamma",
                         f"    {field}: 되살아난값\n    scope: kr\n"
                         "    files:\n      - safety/gamma", 1)
    assert bad != LEDGER, "심는 자리를 못 찾았다 — 합성 대장이 바뀌었다"
    assert lf.check(_led(tmp_path, bad)) == 1, f"`{field}` 가 되살아났는데 조용하다"


def _clean() -> str:
    """별칭이 없는 합성 대장. 빈 값 시험의 바탕이다."""
    s = LEDGER.replace("    desc: 같은 뜻 다른 이름\n", "    what: 다른 이름\n")
    return s.replace("    retrieved: '2026-07-11'\n", "    acquired: '2026-07-11'\n")


def test_an_empty_value_is_not_a_revival(lf, tmp_path):
    """★ 빈 값은 **되살아난 것이 아니다.** 그 도구가 그렇게 적는다
    (`None` · `''` · `[]` · `{}`). 빈 칸에 울면 사람이 그 관문을 끈다."""
    base = _clean()
    assert lf.check(_led(tmp_path, base)) == 0, "바탕이 이미 운다 — 전제가 깨졌다"
    for empty in ("", "''", "[]", "{}"):
        txt = base.replace("    scope: kr\n    files:\n      - safety/gamma",
                           f"    vintage: {empty}\n    scope: kr\n"
                           "    files:\n      - safety/gamma", 1)
        assert txt != base, "심는 자리를 못 찾았다"
        assert lf.check(_led(tmp_path, txt)) == 0, f"빈 값 {empty!r} 에 운다"


def test_the_retired_list_names_its_canon(lf):
    """★ 폐기 목록이 **정본을 말하는가.** 「쓰지 말라」만 적으면 다음 사람이
    어디에 적을지 모르고, 모르면 아무 데나 적는다."""
    for field, (why, canon) in lf.RETIRED_FIELDS.items():
        assert why and canon, f"{field} 에 사유나 정본이 없다"
        assert canon != field, f"{field} 의 정본이 자기 자신이다"


#: 폐기된 넷이 **살 수 있는** 칸. `file` · `vintage` · `retrieved` 는 다
#: 「이 항목이 가리키는 파일」 쪽 어휘다.
FILE_WORDS = {"files", "stem", "file"}


def test_the_scan_covers_every_block_that_names_files(lf):
    """★ 빈 그물 — 훑는 블록이 **파일을 가리키는 블록**을 다 덮는가.

    실물 대장의 다른 표(`layers` · `scopes` · `retired_outputs`)는 파일을
    안 가리키고 어휘가 통째로 다르다 — 그쪽에 `vintage` 가 생길 자리가
    없다. 그래서 「모든 표」가 아니라 **파일을 가리키는 표**로 묻는다:
    분모를 넓게 잡으면 그 시험이 거짓으로 울고, 거짓으로 우는 문은
    안 우는 문보다 나쁘다(§473).
    """
    led = yaml.safe_load(lf.load())
    bearing = set()
    for k, v in led.items():
        if not isinstance(v, dict) or not v:
            continue
        if not all(isinstance(x, dict) for x in v.values()):
            continue
        if any(FILE_WORDS & set(e) for e in v.values()):
            bearing.add(k)
    assert bearing, "파일을 가리키는 블록을 하나도 못 찾았다 — 훑기가 비었다"
    missed = bearing - set(lf.SCAN_BLOCKS)
    assert not missed, f"파일을 가리키는데 안 훑는 블록 — {sorted(missed)}"


def test_no_scanned_block_is_a_dead_declaration(lf):
    """★ 반대쪽(§370) — `SCAN_BLOCKS` 에 적힌 이름이 실물에 **있는가.**
    없는 이름은 죽은 선언이고, 죽은 선언은 「본다」는 거짓 신호다."""
    led = yaml.safe_load(lf.load())
    dead = [b for b in lf.SCAN_BLOCKS if b not in led]
    assert not dead, f"대장에 없는 블록을 훑는다고 적혀 있다 — {dead}"


# ── ② 이관 — 계획과 적용 ───────────────────────────────────────
def test_planning_changes_nothing(lf, tmp_path, capsys):
    """★ 계획만 세울 때 글자를 건드리면 그 도구는 못 믿는다."""
    p = _led(tmp_path)
    before = p.read_text(encoding="utf-8")
    assert lf.run(apply=False, path=p) == 0
    assert p.read_text(encoding="utf-8") == before, "계획만 세우면서 고쳤다"
    assert "아무것도 바꾸지 않았다" in capsys.readouterr().out


def test_applying_merges_the_aliases(lf, tmp_path):
    p = _led(tmp_path)
    assert lf.run(apply=True, path=p) == 0
    got = yaml.safe_load(p.read_text(encoding="utf-8"))["datasets"]["alpha_alias"]
    assert got.get("acquired") == "2026-07-11", f"retrieved 가 안 옮겨졌다 — {got}"
    assert "retrieved" not in got, "옛 이름이 남았다"
    assert got.get("what") == "같은 뜻 다른 이름", f"desc 가 안 옮겨졌다 — {got}"
    assert "desc" not in got, "옛 이름이 남았다"


def test_applying_is_idempotent(lf, tmp_path):
    """★ 두 번 돌려도 같다. 아니면 매번 대장이 흔들리고 diff 가 거짓이 된다."""
    p = _led(tmp_path)
    lf.run(apply=True, path=p)
    once = p.read_text(encoding="utf-8")
    lf.run(apply=True, path=p)
    assert p.read_text(encoding="utf-8") == once, "두 번째 적용이 글자를 또 바꿨다"


def test_applying_keeps_the_comments(lf, tmp_path):
    """★ **본체.** 그 도구가 YAML 왕복을 안 하는 사유가 이것이다 —
    「round-trip 하면 주석 1,500줄이 날아간다」. 실물 대장의 주석이 그만큼
    있고, 그것이 「왜 이 자료를 쓰는가」의 유일한 기록이다."""
    p = _led(tmp_path)
    lf.run(apply=True, path=p)
    got = p.read_text(encoding="utf-8")
    for line in ("# 대장 머리 주석", "# 항목 안 주석", "# 블록 사이 주석"):
        assert line in got, f"{line!r} 이 사라졌다 — 왕복이 섞였다"


def test_applying_leaves_parsable_yaml(lf, tmp_path):
    p = _led(tmp_path)
    lf.run(apply=True, path=p)
    assert yaml.safe_load(p.read_text(encoding="utf-8"))["datasets"]


def test_a_missing_updated_is_filled_from_the_file_name(lf, tmp_path):
    """★ 파일명 8자리가 정본이다. `vintage` 를 그대로 옮기지 않는 사유가
    그 도구에 적혀 있다(연도만 25건 · 정밀도가 다르다)."""
    txt = LEDGER.replace("    updated: '2026-07-11'\n", "", 1)
    p = _led(tmp_path, txt)
    lf.run(apply=True, path=p)
    got = yaml.safe_load(p.read_text(encoding="utf-8"))["datasets"]["gamma_pure"]
    assert got.get("updated") == "2026-07-11", f"파일명에서 안 채웠다 — {got}"


def test_it_does_not_guess_a_date_that_is_not_there(lf, tmp_path):
    """★ **추측하지 않는다.** 8자리를 못 얻으면 채우지 않는다."""
    txt = LEDGER.replace("    updated: '2026-07-11'\n", "", 1)
    txt = txt.replace("safety/gamma_20260711.csv", "safety/gamma.csv")
    p = _led(tmp_path, txt)
    lf.run(apply=True, path=p)
    got = yaml.safe_load(p.read_text(encoding="utf-8"))["datasets"]["gamma_pure"]
    assert "updated" not in got, f"없는 날짜를 지어냈다 — {got}"


def test_an_alias_whose_value_differs_is_left_to_a_person(lf, tmp_path, capsys):
    """★ 두 이름의 값이 **다르면** 합치지 않는다 — 어느 쪽이 맞는지는
    사람이 안다. 자동으로 고르면 한쪽 사실이 조용히 사라진다."""
    txt = LEDGER.replace("    desc: 같은 뜻 다른 이름\n",
                         "    desc: 아주 다른 설명\n    what: 또 다른 설명\n", 1)
    p = _led(tmp_path, txt)
    lf.run(apply=False, path=p)
    assert "손으로 합쳐라" in capsys.readouterr().out, "다른 값을 조용히 합친다"
