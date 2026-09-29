"""
test_sweep_retired.py — 철거된 산출물을 **도구가** 치우는가. (DECISIONS §305)

── 왜 이 파일이 생겼나 ────────────────────────────────────────
`test_no_undeclared_output` 의 실패 메시지가 「`sweep --sweep --yes` 가
치운다」고 말한다. **그 말이 참인지 무는 것이 없으면 그것은 주장이다.**
배치 K 가 죽은 원인이 정확히 그 모양이었다 — §302 가 「철거했다」고 적고
파일은 기계에 남겼다. 적은 것과 된 것이 달랐다.

★ 저장소를 안 건드린다. `torn_down(y, root=...)` 에 임시 트리를 준다 —
  실물 `data/processed` 에 파일을 만들었다 지우는 시험은, 중간에 죽으면
  다음 실행을 빨갛게 만든다.

IN    sources.yaml(retired_outputs) · tools/sweep.py
OUT   없음
밖    **지우는 동작 자체는 안 부른다.** `--sweep --yes` 를 시험에서 돌리면
      실물 파일을 지운다 — 판정(「지울 것에 드는가」)까지만 든다. 지우는 코드는
      `main()` 의 공통 경로이고 `dele`·`land` 와 같은 목록을 받는다.
      **`retired`(원천 데이터셋 폐기)는 안 본다.** 그쪽은 `retired_names()` 다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sweep():
    """`tools/sweep.py` 를 파일에서 적재한다.

    ★ `sys.path` 를 만지지 않는다 — `tests/test_layering.py` 가 그것을 막는다.
      `tools/` 는 패키지가 아니므로 `test_sweep_bookmark.py` 와 같은 방식을 쓴다.
    """
    spec = importlib.util.spec_from_file_location("sweep_ret", ROOT / "tools" / "sweep.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    return m


SW = _sweep()
led, torn_down = SW.led, SW.torn_down


def _ledger() -> dict:
    """★ 대장은 **한 문으로만** 읽는다 — `sweep.led()` 가 그 문이다.
    직접 `yaml.safe_load` 하면 `tests/test_lake.py::test_ledger_is_loaded_through_one_door`
    의 상한을 올려야 하고, 그 상한은 줄어드는 쪽으로만 움직인다."""
    return SW.led()


def test_the_declaration_is_not_empty():
    """철거 대장이 비면 이 시험 전체가 아무것도 안 잰다."""
    assert (_ledger().get("retired_outputs") or {}), (
        "retired_outputs 가 비었다 — 철거한 것이 없으면 이 파일을 지워라")


def test_a_leftover_is_judged_deletable(tmp_path: Path):
    """선언된 경로에 파일이 있으면 「판단 완료」로 지울 것에 든다."""
    y = _ledger()
    ent = next(iter(y["retired_outputs"].values()))
    q = tmp_path / ent["path"]
    q.parent.mkdir(parents=True, exist_ok=True)
    q.write_bytes(b"stale")

    got = torn_down(y, root=tmp_path)
    assert [p for p, _, _ in got] == [q], f"잔재를 못 찾았다: {got}"
    verdict, why = got[0][1], got[0][2]
    assert verdict == "판단 완료", f"판정이 {verdict} — 지울 수 있어야 한다"
    assert "retired_outputs." in why and "§" in why, (
        f"근거에 대장 키와 § 가 없다: {why}")


def test_an_absent_file_is_not_reported(tmp_path: Path):
    """★ 반대 방향. 없는 것을 지울 것에 넣으면 sweep 이 매번 빨개진다."""
    assert torn_down(_ledger(), root=tmp_path) == []


def test_only_declared_paths_are_touched(tmp_path: Path):
    """★ 이것이 안전장치다. 선언 밖 파일을 이 판정이 집으면 **살아 있는
    산출물을 지우게 된다.** `processed` 를 통째로 훑지 않는다는 규약의 시험이다.
    """
    y = _ledger()
    ent = next(iter(y["retired_outputs"].values()))
    d = tmp_path / Path(ent["path"]).parent
    d.mkdir(parents=True, exist_ok=True)
    (d / "segments.geojson").write_text("살아 있는 산출물", encoding="utf-8")
    (d / "streetlight_5186.gpkg").write_text("light_count 가 읽는 것", encoding="utf-8")
    assert torn_down(y, root=tmp_path) == [], "선언 밖 파일을 지울 것에 넣었다"


def test_the_repo_is_clean_right_now():
    """지금 이 저장소에 철거 잔재가 없다. 있으면 sweep 을 돌려라."""
    left = [str(p.relative_to(ROOT)) for p, _, _ in torn_down(led())]
    assert not left, (
        "철거 잔재가 남아 있다: " + ", ".join(left) +
        "\n  uv run python tools/sweep.py --sweep --yes")
