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
import re
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



def _rules_table(master: str) -> dict[str, dict]:
    """MASTER §12-1 룰셋 표를 {이름: {approvals, codeowners}} 로.

    ★ 헤더 `| 룰셋 | 대상 | 승인 | Code Owners |` 를 찾아 **열 이름으로**
      자리를 잡는다. 열 순서가 바뀌어도 값이 엉뚱한 칸에서 읽히지 않는다.
      `—` 는 꺼짐 · 해당 없음이다. 이름이 `—` 인 행(`feat/**`)은 룰셋이 아니다.
    """
    out: dict[str, dict] = {}
    cols: list[str] | None = None
    for line in master.splitlines():
        if not line.startswith("|"):
            if cols is not None and out:
                break
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if cols is None:
            if cells[:1] == ["룰셋"] and "승인" in cells and "Code Owners" in cells:
                cols = cells
            continue
        if set(cells[0]) <= set("-: "):
            continue
        row = dict(zip(cols, cells, strict=True))   # 칸 수가 헤더와 다르면 표가 깨진 것이다
        name = row.get("룰셋", "")
        if not name or name == "—":
            continue
        ap = row.get("승인", "")
        co = row.get("Code Owners", "")
        out[name] = {"approvals": int(ap) if ap.isdigit() else None,
                     "codeowners": co not in ("—", "", "끔", "off")}
    return out


def test_rules_table_approvals_and_codeowners_match_expect():
    """승인 수 · Code Owners 가 `EXPECT` 와 MASTER §12-1 표에서 같은가.

    ★ 2026-09-16. 위 검사는 이름 · 대상 · 머지 방식 **문자열이 있는가**만
      봤다. 승인 수와 Code Owners 는 비교 대상이 아니라 갈려도 초록이었다.
      실제로 갈려 있었다 — 2026-09-03 감사에서 사본 셋이 `release` 를
      \"승인 1 + Code Owners\" 로 적었고 `EXPECT` 는 `codeowners: False` 였다
      (DECISIONS §108 결정 뒤 사본만 안 따라왔다). 이제 필드 단위로 맞춘다.
    """
    spec = importlib.util.spec_from_file_location(
        "rsc", ROOT / "tools/ruleset_check.py")
    rsc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rsc)

    table = _rules_table((ROOT / "docs/MASTER.md").read_text(encoding="utf-8"))
    assert table, "MASTER §12-1 룰셋 표를 못 읽었다 — 헤더가 바뀌었는가"
    bad = []
    for name, want in rsc.EXPECT.items():
        got = table.get(name)
        if got is None:
            bad.append(f"  {name}: MASTER 표에 행이 없다")
            continue
        if got["approvals"] != want["approvals"]:
            bad.append(f"  {name}: 승인 MASTER {got['approvals']} != EXPECT {want['approvals']}")
        if got["codeowners"] != want["codeowners"]:
            bad.append(f"  {name}: Code Owners MASTER {got['codeowners']} "
                       f"!= EXPECT {want['codeowners']}")
    assert not bad, ("룰셋 승인 · Code Owners 가 갈린다:\n" + "\n".join(bad)
                     + "\n\n  정본은 tools/ruleset_check.py 의 EXPECT 다.")


def test_rules_table_probe_is_alive():
    """카나리아 — 표 파서가 실제로 값을 읽는가. **양성 대조다.**

    ★ 파서가 죽으면 표가 `{}` 가 되고, 위 검사는 \"행이 없다\" 로 울거나
      헤더 문구 하나에 조용히 무너진다. 합성 표로 읽기 · 어긋남 검출을
      둘 다 확인한다(DECISIONS §159).
    """
    probe = ("앞 문단\n\n"
             "| 룰셋 | 대상 | 승인 | Code Owners | 필수 검사 | 머지 방식 |\n"
             "|---|---|---|---|---|---|\n"
             "| `release` | `refs/heads/main` | 1 | ✓ | shared | Merge |\n"
             "| `trunk` | `refs/heads/dev` | 0 | — | shared | Merge |\n"
             "| — | `feat/**` | — | — | — | — |\n\n뒤 문단\n")
    got = _rules_table(probe)
    assert got == {"release": {"approvals": 1, "codeowners": True},
                   "trunk": {"approvals": 0, "codeowners": False}}, got


def test_generated_has_components():
    """도식이 `<pre>` 로 흘러나오지 않는가.

    ★ ASCII 를 그대로 넣으면 md 원문과 똑같아 보인다. 그것은 뷰어이지
      렌더가 아니다. 트리·방향·룰셋 카드가 컴포넌트로 나와야 한다.
    """
    if not GEN.exists():
        pytest.skip("아직 생성 전이다")
    doc = GEN.read_text(encoding="utf-8")
    # ★ 2026-09-02. 종전에는 `tree` · `flow` · `cards` · 각주 넷을 찾았다.
    #   그것은 f-string 렌더가 §12 전체를 그리던 시절의 컴포넌트다. 지금은
    #   `playbook.html` 이 템플릿이고 카드 모양은 거기 있으며, 렌더러는
    #   `data-fill` 자리에만 끼운다(§105).
    #
    #   ★ 취지는 같다 — **주입이 실제로 일어났는가.** 자리는 있는데 비어
    #     있으면 하네스가 안 돈 것이고, 그것이 옛 `<pre>` 흘러내림과 같은
    #     실패다.
    fills = re.findall(r'data-fill="([^"]+)"(.*?)</div>', doc, re.S)
    assert fills, (
        "템플릿에 data-fill 자리가 없다 — playbook.html 이 템플릿이고\n"
        "  tools/render_workflow.py 의 fill() 이 거기에 끼운다(DECISIONS §105).")
    empty = [num for num, body in fills if len(body.strip()) < 40]
    assert not empty, (
        f"data-fill 자리가 비었다 — {', '.join('§' + x for x in empty)}\n"
        "  하네스가 안 돌았거나 그 절이 §12-0 색인 밖이다.")
