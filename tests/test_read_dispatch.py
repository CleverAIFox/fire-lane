#!/usr/bin/env python3
"""
test_read_dispatch.py — `kind` → 갈래 배선이 **선언과 맞는가.**  (PLAN §1 #128 · DECISIONS §274)

── 왜 생겼나 ──────────────────────────────────────────────────
갈래를 `read/` 로 내리면서 표 하나가 정본이 됐다. 표는 **조용히 틀릴 수 있다** —
`kind` 하나를 빠뜨려도 그 소스를 돌릴 때까지 아무도 모르고, 도형/표 선언이
어긋나면 dict 가 `save()` 로 들어가 한참 아래에서 엉뚱한 이름으로 죽는다.

IN    firelane.read · firelane.kinds · sources.yaml
OUT   없음 (검사)
밖    **갈래가 옳게 읽는가는 안 본다** — 그것은 레이크가 있어야 재고,
      파이프라인 실행과 `_manifest.json` 대조가 든다. 여기는 **배선**만 본다.
      그리고 **어느 실물을 읽을지도 안 본다** — `ingest.paths_for` 소관이다.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from firelane import kinds, ledger, read

ROOT = Path(__file__).resolve().parents[1]

#: 훑는 범위 — 저장소의 파이썬 전부. 좁히면 `deadcheck ⑤` 가 문다.
ROOTS = ("src", "tools", "tests")


def _repo_py() -> list[Path]:
    return sorted(q for r in ROOTS for q in (ROOT / r).rglob("*.py")
                  if "__pycache__" not in q.parts)


def test_every_kind_the_ledger_uses_has_a_reader():
    """★ 이 시험이 이 파일의 본체다. 하나 빠지면 그 소스가 실행 중에 죽는다."""
    # ★ 대장은 `ledger.load` 한 문으로만 연다 — 여기서 yaml 로 직접 읽으면
    #   `test_lake` 의 「대장 직접 로드」 래칫이 하나 는다(실제로 한 번 늘렸다).
    used = {(v or {}).get("kind")
            for v in ledger.load()["datasets"].values()} - {None}
    # ★ 카나리아. 대장을 못 읽거나 칸 이름이 바뀌면 `used` 가 비고, 그러면
    #   아래 대조가 **공집합끼리 맞아** 조용히 초록이 난다. 주입 ③(대장에서
    #   `kind` 를 전부 지운다)이 실제로 그렇게 통과했다 — 그래서 이 줄이 있다.
    assert len(used) >= 8, (
        f"대장이 쓰는 kind 가 {len(used)}종이다 — 대장을 못 읽었거나 칸 이름이 "
        "바뀌었다. 0 을 통과로 세지 않는다")

    missing = sorted(used - set(read.READERS))
    assert not missing, (
        f"대장이 쓰는 kind 인데 갈래가 없다: {missing}\n"
        "  실행하면 `read.reader()` 가 세운다. 셋을 잇는다 — "
        "firelane.kinds.KINDS · read/<갈래>.py 의 함수 · read.READERS")


def test_the_registry_and_the_classifier_agree():
    """`kinds.KINDS` 는 분류, `read.READERS` 는 읽기다. 한쪽에만 있으면 갈린 것이다."""
    only_class = sorted(set(kinds.KINDS) - set(read.READERS))
    only_read = sorted(set(read.READERS) - set(kinds.KINDS))
    assert not only_class, (
        f"분류에는 있고 읽기에는 없다: {only_class} — 그 kind 는 대장에 적을 수 "
        "있는데 실행하면 죽는다")
    assert not only_read, (
        f"읽기에는 있고 분류에는 없다: {only_read} — `ledger` 가 그 kind 의 "
        "스키마·복수성을 모른다")


def test_geom_declaration_matches_what_each_reader_returns():
    """★ 선언과 실물이 갈리면 dict 가 `save()` 로 들어간다.

    함수 본문에서 `return g` 로 끝나는가를 본다 — 실행 없이 잴 수 있는 것은
    여기까지고, 그 너머는 파이프라인이 든다(머리말 「밖」).
    """
    bad = []
    for kind, fn in read.READERS.items():
        src = inspect.getsource(fn)
        gives_geom = "\n    return g\n" in src
        if gives_geom is not (kind in read.GEOM_KINDS):
            bad.append(f"  {kind}: 실물 {'도형' if gives_geom else '계보 조각'} · "
                       f"선언 {'도형' if kind in read.GEOM_KINDS else '계보 조각'}")
    assert not bad, "`read.GEOM_KINDS` 선언이 갈래 실물과 다르다:\n" + "\n".join(bad)


def test_unknown_kind_says_what_it_knows():
    """모른다고만 하면 다음 사람이 다시 찾아야 한다. 아는 것을 댄다."""
    with pytest.raises(ValueError) as ex:
        read.reader("no_such_kind")
    msg = str(ex.value)
    assert "no_such_kind" in msg
    assert "raw_only" in msg, "아는 kind 를 안 댄다"
    assert "READERS" in msg, "어디를 고치면 되는지 안 알려준다"


def test_no_reader_reaches_back_into_ingest():
    """★ 갈래가 `ingest` 를 부르면 임포트가 돈다(DECISIONS §274-4).

    `save` 는 `Ctx` 로 **주입**받는다 — 그것이 유일한 통로다.
    """
    # ★ **저장소 전체를 훑고 걸러낸다.** `read/` 만 훑으면 갈래 함수가 `tools/` 나
    #   `tests/` 에 슬쩍 놓였을 때 못 본다 — 그리고 `deadcheck ⑤`(좁은 범위)가
    #   「이 검사가 src 만 본다」고 정확히 문다. 훑는 범위는 전부고, 좁은 것은 술어다.
    bad = []
    for p in _repo_py():
        rel = p.relative_to(ROOT).as_posix()
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = ln.strip()
            if not (s.startswith(("import ", "from ")) and "firelane.ingest" in s):
                continue
            if rel.startswith("src/firelane/read/"):
                bad.append(f"  {rel}:{i}  {s}")
            elif "def read_" in p.read_text(encoding="utf-8"):
                bad.append(f"  {rel}:{i}  갈래 함수를 들면서 `ingest` 를 부른다")
    assert not bad, (
        "갈래가 `ingest` 를 임포트한다 — `read → ingest → read` 로 고리가 돈다.\n"
        "  필요한 것은 `Ctx` 로 받아라(지금 `save` 가 그렇다).\n" + "\n".join(bad))


def test_every_family_module_declares_its_scope():
    """머리말의 `밖` 칸 — 이름이 시사하지만 이 모듈이 **안 보는 것**."""
    # ★ 위와 같은 이유로 전부 훑고 `read/` 만 고른다(`deadcheck ⑤`).
    bad = []
    for p in _repo_py():
        if p.parent.name != "read" or p.parent.parent.name != "firelane":
            continue
        if "밖" not in p.read_text(encoding="utf-8")[:2000]:
            bad.append(p.name)
    assert not bad, (
        f"`밖` 칸 없는 갈래 모듈: {bad}\n"
        "  선언이 없으면 다음 사람이 이 모듈에 안 맞는 일을 넣는다")
