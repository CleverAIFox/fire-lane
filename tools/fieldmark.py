#!/usr/bin/env python3
"""
fieldmark.py — **현장 표지(PLAN #260)를 판정 뒤에 얹는 후처리** — 표지된 비도로 구간을 판정 집합에서 빼고(A안), 구간별 열 둘과 한계 절 한 줄을 낸다.

    uv run python tools/fieldmark.py              # 한계 절 한 줄 · 판정 집합의 전후 · 낡은 표지
    uv run python tools/fieldmark.py --selftest

IN    발행본 `web/data/segments.geojson`(읽기만) · `data/field/nonroad_marks.csv`(읽기만) · `data/field/roadview_hypo_2611.csv`(읽기만 · 본 구간의 출처)
OUT   ① 구간별 열 둘 — `nonroad_mark`(비도로 종류 · 없으면 null) · `field_seen`(본 구간이면 true · 아니면 null)
      ② 판정 집합의 전후(A안: 비도로 표지 구간을 뺀다 · blocked 로 보내지 않는다)
      ③ 한계 절 한 줄 — 영역(최소폭 3m 미만 · unknown 또는 needs_cv) 중 표지 · 본 · 안 본 · 층별 본 몫 · 낡은 표지
PARAM `REGION_WIDTH_M`(3.0) · `REGION_VERDICTS` · `NONROAD_KINDS`(닫힌 집합 — 막다른마당은 길이 맞아 비도로가 아니다)
밖    **판정 폐포(`firelane.segments` import 닫힘)를 안 읽고 안 쓴다** — `verdict` 칸을 고치지 않는다. 빼는 일은 이 도구가 센 집합에서만 일어난다.
      **판정 규칙 [0]–[11]을 안 건드린다.** 안 본 구간의 같은 자리는 안 빠진다 — 이 판정은 「본 곳만 정확한」 판정이다(PLAN #260 이 적은 그 위험이 그대로다).
      표지 파일을 안 고친다(`fieldseal` 지문 · 사람 몫).
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)

★ 값 표현 — **둘 다 비어 있으면 「안 봤다」다. 「아님」이 아니다.** `nonroad_mark` 는 비도로 종류 또는 null 이고 「아님」을 뜻하는 값(`False` · 「없음」)을 두지 않는다.
  `field_seen` 은 true 또는 null 이고 `false` 를 두지 않는다. 읽는 법은 셋뿐이다 — 종류가 있다(비도로 표지) · 본 구간이고 종류가 없다(봤고 비도로 표지가 없다) ·
  둘 다 null(안 봤다). 마지막을 비도로가 아니라고 읽지 않는다(표지는 사람이 **본** 구간에만 붙는다).
★ 본 구간 = 판독표에서 사람이 한 칸이라도 채운 행 · 사람이 짚은 사례(`RV_NAMED`) · 표지된 구간. 판독표를 뽑기만 하고 안 채운 행은 안 본 구간이다.
★ 낡은 표지 = 표지의 `seg_uid` 가 발행본에 없는 것. 조용히 버리지 않고 수로 드러낸다(재발행에서 열쇠가 밀린 것이다). 같은 `seg_uid` 가 두 번 들면 결함이다.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from rvsheet import RV_FILE, RV_HUMAN, RV_NAMED

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "web" / "data" / "segments.geojson"
MARKS = ROOT / "data" / "field" / "nonroad_marks.csv"
RVSHEET = ROOT / "data" / "field" / RV_FILE
VERDICTS = ("clear", "needs_cv", "blocked", "unknown")
REGION_VERDICTS = ("unknown", "needs_cv")
REGION_WIDTH_M = 3.0
NONROAD_KINDS = ("지붕통로", "계단", "비포장진입", "적치로덮임")      # 닫힌 집합의 비도로 넷
DEAD_END = "막다른마당"                                               # 길은 맞다 — 비도로 합계에 안 든다
KINDS = (*NONROAD_KINDS, DEAD_END)


def read_rows(path: Path) -> list[dict]:
    """`#` 로 시작하는 줄을 건너뛰고 읽는다(utf-8-sig · BOM 은 읽기에서만 걷는다)."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(ln for ln in f if not ln.startswith("#")))


def seen_uids(rv_rows: list[dict], marks: list[dict]) -> set[str]:
    """본 구간의 `seg_uid` — 채운 판독표 행 · 사람이 짚은 사례 · 표지된 구간."""
    out = {r["seg_uid"] for r in rv_rows if any((r.get(c) or "").strip() for c in RV_HUMAN)}
    return out | set(RV_NAMED) | {m["seg_uid"] for m in marks}


def mark_faults(marks: list[dict]) -> list[str]:
    """표지 파일의 결함 — 같은 열쇠가 두 번 · 닫힌 집합 밖의 종류."""
    bad, seen = [], set()
    for i, m in enumerate(marks, 1):
        if m["seg_uid"] in seen:
            bad.append(f"{i}행: 같은 seg_uid 가 두 번 들었다")
        seen.add(m["seg_uid"])
        if m["종류"] not in KINDS:
            bad.append(f"{i}행: 종류 「{m['종류']}」 가 닫힌 집합 {' · '.join(KINDS)} 밖이다")
    return bad


def stale_marks(marks: list[dict], uids: set[str]) -> list[dict]:
    """발행본에 열쇠가 없는 표지(낡은 표지). 버리지 않고 돌려준다."""
    return [m for m in marks if m["seg_uid"] not in uids]


def columns(uids: list[str], marks: list[dict], seen: set[str]) -> dict[str, list]:
    """구간별 열 둘(`uids` 와 같은 순서). 막다른마당은 `nonroad_mark` 가 null 이고 `field_seen` 이 true 다(봤고 비도로가 아니다)."""
    kind = {m["seg_uid"]: m["종류"] for m in marks if m["종류"] in NONROAD_KINDS}
    return {"nonroad_mark": [kind.get(u) for u in uids], "field_seen": [True if u in seen else None for u in uids]}


def judged(props: list[dict], col: dict[str, list]) -> list[dict]:
    """A안 — 비도로 표지 구간을 뺀 판정 집합. `verdict` 는 안 고친다(blocked 로 안 보낸다)."""
    return [p for p, k in zip(props, col["nonroad_mark"], strict=True) if k is None]


def tally(props: list[dict]) -> dict[str, int]:
    out = {"n": len(props), **{v: 0 for v in VERDICTS}}
    for p in props:
        out[p["verdict"]] = out.get(p["verdict"], 0) + 1
    return out


def region(props: list[dict]) -> list[int]:
    """영역 — 우리 최소폭이 3m 미만이면서 `unknown` · `needs_cv` 인 구간의 위치."""
    return [i for i, p in enumerate(props) if p["width_min_m"] is not None and p["width_min_m"] < REGION_WIDTH_M and p["verdict"] in REGION_VERDICTS]


def region_stat(props: list[dict], col: dict[str, list], n_stale: int) -> dict:
    idx = region(props)
    seen = [i for i in idx if col["field_seen"][i]]
    marked = [i for i in idx if col["nonroad_mark"][i]]
    layers = {v: (sum(props[i]["verdict"] == v for i in seen), sum(props[i]["verdict"] == v for i in idx)) for v in REGION_VERDICTS}
    return {"영역": len(idx), "표지": len(marked), "본": len(seen), "안 본": len(idx) - len(seen), "층": layers, "낡은 표지": n_stale}


def region_line(s: dict) -> str:
    """한계 절 한 줄 — 「영역 304 중 표지 4(1.3%) · 본 17(5.6%) · 안 본 287 · 층별 본 몫 …」. 표지는 본 몫 안의 것이다."""
    pct = lambda a: f"{100 * a / s['영역']:.1f}%" if s["영역"] else "–"          # noqa: E731
    layers = " · ".join(f"{v} {a}/{b}" for v, (a, b) in s["층"].items())
    return (f"영역(최소폭 {REGION_WIDTH_M:g}m 미만 · {' 또는 '.join(REGION_VERDICTS)}) {s['영역']} 중 표지 {s['표지']}({pct(s['표지'])}) · 본 {s['본']}({pct(s['본'])}) · "
            f"안 본 {s['안 본']} · 층별 본 몫 {layers} · 낡은 표지 {s['낡은 표지']} — 표지는 본 구간에만 붙는다(안 봤다는 비도로가 아니라는 말이 아니다)")


def run(seg: Path = SEG, marks_path: Path = MARKS, rv_path: Path = RVSHEET) -> dict:
    props = [f["properties"] for f in json.loads(seg.read_text(encoding="utf-8"))["features"]]
    marks, rv = read_rows(marks_path), read_rows(rv_path)
    uids = [p["seg_uid"] for p in props]
    stale = stale_marks(marks, set(uids))
    col = columns(uids, marks, seen_uids(rv, marks))
    kept = judged(props, col)
    return {"faults": mark_faults(marks), "stale": stale, "before": tally(props), "after": tally(kept), "region": region_stat(props, col, len(stale)), "col": col}


def line(t: dict[str, int]) -> str:
    return f"구간 {t['n']} · " + " · ".join(f"{k} {t[k]}" for k in VERDICTS)


def selftest() -> int:
    props = [{"seg_uid": u, "verdict": v, "width_min_m": w} for u, v, w in (("a", "unknown", 1.0), ("b", "needs_cv", 2.0), ("c", "clear", 8.0), ("d", "unknown", 2.5), ("e", "blocked", 1.0))]
    marks = [{"seg_uid": "a", "종류": "계단"}, {"seg_uid": "d", "종류": DEAD_END}, {"seg_uid": "zz", "종류": "계단"}]
    seen = seen_uids([{"seg_uid": "b", "거리뷰": "있다"}, {"seg_uid": "c"}], marks)
    col = columns([p["seg_uid"] for p in props], marks, seen)
    st = region_stat(props, col, len(stale_marks(marks, {p["seg_uid"] for p in props})))
    ok = (col["nonroad_mark"] == ["계단", None, None, None, None] and col["field_seen"][:5] == [True, True, None, True, None]
          and tally(judged(props, col))["unknown"] == 1 and tally(props)["unknown"] == 2 and tally(judged(props, col))["blocked"] == 1
          and st["영역"] == 3 and st["표지"] == 1 and st["본"] == 3 and st["안 본"] == 0 and st["낡은 표지"] == 1)
    print("selftest", "통과" if ok else "실패")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if "--selftest" in a:
        return selftest()
    r = run()
    for x in r["faults"]:
        print(f"✗ {x}")
    print(f"판정 집합 전 {line(r['before'])}\n판정 집합 후 {line(r['after'])}   (A안 — 비도로 표지 {r['before']['n'] - r['after']['n']}구간을 뺐다 · blocked 로 안 보냈다)")
    print(region_line(r["region"]))
    return 1 if r["faults"] else 0


if __name__ == "__main__":
    sys.exit(main())
