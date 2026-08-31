#!/usr/bin/env python3
"""
test_ledger_outputs.py — data/processed 산출물이 대장에 등재됐는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-24. `segments._write_route()` 가 `route_vehicle.csv` 를 내는데
`sources.yaml` 의 `outputs` 어디에도 없었다. 그 건은 등재로 닫혔고,
같은 검사에 미등재 산출물 전량이 딸려 나왔다. 대장에 없으면
`produced_by` · `consumers` · `verified` · `known_issues` 가 전부 미상이고,
`datalog impact` 가 이 파일을 못 따라간다.

산출물이 늘어나는 것은 정상이다. **대장에 안 적히는 것이 사고다.**
`layers.processed.committed_exceptions` 가 git 추적을 잠근 것과 같은 축이다.

★ 파이프라인을 돌리지 않은 기계에서는 data/processed 가 비어 있다.
  그때는 반대 방향만 본다 — 대장이 가리키는 경로의 형식이 옳은가.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

# 산출물이 아닌 것. 파이프라인 메타데이터이며 대장의 대상이 아니다.
META = {
    "_manifest.json",       # 재현 증적. git_sha · 타이밍
    "_lineage.json",        # datalog 계보
    ".code_fingerprint",    # golden 재잠금 판단
    "segments.schema.json", # segments 의 스키마. 본체와 한 쌍이다
}

# 중간 산출물 접미사. 대장 대상이 아니다.
SKIP_SUFFIX = (".stale_", ".tmp", ".part")


def ledger() -> dict:
    d = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    return d.get("outputs") or {}


def declared_paths() -> dict[str, str]:
    """대장이 선언한 산출물 경로 → 키. 파생물은 '키/파생' 으로 표기한다.

    파생물(재투영본 등)은 본체 항목의 `derives` 아래 둔다. 개별 등재하면
    레이어 하나 늘 때마다 대장이 두 줄씩 불어난다. 다만 `what` 은 파생물도
    쓴다 — 안 그러면 derives 가 검사 우회 구멍이 된다.
    """
    out = {}
    for k, v in ledger().items():
        v = v or {}
        p = v.get("path")
        assert p, f"outputs.{k} 에 path 가 없다 — 경로 없는 산출물 선언은 무의미하다"
        out[p] = k
        for d in v.get("derives") or []:
            d = d or {}
            dp = d.get("path")
            assert dp, f"outputs.{k}.derives 에 path 가 없다"
            assert d.get("what"), (
                f"outputs.{k}.derives[{dp}] 에 what 이 없다 — "
                "파생물도 왜 존재하는지는 적어야 한다")
            out[dp] = f"{k}/파생"
    return out


def actual_files() -> list[Path]:
    if not PROCESSED.is_dir():
        return []
    out = []
    for p in sorted(PROCESSED.rglob("*")):
        if not p.is_file():
            continue
        if p.name in META or any(s in p.name for s in SKIP_SUFFIX):
            continue
        out.append(p)
    return out


def _gitignored(rel: str) -> bool:
    """git 이 무시하는 경로인가.

    ★ gpkg 등 대용량 중간 산출물은 `.gitignore` 로 빠진다. clone 직후나
      CI 에서는 없는 것이 정상이므로 "안 나왔다" 로 볼 수 없다.
    """
    import subprocess
    return subprocess.run(["git", "check-ignore", "-q", rel],
                          cwd=ROOT, capture_output=True).returncode == 0


def test_every_output_declares_a_path():
    """대장의 모든 산출물이 path 를 갖는다."""
    d = declared_paths()
    assert d, "sources.yaml 에 outputs 가 비어 있다"


def repo_layer_prefixes() -> list[str]:
    """base:repo 인 계층의 상대경로 접두사.

    산출물이 processed 에만 떨어지는 것은 아니다 — `field_sample` 은
    `data/field/` 로 간다(사람이 들고 나갈 야장). 계층 선언이 정본이므로
    여기서 목록을 박지 않고 읽어온다.
    """
    d = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    return [v["sub"].rstrip("/") + "/"
            for v in (d.get("layers") or {}).values()
            if v.get("base") == "repo"]


def test_declared_paths_point_into_a_declared_layer():
    """선언 경로가 어떤 계층 안을 가리킨다.

    ★ 계층 밖 산출물은 fsck 의 계층 검사를 통째로 우회한다.
      2026-08-24 의 SSD 루트 오염이 정확히 그 형태였다.
    """
    pre = repo_layer_prefixes()
    bad = [p for p in declared_paths() if not any(p.startswith(x) for x in pre)]
    assert not bad, (
        "outputs 의 경로가 선언된 계층 밖이다: " + ", ".join(bad) +
        f"\n  base:repo 계층: {pre}"
        "\n  계층 밖 산출물은 fsck 가 못 본다. 계층을 늘리거나 경로를 고쳐라")


@pytest.mark.skipif(not PROCESSED.is_dir() or not actual_files(),
                    reason="파이프라인 미실행 — data/processed 가 비었다")
# ★ 2026-08-31. `strict=False` 였다. 고쳐져도 조용히 초록이라 표시를
#   떼야 하는 순간을 아무도 모른다 — "안 된다" 로 적어두고 잊는 장치다.
#   `strict=True` 면 전건 등재되는 순간 xpass 로 빨간불이 뜬다.
#   실측 54건(종전 문서는 "20여건" 이었다. 두 배 넘게 틀렸다).
@pytest.mark.xfail(reason="대장 outputs 미등재 54건. PLAN §1 #41",
                   strict=True)
def test_no_undeclared_output():
    """processed 에 있는데 대장에 없는 파일이 없다.

    route_vehicle.csv 한 건에서 출발해 미등재 산출물 전수를 잡는다.
    """
    known = set(declared_paths())
    orphan = [str(p.relative_to(ROOT)) for p in actual_files()
              if str(p.relative_to(ROOT)) not in known]
    assert not orphan, (
        "대장에 없는 산출물:\n  " + "\n  ".join(orphan) +
        "\n\n  sources.yaml 의 outputs 에 등재하라. 최소 항목:\n"
        "    produced_by · path · inputs · consumers · what · verified\n"
        "  대장에 없으면 datalog impact 가 이 파일을 못 따라가고,\n"
        "  검증 상태와 known_issues 가 아무 데도 안 적힌다.\n"
        "  META 에 넣는 것은 파이프라인 메타데이터일 때만이다.")


@pytest.mark.skipif(not PROCESSED.is_dir() or not actual_files(),
                    reason="파이프라인 미실행 — data/processed 가 비었다")
def test_declared_output_exists_after_run():
    """대장이 선언한 산출물이 실제로 나온다.

    ★ 한 번이라도 돌린 기계에서만 본다. 선언만 있고 안 나오는 산출물은
      소비자가 있으면 조용히 깨진다.
    """
    missing = [f"{k}  ({p})" for p, k in declared_paths().items()
               if not (ROOT / p).exists() and not _gitignored(p)]
    assert not missing, (
        "대장에 있는데 산출되지 않은 것:\n  " + "\n  ".join(missing) +
        "\n  파이프라인이 이 산출물을 더 이상 내지 않으면 대장에서 내려라")


def test_consumers_exist():
    """consumers 에 적힌 파일이 실제로 있다.

    소비자가 사라졌는데 대장에 남으면 impact 분석이 거짓말을 한다.
    """
    dead = []
    for k, v in ledger().items():
        for c in (v or {}).get("consumers") or []:
            if not (ROOT / c).exists():
                dead.append(f"outputs.{k}.consumers → {c}")
    assert not dead, (
        "존재하지 않는 소비자:\n  " + "\n  ".join(dead) +
        "\n  파일을 개명·삭제했으면 대장도 같이 고친다")


def test_no_todo_in_ledger():
    """대장에 TODO 가 남아 있지 않다.

    뼈대 생성이 what/verified 를 TODO 로 깐다. 그 상태로 머지되면 대장이
    있으나 마나다. 채우지 않으면 여기서 막힌다.
    """
    stale = []
    for k, v in ledger().items():
        v = v or {}
        for f in ("what", "verified"):
            if "TODO" in str(v.get(f, "")):
                stale.append(f"outputs.{k}.{f}")
        for d in v.get("derives") or []:
            d = d or {}
            if "TODO" in str(d.get("what", "")):
                stale.append(f"outputs.{k}.derives[{d.get('path')}].what")
    assert not stale, (
        "TODO 가 남은 대장 항목:\n  " + "\n  ".join(stale) +
        "\n\n  뼈대만 깔고 내용을 안 적으면 대장의 의미가 없다.")
