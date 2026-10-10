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


# ── 필드표 ↔ 발행 필드 (2026-10-08 · DECISIONS §436-13) ───────────
# ★ 이 대조는 `tools/docnum_check.py` 의 `main()` **안에만** 있었다 — 위 시험
#   다섯은 지문의 수만 본다. 그래서 「문서 숫자 대조」 축이 **CLI 에서만** 빨갛고
#   pytest 는 조용했다(족 3 · 관문이 갈림). 재잠금 판에서 그 축을 면제하면
#   **아무도 안 세는 자리**가 되므로, 면제 전에 세는 자를 세운다.
# ★ 경로를 **한 줄 리터럴**로 적는다 — `test_tools_are_wired` 의 배선 탐지가
#   줄 단위다(§276-1 꼬리).
_dnspec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location("docnum_check", ROOT / "tools/docnum_check.py")

WEB_SEG = ROOT / "web/data/segments.geojson"


def _docnum():
    import importlib.util
    import sys

    assert _dnspec and _dnspec.loader
    m = importlib.util.module_from_spec(_dnspec)
    sys.modules[_dnspec.name] = m
    _dnspec.loader.exec_module(m)
    return m


def test_the_field_table_names_exactly_the_published_fields():
    """MASTER §11 필드표 **=** 발행된 속성. 양방향이다 — 둘 다 결함이다.

    표에만 있으면 **없는 칸을 설명**하고, 산출물에만 있으면 **설명 없는 칸**이
    나간다. 앞은 읽는 사람을 속이고 뒤는 침묵한다.
    """
    D = _docnum()
    doc = D.doc_fields((ROOT / "docs/MASTER.md").read_text(encoding="utf-8"))
    assert doc, "§11 `### 데이터 필드` 표를 못 찾았다 — 수집이 죽으면 빈 그물이다"
    real = set(json.loads(WEB_SEG.read_text(encoding="utf-8"))
               ["features"][0]["properties"])
    assert doc == real, (
        f"표에만 있다 {sorted(doc - real)}\n"
        f"  산출물에만 있다 {sorted(real - doc)}\n"
        "  ★ 산출물이 정본이다. 재잠금 전이라면 표가 **앞서 있는 것**이고 "
        "`tools/delivercheck.py` 의 `RELOCK_TESTS` 가 이 이름을 든다")


# ── 회색 사유의 가짓수 **낱말** (2026-10-09 · DECISIONS §444 · PLAN #142) ──
# ★ 종전에 기획서의 그 문장을 보던 것은 `docx_check` 의 ⑤ 정방향(= `docx_fix`
#   규칙)뿐이고, 그것이 읽는 것은 `docs/proposal.docx` 였다. 정본이 md 로
#   옮겨진 뒤(§425) **정본의 그 문장은 아무도 안 봤다** — 그래서 `ledger_disputes`
#   가 다섯째 사유로 선 날 문장은 「네 가지」로 거짓이 됐고, 운 것은 사본을
#   보던 검사였다. docx 가 은퇴하면 그 울음도 같이 사라지므로 **먼저 세운다.**
def test_the_grey_reason_word_count_is_watched():
    """합성 입력 — 수사 낱말이 실물과 어긋나면 운다. 양방향."""
    D = _docnum()
    ok = "- GRAY 400구간의 사유는 다섯 가지이며 폭 산출 불가는 0건이다."
    assert not D.gray_kind_faults(ok, 5), "맞는 문장에서 운다"
    assert D.gray_kind_faults(ok, 4), "다섯을 넷이라고 해도 안 운다"
    assert D.gray_kind_faults(ok, 6), "다섯을 여섯이라고 해도 안 운다"
    # ★ **문장이 없으면 운다.** 지우면 조용해지는 축은 없는 축이다(1족).
    assert D.gray_kind_faults("아무 말도 없다", 5), "닻이 사라졌는데 조용하다"
    # ★ 수사는 **한글**이다. 숫자로 적은 것도 어긋남이다 — 문서 서식이 한글이다
    assert D.gray_kind_faults("- GRAY 400구간의 사유는 5 가지다.", 5), "숫자 수사를 통과시킨다"


def test_the_real_proposal_states_the_right_number_of_grey_reasons():
    """실물 — 기획서의 그 문장이 **지금 산출물**의 사유 종수를 든다."""
    D = _docnum()
    n = sum(1 for k in D.counts() if k.startswith("ur_"))
    assert n >= 4, f"회색 사유를 {n}종 셌다 — 수집기를 의심하라"
    bad = D.gray_kind_faults((ROOT / "docs/proposal.md").read_text(encoding="utf-8"), n)
    assert not bad, "\n".join(bad)


# ── 문서가 적어야 하는 수 (2026-10-10 · DECISIONS §452 · PLAN #56) ──────
# ★ 이 축도 `docnum_check.main()` **안에만** 있었다 — 바로 위 필드표가 §436-13
#   에서 같은 사유로 나왔는데 **옆칸은 그대로 뒀다.** 한 판에서 둘을 다 안 옮긴
#   것이 2026-10-10 에 값을 치렀다: `#34` 가 README 를 줄이자 규칙 여섯이
#   **주장 없는 파일**을 가리켰고 전수 pytest 는 초록이었다.
_drspec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location("docnumrules", ROOT / "tools/docnumrules.py")


def _docnumrules():
    import importlib.util
    import sys

    assert _drspec and _drspec.loader
    m = importlib.util.module_from_spec(_drspec)
    sys.modules[_drspec.name] = m
    _drspec.loader.exec_module(m)
    return m


def test_every_declared_number_is_in_its_document():
    """실물 — 선언 표의 모든 (파일 · 라벨)이 지금 산출물의 수를 든다.

    ★ 재잠금 전에는 빨갛다 — `tools/delivercheck.py` 의 `RELOCK_TESTS` 가 이
      이름을 든다. 문서는 **재잠금 뒤의 수**를 적는다.
    """
    R, D = _docnumrules(), _docnum()
    cache: dict[str, str] = {}

    def read(rel: str) -> str:
        return cache.setdefault(rel, (ROOT / rel).read_text(encoding="utf-8"))

    bad = R.present_faults(D.counts(), read)
    assert not bad, "문서가 적은 수가 산출물과 다르다:\n  " + "\n  ".join(bad)


def test_that_axis_bites_a_moved_claim():
    """★ 카나리아 — 주장이 사라진 파일을 가리키면 운다. `#34` 가 겪은 그 자리다."""
    R, D = _docnumrules(), _docnum()
    bad = R.present_faults(D.counts(), lambda rel: "숫자가 하나도 없는 글")
    assert bad, "주장이 없는데 조용하다 — 빈 그물이다"
    assert any("패턴이 낡았다" in m for m in bad), bad
