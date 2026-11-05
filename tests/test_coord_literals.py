"""
test_coord_literals.py — 코드가 **좌표 칸 이름을 직접 쓰지 않는가**.  (PLAN #193 · DECISIONS §631-6 · §634)

── 이 시험이 무는 것 ──────────────────────────────────────────
대장 `coords:` 가 지목한 칸 이름(`LOT` · `LAT` · `DCLR_PSTN_LOT` · `WGS84경도` …)이 `src/firelane/` 의 코드에 **문자열이나 속성**으로 나오면 운다 —
칸 이름은 `ledger.coords(key, 역할)` 로만 받는다. 2026-11-04 에 코드가 제 판단으로 `DCLR_PSTN_*`(신고자 휴대폰 위치)를 골라 거짓 좌표 414점이 발행됐다.
대장이 칸의 **뜻**을 말하고 코드가 그 말을 받아 쓰게 하는 것이 이 시험이 지키는 구조다.

★ AST 로 본다 — 주석 · docstring · 긴 문장 안의 낱말은 안 센다(문자열 상수가 **통째로** 칸 이름일 때와 `.LOT` 꼴 속성일 때만).
★ 범위는 `src/firelane/` 다. `tools/` 의 `위도` · `경도` 는 **우리가 내는 CSV 의 칸 이름**이거나(`evalset` · `sensitivity` · `sidewalk_probe`) 모르는 파일의
  칸을 짐작하는 목록(`triage`)이라 원천 칸의 읽기가 아니다 — 넣으면 오탐 공장이 된다.
★ `ledger.py` 는 이 이름들이 **적히는 자리**가 아니라(이름은 `sources.yaml` 에 있다) 어휘만 든다 — 걸리지 않는다. **면제는 없다** — 걸리면 코드를 `ledger.coords` 로 고친다(면제 표를 두면 「이 파일은 봐주기」가 된다).

IN    src/firelane/**/*.py · sources.yaml(`coords:`)
OUT   없음
밖    **`tools/` 는 안 본다** · 점 자료(`csv_points` 의 `x_col`/`y_col`)는 아직 `coords:` 로 안 옮겨졌다(PLAN #193 후속) — 그 이름은 이 목록에 없다.
"""
from __future__ import annotations

import ast
from pathlib import Path

from firelane import ledger

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "firelane"


def declared_names(led: dict) -> set[str]:
    out: set[str] = set()
    for e in (led.get("datasets") or {}).values():
        for d in (ledger.coords_decl(e) or {}).values():
            if isinstance(d, dict) and {"x", "y"} <= set(d):
                out |= {str(d["x"]), str(d["y"])}
    return out


def literal_hits(root: Path, names: set[str]) -> list[str]:
    hits = []
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root.parent.parent).as_posix() if root.parent.parent in p.parents else str(p)
        if p.name == "ledger.py":
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in names:
                hits.append(f"{rel}:{n.lineno}  \"{n.value}\"")
            elif isinstance(n, ast.Attribute) and n.attr in names:
                hits.append(f"{rel}:{n.lineno}  .{n.attr}")
    return hits


def test_the_code_does_not_name_a_declared_coordinate_column():
    names = declared_names(ledger.load())
    assert len(names) >= 8, f"대장이 지목한 좌표 칸이 {len(names)}개뿐이다 — `coords:` 읽기를 의심하라: {sorted(names)}"
    hits = literal_hits(SRC, names)
    assert not hits, (
        "코드가 대장이 지목한 좌표 칸 이름을 직접 쓴다 — `ledger.coords(key, 역할)` 로 받는다(DECISIONS §634):\n  " + "\n  ".join(hits))


def test_the_probe_sees_strings_and_attributes_but_not_prose(tmp_path):
    """★ 양방향. 실물로만 재면 「언제나 초록」과 구별이 안 된다."""
    pkg = tmp_path / "src" / "firelane"
    pkg.mkdir(parents=True)
    (pkg / "a.py").write_text('"""LOT 는 docstring 이다."""\nx = r.LOT\ny = d["LAT"]\n# LOT\nz = "LOT 은 문장 안의 낱말"\n', encoding="utf-8")
    (pkg / "ledger.py").write_text('v = "LOT"\n', encoding="utf-8")
    got = literal_hits(pkg, {"LOT", "LAT"})
    assert len(got) == 2 and any(".LOT" in g for g in got) and any('"LAT"' in g for g in got), got


def test_the_declared_names_come_from_the_ledger_and_cover_the_incident():
    names = declared_names(ledger.load())
    assert {"LOT", "LAT", "DCLR_PSTN_LOT", "DCLR_PSTN_LAT"} <= names, "사고의 두 쌍이 지목에 없다"
    assert declared_names({"datasets": {"t": {"coords": {"none": "사유"}}}}) == set(), "좌표 없음 선언이 칸을 낸다"

