#!/usr/bin/env python3
"""
release_brief.py — 이 PR 이 무엇을 흡수하는가. 리뷰어가 볼 표를 낸다.

    uv run python tools/release_brief.py                base=dev
    uv run python tools/release_brief.py --base main
    uv run python tools/release_brief.py --base main --md > /tmp/brief.md

── 왜 생겼나 ───────────────────────────────────────────────────
승인이 형식이 되는 이유는 **리뷰어가 무엇을 흡수하는지 모르기 때문**이다.
`gh pr create --fill` 은 커밋 메시지 나열뿐이고, CI 초록불은 "안 깨졌다"
이지 "안전하다" 가 아니다. `§12-1a` 가 *"실제로 막는 것은 승인이 아니라
contract-shared"* 라고 적는데, 그러면 승인은 왜 두는가 —
**두 번째 눈이 볼 것이 있어야** 값이 생긴다(DECISIONS §109).

넷을 본다. 전부 **커밋된 파일**이라 데이터 레이크가 없어도 돈다.

    판정   data/golden/segments.fingerprint.json   4수치가 움직였나
    계보   web/data/_manifest.json                 타일 지문이 바뀌었나
    대장   sources.yaml                            소스가 늘거나 줄었나
    계약   web/data/segments.schema.json           스키마가 바뀌었나

★ 값 차이는 **결정론적으로** 뽑는다. "이 변경이 무엇을 뜻하는가" 는 여기서
  말하지 않는다 — 그것은 사람이 PR 본문에 적는다.

IN    git show <base>:<path>  ·  작업트리
OUT   표준출력 (--md 로 마크다운)
PARAM --base · --md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WATCH = {
    "판정": "data/golden/segments.fingerprint.json",
    "계보": "web/data/_manifest.json",
    "대장": "sources.yaml",
    "계약": "web/data/segments.schema.json",
}


def _at(ref: str, rel: str) -> str | None:
    r = subprocess.run(["git", "show", f"{ref}:{rel}"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _now(rel: str) -> str | None:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def _facts(rel: str, raw: str | None) -> dict[str, object]:
    """파일에서 **비교할 사실만** 뽑는다. 통째 diff 는 리뷰어가 못 읽는다."""
    if raw is None:
        return {}
    if rel.endswith("sources.yaml"):
        import yaml
        y = yaml.safe_load(raw) or {}
        return {"datasets": len(y.get("datasets") or {}),
                "retired": len(y.get("retired") or {})}
    try:
        j = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if "fingerprint" in rel:
        g = j.get("L1", {})
        out: dict[str, object] = {"구간": g.get("n")}
        out.update(g.get("verdict") or {})
        out["총연장m"] = g.get("length_total_m")
        return out
    if "_manifest" in rel:
        # ★ 타일은 줌 레벨별 딕셔너리다. 통째로 내면 리뷰어가 못 읽는다 —
        #   장수와 바이트만 센다. 지문이 같으면 내용도 같다.
        tiles = j.get("tiles") or {}
        n = sum(v.get("count", 0) for v in tiles.values()) if isinstance(tiles, dict) else 0
        return {"타일지문": j.get("tiles_digest"), "타일장수": n,
                "MB": j.get("total_mb"), "파일": len(j.get("files") or [])}
    if "schema" in rel:
        return {"crs": j.get("crs"), "필드수": j.get("count"),
                "sha256": (j.get("sha256") or "")[:12],
                "폭검증": j.get("width_verified")}
    return {}


def main() -> int:
    args = sys.argv[1:]
    base = args[args.index("--base") + 1] if "--base" in args else "dev"
    md = "--md" in args

    rows: list[tuple[str, str, str, str, bool]] = []
    for label, rel in WATCH.items():
        a, b = _facts(rel, _at(f"origin/{base}", rel)), _facts(rel, _now(rel))
        keys = list(dict.fromkeys([*a, *b]))
        if not keys:
            rows.append((label, rel, "—", "읽을 수 없다", False))
            continue
        for k in keys:
            va, vb = a.get(k, "—"), b.get(k, "—")
            rows.append((label, k, str(va), str(vb), va != vb))

    moved = [r for r in rows if r[4]]
    if md:
        print(f"## 이 PR 이 흡수하는 것 (base `{base}`)\n")
        print("| 축 | 항목 | 전 | 후 |")
        print("|---|---|---|---|")
        for label, k, va, vb, ch in rows:
            mark = " **←**" if ch else ""
            print(f"| {label} | `{k}` | {va} | {vb}{mark} |")
        print()
        if moved:
            print(f"★ **{len(moved)}개가 움직였다.** 판정이 바뀌었으면 "
                  "`golden` 재잠금과 전후 값을 본문에 적는다(§12-8b).")
        else:
            print("★ 넷 다 불변이다. 문서·도구만 바뀐 PR 이다.")
        return 0

    print(f"── 흡수 대상 (base origin/{base})\n")
    cur = None
    for label, k, va, vb, ch in rows:
        if label != cur:
            print(f"  [{label}]")
            cur = label
        mark = "  ★" if ch else ""
        print(f"    {k:12} {va:>18} → {vb}{mark}")
    print(f"\n  움직인 것 {len(moved)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
