#!/usr/bin/env python3
"""
tools/segid_audit.py — `seg_id` 가 실제로 불안정한가를 **재서** 보인다.  (Zm27 · DECISIONS §572)

    uv run python tools/segid_audit.py            표 + data/processed/segid_audit.json

── 무엇을 보이나 ───────────────────────────────────────────────
  1  합성   `segments.py` 의 번호 규칙(`sid = f"DM{i:05d}"`, `i` 는 `sorted(units.items())` 의 순번)을 현재 공개본 위에서 그대로
           되풀이한다. 한 도로(또는 구간 하나)를 빼고 다시 번호를 매기면 `seg_id → seg_uid` 매핑이 몇 개나 깨지는가.
  2  이력   git 이력의 `web/data/segments.geojson` 마흔 판과 `data/baseline/*/seg_uid_map.csv` 여덟 판을 **지금 공개본**과 대조한다.
           · `seg_id` 오지시 = 두 판에 다 있는 `seg_id` 중 가리키는 `seg_uid` 가 다른 것의 비율
           · `seg_uid` 유지 = 옛 판의 `seg_uid` 중 지금 판에도 있는 것의 비율
           · 인접한 두 판의 같은 수 — **언제 깨졌나**
IN    git 이력 · data/baseline · data/processed/segments.geojson
OUT   data/processed/segid_audit.json · 화면
PARAM 없다
밖    **아무것도 고치지 않는다.** 읽기만 한다. 합성은 규칙의 복제이지 실행이 아니다(1,041줄 `main()` 을 못 부른다) —
      복제가 규칙과 어긋나면 이 수는 틀린다. 번호 규칙은 `src/firelane/segments.py` 의 `sid = f"DM{i:05d}"` 한 줄이다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUR = ROOT / "data" / "processed" / "segments.geojson"
WEB = "web/data/segments.geojson"
OUT = ROOT / "data" / "processed" / "segid_audit.json"


def _git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def _map(feats: list[dict]) -> dict[str, str | None]:
    return {f["properties"]["seg_id"]: f["properties"].get("seg_uid") for f in feats}


def compare(old: dict[str, str | None], cur: dict[str, str]) -> dict:
    """`old`·`cur` 은 seg_id → seg_uid. `old` 의 seg_uid 가 없으면(옛 판) 비교하지 못한다고 적는다."""
    if not old or all(v is None for v in old.values()):
        return {"n": len(old), "seg_uid_없음": True}
    both = [i for i in old if i in cur]
    wrong = sum(1 for i in both if old[i] != cur[i])
    uo, uc = set(old.values()), set(cur.values())
    id_of_cur = {u: i for i, u in cur.items()}
    id_of_old = {u: i for i, u in old.items()}
    kept = uo & uc
    drift = sum(1 for u in kept if id_of_old[u] != id_of_cur[u])
    return {"n": len(old), "seg_id 겹침": len(both), "seg_id 오지시": wrong,
            "seg_id 오지시 %": round(100 * wrong / len(both), 1) if both else None,
            "seg_uid 유지": len(kept), "seg_uid 유지 %": round(100 * len(kept) / len(uo), 1),
            "유지된 seg_uid 중 번호가 바뀐 것": drift,
            "번호가 바뀐 %": round(100 * drift / len(kept), 1) if kept else None}


def synthetic(cur: dict[str, str], road_of: dict[str, str]) -> list[dict]:
    """번호 규칙을 되풀이한다: 입력 단위들을 정렬해 `enumerate` 로 번호를 다시 매긴다.

    현재 공개본의 단위를 **현재 `seg_id` 순**으로 놓는다(원 규칙의 정렬 키는 노딩 단위 키라 같지 않을 수 있다 — 근사다).
    하나를 빼면 그 **뒤**의 순번이 하나씩 당겨진다. 단위를 **더해도** 똑같이 뒤가 밀린다(구간 분할이 바뀌는 모든 경우).
    """
    order = sorted(cur, key=lambda s: int(s[2:]))
    idx = {s: int(s[2:]) for s in order}
    out = []

    def run(label: str, drop: set[str]) -> None:
        # 원 규칙의 순번은 **범위 밖 단위까지 센 순번**이다(공개본 번호가 1,281 개인데 3,336 까지 있는 이유).
        # 단위 하나가 빠지면 그 **뒤** 단위의 순번만 빠진 개수만큼 당겨진다 — 앞쪽은 안 변한다.
        gone = sorted(idx[s] for s in drop)
        new_id = {s: f"DM{idx[s] - sum(1 for g in gone if g < idx[s]):05d}" for s in order if s not in drop}
        by_new = {v: cur[s] for s, v in new_id.items()}                 # 새 판에서 그 seg_id 가 가리키는 구간
        kept = [s for s in order if s not in drop]
        wrong = sum(1 for s in kept if by_new.get(s) != cur[s])         # 옛 seg_id 를 새 판에서 읽으면 같은 구간인가
        out.append({"시나리오": label, "뺀 구간": len(drop), "남은": len(kept),
                    "옛 seg_id 가 다른 구간을 가리키는 수": wrong,
                    "%": round(100 * wrong / len(kept), 1)})
    run("맨 앞 구간 하나를 뺀다", {order[0]})
    run("가운데 구간 하나를 뺀다", {order[len(order) // 2]})
    run("맨 뒤 구간 하나를 뺀다", {order[-1]})
    roads: dict[str, list[str]] = {}
    for s in order:
        roads.setdefault(road_of.get(s) or "", []).append(s)
    mid = sorted(roads.items(), key=lambda kv: -len(kv[1]))
    for name, ids in (mid[0], mid[len(mid) // 2]):
        run(f"한 도로 「{name}」({len(ids)}구간)를 뺀다", set(ids))
    return out


def history() -> tuple[list[dict], list[dict], list[dict]]:
    cur_feats = json.loads(CUR.read_text(encoding="utf-8"))["features"]
    cur = {k: v for k, v in _map(cur_feats).items()}
    revs = [ln.split() for ln in _git("log", "--format=%h %ad", "--date=short", "--", WEB).splitlines()]   # 새것 먼저
    maps: list[tuple[str, str, dict]] = []
    for h, d in revs:
        feats = json.loads(_git("show", f"{h}:{WEB}"))["features"]
        maps.append((h, d, _map(feats)))
    vs_now = [{"rev": h, "날짜": d, **compare(m, cur)} for h, d, m in maps]
    adj = []
    for (h, d, m), (h2, _d2, m2) in zip(maps, maps[1:], strict=False):         # m 이 새것, m2 가 그 직전
        adj.append({"새 판": h, "날짜": d, "직전 판": h2, **compare(m2, m)})
    base = []
    for p in sorted((ROOT / "data" / "baseline").glob("*/seg_uid_map.csv")):
        with p.open(encoding="utf-8", newline="") as f:
            m = {r["seg_id"]: r["seg_uid"] for r in csv.DictReader(f)}
        base.append({"baseline": p.parent.name, **compare(m, cur)})
    return vs_now, adj, base


def main() -> int:
    cur_feats = json.loads(CUR.read_text(encoding="utf-8"))["features"]
    cur = _map(cur_feats)
    road = {f["properties"]["seg_id"]: f["properties"].get("road_name") for f in cur_feats}
    syn = synthetic(cur, road)
    vs_now, adj, base = history()
    res = {"현재 공개본": {"n": len(cur), "seg_uid 유일": len(set(cur.values())) == len(cur)},
           "합성": syn, "이력(웹 판 vs 지금)": vs_now, "이력(인접 두 판)": adj, "baseline vs 지금": base}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("합성 — 번호를 다시 매기면 옛 seg_id 가 다른 구간을 가리키는 수")
    for s in syn:
        print(f"  {s['시나리오']:<36} {s['옛 seg_id 가 다른 구간을 가리키는 수']:>5} / {s['남은']} ({s['%']}%)")
    print("\n이력 — 지금 공개본 대비 (오지시 = 같은 seg_id 가 다른 seg_uid · 유지 = 옛 seg_uid 가 지금도 있다)")
    for r in vs_now:
        print("  ", r["rev"], r["날짜"], r.get("seg_id 오지시 %"), r.get("seg_uid 유지 %"), r.get("seg_uid_없음", ""))
    print("\n인접 두 판")
    for r in adj:
        print("  ", r["새 판"], r["날짜"], "←", r["직전 판"], r.get("seg_id 오지시 %"), r.get("seg_uid 유지 %"), r.get("seg_uid_없음", ""))
    print("\nbaseline 지금 대비")
    for r in base:
        print("  ", r["baseline"], r.get("seg_id 오지시 %"), r.get("seg_uid 유지 %"), r.get("seg_uid_없음", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
