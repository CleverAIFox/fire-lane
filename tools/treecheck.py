#!/usr/bin/env python3
"""
treecheck.py — 저장소 루트부터 레이크까지 **전수 스캔**해서 선언과 대조한다.

    uv run python tools/treecheck.py             전부
    uv run python tools/treecheck.py --repo      저장소 트리만 (레이크 없이)
    uv run python tools/treecheck.py --lake      레이크만
    uv run python tools/treecheck.py --json
    uv run python tools/treecheck.py --idempotent  두 번 스캔해 같은지 증명

── 왜 전수인가 ────────────────────────────────────────────────
기존 검사는 전부 **항목에서 출발**한다. 대장 40건이 실물에 있나,
글롭이 뭘 잡나, 선언한 산출물이 나왔나. 항목에서 출발하면 **항목이
없는 것은 영원히 안 보인다.**

    doctor.integrity_report()
        disk = {... for p in RAW.rglob("*") if p.is_file()}
                                              ^^^^^^^^^^^

폴더는 대장에 항목이 없어 대조 대상이 아니고, 비어 있으면 파일 대조에도
안 걸린다. `acquire.cmd_quarantine()` 이 `shutil.move` 만 하고 빈 부모를
안 지우므로, 격리를 한 번이라도 했으면 그 자리에 빈 폴더가 남는다.
**그런 폴더가 실제로 몇 개인지는 이 도구를 돌려 봐야 안다.**

★ 그래서 여기는 **실물에서 출발한다.** 루트부터 전부 훑고, 각 경로에
  "누가 이것의 존재를 선언했나" 를 묻는다. 답이 없으면 샌 것이다.

── 멱등의 정의 ────────────────────────────────────────────────
`owned_paths.tracked()` 머리말이 이미 답을 적어 놨다 —
*"디스크를 보면 로컬 생성물 때문에 기기마다 결과가 갈린다."*

    git ls-files    결정론적. 어느 기계에서나 같다
    디스크           기계마다 다르다
    .gitignore      그 차이를 설명해야 하는 유일한 근거

★ **멱등이란 `디스크 − 추적` 이 전부 gitignore 로 설명되는 상태다.**
  설명 안 되는 것이 하나라도 있으면 그 기계는 다른 기계와 다르고,
  그 차이가 언젠가 산출물에 들어온다. `.code_fingerprint` 가
  `data/processed/` 에 있어 기계마다 stale 로 뜨는 것(#42)이 같은 형태다.

── 축 ─────────────────────────────────────────────────────────
저장소
    T1  미추적·미무시   디스크에 있는데 git 도 gitignore 도 모른다  ★ 샘
    T2  무시-추적 모순  gitignore 인데 추적 중 (예외 선언 밖)
    T3  미소유          추적 중인데 CODEOWNERS 매치가 없다
    T4  계층 부재       base=repo 로 선언한 계층 디렉터리가 없다
    T5  빈 디렉터리     저장소 전체
    T6  산출물 선언     outputs 의 path 가 실물과 어긋난다
레이크
    D0  naming 정규식 ↔ providers 등재
    D1  미선언 폴더
    D2  active 인데 파일 0건 (근거 없는 빈 폴더)  ★ 격리의 흔적
    D3  reserved 인데 폴더가 있다
    D4  active 인데 폴더가 없다
    D5  깊이 위반 ({provider}/{file} 2단 고정)
    D6  폴더 ↔ 파일명 provider 불일치
    D7  계층 밖 파일 (레이크 루트)
    D8  required 계층 부재
    D9  유령 provider (active 인데 대장이 안 쓴다)

D0·D1·D5·D6·D9 는 레이크 없이도 돈다(`_acquire.json` 만 본다).

IN    저장소 트리 · sources.yaml · .gitignore · CODEOWNERS · $FIRE_LANE_DATA
OUT   없음 (판정 전용). 종료코드 1 = 결함
PARAM 없음
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from firelane import layers as L
from firelane import ledger as LD

# 대장 조회기는 하나다(firelane.ledger.globs).
from firelane import ledger as _led
from firelane import naming as nm
from firelane import paths
from firelane import providers as P

ROOT = paths.ROOT
ACQ = ROOT / "data" / "_acquire.json"
BAD, WARN = "✗", "!"

#  스캔에서 통째로 뺀다. git 이 애초에 안 보는 것들이라 판정 가치가 없다.
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules",
             ".pytest_cache", ".ruff_cache", ".mypy_cache"}


class F:
    __slots__ = ("axis", "level", "what", "why")

    def __init__(self, axis: str, level: str, what: str, why: str = ""):
        self.axis, self.level, self.what, self.why = axis, level, what, why

    def d(self) -> dict:
        return {"axis": self.axis, "level": self.level,
                "what": self.what, "why": self.why}


# ── 스캔 ──────────────────────────────────────────────────────
def walk(base: Path) -> tuple[list[str], list[str]]:
    """(파일, 디렉터리). **정렬해서 돌려준다 — 멱등의 전제다.**"""
    files, dirs = [], []
    if not base.is_dir():
        return files, dirs
    for p in base.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(base).parts):
            continue
        rel = p.relative_to(base).as_posix()
        (dirs if p.is_dir() else files).append(rel)
    return sorted(files), sorted(dirs)


def tracked() -> set[str] | None:
    """git 이 아는 것. git 이 없으면 None — 판정을 건너뛴다."""
    r = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return {x for x in r.stdout.split("\0") if x}


def ignored(rels: list[str]) -> set[str]:
    """git 이 무시한다고 말하는 것. **규칙을 재구현하지 않는다.**

    ★ `.gitignore` 를 손으로 파싱하면 `!` 예외·디렉터리 규칙·순서에서
      git 과 갈린다. 갈리면 이 도구가 오탐을 내고, 오탐은 사람이
      `--force` 를 쓰게 만든다(DECISIONS §73). git 에게 묻는다.
    """
    if not rels:
        return set()
    #  ★ `--no-index` 가 없으면 **추적 중인 파일은 보고되지 않는다**(git 사양).
    #    gitignore 는 추적 대상에 적용되지 않기 때문인데, T2 가 잡으려는
    #    것이 정확히 그 "무시 규칙인데 추적 중" 상태다. 빼면 T2 가 영원히
    #    0건으로 초록불이 된다 — 검사하지 않고 통과하는 형태다.
    r = subprocess.run(["git", "check-ignore", "--no-index", "--stdin", "-z"],
                       cwd=ROOT, input="\0".join(rels),
                       capture_output=True, text=True)
    return {x for x in r.stdout.split("\0") if x}


# ── 저장소 ────────────────────────────────────────────────────
def check_repo() -> list[F]:
    out: list[F] = []
    files, dirs = walk(ROOT)
    trk = tracked()

    if trk is None:
        out.append(F("T0", WARN, "git", "git 저장소가 아니다 — T1·T2·T3 을 건너뛴다"))
    else:
        ign = ignored(files)
        stray = [f for f in files if f not in trk and f not in ign]
        for s in stray:
            out.append(F(
                "T1", BAD, s,
                "git 도 gitignore 도 모르는 파일이다. 커밋하거나 무시 규칙을"
                " 적어라 — 근거 없는 파일이 있으면 이 기계가 다른 기계와 다르다"))

        exc = set(L.policy("processed").get("committed_exceptions") or [])
        for t in sorted(trk & ign):
            #  `!` 예외로 일부러 추적하는 것. 선언된 것만 통과시킨다.
            if Path(t).name in exc:
                continue
            out.append(F(
                "T2", BAD, t,
                "gitignore 인데 추적 중이다. 규약과 강제자가 어긋난 지점이고"
                " 2026-08-21 에 processed 의 *.csv 구멍이 같은 형태였다"))

        #  ★ `sys.path.insert` 를 쓰지 않는다. `test_layering` 이 금지하고
        #    있고, 그 규칙이 옳다 — 17군데까지 늘어났던 전력이 있다.
        #    tools/ 는 패키지가 아니므로 파일에서 직접 적재한다.
        try:
            import importlib.util as _iu
            _s = _iu.spec_from_file_location("owned_paths",
                                             ROOT / "tools" / "owned_paths.py")
            _m = _iu.module_from_spec(_s)
            _s.loader.exec_module(_m)
            for t in sorted(trk):
                if not _m.owners_of(t):
                    out.append(F("T3", BAD, t,
                                 "CODEOWNERS 매치가 없다. 기본값 `*` 줄이"
                                 " 지워졌는지 보라"))
        except Exception as ex:                              # noqa: BLE001
            out.append(F("T3", WARN, "owned_paths", f"소유 판정 불가: {ex}"))

    #  T4 — base=repo 계층이 실재하나
    for name in L.names():
        pol = L.policy(name)
        if pol.get("base") != "repo":
            continue
        p = ROOT / str(pol.get("sub"))
        if not p.is_dir():
            lv = BAD if pol.get("committed") else WARN
            out.append(F("T4", lv, f"{name} → {pol.get('sub')}",
                         "base=repo 로 선언했는데 없다"))

    #  T5 — 빈 디렉터리. 레이크와 같은 사각이다.
    have = {Path(f).parent.as_posix() for f in files}
    for d in dirs:
        if any(h == d or h.startswith(d + "/") for h in have):
            continue
        out.append(F("T5", WARN, d + "/",
                     "빈 디렉터리. git 은 폴더를 추적하지 않으므로 clone 하면"
                     " 사라진다 — 이 기계에만 있는 것이다"))

    #  T6 — outputs 선언 ↔ 실물
    cfg = LD.load()
    for k, o in (cfg.get("outputs") or {}).items():
        rel = str(o.get("path") or "")
        if not rel:
            out.append(F("T6", BAD, f"outputs:{k}", "path 선언이 없다"))
        elif not (ROOT / rel).exists():
            out.append(F("T6", WARN, f"outputs:{k} → {rel}",
                         "선언된 산출물이 없다. 파이프라인 미실행이면 정상"))
    return out


# ── 레이크 ────────────────────────────────────────────────────
def ledger_files() -> set[str]:
    if not ACQ.exists():
        return set()
    return set(json.loads(ACQ.read_text(encoding="utf-8"))["files"])


def check_names(rels: set[str], *, src: str) -> list[F]:
    out = []
    for rel in sorted(rels):
        parts = rel.split("/")
        if len(parts) != P.depth():
            out.append(F("D5", BAD, f"{src}:{rel}",
                         f"깊이 {len(parts)} — raw 는 {{provider}}/{{file}} "
                         f"{P.depth()}단 고정이다. 중첩하면 글롭이 조용히 빗나간다"))
            continue
        folder, fn = parts
        if not P.known(folder):
            out.append(F("D1", BAD, f"{src}:{rel}",
                         f"등재되지 않은 폴더 {folder!r}. layers.raw.providers 에"
                         " 올리거나 격리한다"))
            continue
        try:
            n = nm.parse(fn, folder=folder)
        except Exception as ex:                              # noqa: BLE001
            out.append(F("D6", BAD, f"{src}:{rel}", str(ex)))
            continue
        if n.provider != folder:
            out.append(F("D6", BAD, f"{src}:{rel}",
                         f"폴더 {folder!r} 와 파일명 provider {n.provider!r} 가"
                         " 다르다. 이중 기록의 값어치는 이 대조 하나다"))
    return out


def check_lake(*, offline: bool) -> list[F]:
    out: list[F] = []
    ok, msg = P.naming_matches_registry()
    if not ok:
        out.append(F("D0", BAD, "layers.raw.naming", msg))

    used = set()
    for e in (LD.load().get("datasets") or {}).values():
        for pat in _led.globs(e):
            used.add(str(pat).split("/")[0])
    for p in sorted(P.active() - used):
        out.append(F("D9", WARN, f"providers:{p}",
                     "active 로 등재됐는데 대장 datasets 가 하나도 안 쓴다."
                     " reserved 로 내리거나 등재를 지운다"))

    led = ledger_files()
    out += check_names(led, src="대장")
    if offline or not paths.RAW.is_dir():
        return out

    files, dirs = walk(paths.RAW)
    disk = set(files)
    out += check_names(disk - led, src="실물")

    have = defaultdict(int)
    for f in disk:
        have[f.split("/")[0]] += 1
    top = {d for d in dirs if "/" not in d}
    for d in sorted(top):
        if not P.known(d):
            continue
        n = have.get(d, 0)
        if d in P.reserved():
            out.append(F("D3", BAD, f"raw/{d}/",
                         f"reserved 인데 폴더가 있다(파일 {n}건). 비었으면"
                         " 지우고, 파일이 있으면 대장에 등재한다"))
        elif n == 0:
            out.append(F("D2", BAD, f"raw/{d}/",
                         "active 인데 파일 0건. 격리·삭제의 흔적이다."
                         " 폴더 존재가 편입 신호로 쓰이므로 남겨두면 안 된다"))
    for p in sorted(P.active() - top):
        out.append(F("D4", WARN, f"raw/{p}/", "active 인데 폴더가 없다"))

    for name in L.names():
        if L.policy(name).get("required") and not L.path(name).is_dir():
            out.append(F("D8", BAD, f"{name} → {L.path(name)}",
                         "required 인데 없다"))
    if paths.DATA and paths.DATA.is_dir():
        roots = {L.path(n).name for n in L.names()}
        for x in sorted(paths.DATA.iterdir()):
            if x.name.startswith("."):
                continue
            if x.is_file():
                out.append(F("D7", BAD, f"$FIRE_LANE_DATA/{x.name}",
                             "계층 밖 파일. 2026-08-24 에 SSD 루트로 11.7MB 가"
                             " 샌 것과 같은 형태다 — interim 으로 옮긴다"))
            elif x.name not in roots:
                out.append(F("D7", WARN, f"$FIRE_LANE_DATA/{x.name}/",
                             "선언되지 않은 최상위 폴더"))
    return out


# ── 멱등 ──────────────────────────────────────────────────────
def snapshot() -> str:
    """스캔 결과의 지문. 두 번 떠서 같아야 한다."""
    h = hashlib.sha256()
    for base in (ROOT, paths.RAW):
        files, dirs = walk(base)
        for x in files + dirs:
            h.update(x.encode() + b"\0")
    return h.hexdigest()[:16]


# ── 출력 ──────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="store_true")
    ap.add_argument("--lake", action="store_true")
    ap.add_argument("--offline", action="store_true",
                    help="레이크 실물 검사를 건너뛴다")
    ap.add_argument("--idempotent", action="store_true",
                    help="두 번 스캔해 지문이 같은지만 본다")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.idempotent:
        s1, s2 = snapshot(), snapshot()
        print(f"{s1}\n{s2}")
        if s1 != s2:
            print("✗ 스캔이 멱등하지 않다 — 스캔 도중 트리가 바뀌었다")
            return 1
        print("✓ 멱등")
        return 0

    both = not (a.repo or a.lake)
    found: list[F] = []
    if both or a.repo:
        found += check_repo()
    if both or a.lake:
        found += check_lake(offline=a.offline)

    if a.json:
        print(json.dumps({"findings": [f.d() for f in found],
                          "snapshot": snapshot()},
                         ensure_ascii=False, indent=1))
        return 1 if any(f.level == BAD for f in found) else 0

    rf, rd = walk(ROOT)
    lf, ld = walk(paths.RAW)
    print("═══ 전수 스캔 ═══")
    print(f"저장소   파일 {len(rf)} · 폴더 {len(rd)}")
    print(f"레이크   파일 {len(lf)} · 폴더 {len(ld)}"
          + ("   (미연결)" if not paths.RAW.is_dir() else ""))
    print(f"대장     datasets {len(LD.load().get('datasets') or {})} · "
          f"실물 {len(ledger_files())}")
    print(f"지문     {snapshot()}\n")

    if not found:
        print("✓ 결함 없음 — 모든 경로에 선언이 있다")
        return 0

    by = defaultdict(list)
    for f in found:
        by[f.axis].append(f)
    for axis in sorted(by):
        g = by[axis]
        print(f"── {axis}  {len(g)}건")
        for f in g[:12]:
            print(f"  {f.level} {f.what}")
        if len(g) > 12:
            print(f"     … 외 {len(g) - 12}건")
        print(f"     {g[0].why}")
    nb = sum(1 for f in found if f.level == BAD)
    print(f"\n결함 {nb} · 경고 {len(found) - nb}")
    return 1 if nb else 0


if __name__ == "__main__":
    sys.exit(main())
