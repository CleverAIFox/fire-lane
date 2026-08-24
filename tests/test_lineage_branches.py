#!/usr/bin/env python3
"""
test_lineage_branches.py — `lineage.verify()` 의 ①②③ 가지를 전부 태운다.

── 왜 생겼나 ───────────────────────────────────────────────────
계보 교착이 **다섯 번** 났다. 전부 같은 함수의 같은 자리다.

    2026-08-22  _manifest.json 을 바이트 전체로 비교했다
    2026-08-22  mutates 를 자가대조했다 (③)
    2026-08-22  ② 통과가 ③ 을 면제하지 않았다              222초 손실
    2026-08-24  raw 30→32 로 ingest 가 자기를 상류로 가리켰다  350초 손실
    2026-08-24  mutates 예외가 ② 에는 없었다 (잠재. 이 파일이 잡았다)

그동안 `verify()` 테스트는 `test_lineage_catches_tampered_input` 하나였고,
그 테스트의 상류 단계는 `reads=()` 라 **③ 가지가 한 번도 실행되지 않았다.**
다섯 번 깨진 가지의 커버리지가 0 이었다.

DECISIONS 는 매번 *"4시나리오로 검증했다"* 고 적었다. 손으로 했고 테스트로
남기지 않았다. §18-5 가 스스로 적은 그대로다 —
*"강제되지 않는 규약은 장식이다."*

**여기서는 조합을 센다.** 가지 셋 × (상류 실행됨/안 됨) × (외부/내부 입력).

IN    src/firelane/lineage.py
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_lineage_under_test", ROOT / "src/firelane/lineage.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_lineage_under_test"] = m
    spec.loader.exec_module(m)
    return m


class Step:
    """pipeline.Step 의 최소 대역. reads/writes/mutates 만 있으면 된다."""

    def __init__(self, name, reads=(), writes=(), mutates=()):
        self.name, self.reads, self.writes, self.mutates = \
            name, reads, writes, mutates

    @property
    def produces(self):
        return tuple(self.writes) + tuple(self.mutates)

    @property
    def consumes(self):
        return tuple(self.reads) + tuple(self.mutates)


def expand(decls):
    return list(decls)


@pytest.fixture
def rig(tmp_path):
    """ingest → segments → publish. ingest 만 외부 입력(raw)을 읽는다."""
    lg = _load()
    raw = tmp_path / "raw"
    raw.mkdir()
    for i in range(30):
        (raw / f"f{i}.bin").write_bytes(b"x" * 10)

    man = tmp_path / "_manifest.json"
    seg = tmp_path / "segments.geojson"
    web = tmp_path / "web.geojson"

    ingest = Step("ingest", reads=(raw,), writes=(man,))
    segments = Step("segments", reads=(man,), writes=(seg,))
    publish = Step("publish", reads=(seg,), writes=(web,))
    steps = [ingest, segments, publish]

    man.write_text('{"datasets":[1]}', encoding="utf-8")
    seg.write_text("{}", encoding="utf-8")
    web.write_text("{}", encoding="utf-8")
    for s in steps:
        lg.record(tmp_path, tmp_path, s, expand)

    def verify(step, fresh=()):
        lg.verify(tmp_path, tmp_path, step, expand, steps, fresh=set(fresh))

    return type("Rig", (), dict(
        lg=lg, root=tmp_path, raw=raw, man=man, seg=seg, web=web,
        ingest=ingest, segments=segments, publish=publish,
        steps=steps, verify=staticmethod(verify)))


# ── ③ 외부 입력 — 막으면 안 된다 ──────────────────────────────
def test_external_input_unchanged_passes(rig):
    rig.verify(rig.ingest)


def test_external_input_changed_passes(rig):
    """★ 2026-08-24 교착. raw 30→32 는 ingest 를 **돌려야 할 이유**다.

    ingest 는 최상류라 "상류부터 다시 돌려라" 가 가리킬 곳이 없다.
    """
    (rig.raw / "new1.bin").write_bytes(b"y" * 10)
    (rig.raw / "new2.bin").write_bytes(b"y" * 10)
    rig.verify(rig.ingest)


def test_external_input_shrunk_passes(rig):
    """줄어드는 방향도 같다. 소스를 내렸으면 다시 돌면 된다."""
    for f in list(rig.raw.iterdir())[:5]:
        f.unlink()
    rig.verify(rig.ingest)


# ── ② 상류 대조 — 08-18 방어. 살아 있어야 한다 ────────────────
def test_upstream_output_tampered_blocks(rig):
    """상류가 이번에 안 돌았는데 그 산출물이 바뀌었다 → 막는다.

    2026-08-18: `_manifest` 는 ngii1k 14,336 을 적었는데 `segments` 는 옛
    레이어 6,675 개를 읽고 있었다. 파일도 mtime 도 status 도 멀쩡했다.
    """
    rig.man.write_text('{"datasets":[1,2]}', encoding="utf-8")
    with pytest.raises(rig.lg.LineageError):
        rig.verify(rig.segments)


def test_upstream_fresh_passes(rig):
    """전량 실행. 상류가 방금 썼으니 달라야 정상이다."""
    rig.man.write_text('{"datasets":[1,2]}', encoding="utf-8")
    rig.lg.record(rig.root, rig.root, rig.ingest, expand)
    rig.verify(rig.segments, fresh=["ingest"])


def test_two_hops_downstream_blocks(rig):
    """한 칸 건너뛴 하류도 자기 상류로 판정한다."""
    rig.seg.write_text('{"z": null}', encoding="utf-8")
    with pytest.raises(rig.lg.LineageError):
        rig.verify(rig.publish)


# ── ③ mutates — 자기가 덧쓴 것을 자기가 다시 읽는다 ───────────
def test_mutated_input_is_not_self_compared(rig):
    """★ 다섯 번째 교착. terrain 이 segments.geojson 에 z 를 넣는 구조다.

    그 파일의 디스크 상태는 **항상** segments 의 기록과 다르다. mutates
    예외가 ③ 에만 있고 ② 에는 없어 `--from terrain` 이 막혔다.
    이 테스트를 처음 돌렸을 때 실제로 빨간불이 났다.
    """
    terrain = Step("terrain", writes=(rig.root / "terrain",),
                   mutates=(rig.seg,))
    steps = [rig.ingest, rig.segments, terrain, rig.publish]
    (rig.root / "terrain").mkdir(exist_ok=True)
    rig.lg.record(rig.root, rig.root, terrain, expand)
    rig.seg.write_text('{"z": 1}', encoding="utf-8")
    rig.lg.verify(rig.root, rig.root, terrain, expand, steps, fresh=set())


# ── ① 상류 기록 없음 — 경고지 실패가 아니다 ───────────────────
def test_missing_upstream_record_is_warning_not_failure(rig, capsys):
    lg = rig.lg
    data = lg.load(rig.root)
    del data["ingest"]
    (rig.root / lg.LINEAGE).write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rig.verify(rig.segments)
    assert "계보 미기록" in capsys.readouterr().out


# ── 회귀 — 최상류 단계는 자기를 상류로 가리킬 수 없다 ─────────
def test_error_never_points_at_the_step_itself(rig):
    """교착의 정의. 오류가 가리키는 상류가 자기 자신이면 탈출구가 없다."""
    (rig.raw / "z.bin").write_bytes(b"z")
    try:
        rig.verify(rig.ingest)
    except rig.lg.LineageError as e:
        pytest.fail(f"최상류 단계가 자기를 상류로 가리킨다:\n{e}")
