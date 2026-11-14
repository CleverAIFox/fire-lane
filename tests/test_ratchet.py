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


def _load_pushready():
    spec = importlib.util.spec_from_file_location("pushready_t", ROOT / "tools" / "pushready.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


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
    # ★ 2026-10-09 (DECISIONS §440-3). `sizecheck.py` → `sizetable.py`. 예외
    #   표를 떼면서 `RATCHETS` 선언도 **표를 따라갔다** — `ratchet.py` 는 선언한
    #   **그 파일에** 수를 고쳐 적으므로 둘이 갈리면 `--write` 가 쓸 자리를 잃는다.
    for want in ("scopedecl.py", "suppress.py", "sizetable.py"):
        assert want in names, f"{want} 가 `RATCHETS` 를 안 선언한다"


def test_every_declared_ratchet_is_a_real_module_constant():
    """선언한 이름이 실물 상수여야 한다 — 아니면 `--write` 가 쓸 자리가 없다."""
    for p, m in RT.owners():
        for name in m.RATCHETS:
            assert hasattr(m, name), f"{p.name} 이 없는 이름 `{name}` 을 선언했다"


def test_declared_ratchet_names_equal_produced_names_per_tool():
    """W13-17 — 선언한 축 집합 == `ratchet_values()` 가 내는 축 집합. **값이 아니라 수**를 센다.

    한쪽만 움직이면 그 축이 조용히 죽는다(534-3 이 뺀 축을 산출이 계속 낸 때). `down-map` 은 표의 **키**가 산출 키다.
    레이크 없이는 못 재는 도구는 `lake_only()` 에 선언된 것만 건너뛴다.
    """
    exempt = RT.lake_only()
    checked = skipped = 0
    for p, m in RT.owners():
        try:
            produced = set(m.ratchet_values())
        except Exception as e:                  # noqa: BLE001 — 레이크 의존 도구의 실측 함수
            # 변이 장부가 낡으면 `mutate.py` 가 **일부러** 죽는다(장부를 다시 재라는 사람 몫의 빨강). 그 하나만 건너뛴다 — 면제 선언된 레이크 도구도 건너뛴다.
            stale_ledger = p.name == "mutate.py" and "mutate.py --write --stale" in str(e)
            assert p.name in exempt or stale_ledger, f"{p.name} 의 `ratchet_values()` 가 죽었는데 면제 사유가 없다 — {e}"
            skipped += 1
            continue
        src = p.read_text(encoding="utf-8")
        declared: set[str] = set()
        for name, direction in m.RATCHETS.items():
            if direction == "down-map":
                # 표는 **예외 항목**만 선언한다 — 산출은 모든 파일을 낸다. 그래서 선언 키 ⊆ 산출 키(산출이 모르는 키를 선언했으면 그 항목이 죽었다)이고
                # 표 항목은 같음 비교에서 뺀다(그 표의 산출 키는 다른 선언이 없으면 표 키 전부다).
                keys = set(RT._map_keys(src, name))
                assert keys <= produced, f"{p.name}: 표 `{name}` 이 산출이 모르는 키를 선언했다 {sorted(keys - produced)[:5]}"
                declared |= produced if len(m.RATCHETS) == 1 else keys
            else:
                declared.add(name)
        assert declared == produced, (
            f"{p.name}: 선언만 {sorted(declared - produced)[:5]} · 산출만 {sorted(produced - declared)[:5]}")
        checked += 1
    assert checked >= 5 and checked > skipped, f"훑은 도구 {checked} · 건너뜀 {skipped} — 빈 그물이다"


class _FakeMod:
    def __init__(self, ratchets, vals):
        self.RATCHETS, self._v = ratchets, vals

    def ratchet_values(self):
        return dict(self._v)


def test_a_store_backed_ratchet_cries_when_loosened_and_asks_to_tighten_when_shrunk(tmp_path, monkeypatch):
    """W13-26 — 값이 소스 밖(값 파일)에 있어도 「느슨해지면 운다 · 조일 게 있으면 조이라고 운다」가 그대로다. 실물 값 파일은 안 건드린다."""
    import ratchetstore as RS
    fake = tmp_path / "tools"
    fake.mkdir()
    (fake / "faker.py").write_text("RATCHETS = {'N': 'up'}\nN = 1\n", encoding="utf-8")
    store = tmp_path / "r.json"
    store.write_text('{"values": {"faker.py": {"N": 10}}}', encoding="utf-8")
    monkeypatch.setattr(RS, "STORE", store)
    monkeypatch.setattr(RT, "TOOLS", fake)
    monkeypatch.setattr(RT, "owners", lambda: [(fake / "faker.py", _FakeMod({"N": "up"}, {"N": 4}))])
    assert RT.run(write=True) == 1, "up 인데 실측 4 < 선언 10 — 느슨해졌는데 초록이다"
    assert RS.read("faker.py", "N") == 10, "느슨해지는 쪽으로 값 파일에 써 버렸다"
    monkeypatch.setattr(RT, "owners", lambda: [(fake / "faker.py", _FakeMod({"N": "up"}, {"N": 12}))])
    assert RT.run(write=False) == 1, "조일 것이 있는데 --write 없이 초록이다"
    assert RS.read("faker.py", "N") == 10
    assert RT.run(write=True) == 0
    assert RS.read("faker.py", "N") == 12, "조이는 값이 값 파일에 안 써졌다"
    assert (fake / "faker.py").read_text(encoding="utf-8") == "RATCHETS = {'N': 'up'}\nN = 1\n", "도구 파일을 고쳤다"


# ── ⑤ 레이크에 기대는 래칫 (§318) ──────────────────────────────

def test_a_declared_lake_only_tool_is_skipped_with_a_reason(tmp_path, monkeypatch):
    """★ 선언된 레이크 의존은 **사유와 함께** 건너뛴다. 조용히 빠지지 않는다."""
    fake = tmp_path / "tools"
    fake.mkdir()
    (fake / "faker.py").write_text(
        "RATCHETS = {'N': 'down'}\nN = 5\n"
        "def ratchet_values():\n"
        "    raise RuntimeError('segments_5186.gpkg 가 없다')\n", encoding="utf-8")
    (fake / "other.py").write_text(
        "RATCHETS = {'M': 'down'}\nM = 5\n"
        "def ratchet_values():\n    return {'M': 5}\n", encoding="utf-8")
    monkeypatch.setattr(RT, "TOOLS", fake)
    monkeypatch.setattr(RT, "lake_only",
                        lambda: {"faker.py": "레이크(2.5GB 외장)가 있어야 돈다"})
    rows = RT.survey()
    sk = [r for r in rows if "skip" in r]
    assert len(sk) == 1 and sk[0]["tool"] == "faker.py"
    assert "레이크" in sk[0]["skip"], "사유를 안 들고 건너뛴다"
    assert "RuntimeError" in sk[0]["cause"], "원인을 안 들고 건너뛴다"
    assert RT.run(write=False) == 0, "선언된 면제인데 빨간불이다"


def test_an_undeclared_death_stays_red(tmp_path, monkeypatch):
    """★ 반대 방향. 「죽었으면 봐 준다」가 되면 어떤 결함도 면제로 통과한다."""
    fake = tmp_path / "tools"
    fake.mkdir()
    (fake / "faker.py").write_text(
        "RATCHETS = {'N': 'down'}\nN = 5\n"
        "def ratchet_values():\n    raise ZeroDivisionError('진짜 결함')\n",
        encoding="utf-8")
    monkeypatch.setattr(RT, "TOOLS", fake)
    monkeypatch.setattr(RT, "lake_only", lambda: {})
    assert RT.run(write=False) == 1
    assert any("err" in r for r in RT.survey())


def test_skipping_everything_is_an_empty_net(tmp_path, monkeypatch):
    """★ 전부 건너뛰면 **빈 그물**이다. 초록이면 관문이 없는 것과 같다."""
    fake = tmp_path / "tools"
    fake.mkdir()
    (fake / "faker.py").write_text(
        "RATCHETS = {'N': 'down'}\nN = 5\n"
        "def ratchet_values():\n    raise RuntimeError('레이크 없음')\n",
        encoding="utf-8")
    monkeypatch.setattr(RT, "TOOLS", fake)
    monkeypatch.setattr(RT, "lake_only", lambda: {"faker.py": "레이크가 있어야 돈다"})
    assert RT.run(write=False) == 1, "재어 본 래칫이 0인데 초록을 냈다"


def test_lake_only_comes_from_verify_not_a_hand_list():
    """★ 정본 하나. 손목록이면 `verify.sh` 와 갈리고, 갈린 순간 면제가 거짓이 된다."""
    got = RT.lake_only()
    assert "widthcross.py" in got, "`ci-exempt` 선언을 안 물려받는다"
    assert len(got["widthcross.py"]) > 5, "사유가 사유가 아니다"
    src = TOOL.read_text(encoding="utf-8")
    assert "gate_parity" in src, "면제 정본을 안 부른다 — 두 번째 독자를 만들었다"
    # ★ **AST 로 본다.** 글자로 보면 「왜 직접 안 읽는가」를 적은 주석이
    #   직접 읽는 것으로 세어진다 — §283-3 이 세 번 겪은 그 결함이다.
    import ast
    lits = [n.value for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and len(n.value) < 80]
    assert not [x for x in lits if "verify.sh" in x], (
        "`ratchet.py` 안에 `verify.sh` 경로 문자열이 있다 — 독자가 둘이 됐다")


def test_the_real_tree_gate_is_wired_without_write_where_it_runs():
    """★ 「지금 트리에서 선언 = 실측」은 **`ratchet.py` 전수**가 든다 — 그 전수는 이 시험이 아니라 아래 셋이 **`--write` 없이** 돈다.

    ── 왜 여기서 전수를 안 도나 (2026-11-12 · DECISIONS §712 · ⓲B-③) ──
    종전 시험은 `RT.run(write=False)` 전수를 불렀다. 전수가 단독 약 100초(지금 약 55초)이고 병렬 8 에서는 5배로 늘어 **300초 시한을 넘었다.** 같은 전수가
    이미 세 곳에서 돈다 — 이 시험이 넷째였다:
      · `tools/pushready.py` ㉠ (푸시 전 — 사람이 돌리는 차단)  · CI 「래칫 정합」 단계  · `tools/verify.sh` 의 `ratchet.py` 단계
    좁힌 것이지 느슨하게 한 것이 아니다: 도구가 **읽고 판정하는가**는 위쪽 합성 트리 시험들이 문다(느슨해진 쪽 · 못 재는 것 · 조이는 쪽), **실제 트리가 맞는가**는 위 셋이 든다.
    여기가 묻는 것은 그 셋이 **`--write` 를 안 쓰고 실제로 걸려 있는가** — 쓰면서 재면 영영 초록이다(§309).
    """
    import re
    PR = _load_pushready()
    seen: list[list[str]] = []

    def fake(cmd: list[str], root: Path) -> tuple[int, str]:
        seen.append(list(cmd))
        return 0, ""
    PR.check_ratchet(ROOT, fake)
    assert seen and "tools/ratchet.py" in seen[0] and "--write" not in seen[0], f"pushready ㉠ 이 ratchet.py 를 `--write` 없이 안 부른다: {seen}"
    ci = (ROOT / ".github" / "workflows" / "contract.yml").read_text(encoding="utf-8")
    lines = [ln.strip() for ln in ci.splitlines() if re.search(r"run:\s*uv run python tools/ratchet\.py\b", ln)]
    assert lines and all("--write" not in ln for ln in lines), f"CI 의 래칫 단계가 없거나 `--write` 다: {lines}"


def test_the_selftest_is_alive():
    r = subprocess.run([sys.executable, str(TOOL), "--selftest"],  # noqa: S603 — 트리 안의 도구다
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
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


# ── 2026-11-04 (PLAN #185 · DECISIONS §620) 우는 자리가 **다음 칸**을 말한다 ────────────
def test_the_ratchet_names_the_next_step_where_it_cries(capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("_rt_chain", Path(__file__).resolve().parents[1] / "tools" / "ratchet.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m            # `@dataclass` 가 되짚는다 — 안 넣으면 지연 신관이다
    spec.loader.exec_module(m)
    loose = [{"tool": "uicheck.py", "name": "UI_TEXT"}]
    m._chain(loose, [], [{"tool": "mutate.py", "name": "-", "err": "낡음"}], False)
    out = capsys.readouterr().out
    assert "손으로" in out and "--write` 는 안 받는다" in out, "느슨해진 쪽이 손으로라고 안 말한다"
    assert "mutate.py --write --stale" in out, "변이 장부가 낡았는데 다음 명령을 안 말한다"
    assert out.index("손으로") < out.index("mutate.py"), "사슬의 순서가 거꾸로다"
    m._chain([], [{"tool": "x.py", "name": "N", "declared": 3, "measured": 2}], [], False)
    assert "ratchet.py --write" in capsys.readouterr().out, "조이는 쪽이 `--write` 를 안 말한다"
    m._chain([], [], [], False)
    assert capsys.readouterr().out == "", "울 것이 없는데 말한다"
