"""K2 · G — 틀리게 판정하던 검사와 도구의 카나리아. (DECISIONS §180)

★ 2026-09-17. 넷 다 **판정은 있었는데 틀린 곳**이다.
  ① dms 가 산문 줄머리 `강제자(` 를 칸으로 읽어 지운 테스트를 "죽은 참조" 로 봉인마다 찍었다
  ② plan_renumber 가 §12 표 번호 `#6` 을 §1 행 참조로 읽었다
  ③ acquire `--quarantine` 이 폐지된 층에 쓸 수 있었다
  ④ normalize_raw 가 처분이 적힌 landing 파일도 "규칙에 없는 파일" 로 냈다
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from firelane import lake

ROOT = Path(__file__).resolve().parents[1]


def _tool(name: str):
    spec = importlib.util.spec_from_file_location(f"k2_{name}", ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(mod)
    return mod


def test_dms_field_ignores_prose_with_parenthesis():
    dms = _tool("dms")
    assert dms.FIELD.match("강제자  `tests/test_x.py::test_y`")
    assert dms.FIELD.match("강제자 없음 — 사유: 기록이다")
    assert not dms.FIELD.match("강제자(`test_plan_x`)가 *PLAN 에 행이 있어야 한다* 고 단언해"), "괄호 산문을 칸으로 읽는다"
    assert not dms.FIELD.match("강제자가 없었다"), "조사 산문을 칸으로 읽는다 — 종전 규칙이 죽었다"


def test_plan_renumber_ignores_foreign_table_numbers():
    pr = _tool("plan_renumber")
    pr._canary()     # 합성 문서의 §12 `#6` 은 빼고 `§1 #6` 만 잡아야 통과한다
    doc = "## 1. 남은 일\n\n| # | 항목 |\n| 3 | a |\n\n## 7. 평가\n\n본문 #3\n\n## 12. 기획서\n\n| # | 서술 |\n본문 #3\n"
    spans = pr._foreign(doc)
    hits = [doc[m.start() - 8:m.end()] for m in pr.REF.finditer(doc) if pr._is_plan_ref(doc, m, spans)]
    assert len(hits) == 1, f"번호 표 없는 §7 산문의 #3 하나만 §1 참조다 — {hits}"


def test_acquire_refuses_quarantine(tmp_path):
    (tmp_path / "raw" / "nfa").mkdir(parents=True)
    (tmp_path / "raw" / "nfa" / "x.csv").write_text("x", encoding="utf-8")
    env = {**__import__("os").environ, "FIRE_LANE_DATA": str(tmp_path)}
    r = subprocess.run([sys.executable, str(ROOT / "tools/acquire.py"), "--quarantine", "--yes"],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 2 and "폐지" in r.stdout, r.stdout[-400:]
    assert not (tmp_path / "_quarantine").exists(), "폐지된 층을 만들었다"


def test_disposition_and_retired_reasons_come_from_the_resolver():
    y = {"retired": {"k": {"files": ["safety/a.csv"], "reason": "사유 한 줄\n둘째 줄"},
                     "g": {"stem": "safety_b"}},
         "landing_disposition": {"items": [{"file": "held-*.zip", "action": "held", "why": "보류\n자세히"},
                                           {"file": "nowhy.zip", "action": "held", "why": ""}]}}
    assert lake.retired_reasons(y) == {"a.csv": "사유 한 줄"}, "글롭 폐기를 이름으로 풀면 안 된다"
    assert lake.disposition(y) == [("held-*.zip", "held", "보류")], "사유 없는 처분은 처분이 아니다"


def test_merge_batch_stops_instead_of_warning():
    """G-2 · G-10 · G-12 — merge_batch 가 빠뜨린 단계를 경고가 아니라 멈춤으로 다룬다. 정적 대조다.

    ★ gh 와 원격이 필요해 흐름을 CI 에서 돌릴 수 없다(DECISIONS §164-2). 멈춤 줄이 지워지면 여기서 운다.
    """
    src = (ROOT / "tools/merge_batch.sh").read_text(encoding="utf-8")
    assert "--base part/infra --state open" in src and "squash 머지부터" in src, "열린 feat PR 을 멈추지 않는다(G-2)"
    assert "merge-base --is-ancestor origin/part/infra origin/dev" in src, "PR 없이 앞선 part/infra 를 멈추지 않는다(G-10)"
    assert "tr -cd 'A-Za-z0-9.-'" in src, "태그 입력의 깨진 바이트를 거르지 않는다(G-12)"
    # ★ 2026-09-23 (DECISIONS §220-4). 체크박스의 물음은 「판정이 움직였나」다 — 이제 판정 지문
    #   **한 파일**만 본다. 종전에는 web/data 까지 봐서 표출 파일 다섯을 멈춘 v0.35 가 「바뀐다」에 찍혔다.
    _line = src.split("out = changed(", 1)[1].split("\n", 1)[0]
    assert "segments.fingerprint.json" in _line and "web/data" not in _line and "data/processed" not in _line, \
        f"판정 아닌 변화를 산출물 변화로 체크한다(G-11 · §220-4): {_line}"


def _tty_block() -> str:
    src = (ROOT / "tools/merge_batch.sh").read_text(encoding="utf-8")
    assert "# >>> tty" in src and "# <<< tty" in src, "merge_batch 의 대화형 입력 구간 표지가 없다"
    return src.split("# >>> tty", 1)[1].split("# <<< tty", 1)[0]


def _reap(pid: int, timeout: float) -> bool:
    """자식을 거둔다. 시한을 넘기면 **죽이고** True 를 낸다.

    ★ 프로세스 그룹째 죽인다. `bash ask.sh` 는 하위 셸을 남기고, 실측에서
      한 번 호출에 `bash` 셋이 살아 있었다. 우두머리만 죽이면 나머지가
      고아로 남아 다음 실행까지 쌓인다 — Fox 의 기계에 1시간 11분 된
      찌꺼기가 그렇게 남아 있었다.
    """
    import os
    import signal
    import time

    end = time.time() + timeout
    while time.time() < end:
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return False
        if done == pid:
            return False
        time.sleep(0.05)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(pid), sig)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                break
        time.sleep(0.2)
        try:
            if os.waitpid(pid, os.WNOHANG)[0] == pid:
                break
        except ChildProcessError:
            break
    return True


def _read_until(fd: int, needle: bytes, timeout: float) -> bytes:
    """가상 터미널에서 `needle` 이 나올 때까지 읽는다. 시한을 넘기면 읽은 만큼 낸다.

    ★ 시계로 기다리지 않는 이유는 `_ask_in_pty` 안에 적었다.
    """
    import os
    import select
    import time

    out, end = b"", time.time() + timeout
    while needle not in out and time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            continue
        try:
            d = os.read(fd, 4096)
        except OSError:
            break
        if not d:
            break
        out += d
    return out


def _ask_in_pty(tmp_path, garbage: bytes, answer: bytes, slow: float = 0.5) -> str:
    """`slow` 는 자식이 `ask` 에 닿기까지 걸리는 시간이다 — **느린 기계를 흉내 낸다.**"""
    import os
    import pty

    sh = tmp_path / "ask.sh"
    sh.write_text("set -uo pipefail\n" + _tty_block() + f"\nsleep {slow}\n"
                  "if ask '진행?'; then echo RESULT=YES; else echo RESULT=NO; fi\n",
                  encoding="utf-8")
    pid, fd = pty.fork()
    if pid == 0:  # 자식 — 가상 터미널이 표준입력이다
        os.execvp("bash", ["bash", str(sh)])
    if garbage:
        os.write(fd, garbage)          # gh --watch 가 남긴 터미널 응답을 흉내 낸다 — 사람이 치기 전에 버퍼에 있다
    # ★ 2026-10-04 실측 (DECISIONS §395). 종전에는 `time.sleep(0.9)` 뒤에
    #   답을 밀어 넣었다 — 자식의 `sleep 0.5` 가 먼저 끝나 `flush_tty` 가
    #   돌 것이라는 **시계 가정**이다. 기계가 바쁘면 그 순서가 뒤집힌다:
    #   답이 먼저 버퍼에 들어가고 `flush_tty` 가 그것을 비워 버려서
    #   `read` 가 영영 안 끝난다. 같은 트리에서 verify 는 통과하고 봉인은
    #   실패했다(pytest 7분40초 → 13분54초 · 거의 두 배 느린 자리).
    #
    #   **시계가 아니라 신호를 기다린다.** 프롬프트는 `flush_tty` 가
    #   돌아온 **뒤에만** 찍힌다 — 그것을 보고 나서 답을 넣으면 기계
    #   속도와 무관하다. 깜빡이는 시험은 빨강보다 나쁘다. 빨강은 고치지만
    #   깜빡이는 「또 그거네」가 된다.
    out = _read_until(fd, b"[y/N]", timeout=20.0)
    assert b"[y/N]" in out, f"20초 안에 프롬프트가 안 떴다 — 자식이 멈췄다: {out!r}"
    os.write(fd, answer)
    # ★ 답이 나오면 바로 끝낸다. 종전에는 **무조건 5초**를 기다렸다 —
    #   호출 넷이면 20초다. 기다리는 시간은 깜빡일 틈이기도 하다.
    out += _read_until(fd, b"RESULT=", timeout=10.0)
    # ★ 2026-09-28 실측 (§284-5). 종전에는 `os.waitpid(pid, 0)` 이었다.
    #   **시간 제한이 없다.** 자식 bash 가 안 죽으면 영원히 기다린다.
    #   Fox 의 기계에서 실제로 났다 — `merge_batch --release` 의
    #   `dms seal --quick` 이 18분째 멈춰 있었고, 1시간 11분 된 `ask.sh`
    #   찌꺼기가 따로 둘 더 살아 있었다. **전에도 났고 아무도 몰랐다.**
    #
    #   영원히 매달릴 수 있는 시험은 그 자체가 결함이다. 빨강을 무한 대기로
    #   바꿔 놓고, 무한 대기는 사람이 죽이고, 죽이면 무엇이 틀렸는지 영영
    #   모른다. **빨강은 빨강으로 나와야 한다.**
    _stuck = _reap(pid, timeout=10.0)
    os.close(fd)
    assert not _stuck, ("가상 터미널 자식이 10초 안에 안 끝났다 — 죽였다. "
                        "`merge_batch` 의 tty 구간이 입력을 못 읽고 매달린다")
    hit = [ln for ln in out.decode("utf-8", "replace").splitlines() if "RESULT=" in ln]
    return hit[-1].split("RESULT=", 1)[1].strip() if hit else "(없음)"


OSC = b"\x1b]11;rgb:0c0c/0c0c/0c0c\x1b\\\x1b[30;1R"


def test_merge_batch_ask_survives_terminal_replies(tmp_path):
    """G-17 — 터미널 응답 바이트가 입력 버퍼에 있어도 사람이 친 y 를 읽는다. **가상 터미널로 실제로 흔든다.**"""
    assert _ask_in_pty(tmp_path, OSC + b"\n", b"y\n") == "YES", "응답 바이트를 답으로 읽는다 — 버퍼 비우기가 죽었다"
    assert _ask_in_pty(tmp_path, OSC, b"y\n") == "YES", "줄바꿈 없는 응답 조각이 y 에 붙어 판정을 깬다"
    assert _ask_in_pty(tmp_path, OSC, b"n\n") == "NO", "n 을 y 로 읽는다"
    assert _ask_in_pty(tmp_path, b"", b"\n") == "NO", "빈 답을 y 로 읽는다"
    # ★ 2026-10-04 (DECISIONS §395). **느린 기계를 여기서 흉내 낸다.**
    #   옛 판은 `자식이 ask 에 닿기까지 1.5s` 에서 매달렸다(실측). 깜빡이를
    #   고치고 나서 그 자리를 안 재면, 다음에 누가 `time.sleep` 으로
    #   되돌려도 평소에는 아무도 모른다 — 바쁜 날에만 운다.
    assert _ask_in_pty(tmp_path, OSC, b"y\n", slow=2.0) == "YES", (
        "자식이 느리면 답이 `flush_tty` 에 먹힌다 — 시계로 기다리고 있다")


def test_merge_batch_ask_reads_piped_answers(tmp_path):
    """파이프로 넘긴 답(run_final 의 릴리즈 질문)은 터미널이 아니라 stdin 에서 읽는다."""
    sh = tmp_path / "pipe.sh"
    sh.write_text("set -uo pipefail\n" + _tty_block() + "\nask a && echo Y1 || echo N1\nask b && echo Y2 || echo N2\n"
                  "t=$(read_answer 'tag: '); echo \"T=$t\"\n", encoding="utf-8")
    r = subprocess.run(["bash", str(sh)], input="y\nn\nv0.14\n", capture_output=True, text=True)
    assert r.stdout.split() == ["Y1", "N2", "T=v0.14"], r.stdout + r.stderr


def test_seal_refuses_uncommitted_tracked_files(tmp_path):
    """§180-7 — 커밋 안 된 추적 파일이 있으면 봉인하지 않는다. 봉인 자신 · 생성 매니페스트만 예외다. **실제 git 저장소로.**"""
    dms = _tool("dms")

    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "a@b")
    git("config", "user.name", "k2")
    for rel in ("src/x.py", "data/dms/SEAL.json", "data/processed/_manifest.json", "docs/a.md"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("0\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base")
    assert dms.uncommitted(tmp_path) == [], "깨끗한 트리를 더럽다고 한다"
    (tmp_path / "data/dms/SEAL.json").write_text("1\n", encoding="utf-8")
    (tmp_path / "data/processed/_manifest.json").write_text("1\n", encoding="utf-8")
    (tmp_path / "untracked.txt").write_text("x\n", encoding="utf-8")
    assert dms.uncommitted(tmp_path) == [], "봉인 · 생성 매니페스트 · 추적 밖 파일은 막지 않는다"
    (tmp_path / "src/x.py").write_text("1\n", encoding="utf-8")
    assert dms.uncommitted(tmp_path) == ["src/x.py"], "커밋에서 빠진 코드를 못 잡는다 — L2d 의 normalize_raw"
    src = (ROOT / "tools/dms.py").read_text(encoding="utf-8")
    assert "dirty = uncommitted()" in src.split("def cmd_seal", 1)[1].split("run_enforcers", 1)[0], "cmd_seal 이 검사를 안 부른다"


def test_no_tool_creates_seal_tags():
    """§180-8 — 태그는 릴리즈(vX.Y)에만. 저장소 도구가 봉인 태그를 만들지 않는다."""
    import re
    pat = re.compile(r"""git\s+tag\s+(?:-a\s+|-f\s+)*["']?seal/""")
    hits = []
    for f in sorted((ROOT / "tools").rglob("*")) + sorted((ROOT / ".github").rglob("*")):
        if f.is_file() and f.suffix in (".sh", ".py", ".yml", ".yaml"):
            for i, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pat.search(ln):
                    hits.append(f"{f.relative_to(ROOT)}:{i}")
    assert not hits, f"봉인 태그를 만든다 — {hits}"
    assert pat.search('git tag "seal/2026-09-17-l2d"'), "프로브가 죽었다 — 옛 스크립트의 형태를 못 잡는다"


def test_verify_skips_are_real_skips():
    """§180-9 — verify 의 `note`(생략)는 **실제로 못 돈 것**만. 보고용 한 줄을 생략 칸에 두지 않는다."""
    import re
    src = (ROOT / "tools/verify.sh").read_text(encoding="utf-8")
    names = re.findall(r'^\s*note\s+"([^"]+)"', src, re.M)
    assert names, "프로브가 죽었다 — note 호출을 못 찾는다"
    assert "흡수 대상" not in names, "보고용 release_brief 줄이 생략 칸으로 돌아왔다"
    # ★ 2026-09-22 (DECISIONS §218-5). 갈래가 건너뛰는 단계는 **이름마다** 한 행을 남긴다
    #   (`verify.sh` 의 `evidence_check`). 그래서 묶음 이름 「파이프라인 전량 + golden」이
    #   단계 이름 넷으로 펴졌고, 내비 갈래도 셋이 됐다. 못 도는 조건은 그대로 둘이다 — npm 부재 · --fast/raw 부재.
    #   「JS 부팅 스모크」는 옛 지도 철거로 단계째 없어졌다.
    # ★ 2026-09-28 (DECISIONS §279-4). 「내비 린트」가 넷째다. 못 도는 조건은
    #   위 셋과 같다 — npm 이 없으면 eslint 도 없다.
    # ★ 2026-09-28 (DECISIONS §285-3). 다섯째·여섯째. 못 도는 조건은 **raw
    #   부재** 하나다. 둘 다 레이크의 실물을 읽는다 —
    #     취입 계약 실물    대장 선언 ↔ raw 파일 · 컬럼 · 건수 · 좌표계(.prj)
    #     대장 스키마↔실물  raw 에서 스키마를 읽어 대장과 대조 (MASTER §18-12)
    #   **덮개가 있다.** 같은 도구의 레이크 불필요 절반을 CI 가 돈다 —
    #   `contract --declared`(무계약 · 모르는 키 · 미선언 좌표계)가 그것이다.
    # ★ 2026-10-02 (DECISIONS §349) **정정.** 여기 「`ledger_schema --check` 는
    #   덮개가 없다. 실물에서 읽는 것이 전부라 대장만 보고 할 수 있는 절반이
    #   없다」가 적혀 있었다. 사흘 뒤 §340-4 가 같은 것을 뒤집었는데
    #   (「세는 대상은 **대장에 적혀 있는 값**이고 `sources.yaml` 은 저장소 안에
    #   있다」) **이 문장은 안 고쳤고**, 그래서 「덮개 없음」이 선언으로 살아남아
    #   그 자리를 영구 사각지대로 뒀다. §346 과 같은 족이다.
    #   지금은 덮개가 둘이다 — `ledger_cross.py`(약속 ↔ 실측 57쌍 4축) ·
    #   `ledger_schema.ratchet_values`(대장에 앉은 못 믿을 값 `UNREADABLE`).
    #   남은 것은 **실물을 읽어야만 아는 드리프트** 하나다.
    allowed = {"내비 환경 = CI", "내비 린트", "내비 타입 검사", "내비 단위 시험",
               "파이프라인 전량", "golden 판정 불변", "golden 게이트 해제 경로",
               "커밋된 web/data 가 최신인가",
               "취입 계약 실물", "대장 스키마↔실물",
               # ★ 2026-09-28 (§289). 파이프라인 산출물(processed/*.gpkg)을 읽는다.
               #   레이크 없는 기계에서는 산출물이 없다 — CI 도 같다.
               "폭 교차대조",
               # ★ 2026-10-03 (DECISIONS §376). 트리 전수는 `gitleaks` 바이너리를
               #   쓴다 — 없는 기계에서는 `note` 로 **미측정을 센다.** 조용히
               #   빠지면 「검사했다」와 「검사기가 없었다」가 같은 초록이 된다.
               #   바이너리 없이도 막히는 한 모양은 `UUID_IN_TRACKED` 가 든다.
               "비밀값 — 작업 트리 전수"}
    assert set(names) <= allowed, f"생략 사유가 새로 생겼다 — 못 도는 조건인지 보고 여기 적는다: {sorted(set(names) - allowed)}"
    brief = (ROOT / "tools/merge_batch.sh").read_text(encoding="utf-8")
    assert "tools/release_brief.py --base main --md" in brief, "release_brief 가 릴리즈 흐름에서도 빠졌다 — 표가 사라진다"
