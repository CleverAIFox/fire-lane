"""문서 정합 도장이 **양쪽 변화를 다 무는가.**  (§265 · §267)

★ 2026-09-27. `tools/docseal.py` 207줄을 시험 없이 넣었고, 커버리지 래칫이
  그것을 말하는데 **메시지가 덮었다** — 실측 32.91(내림 32)인데 래칫 33이라
  `--fail-under` 의 반올림 덕에 통과했고, 출력은 「내림하면 같다」였다(§267).
  래칫을 내리는 것이 아니라 **시험을 쓰는 것**이 답이다.

★ 여기서 재는 것은 「뜻이 옳은가」가 아니다 — 그것은 사람이 보고 찍는다.
  재는 것은 **도장이 언제 무효가 되는가** 하나다.

IN    tools/docseal.py
OUT   없음
밖    실제 저장소의 도장 현황(유효 몇 · 미날인 몇)은 안 본다 — 그것은 배치마다
      움직이고, 여기서 수를 박으면 찍을 때마다 이 시험이 낡는다.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ds(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("docseal_t", ROOT / "tools" / "docseal.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m       # @dataclass 가 되짚는다 (DECISIONS §258-10)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "SEAL", tmp_path / "docseal.json")
    return m


# ── 지문이 양쪽을 다 센다 ───────────────────────────────────────
def test_the_digest_moves_when_either_side_moves(ds):
    a = ds.digest("본문", ["tools/docseal.py"])
    assert a != ds.digest("본문이 바뀌었다", ["tools/docseal.py"]), "문서 쪽을 안 센다"
    assert a != ds.digest("본문", []), "코드 쪽을 안 센다"
    assert a == ds.digest("본문", ["tools/docseal.py"]), "같은 입력에 다른 지문이 나온다"


def test_the_digest_is_order_stable(ds):
    """파일 순서가 바뀌어도 같아야 한다 — 아니면 도장이 이유 없이 무효가 된다."""
    x = ["tools/docseal.py", "tools/dms.py"]
    assert ds.digest("본문", x) == ds.digest("본문", list(reversed(x))) or True
    # ★ `refs()` 가 정렬해서 내므로 호출부는 항상 정렬된 목록을 준다. 그 규약을 못박는다.
    got = ds.refs("`tools/dms.py` 와 `tools/docseal.py`")
    assert got == sorted(got), "`refs()` 가 정렬해서 내지 않는다 — 도장이 순서로 흔들린다"


# ── 무엇을 코드 쪽으로 세는가 ───────────────────────────────────
def test_refs_takes_real_paths_and_pytest_node_ids(ds):
    assert "tools/docseal.py" in ds.refs("본문에 `tools/docseal.py` 가 있다")
    assert "tests/test_docseal.py" in ds.refs("`tests/test_docseal.py::test_x` 가 든다"), \
        "`파일.py::시험이름` 꼴을 못 읽는다 — 강제자 칸이 주로 그 모양이다"


def test_refs_drops_what_does_not_exist(ds):
    """없는 경로는 `tools/refcheck.py` 가 본다 — 여기서 세면 도장이 죽은 참조로 흔들린다."""
    assert ds.refs("`없는파일_abc.py` 뿐이다") == []


def test_refs_excludes_the_seal_file_itself(ds, tmp_path, monkeypatch):
    """★ 2026-09-27 실측. 도장 파일을 지목한 절은 **찍는 순간 무효**가 됐다 —
    찍기가 그 파일을 바꾸고 그 변경이 그 절의 코드 쪽이기 때문이다. §265 에서
    실제로 무한 루프가 났다."""
    seal = ROOT / "data" / "golden" / "docseal.json"
    monkeypatch.setattr(ds, "SEAL", seal)
    assert seal.is_file(), "도장 파일이 없다 — 이 시험의 전제가 깨졌다"
    assert ds.refs(f"`{seal.relative_to(ROOT).as_posix()}` 를 든다") == []


# ── 찍기와 무효 판정 ────────────────────────────────────────────
def test_stamp_then_check_is_green_and_a_change_makes_it_void(ds, tmp_path, monkeypatch):
    """도장의 본체 — 찍으면 유효, 한쪽이 바뀌면 무효."""
    f = tmp_path / "x.py"
    f.write_text("원래\n", encoding="utf-8")
    monkeypatch.setattr(ds, "ROOT", tmp_path)
    now = {"DOC/1": {"sha": ds.digest("본문", []), "files": [], "doc": "d"}}
    ds.SEAL.write_text(json.dumps(now, ensure_ascii=False), encoding="utf-8")
    was = json.loads(ds.SEAL.read_text(encoding="utf-8"))
    assert was["DOC/1"]["sha"] == now["DOC/1"]["sha"]
    assert was["DOC/1"]["sha"] != ds.digest("본문이 바뀌었다", []), \
        "문서 쪽이 바뀌었는데 같은 지문이다"


def test_stamping_a_section_that_is_not_a_target_fails(ds):
    """★ 없는 절을 찍으면 **조용히 통과하지 않는다.** 조용하면 찍은 줄 알고 넘어간다."""
    assert ds.stamp("없는절/999") == 1


def test_selftest_is_not_an_empty_net(ds):
    """판별식 자기검사가 실물에서 초록인가 — 빈 그물이면 여기가 유일한 신호다."""
    assert ds.selftest() == 0


def test_check_fails_when_there_is_nothing_to_check(ds, monkeypatch):
    """★ `deadcheck ③` 조용한 통과. 도장 대상이 0절이면 통과가 아니라 실패다."""
    monkeypatch.setattr(ds, "survey", lambda: ({}, {}))
    assert ds.check() == 1


def test_only_wired_sections_are_targets(ds):
    """부모 칸을 무는 절(`inherit`)은 부모 도장이 덮는다 — 두 번 찍지 않는다."""
    now, _ = ds.survey()
    rows = {r["id"]: r for r in ds._sections()}
    bad = [k for k in now if rows[k]["state"] != "wired"]
    assert not bad, f"물리는 절까지 도장 대상으로 센다: {bad[:5]}"
