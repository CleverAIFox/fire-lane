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

# ★ 2026-10-14 (DECISIONS 530-3). OOM 넷은 `oom.py` 로 내렸다 — `ingest` 가
#   **CLI 진입점**을 import 하던 거꾸로를 바로잡는다. 여기서 다시 내보내지
#   않는다: 받는 쪽이 `oom` 을 직접 보게 해야 폐포가 제 꼴이 된다.
from firelane.oom import run_stage


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


def _inject_vehicle() -> None:
    """차량 제원을 **이 프로세스에** 주입한다.  (DECISIONS §530)

    ★ 2026-10-14. `pipeline.main()` 이 `vehicle.use(ledger.vehicle_spec())` 를
      부르는데 단계는 **자식 프로세스**로 돈다(`subprocess.run([… -m
      firelane.stagerun …])`). 제원은 모듈 전역(`vehicle._S`)이라 **프로세스를
      못 넘는다.** 그래서 `segments` 가 매 실행 「차량 경로 생략 — 차량 제원이
      주입되지 않았다」를 찍고 `route_vehicle.csv` 를 **안 다시 썼다.**
      옛 파일이 그대로 발행돼 관제 화면의 도달 수가 옛 폭으로 서 있었다.

    ★ **없으면 안 죽는다** — 부모가 그렇게 한다(`pipeline.main()` 의 ★).
      제원이 없는 것은 `segments` 가 이미 다루는 사실이고, 여기서 죽이면
      제원과 무관한 단계(ingest · terrain …)까지 못 돈다.

    ★ 도메인은 대장을 **직접 안 읽는다**(PLAN #122). 읽는 것은 진입점이고,
      자식 프로세스에서는 **이 자리가 진입점**이다.
    """
    from firelane import ledger as _led
    from firelane.seg import vehicle as _V

    try:
        _V.use(_led.vehicle_spec())
    except _V.SpecMissing:
        pass


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
    _inject_vehicle()
    fn = stage_main(name)
    from firelane.guards import warn_direct_call

    # `doc` 을 안 넘긴다 — 위 머리말의 「밖」이 그 사유다
    warn_direct_call(f"firelane.{name}")
    run_stage(fn)


if __name__ == "__main__":
    main()
