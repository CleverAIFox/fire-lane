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

import functools
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_STATE: dict[str, Any] = {}


@functools.lru_cache(maxsize=1)
def local_env_names() -> tuple[str, ...]:
    """git 이 **저장소를 가리키려고** 쓰는 환경변수 전부 — 손으로 안 적는다. `git rev-parse --local-env-vars` 가 정본이다. (PLAN #200)

    ★ 비면 죽는다 — 조용히 아무것도 안 비우면 아래 환경 정리는 없는 것과 같다.
    """
    r = subprocess.run(["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True, check=True, timeout=30)
    got = tuple(x for x in r.stdout.split() if x.startswith("GIT_"))
    assert "GIT_DIR" in got, f"git 이 저장소 환경변수를 안 냈다: {r.stdout!r}"
    return got


def mirror_tree(dest: Path, copy: tuple[str, ...] = (), replace: dict[str, str] | None = None, root: Path | None = None) -> Path:
    """실물 저장소의 **거울**을 `dest` 에 짓는다 — 추적 파일을 제자리에서 고쳤다 되돌리는 시험의 자리다. (PLAN #219)

    `copy` 에 든 경로(파일 · 디렉터리)는 **진짜 복사본**이고 나머지 최상위는 전부 심링크다(`.git` · `.venv` 는 뺀다). `replace` 의 `상대경로 → 본문` 은 복사본의 그 파일을 덮는다.
    ★ 파일이 제 위치로 뿌리를 찾는 도구(`Path(__file__).resolve()`)는 **그 도구를 복사본으로 둬야** 거울 뿌리를 본다 — 심링크는 실물로 풀린다.
    ★ 진짜 `docs/MASTER.md` · `src/.../width.py` · `.code_fingerprint` 를 고쳤다 되돌리면 병렬로 도는 다른 시험이 중간 상태를 읽는다(2026-11-10 64개 빨강 · 한 번은 0바이트)."""
    root = ROOT if root is None else root       # 기본 인자로 묶으면 정의 시점에 굳는다(§571)
    want = {tuple(Path(c).parts) for c in copy} | {tuple(Path(r).parts) for r in (replace or {})}

    def build(src: Path, dst: Path, prefix: tuple[str, ...]) -> None:
        dst.mkdir(parents=True, exist_ok=True)
        for e in sorted(src.iterdir()):
            parts = (*prefix, e.name)
            if not prefix and e.name in (".git", ".venv"):
                continue
            if e.name == "__pycache__":
                continue
            if parts in want:
                if e.is_dir():
                    shutil.copytree(e, dst / e.name, ignore=shutil.ignore_patterns("__pycache__"))
                else:
                    shutil.copy2(e, dst / e.name)
            elif any(w[: len(parts)] == parts for w in want) and e.is_dir():
                build(e, dst / e.name, parts)
            else:
                (dst / e.name).symlink_to(e)

    build(root, dest, ())
    for rel, text in (replace or {}).items():
        (dest / rel).write_text(text, encoding="utf-8")
    return dest


def _git(root: Path, *args: str) -> str:
    """★ 물려받은 `GIT_DIR` 등을 **지우고** 부른다 — 세션 훅은 `conftest` 의 자동 픽스처보다 먼저 돌아 그쪽이 못 막는다. (PLAN #200)

    worktree 의 `pre-push` 가 `GIT_DIR=<본>/.git/worktrees/<이름>` 을 물려주면 `cwd` 가 어디든 git 이 그 저장소를 본다.
    `cwd=root` 의 저장소를 찾게 두는 것이 이 가드가 묻는 「이 트리」다.
    """
    drop = set(local_env_names())
    env = {k: v for k, v in os.environ.items() if k not in drop}
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False, timeout=60, env=env)
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


_WRITES: dict[tuple[str, str], str] = {}     # (추적 파일, 시험) → 어떻게 썼나 — 세션 **도중**에 쓴 것(되돌려도 남는다). 자식의 쓰기는 `… · 자식` 으로 적힌다
READS: dict[str, set[str]] = {}               # 시험 파일 → 그 시험이 연 추적 파일들(세션 · 수집 중 읽기는 `fsaudit.SESSION` 칸)

_AUDIT_SITE = str(Path(__file__).resolve().parent / "audit_site")


def _load_fsaudit():
    """파이썬 감사 훅 한 벌 — 읽기(#218) · 쓰기(#219) · 자식 프로세스(#219 ①)가 같은 이벤트다. 경로로 연다(`sys.path` 를 안 만진다 — `test_layering`)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("fsaudit", Path(_AUDIT_SITE) / "fsaudit.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fsaudit"] = mod
    spec.loader.exec_module(mod)
    return mod


fsaudit = sys.modules.get("fsaudit") or _load_fsaudit()


def _sink(kind: str, rel: str, test: str, event: str) -> None:
    """부모 프로세스의 감사 이벤트 → 쓰기는 `_WRITES`(시험 id 로) · 읽기는 `READS`(시험 파일로)."""
    if kind == "w":
        _WRITES.setdefault((rel, test.split(" ")[0] or "(시험 밖 · 수집 · 세션)"), event)
    else:
        READS.setdefault(fsaudit.test_file_of(test), set()).add(rel)


def _parent_test() -> str:
    """지금 도는 시험 id. 수집 중이면 수집하는 모듈(그 모듈의 import 가 읽는 것이 그 시험 파일 몫이다)."""
    # ★ 수집 중이면 환경변수보다 **먼저** 본다 — 중첩 세션은 바깥 시험의 `PYTEST_CURRENT_TEST` 를 물려받아 그것이 낡은 채 남는다.
    return _STATE.get("collecting") or os.environ.get("PYTEST_CURRENT_TEST", "")


def pytest_collectstart(collector) -> None:
    """수집 중 모듈 import 가 읽는 파일을 그 시험 파일에 붙인다(모듈 첫 줄의 `import firelane.x` 도 읽기다)."""
    if type(collector).__name__ == "Module" and not hasattr(collector.config, "workerinput"):
        _STATE["collecting"] = str(collector.path.name)


def pytest_runtest_logstart(nodeid, location) -> None:
    _STATE["collecting"] = ""


def pytest_collection_finish(session) -> None:
    _STATE["collecting"] = ""


WRITE_ALLOW: dict[str, str] = {}      # 추적 파일 → 사유. **비어 있다** — 시험이 추적 파일을 쓰기로 열 정당한 이유가 아직 없다(복사본 `mirror_tree` 에서 한다)


def _drain_children() -> None:
    """자식 프로세스가 로그에 적은 것을 부모의 표로 합친다."""
    d = _STATE.get("audit_dir")
    if not d:
        return
    for kind, rel, test, event in fsaudit.read_log(d):               
        if kind == "w":
            if rel not in WRITE_ALLOW:
                _WRITES.setdefault((rel, test), f"{event} · 자식")
        else:
            READS.setdefault(test, set()).add(rel)


def pytest_sessionstart(session) -> None:
    if hasattr(session.config, "workerinput"):          # xdist 일꾼
        return
    _STATE["before"] = snapshot()
    _STATE["root"] = ROOT
    _STATE["tracked"] = set(_git(ROOT, "ls-files", "-z").split("\0")) - {""}
    _STATE["audit"] = True
    if not _STATE.get("hooked"):
        hook = fsaudit.make_hook(str(ROOT), _STATE["tracked"], lambda *a: _STATE.get("audit") and _sink(*a), _parent_test)
        sys.addaudithook(hook)             # 감사 훅은 뺄 수 없다 — `_STATE["audit"]` 가 켜고 끈다
        _STATE["hooked"] = True
    # ★ 자식 프로세스에 훅을 물린다(#219 ①) — 이 세션이 띄우는 파이썬 전부가 `sitecustomize` 로 같은 훅을 달고 로그에 적는다.
    #   중첩 세션(시험 안에서 도는 pytest)은 **자기 디렉터리를 새로** 만든다 — 바깥 로그에 안쪽 저장소 이름이 섞이지 않는다.
    audit_dir = tempfile.mkdtemp(prefix="fl-audit-")
    fsaudit.prepare(audit_dir, str(ROOT), _STATE["tracked"])
    _STATE["audit_dir"] = audit_dir
    os.environ["FIRE_LANE_AUDIT_DIR"] = audit_dir
    os.environ["PYTHONPATH"] = os.pathsep.join(x for x in (_AUDIT_SITE, os.environ.get("PYTHONPATH", "")) if x)


def pytest_sessionfinish(session, exitstatus) -> None:
    if hasattr(session.config, "workerinput") or "before" not in _STATE:
        return
    _STATE["audit"] = False
    _drain_children()
    out_path = os.environ.get("FIRE_LANE_READS_OUT")      # 읽기 실측 길(`testpick --measure-reads`)만 켠다 — 평소엔 안 쓴다
    if out_path:
        import json
        Path(out_path).write_text(json.dumps({k: sorted(v) for k, v in sorted(READS.items())}, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(_STATE.pop("audit_dir", ""), ignore_errors=True)
    bad = changed(_STATE["before"], snapshot())
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    say = tr.write_line if tr else print
    if _WRITES:
        say(f"✗ 시험이 추적 파일을 **제자리에서 쓰기로 열었다** — {len(_WRITES)}건 (되돌렸어도 병렬로 읽는 시험이 중간 상태를 본다 · 이 세션은 실패다)")
        for (rel, test), ev in sorted(_WRITES.items())[:30]:
            say(f"    {rel}  ← {test}  ({ev})")
        say("  복사본에서 돌려라 — `tracked_guard.mirror_tree` 가 거울을 짓는다(`tests/test_refcheck_paths.py` · `test_doc_fsck.py` 가 본보기).")
        _WRITES.clear()
        session.exitstatus = 1
    if not bad:
        return
    lines = [f"✗ 시험이 추적 파일을 바꿨다 — {len(bad)}개 (시험은 초록이어도 이 세션은 실패다)"] + [f"    {n}" for n in bad[:30]]
    lines.append("  `git diff` 로 무엇이 바뀌었나 보고, 쓴 시험 · 도구를 찾아라. 임시 디렉터리에서 돌려야 하는 시험이면 그렇게 고쳐라(`tests/test_fix_door.py` 가 본보기다).")
    for ln in lines:
        say(ln)
    session.exitstatus = 1
