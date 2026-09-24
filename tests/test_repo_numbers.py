"""문서가 적은 **저장소 구조 숫자**를 실물과 대조한다.

★ 2026-09-25 (DECISIONS §246). §243 감사가 91건을 고치고 지나간 자리에서
  2분 만에 셋이 더 나왔다 —

      MASTER:2213   「소스 64종의 raw sha256」       실물 71종
      MASTER:2597   「절 1,004 전수」                실물 1,017절
      MASTER:3667   「절 540개의 (제목+본문) 해시」   봉인 실물 909절

  못 본 이유는 사람이 게을러서가 아니라 **축이 없어서**다. `dms verify` 는
  참조가 살아 있는지만 보고 수는 안 본다. `test_doc_numbers`(§243 신설)는
  판정 산출물 수(`width_src` · `unknown_reason`)만 본다. 저장소가 자기
  구조를 몇 개라고 말하는지는 **아무도 안 봤다.**

★ `test_doc_numbers.py` 와 **일부러 파일을 갈랐다.** 그쪽 정본은
  `data/golden/segments.fingerprint.json`(판정 산출물)이고 이쪽 정본은
  `sources.yaml` · `dms.scan()`(저장소 구조)다. 한 파일에 두 정본을 두면
  「무엇이 정본인가」가 흐려지고, 그것이 이 저장소가 반복해 배운 형태다.

★ **표기를 좁게 잡는다.** 「소스 21종」처럼 부분집합을 말하는 자리가 실재한다
  (`MASTER §18` · `authority` 칸이 있는 것만 센다). 그래서 정본 이름이 붙은
  표기(`` `datasets` 72종 ``)나 `raw` 가 붙은 표기만 본다. 넓게 잡으면
  부분집합이 걸려 사람이 검사를 끈다 — §243 이 적은 「선언이 검사보다 넓으면
  거짓 초록이 된다」의 거울상이다.

IN    `ledger.load()` · `dms.scan()` · 문서 넷
OUT   없음
PARAM 없음
밖    ① **정본이 없는 값은 안 본다.** 봉인 시점 절 수가 그렇다 — 다음 봉인이
         덮어쓰므로 정본이 될 수 없고, 그래서 §246-2 가 그 수를 문서에서 뺐다.
         여기서 하는 일은 「적힌 수가 맞는가」이고 「적어야 하는가」가 아니다.
      ② **`retired` 종수는 안 본다.** 그 수를 세려면 대장의 폐기 블록을 직접
         읽어야 하고 그것은 `test_lake.py::test_file_owners_are_resolved_in_one_place`
         래칫이 세는 사본이다. 축 하나를 위해 다른 강제자를 깨지 않는다 —
         `MASTER §18` 의 「`retired` 4종」은 **감시 밖**이고, 그렇다고 적는다.
         열려면 `firelane.lake` 가 폐기 종수를 주는 문을 먼저 내야 한다.
"""
from __future__ import annotations

import re
from pathlib import Path

import dms
import pytest

from firelane import ledger

ROOT = Path(__file__).resolve().parent.parent

#: 대조할 문서. 코드 주석은 안 본다 — 구조 숫자를 코드에 적는 자리가 없다.
TARGETS = ("README.md", "docs/MASTER.md", "docs/PLAN.md", "docs/DECISIONS.md")

ALLOW = "<!--stale-ok-->"

#: 축 이름 → (정규식, 사람이 읽을 설명).
#: ★ 각 정규식은 **그 수 하나만** 잡는다. 부분집합 표기가 걸리지 않게
#:   정본 이름이나 `raw` 를 앵커로 쓴다.
AXES: dict[str, tuple[re.Pattern[str], str]] = {
    "datasets": (re.compile(r"`datasets`\s+([\d,]+)\s*종"),
                 "대장 전체 — `sources.yaml::datasets`"),
    "sealable": (re.compile(r"소스\s+([\d,]+)\s*종의\s+raw"),
                 "봉인 대상 — datasets 에서 `on_demand` 를 뺀 수"),
    "sections": (re.compile(r"절\s+([\d,]+)\s*전수"),
                 "지금 세는 절 — `dms.scan()` 행 수"),
}


@pytest.fixture(scope="module")
def truth() -> dict[str, int]:
    """실물. **문서를 안 읽는다** — 대장과 도구가 정본이다.

    ★ `ledger.load()` 로 읽는다. yaml 로 대장을 직접 열면
      `test_lake.py::test_ledger_is_loaded_through_one_door` 래칫이 오른다 —
      **이 파일을 처음 쓸 때 실제로 41로 올려 놨다**(§246). 강제자를 만드는
      배치가 다른 강제자를 깨는 것이 이 저장소가 반복한 형태다.

    ★ 그 두 판별식은 **주석과 머리말도 본다**(`test_layering` 은 일부러 뺀다 —
      「자기 문서를 자기가 막는다」). 그래서 여기서는 문제의 호출 표기를
      글자로 쓰지 않는다. 판별식을 넓히는 쪽이 옳은지는 `PLAN §1 #131` 이 든다.
    """
    ds = ledger.load()["datasets"]
    return {
        "datasets": len(ds),
        "sealable": sum(1 for v in ds.values() if not v.get("on_demand")),
        "sections": len(dms.scan()["rows"]),
    }


def _lines(rel: str) -> list[tuple[int, str]]:
    return [(i, s) for i, s in
            enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), 1)
            if ALLOW not in s]


def _claims(axis: str, text: str) -> list[int]:
    """`axis` 표기가 이 문자열에서 말하는 수들. selftest 가 같은 함수를 쓴다."""
    return [int(m.replace(",", "")) for m in AXES[axis][0].findall(text)]


@pytest.mark.parametrize("axis", sorted(AXES))
def test_the_documents_count_the_repository_correctly(axis: str, truth: dict[str, int]):
    """문서가 적은 수가 실물과 같은가."""
    want = truth[axis]
    bad = [f"{rel}:{no} — {got} (실물 {want})"
           for rel in TARGETS for no, ln in _lines(rel)
           for got in _claims(axis, ln) if got != want]
    assert not bad, (
        f"`{axis}` 수가 실물과 다르다:\n  " + "\n  ".join(bad) + "\n"
        f"  뜻: {AXES[axis][1]}\n"
        f"  ★ 값만 고치면 다음에 또 낡는다 — 이 검사가 그 다음을 받는다.\n"
        f"  회고로 옛 값을 인용하는 줄이면 줄 끝에 {ALLOW} 를 붙여라.")


def test_the_matchers_are_alive():
    """**목표에 닿는 날 빨개지는가.** 합성 문장으로 직접 문다.

    ★ 위 셋은 지금 초록이다. 초록인 검사는 제가 보고 있다는 것을 스스로
      증명하지 못한다 — §243 이 만든 `test_doc_numbers` 가 바로 그 상태로
      이 셋을 못 봤고, `test_contract.navi_reads()` 의 `[\\w_]+` 는 점 둘인
      이름을 영영 안 먹고 있었다.
    """
    assert _claims("datasets", "대장은 `sources.yaml` 하나다. `datasets` 72종 · `retired` 4종.") \
        == [72], "정본 이름이 붙은 표기를 못 읽는다"
    assert _claims("sealable", "`SEAL.json` 이 소스 71종의 raw sha256 을 갖고") == [71], \
        "`raw` 앵커를 못 읽는다"
    assert _claims("sections", "**분모 0**(2026-09-25 · 절 1,017 전수.") == [1017], \
        "쉼표 있는 절 수를 못 읽는다"

    # ★ **부분집합을 잡으면 안 된다.** 이것이 이 검사에서 가장 비싼 오판이다 —
    #   한 번 오탐이 나면 사람이 검사를 끄고, 그 뒤로는 영영 안 본다.
    part = "`authority` 칸이 있는 소스 21종 중 규칙에 맞는 것은 3종이다."
    for axis in AXES:
        assert _claims(axis, part) == [], f"{axis} 가 부분집합 표기를 잡는다 — 오탐이다"
    assert _claims("sealable", "raw 는 소스 71종이다") == [], \
        "어순이 다른데 잡는다 — `종의 raw` 라는 앵커가 느슨해졌다"
    assert _claims("sections", "절 540개의 (제목+본문) 해시") == [], \
        "봉인 스냅샷 표기를 잡는다 — 그 수는 정본이 없다(§246-2)"


def test_every_axis_is_actually_claimed_somewhere(truth: dict[str, int]):
    """축이 문서에서 **한 번도 안 걸리면** 검사가 조용히 0건이 된다.

    ★ `sizecheck` 가 `web/navi/src` 를 안 보던 것과 같은 형태다(§243). 범위가
      비었는데 초록이면 그것은 통과가 아니라 **안 본 것**이다.
    """
    seen = {axis: sum(len(_claims(axis, ln)) for rel in TARGETS for _, ln in _lines(rel))
            for axis in AXES}
    dead = sorted(a for a, n in seen.items() if n == 0)
    assert not dead, (
        f"이 축이 문서 어디에도 안 적혀 있다: {dead}\n"
        f"  잡힌 수: {seen}\n"
        "  표기가 바뀌었거나 그 서술이 사라졌다. 정규식을 고치거나 축을 내려라 —\n"
        "  **안 걸리는 축을 남겨 두면 초록이 거짓말을 한다.**")


def test_the_truth_comes_from_the_ledger_not_the_docs(truth: dict[str, int]):
    """정본이 살아 있는가. 값이 0이면 위 셋이 통째로 무의미해진다."""
    assert truth["datasets"] > 50, f"datasets {truth['datasets']}종 — 대장을 못 읽었다"
    assert truth["sections"] > 500, f"절 {truth['sections']} — `dms.scan()` 이 죽었다"
    assert truth["sealable"] <= truth["datasets"], "봉인 대상이 대장보다 많다"
    assert truth["sealable"] < truth["datasets"], (
        "`on_demand` 소스가 0이다 — 970MB 인 `jijeok` 이 빠져 있어야 한다.\n"
        "  정말 0이 됐으면 이 줄을 고쳐라. 지금은 축이 낡았다는 신호다.")
