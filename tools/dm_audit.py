#!/usr/bin/env python3
"""
tools/dm_audit.py — 문서에 적힌 `DM` 번호가 **지금 공개본에서** 같은 구간을 가리키는가를 센다.  (Zm27 · DECISIONS §572)

    uv run python tools/dm_audit.py            표 → data/processed/dm_refs.csv · 요약 → data/processed/dm_refs.json

IN    docs/DECISIONS.md · docs/MASTER.md · docs/PLAN.md · 현재 공개본 · data/baseline/*/seg_uid_map.csv(옛 번호판 여덟)
OUT   data/processed/dm_refs.csv (번호가 나온 곳마다 한 행) · data/processed/dm_refs.json
PARAM 없다
밖    **문서를 고치지 않는다.** 표만 낸다. 고칠지는 사람이 본다.
      **맥락 대조는 휴리스틱이다.** 번호 뒤 70자 안(다음 `DM` 번호 앞까지, 없으면 앞 25자)에서 **공개본·옛 번호판에 실재하는 도로명**과 `길이 X m` 만 읽는다.
      약칭(「제봉로」 ← 「제봉로200번길」)은 어긋남이 아니라 `약칭` 으로 가른다. 번호 뒤에 도로명이 없으면 대조하지 못한다고 적는다.
      어긋남은 **후보**다 — 문서가 그때의 번호판을 인용했을 수 있다. 그래서 어긋난 행마다 옛 번호판 여덟 중 맥락이 맞는 판을 같이 적는다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "web" / "data" / "segments.geojson"
DOCS = ("docs/DECISIONS.md", "docs/MASTER.md", "docs/PLAN.md")
OUT_CSV = ROOT / "data" / "processed" / "dm_refs.csv"
OUT_JSON = ROOT / "data" / "processed" / "dm_refs.json"

DM = re.compile(r"\bDM\d{5}\b")
HEAD = re.compile(r"^#{2,4}\s+(\d+(?:-\d+)?)\.")
LEN = re.compile(r"길이\s*(\d+(?:\.\d+)?)\s*m")
WINDOW = 70
BEFORE = 25            # 「제봉로 DM00115」 꼴 — 도로명이 번호 앞에 올 때
LEN_TOL = 0.1          # 공개본 length_m 은 소수 1자리다


def road_regex(names: set[str]) -> re.Pattern[str]:
    """공개본과 옛 번호판에 **실재하는 도로명**만 찾는다 — 「이로」 「으로」 같은 낱말을 도로명으로 읽지 않는다. 긴 이름 먼저."""
    return re.compile("|".join(re.escape(n) for n in sorted((n for n in names if len(n) >= 3), key=len, reverse=True)))


def road_status(mentions: list[str], now: str) -> str:
    if not mentions:
        return "맥락 없음"
    if now in mentions:
        return "일치"
    if any(now.startswith(m) for m in mentions):
        return "약칭"
    return "어긋남"


def len_status(vals: list[float], now: float) -> str:
    if not vals:
        return "맥락 없음"
    return "일치" if any(abs(v - now) <= LEN_TOL for v in vals) else "어긋남"


def refs(path: Path, current: dict[str, dict], old: dict[str, dict[str, dict]], road_re: re.Pattern[str]) -> list[dict]:
    out = []
    sec = ""
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if m := HEAD.match(line):
            sec = "§" + m.group(1)
        for t in DM.finditer(line):
            sid = t.group()
            nxt = DM.search(line, t.end())
            win = line[t.end(): min(t.end() + WINDOW, nxt.start() if nxt else len(line))]
            prv = [x for x in DM.finditer(line, 0, t.start())]
            lo = max(prv[-1].end() if prv else 0, t.start() - BEFORE)
            mentions = road_re.findall(win) or road_re.findall(line[lo:t.start()])      # 뒤 70자에 없으면 앞 25자

            lens = [float(x) for x in LEN.findall(win)]
            p = current.get(sid)
            row = {"문서": path.name, "줄": n, "절": sec, "seg_id": sid, "맥락": line[max(0, t.start() - 20): t.end() + WINDOW].strip()}
            if p is None:
                row |= {"seg_uid": "", "도로명(지금)": "", "length_m(지금)": "", "도로명 대조": "번호 없음", "길이 대조": "번호 없음"}
            else:
                row |= {"seg_uid": p["seg_uid"], "도로명(지금)": p["road_name"] or "", "length_m(지금)": p["length_m"],
                        "도로명 대조": road_status(mentions, p["road_name"] or ""), "길이 대조": len_status(lens, p["length_m"])}
            bad = row["도로명 대조"] in ("어긋남", "번호 없음") or row["길이 대조"] in ("어긋남", "번호 없음")
            row["어긋남"] = "Y" if bad else ""
            hit = []
            if bad:
                for name, m in old.items():
                    q = m.get(sid)
                    if q and (not mentions or road_status(mentions, q["road_name"]) in ("일치", "약칭")) \
                            and (not lens or len_status(lens, q["length_m"]) == "일치") and (mentions or lens):
                        hit.append(name)
            row["맥락이 맞는 옛 번호판"] = " ".join(hit)
            out.append(row)
    return out


def load_current() -> dict[str, dict]:
    return {f["properties"]["seg_id"]: f["properties"] for f in json.loads(PUB.read_text(encoding="utf-8"))["features"]}


def load_old() -> dict[str, dict[str, dict]]:
    out = {}
    for p in sorted((ROOT / "data" / "baseline").glob("*/seg_uid_map.csv")):
        with p.open(encoding="utf-8", newline="") as f:
            out[p.parent.name] = {r["seg_id"]: {"seg_uid": r["seg_uid"], "road_name": r["road_name"], "length_m": float(r["length_m"])}
                                  for r in csv.DictReader(f)}
    return out


def main() -> int:
    cur, old = load_current(), load_old()
    names = {p["road_name"] for p in cur.values() if p["road_name"]} | {q["road_name"] for m in old.values() for q in m.values() if q["road_name"]}
    road_re = road_regex(names)
    rows = [r for d in DOCS for r in refs(ROOT / d, cur, old, road_re)]
    cols = ["문서", "줄", "절", "seg_id", "seg_uid", "도로명(지금)", "length_m(지금)", "도로명 대조", "길이 대조", "어긋남", "맥락이 맞는 옛 번호판", "맥락"]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    bad = [r for r in rows if r["어긋남"]]
    tally = {k: sum(1 for r in rows if r["도로명 대조"] == k) for k in ("일치", "약칭", "어긋남", "맥락 없음", "번호 없음")}
    ltally = {k: sum(1 for r in rows if r["길이 대조"] == k) for k in ("일치", "어긋남", "맥락 없음", "번호 없음")}
    summ = {"번호가 나온 곳": len(rows), "서로 다른 번호": len({r["seg_id"] for r in rows}),
            "문서별": {d.split("/")[-1]: sum(1 for r in rows if r["문서"] == d.split("/")[-1]) for d in DOCS},
            "도로명 대조": tally, "길이 대조": ltally, "어긋남 행": len(bad),
            "어긋남 중 옛 번호판에서는 맥락이 맞는 것": sum(1 for r in bad if r["맥락이 맞는 옛 번호판"]),
            "어긋남 목록": [{k: r[k] for k in ("문서", "줄", "절", "seg_id", "seg_uid", "도로명(지금)", "length_m(지금)", "도로명 대조", "길이 대조", "맥락이 맞는 옛 번호판", "맥락")} for r in bad]}
    OUT_JSON.write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: v for k, v in summ.items() if k != "어긋남 목록"})
    for r in bad:
        print(f"  {r['문서']}:{r['줄']} {r['절']} {r['seg_id']} 지금 {r['도로명(지금)']} {r['length_m(지금)']}m · 도로명 {r['도로명 대조']} · 길이 {r['길이 대조']}"
              f" · 옛 판 {r['맥락이 맞는 옛 번호판'] or '—'}\n      {r['맥락']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
