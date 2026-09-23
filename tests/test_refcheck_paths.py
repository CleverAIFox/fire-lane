#!/usr/bin/env python3
"""
test_refcheck_paths.py — 문서의 경로 표기 검사가 **무엇을 넘기는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-24 (PLAN §1 #23 닫힘 · DECISIONS §233). `refcheck ⑦` 이 문서에
  적힌 경로가 실재하는지 본다. 그런데 넘겨야 할 것 셋을 안 넘겼고, 그래서
  **경고 일곱이 상시로 떠 있었다.** 상시 경고는 아무도 안 읽는다.

      ① 기계마다 있는 파일   `web/navi/.env.local` — gitignore 된 자리다
      ② 예시 이름           `tools/x.py 를 참고할 것` — 자리표다
      ③ 「그때 그랬다」       `종전` · `당시` · `옛` 이 든 줄

★ ①을 고치다 **보안 결함이 나왔다** — `.gitignore` 가 `.env` 만 막고
  `.env.local` 을 안 막았다. 그 파일은 `VITE_MAPBOX_TOKEN` 이 사는 자리다.

★ 넘기는 규칙은 **넓어지는 쪽으로 망가진다.** 넓어지면 죽은 참조가
  조용히 통과하고, 그것이 이 검사가 막으려던 바로 그것이다. 그래서
  넘기는 갈래마다 **넘기면 안 되는 짝**을 같이 든다.

IN    tools/refcheck.py · .gitignore
OUT   없음 (검사)
밖    **⑦ 밖의 갈래는 안 본다.** `refcheck` 는 대장·실물·코드 하드코딩까지
      아홉 갈래를 보고, 여기서 드는 것은 문서 경로 표기 하나다.
      그리고 `tools/*.sh` 여섯은 **예시 이름 목록의 대조 대상이 아니다** —
      그 목록은 `Path(m).stem` 으로 비교하고 셸 도구 이름(`fl`·`verify` …)은
      예시 낱말(`x`·`foo` …)과 겹치지 않는다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import refcheck

ROOT = Path(__file__).resolve().parents[1]


def _rows():
    return refcheck.check()


DOCS = {"MASTER.md", "PLAN.md", "DECISIONS.md", "README.md"}


def test_no_warning_is_standing():
    """**문서 경로** 경고가 상시로 떠 있지 않은가.

    ★ ⑦ 갈래만 본다. 나머지 갈래는 레이크를 읽으므로 기계마다 답이 다르고,
      그것까지 여기서 들면 레이크 없는 기계에서 이 시험이 빨개진다 —
      「범위가 이름보다 넓다」 족(§226).
    """
    warn = [f"{w} {m}" for lv, w, m in _rows()
            if lv == refcheck.WARN and w in DOCS]
    assert not warn, "문서 경로 경고가 상시로 떠 있다:\n  " + "\n  ".join(warn)


def test_env_local_is_ignored_by_git():
    """토큰이 사는 자리가 `.gitignore` 에 있는가. **없으면 커밋된다.**"""
    for rel in ("web/navi/.env.local", ".env.local", "web/navi/.env.production.local"):
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT)
        assert r.returncode == 0, (
            f"{rel} 이 gitignore 밖이다 — `git add -A` 로 토큰이 커밋된다.\n"
            "  막히는 층이 `commit_policy` 하나뿐이면 `--no-verify` 로 뚫린다(MASTER §12-9).")


def test_ignored_probe_is_alive():
    """`_ignored` 가 **아무거나 참**이면 검사가 통째로 죽는다."""
    assert refcheck._ignored("web/navi/.env.local") is True
    assert refcheck._ignored("README.md") is False
    assert refcheck._ignored("docs/MASTER.md") is False


def test_history_keywords_do_not_swallow_a_live_path():
    """「그때 그랬다」 낱말이 든 줄이라도 **지금 있는 경로**는 넘기면 안 된다.

    ★ 넘기는 규칙은 *없는* 경로에만 걸린다 — 있는 경로는 애초에 검사 대상이
      아니다. 이 시험은 그 순서가 뒤집히지 않았는지를 든다.
    """
    src = (ROOT / "tools" / "refcheck.py").read_text(encoding="utf-8")
    i = src.index("_gone = {ln for ln")
    head = src[:i]
    assert "if (ROOT / m).exists():" in src[i - 900:i + 900], (
        "존재 확인이 넘기기보다 **뒤**로 갔다 — 있는 경로까지 낱말 하나로 넘어간다")
    del head


def test_example_names_are_only_placeholders():
    """예시 이름 목록이 **실제 도구 이름을 삼키지 않는가.**"""
    src = (ROOT / "tools" / "refcheck.py").read_text(encoding="utf-8")
    i = src.index('Path(m).stem in (')
    names = src[i:src.index(")", i)]
    real = [p.stem for p in (ROOT / "tools").glob("*.py")]
    hit = [n for n in real if f'"{n}"' in names]
    assert not hit, f"예시 이름이 실제 도구를 삼킨다: {hit}"


def test_plan_row_23_is_closed_and_its_number_is_reserved():
    """#23 이 닫혔고 번호는 비워 뒀는가 — 번호는 영구 식별자다(§0-2)."""
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    assert "| 23 | 문서의 죽은 경로 참조 |" not in plan, "#23 이 아직 있다"
    assert "#23" in plan.split("결번 —")[1].split("\n")[0], (
        "결번 대장에 #23 이 없다 — 번호를 다시 쓰면 밖의 인용이 다른 행을 가리킨다")


def test_refcheck_still_fails_on_a_real_dead_reference():
    """★ 빈 그물인가. **없는 경로**를 넣으면 실제로 우는가."""
    doc = ROOT / "docs" / "MASTER.md"
    keep = doc.read_text(encoding="utf-8")
    try:
        doc.write_text(keep + "\n\n`tools/zq7_absent.py` 가 이것을 든다.\n",
                       encoding="utf-8")
        warn = [m for lv, w, m in refcheck.check()
                if lv == refcheck.WARN and w in DOCS]
        assert any("zq7_absent" in m for m in warn), (
            f"합성 죽은 참조를 못 잡았다 — 프로브가 죽었다: {warn}")
    finally:
        doc.write_text(keep, encoding="utf-8")


def test_module_runs_as_a_script():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "refcheck.py")],
                       capture_output=True, text=True, cwd=ROOT)
    assert "죽은 참조" in r.stdout, r.stdout + r.stderr
