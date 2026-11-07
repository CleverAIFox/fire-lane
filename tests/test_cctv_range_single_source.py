"""`CCTV_RANGE` 의 숫자는 `seg/params.py` 한 곳에만 산다.  (감사 1-6 · Zm20)

2026-10-10 에 25.0 → 19.0 으로 내렸는데 다섯 자리가 옛 25 를 말한 채 남았다.
같은 수를 문장 속에 박아 두면 상수를 고칠 때 문장이 안 따라온다 — 그래서
이 시험은 **정본 값을 문장에서 찾는 것이 아니라**, 상수를 말하는 줄에
정본이 아닌 숫자가 붙어 있는지 본다.

IN    이 파일의 대상 모듈 · 실물
OUT   없음 (검사)
PARAM 없음
밖    **`CCTV_RANGE` 가 옳은 값인가**는 안 본다 — 정본은 `seg/params.py` 이고 값은 측정이 정한다. 문장 속 숫자가 낡았는지만 본다.
"""
from __future__ import annotations

import re
from pathlib import Path

from firelane.seg.params import CCTV_RANGE

ROOT = Path(__file__).resolve().parents[1]

#: CCTV 유효범위를 말하던 다섯 자리 (+ 그림 기본값)
SITES = (
    "src/firelane/publish_web.py",
    "src/firelane/guards.py",
    "tools/figures/value.py",
    "tools/desk_check.py",
    "src/firelane/seg/report.py",
)

#: 「CCTV_RANGE 25.0」 · 「CCTV ... 25m」 · `cctv_dist_m ... <= 25` · `get("CCTV_RANGE", 25.0)`
_STALE = re.compile(
    r"CCTV_RANGE[^\n]{0,8}\b25(\.0)?\b"
    r"|CCTV[^\n]{0,12}\(?\b25(\.0)?\s*m\b"
    r"|cctv_dist_m[^\n]{0,60}<=\s*25\b"
    r"|반경 25m")


def test_no_site_states_the_old_cctv_range() -> None:
    assert CCTV_RANGE != 25.0, "이 시험의 전제 — 정본이 25 면 옛 수와 구별이 안 된다"
    hits = []
    for rel in SITES:
        for n, ln in enumerate((ROOT / rel).read_text(encoding="utf-8").split("\n"), 1):
            if _STALE.search(ln):
                hits.append(f"{rel}:{n}: {ln.strip()[:90]}")
    assert not hits, "옛 CCTV 유효범위(25)를 말한다:\n  " + "\n  ".join(hits)


def test_schema_text_follows_the_constant() -> None:
    """서술 문자열은 상수에서 **만든다** — 숫자를 손으로 적지 않는다."""
    from firelane.seg import report

    src = (ROOT / "src/firelane/seg/report.py").read_text(encoding="utf-8")
    m = re.search(r'"cv_feasible":\s*(f?)"([^"]*)"', src)
    assert m, "cv_feasible 서술을 못 찾았다"
    assert m.group(1) == "f" and "{CCTV_RANGE" in m.group(2), \
        "cv_feasible 서술이 f-문자열로 상수에서 만들어지지 않는다"
    assert report.CCTV_RANGE == CCTV_RANGE


def test_figure_does_not_invent_a_default() -> None:
    """그림이 정본을 못 읽었을 때 25 를 지어내지 않는다 — 크게 운다."""
    src = (ROOT / "tools/figures/value.py").read_text(encoding="utf-8")
    assert 'p.get("CCTV_RANGE"' not in src
