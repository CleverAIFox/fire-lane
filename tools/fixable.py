#!/usr/bin/env python3
"""
fixable.py — **관문이 울 때 기계가 고칠 수 있는 것이 몇인가.** 래칫.

    uv run python tools/fixable.py            판정 (verify.sh · CI)
    uv run python tools/fixable.py --table    단계별 전수
    uv run python tools/fixable.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 (DECISIONS §362) ──────────────────────────────────
2026-10-03 실측. `tools/` 120개 중 **74개가 울기만 한다**(21,260줄). 검출은
기계가 하고 **수리는 100% 사람이 한다.** 그래서 관문이 늘수록 사람의 일이
늘었다 — 갑옷이 아니라 **알람 시계를 여든아홉 개 산 것**이다.

`verify.sh` 가 수리를 안 하는 것은 **옳다.** 그 파일이 그 사유를 적는다 —

    ★ `--write` 를 여기서 안 돈다. 쓰고 나서 재면 이 관문은 영영 초록이다.

검사기가 자기를 고치면 검사가 아니다. 빠진 것은 그 판단이 아니라 **수리 문**
이다. 검사 문만 있고 수리 문이 없으니 수리가 사람 손으로 흘러갈 수밖에 없다.

`tools/fix.sh` 가 그 문이고, 이 도구는 **그 문이 덜 열렸는가**를 센다.

── 세 갈래 ────────────────────────────────────────────────────
    기계     답이 하나다. 문이 돈다
    사람     수리 경로는 있는데 **판단이 먼저다** — golden 재잠금 · 도장 ·
             지문 · 레이크가 필요한 것 · 지우는 것 · 네트워크
    없음     고칠 것이 없다. 시험 · 린트 · 빌드 — 결함은 코드에 있다

★ **「사람」을 「기계」로 옮기는 것이 늘 이득은 아니다.** `docseal stamp` 를
  자동으로 찍으면 봉인이 죽는다 — 그 도장의 뜻이 「사람이 절과 코드를 같이
  읽었다」이기 때문이다. 그래서 이 도구가 미는 수는 「사람 0」이 아니라
  **「기계인데 문에 안 걸린 것 0」** 이다.

IN    tools/verify.sh (단계와 그 명령) · tools/fix.sh (문이 부르는 목록)
OUT   표준출력 (판정)
PARAM UNDOORED (래칫)
밖    **고치지 않는다.** 고치는 것은 `tools/fix.sh` 다.
      **분류가 옳은가는 안 본다.** 어느 단계가 「사람」인지는 사람의 판단이고
      그 사유는 `fix.sh` 의 표에 적힌다. 여기가 드는 것은
      「기계라고 적어 놓고 문에 안 건 것이 있는가」 하나다.
      **`--fix` 를 가진 도구를 다 돌려야 한다고 말하지 않는다** — `golden lock`
      도 `--write` 류이고 그것을 자동으로 돌리면 판정이 조용히 잠긴다.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify.sh"
DOOR = ROOT / "tools" / "fix.sh"

#: 수리 깃발로 볼 것. **`--yes` 는 뺀다** — 그것은 확인이지 수리가 아니다.
REPAIR_FLAGS = ("--write", "--apply", "--fix", "--sync", "--repair", "--relock")

#: 수리 경로가 있지만 **사람이 먼저 판단한다.** 키는 도구 경로, 값은 사유.
#: ★ 이 표가 「왜 자동화 안 하나」의 정본이다. 비면 그 사유가 사라진다.
HUMAN_FIRST: dict[str, str] = {
    "tools/golden.py":
        "`lock` 은 판정의 사진을 다시 찍는다. 찍기 전에 **판정 네 수치가 움직였는지**를 "
        "사람이 보고 PR 본문에 전후를 적어야 한다. 자동으로 찍으면 움직인 판정이 "
        "그대로 정답이 된다",
    "tools/docseal.py":
        "`stamp` 의 뜻이 **「사람이 절과 코드를 같이 읽었다」**이다. 기계가 찍으면 그 "
        "도장은 아무것도 안 뜻한다 — 봉인 전체가 죽는다. 이 하나는 영원히 사람이다",
    "tools/fieldseal.py":
        "실측 층의 무결성 지문이다. 그 도구 머리말이 **「★ 사람이 친다」**고 적는다 — "
        "인용의 밑동이 움직였다는 뜻이라 왜 움직였는지를 같이 적어야 한다",
    "tools/ledger_schema.py":
        "`--apply` 가 **레이크 실물을 읽어** 대장 `schema` 를 갱신한다. 레이크가 있는 "
        "기계에서만 돌고, 대장 값이 바뀌므로 무엇이 바뀌었는지를 사람이 본다",
    "tools/actionpin.py":
        "`--write` 가 **네트워크로** 태그를 풀어 지문을 받는다. 문이 네트워크를 타면 "
        "끊긴 자리에서 「고쳤다」와 「못 받았다」가 섞인다",
    "tools/tidy.py":
        "**지운다.** 지우는 것에 기본값을 주지 않는다 — 그 도구가 `--yes` 를 요구하는 "
        "것이 그 사유다",
    "tools/sweep.py":
        "**레이크를 지운다.** 지운 것을 되돌리려면 제공기관에서 다시 내려받아야 하고 "
        "어떤 자료는 그 판이 더는 없다 — 되돌릴 수 없는 일에 기본값을 주지 않는다",
    "tools/install_navi.py":
        "`--from <폴더>` 로 **밖에서 받은 작업물을 저장소 자리에 앉힌다.** 그 폴더가 "
        "어디인지는 사람만 알고, 반복해 도는 문이 그것을 추측하면 엉뚱한 것을 덮는다",
    "tools/navi_setup.py":
        "루트에 떨어진 일회성 스크립트를 규약 자리로 옮기는 **이사 도구**다. "
        "이사는 한 번이고, 매번 도는 문에 걸면 이미 제자리인 것을 또 만진다",
}


#: 수리 깃발이 **글자로는 있는데 실은 없는** 것. 키는 도구 경로, 값은 사유.
#: ★ 깃발이 「그 깃발은 폐지됐다」를 찍으려고 남아 있는 경우가 있다. 글자만
#:   보면 수리 경로로 세어지고, 그러면 문이 죽은 깃발을 부른다 — 실제로 이
#:   도구의 첫 판이 `plan_renumber --apply` 를 불렀고 그 도구가 거절했다.
NO_REPAIR: dict[str, str] = {
    "tools/plan_renumber.py":
        "`--apply` 는 2026-09-20 에 **폐지됐다**(DECISIONS §205). 그 깃발이 아직 "
        "코드에 있는 것은 **「폐지됐다」를 찍기 위해서**다. §1 행 번호는 영구 "
        "식별자라 당기면 밖의 인용 백여 곳이 조용히 다른 행을 가리킨다. "
        "이 도구는 이제 **검사만** 한다 — 결번이 정상이다",
}


def steps() -> list[tuple[str, str]]:
    """`verify.sh` 의 (단계 이름, 명령). **정본은 그 파일 하나다.**"""
    txt = VERIFY.read_text(encoding="utf-8")
    return re.findall(r'^\s*step\s+"([^"]+)"\s+(.*)$', txt, re.M)


def _flags(p: Path) -> set[str]:
    """도구가 **코드에서** 받는 깃발. 머리말의 사용 예시는 선언이 아니다(§283-3)."""
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef))
            and ast.get_docstring(n) is not None}
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value.startswith("--") and id(n) not in docs}


def tool_of(cmd: str) -> str | None:
    m = re.search(r"(tools/[\w/]+\.(?:py|sh))", cmd)
    return m.group(1) if m else None


def door_tools() -> set[str]:
    """`fix.sh` 가 실제로 부르는 도구. 문이 없으면 빈 집합이다."""
    if not DOOR.is_file():
        return set()
    txt = DOOR.read_text(encoding="utf-8")
    return set(re.findall(r"(tools/[\w/]+\.(?:py|sh))", txt))


def classify() -> dict[str, list[tuple[str, str]]]:
    """단계를 셋으로 가른다 → {'기계': [...], '사람': [...], '없음': [...]}"""
    out: dict[str, list[tuple[str, str]]] = {"기계": [], "사람": [], "없음": []}
    seen: set[tuple[str, str]] = set()
    for name, cmd in steps():
        tool = tool_of(cmd)
        if (name, tool or "") in seen:
            continue
        seen.add((name, tool or ""))
        if tool and tool in HUMAN_FIRST:
            out["사람"].append((name, tool))
            continue
        if tool and tool in NO_REPAIR:
            out["없음"].append((name, tool))
            continue
        if not tool or not (ROOT / tool).is_file() or not tool.endswith(".py"):
            out["없음"].append((name, tool or cmd.split()[0]))
            continue
        if _flags(ROOT / tool) & set(REPAIR_FLAGS):
            out["기계"].append((name, tool))
        else:
            out["없음"].append((name, tool))
    return out


def undoored() -> list[tuple[str, str]]:
    """**기계인데 문에 안 걸린 것.** 이 수를 민다."""
    door = door_tools()
    return [(n, t) for n, t in classify()["기계"] if t not in door]



# ── 둘째 팔 — **문과 관문이 같은 도구의 다른 모드를 부르는 자리** ────
#
# ★ 2026-10-03 (DECISIONS §374). 첫 팔은 「기계인데 문에 **안 걸린** 도구」를
#   센다. 그런데 **걸려 있는데도 안 덮이는** 자리가 있었다 — `fix.sh` 가
#   `dms.py --apply`(scan 모드)를 부르고, 관문은 `dms.py verify` 다. 문이
#   「고칠 것이 없다」고 답한 바로 그때 관문은 **빨갰다.**
#
#   실기(2026-10-03): 합본 배치를 만들어 놓고 `fix.sh` 를 다 돌려 「빨강 0」을
#   보고 보냈다. 전수 verify 를 돌리니 「죽은 강제자 참조」가 빨갰다 —
#   §367 의 강제자 칸이 §370 의 개명을 안 따라온 것이었다. **문이 그 자리를
#   볼 수 없다는 사실이 어디에도 안 적혀 있었다.**
#
# ★ 이 팔이 미는 수는 「모드를 맞춰라」가 **아니다.** 맞출 수 없는 자리가 있다 —
#   「`_oneway` 가 어디로 갔나」는 답이 하나가 아니다. 미는 것은
#   **「안 덮인다는 사실이 적혀 있는가」**이고, 적히면 `fix.sh` 가 그것을 찍는다.
#: `"도구::관문모드"` → 사유. **적는 순간 `fix.sh` 가 사람에게 찍는다.**
MODE_SPLIT: dict[str, str] = {
    "tools/dms.py::verify":
        "`--apply` 는 `scan` 이 찾는 것(절↔코드 물림 · 크기)을 고친다. `verify` 가 "
        "찾는 **죽은 강제자 지목**은 「그 함수가 어디로 갔나」이고 답이 하나가 "
        "아니다 — 옮겼는지 지웠는지 이름만 바뀌었는지는 사람이 안다",
    "tools/dms.py::delta":
        "**측정이다.** 강제자가 소급으로 몇 늘었나를 세는 자리라 고칠 것이 없다 — "
        "수가 늘면 그것은 결함이 아니라 기록이다",
    "tools/dms.py::ancestry":
        "봉인 조상 사슬을 본다. 끊기면 고치는 방법은 **봉인을 다시 찍는 것**이고 "
        "그것은 `HUMAN_FIRST` 의 `docseal`·`golden` 과 같은 사유로 사람이 한다",
}


def _subs(txt: str, kind: str) -> dict[str, set[str]]:
    """`fix`/`step` 줄에서 (도구 → 그 줄이 쓰는 서브명령 집합)."""
    out: dict[str, set[str]] = {}
    for line in re.findall(rf'^\s*{kind}\s+"[^"]+"\s+(.*)$', txt, re.M):
        tool = tool_of(line)
        if not tool or not tool.endswith(".py"):
            continue
        parts = line.split()
        try:
            i = next(i for i, p in enumerate(parts) if tool in p)
        except StopIteration:
            continue
        rest = [p for p in parts[i + 1:] if not p.startswith("-")]
        out.setdefault(tool, set()).add(rest[0] if rest else "")
    return out


def mode_gaps() -> list[tuple[str, str]]:
    """**문이 안 덮는 관문 모드** (도구, 모드). 사유가 적힌 것은 빼고 센다."""
    if not DOOR.is_file():
        return []
    doors = _subs(DOOR.read_text(encoding="utf-8"), "fix")
    gates = _subs(VERIFY.read_text(encoding="utf-8"), "step")
    out = []
    for tool, gs in sorted(gates.items()):
        ds = doors.get(tool)
        if ds is None:
            continue                      # 문이 아예 없다 — 첫 팔이 든다
        for g in sorted(gs):
            if g in ds:
                continue
            if f"{tool}::{g}" in MODE_SPLIT:
                continue
            out.append((tool, g))
    return out


def split_rows() -> list[tuple[str, str, str]]:
    """사유가 적힌 갈림 전수 (도구, 모드, 사유). `fix.sh` 가 이것을 찍는다."""
    return [(k.split("::")[0], k.split("::")[1], v) for k, v in sorted(MODE_SPLIT.items())]

#: 기계가 고칠 수 있는데 `fix.sh` 가 안 부르는 단계. **0 이 목표다.**
#: ★ 이력 — 2026-10-03 §362 첫 실측 10 (문을 세우기 전) → 문을 세우고 0.
UNDOORED = 0

#: 문이 안 덮는 관문 모드 중 **사유가 안 적힌** 것. **0 이 목표다.**
#: ★ 이력 — 2026-10-03 §374 첫 실측 3(`dms.py` 의 `verify`·`delta`·`ancestry`),
#:   셋 다 사유를 적어 0.
MODE_GAP = 0

RATCHETS = {"UNDOORED": "down", "MODE_GAP": "down"}


def ratchet_values() -> dict[str, int]:
    return {"UNDOORED": len(undoored()), "MODE_GAP": len(mode_gaps())}


def check() -> int:
    c = classify()
    tot = sum(len(v) for v in c.values())
    print(f"verify 단계 {tot}")
    print(f"  기계가 고친다   {len(c['기계']):>3}   `tools/fix.sh` 가 돈다")
    print(f"  사람이 먼저     {len(c['사람']):>3}   사유는 `fixable.HUMAN_FIRST` 에 있다")
    print(f"  고칠 것 없음    {len(c['없음']):>3}   시험 · 린트 · 빌드")

    bad = undoored()
    if not DOOR.is_file():
        print(f"\n✗ 수리 문이 없다 — {DOOR.relative_to(ROOT)}")
        return 1
    rc = 0
    if len(bad) > UNDOORED:
        print(f"\n✗ 기계가 고칠 수 있는데 문에 안 걸린 단계 {len(bad)} > 래칫 {UNDOORED}")
        for n, t in bad:
            print(f"    {n:28} {t}")
        print("\n  `tools/fix.sh` 에 그 도구를 더하거나, 사람이 먼저여야 하면")
        print("  `fixable.HUMAN_FIRST` 에 **사유와 함께** 적어라.")
        rc = 1
    elif len(bad) < UNDOORED:
        print(f"\n✗ 문에 안 걸린 단계 {len(bad)} < 래칫 {UNDOORED} — 래칫을 그 수로 내려라")
        print("  uv run python tools/ratchet.py --write")
        rc = 1
    dead = [t for t in (*HUMAN_FIRST, *NO_REPAIR) if not (ROOT / t).is_file()]
    if dead:
        print(f"\n✗ 면제표가 없는 도구를 든다 {dead} — 죽은 선언이다")
        rc = 1
    # ★ 반대 방향. `NO_REPAIR` 가 **실은 수리 깃발이 없는** 도구를 들면 그 줄은
    #   거짓이다 — 깃발이 사라진 날 아무도 모른다.
    inert = [t for t in NO_REPAIR
             if (ROOT / t).is_file() and not (_flags(ROOT / t) & set(REPAIR_FLAGS))]
    if inert:
        print(f"\n✗ `NO_REPAIR` 가 **깃발도 없는** 도구를 든다 {inert} — 줄을 지워라")
        rc = 1
    # ── 둘째 팔 (§374) ─────────────────────────────────────────
    gaps = mode_gaps()
    if len(gaps) > MODE_GAP:
        print(f"\n✗ 문이 **안 덮는** 관문 모드 {len(gaps)} > 래칫 {MODE_GAP}")
        for tool, g in gaps:
            print(f"    {tool}  관문 모드 `{g or '(기본)'}`")
        print("\n  문이 그 모드도 부르게 하거나, 부를 수 없으면")
        print("  `fixable.MODE_SPLIT` 에 **사유와 함께** 적어라 — 그러면 `fix.sh`")
        print("  가 「이 관문은 문이 안 덮는다」를 사람에게 찍는다.")
        rc = 1
    elif len(gaps) < MODE_GAP:
        print(f"\n✗ 안 덮는 모드 {len(gaps)} < 래칫 {MODE_GAP} — 래칫을 그 수로 내려라")
        rc = 1
    dead_split = [k for k in MODE_SPLIT if not (ROOT / k.split("::")[0]).is_file()]
    if dead_split:
        print(f"\n✗ `MODE_SPLIT` 이 없는 도구를 든다 {dead_split} — 죽은 선언이다")
        rc = 1
    # ★ 반대 방향 — 문이 **실은 덮는** 모드를 「안 덮는다」고 적으면 그 줄이 거짓이다
    doors = _subs(DOOR.read_text(encoding="utf-8"), "fix") if DOOR.is_file() else {}
    covered = [k for k in MODE_SPLIT
               if k.split("::")[1] in doors.get(k.split("::")[0], set())]
    if covered:
        print(f"\n✗ `MODE_SPLIT` 이 **문이 덮는** 모드를 든다 {covered} — 줄을 지워라")
        rc = 1

    if rc == 0:
        print(f"\n✓ 기계가 고칠 수 있는 것은 전부 문에 걸려 있다 (사람 {len(c['사람'])})")
        if MODE_SPLIT:
            print(f"  ★ 그런데 문이 **안 덮는** 관문 모드가 {len(MODE_SPLIT)} 있다 —"
                  " 사유는 `MODE_SPLIT` 에 있고 `fix.sh` 가 찍는다")
    return rc


def table() -> int:
    c = classify()
    door = door_tools()
    for k in ("기계", "사람", "없음"):
        print(f"\n═══ {k}  {len(c[k])}")
        for n, t in c[k]:
            mark = ""
            if k == "기계":
                mark = "  문" if t in door else "  ★ 문 밖"
            elif k == "사람":
                mark = "  — " + " ".join(HUMAN_FIRST.get(t, "").split())[:58]
            print(f"  {n:30} {t:30}{mark}")
    return 0


def selftest() -> int:
    """★ 합성으로 민다. 실제 저장소 수는 `check()` 가 든다."""
    import tempfile
    global VERIFY, DOOR
    keep_v, keep_d = VERIFY, DOOR
    fails = []
    try:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            VERIFY = d / "verify.sh"
            DOOR = d / "fix.sh"
            VERIFY.write_text(
                'step "가짜 수리됨" uv run python tools/ratchet.py\n'
                'step "가짜 사람" uv run python tools/golden.py check\n'
                'step "가짜 없음" uv run pytest\n', encoding="utf-8")
            DOOR.write_text("# 빈 문\n", encoding="utf-8")
            c = classify()
            if [n for n, _ in c["기계"]] != ["가짜 수리됨"]:
                fails.append(f"기계 갈래가 틀렸다 — {c['기계']}")
            if [n for n, _ in c["사람"]] != ["가짜 사람"]:
                fails.append(f"사람 갈래가 틀렸다 — {c['사람']}")
            if [n for n, _ in c["없음"]] != ["가짜 없음"]:
                fails.append(f"없음 갈래가 틀렸다 — {c['없음']}")
            if len(undoored()) != 1:
                fails.append("문이 비었는데 「문 밖」을 못 센다 — 늘 통과하는 검사다")

            # ★ 반대 방향. 문에 걸면 0 이어야 한다. 아니면 늘 우는 검사다.
            DOOR.write_text("uv run python tools/ratchet.py --write\n", encoding="utf-8")
            if undoored():
                fails.append(f"문에 걸었는데 아직 「문 밖」이다 — {undoored()}")
    finally:
        VERIFY, DOOR = keep_v, keep_d

    # ★ 깃발 읽기가 머리말을 안 읽는가(§283-3).
    import tempfile as _t
    with _t.TemporaryDirectory() as td:
        p = Path(td) / "x.py"
        p.write_text('"""쓰기 — `x.py --write` 로 고친다."""\nprint(1)\n', encoding="utf-8")
        if "--write" in _flags(p):
            fails.append("머리말의 사용 예시를 깃발 선언으로 센다")
        p.write_text('"""머리말."""\nimport sys\nif sys.argv[1:] == ["--write"]: pass\n',
                     encoding="utf-8")
        if "--write" not in _flags(p):
            fails.append("손으로 가른 깃발을 못 읽는다")

    if not steps():
        fails.append("실물 verify.sh 에서 단계를 하나도 못 읽었다 — 빈 그물이다")

    for f in fails:
        print(f"  ✗ {f}")
    print("✓ 자기검사 통과 · 판별식 7" if not fails else f"✗ {len(fails)}건")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    rest = list(sys.argv[1:] if argv is None else argv)
    if rest == ["--selftest"]:
        return selftest()
    if rest == ["--table"]:
        return table()
    if rest:
        print((__doc__ or "").strip())
        return 2
    return check()


if __name__ == "__main__":
    sys.exit(main())
