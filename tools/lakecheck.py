#!/usr/bin/env python3
"""
lakecheck.py — 데이터 레이크의 **선언과 실물**을 대조한다.

★ `datalog fsck` 를 아직 안 고친다. 별도로 재서 수를 확정하고, 그 다음에
  흡수할지 정한다. 고치면서 재면 무엇이 고쳐서 줄었고 무엇이 원래 없었는지
  못 가른다.

프로브 여섯. 전부 **세는 것**으로 끝난다.

  L1  제공기관 state ↔ 실물   reserved 인데 파일이 있나 · active 인데 0건인가
  L2  격리 잔재               _quarantine 이 raw 정본과 중복인가
  L3  landing 우회 ★          입구를 안 거친 원본이 밖에 있나
  L4  ext 어휘 밖             처리 코드가 없는 확장자가 들어왔나
  L5  norm ↔ raw 계보         norm 이 raw 어느 것의 파생인가
  L6  명명 규칙 ↔ 실물 구조    규칙이 실제 디렉터리 구조를 아는가

★ 프로브가 잴 수 없으면 **0건이 아니라 빨간불**이다. `deadcheck` 의 ⑤가
  git 없을 때 조용히 return 해서 한동안 0건을 냈다. 같은 실수를 안 한다.

    uv run python tools/lakecheck.py
    uv run python tools/lakecheck.py --scan /mnt/c/Users/fox/Downloads
    uv run python tools/lakecheck.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HITS: list[dict] = []


def hit(probe: str, what: str, detail: str = "", fix: str = "") -> None:
    HITS.append({"probe": probe, "what": what, "detail": detail, "fix": fix})


def lake() -> Path | None:
    d = os.environ.get("FIRE_LANE_DATA")
    return Path(d) if d and Path(d).is_dir() else None


def led() -> dict:
    return yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))


def disposed(y: dict) -> set[str]:
    """`landing_disposition` 에 처분이 적힌 파일 이름.

    ★ **판단 보류도 처분이다.** `_quarantine` 이 "판단 보류지 폐기가
      아니다" 인 것과 같다. 적힌 것은 운지 않는다 — 영구 빨간불은
      사람이 검사를 끄게 만든다.
    """
    d = (y.get("landing_disposition") or {}).get("items") or []
    return {str((it or {}).get("file", "")) for it in d if isinstance(it, dict)}


# ── L1  제공기관 state ↔ 실물 ───────────────────────────────────
def l1(D: Path, y: dict) -> None:
    """`reserved` 는 "파일 0건이 정상이고 폴더도 없어야 한다" 로 정의돼 있다."""
    prov = ((y.get("layers") or {}).get("raw") or {}).get("providers") or {}
    if not prov:
        hit("L1", "★ providers 선언을 못 읽었다 — 이 프로브가 아무것도 못 본다")
        return
    for name, v in prov.items():
        state = (v or {}).get("state") if isinstance(v, dict) else None
        folder = D / "raw" / name
        n = sum(1 for _ in folder.rglob("*")) if folder.is_dir() else 0
        n = sum(1 for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else 0
        if state == "reserved" and n:
            hit("L1", f"{name}: 선언 reserved 인데 실물 {n}개",
                "reserved 는 '파일 0건이 정상이고 폴더도 없어야 한다'",
                f"sources.yaml 의 {name} state 를 active 로")
        elif state == "active" and not n:
            hit("L1", f"{name}: 선언 active 인데 실물 0개",
                "active 는 '대장이 실제로 읽는다. 파일 0건이면 결손이다'",
                "실물을 반입하거나 reserved 로 내린다")
        elif state is None:
            hit("L1", f"{name}: state 선언이 없다", "",
                "active 또는 reserved 를 적는다")


# ── L2  격리 잔재 ───────────────────────────────────────────────
def _sha(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def l2(D: Path, y: dict) -> None:
    """격리는 판단 보류지 폐기가 아니다. 판단이 끝난 것만 나간다.

    ★ 첫 판은 "개명본 추정" 을 "폐기 대장 근거" 보다 **먼저** 봐서
      정상 처분된 셋을 오탐으로 냈다. 순서를 뒤집는다 — 대장에 근거가
      있으면 그것으로 끝이고, 추정은 근거가 없을 때만 쓴다.
    ★ 그리고 basename 만 보고 경로를 잃어 sha 대조를 못 했다. 경로를 쥔다.
    """
    q = D / "_quarantine"
    if not q.is_dir():
        hit("L2", "★ _quarantine 폴더가 없다 — 이 프로브가 못 잰다")
        return
    raw = {p.name: p for p in (D / "raw").rglob("*") if p.is_file()}
    # 대장이 격리를 정당화하는 근거 — retired 의 stem · file · files
    ok: set[str] = set()
    for v in (y.get("retired") or {}).values():
        if not isinstance(v, dict):
            continue
        if v.get("stem"):
            ok.add(v["stem"])
        for f in ([v["file"]] if v.get("file") else []) + (v.get("files") or []):
            ok.add(Path(str(f)).name)

    for p in sorted(q.rglob("*")):
        if not p.is_file() or p.name.startswith("_") or p.suffix == ".md":
            continue
        # ① 대장에 근거가 있으면 정상이다. 여기서 끝낸다
        if p.name in ok or any(p.name.startswith(s) for s in ok):
            continue
        # ② 같은 이름이 raw 에 있으면 내용을 대조한다 — 추정하지 않는다
        m = raw.get(p.name)
        if m:
            same = _sha(p) == _sha(m)
            hit("L2", f"{p.relative_to(q)}: raw 에 같은 이름이 있고 내용이 "
                      f"{'같다' if same else '★다르다'}",
                f"{p.stat().st_size / 1e6:.1f}MB · raw/{m.relative_to(D / 'raw')}",
                "격리본을 지운다" if same else "다른 자료다. 판단이 필요하다")
            continue
        # ③ 개명 추정 — 언더스코어를 지운 이름으로 raw 를 찾고 sha 로 확인한다
        sq = p.stem.replace("_", "")
        cand = [r for r in raw.values() if r.stem.replace("_", "") == sq]
        if cand:
            same = _sha(p) == _sha(cand[0])
            hit("L2", f"{p.relative_to(q)}: 개명본이 raw 에 있고 내용이 "
                      f"{'같다' if same else '★다르다'}",
                f"{p.stat().st_size / 1e6:.1f}MB · raw/{cand[0].relative_to(D / 'raw')}",
                "격리본을 지운다" if same else "개명이 아니다. 판단이 필요하다")
            continue
        hit("L2", f"{p.relative_to(q)}: 격리 사유가 대장에 없다",
            f"{p.stat().st_size / 1e6:.1f}MB", "retired 에 등재하거나 반입한다")


# ── L3  landing 우회 ★ ──────────────────────────────────────────
def l3(D: Path, y: dict, scan: list[Path]) -> None:
    """입구를 안 거친 원본이 밖에 있는가.

    ★ 이것이 제일 중요하다. `landing` 이 비면 "받았는데 안 넣은 것" 을
      셀 수 없고, 입구가 우회되면 그 뒤 검사 전부가 부분집합 위에서 돈다.
    """
    DATA_EXT = {".zip", ".7z", ".csv", ".json", ".shp", ".gpkg", ".tif",
                ".hwp", ".hwpx", ".xls", ".xlsx", ".txt", ".dbf"}
    landing = D / "landing"
    n_land = sum(1 for p in landing.rglob("*") if p.is_file()) if landing.is_dir() else 0
    print(f"     landing {n_land}건")

    if not scan and os.environ.get("FIRE_LANE_INBOX"):
        scan = [Path(os.environ["FIRE_LANE_INBOX"])]     # ★ 손으로 주면 그것도 사본이다
    if not scan:
        hit("L3", "★ --scan 도 FIRE_LANE_INBOX 도 없다 — 레이크 밖은 아무도 안 본다",
            "다운로드 폴더 등 사람이 파일을 받는 자리",
            "uv run python tools/lakecheck.py --scan <다운로드 경로>")
        return
    # ★ 이름이 아니라 **내용**으로 본다. 반입하며 개명하므로 이름은 안 맞는다.
    #   첫 판은 이름만 봐서 이미 반입된 넷을 미반입으로 냈다.
    have = {p.name for p in D.rglob("*") if p.is_file()}
    fp = {_sha(p) for p in D.rglob("*") if p.is_file() and p.stat().st_size > 100_000}
    for d in scan:
        if not d.is_dir():
            hit("L3", f"★ --scan {d} 가 폴더가 아니다")
            continue
        out = [p for p in d.iterdir()
               if p.is_file() and p.suffix.lower() in DATA_EXT
               and p.name not in have and p.stat().st_size > 100_000]
        out = [p for p in out if _sha(p) not in fp]
        skip = disposed(y)          # ★ 적힌 것은 운지 않는다
        out = [p for p in out if p.name not in skip]
        for p in sorted(out, key=lambda x: -x.stat().st_size):
            hit("L3", f"{p.name}: 레이크 밖에 있다",
                f"{p.stat().st_size / 1e6:.0f}MB · {d}",
                "landing 으로 옮기고 landing_disposition 에 적는다")


# ── L4  ext 어휘 밖 ─────────────────────────────────────────────
def l4(D: Path, y: dict) -> None:
    """대장 ext 어휘에 없는 확장자는 acquire 가 격리한다."""
    vocab = {e for v in (y.get("datasets") or {}).values()
             for e in ((v or {}).get("ext") or [])}
    if not vocab:
        hit("L4", "★ ext 어휘를 못 읽었다")
        return
    src = "\n".join((ROOT / p).read_text(encoding="utf-8", errors="replace")
                    for p in ("src/firelane/ingest.py", "tools/acquire.py")
                    if (ROOT / p).exists())
    for zone in ("landing", "raw"):
        d = D / zone
        if not d.is_dir():
            continue
        skip = disposed(y)
        for e, n in Counter(p.suffix.lstrip(".").lower()
                            for p in d.rglob("*")
                            if p.is_file() and p.name not in skip).items():
            if e and e not in vocab:
                coded = bool(re.search(rf'["\']\.?{e}["\']', src))
                hit("L4", f"{zone}: `.{e}` {n}건이 ext 어휘 밖이다",
                    f"어휘 {sorted(vocab)} · 처리 코드 {'있음' if coded else '0건'}",
                    "어휘를 넓히거나 다른 형식으로 바꾼다")


# ── L5  norm ↔ raw 계보 ─────────────────────────────────────────
def l5(D: Path, y: dict) -> None:
    """norm 은 raw 를 형식만 정규화한 것이다. 상류가 없으면 고아다."""
    norm, raw = D / "norm", D / "raw"
    if not norm.is_dir():
        hit("L5", "★ norm 폴더가 없다 — 이 프로브가 못 잰다")
        return
    raw_stems = [p.stem for p in raw.rglob("*") if p.is_file()]
    orphan = []
    for p in sorted(norm.rglob("*")):
        if not p.is_file():
            continue
        key = "_".join(p.stem.split("_")[:3])
        if not any(r.startswith(key[:14]) for r in raw_stems):
            orphan.append(p)
    n = sum(1 for p in norm.rglob("*") if p.is_file())
    print(f"     norm {n}건 · 상류 없는 것 {len(orphan)}건")
    for p in orphan:
        hit("L5", f"{p.relative_to(norm)}: raw 에 상류가 없다", "",
            "raw 를 반입하거나 norm 에서 뺀다")


# ── L6  명명 규칙 ↔ 실물 구조 ───────────────────────────────────
def l6(D: Path, y: dict) -> None:
    """규칙이 **실제 디렉터리 구조**를 아는가.

    ★ `datalog fsck` 는 상대경로 전체로 맞춘다(`its/its_….csv`). 그런데
      `norm` 규칙은 파일명만 상정한다 — `norm` 도 `raw` 처럼 제공기관
      폴더를 쓰는데 규칙이 그것을 모른다. 파일이 아니라 **규칙이 틀렸다.**
      같은 병이 한 번 있었고 그때는 날짜 자릿수였다(sources.yaml:616).
    """
    layers = y.get("layers") or {}
    for name, pol in layers.items():
        rx = (pol or {}).get("naming")
        sub = (pol or {}).get("sub")
        base = (pol or {}).get("base")
        if not rx or not sub:
            continue
        d = (D / sub) if base == "data" else (ROOT / sub)
        if not d.is_dir():
            continue
        pat = re.compile(rx)
        files = [p for p in d.rglob("*") if p.is_file() and not p.name.startswith("_")]
        rel_bad = [p for p in files if not pat.match(str(p.relative_to(d)))]
        name_bad = [p for p in files if not pat.match(p.name)]
        if not files:
            continue
        # 상대경로로는 전건 위반인데 파일명으로는 전건 통과 → 규칙이 폴더를 모른다
        # ★ 상대경로로 전건 통과하면 규칙이 옳은 것이다. 첫 판은 name_bad 만
        #   보고 raw·baseline 을 오탐으로 냈다 — 그 둘은 규칙이 폴더를 **안다**.
        if not rel_bad:
            continue
        if rel_bad and not name_bad:
            depth = {len(p.relative_to(d).parts) for p in files}
            hit("L6", f"{name}: 규칙이 폴더 계층을 모른다 — 위반 {len(rel_bad)}/{len(files)}건",
                f"파일명만으로는 전건 통과한다. 실물 깊이 {sorted(depth)} · "
                f"규칙 `{rx}`",
                "규칙 앞에 제공기관 폴더를 넣는다 — raw 규칙과 같은 꼴로")
        elif name_bad:
            hit("L6", f"{name}: 실물이 규칙을 어긴다 — {len(name_bad)}/{len(files)}건",
                " · ".join(p.name for p in name_bad[:4]),
                "파일을 개명하거나 규칙을 실물에 맞춘다")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan", action="append", default=[],
                    help="레이크 밖에서 원본을 찾을 폴더 (여러 번 가능)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    D = lake()
    if D is None:
        print("✗ FIRE_LANE_DATA 가 없거나 폴더가 아니다 — 아무것도 못 잰다")
        print("  ★ 0건이 아니라 실패다. 프로브가 조용히 통과하면 안 된다")
        return 1
    y = led()
    print(f"레이크 {D}\n")

    scan = [Path(x) for x in a.scan]
    for tag, fn in (("L1  제공기관 state", l1), ("L2  격리 잔재", l2),
                    ("L3  landing 우회", l3), ("L4  ext 어휘", l4),
                    ("L5  norm 계보", l5), ("L6  명명 규칙", l6)):
        before = len(HITS)
        print(f"  {tag}")
        try:
            fn(D, y, scan) if fn is l3 else fn(D, y)
        except Exception as e:
            hit(tag[:2], f"★ 프로브가 예외로 죽었다 — {type(e).__name__}: {e}")
        n = len(HITS) - before
        for h in HITS[before:]:
            print(f"     ✗ {h['what']}")
            if h["detail"]:
                print(f"        {h['detail']}")
            if h["fix"]:
                print(f"        → {h['fix']}")
        if n == 0:
            print("     ✓ 없음")
        print()

    print(f"합계 {len(HITS)}건")
    json.dump({"total": len(HITS), "hits": HITS},
              open(ROOT / "LAKELIST.json", "w"), ensure_ascii=False, indent=1)
    print("LAKELIST.json 기록")

    if a.selftest:
        # ★ 양성 대조. 프로브가 아무것도 못 내면 깨끗한 것이 아니라 죽은 것이다.
        by = Counter(h["probe"][:2] for h in HITS)
        dead = [p for p in ("L1", "L2", "L3", "L4", "L5", "L6") if p not in by]
        print(f"\n프로브별 {dict(by)}")
        if len(dead) >= 4:
            print(f"★ selftest 실패 — {len(dead)}개 프로브가 0건이다. 의심하라")
            return 1
        print("selftest 통과")
        return 0
    return min(len(HITS), 250)


if __name__ == "__main__":
    sys.exit(main())
