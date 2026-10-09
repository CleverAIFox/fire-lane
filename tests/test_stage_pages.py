"""
test_stage_pages.py — 배포 준비가 **비었다고 말하는가.**  (DECISIONS §444-4)

★ `STAGED` 가 이 판에서 비었다(`docs/proposal.docx → web/` 한 줄이 은퇴했다).
  빈 표를 **지우지 않는 것**이 규약이고(PLAN §13-3 — 옮길 것은 다시 생긴다)
  그 대가로 `deadcheck ①(상수)` 가 「빈 모음을 도는 검사」로 센다. 그 면제의
  값을 여기서 치른다 — **공백을 말하는가**와 **그물이 살았는가** 둘이다.

밖    **배포를 안 한다** — `--deploy` 가 실제로 지우는지는 CI 에서만 성립한다
      (`GITHUB_ACTIONS` 가 전제다). 여기는 판별식만 본다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "stage_pages_t", ROOT / "tools" / "stage_pages.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def test_the_empty_table_is_spoken(capsys):
    """★ **빈 표가 말을 한다.** 조용하면 「옮겼다」와 「옮길 것이 없다」가 같아진다."""
    sp = _mod()
    assert sp.STAGED == [], "표가 찼다 — 이 시험과 면제를 같이 고쳐라"
    assert sp.main.__doc__ is None or True
    sys.argv = ["stage_pages.py", "--check"]
    assert sp.main() == 0
    out = capsys.readouterr().out
    assert "STAGED 가 비었다" in out, f"공백을 말하지 않는다\n{out}"


def test_the_net_is_alive_while_the_table_is_empty():
    """★ 0건이 죽음이 아님을 **합성 입력으로** 증명한다. 양방향."""
    sp = _mod()
    def no(_rel: str) -> bool:
        return False

    def yes(_rel: str) -> bool:
        return True

    assert sp.staged_faults([("docs/없는것.md", "web/x.md")], no), "없는 정본을 안 문다"
    assert not sp.staged_faults([("docs/있는것.md", "web/x.md")], yes), "있는 정본을 문다"
    assert not sp.staged_faults([], no), "빈 표에서 운다"


def test_the_drop_list_is_real():
    """실물 — 빼라고 적힌 것이 실재한다. 죽은 항목은 **아무것도 안 하고 조용하다.**"""
    sp = _mod()
    assert sp.DEPLOY_DROP, "뺄 것이 0 이다 — 그러면 이 검사가 빈 그물이다"
    bad = sp.drop_faults(sp.DEPLOY_DROP, lambda rel: (ROOT / rel).exists())
    assert not bad, "\n".join(bad)
    assert sp.drop_faults(["web/절대없는것.html"], lambda _r: False), "죽은 항목을 안 문다"
