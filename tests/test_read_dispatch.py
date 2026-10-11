#!/usr/bin/env python3
"""
test_read_dispatch.py — `kind` → 갈래 배선이 **선언과 맞는가.**  (PLAN §1 #128 · DECISIONS §274)

── 왜 생겼나 ──────────────────────────────────────────────────
갈래를 `read/` 로 내리면서 표 하나가 정본이 됐다. 표는 **조용히 틀릴 수 있다** —
`kind` 하나를 빠뜨려도 그 소스를 돌릴 때까지 아무도 모르고, 도형/표 선언이
어긋나면 dict 가 `save()` 로 들어가 한참 아래에서 엉뚱한 이름으로 죽는다.

IN    firelane.read · firelane.kinds · sources.yaml
OUT   없음 (검사)
밖    **갈래가 옳게 읽는가는 안 본다** — 그것은 레이크가 있어야 재고,
      파이프라인 실행과 `_manifest.json` 대조가 든다. 여기는 **배선**만 본다.
      그리고 **어느 실물을 읽을지도 안 본다** — `ingest.paths_for` 소관이다.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from firelane import kinds, ledger, read

ROOT = Path(__file__).resolve().parents[1]

#: 훑는 범위 — 저장소의 파이썬 전부. 좁히면 `deadcheck ⑤` 가 문다.
ROOTS = ("src", "tools", "tests")


def _repo_py() -> list[Path]:
    return sorted(q for r in ROOTS for q in (ROOT / r).rglob("*.py")
                  if "__pycache__" not in q.parts)


def test_every_kind_the_ledger_uses_has_a_reader():
    """★ 이 시험이 이 파일의 본체다. 하나 빠지면 그 소스가 실행 중에 죽는다."""
    # ★ 대장은 `ledger.load` 한 문으로만 연다 — 여기서 yaml 로 직접 읽으면
    #   `test_lake` 의 「대장 직접 로드」 래칫이 하나 는다(실제로 한 번 늘렸다).
    used = {(v or {}).get("kind")
            for v in ledger.load()["datasets"].values()} - {None}
    # ★ 카나리아. 대장을 못 읽거나 칸 이름이 바뀌면 `used` 가 비고, 그러면
    #   아래 대조가 **공집합끼리 맞아** 조용히 초록이 난다. 주입 ③(대장에서
    #   `kind` 를 전부 지운다)이 실제로 그렇게 통과했다 — 그래서 이 줄이 있다.
    assert len(used) >= 8, (
        f"대장이 쓰는 kind 가 {len(used)}종이다 — 대장을 못 읽었거나 칸 이름이 "
        "바뀌었다. 0 을 통과로 세지 않는다")

    missing = sorted(used - set(read.READERS))
    assert not missing, (
        f"대장이 쓰는 kind 인데 갈래가 없다: {missing}\n"
        "  실행하면 `read.reader()` 가 세운다. 셋을 잇는다 — "
        "firelane.kinds.KINDS · read/<갈래>.py 의 함수 · read.READERS")


def test_the_registry_and_the_classifier_agree():
    """`kinds.KINDS` 는 분류, `read.READERS` 는 읽기다. 한쪽에만 있으면 갈린 것이다."""
    only_class = sorted(set(kinds.KINDS) - set(read.READERS))
    only_read = sorted(set(read.READERS) - set(kinds.KINDS))
    assert not only_class, (
        f"분류에는 있고 읽기에는 없다: {only_class} — 그 kind 는 대장에 적을 수 "
        "있는데 실행하면 죽는다")
    assert not only_read, (
        f"읽기에는 있고 분류에는 없다: {only_read} — `ledger` 가 그 kind 의 "
        "스키마·복수성을 모른다")


def test_geom_declaration_matches_what_each_reader_returns():
    """★ 선언과 실물이 갈리면 dict 가 `save()` 로 들어간다.

    함수 본문에서 `return g` 로 끝나는가를 본다 — 실행 없이 잴 수 있는 것은
    여기까지고, 그 너머는 파이프라인이 든다(머리말 「밖」).
    """
    bad = []
    for kind, fn in read.READERS.items():
        src = inspect.getsource(fn)
        gives_geom = "\n    return g\n" in src
        if gives_geom is not (kind in read.GEOM_KINDS):
            bad.append(f"  {kind}: 실물 {'도형' if gives_geom else '계보 조각'} · "
                       f"선언 {'도형' if kind in read.GEOM_KINDS else '계보 조각'}")
    assert not bad, "`read.GEOM_KINDS` 선언이 갈래 실물과 다르다:\n" + "\n".join(bad)


def test_unknown_kind_says_what_it_knows():
    """모른다고만 하면 다음 사람이 다시 찾아야 한다. 아는 것을 댄다."""
    with pytest.raises(ValueError) as ex:
        read.reader("no_such_kind")
    msg = str(ex.value)
    assert "no_such_kind" in msg
    assert "raw_only" in msg, "아는 kind 를 안 댄다"
    assert "READERS" in msg, "어디를 고치면 되는지 안 알려준다"


def test_no_reader_reaches_back_into_ingest():
    """★ 갈래가 `ingest` 를 부르면 임포트가 돈다(DECISIONS §274-4).

    `save` 는 `Ctx` 로 **주입**받는다 — 그것이 유일한 통로다.
    """
    # ★ **저장소 전체를 훑고 걸러낸다.** `read/` 만 훑으면 갈래 함수가 `tools/` 나
    #   `tests/` 에 슬쩍 놓였을 때 못 본다 — 그리고 `deadcheck ⑤`(좁은 범위)가
    #   「이 검사가 src 만 본다」고 정확히 문다. 훑는 범위는 전부고, 좁은 것은 술어다.
    bad = []
    for p in _repo_py():
        rel = p.relative_to(ROOT).as_posix()
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = ln.strip()
            if not (s.startswith(("import ", "from ")) and "firelane.ingest" in s):
                continue
            if rel.startswith("src/firelane/read/"):
                bad.append(f"  {rel}:{i}  {s}")
            elif "def read_" in p.read_text(encoding="utf-8"):
                bad.append(f"  {rel}:{i}  갈래 함수를 들면서 `ingest` 를 부른다")
    assert not bad, (
        "갈래가 `ingest` 를 임포트한다 — `read → ingest → read` 로 고리가 돈다.\n"
        "  필요한 것은 `Ctx` 로 받아라(지금 `save` 가 그렇다).\n" + "\n".join(bad))


def test_every_family_module_declares_its_scope():
    """머리말의 `밖` 칸 — 이름이 시사하지만 이 모듈이 **안 보는 것**."""
    # ★ 위와 같은 이유로 전부 훑고 `read/` 만 고른다(`deadcheck ⑤`).
    bad = []
    for p in _repo_py():
        if p.parent.name != "read" or p.parent.parent.name != "firelane":
            continue
        if "밖" not in p.read_text(encoding="utf-8")[:2000]:
            bad.append(p.name)
    assert not bad, (
        f"`밖` 칸 없는 갈래 모듈: {bad}\n"
        "  선언이 없으면 다음 사람이 이 모듈에 안 맞는 일을 넣는다")


# ── 읽지 않는 갈래 — 이름을 안 부르고 있었다 (§495) ───────────
# ★ `read_raw_only` 는 데이터셋의 36%(26/72)를 드는 갈래다(§274-3). 일곱 줄
#   이고 앞으로도 일곱 줄이라고 머리말이 적는데, `tools/srccov.py` 가
#   「시험이 이름으로도 안 부른다」로 셌다(§493). **가장 많은 소스를 지나는
#   갈래**를 미는 자리가 없었다 — 이 파일은 배선만 보고 갈래 안은 안 봤다.
def _ctx(**over):
    """`Ctx` 한 벌. 이 갈래는 `rec` 하나만 만지므로 나머지는 자리만 채운다."""
    from pathlib import Path

    from firelane.read.ctx import Ctx

    base = {"key": "dem", "e": {"kind": "raw_only"}, "src": Path("a.zip"),
            "hits": [Path("a.zip")], "crs": "EPSG:5186", "tmp": Path(),
            "out": Path(), "rec": {"key": "dem", "status": "OK"},
            "save": lambda *a, **k: {}}
    return Ctx(**(base | over))


def test_raw_only_is_a_skip_not_a_failure():
    """★ 본체. **SKIP 이고 FAIL 이 아니다** — 다른 스크립트가 직접 읽는다.

    FAIL 로 적으면 `_manifest.json` 에 실패 26건이 서고, 그 26 이 서면
    진짜 실패가 안 보인다(§18-13 — 잦은 오탐은 진짜 경보를 죽인다).
    """
    from firelane.read.passthrough import read_raw_only

    got = read_raw_only(_ctx())
    assert got["status"] == "SKIP", got["status"]
    assert "raw_only" in got["note"]


def test_raw_only_claims_no_features_and_no_outputs():
    """★ 산출을 **빈 것으로** 적는다. 안 적으면 앞 단계의 수가 그대로 남는다."""
    from firelane.read.passthrough import read_raw_only

    dirty = {"key": "dem", "status": "OK", "features": 12345,
             "geom": ["LineString"], "outputs": ["processed/옛것.gpkg"]}
    got = read_raw_only(_ctx(rec=dirty))
    assert got["features"] == "" and got["geom"] == [] and got["outputs"] == []


def test_raw_only_keeps_the_lineage_it_was_handed():
    """앞서 쌓인 계보 조각(키 · 원본 sha 같은 것)은 **지우지 않는다**."""
    from firelane.read.passthrough import read_raw_only

    got = read_raw_only(_ctx(rec={"key": "dem", "source_sha256": "abc",
                                  "status": "OK"}))
    assert got["key"] == "dem" and got["source_sha256"] == "abc"


def test_raw_only_does_not_open_the_file():
    """★ 머리말의 약속 — 「실물을 열지 않는다」. 없는 경로를 줘도 돈다."""
    from pathlib import Path

    from firelane.read.passthrough import read_raw_only

    got = read_raw_only(_ctx(src=Path("/없는곳/없는파일.zip"),
                             hits=[Path("/없는곳/없는파일.zip")]))
    assert got["status"] == "SKIP"


# ── CSV 점 읽기 — 절단 상자가 판정이다 (§495) ─────────────────
# ★ `read/_io.load_csv_points` 는 좌표 있는 CSV 전부가 지나는 자다. 절단
#   상자(`BBOX_4326`)가 여기서 걸리고, 그 상자는 **대장이 내준다**(§274-4).
#   `tools/srccov.py` 가 「시험이 이름으로도 안 부른다」로 셌다(§493).
def _csv(tmp_path, body: str, enc: str = "utf-8"):
    p = tmp_path / "pts.csv"
    p.write_bytes(body.encode(enc))
    return p


def _inside():
    """대장 상자 **안**의 한 점. 수를 손으로 적지 않는다."""
    from firelane.read._io import BBOX_4326

    return ((BBOX_4326[0] + BBOX_4326[2]) / 2, (BBOX_4326[1] + BBOX_4326[3]) / 2)


def test_csv_points_keeps_what_is_inside_the_ledger_box(tmp_path):
    """★ 본체. 상자 안은 남고 **밖은 떨어진다.**"""
    from firelane.read._io import load_csv_points

    lon, lat = _inside()
    p = _csv(tmp_path, "이름,경도,위도\n"
             f"안,{lon},{lat}\n"
             "밖,127.5,36.5\n"
             "먼곳,0,0\n")
    g = load_csv_points(p, "경도", "위도", "utf-8")
    assert g["이름"].tolist() == ["안"], g["이름"].tolist()
    assert g.crs.to_epsg() == 4326


def test_swapped_longitude_and_latitude_silently_yields_nothing(tmp_path):
    """★ **적어 둔다** — 경위도를 뒤집은 파일은 0건이 되고 **안 운다.**

    위도 35 는 경도 상자(126.9x) 밖이고 경도 126.9 는 위도 상자 밖이다.
    그래서 뒤집힌 파일은 전부 걸러져 「상자 밖이라 0건」과 구별되지 않는다.
    원본이 `X좌표=위도` 로 오는 경우가 실제로 있다(`safety_firestation`
    머리말). 그 꼴을 아는 것은 지금 **사람**이고, 여기 그 사실을 남긴다.
    """
    from firelane.read._io import load_csv_points

    lon, lat = _inside()
    p = _csv(tmp_path, f"이름,경도,위도\n뒤집힘,{lat},{lon}\n")
    assert len(load_csv_points(p, "경도", "위도", "utf-8")) == 0


def test_a_non_numeric_coordinate_is_dropped_not_fatal(tmp_path):
    """좌표 칸에 글자가 오면 **그 행만** 버린다 — 파일을 통째로 잃지 않는다."""
    from firelane.read._io import load_csv_points

    lon, lat = _inside()
    p = _csv(tmp_path, "이름,경도,위도\n"
             f"좋음,{lon},{lat}\n"
             "글자,없음,없음\n"
             f"빈칸,,{lat}\n")
    g = load_csv_points(p, "경도", "위도", "utf-8")
    assert g["이름"].tolist() == ["좋음"]


def test_other_columns_keep_their_leading_zeros(tmp_path):
    """★ `dtype=str` 이다. 법정동코드 `0100` 이 `100` 이 되면 조인이 깨진다."""
    from firelane.read._io import load_csv_points

    lon, lat = _inside()
    p = _csv(tmp_path, "코드,경도,위도\n"
             f"0100,{lon},{lat}\n")
    g = load_csv_points(p, "경도", "위도", "utf-8")
    assert g["코드"].tolist() == ["0100"], g["코드"].tolist()


def test_a_cp949_file_reads_without_being_told(tmp_path):
    """★ 선언이 틀려도 읽는다 — 같은 데이터셋도 받을 때마다 인코딩이 바뀐다."""
    from firelane.read._io import load_csv_points

    lon, lat = _inside()
    p = _csv(tmp_path, f"이름,경도,위도\n소방서,{lon},{lat}\n", enc="cp949")
    g = load_csv_points(p, "경도", "위도", "utf-8")   # **틀린** 선언을 준다
    assert g["이름"].tolist() == ["소방서"]


def test_the_row_filter_runs_before_the_coordinates_are_parsed(tmp_path):
    """`filt` 는 **글자 상태**에서 돈다 — 그래서 코드값으로 거를 수 있다."""
    from firelane.read._io import load_csv_points

    lon, lat = _inside()
    p = _csv(tmp_path, "종류,경도,위도\n"
             f"소방,{lon},{lat}\n"
             f"경찰,{lon},{lat}\n")
    g = load_csv_points(p, "경도", "위도", "utf-8",
                        filt=lambda d: d[d["종류"] == "소방"])
    assert g["종류"].tolist() == ["소방"]
