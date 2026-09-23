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

IN    단계 모듈의 `main()`
OUT   없음 (종료코드 — 정상은 `main()` 이 정한 대로, 메모리 실패는 12)
PARAM 없음
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


def run_stage(main) -> None:
    """단계 모듈의 `main()` 을 돌린다. 메모리 실패만 가로챈다."""
    import errno

    try:
        main()
    except MemoryError:
        oom_exit("MemoryError")
    except OSError as e:                       # [Errno 12] Cannot allocate memory
        if e.errno != errno.ENOMEM:
            raise
        oom_exit(f"OSError [Errno {e.errno}] {e.strerror}")


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
                         for ln in Path("/proc/meminfo").read_text().splitlines()
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
