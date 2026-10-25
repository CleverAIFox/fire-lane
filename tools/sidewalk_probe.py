#!/usr/bin/env python3
"""
tools/sidewalk_probe.py — 「보도가 **없는** 것」과 「보도가 **자료에 없는** 것」을 가르는 표본표를 뽑는다.  (Zm32 · DECISIONS §577)

    uv run python tools/sidewalk_probe.py            data/field/sidewalk_probe_2610.csv 를 쓴다 (이미 있으면 거부 — 사람이 채운 표를 덮지 않는다)
    uv run python tools/sidewalk_probe.py --force    채워진 행이 없을 때만 다시 뽑는다

── 무엇을 재나 ───────────────────────────────────────────────
보도 폴리곤(1:1,000 `A0033320`)이 구간 중심선 20m 안에 **없는** 구간(`tools/carve_survey.py` 의 표본틀 — 재현한 구간 중 1,041)에서 무작위 20구간을 뽑는다.
사람이 **거리뷰로 「보도 · 보행포장이 실제로 있나」만** 본다. **폭은 안 잰다.** 20개 중 몇 개에 실제로 있는지가 **자료 결손률**이다.

★ 이 표는 평가셋(`evalset_2610.csv`) · 뒤집힘 표(`flip_*_2610.csv`)와 **별개다.** 합치지 않는다. 봉인하지 않는다.
★ 표본이 20개라 결손률의 불확실성이 크다(예: 20 중 6 이면 95% 신뢰구간이 대략 15~52%). 점추정이 아니라 **범위**로 읽는다.
★ 시드는 기존 규약이다(`tools/evalgen.py` 의 `SEED`). 표본틀은 `seg_id` 순으로 놓고 뽑는다 — 폭 · 판정 · 대장으로 정렬하지 않는다.

IN    data/processed/carve_survey.json (표본틀) · 발행본(구간 중점 · 도로명 · 길이)
OUT   data/field/sidewalk_probe_2610.csv
PARAM `K` (20) · 시드(`evalgen.SEED`)
밖    **판정을 안 바꾼다.** 보도가 있다고 확인돼도 이 도구는 폭 계산에 아무것도 안 한다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

from evalgen import SEED

ROOT = Path(__file__).resolve().parents[1]
CARVE = ROOT / "data" / "processed" / "carve_survey.json"
OUT_CSV = ROOT / "data" / "field" / "sidewalk_probe_2610.csv"
FRAME_KEY = "표본틀 — 재현한 구간 중 보도 20m 밖"
K = 20
HUMAN_COLS = ("sidewalk_present", "note")
COLS = ("seg_id", "seg_uid", "위도", "경도", "도로명", "length_m", *HUMAN_COLS)
HEAD = (
    "# 보도 자료 결손 표본 (Zm32 · DECISIONS §577) — 이 머리는 읽는 쪽이 '#' 로 시작하는 줄을 건너뛴다",
    "# 1) 거리뷰로 「보도 · 보행포장이 실제로 있나」만 본다. 폭은 재지 않는다",
    "# 2) sidewalk_present = Y(있다) · N(없다) · ?(거리뷰가 없거나 판단 못 한다). 보도 = 연석 · 포장색 · 질감 · 노란선으로 차도와 가른 보행자 공간. 주차선은 보도가 아니다",
    "# 3) 한쪽에라도 있으면 Y 다. 어느 쪽인지는 note 에 적는다(선택)",
    "# 4) 자료 결손률 = Y ÷ (Y + N). ? 는 분모에서 뺀다. 표본이 20개라 범위로 읽는다",
    "# 5) 이 표는 evalset_2610.csv · flip_*_2610.csv 와 별개다 — 합치지 않는다. 구간의 키는 seg_uid 다(seg_id 는 재발행하면 밀린다)",
    "# 6) 위경도 = 구간 중점(WGS84 · 소수 6자리 · 「위도, 경도」). 표본틀 = 보도 폴리곤이 구간 중심선 20m 안에 없는 구간",
)


def draw(frame: list[dict], k: int, seed: int = SEED) -> list[dict]:
    """표본틀에서 `k` 개를 뽑는다. **`seg_id` 순으로 놓고** 시드로 뽑는다 — 판정 · 폭으로 정렬하지 않는다. 틀이 `k` 보다 작으면 틀 전부."""
    ordered = sorted(frame, key=lambda r: r["seg_id"])
    return random.Random(seed).sample(ordered, min(k, len(ordered)))


def load_frame(path: Path | None = None) -> list[dict]:
    path = CARVE if path is None else path
    if not path.exists():
        sys.exit(f"★ {path.name} 이 없다 — 먼저 `uv run python tools/carve_survey.py` 를 돌려라")
    return json.loads(path.read_text(encoding="utf-8"))[FRAME_KEY]


def build(frame: list[dict], props: dict[str, dict], mids: dict[str, tuple[float, float]], k: int = K) -> list[dict]:
    rows = []
    for r in draw(frame, k):
        p, (lat, lon) = props[r["seg_id"]], mids[r["seg_id"]]
        if p["seg_uid"] != r["seg_uid"]:
            sys.exit(f"★ {r['seg_id']} 의 seg_uid 가 표본틀과 발행본에서 다르다 — 번호가 밀렸다. 표본틀을 다시 만든다(carve_survey)")
        rows.append({"seg_id": r["seg_id"], "seg_uid": r["seg_uid"], "위도": f"{lat:.6f}", "경도": f"{lon:.6f}",
                     "도로명": p.get("road_name") or "", "length_m": p["length_m"], "sidewalk_present": "", "note": ""})
    return rows


def write(rows: list[dict], path: Path | None = None) -> None:
    path = OUT_CSV if path is None else path          # 호출 시점에 읽는다(§571)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("\n".join(HEAD) + "\n")
        w = csv.DictWriter(f, fieldnames=list(COLS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def filled(path: Path | None = None) -> bool:
    path = OUT_CSV if path is None else path
    with path.open(encoding="utf-8", newline="") as f:
        return any((r.get("sidewalk_present") or "").strip() for r in csv.DictReader(ln for ln in f if not ln.startswith("#")))


def main(argv: list[str] | None = None) -> int:
    force = "--force" in (sys.argv[1:] if argv is None else argv)
    if OUT_CSV.exists():
        if filled():
            print("채워진 행이 있다 — 덮어쓰기를 거부한다(--force 로도 안 된다).")
            return 3
        if not force:
            print(f"{OUT_CSV.name} 이 이미 있다 — 다시 뽑으려면 --force")
            return 3
    import sensitivity as S  # 구간 중점 · 발행본 속성은 한 집에서 읽는다
    feats = json.loads(S.SEG.read_text(encoding="utf-8"))["features"]
    props = {f["properties"]["seg_id"]: f["properties"] for f in feats}
    rows = build(load_frame(), props, S._mids())
    write(rows)
    print(f"보도 결손 표본 {len(rows)}구간 → {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
