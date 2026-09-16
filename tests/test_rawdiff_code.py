#!/usr/bin/env python3
"""
test_rawdiff_code.py — 전량 생략이 **코드 변경**에도 무너지는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-16. `verify.sh` 의 `파이프라인 전량` 은 `dms.py rawdiff` 가 0 을
내면 생략한다. 그런데 rawdiff 는 **raw 만** 봉인과 대조했다. 근거 문장은
*"raw 가 봉인과 같으면 판정도 같다"* 였다.

판정은 raw 와 코드의 함수다. 판정 범위나 중심선 보정처럼 **코드만 바꾸는
배치**는 raw 가 같아 전량이 생략되고, 옛 산출물이 남고, `golden` 은 옛
산출물을 옛 지문과 맞춰 초록을 낸다. `커밋된 web/data 가 최신인가` 도
재실행이 없었으니 초록이다 — **변경이 전부 초록으로 통과한다**(DECISIONS §164).

★ 이 검사의 대상은 "생략 판정이 옳은가" 이고, 생략은 **실패로 안 보인다.**
  그래서 양쪽을 다 확인한다 — 같으면 0(생략이 산다), 다르면 1(전량이 돈다).
  한쪽만 보면 항상 1 을 내는 고장 난 rawdiff 도 통과한다(DECISIONS §159).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _dms():
    spec = importlib.util.spec_from_file_location("dms_rawdiff", ROOT / "tools/dms.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def dms(tmp_path, monkeypatch):
    m = _dms()
    monkeypatch.setattr(m, "STATE", tmp_path)
    monkeypatch.setattr(m, "raw_print", lambda: {"gjcity_road": ["aaa"]})
    return m


def _seal(m, tmp_path, **rec):
    base = {"commit": "abc1234", "raw": {"gjcity_road": ["aaa"]},
            "code": {"sha256": "c0de", "files": 3}}
    base.update(rec)
    (tmp_path / m.SEAL).write_text(json.dumps(base), encoding="utf-8")


def test_same_raw_and_code_skips(dms, tmp_path, monkeypatch):
    """둘 다 같으면 0 — 생략이 살아 있다. **이것이 없으면 아래 셋은 무의미하다.**"""
    _seal(dms, tmp_path)
    monkeypatch.setattr(dms, "code_print", lambda: {"sha256": "c0de", "files": 3})
    assert dms.cmd_rawdiff() == 0


def test_code_change_alone_forces_full_run(dms, tmp_path, monkeypatch, capsys):
    """★ 핵심. raw 는 같고 코드만 다르면 1 이어야 한다."""
    _seal(dms, tmp_path)
    monkeypatch.setattr(dms, "code_print", lambda: {"sha256": "beef", "files": 3})
    assert dms.cmd_rawdiff() == 1
    out = capsys.readouterr().out
    assert "코드가 봉인과 다르다" in out
    assert "git diff --stat abc1234" in out, "어디가 바뀌었는지 볼 명령을 안 준다"


def test_old_seal_without_code_forces_full_run(dms, tmp_path, monkeypatch):
    """코드 지문이 없는 옛 봉인은 모르는 것이다 — 모르면 안 건너뛴다."""
    _seal(dms, tmp_path, code=None)
    monkeypatch.setattr(dms, "code_print", lambda: {"sha256": "c0de", "files": 3})
    assert dms.cmd_rawdiff() == 1


def test_unmeasurable_code_forces_full_run(dms, tmp_path, monkeypatch):
    _seal(dms, tmp_path)
    monkeypatch.setattr(dms, "code_print", lambda: None)
    assert dms.cmd_rawdiff() == 1


def test_code_print_moves_with_content_not_with_junk(tmp_path):
    """실제 git 저장소에서 — 추적 파일 한 줄이면 움직이고, 찌꺼기로는 안 움직인다."""
    m = _dms()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "src/firelane/seg").mkdir(parents=True)
    (tmp_path / "src/firelane/seg/scope.py").write_text("BUFFER_M = 0\n", encoding="utf-8")
    (tmp_path / "sources.yaml").write_text("layers: {}\n", encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web/app.js").write_text("x\n", encoding="utf-8")
    subprocess.run([*git, "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run([*git, "-C", str(tmp_path), "commit", "-qm", "0"], check=True)

    a = m.code_print(tmp_path)
    assert a and a["files"] == 2, a          # web/ 은 파이프라인 코드가 아니다

    (tmp_path / "src/firelane/seg/__pycache__").mkdir()
    (tmp_path / "src/firelane/seg/__pycache__/scope.pyc").write_bytes(b"junk")
    (tmp_path / "web/app.js").write_text("y\n", encoding="utf-8")
    assert m.code_print(tmp_path) == a, "추적 밖 찌꺼기나 web/ 이 지문을 흔든다"

    (tmp_path / "src/firelane/seg/scope.py").write_text("BUFFER_M = 300\n", encoding="utf-8")
    b = m.code_print(tmp_path)
    assert b["sha256"] != a["sha256"], "판정 범위를 바꿨는데 지문이 그대로다 — 카나리아가 죽었다"

    (tmp_path / "sources.yaml").unlink()
    c = m.code_print(tmp_path)
    assert c["sha256"] != b["sha256"], "추적 파일 삭제가 지문에 안 잡힌다"


def test_seal_records_code_print():
    """봉인이 코드 지문을 **적는가.** 안 적으면 다음 rawdiff 가 영원히 전량을 돈다."""
    src = (ROOT / "tools/dms.py").read_text(encoding="utf-8")
    assert '"code": code_print()' in src
