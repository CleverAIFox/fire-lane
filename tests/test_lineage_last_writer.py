"""`lineage.verify` 는 파일을 **마지막으로 쓴 단계**의 기록과 대조한다.  (PLAN #212)

★ 왜 — `terrain` 이 `ingest` 산출(`fire_station.geojson` · `_manifest.json`)에 z 를 덧쓴다. 그러면 디스크는 `terrain` 의 기록과 같고 `ingest` 의 기록과는 늘 다르다 —
  전량이 끝날 때마다 다음 `--from segments` 가 막혔다(복사본 실험으로 재현). 계보를 거짓으로 고치는 길(`terrain` 이 `ingest` 칸에 덮어 적는다)은 안 갔다 —
  「ingest 와 terrain 사이에 남이 고친 것」을 못 잡게 된다. 대조 상대만 바꿨다.

★ 양성 대조 둘이 본체다 — ㉮ **마지막 작성자 뒤에 남이 파일을 고치면 여전히 잡는가**(안 되면 검증이 죽는다) · ㉯ **전량 직후 `--from segments` 가 서는가**.
  「마지막」을 무엇으로 정하는지(기록 시각 · 같은 시각이면 단계 순서)는 `lineage.last_writer` 가 사유와 함께 적는다 — 아래 시험이 시각 · 순서 · 낡은 기록을 가른다.

밖    `pipeline` 전체를 안 돈다 — 합성 단계로 `verify` 의 판정만 본다. 실제 계보 파일(`data/processed/_lineage.json`)은 CI 에 없어(`.gitignore`) 로컬 시험은 건너뛴다.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("_lineage_lw", ROOT / "src/firelane/lineage.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_lineage_lw"] = m
    spec.loader.exec_module(m)
    return m


class Step:
    def __init__(self, name, reads=(), writes=(), mutates=()):
        self.name, self.reads, self.writes, self.mutates = name, reads, writes, mutates

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
    """ingest(F 를 쓴다) → segments(F 를 읽는다) → terrain(F 를 덧쓴다). `fire_station.geojson` 의 실제 모양이다."""
    lg = _load()
    f = tmp_path / "F.geojson"
    seg = tmp_path / "seg.geojson"
    f.write_bytes(b"ingest-bytes")
    ingest = Step("ingest", writes=(f,))
    segments = Step("segments", reads=(f,), writes=(seg,))
    terrain = Step("terrain", mutates=(f,))
    steps = [ingest, segments, terrain]
    seg.write_text("{}", encoding="utf-8")

    def stamp(name, at):
        """단계를 지금 디스크 상태로 기록하고 기록 시각을 `at` 으로 못박는다."""
        s = next(x for x in steps if x.name == name)
        lg.record(tmp_path, tmp_path, s, expand)
        p = tmp_path / lg.LINEAGE
        d = json.loads(p.read_text(encoding="utf-8"))
        d[name]["at"] = at
        p.write_text(json.dumps(d), encoding="utf-8")

    def verify(step):
        lg.verify(tmp_path, tmp_path, step, expand, steps, fresh=set())

    return type("Rig", (), dict(lg=lg, f=f, steps=steps, ingest=ingest, segments=segments, terrain=terrain,
                                stamp=staticmethod(stamp), verify=staticmethod(verify), root=tmp_path))


T1, T2, T3 = "2026-11-09T10:00:00+09:00", "2026-11-09T10:05:00+09:00", "2026-11-09T10:10:00+09:00"


def _full_run(rig):
    """ingest → segments → terrain 이 차례로 돈 직후. terrain 이 F 에 z 를 덧쓴다."""
    rig.stamp("ingest", T1)
    rig.stamp("segments", T2)
    rig.f.write_bytes(b"terrain-bytes-with-z")
    rig.stamp("terrain", T3)


def test_after_a_full_run_the_next_from_segments_passes(rig):
    """㉯ 전량 직후 `--from segments` 가 선다 — 디스크는 terrain 의 기록과 같다."""
    _full_run(rig)
    rig.verify(rig.segments)


def test_someone_editing_the_file_after_the_last_writer_is_still_caught(rig):
    """㉮ ★ 마지막 작성자(terrain) 뒤에 남이 파일을 고치면 **여전히 잡는다.** 안 잡으면 이 고침은 검증을 죽이는 것이다."""
    _full_run(rig)
    rig.f.write_bytes(b"someone-else-edited")
    with pytest.raises(rig.lg.LineageError) as e:
        rig.verify(rig.segments)
    assert "terrain 가 쓴 것" in str(e.value)               # 탓하는 단계가 마지막 작성자다


def test_the_ingest_record_is_not_rewritten_by_the_fix(rig):
    """계보는 각 단계가 쓴 것을 **그대로** 적는다 — 대조 상대만 바뀌었다. ingest 칸이 terrain 값으로 덮이면 뜻이 무너진다."""
    _full_run(rig)
    rig.verify(rig.segments)
    d = json.loads((rig.root / rig.lg.LINEAGE).read_text(encoding="utf-8"))
    key = "F.geojson"
    assert d["ingest"]["outputs"][key] != d["terrain"]["outputs"][key]


def test_a_later_rerun_of_the_upstream_makes_it_the_last_writer_by_time(rig):
    """시각이 순서를 이긴다 — ingest 가 terrain **뒤에 다시** 돌면(z 가 지워졌다) 마지막 작성자는 ingest 다.

    순서만 썼다면 낡은 terrain 기록과 대조해 엉뚱한 단계를 탓한다. 디스크가 ingest 의 새 산출이면 통과한다.
    """
    _full_run(rig)
    rig.f.write_bytes(b"ingest-bytes-v2")
    rig.stamp("ingest", "2026-11-09T10:20:00+09:00")
    assert rig.lg.last_writer(json.loads((rig.root / rig.lg.LINEAGE).read_text(encoding="utf-8")), "F.geojson",
                              [s.name for s in rig.steps]) == "ingest"
    rig.verify(rig.segments)
    rig.f.write_bytes(b"terrain-bytes-with-z")                # 낡은 terrain 산출이 도로 놓이면 — ingest 새 기록과 달라 잡는다
    with pytest.raises(rig.lg.LineageError) as e:
        rig.verify(rig.segments)
    assert "ingest 가 쓴 것" in str(e.value)


def test_same_second_ties_are_broken_by_pipeline_order(rig):
    """같은 시각이면 단계 순서가 정한다 — `mutates` 는 늘 뒤 단계가 덧쓴다."""
    rig.stamp("ingest", T1)
    rig.f.write_bytes(b"terrain-bytes-with-z")
    rig.stamp("terrain", T1)                                   # 같은 초
    rig.stamp("segments", T2)
    rig.verify(rig.segments)                                   # 디스크 = terrain 기록(순서가 뒤)
    rig.f.write_bytes(b"ingest-bytes")
    with pytest.raises(rig.lg.LineageError):
        rig.verify(rig.segments)


def test_an_unreadable_timestamp_never_wins(rig):
    """시각을 못 읽는 기록은 가장 이르다 — 깨진 기록이 「마지막」이 되어 판정을 가져가지 못한다."""
    _full_run(rig)
    p = rig.root / rig.lg.LINEAGE
    d = json.loads(p.read_text(encoding="utf-8"))
    d["terrain"]["at"] = "쓰레기"
    assert rig.lg.last_writer(d, "F.geojson", [s.name for s in rig.steps]) == "ingest"


def test_a_file_nobody_recorded_has_no_last_writer(rig):
    assert rig.lg.last_writer({}, "F.geojson", ["ingest"]) is None


def test_the_real_local_lineage_now_passes_the_segments_check_if_it_exists():
    """이 기계에서 지금 막히던 실제 계보(`fire_station.geojson` 30976… ≠ 89aa…)가 이제 통과한다. CI 에는 그 파일이 없다."""
    lin = ROOT / "data" / "processed" / "_lineage.json"
    if not lin.is_file():
        pytest.skip("환경skip(산출물) — `_lineage.json` 은 .gitignore 라 CI 에 없다")
    from firelane import lineage, pipeline
    step = next(s for s in pipeline.STEPS if s.name == "segments")
    try:
        lineage.verify(pipeline.PROCESSED, pipeline.ROOT, step, pipeline.expand, pipeline.STEPS, fresh=set())
    except lineage.LineageError as e:
        text = str(e)
        assert "fire_station" not in text and "_manifest.json" not in text, f"덧쓰기 때문에 막히던 두 칸이 아직 막는다:\n{text}"
