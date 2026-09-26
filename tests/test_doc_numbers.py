"""문서가 든 숫자를 **커밋된 지문**과 대조한다 — 레이크 없이 돈다.

★ 2026-09-24 (PLAN §13 W13-1 · DECISIONS §243). `tools/docnum_check.py` 가
  같은 일을 하지만 `data/processed/segments.geojson` 을 읽는다. 그 파일은
  커밋 대상이 아니라서 **clone 직후 · CI · 남의 기계에서 안 돈다** —
  `! … 없음 — pipeline 을 먼저 돌려라` 하고 1 을 낸다. 즉 숫자 대조는
  「전량을 돌린 사람의 기계」에서만 살아 있었고, 문서를 고치는 사람은
  대개 그 기계가 아니다.

  `data/golden/segments.fingerprint.json` 의 `L1` 은 **커밋된다**. 판정
  정본이 거기 있는데 문서 대조가 그것을 안 봤다.

★ **지문을 안 건드린다.** 이 시험은 읽기만 한다 — 지문은 판정 산출물이고,
  문서를 맞추려고 산출물을 고치는 순간 대조가 뒤집힌다.

★ 실제로 무엇을 잡았나 (2026-09-24 감사) —

      MASTER:126   기준일 2026-08-24        숫자는 09-16 것
      MASTER:326   ngii1k 1,014 · silpok 84  실제 1,166 · 112
      MASTER:335   같은 값 + 「대조 도구가 없다」
      MASTER:1170  no_cctv_band 152         같은 문서 151행은 183
      width.py:5   ngii1k 1014 · silpok 84
      test_seg_width:4  같은 값
      PLAN:127     needs_cv 191구간          실제 226

  일곱 전부 **2026-09-16 흡수-2(1,101 → 1,281)가 건너뛴 자리**이고, 옛 값은
  `data/baseline/20260824-pre-nreg/meta.json` 한 파일에서 글자 그대로 나온다.
  `docnum_check` 가 보는 축(판정 4종 · CCTV · 소방청 지정) **밖**이었다.

밖   기준일 문자열은 안 본다 — 지문에 날짜 칸이 없고, 날짜를 넣으려면
     판정 산출물을 고쳐야 한다. 숫자가 맞으면 날짜가 틀려도 읽는 사람이
     쓰는 값은 옳다. 날짜 하나를 위해 지문을 흔들지 않는다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FP = ROOT / "data/golden/segments.fingerprint.json"

#: 대조 대상. 문서 셋 + 그 숫자를 docstring 에 박은 코드 둘.
#: ★ 코드도 본다 — `width.py` 가 「이 파일이 ngii1k 1014 … 를 만든다」고
#:   적고 있었다. 만드는 쪽이 틀린 수를 말하면 읽는 쪽이 의심을 안 한다.
TARGETS = ("README.md", "docs/MASTER.md", "docs/PLAN.md",
           "src/firelane/seg/width.py", "tests/test_seg_width.py")

ALLOW = "<!--stale-ok-->"

#: `ngii1k 1,166 · silpok 112 · ngii 1`. 쉼표는 있어도 없어도 된다.
SRC_PAT = re.compile(r"ngii1k\s+([\d,]+)\s*·\s*silpok\s+([\d,]+)\s*·\s*ngii\s+(\d+)")

#: `` `no_cctv_band` | 183 `` · ``(`no_cctv_band` 183)``. 표와 산문을 같이 먹는다.
RSN_PAT = re.compile(r"`(no_cctv_\w+)`[^\d\n]{0,8}(\d+)")


@pytest.fixture(scope="module")
def l1() -> dict:
    assert FP.exists(), f"{FP} 가 없다 — 판정 지문은 커밋 대상이다"
    return json.loads(FP.read_text(encoding="utf-8"))["L1"]


def _lines(rel: str) -> list[tuple[int, str]]:
    return [(i, s) for i, s in
            enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), 1)
            if ALLOW not in s]


def _src_claims(text: str) -> list[tuple[int, int, int]]:
    """`(ngii1k, silpok, ngii)` 주장 목록. selftest 가 같은 함수를 쓴다."""
    return [tuple(int(g.replace(",", "")) for g in m)  # type: ignore[misc]
            for m in SRC_PAT.findall(text)]


def _rsn_claims(text: str) -> list[tuple[str, int]]:
    return [(k, int(v)) for k, v in RSN_PAT.findall(text)]


def test_width_source_counts_match_the_fingerprint(l1):
    """채택 소스 수. MASTER §3-5 가 「실측값이라 대조 도구가 없다」고 적고 있었다."""
    w = l1["width_src"]
    want = (w["ngii1k"], w["silpok"], w["ngii"])
    bad = [f"{rel}:{no} — {got} (지문 {want})"
           for rel in TARGETS for no, ln in _lines(rel)
           for got in _src_claims(ln) if got != want]
    assert not bad, (
        "채택 소스 수가 지문과 다르다:\n  " + "\n  ".join(bad) + "\n"
        f"  정본 {FP.relative_to(ROOT)} · L1.width_src\n"
        f"  일부러 옛 값을 인용하는 줄이면 줄 끝에 {ALLOW} 를 붙여라.")


def test_unknown_reason_counts_match_the_fingerprint(l1):
    """`no_cctv_*` 수. MASTER 151행은 183, 1170행은 152 였다 — 같은 문서 안에서."""
    want = l1["unknown_reason"]
    bad = [f"{rel}:{no} — {k} {got} (지문 {want[k]})"
           for rel in TARGETS for no, ln in _lines(rel)
           for k, got in _rsn_claims(ln) if k in want and got != want[k]]
    assert not bad, (
        "`unknown_reason` 수가 지문과 다르다:\n  " + "\n  ".join(bad) + "\n"
        f"  정본 {FP.relative_to(ROOT)} · L1.unknown_reason")


def test_the_matchers_are_alive():
    """**목표에 닿는 날 빨개지는가.** 실제 나무가 아니라 합성 문장으로 증명한다.

    ★ 위 둘은 지금 초록이다. 초록인 검사는 「정말 보고 있는가」를 스스로
      증명하지 못한다 — 정규식 한 글자가 낡으면 영영 초록이다. 실제로
      `test_contract.navi_reads()` 의 `[\\w_]+` 가 점 둘인 이름을 영영
      안 먹고 있었다(같은 날 고쳤다).
    """
    assert _src_claims("채택 소스   ngii1k 1,014 · silpok 84 · ngii 1 · 미산출 2") \
        == [(1014, 84, 1)], "쉼표 있는 표기를 못 읽는다"
    assert _src_claims("`ngii1k 1166 · silpok 112 · ngii 1` 을 만든다") \
        == [(1166, 112, 1)], "쉼표 없는 표기를 못 읽는다"
    assert _src_claims("ngii1k 만 적힌 줄") == [], "없는 곳에서 잡는다"

    assert _rsn_claims("| `no_cctv_band` | 183 | 3~7m 대역") == [("no_cctv_band", 183)], \
        "표 꼴을 못 읽는다"
    assert _rsn_claims("`unknown`(`no_cctv_band` 152)으로 내려간다") \
        == [("no_cctv_band", 152)], "산문 꼴을 못 읽는다"
    assert _rsn_claims("`no_cctv_band` 는 대역이다") == [], \
        "숫자가 멀리 있는데 잡는다 — 8글자 창이 넓어졌다"


def test_the_targets_exist():
    """대조 대상이 사라지면 검사가 **조용히 0건**이 된다."""
    for rel in TARGETS:
        assert (ROOT / rel).exists(), f"{rel} 이 없다 — TARGETS 를 고쳐라"
    seen = sum(len(_src_claims(ln)) for rel in TARGETS for _, ln in _lines(rel))
    assert seen >= 2, f"채택 소스 주장을 {seen}건 찾았다 — 정규식이 낡았거나 문서가 비었다"


def test_the_full_rerun_time_has_one_voice():
    """전량 재실행 시간이 285초 · 2분45초 · 2분40초 셋으로 갈려 있었다.

    ★ **실측 정본이 없다.** 셋 다 사람이 적은 값이고 기계도 다르다
      (DECISIONS §143 은 5분18초라고 적는다 — 네 번째 값이다).
      정본을 만드는 것은 6족(측정)이고 `PLAN §13` 이 든다.
      여기서 닫는 것은 「**샤드 봉인 전 값이 현재형으로 남아 있는 것**」
      하나다 — 285초는 2026-09-16 이전 값이고, 그 뒤 두 값과 120초 차이다.
    """
    bad = [f"{rel}:{no}  {ln.strip()[:70]}"
           for rel in ("README.md", "docs/MASTER.md", "docs/PLAN.md")
           for no, ln in _lines(rel) if "285초" in ln]
    assert not bad, (
        "폐기된 전량 재실행 시간 285초(샤드 봉인 전)가 현재형에 남아 있다:\n  "
        + "\n  ".join(bad) + "\n"
        "  회고로 인용하는 줄이면 줄 끝에 " + ALLOW + " 를 붙여라.")
