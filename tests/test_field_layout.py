"""`data/field` 에 **계산 산출물이 없다** — 층 정의대로 배치됐는가.  (Zm44 · DECISIONS §584)

IN    sources.yaml · tools/sensitivity.py · data/field
OUT   없음 (검사)
밖    **나머지 파일이 층에 맞는지는 안 본다**(`evalset` · `flip_top` · `sidewalk_probe` 는 사람이 채우는 표라 조건부이고, 봉인 키는 정의 밖이다 — §584).
      여기는 **「도구가 뽑은 계산 결과이고 사람 칸이 안 채워지는 표」가 실측 층에 없는가** 하나다.

★ `layers.field` 의 정의는 「실측 원자료 · 사람이 만드는 유일한 데이터 · 재생성 불가」이고 `layers.processed` 는 「파이프라인 정본 · 사람이 손으로 만들지 않는다」다.
  `flip_2610.csv` 는 `tools/sensitivity.py` 가 부트스트랩으로 계산한 1,169행이고 사람이 채우지 않는다 — 같은 도구의 `flip_detail.json` 은 이미 `processed` 에 있었다.
"""
from __future__ import annotations

from pathlib import Path

import sensitivity as S

from firelane import ledger

ROOT = Path(__file__).resolve().parents[1]


def test_flip_table_is_not_in_the_field_layer() -> None:
    assert not (ROOT / "data" / "field" / "flip_2610.csv").exists(), "계산 산출물이 실측 층에 있다 — data/processed 로 옮긴다"


def test_the_tool_writes_the_flip_table_next_to_its_json() -> None:
    assert S.FLIP_CSV.parent == S.FLIP_JSON.parent == ROOT / "data" / "processed", (S.FLIP_CSV, S.FLIP_JSON)


def test_the_ledger_places_the_flip_table_in_processed() -> None:
    out = ledger.load()["outputs"]
    assert out["flip_2610"]["path"] == "data/processed/flip_2610.csv", out["flip_2610"]["path"]
    assert Path(out["flip_2610"]["path"]).parent == Path(out["flip_detail"]["path"]).parent
