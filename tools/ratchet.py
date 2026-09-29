#!/usr/bin/env python3
"""
ratchet.py — 래칫을 **도구가 스스로 조인다.** 사람이 받아적지 않는다.

    uv run python tools/ratchet.py             무엇이 낡았나 (안 고친다)
    uv run python tools/ratchet.py --write     조이는 쪽으로만 고쳐 적는다
    uv run python tools/ratchet.py --selftest  ★ 느슨해지는 쪽을 막는가

── 왜 생겼나 (DECISIONS §309) ──────────────────────────────────
배치 L 에서 관문 열이 울었고 **여덟이 「숫자를 같이 올려라/내려라」**였다 —

    scopedecl   `밖` 칸을 채웠으면 `NO_DECL` 도 153 으로 내려라
    scopedecl   `--selftest` 를 늘렸으면 `SELFTEST_MIN` 도 33 으로 올려라
    sizecheck   segments.py: 780줄 < 예외 853 — 줄었다. EXCEPTIONS 를 780 으로 내려라
    suppress    사유 없는 억제가 57 으로 줄었다 — RATCHET 을 57 으로 조여라

**도구가 답을 이미 알고 있다.** 메시지에 정확한 수가 찍혀 있고, 사람이 하는
일은 그 수를 상수 자리에 **받아적는 것**뿐이다. 받아적는 일을 사람에게 맡기면
두 가지가 생긴다 — ① 배치마다 그 왕복이 든다 ② 안 적으면 래칫이 낡고,
**낡은 래칫은 초록으로 위장한다**(`sizecheck` 머리말이 적은 그 병).

★ 그런데 왜 여태 자동화가 없었나. 자동으로 쓰면 **느슨해지는 쪽으로도 쓸 수
  있기 때문**이다. 그것은 검사를 끄는 것과 같다. 그래서 이 도구가 지키는 것은
  값이 아니라 **방향**이다 —

      down  조이는 쪽이 작아지는 것   (실측 < 선언 일 때만 쓴다)
      up    조이는 쪽이 커지는 것     (실측 > 선언 일 때만 쓴다)

  반대 방향이면 **안 쓰고 빨간불을 낸다.** 그 경우는 결함이고, 결함은 사람이
  본다. 그래서 `--write` 를 자동으로 돌려도 관문이 약해지지 않는다.

★ 도구마다 `--write` 를 달지 않는다. 그러면 **같은 판단이 여섯 벌**이 되고,
  그중 하나가 방향을 틀리게 적는 날이 온다(R3). 판단은 여기 하나이고, 각
  도구는 **제 래칫의 이름과 방향, 그리고 지금 실측값**만 낸다.

★ 선언값은 **모듈이 아니라 원문에서** 읽는다(`_scalar` · `_map_entry` 가 낸
  값 그대로). 적재한 모듈의 속성을 믿으면 안 되는 사유가 둘이다 —

  ① `.pyc` 캐시. 파이썬은 「같은 초에 고쳐졌고 바이트 수가 같으면」 옛
     바이트코드를 준다. `100 → 4`(-2) · `9 → 1000`(+3) · `50 → 8`(-1) 을 한
     파일에 쓰면 합이 **정확히 0** 이라, 고쳐 쓴 직후 다시 재면 **옛 값이
     돌아온다.** 실측한 결함이다(`tests/test_ratchet.py` 의 자릿수 섞은 사례).
  ② 계산된 상수. 모듈이 상수를 식으로 만들면 그 값과 원문의 글자가 다르고,
     `--write` 는 **글자를 고친다.** 재는 것과 고치는 것이 같은 자리여야 한다.

── 도구 쪽 규약 ────────────────────────────────────────────────
래칫을 든 도구는 모듈 최상위에 둘을 둔다. 손목록이 아니다 — 이 도구가
`tools/*.py` 를 훑어 **`RATCHETS` 를 선언한 것만** 집는다.

    RATCHETS = {"NO_DECL": "down", "SELFTEST_MIN": "up"}

    def ratchet_values() -> dict[str, int]:
        \"\"\"이름 → 지금 실측값.\"\"\"

`down-map` 은 값이 **경로 → 수** 인 표다(`sizecheck.EXCEPTIONS`). 항목마다
따로 조인다.

IN    tools/*.py 중 `RATCHETS` 를 선언한 것
OUT   표준출력 · `--write` 면 그 도구의 상수 자리
PARAM 없다. **문턱이 없다** — 방향만 본다
밖    **래칫이 옳은 수인가는 안 본다.** 「`NO_DECL` 150 이 좋은 값인가」는
      사람의 판단이고, 여기가 드는 것은 「선언이 실측과 같은가」와
      「고칠 때 조이는 쪽인가」 둘이다.
      **관문을 대신하지 않는다.** 래칫을 어겼을 때 빨간불을 내는 것은 여전히
      그 도구다 — 이 도구는 **받아적기**만 없앤다.
      **`tools/gate_parity.py` 는 안 든다.** 그 도구의 두 래칫은 `report()`
      안에서 인쇄와 함께 계산돼 값만 꺼낼 수가 없다. 둘 다 0 이고 움직인 적이
      없어 값이 작다 — 꺼내는 리팩터는 별개의 일이다(PLAN).
      **`data/golden` · 봉인지는 안 든다.** 그것은 래칫이 아니라 지문이다.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

#: 이 도구가 아는 방향. 다른 낱말을 적으면 그 도구는 빨간불로 든다.
DIRECTIONS = ("down", "up", "down-map")


def _load(p: Path):
    """도구를 파일에서 적재한다. `RATCHETS` 가 없으면 None."""
    src = p.read_text(encoding="utf-8", errors="ignore")
    if "RATCHETS" not in src:
        return None                       # 읽지도 않는다 — 훑기가 싸야 한다
    spec = importlib.util.spec_from_file_location(f"_rt_{p.stem}", p)
    if not spec or not spec.loader:
        return None
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m            # @dataclass 가 되짚는다 (§258-10)
    try:
        spec.loader.exec_module(m)
    except Exception as e:                # noqa: BLE001 — 남의 도구를 적재한다
        print(f"  ! {p.name} 적재 실패 — {type(e).__name__}: {e}")
        return None
    return m if isinstance(getattr(m, "RATCHETS", None), dict) else None


def owners() -> list[tuple[Path, object]]:
    """`RATCHETS` 를 선언한 도구들. **손목록이 아니다.**"""
    out = []
    for p in sorted(TOOLS.glob("*.py")):
        if p.name == Path(__file__).name:
            continue
        m = _load(p)
        if m is not None:
            out.append((p, m))
    return out


def _scalar(src: str, name: str) -> tuple[int, int, int] | None:
    """모듈 최상위 `name = <int>` 의 (값, 시작오프셋, 끝오프셋)."""
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == name:
                v = node.value
                if isinstance(v, ast.Constant) and isinstance(v.value, int):
                    lines = src.splitlines(keepends=True)
                    off = sum(len(x) for x in lines[:v.lineno - 1])
                    return v.value, off + v.col_offset, off + v.end_col_offset
    return None


def _map_keys(src: str, name: str) -> list[str]:
    """최상위 표 `name` 의 문자열 키들 — **원문 순서 그대로.**"""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            tgt, val = node.target, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt, val = node.targets[0], node.value
        else:
            continue
        if isinstance(tgt, ast.Name) and tgt.id == name and isinstance(val, ast.Dict):
            return [k.value for k in val.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    return []


def _map_entry(src: str, name: str, key: str) -> tuple[int, int, int] | None:
    """최상위 표 `name` 안에서 `key` 항목의 (값, 시작, 끝)."""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            tgt, val = node.target, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt, val = node.targets[0], node.value
        else:
            continue
        if not (isinstance(tgt, ast.Name) and tgt.id == name):
            continue
        if not isinstance(val, ast.Dict):
            continue
        for k, v in zip(val.keys, val.values, strict=True):
            if (isinstance(k, ast.Constant) and k.value == key
                    and isinstance(v, ast.Constant) and isinstance(v.value, int)):
                lines = src.splitlines(keepends=True)
                off = sum(len(x) for x in lines[:v.lineno - 1])
                return v.value, off + v.col_offset, off + v.end_col_offset
    return None


def tightens(direction: str, declared: int, measured: int) -> bool:
    """실측이 **조이는 쪽**으로 움직였는가."""
    if direction in ("down", "down-map"):
        return measured < declared
    return measured > declared


def survey() -> list[dict]:
    """도구 × 래칫 × 실측. 판정은 안 한다."""
    rows: list[dict] = []
    for p, m in owners():
        try:
            vals = m.ratchet_values()
        except AttributeError:
            rows.append({"tool": p.name, "name": "—", "err":
                         "`RATCHETS` 는 선언했는데 `ratchet_values()` 가 없다"})
            continue
        except Exception as e:            # noqa: BLE001 — 남의 실측 함수를 부른다
            rows.append({"tool": p.name, "name": "—", "err":
                         f"`ratchet_values()` 가 죽었다 — {type(e).__name__}: {e}"})
            continue
        src = p.read_text(encoding="utf-8")
        for name, direction in m.RATCHETS.items():
            if direction not in DIRECTIONS:
                rows.append({"tool": p.name, "name": name, "err":
                             f"모르는 방향 `{direction}` — {DIRECTIONS} 중 하나여야 한다"})
                continue
            if direction == "down-map":
                keys = _map_keys(src, name)
                if not keys:
                    rows.append({"tool": p.name, "name": name, "err":
                                 "최상위 표가 아니거나 문자열 키가 없다"})
                    continue
                for key in keys:
                    got = vals.get(key)
                    if got is None:
                        continue          # 파일이 없어진 경우 — 그 도구가 따로 운다
                    at = _map_entry(src, name, key)
                    if at is None:
                        rows.append({"tool": p.name, "name": name, "err":
                                     f"`{key}` 항목의 값이 정수 상수가 아니다"})
                        continue
                    rows.append({"tool": p.name, "name": name, "key": key,
                                 "dir": direction, "declared": at[0], "measured": got,
                                 "at": at})
                continue
            if name not in vals:
                rows.append({"tool": p.name, "name": name, "err":
                             "`ratchet_values()` 가 이 이름을 안 낸다"})
                continue
            at = _scalar(src, name)
            if at is None:
                rows.append({"tool": p.name, "name": name, "err":
                             "최상위 정수 상수가 아니다 — `--write` 가 쓸 자리가 없다"})
                continue
            rows.append({"tool": p.name, "name": name, "dir": direction,
                         "declared": at[0], "measured": vals[name], "at": at})
    return rows


def _apply(p: Path, edits: list[tuple[int, int, int]]) -> None:
    """뒤에서부터 적어 넣는다 — 앞에서 쓰면 오프셋이 밀린다."""
    src = p.read_text(encoding="utf-8")
    for val, a, b in sorted(edits, key=lambda e: -e[1]):
        src = src[:a] + str(val) + src[b:]
    p.write_text(src, encoding="utf-8")


def run(write: bool) -> int:
    rows = survey()
    if not rows:
        print("★ 래칫을 선언한 도구가 하나도 없다 — 판별식을 의심하라")
        return 1

    err = [r for r in rows if "err" in r]
    stale = [r for r in rows if "err" not in r and r["declared"] != r["measured"]]
    loose = [r for r in stale if not tightens(r["dir"], r["declared"], r["measured"])]
    tight = [r for r in stale if tightens(r["dir"], r["declared"], r["measured"])]

    print(f"래칫 {len(rows) - len(err)}개 · 낡음 {len(stale)}"
          f" (조이는 쪽 {len(tight)} · 느슨해진 쪽 {len(loose)})")

    for r in err:
        print(f"  ✗ {r['tool']} · {r['name']} — {r['err']}")

    for r in loose:
        k = f"[{r['key']}]" if "key" in r else ""
        print(f"\n  ✗ {r['tool']} · {r['name']}{k} — **느슨해지는 쪽**이다"
              f"  선언 {r['declared']} → 실측 {r['measured']} ({r['dir']})")
        print("     이것은 받아적을 일이 아니라 **결함**이다. 그 도구가 왜 우는지 읽어라.")
        print("     여기서는 안 쓴다 — 자동으로 느슨해지면 관문이 죽는다.")

    for r in tight:
        k = f"[{r['key']}]" if "key" in r else ""
        mark = "→ 고쳐 적었다" if write else "(--write 로 고친다)"
        print(f"  · {r['tool']} · {r['name']}{k}  {r['declared']} → {r['measured']}  {mark}")

    if write and tight:
        by: dict[Path, list] = {}
        for r in tight:
            # `at` 은 `survey()` 에서 이미 확인됐다 — 못 찾은 것은 `err` 로 빠진다.
            by.setdefault(TOOLS / r["tool"], []).append((r["measured"], r["at"][1], r["at"][2]))
        for p, edits in by.items():
            _apply(p, edits)
        print(f"\n✓ {len(tight)}개를 조였다 — 커밋에 **왜 움직였는지**를 적어라")
        return 0

    if loose or err:
        return 1
    if tight:
        print("\n✗ 조일 것이 있다 — `--write` 가 고쳐 적는다")
        return 1
    print("✓ 래칫이 전부 실측과 같다")
    return 0


def selftest() -> int:
    """**느슨해지는 쪽을 막는가.** 그것이 이 도구의 안전장치다."""
    fails = []
    # ① 방향 판정
    if not tightens("down", 10, 8):
        fails.append("down 에서 8 < 10 을 조임으로 안 본다")
    if tightens("down", 10, 12):
        fails.append("down 에서 12 > 10 을 조임으로 봤다 — **느슨해지는 쪽이다**")
    if not tightens("up", 10, 12):
        fails.append("up 에서 12 > 10 을 조임으로 안 본다")
    if tightens("up", 10, 8):
        fails.append("up 에서 8 < 10 을 조임으로 봤다 — **느슨해지는 쪽이다**")
    if not tightens("down-map", 10, 8) or tightens("down-map", 10, 12):
        fails.append("down-map 이 down 과 다르게 판정한다")

    # ② 상수 자리 찾기
    src = 'X = 5\nY: int = 7\nT = {"a/b.py": 41, "c.py": 9}\n'
    got = _scalar(src, "X")
    if not got or got[0] != 5 or src[got[1]:got[2]] != "5":
        fails.append(f"최상위 정수 상수를 못 짚는다 — {got}")
    if _scalar(src, "T") is not None:
        fails.append("표를 정수 상수로 잘못 짚는다")
    e = _map_entry(src, "T", "a/b.py")
    if not e or e[0] != 41 or src[e[1]:e[2]] != "41":
        fails.append(f"표 항목을 못 짚는다 — {e}")
    if _map_entry(src, "T", "없는키") is not None:
        fails.append("없는 키를 짚었다")

    # ③ 실제로 써지는가 — 임시 파일에만
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        q = Path(d) / "t.py"
        q.write_text(src, encoding="utf-8")
        _apply(q, [(3, *_scalar(src, "X")[1:]), (40, *_map_entry(src, "T", "a/b.py")[1:])])
        after = q.read_text(encoding="utf-8")
        if "X = 3" not in after or '"a/b.py": 40' not in after:
            fails.append(f"쓰기가 자리를 어긋나게 넣는다 —\n{after}")

    # ④ 훑기가 비지 않았다
    if not owners():
        fails.append("`RATCHETS` 를 선언한 도구를 하나도 못 찾았다 — 빈 그물이다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 4")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="래칫을 조이는 쪽으로만 고쳐 적는다")
    ap.add_argument("--write", action="store_true", help="조이는 쪽으로만 쓴다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    return run(a.write)


if __name__ == "__main__":
    raise SystemExit(main())
