"""`sweep` 의 레이크 지문 **북마크**가 낡은 것을 재사용하지 않는가.  (§258-17)

★ 왜 이 파일이 있나 (2026-09-26). `sweep` 은 매 실행 레이크 2.5GB 를 처음부터
  다시 해싱했다(30~90초). 이 저장소는 「안 바뀐 것은 다시 안 한다」를 샤드 봉인으로
  이미 하고 있는데 **여기만 그 원리가 없었다.** 사흘 연속 난 `ENOMEM` 을 읽기 버퍼
  크기로 때운 것이 그 증상이다 — 증상을 고치기 전에 「왜 2.5GB 를 매번 읽나」를
  물었어야 했다.

★ **재사용은 위험한 쪽이다.** 내용이 바뀐 파일의 옛 지문을 쓰면 sweep 이
  「이 파일은 레이크에 이미 있다 = 지워도 된다」를 **거짓으로** 말한다. 지우면
  되돌릴 수 없다(§226 의 그 사고 형태). 그래서 이 파일이 재는 것은 「빨라졌나」가
  아니라 **「낡은 것을 재사용하지 않는가」** 다.

IN    tools/sweep.py
OUT   없음
밖    얼마나 빨라지는가는 안 잰다 — 기계마다 다르고, 느린 것은 결함이 아니다.
      `sha()` 의 버퍼 재시도(§258-15)도 여기 밖이다.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sw(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("sweep_bm", ROOT / "tools" / "sweep.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    m.UNREAD.clear()
    monkeypatch.setattr(m, "FP_CACHE", tmp_path / "fp.json")
    return m


def _touch(p: Path, body: bytes, *, mtime: float | None = None) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


# ── ① 북마크가 실제로 재사용되는가 ──────────────────────────────
def test_an_unchanged_file_is_not_hashed_twice(sw, tmp_path):
    f = _touch(tmp_path / "a.bin", b"hello")
    st = f.stat()
    sw._fp_save({"a.bin": [st.st_size, st.st_mtime_ns, "지문하나"]})
    got = sw._fp_load()
    assert got["a.bin"][:2] == [st.st_size, st.st_mtime_ns]
    assert got["a.bin"][2] == "지문하나"


# ── ② **낡은 것을 재사용하지 않는가** — 이쪽이 본체다 ───────────
@pytest.mark.parametrize("how", ["내용과 크기", "mtime 만"])
def test_a_changed_file_invalidates_the_bookmark(sw, tmp_path, how):
    """★ 크기든 mtime 이든 **하나만 달라도** 다시 판다.

    내용이 같은데 mtime 만 바뀌면 헛일을 한 번 한다 — 그것은 안전한 쪽이다.
    반대(내용이 바뀌었는데 재사용)는 「지워도 된다」를 거짓으로 만든다.
    """
    f = _touch(tmp_path / "a.bin", b"hello", mtime=1_000_000)
    old = f.stat()
    sw._fp_save({"a.bin": [old.st_size, old.st_mtime_ns, "옛지문"]})

    if how == "내용과 크기":
        _touch(f, b"hello world", mtime=1_000_000)
    else:
        os.utime(f, (2_000_000, 2_000_000))

    new = f.stat()
    was = sw._fp_load()["a.bin"]
    assert not sw.fp_valid(was, new.st_size, new.st_mtime_ns), \
        f"{how} 가 바뀌었는데 북마크를 유효하다고 한다"
    # 반대편 — 안 바뀌면 유효해야 한다. 아니면 북마크가 아무 일도 안 한다
    assert sw.fp_valid([old.st_size, old.st_mtime_ns, "옛지문"], old.st_size, old.st_mtime_ns)
    assert not sw.fp_valid(None, old.st_size, old.st_mtime_ns)


def test_the_loop_asks_fp_valid_not_its_own_comparison(sw):
    """★ 판단이 **그 자리에서** 쓰이는가. 첫 판은 비교를 루프 안에 인라인으로
    뒀고, 그래서 「mtime 을 무시하고 무조건 재사용」 주입이 안 잡혔다 —
    헬퍼만 재고 판단을 안 쟀다(§258-10 과 같은 형태)."""
    import ast

    src = (ROOT / "tools" / "sweep.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "fp_valid" in called, "`main` 이 제 비교를 쓴다 — 주입이 안 잡힌다"


def test_a_missing_cache_is_not_a_silent_pass(sw, tmp_path):
    """북마크가 없거나 깨졌으면 **전부 다시 판다.** 조용히 빈 결과를 내면
    레이크가 통째로 「없다」가 되고, 그러면 모든 INBOX 파일이 「새것」이 된다."""
    assert sw._fp_load() == {}
    (tmp_path / "fp.json").write_text("{깨진 json", encoding="utf-8")
    assert sw._fp_load() == {}


def test_a_bookmark_that_cannot_be_written_does_not_change_the_answer(sw, tmp_path):
    """못 써도 죽지 않는다 — 다음 실행이 느려질 뿐 판단은 같다."""
    sw.FP_CACHE = tmp_path / "없는폴더" / "x" / "fp.json"
    sw._fp_save({"a": [1, 2, "x"]})          # 예외가 안 나야 한다
    sw.FP_CACHE = tmp_path / "fp.json"


# ── ③ 지문 자체가 옳은가 ────────────────────────────────────────
def test_the_digest_is_a_real_sha256(sw, tmp_path):
    body = b"x" * 300_000                    # 버퍼(256KB)를 넘겨 두 번 읽게 한다
    f = _touch(tmp_path / "big.bin", body)
    assert sw.sha(f) == hashlib.sha256(body).hexdigest()
    assert sw.UNREAD == []


def test_an_unreadable_file_is_recorded_not_swallowed(sw, tmp_path):
    """★ §258-15. 못 읽으면 **어느 파일인지 적고** 넘어간다. 조용히 빠지면
    그 파일이 「레이크에 없다」로 세어진다."""
    assert sw.sha(tmp_path / "없다.bin") is None
    assert len(sw.UNREAD) == 1 and "없다.bin" in sw.UNREAD[0][0]


def test_the_bookmark_shrinks_when_files_disappear(sw, tmp_path):
    """사라진 파일은 북마크에서 빠진다 — 안 그러면 북마크가 영영 자란다.

    `main` 이 이번 실행에서 **본 것만** 다시 쓰는 것으로 그렇게 한다.
    여기서는 그 규약을 글자로 못박는다.
    """
    src = (ROOT / "tools" / "sweep.py").read_text(encoding="utf-8")
    assert "_fp_save(seen)" in src, "이번 실행이 본 것이 아니라 옛 북마크를 그대로 다시 쓴다"
    assert "seen[rel] =" in src


def test_the_cache_is_not_committed():
    """북마크는 **기계마다 다른 파생물**이다. 커밋되면 남의 기계 mtime 을 믿게 된다."""
    import subprocess

    r = subprocess.run(["git", "check-ignore", "-q", ".work/lake_fp.json"],
                       cwd=ROOT, capture_output=True)
    assert r.returncode == 0, ".work/ 가 gitignore 밖이다 — 북마크가 커밋될 수 있다"
    assert json.loads("{}") == {}          # json 임포트가 죽은 참조가 아님을 보인다
