#!/usr/bin/env python3
"""
acquire.py — landing → raw 획득 게이트. **적재한 것을 검증한다.**

    uv run python tools/acquire.py                 세 판정만 (아무것도 안 옮긴다)
    uv run python tools/acquire.py --stage         landing → raw 편입
    uv run python tools/acquire.py --verify        raw 와 landing 의 sha 대조
    uv run python tools/acquire.py --prune-landing raw 와 sha 가 같은 landing 원본 삭제
    uv run python tools/acquire.py --quarantine    대장에 없는 raw 파일을 격리

── 왜 만들었나 ────────────────────────────────────────────────
MASTER §18-12 는 이 도구를 **이름까지 적어놓고** 있었다.

    landing (외장 SSD fire-lane-data/)
            ↓  acquire.py stage  — 대장 매칭
    data/raw/<제공기관>/
    data/_quarantine/

**그런데 파일이 없었다.** `contract.py` 머리말이 적은 것과 같은 일이다 —
*"설계는 있었고 구현이 없었다."* 그래서 실제로는 이렇게 굴러갔다.

    적재   normalize_raw.py 가 landing → raw 로 **복사**한다
    검증   없다
    정리   없다

그 결과가 2026-08-23 SSD 스캔에 그대로 찍혔다.

    landing 32개 2.4GB · raw 32개 3.4GB   ← 같은 파일이 두 벌
    격리 대상 4건                          ← 대장에 없는데 raw 에 있다
    raw/nsdi/AL_D002_12_20260808.zip 970MB ← 폴더 규칙·명명규칙·대장 전부 밖

★ 제일 나쁜 것은 `normalize_raw` 의 "이미 있음" 판정이다.

    if dst.exists() and dst.stat().st_size == f.stat().st_size:  # 크기만 본다

  **크기가 같으면 통과한다.** 313MB 정사영상이 전송 중 잘려도, 다른 판이
  같은 크기로 와도 못 잡는다. 실증했다 — 같은 크기 · 다른 sha 두 파일을
  놓으면 "이미 있음 1건" 으로 넘어간다.

  이 저장소는 exFAT 에서 2.5GB 를 날렸을 때 *"문제는 백업이 없어서가 아니라
  백업이 깨진 걸 몰랐던 것"* 이라고 적었다(§18-8). 획득 쪽에 같은 구멍이
  그대로 남아 있었다.

── 세 판정 (§18-12) ───────────────────────────────────────────
    대장에 있음 + 파일 있음   →  raw 편입 · sha 기록
    대장에 있음 + 파일 없음   →  ★ 결손 경고
    대장에 없음 + 파일 있음   →  _quarantine (삭제하지 않는다)

★ 멱등하다. 같은 sha 면 다시 복사하지 않고, `--stage` 를 몇 번 돌려도 결과가
  같다. 크기가 아니라 **내용**으로 판정하므로 그 약속이 실제로 성립한다.

IN    $FIRE_LANE_DATA/landing · sources.yaml
OUT   $FIRE_LANE_DATA/raw · _quarantine · raw/_acquire.json (sha 대장)
PARAM 없음
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from firelane.paths import QUARANTINE, RAW, ROOT

KST = timezone(timedelta(hours=9))
LANDING = RAW.parent / "landing"
LEDGER = RAW / "_acquire.json"          # 무엇을 언제 어떤 sha 로 넣었나

C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m",
     "c": "\033[36m", "d": "\033[90m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}"
        n /= 1024
    return ""


def sha256(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def load_ledger() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"files": {}}


def save_ledger(d: dict) -> None:
    d["at"] = datetime.now(KST).isoformat(timespec="seconds")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def dataset_globs() -> dict[str, str]:
    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    return {k: (v or {}).get("file", "") for k, v in y.get("datasets", {}).items()}


def raw_files() -> list[Path]:
    if not RAW.is_dir():
        return []
    return sorted(p for p in RAW.rglob("*")
                  if p.is_file() and not p.name.startswith("_"))


# ── 판정 ───────────────────────────────────────────────────────
def judge() -> tuple[dict, list[str], list[Path]]:
    """(대장키 → 매칭 파일들, 결손 키, 격리 대상 파일)."""
    globs = dataset_globs()
    matched: dict[str, list[Path]] = {}
    claimed: set[Path] = set()
    missing: list[str] = []
    for k, g in globs.items():
        if not g:
            continue
        hits = sorted(RAW.glob(g)) if RAW.is_dir() else []
        if hits:
            matched[k] = hits
            claimed |= set(hits)
        else:
            missing.append(k)
    orphan = [p for p in raw_files() if p not in claimed]
    return matched, missing, orphan


def cmd_judge() -> int:
    matched, missing, orphan = judge()
    print(col("── 세 판정 (MASTER §18-12)", "c"))
    print(f"  {col('편입', 'g')}    {len(matched)}종")
    if missing:
        print(f"  {col('★ 결손', 'r')}  {len(missing)}종 — 대장에 있는데 파일이 없다")
        for k in missing:
            print(f"      {k}")
        print(col("      결손은 폐기가 아니다. 재취득하거나 retired 로 옮겨라.", "d"))
    if orphan:
        n = sum(p.stat().st_size for p in orphan)
        print(f"  {col('★ 격리 대상', 'y')}  {len(orphan)}건 · {human(n)} — 대장에 없다")
        for p in orphan:
            print(f"      {human(p.stat().st_size):>10}  {p.relative_to(RAW)}")
        print(col("      대장에 추가하거나 retired 에 사유를 적고 _quarantine 으로 내려라.", "d"))
    if not missing and not orphan:
        print(f"  {col('대장과 실물이 일치한다', 'g')}")
    return 1 if (missing or orphan) else 0


# ── 검증 ───────────────────────────────────────────────────────
def cmd_verify() -> int:
    """raw 파일의 sha 를 대장(_acquire.json)과 대조한다.

    ★ 크기가 아니라 내용을 본다. `normalize_raw` 의 "이미 있음" 은 크기만
      봐서, 같은 크기로 잘린 파일을 통과시킨다.
    """
    led = load_ledger()["files"]
    files = raw_files()
    if not files:
        print(col(f"raw 가 비었다: {RAW}", "r"))
        return 1
    if not led:
        print(col("sha 대장이 없다 — 지금 만든다 (기준선)", "y"))
        d = {"files": {}}
        for p in files:
            d["files"][str(p.relative_to(RAW))] = {
                "sha256": sha256(p), "bytes": p.stat().st_size}
            print(f"  {col('기록', 'd')}  {p.relative_to(RAW)}")
        save_ledger(d)
        print(f"\n{col(f'{len(files)}개 기록 → {LEDGER}', 'g')}")
        return 0

    bad, new = [], []
    for p in files:
        rel = str(p.relative_to(RAW))
        want = led.get(rel)
        if want is None:
            new.append(rel)
            continue
        if p.stat().st_size != want["bytes"]:
            bad.append((rel, "크기 다름", f"{want['bytes']} → {p.stat().st_size}"))
            continue
        got = sha256(p)
        if got != want["sha256"]:
            # ★ 크기가 같은데 sha 가 다르다. 이것이 정확히 normalize_raw 가
            #   놓치는 경우다 — 손상됐거나, 같은 크기의 다른 판이다.
            bad.append((rel, "★ 크기 같고 내용 다름",
                        f"{want['sha256'][:12]} → {got[:12]}"))
    gone = [r for r in led if not (RAW / r).exists()]

    print(col("── sha 대조", "c"))
    print(f"  검사 {len(files)}개")
    for rel, why, detail in bad:
        print(f"  {col(why, 'r')}  {rel}\n      {col(detail, 'd')}")
    for rel in gone:
        print(f"  {col('사라짐', 'r')}  {rel}")
    for rel in new:
        print(f"  {col('대장에 없음', 'y')}  {rel}   (--verify 를 다시 돌리면 기록된다)")
    if not (bad or gone):
        print(f"  {col('전부 일치', 'g')}")
        if new:
            led2 = load_ledger()
            for rel in new:
                p = RAW / rel
                led2["files"][rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
            save_ledger(led2)
            print(f"  {col(f'새 파일 {len(new)}개 기록', 'd')}")
        return 0
    print(col("\n★ 손상되거나 바뀐 파일이 있다. raw 는 불변이어야 한다.", "r"))
    print("  landing 원본이 남아 있으면 --stage 로 다시 넣고, 없으면 재취득하라.")
    return 1


# ── 편입 ───────────────────────────────────────────────────────
def cmd_stage(dry: bool) -> int:
    """landing → raw. 이름 규칙은 normalize_raw 가 정본이므로 그것을 부른다.

    ★ 여기서 규칙을 다시 쓰지 않는다. RULES 가 두 곳에 살면 반드시 어긋난다.
    """
    if not LANDING.is_dir():
        print(col(f"landing 이 없다: {LANDING}", "y"))
        return 0
    import subprocess
    args = [sys.executable, "-m", "firelane.normalize_raw", str(LANDING)]
    if dry:
        args.append("--dry-run")
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode:
        return r.returncode
    if dry:
        return 0
    print(col("\n── 편입 후 sha 기록", "c"))
    return cmd_verify()


# ── landing 정리 ───────────────────────────────────────────────
def cmd_prune_landing(dry: bool) -> int:
    """raw 에 **내용까지 같은** 사본이 있는 landing 원본을 지운다.

    ★ 크기가 아니라 sha 로 짝을 찾는다. landing 은 원본 파일명이고 raw 는
      규칙 파일명이라 이름으로는 못 맞춘다.
    ★ sha 가 같은 것만 지운다. 하나라도 다르면 그 파일은 남긴다 —
      "복사가 성공했다" 는 확인 없이 원본을 지우면 그게 소실이다.
    """
    if not LANDING.is_dir():
        print(col(f"landing 이 없다: {LANDING}", "y"))
        return 0
    raw_sha = {}
    for p in raw_files():
        raw_sha.setdefault(sha256(p), []).append(p)

    freed, keep = 0, []
    print(col("── landing 정리 (raw 와 내용이 같은 것만)", "c"))
    for p in sorted(LANDING.rglob("*")):
        if not p.is_file():
            continue
        s = sha256(p)
        twin = raw_sha.get(s)
        if twin:
            freed += p.stat().st_size
            print(f"  {col('중복', 'g')}  {human(p.stat().st_size):>10}  {p.name}")
            print(f"        {col('= ' + str(twin[0].relative_to(RAW)), 'd')}")
            if not dry:
                p.unlink()
        else:
            keep.append(p)

    if keep:
        print(f"\n  {col('raw 에 짝이 없다 — 남긴다', 'y')}  {len(keep)}건")
        for p in keep[:12]:
            print(f"      {human(p.stat().st_size):>10}  {p.name}")
        print(col("      아직 편입 안 된 것이거나, 편입본과 내용이 다르다.", "d"))
        print(col("      --stage 를 먼저 돌리고 --verify 로 확인하라.", "d"))
    print(f"\n  {col(('지울 수 있는' if dry else '지운') + f' 용량 {human(freed)}', 'g')}")
    if dry and freed:
        print("  실제로 지우려면:  --prune-landing --yes")
    return 0


# ── 격리 ───────────────────────────────────────────────────────
def cmd_quarantine(dry: bool) -> int:
    _, _, orphan = judge()
    if not orphan:
        print(col("격리할 것이 없다.", "g"))
        return 0
    print(col("── 격리 (삭제하지 않는다)", "c"))
    for p in orphan:
        dst = QUARANTINE / p.relative_to(RAW)
        print(f"  {col('격리', 'y')}  {p.relative_to(RAW)}  →  {dst.relative_to(QUARANTINE.parent)}")
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dst))
    if dry:
        print("\n  실제로 옮기려면:  --quarantine --yes")
    else:
        print(col(f"\n  {len(orphan)}건 격리. 대장에 추가할지 retired 로 보낼지 정하라.", "d"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="store_true", help="landing → raw 편입")
    ap.add_argument("--verify", action="store_true", help="raw sha 대조")
    ap.add_argument("--prune-landing", action="store_true", help="중복 원본 삭제")
    ap.add_argument("--quarantine", action="store_true", help="대장에 없는 파일 격리")
    ap.add_argument("--yes", action="store_true", help="실제로 옮기거나 지운다")
    a = ap.parse_args()

    if not RAW.is_dir():
        print(col(f"raw 가 없다: {RAW}", "r"))
        print("  export FIRE_LANE_DATA=<raw 상위 폴더>")
        return 1
    print(f"{col('raw', 'd')}      {RAW}")
    print(f"{col('landing', 'd')}  {LANDING}{'' if LANDING.is_dir() else '   (없음)'}\n")

    if a.stage:
        return cmd_stage(not a.yes)
    if a.verify:
        rc = cmd_verify()
        # ★ 종료코드가 곧 게이트다. 파이프라인·CI 가 이것을 본다.
        return rc
    if a.prune_landing:
        return cmd_prune_landing(not a.yes)
    if a.quarantine:
        return cmd_quarantine(not a.yes)
    return cmd_judge()


if __name__ == "__main__":
    raise SystemExit(main())
