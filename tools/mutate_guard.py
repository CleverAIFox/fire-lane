#!/usr/bin/env python3
"""
mutate_guard.py — **흔든 파일을 반드시 되돌린다.** 신호에도.

부류  절차

── 왜 생겼나 (2026-10-08 · DECISIONS §435) ─────────────────────
`tools/mutate.py` 는 과녁을 **제자리에서** 바꿔 쓰고 `finally` 로 되돌린다.
§398-6 이 그 창을 적어 두었다 — 「되돌리기는 보장되지만 그 창 안에 다른 관문을
돌리면 그 관문이 흔들린 사본을 읽는다」.

★ **그 「보장」이 참이 아니다.** `finally` 는 예외에는 돌지만 **신호에는 안 돈다.**
  이 배치에서 돌연변이 측정을 시간 상한으로 끊었더니(`SIGTERM`)
  `tools/sealcov.py` 에 `not` 하나가 지워진 채로 남았다. 그 뒤 일어난 일 —

```
sealcov --selftest  이 「밑동에서 이미 빨갛다」가 됐다   → 붙잡이 0
그 도구의 돌연변이 넷이 전부 「못 쟀다」로 떨어졌다      → 장부가 줄었다
`--write` 가 줄어든 수를 **조이는 쪽으로** 받아적었다   → 손으로 적은 수가 덮였다
```

**흔든 트리가 살아남으면 그 뒤의 모든 측정이 거짓이 된다.** 그리고 그 거짓은
「줄었다」로 보이므로 **래칫이 조용히 조여진다** — 가장 나쁜 방향이다.

── 무엇을 하나 ─────────────────────────────────────────────────
흔드는 동안의 원본을 적어 두고, **나가는 길 전부**에서 되돌린다 —
정상 종료(`atexit`) · `SIGTERM` · `SIGINT` · `SIGHUP`.

★ `SIGKILL` 은 못 잡는다. 못 잡는다는 사실을 여기 적는다(R23) — 그때는
  `git status` 에 흔든 파일이 보이고, 그것이 유일한 단서다.

IN    없음 (호출자가 경로와 원본을 준다)
OUT   없음 (파일 복원)
PARAM 없음
밖    **무엇을 흔드나는 안 본다.** 돌연변이를 고르고 붙잡이를 돌리는 것은
      `mutate.py` 의 일이고, 여기는 「되돌려졌는가」 하나만 든다.
"""
from __future__ import annotations

import atexit
import os
import signal
import sys
from pathlib import Path

#: 지금 흔들려 있는 파일 → 원본. **비어 있어야 정상이다.**
_IN_FLIGHT: dict[Path, str] = {}

#: 되돌린 파일 수. 신호로 되돌린 적이 있으면 0 이 아니다 — 자기검사가 본다.
restored = 0


def hold(path: Path, original: str) -> None:
    """흔들기 **전에** 원본을 맡긴다."""
    _IN_FLIGHT[Path(path)] = original


def release(path: Path) -> None:
    """정상 복원이 끝난 뒤 맡긴 것을 거둔다."""
    _IN_FLIGHT.pop(Path(path), None)


def restore_all() -> int:
    """맡긴 전부를 되돌린다. 되돌린 수를 낸다. **두 번 불러도 안전하다.**"""
    global restored
    n = 0
    for p, orig in list(_IN_FLIGHT.items()):
        try:
            if p.read_text(encoding="utf-8") != orig:
                p.write_text(orig, encoding="utf-8")
                n += 1
        except OSError:
            # ★ 되돌리기가 실패해도 **다음 파일은 시도한다.** 하나가 막혀
            #   나머지를 포기하면 트리에 흔든 사본이 더 남는다.
            pass
        _IN_FLIGHT.pop(p, None)
    restored += n
    return n


def _on_signal(sig: int, _frame) -> None:
    n = restore_all()
    if n:
        print(f"\n★ 신호 {sig} — 흔든 파일 {n}개를 되돌렸다", file=sys.stderr)
    # ★ 기본 동작으로 죽는다. 종료코드를 삼키면 부르는 쪽이 성공으로 본다.
    signal.signal(sig, signal.SIG_DFL)
    os.kill(os.getpid(), sig)


def install() -> None:
    """나가는 길 전부에 복원을 건다. **여러 번 불러도 안전하다.**"""
    atexit.register(restore_all)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(s, _on_signal)
        except (ValueError, OSError):
            # ★ 주 스레드가 아니면 못 건다. 그때는 `atexit` 만 남는다.
            pass


def selftest() -> int:
    """★ 맡긴 것이 **되돌아오는가.** 신호 경로는 하위 프로세스로 민다."""
    import subprocess
    import tempfile

    bad = []
    with tempfile.TemporaryDirectory() as d:
        q = Path(d) / "t.py"
        q.write_text("x = 1\n", encoding="utf-8")
        hold(q, "x = 1\n")
        q.write_text("x = 2\n", encoding="utf-8")
        if restore_all() != 1:
            bad.append("흔든 파일을 되돌렸다고 안 센다")
        if q.read_text(encoding="utf-8") != "x = 1\n":
            bad.append("되돌리지 못했다")
        if restore_all() != 0:
            bad.append("두 번 불렀을 때 또 센다 — 멱등이 아니다")
        # ★ 안 바뀐 파일은 **쓰지 않는다** — 쓰면 mtime 이 움직여 다른 관문이 깬다
        hold(q, "x = 1\n")
        if restore_all() != 0:
            bad.append("안 바뀐 파일을 되돌렸다고 센다")

        # ── 신호 경로 — 하위 프로세스를 띄워 SIGTERM 으로 끊는다
        # ★ 자리를 **`cwd` 로** 준다. `sys.path` 조작을 코드 문자열에 적으면
        #   `tests/test_layering.py` 가 그 글자를 이 파일의 것으로 세고,
        #   `PYTHONPATH` 를 손대면 `tools/env_check.py` 가 「paths.py 밖에서
        #   os.environ 을 읽는다」로 운다. `python -c` 는 cwd 를 먼저 보므로
        #   둘 다 안 건드리고 자리를 줄 수 있다.
        code = (
            "import time,pathlib\n"
            "import mutate_guard as g\n"
            f"p = pathlib.Path({str(q)!r})\n"
            "g.install(); g.hold(p, 'x = 1\\n')\n"
            "p.write_text('x = 9\\n', encoding='utf-8')\n"
            "print('ready', flush=True)\n"
            "time.sleep(30)\n"
        )
        pr = subprocess.Popen([sys.executable, "-c", code],
                              cwd=str(Path(__file__).parent),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True)
        try:
            if (pr.stdout.readline() or "").strip() != "ready":
                bad.append("하위 프로세스가 흔들지 못했다")
            else:
                if q.read_text(encoding="utf-8") != "x = 9\n":
                    bad.append("하위 프로세스가 흔든 것이 안 보인다")
                pr.terminate()
                pr.wait(timeout=20)
                if q.read_text(encoding="utf-8") != "x = 1\n":
                    bad.append("**SIGTERM 에 되돌리지 않았다** — 이 파일의 존재 이유다")
        except subprocess.TimeoutExpired:
            bad.append("하위 프로세스가 신호에 안 죽었다")
            pr.kill()
        finally:
            if pr.poll() is None:
                pr.kill()

    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 복원 · 멱등 · 무변경 무쓰기 · **SIGTERM 복원**")
    return 1 if bad else 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else 0)
