#!/usr/bin/env python3
"""
env_check.py — 환경변수 선언 ↔ 실물. **양방향이다.**

    uv run python tools/env_check.py              검사
    uv run python tools/env_check.py --readers    os.environ 독자 전수
    uv run python tools/env_check.py --selftest   ★ 프로브가 살아 있나

★ 왜 양방향인가.
  한쪽만 걸면 예외값에 영원히 머문다. 두 방향 다 실제로 썩는다 —

    코드 → 예시   새 변수를 코드에 넣고 `.env.example` 에 안 적는다.
                  다음 사람이 기계를 세팅하면 그 변수만 비어 있고,
                  증상은 엉뚱한 데서 난다(오늘 FIRE_LANE_INBOX 가 그랬다).
    예시 → 코드   예시에 있는데 코드가 안 쓴다. `FIRE_LANE_RAW` 가 그 상태다.
                  지워진 변수를 계속 세팅하게 만들고, 그게 현역을 이겼다.

★ **단일 독자**가 키 목록 대조보다 세다.
  키 목록은 `os.environ[f"FIRE_LANE_{x}"]` 같은 동적 접근을 못 잡는다.
  "paths.py 밖에서 os.environ 금지" 는 문법만 보면 되고 빠져나갈 구멍이 없다.
  지금은 12곳이 어긴다 — 그래서 이 검사는 **지금 빨갛다.**
  숫자를 줄이는 것이 일이고, 검사를 무르게 만드는 것이 일이 아니다.

★ 면제는 `os.environ` 전체를 보되 명시적으로 적는다.
  `FIRE_LANE_*` 만 보면 `GDAL_*` 같은 것이 또 열두 곳에 흩어지고,
  그때 두 번째 검사를 만들게 된다. 면제는 적히고 세지므로 낡지 않는다.

★ **2026-09-24. 셸이 검사 밖이었다**(DECISIONS §226-1 · `tools/scopedecl.py` 가 잡았다).
  이 파일 머리가 「오늘 FIRE_LANE_INBOX 가 그랬다」고 적고 있는데, 정작 그 변수를
  쓰는 자리는 `tools/fl.sh` · `tools/inbox_fl.sh` **셸 둘**이고 이 검사는 `.py` 만
  훑었다. 즉 **자기가 사례로 든 그 변수를 못 보는 상태**로 열흘을 돌았다.
  「범위가 이름보다 좁고 그것이 선언돼 있지 않다」 족의 일곱 번째다(PLAN §13).

IN    .env.example · src/**.py · tools/**.py · tools/*.sh
OUT   없음 (검사)
밖    **셸의 단일 독자 규율은 안 본다.** `readers()` 는 파이썬 AST 라 `.sh` 를
      못 읽는다 — 셸에서는 키가 쓰이는가만 보고 `paths.py` 경유 여부는 안 본다.
      셸에 `paths.py` 같은 접근자를 둘 방법이 없기 때문이다.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"

# ── 분류 ──────────────────────────────────────────────────────
# 설정  — `.env.example` 에 반드시 있어야 한다
SETTINGS = {"FIRE_LANE_DATA", "FIRE_LANE_INBOX",
            "FIRE_LANE_STAGE", "FIRE_LANE_BACKUP",
            # ★ 2026-09-24. 셸에만 사는 변수. `.py` 만 훑던 시절엔 안 보였다.
            "FIRE_LANE_REPO"}
# 스위치 — 일회성 디버그. 셸 export 로 쓴다. 예시에 적으면 잡음이다
SWITCHES = {"FIRE_LANE_DEBUG_SEG", "FIRE_LANE_DEBUG_XY", "FIRE_LANE_MIX_SRC",
            "FIRE_LANE_NO_MERGE", "FIRE_LANE_OLD_SNAP",
            # ★ 2026-09-18 (§188-1). R3a 뼈대 시험 교체. R3c 가 기본을 바꾸면 여기서 뺀다.
            "FIRE_LANE_SKELETON"}
# 폐기  — 설정돼 있으면 시끄럽게. 예시에 있으면 안 된다
RETIRED = {"FIRE_LANE_RAW"}

# ── 단일 독자 면제 ────────────────────────────────────────────
#   paths      정본
#   quiet_gdal GDAL_* 를 끄는 자리. 우리 변수가 아니다
#   tests/     검사가 환경을 흉내 내는 것은 정상이다
# ★ 2026-09-13. `tools/batches/` 를 뺐다. 디렉터리가 없어졌고, 사문화된
#   면제를 남기면 같은 이름이 다시 들어왔을 때 조용히 통과한다.
# ★ 2026-09-14. 넷을 더했다. **접근자로 못 바꾸는 것들**이고, 사유 없이
#   넣지 않는다 — 사유 없는 면제는 검사를 끄기만 한다(RED.txt 와 같은 규율).
#   pipeline        자식 프로세스에 환경을 **넘긴다.** 읽는 것이 아니다
#   doctor          기계 진단이 본업. 동적 접근이 그 도구의 내용이다
#   pr_body_check   GITHUB_*. CI 가 주는 값이지 우리 변수가 아니다
#   pull_data       NO_COLOR. 표시용 관례 변수다
EXEMPT = ("src/firelane/paths.py", "src/firelane/quiet_gdal.py", "tests/",
          "src/firelane/pipeline.py", "tools/doctor.py",
          "tools/pr_body_check.py", "tools/pull_data.py")

# ★ 2026-09-14. `paths.env|flag|secret("KEY")` 를 같이 본다.
#   단일 독자로 옮기는 순간 종전 판은 그 키를 **못 보게 됐다** —
#   `guards.py` 가 접근자로 바뀌자 `FIRE_LANE_STAGE` 가 "코드가 안 쓴다"
#   로 울었다. 자리를 하나로 만드는 것의 값은 스캐너가 그 자리를 알아야
#   나온다. 옮기면서 같이 안 옮기면 옮긴 만큼 눈이 먼다.
ENV_RE = re.compile(r"""os\.environ(?:\.get)?[\[(]\s*["']([A-Z_]+)["']|"""
                    r"""getenv\(\s*["']([A-Z_]+)["']|"""
                    r"""paths\.(?:env|flag|secret)\(\s*["']([A-Z_]+)["']""")

# ★ 셸의 참조. `$FIRE_LANE_X` · `${FIRE_LANE_X}` · `FIRE_LANE_X=` 세 꼴 전부.
#   대입도 쓰임으로 센다 — `fl.sh` 는 `.env` 를 읽어 쓰므로 대입이 곧 계약이다.
SH_RE = re.compile(r"\$\{?(FIRE_LANE_[A-Z0-9_]+)\}?|^\s*(?:export\s+)?"
                   r"(FIRE_LANE_[A-Z0-9_]+)=", re.M)


def _py() -> list[Path]:
    return sorted([*(ROOT / "src").rglob("*.py"), *(ROOT / "tools").rglob("*.py")])


def _sh() -> list[Path]:
    """셸도 환경변수의 소비자다. 2026-09-24 이전에는 이 목록이 없었다."""
    return sorted((ROOT / "tools").glob("*.sh"))


def used_keys() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in _py():
        for m in ENV_RE.finditer(p.read_text(encoding="utf-8", errors="replace")):
            k = m.group(1) or m.group(2) or m.group(3)
            if k and k.startswith("FIRE_LANE"):
                out.setdefault(k, []).append(str(p.relative_to(ROOT)))
    for p in _sh():
        for m in SH_RE.finditer(p.read_text(encoding="utf-8", errors="replace")):
            k = m.group(1) or m.group(2)
            if k:
                out.setdefault(k, []).append(str(p.relative_to(ROOT)))
    return out


def declared_keys() -> set[str]:
    if not EXAMPLE.exists():
        return set()
    keys = set()
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k = line.removeprefix("export ").partition("=")[0].strip()
        if k:
            keys.add(k)
    return keys


def readers() -> list[tuple[str, int, str]]:
    """`os.environ` 을 **코드에서** 읽는 곳.

    ★ 2026-09-13. 종전에는 줄 단위 정규식이었고 `#` 뒤만 잘라냈다. 그래서
      **도크스트링과 print 문자열을 독자로 셌다** — 이 파일 자신의 6줄이
      그렇게 잡혔고, 26곳 중 6곳이 오탐이었다.

      틀린 분모로는 줄어드는지 알 수 없다. `dms` 가 417 을 못 재현해
      350 으로 갈아탄 것과 같은 문제다(2026-09-13).

    ★ AST 로 보면 문자열은 애초에 코드가 아니다. 정규식을 정교하게
      만드는 길로 가지 않는다 — 문법을 아는 것이 문법을 흉내 내는 것을
      이긴다.
    """
    hits = []
    for p in _py():
        rel = str(p.relative_to(ROOT))
        if any(rel.startswith(e) for e in EXEMPT):
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        for i in _environ_lines(src):
            hits.append((rel, i, src.splitlines()[i - 1].strip()[:70]))
    return sorted(set(hits))


def _environ_lines(src: str) -> list[int]:
    """`os.environ` 에 닿는 줄 번호.

    ★ 2026-09-13. `import os as _os` 를 따라간다. 별칭을 안 따라가던
      판이 `seg/params.py` 다섯 곳을 통째로 놓쳤다 — 오탐 6을 없애며
      미탐 5를 만들었고, 숫자가 줄어서 일이 잘 되는 것처럼 보였다.
      **프로브가 좁아지는 쪽으로 망가지면 아무도 모른다.**

    ★ `from os import environ` 도 본다. 그쪽이 더 안 보인다.
    """
    import ast

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    names, bare = {"os"}, set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for al in n.names:
                if al.name == "os":
                    names.add(al.asname or "os")
        elif isinstance(n, ast.ImportFrom) and n.module == "os":
            for al in n.names:
                if al.name == "environ":
                    bare.add(al.asname or "environ")
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Attribute) and n.attr == "environ"
                and isinstance(n.value, ast.Name) and n.value.id in names):
            out.append(n.lineno)
        elif isinstance(n, ast.Name) and bare and n.id in bare:
            out.append(n.lineno)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readers", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    used, decl = used_keys(), declared_keys()
    fail = 0

    if a.selftest:
        # ★ 0건이 청결인지 죽음인지 가르는 유일한 방법이다(HANDOFF 원칙 ④).
        print("양성 대조 — 없는 키를 넣으면 잡히나")
        ok1 = "FIRE_LANE_GHOST" not in used and "FIRE_LANE_GHOST" not in decl
        probe = dict(used); probe["FIRE_LANE_GHOST"] = ["<가짜>"]
        ok2 = bool(set(probe) - decl - SWITCHES - RETIRED)
        print(f"  · 유령 키 미검출 상태  {ok1}")
        print(f"  · 넣으면 검출          {ok2}")
        # ★ 2026-09-14. `(0 이면 프로브를 의심하라)` 를 뗐다. 그 말은 실물
        #   0 이 청결인지 죽음인지 가를 장치가 없던 시절의 것이다. 지금은
        #   아래 카나리아가 그 일을 하고, **0 은 목표 달성**이다.
        print(f"  · 독자 프로브          {len(readers())}곳 (0 이 목표다)")
        # ★ 별칭 카나리아. 2026-09-13 에 `import os as _os` 를 못 봐서
        #   `seg/params.py` 다섯 곳을 통째로 놓쳤다. 프로브가 **좁아지는**
        #   쪽으로 망가지면 숫자가 줄어 일이 잘 되는 것처럼 보인다.
        forms = {
            "os.environ": "import os\nx = os.environ.get('A')\n",
            "별칭 _os.environ": "import os as _os\nx = _os.environ.get('A')\n",
            "from os import environ": "from os import environ\nx = environ.get('A')\n",
        }
        ok3 = True
        for label, code in forms.items():
            got = bool(_environ_lines(code))
            print(f"  · {label:24} {got}")
            ok3 = ok3 and got
        # ★ 2026-09-14. `readers()` 를 생존 조건에서 뺐다. 그것이 비면
        #   빨강이라는 규칙은 독자가 남아 있던 시절에 맞았다 — 목표를
        #   이루는 순간 프로브가 자기가 죽은 줄 안다.
        #   **생존은 카나리아가 증명한다. 실물 수는 결과지 증거가 아니다.**
        # ★ 분모가 0 에 닿는 검사는 전부 같은 함정을 갖는다.
        #   `dupcheck` · `vintage_check` · `dms verify` 도 그렇다 —
        #   셋은 카나리아나 `--max` 래칫이 있어서 아직 안 걸렸을 뿐이다.
        return 0 if (ok1 and ok2 and ok3) else 1

    if a.readers:
        r = readers()
        print(f"── os.environ 독자 — paths.py 밖 {len({x[0] for x in r})}파일 · {len(r)}곳")
        for rel, ln, src in r:
            print(f"  {rel}:{ln}  {src}")
        print("\n★ 목표는 0 이다. paths.py 가 유일한 독자여야 동적 접근까지 막힌다.")
        return 0

    # ── ① 코드 → 예시 ────────────────────────────────────────
    miss = sorted((set(used) & SETTINGS) - decl)
    ghost = sorted(set(used) - decl - SETTINGS - SWITCHES - RETIRED)
    if miss or ghost:
        fail = 1
        print("✗ 코드가 쓰는데 .env.example 에 없다")
        for k in miss + ghost:
            print(f"    {k}   ← {', '.join(sorted(set(used[k])))[:70]}")
        print("  새 기계를 세팅하면 이 값만 비고, 증상은 엉뚱한 데서 난다.")

    # ── ② 예시 → 코드 ────────────────────────────────────────
    dead = sorted(decl - set(used))
    if dead:
        fail = 1
        print("✗ .env.example 에 있는데 코드가 안 쓴다")
        for k in dead:
            print(f"    {k}")
        print("  지워진 변수를 계속 세팅하게 만든다. FIRE_LANE_RAW 가 그랬다.")

    # ── ③ 분류 위반 ──────────────────────────────────────────
    bad = sorted(decl & (SWITCHES | RETIRED))
    if bad:
        fail = 1
        print("✗ 예시에 있으면 안 되는 것")
        for k in bad:
            why = "일회성 디버그 스위치" if k in SWITCHES else "폐기된 변수"
            print(f"    {k}   {why}")

    # ── ④ 단일 독자 ──────────────────────────────────────────
    r = readers()
    files = sorted({x[0] for x in r})
    if r:
        fail = 1
        print(f"✗ paths.py 밖에서 os.environ 을 읽는다 — {len(files)}파일 · {len(r)}곳")
        for f in files:
            print(f"    {f}")
        print("  ★ 키 목록 대조는 동적 접근을 못 잡는다. 단일 독자는 못 빠져나간다.")
        print("    tools/env_check.py --readers 로 줄 번호를 본다.")

    if not fail:
        print(f"✓ 없음 — 설정 {len(decl)}키 · 독자 paths.py 하나")
    return fail


if __name__ == "__main__":
    raise SystemExit(main())
