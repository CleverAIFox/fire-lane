#!/usr/bin/env python3
"""
b5_env.py — **경로 설정을 `.env` 하나로 모은다.**

    uv run python tools/batches/b5_env.py            무엇을 할지만
    uv run python tools/batches/b5_env.py --apply    실제로

★ 오늘 이것 때문에 네 번 헛돌았다.
  `~/.fire-lane.local` 은 **아무도 안 읽는 파일**이었다. 인수인계서는
  "복원됨" 이라고 적었는데 `paths.py:35` 의 `os.environ.get` 이 전부다.
  선언이 실물보다 앞선 전형이고, 이 저장소가 232번 본 모양이다.

★ **셸이 `.env` 를 이긴다.** 반대로 하면 `FIRE_LANE_RAW` 사고가 재현된다 —
  `paths.py:40` 이 적어놨다. 폐기된 변수가 현역을 경고 없이 이기고 있었고,
  *"기계마다 .bashrc 를 고치는 것은 해결이 아니다 — 코드가 알아채야 한다."*
  `.env` 는 **기본값**이고 `export` 는 그 판을 덮는 것이다.
  파일이 조용히 셸을 이기면 "내가 export 했는데 왜 안 먹지" 가 된다.

★ **의존성을 안 늘린다.** `python-dotenv` 를 `paths.py` 에 물리면 안 된다.
  이 모듈은 저장소 전체가 import 하고, `wmax_audit.py` 같은 순수
  표준 라이브러리 도구도 그 아래 `params.py` 를 탄다(B3 에서 확인).
  15줄 파서로 끝난다.

★ `.env` 는 **저장소 루트**에 둔다. 레이크(`/mnt/f/...`)가 아니다.
  레이크에 두면 그 파일을 찾으려고 또 레이크 경로가 필요하다 — 뱀이 제 꼬리를 문다.
  저장소 루트는 `paths.py` 가 자기 위치로 이미 안다. 그리고 오늘 증명됐듯이
  레이크는 사라져도 저장소는 남는다(`~/projects` 는 ext4, `/mnt/f` 는 drvfs).

★ 이 배치가 **하지 않는** 것 — `os.environ` 을 읽는 나머지 12곳 정리.
  `datalog · guards · pipeline · quiet_gdal · seg/params · doctor ·
   lakecheck · matchcheck · pr_body_check · pull_data · scan_data · sweep`
  "paths.py 가 유일한 독자" 는 **목표지 현재 상태가 아니다.**
  `tools/env_check.py --readers` 가 그걸 세고, 고치는 것은 별건이다.
  일감 규모를 알고 시작해야 한다.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

ANCHOR = 'ROOT = Path(__file__).resolve().parents[2]\n'

LOADER = '''ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """저장소 루트 `.env` 를 환경에 얹는다. **셸에 이미 있으면 안 덮는다.**

    ★ 2026-09-12 (B5). 종전에는 `~/.fire-lane.local` 이 설정 파일인 척
      했지만 **읽는 코드가 한 줄도 없었다.** `.bashrc` 가 source 해야만
      동작하는 구조였고, 기계를 갈아엎으면 조용히 사라진다. 실제로 사라졌다.

    ★ 우선순위 — 셸 > .env. 뒤집으면 폐기 변수가 현역을 이기던 사고가
      그대로 재현된다(위 FIRE_LANE_RAW 주석). `.env` 는 기본값이고
      `export` 는 그것을 덮는 일회성 판단이다.

    ★ 의존성을 안 쓴다. 이 모듈은 순수 표준 라이브러리 도구도 타고 들어온다.
    """
    p = ROOT / ".env"
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        key, sep, val = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:      # ★ 셸이 이긴다
            os.environ[key] = val


_load_dotenv()
'''

# ★ **덮지 않는다. 덧붙인다.** 기존 `.env.example` 에는 VWORLD_KEY 와
#   drvfs 마운트 대처법(MASTER §18-13)이 들어 있다. 한 번 덮어써서
#   날릴 뻔했다 — B3 내내 지키던 손실 금지를 이 배치가 어겼다.
#   키가 하나라도 사라지면 멈춘다.
APPEND = '''

# ══ 분류 — 2026-09-12 (B5) ════════════════════════════════════
# ★ 위 키들이 '설정' 이다. 아래는 여기 **적으면 안 되는** 것들이라
#   목록만 남긴다. `tools/env_check.py` 가 이 분류를 강제한다.
#
#   설정    .env · .env.example 필수
#             FIRE_LANE_DATA · FIRE_LANE_INBOX · FIRE_LANE_STAGE ·
#             FIRE_LANE_BACKUP · VWORLD_KEY · VWORLD_DOMAIN
#   스위치  셸에서 한 번 export 하고 만다. 여기 적으면 잡음만 늘고
#           켜 둔 걸 잊는다
#             FIRE_LANE_DEBUG_SEG · FIRE_LANE_DEBUG_XY ·
#             FIRE_LANE_MIX_SRC · FIRE_LANE_NO_MERGE · FIRE_LANE_OLD_SNAP
#   폐기    설정돼 있으면 paths.py 가 시끄럽게 운다
#             FIRE_LANE_RAW
#
# ★ 읽는 방식이 바뀌었다. 종전에는 셸 export 만 봤다(`~/.fire-lane.local`
#   은 **아무도 안 읽는 파일**이었다). 이제 paths._load_dotenv() 가
#   저장소 루트 `.env` 를 읽는다. **셸이 이긴다** — `.env` 는 기본값이고
#   `export` 는 그 판을 덮는 일회성 판단이다.

# 중간 산출물 자리. 안 주면 레이크 아래를 쓴다.
FIRE_LANE_STAGE=
# 백업 대상 루트.
FIRE_LANE_BACKUP=
'''

_UNUSED = '''# .env.example — **키 목록의 정본.** 값은 기계마다 다르므로 비워 둔다.
#
#   cp .env.example .env   후 값을 채운다. `.env` 는 gitignore 다.
#   셸에 export 가 있으면 그쪽이 이긴다(paths._load_dotenv).
#
# ★ 이 파일과 코드가 어긋나면 `tools/env_check.py` 가 운다. **양방향이다** —
#   코드에만 있는 키도, 여기에만 있는 키도 잡는다. 한쪽만 걸면 예외값에
#   영원히 머문다.

# ── 설정 — 없으면 파이프라인이 못 돈다 ────────────────────────
# 데이터 레이크 루트. raw · norm · landing · interim · _quarantine 의 부모.
FIRE_LANE_DATA=

# 사람이 파일을 받는 자리. lakecheck L3 · sweep 이 '레이크 밖' 을 여기서 본다.
# ★ 규약 — 더러운 파일은 윈도우 Downloads 에만 받는다. WSL 홈에 안 남긴다.
FIRE_LANE_INBOX=

# ── 선택 ──────────────────────────────────────────────────────
# 중간 산출물 자리. 안 주면 레이크 아래를 쓴다.
FIRE_LANE_STAGE=

# 백업 대상 루트.
FIRE_LANE_BACKUP=

# ── 여기 없는 것 ──────────────────────────────────────────────
# FIRE_LANE_RAW        폐기(2026-08-15). 설정돼 있으면 paths.py 가 시끄럽게 운다
# FIRE_LANE_DEBUG_SEG  일회성 디버그 스위치다. 셸에서 한 번 export 하고 만다.
# FIRE_LANE_DEBUG_XY   .env 에 적으면 잡음만 늘고, 켜 둔 걸 잊는다
# FIRE_LANE_MIX_SRC
# FIRE_LANE_NO_MERGE
# FIRE_LANE_OLD_SNAP
'''


def _names(src: str) -> set[str]:
    out: set[str] = set()
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    changed = 0

    # ── ① paths.py 에 로더 ────────────────────────────────────
    p = ROOT / "src/firelane/paths.py"
    before = p.read_text(encoding="utf-8")
    if "_load_dotenv" in before:
        print("  = src/firelane/paths.py  이미 적용됨")
    else:
        if before.count(ANCHOR) != 1:
            sys.exit(f"★ paths.py — 앵커가 {before.count(ANCHOR)}곳이다. 멈춘다.")
        text = before.replace(ANCHOR, LOADER)
        lost = _names(before) - _names(text)
        if lost:
            sys.exit(f"★ paths.py — 이름이 사라진다: {sorted(lost)}")
        ast.parse(text)
        print(f"  {'✓' if a.apply else '·'} src/firelane/paths.py   .env 로더")
        if a.apply:
            p.write_text(text, encoding="utf-8")
        changed += 1

    # ── ② .env.example ────────────────────────────────────────
    ex = ROOT / ".env.example"
    if not ex.exists():
        sys.exit("★ .env.example 이 없다. 이 배치는 덧붙이기만 한다.")
    cur = ex.read_text(encoding="utf-8")
    if "분류 — 2026-09-12 (B5)" in cur:
        print("  = .env.example  이미 적용됨")
    else:
        def keys(t):
            return {l.removeprefix("export ").partition("=")[0].strip()
                    for l in t.splitlines()
                    if l.strip() and not l.strip().startswith("#") and "=" in l}
        new = cur.rstrip("\n") + APPEND
        lost = keys(cur) - keys(new)
        if lost:
            sys.exit(f"★ .env.example — 키가 사라진다: {sorted(lost)}. 되돌린다.")
        print(f"  {'✓' if a.apply else '·'} .env.example   "
              f"키 {len(keys(cur))} → {len(keys(new))} (덧붙임)")
        if a.apply:
            ex.write_text(new, encoding="utf-8")
        changed += 1

    # ── ③ .gitignore ──────────────────────────────────────────
    gi = ROOT / ".gitignore"
    g = gi.read_text(encoding="utf-8")
    if "\n.env\n" in g or g.startswith(".env\n"):
        print("  = .gitignore  이미 .env 를 무시한다")
    else:
        add = ("\n# 기계마다 다른 경로 설정. 키 목록의 정본은 .env.example 이다.\n"
               "# ★ 전역 excludesFile 에도 있지만 저장소에도 적는다 —\n"
               "#   전역은 나를 지키고 저장소는 협업자를 지킨다.\n"
               ".env\n!.env.example\n")
        print(f"  {'✓' if a.apply else '·'} .gitignore   .env 추가")
        if a.apply:
            gi.write_text(g.rstrip("\n") + "\n" + add, encoding="utf-8")
        changed += 1

    print(f"\n변경 {changed}" + ("" if a.apply else "   ★ dry-run. --apply 를 붙일 것"))
    if a.apply:
        print("\n다음 —")
        print("  cp .env.example .env   후 FIRE_LANE_DATA · FIRE_LANE_INBOX 를 채운다")
        print("  uv run python tools/env_check.py")
        print("  uv run python tools/env_check.py --selftest   ★ 일부러 깨뜨려 본다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
