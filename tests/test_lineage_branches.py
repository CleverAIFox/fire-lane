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


# ── 계보 장부를 읽는 두 입 (DECISIONS §496) ───────────────────
# ★ `guards.manifest_status` · `manifest_outputs` 는 `_manifest.json` 을 읽는
#   **입**이고, 이 파일이 드는 `verify()` 와 `lineage_check()` 가 그 위에 선다.
#   `manifest_outputs` 머리말이 그 까닭을 적는다 — 「한 key 가 여러 파일을
#   낸다. ngii1k 하나가 10개를 만든다. **key 만 보는 검사는 그 10개 중 일부만
#   갱신된 상태를 통과시킨다.**」 그 입을 미는 자리가 없었다(§496 — `get`
#   하나 때문에 입출력으로 가려져 있었다).
def _manifest_dir(tmp_path: Path, datasets: list[dict]) -> Path:
    d = tmp_path / "processed"
    d.mkdir()
    (d / "_manifest.json").write_text(
        json.dumps({"datasets": datasets}, ensure_ascii=False), encoding="utf-8")
    return d


def test_manifest_status_reads_every_key(tmp_path):
    """key → status 를 그대로 낸다. 실패도 **적어** 온다 — 거르는 쪽은 부르는 자다."""
    from firelane.guards import manifest_status

    d = _manifest_dir(tmp_path, [
        {"key": "a", "status": "OK"},
        {"key": "b", "status": "FAIL"},
        {"key": "c", "status": "SKIP"},
    ])
    assert manifest_status(d) == {"a": "OK", "b": "FAIL", "c": "SKIP"}


def test_a_missing_manifest_is_a_guard_failure_not_an_empty_dict(tmp_path):
    """★ 장부가 없으면 **운다.** 빈 표를 내면 그 위의 검사가 0건을 돌고 초록이다."""
    import pytest

    from firelane.guards import GuardFailure, manifest_status

    (tmp_path / "processed").mkdir()
    with pytest.raises(GuardFailure, match=r"_manifest\.json"):
        manifest_status(tmp_path / "processed")


def test_manifest_outputs_maps_each_file_to_the_key_that_made_it(tmp_path):
    """★ 본체. **한 key 가 여러 파일**을 낸다 — 파일마다 적는다."""
    from firelane.guards import manifest_outputs

    d = _manifest_dir(tmp_path, [
        {"key": "ngii1k", "status": "OK",
         "outputs": ["ngii1k_5186.gpkg", "ngii1k_walk_5186.gpkg"]},
        {"key": "cctv", "status": "OK", "outputs": ["cctv_5186.gpkg"]},
    ])
    assert manifest_outputs(d) == {
        "ngii1k_5186.gpkg": "ngii1k", "ngii1k_walk_5186.gpkg": "ngii1k",
        "cctv_5186.gpkg": "cctv"}


def test_a_failed_dataset_contributes_no_outputs(tmp_path):
    """★ 실패한 key 의 산출물은 **안 센다.** 세면 깨진 파일이 신선하다고 읽힌다."""
    from firelane.guards import PASS_STATUS, manifest_outputs

    assert set(PASS_STATUS) == {"OK", "SKIP"}, "통과 어휘가 바뀌었다"
    d = _manifest_dir(tmp_path, [
        {"key": "a", "status": "FAIL", "outputs": ["a.gpkg"]},
        {"key": "b", "status": "SKIP", "outputs": ["b.gpkg"]},
        {"key": "c", "status": "OK", "outputs": None},
    ])
    assert manifest_outputs(d) == {"b.gpkg": "b"}


# ── 데이터셋 하나의 지문 (DECISIONS §499) ────────────────────
def test_sha_of_a_directory_changes_when_one_sheet_changes(tmp_path):
    """★ `ingest.sha_of` — **여러 파일이 한 데이터셋**인 경우가 있다.

    도엽 디렉터리(ngii1k)가 그렇다. 도엽 한 장이 빠지거나 연도가 바뀌면
    **여기서 드러나야 한다** — 이 수가 봉인의 `raw` 칸이고, 안 움직이면
    바뀐 입력으로 만든 산출물이 「같은 입력」으로 기록된다.
    """
    from firelane.ingest import sha_of

    d = tmp_path / "sheets"
    (d / "sub").mkdir(parents=True)
    (d / "a.ngi").write_text("A", encoding="utf-8")
    (d / "sub" / "b.ngi").write_text("B", encoding="utf-8")
    base = sha_of(d)

    (d / "sub" / "b.ngi").write_text("B2", encoding="utf-8")
    assert sha_of(d) != base, "내용이 바뀌었는데 지문이 같다"

    (d / "sub" / "b.ngi").write_text("B", encoding="utf-8")
    assert sha_of(d) == base, "같은 내용에 다른 지문이다 — 재현이 안 된다"

    (d / "c.ngi").write_text("C", encoding="utf-8")
    assert sha_of(d) != base, "도엽이 늘었는데 지문이 같다"


def test_sha_of_a_directory_notices_a_rename(tmp_path):
    """★ 경로도 지문에 든다 — 이름만 바뀌어도 다른 데이터셋이다(도엽 번호)."""
    from firelane.ingest import sha_of

    d = tmp_path / "sheets"
    d.mkdir()
    (d / "gj037.ngi").write_text("A", encoding="utf-8")
    before = sha_of(d)
    (d / "gj037.ngi").rename(d / "gj038.ngi")
    assert sha_of(d) != before


def test_sha_of_ignores_underscore_files_so_our_own_bookkeeping_does_not_count(tmp_path):
    """★ `_` 로 시작하는 것은 **우리가 쓴 장부**다 — 입력 지문에 들면 안 된다.

    들면 `_manifest.json` 을 쓰는 순간 입력이 바뀌었다고 나오고, 다음 실행이
    상류 재빌드를 요구한다(§267 이 계보에서 겪은 그 자리).
    """
    from firelane.ingest import sha_of

    d = tmp_path / "sheets"
    d.mkdir()
    (d / "a.ngi").write_text("A", encoding="utf-8")
    before = sha_of(d)
    (d / "_manifest.json").write_text("{}", encoding="utf-8")
    assert sha_of(d) == before


def test_sha_of_a_single_file_is_its_own_hash(tmp_path):
    """파일 하나면 그 파일의 해시다 — 디렉터리 셈법을 끼우지 않는다."""
    from firelane.hashing import sha256
    from firelane.ingest import sha_of

    p = tmp_path / "one.zip"
    p.write_bytes(b"PK\x03\x04")
    assert sha_of(p) == sha256(p)


def test_fingerprint_sees_a_change_past_the_first_16mib(tmp_path):
    """16MiB 뒤의 바이트가 바뀌어도 지문이 달라진다.  (감사 1-8 · Zm20)

    종전 `_sha` 는 16MiB 를 넘으면 읽기를 멈추고 크기만 섞었다 — 실물 `building.geojson`
    (17.0MB) 이 그 넘는 쪽이었다. 크기가 같은 채 뒤쪽이 바뀌면 계보가 못 본다.
    """
    from firelane import lineage

    a = tmp_path / "big.json"
    blob = bytearray(b"x" * ((1 << 24) + (3 << 20)))
    a.write_bytes(bytes(blob))
    before = lineage.fingerprint(a)
    blob[-5] = ord("y")                       # 크기 그대로, 끝에서 다섯째 바이트만
    a.write_bytes(bytes(blob))
    assert lineage.fingerprint(a) != before, "16MiB 뒤의 변경을 못 본다"
