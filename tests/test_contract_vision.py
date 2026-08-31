#!/usr/bin/env python3
"""
test_contract_vision.py — 영상판정 계약이 MASTER §19 와 어긋나지 않는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-27. CV 파트 2인이 붙으면서 `src/contracts/` 를 신설했다.
**그 순간 §19 의 정본이 둘이 됐다** — 산문(MASTER)과 코드(contracts).

없앨 수 없는 중복이라면 최소한 어긋남은 잡는다(R15~R18).
GIS ↔ UI 경계에서 `test_contract.py` 가 하는 일을 GIS ↔ CV 경계에서 한다.

★ 이 검사가 있어야 CV 파트가 GIS 코드를 한 줄도 안 보고 붙을 수 있다.
  그것이 계약 계층을 만든 이유 전부다.

IN    src/contracts/vision.py · docs/MASTER.md §19-1
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# ★ sys.path 를 조작하지 않는다(test_layering). `src` 레이아웃 패키지이므로
#   `uv sync` 가 editable 로 깔아준다. 경로를 손대면 다음 테스트도 따라 한다.
pytest.importorskip("pydantic")
from pydantic import ValidationError  # noqa: E402

from contracts import ObsSpec, VisionResult  # noqa: E402

MASTER = ROOT / "docs/MASTER.md"

# MASTER §19-1 의 예시 그대로. 이 값이 통과하지 못하면 문서가 거짓말이다.
CANON = {
    "obs_id": "OBS-001",
    "seg_uid": "DM-192942-283921-YM7N",
    "passable_width_m": 2.83,
    "passable_width_hard_m": 4.10,
    "at_offset_m": 17.4,
    "observed_at": "2026-08-20T14:03:00+09:00",
    "n_frames": 45,
    "confidence": 0.82,
    "masked": True,
    "calib_id": "gayeon-iphone13-video-1080p30-20260820",
    "h_id": "OBS-001-S03",
    "params_ver": "v2",
    "n_ref": 7,
    "h_rms_px": 1.83,
}


def test_master_example_validates():
    """문서에 적힌 예시가 코드를 통과하는가."""
    r = VisionResult(**CANON)
    assert r.passable_width_m == 2.83


def test_field_set_matches_master():
    """★ 필드 집합이 §19-1 코드블록과 **정확히** 같은가.

    부분집합 검사로는 안 된다. 코드에만 있는 필드는 문서에 없는 계약이고,
    문서에만 있는 필드는 CV 파트가 보내도 버려진다. R7 과 같은 이유다.
    """
    if not MASTER.exists():
        pytest.skip("MASTER.md 없음")
    txt = MASTER.read_text(encoding="utf-8")
    m = re.search(r"### 19-1\..*?```json\n(.*?)```", txt, re.S)
    assert m, "MASTER §19-1 의 json 코드블록을 못 찾았다"
    doc_fields = set(re.findall(r'^\s*"(\w+)":', m.group(1), re.M))
    code_fields = set(VisionResult.model_fields)
    only_doc = sorted(doc_fields - code_fields)
    only_code = sorted(code_fields - doc_fields)
    assert not (only_doc or only_code), (
        "영상판정 계약이 문서와 갈렸다.\n"
        f"  문서에만: {only_doc}\n"
        f"  코드에만: {only_code}\n"
        "  MASTER §19-1 과 src/contracts/vision.py 를 같이 고친다.")


def test_masked_is_carried_but_not_enforced():
    """마스킹 여부를 싣되 거부하지는 않는다.

    ★ 마스킹 시점은 법 요건이 아니라 정책이며 미결이다. 정책을 스키마에
      박으면 정책이 바뀔 때 코드가 막는다. 값은 실어 보내되 판단은
      상류에서 한다 — 미결 정본은 PLAN 이다.
    """
    assert "masked" in VisionResult.model_fields
    r = VisionResult(**{**CANON, "masked": False})
    assert r.masked is False


def test_hard_width_cannot_be_smaller():
    """차를 뺀 폭이 지금 폭보다 좁을 수 없다."""
    with pytest.raises(ValidationError):
        VisionResult(**{**CANON, "passable_width_hard_m": 1.0})


def test_naive_timestamp_is_rejected():
    """시간대 없는 시각을 받지 않는다 — 관측 신선도가 9시간 어긋난다."""
    with pytest.raises(ValidationError):
        VisionResult(**{**CANON, "observed_at": "2026-08-20T14:03:00"})


def test_seg_id_is_rejected():
    """★ seg_id 를 seg_uid 자리에 못 넣는다.

    파이프라인을 돌릴 때마다 seg_id 가 밀린다. 외부 참조에 쓰면 다음
    실행에 전부 깨지는데, 형식이 비슷해 눈으로는 안 보인다(§5-2).
    """
    for bad in ("DM00123", "1042", "DM-192942-283921"):
        with pytest.raises(ValidationError):
            VisionResult(**{**CANON, "seg_uid": bad})


def test_experimental_fields_are_allowed():
    """★ CV 가 실험 중인 필드를 붙여 보낼 수 있는가.

    forbid 로 두면 CV 가 필드 하나 늘릴 때마다 계약 PR 이 필요하고,
    그러면 파트가 계약을 우회하기 시작한다. 확정되면 등재하고
    `params_ver` 를 올린다.
    """
    r = VisionResult(**{**CANON, "mask_quality": 0.91})
    assert r.mask_quality == 0.91


def test_contract_carries_no_verdict_or_threshold():
    """★ 판정과 임계값이 계약에 새어들지 않았는가.

    비전이 넘기는 것은 **최소 통행폭 하나**다. 판정까지 넘어오면 임계값
    3.0m 가 두 군데에 박히고, 실측 후 한쪽만 바뀌면 화면과 데이터가
    어긋난다(§19 머리말). 임계값 정본은 seg/params.py 다(R3).
    """
    banned = {"verdict", "passable", "is_passable", "truck", "park"}
    hit = sorted(f for f in VisionResult.model_fields
                 if f.lower() in banned)
    assert not hit, (
        f"계약에 판정성 필드가 있다: {hit}\n"
        "  비전은 폭만 넘긴다. 판정은 GIS 가 한다.")

    src = (ROOT / "src/contracts/vision.py").read_text(encoding="utf-8")
    code = "\n".join(l.split("#", 1)[0] for l in src.splitlines())
    nums = re.findall(r"(?<![\w.])(3\.0|7\.0|2\.0|25\.0)(?![\w.])", code)
    assert not nums, (
        f"계약에 판정 임계값이 박혀 있다: {sorted(set(nums))}\n"
        "  정본은 src/firelane/seg/params.py 하나다(MASTER §18-5 R3).\n"
        "  실측 후 임계값이 바뀔 때 한쪽만 바뀐다.")


def test_obs_spec_does_not_leak_road_width():
    """★ GIS 가 도로폭을 주지 않는가(§19-2).

    GIS 폭을 먼저 알고 재면 그 값 근처로 수렴하고, 그러면 영상이 GIS 를
    검증하는 의미가 사라진다. GIS 폭 자체가 미검증이라 물려주면 틀린 값이
    재생산된다. 소방서 7구간에서 이미 겪은 병이다 —
    **게이트로 쓴 자료는 검증 수단이 아니다.**
    """
    leaked = sorted(f for f in ObsSpec.model_fields if "width" in f.lower())
    assert not leaked, (
        f"ObsSpec 이 폭을 넘긴다: {leaked}\n"
        "  방향(bearing_deg)은 폭이 아니므로 순환하지 않는다. 폭은 안 된다.")

