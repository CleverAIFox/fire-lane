#!/usr/bin/env python3
"""
test_contract_vocab.py — **계약 어휘가 셋 다 같은가.** 대장 · 코드 · 머리말.

── 왜 생겼나 (2026-09-28 · DECISIONS §284) ─────────────────────
`contract:` 블록의 키를 아무도 세지 않았다. 실측 3방향 어긋남 —

    키                머리말  읽는 코드  대장
    crs                 ○       ✗        0    ★ 개명 전 이름이 남아 있었다
    delimiter           ✗       ○        2    ★ 어휘인데 머리말에 없었다
    optional_cols       ✗       ○        1    ★ 같다
    columns             ✗       ○        0    ★ 같다

★ `crs` 는 항목 수준 `crs_native` 로 개명됐고 개명 때 `contract.py` 머리말만
  옛 이름을 들고 남았다. 그 한 줄이 **「선언 CRS 와 실물 .prj 를 대조한다」는
  약속**으로 읽혔다. 아무도 안 하고 있었다 — `probe_crs` 가 있는데도.

★ 오타는 더 조용하다. `required_col` 이라 적으면 `c.get("required_cols")` 가
  `None` 을 받고 **검사가 그냥 사라진다.** 빨강도 경고도 안 뜬다.

IN    sources.yaml · firelane.ledger.CONTRACT_KEYS · firelane.contract
OUT   없음 (검사)
PARAM 없음
밖    **`tools/` 의 `.sh` 는 안 본다.** 구분자 기본값 검사는 파이썬만 훑는다 —
      셸 스크립트는 대장의 `contract` 블록을 읽지 않는다(실측 0곳).
      **계약 값이 옳은가는 안 본다.** `rows: 50000` 이 맞는 숫자인지는
      실물을 봐야 알고 그쪽은 레이크가 붙은 곳에서 본다. 여기가 드는 것은
      「어휘가 같은가」와 「기본값 정본이 하나인가」 둘이다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from firelane import contract, ledger

ROOT = Path(__file__).resolve().parents[1]


def _ds() -> dict:
    # ★ 대장은 **한 문**으로 읽는다(§173-4 ②). 직접 파싱하면 `test_lake` 의
    #   「대장 직접 로드」 래칫이 운다 — 실제로 첫 판이 40 → 41 로 걸렸다.
    return ledger.load().get("datasets", {}) or {}


# ── ① 어휘 ─────────────────────────────────────────────────────
def test_the_ledger_uses_no_key_outside_the_vocabulary():
    """대장이 어휘 밖 키를 쓰면 그 검사는 조용히 사라진다."""
    unknown: dict[str, list[str]] = {}
    for key, e in _ds().items():
        for k in (e or {}).get("contract") or {}:
            if k not in ledger.CONTRACT_KEYS:
                unknown.setdefault(k, []).append(key)
    assert not unknown, (
        "대장이 어휘 밖 계약 키를 쓴다 — " +
        " · ".join(f"`{k}` ({', '.join(v[:3])})" for k, v in unknown.items()) +
        "\n  오타면 고쳐라. 새 어휘면 `ledger.CONTRACT_KEYS` 에 올려라.")


def test_every_vocabulary_key_is_read_by_the_module_it_names():
    """★ 죽은 어휘를 막는다. `crs` 가 그렇게 5주를 살아남았다."""
    dead = []
    for key, (_why, mod) in ledger.CONTRACT_KEYS.items():
        rel = mod.removeprefix("firelane.").replace(".", "/")
        src = ROOT / "src" / "firelane" / f"{rel}.py"
        assert src.is_file(), f"`{key}` 가 가리키는 {mod} 이 없다 — {src}"
        if f'"{key}"' not in src.read_text(encoding="utf-8"):
            dead.append(f"`{key}` → {mod} 가 그 이름을 안 읽는다")
    assert not dead, ("죽은 계약 어휘 — " + " · ".join(dead) +
                      "\n  읽는 자리를 만들거나 어휘에서 내려라.")


def test_the_contract_docstring_does_not_list_the_vocabulary_again():
    """★ 목록을 두 곳에 적으면 한쪽이 낡는다. 그것이 §284 의 전부다."""
    doc = contract.__doc__ or ""
    assert "ledger.CONTRACT_KEYS" in doc, \
        "머리말이 어휘의 정본을 가리키지 않는다"
    # 옛 이름이 계약 키 꼴로 다시 등장하면 안 된다.
    assert not re.search(r"^\s+crs:\s", doc, re.M), \
        "머리말이 `crs:` 를 계약 키로 다시 들었다 — 그 키는 `crs_native` 다"


# ── ② 구분자 기본값의 정본 ──────────────────────────────────────
def test_only_the_accessor_carries_the_delimiter_default():
    """기본값이 세 곳에 각기 있었다 — `|` · `|` · pandas 기본 쉼표."""
    bad = []
    # ★ `tests` 도 본다. 시험이 `get("delimiter", "|")` 를 적으면 그것도
    #   **두 번째 정본**이다 — 실물이 바뀌어도 그 시험만 옛 기본값으로
    #   초록을 낸다. 넓히는 쪽이 맞아서 넓혔다(deadcheck ⑤).
    for p in [*(ROOT / "src" / "firelane").rglob("*.py"),
              *(ROOT / "tools").rglob("*.py"),
              *(ROOT / "tests").rglob("*.py")]:
        # ★ 판별식이 사는 파일 자신은 뺀다 — 안 빼면 제 정규식을 제가 잡고
        #   늘 한 건이 뜬다(`deadcheck` 의 같은 주석과 같은 자리).
        if (p.name == "ledger.py" or "__pycache__" in p.parts
                or p.resolve() == Path(__file__).resolve()):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r'get\(\s*"delimiter"\s*,', line):
                bad.append(f"{p.relative_to(ROOT).as_posix()}:{i}")
    assert not bad, ("구분자 기본값을 자기 자리에서 또 정하는 곳 — " +
                     " · ".join(bad) + "\n  `ledger.delimiter_of(e)` 를 써라.")


@pytest.mark.parametrize(("kind", "c", "want"), [
    ("text_table", {}, "|"),            # 도로명주소 DB 계열
    ("csv_table", {}, ","),
    ("csv_points", {}, ","),
    ("text_table", {"delimiter": ";"}, ";"),   # 선언이 갈래 기본값을 덮는다
])
def test_delimiter_of(kind, c, want):
    assert ledger.delimiter_of({"kind": kind, "contract": c}) == want


# ── ③ 선언 검사가 빈 그물이 아닌가 ──────────────────────────────
def test_declared_check_catches_an_unknown_key():
    """★ 지금 실물이 0건이라 통과한다. 0건과 못 봄을 가른다."""
    bad, _w, _n, _c = contract.declared_issues(
        {"시험": {"kind": "csv_table", "contract": {"required_col": ["가"]}}})
    assert bad and "required_col" in bad[0], f"모르는 키를 못 잡았다 — {bad}"


def test_declared_check_catches_a_geometry_source_without_a_crs():
    _b, warn, _n, _c = contract.declared_issues(
        {"시험": {"kind": "shp_zip", "contract": {"encoding": "cp949"}}})
    assert warn and "crs_native" in warn[0], f"좌표계 누락을 못 잡았다 — {warn}"


def test_declared_check_passes_a_clean_entry():
    bad, warn, n, crs = contract.declared_issues(
        {"시험": {"kind": "shp_zip", "crs_native": 5186,
                "contract": {"encoding": "cp949"}}})
    assert (bad, warn, n, crs) == ([], [], 0, 1)


def test_a_table_source_needs_no_crs():
    """좌표가 없는 갈래에 좌표계를 요구하면 매번 오탐한다."""
    _b, warn, _n, _c = contract.declared_issues(
        {"시험": {"kind": "csv_table", "contract": {"encoding": "cp949"}}})
    assert not warn, f"표 소스에 좌표계를 요구했다 — {warn}"


def test_crs_native_is_written_as_a_bare_code():
    """`crs_native` 표기가 **한 꼴인가.**  (§428)

    ★ `ledger.crs_of()` 머리말이 *「대장은 `crs_native: 5186` 으로 **정수**를
      적는다」*고 못 박는데, 실측하면 `EPSG:` 접두를 쓴 것이 **일곱**이었다.
      그 함수가 둘 다 받아 정규화하므로 런타임은 안 깨졌고, 그래서 **아무도 안
      물었다** — 조용한 어긋남이고 족 2 다. 그중 둘은 §419 가 새로 만든 것이다.

    ★ 왜 접두 없는 쪽이 정본인가 — `MASTER §18-3a` 의 예시가 그렇고, 수가 많다
      (30 대 7). 그리고 `crs_of()` 가 **붙이는** 쪽으로 정규화한다: 대장이 이미
      붙여 두면 그 함수가 할 일이 없어지고, 하는 일이 없는 정규화는 다음 사람이
      지운다.
    """
    #: ★ **면제가 아니라 등록이다.** 이 둘은 커밋된 샤드 봉인지가 그 글자를
    #:   해시했고, 고치면 `test_committed_manifest_uses_new_cfg_print` 가 찢어진다.
    #:   다시 빌드 없이는 못 넘긴다 — **`PLAN #158` 이 해소를 든다.**
    #:   `BACKWARD` 와 같은 규율이다: 사유와 **해소 조건**을 같이 적는다.
    SEALED = {"child_zone_std", "senior_zone_std"}
    bad = [f"{k}: {e['crs_native']!r}" for k, e in _ds().items()
           if k not in SEALED and (e or {}).get("crs_native") is not None
           and str(e["crs_native"]).upper().startswith("EPSG:")]
    # ★ 역방향 — 해소됐는데 목록이 남으면 다음 어긋남이 조용히 면제된다(§69)
    stale = sorted(k for k in SEALED
                   if not str((_ds().get(k) or {}).get("crs_native", "")).upper().startswith("EPSG:"))
    assert not stale, (f"`SEALED` 가 이미 고쳐진 것을 든다 — {stale}. 그 줄을 지우고 "
                       "`PLAN #158` 을 닫아라")
    assert not bad, (
        "`crs_native` 에 `EPSG:` 접두를 적었다 — 정본은 맨 코드다:\n  "
        + "\n  ".join(bad)
        + "\n  붙이는 일은 `ledger.crs_of()` 가 한다. 대장은 사실만 적는다.")


# ── ④ 래칫이 실물과 같은가 ──────────────────────────────────────
def test_ratchets_match_the_ledger():
    _b, _w, n, crs = contract.declared_issues(_ds())
    assert n == contract.NO_CONTRACT_RATCHET, (
        f"무계약이 {n} 인데 래칫은 {contract.NO_CONTRACT_RATCHET} 이다")
    assert crs == contract.CRS_DECLARED_RATCHET, (
        f"crs_native 선언이 {crs} 인데 래칫은 "
        f"{contract.CRS_DECLARED_RATCHET} 이다")


def test_the_declared_mode_needs_no_lake():
    """★ 이 갈래가 CI 에 붙는 근거다. 레이크를 안 읽는가."""
    # ★ 2026-10-08 (§431 · PLAN #157). `contract.py` → `contract_verdict.py`.
    src = (ROOT / "src" / "firelane" / "contract_verdict.py").read_text(encoding="utf-8")
    body = src.split("def declared_issues")[1].split("\ndef ")[0]
    for forbidden in ("RAW", "paths_of", "read_csv", "zip_names", "decode_ok"):
        assert forbidden not in body, (
            f"`declared_issues` 가 {forbidden} 를 쓴다 — 실물을 읽으면 "
            "레이크 없는 CI 에서 돌 수 없다")
