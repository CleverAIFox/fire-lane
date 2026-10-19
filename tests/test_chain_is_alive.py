"""test_chain_is_alive.py — 반입 체인의 **단계가 살아 있는가** · 결손이 **몇인가.**

── 왜 제 집인가 (2026-10-14 · DECISIONS 535-2) ────────────────
사람이 물었다 — 「데이터 관리 파이프라인은 **할 때마다 고쳐야** 하나.
재현적 도구가 무슨 의미가 있나.」 그 말이 맞았고, 원인이 하나였다 —

    ingest     [MISSING] 셋을 넉 달 찍었다    경고일 뿐
    judge      「결손 3종」으로 운다           **맞는 자다**
    pull_data  quarantine 에서 먼저 죽는다     judge 에 **도달하지 못한다**

`--quarantine` 은 §173-2 가 폐지했는데 체인이 넉 달 그것을 계속 불렀고,
그 도구는 거절만 하며 종료코드 2 로 죽는다. **죽은 단계 하나가 맞는 자를
넉 달 가렸다.**

여기 둘은 그 사슬을 **기계가** 끊게 한다 — 폐지를 적게 하고(부르는 쪽을
댄다), 결손을 래칫으로 든다(레이크 없이도 잰다). `test_intake_rules.py`
가 상한 700 에 서 있어서이기도 하지만, 축이 다르다 — 그쪽은 「체인의 꼴」을
보고 이쪽은 「체인이 **도는가**」를 본다.

IN    tools/acquire.py(`RETIRED_FLAGS` · `LEDGER_MISSING`) · tools/pull_data.py
      data/_acquire.json (커밋되는 sha 대장)
OUT   없음 (검사)
PARAM 없음 — 래칫 둘은 `acquire.py` 가 든다(그 축을 아는 도구가 제 래칫을 든다)
밖    **반입을 돌리지 않는다.** 레이크를 안 읽는다 — 그것이 이 자의 값이다.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pull():
    """`tools/pull_data.py` 를 **경로로** 들인다.

    ★ 2026-10-15. 종전에는 `sys.path` 에 `tools/` 를 꽂았다.
      `test_layering::test_sys_path_해킹이_없다` 가 그것을 금한다 — 꽂으면
      그 뒤 모든 시험의 import 가 달라지고, 순서에 따라 결과가 갈린다.
      `test_acquire.py` 가 쓰는 꼴(`spec_from_file_location`)을 그대로 쓴다.
    """
    spec = importlib.util.spec_from_file_location(
        "pull_data", ROOT / "tools/pull_data.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def test_no_chain_step_calls_a_retired_flag():
    """**이 판의 머리다**(DECISIONS 535-2). 체인이 **죽은 플래그**를 부르지 않는가.

    ★ **죽은 단계 하나가 맞는 자를 넉 달 가렸다** — 사유는 DECISIONS 535-2.
      폐지한 쪽(`acquire.RETIRED_FLAGS`)과 부르는 쪽을 기계가 댄다.
    """

    import acquire as A

    assert A.RETIRED_FLAGS, (
        "`RETIRED_FLAGS` 가 비었다 — 폐지를 적는 자리가 사라지면 이 자는 빈 그물이다")
    m = _pull()
    a = types.SimpleNamespace(keep_landing=False, all=True)
    bad = ["  " + x for x in _calls_retired(m.steps(a), A.RETIRED_FLAGS)]
    assert not bad, (
        "체인이 **폐지된 플래그**를 부른다 — 그 단계는 거절만 하고 죽으므로\n"
        "  뒤의 단계가 **통째로 안 돈다.**\n" + "\n".join(bad)
        + "\n  폐지한 절: "
        + " · ".join(f"{k} → {v}" for k, v in A.RETIRED_FLAGS.items()))


def test_the_ledger_missing_count_is_a_ratchet():
    """대장이 적은 자산 중 **아직 안 들어온 것**의 수. 내려가는 쪽으로만.

    ★ `judge()` 는 레이크를 glob 하므로 **레이크 없는 기계에서 침묵한다.**
      커밋되는 sha 대장으로 같은 수를 내면 어디서나 운다(535-2).
    """
    import acquire as A

    got = A.missing_from_register()
    assert len(got) <= A.LEDGER_MISSING, (
        f"대장에 적고 **안 들어온** 자산이 {len(got)} 다 — 선언 {A.LEDGER_MISSING} 보다 늘었다.\n"
        + "\n".join(f"  {k}  {g}" for k, g in got)
        + "\n  반입하거나(`tools/pull_data.py --yes`) 대장에서 빼라."
        "\n  ★ 늘리는 쪽으로는 안 고친다 — 그 수가 곧 **빚**이다.")
    assert len(got) == A.LEDGER_MISSING, (
        f"결손이 {A.LEDGER_MISSING} → {len(got)} 로 **줄었다.** 좋은 일이다 — "
        f"`acquire.LEDGER_MISSING` 을 {len(got)} 로 내려 적어라. "
        "안 내리면 다음에 늘어도 안 운다.")


def _no_way_in(rules, globs) -> list[tuple[str, str]]:
    """대장이 적은 정규명 중 **어느 통과 규칙에도 안 맞는** 것. 두 시험이 쓴다."""
    import re as _re

    out = []
    for k, gs in globs.items():
        pats = [g for g in (gs if isinstance(gs, list) else [gs]) if g]
        for g in pats:
            name = g.rsplit("/", 1)[-1]
            if any(c in name for c in "*?["):      # 글롭은 이름을 안 정한다
                continue
            if not any(_re.match(a, name) for a, _, _ in rules):
                out.append((k, g))
                break
    return out


def test_every_ledger_asset_has_a_way_in():
    """★ **이 판의 머리다**(DECISIONS 535-3). 대장이 적은 자산에 **들어올 길**이 있는가.

    2026-10-14 에 반입이 **네 번 연속** 막혔다. 매번 다른 자리였고 매번
    「고치고 다시 돌려라」였다 —

        ① `normalize_raw.RULES` 에 원본 이름 규칙이 없다
        ② `pull_data` 가 폐지된 `quarantine` 을 부른다
        ③ `providers` 에 `gjpolice` 가 없다 (통과 규칙이 정규명을 못 받는다)
        ④ `PASSTHROUGH_EXT` 에 `xlsx` 가 없다

    ①③④ 는 **같은 물음의 세 얼굴**이다 — 「이 자산이 raw 에 앉을 수 있는
    이름인가」. 셋을 따로 고치면 다음 자산에서 **또 하나가 빠진다.**
    머리말이 적은 「hwp·pdf·ngi·nda 가 없어 왕복 멱등이 거짓이었던 이력」이
    그 자리의 네 번째였다.

    ★ 그래서 **수를 늘리는 대신 재는 자를 세운다.** 대장에 자산을 적는 그
      판에서 운다 — 반입을 돌릴 때가 아니라.
    """
    from firelane.acquire_rules import dataset_globs
    from firelane.normalize_raw import passthrough_rules

    bad = _no_way_in(passthrough_rules(), dataset_globs())
    assert not bad, (
        f"대장에 자리가 있는데 **들어올 길이 없는** 자산 {len(bad)}건 —\n"
        + "\n".join(f"  {k}  {g}" for k, g in bad)
        + "\n  셋 중 하나가 빠졌다: `normalize_raw.RULES`(원본 이름) · "
        "`layers.raw.providers`(stem 접두) · `PASSTHROUGH_EXT`(확장자).\n"
        "  ★ 이 자산은 **영원히 반입이 안 된다** — 반입을 돌려도 매번 같은 "
        "자리에서 멈춘다.")


def test_the_way_in_probe_bites():
    """★ **카나리아.** 세 얼굴을 합성으로 하나씩 막아 본다."""
    rules = [(r"^gjcity_[a-z0-9_-]+_\d{8}\.(csv|xlsx)$", "gjcity", None)]
    ok = {"a": "gjcity/gjcity_x_jngj_20260101.csv"}
    assert not _no_way_in(rules, ok), "맞는 이름을 막았다 — 거짓 빨강은 꺼진다"

    assert _no_way_in(rules, {"b": "gjpolice/gjpolice_x_jngj_20260101.csv"}), (
        "제공기관이 없는데 통과시킨다")
    assert _no_way_in(rules, {"c": "gjcity/gjcity_x_jngj_20260101.hwpx"}), (
        "확장자가 없는데 통과시킨다")
    assert _no_way_in(rules, {"d": "gjcity/한글이름.csv"}), (
        "원본 이름 규칙이 없는데 통과시킨다")
    assert not _no_way_in(rules, {"e": "gjcity/gjcity_*_2026*.csv"}), (
        "글롭은 이름을 안 정하므로 **안 본다** — 보면 거짓 빨강이 난다")


def _calls_retired(steps, retired: dict[str, str]) -> list[str]:
    """체인 단계들이 부르는 **폐지 플래그**. 두 시험이 같은 자를 쓴다."""
    return [f"{s.name}: {f}" for s in steps for f in retired if f in s.cmd]


def test_the_probe_bites_both_ways():
    """★ **카나리아.** 같은 자를 합성 입력 둘로 민다 — 안 울면 빈 그물이다.

    위 둘은 실물을 보므로 **지금 깨끗하면 늘 초록**이다. 그 초록이 「봤다」인지
    「안 봤다」인지 가르는 길이 없으면 그것은 그물이 아니다(§445).
    """
    S = types.SimpleNamespace
    dead = {"--quarantine": "DECISIONS §173-2"}

    bad = [S(name="q", cmd=["python", "acquire.py", "--quarantine"]),
           S(name="judge", cmd=["python", "acquire.py"])]
    assert _calls_retired(bad, dead), "폐지 플래그를 부르는데 못 집는다 — 빈 그물이다"

    ok = [S(name="judge", cmd=["python", "acquire.py"]),
          S(name="prep", cmd=["python", "-m", "firelane.prep", "--apply"])]
    assert not _calls_retired(ok, dead), "깨끗한 체인을 빨갛다고 한다 — 거짓 빨강은 꺼진다"

    assert not _calls_retired(bad, {}), (
        "폐지 표가 비면 아무것도 안 집어야 한다 — 그래야 `RETIRED_FLAGS` 가 "
        "비었을 때의 빈 그물을 위 시험이 따로 막는 뜻이 선다")

