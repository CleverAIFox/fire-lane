#!/usr/bin/env python3
"""
webmanifest.py — web/data 산출물의 계보를 만들고 검증한다.

    python -m firelane.webmanifest           지문을 뜬다
    python -m firelane.webmanifest --check   현재 파일이 지문과 같은가

── 왜 필요한가 ────────────────────────────────────────────────
`data/processed/_manifest.json` 은 원본의 source_sha256 까지 박아놨다.
그런데 `web/data/` 에는 매니페스트가 없었다. publish_web.py 산출물인데
계보가 0이다. R5("존재만 보고 건너뛰지 말고 캐시 키에 입력 sha 를 넣어라")가
표출 계층에서 끊긴다.

  - ortho 타일이 어느 정사영상에서 언제 나왔는지 기록이 없다
  - PLAN #11 은 정사영상 정합이 미검증 가정이라고 적어놨다.
    검증 안 된 가정 위 산출물이 저장소에 있는데 출처를 못 되짚는다

타일은 개별 해시를 뜨면 매니페스트가 파일보다 커진다. 줌 레벨별 집계 +
전체 결합 해시로 갈음한다.

── 2026-08-22. tools/web_manifest.py 에서 옮겼다 ──────────────
★ 두 가지가 문제였다.

  1. **생산자가 아닌 곳에 있었다.** publish_web.py 는 web/data 를 쓰면서
     이 매니페스트는 안 만들었고, 사람이 따로 `python tools/web_manifest.py`
     를 기억해서 돌려야 했다. 아무도 안 돌렸다. CI 가 main 에서만 도는
     바람에 2주 동안 아무도 몰랐고, gis 로 켜자마자 바로 잡혔다.
     §5-5(ingest.py 직접 호출 시 계보 누락)와 같은 함정이다.
     이제 publish 가 자기 산출물의 계보를 자기가 쓴다 — ingest 가
     processed/_manifest.json 을 쓰는 것과 같다.

  2. **cwd 에 의존했다.** `WEB = Path("web/data")` 라 저장소 루트에서만
     동작했다. paths 를 쓴다.

★ 오류 메시지도 틀려 있었다. "publish_web.py 를 돌리고 커밋할 것" 이라고
  했는데 publish_web.py 는 이 파일을 만들지 않았다. 그 안내를 따라
  `--only publish` 를 돌렸다가 아무것도 안 바뀌는 일이 실제로 있었다.
  지금은 publish 가 만드므로 그 안내가 비로소 참이 됐다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime

from firelane.paths import PROCESSED, WEB

MANIFEST = WEB / "_manifest.json"
SOURCES = ["segments.geojson", "segments.schema.json", "_manifest.json"]


def sha(p) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> dict:
    src = {}
    for name in SOURCES:
        p = PROCESSED / name
        src[name] = {"sha256": sha(p), "bytes": p.stat().st_size} if p.exists() else None

    files, tiles = {}, {}
    tile_h = hashlib.sha256()

    for p in sorted(WEB.rglob("*")):
        if not p.is_file() or p.name == MANIFEST.name:
            continue
        rel = p.relative_to(WEB).as_posix()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            z = rel.split("/")[1] if "/" in rel else "?"
            t = tiles.setdefault(z, {"count": 0, "bytes": 0})
            t["count"] += 1
            t["bytes"] += p.stat().st_size
            tile_h.update(rel.encode())
            tile_h.update(str(p.stat().st_size).encode())
        else:
            files[rel] = {"sha256": sha(p), "bytes": p.stat().st_size}

    total_mb = (sum(f["bytes"] for f in files.values())
                + sum(t["bytes"] for t in tiles.values())) / 1e6

    return {
        "generated_at": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
        "note": "publish_web.py 산출물. 손으로 고치지 마라 — 다음 실행에 덮어써진다.",
        "source": src,
        "files": files,
        "tiles": dict(sorted(tiles.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)),
        "tiles_digest": tile_h.hexdigest()[:16],
        "total_mb": round(total_mb, 2),
    }


def write() -> dict:
    """지문을 떠서 기록한다. publish_web.py 가 마지막에 부른다."""
    m = build()
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return m


def check() -> int:
    if not MANIFEST.exists():
        print(f"::error::{MANIFEST} 없음 — fire-lane --only publish 를 돌려라")
        return 1
    old = json.loads(MANIFEST.read_text(encoding="utf-8"))
    new = build()

    bad = []
    for rel, meta in old.get("files", {}).items():
        cur = new["files"].get(rel)
        if cur is None:
            bad.append(f"사라짐  {rel}")
        elif cur["sha256"] != meta["sha256"]:
            bad.append(f"변경됨  {rel}")
    for rel in new["files"]:
        if rel not in old.get("files", {}):
            bad.append(f"추가됨  {rel}")
    if old.get("tiles_digest") != new["tiles_digest"]:
        bad.append(f"타일 구성 변경  {old.get('tiles_digest')} -> {new['tiles_digest']}")

    if bad:
        # ★ 안내를 정확히. 종전에는 "publish_web.py 를 돌려라" 였는데 그것이
        #   이 파일을 만들지 않아서, 시키는 대로 해도 안 고쳐졌다.
        print("::error::web/data 가 매니페스트와 다르다. "
              "fire-lane --only publish 를 돌리고 커밋할 것")
        for b in bad[:20]:
            print("  " + b)
        if len(bad) > 20:
            print(f"  ... 외 {len(bad) - 20}건")
        return 1

    print(f"web/data 계보 OK · {new['total_mb']}MB · 타일 {new['tiles_digest']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="기록하지 않고 대조만")
    a = ap.parse_args()
    if a.check:
        return check()
    m = write()
    print(f"기록: {MANIFEST}  ({m['total_mb']}MB · 타일 {m['tiles_digest']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
