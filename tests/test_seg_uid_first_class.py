"""구간을 가리키는 산출물은 `seg_uid` 를 **함께** 싣는다.  (Zm27 · DECISIONS §572)

IN    data/field · data/processed · web/data 의 산출물(있는 것만) · 발행본
OUT   없음 (검사)
PARAM 없음
밖    seg_uid 값이 옳은가는 안 본다 — 같은 파일 안에서 `seg_id` 옆에 짝이 있는지, 그 짝이 발행본과 같은지만 본다.

★ 왜 — `seg_id` 는 구간 분할이 바뀌면 뒤가 밀리는 순번이다(`segments.py` 의 `DM{i:05d}`). 2026-09-16~17 에 실제로 96% 가
  다른 구간을 가리키게 됐다(`tools/segid_audit.py`). `seg_id` 만 든 표는 다음 재발행 뒤에 **조용히 다른 구간을 가리킨다.**
  평가셋이 그 꼴이었다(§571).
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from firelane.generated import for_role

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "web/data/segments.geojson"
DM = re.compile(r"\bDM\d{5}\b")
#: 번호를 안 싣는 산출물이 아니라 **seg_id 가 키가 아닌** 파일(번호 규칙을 설명하는 예시 · 판 이력 자체).
SKIP_JSON = ("segments.schema.json",)
#: 채점 전에 열지 않는 봉인 키는 **수집 단계에서 거른다**(skip 이 아니다). 키의 `uids` 는 `test_evalset.py` 가 새로 뽑은 키로 본다.
SEALED = (".key.json",)


def _pub() -> dict[str, str]:
    if not PUB.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    return {f["properties"]["seg_id"]: f["properties"]["seg_uid"] for f in json.loads(PUB.read_text(encoding="utf-8"))["features"]}


def _csvs() -> list[Path]:
    out = []
    for d in ("data/field", "data/processed"):
        out += [p for p in sorted((ROOT / d).glob("*.csv")) if ".stale" not in p.name]
    return out


def _header(p: Path) -> list[str]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return next(csv.reader(lines[:1]), [])


@pytest.mark.parametrize("path", _csvs(), ids=lambda p: p.name)
def test_every_csv_that_names_a_segment_also_carries_its_seg_uid(path: Path) -> None:
    h = _header(path)
    if "seg_id" in h:
        assert "seg_uid" in h, f"{path.relative_to(ROOT)} 가 seg_id 만 싣는다 — seg_uid 를 옆에 둔다"


def test_the_seg_uid_beside_each_seg_id_is_the_published_one() -> None:
    pub = _pub()
    bad = []
    for p in _csvs():
        h = _header(p)
        if "seg_id" not in h or "seg_uid" not in h:
            continue
        with p.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(ln for ln in f if not ln.startswith("#")):
                if r["seg_id"] in pub and r["seg_uid"] and pub[r["seg_id"]] != r["seg_uid"]:
                    bad.append((p.name, r["seg_id"]))
    assert not bad, f"seg_id 가 발행본과 다른 구간을 가리킨다(번호가 밀렸다): {bad[:5]}"


def _jsons() -> list[Path]:
    out = []
    # ★ Zm36. 생성물 루트는 등록부가 든다(`test_generated_registry`) — 여기서 다시 적지 않는다. `data/field` 는 생성물이 아니라 사람의 표 자리라 따로 더한다.
    for d in ("data/field", *for_role("fresh")):
        out += [p for p in sorted((ROOT / d).glob("*.json")) if p.name not in SKIP_JSON and ".stale" not in p.name and not p.name.endswith(SEALED)]
    return out


@pytest.mark.parametrize("path", _jsons(), ids=lambda p: p.name)
def test_every_json_that_names_a_segment_by_number_also_carries_its_seg_uid(path: Path) -> None:
    pub = _pub()
    text = path.read_text(encoding="utf-8")
    missing = sorted({t for t in DM.findall(text) if t in pub and pub[t] not in text})
    assert not missing, f"{path.relative_to(ROOT)}: seg_id {len(missing)}개의 seg_uid 가 같은 파일에 없다 — {missing[:5]}"
