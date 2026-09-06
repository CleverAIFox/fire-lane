#!/usr/bin/env python3
"""
publish_fleet.py — 관내 보유 차종과 제원을 내비가 먹을 형태로 낸다.

IN    sources.yaml (vehicle_spec · vehicle_profiles.items) · web/config.js (CONFIG.fleet)
OUT   web/data/fleet.json
PARAM 없음

── 왜 필요한가 ─────────────────────────────────────────────────
와이어프레임의 **출동 차량 선택** 화면이 차종 목록과 제원을 요구한다.
지금 `vehicle_spec.json` 은 **기준 차량 한 대 분량**이라 그 화면을 못 만든다.

정본이 둘로 나뉘어 있다. 그대로 둔 채 이어 붙인다 —

    vehicle_profiles.items   차종별 제원 (KFS 7종 규격)
    web/config.js CONFIG.fleet  관내 배치 (안전센터 · 대수 · 확정 여부)

★ 어느 쪽도 여기서 재선언하지 않는다. `publish_navi.py` 가 판정색을
  `config.js` 에서 뽑은 것과 같은 방식이다(MASTER §10-2).

── ★ 무엇을 판정에 쓰고 무엇을 참고로 두는가 ───────────────────
화면이 그것을 구분해 말해야 한다. `DECISIONS §86-5` 가 겪은 자리다 —
판정은 "못 믿는 값" 으로 아는데 화면이 확정처럼 띄웠다.

    전폭          판정에 쓴다        KFS-1-0073 §3.3 확인
    여유          판정에 쓴다        추정 (D-30)
    최소회전반경   **참고만**         turn_radius_verified: false
    전장          판정하지 않는다     인터뷰의 "물탱크차는 못 들어간다" 가
                                     사실 폭이 아니라 전장 문제인데
                                     지금 판정은 폭만 본다
    전고          판정하지 않는다     상공 장애물 데이터가 없다

★ `grade` 와 `turnUnknown` 은 `config.js` 가 이미 든다. 화면은 그것을
  그대로 쓰고 숫자를 확정처럼 띄우지 않는다.
"""
from __future__ import annotations

import json
import re

import yaml

from firelane.paths import ROOT

W = ROOT / "web" / "data"

# CONFIG.fleet 한 항목을 통째로 잡는다. 중첩 중괄호가 없어 이 정도로 충분하다.
_ENTRY = re.compile(r"\{\s*id\s*:\s*\"([^\"]+)\"(.*?)\}\s*,", re.S)
_KV_S = re.compile(r"(\w+)\s*:\s*\"([^\"]*)\"")
_KV_N = re.compile(r"(\w+)\s*:\s*(\d+(?:\.\d+)?)")
_KV_B = re.compile(r"(\w+)\s*:\s*(true|false)")


def _fleet_from_config() -> list[dict]:
    """`web/config.js` 의 CONFIG.fleet 배열을 읽는다.

    ★ 정규식으로 JS 를 읽는다. 취약하지만 대상이 한 블록뿐이고
      **못 읽으면 죽는다** — 차종이 빠진 채 발행되면 화면이 조용히
      기준 차량 하나만 보여주고 아무도 못 알아챈다.
    """
    txt = (ROOT / "web" / "config.js").read_text(encoding="utf-8")
    try:
        blk = txt[txt.index("fleet:"):]
        blk = blk[:blk.index("\n  ],") + 4]
    except ValueError:
        raise SystemExit("★ web/config.js 에서 fleet 블록을 못 찾았다") from None

    out = []
    for vid, body in _ENTRY.findall(blk):
        rec: dict = {"id": vid}
        rec.update({k: v for k, v in _KV_S.findall(body)})
        rec.update({k: float(v) for k, v in _KV_N.findall(body)})
        rec.update({k: v == "true" for k, v in _KV_B.findall(body)})
        out.append(rec)
    if not out:
        raise SystemExit("★ CONFIG.fleet 에서 차량을 하나도 못 읽었다")
    return out


def main() -> None:
    src = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    spec = src.get("vehicle_spec") or {}
    if not spec:
        raise SystemExit(
            "★ sources.yaml 에 vehicle_spec 이 없다. seg/vehicle.py 와 같은 이유로"
            " 기본값을 두지 않는다 — 두면 아무도 안 채우고 그 값이 판정에 들어간다.")

    profiles = (src.get("vehicle_profiles") or {}).get("items") or {}
    fleet = _fleet_from_config()
    clearance = float(spec["clearance_m"])

    rows = []
    for f in fleet:
        p = profiles.get(str(f.get("profile", "")), {})
        width = float(p.get("width_m", spec["width_m"]))
        rows.append({
            "id": f["id"],
            "label": f.get("label") or p.get("label") or f["id"],
            "station": f.get("group"),
            "count": int(f.get("count", 1)),
            # ── 판정에 쓰는 값 ──────────────────────────────────
            "width_m": width,
            "clearance_m": clearance,
            "required_width_m": round(width + clearance, 2),
            # ── 참고값. 화면이 숫자 대신 등급을 띄운다 ──────────
            "turn_grade": f.get("grade"),          # 여유 · 주의 · 미판정
            "turn_unknown": bool(f.get("turnUnknown", False)),
            "turn_radius_verified": bool(spec.get("turn_radius_verified", False)),
            # ── 판정하지 않는 값 ────────────────────────────────
            "length_m": p.get("length_m"),
            "height_m": p.get("height_m"),
            "match": f.get("match"),               # 확정 · 추정
            "note": f.get("note"),
        })

    default = next((r["id"] for r in rows if r["id"].startswith("pump-js")),
                   rows[0]["id"])
    out = {
        "default": default,
        "note": (
            "전폭과 여유만 판정에 쓴다. 회전반경은 미검증이라 등급으로만 낸다. "
            "전장·전고는 판정하지 않는다 — 전장은 폭만 보는 현재 판정의 한계이고, "
            "전고는 상공 장애물 데이터가 없다."),
        "source": str(spec.get("source", ""))[:300],
        "vehicles": rows,
    }
    W.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    (W / "fleet.json").write_text(txt, encoding="utf-8")

    print(f"  fleet.json  차종 {len(rows)} · 총 {sum(r['count'] for r in rows)}대"
          f" · {len(txt.encode()) / 1024:.1f}KB")
    for r in rows:
        print(f"    {r['label']:18s} {r['station'] or '':14s} "
              f"폭 {r['width_m']}m · 필요 {r['required_width_m']}m · "
              f"회전 {r['turn_grade'] or '—'}")


if __name__ == "__main__":
    main()
