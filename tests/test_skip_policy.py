"""skip 정책 카나리아 — 판별식과 훅이 **실제로** 분류 밖 skip 을 실패로 바꾸는가.

★ 2026-09-17 (DECISIONS §175). 정책이 문서에만 있으면 51 이 다시 쌓인다.
  판별식은 합성 사유로, 훅은 합성 테스트 파일을 별도 pytest 프로세스로 돌려 흔든다.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import skip_policy as sp

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 17)
TITLES = {"대장 · SSD 디렉토리 구조와 해석기 하나"}


def _j(reason: str, lake: bool = False) -> str | None:
    return sp.judge(reason, lake_attached=lake, today=TODAY, plan_titles=TITLES)


def test_judge_classifies_reasons():
    assert _j("환경skip(도구) — node 없음") is None
    assert _j("환경skip(산출물) — 파이프라인 미실행") is None
    assert _j("환경skip(레이크) — 레이크 미마운트") is None
    assert _j("could not import 'pydantic': No module named 'pydantic'") is None
    assert _j("유예skip — 「대장 · SSD 디렉토리 구조와 해석기 하나」 · 2026-09-10 — L2 대기") is None


def test_judge_rejects_what_hides():
    assert _j("환경skip(레이크) — 레이크 미마운트", lake=True), "레이크 기계의 레이크 skip 은 실패다"
    assert sp.judge("환경skip(산출물) — 파이프라인 미실행", lake_attached=True, today=TODAY,
                    plan_titles=TITLES, outputs_present=True), "산출물이 있는 레이크 기계의 산출물 skip 은 실패다"
    assert not sp.judge("환경skip(산출물) — 파이프라인 미실행", lake_attached=True, today=TODAY,
                        plan_titles=TITLES, outputs_present=False), "clone 직후 레이크 기계는 허용"
    assert _j("랜덤 미사용"), "해당없음은 skip 이 아니다"
    assert _j("got empty parameter set ['x'], function f at t.py:1"), "빈 parametrize 도 해당없음이다"
    assert _j("환경skip — 태그 없음"), "환경skip 은 무엇이 없는지 태그를 단다"
    assert _j("유예skip — 「없는 행」 · 2026-09-10 — x"), "닫힌 PLAN 행을 붙든 유예"
    assert _j("유예skip — 「대장 · SSD 디렉토리 구조와 해석기 하나」 · 2026-08-01 — x"), "21일 넘은 유예"
    assert _j("유예skip — 「대장 · SSD 디렉토리 구조와 해석기 하나」 · 2026-10-01 — x"), "미래 날짜"


def test_plan_titles_are_read():
    """PLAN §1 행 제목을 못 읽으면 모든 유예가 거부된다 — 파서가 살아 있는가."""
    titles = sp.plan_titles()
    assert len(titles) > 20, f"PLAN §1 행 제목 {len(titles)}개 — 표 파서가 죽었다"


def test_hook_turns_unclassified_skip_into_failure(tmp_path):
    """훅 카나리아 — 합성 테스트 셋(분류 밖 · 환경 · 해당없음 빈 parametrize)을 별도 프로세스로 돌린다."""
    t = tmp_path / "test_synth.py"
    t.write_text(
        "import pytest\n"
        "def test_bad():\n    pytest.skip('랜덤 미사용')\n"
        "def test_ok():\n    pytest.skip('환경skip(도구) — 합성')\n"
        "@pytest.mark.parametrize('x', [])\ndef test_empty(x):\n    pass\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "tests"), str(ROOT / "src"),
                                                         os.environ.get("PYTHONPATH", "")]),
           "FIRE_LANE_DATA": ""}
    r = subprocess.run([sys.executable, "-m", "pytest", "-p", "conftest", "-p", "no:cacheprovider",
                        "-q", "-rA", str(t)], cwd=tmp_path, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr
    # 호출 단계 skip 은 failed, 준비 단계 skip(빈 parametrize)은 error 로 나온다 — 둘 다 초록이 아니다
    assert "1 failed, 1 skipped, 1 error" in out, f"훅이 안 걸렸다 — conftest 가 죽었다\n{out[-1500:]}"
    assert "skip 정책 위반" in out


# ── 정적 — 사유가 **쓰인 자리**에서 이미 정책 안인가 ────────────
#
# ★ 2026-09-24 (DECISIONS §238). 지금까지 정책은 **skip 이 실제로 나야** 걸렸다.
#   `conftest` 훅은 보고된 skip 만 보고, 안 타진 갈래는 안 본다. 그래서 정책 밖
#   사유 셋이 **로컬에서는 한 번도 안 타져** 조용히 살아 있었다 —
#
#       tests/test_dest_scope.py:52          .gitignore 된 경계 파일. CI 에만 없다
#       tests/test_generated_families.py:40  git 없는 기계에만
#       tests/test_tile_zoom_agreement.py    타일을 안 구운 기계에만
#
#   셋 다 **CI 에서 처음 타지고 그때 실패로 바뀐다.** 로컬 초록 · CI 빨강이고,
#   그 모양을 §206 이 이 저장소에서 제일 나쁜 것으로 적는다.
#
# ★ 이 검사는 **소스를 읽는다.** 안 타지는 갈래도 글자는 있으므로, 「그날이 와야
#   아는 것」을 오늘 안다. 런타임 훅(위)과 짝이다 — 훅은 동적 사유를, 이쪽은
#   정적 앞머리를 본다. 둘 중 하나만으로는 반이 빈다.
def _skip_literals() -> list[tuple[str, int, str]]:
    """`pytest.skip(...)` · `pytest.xfail(...)` 의 **정적으로 아는 앞머리**.

    f-string 은 고정 부분만 잇고 치환 자리는 `\\x00` 으로 둔다 — 앞머리가
    분류 접두사면 통과이고, 접두사 자리에 치환이 오면 알 수 없으므로 운다.
    """
    import ast
    out = []
    for f in sorted((ROOT / "tests").rglob("*.py")):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(n, ast.Call) or not n.args:
                continue
            fn = n.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else None)
            if name not in ("skip", "xfail"):
                continue
            a = n.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                s = a.value
            elif isinstance(a, ast.JoinedStr):
                s = "".join(v.value if isinstance(v, ast.Constant)
                            and isinstance(v.value, str) else "\x00"
                            for v in a.values)
            else:
                s = "\x00"
            out.append((str(f.relative_to(ROOT)), n.lineno, s))
    return out


def test_every_written_skip_reason_is_already_in_policy():
    """안 타지는 갈래까지 본다 — **그날이 와야 아는 것을 오늘 안다.**"""
    rows = _skip_literals()
    assert len(rows) >= 10, (
        f"`pytest.skip` 자리를 {len(rows)}개만 찾았다 — AST 수집이 죽었다. "
        "실물은 열 곳이 넘는다")
    bad = [f"  {f}:{ln}  {s[:60]!r}" for f, ln, s in rows
           if not (s.startswith("환경skip(") or s.startswith("유예skip — "))]
    assert not bad, (
        "정책 밖 사유가 **쓰여 있다**. 그 갈래가 타지는 기계에서 실패가 된다:\n"
        + "\n".join(bad) + "\n\n"
        "  `환경skip(레이크|산출물|도구) — …` · `유예skip — 「행」 · 날짜 — …` 중 하나.\n"
        "  분류 접두사는 **f-string 의 고정 부분**에 와야 한다 — 치환으로 시작하면 못 본다.")


def test_the_static_scan_bites():
    """★ 빈 그물인가. 셋을 고친 뒤 0건이 되므로 **합성 입력**으로 확인한다."""
    import ast as _ast
    src = _ast.parse('import pytest\npytest.skip("랜덤 미사용")\n')
    call = next(n for n in _ast.walk(src) if isinstance(n, _ast.Call))
    assert call.args[0].value == "랜덤 미사용"
    assert not "랜덤 미사용".startswith("환경skip("), "판별 접두사가 바뀌었다"
    assert "환경skip(산출물) — x 가 없다".startswith("환경skip("), "정상 사유를 거른다"
