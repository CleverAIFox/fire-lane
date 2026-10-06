#!/usr/bin/env python3
"""
suppress.py — **사유 없이 검사를 끄는 주석**을 센다. 양방향 래칫.  (DECISIONS §279-6)

    uv run python tools/suppress.py              검사 (양방향 래칫)
    uv run python tools/suppress.py --list       어디에 있는지 전부
    uv run python tools/suppress.py --selftest   ★ 판별식이 살아 있나

── 왜 생겼나 (2026-09-28 실측) ────────────────────────────────
SKIP 전수를 냈더니 이 저장소는 **사유 딸린 면제 쪽은 이미 매우 조여 있었다** —
`pytest` skip 39 · `verify.sh` note 9 · CI `if:` 6 · `# ci-exempt:` 12 ·
면제표 94항목, **사유 없는 것 0**. 형식으로 사유를 강제하고 죽은 면제까지
잡는 강제자가 세 방향으로 붙어 있다.

★ 남은 빚은 전부 **주석 한 줄짜리 억제**에 몰려 있었다. 표에 안 들어가고
  사유를 안 적어도 되고 아무도 안 세는 자리다 —

    noqa                        59   ★ **전부 죽은 억제였다** — 아래
    eslint-disable-line          28   ★ **eslint 가 저장소에 아예 없었다**(§279-4)
    <!--voice-ok-->              15
    <!--stale-ok-->              12
    # type: ignore                5
                                ───
                                119

★ 「사유를 적게 강제」하는 쪽이 더 낫지만 119개를 하루에 못 적는다. **세는 것이
  먼저다** — 세지 않으면 120이 되어도 아무도 모른다. 래칫은 양방향이다: 늘면
  울고, 줄여도 기록을 안 내리면 운다(느슨해진 래칫은 초록으로 위장한다).

★ **사유가 붙은 억제는 안 센다.** 「noqa 뒤에 말이 붙어 있다」 처럼
  코드 뒤에 말이 붙어 있으면 그것은 사유다. 세는 것은 **말 없이 끈 것**이다.

IN    src/** · tools/** · tests/** · web/navi/src/** · web/navi/test/** · docs/**
OUT   갈래별 수 · 종료코드
PARAM RATCHET · FAMILIES
밖    **억제가 정당한가는 안 본다.** `# noqa: BLE001` 이 옳은 자리인지, 그
      `<!--stale-ok-->` 가 진짜 옛 인용인지는 사람이 본다. 여기가 드는 것은
      「몇 개인가」와 「늘었는가」 둘뿐이다.
      **사유 딸린 면제표(`EXEMPT` · `ci-exempt` · pytest skip)는 안 센다** —
      그쪽은 각자의 강제자가 사유를 형식으로 강제하고 죽은 면제까지 잡는다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 2026-09-28 실측 119 → **57**. 같은 날 `noqa` 59개를 지우고 시작한다.
#:
#: ★ 지운 59개는 **어느 룰셋에도 없는 규칙 이름**을 적고 있었다(`ruff --extend-select
#:   RUF100` 을 기본·엄격 두 설정으로 돌려 교집합을 냈다). 아무것도 안 막으면서
#:   「검사를 통과시켰다」고 보이는 주석이고, `eslint` 가 없는데 있던
#:   `eslint-disable-line` 28개와 **같은 병**이다(§279-4).
#:
#: ★ **사유가 붙은 12개는 남겼다.** 규칙이 꺼져 있어도 「이 blind except 는
#:   일부러다」라는 말은 값이 있다. 지우면 그 말이 사라진다.
#:
#: ★ 규칙을 **켜는 쪽**이 더 낫다. 실측 — `BLE001` 28 · `PLC0415` 526 ·
#:   `S603` 83 · `E402` 39 · `ARG001` 23 · `E731` 4 가 억제 없이 걸린다.
#:   526 짜리를 오늘 켤 수는 없다. 수를 여기 적어 두는 것이 다음 배치의 입구다.
#: **줄기만 한다.**
#:
#: ★ **2026-09-30. 57 → 61 로 올렸다**(DECISIONS §319-1). 올리는 것은 이 도구가
#:   금지하는 방향이라 사람이 손으로 올리고 **왜**를 여기 적는다 —
#:
#:   `docgen` 에 판정 네 축(`v_clear` 등)을 붙였다. 그 축이 문서 넷을 다 보므로
#:   `DECISIONS` 의 **회고 인용 네 줄**(2026-08-24 의 「통행 불가 416」 따위)이
#:   함께 걸렸고, 그 줄에는 `<!--stale-ok-->` 를 붙일 수밖에 없다 — 역사는
#:   고칠 수 없고, 축을 빼면 **판정 수가 다시 사람 손으로 돌아간다.**
#:
#: ★ 이 넷은 위 목록의 다른 억제와 성격이 다르다. 저것들은 「검사를 껐다」이고
#:   이 넷은 **「이 줄은 과거다」라는 사실 표기**다. 그런데 이 도구는 문서 표기
#:   둘(`voice-ok` · `stale-ok`)을 「뒤에 말이 붙을 자리가 없어 전부 센다」로
#:   두었으므로 가를 수가 없다. 가르는 일(표기에 사유를 붙일 수 있게 하는 것)은
#:   별개의 배치이고, 그때 이 수는 스물넷이 빠진다.
#:
#: ★ **2026-09-30. 두 힘이 같은 날 이 수를 움직였다.** 방향이 반대라 둘을 같이 적는다 —
#:
#:   ① **측정 배치가 회고를 얼렸다** (61 → 64). 판정 산출물이 움직이자
#:      `DECISIONS §319` 의 실기 기록 한 줄과 `§308` 의 전후 기록 두 줄이 옛 수를
#:      들게 됐다. 그 셋은 「그날 그랬다」는 기록이라 고칠 수 없고, 안 얼리면
#:      `docnum` 이 「옛 수가 남았다」로 운다. **판정이 움직이면 회고가 굳는다** —
#:      측정 배치마다 이 수가 몇 올라가는 것이 이 도구의 정상 동작이다.
#:
#:   ② **세는 쪽의 결함 열셋을 걷었다**(DECISIONS §325). 위 문단의 「스물넷」이
#:      틀렸다. 빠진 열셋은 어휘 문제가 아니라 **이 도구가 잘못 센 것**이었다 —
#:
#:          | `<!--stale-ok-->` | 옛 숫자를 의도적으로 인용한 줄 |   (MASTER §0-2)
#:          tonecheck.py … (`<!--voice-ok-->` 면 통과)              (README 도구표)
#:
#:      **어휘를 정의하는 줄 자신**을 「사유 없이 검사를 끈 자리」로 세고 있었다.
#:      규약을 적으면 빚이 느는 셈이고, 그러면 아무도 규약을 안 적는다. 백틱 안은
#:      표기를 **말한 것**이지 **쓴 것**이 아니다(`mentioned()`).
#:
#:   ★ 아래 수는 **둘을 합산한 것이 아니라 병합된 트리에서 실측한 것**이다.
#:     실제로 합산은 틀린다 — ①의 64 에서 ②의 13 과 W13-9 행의 1 을 빼면 50 인데
#:     실측은 **52** 다. 이 배치가 제 회고에 `voice-ok` 둘을 더했기 때문이고,
#:     그 둘은 §333 이 옛 안내문을 인용하는 자리다. 더하고 빼서 적으면 그것은
#:     **재지 않은 수**이고, 이 저장소가 반복해 다친 그 형태다.
#:     내역: type-ignore 5 · eslint 14 · voice-ok 16 · stale-ok 17.
#:
#: ★ 그래서 「표기에 사유 슬롯을 붙이는 배치」는 **안 만든다.** 남은 것은 대부분
#:   DECISIONS·MASTER 의 회고 줄이고, 거기 붙일 사유는 전부 같은 한 마디
#:   (「이 줄은 과거 기록이다」)다. 같은 말을 마흔 몇 번 적는 것은 빚을 갚는
#:   것이 아니라 **빚을 예쁘게 적는 것**이다. 그리고 append-only 인 문서의 옛
#:   줄을 마흔 몇 개 고치는 일이기도 하다. PLAN 이 줄었다.
#: ★ 이 수가 아래 값보다 늘면 그것은 진짜 결함이다. 래칫은 산다.
#:
#: ★ **2026-10-03. 52 → 53 으로 올렸다**(DECISIONS §375). 올리는 것은 이 수의
#:   방향이 아니라 사람이 손으로 올리고 **왜**를 여기 적는다 —
#:
#:   소급 전수 재검증에서 현재형 문서가 옛 판정 수를 든 자리 **여덟**을 찾았다
#:   (`unknown` 399 ×3 · `needs_cv` 226 ×3 · `blocked` 191 ×5 중 현재형 다섯).
#:   그 재발을 막으려고 `docnum_check.RETIRED` 에 191 을 넣었고, 그러자
#:   `PLAN §1 #51` 의 **2026-09-18 R3a 실측 기록**(「blocked 191 → 340」)이 같이
#:   걸렸다. 그 줄은 **그날 그랬다**는 기록이라 고칠 수 없다 — `stale-ok` 하나다.
#:
#:   ★ 이것이 §319-1 · §325 가 적은 그 정상 동작이다 — **판정이 움직이면
#:     회고가 굳는다.** 폐기값을 지키려면 그 값을 인용한 역사를 얼려야 한다.
RATCHET = 52

#: `tools/ratchet.py` 가 **줄었을 때만** 이 수를 고쳐 적는다(§309).
#: **느는** 쪽은 안 쓴다 — 그것은 받아적을 일이 아니라 결함이다.
RATCHETS = {"RATCHET": "down"}


def ratchet_values() -> dict[str, int]:
    """사유 없는 억제의 지금 수. **판정은 `check()` 소관**이다."""
    return {"RATCHET": sum(len(v) for v in tally().values())}


#: 갈래 → (무엇을 보나, 어디를 보나, 사유가 붙었는지 가르는 패턴)
#: 사유 = 억제 뒤에 오는 **말**. 있으면 안 센다.
FAMILIES: dict[str, tuple[re.Pattern, tuple[str, ...], tuple[str, ...]]] = {
    # 「noqa: RULE」 뒤에 아무 말도 없으면 사유가 없는 것이다.
    "noqa": (re.compile(r"#\s*noqa(?::\s*[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)?(?P<why>.*)$"),
             ("src", "tools", "tests"), ("*.py",)),
    # `# type: ignore[code]` — 같은 규칙.
    "type-ignore": (re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(?P<why>.*)$"),
                    ("src", "tools", "tests"), ("*.py",)),
    # `// eslint-disable-next-line rule -- 사유` — `--` 뒤가 eslint 의 사유 규약이다.
    "eslint": (re.compile(r"eslint-disable(?:-next-line|-line)?\s+\S+(?P<why>.*)$"),
               ("web/navi/src", "web/navi/test"), ("*.ts", "*.tsx")),
    # 문서 표기 둘. 줄 끝 표기라 뒤에 말이 붙을 자리가 없다 — 전부 센다.
    "voice-ok": (re.compile(r"<!--voice-ok-->(?P<why>)"), ("docs", "."), ("*.md", "*.py")),
    "stale-ok": (re.compile(r"<!--stale-ok-->(?P<why>)"), ("docs", "."), ("*.md",)),
}

#: 사유로 안 치는 꼬리 — 규칙 이름을 한 번 더 적은 것 따위.
_NOISE = re.compile(r"^[\s:,\-]*$")

#: 한 줄 안의 백틱 코드 구간.
_CODE = re.compile(r"`[^`]*`")


def mentioned(line: str, at: int) -> bool:
    """그 자리가 **백틱 안**인가 — 즉 표기를 *쓴* 것이 아니라 *말한* 것인가.

    ★ 2026-09-30 (DECISIONS §325). 종전 판은 이 구분을 안 했다. 그래서

        `MASTER §0-2`  | `<!--stale-ok-->` | 옛 숫자를 의도적으로 인용한 줄 |
        `README §도구`  tonecheck.py  … (`<!--voice-ok-->` 면 통과)

      **어휘를 정의하는 줄 자신**이 「사유 없이 검사를 끈 자리」로 세어졌다.
      규약을 적으면 빚이 느는 셈이라 아무도 규약을 안 적게 된다.

    ★ 새 규칙이 아니다 — `test_sources_of_truth` 의 `code_only` 가 같은 구분을
      먼저 했고(§222-5), 그때도 **오탐을 먼저 없애고 켰다.** 잘못된 경보는
      진짜 경보를 죽인다(MASTER §18-13).
    """
    return any(m.start() <= at < m.end() for m in _CODE.finditer(line))


def _files(roots: tuple[str, ...], globs: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for r in roots:
        base = ROOT / r
        if not base.is_dir():
            continue
        for g in globs:
            it = base.glob(g) if r == "." else base.rglob(g)
            out += [p for p in it
                    if "node_modules" not in p.parts and ".venv" not in p.parts]
    return sorted(set(out))


def hits(name: str) -> list[tuple[str, int, str]]:
    """그 갈래에서 **사유 없이** 끈 자리 (경로, 줄, 글)."""
    rx, roots, globs = FAMILIES[name]
    out = []
    for p in _files(roots, globs):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            # ★ `finditer` 다. 한 줄에 「표기를 말한 것」과 「실제로 붙인 것」이
            #   같이 있을 수 있고, `search` 면 앞의 백틱에 걸려 **뒤의 진짜를
            #   통째로 흘린다.** 미탐은 이 도구에서 제일 나쁜 방향이다.
            for m in rx.finditer(line):
                if _NOISE.match(m.group("why") or "") and not mentioned(line, m.start()):
                    out.append((p.relative_to(ROOT).as_posix(), i, line.strip()[:90]))
                    break
    return out


def tally() -> dict[str, list]:
    return {k: hits(k) for k in FAMILIES}


def check() -> int:
    t = tally()
    n = sum(len(v) for v in t.values())
    wide = max(len(k) for k in FAMILIES)
    for k, v in t.items():
        print(f"  {k:<{wide}}  {len(v):>4}")
    print(f"  {'합계':<{wide}}  {n:>4}   래칫 {RATCHET}")
    if n > RATCHET:
        print(f"\n✗ 사유 없는 억제가 {n} — 기록 {RATCHET} 보다 늘었다")
        print("  억제는 **검사를 끄는 것**이다. 끈 이유를 안 적으면 다음 사람은")
        print("  그것이 옳은지 알 수가 없고, 그러면 영영 안 지워진다.")
        print("  둘 중 하나를 해라 — ① 억제를 지우고 코드를 고친다")
        print("                      ② 억제 뒤에 사유를 한 줄 적는다")
        return 1
    if n < RATCHET:
        print(f"\n✗ 사유 없는 억제가 {n} 으로 줄었다 — "
              f"{__file__} 의 RATCHET 을 {n} 으로 조여라")
        print("  느슨해진 래칫은 초록으로 위장한다(`sizecheck` 머리말과 같은 사유).")
        return 1
    print(f"\n✓ 사유 없는 억제 {n} = 래칫 {RATCHET}")
    return 0


def selftest() -> int:
    """★ 사유가 있는 것과 없는 것을 실제로 가르는가. 빈 그물이 아닌가."""
    bad = []
    if not FAMILIES:
        bad.append("`FAMILIES` 가 비었다 — 볼 것이 없으면 통과가 아니다")

    def one(name: str, line: str) -> bool:
        rx = FAMILIES[name][0]
        m = rx.search(line)
        return bool(m) and bool(_NOISE.match(m.group("why") or ""))

    cases = [
        ("noqa", "x = 1  # noqa: BLE001", True, "사유 없는 noqa 를 안 센다"),
        ("noqa", "x = 1  # noqa: BLE001  아래에서 보고한다", False, "사유 붙은 noqa 를 센다"),
        ("noqa", "x = 1  # noqa", True, "규칙 없는 맨 noqa 를 안 센다"),
        ("noqa", "x = 1  # 평범한 주석", False, "평범한 주석을 억제로 센다"),
        ("type-ignore", "y: int = z  # type: ignore[assignment]", True, "사유 없는 type:ignore 를 안 센다"),
        ("type-ignore", "y: int = z  # type: ignore -- 상류 스텁이 틀렸다", False,
         "사유 붙은 type:ignore 를 센다"),
        ("eslint", "// eslint-disable-next-line react-hooks/exhaustive-deps", True,
         "사유 없는 eslint 억제를 안 센다"),
        ("eslint", "// eslint-disable-next-line react-hooks/exhaustive-deps -- ref 다", False,
         "사유 붙은 eslint 억제를 센다"),
        ("voice-ok", "<!--voice-ok-->", True, "voice-ok 를 안 센다"),
        ("stale-ok", "| 21 | 266/1,101 | <!--stale-ok-->", True, "stale-ok 를 안 센다"),
    ]
    # ★ 말한 것과 쓴 것. **어휘 정의 줄이 제 빚이 되면 규약을 못 적는다.**
    for fam, mark in (("voice-ok", "<!--voice-ok-->"), ("stale-ok", "<!--stale-ok-->")):
        said = f"| `{mark}` | 옛 것을 의도적으로 인용한 줄 |"
        rx = FAMILIES[fam][0]
        m = rx.search(said)
        if not (m and mentioned(said, m.start())):
            bad.append(f"{fam} — 백틱 안의 표기를 **쓴 것**으로 센다: {said!r}")
        used = f"노드접합 · 병합 후   1,101     {mark}"
        m = rx.search(used)
        if not (m and not mentioned(used, m.start())):
            bad.append(f"{fam} — 실제로 붙인 표기를 **말한 것**으로 흘린다: {used!r}")
        # ★ 한 줄에 둘 — 앞이 백틱이어도 **뒤의 진짜**를 집어야 한다.
        both = f"표기는 `{mark}` 다. 이 줄은 옛 수 1,101 을 든다 {mark}"
        if not any(not mentioned(both, m.start()) for m in rx.finditer(both)):
            bad.append(f"{fam} — 한 줄에 둘일 때 뒤엣것을 통째로 흘린다(미탐)")
    for fam, line, want, why in cases:
        if one(fam, line) is not want:
            bad.append(why + f" — {line!r}")
    # ★ 실물에서 한 갈래라도 0 이면 그 패턴이 죽었을 수 있다. 0 자체는 결함이
    #   아니지만 **전부 0 이면** 그물이 비었다는 뜻이다.
    if sum(len(v) for v in tally().values()) == 0:
        bad.append("실물에서 하나도 안 잡힌다 — 패턴이 실물과 갈렸다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 갈래 {len(FAMILIES)}개가 사유 있는 것과 없는 것을 가른다")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사유 없는 억제 래칫")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.list:
        for k, v in tally().items():
            print(f"\n── {k}  {len(v)}")
            for f, ln, s in v:
                print(f"    {f}:{ln}  {s}")
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
