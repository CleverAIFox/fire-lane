#!/usr/bin/env python3
"""
test_generated_families.py — 커밋된 생성물마다 (만드는 것 · 재현 확인 · 읽는 것) 이 있는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22 (DECISIONS §218-6 · 계급 가드 5). 생성물 등록부(`firelane.generated`)는
「어느 검사가 이 경로를 빼는가」(역할)만 들었다. 누가 만들고 무엇이 재현을 확인하는지는
머리말과 verify.sh 주석에 흩어져 있었고, 셋 중 하나가 빠진 생성물은 낡아도 아무도
모른다 — `web/workflow.html` · `docs/figures` 가 각각 그 모양으로 한 번씩 낡았다.

  ① 가족마다 generator · check 도구가 실재하고, check 인자(`--check` · 부속명령)가
     그 도구 소스에 실제로 있다 · consumer 가 실재한다
  ② `GEN_ROOTS` 아래 **추적 파일은 전부 정확히 한 가족**에 든다
  ③ 가족 패턴마다 추적 파일이 하나 이상 걸린다(빈 그물 금지)

IN    src/firelane/generated.py · git ls-files
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import importlib.util
import re
import shlex
import subprocess
from pathlib import Path

import pytest

from firelane import generated as G

ROOT = Path(__file__).resolve().parents[1]


def _tracked() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "--", *G.GEN_ROOTS], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git 저장소가 아니다")
    # 작업나무에서 지운 파일(미커밋 삭제)은 뺀다
    return [p for p in out.splitlines() if (ROOT / p).exists()]


def _code_file(ref: str) -> Path | None:
    if ref.startswith("firelane."):
        spec = importlib.util.find_spec(ref)
        return Path(spec.origin) if spec and spec.origin else None
    p = ROOT / ref
    return p if p.is_file() else None


@pytest.mark.parametrize("fam", G.FAMILIES, ids=lambda f: f.name)
def test_family_points_at_real_code(fam: G.Family):
    bad = []
    if _code_file(fam.generator) is None:
        bad.append(f"generator {fam.generator!r} 가 없다")
    assert fam.checks, "재현 확인 명령이 없다 — 낡아도 아무도 모른다"
    for cmd in fam.checks:
        tok = shlex.split(cmd)
        assert tok[:3] == ["uv", "run", "python"], cmd
        tool = _code_file(tok[3])
        if tool is None:
            bad.append(f"check {cmd!r} 의 도구가 없다")
            continue
        src = tool.read_text(encoding="utf-8")
        # 얇은 래퍼(`from firelane.webmanifest import main`)는 본체까지 읽는다
        for mod in re.findall(r"^from (firelane\.\w+) import main\b", src, re.M):
            body = _code_file(mod)
            src += body.read_text(encoding="utf-8") if body else ""
        bad += [f"check {cmd!r} 의 인자 {a!r} 가 {tok[3]} 에 없다"
                for a in tok[4:] if f'"{a}"' not in src and f"'{a}'" not in src]
    assert fam.consumers, "읽는 것이 없다 — 아무도 안 읽는 생성물은 지운다"
    bad += [f"consumer {c!r} 가 없다" for c in fam.consumers if not (ROOT / c).exists()]
    assert not bad, f"가족 {fam.name}:\n  " + "\n  ".join(bad)


def test_every_tracked_generated_file_has_exactly_one_family():
    tracked = _tracked()
    assert len(tracked) > 100, f"추적 생성물이 {len(tracked)}개뿐이다 — 루트가 옮겨졌나"
    orphan, double = [], []
    for p in tracked:
        fams = G.families_of(p)
        if not fams:
            orphan.append(p)
        elif len(fams) > 1:
            double.append(f"{p} ← {[f.name for f in fams]}")
    assert not orphan, ("가족이 없는 추적 생성물 — generated.FAMILIES 에 "
                        "(generator, check, consumer) 와 함께 더하라:\n  "
                        + "\n  ".join(orphan[:20]))
    assert not double, "두 가족에 걸린 생성물:\n  " + "\n  ".join(double[:20])


def test_every_family_glob_catches_something():
    tracked = _tracked()
    empty = [f"{f.name}: {g}" for f in G.FAMILIES for g in f.globs
             if not any(G._glob_re(g).match(p) for p in tracked)]
    assert not empty, "아무 추적 파일도 안 걸리는 패턴(빈 그물):\n  " + "\n  ".join(empty)


def test_glob_star_does_not_cross_slash():
    assert G.families_of("web/data/fleet.json")[0].name == "web-data"
    assert G.families_of("web/data/ortho/19/1/2.jpg")[0].name == "web-ortho"
    assert G.families_of("docs/figures/.lock.json")[0].name == "figures"
    assert not G.families_of("web/navi/src/app/App.tsx")
