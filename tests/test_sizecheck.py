"""파일 길이 양방향 래칫 — `tools/sizecheck.py` 가 **다섯 갈래로 우는가** (DECISIONS §218-5).

★ 판정기는 순수 함수(`judge`)라 합성 입력으로 부른다. 저장소 실물로는 「지금 초록인가」만
  알 수 있고, 초록은 「검사했다」를 뜻하지 않는다(DECISIONS §199) — 우는 경로를 따로 본다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import sizecheck as sc

ROOT = Path(__file__).resolve().parents[1]
LIM = {"code": 10, "test": 20}


@pytest.mark.parametrize(
    ("counts", "exc", "want"),
    [
        ({"tools/a.py": 11}, {}, "새로 넘었다"),
        ({"src/x/a.py": 13}, {"src/x/a.py": 12}, "늘었다"),
        ({"tools/a.py": 11}, {"tools/a.py": 12}, "11 으로 내려라"),
        ({"tools/a.py": 9}, {"tools/a.py": 12}, "지워라"),
        ({}, {"tools/a.py": 12}, "파일이 없다"),
        ({"tools/a.py": 5}, {"tools/a.py": 8}, "예외가 아니다"),
    ],
    ids=["new-oversize", "grew", "shrank", "under-limit", "gone", "exception-under-limit"],
)
def test_judge_fails_each_way(counts: dict, exc: dict, want: str) -> None:
    bad = sc.judge(counts, exc, LIM)
    assert any(want in b for b in bad), f"「{want}」 로 울어야 하는데 — {bad}"


def test_judge_passes_exact_and_uses_test_limit() -> None:
    """예외와 같은 수 · 시험은 시험 상한(여기 20)을 쓴다 — 정상은 조용하다."""
    assert sc.judge({"tools/a.py": 12, "tests/t.py": 20, "src/b.py": 10},
                    {"tools/a.py": 12}, LIM) == []
    assert sc.judge({"tests/t.py": 21}, {}, LIM), "시험 상한을 넘었는데 안 울었다"


def test_count_matches_wc(tmp_path: Path) -> None:
    """`wc -l` 과 같게 센다 — 끝개행 없는 마지막 줄은 안 센다."""
    p = tmp_path / "a.py"
    p.write_bytes(b"a\nb\nc")
    assert sc.count_lines(p) == 2


def test_repo_is_at_its_recorded_state() -> None:
    """저장소 실물이 EXCEPTIONS 와 같은가 — verify · CI 와 같은 명령으로."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "sizecheck.py")],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:]


def test_selftest_is_green() -> None:
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "sizecheck.py"), "--selftest"],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout[-800:]


def test_limits_live_only_in_sizecheck() -> None:
    """상한 · 예외 수를 부르는 쪽이 인자로 적지 않는다 — 집은 `sizecheck.py` 하나다(W3-11)."""
    for rel in ("tools/verify.sh", ".github/workflows/contract.yml"):
        body = (ROOT / rel).read_text(encoding="utf-8")
        assert "tools/sizecheck.py\n" in body, f"{rel} 가 sizecheck 를 인자 없이 부르지 않는다"
