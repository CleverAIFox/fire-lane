#!/usr/bin/env python3
"""
ratchetstore.py — 래칫 값을 **도구 파일 밖**에 둔다. 값이 움직여도 그 도구를 지목한 도장이 안 죽는다.  (PLAN #198)

    uv run python tools/ratchetstore.py --rank      도구마다 「값을 한 번 고치면 죽는 도장 수」 — 옮길 후보를 잰다(읽기 전용)

── 왜 있나 ─────────────────────────────────────────────────────
`sealcov.SEALED_FILES` 를 `ratchet --write` 로 한 칸 조이면 **그 파일의 글자가 바뀌어** 그 파일을 지목한 도장이 죽는다 —
2026-11-08 에 681 → 683 한 번에 **28절**이 죽었다(2026-10-20 에 20 · 2026-11-07 에 87). 값은 판정 논리가 아니라 **잰 수**다.
값만 밖으로 빼면 논리를 고칠 때만 도장이 죽는다 — 그것이 도장의 뜻이다.

★ **공용 파일 하나**(`ratchets.json` 꼴)다. 도구마다 따로 두면 규약이 둘이 되고 다음 도구가 같은 병을 앓을 때 또 묻는다.
  **지금은 기준을 넘은 도구만 넣는다**(`MOVE_AT`): 값 변경 한 번에 도장이 그 수 이상 죽고 **값이 아직 움직일 수 있는** 도구.
  기준이 있으므로 다음 도구를 옮길지는 판단이 아니라 `--rank` 의 측정이다.

★★ **그 값 파일을 어느 절도 백틱으로 적지 않는다.** 도장의 지문은 절이 백틱으로 지목한 파일의 내용을 넣는다 — 적는 순간 그 절의 지문에
  값이 들어가고 값이 움직일 때 그 절이 죽는다. 원점이다. `tests/test_ratchetstore.py` 가 문서 전체에서 그 이름을 센다.

IN    `data/golden/` 의 래칫 값 파일 · `tools/*.py` 의 `RATCHETS` 선언 · 도장의 절 → 파일 지목
OUT   값 파일(쓰기는 `write()` 뿐 — `ratchet.py --write` 가 부른다) · `--rank` 는 화면
PARAM MOVE_AT
밖    **값이 옳은 수인가는 안 본다**(그것은 `ratchet.py` 도 안 본다). 어느 도구를 옮길지 **고르지도 않는다** — 수만 낸다.
      값 파일을 읽는 도구는 제 값을 여기서 받는다 — 읽는 자리가 하나다(`read`).
부류  조사   `--rank` 는 사람이 손으로 돌려 **수를 내고 멈춘다** — 어느 도구를 옮길지는 안 고른다.
             `read`/`write` 를 `ratchet.py` 가 부르지만 `main()` 이 있어 **몸통이 아니다**.
             `testpick.py` 와 같은 꼴이다 — 그쪽도 `--run` 을 훅이 부르는데 「조사」다  (DECISIONS §437)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: 값 파일. **어느 문서도 이 경로를 백틱으로 적지 않는다**(머리말 ★★ · 시험이 센다).
STORE = ROOT / "data" / "golden" / "ratchets.json"

#: 값을 한 번 고치면 죽는 도장이 이 수 **이상**이면 값 파일로 옮긴다. 실측(2026-11-08): sealcov 28 · docseal 23 · 그다음 13.
MOVE_AT = 20


def load(path: Path | None = None) -> dict[str, dict[str, int]]:
    """도구 파일명 → {래칫 이름 → 값}. 못 읽으면 **죽는다** — 빈 표로 읽으면 선언이 사라진 것과 같다."""
    p = path or STORE
    d = json.loads(p.read_text(encoding="utf-8"))["values"]
    return {t: {k: int(v) for k, v in m.items()} for t, m in d.items()}


def read(tool: str, name: str, path: Path | None = None) -> int:
    """도구 `tool`(예 `sealcov.py`) 의 래칫 `name` 의 선언값."""
    return load(path)[tool][name]


def write(tool: str, name: str, value: int, path: Path | None = None) -> None:
    """한 칸을 덮는다. 방향 판단은 `ratchet.py` 의 몫이고 여기는 받아 적기만 한다."""
    p = path or STORE
    d = json.loads(p.read_text(encoding="utf-8"))
    d["values"][tool][name] = int(value)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def seals_per_tool() -> dict[str, int]:
    """도구 → 그 파일을 지목한 **도장 대상 절**의 수. 값을 한 번 고치면 그만큼 죽는다."""
    import docseal as D
    now, _was, _ = D.survey()
    out: dict[str, int] = {}
    for one in now.values():
        for f in one["files"]:
            out[f] = out.get(f, 0) + 1
    return out


def movable(direction: str, value: object) -> bool:
    """이 래칫의 값이 **아직 움직일 수 있는가.** `up` 은 늘 올라갈 수 있고 `down` 은 0 이 바닥이라 0 이면 더 못 조인다.

    ★ 2026-11-08 (PLAN #198 ④ · DECISIONS §670). `UNSEALED` 는 도장 23절이 지목하지만 값이 0 이라 조일 일이 없다 — 지목한 절 수만으로는
      「옮길 이득」이 안 보인다. 그래서 기준은 둘이다: **움직일 수 있는 값**이고 **지목한 도장이 `MOVE_AT` 이상**.
    `down-map` 은 항목 값이 하나라도 0 보다 크면 움직일 수 있다. 모르는 꼴은 움직일 수 있다고 본다(안 옮기는 쪽의 실수가 더 싸다).
    """
    if direction == "up":
        return True
    if isinstance(value, dict):
        return any(not isinstance(v, int) or v > 0 for v in value.values())
    return not isinstance(value, int) or value > 0


def rank() -> list[tuple[int, str, list[str], bool, bool]]:
    """(죽는 도장 수, 도구, 래칫 이름들, 이미 값 파일에 있나, 움직일 수 있는 값이 있나) — 많은 순."""
    import ratchet as R
    cnt = seals_per_tool()
    stored = load()
    rows = [(cnt.get(f"tools/{p.name}", 0), p.name, list(m.RATCHETS), p.name in stored,
             any(movable(d, getattr(m, n, None)) for n, d in m.RATCHETS.items())) for p, m in R.owners()]
    return sorted(rows, key=lambda r: (-r[0], r[1]))


def due(rows: list[tuple[int, str, list[str], bool, bool]]) -> list[str]:
    """옮길 차례 — **둘을 같이** 만족하는 도구: 지목한 도장이 기준 이상 · 움직일 수 있는 값이 있다 · 아직 값 파일에 없다."""
    return [t for n, t, _, moved, mv in rows if n >= MOVE_AT and mv and not moved]


def main(argv: list[str] | None = None) -> int:
    if (argv if argv is not None else sys.argv[1:]) != ["--rank"]:
        print(__doc__)
        return 2
    rows = rank()
    print(f"값 한 번에 죽는 도장 수 — 기준 {MOVE_AT} 이상 **이고 움직일 수 있는 값**이면 값 파일로 옮긴다(`MOVE_AT`)")
    for n, tool, names, moved, mv in rows:
        if n >= MOVE_AT or moved:
            state = "값 파일에 있다" if moved else ("★ 옮길 차례" if mv else "값이 바닥이라 안 옮긴다")
            print(f"  {n:3d}  {tool:20s}  {state}  {', '.join(names)}")
    todo = due(rows)
    print(f"  (기준 미만 {sum(1 for n, *_ in rows if n < MOVE_AT)}개는 안 옮긴다)")
    if todo:
        print(f"  → 옮길 차례: {', '.join(todo)} (이 도구는 판정이 아니라 측정만 한다 — 종료 코드는 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
