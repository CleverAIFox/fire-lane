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


#: 실측 층에 있으면 안 되는 **계산 산출물**(사람이 안 채운다). 이름 → 가야 할 층.
DERIVED_NOT_FIELD = {"flip_2610.csv": "data/processed"}


def derived_in(field: Path) -> list[str]:
    """`field` 안에 있는 계산 산출물의 이름들. 비면 층이 맞다."""
    return sorted(n for n in DERIVED_NOT_FIELD if (field / n).exists())


def test_flip_table_is_not_in_the_field_layer(tmp_path: Path) -> None:
    assert not derived_in(ROOT / "data" / "field"), "계산 산출물이 실측 층에 있다 — data/processed 로 옮긴다"
    # ★ 카나리아 — 같은 판별식을 **합성 결함으로 반대쪽에서도** 민다. 늘 비어 있다고 답하는 판별식이면 위가 늘 통과한다.
    (tmp_path / "flip_2610.csv").write_text("x\n", encoding="utf-8")
    assert derived_in(tmp_path) == ["flip_2610.csv"], "실측 층에 든 계산 산출물을 못 잡는다"


def test_the_tool_writes_the_flip_table_next_to_its_json() -> None:
    assert S.FLIP_CSV.parent == S.FLIP_JSON.parent == ROOT / "data" / "processed", (S.FLIP_CSV, S.FLIP_JSON)


def test_the_ledger_places_the_flip_table_in_processed() -> None:
    out = ledger.load()["outputs"]
    assert out["flip_2610"]["path"] == "data/processed/flip_2610.csv", out["flip_2610"]["path"]
    assert Path(out["flip_2610"]["path"]).parent == Path(out["flip_detail"]["path"]).parent
