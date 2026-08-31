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

    # ── ingest 산출물은 매니페스트가 정본이다 ────────────────
    # ★ 2026-08-31. 종전에는 `outputs` 만 봤고 그래서 `bin_cloth.geojson`
    #   같은 **대장 키와 1:1 인 42건**이 전부 "미등재" 로 떴다. 그것을
    #   `outputs` 에 적으면 한 산출물이 두 대장에 산다 — R14 위반이고
    #   키 하나 늘 때마다 또 어긋난다.
    #
    #   `ingest` 는 키마다 `_manifest.json` 의 `datasets[].outputs` 에
    #   무엇을 냈는지 기록한다(`ingest.py:382`). R13 이 "계보는
    #   매니페스트 목록과 디스크를 대조한다" 고 적는 그 자리다.
    #   ★ `datasets` 는 **list** 다. 원소 키 — key · found · sha256 ·
    #     outputs · layers. dict 로 읽으면 AttributeError 로 죽는다.
    mf = ROOT / "data/processed/_manifest.json"
    if mf.exists():
        import json
        rows = json.loads(mf.read_text(encoding="utf-8")).get("datasets") or []
        if isinstance(rows, dict):
            rows = list(rows.values())
        for rec in rows:
            for f in (rec or {}).get("outputs") or []:
                out[f"data/processed/{f}"] = f"{(rec or {}).get('key')}/ingest"

    # ★ 단계 산출물도 매니페스트가 든다. `terrain.raster` 가 그 예다.
    #   최상위 키에 흩어져 있어 `datasets` 순회로는 안 잡힌다.
    if mf.exists():
        for k, rec in json.loads(mf.read_text(encoding="utf-8")).items():
            if not isinstance(rec, dict):
                continue
            for v in rec.values():
                if isinstance(v, str) and v.endswith((".tif", ".gpkg", ".geojson",
                                                      ".csv", ".json")):
                    out[f"data/processed/{v}"] = f"{k}/단계"
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


# ── 조회는 상태를 바꾸지 않는다 (R22) ───────────────────────────
# ★ 2026-08-31. `ingest --check` 가 `_manifest.json` 을 덮어썼다. `--check`
#   레코드는 `key·found·sha256` 셋뿐이라 **계보 27건이 0건이 됐고**, 그
#   커밋에 `rewrite (95%)` 가 찍혔는데 `golden` 은 L1·L2·L3 전부 OK 를 냈다.
#   `segments.geojson` 하나만 읽으니 입력 계보가 죽은 것을 모른다.
#   복구에 전량 재실행 317초.
#
#   이 파일이 같은 병을 세 번 겪었다 — `--only` 가 대장을 통째로 덮은 것
#   (08-22), 최상위 키를 날린 것(08-25), 그리고 이번. 전부 **조회·부분
#   실행이 전체 상태를 파괴**한 형태다. 네 번째를 여기서 막는다.
def test_check_does_not_write():
    """`--check` 후 매니페스트 내용이 그대로인가."""
    import hashlib
    import os
    import subprocess
    import sys

    man = ROOT / "data/processed/_manifest.json"
    if not man.exists():
        pytest.skip("파이프라인 미실행")
    before = hashlib.sha256(man.read_bytes()).hexdigest()
    r = subprocess.run([sys.executable, "-m", "firelane.ingest", "--check"],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    after = hashlib.sha256(man.read_bytes()).hexdigest()
    assert before == after, (
        "`ingest --check` 가 _manifest.json 을 바꿨다.\n"
        "  조회는 읽기만 한다. 쓰기 경로 앞에서 return 하는지 보라 —\n"
        "  src/firelane/ingest.py 의 `if a.check:` 분기.\n"
        f"  종료코드 {r.returncode}")


def test_manifest_keeps_lineage():
    """매니페스트가 계보를 들고 있는가.

    ★ 위 검사는 `--check` 한 경로만 본다. 이것은 **결과 자체**를 본다.
      어떤 경로로든 계보가 날아가면 여기가 운다. `outputs` 가 없으면
      `datalog impact` 가 산출물을 못 따라가고 R13 이 성립하지 않는다.
    """
    man = ROOT / "data/processed/_manifest.json"
    if not man.exists():
        pytest.skip("파이프라인 미실행")
    import json
    d = json.loads(man.read_text(encoding="utf-8")).get("datasets") or []
    rows = d if isinstance(d, list) else list(d.values())
    has = sum(1 for r in rows if (r or {}).get("outputs"))
    assert has, (
        f"매니페스트 {len(rows)}종 중 `outputs` 를 든 것이 0건이다.\n"
        "  얕은 판이 계보를 덮었다. `uv run fire-lane` 으로 전량 재실행하면\n"
        "  복구된다(약 300초). golden 은 이 상태를 초록불로 통과시킨다.")
