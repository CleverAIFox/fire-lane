"""`FIRE_LANE_PROCESSED` — 격리 재취입이 메인 `data/processed` 를 못 건드린다.  (PLAN #183 · 2026-11-09)

★ 예전 레시피(코드를 격리 트리로 통째 복사 · DECISIONS §603 · §620)를 환경변수 하나로 바꿨다. 그 시험은 `tests/test_shardseal.py` 에 있었고 이 자리로 옮겼다
  (그 파일이 길이 상한 700 에 붙어 있다).

밖    **다른 모듈이 따로 든 `ROOT / "data" / "processed"`**(`publish_*` · `datalog` · `expectation` 등)는 안 본다 — `ingest` 폐포가 읽는 `paths.PROCESSED` 한 곳만 본다.
      레이크(`FIRE_LANE_DATA`)가 없으면 격리 재취입 시험은 건너뛴다.
"""
from __future__ import annotations


def test_isolated_reingest_with_the_processed_env_keeps_ingest_out_of_the_main_processed_dir(tmp_path):
    """`FIRE_LANE_PROCESSED` + 스크래치 `FIRE_LANE_DATA` 로 돌린 `ingest --only` 가 **메인 `data/processed` 를 안 건드린다.**

    ★ 2026-11-03 에 `paths.PROCESSED = ROOT/data/processed` 가 고정이라 worktree 에서 돌린 ingest 가 **메인에 썼다**(추적 파일 `_manifest.json` 까지).
      예전 레시피(DECISIONS §603 · §620)는 코드를 격리 트리로 **통째로 복사**해야 했다. 이제 코드는 그대로 두고 환경변수 하나로 돌린다 — 자식 프로세스가 따라온다.
      ① 자식이 보는 `PROCESSED` 가 스크래치인지 **먼저 단언**하고(아니면 돌지 않는다) ② 메인의 파일 해시가 전후로 같은지 문다.
    밖  레이크(`FIRE_LANE_DATA`)가 없으면 건너뛴다 — 읽을 원본이 없다.
    """
    import hashlib
    import os
    import subprocess
    import sys
    from pathlib import Path

    import pytest

    root = Path(__file__).resolve().parents[1]
    lake = os.environ.get("FIRE_LANE_DATA")
    if not lake or not (Path(lake) / "raw").is_dir():
        pytest.skip("환경skip(레이크) — 격리 재취입에 읽을 원본이 없다")
    key = "civil_office"                       # 작고 빨리 끝나는 소스(64행)
    if not list((Path(lake) / "raw").glob("*/*civil*office*")):
        pytest.skip(f"환경skip(레이크) — {key} 원본이 레이크에 없다")

    scratch = tmp_path / "scratch"
    for d in ("raw", "norm", "interim", "landing", "retired"):
        (scratch / d).mkdir(parents=True)
    for layer in ("raw", "norm"):
        for p in (Path(lake) / layer).iterdir():
            (scratch / layer / p.name).symlink_to(p)
    out = tmp_path / "processed"
    out.mkdir()
    for f in ("_manifest.json", "_lineage.json"):   # 캐시(`.rawprint.json`)는 안 심는다 — 격리 산출 자리에 **새로** 생기는지가 증거다
        if (root / "data" / "processed" / f).is_file():
            (out / f).write_bytes((root / "data" / "processed" / f).read_bytes())

    env = {k: v for k, v in os.environ.items() if k != "FIRE_LANE_RAW"}      # 폐기 변수는 데이터 경로를 덮는다
    env.update(FIRE_LANE_DATA=str(scratch), FIRE_LANE_PROCESSED=str(out))

    # ① 먼저 단언 — 자식이 보는 산출 경로가 스크래치여야 한다. 아니면 **돌지 않는다**(메인을 덮기 전에 멈춘다).
    probe = subprocess.run([sys.executable, "-c", "from firelane import paths; print(paths.PROCESSED)"],
                           cwd=root, env=env, capture_output=True, text=True, check=True, timeout=60).stdout.split()
    assert Path(probe[0]) == out, f"격리가 안 됐다 — PROCESSED {probe[0]}. 이대로 돌리면 **메인에 쓴다.**"

    def tree_hash(d: Path) -> dict[str, str]:
        # `.rawprint.json` 은 추적 밖 캐시라 같은 시각에 도는 **다른 시험**(병렬 묶음)이 메인의 것을 고친다 — 전후 비교에서 뺀다.
        # 대신 격리 쪽에 그 캐시가 **새로** 생겼는지를 아래에서 따로 본다(캐시가 메인으로 샜다면 거기 안 생긴다).
        return {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(d.rglob("*")) if p.is_file() and p.name != ".rawprint.json"}

    before = tree_hash(root / "data" / "processed")
    r = subprocess.run([sys.executable, "-m", "firelane.ingest", "--only", key],
                       cwd=root, env=env, capture_output=True, text=True, check=False, timeout=300)
    assert r.returncode == 0, f"격리 ingest 가 죽었다:\n{r.stdout[-400:]}\n{r.stderr[-400:]}"
    assert (out / f"{key}.geojson").is_file(), "격리 산출 자리에 산출이 안 생겼다 — 어디에 썼나"
    assert (out / ".rawprint.json").is_file(), "격리 산출 자리에 캐시(`.rawprint.json`)가 안 생겼다 — 캐시가 메인으로 샜다"
    assert tree_hash(root / "data" / "processed") == before, "**메인 `data/processed` 가 바뀌었다** — 격리가 샜다"


def test_the_processed_env_is_optional_and_defaults_to_the_repository_value():
    """환경변수가 없으면 지금 값 그대로다(PLAN #183 · 도착 조건). 있으면 그리로 간다."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    base = {k: v for k, v in os.environ.items() if k != "FIRE_LANE_PROCESSED"}
    def run(e: dict) -> str:
        return subprocess.run([sys.executable, "-c", "from firelane import paths; print(paths.PROCESSED)"],
                              cwd=root, env=e, capture_output=True, text=True, check=True, timeout=60).stdout.strip()

    assert Path(run(base)) == root / "data" / "processed"
    assert run({**base, "FIRE_LANE_PROCESSED": "/tmp/zz_processed"}) == "/tmp/zz_processed"
