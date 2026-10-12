#!/usr/bin/env python3
"""
stagerun.py — 단계 모듈을 돌리는 껍데기. **메모리로 죽은 것을 메모리로 죽었다고** 말한다.

── 왜 별도 파일인가 (2026-09-23 · DECISIONS §224-3a) ───────────
처음에는 이 코드를 `guards.py` 에 뒀다. 그랬더니 `golden.py check` 가 빨개졌다 —
`guards` 는 `firelane.segments` 의 **import 닫힘 안**에 있고, 그 닫힘이 곧 판정
지문이기 때문이다. 판정 바이트는 한 글자도 안 움직였는데 지문만 움직였다.

그것은 재잠금할 일이 아니라 **코드를 잘못 둔 것**이다. 이 배치가 §224-2 에서
규탄한 병과 같다 — 봉인 안에 봉인과 무관한 것을 넣으면 봉인이 매번 찢어지고,
찢어지는 봉인은 곧 무시된다. OOM 안내문 한 줄 때문에 판정 기준선을 다시 찍는
것은 그 길의 첫걸음이다.

그래서 **판정이 안 읽는 자리**에 둔다. `firelane.segments` 가 이 모듈을 안
import 하므로 여기를 고쳐도 golden 은 안 움직인다. 반대로 `ingest` 는
import 하므로 샤드 봉인은 움직인다 — 그쪽은 `--reseal-code` 가 받는다.

── 무엇을 하나 ─────────────────────────────────────────────────
`main()` 을 돌리되 `MemoryError` · `OSError(ENOMEM)` 만 가로채 처방을 찍고
전용 종료코드로 나간다. 다른 예외는 **건드리지 않는다** — 삼키면 그것이
1족(조용한 실패)이다.

★ 종료코드로 가른다. 출력을 파싱하면 문구를 다듬는 순간 검사가 죽는다
  (`pages_add_navi` 의 앵커가 한국어 주석이었던 것과 같은 자리).
★ 값의 정본은 이 파일의 `ENOMEM_RC` 하나다. `ingest` 가 내고 `pipeline` 이
  읽는다. 양쪽에 숫자를 박으면 그것이 곧 갈린다(MASTER §18-3).

── 왜 껍데기가 **밖**에서 씌워지나 (2026-10-11 · DECISIONS §463-1) ──
처음에는 단계 모듈 제 `__main__` 이 `run_stage(main)` 을 부르게 했다. 그런데
그렇게 하면 **그 모듈이 이 파일을 import 한다.** `code_closure` 는 `ast.walk`
라서 `if __name__` 안의 import 도 센다 — 그 한 줄이 `segments` 의 판정 폐포를
늘리고 golden 지문을 움직인다. 이 파일 머리말이 처음부터 경계한 그 자리다.

그래서 **일곱 단계 중 하나(`ingest`)만** 껍데기를 썼다. 그 결과가 2026-10-11
실측이다 — `ortho` 가 TIF 넉 장(1.25GB)을 해시하다 ENOMEM 으로 죽었고,
파이썬 역추적이 그대로 나오고, 파이프라인은 그것을 **보통 실패**로 읽어
`tidy.py --yes` 를 권했다(§463-3 이 그 안내를 든다).

고치는 자리는 단계가 아니라 **부르는 쪽**이다. 파이프라인이

    python -m firelane.stagerun <단계> [깃발...]

로 부르면 껍데기는 일곱 단계 전부를 덮고, **단계 모듈은 한 줄도 안 바뀐다** —
폐포도 봉인도 안 움직인다.

IN    단계 모듈 이름 (`sys.argv[1]`)
OUT   없음 (종료코드 — 정상은 `main()` 이 정한 대로, 메모리 실패는 12)
PARAM 단계 모듈 이름 하나. 뒤따르는 깃발은 **그 단계에 그대로 넘긴다**
밖    **깃발이 옳은가는 안 본다.** 모르는 깃발 거절은 단계 자신이 부르는
      `src/firelane/guards.py` 의 `warn_direct_call` 소관이다(§283-2) —
      여기서 한 번 더 들면 `ingest` 의 `--keep-work` 가 거절된다
"""
from __future__ import annotations

import sys
from pathlib import Path

# 단계가 **메모리로** 죽었을 때의 종료코드.
#
# 왜 가르나: 종전에는 ingest 가 어떻게 죽었든 1 이었고, 파이프라인이 그것을
# 「소스가 실패했다」로 읽어 `--retry-failed` 를 찍었다. 그 명령은 "실패한
# 소스가 없다"를 내놓는다 — **안내가 거짓이었고 사람이 그 말을 따라 헛돌았다.**
# 137 은 OS 의 OOM killer(SIGKILL)다. 그쪽은 우리가 정하는 값이 아니다.
ENOMEM_RC = 12


def is_oom(ex: BaseException) -> bool:
    """메모리로 죽었나. **판별의 집은 여기 하나다.**

    ★ 2026-10-11 (DECISIONS §461). 부르는 쪽이 둘이 됐다 — 이 껍데기와
      `ingest` 의 **샤드 루프**다. 그 루프가 `except Exception` 으로 먼저
      잡아서 이 파일의 처방이 한 번도 안 찍혔고, 사람은 「소스가 실패했다」는
      거짓 안내를 따라갔다(§224-3 이 고친 그 1족이 다른 길로 돌아왔다).
      양쪽이 `errno` 를 각자 적으면 다음에 또 갈린다.
    """
    import errno

    return isinstance(ex, MemoryError) or (
        isinstance(ex, OSError) and ex.errno == errno.ENOMEM)


def run_stage(main) -> None:
    """단계 모듈의 `main()` 을 돌린다. 메모리 실패만 가로챈다."""
    try:
        main()
    except (MemoryError, OSError) as e:        # [Errno 12] Cannot allocate memory
        if not is_oom(e):
            raise
        oom_exit(f"{type(e).__name__}: {e}")


def oom_exit(what: str) -> None:
    """메모리가 모자라 죽었다 — 처방을 찍고 전용 종료코드로 나간다."""
    import traceback

    traceback.print_exc()
    print(f"\n★ 메모리가 모자라 죽었다 — {what}", file=sys.stderr)
    print("  소스가 실패한 것이 **아니다.** `--retry-failed` 는 할 일이 없다고 답한다.",
          file=sys.stderr)
    try:                                       # 있으면 숫자를 보여준다. 없어도 죽지 않는다
        mi = dict(
            (k.strip(), v.strip())
            for k, v in (ln.split(":", 1)
                         for ln in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
                         if ":" in ln))
        print(f"  지금  MemTotal {mi.get('MemTotal', '?')} · "
              f"MemAvailable {mi.get('MemAvailable', '?')}", file=sys.stderr)
    except OSError:
        pass
    print("\n  WSL 이면 (Windows PowerShell):", file=sys.stderr)
    print("    wsl --shutdown                     VM 메모리를 통째로 반납한다", file=sys.stderr)
    print("    notepad $env:USERPROFILE\\.wslconfig   [wsl2] memory=12GB", file=sys.stderr)
    print("\n  ★ 코드만 바뀌어 봉인이 찢어진 것이라면 다시 빌드할 필요가 없다 —", file=sys.stderr)
    print("    raw · 산출물이 봉인과 같은 샤드는 code 칸만 고치면 된다:", file=sys.stderr)
    print("      uv run python -m firelane.ingest --reseal-code", file=sys.stderr)
    print("    소스마다 자식 프로세스로 돌려 메모리를 반납할 수도 있다:", file=sys.stderr)
    print("      uv run fire-lane --from ingest --split", file=sys.stderr)
    sys.exit(ENOMEM_RC)


def stage_main(module: str):
    """단계 모듈의 `main`. **없으면 거기서 운다** — 조용히 0 으로 안 나간다."""
    import importlib

    try:
        mod = importlib.import_module(f"firelane.{module}")
    except ModuleNotFoundError as e:
        # ★ **그 모듈이 없을 때만** 받는다. 단계가 제 의존을 못 찾은 것이라면
        #   그것은 사용법 문제가 아니라 환경 문제이고, 삼키면 1족이 된다.
        if e.name != f"firelane.{module}":
            raise
        print(f"✗ firelane.{module} 이 없다 — 단계 이름이 아니다", file=sys.stderr)
        print("  단계 목록:  uv run fire-lane --help", file=sys.stderr)
        sys.exit(2)
    fn = getattr(mod, "main", None)
    if fn is None:
        print(f"✗ firelane.{module} 에 main() 이 없다 — 단계가 아니다", file=sys.stderr)
        sys.exit(2)
    return fn


def main() -> None:
    """`python -m firelane.stagerun <단계> [깃발...]`"""
    rest = sys.argv[1:]
    if not rest or rest[0].startswith("-"):
        # ★ 역추적을 토하지 않고 사용법으로 거절한다 — `test_cli_surface` 가 드는 축이다
        print((__doc__ or "").strip(), file=sys.stderr)
        sys.exit(2)
    name, flags = rest[0], rest[1:]
    # 단계가 보는 인자는 **제 것뿐**이다. 제 이름이 argv[0] 에 와야
    # `warn_direct_call` 과 단계의 argparse 가 같은 것을 본다.
    sys.argv = [f"firelane.{name}", *flags]
    fn = stage_main(name)
    from firelane.guards import warn_direct_call

    # `doc` 을 안 넘긴다 — 위 머리말의 「밖」이 그 사유다
    warn_direct_call(f"firelane.{name}")
    run_stage(fn)


if __name__ == "__main__":
    main()
