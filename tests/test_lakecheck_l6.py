"""`lakecheck L6`(명명규칙) 이 **무엇을 세고 무엇을 빼는지** 잰다.  (§504 · §505)

★ 왜 이 파일이 따로 있나 (2026-10-12). L6 이 한 판에 두 번 틀렸고 **틀린 꼴이
  둘 다 「세는 쪽」**이었다 —

    ① 분자가 틀렸다 (§504)
       규칙이 `^(제공기관)/` 꼴이면 **파일명만으로는 전건이 위반**이다. L6 은
       그 `name_bad` 를 찍어 `retired` 를 「59/59건」이라 했고 실제 위반은
       하나였다. 같은 사실을 `layerfsck` 는 1 로 세었다 — 두 자가 1 과 59 로
       갈렸다(§458-1 과 같은 꼴).
    ② 분모가 틀렸다 (§505)
       `data/retired/QUARANTINE.md` 는 데이터가 아니라 **층을 설명하는 사람
       문서**고, `firelane.lake.RECORD_NAMES` 가 그것을 **이미 선언**하며
       `lake.rows()` 는 「기록」으로 분류한다. L6 과 `layerfsck` 는 그 선언을
       안 읽어서 같은 파일을 유일한 위반으로 셌다 — 선언이 있는데 읽는 자가
       하나면 그 선언은 절반만 산다.

  ②를 고치는 첫 수로 그 파일을 `_QUARANTINE.md` 로 **개명했고 그것이 틀렸다.**
  `_` 접두는 두 검사를 건너뛰게 하지만 `lake.rows()` 가 그 이름을 못 알아봐서
  레이크 관문이 「주인없음」(차단)으로 울었다. **선언을 안 찾고 관례를
  발명했다** — 「말하기 전에 그 파일을 연다」를 안 한 값이다.

IN    tools/lakecheck.py::l6 · firelane.lake.RECORD_NAMES ·
      src/firelane/layerfsck.py (선언을 **베껴 적지 않는지**만)
OUT   없음
밖    `naming` 규칙 자체가 옳은지는 여기서 안 본다(`sources.yaml` 의 몫이다).
      여기 잠그는 것은 **분자**(상대경로로 센다)와 **분모**(기록 파일을 뺀다)뿐이다.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys

import pytest

from firelane import lake

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "lakecheck.py"
POL = {"layers": {"retired": {
    "base": "data", "sub": "retired", "naming": "^(eais|ngii)/"}}}


@pytest.fixture
def lc():
    """경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering — 경로 조작 금지)."""
    spec = importlib.util.spec_from_file_location("lakecheck_l6t", SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    m.HITS.clear()
    return m


def _layer(tmp: pathlib.Path, *rels: str) -> None:
    for r in rels:
        f = tmp / "retired" / r
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")


def _hits(lc, tmp: pathlib.Path, *rels: str) -> list[dict]:
    """층을 깔고 L6 을 한 번 돌려 **울음 목록**을 낸다.

    ★ 판정을 돌리는 자리를 하나로 둔다 — 그래야 같은 판별식을
      `assert not _hits(…)`(정상)와 `assert _hits(…)`(합성) 둘로 밀 수 있다.
      `l6` 는 값을 안 내고 `HITS` 에 쌓으므로 그 꼴을 여기서 만든다
      (`tools/canary.py` 의 정의 — 이름이 아니라 **문법**으로 센다).
    """
    _layer(tmp, *rels)
    lc.HITS.clear()
    lc.l6(tmp, POL)
    return list(lc.HITS)


# ── 분자 — 상대경로로 센다 (§504) ───────────────────────────────────
def test_l6_counts_the_relative_path_violations_not_every_file(lc, tmp_path):
    """★ **세는 꼴이 실물과 달랐다.** 위반 하나를 「전건」이라 찍던 자리다."""
    hits = _hits(lc, tmp_path, "ngii/ngii_basemap_gj037_20260806.zip",
                 "ngii/ngii_basemap_gj038_20260807.zip", "strays.zip")
    assert len(hits) == 1, hits
    assert "1/3건" in hits[0]["what"], hits[0]["what"]
    assert "strays.zip" in hits[0]["detail"], hits[0]["detail"]


def test_l6_is_quiet_when_every_file_sits_under_its_provider(lc, tmp_path):
    """★ 반대 방향 — 전건이 규칙대로면 조용하다."""
    assert not _hits(lc, tmp_path, "ngii/a.zip", "eais/b.csv")


# ── 분모 — 기록 파일을 뺀다 (§505) ──────────────────────────────────
def test_a_record_file_is_not_a_naming_violation(lc, tmp_path):
    """★ **선언은 이미 있었다.** `RECORD_NAMES` 를 돌면서 본다.

    여기 이름을 베껴 적으면 집이 셋으로 갈린다 — 선언에 이름이 더 붙으면
    이 시험이 그것까지 같이 본다.
    """
    assert lake.RECORD_NAMES, "선언이 비면 이 시험은 아무것도 안 본다"
    assert not _hits(lc, tmp_path, "ngii/a.zip", *lake.RECORD_NAMES)


def test_the_record_file_keeps_its_declared_name():
    """★ 개명으로는 못 고친다 — `rows()` 가 **그 이름 그대로**를 맞춘다.

    `rows()` 는 `parts[-1] in RECORD_NAMES` 로 본다. `_` 접두를 붙이면 L6 과
    `layerfsck` 는 조용해지지만 `rows()` 가 그 이름을 못 알아봐서
    「주인없음」(차단)으로 분류한다 — 실기에서 그렇게 울었다. 선언된 이름에
    접두가 붙는 순간 이 시험이 운다.
    """
    assert lake.RECORD_NAMES, "선언이 비면 이 시험은 아무것도 안 본다"
    for nm in lake.RECORD_NAMES:
        assert not nm.startswith("_"), f"{nm} — `_` 접두는 rows() 가 못 읽는다"
    assert "주인없음" in lake.BLOCKING, "차단이 아니면 이 함정은 안 울린다"
    body = (ROOT / "src/firelane/lake.py").read_text(encoding="utf-8")
    assert "parts[-1] in RECORD_NAMES" in body, "rows() 가 맞추는 꼴이 바뀌었다"


def test_both_readers_read_the_one_declaration(lc):
    """★ 두 집이 **같은 선언**을 읽는가 — 베껴 적으면 또 갈린다(§505 · §474)."""
    for rel in ("tools/lakecheck.py", "src/firelane/layerfsck.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "RECORD_NAMES" in src, f"{rel} 가 선언을 안 읽는다"
        copied = [n.value for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and n.value in lake.RECORD_NAMES]
        assert not copied, f"{rel} 가 선언을 베껴 적었다 — {copied}"
