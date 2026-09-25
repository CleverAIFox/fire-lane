#!/usr/bin/env python3
"""
publish_fleet.py — 관내 보유 차종과 제원을 내비가 먹을 형태로 낸다.

IN    sources.yaml (vehicle_spec · vehicle_profiles.items) · web/config.js (CONFIG.fleet)
      web/assets/vehicles/profiles.json (turningRadius — 제원표 참고값)
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
                                     제원표에 값이 있는 차만 숫자로 낸다
                                     (`turn_radius_ref_m`, 2026-09-22 §212)
    전장          판정하지 않는다     인터뷰의 "물탱크차는 못 들어간다" 가
                                     사실 폭이 아니라 전장 문제인데
                                     지금 판정은 폭만 본다
    전고          판정하지 않는다     상공 장애물 데이터가 없다

★ `grade` 와 `turnUnknown` 은 `config.js` 가 이미 든다.

── ★ 회전반경 숫자 — 무엇을 내고 무엇을 안 내는가 (§212) ────────
2026-09-22 결정: **숫자가 있는 제원만 숫자로 띄운다.** 판정에는 여전히
안 쓴다. 숫자가 나가는 조건은 둘 다 참일 때뿐이다 —

    1. 그 차의 `profile` 이 `profiles.json` 에 있고 `turningRadius` 가 null 이 아니다
    2. `config.js` 가 그 차에 `turnUnknown` 을 걸지 않았다

2 가 사다리차 둘을 거른다. 제원표 값이 있지만 차대 축이 달라(2축 대표값 ↔
3축 실차, 길이 구분 ↔ 관절 구분) **그 차의 값이 아니다**(§84-3). 값이
있다고 내면 그것이 §86-5 의 사고다. 1 이 구급 · 구조 · 조연을 거른다 —
제원표에 칸이 비어 있다.

★ 키 이름이 `turn_radius_ref_m` 인 이유 — `vehicle_spec.turn_radius_m`(법정 상한
  12m)은 `turn_radius_verified` 가 켜지면 **판정**에 들어가는 값이다. 같은 이름을
  쓰면 누군가 `{...spec, ...vehicle}` 한 줄로 참고값을 판정에 흘린다. 거른 차는 `turn_radius_ref_m: null` 이고 화면은 등급을
낸다. **없는 숫자를 기본값으로 채우지 않는다.**
"""
from __future__ import annotations

import json
import re

import yaml

from firelane.paths import ROOT

W = ROOT / "web" / "data"
PROFILES = ROOT / "web" / "assets" / "vehicles" / "profiles.json"


def _turn_radii() -> dict[str, float]:
    """`profiles.json` 의 profile id → 최소회전반경(m). 값이 없는 차종은 뺀다.

    ★ 파일이 없으면 죽는다. 조용히 빈 표로 가면 화면의 숫자가 전부
      등급으로 떨어지고, 그것이 「제원이 없다」인지 「못 읽었다」인지
      아무도 못 가른다.
    """
    d = json.loads(PROFILES.read_text(encoding="utf-8"))
    if d.get("units") != "mm":
        raise SystemExit(f"★ profiles.json 단위가 mm 가 아니다: {d.get('units')!r}")
    return {p["id"]: round(p["turningRadius"] / 1000, 1)
            for p in d.get("profiles", []) if p.get("turningRadius")}


#: 「제원 완성」 — 코너 회전 점검에 쓸 수 있는 조건. 전장 · 전폭 · 전고 · 축거 · 최소회전반경이
#: 전부 제원표에 있고, 편성 대장의 차가 그 제원표 차종과 **확정** 대응일 때만이다.
SPEC_KEYS = ("length", "width", "height", "wheelbase", "turningRadius")


def _complete_profiles() -> dict[str, dict]:
    """profile id → {wheelbase_m, turn_radius_m} — 제원 다섯이 다 있는 차종만.

    ★ 2026-09-22 (DECISIONS §218-2). 사용자 결정 — 「회전반경은 제원이 다 확보돼야 쓴다.
      다 확보된 범주는 지원한다」. 지금 그런 범주는 중형 펌프차 · 대형 물탱크차 둘이다.
      미검증(그 동네 그 차를 잰 값이 아니라 제작규격 대표값)이라 **막지 않고** 경로 비용과
      경고에만 쓴다 — 통행 규칙과 같은 정책(§215-1).
    """
    d = json.loads(PROFILES.read_text(encoding="utf-8"))
    return {p["id"]: {"wheelbase_m": round(p["wheelbase"] / 1000, 2),
                      "turn_radius_m": round(p["turningRadius"] / 1000, 1)}
            for p in d.get("profiles", []) if all(p.get(k) for k in SPEC_KEYS)}

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
    radii = _turn_radii()
    complete = _complete_profiles()
    clearance = float(spec["clearance_m"])

    # ★ 2026-09-25 (PLAN §1 #38 · DECISIONS §253). **없는 이름을 조용히 넘기지 않는다.**
    #   종전에는 `profiles.get(id, {})` 가 빈 dict 를 주고 `p.get("width_m", spec["width_m"])`
    #   이 기준차 2.5 로 떨어졌다. 그 결과 열 차종 중 **여섯**이 대장에 없는 이름을
    #   가리키는 채로 전장·전고가 통째로 null 이었고 **아무도 몰랐다** —
    #   인터뷰가 「커서 못 들어간다」고 지목한 물탱크차가 그중 하나다(전장 10.0m).
    #   대장에 **없는** 이름이면 죽는다. 대응이 없는 차는 `profile: null` 로 적는다.
    unknown = sorted({str(f["profile"]) for f in fleet
                      if f.get("profile") and str(f["profile"]) not in profiles})
    if unknown:
        raise SystemExit(
            f"★ config.js 의 fleet 이 대장에 없는 profile 을 가리킨다: {unknown}\n"
            f"  대장 `vehicle_profiles.items` 에 있는 이름: {sorted(profiles)}\n"
            "  대응이 있으면 그 이름으로 고치고, **없으면 `profile: null` 로 적어라.**\n"
            "  없는 이름을 두면 전장·전고가 조용히 null 이 되고 전폭이 기준차로 떨어진다.")

    rows = []
    for f in fleet:
        pid = str(f.get("profile") or "")
        p = profiles.get(pid, {})
        # profile 이 null 인 차는 기준차 전폭을 쓴다 — 그것이 소방청 기준값이고,
        # 그 사실이 `match`/`note` 에 적혀 화면까지 간다(§212).
        width = float(p.get("width_m", spec["width_m"]))
        unknown = bool(f.get("turnUnknown", False))
        radius = None if unknown else radii.get(str(f.get("profile", "")))
        full = None if unknown or f.get("match") != "확정" else complete.get(str(f.get("profile", "")))
        rows.append({
            "id": f["id"],
            "label": f.get("label") or p.get("label") or f["id"],
            "station": f.get("group"),
            "count": int(f.get("count", 1)),
            # ── 판정에 쓰는 값 ──────────────────────────────────
            "width_m": width,
            "clearance_m": clearance,
            "required_width_m": round(width + clearance, 2),
            # ── 참고값. 판정에 안 쓴다 ─────────────────────────
            "turn_grade": f.get("grade"),          # 여유 · 주의 · 미판정
            "turn_unknown": unknown,
            # 제원표 값(m). 그 차의 값이라고 말할 수 없으면 null (§212)
            "turn_radius_ref_m": radius,
            "turn_radius_verified": bool(spec.get("turn_radius_verified", False)),
            # ── 코너 회전 점검(§218-2) — 제원 완성 범주만. 막지 않고 비용 · 경고 ─────
            "spec_complete": full is not None,
            "turn_check_radius_m": full["turn_radius_m"] if full else None,
            "wheelbase_m": full["wheelbase_m"] if full else None,
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
            "전폭과 여유만 판정에 쓴다. 회전반경은 제원표에 그 차의 값이 있을 때만 "
            "참고로 숫자를 내고(미검증 · 판정 미반영), 없으면 등급으로 낸다. "
            "제원 다섯(전장·전폭·전고·축거·회전반경)이 다 있고 대응이 확정인 차종만 "
            "경로가 코너 회전을 점검한다 — 막지 않고 비용과 경고로(spec_complete). "
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
              f"회전 {r['turn_radius_ref_m'] or r['turn_grade'] or '—'}")


if __name__ == "__main__":
    main()
