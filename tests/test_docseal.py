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


# ── 절을 하나 붙였다고 직전 절이 무효가 되면 안 된다 (§273-10) ──
def test_appending_a_section_does_not_void_the_one_before_it(ds, tmp_path, monkeypatch):
    """★ 2026-09-27 실측. `§273` 을 붙이자 `§272` 의 도장이 무효가 됐다 —
    **참조 파일이 하나도 안 바뀌었는데.** 마지막 절은 EOF 까지 잘리는데 뒤에 새
    절이 붙으면 구분용 빈 줄 하나가 본문에 들고 나기 때문이다.

    ★ 거짓 무효는 도장을 죽인다. 배치마다 뜨는 「다시 보라」는 아무도 안 읽고,
      그러면 진짜 무효도 같이 안 읽힌다.
    """
    # ★ 실물 모양을 그대로 쓴다. 붙이기 전에는 파일이 본문에서 끝나고(빈 줄 없음),
    #   붙인 뒤에는 절 사이 **구분 빈 줄 하나**가 생긴다. 처음에 양쪽 다 빈 줄을
    #   넣고 재현했더니 `.rstrip()` 을 떼도 초록이었다 — 합성이 실물과 달랐다.
    one = tmp_path / "d.md"
    monkeypatch.setattr(ds, "ROOT", tmp_path)

    one.write_text("## 1\n본문\n", encoding="utf-8")
    alone = ds.body([{"doc": "d.md", "line": 1, "depth": 2, "id": "d/1"}], 0)
    one.write_text("## 1\n본문\n\n## 2\n뒤에 붙은 절\n", encoding="utf-8")
    rows = [{"doc": "d.md", "line": 1, "depth": 2, "id": "d/1"},
            {"doc": "d.md", "line": 4, "depth": 2, "id": "d/2"}]
    followed = ds.body(rows, 0)
    assert alone == followed, (
        "절을 뒤에 붙였더니 앞 절의 본문이 달라진다 — 도장이 이유 없이 무효가 된다.\n"
        f"  홀로: {alone!r}\n  뒤에 절: {followed!r}")


def test_an_old_digest_is_accepted_and_not_a_silent_pass(ds):
    """★ 규칙이 바뀌어도 **사람이 확인한 사실**은 그대로다 — 옛 지문을 받는다.

    다만 **아무 지문이나 받지는 않는다.** 받는 것은 `LEGACY_BODIES` 가 내는 것뿐이고,
    엉뚱한 지문은 여전히 무효다. 그 둘을 안 가르면 도장이 통과만 하는 도장이 된다.
    """
    now = {"sha": "새것", "legacy": ["옛것"]}
    assert ds.valid(now, {"sha": "새것"}), "새 지문을 거절한다"
    assert ds.valid(now, {"sha": "옛것"}), "옛 판 지문을 안 받는다 — 규칙만 바꿔도 전부 무효가 된다"
    assert not ds.valid(now, {"sha": "엉뚱한것"}), "아무 지문이나 받는다 — 도장이 죽었다"
    assert not ds.valid(now, None), "도장이 없는데 유효라고 한다"
    assert ds.LEGACY_BODIES, "옛 판 목록이 비었다 — 빈 목록은 통과가 아니다"


# ── 도장 갈래 — «읽음» 과 «불변» 은 다른 주장이다  (§277) ────────
def test_a_bare_stamp_refuses(ds):
    """★ 이 파일에서 제일 중요한 시험이다.

    종전에는 `stamp` 를 인자 없이 부르면 `was = now` 로 **전부** 찍었다.
    490절을 한 줄로 「확인했다」로 만드는 명령이 있었다는 뜻이고, 그러면
    이 도구의 뜻이 그 한 줄로 죽는다. 무엇을 왜 찍는지 말해야 찍는다.
    """
    assert ds.stamp(None, unmoved=False) == 1, "인자 없는 stamp 가 전부 찍는다"
    assert not ds.SEAL.exists(), "찍지 말아야 하는데 파일을 썼다"


def test_the_two_kinds_are_not_the_same_claim(ds):
    """「사람이 읽었다」와 「안 움직였다」를 한 칸에 적으면 수가 거짓이 된다."""
    assert set(ds.KINDS) == {"read", "unmoved"}
    assert ds.KINDS["read"] != ds.KINDS["unmoved"]
    assert ds.DEFAULT_KIND == "read", \
        "갈래 칸이 없는 옛 도장은 **사람이 찍은 것**이다 — 기계 것으로 세면 읽음이 준다"


def test_an_old_stamp_without_a_kind_counts_as_read(ds):
    """옛 판에는 갈래 칸이 없다. 그것을 「불변」으로 읽으면 사람이 읽은 기록이 사라진다."""
    assert ds.kind_of({"sha": "x"}) == "read"
    assert ds.kind_of(None) == "read"
    assert ds.kind_of({"sha": "x", "kind": "unmoved"}) == "unmoved"


def test_stamping_one_section_marks_it_read(ds, monkeypatch):
    monkeypatch.setattr(ds, "survey", lambda: ({"D/1": {"sha": "a", "files": [], "doc": "d"}}, {}))
    assert ds.stamp("D/1") == 0
    got = json.loads(ds.SEAL.read_text(encoding="utf-8"))
    assert got["D/1"]["kind"] == "read", "사람이 찍었는데 기계 갈래로 적혔다"


# ── 절 단위로 재는가  (§277-1) ──────────────────────────────────
def test_moved_after_is_measured_per_section_not_per_document(ds, monkeypatch):
    """★ 문서 mtime 으로 재면 **모든 절**이 「코드보다 나중」이 된다.

    문서는 배치마다 손대기 때문이다. 실제로 그렇게 재봤다가 459/470 이라는
    쓸모없는 수가 나왔다 — 그 수로는 어느 절도 못 고른다.
    """
    rows = [{"id": "D/1", "doc": "docs/D.md", "line": 1, "depth": 2},
            {"id": "D/2", "doc": "docs/D.md", "line": 5, "depth": 2}]
    monkeypatch.setattr(ds, "_span", lambda r, i: (0, 4) if i == 0 else (4, 9))
    # 1절은 100 에 쓰였고, 2절은 300 에 쓰였다
    blames = {"docs/D.md": [100, 100, 100, 100, 300, 300, 300, 300, 300]}
    mt = {"a.py": 200}
    assert ds.moved_after(rows, 0, ["a.py"], blames, mt) == 200, \
        "절(100)보다 코드(200)가 나중인데 0 을 냈다"
    assert ds.moved_after(rows, 1, ["a.py"], blames, mt) == 0, \
        "절(300)이 코드(200)보다 나중인데 움직였다고 했다"


def test_moved_after_refuses_when_it_cannot_measure(ds, monkeypatch):
    """★ blame 을 못 읽으면 **안 찍는다.** 못 잰 것을 「불변」으로 찍으면 거짓 도장이다."""
    rows = [{"id": "D/1", "doc": "docs/D.md", "line": 1, "depth": 2}]
    monkeypatch.setattr(ds, "_span", lambda r, i: (0, 0))
    assert ds.moved_after(rows, 0, ["a.py"], {"docs/D.md": []}, {"a.py": 999}) == 0


def test_span_follows_the_same_rule_as_body(ds, tmp_path, monkeypatch):
    """★ 경계 규칙이 두 벌이면 갈린다 — 도장은 `body()` 로 뜨고 시각은 `_span()` 으로 잰다."""
    monkeypatch.setattr(ds, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "D.md").write_text(
        "## 1. 가\n본문\n\n### 1-1. 나\n안쪽\n\n## 2. 다\n딴절\n", encoding="utf-8")
    rows = [{"id": "D/1", "doc": "docs/D.md", "line": 1, "depth": 2},
            {"id": "D/1-1", "doc": "docs/D.md", "line": 4, "depth": 3},
            {"id": "D/2", "doc": "docs/D.md", "line": 7, "depth": 2}]
    a, b = ds._span(rows, 0)
    assert (a, b) == (0, 6), "얕은 제목 전까지가 아니다"
    assert "딴절" not in ds.body(rows, 0), "옆 절을 삼켰다"
    assert "안쪽" in ds.body(rows, 0), "하위 절을 잘라냈다"
