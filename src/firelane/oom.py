#!/usr/bin/env python3
"""
oom.py — 단계가 **메모리로** 죽었을 때의 종료코드 · 판별 · 처방.

── 왜 제 집인가 (2026-10-14 · DECISIONS 530-3) ────────────────
이 넷은 `stagerun.py` 에 있었고, `ingest` 가 거기서 받아 썼다 —
그 import 에 **「순환을 끊는다」**는 주석이 붙어 있었다. 순환이 이미 있다는
자백이다. `ingest` 가 **CLI 진입점**을 import 하는 것은 거꾸로다.

그 거꾸로가 값을 치렀다. `stagerun.main()` 에 차량 제원 주입을 넣자
`seg/vehicle.py` 가 **ingest 샤드 폐포**에 들어왔고
`test_shardseal::test_code_closure_follows_ingest_imports_not_segments` 가
울었다 — 그 자가 지키는 것은 「판정 코드 한 줄에 ingest 전량이 다시 돈다」이고,
이 8GB 기계에서 그것은 `ngii_road` 의 `Errno 12` 다(§165-8 · §266).

`stagerun` 을 `NOT_PRODUCERS` 에 넣어 **면제**하는 길도 있었지만 그 목록의
기준은 「고치면 산출물이 바뀌는가」이고 `seg/vehicle.py` 는 **바뀐다.**
면제가 아니라 **방향을 바로잡는** 쪽을 골랐다.

★ 값의 정본은 이 파일의 `ENOMEM_RC` 하나다. `ingest` 가 내고 `pipeline` 이
  읽는다. 양쪽에 숫자를 박으면 그것이 곧 갈린다(MASTER §18-3).

IN    없음 (예외 객체 · /proc/meminfo)
OUT   없음 (표준에러 · 종료코드)
PARAM ENOMEM_RC
밖    단계를 **고르고 돌리는** 일은 `stagerun.py` 가 든다. 여기는 죽는 길만 안다.
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
