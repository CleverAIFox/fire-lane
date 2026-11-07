"""`tools/encoding_check.py --fix` 가 백업을 **봉인 층 밖**에 쓴다.  (Zm30 · DECISIONS §575)

IN    tools/encoding_check.py
OUT   없음 (검사)
PARAM 없음
밖    고친 결과가 옳은가(BOM · CRLF · 개행)는 안 본다 — 백업이 어디로 가는가만 본다.

★ 왜 — `fix()` 가 고칠 CSV 옆에 `<이름>.csv.bak_enc` 를 썼다. `data/field` 는 사람이 만든 봉인 층이라 그 옆의 새 파일이 대장 검사
  (`doc_fsck`)와 봉인 검사(`fieldseal`)를 걸었다. 실제로 `naver_width_2610.csv.bak_enc` 가 2026-10-23 부터 남아 대장 시험을 빨갛게 했다.
  백업은 `paths.INTERIM`(탐색 · 대조 산출물 · 커밋 안 함 · 지워도 되는 층)의 `encoding_backup/` 으로 간다.
"""
from __future__ import annotations

from pathlib import Path

import encoding_check as E
import pytest


def _crlf_csv(tmp_path: Path) -> tuple[Path, bytes]:
    field = tmp_path / "data" / "field"
    field.mkdir(parents=True)
    p = field / "x.csv"
    b = b"a,b\r\n1,2\r\n"
    p.write_bytes(b)
    return p, b


def test_fix_creates_no_new_file_in_the_sealed_field_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p, b = _crlf_csv(tmp_path)
    bk = tmp_path / "interim" / "encoding_backup"
    monkeypatch.setattr(E, "backup_root", lambda: bk, raising=False)
    assert E.fix(p, b) is True
    assert sorted(x.name for x in p.parent.iterdir()) == ["x.csv"], "data/field 안에 새 파일이 생겼다"
    assert p.read_bytes() == b"a,b\n1,2\n", "고친 결과가 LF 여야 한다"


def test_the_backup_is_written_outside_and_keeps_the_original_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p, b = _crlf_csv(tmp_path)
    bk = tmp_path / "interim" / "encoding_backup"
    monkeypatch.setattr(E, "backup_root", lambda: bk, raising=False)
    E.fix(p, b)
    saved = list(bk.rglob("*.bak_enc"))
    assert len(saved) == 1 and saved[0].read_bytes() == b, "원본 바이트가 백업에 그대로 있어야 한다"
    assert tmp_path / "data" / "field" not in saved[0].parents


def test_the_default_backup_root_is_the_interim_layer() -> None:
    from firelane.paths import INTERIM
    assert E.backup_root() == INTERIM / "encoding_backup"


def test_the_detector_that_decides_what_to_fix_is_silent_on_clean_text_and_cries_on_crlf(tmp_path: Path) -> None:
    """판별식 카나리아 — 백업이 어디로 가든 **무엇을 고칠지** 가르는 `check()` 가 살아 있다."""
    clean, dirty = tmp_path / "a.csv", tmp_path / "b.csv"
    clean.write_bytes(b"a,b\n1,2\n")
    dirty.write_bytes(b"a,b\r\n1,2\r\n")
    assert not E.check(clean)[0]
    assert "CRLF" in E.check(dirty)[0]
