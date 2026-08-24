#!/usr/bin/env python3
"""
datalog.py — 데이터 대장 도구

    python -m firelane.datalog record      매니페스트 갱신(파이프라인 끝에서 호출)
    python -m firelane.datalog graph       의존 그래프 → docs/lineage.mmd
    python -m firelane.datalog impact KEY  이 소스를 바꾸면 깨지는 것
    python -m firelane.datalog backup DIR  외장으로 복사 + sha 기록
    python -m firelane.datalog verify DIR  외장 대조
    python -m firelane.datalog check       대장 정합성 검사
    python -m firelane.datalog fsck        계층 선언 ↔ 실물 대조

── 설계 원칙 ──────────────────────────────────────────────────
사람이 손으로 쓰는 대장은 sources.yaml 하나다.
이 스크립트가 만드는 것(_manifest.json, lineage.mmd)은 전부 생성물이고
손으로 고치지 않는다. 손대장이 둘이 되면 반드시 어긋난다.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from firelane.paths import ROOT

KST = timezone(timedelta(hours=9))
SOURCES = ROOT / "sources.yaml"
PROCESSED = ROOT / "data" / "processed"
MANIFEST = PROCESSED / "_manifest.json"
# ★ processed 는 백업하지 않는다. raw + 코드 + 대장으로 재생성된다.
#   보관 우선순위: raw·field(재생성 불가) > norm(재정규화 가능) > processed(버림)
# 저장소 **안**에 있을 때만 해당한다. 밖에 있으면 EXTERNAL_TARGETS 가 잡는다.
BACKUP_TARGETS = ["data/raw", "data/norm", "data/field"]
# raw 는 레포 밖에 있다. 상대경로만 훑으면 2.5GB 가 통째로 빠진다.
# 백업 대상에서 raw 가 빠졌다는 것을 파일 개수로만 알 수 있으면 조용한 결측이다.
#
# ★ 2026-08-23 버그 수정. 종전에는 **폐기된 `FIRE_LANE_RAW` 만** 봤다.
#   현행 변수는 `FIRE_LANE_DATA` 이고(MASTER §6-2), 그것만 설정한 기계에서는
#   EXTERNAL_TARGETS 가 빈 리스트가 되어 **raw 가 백업에서 통째로 빠졌다.**
#   `data/raw` 상대경로는 저장소 안이라 존재하지 않으므로 "백업 대상 없음"
#   한 줄만 찍고 넘어간다 — 정확히 이 파일이 경고하는 조용한 결측이다.
#   경로 정본은 paths.py 다. 여기서 환경변수를 직접 읽지 않는다.
from firelane.paths import FIELD as _FIELD
from firelane.paths import NORM as _NORM
from firelane.paths import RAW as _RAW

EXTERNAL_TARGETS = [q for q in (_RAW, _NORM, _FIELD)
                    if q.exists() and ROOT not in q.parents and q != ROOT]

# ★ raw 와 field 는 재생성이 불가능하다. processed 는 재생성되지만 시간이 든다.
#   이 우선순위가 백업 순서이자 복원 훈련 대상 순서다.
CRITICAL = ["data/raw", "data/field"]


# ──────────────────────────────────────────────────────────────
def sha256(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def git_state() -> dict:
    def run(*a):
        try:
            return subprocess.check_output(["git", *a], cwd=ROOT,
                                           text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return None
    dirty = run("status", "--porcelain")
    return {"sha": run("rev-parse", "--short", "HEAD"),
            "dirty": bool(dirty),
            "dirty_files": (dirty.splitlines()[:10] if dirty else [])}


def load_sources() -> dict:
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}


# ──────────────────────────────────────────────────────────────
def cmd_record() -> None:
    """
    파이프라인 끝에서 호출한다. processed 산출물의 지문을 남긴다.

    ★ git_dirty 인 상태로 만든 산출물은 재현이 불가능하다.
      커밋 안 한 코드로 만든 결과가 발표 자료가 되는 걸 막기 위해 경고한다.
    """
    src = load_sources()
    outputs = src.get("outputs", {}) or {}
    g = git_state()

    rec = {}
    for p in sorted(PROCESSED.glob("*")):
        if p.name.startswith("_") or p.is_dir():
            continue
        entry = {"sha256": sha256(p)[:32], "bytes": p.stat().st_size}
        # 대장에 선언된 산출물이면 계보를 함께 박는다
        for _key, meta in outputs.items():
            if meta.get("path", "").endswith(p.name):
                entry["produced_by"] = meta.get("produced_by")
                entry["inputs"] = meta.get("inputs", [])
                entry["stable_key"] = meta.get("stable_key")
                entry["verified"] = meta.get("verified", False)
                break
        else:
            # 대장에 없는 산출물. 이게 쌓이면 아무도 뭔지 모르는 파일이 늘어난다
            entry["undeclared"] = True
        rec[p.name] = entry

    manifest = {
        "run": {"at": datetime.now(KST).isoformat(timespec="seconds"),
                "git": g, "python": sys.version.split()[0]},
        "outputs": rec,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    n_und = sum(1 for v in rec.values() if v.get("undeclared"))
    print(f"기록 {len(rec)}개 → {MANIFEST}")
    if n_und:
        print(f"  ! 대장에 없는 산출물 {n_und}개. sources.yaml outputs 에 추가할 것")
        for k, v in rec.items():
            if v.get("undeclared"):
                print(f"      {k}")
    if g["dirty"]:
        print("  ! git 워킹트리가 더럽다. 이 산출물은 재현 불가다")
        for f in g["dirty_files"]:
            print(f"      {f}")


# ──────────────────────────────────────────────────────────────
def cmd_graph() -> None:
    """의존 그래프. 손으로 그리지 않는다 — 그리는 순간 낡는다."""
    src = load_sources()
    ds = src.get("datasets", {}) or {}
    out = src.get("outputs", {}) or {}

    L = ["```mermaid", "graph LR"]
    for k, v in ds.items():
        ver = "✓" if v.get("verified") else "?"
        L.append(f'  {k}["{k}<br/>{v.get("vintage","")} {ver}"]')
    for k, v in out.items():
        L.append(f'  {k}(["{k}"])')
        for i in v.get("inputs", []):
            L.append(f"  {i} --> {k}")
        for c in v.get("consumers", []):
            cid = c.replace("/", "_").replace(".", "_")
            L.append(f'  {cid}["{c}"]')
            L.append(f"  {k} --> {cid}")
    L.append("```")

    p = ROOT / "docs" / "lineage.mmd"
    p.parent.mkdir(exist_ok=True)
    p.write_text("\n".join(L), encoding="utf-8")
    print(f"→ {p}  (노드 {len(ds)+len(out)})")


def cmd_impact(key: str) -> None:
    """
    이 소스를 갱신하면 무엇이 깨지는가.
    소스 재다운로드 전에 반드시 돌린다. 이게 consumers 필드의 존재 이유다.
    """
    src = load_sources()
    out = src.get("outputs", {}) or {}
    hit_out = [k for k, v in out.items() if key in v.get("inputs", [])]
    hit_con = sorted({c for k in hit_out for c in out[k].get("consumers", [])})

    print(f"[{key}] 를 바꾸면")
    print(f"  재생성 필요 산출물 {len(hit_out)}")
    for k in hit_out:
        print(f"    - {k}  ({out[k].get('produced_by')})")
    print(f"  영향받는 소비자 {len(hit_con)}")
    for c in hit_con:
        print(f"    - {c}")
    if not hit_out:
        print("  없음 — 대장에 inputs 가 안 적혀 있을 가능성이 크다. check 를 먼저 돌려라")


# ──────────────────────────────────────────────────────────────
def cmd_check() -> None:
    """
    대장 정합성. 셋 다 '조용히 틀어지는' 종류라 자동 검사가 필요하다.
    """
    src = load_sources()
    ds = src.get("datasets", {}) or {}
    out = src.get("outputs", {}) or {}
    bad = 0

    # 1. outputs.inputs 가 datasets 나 outputs 에 실제로 있는가
    known = set(ds) | set(out)
    for k, v in out.items():
        for i in v.get("inputs", []):
            if i not in known:
                print(f"  ! {k}.inputs 의 '{i}' 가 대장에 없다"); bad += 1

    # 2. 필수 필드 누락
    need_ds = ["what", "crs_native", "license", "vintage"]
    for k, v in ds.items():
        for f in need_ds:
            if not v.get(f):
                print(f"  ! datasets.{k} 에 {f} 없음"); bad += 1
    for k, v in out.items():
        for f in ["produced_by", "inputs", "consumers", "what"]:
            # consumers 는 빈 리스트가 정상일 수 있다(아직 아무도 안 쓰는 산출물).
            # 키 자체가 없는 것과 비어 있는 것을 구분한다.
            if f == "consumers":
                if "consumers" not in v:
                    print(f"  ! outputs.{k} 에 consumers 키 없음"); bad += 1
                elif not v["consumers"]:
                    print(f"  · outputs.{k} 는 아직 소비자가 없다")
                continue
            if not v.get(f):
                print(f"  ! outputs.{k} 에 {f} 없음"); bad += 1

    # 3. 선언된 산출물이 실제로 존재하는가
    for k, v in out.items():
        p = ROOT / v.get("path", "")
        if v.get("path") and not p.exists():
            print(f"  ! outputs.{k}.path 없음: {v['path']}"); bad += 1

    # 4. verified=false 인데 발표에 쓰이는 것 (경고만)
    unver = [k for k, v in out.items() if not v.get("verified")]
    if unver:
        print(f"  · 미검증 산출물 {len(unver)}: {', '.join(unver)}")
        print("    미검증 값을 검증된 값처럼 쓰지 마라")

    print("OK" if bad == 0 else f"문제 {bad}건")
    sys.exit(1 if bad else 0)


# ──────────────────────────────────────────────────────────────
def _walk(base: Path):
    for p in sorted(base.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            yield p


def cmd_backup(dest: str) -> None:
    """
    복사하고 지문을 남긴다. rsync 만으로는 부족하다 —
    exFAT 에서 2.5GB 를 날렸을 때 문제는 백업이 없어서가 아니라
    백업이 깨진 걸 몰랐던 것이다.
    """
    import shutil
    D = Path(dest)
    D.mkdir(parents=True, exist_ok=True)
    index = {}
    n = 0
    _pairs = [(ROOT / rel, ROOT) for rel in BACKUP_TARGETS
              if (ROOT / rel).exists()]
    # ★ 저장소 밖 계층(raw · norm). 위와 겹치지 않는다 — 위는 exists() 로
    #   걸러지고 raw 가 밖에 있으면 저장소 안 경로는 존재하지 않는다.
    _pairs += [(ext, ext.parent) for ext in EXTERNAL_TARGETS]
    if not _pairs:
        print("  ★ 백업 대상이 하나도 없다. FIRE_LANE_DATA 를 확인하라.")
        print("     복사할 것이 없는 것과 못 찾은 것은 다르다.")
    for base, anchor in _pairs:
        if not base.exists():
            print(f"  ! 백업 대상 없음: {base}")
            continue
        for p in _walk(base):
            r = str(p.relative_to(anchor))
            t = D / r
            t.parent.mkdir(parents=True, exist_ok=True)
            if not t.exists() or t.stat().st_size != p.stat().st_size:
                # ★ copy2 가 아니라 copyfile 이다.
                #   WSL drvfs(외장 하드) 는 utime 설정을 막아 copy2 가
                #   PermissionError 로 죽는다. 우리가 보존해야 하는 것은
                #   타임스탬프가 아니라 내용이고, 그 검증은 sha256 이 한다.
                shutil.copyfile(p, t)
            index[r] = {"sha256": sha256(p), "bytes": p.stat().st_size}
            n += 1
    (D / "_backup_index.json").write_text(
        json.dumps({"at": datetime.now(KST).isoformat(timespec="seconds"),
                    "files": index}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"백업 {n}개 → {D}")
    print("★ 복원 훈련 주기는 팀 합의 사항이다. 임의로 정하지 않는다.")
    print("  복원해 본 적 없는 백업은 백업이 아니다")


def cmd_verify(dest: str) -> None:
    D = Path(dest)
    idx_p = D / "_backup_index.json"
    if not idx_p.exists():
        print("! _backup_index.json 없음. backup 을 먼저 돌려라")
        sys.exit(1)
    idx = json.loads(idx_p.read_text(encoding="utf-8"))["files"]
    missing, corrupt, ok = [], [], 0
    for rel, meta in idx.items():
        t = D / rel
        if not t.exists():
            missing.append(rel); continue
        if sha256(t) != meta["sha256"]:
            corrupt.append(rel); continue
        ok += 1
    print(f"정상 {ok} · 누락 {len(missing)} · 손상 {len(corrupt)}")
    for r in (missing + corrupt)[:20]:
        crit = " ★재생성불가" if any(r.startswith(c) for c in CRITICAL) else ""
        print(f"  {r}{crit}")
    sys.exit(1 if (missing or corrupt) else 0)



# ── fsck — 계층 선언과 실물을 대조한다 ────────────────────────
def cmd_fsck() -> None:
    """`sources.yaml` 의 layers 선언과 디스크·git·기계 설정을 대조한다.

    ★ 2026-08-24 신설. 이 저장소가 반복해 배운 것은 하나다 —
      **측정은 하는데 대조가 없다.** 계층도 같았다. 문서가 여섯이라 적고
      코드가 넷만 알아도 아무도 몰랐고, 없는 계층을 쓰려던 도구는 자기
      자리를 발명했다(SSD 루트 11.7MB).
    """
    import os
    import subprocess

    from firelane import layers as L

    bad: list[str] = []
    warn: list[str] = []
    print("── 계층 fsck")

    for n in L.names():
        pol, p = L.policy(n), L.path(n)
        mark = "OK  " if p.is_dir() else "없음"
        note = ""
        # ① required — 조용한 폴백을 금지한다
        if pol["required"] and not p.is_dir():
            bad.append(f"{n}: required 인데 없다 — {p}")
            mark = "★없음"
        if pol.get("status") == "미구현":
            note = "  (선언상 미구현)"
        # ② base 가 선언대로인가
        want = L.expected_base(n)
        try:
            p.relative_to(want)
        except ValueError:
            bad.append(f"{n}: base={pol['base']} 인데 {want} 아래가 아니다 — {p}")
        print(f"  {mark} {n:11s} {pol['base']:5s} {p}{note}")

    # ③ naming — 규칙 위반 파일
    print("\n── 파일명 규칙")
    for n in L.names():
        rx = pol_rx = L.policy(n).get("naming")
        p = L.path(n)
        if not rx or not p.is_dir():
            continue
        import re as _re
        pat = _re.compile(pol_rx)
        off = [str(q.relative_to(p)) for q in p.rglob("*")
               if q.is_file() and not q.name.startswith("_")
               and not pat.match(str(q.relative_to(p)))]
        print(f"  {n:11s} 위반 {len(off)}건")
        for q in off[:5]:
            bad.append(f"{n}: 명명규칙 위반 — {q}")

    # ④ committed 선언 ↔ .gitignore 실제
    print("\n── git 추적")
    for n in L.names():
        pol, p = L.policy(n), L.path(n)
        try:
            rel = p.relative_to(ROOT)
        except ValueError:
            continue                     # 저장소 밖이면 git 이 볼 일이 없다
        # ★ 백업 대상인데 저장소 밖인 계층(raw · quarantine)은 여기 안 온다.
        #   그쪽은 datalog verify 가 sha 로 본다.
        r = subprocess.run(["git", "check-ignore", "-q", str(rel)],
                           cwd=ROOT, capture_output=True)
        ignored = (r.returncode == 0)
        # ★ 2026-08-24. 폴더만 보면 안 된다. `.gitignore` 가 폴더를 막고
        #   `!` 로 몇 개만 여는 패턴이 있다(processed 넷). 선언의
        #   committed_exceptions 와 실제 추적 목록을 대조한다.
        exc = set(pol.get("committed_exceptions") or [])
        tracked = set()
        if rel:
            out = subprocess.run(["git", "ls-files", str(rel)], cwd=ROOT,
                                 capture_output=True, text=True).stdout.split()
            tracked = {Path(x).name for x in out}
        if exc:
            miss, extra = sorted(exc - tracked), sorted(tracked - exc)
            ok = not miss and not extra
            print(f"  {'OK  ' if ok else '★   '} {n:11s} "
                  f"예외 {len(exc)}개 · 추적 {len(tracked)}개")
            for q in miss:
                bad.append(f"{n}: 선언은 {q} 를 추적한다는데 git 이 모른다")
            for q in extra:
                bad.append(f"{n}: git 이 {q} 를 추적하는데 선언에 없다")
        else:
            ok = (ignored != bool(pol["committed"]))
            print(f"  {'OK  ' if ok else '★   '} {n:11s} "
                  f"committed={pol['committed']} · gitignore={ignored}")
            if not ok:
                bad.append(f"{n}: committed={pol['committed']} 인데 "
                           f"gitignore={ignored} — 선언과 실제가 다르다")

    # ⑤ regenerable:false 인데 커밋도 안 되고 백업도 아니면 소실 대기
    print("\n── 소실 위험 (R2)")
    for n in L.names():
        pol = L.policy(n)
        if pol["regenerable"] or pol["committed"] or pol["backup"]:
            continue
        if not L.path(n).is_dir():
            continue
        warn.append(f"{n}: 재생성 불가인데 커밋도 백업도 아니다 — 소실 대기")
        print(f"  ★    {n}")
    if not warn:
        print("  없음")

    # ⑥ backup — 마지막 백업 시각
    print("\n── 백업")
    for n in L.of("backup"):
        p = L.path(n)
        print(f"  {n:11s} {'있음' if p.is_dir() else '없음'}  {p}")
    print("  ★ 마지막 백업 시각은 datalog verify DIR 로 확인한다")

    # ⑦ 기계 설정 — 환경변수도 검사 대상이다
    print("\n── 기계 설정")
    if os.environ.get("FIRE_LANE_RAW"):
        bad.append("FIRE_LANE_RAW(폐기) 가 설정돼 있다 — "
                   "FIRE_LANE_DATA 를 덮어써 기계 간 산출물이 갈린다")
        print("  ★    FIRE_LANE_RAW 잔존")
    else:
        print("  OK   FIRE_LANE_RAW 없음")
    if not os.environ.get("FIRE_LANE_DATA"):
        warn.append("FIRE_LANE_DATA 미설정 — raw 가 저장소 안으로 떨어진다")
        print("  ★    FIRE_LANE_DATA 미설정")
    else:
        print("  OK   FIRE_LANE_DATA 설정됨")
    hp = subprocess.run(["git", "config", "core.hooksPath"],
                        cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if hp != ".githooks":
        warn.append("core.hooksPath 미설정 — .githooks 가 텍스트 파일이다. "
                    "git config core.hooksPath .githooks")
        print(f"  ★    core.hooksPath = {hp or '(없음)'}")
    else:
        print("  OK   core.hooksPath = .githooks")

    print()
    for w in warn:
        print(f"  ⚠ {w}")
    for b in bad:
        print(f"  ★ {b}")
    print(f"\n{'계층 선언과 실물이 일치한다' if not bad else f'★ {len(bad)}건 어긋남'}")
    sys.exit(1 if bad else 0)

# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd, *rest = sys.argv[1:]
    {"record": cmd_record, "graph": cmd_graph, "check": cmd_check,
     "impact": cmd_impact, "backup": cmd_backup, "verify": cmd_verify,
     "fsck": cmd_fsck}[cmd](*rest)
