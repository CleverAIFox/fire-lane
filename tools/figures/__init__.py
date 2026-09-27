#!/usr/bin/env python3
"""
tools/figures/ — 정본에서 그리는 그림들. **묶음 하나에 함수 하나씩.**

★ 2026-09-28 (DECISIONS §281-2). `render_figures.py` 한 파일이 741줄이 됐다.
  기획서 그림 24장 중 19장이 아직 저장소 밖 래스터이고(`docx_figs.SOURCELESS_MAX`)
  그것들이 들어올 자리가 여기다 — 다 옮기면 2천 줄이 된다. 한 번에 가른다.
  `src/firelane/read/` 와 같은 모양이고 같은 사유다.

    __init__.py    공용 — 색 · 이름 · 정본 읽기(`_golden` · `_params`)
    value.py       값 그림 — golden · params 의 수를 그린다
    xsec.py        도로폭 산출 — 규칙을 그린다
    structure.py   구조 그림 — 관계를 그린다

정본 목록은 `tools/render_figures.FIGURES` 하나다. 여기 함수를 더하면 거기에도
한 줄을 달아야 하고, 안 달면 `tools/docx_figs.py` 가 운다.

IN    data/golden/segments.fingerprint.json · src/firelane/seg/params.py
OUT   SVG 문자열
PARAM COLOR · LABEL
밖    **배치는 안 본다** — 넘침 · 겹침은 `tools/svg_fit.py` 가 `svg()` 안에서
      든다. **기획서에 넣지 않는다** — `tools/docx_figs.py --sync` 가 넣는다.
"""
from __future__ import annotations

import json
from pathlib import Path

# ★ `pyproject.toml` 의 `pythonpath = ["tools", "src"]` 가 `tools/` 를 잡는다 —
#   경로 조작 없이 붙는다.
from svg_fit import FONT, H, W, text_extent  # noqa: F401  카나리아가 든다

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/figures"
LOCK = OUT / ".lock.json"

COLOR = {"clear": "#16a34a", "needs_cv": "#ea580c",
         "blocked": "#dc2626", "unknown": "#94a3b8"}
LABEL = {"clear": "통행 가능", "needs_cv": "판정 보류",
         "blocked": "통행 불가", "unknown": "영상판정 불가"}


def _golden() -> dict:
    p = ROOT / "data/golden/segments.fingerprint.json"
    return json.loads(p.read_text(encoding="utf-8"))["L1"]


def _params() -> dict:
    """`params.py` 를 임포트하지 않고 읽는다 — 도구가 파이프라인에 안 붙는다."""
    src = (ROOT / "src/firelane/seg/params.py").read_text(encoding="utf-8")
    out = {}
    for line in src.splitlines():
        for key in ("TRUCK", "PARK", "CCTV_RANGE", "XSEC_EXCL", "WMAX_CAP", "SNAP_TOL"):
            if line.startswith(key):
                try:
                    out[key] = float(line.split("=")[1].split("#")[0].strip())
                except ValueError:
                    pass
    return out


