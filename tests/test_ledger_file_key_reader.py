"""`inventory` · `intake_name` 이 대장의 `files` 를 본다.  (감사 1-4 · Zm20)

두 소비자가 `meta.get("file")` 단수만 읽었다. 정본 접근자 `ledger.files_decl()` 은
`files` 를 먼저 보고 `file` 로 물러난다 — 두 소비자만 그 길을 비껴, `files:` 로 적힌
항목은 「file 미지정」 · 제안 없음으로 조용히 빠졌다.
`test_ledger_accessor.py` 의 래칫은 `.get("files")` 만 세므로 이 단수 읽기를 못 잡았다.

IN    이 파일의 대상 모듈 · 실물
OUT   없음 (검사)
PARAM 없음
밖    **대장 전체의 소비자**는 안 본다 — 그것은 `test_ledger_accessor.py` 소관이다. 여기는 이 둘이 `files` 를 읽는지만 본다.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

import firelane.inventory as inv
from firelane.intake_name import propose

ROOT = Path(__file__).resolve().parents[1]


def test_inventory_resolves_a_files_only_entry(tmp_path: Path, monkeypatch) -> None:
    raw = tmp_path / "raw" / "zz"
    raw.mkdir(parents=True)
    (raw / "a.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    src = tmp_path / "sources.yaml"
    src.write_text(yaml.safe_dump({"datasets": {
        "zz_demo": {"kind": "csv", "files": ["zz/a.csv"]}}}), encoding="utf-8")
    monkeypatch.setattr(inv, "SOURCES", src)
    monkeypatch.setattr(inv, "RAW", tmp_path / "raw")
    out = inv.collect()["datasets"]
    assert out["zz_demo"].get("status") != "file 미지정", \
        "`files:` 로 적은 항목을 `file` 단수만 읽어 미지정으로 본다"


def test_intake_name_suggests_from_a_files_only_entry() -> None:
    ds = {"zz_demo": {"kind": "csv", "files": ["zz/zz_demo_gj_20260101.csv"],
                      "note": "문서번호 KFS-1-2026-0001"}}
    got = propose(Path("KFS-1-2026-0001_다운로드.csv"), ds)
    assert got["matched_key"] == "zz_demo"
    assert got["suggest"] == "zz/zz_demo_gj_20260101.csv", \
        "`files:` 항목에서 제안을 못 만든다 — `file` 단수만 읽는다"


def test_no_singular_file_reader_in_the_two_consumers() -> None:
    pat = re.compile(r'\.get\(\s*"file"\s*[,)]')
    for rel in ("src/firelane/inventory.py", "src/firelane/intake_name.py"):
        code = "\n".join(ln for ln in (ROOT / rel).read_text(encoding="utf-8").split("\n")
                         if not ln.lstrip().startswith("#"))
        assert not pat.search(code), f"{rel}: 대장 `file` 단수를 직접 읽는다 — `ledger.files_decl()` 로"
