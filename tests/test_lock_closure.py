"""잠금 폐포 — **좁힌 것이 여전히 무는가.**  (DECISIONS §345)

── 왜 이 파일이 생겼나 ─────────────────────────────────────────
`shardseal.code_print` 과 `golden` 이 `uv.lock` **파일 전체**를 해시하고 있었다.
의도는 「산출물을 만드는 패키지의 판」이었고 구현은 「잠금 파일」이었다 —
그래서 취입에 한 바이트도 안 닿는 `ultralytics` 를 선언에서 지우는 일이
45샤드를 찢었다.

좁히는 변경은 **느슨해지는 쪽**이다. 그래서 이 파일이 드는 물음은 하나다 —
**좁힌 뒤에도 물어야 할 것을 무는가.** 틀리는 방향이 둘인데 값이 다르다.

    넓게 틀린다   안 찢어도 될 것이 찢어진다        → 시간을 잃는다
    좁게 틀린다   **낡은 산출물을 재사용한다**      → 판정이 거짓이 된다

후자는 되돌릴 수 없다. 그래서 「모르면 터뜨린다」가 설계이고, 그것도 여기서
판별식으로 든다.

★ **합성 잠금으로 잰다.** 실물 `uv.lock` 으로 재면 「`ultralytics` 를 지워도
  안 움직인다」를 증명할 수가 없다 — 지울 것이 이미 없다. 결함이 사라지면
  영구 빨간불이 되는 그 꼴이다(§262-2).

IN    합성 트리(src/firelane · pyproject.toml · uv.lock)
OUT   없음 (검사)
밖    **실물 저장소의 값이 맞는가는 안 본다.** 지금 폐포가 12·13·19 인 것은
      `test_the_real_tree_closure_is_the_geo_stack` 이 아래쪽에서 따로 든다.
      **의존성 해석이 옳은가도 안 본다** — 그것은 `uv` 의 일이고, 여기가 드는
      것은 「잠금에 적힌 그래프를 제대로 따라가는가」다.
"""
from __future__ import annotations

import textwrap

import pytest

from firelane import shardseal

LOCKMAP = '[tool.deptry]\npackage_module_name_map = { "PyYAML" = "yaml" }\n'


def _lock(*rows: tuple[str, str, tuple[str, ...]]) -> str:
    """합성 `uv.lock`. `(이름, 판, 직접의존)` 들."""
    out = ["version = 1", ""]
    for name, ver, deps in rows:
        out += ["[[package]]", f'name = "{name}"', f'version = "{ver}"']
        if deps:
            out.append("dependencies = [")
            out += [f'    {{ name = "{d}" }},' for d in deps]
            out.append("]")
        out.append("")
    return "\n".join(out)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """`firelane.ingest` 가 `geopandas` · `yaml` 을 import 하는 최소 트리."""
    pkg = tmp_path / "src" / "firelane"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "ingest.py").write_text(textwrap.dedent("""
        import geopandas
        import yaml
        from firelane.guards import g
    """).lstrip(), encoding="utf-8")
    (pkg / "guards.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(LOCKMAP, encoding="utf-8")
    (tmp_path / "uv.lock").write_text(_lock(
        # 폐포 안 — geopandas 가 shapely 를 끌고 오고 shapely 가 numpy 를
        ("geopandas", "1.1.4", ("shapely",)),
        ("shapely", "2.1.2", ("numpy",)),
        ("numpy", "2.5.3", ()),
        ("pyyaml", "6.0.3", ()),
        # 폐포 밖 — 아무도 import 하지 않는다
        ("ultralytics", "8.4.156", ("torch",)),
        ("torch", "2.14.0", ()),
    ), encoding="utf-8")
    monkeypatch.setattr(shardseal, "PKG", pkg)
    monkeypatch.setattr(shardseal, "ROOT", tmp_path)
    return tmp_path


# ══ ① 폐포가 무엇을 긋는가 ══════════════════════════════════════
def test_the_closure_is_the_imports_plus_their_transitive_deps(tree) -> None:
    """★ **전이까지 센다.** `geopandas` 만 세면 `shapely` 판이 움직여도 모른다 —
    그런데 실제로 폭을 재는 것은 `shapely` 다."""
    got = shardseal.lock_deps("firelane.ingest")
    assert got == ["geopandas==1.1.4", "numpy==2.5.3", "pyyaml==6.0.3", "shapely==2.1.2"], got


def test_the_import_name_goes_through_the_declared_map(tree) -> None:
    """★ `import yaml` → 배포 이름 `PyYAML` → 잠금의 `pyyaml`. 그 짝의 집은
    `pyproject` 한 표이고, 대소문자 차이는 `_norm` 이 접는다(§18-3)."""
    assert "pyyaml==6.0.3" in shardseal.lock_deps("firelane.ingest")


def test_the_net_is_not_empty(tree) -> None:
    """★ **빈 그물 물음**(MASTER §17-0 ③). 수집기가 죽으면 아래 「안 움직인다」
    판별식들이 전부 조용히 통과한다 — 0개를 0개와 비교하기 때문이다."""
    assert len(shardseal.lock_deps("firelane.ingest")) >= 4


# ══ ② 안 움직여야 하는 것 ═══════════════════════════════════════
def test_removing_an_unused_package_does_not_move_the_print(tree) -> None:
    """★ **이 배치의 요점.** 쓰지 않는 선언을 지우는 것이 샤드를 찢지 않는다."""
    before = shardseal.lock_print("firelane.ingest")
    (tree / "uv.lock").write_text(_lock(
        ("geopandas", "1.1.4", ("shapely",)),
        ("shapely", "2.1.2", ("numpy",)),
        ("numpy", "2.5.3", ()),
        ("pyyaml", "6.0.3", ()),
    ), encoding="utf-8")                       # ultralytics · torch 를 지웠다
    assert shardseal.lock_print("firelane.ingest") == before, (
        "폐포 밖 패키지를 지웠는데 지문이 움직인다 — 좁히기가 안 먹었다")


def test_an_unused_package_version_bump_does_not_move_the_print(tree) -> None:
    before = shardseal.lock_print("firelane.ingest")
    (tree / "uv.lock").write_text(
        (tree / "uv.lock").read_text(encoding="utf-8").replace("8.4.156", "9.0.0"),
        encoding="utf-8")
    assert shardseal.lock_print("firelane.ingest") == before


# ══ ③ 움직여야 하는 것 — 여기가 죽으면 좁히기가 사고다 ═══════════
def test_a_direct_dependency_bump_moves_the_print(tree) -> None:
    """★ 주석이 늘 적고 있던 그 문장 — 「geopandas 판이 바뀌면 산출물도 바뀐다」."""
    before = shardseal.lock_print("firelane.ingest")
    (tree / "uv.lock").write_text(
        (tree / "uv.lock").read_text(encoding="utf-8").replace("1.1.4", "1.2.0"),
        encoding="utf-8")
    assert shardseal.lock_print("firelane.ingest") != before, "geopandas 가 움직였는데 지문이 그대로다"


def test_a_transitive_dependency_bump_moves_the_print(tree) -> None:
    """★ `numpy` 는 아무 파일도 직접 import 하지 않는다. 그래도 폭을 계산한다."""
    before = shardseal.lock_print("firelane.ingest")
    (tree / "uv.lock").write_text(
        (tree / "uv.lock").read_text(encoding="utf-8").replace("2.5.3", "2.6.0"),
        encoding="utf-8")
    assert shardseal.lock_print("firelane.ingest") != before, "전이 의존이 움직였는데 지문이 그대로다"


def test_dropping_an_import_moves_the_print(tree) -> None:
    """★ 폐포가 **줄어드는** 것도 움직임이다. 이름을 안 세면 판만 보게 되고,
    그러면 패키지가 빠진 것을 못 본다."""
    before = shardseal.lock_print("firelane.ingest")
    (tree / "src" / "firelane" / "ingest.py").write_text(
        "import geopandas\nfrom firelane.guards import g\n", encoding="utf-8")
    assert shardseal.lock_print("firelane.ingest") != before, "import 를 지웠는데 지문이 그대로다"


def test_code_print_carries_the_lock_axis(tree) -> None:
    """`code_print` 가 그 축을 **실제로 싣는가.** 안 실으면 위 전부가 헛돈다."""
    before = shardseal.code_print("firelane.ingest")
    (tree / "uv.lock").write_text(
        (tree / "uv.lock").read_text(encoding="utf-8").replace("1.1.4", "1.2.0"),
        encoding="utf-8")
    assert shardseal.code_print("firelane.ingest") != before


# ══ ④ 모르면 터뜨린다 ══════════════════════════════════════════
def test_an_unknown_seed_raises_instead_of_narrowing_silently(tree) -> None:
    """★ **되돌릴 수 없는 방향을 막는다.** 씨앗을 잠금에서 못 찾을 때 조용히
    빼면 그 패키지의 판이 움직여도 지문이 안 움직이고, 그러면 **낡은 산출물을
    재사용한다.** 시간을 잃는 쪽이 아니라 판정이 거짓이 되는 쪽이다."""
    (tree / "src" / "firelane" / "ingest.py").write_text(
        "import nowhere_to_be_found\nfrom firelane.guards import g\n", encoding="utf-8")
    # ★ 점은 정규식 메타문자다 — 날것 꼴로 벗긴다(엄격 린트 RUF043).
    with pytest.raises(RuntimeError, match=r"uv\.lock"):
        shardseal.lock_deps("firelane.ingest")


def test_a_missing_lock_is_an_empty_print_not_a_crash(tree) -> None:
    """잠금이 없는 트리(clone 직후 · 합성)에서도 돌아야 한다 — 그때는 축이 없다."""
    (tree / "uv.lock").unlink()
    assert shardseal.lock_print("firelane.ingest") == ""
    assert shardseal.code_print("firelane.ingest")        # 코드 축은 그대로 있다


# ══ ⑤ 실물 저장소 ══════════════════════════════════════════════
def test_the_real_tree_closure_is_the_geo_stack() -> None:
    """실물에서 폐포가 **지리 스택**인가. 엉뚱한 것이 들면 좁히기가 틀린 것이고,
    비면 수집기가 죽은 것이다.

    ★ 수를 못 박지 않는다 — 의존성이 늘면 그 수는 당연히 는다. 못 박으면
      「목표에 닿는 날 빨개지는 검사」가 된다(§230).
    """
    names = {x.split("==")[0].lower() for x in shardseal.lock_deps("firelane.segments")}
    for need in ("geopandas", "shapely", "numpy", "pyproj", "networkx", "pandas"):
        assert need in names, f"판정 폐포에 {need} 가 없다 — 수집기가 죽었다"
    assert "ultralytics" not in names and "fastapi" not in names, (
        "판정에 안 닿는 패키지가 폐포에 있다 — 좁히기가 안 먹었다")


def test_the_real_tree_narrowing_is_actually_narrower() -> None:
    """★ 좁혔다고 **말만** 하지 않는다. 잠금 전체보다 적은가."""
    import re
    whole = len(re.findall(r"^name = ", (shardseal.ROOT / "uv.lock")
                           .read_text(encoding="utf-8"), re.M))
    for start in ("firelane.ingest", "firelane.segments", "firelane.ortho"):
        n = len(shardseal.lock_deps(start))
        assert 0 < n < whole, f"{start} 폐포 {n} / 잠금 {whole} — 좁혀지지 않았다"


def test_golden_and_shardseal_use_one_function() -> None:
    """★ **한쪽만 좁히면 헛되다.** `golden` 이 제 길로 `uv.lock` 을 바이트로
    재고 있으면 그쪽이 그대로 찢는다 — 그래서 둘이 같은 함수를 쓴다."""
    src = (shardseal.ROOT / "tools" / "golden.py").read_text(encoding="utf-8")
    assert "lock_print" in src, "golden 이 `shardseal.lock_print` 를 안 쓴다"
    live = "\n".join(x.split("#", 1)[0] for x in src.splitlines())
    assert "read_bytes" not in live, "golden 이 아직 잠금을 바이트로 잰다"
