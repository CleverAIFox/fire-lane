"""
fireaccess.py — 소방서가 지정한 **소방통로확보대상**(`fire_access`)을 구간 칸으로 싣는다. (Zm8 · DECISIONS §550)

IN    `data/processed/fire_access.csv`(동부소방서 · 20구간 · 7,120m · 3,452세대) · 구간 표(`road_name` · `length_m`)
OUT   `nfa_access_listed` · `nfa_access_width` · `nfa_access_len_m` · `nfa_access_hh` · `nfa_access_len_ratio` · `nfa_access_loose` · `nfa_access_token`
PARAM `RATIO_LO` · `RATIO_HI`
밖    **판정을 안 한다.** 관문(`tests/test_fire_access_gate.py`)이 읽을 뿐이다 — 판정 폐포(`segments.py`) 밖이라 골든 코드 지문을 안 건드린다.
      **폭 숫자를 직접 비교하지 않는다** — 소방서 폭은 구간 **대표값**이고 우리 `wmin` 은 지점 **최솟값**이다. 다른 물리량이다.
      「소방서보다 넓으면 과대판정」 같은 규칙은 근거가 없어 만들지 않는다.

── 매칭 — **정확 일치**다 (부분 문자열이 아니다) ────────────────────────
좌표가 없다. 지역명(자유 문장)에서 **우리 `road_name` 이 통째로 한 도로명으로 나타날 때만** matched 다. 부분 문자열로 맞추면 `경양로`(대로 · 13~26m)가 `경양로 247번길 26` 같은 골목 행에 걸린다 —
처음 안이 그렇게 맞췄다가 경양로 22구간이 오탐으로 걸렸다(DECISIONS §550-2).
  · `NNN번길` 이 도로명에 **붙는다**: `경양로 247번길 26` 은 `경양로247번길` 이다(띄어 써도 같다). 그래서 본선 `경양로` 는 이 행에 **안 걸린다.**
  · 앞이 한글·숫자가 아니고 뒤가 `NN번길` · 한글이 아니면 통째다 — `경양로 333외` 는 본선 `경양로` 다.
  · ★ 소방서가 본선을 지정했는지 번길을 지정했는지는 **지역명 전체를 읽어야 안다** — 그래서 `nfa_access_token` 에 **원문**을 남긴다(사람이 판단한다).
여러 행이 걸리면 **구간거리가 가장 큰 행**을 쓴다. `nfa_access_width` 는 소방서가 적은 문자열 그대로다(`2.7~3.2` 같은 범위가 있다).

── `nfa_access_len_ratio` — 매칭 품질을 이것이 든다 ─────────────────────
`우리 그 도로명의 연장 합 ÷ 소방서 구간거리`. 소방서는 도로의 **일부 구간만** 지정한다 — 동계로9번길은 우리 235m · 소방서 220m(1.1배, 깨끗)지만 대부분은 4~37배다(간선의 좁은 일부).
`RATIO_LO`(0.5)~`RATIO_HI`(2.0) 밖이면 `nfa_access_loose = True` — **매칭이 느슨하다**(비교가 안 된다). 이 두 수는 4개의 깨끗한 사례를 보고 사람이 정했다(측정으로 도출한 값이 아니다).

★ `nfa_access_token` — 매칭된 행의 **지역명 원문**이다(문자열). 본선인지 번길인지 사람이 읽고 판단하게 한다.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

RATIO_LO, RATIO_HI = 0.5, 2.0
NAMES = ("nfa_access_listed", "nfa_access_width", "nfa_access_len_m", "nfa_access_hh",
         "nfa_access_len_ratio", "nfa_access_loose", "nfa_access_token")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def load(path: Path) -> list[dict]:
    """소방서 표 → 행 목록(`text` 원문 · `norm` 공백 제거 · `len` · `width` 문자열 · `hh`)."""
    rows = []
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(dict(text=r["지역명"], norm=_norm(r["지역명"]), len=float(r["구간거리(m)"]),
                             width=r["폭(m)"], hh=int(r["세대수"])))
    return rows


def _token_pattern(name: str):
    """이름의 글자↔숫자 경계에 공백을 허용한다(`제봉로 184번길` 도 `제봉로184번길` 이다). 앞은 한글·숫자가 아니고 뒤는 `NN번길` 이 아니어야 통째다."""
    parts = re.findall(r"\d+|[^\d]+", name)
    body = r"\s*".join(re.escape(p) for p in parts)
    return re.compile(rf"(?<![가-힣\d]){body}(?!\s*\d+번길)(?![가-힣])")


def match(road_name: str | None, rows: list[dict]):
    """정확 일치한 행. 못 찾으면 None. 여럿이면 구간거리가 가장 큰 행."""
    if not road_name:
        return None
    pat = _token_pattern(road_name)
    hit = [r for r in rows if pat.search(r["text"])]
    return max(hit, key=lambda r: r["len"]) if hit else None


def columns(road_names, lengths, rows: list[dict]) -> dict[str, list]:
    """구간마다의 `nfa_access_*` 일곱 칸(같은 순서의 목록). 판정에 안 쓴다."""
    total: dict[str, float] = defaultdict(float)
    for rn, ln in zip(road_names, lengths, strict=True):
        if rn:
            total[rn] += float(ln or 0.0)
    out: dict[str, list] = {k: [] for k in NAMES}
    for rn in road_names:
        row = match(rn, rows)
        if row is None:
            for k, v in zip(NAMES, (False, None, None, None, None, None, None), strict=True):
                out[k].append(v)
            continue
        ratio = round(total[rn] / row["len"], 2)
        for k, v in zip(NAMES, (True, row["width"], row["len"], row["hh"], ratio,
                                not (RATIO_LO <= ratio <= RATIO_HI), row["text"]), strict=True):
            out[k].append(v)
    return out
