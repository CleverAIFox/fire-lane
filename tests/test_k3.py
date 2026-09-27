"""K3 · G — 도구 결함 카나리아. (DECISIONS §182)

★ 2026-09-17. 형태로 잡는다 — 같은 모양이 저장소 어디에 다시 생겨도 운다.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _py_files():
    for sub in ("src", "tools"):
        yield from sorted((ROOT / sub).rglob("*.py"))


def _fields_or_empty(tree: ast.AST) -> list[int]:
    """`x["fields"] or []` · `x.get("fields") or []` — numpy 배열에 `or` 를 걸면 진리값이 모호해 죽는다."""
    hits = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)):
            continue
        left = n.values[0]
        key = None
        if isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Constant):
            key = left.slice.value
        elif (isinstance(left, ast.Call) and isinstance(left.func, ast.Attribute) and left.func.attr == "get"
              and left.args and isinstance(left.args[0], ast.Constant)):
            key = left.args[0].value
        if key == "fields":
            hits.append(n.lineno)
    return hits


def test_g15_pyogrio_fields_never_meet_or():
    """§182-4 · G-15 — pyogrio `read_info()["fields"]` 는 numpy 배열이다. EDA v2 가 `or []` 로 받아 기본도를 전멸시켰다.
    저장소에는 그 형태가 0건이다(2026-09-17 전수). 생기면 여기서 운다."""
    bad = [f"{p.relative_to(ROOT)}:{ln}" for p in _py_files()
           for ln in _fields_or_empty(ast.parse(p.read_text(encoding="utf-8")))]
    assert not bad, f"fields 를 `or` 로 받는다 — `list(info['fields'])` 로 — {bad}"
    probe = ast.parse('a = info["fields"] or []\nb = d.get("fields") or []\nc = info["features"] or 0\n')
    assert _fields_or_empty(probe) == [1, 2], "프로브가 죽었다"


JQ_FIRST = re.compile(r"""--jq\s+(['"])(?P<expr>.*?\.\[0\][^'"]*)\1""")


def _jq_first_without_empty(text: str) -> list[str]:
    return [m.group("expr") for m in JQ_FIRST.finditer(text) if "// empty" not in m.group("expr")]


def test_g16_jq_first_element_has_empty_fallback():
    """§182-3 · G-16 — `.[0].x` 는 목록이 비면 `null` 을 **글자로** 낸다. `[ -z ]` 가 못 걸러 `PR #null` 로 흘렀다."""
    bad = []
    for p in [*sorted((ROOT / "tools").rglob("*.sh")), *sorted((ROOT / ".github").rglob("*.yml"))]:
        bad += [f"{p.relative_to(ROOT)}: {e}" for e in _jq_first_without_empty(p.read_text(encoding="utf-8"))]
    assert not bad, f"jq `.[0]` 에 `// empty` 가 없다 — {bad}"
    assert _jq_first_without_empty("x=$(gh pr list --jq '.[0].number')") == [".[0].number"], "프로브가 죽었다"
    assert _jq_first_without_empty("x=$(gh pr list --jq '.[0].number // empty')") == []


def test_g15_inventory_field_list_accepts_numpy():
    import numpy as np

    from firelane.inventory import _field_list
    assert _field_list(np.array(["A", "B"], dtype=object)) == ["A", "B"]
    assert _field_list(np.array([], dtype=object)) == []
    assert _field_list(None) == []


def test_g23_wait_checks_reads_head_commit_runs():
    """§182-8 · G-23 — CI 대기는 PR 머리 커밋의 check-run 을 본다. "체크가 있으면 끝" 은 옛 실행으로 판정한다."""
    src = (ROOT / "tools/merge_batch.sh").read_text(encoding="utf-8")
    body = src[src.index("wait_checks() {"):src.index("sync_parts() {")]
    assert "headRefOid" in body and "check-runs" in body, "머리 커밋 기준이 아니다"
    assert "started_at" in body, "본문 편집 뒤 새 실행을 구분하지 못한다"
    assert not re.search(r'gh pr checks "\\$n"[^\\n]*>/dev/null 2>&1 && break', body), "옛 형태(존재만 확인)가 돌아왔다"


def test_g14_zip_names_are_recorded_readable(tmp_path):
    """§182-1 — 플래그 없는 CP949 zip 이름은 `╣╬┐°…` 가 아니라 한글로 기록한다. UTF-8 · ASCII 이름은 그대로."""
    import importlib.util
    import zipfile
    spec = importlib.util.spec_from_file_location("k3_ledger_schema", ROOT / "tools" / "ledger_schema.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    zp = tmp_path / "a.zip"
    class Cp949Info(zipfile.ZipInfo):          # 제공처 zip 처럼 — CP949 바이트 · UTF-8 플래그 없음
        def _encodeFilenameFlags(self):
            return self.filename.encode("cp949"), self.flag_bits & ~0x800

    with zipfile.ZipFile(zp, "w") as z:
        z.writestr(Cp949Info("민원행정기관_202401.shp"), b"x")
        z.writestr("TL_SPRD_RW.shp", b"x")
        z.writestr("한글_utf8.dbf", b"x")
    with zipfile.ZipFile(zp) as z:
        assert z.namelist()[0].startswith("╣╬"), "프로브가 죽었다 — 제공처 zip 모양이 아니다"
    with zipfile.ZipFile(zp) as z:
        got = [m._zip_display(i) for i in z.infolist()]
    assert got == ["민원행정기관_202401.shp", "TL_SPRD_RW.shp", "한글_utf8.dbf"]
