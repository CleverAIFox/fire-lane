"""파이썬 감사 훅 하나로 **추적 파일의 읽기 · 쓰기**를 보고, 그 훅을 **자식 프로세스에 물려준다.**  (PLAN #218 · #219 · 한 설계)

IN    파이썬 감사 이벤트(`open` · `os.remove` · `os.rename` · `os.replace` · `shutil.copyfile`) · 환경변수 `FIRE_LANE_AUDIT_DIR`
OUT   `FIRE_LANE_AUDIT_DIR/log` 에 한 줄씩(`종류\\t경로\\t시험 파일\\t이벤트`) — 자식이 낸다. 부모는 메모리에 쌓는다.
PARAM 없음
TAG   `FIRE_LANE_AUDIT_TAG` 가 있으면 시험 파일 대신 그 이름이 꼬리표다 — 시험이 아닌 사슬(`tools/fix.sh` 의 단계)이 같은 훅으로 의존을 잴 때 쓴다(PLAN #220)
밖    **파이썬이 아닌 자식**(`sed -i` · `cp` · `git checkout`)은 못 본다. `os.listdir` · `glob` 같은 **디렉터리 읽기**는 안 센다(그 뒤에 파일을 열면 그 열기가 센다).
      `dir_fd` 로 지우는 `rmtree` 의 내부도 못 본다. 이미 import 된 모듈은 다시 안 읽히니 **한 프로세스에 시험 파일 여럿이면 읽기가 뒤 파일에 안 붙는다**(그래서 읽기 실측은 파일마다 프로세스를 따로 쓴다).

★ 왜 한 모듈인가 — ② 읽기(어느 시험이 어느 파일을 읽나 → 푸시 전에 돌릴 시험을 고른다)와 ③ 쓰기(시험이 추적 파일을 쓰나 → 세션 실패)는 같은 이벤트의 두 면이고,
  프로세스 경계를 넘는 길(`sitecustomize` 가 `PYTHONPATH` 로 훅을 물려준다)도 둘에 똑같이 필요하다. 두 번 짜면 한쪽이 낡는다.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Callable

SESSION = "(세션)"          # 시험도 수집도 아닌 때의 읽기 — 어느 시험 몫도 아니다(conftest · 플러그인)
_busy = False


def classify(event: str, args: tuple) -> tuple[str, object] | None:
    """감사 이벤트 → (`r` 읽기 | `w` 쓰기, 경로). 보지 않는 이벤트면 None. 순수 함수."""
    if event == "open":
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_TRUNC | os.O_APPEND)))
        return ("w" if writing else "r"), path
    if event in ("os.remove", "os.rename", "os.replace"):
        fds = args[1:2] if event == "os.remove" else args[2:4]
        if any(fd is not None and fd != -1 for fd in fds):          # `rmtree` 가 열린 디렉터리 기준 상대 이름으로 지운다
            return None
        return "w", args[0]
    if event == "shutil.copyfile":
        return "w", args[1]
    return None


def rel_of(path: object, root: str) -> str | None:
    """`root` 아래의 상대 경로. 밖이거나 경로가 아니면 None."""
    if not isinstance(path, (str, bytes, os.PathLike)):
        return None
    rel = os.path.relpath(os.path.abspath(os.fsdecode(path)), root)
    if rel.startswith(".."):
        return None
    head, tail = os.path.split(rel)
    if tail.endswith(".pyc") and os.path.basename(head) == "__pycache__":
        # 바이트코드 캐시가 유효하면 인터프리터는 `.py` 를 **안 연다**(`.pyc` 만 연다) — 캐시 파일을 원본 소스로 되돌려 읽기로 센다
        return os.path.join(os.path.dirname(head), tail.split(".")[0] + ".py")
    return rel


def test_file_of(current: str) -> str:
    """`PYTEST_CURRENT_TEST` (`tests/test_x.py::name (call)`) → 시험 파일 이름. 비면 `SESSION`."""
    head = current.split(" ")[0].split("::")[0]
    return head.rsplit("/", 1)[-1] if head else SESSION


def make_hook(root: str, tracked: set[str], sink: Callable[[str, str, str, str], None],
              test_of: Callable[[], str] = lambda: os.environ.get("FIRE_LANE_AUDIT_TAG") or test_file_of(os.environ.get("PYTEST_CURRENT_TEST", ""))) -> Callable[[str, tuple], None]:
    """감사 훅을 짓는다. `sink(종류, 경로, 시험 파일, 이벤트)` 가 받는다. 훅은 시험을 죽이지 않는다(못 읽은 한 건이 세션을 깨면 안 된다)."""
    def hook(event: str, args: tuple) -> None:
        global _busy
        if _busy:
            return
        try:
            got = classify(event, args)
            if got is None:
                return
            kind, path = got
            rel = rel_of(path, root)
            if rel is None or rel not in tracked:
                return
            _busy = True
            try:
                sink(kind, rel, test_of(), event)
            finally:
                _busy = False
        except Exception:
            return
    return hook


def prepare(audit_dir: str, root: str, tracked: set[str]) -> None:
    """자식이 읽을 것을 적어 둔다 — 뿌리 · 추적 파일 목록 · 빈 로그. 부모(세션 시작)가 부른다."""
    os.makedirs(audit_dir, exist_ok=True)
    with open(os.path.join(audit_dir, "root.txt"), "w", encoding="utf-8") as f:
        f.write(root)
    with open(os.path.join(audit_dir, "tracked.txt"), "w", encoding="utf-8") as f:
        f.write("\0".join(sorted(tracked)))
    open(os.path.join(audit_dir, "log"), "w", encoding="utf-8").close()


def read_log(audit_dir: str) -> list[tuple[str, str, str, str]]:
    """자식들이 쓴 줄 → (종류, 경로, 시험 파일, 이벤트)."""
    out = []
    try:
        with open(os.path.join(audit_dir, "log"), encoding="utf-8", errors="replace") as f:
            for ln in f:
                p = ln.rstrip("\n").split("\t")
                if len(p) == 4:
                    out.append((p[0], p[1], p[2], p[3]))
    except OSError:
        pass
    return out


def install_child() -> None:
    """`sitecustomize` 가 부른다 — 환경에 감사 디렉터리가 있으면 훅을 달고 로그에 한 줄씩 **덧붙인다**(덧붙이기 모드 한 번의 쓰기라 병렬 자식이 섞여도 줄이 안 찢어진다)."""
    d = os.environ.get("FIRE_LANE_AUDIT_DIR")
    if not d:
        return
    try:
        with open(os.path.join(d, "root.txt"), encoding="utf-8") as f:
            root = f.read()
        with open(os.path.join(d, "tracked.txt"), encoding="utf-8") as f:
            tracked = {x for x in f.read().split("\0") if x}
        log = os.path.join(d, "log")
    except OSError:
        return
    seen: set[tuple[str, str, str]] = set()

    def sink(kind: str, rel: str, test: str, event: str) -> None:
        key = (kind, rel, test)
        if key in seen:
            return
        seen.add(key)
        with open(log, "a", encoding="utf-8") as f:            # 한 줄을 닫을 때 한 번에 쓴다 — 병렬 자식이 섞여도 줄이 안 찢어진다
            f.write(f"{kind}\t{rel}\t{test}\t{event}\n".replace("\r", " "))
    sys.addaudithook(make_hook(root, tracked, sink))
