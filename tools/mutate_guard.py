#!/usr/bin/env python3
"""
mutate_guard.py — **흔든 파일을 반드시 되돌린다.** 신호에도.

★ 2026-10-14 (DECISIONS §521). 종전에 머리말이 **`부류  절차`** 를 적고
  있었다. 지금은 `--pending` 이 verify · CI 에서 돌아 **흔들다 죽은 자국**을
  막으므로 관문이고, **관문의 부류는 적지 않는다** — `toolclass` 가 「누가
  부르나」로 **도출한다**(`tests/test_toolclass.py::test_gates_are_derived_not_declared`).
  적으면 그 도출과 선언이 갈린다. 라이브러리 역할은 그대로다 — `mutate.py`
  가 import 한다.

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

#: 맡긴 것을 **디스크에도** 둔다.
#: ★ 2026-10-14 (DECISIONS §521). 위 머리말이 「`SIGKILL` 은 못 잡는다 …
#:   그때는 `git status` 에 흔든 파일이 보이고 **그것이 유일한 단서**다」로
#:   그 구멍을 적어 두고 **아무도 그 단서를 안 읽게** 뒀다. 2026-10-13 에
#:   `tools/widthcross.py` 가 흔들린 채 남아 그 뒤 전수 verify 가 통째로
#:   거짓이 됐다 — `OVERCLAIM_SOFT` 32 → 39 가 그 수고, 다음 판이 **제가
#:   올린 줄 알고** 빨갰다.
#: ★ 메모리는 `SIGKILL` 에 사라지지만 **파일은 남는다.** 그래서 원본을
#:   여기 적어 두면 ① 남아 있다는 사실이 신호가 되고 ② 되돌릴 수도 있다.
#:   `data/interim` 은 gitignore 라 트리를 더럽히지 않는다 — 그러니 **읽는
#:   관문이 있어야** 신호가 된다(`fl.sh` 1단계 · `verify.sh`).
HOLD_DIR = Path(__file__).resolve().parent.parent / "data" / "interim" / "_mutate_hold"

#: 되돌린 파일 수. 신호로 되돌린 적이 있으면 0 이 아니다 — 자기검사가 본다.
restored = 0


def _side(path: Path) -> Path:
    """그 파일의 사이드카 자리. 이름 하나로 정해진다."""
    return HOLD_DIR / f"{Path(path).name}.orig"


def hold(path: Path, original: str) -> None:
    """흔들기 **전에** 원본을 맡긴다. 메모리와 **디스크 둘 다**."""
    _IN_FLIGHT[Path(path)] = original
    try:
        HOLD_DIR.mkdir(parents=True, exist_ok=True)
        _side(path).write_text(original, encoding="utf-8")
    except OSError:
        # ★ 사이드카를 못 써도 흔들기는 간다 — 메모리 복원이 주 경로다.
        #   여기서 죽으면 측정이 아예 안 돌고, 그것이 더 나쁘다.
        pass


def release(path: Path) -> None:
    """정상 복원이 끝난 뒤 맡긴 것을 거둔다."""
    _IN_FLIGHT.pop(Path(path), None)
    _side(path).unlink(missing_ok=True)


def pending() -> list[Path]:
    """**죽은 흔들기가 남긴 사이드카.** 비어 있어야 정상이다. 순수하다."""
    if not HOLD_DIR.is_dir():
        return []
    return sorted(HOLD_DIR.glob("*.orig"))


def recover() -> list[str]:
    """사이드카로 되돌린다. 되돌린 이름을 낸다 — `SIGKILL` 뒤의 길이다."""
    out = []
    tools = Path(__file__).resolve().parent
    for s in pending():
        tgt = tools / s.name[: -len(".orig")]
        orig = s.read_text(encoding="utf-8")
        if tgt.is_file() and tgt.read_text(encoding="utf-8") != orig:
            tgt.write_text(orig, encoding="utf-8")
            out.append(tgt.name)
        s.unlink(missing_ok=True)
    return out


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
        _side(p).unlink(missing_ok=True)
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

        # ── 사이드카 — `SIGKILL` 이 메모리를 지워도 **파일은 남는다**
        #    ★ 2026-10-14 (§521). 실물 과녁 이름으로 민다 — `recover()` 가
        #      `tools/<이름>` 을 고치므로 아무 이름이나 쓰면 **엉뚱한 도구를
        #      덮는다.** 이 파일 자신을 쓰고 내용은 안 바꿔 둔다.
        me = Path(__file__).resolve()
        hold(me, me.read_text(encoding="utf-8"))
        if not pending():
            bad.append("맡겼는데 사이드카가 없다 — SIGKILL 뒤에 단서가 없다")
        release(me)
        if pending():
            bad.append("거뒀는데 사이드카가 남는다 — 다음 실행이 거짓으로 운다")
        # 되돌리기도 민다 — 내용이 같으면 **안 쓴다**
        hold(me, me.read_text(encoding="utf-8"))
        if recover() != []:
            bad.append("안 바뀐 파일을 되돌렸다고 센다 (사이드카 경로)")
        if pending():
            bad.append("`recover()` 가 사이드카를 안 거둔다")
        _IN_FLIGHT.pop(me, None)

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
                # ★ 2026-10-12 (DECISIONS §487). 20초였고 **부하에서 깨졌다** —
                #   `mutate` 가 하위프로세스를 여럿 돌리는 동안 이 자기검사를
                #   같이 돌리면 「신호에 안 죽었다」로 빨갛게 났다(실측 1회).
                #   이 자가 묻는 것은 「**죽나**」이고 「20초 안에 죽나」가
                #   아니다. 상한을 늘리는 것은 느슨해지는 것이 아니다 — 정말
                #   안 죽으면 여전히 빨갛고, **흔들리는 시험은 꺼진다.**
                pr.wait(timeout=90)
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
    ap.add_argument("--pending", action="store_true",
                    help="죽은 흔들기가 남긴 사이드카. 있으면 종료코드 1")
    ap.add_argument("--recover", action="store_true",
                    help="사이드카로 되돌린다 (SIGKILL 뒤의 길)")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if a.recover:
        done = recover()
        print(f"되돌렸다 {len(done)}" + (f" — {' · '.join(done)}" if done else ""))
        sys.exit(0)
    if a.pending:
        left = pending()
        if not left:
            print("✓ 흔들다 죽은 자국 0")
            sys.exit(0)
        print(f"✗ **흔들다 죽은 자국 {len(left)}** — "
              f"{' · '.join(s.name for s in left)}")
        print("  그 도구가 흔들린 채 남아 있을 수 있다. 남아 있으면 **그 뒤의")
        print("  모든 측정이 거짓**이다(DECISIONS §435 · §521). 되돌려라 —")
        print("    uv run python tools/mutate_guard.py --recover")
        sys.exit(1)
    sys.exit(0)
