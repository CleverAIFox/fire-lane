#!/usr/bin/env python3
"""
test_generated_registry.py — 생성물 경로 목록이 한 곳에만 사는가. (PLAN §13 W3-13)

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22. 생성물 경로 목록이 아홉 곳에 따로 살았고, 「커밋된 web/data 가
최신인가」 단계가 그중 하나만 좁게 들어 `seg_uid_map.csv` 를 놓쳤다
(DECISIONS §192). 정본을 `src/firelane/generated.py` 한 곳에 **역할**과 함께
두었다. 이 시험은 세 가지를 든다.

  ① 호출부마다 자기 역할을 등록부에서 뽑는가 — 값이 같고, 손 목록이 없다
  ② 등록부의 경로가 실제로 있는가 · 역할이 비지 않았는가
  ③ 등록부 밖에서 생성물 루트를 둘 이상 든 목록 literal 을 새로 만들지 않는가

IN    src/firelane/generated.py · 호출부 여덟 · .pre-commit-config.yaml · sources.yaml
OUT   없음 (검사)
PARAM CALL_SITES
"""
from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

from firelane import generated as G

ROOT = Path(__file__).resolve().parents[1]

# 호출부 → 그 파일에서 등록부로 바꾼 이름과 역할.
CALL_SITES = {
    "tools/encoding_check.py": ("GENERATED", "encoding"),
    "tools/dms.py": ("GENERATED", "seal"),
    "tools/freshcheck.py": ("--paths", "fresh"),
    "tools/commit_policy.py": ("r_processed", "committed"),
    "tools/tidy.py": ("NEVER", "never-delete"),
    "tests/test_web_ownership.py": ("GENERATED_DIR", "web-out"),
    "tests/test_ledger_outputs.py": ("startswith", "ledger-skip"),
}


def _norm(s: str) -> str:
    return s.rstrip("/")


REG_PATHS = {g.path for g in G.REGISTRY}
ROOT_DIRS = {g.path for g in G.REGISTRY if g.kind == "dir"}


def _collection_strings(tree: ast.AST):
    """(줄, 목록 literal 속 문자열들) — tuple · list · set literal 마다."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            strs = [e.value for e in node.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if strs:
                yield node.lineno, strs


# ── ① 호출부 ────────────────────────────────────────────────────

def test_call_sites_import_the_registry():
    bad = [f for f in CALL_SITES
           if "from firelane.generated import" not in
           (ROOT / f).read_text(encoding="utf-8")]
    assert not bad, f"등록부를 안 부르는 호출부: {bad}"


def test_call_sites_hold_no_literal_generated_list():
    """호출부 파일의 목록 literal 에 등록부 경로가 손으로 들어 있지 않은가."""
    bad = []
    for f in CALL_SITES:
        tree = ast.parse((ROOT / f).read_text(encoding="utf-8"))
        for line, strs in _collection_strings(tree):
            hit = [s for s in strs if _norm(s) in REG_PATHS]
            if hit:
                bad.append(f"  {f}:{line} {hit}")
    assert not bad, ("생성물 경로를 손으로 든 목록이 남았다 — "
                     "firelane.generated.for_role/prefixes 로 뽑아라\n"
                     + "\n".join(bad))


def test_call_site_values_come_from_registry():
    """각 호출부의 실효값 = 그 역할의 등록부 값."""
    enc = importlib.import_module("encoding_check")
    assert enc.GENERATED == G.prefixes("encoding")

    dms = importlib.import_module("dms")
    assert dms.GENERATED == G.prefixes("seal")
    assert dms.SEAL_MAY_BE_DIRTY == G.prefixes("seal-dirty")

    cp = importlib.import_module("commit_policy")
    for p in G.for_role("committed"):
        assert not cp.r_processed(p), f"{p} 는 커밋 예외인데 commit_policy 가 막는다"
    assert cp.r_processed("data/processed/building.geojson")

    tidy = importlib.import_module("tidy")
    assert set(G.for_role("never-delete")) <= set(tidy.NEVER)
    extra = {n for n in tidy.NEVER if n in REG_PATHS} - set(G.for_role("never-delete"))
    assert not extra, f"tidy.NEVER 가 역할 밖 생성물을 든다: {extra}"

    wo = importlib.import_module("test_web_ownership")
    assert (wo.GENERATED_DIR,) == G.for_role("web-out")

    src = (ROOT / "tools/freshcheck.py").read_text(encoding="utf-8")
    assert 'default=list(for_role("fresh"))' in src, "freshcheck --paths 기본값이 등록부를 안 본다"
    led = (ROOT / "tests/test_ledger_outputs.py").read_text(encoding="utf-8")
    assert 'prefixes("ledger-skip")' in led, "test_ledger_outputs 가 등록부를 안 본다"


def test_precommit_exclude_matches_encoding_role():
    """`.pre-commit-config.yaml` 은 YAML 이라 import 를 못 한다 — 같은지를 든다."""
    s = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    body = s.split("exclude:", 1)[1].split("^(", 1)[1].split(")", 1)[0]
    got = {x for x in re.findall(r"^\s+([\w/.-]+/)\s*\|?\s*$", body, re.M)
           if "node_modules" not in x}
    assert got == set(G.prefixes("encoding")), (
        f".pre-commit exclude {sorted(got)} ↔ 등록부 encoding {sorted(G.prefixes('encoding'))}")


def test_committed_role_matches_layers_declaration():
    """`sources.yaml` layers.processed.committed_exceptions ↔ 역할 committed."""
    from firelane import layers  # 대장은 한 문으로 읽는다(test_lake 래칫)
    pol = layers.policy("processed")
    decl = {f"{pol['sub']}/{f}" for f in pol["committed_exceptions"]}
    assert decl == set(G.for_role("committed"))


# ── ② 등록부 자체 ───────────────────────────────────────────────

def test_registry_paths_exist():
    bad = []
    for g in G.REGISTRY:
        assert g.kind in ("dir", "file"), g
        assert not g.path.endswith("/") and not g.path.startswith("/"), g
        p = ROOT / g.path
        ok = p.is_dir() if g.kind == "dir" else p.is_file()
        if not ok and not any(c in g.path for c in "*?["):
            bad.append(f"  {g.path} ({g.kind})")
    assert not bad, "등록부 경로가 실물에 없다\n" + "\n".join(bad)


def test_roles_are_non_empty_and_known():
    expected = {"encoding", "seal", "seal-dirty", "fresh", "committed",
                "never-delete", "web-out", "ledger-skip"}
    assert G.ROLES == expected
    for r in G.ROLES:
        assert G.for_role(r), f"역할 {r} 가 비었다"
    for g in G.REGISTRY:
        assert g.roles, f"{g.path} 에 역할이 없다 — 어느 질문에도 안 쓰이면 지운다"
    try:
        G.for_role("없는역할")
    except KeyError:
        pass
    else:
        raise AssertionError("모르는 역할을 조용히 빈 값으로 돌려준다")


def test_cli_prints_role():
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert G.main(["--role", "fresh"]) == 0
    assert tuple(buf.getvalue().split()) == G.for_role("fresh")


# ── ③ 새 손 목록 금지 ──────────────────────────────────────────

# 루트를 둘 이상 들지만 「무엇이 생성물인가」를 묻지 않는 자리. (파일, 이름) → 사유.
ALLOW = {
    ("tools/doc_fsck.py", "REPO_DIRS"):
        "「저장소 안에 실물이 있는 디렉터리」— 생성물 여부가 아니라 존재 확인 범위다. "
        "web · src · docs 와 나란히 든다",
    ("tests/test_guards.py", "must"):
        "tidy.NEVER 의 **독립 핀**이다. 등록부에서 뽑으면 등록부에서 한 줄 빠질 때 "
        "안전장치도 같이 조용히 빠진다 — 일부러 손으로 든다",
}


def _bound_name(tree: ast.AST, node: ast.AST) -> str | None:
    for a in ast.walk(tree):
        if isinstance(a, ast.Assign) and a.value is node:
            t = a.targets[0]
            return t.id if isinstance(t, ast.Name) else None
    return None


def test_no_new_generated_root_list_outside_registry():
    """등록부 밖에서 생성물 루트 디렉터리를 **둘 이상** 든 목록 literal 이 없다.

    단일 파일 경로(`ROOT / "data/processed/segments.geojson"`)나 한 루트 속
    파일 목록은 목록의 복제가 아니라 사용이다. 루트 둘 이상을 나란히 드는 것이
    바로 W3-13 의 병 — 「무엇이 생성물인가」를 한 번 더 적는 것이다.
    """
    me = Path(__file__).resolve()
    bad = []
    for d in ("tools", "tests", "src"):
        for f in sorted((ROOT / d).rglob("*.py")):
            if f.resolve() in (me, (ROOT / "src/firelane/generated.py").resolve()):
                continue
            if "fixtures" in f.parts or "__pycache__" in f.parts:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            rel = f.relative_to(ROOT).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                    continue
                strs = [e.value for e in node.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                roots = {_norm(s) for s in strs} & ROOT_DIRS
                if len(roots) < 2:
                    continue
                if (rel, _bound_name(tree, node)) in ALLOW:
                    continue
                bad.append(f"  {rel}:{node.lineno} {sorted(roots)}")
    assert not bad, ("생성물 루트 목록을 손으로 들었다 — "
                     "src/firelane/generated.py 에 역할을 더하고 for_role 로 뽑아라\n"
                     + "\n".join(bad))
