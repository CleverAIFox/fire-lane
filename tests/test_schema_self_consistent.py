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

from firelane.seg.classify import REASONS, VERDICTS, classify
from firelane.seg.geom import VERDICT_RULE
from firelane.seg.params import CCTV_RANGE, PARK, TRUCK

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "src" / "firelane" / "seg" / "report.py"

def judgment_fields() -> dict[str, str]:
    """판정에 **드는** 발행 열 → `classify()` 인자 이름. **`segments.py` 의 호출에서 유도한다.**

    ★ 2026-10-24 (Zm22 · 감사). 종전에는 이것이 **손으로 적은 네 칸**이었고(`width_min_m` · `width_max_m` · `n_sample` ·
      `road_bt_m`) 규칙 [8]~[11] 이 읽는 `width_min_any_m` · `width_min_sym_m` · `clear_med_m` 와 `cctv_dist_m` · `length_m`
      을 몰랐다 — 그 열들이 「판정에 안 쓴다」고 적혀 나갔다(9월 `road_bt_m` 사고와 같은 꼴). 이제 `classify(...)` 호출의
      키워드 인자 값을 `rec[...] = dict(...)` 의 열 이름으로 되짚는다. 새 인자가 생기면 열이 저절로 따라오고,
      되짚지 못하면 시험이 **운다**(조용히 빠지지 않는다).
    """
    src = (ROOT / "src" / "firelane" / "segments.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    call = next((n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "classify"), None)
    rec = next((n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "dict"
                and any(k.arg == "width_min_m" for k in n.keywords)), None)
    assert call is not None and rec is not None, "segments.py 에서 classify() 호출이나 rec 행을 못 찾았다 — 유도가 빈 그물이다"
    by_expr = {ast.unparse(k.value): k.arg for k in rec.keywords if k.arg}
    out: dict[str, str] = {}
    for kw in call.keywords:
        v = kw.value
        if isinstance(v, ast.Subscript) and isinstance(v.slice, ast.Constant) and isinstance(v.slice.value, str):
            col = v.slice.value                              # `_wa["width_min_any_m"]` 처럼 열 이름이 적혀 있다
        else:
            col = by_expr.get(ast.unparse(v))
            if col is None:                                   # `g.length` → `round(g.length, 1)` 처럼 감싼 표현
                col = next((c for e, c in by_expr.items() if ast.unparse(v) in e), None)
        assert col is not None, f"classify({kw.arg}=…) 의 값 `{ast.unparse(v)}` 이 어느 발행 열인지 되짚지 못했다"
        out[col] = kw.arg
    return out


JUDGMENT_FIELDS = judgment_fields()

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
    # needs_cv 의 이유(`cv_reason`)는 `unknown_reason` 어휘(REASONS)와 **다른 칸**이다. 이 집합은 실제로 classify 가 내는지 아래에서 댄다.
    got = classify(wmin=7.5, wmax=8.0, nreg=5, road_bt=6.0, length_m=30.0, cctv_dist=10.0, wmin_any=2.0, wsym=None)
    assert got == ("needs_cv", "source_conflict"), f"cv_reason 어휘가 달라졌다 — {got}"
    sym = classify(wmin=7.5, wmax=8.0, nreg=5, road_bt=6.0, length_m=30.0, cctv_dist=10.0, wmin_any=None, wsym=2.0)
    assert sym == ("needs_cv", "sym_low"), f"규칙 [9] 의 cv_reason 이 달라졌다 — {sym}"
    ghost = sorted(named - set(REASONS) - {got[1], sym[1]})
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

def test_the_derived_map_covers_every_rule_input_and_only_those():
    """★ 유도가 손목록 때보다 **더 많이** 잡는다 — 규칙 [8]~[11] 의 입력까지. 그리고 중앙값은 안 든다.

    `classify()` 가 받는 인자(기본값 없는 것 · 호출이 넘기는 것)가 전부 열로 되짚였고, 그 밖의 열(`width_med_m` ·
    `clear_min_m` · `clear_max_m`)은 판정 입력이 아니다.
    """
    import inspect

    params = set(inspect.signature(classify).parameters)
    passed = set(JUDGMENT_FIELDS.values())
    assert passed <= params, f"classify() 에 없는 인자를 넘긴다: {sorted(passed - params)}"
    for col in ("width_min_m", "width_max_m", "n_sample", "road_bt_m",
                "width_min_any_m", "width_min_sym_m", "clear_med_m", "cctv_dist_m", "length_m"):
        assert col in JUDGMENT_FIELDS, f"판정이 읽는 {col} 을 유도가 못 잡았다"
    for col in ("width_med_m", "clear_min_m", "clear_max_m"):
        assert col not in JUDGMENT_FIELDS, f"{col} 은 판정이 읽지 않는 칸이다 — 읽으면 시험이 울어야 한다"


def test_a_denial_is_still_allowed_outside_the_judgment():
    """판정 밖 열은 「판정에 쓰지 않는다」로 적어도 된다 — 그 표현 자체를
    금지하는 것이 아니다. 실제로 그런 열이 있어야 이 시험이 뜻을 갖는다."""
    F = fields()
    outside = [n for n, d in F.items()
               if n not in JUDGMENT_FIELDS and any(x in d for x in DENIALS)]
    assert outside, (
        "「판정에 쓰지 않는다」고 적힌 판정 밖 열이 하나도 없다 — "
        "표현이 사라졌으면 DENIALS 를 다시 보라(예: `z`)")
