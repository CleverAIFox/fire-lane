#!/usr/bin/env python3
"""
scan_data.py — 데이터 레이크 구조를 훑고 대장과 대조한다.

    uv run python tools/scan_data.py                 요약
    uv run python tools/scan_data.py --full          전체 파일 목록까지
    uv run python tools/scan_data.py --sha           내용 중복까지 (느리다)
    uv run python tools/scan_data.py --root /경로    FIRE_LANE_DATA 대신 지정

── 무엇을 보나 ────────────────────────────────────────────────
1. 계층      landing / raw / norm / field / _quarantine 이 규칙대로 있는가
2. 제공기관   raw 하위가 대장이 선언한 제공기관 폴더인가 (MASTER 18-2)
             ★ 2026-10-05. **수를 안 적는다** — 제공기관이 늘면 낡는다(§396-6)
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
import os
import re
import sys
from pathlib import Path

from firelane import providers

ROOT_REPO = Path(__file__).resolve().parent.parent

# MASTER 18-2. 폴더 = 제공기관.
# ★ 2026-08-27. 여기에 8종이 하드코딩돼 있었다(nsdi 없음). 같은 목록이
#   layers.raw.naming · normalize_raw 머리말 · ORG · 테스트 두 곳까지
#   **다섯 벌**이었고 값이 갈려 있었다. DECISIONS §73 이 "세 곳에서
#   달랐다" 고 적고 통일했는데, 통일한 값이 또 복사된 것이다.
#   정본은 layers.raw.providers 다. 여기는 읽기만 한다.
PROVIDERS = {k: v["org"] for k, v in providers.spec().items()}
def lake_tiers() -> list[str]:
    """레이크에 사는 계층의 **폴더 이름**. 정본은 `src/firelane/paths.py` 다.

    ── 왜 읽어 오나 (DECISIONS §338) ───────────────────────────
    ★ 바로 위 문단이 `PROVIDERS` 를 두고 「같은 목록이 **다섯 벌**이었고 값이
      갈려 있었다 … 정본은 대장이다. 여기는 읽기만 한다」라고 적어 놨다.
      그리고 **그 다음 줄의 `TIERS` 는 하드코딩으로 남아 있었다.** 규칙을
      적은 자리와 어긴 자리가 두 줄 차이였다(§335 와 같은 꼴).

    ★ 그 목록은 **양쪽으로** 틀려 있었다 —
        `interim` 이 빠졌다   선언돼 있는 계층인데 「규칙에 없는 최상위」로 찍혔다
        `field` 가 들었다     2026-08-23 에 **저장소 안이 정본**으로 정해진 계층이다
                              (`paths.py:149`). 레이크에 없는 것을 「없다」고 조른다

    ★ `paths.py` 를 **글로 읽는다.** 값을 적재해서 보면 `FIRE_LANE_DATA` 가
      없는 기계에서 저장소 계층까지 섞인다(`(DATA / "x") if DATA else (ROOT / …)`).
      `uicheck.navi_off()` 가 `layers.ts` 를 읽는 것과 같은 방법이다.
    ★ **주석은 걷는다.** `paths.py:150` 이 「종전에는 `(DATA / "field")` 였는데」
      라고 적어 놨고, 안 걷으면 그 회고가 계층으로 세어진다.
    """
    src = (ROOT_REPO / "src" / "firelane" / "paths.py").read_text(encoding="utf-8")
    live = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    return sorted(set(re.findall(r"DATA\s*/\s*[\"']([a-z_][a-z0-9_]*)[\"']", live)))


TIERS = lake_tiers()

# provider_dataset_scope_date[_식별자].ext  — 소문자·숫자·밑줄·하이픈·점만
#
# ★ 2026-10-01 (DECISIONS §339). 꼬리 `(_[a-z0-9]+)?` 를 더했다. 15건이 이탈로
#   찍히고 있었는데 **15개의 실수가 아니라 규칙 하나가 빠진 것**이었다 —
#   `ngii_ortho_…_20251231_gj037.tif` 의 `gj037` 은 **도엽 번호**이고
#   `safety_vehiclecard_…_20260904_daein11.pdf` 의 `daein11` 은 **차량 식별자**다.
#
# ★ **이름을 고치는 쪽은 불가능하다.** 꼬리를 지우면 ortho 넷이 한 이름으로
#   뭉갠다(tif 4 · xml 4 · vehiclecard 4 · basemap 2). 꼬리가 정보를 든다.
#
# ★ 그리고 `sources.yaml` 의 `layers.norm.naming` 은 **이미 그 꼬리를 허용하고
#   있었다**(`(?:_[a-z0-9-]+)?`). 같은 사실을 두 곳이 다르게 알고 있었고
#   `raw` 를 보는 이쪽만 몰랐다.
NAME_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9\-]+)+_\d{8}(_[a-z0-9]+)?\.[a-z0-9]+$")

SKIP = {".ds_store", "thumbs.db", "desktop.ini"}




from firelane import paths
from firelane.console import human
from firelane.hashing import sha256 as _h_sha256


def sha256(p, chunk: int = 1 << 20) -> str:
    # ★ 2026-09-13. 구현은 `firelane.hashing` 한 곳이다.
    #   이름은 호출부 때문에 남긴다 — 옮긴 것과 고친 것을
    #   한 커밋에 섞지 않는다(원칙 ⑤).
    return _h_sha256(p, chunk)


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


def selftest() -> int:
    """계층 목록과 이름 규칙이 **실물에서 유도되는가.** (DECISIONS §338 · §339)"""
    fails = []

    # ① 계층 — `paths.py` 에서 나오는가
    got = lake_tiers()
    if not got:
        fails.append("`paths.py` 에서 계층을 하나도 못 읽는다 — 빈 그물이다")
    for must in ("raw", "norm", "landing"):
        if must not in got:
            fails.append(f"`{must}` 가 빠졌다 — 정규식이 `paths.py` 와 갈렸다")
    # ★ 2026-08-23 에 **저장소 안이 정본**으로 정해진 계층이다. 레이크 목록에
    #   있으면 없는 것을 「없다」고 조른다.
    if "field" in got:
        fails.append("`field` 가 레이크 계층으로 잡힌다 — 주석을 안 걷고 있다(`paths.py:150`)")
    if "interim" not in got:
        fails.append("`interim` 이 빠졌다 — 하드코딩이 그것을 빠뜨린 그 결함이다")

    # ② 이름 규칙 — 꼬리를 받되 틀린 것은 거절하는가
    for n in ("ngii_ortho_jngj-donggu_20251231_gj037.tif",
              "safety_vehiclecard_jngj-donggu_20260904_daein11.pdf"):
        if not NAME_RE.match(n):
            fails.append(f"도엽·식별자 꼬리를 거절한다 — {n}")
    for n in ("juso_road_geom_jngj_20260701.zip", "its_nodelink_kr_20260812.zip"):
        if not NAME_RE.match(n):
            fails.append(f"원래 맞던 이름을 거절한다 — {n}")
    for n in ("대문자_안됨_20260101.csv", "no-underscore.csv",
              "safety_cctv_jngj_2026063.csv", "safety_cctv_jngj_20260630_a_b.csv"):
        if NAME_RE.match(n):
            fails.append(f"넓히면서 **틀린 것까지 받는다** — {n}")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 11")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(paths.DATA or ""))
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--sha", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    # ★ 레이크가 없어도 돈다 — 판별식은 `paths.py` 와 합성 이름만 쓴다.
    if a.selftest:
        return selftest()

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
        # ★ 2026-09-03 배선 복구. 종전에는 `e.get("file")` 단수만 읽었다.
        #   2026-08-31 에 `file`/`files` 를 37종에서 빼고 `stem`+`ext` 로
        #   뒤집었는데(PLAN #46) 이 소비자만 이관에서 빠졌다. 그 결과
        #   44종 중 42종이 "file 선언 없음" 으로 빠져나가 **claimed 가
        #   공집합이 됐고, raw 전량이 격리 대상으로 떴다.**
        #   조용히 안 하는 게 아니라 시끄럽게 틀린 것을 말했다(§18-13).
        #   정본은 `ledger.globs()` 하나다 — 여기서 다시 쓰지 않는다.
        from firelane import ledger as _led
        for key, e in sorted(ds.items()):
            pats = [str(g) for g in _led.globs(e)] if e else []
            if not pats:
                print(f"  ★ {key:22s} 경로 선언이 없다 (stem·file·files 전부 없음)")
                continue
            hit = {r for r in rawset
                   for pat in pats
                   if fnmatch.fnmatch(r, pat) or r.startswith(pat.rstrip("/") + "/")}
            pat = " · ".join(pats[:2])
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

    # ── 7. 선언 밖 형제 ★ ──────────────────────────────────
    #
    # ★ 2026-09-03 신설. **모든 검사가 선언된 루트에서 아래로만 봤다.**
    #   treecheck · refcheck · doc_fsck ④ · acquire 가 전부 그렇다.
    #   그래서 `FIRE_LANE_DATA` 의 **형제**에 있는 것은 아무도 못 봤다.
    #
    #   실제 사고 — SSD 에 `data/field/` 가 `fire-lane-data/` 와 나란히
    #   남아 있었고 그 안에 DECISIONS §42 의 네이버 산출 넷이 있었다.
    #   `paths.FIELD` 는 저장소 `data/field` 를 가리키므로(paths.py:128)
    #   SSD 쪽은 어떤 선언에도 안 들어간다. 옮기고 원본을 안 지운 것이다.
    #
    # ★ 이것은 방향이 아니라 **범위**의 단방향이다. 오늘 감사에서 나온
    #   "검사가 한 방향만 본다" 와 같은 병이고, 고치는 법도 같다 —
    #   선언에서 실물로만 가지 말고 실물에서 선언으로도 온다.
    print("\n" + "=" * 62)
    print("7. 선언 밖 형제 (FIRE_LANE_DATA 의 이웃)")
    from firelane.paths import DATA
    if DATA is None:
        print("  FIRE_LANE_DATA 가 없다. 저장소 안에서 도는 중이라 형제가 없다.")
    else:
        lake = Path(DATA)
        base = lake.parent
        stray = []
        for d in sorted(base.iterdir()):
            if not d.is_dir() or d.resolve() == lake.resolve():
                continue
            if d.name.startswith((".", "$")) or d.name == "System Volume Information":
                continue
            fs = [f for f in d.rglob("*") if f.is_file()]
            if fs:
                stray.append((d, fs))
        if not stray:
            print(f"  없다. {base} 아래는 {lake.name} 하나뿐이다.")
        else:
            print(f"  ★ {len(stray)}개 — 데이터 레이크 밖이라 대장도 강제자도 못 본다")
            for d, fs in stray:
                sz = sum(f.stat().st_size for f in fs)
                print(f"    {d.name:24s} {len(fs):4d}개 {human(sz):>10s}  {d}")
                for f in sorted(fs)[:12]:
                    print(f"        {f.relative_to(d)}")
                if len(fs) > 12:
                    print(f"        … 외 {len(fs) - 12}건")
            print("\n  처분은 사람이 정한다 — 레이크로 편입하거나, 대장에 등재하거나,")
            print("  이미 옮긴 원본이면 지운다. **그대로 두지 마라.**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
