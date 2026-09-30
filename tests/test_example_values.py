"""
test_example_values.py — **도구가 가르치는 예시가 제 관문을 통과하는가.**
(DECISIONS §332 · `tools/baseline.py::tag_ok`)

── 왜 이 파일이 생겼나 (2026-09-30) ────────────────────────────
`tools/fl.sh` 가 측정 배치에서 죽으며 이렇게 적었다 —

    받아들이겠다면 … --measured=v0.48

사람이 그대로 쳤다. **그 값은 봉인 명명 규칙(`^\\d{8}-[a-z0-9-]+/`)을 어긴다.**
`baseline.py freeze` 는 그 규칙을 몰라서 그대로 받았고, 같은 규칙을 드는
`lakecheck` L6 와 `datalog` 가 **전수 verify 에서** 울었다 — 파이프라인을 두 번
돌린 뒤다. 되돌리는 값이 컸다.

★ **안내가 틀린 값을 가르치면 그것이 제일 빨리 퍼진다.** 사람은 예시를
  의심하지 않는다 — 도구가 준 값이기 때문이다. 그래서 여기서 문는 것은
  「규칙이 있는가」가 아니라 **「그 규칙을 도구 제 입이 지키는가」**다.

IN    tools/**(머리말 · 안내 문구) · sources.yaml 의 `layers.baseline.naming`
OUT   없음
밖    **예시가 좋은 예시인가는 안 본다.** 읽기 쉬운지, 대표적인지는 사람이 본다.
      여기가 드는 것은 「그 값이 제 관문을 통과하는가」 하나다.
      **규칙을 여기 다시 적지 않는다** — 정본은 `sources.yaml` 이고, 적으면
      같은 사실이 두 집에 산다(2족).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _baseline():
    spec = importlib.util.spec_from_file_location("baseline_t", ROOT / "tools" / "baseline.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


BL = _baseline()

#: 봉인 태그가 나오는 자리. `--tag <값>` · `--measured=<값>` 둘뿐이다.
TAGGED = re.compile(r"--(?:tag\s+|measured=)([A-Za-z0-9][\w.\-]*)")

#: 안내를 읽는 파일.
#:
#: ★ `tools/inbox_fl.sh` 는 **안 본다.** 그것은 INBOX 에서 진짜 `fl.sh` 를 찾아
#:   부르는 부트스트랩이고 태그 예시를 한 줄도 안 든다 — 넣으면 `EXEMPT` 가
#:   죽은 면제로 잡힌다(`test_tools_are_wired`). **읽기만 하는 것은 배선이
#:   아니지만 그 검사는 그것을 못 가른다**, 그러니 여기서 안 넣는 쪽이 맞다.
SOURCES = ("tools/fl.sh", "tools/remeasure.py",
           "README.md", "docs/MASTER.md", "docs/PLAN.md")


def test_the_rule_has_one_home():
    """규칙이 `sources.yaml` 에 있고 `baseline.py` 가 **그것을 읽는가.**"""
    rx = BL.tag_rule()
    assert rx, "봉인 명명 규칙을 못 읽는다 — 관문이 빈 그물이다"
    src = (ROOT / "tools" / "baseline.py").read_text(encoding="utf-8")
    assert rx not in src, (
        "규칙 문자열이 `baseline.py` 에도 적혀 있다 — 같은 사실이 두 집에 산다")


def test_every_example_tag_passes_its_own_gate():
    """★ **이것이 2026-09-30 의 그 결함이다.**"""
    bad = []
    for rel in SOURCES:
        p = ROOT / rel
        if not p.is_file():
            continue
        for no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for tag in TAGGED.findall(line):
                if tag.startswith("$") or tag.startswith("<"):
                    continue          # 셸 치환·자리표시자는 값이 아니다
                if not BL.tag_ok(tag):
                    bad.append(f"{rel}:{no}  `{tag}` — 제 관문이 거절할 값을 가르친다")
    assert not bad, (
        "도구가 규칙을 어기는 예시를 가르친다 —\n  " + "\n  ".join(bad)
        + f"\n\n  규칙: {BL.tag_rule()}  (정본은 sources.yaml `layers.baseline.naming`)")


def test_the_net_is_not_empty():
    """★ 반대 방향. 예시를 하나도 못 찾으면 위 시험은 **언제나 초록**이다."""
    found = [t for rel in SOURCES if (ROOT / rel).is_file()
             for t in TAGGED.findall((ROOT / rel).read_text(encoding="utf-8"))
             if not t.startswith(("$", "<"))]
    assert found, "예시 태그를 하나도 못 찾았다 — 정규식이 안내와 갈렸다"


def test_the_gate_actually_refuses():
    """규칙을 어기는 값을 **정말 거절하는가.** 안 거절하면 위 시험이 헛돈다."""
    assert not BL.tag_ok("v0.48"), "2026-09-30 에 앉았던 그 값을 통과시킨다"
    assert not BL.tag_ok("covrate"), "날짜 없는 이름을 통과시킨다"
    assert BL.tag_ok("20260930-covrate"), "규칙을 지킨 값을 거절한다"
    assert BL.tag_ok("20260918-pre-r3"), "기존 봉인 이름을 거절한다"
