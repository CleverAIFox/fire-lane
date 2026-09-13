#!/usr/bin/env python3
"""
b2_lake.py — B2 ①~④ 적용. **선언을 실물에 맞춘다.**

    uv run python tools/b2_lake.py            무엇을 할지만
    uv run python tools/b2_lake.py --apply    실제로
    uv run python tools/b2_lake.py --apply    두 번째. 전부 "변경 없음"

멱등이다.

★ `sources.yaml` 은 주석이 본체다. yaml.safe_load → dump 왕복을 하면
  2,968줄 중 대부분인 산문과 판단 근거가 통째로 날아간다. 그래서 **텍스트로
  고치고**, 대신 파싱 결과의 **키 집합을 전후 대조**해서 항목이 사라지면
  되돌린다. `codepatch` 가 파이썬에 하는 일을 YAML 에 하는 것이다.

고치는 것 넷.

  ① norm 명명 규칙   ★ 손목록 금지 — providers.pattern() 생성기를 탄다
  ② 제공기관 state   mois·gjbg 가 reserved 인데 실물이 있다
  ③ 머리말 메타      provider·acquired·crs 가 0/61 이다. 실물과 맞춘다
  ④ 격리 중복 삭제   sha 가 같은 것만. 다르면 손대지 않는다

`retired` 스키마(B2 ②)는 여기 없다. 그것은 `stem` 을 사람이 정해야 하고,
정하기 전에 `ledger_fields --apply` 를 돌리면 파일 지목이 날아간다.
그 경고를 `ledger_fields.check()` 에 넣는 것까지만 한다.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sources.yaml"


# ── YAML 안전장치 ───────────────────────────────────────────────
def keyset(text: str) -> set[str]:
    """블록.항목.필드 세 단계 키 집합. 손실 대조의 기준이다."""
    d = yaml.safe_load(text) or {}
    out: set[str] = set()
    for blk, items in d.items():
        out.add(blk)
        if isinstance(items, dict):
            for k, v in items.items():
                out.add(f"{blk}.{k}")
                if isinstance(v, dict):
                    out |= {f"{blk}.{k}.{f}" for f in v}
    return out


class Ledger:
    def __init__(self) -> None:
        self.orig = LEDGER.read_text(encoding="utf-8")
        self.text = self.orig
        self.log: list[str] = []
        self.skip: list[str] = []

    def sub(self, old: str, new: str, *, why: str) -> Ledger:
        n = self.text.count(old)
        if n == 0:
            self.skip.append(f"{why} — 대상 없음(이미 적용?)")
            return self
        if n > 1:
            raise RuntimeError(f"`{old[:46]}` 가 {n}건이다. 모호하면 안 바꾼다")
        self.text = self.text.replace(old, new, 1)
        self.log.append(why)
        return self

    def commit(self, *, apply: bool) -> bool:
        if self.text == self.orig:
            print(f"  = sources.yaml  변경 없음  {' · '.join(self.skip)}")
            return True
        try:
            after = keyset(self.text)
        except yaml.YAMLError as e:
            print(f"  ✗ sources.yaml  편집 결과가 YAML 오류다 — {e}")
            return False
        lost = keyset(self.orig) - after
        if lost:
            print(f"  ✗ sources.yaml  **키가 사라졌다** — {sorted(lost)[:6]}")
            print("     되돌린다. 텍스트 치환이 항목을 먹었다")
            return False
        mark = "→" if apply else "·"
        print(f"  {mark} sources.yaml")
        for x in self.log:
            print(f"      + {x}")
        for x in self.skip:
            print(f"      = {x}")
        gained = sorted(after - keyset(self.orig))
        if gained:
            print(f"      새 키 {gained[:6]}")
        if apply:
            LEDGER.write_text(self.text, encoding="utf-8")
        return True


# ── ① norm 명명 규칙 ────────────────────────────────────────────
NORM_OLD = r"""    naming: '^\w+_[a-z0-9-]+_[a-z0-9-]+_\d{8}\.'"""
NORM_NEW = r"""    # ★ 2026-09-10. 종전 규칙은 실물 29/29 를 위반으로 냈다. 파일명만으로는
    #   전건 통과하는데, norm 도 raw 처럼 **제공기관 폴더**를 쓰고 fsck 는
    #   상대경로로 맞추기 때문이다. 파일이 아니라 규칙이 폴더를 몰랐다.
    #   같은 병이 한 번 있었고(위 주석의 \d{4} 건) 그때도 규칙이 틀렸다.
    #
    #   ★ provider 목록을 여기 손으로 적지 마라. 2026-08-27 까지 그 목록이
    #     네 곳에 있었고 세 곳에서 달랐다(§18-2a). raw 와 **같은 생성기**를
    #     탄다 — providers.pattern_file() 이 만들고
    #     test_provider_registry 가 대조한다.
    naming: '^(eais|gjbg|gjcity|its|juso|mois|nfa|ngii|nsdi|safety|sbiz|vworld)/\w+_[a-z0-9-]+_[a-z0-9-]+_\d{8}\.'"""

PATTERN_FILE = '''

def pattern_file() -> str:
    """`layers.norm.naming` 이 가져야 할 값. 선언에서 만든다.

    ★ raw 는 폴더까지만 본다(`^(a|b)/`). norm 은 그 아래 파일명 문법까지
      본다. 두 규칙이 provider 목록을 **따로 갖지 않게** 여기서 합친다 —
      목록을 손으로 적으면 다섯 번째 사본이 된다.
    """
    return pattern() + r"\\w+_[a-z0-9-]+_[a-z0-9-]+_\\d{8}\\."
'''


# ── ② 제공기관 state ────────────────────────────────────────────
STATE = [
    ("      mois:    {org: 행정안전부 공공데이터포털,    state: reserved}",
     "      mois:    {org: 행정안전부 공공데이터포털,    state: active}",
     "mois → active (실물 2건)"),
    ("      gjbg:    {org: 전남광주통합특별시 빅데이터 통합플랫폼, state: reserved}",
     "      gjbg:    {org: 전남광주통합특별시 빅데이터 통합플랫폼, state: active}",
     "gjbg → active (실물 1건)"),
]


# ── ③ 머리말 메타 ───────────────────────────────────────────────
HEAD_OLD = """# 메타 항목 (URL 은 적지 않는다. 자주 깨지고 provider+scope 면 다시 찾는다)
#   provider  어느 사이트에서 받았나
#   updated   데이터 갱신일 (다운로드일 아님)
#   acquired  우리가 받은 날
#   scope     공간 범위 + 건수
#   crs       좌표계. ★ "명시"와 "추정"을 구분해서 적을 것"""

HEAD_NEW = """# 메타 항목 (URL 은 적지 않는다. 자주 깨지고 provider+scope 면 다시 찾는다)
#
# ★ 2026-09-10 정정. 이 머리말이 요구하던 provider · acquired · crs 는
#   **어느 항목에도 없다**(0/61). 이관되면서 자리가 옮겨갔는데 머리말만
#   안 따라왔다. 대장이 자기 스키마를 틀리게 적고 있었다.
#
#   stem      파일명 첫 토큰이자 raw 폴더명. provider 의 자리다
#             (종전 `provider` 필드. layers.raw.providers 가 어휘 정본)
#   updated   데이터 갱신일 (다운로드일 아님)
#             ★ 모르면 추정이라고 적는다. 비워두지 않는다
#   scope     공간 범위 + 건수
#   crs_native  좌표계. ★ "명시"와 "추정"을 구분해서 적을 것
#             (.prj 가 없으면 추정이다. 그렇게 적는다)
#
#   받은 날은 여기 적지 않는다 — `_acquire.json` 이 sha 와 함께 갖는다
#   (종전 `acquired` 필드)"""


def do_ledger(apply: bool) -> int:
    fail = 0
    print("── ① norm 명명 규칙 — 생성기로 통일")
    print("── ② 제공기관 state — 실물을 따라간다")
    print("── ③ 머리말 메타 — 0/61 인 필드를 정정한다")
    L = Ledger()
    try:
        L.sub(NORM_OLD, NORM_NEW, why="norm.naming 에 제공기관 폴더 접두")
        for old, new, why in STATE:
            L.sub(old, new, why=why)
        L.sub(HEAD_OLD, HEAD_NEW, why="머리말 메타 정정 (provider·acquired·crs)")
        if not L.commit(apply=apply):
            fail += 1
    except RuntimeError as e:
        print(f"  ✗ sources.yaml  {e}")
        fail += 1

    # providers.pattern_file() — norm 규칙의 생성기
    p = ROOT / "src" / "firelane" / "providers.py"
    src = p.read_text(encoding="utf-8")
    if "def pattern_file" in src:
        print("  = providers.py  pattern_file() 이미 있다")
    else:
        m = re.search(r'return "\^\(" \+ "\|"\.join\(sorted\(all\(\)\)\) \+ "\)/"\n', src)
        if not m:
            print("  ✗ providers.py  pattern() 앵커를 못 찾았다")
            fail += 1
        else:
            out = src[:m.end()] + PATTERN_FILE + src[m.end():]
            mark = "→" if apply else "·"
            print(f"  {mark} providers.py  pattern_file() 추가")
            if apply:
                p.write_text(out, encoding="utf-8")
    return fail


# ── ④ 격리 중복 삭제 ────────────────────────────────────────────
def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def do_quarantine(apply: bool) -> int:
    print("\n── ④ 격리 중복 — ★ sha 가 같은 것만 지운다")
    D = os.environ.get("FIRE_LANE_DATA")
    if not D or not Path(D).is_dir():
        print("  ✗ FIRE_LANE_DATA 가 없다 — 이 단계를 못 잰다")
        return 1
    D = Path(D)
    q, raw = D / "_quarantine", D / "raw"
    if not q.is_dir():
        print("  = _quarantine 없음")
        return 0
    idx: dict[str, Path] = {}
    for r in raw.rglob("*"):
        if r.is_file():
            idx.setdefault(r.stem.replace("_", ""), r)
    n = 0
    for p in sorted(q.rglob("*")):
        if not p.is_file() or p.suffix == ".md":
            continue
        m = idx.get(p.stem.replace("_", ""))
        if not m:
            continue
        if sha(p) != sha(m):
            print(f"  ★ {p.name}  이름은 같은데 **내용이 다르다** — 안 지운다")
            continue
        mark = "→" if apply else "·"
        print(f"  {mark} 삭제 {p.relative_to(D)}  ({p.stat().st_size / 1e6:.1f}MB)")
        print(f"      raw/{m.relative_to(raw)} 와 sha 동일")
        if apply:
            p.unlink()
        n += 1
    if not n:
        print("  = 중복 없음")
    return 0


# ── ledger_fields 경고 ──────────────────────────────────────────
WARN = '''
# ★ 2026-09-10. `retired` 는 항목이 두 종류다 — 실물이 격리에 있는 것과
#   받은 적조차 없는 것. 전자는 `file`/`files` 가 **재유입을 막는 유일한
#   근거**이고 대체할 `stem` 이 아직 없다. 그것을 지우면 acquire 가 폐기
#   자료를 다시 받아들인다. 실측: retired 10종 중 stem 없는 것 8종,
#   그중 실물이 있는 것 3종.
RETIRED_NEEDS_STEM = ("kfs_paint_marking_20241224",
                      "firestation_kr_20250701",
                      "hydrant_point_jngj_20250917")
'''


def do_warn(apply: bool) -> int:
    p = ROOT / "tools" / "ledger_fields.py"
    if not p.exists():
        print("\n  = ledger_fields.py 없음 (B1 미적용)")
        return 0
    src = p.read_text(encoding="utf-8")
    print("\n── ⑤ ledger_fields 에 파괴 경고")
    if "RETIRED_NEEDS_STEM" in src:
        print("  = 이미 있다")
        return 0
    if "RETIRED_FIELDS" not in src:
        print("  = check() 가 아직 없다 (B1/W4 미적용). 건너뜀")
        return 0
    out = src.replace("RETIRED_FIELDS = {", WARN.lstrip("\n") + "\nRETIRED_FIELDS = {", 1)
    mark = "→" if apply else "·"
    print(f"  {mark} RETIRED_NEEDS_STEM 3종 등재 — --apply 전에 stem 을 채우라는 근거")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


def measure(tag: str) -> None:
    for cmd in (["python", str(ROOT / "tools" / "lakecheck.py")],
                ["python", "-m", "firelane.datalog", "fsck"]):
        r = subprocess.run([sys.executable] + cmd[1:], cwd=ROOT,
                           capture_output=True, text=True,
                           env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
        line = [x for x in (r.stdout or "").splitlines()
                if "합계" in x or "어긋남" in x]
        print(f"  {tag}  {cmd[-1]:22s} {line[-1].strip() if line else '?'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--measure", action="store_true")
    a = ap.parse_args()
    if a.measure:
        measure("현재")
        return 0
    if a.apply:
        bak = LEDGER.with_suffix(".yaml.b2bak")
        if not bak.exists():
            shutil.copy2(LEDGER, bak)
            print(f"백업 {bak.name}\n")
    print(f"{'적용' if a.apply else 'dry-run — --apply 로 실행'}\n")
    fail = do_ledger(a.apply) + do_quarantine(a.apply) + do_warn(a.apply)
    print(f"\n{'실패 ' + str(fail) + '건' if fail else '전부 통과'}")
    if a.apply and not fail:
        print("\n다음 —")
        print("  uv run python tools/lakecheck.py")
        print("  uv run python -m firelane.datalog fsck")
        print("  pytest tests/test_provider_registry.py -q")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
