"""
test_schema_self_consistent.py — 산출물 스키마가 **스스로를 반박하지 않는가.**
(DECISIONS §305)

── 왜 이 파일이 생겼나 (2026-09-29) ────────────────────────────
`segments.schema.json` 이 한 파일 안에서 두 가지를 동시에 말하고 있었다 —

    fields.road_bt_m    「참고용. **판정에는 쓰지 않는다**」
    verdict_rule[1]     「wmax 없음 + wmin < 3.0 + **ROAD_BT < 3.0** -> blocked」

실측하면 그 규칙이 **blocked 191건 중 131건(69%)을 혼자 만든다.** 즉 판정의
과반을 만드는 열에 「판정에 쓰지 않는다」가 붙어 나갔다. 그리고 이 파일은
`paths.py:178` 이 적듯 **UI 담당이 읽는 계약**이다.

같은 파일에 둘째 모순도 있었다 —

    verdict_rule[6]          「… -> unknown (**reason=no_cctv**)」
    fields.unknown_reason    「no_cctv_narrow|_thin|_band|_single」 (옳다)

`no_cctv` 는 산출물에 **한 번도 없는 값**이다. 그것으로 분기하는 소비자는
회색 399건 중 0행을 받는다.

★ 기존 관문이 왜 못 봤나. `test_schema_matches_data` 는 컬럼 **집합**만 보고,
  `test_unknown_reason_vocabulary_is_declared_in_three_places` 는 **어휘가
  세 곳에 다 있는가**만 본다. 둘 다 「같은 파일의 두 칸이 서로를 부정하는가」는
  안 봤다 — 한 문서 안의 모순은 아무 관문의 범위가 아니었다.

── 무엇을 보나 ────────────────────────────────────────────────
    ① 판정에 드는 열이 「판정에 쓰지 않는다」고 적혀 있지 않은가
    ② `verdict_rule` 이 드는 사유·판정 낱말이 전부 실재하는 어휘인가
    ③ `verdict_rule` 이 드는 숫자가 파라미터 정본과 같은가
    ④ 선언표(`JUDGMENT_FIELDS`)가 낡지 않았는가 — 반대 방향

IN    src/firelane/seg/report.py(fields) · seg/geom.py(VERDICT_RULE) ·
      seg/classify.py(REASONS · VERDICTS) · seg/params.py
OUT   없음
밖    **판정이 옳은가는 안 본다.** 규칙이 좋은 규칙인지도 안 본다 — 문서가
      스스로 모순되지 않는가만 든다.
      **발행된 `web/data/segments.schema.json` 을 안 읽는다.** 그것은 생성물이라
      파이프라인을 다시 돌려야 갱신된다(§298 이 정한 규율). 여기는 **생성기**를
      읽는다 — §17 이 「코드가 정본」이라 정한 그 자리다. 발행본이 생성기와
      맞는가는 `freshcheck` · `golden` 이 든다.
      **`width_*` 값의 진위**도 밖이다(`tools/widthcross.py`).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from firelane.seg.classify import REASONS, VERDICTS
from firelane.seg.geom import VERDICT_RULE
from firelane.seg.params import CCTV_RANGE, PARK, TRUCK

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "src" / "firelane" / "seg" / "report.py"

#: 판정에 **드는** 열 → `VERDICT_RULE` 안에서 그 열을 부르는 낱말.
#:
#: ★ 손목록이지만 **낡으면 운다** — ④ 가 낱말이 규칙에 실재하는지 보고,
#:   ① 이 그 열의 서술을 본다. 규칙에서 낱말이 사라지면 ④ 가 울고, 판정에
#:   드는 열이 새로 생기면 사람이 여기 한 줄을 적어야 한다.
#:   자동으로 뽑을 수는 없다 — 규칙은 산문이고 열 이름과 낱말이 다르다
#:   (`ROAD_BT` ↔ `road_bt_m`). 뽑는 척하면 그것이 더 나쁘다.
JUDGMENT_FIELDS = {
    "width_min_m": "wmin",
    "width_max_m": "wmax",
    "n_sample": "정규표본",
    "road_bt_m": "ROAD_BT",
}

#: 「이 열은 판정 밖이다」로 읽히는 표현. 하나라도 걸리면 ① 이 운다.
DENIALS = ("판정에는 쓰지 않는다", "판정에 쓰지 않는다", "판정에 안 쓴다",
           "판정에는 안 쓴다", "판정 밖이다")


def fields() -> dict[str, str]:
    """`report.py` 의 `fields` 표를 **파이프라인 없이** 읽는다.

    AST 로 읽는다 — 정규식으로 dict 를 오리면 여러 줄 이어붙인 서술에서 끊긴다.
    """
    tree = ast.parse(REPORT.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values, strict=True):
            if isinstance(k, ast.Constant) and k.value == "fields" and isinstance(v, ast.Dict):
                out = {}
                for kk, vv in zip(v.keys, v.values, strict=True):
                    if not isinstance(kk, ast.Constant):
                        continue
                    try:
                        out[kk.value] = ast.literal_eval(vv)
                    except ValueError:
                        out[kk.value] = ""
                return out
    raise AssertionError("report.py 에서 fields 표를 못 찾았다 — 이 시험이 빈 그물이다")


# ── ① 판정에 드는 열이 판정 밖이라고 적혀 있지 않다 ────────────

def test_no_judgment_field_denies_being_used():
    F = fields()
    bad = []
    for name in JUDGMENT_FIELDS:
        desc = F.get(name)
        assert desc is not None, f"스키마에 {name} 이 없다 — 판정이 그것을 읽는다"
        for d in DENIALS:
            if d in desc:
                bad.append(f"{name}: 「{d}」 ← verdict_rule 이 이 열로 판정한다")
    assert not bad, (
        "스키마가 스스로를 반박한다:\n  " + "\n  ".join(bad) +
        "\n\n  둘 중 하나다 — 규칙에서 그 열을 빼거나, 서술을 사실로 고쳐라.\n"
        "  이 파일은 밖(UI 담당)이 읽는 계약이다(MASTER §18-6 · paths.py:178).")


# ── ② 규칙이 드는 낱말이 전부 실재한다 ─────────────────────────

def test_every_reason_named_in_the_rules_exists():
    named = set()
    for r in VERDICT_RULE:
        for m in re.finditer(r"reason=([a-z_|]+)", r):
            named |= set(m.group(1).split("|"))
    assert named, "규칙이 `reason=` 를 하나도 안 든다 — 이 시험이 빈 그물이다"
    ghost = sorted(named - set(REASONS))
    assert not ghost, (
        f"규칙이 드는 사유가 산출물에 없는 값이다: {ghost}\n"
        f"  실재하는 어휘: {list(REASONS)}\n"
        "  그 값으로 분기하는 소비자는 0행을 받는다.")


def test_every_verdict_named_in_the_rules_exists():
    named = set()
    for r in VERDICT_RULE:
        for m in re.finditer(r"->\s*([a-z_]+)", r):
            named.add(m.group(1))
    assert named, "규칙이 `->` 로 판정을 하나도 안 낸다"
    ghost = sorted(named - set(VERDICTS))
    assert not ghost, f"규칙이 드는 판정이 어휘 밖이다: {ghost} · 어휘 {list(VERDICTS)}"


def test_the_field_enum_lists_the_same_verdicts():
    """`fields.verdict` 의 열거가 어휘와 같다."""
    F = fields()
    listed = set(re.findall(r"[a-z_]+", F["verdict"].split(" ")[0]))
    assert listed == set(VERDICTS), (
        f"fields.verdict 열거 {sorted(listed)} ≠ 어휘 {sorted(VERDICTS)}")


def test_the_field_enum_lists_the_same_reasons():
    F = fields()
    blk = F["unknown_reason"]
    miss = sorted(r for r in REASONS if r not in blk)
    assert not miss, f"fields.unknown_reason 이 설명하지 않는 사유: {miss}"


# ── ③ 규칙이 드는 숫자가 파라미터 정본과 같다 ──────────────────

def test_the_numbers_in_the_rules_come_from_the_constants():
    """산문에 박힌 숫자가 상수와 갈리면 문서가 조용히 낡는다."""
    txt = " ".join(VERDICT_RULE)
    want = {TRUCK, TRUCK + 2 * PARK, CCTV_RANGE}
    seen = {float(x) for x in re.findall(r"\d+\.\d+|\b\d+(?=m\b)", txt)}
    miss = sorted(w for w in want if w not in seen)
    assert not miss, (
        f"규칙 문언에 상수가 안 보인다: {miss} · 문언이 든 수 {sorted(seen)}\n"
        "  임계값을 고쳤으면 `VERDICT_RULE` 문언도 같이 고쳐라(R7).")


# ── ④ 반대 방향 — 선언표가 낡지 않았다 ─────────────────────────

def test_the_declared_map_is_not_stale():
    """★ 이것이 없으면 ① 이 **항상 통과하는 검사**가 된다(§69).

    규칙에서 어떤 열이 빠졌는데 `JUDGMENT_FIELDS` 에 남아 있으면, ① 은 판정에
    안 드는 열의 서술을 계속 검사한다 — 통과하지만 아무것도 안 지킨다.
    """
    txt = " ".join(VERDICT_RULE)
    lost = sorted(f for f, token in JUDGMENT_FIELDS.items() if token not in txt)
    assert not lost, (
        f"선언표가 든 열을 규칙이 더는 안 부른다: {lost}\n"
        "  규칙에서 뺐으면 `JUDGMENT_FIELDS` 에서도 빼고, 그 열의 서술을\n"
        "  「판정에 쓰지 않는다」로 고쳐라 — 그것이 그때는 사실이다.")


def test_a_denial_is_still_allowed_outside_the_judgment():
    """판정 밖 열은 「판정에 쓰지 않는다」로 적어도 된다 — 그 표현 자체를
    금지하는 것이 아니다. 실제로 그런 열이 있어야 이 시험이 뜻을 갖는다."""
    F = fields()
    outside = [n for n, d in F.items()
               if n not in JUDGMENT_FIELDS and any(x in d for x in DENIALS)]
    assert outside, (
        "「판정에 쓰지 않는다」고 적힌 판정 밖 열이 하나도 없다 — "
        "표현이 사라졌으면 DENIALS 를 다시 보라(예: `z`)")
