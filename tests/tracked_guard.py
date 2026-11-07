"""시험 세션이 **추적 파일을 조용히 바꾸지 않았는가** — 세션 앞뒤로 지문을 비교한다.  (Zm39 · DECISIONS §580)

IN    git 의 추적 파일(작업 트리 쪽 내용)
OUT   없음. 바뀐 게 있으면 **파일 목록을 찍고 세션을 실패시킨다.**
PARAM 없음 — 끄는 스위치를 일부러 두지 않았다(`FIRE_LANE_HOOK_PROBE` 가 영구 우회가 됐던 사고, `.githooks/pre-commit` 머리말).
밖    **무엇이 썼는지는 안 가린다**(시험인가 · 부르는 도구인가). 바뀐 파일 이름이 단서다.
      **추적 안 된 파일 · 무시된 산출물**은 안 본다(`data/processed` 등은 시험이 만드는 것이 정상이다).

★ 왜 생겼나 — 같은 사고가 두 번 났다. ① 평가셋 55행이 합성 데이터로 덮였다(기본 인자 경로 · §571). ② `test_fix_door` 가 실제 트리에서
  수리 문 `tools/fix.sh` 를 통째로 돌아 기획서 날짜와 래칫 상수를 바꿨다(§580). 둘 다 **시험이 초록인 채** 추적 파일이 바뀌었고, 사람이 `git status`
  를 우연히 봐서 알았다. 원인이 다른 두 사고를 한 장치가 문다 — 길(기본 인자 · 수리 문 · 생성기 · 전역 상태)을 가리지 않고 **결과**를 본다.

★ 지문은 `git diff HEAD` 로 **이미 더러운 파일**만 해시한다 — 2천여 추적 파일 전부를 읽지 않는다(세션당 0.1초대).
  세션 전에 더러웠던 파일이 세션 중에 **더 바뀌어도** 잡는다(전후 해시 비교).

★ xdist 일꾼에서는 안 돈다 — 지휘자만 본다(일꾼마다 보면 한 파일이 N번 보고된다).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_STATE: dict[str, dict[str, str]] = {}


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 가 실패했다 — {r.stderr.strip()[:120]}")
    return r.stdout


def snapshot(root: Path = ROOT) -> dict[str, str]:
    """HEAD 와 다른 추적 파일 → 내용 해시(지워졌으면 `<삭제>`)."""
    out: dict[str, str] = {}
    for name in _git(root, "diff", "HEAD", "--name-only", "-z").split("\0"):
        if not name:
            continue
        p = root / name
        out[name] = _git(root, "hash-object", "--", name).strip() if p.is_file() else "<삭제>"
    return out


def changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """전후로 달라진 파일. 세션 전에는 깨끗했다가 더러워진 것 · 더러웠다가 되돌린 것 · 더러운 채 또 바뀐 것 전부."""
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


def pytest_sessionstart(session) -> None:
    if hasattr(session.config, "workerinput"):          # xdist 일꾼
        return
    _STATE["before"] = snapshot()


def pytest_sessionfinish(session, exitstatus) -> None:
    if hasattr(session.config, "workerinput") or "before" not in _STATE:
        return
    bad = changed(_STATE["before"], snapshot())
    if not bad:
        return
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    lines = [f"✗ 시험이 추적 파일을 바꿨다 — {len(bad)}개 (시험은 초록이어도 이 세션은 실패다)"] + [f"    {n}" for n in bad[:30]]
    lines.append("  `git diff` 로 무엇이 바뀌었나 보고, 쓴 시험 · 도구를 찾아라. 임시 디렉터리에서 돌려야 하는 시험이면 그렇게 고쳐라(`tests/test_fix_door.py` 가 본보기다).")
    for ln in lines:
        (tr.write_line if tr else print)(ln)
    session.exitstatus = 1
