#!/usr/bin/env python3
"""
scan_data.py — 데이터 레이크 구조를 훑고 대장과 대조한다.

    uv run python tools/scan_data.py                 요약
    uv run python tools/scan_data.py --full          전체 파일 목록까지
    uv run python tools/scan_data.py --sha           내용 중복까지 (느리다)
    uv run python tools/scan_data.py --root /경로    FIRE_LANE_DATA 대신 지정

── 무엇을 보나 ────────────────────────────────────────────────
1. 계층      landing / raw / norm / field / _quarantine 이 규칙대로 있는가
2. 제공기관   raw 하위가 8폴더 규칙을 지키는가 (MASTER 18-2)
3. 명명규칙   provider_dataset_scope_date.ext 를 따르는가
4. 대장 대조  ★ 이것이 본체다 (MASTER 18-3 게이트)
                대장에 있음 + 파일 있음  →  정상
                대장에 있음 + 파일 없음  →  결손
                대장에 없음 + 파일 있음  →  격리 대상
5. 중복      같은 이름 / (--sha) 같은 내용

읽기 전용이다. 아무것도 옮기거나 지우지 않는다. 판단은 사람이 한다.
"""
from __future__ import annotations

import argparse
import collections
import fnmatch
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT_REPO = Path(__file__).resolve().parent.parent

# MASTER 18-2. 폴더 = 제공기관.
PROVIDERS = {
    "juso": "도로명주소", "its": "국가교통정보센터",
    "ngii": "국토정보플랫폼", "vworld": "브이월드",
    "safety": "공공데이터포털(안전)", "gjcity": "공공데이터포털(광주 동구)",
    "sbiz": "소상공인시장진흥공단", "eais": "건축HUB",
}
TIERS = ["raw", "norm", "field", "_quarantine", "landing"]

# provider_dataset_scope_date.ext  — 소문자·숫자·밑줄·하이픈·점만
NAME_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9\-]+)+_\d{8}\.[a-z0-9]+$")

SKIP = {".ds_store", "thumbs.db", "desktop.ini"}


def human(n: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:,.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_ledger() -> dict:
    """sources.yaml 의 datasets 를 읽는다. 없으면 빈 dict."""
    try:
        import yaml
    except ImportError:
        print("  ! pyyaml 없음 — 대장 대조를 건너뛴다")
        return {}
    p = ROOT_REPO / "sources.yaml"
    if not p.exists():
        print(f"  ! {p} 없음 — 대장 대조를 건너뛴다")
        return {}
    y = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return y.get("datasets", {}) or {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("FIRE_LANE_DATA", ""))
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--sha", action="store_true")
    a = ap.parse_args()

    root = Path(a.root).expanduser()
    if not root.is_dir():
        print(f"! 경로 없음: {root}")
        print("  FIRE_LANE_DATA 를 설정하거나 --root 로 지정하라")
        return 1

    files = []
    for p in root.rglob("*"):
        if p.is_file() and p.name.lower() not in SKIP:
            files.append((p.relative_to(root), p.stat().st_size, p))
    total = sum(f[1] for f in files)
    print(f"루트  {root}")
    print(f"파일  {len(files):,}개 · {human(total)}\n")

    # ── 1. 계층 ────────────────────────────────────────────
    print("=" * 62)
    print("1. 계층")
    tops = collections.Counter()
    tsize = collections.Counter()
    for rel, sz, _ in files:
        k = rel.parts[0]
        tops[k] += 1
        tsize[k] += sz
    for k in sorted(tops, key=lambda x: -tsize[x]):
        mark = "" if k in TIERS else "   ← 규칙에 없는 최상위"
        print(f"  {k:22s} {tops[k]:6,}개  {human(tsize[k]):>10s}{mark}")
    for t in TIERS:
        if t not in tops and t != "landing":
            print(f"  {t:22s}      — 없음")

    # ── 2. 제공기관 폴더 ──────────────────────────────────
    print("\n" + "=" * 62)
    print("2. raw 제공기관 폴더 (MASTER 18-2)")
    raw = [(rel, sz, p) for rel, sz, p in files if rel.parts[0] == "raw"]
    if not raw:
        print("  raw 없음")
    else:
        prov = collections.Counter()
        psize = collections.Counter()
        for rel, fsz, _ in raw:
            k = rel.parts[1] if len(rel.parts) > 1 else "(raw 직하 파일)"
            prov[k] += 1
            # ★ 2026-08-23 버그 수정. 여기가 `psize[k] += sz` 였다.
            #   루프 변수는 `_sz` 인데 §1 루프의 마지막 `sz` 를 더하고 있었다.
            #   함수 스코프에 `sz` 가 살아 있어 NameError 도 안 났고 —
            #   `test_static.py`(정의되지 않은 이름)도 못 잡는다.
            #
            #   결과: 모든 제공기관 크기가 **마지막 파일 크기 × 파일 수** 였다.
            #   실측(2026-08-23, 외장 SSD): 전체 5.8GB 인데 폴더 합이 30GB —
            #   eais 1개 970.2MB · its 2개 1.9GB · ngii 11개 10.4GB,
            #   전부 970.2MB(= nsdi/AL_D002 크기)의 배수였다.
            #
            #   숫자가 그럴듯해서 오래 안 보였다. 합계와 대조했으면 즉시 드러났다.
            psize[k] += fsz
        for k in sorted(prov):
            tag = PROVIDERS.get(k, "★ 규칙에 없는 폴더")
            print(f"  {k:16s} {prov[k]:5,}개 {human(psize[k]):>10s}  {tag}")
        for k in PROVIDERS:
            if k not in prov:
                print(f"  {k:16s}     — 없음  {PROVIDERS[k]}")

    # ── 3. 명명규칙 ────────────────────────────────────────
    print("\n" + "=" * 62)
    print("3. 명명규칙 이탈 (raw 직속 파일만)")
    bad = []
    for rel, _sz, _ in raw:
        if len(rel.parts) != 3:          # raw/provider/파일 이 정상
            bad.append((rel, "계층 깊이"))
        elif not NAME_RE.match(rel.name):
            bad.append((rel, "이름 형식"))
    print(f"  {len(bad)} / {len(raw)} 건")
    for rel, why in bad[:40 if not a.full else len(bad)]:
        print(f"    [{why}] {rel}")
    if len(bad) > 40 and not a.full:
        print(f"    … 외 {len(bad)-40}건 (--full)")

    # ── 4. 대장 대조 ★ ─────────────────────────────────────
    print("\n" + "=" * 62)
    print("4. 대장 대조 (MASTER 18-3 게이트)")
    ds = load_ledger()
    if ds:
        rawset = {str(rel.relative_to("raw")).replace(os.sep, "/") for rel, _, _ in raw}
        claimed = set()
        missing = []
        for key, e in sorted(ds.items()):
            pat = (e or {}).get("file")
            if not pat:
                print(f"  · {key:22s} file 선언 없음")
                continue
            pat = pat.rstrip("/")
            hit = {r for r in rawset if fnmatch.fnmatch(r, pat) or r.startswith(pat + "/")}
            if hit:
                claimed |= hit
                print(f"  OK {key:22s} {len(hit):4d}개  {pat}")
            else:
                missing.append((key, pat))
        print()
        for key, pat in missing:
            print(f"  ★ 결손 {key:20s} {pat}")
        orphan = sorted(rawset - claimed)
        print(f"\n  격리 대상(대장에 없는 raw 파일) {len(orphan)}건")
        for o in orphan[:40 if not a.full else len(orphan)]:
            print(f"    {o}")
        if len(orphan) > 40 and not a.full:
            print(f"    … 외 {len(orphan)-40}건 (--full)")

    # ── 5. 중복 ────────────────────────────────────────────
    print("\n" + "=" * 62)
    print("5. 중복")
    byname = collections.defaultdict(list)
    for rel, sz, _ in files:
        byname[rel.name].append((rel, sz))
    dup = {k: v for k, v in byname.items() if len(v) > 1}
    print(f"  같은 이름 {len(dup)}종")
    for k, v in sorted(dup.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"    {k}")
        for rel, sz in v[:4]:
            print(f"        {human(sz):>10s}  {rel}")

    if a.sha:
        print("\n  같은 내용 (sha256)")
        bysha = collections.defaultdict(list)
        for rel, sz, p in files:
            if sz:
                bysha[sha256(p)].append((rel, sz))
        same = {k: v for k, v in bysha.items() if len(v) > 1}
        waste = sum(v[0][1] * (len(v) - 1) for v in same.values())
        print(f"    {len(same)}종 · 낭비 {human(waste)}")
        for _k, v in sorted(same.items(), key=lambda x: -x[1][0][1])[:15]:
            print(f"    {human(v[0][1]):>10s} × {len(v)}")
            for rel, _ in v[:4]:
                print(f"        {rel}")

    # ── 6. 확장자 · 큰 파일 ───────────────────────────────
    print("\n" + "=" * 62)
    print("6. 확장자")
    ext = collections.Counter((rel.suffix.lower() or "(없음)") for rel, _, _ in files)
    esz = collections.Counter()
    for rel, sz, _ in files:
        esz[rel.suffix.lower() or "(없음)"] += sz
    for k, v in ext.most_common(15):
        print(f"  {k:10s} {v:6,}개 {human(esz[k]):>10s}")

    print("\n  큰 파일 상위 15")
    for rel, sz, _ in sorted(files, key=lambda f: -f[1])[:15]:
        print(f"    {human(sz):>10s}  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
