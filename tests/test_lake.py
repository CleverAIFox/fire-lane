"""레이크 해석기 · 대장 강제자 — **파일의 주인은 한 곳이 판정한다.**

★ 2026-09-17 (DECISIONS §173-4 · §174). 네 기준을 여기서 지킨다.
  ① 관문 — `lake.gate` 가 막는가(모의 레이크)
  ② 해석은 한 곳 — 대장 직접 로드 · 주인 블록 직접 해석 사본 수 래칫
  ③ 카나리아 — 그날의 사고 셋을 합성 대장으로 재현한다
  ④ 래칫 — 지금 위반 수를 상한으로 박고 내린다. **늘면 운다 · 줄면 상한을 내려라**

★ 실물 레이크 검사는 레이크가 붙은 기계에서만 돈다. CI 는 모의 레이크와 카나리아가 지킨다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from firelane import lake, ledger, paths

ROOT = Path(__file__).resolve().parents[1]

# ── 래칫 상한 — 2026-09-17 실측. 줄였으면 여기를 내린다 ─────────────
MAX_RETIRED_GLOB = 0          # 폐기 항목이 글롭으로 파일을 가리키는 수
MAX_RETIRED_NO_SHA = 7        # 이름으로는 적었는데 sha 가 없는 폐기 파일 — L2 가 레이크에서 잰다
MAX_LEDGER_LOADERS = 40       # ledger · lake 밖에서 sources.yaml 을 직접 yaml 로 읽는 파일
MAX_OWNER_BLOCK_READERS = 13  # ledger · lake 밖에서 retired · landing_disposition 블록을 직접 읽는 파일
MAX_AUTHORITY_BAD = 63        # authority 칸 규칙(MASTER §18-3a) 위반 datasets


def _ratchet(name: str, got: int, cap: int, detail: list[str]) -> None:
    assert got <= cap, (
        f"{name} {got} > 상한 {cap} — 늘었다.\n" + "\n".join(f"  {d}" for d in detail[:30]))
    assert got == cap, (
        f"{name} {got} < 상한 {cap} — 줄었다. 좋은 일이다.\n"
        f"  tests/test_lake.py 의 상한을 {got} 으로 내려라. 안 내리면 다시 늘어도 안 운다.")


# ── 판별식 — 카나리아가 흔든다 ─────────────────────────────────────
def retired_globbed(y: dict) -> list[str]:
    return lake.claims(y).retired_globbed


def retired_without_sha(y: dict) -> list[str]:
    out = []
    for k, e in (y.get("retired") or {}).items():
        sha = (e or {}).get("sha256") or {}
        for f in ledger.globs(e or {}):
            if not any(c in f for c in "*?[") and not (isinstance(sha, dict) and sha.get(f)):
                out.append(f"{k}: {f}")
    return out


LOAD = re.compile(r"safe_load|YAML\(|yaml\.load")
OWNER_BLOCK = re.compile(
    r"""(?:get\(\s*|\[\s*)["'](?:retired|landing_disposition)["']""")
EXEMPT_FILES = {"src/firelane/ledger.py", "src/firelane/lake.py", "tests/test_lake.py"}


def _sources() -> list[tuple[str, str]]:
    files = [*(ROOT / "src").rglob("*.py"), *(ROOT / "tools").glob("*.py"),
             *(ROOT / "tests").glob("*.py")]
    return [(p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8")) for p in sorted(files)]


def ledger_loaders(srcs: list[tuple[str, str]]) -> list[str]:
    return [r for r, s in srcs
            if r not in EXEMPT_FILES and "sources.yaml" in s and LOAD.search(s)]


def owner_block_readers(srcs: list[tuple[str, str]]) -> list[str]:
    return [r for r, s in srcs if r not in EXEMPT_FILES and OWNER_BLOCK.search(s)]


AUTHORITY = re.compile(r"^\S.*\S \((?P<route>[^()]+)\)$")


def authority_bad(y: dict) -> list[str]:
    out = []
    for k, e in (y.get("datasets") or {}).items():
        a = str((e or {}).get("authority") or "").strip()
        if not a:
            out.append(f"{k}: 칸 없음")
        elif "경유" in a:
            out.append(f"{k}: 개인 경유 — {a}")
        elif not AUTHORITY.match(a):
            out.append(f"{k}: 받은 경로 괄호 없음 — {a}")
    return out


# ── 래칫 ────────────────────────────────────────────────────────────
def test_retired_entries_name_files_not_globs():
    """폐기 항목은 파일 이름으로 주인이 된다(§173-2). 글롭은 활성을 잡는다(§172-5)."""
    bad = retired_globbed(ledger.load())
    _ratchet("폐기 글롭", len(bad), MAX_RETIRED_GLOB, bad)


def test_retired_files_carry_sha():
    """이름 · sha 둘 다 있어야 파일 단위 주인이다. 이름만으로는 같은 이름의 다른 판을 못 가린다."""
    bad = retired_without_sha(ledger.load())
    _ratchet("sha 없는 폐기 파일", len(bad), MAX_RETIRED_NO_SHA, bad)


def test_ledger_is_loaded_through_one_door():
    """`sources.yaml` 을 yaml 로 직접 읽는 파일 — `ledger.load` 로 옮길 사본(§173-4 ②)."""
    bad = ledger_loaders(_sources())
    _ratchet("대장 직접 로드", len(bad), MAX_LEDGER_LOADERS, bad)


def test_file_owners_are_resolved_in_one_place():
    """retired · landing_disposition 를 직접 읽는 파일 — `firelane.lake` 로 옮길 사본."""
    bad = owner_block_readers(_sources())
    _ratchet("주인 블록 직접 해석", len(bad), MAX_OWNER_BLOCK_READERS, bad)


def test_authority_names_institution_and_route():
    """authority = 기관 + 받은 경로 괄호. 개인 이름 금지(MASTER §18-3a · DECISIONS §173-3)."""
    bad = authority_bad(ledger.load())
    _ratchet("authority 규칙 위반", len(bad), MAX_AUTHORITY_BAD, bad)


def test_ratchet_probes_are_alive():
    """카나리아 — 판별식 넷이 **합성 입력에서** 운다."""
    y = {"retired": {"g": {"stem": "safety_firestation"},
                     "n": {"files": ["safety/a.csv"]},
                     "s": {"files": ["safety/b.csv"], "sha256": {"safety/b.csv": "ab"}}},
         "datasets": {"x": {"authority": "동부소방서"},
                      "y": {"authority": "전남광주통합특별시 동부소방서 (정보공개청구)"},
                      "z": {"authority": "동부소방서 (우지혜 경유)"}, "w": {}}}
    assert retired_globbed(y) == ["g"], "폐기 글롭 판별식이 죽었다"
    assert retired_without_sha(y) == ["n: safety/a.csv"], "sha 판별식이 죽었다"
    assert len(authority_bad(y)) == 3, f"authority 판별식이 죽었다: {authority_bad(y)}"
    srcs = [("tools/a.py", 'yaml.safe_load(open("sources.yaml"))'),
            ("tools/b.py", 'y.get("retired")'), ("tools/c.py", 'print("retired")'),
            ("src/firelane/ledger.py", 'yaml.safe_load(open("sources.yaml")) ; y["retired"]')]
    assert ledger_loaders(srcs) == ["tools/a.py"], "대장 로드 판별식이 죽었다"
    assert owner_block_readers(srcs) == ["tools/b.py"], "주인 블록 판별식이 죽었다"


# ── 해석기 카나리아 — 모의 레이크 ───────────────────────────────────
def _lake(tmp: Path, files: list[str]) -> Path:
    for rel in files:
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    return tmp


def _by(rows: list[lake.Row]) -> dict[str, lake.Row]:
    return {r.rel: r for r in rows}


def test_stem_glob_retired_on_active_file_blocks_the_gate(tmp_path):
    """§172-5 재현 — 폐기 stem 글롭이 활성 파일을 잡으면 두주인이고 **관문이 닫힌다.**"""
    y = {"datasets": {"fire_station": {"stem": "safety_firestation"}},
         "retired": {"firestation_kr_20250701": {"stem": "safety_firestation"}}}
    root = _lake(tmp_path, ["raw/safety/safety_firestation_kr_20240901.csv"])
    rows = lake.resolve(y, root)
    assert _by(rows)["raw/safety/safety_firestation_kr_20240901.csv"].state == "두주인"
    why = lake.gate(y, rows)
    assert any("두주인" in w for w in why) and any("폐기 글롭" in w for w in why), why


def test_named_retired_beats_active_glob(tmp_path):
    """폐기를 이름으로 적으면 활성 글롭보다 구체적이다 — 격리된 폐기본은 폐기 주인이다."""
    y = {"datasets": {"fire_station": {"stem": "safety_firestation"}},
         "retired": {"old": {"stem": "safety_firestation",
                             "files": ["safety/safety_firestation_kr_20250701.csv"]}}}
    root = _lake(tmp_path, ["raw/safety/safety_firestation_kr_20240901.csv",
                            "_quarantine/safety/safety_firestation_kr_20250701.csv",
                            "retired/safety/safety_firestation_kr_20250701.csv"])
    by = _by(lake.resolve(y, root))
    assert by["raw/safety/safety_firestation_kr_20240901.csv"].owners == ("datasets:fire_station",)
    assert by["_quarantine/safety/safety_firestation_kr_20250701.csv"].owners == ("retired:old",)
    assert by["retired/safety/safety_firestation_kr_20250701.csv"].state == "정상"
    assert lake.gate(y, lake.resolve(y, root)) == []


def test_quarantine_lookup_is_not_raw_only(tmp_path):
    """lake_scan S8 오판 재현 — 격리 파일의 은퇴 사유를 raw 에서만 찾으면 "근거 없음" 이 된다."""
    y = {"retired": {"enforcement": {"files": ["gjcity/gjcity_parking_enforce_jngj-donggu_20240108.csv"]}}}
    root = _lake(tmp_path, ["_quarantine/gjcity/gjcity_parking_enforce_jngj-donggu_20240108.csv",
                            "_quarantine/QUARANTINE.md", "_quarantine/eais/unknown.csv"])
    by = _by(lake.resolve(y, root))
    r = by["_quarantine/gjcity/gjcity_parking_enforce_jngj-donggu_20240108.csv"]
    assert (r.state, r.owners) == ("폐지층", ("retired:enforcement",)), r
    assert "사유 없음" in by["_quarantine/eais/unknown.csv"].note
    assert by["_quarantine/QUARANTINE.md"].state == "폐지층"


def test_one_archive_many_layers_is_sharing_not_two_owners(tmp_path):
    """전자지도 zip 하나를 레이어가 다른 datasets 여섯이 쓴다 — 공유다. 레이어가 같으면 두주인."""
    shared = {"a": {"stem": "juso_elctrnmap", "layer": "TL_SPRD_MANAGE.shp"},
              "b": {"stem": "juso_elctrnmap", "layer": "TL_SPBD_BULD.shp"}}
    root = _lake(tmp_path, ["raw/juso/juso_elctrnmap_jngj_20260711.zip"])
    rel = "raw/juso/juso_elctrnmap_jngj_20260711.zip"
    assert _by(lake.resolve({"datasets": shared}, root))[rel].state == "정상"
    same = {"a": {"stem": "juso_elctrnmap", "layer": "X.shp"}, "b": {"stem": "juso_elctrnmap", "layer": "X.shp"}}
    assert _by(lake.resolve({"datasets": same}, root))[rel].state == "두주인"
    bare = {"a": {"stem": "juso_elctrnmap"}, "b": {"stem": "juso_elctrnmap"}}
    assert _by(lake.resolve({"datasets": bare}, root))[rel].state == "두주인"


def test_layers_outside_the_declaration_block_the_gate(tmp_path):
    """선언 밖 폴더 · 루트 파일 · 주인 없는 raw 는 관문을 닫는다. _meta 는 폐지층."""
    y = {"datasets": {"k": {"files": ["nfa/a.csv"]}},
         "landing_disposition": {"items": [{"file": "held-*.zip", "why": "보류 사유"},
                                           {"file": "nowhy-*.zip", "why": ""}]}}
    root = _lake(tmp_path, ["raw/nfa/a.csv", "raw/nfa/stray.csv", "tiles/ortho/15/1.jpg",
                            "stray_at_root.txt", "raw/_meta/x.meta.json",
                            "landing/held-1.zip", "landing/nowhy-1.zip", "interim/t.gpkg"])
    by = _by(lake.resolve(y, root))
    assert by["raw/nfa/a.csv"].state == "정상"
    assert by["raw/nfa/stray.csv"].state == "주인없음"
    assert by["tiles/ortho/15/1.jpg"].state == "선언밖"
    assert by["stray_at_root.txt"].state == "선언밖"
    assert by["raw/_meta/x.meta.json"].state == "폐지층"
    assert by["landing/held-1.zip"].state == "정상"
    assert by["landing/nowhy-1.zip"].state == "주인없음", "사유 없는 처분은 처분이 아니다"
    assert by["interim/t.gpkg"].state == "정상"
    why = lake.gate(y, lake.resolve(y, root))
    assert len(why) == 4, why   # stray.csv · tiles · 루트 파일 · 사유 없는 landing


def test_norm_owner_follows_converter_dst_and_named_absence(tmp_path):
    """norm 주인은 `_prep.json` 의 dst(변환기가 확장자를 바꾼다). 이름으로 주장한 것이 없으면 결손."""
    y = {"datasets": {"card": {"files": ["safety/card_20260904_jisan2.pdf"]},
                      "gone": {"files": ["safety/missing.csv"]}}}
    prep = {"files": {"safety/card_20260904_jisan2.pdf": {"dst": "safety/card_20260904_jisan2.csv"}}}
    root = _lake(tmp_path, ["raw/safety/card_20260904_jisan2.pdf", "norm/safety/card_20260904_jisan2.csv"])
    rows = lake.resolve(y, root, prep)
    by = _by(rows)
    assert by["norm/safety/card_20260904_jisan2.csv"].state == "정상"
    assert any(r.state == "결손" and r.owners == ("datasets:gone",) for r in rows)


# ── 실물 레이크 — 붙은 기계에서만 ───────────────────────────────────
def _lake_attached() -> bool:
    d = paths.DATA
    return bool(d and (d / "raw").is_dir() and any((d / "raw").iterdir()))


@pytest.mark.skipif(not _lake_attached(), reason="환경skip — 레이크가 없다(CI)")
def test_real_lake_has_no_two_owners():
    """실물 레이크에서 두주인 0 · 폐기 글롭 0. 나머지 상태(폐지층 · 선언밖)는 L2 가 비운다."""
    import json
    y = ledger.load()
    prep_p = ROOT / "data" / "_prep.json"
    prep = json.loads(prep_p.read_text(encoding="utf-8")) if prep_p.exists() else {}
    rows = lake.resolve(y, paths.DATA, prep)
    two = [f"{r.rel}  {' · '.join(r.owners)}" for r in rows if r.state == "두주인"]
    assert not two, "두주인 — 대장이 같은 파일을 둘로 주장한다\n" + "\n".join(two)
    assert not retired_globbed(y)
