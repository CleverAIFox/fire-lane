"""
test_actionpin.py — **관문이 어느 코드로 도는가.** 1족 가드.
(PLAN §13 W13-6 · DECISIONS §324 · `tools/actionpin.py`)

── 왜 이 파일이 생겼나 (2026-09-30) ────────────────────────────
`uses: actions/checkout@v7` 은 코드를 안 가리킨다. `v7` 은 **옮겨 다니는
이름표**이고, 그 이름표를 쥔 쪽이 다른 커밋에 다시 붙이면 우리 CI 가 조용히
다른 코드를 돈다 — 우리가 고친 것이 없는데 결과가 바뀌고, 바뀐 줄도 모른다.

★ 그래서 **인스턴스를 지우는 것은 배치가 하고 이 파일은 족을 닫는다**
  (PLAN §13-5 규칙 1). 20줄을 지문으로 바꾼 것은 한 번의 일이고, 다음에
  누가 태그로 되돌리거나 새 워크플로를 태그로 쓰는 것을 막는 것이 여기다.
  워크플로가 새로 생겨도 자동으로 물린다 — 목록을 안 든다.

★ 둘째는 시간 상한이다. `timeout-minutes` 가 없으면 GitHub 기본 **6시간**까지
  매달린다. 죽은 작업 하나가 반나절을 태우고, 그동안 아무도 결과를 못 본다.

IN    tools/actionpin.py · .github/workflows/*
OUT   없음
밖    **상한 값이 맞는가는 안 본다.** 조일 근거는 W13-9(전량 재실행 시간 실측
      정본)가 서야 생긴다 — 근거 없이 조이면 느린 러너에서 무고한 빨간불이 나고
      그것이 검사를 끄게 만든다(MASTER §18-13).
      **판이 최신인가는 안 본다.** `v7` 을 `v8` 로 올리는 것은 사람의 판단이다.
      **액션이 안전한가는 안 본다.** 여기가 드는 것은 「아는 코드가 도는가」다.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_t", ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


AP = _load("actionpin")


# ── ① 실물 ─────────────────────────────────────────────────────

def test_the_real_workflows_are_pinned():
    """★ **이것이 가드다.** 태그로 되돌리면 여기서 운다."""
    bad = AP.pin_faults()
    assert not bad, "떠 있는 이름표로 도는 액션이 있다 —\n  " + "\n  ".join(bad)


def test_every_job_has_a_time_bound():
    bad = AP.timeout_faults()
    assert not bad, "시간 상한 없는 작업이 있다 —\n  " + "\n  ".join(bad)


def test_the_net_is_not_empty():
    """★ 반대 방향. 워크플로를 하나도 못 찾으면 위 둘은 **항상 초록**이다."""
    wfs = AP.workflows()
    assert len(wfs) >= 4, f"워크플로를 {len(wfs)}개만 찾았다 — 경로가 틀렸다"
    n = sum(1 for p in wfs for ln in p.read_text(encoding="utf-8").splitlines()
            if (m := AP.USES.match(ln)) and not AP.is_local(m.group("ref")))
    assert n >= 15, f"밖 액션을 {n}줄만 찾았다 — 정규식이 줄을 못 읽는다"


# ── ② 판정기 ───────────────────────────────────────────────────

def test_a_floating_tag_is_caught(tmp_path: Path, monkeypatch):
    """★ 고침을 되돌린 트리에서 **실제로 우는가.** 합성 워크플로로 본다."""
    wf = tmp_path / "workflows"
    wf.mkdir()
    (wf / "x.yml").write_text(
        "name: x\non:\n  push:\njobs:\n  a:\n    runs-on: ubuntu-24.04\n"
        "    timeout-minutes: 5\n    steps:\n      - uses: actions/checkout@v7\n",
        encoding="utf-8")
    monkeypatch.setattr(AP, "WF", wf)
    bad = AP.pin_faults()
    assert len(bad) == 1 and "떠 있는 이름표" in bad[0], bad
    assert not AP.timeout_faults()


def test_a_bare_digest_without_its_tag_is_caught(tmp_path: Path, monkeypatch):
    """지문만 있고 판 표기가 없으면 **사람이 갱신을 못 한다.**"""
    wf = tmp_path / "workflows"
    wf.mkdir()
    sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"
    (wf / "x.yml").write_text(
        f"name: x\non:\n  push:\njobs:\n  a:\n    runs-on: ubuntu-24.04\n"
        f"    timeout-minutes: 5\n    steps:\n      - uses: actions/checkout@{sha}\n",
        encoding="utf-8")
    monkeypatch.setattr(AP, "WF", wf)
    bad = AP.pin_faults()
    assert len(bad) == 1 and "어느 판인지" in bad[0], bad


def test_a_job_without_a_bound_is_caught(tmp_path: Path, monkeypatch):
    wf = tmp_path / "workflows"
    wf.mkdir()
    sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"
    (wf / "x.yml").write_text(
        f"name: x\non:\n  push:\njobs:\n  a:\n    runs-on: ubuntu-24.04\n"
        f"    steps:\n      - uses: actions/checkout@{sha}  # v7\n",
        encoding="utf-8")
    monkeypatch.setattr(AP, "WF", wf)
    assert not AP.pin_faults()
    bad = AP.timeout_faults()
    assert len(bad) == 1 and "`a`" in bad[0], bad


def test_a_reusable_workflow_job_is_exempt(tmp_path: Path, monkeypatch):
    """★ **GitHub 이 그 작업의 상한을 거부한다** — 넣으면 워크플로가 통째로 안 돈다.

    면제가 아니라 문법이다. 그래서 여기서 빼는 것이 옳고, 빼는 것을 잊으면
    「고치라는 대로 고쳤더니 CI 가 죽는」 검사가 된다.
    """
    wf = tmp_path / "workflows"
    wf.mkdir()
    (wf / "x.yml").write_text(
        "name: x\non:\n  push:\njobs:\n  gate:\n    uses: ./.github/workflows/c.yml\n"
        "    secrets: inherit\n", encoding="utf-8")
    monkeypatch.setattr(AP, "WF", wf)
    assert not AP.timeout_faults(), "재사용 호출 작업에 상한을 요구한다"
    assert not AP.pin_faults(), "저장소 안 워크플로를 고정하라고 한다"


def test_the_selftest_is_alive():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "actionpin.py"),  # noqa: S603 — 트리 안의 도구다
                        "--selftest"], capture_output=True, text=True,
                       cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


# ── ③ 배선 ─────────────────────────────────────────────────────

def test_the_check_runs_on_both_gates():
    """★ 로컬에만 걸면 3족이다 — CI 는 그 검사를 영영 안 돈다."""
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "contract.yml").read_text(encoding="utf-8")
    assert "tools/actionpin.py" in sh, "`verify.sh` 가 안 부른다"
    assert "tools/actionpin.py" in ci, "CI 가 안 부른다 — 관문이 갈린다"
    # ★ 주석에 낱말이 있는 것과 **부르는 것**은 다르다. 부르는 줄만 본다 —
    #   이 구분을 안 하면 머리말에 설명을 적었다고 시험이 운다.
    calls = [ln for ln in (sh + "\n" + ci).splitlines()
             if "tools/actionpin.py" in ln and "#" not in ln.split("tools/")[0]]
    assert calls, "부르는 줄을 하나도 못 찾았다 — 빈 그물이다"
    assert not any("--write" in ln for ln in calls), (
        "관문이 `--write` 를 부른다 — 검사가 제가 볼 것을 고치면 영원히 초록이다")


def test_writing_twice_changes_nothing(tmp_path: Path, monkeypatch):
    """★ **멱등인가.** 두 번째가 무언가 바꾸면 배치마다 워크플로가 흔들리고,
    흔들리면 도장이 매번 무효가 되어 「다시 보라」의 신호가 0 이 된다.

    네트워크를 안 쓴다 — 태그를 푸는 자리만 가짜로 세운다. 판정과 달리
    `--write` 는 `git ls-remote` 가 필요하고 CI 에 그것을 기대면 안 된다.
    """
    sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"
    wf = tmp_path / "workflows"
    wf.mkdir()
    f = wf / "x.yml"
    f.write_text(
        "name: x\non:\n  push:\njobs:\n  a:\n    runs-on: ubuntu-24.04\n"
        "    timeout-minutes: 5\n    steps:\n      - uses: actions/checkout@v7\n"
        "      - uses: ./.github/actions/local\n",
        encoding="utf-8")
    monkeypatch.setattr(AP, "WF", wf)
    monkeypatch.setattr(AP, "resolve", lambda repo, tag: sha)

    assert AP.write() == 0
    once = f.read_text(encoding="utf-8")
    assert f"actions/checkout@{sha}  # v7" in once, once
    assert "./.github/actions/local" in once, "저장소 안 액션을 건드렸다"

    assert AP.write() == 0
    assert f.read_text(encoding="utf-8") == once, "두 번째 쓰기가 무언가 바꿨다"
    assert not AP.pin_faults(), "제가 쓴 것을 제가 위반으로 읽는다"


def test_writing_never_bumps_the_version(tmp_path: Path, monkeypatch):
    """★ 고정과 **갱신**은 다른 일이다. 한 배치에서 같이 하면 CI 가 빨개졌을 때
    「지문 때문인가 판 때문인가」를 못 가른다."""
    wf = tmp_path / "workflows"
    wf.mkdir()
    f = wf / "x.yml"
    f.write_text(
        "name: x\non:\n  push:\njobs:\n  a:\n    runs-on: ubuntu-24.04\n"
        "    timeout-minutes: 5\n    steps:\n      - uses: actions/checkout@v6\n",
        encoding="utf-8")
    monkeypatch.setattr(AP, "WF", wf)
    asked: list[tuple[str, str]] = []
    monkeypatch.setattr(AP, "resolve",
                        lambda repo, tag: asked.append((repo, tag))
                        or "3d3c42e5aac5ba805825da76410c181273ba90b1")
    AP.write()
    assert asked == [("actions/checkout", "v6")], f"적힌 태그가 아닌 것을 물었다 — {asked}"
    assert "# v6" in f.read_text(encoding="utf-8"), "적힌 판을 안 남겼다"
