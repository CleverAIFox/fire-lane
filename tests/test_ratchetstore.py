"""tools/ratchetstore.py — 래칫 값을 도구 파일 밖에 둔다. 값만 움직이면 도장이 안 죽고 **논리를 고치면 죽는다**. (PLAN #198)

★ 양성 대조 둘이 이 시험의 본체다. 앞쪽만 있으면 **봉인이 뚫렸는지** 모른다 — 값을 밖으로 빼며 도구 논리까지 지문 밖으로 새면 도장이 아무것도 안 문다.
  그래서 같은 도구 사본에서 ① 값만 고쳐 쓰고(지문 불변) ② 논리 한 줄을 고쳐 쓰는(지문 변경) 둘을 **실제 도장 지문 함수**(`docsealfp.digest`)로 본다.

★★ 그 값 파일을 어느 문서 절도 백틱으로 적지 않는다 — 적는 순간 그 절의 지문에 값이 들어가고 원점이다. 문서 전체에서 센다.

밖    기준 수(`MOVE_AT`)가 옳은가는 안 본다 — `--rank` 가 수를 내는지만 본다. 실제 `ratchet --write` 의 전 도구 경로는 `test_ratchet` 가 든다.
"""
from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import docseal
import docsealfp as FP
import ratchet as R
import ratchetstore as RS

ROOT = Path(__file__).resolve().parents[1]
STORE_REL = "data/golden/ratchets.json"


def _tmp_tree(tmp_path: Path) -> Path:
    """도구 사본과 값 파일 사본만 든 작은 저장소 뿌리 — 지문 함수가 그 뿌리를 읽게 한다."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "data" / "golden").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "sealcov.py", tmp_path / "tools" / "sealcov.py")
    shutil.copy(ROOT / STORE_REL, tmp_path / STORE_REL)
    return tmp_path


def _digest(root: Path, monkeypatch) -> str:
    monkeypatch.setattr(FP, "ROOT", root)
    return FP.digest("sealcov 를 지목한 절 본문", ["tools/sealcov.py"])


def test_changing_only_the_value_does_not_move_the_tool_seal(tmp_path, monkeypatch):
    root = _tmp_tree(tmp_path)
    before = _digest(root, monkeypatch)
    RS.write("sealcov.py", "SEALED_FILES", RS.read("sealcov.py", "SEALED_FILES") + 7, root / STORE_REL)
    assert RS.read("sealcov.py", "SEALED_FILES", root / STORE_REL) == RS.read("sealcov.py", "SEALED_FILES") + 7, "값 파일에 안 써졌다"
    assert _digest(root, monkeypatch) == before, "값만 고쳤는데 도구의 지문이 움직였다 — 값이 아직 도구 파일 안에 있다"


def test_changing_the_tool_logic_still_moves_the_tool_seal(tmp_path, monkeypatch):
    """양성 대조 — 이것이 안 죽으면 봉인이 뚫린 것이다(값만 밖에 있어야 하고 논리는 지문 안에 남아야 한다)."""
    root = _tmp_tree(tmp_path)
    before = _digest(root, monkeypatch)
    p = root / "tools" / "sealcov.py"
    src = p.read_text(encoding="utf-8")
    assert "if cov < SEALED_FILES:" in src, "대조가 고칠 논리 줄을 못 찾는다 — 도구가 바뀌었으면 이 시험도 따라간다"
    p.write_text(src.replace("if cov < SEALED_FILES:", "if cov <= SEALED_FILES:", 1), encoding="utf-8")
    assert _digest(root, monkeypatch) != before, "논리를 고쳤는데 지문이 안 움직였다 — 봉인이 뚫렸다"


def test_sealcov_keeps_no_integer_literal_for_the_stored_value():
    tree = ast.parse((ROOT / "tools" / "sealcov.py").read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SEALED_FILES" for t in n.targets):
            assert not isinstance(n.value, ast.Constant), "SEALED_FILES 가 다시 숫자 리터럴이다 — 한 칸 조일 때마다 이 도구의 도장이 죽는다"
            return
    raise AssertionError("SEALED_FILES 선언을 못 찾았다")


def test_ratchet_write_goes_to_the_store_and_never_touches_the_tool_file(tmp_path, monkeypatch):
    store = tmp_path / "r.json"
    store.write_text(json.dumps({"values": {"sealcov.py": {"SEALED_FILES": 5}}}), encoding="utf-8")
    monkeypatch.setattr(RS, "STORE", store)
    row = {"tool": "sealcov.py", "name": "SEALED_FILES", "dir": "up", "declared": 5, "measured": 9, "at": (5, 0, 0), "store": True}
    monkeypatch.setattr(R, "survey", lambda: [row])
    tool = ROOT / "tools" / "sealcov.py"
    before = tool.read_bytes()
    assert R.run(write=True) == 0
    assert RS.read("sealcov.py", "SEALED_FILES") == 9, "조이는 값이 값 파일에 안 써졌다"
    assert tool.read_bytes() == before, "값 파일 쪽 래칫인데 도구 파일을 고쳤다"


def test_no_document_names_the_store_path_in_backticks():
    """★★ 적는 순간 그 절의 지문에 값이 들어간다. 도장이 읽는 정규식(`docsealfp.PATH`)으로 문서 전체를 센다."""
    hits = []
    for md in [*sorted((ROOT / "docs").glob("*.md")), ROOT / "README.md"]:
        if md.is_file() and STORE_REL in FP.PATH.findall(md.read_text(encoding="utf-8")):
            hits.append(md.name)
    assert not hits, f"{hits} 가 값 파일 경로를 백틱으로 적었다 — 그 절의 도장이 값에 묶인다"


def test_the_rank_names_the_costliest_tools_and_the_moved_one_is_marked():
    rows = RS.rank()
    assert rows and rows == sorted(rows, key=lambda r: (-r[0], r[1])), "많은 순이 아니다"
    top = rows[0]
    assert top[1] == "sealcov.py" and top[3] is True, "값 파일로 옮긴 도구가 표시되지 않는다"
    assert top[0] >= RS.MOVE_AT, f"옮긴 근거가 기준({RS.MOVE_AT}) 미만이다 — {top[0]}절"


def test_the_store_has_exactly_the_tools_above_the_bar_or_a_reason():
    """값 파일에 든 도구는 전부 기준을 넘는다 — 기준 없이 하나씩 늘리면 규약이 판단으로 돌아간다."""
    cnt = RS.seals_per_tool()
    low = {t: cnt.get(f"tools/{t}", 0) for t in RS.load() if cnt.get(f"tools/{t}", 0) < RS.MOVE_AT}
    assert not low, f"기준 {RS.MOVE_AT} 미만인 도구가 값 파일에 있다: {low}"
    assert docseal  # 같은 survey 를 쓴다 — 두 번째 셈이 없다
