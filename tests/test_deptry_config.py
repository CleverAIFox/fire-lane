"""deptry 설정 — 알려진 예외가 **살아 있는가**, 판이 한 가지인가 (4족 클래스 가드).

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-22 (DECISIONS §218-5). `verify.sh` 「의존성 선언↔import (deptry)」와 contract.yml 이
  deptry 를 돈다. deptry 는 **새 결함**은 잡지만 **죽은 면제**는 말하지 않는다 — 면제해 둔
  `fastapi` 를 누가 import 하기 시작해도 면제는 그대로 남아 사각지대가 된다. 래칫이 한 방향만
  조이는 것이다. 이 파일이 반대 방향을 든다:

    · 면제된 패키지를 src · tools 가 import 하면 실패 — 「면제를 지워라」
    · 면제가 pyproject 에 선언되지 않은 패키지를 들면 실패 — 유령 면제
    · verify.sh 와 contract.yml 의 deptry 판이 다르면 실패 — 같은 검사기를 다른 판으로 돈다

★ deptry 를 여기서 **돌리지 않는다.** 시험은 오프라인에서도 돌아야 하고, 판정 자체는 verify ·
  CI 가 든다. 여기서 보는 것은 설정의 정합이다. import 이름표는 pyproject 의
  `package_module_name_map` 을 그대로 쓴다 — 표를 여기 다시 적으면 집이 둘이 된다.
"""
from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
DEPTRY = PYPROJECT["tool"]["deptry"]
CALL = re.compile(r"uv run --no-sync --with deptry==(\d+\.\d+\.\d+) deptry src tools")


def _dist(req: str) -> str:
    return re.match(r"[A-Za-z0-9._-]+", req).group(0)


def _declared() -> set[str]:
    proj = PYPROJECT["project"]
    out = {_dist(d) for d in proj["dependencies"]}
    for reqs in proj.get("optional-dependencies", {}).values():
        out |= {_dist(d) for d in reqs}
    return out


def _modules(dist: str) -> set[str]:
    m = DEPTRY.get("package_module_name_map", {}).get(dist)
    if m is None:
        return {dist.lower().replace("-", "_")}
    return {m} if isinstance(m, str) else set(m)


def _imported_tops() -> dict[str, str]:
    """src · tools 가 import 하는 최상위 모듈 → 처음 본 자리."""
    out: dict[str, str] = {}
    for d in ("src", "tools"):
        for f in sorted((ROOT / d).rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    mods = [a.name for a in n.names]
                elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                    mods = [n.module]
                else:
                    continue
                for mod in mods:
                    out.setdefault(mod.split(".")[0], f"{f.relative_to(ROOT)}:{n.lineno}")
    return out


def test_import_scanner_is_not_an_empty_net() -> None:
    """★ 빈 그물인가. 스캐너가 죽으면 아래 「죽은 면제」가 조용히 통과한다."""
    tops = _imported_tops()
    for need in ("shapely", "geopandas", "yaml"):
        assert need in tops, f"src·tools 가 {need} 를 import 하는데 못 잡았다 — 스캐너가 죽었다"


def test_known_exceptions_are_still_unused() -> None:
    """면제된 패키지를 **아직 아무도 import 안 하는가.** 하기 시작했으면 면제를 지운다."""
    tops = _imported_tops()
    dead = []
    for dist in DEPTRY["per_rule_ignores"]["DEP002"]:
        hit = sorted(mod for mod in _modules(dist) if mod in tops)
        if hit:
            dead.append(f"  {dist} — {hit[0]} 를 {tops[hit[0]]} 가 import 한다")
    assert not dead, (
        "쓰이게 된 패키지가 DEP002 면제에 남아 있다.\n" + "\n".join(dead)
        + "\n\n  pyproject.toml `[tool.deptry.per_rule_ignores] DEP002` 에서 지워라.\n"
          "  면제는 사각지대다 — 남겨 두면 그 패키지를 다시 안 쓰게 돼도 아무도 안 운다.")


def test_known_exceptions_name_declared_packages() -> None:
    """면제가 **선언된 패키지**를 드는가. 선언을 지웠으면 면제도 지운다."""
    declared = {d.lower() for d in _declared()}
    ghost = sorted(d for d in DEPTRY["per_rule_ignores"]["DEP002"] if d.lower() not in declared)
    assert not ghost, f"pyproject 에 선언되지 않은 패키지를 면제한다 — {ghost}"


def test_known_exceptions_do_not_grow() -> None:
    """면제는 **래칫**이다 — 2026-09-22 실측 여덟에서 늘지 않는다.

    ★ 늘려야 하면 이 수를 올리고 **왜 import 없이 선언하는지** 커밋에 적는다.
      줄면 이 수도 내린다(양방향). 수의 집은 여기 하나다.
    """
    n = len(DEPTRY["per_rule_ignores"]["DEP002"])
    assert n == 8, (f"DEP002 면제가 {n}개다 — 기록 8. 늘었으면 사유를, 줄었으면 이 수를 내려라"
                    " (느슨해진 래칫은 초록으로 위장한다)")


def test_deptry_is_pinned_identically_in_verify_and_ci() -> None:
    """verify.sh 와 contract.yml 이 **같은 판 · 같은 대상**으로 deptry 를 부르는가."""
    got = {}
    for rel in ("tools/verify.sh", ".github/workflows/contract.yml"):
        body = "\n".join(line.split("#", 1)[0]
                         for line in (ROOT / rel).read_text(encoding="utf-8").splitlines())
        found = CALL.findall(body)
        assert len(found) == 1, (f"{rel} 에서 `uv run --no-sync --with deptry==X.Y.Z deptry src tools`"
                                 f" 호출을 {len(found)}개 찾았다 — 정확히 하나여야 한다")
        got[rel] = found[0]
    assert len(set(got.values())) == 1, f"deptry 판이 갈린다 — {got}"
