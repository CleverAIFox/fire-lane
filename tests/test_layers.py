#!/usr/bin/env python3
"""
test_layers.py — MASTER §18-1 계층 선언과 코드를 대조한다.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-24. §18-1 이 계층을 선언하는데 `interim` 은 `paths.py` 에 **선언
조차 없었다.** 그래서 탐색 도구가 갈 곳이 없어 프로젝트 루트에 떨궜다.

    jijeok_probe._side()  →  RAW.parent.parent   (프로젝트 루트)
    결과: jijeok_scope.gpkg 10.5MB · jijeok_width.gpkg · jijeok_join.gpkg
          check27.csv · check27.html · check42.csv

**계층이 없으면 파일은 아무 데나 떨어진다.** 규율이 아니라 구조의 문제다.
문서가 "여섯 계층" 이라고 적어놓고 코드가 넷만 알면, 나머지 둘을 쓰려던
도구는 매번 자기 자리를 발명한다.

IN    src/firelane/paths.py · docs/MASTER.md · tools/*.py
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

from firelane import paths

ROOT = Path(__file__).resolve().parent.parent

# MASTER §18-1 이 선언하는 계층. 여기와 문서가 어긋나면 한쪽이 낡은 것이다.
# ★ 2026-08-26. 손으로 적던 목록을 `layers.BIND` 에서 유도한다.
#   `golden` · `baseline` 을 등재했을 때 이 목록만 낡아 실패했다 —
#   계층이 늘 때마다 여기를 고쳐야 하는 구조 자체가 드리프트 원인이다.
from firelane import layers as _layers  # noqa: E402

DECLARED = sorted(_layers.BIND.values())


def test_every_declared_layer_exists_in_paths():
    missing = [n for n in DECLARED if not hasattr(paths, n)]
    assert not missing, (
        "MASTER §18-1 이 선언한 계층이 paths.py 에 없다: "
        + ", ".join(missing)
        + "\n  선언만 있고 코드가 모르면, 그 계층을 쓰려던 도구는\n"
        "  매번 자기 자리를 발명한다(2026-08-24 SSD 루트 오염).")


def test_master_layer_table_matches_paths():
    """문서 표의 계층 이름이 paths.py 에 전부 있는가."""
    txt = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    sec = txt.split("## 18-1. 계층", 1)
    if len(sec) < 2:
        return
    body = sec[1].split("## 18-2", 1)[0]
    named = set(re.findall(r"^\| `(\w+)` \|", body, re.M))
    known = {n.lower() for n in DECLARED}
    unknown = sorted(n for n in named if n.lower() not in known)
    assert not unknown, (
        f"문서 §18-1 이 적은 계층을 paths.py 가 모른다: {unknown}\n"
        "  둘 중 하나가 낡았다. 코드가 정본이고 문서를 고친다(§17).")


def test_no_tool_writes_outside_declared_layers():
    """★ 저장소 밖 임의 위치에 쓰지 않는다.

    `RAW.parent` · `RAW.parent.parent` 는 계층이 아니다. 거기 쓰면 대장에도
    gitignore 에도 안 잡히고 백업 대상도 아니다 — 사실상 소실 대기다.

    ★ 2026-08-24. 처음에 정규식으로 잡았더니 **사유를 적은 주석·독스트링이
      자기 검사에 걸렸다.** 줄 시작 문자로 거르는 회피도 이어지는 줄을
      놓친다. `test_sys_path_해킹이_없다` 가 겪은 함정과 같다.

      휴리스틱을 버리고 `ast` 로 **실제 속성 접근만** 본다. 주석과
      문자열은 파서가 애초에 안 준다. 검사는 자기가 검사하는 대상과 같은
      눈으로 보면 안 된다.
    """
    import ast as _ast

    class Visit(_ast.NodeVisitor):
        def __init__(self):
            self.hits = []

        def visit_Attribute(self, node):
            # RAW.parent · RAW.parent.parent 를 잡는다
            if node.attr == "parent":
                base = node.value
                while isinstance(base, _ast.Attribute) and base.attr == "parent":
                    base = base.value
                if isinstance(base, _ast.Name) and base.id == "RAW":
                    self.hits.append(node.lineno)
            self.generic_visit(node)

    bad = []
    for f in sorted((ROOT / "tools").rglob("*.py")) + \
             sorted((ROOT / "src").rglob("*.py")):
        try:
            tree = _ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        v = Visit()
        v.visit(tree)
        for ln in v.hits:
            bad.append(f"{f.relative_to(ROOT)}:{ln}")
    assert not bad, (
        "계층 밖(raw 상위)을 작업 위치로 쓴다:\n  " + "\n  ".join(bad)
        + "\n  paths.INTERIM 을 써라. 2026-08-24 에 이것으로 SSD 루트가"
        " 오염됐다.")


def test_interim_is_not_committed():
    """interim 은 재생성 가능하다. 저장소에 들어오면 안 된다(R2)."""
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\s*/?data/interim/?", gi, re.M), \
        ".gitignore 에 data/interim 이 없다. 재생성 가능한 것은 커밋하지 않는다."


# ── 선언 ↔ 코드 ↔ 문서 3자 대조 (2026-08-24) ──────────────────
# ★ `datalog fsck` 는 사람이 돌리는 도구다. 안 돌리면 안 돈다 — 이 저장소가
#   오늘 하루 동안 그것을 세 번 증명했다(.githooks 미설정 · acquire 미실행 ·
#   CI 손목록). **기계와 무관한 부분은 테스트가 본다.**
#
#   기계에 의존하는 것(디렉터리 존재 · 백업 시각 · 환경변수)은 fsck 소관이고,
#   여기서는 선언 자체의 정합만 본다. CI 에는 SSD 가 없다.

def _L():
    from firelane import layers
    return layers


def test_declaration_and_bind_cover_the_same_layers():
    L = _L()
    declared, bound = set(L.names()), set(L.BIND)
    assert declared == bound, (
        f"선언에만 있음: {sorted(declared - bound)}\n"
        f"BIND 에만 있음: {sorted(bound - declared)}\n"
        "  둘이 어긋나면 그 계층을 쓰려던 도구는 자기 자리를 발명한다.")


def test_every_layer_resolves_to_a_path():
    L = _L()
    for n in L.names():
        L.path(n)          # LayerError 가 나면 실패다


def test_declared_base_matches_resolved_path():
    """base: repo 인데 SSD 를 가리키면 clone 만으로 안 보인다.

    2026-08-23 에 `paths.FIELD` 가 정확히 그 상태였다 — `(DATA / "field")` 라
    FIRE_LANE_DATA 가 설정된 기계에서 야장이 SSD 로 이사했을 것이다.
    """
    L = _L()
    bad = []
    for n in L.names():
        try:
            L.path(n).relative_to(L.expected_base(n))
        except ValueError:
            bad.append(f"  {n}: base={L.declared_base(n)} 인데 "
                       f"{L.expected_base(n)} 아래가 아니다 — {L.path(n)}")
    assert not bad, "선언한 base 와 실제 경로가 다르다\n" + "\n".join(bad)


def test_regenerable_false_layers_are_kept_somehow():
    """재생성 불가인데 커밋도 백업도 아니면 소실 대기다(R2).

    `landing` 만 예외다 — 공공데이터포털에서 다시 받는다.
    """
    L = _L()
    ALLOW = {"landing"}
    bad = [n for n in L.names()
           if not L.policy(n)["regenerable"]
           and not L.policy(n)["committed"]
           and not L.policy(n)["backup"]
           and n not in ALLOW]
    assert not bad, (
        f"재생성 불가인데 커밋도 백업도 아니다: {bad}\n"
        "  ignore 목록에 넣기 전에 재생성되는지 먼저 확인한다(R2).")


def test_committed_exceptions_match_gitignore_negations():
    """선언의 예외 ↔ `.gitignore` 의 `!` 줄.

    2026-08-24. `processed` 는 폴더를 ignore 하고 넷만 `!` 로 연다.
    fsck 가 폴더만 보고 어긋났다고 했는데 실제로는 코드가 옳았다.
    선언에 예외를 적어 셋(선언 · gitignore · git ls-files)을 맞춘다.
    """
    L = _L()
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    neg = {Path(l.strip()[1:]).name
           for l in gi.splitlines() if l.strip().startswith("!")}
    bad = []
    for n in L.names():
        for f in (L.policy(n).get("committed_exceptions") or []):
            if f not in neg:
                bad.append(f"  {n}: 선언은 {f} 를 예외로 두는데 "
                           ".gitignore 에 `!` 가 없다")
    assert not bad, "선언과 .gitignore 가 어긋난다\n" + "\n".join(bad)


def test_unimplemented_layers_declare_it():
    """`norm` 처럼 아직 없는 계층은 status 로 밝힌다.

    미구현을 현황처럼 적으면 다음 사람이 있는 줄 알고 쓴다.
    격차는 산문이 아니라 데이터여야 한다.
    """
    L = _L()
    assert not L.implemented("norm"), \
        "norm 이 구현됐으면 status 를 지우고 migrated 를 채워라"
    assert L.policy("norm").get("migrated") == [], \
        "norm.migrated 는 이관한 dataset_key 목록이다. 하나씩 + golden check"
