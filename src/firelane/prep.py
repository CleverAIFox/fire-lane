#!/usr/bin/env python3
"""
prep.py — raw → norm. **형식만 통일한다. 값은 안 바꾼다.**

    uv run python -m firelane.prep              계획만 (아무것도 안 쓴다)
    uv run python -m firelane.prep --apply       실행
    uv run python -m firelane.prep --check       norm 이 raw 와 정합한가

── 경계 ───────────────────────────────────────────────────────
바꾸는 것 셋 —
    인코딩   → UTF-8 (BOM 없음)
    개행     → LF
    파일명   → 대장의 정규명

★ 그 밖의 무엇도 바꾸지 않는다. 컬럼명 공백을 털고 싶어지고, 빈 문자열을
  NA 로 바꾸고 싶어지고, 좌표 컬럼명이 반대인 것(`fire_station` 의 X좌표에
  위도가 들어 있다)을 고치고 싶어진다. **하면 안 된다.**

  norm 의 값어치는 "원본이 그랬는지 우리가 고친 건지" 를 언제나 가릴 수
  있다는 것 하나다. 그 경계가 흐려지면 norm 은 processed 의 나쁜 사본이
  된다. 값 보정은 `ingest` 가 하고 그 사실이 계보에 남는다.

── 왜 멱등해야 하나 ───────────────────────────────────────────
`normalize_raw` 가 **크기로** "이미 있음" 을 판정했다. 313MB 정사영상이
전송 중 잘려도 같은 크기면 통과했고, 실증됐다(2026-08-23). 여기서는
`_prep.json` 에 (src_sha, dst_sha) 쌍을 남기고 **양쪽 다** 대조한다.
raw 가 바뀌면 다시 만들고, norm 이 손상되면 다시 만든다.

── 미구현이던 이유 ────────────────────────────────────────────
`layers.norm.status: 미구현` 이었고 caveat 이 이렇게 적고 있었다 —
*"디렉터리 문제가 아니라 변환 문제다. ingest 입력 경로가 전부 바뀐다."*

맞다. 그래서 **소스 하나씩 옮긴다.** `layers.norm.migrated` 에 키를 쌓고,
`source_path()` 가 그 목록을 보고 norm 과 raw 중 하나를 돌려준다.
전량 전환 없이 한 건씩 이동할 수 있고, 매 건 `golden.py check` 로
산출물 불변을 확인한다.

IN    $FIRE_LANE_DATA/raw · sources.yaml
OUT   $FIRE_LANE_DATA/norm · data/_prep.json (커밋한다)
PARAM 없음
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from firelane import encoding as enc
from firelane import ledger as _led
from firelane.paths import NORM, RAW, ROOT

KST = timezone(timedelta(hours=9))
STATE = ROOT / "data" / "_prep.json"

# 텍스트만 정규화한다. zip · tif · shp 는 바이트를 건드릴 수 없다.
TEXT_EXT = {".csv", ".txt", ".tsv", ".json", ".prj", ".cpg"}


def sha256(p: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def _sources() -> dict:
    return yaml.safe_load(
        (ROOT / "sources.yaml").read_text(encoding="utf-8")) or {}


def migrated() -> set[str]:
    """norm 으로 옮긴 소스 키. 여기 없는 것은 아직 raw 를 읽는다."""
    L = (_sources().get("layers") or {}).get("norm") or {}
    return set(L.get("migrated") or [])


def source_path(key: str, rel: str) -> Path:
    """이 소스를 지금 어디서 읽어야 하나. **ingest 가 이것만 부른다.**

    ★ 이 함수가 있어서 전량 전환이 필요 없다. 한 건 옮기고, 여기가
      알아서 갈라주고, golden 으로 불변을 확인하고, 다음 건으로 간다.
    """
    if key in migrated():
        p = NORM / rel
        if p.exists():
            return p
        raise FileNotFoundError(
            f"{key} 는 norm 으로 마이그레이션됐다고 선언됐는데 실물이 없다: {p}\n"
            "  ★ 선언과 실물이 어긋난다. prep --apply 를 돌리거나\n"
            "    sources.yaml 의 layers.norm.migrated 에서 키를 빼라.")
    return RAW / rel


def _load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"files": {}, "at": None}


def _targets() -> list[tuple[str, str, dict]]:
    """(key, 상대경로, 대장항목). 텍스트 파일만."""
    out = []
    for key, e in (_sources().get("datasets") or {}).items():
        files = _led.globs(e)
        for pat in files:
            if any(c in pat for c in "*?["):
                for p in sorted(RAW.glob(pat)):
                    if p.suffix.lower() in TEXT_EXT:
                        out.append((key, str(p.relative_to(RAW)), e))
            elif Path(pat).suffix.lower() in TEXT_EXT:
                out.append((key, pat, e))
    return out


def run(*, apply: bool) -> int:
    st = _load_state()
    done = skip = miss = 0
    for key, rel, e in _targets():
        src = RAW / rel
        if not src.exists():
            print(f"  결손  {rel}   (대장에 있는데 raw 에 없다)")
            miss += 1
            continue
        ssha = sha256(src)
        dst = NORM / rel
        rec = st["files"].get(rel)
        if (rec and rec["src_sha256"] == ssha and dst.exists()
                and sha256(dst) == rec["dst_sha256"]):
            skip += 1
            continue

        declared = e.get("encoding")
        v = enc.detect(src)
        problems = enc.verify_declared(src, declared) if declared else []
        tag = "정규화" if apply else "정규화 예정"
        print(f"  {tag}  {rel}")
        print(f"        {v.encoding}/{v.newline} → utf-8/lf"
              f"   한글 {v.hangul_ratio:.3f}")
        for p in problems:
            print(f"        ★ {p.splitlines()[0]}")
        if not apply:
            done += 1
            continue
        # ★ 선언이 있으면 선언으로 읽는다. 판별은 대조용이지 결정용이 아니다.
        #   판별로 읽으면 대장이 정본이라는 원칙이 깨지고, 인코딩이 실행마다
        #   달라질 수 있다.
        meta = enc.to_norm(src, dst, declared=declared or v.encoding)
        st["files"][rel] = {
            "key": key, "src_sha256": ssha, "dst_sha256": sha256(dst),
            **meta,
            "at": datetime.now(KST).isoformat(timespec="seconds"),
        }
        done += 1

    if apply:
        st["at"] = datetime.now(KST).isoformat(timespec="seconds")
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    print(f"\n{'정규화' if apply else '대상'} {done} · 최신 {skip} · 결손 {miss}")
    if not apply and done:
        print("  실제로 쓰려면 --apply")
    return 1 if miss else 0


def check() -> int:
    """norm 이 지금의 raw 에서 나온 것인가. **재현성 게이트다.**"""
    st = _load_state()
    stale = broken = ok = 0
    for rel, rec in st["files"].items():
        src, dst = RAW / rel, NORM / rel
        if not dst.exists():
            print(f"  누락  {rel}")
            broken += 1
        elif sha256(dst) != rec["dst_sha256"]:
            print(f"  손상  {rel}   norm 이 기록과 다르다")
            broken += 1
        elif src.exists() and sha256(src) != rec["src_sha256"]:
            print(f"  낡음  {rel}   raw 가 바뀌었다 — prep --apply 를 돌려라")
            stale += 1
        else:
            ok += 1
    print(f"\n정상 {ok} · 낡음 {stale} · 손상 {broken}")
    return 1 if (stale or broken) else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    return check() if a.check else run(apply=a.apply)


if __name__ == "__main__":
    sys.exit(main())
