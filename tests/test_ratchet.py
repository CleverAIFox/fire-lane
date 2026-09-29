"""
test_ratchet.py — 래칫 자동 조임이 **느슨해지는 쪽으로 쓸 수 없는가**.
(DECISIONS §309 · `tools/ratchet.py`)

── 왜 이 파일이 생겼나 (2026-09-29) ────────────────────────────
래칫에 `--write` 를 다는 일은 **관문을 끄는 장치를 만드는 일과 한 끗 차이**다.
쓰는 쪽을 자동화하면, 실측이 나빠졌을 때도 그 나쁜 수를 선언에 적어 버릴 수
있고 그러면 검사는 영영 초록이 된다(§264 가 「항상 통과하는 검사」로 부른 것).

★ 그래서 여기가 무는 것은 「값이 맞는가」가 아니라 **「방향을 어겼는가」**다 —

    ① 조이는 쪽만 쓴다        · 반대 방향이면 **안 쓰고 빨간불**
    ② 안 쓰는 것으로 끝나지 않는다 · 느슨해진 것을 **초록으로 덮지 않는다**
    ③ 쓰기가 자리를 안 어긋낸다   · 표 항목 여럿을 한 파일에 쓸 때
    ④ 그물이 비지 않았다        · 훑기가 0개를 모으면 「전부 맞다」가 거짓말이다

IN    tools/ratchet.py · `RATCHETS` 를 선언한 도구들
OUT   없음
밖    **래칫의 값이 옳은가는 안 본다.** 「`NO_DECL` 150 이 좋은 수인가」는 사람의
      판단이다 — 여기는 「선언이 실측과 같은가」와 「고칠 때 방향을 지키는가」만 든다.
      **실물 도구 파일에 안 쓴다.** 쓰기는 전부 `tmp_path` 사본에서 본다 —
      시험이 트리를 고치면 그 시험은 제가 만든 상태를 재는 것이 된다.
      **각 관문의 빨간불은 그 도구 소관이다** — 래칫을 어겼을 때 우는 것은
      여전히 `scopedecl` · `suppress` · `sizecheck` 이고, 이 도구는 받아적기만 없앤다.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "ratchet.py"


def _rt():
    spec = importlib.util.spec_from_file_location("ratchet_t", TOOL)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m          # @dataclass·되짚기 (§258-10)
    spec.loader.exec_module(m)
    return m


RT = _rt()


# ── ① 조이는 쪽만 쓴다 ─────────────────────────────────────────

def test_a_loosening_move_is_never_a_tightening_one():
    """★ 이 시험 하나가 이 도구의 안전 전부다.

    `down` 래칫에서 실측이 **커지는** 것은 나빠진 것이고, `up` 래칫에서
    **작아지는** 것도 나빠진 것이다. 둘 다 조임으로 보면 안 된다 — 그러면
    `--write` 가 나빠진 수를 선언에 적어 검사를 끈다.
    """
    assert RT.tightens("down", 10, 8), "down 에서 줄어든 것을 조임으로 안 본다"
    assert not RT.tightens("down", 10, 12), (
        "down 에서 **늘어난** 것을 조임으로 봤다 — `--write` 가 관문을 끈다")
    assert RT.tightens("up", 10, 12), "up 에서 늘어난 것을 조임으로 안 본다"
    assert not RT.tightens("up", 10, 8), (
        "up 에서 **줄어든** 것을 조임으로 봤다 — `--write` 가 관문을 끈다")


def test_an_unchanged_ratchet_is_not_written():
    """같은 값이면 쓸 것이 없다 — 방향은 둘 다 **엄격 부등호**다."""
    for d in ("down", "up", "down-map"):
        assert not RT.tightens(d, 10, 10), f"{d} 가 같은 값을 움직임으로 본다"


def test_the_map_direction_matches_the_scalar_one():
    """`down-map` 은 항목마다 `down` 이다 — 다르게 판정하면 예외 표만 샌다."""
    for dec, got in ((10, 8), (10, 12), (10, 10)):
        assert RT.tightens("down-map", dec, got) == RT.tightens("down", dec, got)


# ── ② 느슨해진 것을 초록으로 덮지 않는다 ────────────────────────

def test_a_loosened_ratchet_makes_the_tool_red(tmp_path: Path, monkeypatch):
    """★ 「안 쓴다」로 끝나면 안 된다. 실측이 나빠졌는데 **초록**이면,
    자동화를 돌리는 사람은 그 사실을 영영 못 본다.
    """
    fake = tmp_path / "tools"
    fake.mkdir()
    (fake / "faker.py").write_text(
        "RATCHETS = {'N': 'down'}\n"
        "N = 5\n"
        "def ratchet_values():\n"
        "    return {'N': 9}\n", encoding="utf-8")
    monkeypatch.setattr(RT, "TOOLS", fake)
    rows = RT.survey()
    row = next(r for r in rows if r.get("name") == "N")
    assert not RT.tightens(row["dir"], row["declared"], row["measured"])
    assert RT.run(write=True) == 1, (
        "실측이 나빠졌는데 `--write` 가 초록을 냈다 — 아무도 그 사실을 못 본다")
    assert "N = 5" in (fake / "faker.py").read_text(encoding="utf-8"), (
        "느슨해지는 쪽으로 **써 버렸다** — 관문이 죽는다")


def test_a_broken_measure_is_red_not_silent(tmp_path: Path, monkeypatch):
    """실측 함수가 죽으면 빨간불이다. 조용히 건너뛰면 그 래칫은 사라진다."""
    fake = tmp_path / "tools"
    fake.mkdir()
    (fake / "faker.py").write_text(
        "RATCHETS = {'N': 'down'}\nN = 5\n", encoding="utf-8")   # 함수가 없다
    monkeypatch.setattr(RT, "TOOLS", fake)
    assert RT.run(write=False) == 1
    assert any("err" in r for r in RT.survey())


def test_an_unknown_direction_is_red(tmp_path: Path, monkeypatch):
    """모르는 방향을 「기본은 조임」으로 처리하면 안 된다 — 오타가 관문을 끈다."""
    fake = tmp_path / "tools"
    fake.mkdir()
    (fake / "faker.py").write_text(
        "RATCHETS = {'N': 'donw'}\n"
        "N = 5\n"
        "def ratchet_values():\n"
        "    return {'N': 1}\n", encoding="utf-8")
    monkeypatch.setattr(RT, "TOOLS", fake)
    assert RT.run(write=True) == 1
    assert "N = 5" in (fake / "faker.py").read_text(encoding="utf-8")


# ── ③ 쓰기가 자리를 안 어긋낸다 ────────────────────────────────

def test_writing_several_values_in_one_file_does_not_shift(tmp_path: Path, monkeypatch):
    """★ 한 파일에 둘 이상 쓸 때, 앞에서부터 쓰면 뒤의 오프셋이 밀린다.

    자릿수가 바뀌는 수(9 → 10)를 일부러 섞는다 — 길이가 같으면 이 결함이 안 보인다.
    """
    fake = tmp_path / "tools"
    fake.mkdir()
    q = fake / "faker.py"
    q.write_text(
        "RATCHETS = {'A': 'down', 'B': 'up', 'T': 'down-map'}\n"
        "A = 100\n"
        "B = 9\n"
        "T: dict[str, int] = {'x/y.py': 50, 'z.py': 7}\n"
        "def ratchet_values():\n"
        "    return {'A': 4, 'B': 1000, 'x/y.py': 8, 'z.py': 7}\n", encoding="utf-8")
    monkeypatch.setattr(RT, "TOOLS", fake)
    assert RT.run(write=True) == 0
    after = q.read_text(encoding="utf-8")
    assert "A = 4" in after, after
    assert "B = 1000" in after, after
    assert "'x/y.py': 8" in after, after
    assert "'z.py': 7" in after, "안 움직인 항목을 건드렸다"
    monkeypatch.setattr(RT, "TOOLS", fake)
    assert RT.run(write=False) == 0, "두 번째 실행이 아직도 낡았다고 한다"


# ── ④ 그물이 비지 않았다 ───────────────────────────────────────

def test_the_real_tools_declare_ratchets():
    """실물 트리에서 래칫을 실제로 찾는다 — 0개면 「전부 맞다」가 거짓말이다."""
    names = {p.name for p, _ in RT.owners()}
    for want in ("scopedecl.py", "suppress.py", "sizecheck.py"):
        assert want in names, f"{want} 가 `RATCHETS` 를 안 선언한다"


def test_every_declared_ratchet_is_a_real_module_constant():
    """선언한 이름이 실물 상수여야 한다 — 아니면 `--write` 가 쓸 자리가 없다."""
    for p, m in RT.owners():
        for name in m.RATCHETS:
            assert hasattr(m, name), f"{p.name} 이 없는 이름 `{name}` 을 선언했다"


def test_the_real_tree_is_at_its_ratchets():
    """지금 트리에서 선언 = 실측이다. **이것이 관문 자체다.**"""
    assert RT.run(write=False) == 0, (
        "래칫이 실측과 다르다 — `uv run python tools/ratchet.py --write` 로 조여라")


def test_the_selftest_is_alive():
    r = subprocess.run([sys.executable, str(TOOL), "--selftest"],  # noqa: S603 — 트리 안의 도구다
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_verify_runs_it_without_write():
    """★ 관문이 `--write` 를 돌면 **항상 통과한다** — 쓰고 나서 재기 때문이다."""
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    assert "tools/ratchet.py" in sh, "verify.sh 가 이 도구를 안 부른다"
    line = [ln for ln in sh.splitlines()
            if "tools/ratchet.py" in ln and ln.strip().startswith("step ")]
    assert line, "`step` 이 아니다 — note 로 적으면 실패가 판정에 안 든다"
    assert "--write" not in line[0], (
        "관문이 `--write` 를 돈다 — 쓰고 나서 재므로 **영영 초록이다**")
