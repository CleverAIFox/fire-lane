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
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _dms():
    spec = importlib.util.spec_from_file_location("dms_rawdiff", ROOT / "tools/dms.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def dms(tmp_path, monkeypatch):
    m = _dms()
    monkeypatch.setattr(m, "STATE", tmp_path)
    monkeypatch.setattr(m, "raw_print", lambda: {"gjcity_road": ["aaa"]})
    return m


# ★ 2026-09-20 (W4-4). `code.files` 가 **개수에서 파일별 지문으로** 바뀌었다.
#   개수만으로는 「무엇이 바뀌었나」를 못 말한다 — 고치기만 하면 수는 늘 같다.
FILES = {"src/firelane/segments.py": "aaa", "sources.yaml": "bbb"}


def _seal(m, tmp_path, **rec):
    base = {"commit": "abc1234", "raw": {"gjcity_road": ["aaa"]},
            "code": {"sha256": "c0de", "files": dict(FILES)}}
    base.update(rec)
    (tmp_path / m.SEAL).write_text(json.dumps(base), encoding="utf-8")


def test_same_raw_and_code_skips(dms, tmp_path, monkeypatch):
    """둘 다 같으면 0 — 생략이 살아 있다. **이것이 없으면 아래 셋은 무의미하다.**"""
    _seal(dms, tmp_path)
    monkeypatch.setattr(dms, "code_print", lambda: {"sha256": "c0de", "files": dict(FILES)})
    assert dms.cmd_rawdiff() == 0


def test_code_change_alone_forces_full_run(dms, tmp_path, monkeypatch, capsys):
    """★ 핵심. raw 는 같고 코드만 다르면 1 이어야 한다."""
    _seal(dms, tmp_path)
    monkeypatch.setattr(dms, "code_print",
                        lambda: {"sha256": "beef",
                                 "files": {**FILES, "src/firelane/segments.py": "NEW"}})
    assert dms.cmd_rawdiff() == 1
    out = capsys.readouterr().out
    assert "코드가 봉인과 다르다" in out
    assert "git diff --stat abc1234" in out, "어디가 바뀌었는지 볼 명령을 안 준다"


def test_old_seal_without_code_forces_full_run(dms, tmp_path, monkeypatch):
    """코드 지문이 없는 옛 봉인은 모르는 것이다 — 모르면 안 건너뛴다."""
    _seal(dms, tmp_path, code=None)
    monkeypatch.setattr(dms, "code_print", lambda: {"sha256": "c0de", "files": dict(FILES)})
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
    assert a and len(a["files"]) == 2, a     # web/ 은 파이프라인 코드가 아니다
    assert set(a["files"]) == {"sources.yaml", "src/firelane/seg/scope.py"}, a

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


def test_code_diff_names_the_file_that_moved(dms, tmp_path, monkeypatch, capsys):
    """**무엇이 바뀌었는지 말하는가** (W4-4 · DECISIONS §203).

    ★ 종전 출력은 「파일 3 → 3」이었다. 고치기만 하면 수는 언제나 같으므로
      **정보가 0인 줄**이었고, 사람은 `git diff --stat` 을 손으로 쳐서
      범위 전체를 다시 훑어야 했다. 바로 아래 `raw` 블록은 같은 상황에서
      키별로 신설·변경·삭제를 말한다 — **같은 함수 안에서 한쪽만 말을 못 했다.**
      무엇이 바뀌었는지 못 말하는 봉인은 봉인이 아니다.
    """
    _seal(dms, tmp_path)
    monkeypatch.setattr(dms, "code_print", lambda: {
        "sha256": "beef",
        "files": {"src/firelane/segments.py": "CHANGED",   # 변경
                  "tools/verify.sh": "ccc"}})              # 신설 (sources.yaml 삭제)
    assert dms.cmd_rawdiff() == 1
    out = capsys.readouterr().out
    assert "변경  src/firelane/segments.py" in out, out
    assert "신설  tools/verify.sh" in out, out
    assert "삭제  sources.yaml" in out, out
    assert "신설 1 · 변경 1 · 삭제 1" in out, out


def test_old_seal_with_counted_files_still_reads(dms, tmp_path, monkeypatch, capsys):
    """옛 봉인(`files` 가 개수)을 만나도 죽지 않는가.

    ★ `SEAL.json` 은 커밋돼 있다. 모양을 바꾼 날, 아직 안 다시 찍은 봉인이
      트리에 남아 있다 — 그것을 읽다 터지면 **생략 판정 대신 예외**가 나고,
      `verify.sh` 의 「파이프라인 전량」 단계가 통째로 빨개진다.
      모르면 안 건너뛰는 것이 규율이지, 모르면 죽는 것이 규율이 아니다.
    """
    _seal(dms, tmp_path, code={"sha256": "c0de", "files": 3})
    monkeypatch.setattr(dms, "code_print", lambda: {"sha256": "beef", "files": dict(FILES)})
    assert dms.cmd_rawdiff() == 1
    out = capsys.readouterr().out
    assert "옛 봉인이라 파일별 지문이 없다" in out, out
    assert "파일 3 → 2" in out, out
