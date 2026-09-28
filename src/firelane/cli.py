"""
cli.py — 명령줄 표면의 관문. **인자를 거절하는 일만 한다.**

── 왜 생겼나 (2026-09-28 실측 · DECISIONS §283-2) ──────────────
저장소의 CLI 118개에 「모르는 깃발」을 하나 줘 보았다. **25개가 결함이었다** —

    종료 0, 아무 말 없이 일을 했다      20   ★ 제일 나쁘다
    파이썬 역추적을 토했다                4
    모르는 깃발을 받고도 25초 넘게 돌았다   2   ★ 잘못 불러도 돈다

★ **종료 0 이 왜 제일 나쁜가.** `verify.sh` 가 `--check` 를 `--chek` 으로
  적어도 초록이다. 도구는 기본 동작을 하고, 부른 쪽은 「검사가 돌았다」고
  믿는다. 이 저장소가 세어 온 1족(무음 통과) 의 교과서적 형태다.

★ 값을 실제로 치렀다. 이 25개를 찾으려고 전수로 한 번 불러 본 것만으로
  `sources.yaml` 과 **`data/field`(재생성 불가 층)** 가 덮어써졌다 —
  모르는 깃발을 무시한 도구들이 그대로 일을 했기 때문이다(§283-2).

★ 인자를 안 받는 도구가 `sys.argv` 를 **안 보는 것**은 게으름이 아니라
  결함이다. 안 보면 거절도 못 한다.

    from firelane.cli import no_args
    if __name__ == "__main__":
        no_args(__doc__)
        sys.exit(main())

IN    sys.argv
OUT   없음 (거절할 때 종료 2)
PARAM 없음
밖    **인자가 옳은 값인가는 안 본다.** 경로가 실제로 있는지, 숫자가
      범위 안인지는 도구 각자가 본다. 여기가 드는 것은 「받기로 한
      개수·이름과 맞는가」 하나다. **인자를 받는 도구는 여기가 아니라
      `argparse` 를 쓴다** — 이 저장소의 정본이고 98개가 그렇다. 흉내낸
      미니 파서를 여기 두면 관문이 둘이 된다(2족).
"""
from __future__ import annotations

import sys

#: 거절할 때의 종료코드. `argparse` 가 쓰는 값과 같게 둔다 —
#: 부르는 쪽이 「사용법 오류」를 한 가지로만 알면 된다.
USAGE_EXIT = 2


def _head(doc: str | None) -> str:
    """머리말 첫 줄(`이름.py — 무엇`). 없으면 빈 글."""
    for line in (doc or "").strip().splitlines():
        if line.strip():
            return line.strip()
    return ""


def reject(why: str, doc: str | None = None, usage: str = "") -> None:
    """사용법을 내고 종료 2. **역추적이 아니라 이것을 낸다.**"""
    print(f"✗ {why}")
    if usage:
        print(f"\n  {usage}")
    if (h := _head(doc)):
        print(f"\n  {h}")
    sys.exit(USAGE_EXIT)


#: `argparse` 가 공짜로 주는 것. 관문을 세우면서 이것을 같이 막으면
#: 「이 도구가 뭐 하는 것이냐」를 물을 길이 없어진다 — 첫 판이 그랬다.
HELP = ("-h", "--help")


def no_args(doc: str | None = None, argv: list[str] | None = None) -> None:
    """인자를 **안 받는** 도구의 관문. 뭐라도 오면 거절한다.

    `-h` · `--help` 는 받는다. 머리말을 내고 종료 0 — `argparse` 와 같은 꼴이다.
    """
    rest = (sys.argv[1:] if argv is None else argv)
    if not rest:
        return
    if len(rest) == 1 and rest[0] in HELP:
        print((doc or "").strip() or _head(doc))
        sys.exit(0)
    reject(f"이 도구는 인자를 받지 않는다 — {' '.join(rest)}", doc)
