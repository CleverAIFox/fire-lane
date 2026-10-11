#!/usr/bin/env python3
"""
navicov.py — **내비 번들에서 시험이 안 드는 순수 함수가 몇인가.** 래칫.

    uv run python tools/navicov.py
    uv run python tools/navicov.py --list        안 드는 것을 파일별로 본다
    uv run python tools/navicov.py --selftest

── 왜 생겼나 (DECISIONS §482) ──────────────────────────────────
§481 이 파이썬 쪽에서 「**부류 관문인데 미는 자가 없는 것**」을 셌다. 그 분모가
세어지자 세 자리가 나왔고 셋 다 시험이 생겼다. **같은 질문을 번들에 한 적이
없었다** — 번들은 `vitest` 29판이 돌고 있어서 「돈다」와 「든다」가 구별되지
않았다.

재 보니 **순수 함수 149 중 40** 을 시험이 **이름으로도 부르지 않았다.** 그중
모듈 통째로 안 드는 것이 셋이다 — `domain/speed.ts`(도착 예정 시각이 전부
여기 매달린다) · `domain/routeSolve.ts` · `infra/dataSource.ts`.

★ **부류로 나눈다.** 나누지 않으면 수가 122 로 나오고(내보낸 이름 289 중),
  그 122 는 「리액트 훅이라 렌더러가 필요한 것」과 「색 토큰이라 분기가 없는
  것」과 「순수 함수인데 아무도 안 드는 것」이 섞인 수다. 섞은 수는 아무도
  안 본다 — `unusedcheck` 가 25 를 셋으로 쪼갠 그 배치(§317)와 같은 꼴이고,
  §481 이 적은 「**부류로 나누지 않아 못 봤다**」가 그 병의 이름이다.

      리액트  app/ · components/   렌더러가 있어야 든다. **안 문다**
      서식    ui/                  색·간격·문구 토큰. 분기가 없다. **안 문다**
      순수상수                     문턱값·표. 시험이 **값으로** 들 수는 있으나
                                   이름으로 안 부를 수 있다. **안 문다**
      순수함수 domain/ · infra/ · config  ← **여기 하나를 문다**

★ 왜 함수만 무는가. 상수는 「이름을 안 부른다」가 결함이 아니다 —
  `GATES_MIN_M` 은 `voice.test.ts` 가 **거리를 넣어** 든다. 함수는 다르다.
  이름을 아무 시험도 안 부르면 그 함수는 **한 번도 호출된 적이 없다**는
  뜻에 가깝고, 고쳐도 번들이 조용하다.

IN    web/navi/src/**/*.ts · web/navi/test/**/*.ts
OUT   표준출력 (판정)
PARAM NAVI_UNTESTED (래칫)
밖    **시험이 좋은가는 안 본다.** 이름을 부르면 든 것으로 센다 —
      `tools/canary.py` 의 `touches()` 와 같은 한계이고, 같은 이유로
      **일부러** 느슨하다: 「정말 미는가」를 정적으로 묻는 자는 없고,
      있는 척하면 그 수가 거짓이 된다. 여기가 드는 것은 **아무도 안
      부르는 것**이라는 바닥 하나다.
      **`.tsx` 를 안 센다.** 거기 내보낸 것은 컴포넌트이고 렌더러가 든다.
      **간접 호출은 못 본다.** `extractManeuvers` 가 `classify` 를 부르고
      그 시험이 있으면 `classify` 는 **실행되지만** 여기서는 안 드는 것으로
      센다 — 이름을 부르는 시험이 없으면 `classify` 의 문턱(25 · 50 · 120 ·
      160)을 **그 시험이 지켜 주지 않는다.** 분모를 넓게 잡는 쪽이 옳다.
      **덮개율(coverage)이 아니다.** 줄을 세지 않는다 — `vitest --coverage`
      를 켜려면 의존성이 늘고, 그 수는 「몇 줄이 돌았나」라서 「누가 지키나」를
      안 말한다.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAVI = ROOT / "web" / "navi"

#: 안 드는 순수 함수 수. **내려가는 쪽으로만.**
#:
#: ★ 이력 — 2026-10-12 §482 첫 실측 **40**(순수 함수 149 중). 같은 배치에서
#:   `geo` 다섯 · `speed` 셋 · `turn` 둘에 시험을 달고 죽은 내보냄 둘을
#:   걷어 **30** 으로 내렸다.
NAVI_UNTESTED = 26

RATCHETS = {"NAVI_UNTESTED": "down"}

#: 부류를 가르는 경로 접두. **여기 없는 것이 `순수`** 다.
NOT_PURE = {"app/": "리액트", "components/": "리액트", "ui/": "서식"}


def ratchet_values() -> dict[str, int]:
    """실측. **판정은 `check()` 소관**이다."""
    return {"NAVI_UNTESTED": sum(len(v) for v in untested().values())}


def _klass(rel: str) -> str:
    for pre, name in NOT_PURE.items():
        if rel.startswith(pre):
            return name
    return "순수"


#: `export function f(` · `export async function f(`
_FN = re.compile(r"^export (?:async )?function (\w+)", re.M)
#: `export const A = `
_CONST = re.compile(r"^export const (\w+)", re.M)
#: `export const f = (…) =>` · `export const f: T = (…) =>` — **함수 쪽이다.**
_ARROW = re.compile(r"^export const (\w+)\s*(?::[^=]+)?=\s*(?:async\s*)?\(", re.M)


def exports(text: str) -> tuple[list[str], list[str]]:
    """한 파일이 내보낸 (**함수**, **상수**). 화살표 꼴은 함수로 센다."""
    arrow = {m.group(1) for m in _ARROW.finditer(text)}
    cons = [m.group(1) for m in _CONST.finditer(text)]
    fns = [m.group(1) for m in _FN.finditer(text)] + [c for c in cons if c in arrow]
    return fns, [c for c in cons if c not in arrow]


def test_text(tests: Path | None = None) -> str:
    """시험 묶음을 한 글자로 이어 붙인다. 이름을 찾을 건초더미다."""
    d = tests if tests is not None else NAVI / "test"
    if not d.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(d.rglob("*.ts")))


def tally(src: Path | None = None, tests: Path | None = None) -> dict[str, list[int]]:
    """부류 → [내보낸 수, 시험이 이름을 안 부르는 수]."""
    s = src if src is not None else NAVI / "src"
    hay = test_text(tests)
    out: dict[str, list[int]] = {}
    for p in sorted(s.rglob("*.ts")):
        rel = p.relative_to(s).as_posix()
        if rel.endswith(".d.ts"):
            continue
        fns, cons = exports(p.read_text(encoding="utf-8"))
        k = _klass(rel)
        for kind, names in ((f"{k}함수" if k == "순수" else k, fns),
                            (f"{k}상수" if k == "순수" else k, cons)):
            row = out.setdefault(kind, [0, 0])
            row[0] += len(names)
            row[1] += sum(1 for n in names
                          if not re.search(rf"\b{re.escape(n)}\b", hay))
    return out


def untested(src: Path | None = None, tests: Path | None = None) -> dict[str, list[str]]:
    """**순수 함수**만. 파일 → 시험이 이름을 안 부르는 함수 이름들."""
    s = src if src is not None else NAVI / "src"
    hay = test_text(tests)
    out: dict[str, list[str]] = {}
    for p in sorted(s.rglob("*.ts")):
        rel = p.relative_to(s).as_posix()
        if rel.endswith(".d.ts") or _klass(rel) != "순수":
            continue
        fns, _ = exports(p.read_text(encoding="utf-8"))
        miss = [n for n in fns if not re.search(rf"\b{re.escape(n)}\b", hay)]
        if miss:
            out[rel] = miss
    return out


def check(show: bool = False) -> list[str]:
    bad: list[str] = []
    if not (NAVI / "src").is_dir():
        return ["`web/navi/src` 가 없다 — 번들이 사라졌거나 작업트리가 얕다"]
    t = tally()
    for kind in ("순수함수", "순수상수", "서식", "리액트"):
        n, gap = t.get(kind, [0, 0])
        mark = "  ← 문다" if kind == "순수함수" else ""
        print(f"  {kind:<5} 내보낸 {n:>3} · 시험이 이름을 안 부르는 것 {gap:>3}{mark}")
    miss = untested()
    now = sum(len(v) for v in miss.values())
    print(f"안 드는 순수 함수 {now} · 래칫 {NAVI_UNTESTED}")
    if show:
        for rel, names in miss.items():
            print(f"    {rel:<30} {len(names):>2}  {' '.join(names)}")

    # ★ 빈 그물 — 분모가 0 이면 이 관문은 아무것도 안 든다
    total = t.get("순수함수", [0, 0])[0]
    if total == 0:
        bad.append("순수 함수를 하나도 못 찾았다 — 훑기가 비었다(정규식이나 경로)")
    if not test_text():
        bad.append("시험 묶음이 비었다 — **모든 함수가 안 드는 것으로 세어진다**")

    if now > NAVI_UNTESTED:
        bad.append(f"시험이 안 드는 순수 함수가 {now} 로 늘었다 (래칫 {NAVI_UNTESTED})\n"
                   "       새 순수 함수에는 그것을 **이름으로 부르는** 시험을 같이 달아라")
    elif now < NAVI_UNTESTED:
        bad.append(f"안 드는 순수 함수가 {now} 로 줄었다 — "
                   "`uv run python tools/ratchet.py --write` 로 조여라")
    return bad


def selftest() -> int:
    """★ **양방향.** 합성 트리로 민다 — 실물 수에 기대면 실물이 바뀔 때 운다."""
    import tempfile
    fails = []

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src, tst = root / "src", root / "test"
        (src / "domain").mkdir(parents=True)
        (src / "ui").mkdir()
        (src / "app").mkdir()
        tst.mkdir()
        (src / "domain" / "a.ts").write_text(
            "export function 든다(x: number) { return x; }\n"
            "export function 안든다(x: number) { return x; }\n"
            "export const 문턱 = 7;\n"
            "export const 화살표 = (x: number) => x;\n", encoding="utf-8")
        (src / "ui" / "t.ts").write_text("export const 색 = '#fff';\n", encoding="utf-8")
        (src / "app" / "h.ts").write_text("export function useX() { return 1; }\n",
                                          encoding="utf-8")
        (tst / "a.test.ts").write_text("import { 든다 } from '../src/domain/a';\n"
                                       "든다(1);\n", encoding="utf-8")

        miss = untested(src, tst)
        got = sorted(n for v in miss.values() for n in v)
        if got != ["안든다", "화살표"]:
            fails.append(f"안 드는 함수를 틀리게 센다 — {got}\n"
                         "       기대: 안든다(이름을 안 부른다) · 화살표(꼴만 다른 함수다)")
        # ★ 음성 — 이름을 부르는 것은 **안** 세어야 한다
        if any("든다" == n for v in miss.values() for n in v):
            fails.append("시험이 이름을 부르는 함수를 안 드는 것으로 센다")

        t = tally(src, tst)
        if t.get("순수상수", [0, 0])[1] != 1:
            fails.append(f"순수 상수를 틀리게 센다 — {t.get('순수상수')} (기대 [1, 1])")
        if t.get("서식", [0, 0])[0] != 1 or t.get("리액트", [0, 0])[0] != 1:
            fails.append(f"부류를 틀리게 가른다 — 서식 {t.get('서식')} · 리액트 {t.get('리액트')}")
        # ★ 서식·리액트는 **분모에만** 있고 물리는 수에는 없다
        if "ui/t.ts" in miss or "app/h.ts" in miss:
            fails.append("서식·리액트를 무는 수에 넣는다 — 렌더러 없이 못 드는 것들이다")

        # ★ 빈 그물 — 시험 묶음이 비면 **전부** 안 드는 것이 되어야 한다
        empty = untested(src, root / "없는곳")
        if sorted(n for v in empty.values() for n in v) != ["든다", "안든다", "화살표"]:
            fails.append("시험이 없는데도 드는 것이 있다고 센다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 6")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="내비 번들에서 시험이 안 드는 순수 함수")
    ap.add_argument("--list", action="store_true", help="안 드는 것을 파일별로 본다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    bad = check(a.list)
    if bad:
        print("\n✗ 내비 시험 분모")
        for b in bad:
            print(f"   {b}")
        return 1
    print("✓ 내비 시험 분모")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
