#!/usr/bin/env python3
"""
navicheck.py — **내비 그래프가 이미 센 결함을 관문으로 세운다.** 래칫.

    uv run python tools/navicheck.py
    uv run python tools/navicheck.py --snap       막다른 끝 근접 표 (판정 안 함)
    uv run python tools/navicheck.py --selftest

── 왜 생겼나 (DECISIONS §358) ──────────────────────────────────
2026-10-03. `web/data/navi_graph.json` 의 `counts` 를 열었더니 이렇게 적혀
있었다 —

    oneway                57
    oneway_dir_known       1      ★ 일방통행 **56개가 방향을 모른다**
    turn_bans              5      ★ `turn_restriction.csv` 는 87행이다
    park_unplaced_rows 87,015     ★ 단속 141,556행 중 구간에 못 붙었다
    ecam_unplaced_sites   39

**측정은 이미 돼 있었다. 발행물에 적혀 있었다. 그런데 아무도 안 물었다** —
`verify.sh` 88단계 중 이 넷을 보는 단계가 없다. 6족(측정 미결)이다.

★ 이 도구가 **고치지 않는다.** 일방통행 방향을 채우려면 ITS 표준노드링크를
  다시 읽어야 하고 그것은 다른 일이다. 여기가 하는 것은 **못을 박는 것**이다 —
  지금 수에서 더 나빠지면 운다. 좋아지면 `ratchet.py --write` 가 내려 적는다.

── 막다른 끝은 왜 수를 안 무는가 ───────────────────────────────
막다른 길 449/1,139(39.4%)는 큰 수지만 **그 자체는 결함이 아니다.** 골목은
원래 막힌다. 그래서 전수를 래칫으로 걸면 실재하는 막다른 길을 없애라는
뜻이 된다 — 틀린 요구다.

실측으로 갈랐다(2026-10-03 · `--snap`) —

    테두리(maxBounds)에 닿은 것        1 / 449    ← 범위를 자른 자국이 아니다
    1m 안에 다른 노드가 있는 것        20         ★ `node_tol_m` 이 0.5 다
    2m 안                             48
    중앙값                            19.4m
    서로를 최근접으로 가리키는 쌍      58쌍

**1m 안에 이웃이 있는데 안 이어진 것은 스냅 실패다.** 가장 가까운 쌍이
0.59m 로 허용치 0.5m 를 아슬하게 넘는다. 이 수(`DEAD_END_NEAR`)만 문다.

★ `node_tol_m` 을 올릴지는 **여기가 안 정한다.** 경로가 달라지므로 PLAN 의
  일이다. 이 도구는 그 판단에 쓸 표를 낸다(`--snap`).

IN    web/data/navi_graph.json   ★ **커밋돼 있다** — 레이크 없이 돈다
      data/processed/turn_restriction.csv  (있으면 분모로 쓴다)
OUT   표준출력 (판정)
PARAM ONEWAY_DIR_UNKNOWN · TURN_BANS · PARK_UNPLACED · DEAD_END_NEAR (래칫)
밖    **그래프를 안 고친다.** 생산자는 `firelane.publish_navi` 다.
      **어느 수가 옳은가는 안 본다.** 「일방통행 56이 0이어야 하는가」는
      사람의 판단이고, 여기가 드는 것은 「늘었는가」다.
      **판정에 안 닿는다.** `publish_navi` 는 `golden.judgment_files()` 밖이다.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "web" / "data" / "navi_graph.json"
TURNS_CSV = ROOT / "data" / "processed" / "turn_restriction.csv"

#: 스냅 실패로 볼 거리. `node_tol_m`(0.5) 의 두 배 — 측량 잡음의 폭이다.
#: 2026-10-03 실측: 0.5m 안 0건 · 1m 안 20건 · 2m 안 48건. 가장 가까운 쌍 0.59m.
NEAR_M = 1.0

#: 일방통행인데 방향을 못 정한 수. **내린다.**
#: ★ 이력 — 2026-10-03 §358 첫 실측 56 (oneway 57 · dir_known 1).
ONEWAY_DIR_UNKNOWN = 56

#: 그래프에 앉은 회전금지 수. **올린다.** `turn_restriction.csv` 는 87행이다.
#: ★ 이력 — 2026-10-03 §358 첫 실측 5.
TURN_BANS = 5

#: 구간에 못 붙인 단속 행. **내린다.** 분모는 `parking_enforce.csv` 141,556행.
#: ★ 이력 — 2026-10-03 §358 첫 실측 87,015.
PARK_UNPLACED = 87015

#: NEAR_M 안에 다른 노드가 있는데 안 이어진 막다른 끝. **내린다. 0 이 목표다.**
#: ★ 이력 — 2026-10-03 §358 첫 실측 20.
DEAD_END_NEAR = 20

RATCHETS = {"ONEWAY_DIR_UNKNOWN": "down", "TURN_BANS": "up",
            "PARK_UNPLACED": "down", "DEAD_END_NEAR": "down"}


def load() -> dict:
    """그래프를 읽는다. 없으면 빈 그물이므로 부르는 쪽이 운다.

    ★ 경로는 **저장소 안일 때만** 줄여 적는다. 자기검사가 임시 폴더로
      갈아끼우므로 `relative_to` 가 거기서 터진다 — 메시지를 만들다가
      죽으면 「없다」를 「망가졌다」로 읽게 된다.
    """
    if not GRAPH.is_file():
        try:
            shown = GRAPH.relative_to(ROOT).as_posix()
        except ValueError:
            shown = str(GRAPH)
        raise RuntimeError(f"{shown} 가 없다 — 실측 못 한다")
    return json.loads(GRAPH.read_text(encoding="utf-8"))


def _m(a: list[float], b: list[float]) -> float:
    """두 경위도 사이 거리(m). 국소 평면 근사 — 이 범위에서 오차가 cm 아래다."""
    dx = (a[0] - b[0]) * 111_320.0 * math.cos(math.radians(a[1]))
    dy = (a[1] - b[1]) * 111_320.0
    return math.hypot(dx, dy)


def degrees(g: dict) -> Counter:
    """노드 번호 → 닿은 엣지 수. `nodes` 가 좌표 배열이라 **인덱스가 번호**다."""
    deg: Counter = Counter()
    for e in g.get("edges") or []:
        for side in ("a", "b"):
            v = e.get(side)
            if isinstance(v, int):
                deg[v] += 1
    return deg


def dead_ends(g: dict) -> list[int]:
    deg = degrees(g)
    return [i for i in range(len(g.get("nodes") or [])) if deg[i] == 1]


def near_pairs(g: dict, limit_m: float = NEAR_M) -> list[tuple[float, int, int]]:
    """막다른 끝 중 `limit_m` 안에 다른 노드가 있는 것. (거리, 끝, 상대).

    ★ 전수 곱(449 × 1,139)이면 51만 번이고 1초 안이다. 격자를 깔면 빨라지지만
      **빠른 코드와 맞는 코드 중 맞는 쪽을 고른다** — 이 수는 관문이 든다.
    """
    nodes = g.get("nodes") or []
    out = []
    for i in dead_ends(g):
        best = (float("inf"), -1)
        for j, q in enumerate(nodes):
            if j == i:
                continue
            d = _m(nodes[i], q)
            if d < best[0]:
                best = (d, j)
        if best[0] <= limit_m:
            out.append((best[0], i, best[1]))
    return sorted(out)


def turn_rows() -> int | None:
    """`turn_restriction.csv` 행 수. 없으면 None — 레이크 없는 기계가 정상이다."""
    if not TURNS_CSV.is_file():
        return None
    with TURNS_CSV.open(encoding="utf-8-sig", newline="") as fh:
        return sum(1 for _ in csv.reader(fh)) - 1


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. **판정은 안 한다**(`check()` 소관)."""
    g = load()
    c = g.get("counts") or {}
    return {
        "ONEWAY_DIR_UNKNOWN": int(c.get("oneway", 0)) - int(c.get("oneway_dir_known", 0)),
        "TURN_BANS": int(c.get("turn_bans", 0)),
        "PARK_UNPLACED": int(c.get("park_unplaced_rows", 0)),
        "DEAD_END_NEAR": len(near_pairs(g)),
    }


#: 래칫 이름 → (선언값, 사람이 읽는 이름, 늘었을 때 할 말)
_SAY = {
    "ONEWAY_DIR_UNKNOWN": ("일방통행 방향 미상",
                           "역주행으로 보내거나, 피하려다 길을 잃는다. 둘 다 틀린다"),
    "TURN_BANS": ("그래프에 앉은 회전금지",
                  "금지 회전을 지나는 경로가 나온다"),
    "PARK_UNPLACED": ("구간에 못 붙인 단속 행",
                      "상습 주차 가중(PLAN #31 · #60)의 분자가 그만큼 비어 있다"),
    "DEAD_END_NEAR": (f"{NEAR_M:g}m 안에 이웃이 있는 막다른 끝",
                      "끊긴 길이다. 경로가 멀리 돌거나 못 간다고 말한다"),
}


def check() -> int:
    g = load()
    c = g.get("counts") or {}
    got = ratchet_values()
    nodes, edges = len(g.get("nodes") or []), len(g.get("edges") or [])
    de = dead_ends(g)
    print(f"노드 {nodes:,} · 엣지 {edges:,} · 막다른 끝 {len(de):,} "
          f"({len(de)/max(1, nodes):.1%})")
    rows = turn_rows()
    print(f"일방통행 {c.get('oneway', 0)} · 방향 아는 것 {c.get('oneway_dir_known', 0)}"
          f" · 회전금지 {c.get('turn_bans', 0)}"
          + (f" / 원천 {rows}행" if rows is not None else " / 원천은 레이크에 있다"))

    rc = 0
    print()
    for name, want in ((k, globals()[k]) for k in RATCHETS):
        now = got[name]
        label, harm = _SAY[name]
        tighter = "down" if RATCHETS[name] == "down" else "up"
        worse = now > want if tighter == "down" else now < want
        better = now < want if tighter == "down" else now > want
        mark = "✗" if worse or better else "·"
        print(f"  {mark} {label:<34} {now:>7,}  래칫 {want:>7,}")
        if worse:
            print(f"      **나빠졌다.** {harm}")
            rc = 1
        elif better:
            print("      **좋아졌다 — 래칫을 그 수로 옮겨라.** 안 옮기면 다시 는다.")
            print("      uv run python tools/ratchet.py --write")
            rc = 1
    if rc == 0:
        print("\n✓ 내비 그래프가 래칫과 같다")
    return rc


def snap_report() -> int:
    """막다른 끝이 **테두리 자국인가 스냅 실패인가.** 판정 안 한다."""
    g = load()
    nodes = g.get("nodes") or []
    de = dead_ends(g)
    print(f"막다른 끝 {len(de)} / 노드 {len(nodes)}  ({len(de)/max(1,len(nodes)):.1%})"
          f" · node_tol_m = {g.get('node_tol_m')}")
    best: dict[int, tuple[float, int]] = {}
    for i in de:
        b = (float("inf"), -1)
        for j, q in enumerate(nodes):
            if j != i:
                d = _m(nodes[i], q)
                if d < b[0]:
                    b = (d, j)
        best[i] = b
    deg = degrees(g)
    print(f"\n{'거리 이하':>10} {'건':>5} {'누적%':>7}   상대도 막다른 끝")
    for t in (0.5, 0.75, 1, 1.5, 2, 3, 5, 10, 20, 50):
        n = [i for i in de if best[i][0] <= t]
        dd = sum(1 for i in n if deg[best[i][1]] == 1)
        print(f"{t:>9}m {len(n):>5} {len(n)/max(1,len(de)):>6.1%}   {dd:>5}")
    ds = sorted(best[i][0] for i in de)
    print(f"\n중앙값 {ds[len(ds)//2]:.1f}m · 최대 {ds[-1]:.0f}m")
    mutual = sum(1 for i in de if deg[best[i][1]] == 1 and best.get(best[i][1], (0, -1))[1] == i)
    print(f"서로를 최근접으로 가리키는 쌍 {mutual//2}쌍  ← 끊긴 길 후보")
    print(f"\n★ {NEAR_M:g}m 안 {len(near_pairs(g))}건이 `DEAD_END_NEAR` 다. 가까운 열 —")
    for d, i, j in near_pairs(g, 3.0)[:10]:
        print(f"    {d:6.2f}m  노드{i:>5} {nodes[i]}  ↔ 노드{j:>5} (차수 {deg[j]})")
    print("\n★ 아무것도 안 고쳤다. `node_tol_m` 을 올릴지는 PLAN 의 일이다 —")
    print("  경로가 달라지므로 내비 시험과 같이 본다.")
    return 0


def selftest() -> int:
    """★ 반대 방향. **합성 그래프에 심은 결함을 내는가.**"""
    fails = []
    import tempfile
    global GRAPH
    keep = GRAPH

    def fake(counts: dict, nodes: list, edges: list) -> dict:
        return {"crs": "EPSG:4326", "node_tol_m": 0.5, "counts": counts,
                "nodes": nodes, "edges": edges, "turns": []}

    try:
        with tempfile.TemporaryDirectory() as td:
            GRAPH = Path(td) / "g.json"

            # ① 좌표 배열 노드에서 차수를 세는가. 0·1·2 를 잇고 3 은 띄운다.
            #    ★ 노드 3 은 **고아**(차수 0)지 막다른 끝(차수 1)이 아니다.
            #      둘을 섞으면 「길이 끊겼다」와 「길이 없다」가 한 수가 된다.
            g = fake({}, [[126.92, 35.15], [126.921, 35.151],
                          [126.922, 35.152], [126.93, 35.16]],
                     [{"a": 0, "b": 1}, {"a": 1, "b": 2}])
            GRAPH.write_text(json.dumps(g) + "\n", encoding="utf-8")
            if sorted(dead_ends(load())) != [0, 2]:
                fails.append(f"막다른 끝을 못 센다 — {sorted(dead_ends(load()))}")
            if degrees(load())[3] != 0:
                fails.append("고아 노드의 차수가 0 이 아니다")

            # ② NEAR_M 안의 이웃을 잡는가. 0.6m 떨어뜨린 끝 둘을 심는다.
            d = 0.6 / 111_320.0
            g = fake({}, [[126.92, 35.15], [126.921, 35.151],
                          [126.92, 35.15 + d], [126.925, 35.155]],
                     [{"a": 0, "b": 1}, {"a": 2, "b": 3}])
            GRAPH.write_text(json.dumps(g) + "\n", encoding="utf-8")
            near = near_pairs(load())
            if len(near) != 2:
                fails.append(f"0.6m 떨어진 끝 쌍을 못 잡는다 — {len(near)}건")

            # ③ ★ 멀면 안 잡는가. 안 그러면 **항상 우는 검사**다.
            g = fake({}, [[126.92, 35.15], [126.921, 35.151],
                          [126.93, 35.16], [126.931, 35.161]],
                     [{"a": 0, "b": 1}, {"a": 2, "b": 3}])
            GRAPH.write_text(json.dumps(g) + "\n", encoding="utf-8")
            if near_pairs(load()):
                fails.append("먼 끝을 스냅 실패로 센다 — 문턱이 안 듣는다")

            # ④ counts 를 그대로 읽는가. 뺄셈 방향이 맞는가.
            g = fake({"oneway": 10, "oneway_dir_known": 3, "turn_bans": 7,
                      "park_unplaced_rows": 42}, [], [])
            GRAPH.write_text(json.dumps(g) + "\n", encoding="utf-8")
            v = ratchet_values()
            if v["ONEWAY_DIR_UNKNOWN"] != 7:
                fails.append(f"방향 미상이 10-3=7 이 아니다 — {v['ONEWAY_DIR_UNKNOWN']}")
            if (v["TURN_BANS"], v["PARK_UNPLACED"]) != (7, 42):
                fails.append(f"counts 를 그대로 안 읽는다 — {v}")

            # ⑤ ★ 그래프가 없으면 **조용히 0 을 내지 않는가.**
            GRAPH = Path(td) / "없다.json"
            try:
                ratchet_values()
                fails.append("그래프가 없는데 값을 낸다 — 빈 그물이 초록으로 간다")
            except RuntimeError:
                pass
    finally:
        GRAPH = keep

    # ⑥ 실물이 0 이 아닌가 — 빈 그물 방지.
    try:
        if sum(ratchet_values().values()) <= 0:
            fails.append("실측 합이 0 — 발행물을 못 읽었다")
    except RuntimeError as e:
        fails.append(f"실물 그래프를 못 읽는다 — {e}")

    for f in fails:
        print(f"  ✗ {f}")
    print("✓ 자기검사 통과 · 판별식 9" if not fails else f"✗ {len(fails)}건")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    rest = list(sys.argv[1:] if argv is None else argv)
    if rest == ["--selftest"]:
        return selftest()
    if rest == ["--snap"]:
        return snap_report()
    if rest:
        print((__doc__ or "").strip())
        return 2
    return check()


if __name__ == "__main__":
    sys.exit(main())
