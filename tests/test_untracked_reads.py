"""비추적 읽기 선언 검사 — 시험이 `.gitignore` 생성물 · 환경 파일을 열면 **선언표에 사유와 함께 있어야** 한다. (2026-11-20 · `test_fieldmark` 사고)

PLAN 본문  규칙 없음 — PLAN.md 를 읽어 규칙을 세우지 않는다
IN    `tests/audit_site/untracked_reads.py`(선언표 · 판별) · `tests/audit_site/fsaudit.py`(훅) · `data/golden/testreads.json`(읽기 장부의 `untracked` 칸 — `testpick --measure-reads --write` 가 쓴다)
OUT   없음 (검사)
밖    **장부가 잰 만큼만 안다** — 시험이 바뀐 뒤 다시 안 쟀으면 새 읽기는 장부에 없다(그 낡음은 `testpick` 의 `reads_stale` 가 말하고 `pushready` ㉥ 가 초록을 안 낸다).
      이 파일은 **저장소에 든 파일만** 읽는다 — 생성물을 읽는 시험을 막는 시험이 생성물을 읽으면 안 된다. 사고의 원형(`width_samples.csv` 를 여는 시험)은 임시 뿌리에서 같은 이름으로 재현한다.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "tests" / "audit_site"
LEDGER = ROOT / "data" / "golden" / "testreads.json"


def _load(name: str):
    """경로로 연다(`sys.path` 를 안 만진다 — `test_layering`). 훅 모듈은 이 시험 전용 사본이다(전역 `_busy` 를 남과 안 나눈다)."""
    spec = importlib.util.spec_from_file_location(f"{name}_for_untracked_reads", SITE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


U = _load("untracked_reads")
F = _load("fsaudit")

GOOD = "환경skip(산출물) — 없으면 건너뛴다(CI 에서 안 돈다)"


# ── 카나리아(445) — 합성 장부 · 합성 표로 판별이 울고 안 우는 것을 보인다 ──────────────

def test_a_read_nobody_declared_cries():
    bad = U.judge({"test_a.py": ["data/processed/width_samples.csv"]}, {}, {})
    assert len(bad) == 1 and "선언 없는 비추적 읽기" in bad[0] and "test_a.py" in bad[0] and "width_samples.csv" in bad[0]


def test_a_declaration_with_a_reason_silences_exactly_that_test_and_pattern():
    decl = {"test_a.py": {"data/processed/width_samples.csv": GOOD}}
    assert U.judge({"test_a.py": ["data/processed/width_samples.csv"]}, decl, {}) == []
    other_test = U.judge({"test_a.py": ["data/processed/width_samples.csv"], "test_b.py": ["data/processed/width_samples.csv"]}, decl, {})
    assert len(other_test) == 1 and "test_b.py" in other_test[0], "선언은 시험마다다 — 남의 선언이 내 읽기를 덮으면 안 된다"
    other_path = U.judge({"test_a.py": ["data/processed/width_samples.csv", "data/processed/other.csv"]}, decl, {})
    assert len(other_path) == 1 and "other.csv" in other_path[0]


def test_a_dead_declaration_cries():
    """선언표에 있는데 장부에 그 읽기가 없다 — 시험이 더는 안 읽는데 면제가 남으면 사각지대다."""
    decl = {"test_a.py": {"data/processed/gone.csv": GOOD}}
    bad = U.judge({"test_a.py": []}, decl, {})
    assert len(bad) == 1 and "죽은 선언" in bad[0] and "gone.csv" in bad[0]
    assert any("죽은 선언" in b for b in U.judge({}, decl, {})), "장부에 시험 칸 자체가 없어도(시험이 없어졌다) 죽은 선언이다"


@pytest.mark.parametrize("why", ["", "   ", "짧다"])
def test_a_declaration_with_an_empty_reason_cries(why):
    bad = U.judge({"test_a.py": ["data/x.csv"]}, {"test_a.py": {"data/x.csv": why}}, {})
    assert len(bad) == 1 and "사유가 빈 선언" in bad[0]


def test_an_ambient_entry_is_exempt_for_every_test_and_a_dead_or_reasonless_one_cries():
    allow = {".env": "환경 로더가 import 때 읽는다 — 시험이 고르는 입력이 아니다"}
    assert U.judge({"test_a.py": [".env"], "test_b.py": [".env"]}, {}, allow) == []
    assert U.dead_allow({"test_a.py": [".env"]}, allow) == []
    assert len(U.dead_allow({"test_a.py": []}, allow)) == 1 and "죽은 허용" in U.dead_allow({"test_a.py": []}, allow)[0]
    assert any("사유가 빈 허용" in b for b in U.judge({"test_a.py": [".env"]}, {}, {".env": ""}))


def test_an_ambient_glob_exempts_what_is_under_it_and_nothing_else():
    allow = {"src/fire_lane.egg-info/*": "패키지 메타데이터 — import 때 읽는다"}
    assert U.judge({"t.py": ["src/fire_lane.egg-info/PKG-INFO"]}, {}, allow) == []
    assert len(U.judge({"t.py": ["src/fire_lane.egg-info/PKG-INFO", "src/other/x"]}, {}, allow)) == 1


def test_a_ledger_cell_missing_means_not_measured_yet():
    assert U.incomplete({"reads": {"a.py": [], "b.py": []}}) == ["a.py", "b.py"], "`untracked` 키가 통째로 없는 옛 장부"
    assert U.incomplete({"reads": {"a.py": [], "b.py": []}, "untracked": {"a.py": []}}) == ["b.py"]
    assert U.incomplete({"reads": {"a.py": []}, "untracked": {"a.py": []}}) == [], "빈 칸 = 재 봤고 안 읽는다"


# ── 사고의 원형 — 임시 뿌리에서 같은 길(훅 → 장부 칸 → 판별)을 걷는다 ──────────────────────

@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "processed" / "width_samples.csv").write_text("seg_uid,w\n", encoding="utf-8")        # 생성물 — 추적 안 됨
    (tmp_path / ".env").write_text("K=v\n", encoding="utf-8")
    (tmp_path / "tracked.txt").write_text("t\n", encoding="utf-8")
    return tmp_path


def _hook_reads(root: Path, test: str, *rels: str, tracked: tuple[str, ...] = ("tracked.txt",)) -> list[tuple[str, str]]:
    """훅(`fsaudit.make_hook`)에 열기 이벤트를 먹여 (종류, 경로)를 받는다."""
    got: list[tuple[str, str]] = []
    hook = F.make_hook(str(root), set(tracked), lambda kind, rel, t, ev: got.append((kind, rel)), lambda: test)
    for r in rels:
        hook("open", (str(root / r), "r", os.O_RDONLY))
    return got


def _verdict(got: list[tuple[str, str]], test: str, declared: dict, allow: dict) -> list[str]:
    untracked = {test: sorted(rel for kind, rel in got if kind == "n")}
    return U.judge(untracked, declared, allow)


def test_the_incident_prototype_is_recorded_by_the_hook_and_cries_until_declared(root: Path):
    """사고: 시험이 `data/processed/width_samples.csv`(실존 · 비추적)를 연다 → 훅이 `n` 으로 적는다 → 선언표에 없으면 빨갛다 → 사유와 올리면 초록."""
    got = _hook_reads(root, "test_fieldmark.py", "data/processed/width_samples.csv", "tracked.txt")
    assert ("n", "data/processed/width_samples.csv") in got and ("r", "tracked.txt") in got, "비추적은 `n` · 추적은 `r` — 두 칸이 섞이면 `touching` 의 뜻이 바뀐다"
    assert len(_verdict(got, "test_fieldmark.py", {}, U.ALLOW)) == 1, "선언 없는 읽기가 안 울었다 — 이 검사를 세운 의미가 없다"
    decl = {"test_fieldmark.py": {"data/processed/width_samples.csv": GOOD}}
    assert _verdict(got, "test_fieldmark.py", decl, U.ALLOW) == []


def test_the_real_ambient_env_file_is_exempt_without_a_declaration(root: Path):
    got = _hook_reads(root, "test_any.py", ".env")
    assert got == [("n", ".env")]
    assert [b for b in _verdict(got, "test_any.py", {}, U.ALLOW) if "선언 없는" in b] == [], "`.env` 는 배경 허용 목록이라 선언이 필요 없다"


def test_the_hook_ignores_missing_paths_tool_dirs_caches_bytecode_outside_paths_and_writes(root: Path):
    for d in (".venv/lib", "node_modules/x", ".git/objects", "pkg/__pycache__", ".cache/y", ".pytest_cache/v", ".ruff_cache/z"):
        (root / d).mkdir(parents=True)
        (root / d / "f.txt").write_text("x\n", encoding="utf-8")
    (root / "m.so").write_bytes(b"\0")
    (root / "m.pyc").write_bytes(b"\0")
    skipped = [".venv/lib/f.txt", "node_modules/x/f.txt", ".git/objects/f.txt", "pkg/__pycache__/f.txt", ".cache/y/f.txt",
               ".pytest_cache/v/f.txt", ".ruff_cache/z/f.txt", "m.so", "m.pyc", "data/processed/absent.csv"]
    assert _hook_reads(root, "t.py", *skipped) == []
    assert _hook_reads(root, "t.py", "..") == [] and F.untracked_read("../outside", str(root)) is False
    got: list[tuple[str, str]] = []
    hook = F.make_hook(str(root), {"tracked.txt"}, lambda kind, rel, t, ev: got.append((kind, rel)), lambda: "t.py")
    hook("open", (str(root / "data" / "processed" / "width_samples.csv"), "w", os.O_WRONLY))
    assert got == [], "비추적 **쓰기**는 안 센다(현행 유지)"


def test_a_tracked_write_is_still_recorded_as_w_and_a_tracked_read_as_r(root: Path):
    got: list[tuple[str, str]] = []
    hook = F.make_hook(str(root), {"tracked.txt"}, lambda kind, rel, t, ev: got.append((kind, rel)), lambda: "t.py")
    hook("open", (str(root / "tracked.txt"), "w", os.O_WRONLY))
    hook("open", (str(root / "tracked.txt"), "r", os.O_RDONLY))
    assert got == [("w", "tracked.txt"), ("r", "tracked.txt")]


def test_a_child_python_logs_the_untracked_read_through_sitecustomize(root: Path, tmp_path_factory: pytest.TempPathFactory):
    """자식 프로세스 길 — `prepare` → `PYTHONPATH`(`sitecustomize`) → 자식이 연 비추적 파일이 로그에 `n` 으로 남는다."""
    audit = tmp_path_factory.mktemp("audit")
    F.prepare(str(audit), str(root), {"tracked.txt"})
    env = {**os.environ, "FIRE_LANE_AUDIT_DIR": str(audit), "FIRE_LANE_AUDIT_TAG": "test_child.py", "PYTHONPATH": str(SITE)}
    code = "open('data/processed/width_samples.csv').read(); open('tracked.txt').read()"
    r = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, timeout=60, check=False)
    assert r.returncode == 0, r.stderr
    rows = {(k, p) for k, p, tag, _ev in F.read_log(str(audit)) if tag == "test_child.py"}
    assert ("n", "data/processed/width_samples.csv") in rows and ("r", "tracked.txt") in rows, rows


# ── 실물 표 · 실물 장부 ───────────────────────────────────────────────────────────

def test_the_ambient_list_is_exactly_the_three_reviewed_entries():
    """★ 래칫 — 배경 허용 목록은 `.env` · 패키지 메타데이터 · CI 가 빌드하는 `web/navi/dist` 셋이다. 늘리는 것은 이 시험의 수를 같이 고치는 사람의 결정이다."""
    assert set(U.ALLOW) == {".env", "src/fire_lane.egg-info/*", "web/navi/dist/*"}
    assert all(len(v.strip()) >= U.MIN_REASON for v in U.ALLOW.values())


def test_every_real_declaration_names_a_real_test_file_and_carries_a_reason():
    gone = sorted(n for n in U.DECLARED if not (ROOT / "tests" / n).is_file())
    assert not gone, f"없어진 시험을 선언표가 든다: {gone}"
    assert all(len(why.strip()) >= U.MIN_REASON for pats in U.DECLARED.values() for why in pats.values())
    assert not (set(U.DECLARED) & {"test_fieldmark.py"}), "사고 난 시험은 읽기를 선언하지 않고 **고쳤다**(표본 입력을 스스로 만든다 · 33d95841)"


def test_the_real_ledger_has_measured_every_test_for_untracked_reads_and_every_one_is_declared():
    """실물 장부 — `untracked` 칸이 없으면(옛 장부 · 재측정 전) **사람이 다시 잰다**. 건너뛰지 않는다. 있으면 선언 없는 읽기 · 죽은 선언이 없어야 한다."""
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    missing = U.incomplete(ledger)
    assert not missing, (f"비추적 읽기 장부가 없다 — 칸이 없는 시험 {len(missing)}개({', '.join(missing[:3])}{' …' if len(missing) > 3 else ''}). "
                         "사람이 `uv run python tools/testpick.py --measure-reads --write` 를 친다(낡은 몇 개만이면 `--only <파일…>`)")
    bad = [*U.judge(ledger["untracked"], U.DECLARED, U.ALLOW), *U.dead_allow(ledger["untracked"], U.ALLOW)]
    assert not bad, "\n".join(bad[:20]) + "\n  선언은 `tests/audit_site/untracked_reads.py` — 읽어도 되는 이유를 한 줄로 올리거나, 시험이 생성물을 안 읽게 고친다(CI 러너에 없다)."
