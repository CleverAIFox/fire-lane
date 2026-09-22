#!/usr/bin/env python3
"""
test_fieldsheet.py — 실측 대조 도구가 **위험 오판**을 세고, 봉인 트랙을 보정에 안 쓰는가.
(DECISIONS §215-4)

야장이 아직 비어 있어서 실물로는 못 돌린다. 실제 관측점 파일의 머리와 행을 그대로 쓰고
실측 칸만 채워 돌린다 — 도구가 야장 서식을 그대로 먹는지까지 본다.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/field_compare.py"
OBS = ROOT / "data" / "field" / "obs_points.csv"


def _run(p: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), "--obs", str(p), *a],
                          capture_output=True, text=True, cwd=ROOT)


def _fill(tmp: Path, fill) -> Path:
    rows = list(csv.DictReader(OBS.open(encoding="utf-8")))
    for r in rows:
        r["measured_m"], r["kind"] = fill(r)
    out = tmp / "obs.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return out


def test_empty_fieldsheet_is_not_an_error():
    r = _run(OBS)
    assert r.returncode == 0, r.stdout + r.stderr


def test_danger_is_counted_and_sealed_track_not_used_for_correction(tmp_path):
    clear_a = next(r for r in csv.DictReader(OBS.open(encoding="utf-8"))
                   if r["verdict"] == "clear" and r["track"] == "A" and r["width_min_m"])
    clear_c = next((r for r in csv.DictReader(OBS.open(encoding="utf-8"))
                    if r["verdict"] == "clear" and r["track"] == "C" and r["width_min_m"]), None)

    def fill(r):
        if r["seg_uid"] == clear_a["seg_uid"]:
            return "2.5", "passable"                     # 우리 초록인데 실측 2.5m
        if clear_c and r["seg_uid"] == clear_c["seg_uid"]:
            return "1.0", "passable"                     # 봉인 트랙 — 더 크게 틀려도 보정에 안 쓴다
        return (r["width_min_m"] or "5"), "curb"

    p = _fill(tmp_path, fill)
    r = _run(p, "--json")
    s = json.loads(r.stdout)
    assert s["tracks"]["A"]["danger"] == 1, s["tracks"]
    want = round(float(clear_a["width_min_m"]) - 2.5, 2)
    assert s["suggest_shrink_m"] == want, f"보정 제안 {s['suggest_shrink_m']} ≠ {want} — 봉인 트랙이 섞였나"
    assert s["by_kind"]["curb"]["mae_m"] == 0.0, "우리 값 그대로 적은 점의 오차가 0 이 아니다"
    assert _run(p).returncode == 1, "A·B 에 위험 오판이 있는데 종료코드가 0 이다"


def test_kinds_are_not_mixed(tmp_path):
    p = _fill(tmp_path, lambda r: ("4.0", "wall" if r["seq"] == "1" else "passable"))
    s = json.loads(_run(p, "--json").stdout)
    assert set(s["by_kind"]) == {"wall", "passable"}, s["by_kind"]
