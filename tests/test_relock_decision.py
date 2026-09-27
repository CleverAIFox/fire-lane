"""재잠금이 필요한가를 **지문이** 답하는가.  (§262 · PLAN #137 닫힘)

★ 2026-09-25 (§258-9). 이 판단이 **PR 본문 산문**에 있었다. 사람이 「재잠금은
  필요하다」라고 적으면 `go.sh` 가 그 줄을 읽어 `--relock` 을 붙였다(§256).
  사람의 기억은 없앴지만 판단은 여전히 글이었고, 그 한 줄을 「이번 세션이 판정
  코드를 안 건드렸다」 기준으로 적었다. `fl.sh` 는 가지를 base 에서 **새로
  짓기** 때문에 기준이 배치 전체여야 했다 — 실패 여덟 중 다섯이 거기서 나왔다.

★ 답은 이미 저장소 안에 있었다. `golden._staleness()` 가 잠긴 코드 지문과 지금
  코드 지문을 견준다. 없던 것은 **그것을 물어보는 입구**뿐이었다.

★ 여기서 재는 것은 지문 계산이 아니라 **rc 규약**이다 — `fl.sh` 가 그 rc 하나로
  `--relock` 을 붙일지 정하므로, 방향이 뒤집히면 재잠금이 필요한 배치가 조용히
  안 잠기거나(거짓 초록) 안 바뀐 배치가 20분 재빌드를 돈다.

IN    tools/golden.py 의 `stale` 하위명령 · tools/fl.sh
OUT   없음
밖    지문이 **옳은가**는 `golden selftest` 소관이다. 여기서는 「어긋남이 있다 →
      rc 1」 · 「없다 → rc 0」 두 방향과, `fl.sh` 가 그 rc 를 실제로 읽는가만 본다.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def g():
    spec = importlib.util.spec_from_file_location("golden_relock", ROOT / "tools" / "golden.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m          # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    return m


def test_no_drift_means_no_relock(g, monkeypatch, capsys):
    monkeypatch.setattr(g, "_staleness", lambda: [])
    assert g.cmd_stale(None) == 0
    assert "불필요" in capsys.readouterr().out


def test_drift_means_relock(g, monkeypatch, capsys):
    monkeypatch.setattr(g, "_staleness", lambda: ["★ 변경  src/firelane/seg/width.py"])
    assert g.cmd_stale(None) == 1
    out = capsys.readouterr().out
    assert "재잠금이 필요하다" in out
    assert "width.py" in out, "무엇이 어긋났는지 안 말한다 — 사람이 판단을 못 되짚는다"


def test_a_missing_lock_is_not_a_quiet_no(g, monkeypatch):
    """★ 잠근 지문이 없으면 「재잠금 불필요」가 **아니다.** 조용한 0 은 거짓 초록이다."""
    monkeypatch.setattr(g, "GOLD", ROOT / "없는폴더")
    assert g.cmd_stale(None) == 1


def test_fl_sh_asks_the_fingerprint_not_the_prose():
    """★ 입구를 만들어 놓고 `fl.sh` 가 안 부르면 §258-9 가 그대로다.

    산문(`--relock` 플래그)은 **켜는 쪽으로만** 남는다 — 지문이 필요하다고
    하면 플래그가 없어도 잠그고, 사람이 굳이 붙이면 그것도 존중한다.
    """
    lines = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8").splitlines()
    # ★ **조건 자리**를 짚는다. 처음엔 「`golden.py stale` 이라는 글자가 있는가」로
    #   썼는데, 판단하는 호출을 `true` 로 갈아도 아래 출력용 호출이 남아서 통과했다
    #   — 주입이 잡았다. 있는 것과 **그것으로 정하는 것**은 다르다.
    ask = [i for i, ln in enumerate(lines)
           if re.match(r"\s*(el)?if\b.*golden\.py stale", ln)]
    assert ask, (
        "`fl.sh` 가 재잠금 여부를 **지문에 묻는 조건문**이 없다 — "
        "판단이 아직 PR 본문 산문이다(§258-9)")
    near = "\n".join(lines[ask[0]:ask[0] + 8])
    assert re.search(r"\bRELOCK=1\b", near), (
        "물어보기만 하고 그 답으로 `RELOCK` 을 안 올린다 — 장식이다\n" + near)
