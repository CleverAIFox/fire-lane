#!/usr/bin/env python3
"""
doc_fsck.py — 문서가 하는 말과 실물이 어긋나는 곳을 넷만 본다.

── 왜 생겼나 ───────────────────────────────────────────────────
강제자 23종이 전부 **문서 ↔ 실물** 한 방향이었다. `docnum_check` 는 숫자를,
`test_docref` 는 절 참조를, `golden` 은 산출물을 본다. **문서 ↔ 문서** 를 보는
것이 하나도 없었고, 2026-09-01 에 그 자리에서 넷이 한꺼번에 나왔다.

    src/firelane/README.md 의 대장 예시가 `url` `license` `retrieved` 를 든다
        → datasets 41개 중 그 셋을 쓰는 항목이 0건이다
    web/config.js 가 web/assets/vehicles/profiles.json 을 fetch 한다
        → 저장소에 그 파일이 없다. clone 한 사람은 제원 칸이 빈다
    sources.yaml 이 turn_radius 를 "7종 전수 확인 0건" 으로 선언한다
        → profiles.json 은 7300~11889 를 갖고 있다
    layers.field 가 "재취득 불가한 실측" 이라고 선언한다
        → 재취득 가능한 공공데이터 CSV 가 거기 들어와 있고 대장에도 없다

넷 다 **읽으면 보이는데 아무도 안 읽었다.** `§79` 가 적은 형태 그대로다.

── 안 하는 것 ──────────────────────────────────────────────────
★ **자연어 모순은 잡지 않는다.** "A 문서와 B 문서가 다른 말을 한다" 를 기계가
  판정하려면 두 서술의 의미를 비교해야 하고, 그것은 이 도구의 범위가 아니다.
  여기서 보는 것은 **구조** 넷뿐이다 — 키 목록 · 파일 경로 · 부재 선언 · 등재.

★ 정본이 어느 쪽인지도 판정하지 않는다. 어긋난 자리를 짚고 사람에게 넘긴다.
  최신이 정본인 것이 보통이지만 그 판단은 사람이 한다.

IN    src/firelane/README.md · sources.yaml · docs/*.md · web/ · data/field
OUT   없음 (검사). 어긋나면 1
PARAM FIELD_EXEMPT — 등재 유예 목록. 비우는 것이 목표다
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sources.yaml"
PIPE_README = ROOT / "src/firelane/README.md"

# ★ 등재가 아직 안 된 field 파일. **늘리지 마라.** 여기 있는 동안은 그 파일이
#   무엇인지 저장소가 설명하지 못한다. PLAN 이 이 목록의 처리를 든다.
FIELD_EXEMPT = {
    "fieldsheet.md",            # sources.yaml consumers 가 든다
}

# ★ 한시 유예. **늘리지 마라.** 사유와 해소 조건을 함께 적는다(§80 과 같은 형태).
PATH_EXEMPT = {
    # 2026-09-01. 파일이 광인사 그램에만 있다. UI 담당이 커밋하면 해소된다.
    #   config.js:327 · vehicle.js:187 이 fetch 하고, 없으면 화면이
    #   "제원 미확인" 만 띄운다. PLAN 이 이 항목을 든다.
    "web/assets/vehicles/profiles.json",
}

# 경로 참조를 찾을 때 저장소 안인 것만 본다. data/raw · norm · landing ·
# interim · _quarantine 은 외장 SSD 라 여기서 존재를 확인할 수 없고,
# data/processed 는 재생성물이라 clone 직후에는 없는 것이 정상이다.
REPO_DIRS = ("web", "src", "tools", "tests", "docs", ".github",
             "data/field", "data/golden", "data/baseline")
PATH_RX = re.compile(
    r"(?<![\w/.-])(" + "|".join(d.replace("/", r"/") for d in REPO_DIRS)
    + r")/[\w./-]+\.[A-Za-z0-9]{1,6}(?![\w/.-])")

# ★ DECISIONS 와 PLAN 은 보지 않는다. 전자는 **경위**라 폐기한 도구를 과거형
#   으로 적는 것이 정상이고(`tools/docfix_20260817.py` 는 지운 것이 맞다),
#   후자는 **계획**이라 아직 없는 파일을 가리키는 것이 정상이다. 여기서 보는
#   것은 "지금 그렇게 동작한다" 고 말하는 문서와 설정뿐이다.
SCAN_GLOBS = ("docs/MASTER.md", "sources.yaml", "web/config.js",
              "web/js/**/*.js", "src/firelane/README.md", "README.md",
              ".github/CODEOWNERS")


def _ledger() -> dict:
    return yaml.safe_load(LEDGER.read_text(encoding="utf-8"))


# ── 1. 스키마 — 문서가 드는 키 ↔ 실제 쓰는 키 ────────────────────
def check_schema(led: dict) -> list[str]:
    """대장 예시가 든 키와 실물 41개가 쓰는 키를 센다."""
    blocks = re.findall(r"```yaml\n(.*?)```", PIPE_README.read_text(encoding="utf-8"),
                        re.S)
    documented: set[str] = set()
    for b in blocks:
        for line in b.splitlines():
            m = re.match(r"^\s{4}([a-z_]+):", line)
            if m:
                documented.add(m.group(1))
    if not documented:
        return ["src/firelane/README.md 에서 대장 예시 yaml 블록을 못 찾았다"]

    used: dict[str, int] = {}
    for v in led["datasets"].values():
        for k in v:
            used[k] = used.get(k, 0) + 1
    n = len(led["datasets"])

    bad = []
    dead = sorted(documented - set(used))
    if dead:
        bad.append(f"문서만 들고 실물이 0건인 키 {len(dead)}개 — {', '.join(dead)}")
    # 절반 넘게 쓰이는데 문서에 없으면 문서가 낡은 것이다
    missing = sorted(k for k, c in used.items() if c > n // 2 and k not in documented)
    if missing:
        bad.append(f"실물 과반이 쓰는데 문서에 없는 키 {len(missing)}개 — "
                   f"{', '.join(missing)}")
    return bad


# ── 2. 경로 — 문서·설정이 가리키는 저장소 파일이 실재하는가 ───────
def check_paths() -> list[str]:
    seen: dict[str, set[str]] = {}
    for g in SCAN_GLOBS:
        for f in ROOT.glob(g):
            if not f.is_file():
                continue
            for m in PATH_RX.finditer(f.read_text(encoding="utf-8", errors="ignore")):
                p = m.group(0)
                if "*" in p or "{" in p:
                    continue
                seen.setdefault(p, set()).add(str(f.relative_to(ROOT)))
    return [f"{p} 이 없다 — {' · '.join(sorted(src))} 가 가리킨다"
            for p, src in sorted(seen.items())
            if p not in PATH_EXEMPT and not (ROOT / p).exists()]


# ── 3. 부재 선언 — "없다" 고 적은 값이 실물에 있는가 ──────────────
def check_absent(led: dict) -> list[str]:
    """`absent:` 로 없다고 선언한 필드명이 저장소 데이터에 나타나면 운다."""
    names: dict[str, str] = {}

    def walk(node, trail: str):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "absent" and isinstance(v, dict):
                    for f in v:
                        names[f] = trail or "(최상위)"
                else:
                    walk(v, f"{trail}.{k}" if trail else k)

    walk(led, "")
    if not names:
        return []

    hay: list[tuple[str, str]] = []
    for g in ("web/**/*.json", "web/**/*.js", "data/field/*.csv",
              "data/processed/*.json"):
        for f in ROOT.glob(g):
            if f.is_file():
                hay.append((str(f.relative_to(ROOT)),
                            f.read_text(encoding="utf-8", errors="ignore")))

    bad = []
    for field, where in names.items():
        cam = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), field)
        stem = re.sub(r"_m$|_pct$", "", field)
        hits = sorted({p for p, t in hay
                       if re.search(rf"\b({re.escape(field)}|{re.escape(cam)}"
                                    rf"|{re.escape(stem)})\b", t)})
        if hits:
            bad.append(f"{where}.absent.{field} 은 없다고 선언했는데 "
                       f"{' · '.join(hits[:3])} 에 있다")
    return bad


# ── 4. 등재 — 사람이 만드는 계층의 파일이 대장에 있는가 ───────────
def check_field_ledger(led: dict) -> list[str]:
    """
    `layers.field` 는 `committed: true · regenerable: false` 로 raw 등급 보호를
    선언한다. 대장에 없으면 그 보호 목록에서 빠지고, 인수인계 때 그 파일이
    무엇인지 아무도 설명하지 못한다.

    ★ golden · baseline 은 같은 등급이지만 도구가 만드는 봉인이라 대장이 아니라
      `tools/golden.py` · `tools/baseline.py` 가 든다. 여기서 보지 않는다.
    """
    d = ROOT / "data/field"
    if not d.is_dir():
        return []
    text = LEDGER.read_text(encoding="utf-8")
    bad = []
    for f in sorted(d.iterdir()):
        if not f.is_file() or f.name in FIELD_EXEMPT:
            continue
        if f.name not in text:
            bad.append(f"data/field/{f.name} 이 대장에 없다 — "
                       "재취득 가능하면 raw 로, 실측이면 대장에 등재한다")
    return bad


CHECKS = (
    ("① 스키마   문서가 드는 키 ↔ 실물이 쓰는 키", lambda led: check_schema(led)),
    ("② 경로     문서·설정이 가리키는 파일 ↔ 실재", lambda led: check_paths()),
    ("③ 부재선언 '없다' 고 적은 값 ↔ 실물", lambda led: check_absent(led)),
    ("④ 등재     사람이 만드는 계층 ↔ 대장", lambda led: check_field_ledger(led)),
)


def run() -> dict[str, list[str]]:
    led = _ledger()
    return {name: fn(led) for name, fn in CHECKS}


def main() -> int:
    out = run()
    total = 0
    for name, bad in out.items():
        mark = "OK " if not bad else "★  "
        print(f"{mark}{name}")
        for b in bad:
            print(f"      {b}")
        total += len(bad)
    print()
    if total:
        print(f"어긋난 곳 {total}건. 어느 쪽이 정본인지는 사람이 정한다.")
    else:
        print("문서와 실물이 구조상 일치한다.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
