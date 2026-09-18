"""golden 코드 지문이 파이썬 버전을 안 타는가 (DECISIONS §185 · G-24).

★ CI 는 3.11 · 사용자 기계는 3.13 이다. 아래 고정 해시가 **두 곳에서 같이 통과해야** 강제가 된다 —
  옛 `ast.dump` 방식은 같은 원문에서 버전마다 다른 값을 냈다.
"""
from __future__ import annotations

import hashlib
import json

import golden

SRC = '''"""모듈 docstring."""
import math

TRUCK      = 3.0   # 정렬 공백 · 주석


def width(a, b=2):
    """함수 docstring."""
    x = f"{a!r:>{b}} · {math.pi:.2f} · {'안' if a else f'{b}'}"
    return (a
            + b), x


class K:
    """클래스 docstring."""

    def m(self):
        return f'{self}'
'''

# ★ 3.11 · 3.12 · 3.13 에서 같은 값인지 샌드박스에서 확인한 뒤 박았다(2026-09-18). 옛 방식은 셋이 달랐다.
PINNED = "4d648c21bdb23a2f"


def _h(src: str) -> str:
    return hashlib.sha256(golden.logic_text(src).encode()).hexdigest()[:16]


def test_logic_text_is_pinned_across_python_versions():
    assert _h(SRC) == PINNED, "logic_text 가 이 파이썬에서 다른 값을 낸다 — 지문이 버전을 탄다(G-24)"


def test_comments_docstrings_blank_lines_and_wrapping_do_not_move_it():
    noise = SRC.replace("# 정렬 공백 · 주석", "# 다른 주석").replace('"""함수 docstring."""', '"""바뀐 설명\n\n    여러 줄."""')
    noise = noise.replace("return (a\n            + b), x", "return (a + b), x").replace("\n\nclass K", "\n\n\n\nclass K")
    assert _h(noise) == _h(SRC)


def test_logic_changes_move_it():
    for a, b in [("TRUCK      = 3.0", "TRUCK      = 3.5"), ("b=2", "b=3"), ("{math.pi:.2f}", "{math.pi:.3f}"),
                 ("return f'{self}'", "return f'{self!r}'")]:
        assert a in SRC
        assert _h(SRC.replace(a, b)) != _h(SRC), f"{a} → {b} 를 못 봤다"


def test_rehash_moves_only_with_legacy_proof(tmp_path, monkeypatch):
    fp = tmp_path / ".code_fingerprint"
    monkeypatch.setattr(golden, "CODE_FP", fp)
    fp.write_text(json.dumps({"all": "0" * 16, "files": {}}) + "\n", encoding="utf-8")
    assert golden.cmd_rehash(None) == 1, "옛 방식 지문이 다른데 옮겼다"
    assert "tokens" not in fp.read_text(encoding="utf-8")

    fp.write_text(json.dumps({"all": golden._legacy_ast_fingerprint(), "files": {}}) + "\n", encoding="utf-8")
    assert golden.cmd_rehash(None) == 0
    d = json.loads(fp.read_text(encoding="utf-8"))
    assert d["method"] == golden.FP_METHOD and d["all"] == golden._logic_fingerprint()[0]
    assert golden.cmd_rehash(None) == 0, "두 번째 rehash 는 할 일 없음으로 끝나야 한다"


def test_lock_writes_method_and_old_method_is_reported(tmp_path, monkeypatch):
    now, per = golden._logic_fingerprint()
    assert json.loads(golden._dump_fp(now, per))["method"] == golden.FP_METHOD
    fp = tmp_path / ".code_fingerprint"
    monkeypatch.setattr(golden, "CODE_FP", fp)
    monkeypatch.setattr(golden, "SEG", tmp_path / "segments.geojson")
    (tmp_path / "segments.geojson").write_text("{}", encoding="utf-8")
    fp.write_text(json.dumps({"all": now, "files": per}) + "\n", encoding="utf-8")     # 값은 같아도 방식 칸이 없다
    out = golden._staleness()
    assert out and "옛 방식" in out[0], "옛 방식 잠금을 조용히 통과시켰다"
