#!/usr/bin/env python3
"""
doctor.py — **데이터 레이크 전체가 의도대로인가.** 한 명령으로 본다.

    uv run python tools/doctor.py            전 계층 스캔 + 선언 대조
    uv run python tools/doctor.py --brief    요약만

FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다

── 왜 ─────────────────────────────────────────────────────────
검사가 다섯 곳에 흩어져 있었다.

    acquire.py --verify     raw sha
    datalog fsck            계층 선언 ↔ 디스크
    intake.py --audit       파일명 문법
    ledger_schema --check   스키마 드리프트
    refcheck                죽은 참조

각각 옳다. 그런데 **다섯 개를 순서대로 치는 사람은 없다.** 실제로
2026-08-26 에 `intake.py` 를 만들어 놓고 `--stage` 를 안 돌려서 차량 제원
문서 13건이 다운로드 폴더에 그대로 남아 있었다 — 도구는 있고 파이프라인은
안 돌았다. 그것을 알려주는 자리가 없었다.

여기가 그 자리다. **하나를 치면 전부 본다.**

── 보는 것 ────────────────────────────────────────────────────
    ① 계층별 실측 — 파일수 · 용량 · 대용량 TOP
    ② 선언 대조   — layers 의 required · committed · backup 이 지켜지나
    ③ 파이프라인  — 다운로드 → landing → raw 사이에 멈춘 것이 있나
    ④ 무결성      — sha · 대장 ↔ 실물 · quarantine 사유
    ⑤ 백업        — backup:true 계층이 실제로 백업됐나 · 언제

★ 판정만 한다. 고치지 않는다. 고치는 것은 각 도구의 일이고, 여기는
  "무엇을 쳐야 하는가" 를 말해준다.

IN    $FIRE_LANE_DATA · $FIRE_LANE_INBOX · sources.yaml
OUT   없음 (진단 전용)
PARAM 없음
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "sources.yaml"
ACQ = ROOT / "data" / "_acquire.json"
INTAKE = ROOT / "data" / "_intake.json"

OK, WARN, BAD = "✓", "!", "✗"

# 브라우저 부산물. landing 으로 올리지 않는다.
JUNK = re.compile(r"\.(crdownload|part|tmp|partial)$|^~\$|^\.DS_Store$")


def _sha(p: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()
_todo: list[str] = []


JUNK = re.compile(r"\.(crdownload|part|tmp|partial)$|^~\$|^\.DS_Store$")


def _sha256(p: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def _scan(p: Path) -> tuple[int, int, list[tuple[int, Path]]]:
    if not p.is_dir():
        return -1, 0, []
    files = [f for f in p.rglob("*") if f.is_file()]
    sizes = sorted(((f.stat().st_size, f) for f in files), reverse=True)
    return len(files), sum(s for s, _ in sizes), sizes[:3]


def _gb(n: int) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.1f} MB"


def layers_report(brief: bool) -> None:
    from firelane import layers as L
    print("═══ ① 계층 실측 ═══")
    print(f"  {'계층':11} {'파일':>6} {'용량':>10}  {'정책':22} 경로")
    for n in L.names():
        pol, path = L.policy(n), L.path(n)
        cnt, sz, top = _scan(path)
        tag = []
        if pol.get("required"):
            tag.append("required")
        if pol.get("backup"):
            tag.append("backup")
        if pol.get("committed"):
            tag.append("committed")
        if pol.get("status") == "미구현":
            tag.append("★미구현")
        mark = BAD if (pol.get("required") and cnt < 0) else (
            WARN if cnt < 0 else OK)
        print(f"{mark} {n:11} {(cnt if cnt >= 0 else '—'):>6} "
              f"{(_gb(sz) if cnt > 0 else '—'):>10}  "
              f"{'·'.join(tag) or '—':22} {path}")
        if mark == BAD:
            _todo.append(f"layers.{n} 이 required 인데 없다 — "
                         "FIRE_LANE_DATA 를 확인하라")
        if not brief and cnt > 0 and n in ("raw", "_quarantine", "quarantine"):
            for s, f in top:
                print(f"    {_gb(s):>10}  {f.name}")


def pipeline_report() -> None:
    """다운로드 → landing → raw 사이에 멈춘 것."""
    from firelane.paths import LANDING
    print("\n═══ ② 파이프라인 정체 ═══")

    # 다운로드
    try:
        from firelane.paths import inbox
        inb = inbox()
        seen = set()
        if INTAKE.exists():
            seen = {v["sha256"] for v in
                    json.loads(INTAKE.read_text(encoding="utf-8"))["files"].values()}
        new = [p for p in (inb.iterdir() if inb.is_dir() else [])
               if p.is_file() and not JUNK.search(p.name)
               and _sha(p) not in seen]
        m = WARN if new else OK
        print(f"{m} 다운로드 → landing   미편입 {len(new)}건   {inb}")
        for p in new[:6]:
            print(f"    {p.name}")
        if len(new) > 6:
            print(f"    … 외 {len(new) - 6}건")
        if new:
            _todo.append("uv run python tools/intake.py --stage --yes"
                         f"   (다운로드 {len(new)}건이 대기 중)")
    except Exception as ex:                        # noqa: BLE001
        print(f"{WARN} 다운로드 검사 실패 — {type(ex).__name__}: {ex}"[:78])

    # landing → raw
    lc, _, _ = _scan(LANDING)
    if lc > 0:
        led = json.loads(ACQ.read_text(encoding="utf-8"))["files"] if ACQ.exists() else {}
        raw_sha = {v["sha256"] for v in led.values()}
        stuck = [p for p in LANDING.rglob("*")
                 if p.is_file() and _sha(p) not in raw_sha]
        m = WARN if stuck else OK
        print(f"{m} landing → raw        미편입 {len(stuck)}건 / landing {lc}건")
        for p in stuck[:6]:
            print(f"    {p.name}")
        if stuck:
            _todo.append("uv run python tools/acquire.py --stage --yes"
                         f"   (landing {len(stuck)}건이 대기 중)")
    else:
        print(f"{OK} landing → raw        landing 비어 있다")

    # raw → norm
    from firelane import layers as L
    if L.policy("norm").get("status") == "미구현":
        mig = L.policy("norm").get("migrated") or []
        print(f"{WARN} raw → norm           미구현 · 이관 {len(mig)}건")
        _todo.append("layers.norm 이 미구현이다 — prep.py 로 한 건씩 옮긴다")


def integrity_report() -> None:
    from firelane.paths import QUARANTINE, RAW
    print("\n═══ ③ 무결성 ═══")
    led = json.loads(ACQ.read_text(encoding="utf-8"))["files"] if ACQ.exists() else {}
    disk = ({str(p.relative_to(RAW)) for p in RAW.rglob("*") if p.is_file()}
            if RAW.is_dir() else set())
    only_led, only_disk = sorted(set(led) - disk), sorted(disk - set(led))
    m = BAD if (only_led or only_disk) else OK
    print(f"{m} 대장 {len(led)} · 실물 {len(disk)} · "
          f"대장만 {len(only_led)} · 실물만 {len(only_disk)}")
    for x in (only_led + only_disk)[:6]:
        print(f"    {x}")
    if only_led:
        _todo.append("대장에 있는데 실물이 없다 — acquire.py --verify 로 원인 확인")
    if only_disk:
        _todo.append("uv run python tools/acquire.py --quarantine"
                     f"   (대장 밖 {len(only_disk)}건)")

    # 대장 글롭이 실물을 잡나
    d = yaml.safe_load(YAML.read_text(encoding="utf-8")) or {}
    dead = []
    for k, e in (d.get("datasets") or {}).items():
        for pat in (e.get("files") or ([e["file"]] if "file" in e else [])):
            if not [r for r in led if fnmatch.fnmatch(r, str(pat))]:
                dead.append(k)
    m = BAD if dead else OK
    print(f"{m} 죽은 대장 참조 {len(dead)}건" + (f"  {dead[:5]}" if dead else ""))
    if dead:
        _todo.append("uv run python tools/migrate_names.py --apply --yes"
                     "   (죽은 참조 복구)")

    # ★ 대장의 `ext` 가 실물 확장자 집합과 같은가.
    #
    #   2026-08-27. `ledger_stem` 이 이관될 때 raw 에 `.hwp` 만 있어서
    #   `ext: [hwp]` 로 굳었고, 나중에 들어온 `.pdf` 가 대장 밖으로 판정돼
    #   **매번 격리 대상**이 됐다. 08-25 에 근거로 인용한 PDF 두 건이다.
    #
    #   대장이 실물의 반쪽만 알고 있으면 격리가 잘못 돈다. 그 어긋남을
    #   여기서 센다 — 격리가 실행되기 **전에** 보여야 한다.
    from firelane import naming as _nm
    _ext_bad = []
    for k, e in (d.get("datasets") or {}).items():
        want = set(e.get("ext") or [])
        if not want:
            continue
        got = set()
        for rel in led:
            try:
                n = _nm.parse(rel.rsplit("/", 1)[-1], strict=False)
            except Exception:                      # noqa: BLE001
                continue
            stems = e.get("stems") or ([e["stem"]] if e.get("stem") else [])
            if f"{n.provider}_{n.dataset}" in stems:
                got.add(n.ext)
        if got and got != want:
            _ext_bad.append((k, sorted(want), sorted(got)))
    m = WARN if _ext_bad else OK
    print(f"{m} 대장 ext ↔ 실물 확장자 어긋남 {len(_ext_bad)}건")
    for k, w, g in _ext_bad[:6]:
        print(f"    {k:22} 선언 {w} · 실물 {g}")
    if _ext_bad:
        _todo.append("uv run python tools/ledger_stem.py --apply"
                     "   (ext 선언이 실물과 다르다 — 격리가 잘못 돈다)")

    # quarantine 사유
    qc, qs, qtop = _scan(QUARANTINE)
    if qc > 0:
        has = (QUARANTINE / "QUARANTINE.md").exists() or \
              (QUARANTINE / "README.md").exists()
        m = OK if has else WARN
        print(f"{m} 격리 {qc}건 {_gb(qs)} · 사유 기록 {'있음' if has else '★없음'}")
        if not has:
            _todo.append("_quarantine 에 사유 기록이 없다 — "
                         "격리는 판단 보류지 폐기가 아니다(§18-12)")


def backup_report() -> None:
    from firelane import layers as L
    print("\n═══ ④ 백업 ═══")
    targets = L.of("backup")
    print(f"  backup:true 계층 — {', '.join(targets)}")
    found = False
    for env in ("FIRE_LANE_BACKUP",):
        import os
        b = os.environ.get(env)
        if b and (Path(b) / "_backup_index.json").exists():
            idx = json.loads((Path(b) / "_backup_index.json").read_text(
                encoding="utf-8"))
            print(f"{OK} {b}  {len(idx['files'])}건 · {idx['at']}")
            found = True
    if not found:
        print(f"{WARN} 백업 흔적이 없다(_backup_index.json 미발견)")
        _todo.append("uv run python -m firelane.datalog backup <외장경로>"
                     "   · 그 뒤 verify")
        _todo.append("★ 복원해 본 적 없는 백업은 백업이 아니다(§18-8). "
                     "주기는 팀 합의 사항이다")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", action="store_true")
    a = ap.parse_args()
    layers_report(a.brief)
    pipeline_report()
    integrity_report()
    backup_report()

    print("\n═══ 해야 할 것 ═══")
    if not _todo:
        print("  없다. 체계가 선언대로다.")
        return 0
    for i, t in enumerate(_todo, 1):
        print(f"  {i}. {t}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
