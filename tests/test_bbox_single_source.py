#!/usr/bin/env python3
"""
test_bbox_single_source.py — 추출 범위(BBOX)가 **한 곳에만** 사는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-16. `sources.yaml` 의 `bbox_4326` 과 `ingest.py` 의 `BBOX_4326` 튜플이 두 벌이었다.
샤드 봉인지 cfg 칸은 대장 값을 재는데 실제 거르기는 튜플이 했다. 대장만 고치면 40샤드가
찢어져 다시 빌드하고도 산출은 그대로다. 웅토피아가 지산안전센터 300m 원이 잘리는 것을 찾아
동쪽을 넓힐 때 같은 자리를 고쳤다(웅토피아 DECISIONS §125 · 이 저장소 DECISIONS §169).

★ 둘을 본다 — ① ingest 가 대장 값을 쓰는가 ② 코드에 BBOX 꼴 숫자 튜플이 새로 박히지 않는가.
  ①만 보면 다른 모듈이 사본을 다시 만들어도 초록이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

from firelane import ingest

ROOT = Path(__file__).resolve().parents[1]
# 추출 범위가 아닌 **판별용** 넓은 상자. 좌표계 추정(probe)이 쓴다. 사유 없이 늘리지 않는다.
ALLOWED = {
    "src/firelane/krgis/crs.py": "GWANGJU_BBOX · KOREA_BBOX — 좌표계 판별용 광역 상자. 추출 범위가 아니다",
}


def _ledger_bbox() -> tuple:
    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    return tuple(y["bbox_4326"])


def test_ingest_reads_the_ledger_bbox():
    assert ingest.BBOX_4326 == _ledger_bbox(), (
        f"ingest.BBOX_4326 {ingest.BBOX_4326} ≠ sources.yaml bbox_4326 {_ledger_bbox()}\n"
        "  대장이 정본이다. 샤드 봉인지 cfg 칸이 대장 값을 잰다 — 둘이 갈리면 근거와 실물이 갈린다.")


def _bbox_like(node: ast.AST) -> bool:
    if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 4:
        return False
    vals = [e.value for e in node.elts if isinstance(e, ast.Constant)
            and isinstance(e.value, (int, float)) and not isinstance(e.value, bool)]
    if len(vals) != 4:
        return False
    x0, y0, x1, y1 = vals
    return 124 <= x0 < x1 <= 132 and 33 <= y0 < y1 <= 39


def test_no_bbox_literal_copies_in_code():
    bad = []
    for base in ("src", "tools"):
        for p in sorted((ROOT / base).rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            if rel in ALLOWED:
                continue
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if _bbox_like(node):
                    bad.append(f"  {rel}:{node.lineno}")
    assert not bad, (
        "경위도 상자 꼴 숫자 튜플이 코드에 박혀 있다 —\n" + "\n".join(bad)
        + "\n\n  추출 범위면 `sources.yaml` 의 `bbox_4326` 을 읽어라.\n"
          "  판별용 광역 상자면 ALLOWED 에 사유와 함께 적어라.")


def test_allowed_entries_are_real():
    ghost = [k for k in ALLOWED if not (ROOT / k).is_file()]
    assert not ghost, f"ALLOWED 가 없는 파일을 든다 — {ghost}"


def test_detector_bites():
    """카나리아 — 옛 튜플을 넣으면 잡는가. 탐지식이 무르면 위 검사가 죽는다."""
    tree = ast.parse("BBOX_4326 = (126.907, 35.140, 126.940, 35.162)")
    assert any(_bbox_like(n) for n in ast.walk(tree))
    assert not any(_bbox_like(n) for n in ast.walk(ast.parse("RGB = (12, 34, 56, 78)")))
