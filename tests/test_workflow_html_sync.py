#!/usr/bin/env python3
"""
test_workflow_html_sync.py — 협업 방침 화면이 MASTER §12 와 같은가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-31. `docs/workflow.html` 을 손으로 썼다. 그 순간 규약 정본이 둘이
됐고, 같은 날 `MASTER §12-1` 만 낡은 채로 `dev` 흡수 머지를 통과했다 —
작업 하나가 소리 없이 사라졌고 아무도 몰랐다.

종전에는 두 문서의 문자열을 여덟 갈래로 대조했다. **그 대조 자체가 낡았다** —
한쪽에 새 절이 생기면 검사가 그것을 모른다.

★ 사본을 대조로 지키는 것보다 **사본을 만들지 않는 것**이 싸다.
  이제 `web/workflow.html` 은 `tools/render_workflow.py` 가 만드는 생성물이고,
  이 검사는 "재생성 결과와 같은가" 하나만 본다(R2).

IN    docs/MASTER.md §12 · tools/render_workflow.py
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "web/workflow.html"


def _mod():
    spec = importlib.util.spec_from_file_location(
        "rw", ROOT / "tools/render_workflow.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_generated_matches_master():
    """재생성 결과가 커밋된 것과 같은가.

    다르면 둘 중 하나다 — MASTER §12 를 고치고 재생성을 안 했거나,
    생성물을 손으로 고쳤거나. 어느 쪽이든 정본은 MASTER 다.
    """
    if not GEN.exists():
        pytest.skip("아직 생성 전이다")
    m = _mod()
    # ★ 2026-09-02. 종전에는 `render(classify(section12(...)))` 로
    #   **내부를 직접 조립**했다. 파이프라인이 바뀌면 이 줄도 같이 고쳐야
    #   했고 실제로 상황별 재편에서 터졌다. 검사가 구현을 알면 구현을
    #   못 바꾼다. 조립은 `build()` 하나이고 검사는 그것만 부른다.
    want = m.build()
    assert GEN.read_text(encoding="utf-8") == want, (
        "web/workflow.html 이 MASTER §12 와 다르다.\n"
        "  uv run python tools/render_workflow.py  로 재생성하라.\n"
        "  손으로 고쳤다면 그 수정을 MASTER §12 로 옮겨라 —\n"
        "  이 파일은 생성물이고 다음 배포에 덮인다.")


def test_no_handwritten_copy():
    """`docs/workflow.html` 이 되살아나지 않았는가.

    ★ 그 파일이 정본이던 시절의 잔재다. 다시 만들면 사본이 둘이 되고,
      2026-08-31 에 그래서 한쪽이 조용히 낡았다.
    """
    old = ROOT / "docs/workflow.html"
    assert not old.exists(), (
        "docs/workflow.html 이 다시 생겼다.\n"
        "  정본은 docs/MASTER.md §12 이고 화면은 web/workflow.html 이 생성물이다.")


def test_rules_table_agrees_with_ruleset_check():
    """룰셋 방침이 `EXPECT` · MASTER §12-1 두 곳에서 같은가.

    ★ 실물과 대조하는 것은 `tools/ruleset_check.py` 뿐이므로 그쪽이 정본이다.
      MASTER 는 사람이 읽는 표이며, 갈리면 여기서 운다.
    """
    spec = importlib.util.spec_from_file_location(
        "rsc", ROOT / "tools/ruleset_check.py")
    rsc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rsc)

    master = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    bad = []
    for name, want in rsc.EXPECT.items():
        if name not in master:
            bad.append(f"  MASTER §12-1 에 룰셋 이름 `{name}` 이 없다")
        if want["ref"] not in master:
            bad.append(f"  MASTER §12-1 에 대상 `{want['ref']}` 이 없다")
        for meth in want["merge"]:
            if meth.lower() not in master.lower():
                bad.append(f"  MASTER §12-1 에 머지 방식 `{meth}` 이 없다 ({name})")
    assert not bad, (
        "룰셋 방침이 갈린다:\n" + "\n".join(sorted(set(bad))) +
        "\n\n  정본은 tools/ruleset_check.py 의 EXPECT 다.")


def test_generated_has_components():
    """도식이 `<pre>` 로 흘러나오지 않는가.

    ★ ASCII 를 그대로 넣으면 md 원문과 똑같아 보인다. 그것은 뷰어이지
      렌더가 아니다. 트리·방향·룰셋 카드가 컴포넌트로 나와야 한다.
    """
    if not GEN.exists():
        pytest.skip("아직 생성 전이다")
    doc = GEN.read_text(encoding="utf-8")
    for cls, what in (("tree", "브랜치 트리"), ("flow", "방향 도식"),
                      ("cards", "룰셋 카드"), ("details class=\"why\"", "각주")):
        assert f'class="{cls}"' in doc or cls in doc, (
            f"{what} 컴포넌트가 없다 — 파서가 실패해 <pre> 로 떨어졌다.\n"
            "  tools/render_workflow.py 의 as_tree · as_flow · as_rules 를 보라.")
