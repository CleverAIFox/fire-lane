"""봉인 무효화가 **실제 영향만큼만 넓은가.**

★ 2026-09-25 (DECISIONS §255). 종전에는 `SEAL.json` 의 `tool` 지문 **하나**가
  봉인 전체를 무효화했다. `_tool_print()` 가 `dms.py` 가 부르는 도구 다섯
  (`dms` · `dupcheck` · `deadcheck` · `env_check` · `verify.sh`)을 한 해시로
  합쳤기 때문이다. 그래서 —

      `dupcheck.py` 한 줄 수정  →  절 1,036개가 통째로 재검사 대상

  `dupcheck` 는 **코드 사본을 세는 도구**이고 절 내용과 아무 상관이 없다.
  실제로 이 배치가 `verify.sh` 에 단계 하나를 더한 순간 봉인 전체가 무효가 됐다.

★ **그 구조가 「감사할 일을 만든다».** 전수 재검사는 비싸고, 사람이 그것을
  회피하기 시작하면 봉인은 장식이 된다. §243 이 「선언이 검사보다 넓으면 거짓
  초록이 된다」를 적었고 이것은 그 거울상이다 — **무효화가 영향보다 넓으면
  재검사가 습관적으로 건너뛰어진다.**

★ 이 파일이 지키는 것은 둘이다. ① 축별 무효가 **실제로 좁게** 나오는가
  ② 새 축이 생겼는데 `axis_tools()` 에 없으면 우는가 — **손목록이 실물보다
  좁아지는 것**이 이 저장소가 반복해 겪은 형태다(W3-8 족).

IN    tools/dms.py (읽기) · data/dms/SEAL.json (있으면)
OUT   없음
PARAM 없음
밖    어느 도구가 어느 축을 **정말** 정하는지는 사람이 판단한다. 이 검사는
      그 선언이 **실물 축을 다 덮는가**와 **판정이 선언대로 도는가**만 본다.
      선언 자체가 틀렸으면(예: `sections` 가 `dupcheck` 에도 의존한다면)
      여기서는 안 잡힌다 — 그것은 `seal` 재실행이 잡는다.
"""
from __future__ import annotations

import json
from pathlib import Path

import dms
import pytest

ROOT = Path(__file__).resolve().parent.parent
SEAL = ROOT / "data/dms/SEAL.json"


def _fake_old(**over) -> dict:
    """지금 도구 지문을 그대로 담은 **가짜 옛 봉인.** 한 도구만 흔들어 쓴다."""
    base = {"tools": dict(dms._tool_prints()), "tool": dms._tool_print()}
    tools = base["tools"]
    for name, val in over.items():
        key = f"tools/{name}"
        assert key in tools, f"{key} 가 도구 범위에 없다 — 범위가 바뀌었다"
        tools[key] = val
    return base


# ── 선언이 실물을 덮는가 ────────────────────────────────────────
def test_every_sealed_axis_is_declared():
    """**실물 봉인의 축이 전부 선언돼 있는가.** 빠진 축은 아무도 안 본다."""
    if not SEAL.exists():
        pytest.skip("환경skip(산출물) — 봉인이 아직 없다. `dms.py seal` 이 찍는다")
    keys = set(json.loads(SEAL.read_text(encoding="utf-8")))
    missing = sorted(keys - set(dms.axis_tools()) - set(dms.SEAL_META))
    assert not missing, (
        f"봉인에 있는데 `axis_tools()` 에 없는 축: {missing}\n"
        "  선언 밖의 축은 **무효 판정을 안 받는다** — 도구가 바뀌어도 유효한\n"
        "  것처럼 남는다. 축을 더하고 어느 도구가 그것을 정하는지 적어라.\n"
        "  봉인 자신의 기록이면 `SEAL_META` 에 넣어라.")


def test_no_declared_axis_is_a_ghost():
    """반대 방향 — 선언에만 있고 봉인에 없는 축. 있으면 선언이 낡았다."""
    if not SEAL.exists():
        pytest.skip("환경skip(산출물) — 봉인이 아직 없다")
    keys = set(json.loads(SEAL.read_text(encoding="utf-8")))
    ghost = sorted(set(dms.axis_tools()) - keys)
    assert not ghost, (
        f"`axis_tools()` 에만 있고 봉인에 없는 축: {ghost}\n"
        "  유령 선언은 「있다고 적혀 있으면 사람이 안 본다」의 형태다(§243).")


def test_the_declared_tools_exist():
    """선언이 가리키는 도구가 실물인가. 없는 파일을 가리키면 **영영 안 바뀐다.**"""
    scope = {p.relative_to(ROOT).as_posix() for p in dms._tool_scope()}
    bad = []
    for axis, tools in dms.axis_tools().items():
        for t in tools:
            if not (ROOT / t).is_file():
                bad.append(f"{axis} → {t} (파일이 없다)")
            elif t not in scope:
                bad.append(f"{axis} → {t} (`dms` 도구 범위 밖 — 지문이 안 잡힌다)")
    assert not bad, (
        "선언이 잡히지 않는 도구를 가리킨다:\n  " + "\n  ".join(bad) + "\n"
        f"  범위: {sorted(scope)}\n"
        "  범위는 `dms.py` 본문의 `tools/…` 리터럴에서 나온다(`_tool_scope`).")


# ── 무효가 좁게 나오는가 ────────────────────────────────────────
def test_nothing_is_stale_when_no_tool_moved():
    """아무 도구도 안 바뀌면 **전 축이 살아 있다.** 이게 안 되면 봉인이 무의미하다."""
    assert dms.stale_axes(_fake_old()) == {}, (
        "도구가 그대로인데 무효인 축이 있다 — 지문 계산이 결정적이지 않다.")


def test_a_counting_tool_does_not_invalidate_the_sections():
    """**`dupcheck` 를 고쳐도 절 1,036개는 살아 있다.** 이것이 §255 의 전부다."""
    stale = dms.stale_axes(_fake_old(**{"dupcheck.py": "0" * 16}))
    # ★ 2026-09-25 실측 정정. `dup_groups` **와 `enforcers`** 둘이다 —
    #   `PROBES` 가 `dupcheck --selftest` 를 돌리므로 강제자 기록도 정당하게
    #   무효다. 처음에 `{"dup_groups"}` 하나로 적었고 **입증이 그것을 잡았다.**
    #   선언을 손으로 좁히면 이렇게 틀린다(§255-2).
    assert set(stale) == {"dup_groups", "enforcers"}, (
        f"`dupcheck.py` 하나를 고쳤는데 무효 축이 {sorted(stale)} 다.\n"
        "  기대는 `dup_groups`(사본군을 세는 도구다) · `enforcers`(PROBES 가 돌린다).")
    # **여기가 §255 의 전부다** — 절 축 셋은 살아 있다.
    for axis in ("sections", "denominator", "dead_refs"):
        assert axis not in stale, (
            f"`{axis}` 가 사본 세기에 딸려 무효가 됐다.\n"
            "  `dupcheck` 는 코드 사본을 세는 도구고 절 내용과 무관하다.\n"
            "  종전에는 이 한 줄이 봉인 **전체**를 무효화했다.")
    assert "docs" not in stale and "raw" not in stale


def test_the_parser_tool_does_invalidate_the_sections():
    """반대로 **`dms.py` 가 바뀌면 절 축은 무효다.** 좁히기만 하면 안 된다."""
    stale = dms.stale_axes(_fake_old(**{"dms.py": "0" * 16}))
    for axis in ("sections", "denominator", "dead_refs"):
        assert axis in stale, (
            f"`dms.py` 가 바뀌었는데 `{axis}` 가 유효하다고 나온다.\n"
            "  절 해시·상태·물림은 이 도구의 파싱·분류 규칙이 정한다 —\n"
            "  규칙이 바뀌면 옛 통과는 증표가 아니다.")
    assert "dup_groups" not in stale, "사본군까지 딸려 무효가 됐다 — 여전히 너무 넓다"


def test_the_gate_tools_invalidate_only_the_enforcer_record():
    """관문 도구가 바뀌면 **강제자 기록만** 무효다."""
    for name in ("verify.sh", "deadcheck.py", "env_check.py"):
        stale = dms.stale_axes(_fake_old(**{name: "0" * 16}))
        assert set(stale) == {"enforcers"}, (
            f"`{name}` 하나를 고쳤는데 무효 축이 {sorted(stale)} 다.\n"
            "  이 배치가 실제로 `verify.sh` 에 단계를 더했고, 종전 구조에서는\n"
            "  그 한 줄에 봉인 전체가 무효가 됐다.")


def test_the_tool_free_axes_survive_every_tool_change():
    """**도구와 무관한 축**은 도구가 전부 바뀌어도 살아 있다.

    `docs` · `raw` · `code` 는 순수 파일·입력 해시다. 도구를 고쳐도 그 파일의
    내용이 달라지지 않는다 — 무효로 보는 것은 근거 없는 재검사다.
    """
    dead = {f"{p.name}": "0" * 16 for p in dms._tool_scope()}
    stale = dms.stale_axes(_fake_old(**dead))
    for axis in ("docs", "raw", "code", "declared_red"):
        assert axis not in stale, (
            f"도구를 다 바꿨는데 `{axis}` 가 무효로 나온다 — 그 축은 도구를 안 쓴다.")


def test_an_old_seal_is_treated_as_fully_stale():
    """`tools` 칸이 없는 옛 봉인은 **전 축 무효**다. 모를 때 유효하다 하지 않는다."""
    stale = dms.stale_axes({"tool": "abc"})
    assert set(stale) == set(dms.axis_tools()), (
        "옛 봉인인데 일부 축을 유효하다고 본다 — 축별 판정의 재료가 없는데\n"
        "  유효하다고 말하는 것은 검사를 끄는 것과 같다.")
    assert dms.stale_axes({}) , "봉인이 비어도 전 축 무효여야 한다"


def test_the_probe_itself_is_alive():
    """카나리아 — 판별식이 죽으면 위 전부가 **조용히 초록**이다."""
    assert dms.stale_axes(_fake_old()) == {}, "기준선이 안 맞는다"
    got = dms.stale_axes(_fake_old(**{"dupcheck.py": "x"}))
    assert got, "도구를 흔들었는데 아무것도 안 잡힌다 — 판별식이 죽었다"
    assert len(dms._tool_prints()) >= 4, (
        f"도구 지문이 {len(dms._tool_prints())}개뿐이다 — 범위가 줄었다")
    assert set(dms._tool_prints()) == {
        p.relative_to(ROOT).as_posix() for p in dms._tool_scope()}, "범위와 지문이 어긋난다"

# ── 입증 — 선언이 실물 호출을 덮는가 ──────────────────────────
def test_the_enforcer_axis_is_derived_not_hand_written():
    """**손목록은 실물보다 좁아진다.** `enforcers` 는 `PROBES` 에서 뽑아야 한다.

    ★ 2026-09-25. 이 표를 처음 손으로 적었을 때 `enforcers` 에서 `dms.py` 와
      `dupcheck.py` 를 빠뜨렸다 — `PROBES` 가 그 둘을 `--selftest` 로 돌리는데
      그것을 안 봤다. **입증 없이 무효 범위를 좁힌 것**이고, 좁힌 축은
      「도구가 바뀌었는데 유효하다」고 말한다. 거짓 초록보다 나쁘다.
    """
    got = set(dms.axis_tools()["enforcers"])
    want = {"tools/verify.sh"} | {str(c[0]) for _l, c in dms.PROBES
                                  if str(c[0]).startswith("tools/")}
    assert got == want, (
        f"`enforcers` 선언이 실물 프로브와 다르다\n  선언 {sorted(got)}\n  실물 {sorted(want)}\n"
        "  `PROBES` 에 프로브를 더하면 이 축의 범위가 **저절로** 따라가야 한다.")
    assert len(want) >= 4, f"프로브가 {len(want)}개뿐이다 — `PROBES` 가 줄었다"


def test_no_axis_declares_less_than_the_code_calls():
    """축 값을 만드는 코드가 **선언 밖 도구**를 부르면 그 축은 거짓으로 유효해진다.

    `cmd_seal` 이 축 값을 조립하면서 `_run([sys.executable, "tools/…"])` 로 부르는
    도구를 뽑아, 어느 축도 그것을 빠뜨리지 않았는지 본다. 정적 추출이라 실행이
    필요 없다.
    """
    import ast

    src = (ROOT / "tools/dms.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "cmd_seal")
    called = {s.value for s in ast.walk(fn)
              if isinstance(s, ast.Constant) and isinstance(s.value, str)
              and s.value.startswith("tools/")}
    declared = {t for ts in dms.axis_tools().values() for t in ts}
    missed = sorted(called - declared)
    assert not missed, (
        f"`cmd_seal` 이 부르는데 어느 축도 선언하지 않은 도구: {missed}\n"
        f"  선언된 것: {sorted(declared)}\n"
        "  그 도구가 바뀌어도 모든 축이 「유효하다」고 말한다 — **입증 없이 좁힌 것**이다.\n"
        "  어느 축의 값을 그 도구가 만드는지 적어라.")
    assert called, "도구 호출을 하나도 못 찾았다 — 추출기가 죽었다(빈 그물)"


def test_the_declaration_is_not_wider_than_the_code_either():
    """반대 방향 — 아무도 안 부르는 도구를 선언하면 **쓸데없이 무효가 넓어진다.**

    ★ 이 검사는 `verify.sh` 를 뺀다. 그것은 `bash` 로 불리므로 위 추출기의
      `sys.executable` 경로에 안 잡힌다 — 안 잡히는 것과 안 부르는 것은 다르다.
    """
    import ast

    src = (ROOT / "tools/dms.py").read_text(encoding="utf-8")
    all_lit = {s.value for s in ast.walk(ast.parse(src))
               if isinstance(s, ast.Constant) and isinstance(s.value, str)
               and s.value.startswith("tools/")}
    declared = {t for ts in dms.axis_tools().values() for t in ts} - {"tools/verify.sh"}
    ghost = sorted(declared - all_lit)
    assert not ghost, (
        f"선언에만 있고 `dms.py` 가 이름조차 안 드는 도구: {ghost}\n"
        "  그 도구가 바뀔 때마다 근거 없이 축이 무효가 된다 — 재검사를 습관적으로\n"
        "  건너뛰게 만드는 쪽이다(§255).")


# ── 재도장이 계보를 같이 갱신하는가 ────────────────────────────
def test_resealing_also_refreshes_the_lineage_entry(tmp_path):
    """★ 2026-09-27 실기 (DECISIONS §267). 재도장이 대장을 고치는데 `_lineage.json` 은
    옛 해시를 든 채였다. 바로 다음 `segments` 가 「입력이 바뀌었으니 상류부터
    다시 돌려라」로 막혔다 — **재도장이 재빌드를 부르는** 자리였고, 그것은 이
    도구가 없애려던 바로 그 비용이다(DECISIONS §224-2).

    밖  재도장이 **무엇을** 고치는지는 위 시험들이 든다. 여기서 보는 것은
        「고친 뒤 계보가 따라오는가」 하나다.
    """
    import importlib.util
    import json
    import sys

    root = Path(__file__).resolve().parents[1]
    # ★ 2026-10-11 (DECISIONS §460). 재도장의 집이 `reseal.py` 다.
    spec = importlib.util.spec_from_file_location("ss_lin", root / "src/firelane/reseal.py")
    assert spec and spec.loader
    ss = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ss      # @dataclass 가 되짚는다 (DECISIONS §258-10)
    spec.loader.exec_module(ss)
    from firelane import lineage

    man = tmp_path / "_manifest.json"
    man.write_text(json.dumps({"datasets": [{"key": "a"}]}, ensure_ascii=False), encoding="utf-8")
    lin = tmp_path / lineage.LINEAGE
    lin.write_text(json.dumps({"ingest": {"outputs": {
        "data/processed/_manifest.json": {"kind": "manifest", "n": 1, "sha256": "옛해시"}}}},
        ensure_ascii=False), encoding="utf-8")

    ss._relineage(man)

    got = json.loads(lin.read_text(encoding="utf-8"))["ingest"]["outputs"][
        "data/processed/_manifest.json"]
    assert got["sha256"] != "옛해시", "계보가 안 따라온다 — 다음 단계가 상류 재실행을 요구한다"
    assert got == lineage._manifest_digest(man), "계보 값이 `lineage` 의 계산과 다르다 — 두 벌이다"


def test_relineage_is_wired_into_the_reseal_path():
    """★ 함수만 있고 안 불리면 장식이다. 부르는 자리를 짚는다."""
    import ast

    root = Path(__file__).resolve().parents[1]
    # ★ 2026-10-11 (DECISIONS §460). 재도장의 집이 `reseal.py` 로 갈라졌다 —
    #   길이 상한이 그 경계를 가리켰고 물음도 둘이다. **문 셋을 다 짚는다.**
    src = (root / "src/firelane/reseal.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for name in ("reseal_code_cli", "reseal_cfg_cli"):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        called = {n.func.id for n in ast.walk(fn)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "_relineage" in called, (
            f"{name} 이 계보를 안 갱신한다 — §267 이 그대로 돌아온다")


# ── 코드 칸만 받아주는 문 (DECISIONS §496) ───────────────────
# ★ `reseal.reseal_code` 는 **사람이 판단해 받아주는 문**이다(§224-2).
#   `code` 는 ingest 가 import 하는 모듈 전부의 로직 지문이라, 산출물을 한
#   바이트도 바꾸지 않는 변경(안내 문구 · 종료코드)에도 65종이 전부 찢어진다.
#   이 8GB 기계에서 전량 재빌드는 `ngii_road` 에서 거의 반드시 죽으므로,
#   그 문이 없으면 **ingest 를 고칠 수 없는 구조**가 된다.
#
# ★ 그런데 그 문을 미는 자리가 없었다 — `tools/srccov.py` 가 셌다(§493 · §496).
#   「공짜로 열어주지 않는다」가 이 함수의 약속이고, 그 약속이 이 절의 과녁이다.
def _reseal_mod():
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "rs_code", root / "src/firelane/reseal.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _sealed(tmp_path, code: str = "옛코드"):
    """raw · out 이 **실물과 같은** 레코드 한 벌. 그래야 받아줄 자격이 있다."""
    from firelane import shardseal as ss

    tmp_path.mkdir(parents=True, exist_ok=True)
    raw = tmp_path / "raw.csv"
    raw.write_text("a,b\n1,2\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    (out / "o.csv").write_text("x\n", encoding="utf-8")
    seal = {"raw": ss.raw_print([raw]), "cfg": "C", "code": code,
            "out": ss.out_print(out, ["o.csv"])}
    rec = {"key": "k", "status": "OK", "seal": seal}
    cfg = {"datasets": {"k": {"stem": "x"}}}
    return rec, cfg, out, raw


def test_reseal_code_fixes_only_the_code_slot(tmp_path):
    """★ 본체. `code` 만 바뀌고 나머지 **셋은 그대로**다.

    raw · cfg · out 이 「무엇으로 만들었나」의 증거다. 하나라도 같이 고치면
    이 문이 봉인을 **지어내는** 자리가 된다.
    """
    m = _reseal_mod()
    rec, cfg, out, raw = _sealed(tmp_path)
    before = dict(rec["seal"])
    fixed, skipped = m.reseal_code([rec], cfg, out, "새코드",
                                   lambda _k, _e: [raw])
    assert (fixed, skipped) == (["k"], [])
    assert rec["seal"]["code"] == "새코드"
    for slot in ("raw", "cfg", "out"):
        assert rec["seal"][slot] == before[slot], slot


def test_reseal_code_refuses_when_the_outputs_moved(tmp_path):
    """★ 산출물이 달라졌으면 **안 받는다** — 다시 빌드해야 하는 상태다."""
    m = _reseal_mod()
    rec, cfg, out, raw = _sealed(tmp_path)
    (out / "o.csv").write_text("달라졌다\n", encoding="utf-8")
    fixed, skipped = m.reseal_code([rec], cfg, out, "새코드",
                                   lambda _k, _e: [raw])
    assert (fixed, skipped) == ([], ["k"])
    assert rec["seal"]["code"] == "옛코드", "받아주면 안 되는 것을 받았다"


def test_reseal_code_refuses_when_the_inputs_moved(tmp_path):
    """★ raw 가 달라졌으면 **안 받는다** — 같은 입력이라는 전제가 깨졌다."""
    m = _reseal_mod()
    rec, cfg, out, raw = _sealed(tmp_path)
    raw.write_text("a,b\n9,9\n", encoding="utf-8")
    assert m.reseal_code([rec], cfg, out, "새코드",
                         lambda _k, _e: [raw]) == ([], ["k"])
    assert rec["seal"]["code"] == "옛코드"


def test_reseal_code_skips_a_record_whose_paths_cannot_be_resolved(tmp_path):
    """대장에서 실물을 못 찾으면 건너뜀이다 — **조용히 고치지 않는다.**"""
    m = _reseal_mod()
    rec, cfg, out, _raw = _sealed(tmp_path)

    def boom(key, _e):
        raise KeyError(key)

    assert m.reseal_code([rec], cfg, out, "새코드", boom) == ([], ["k"])


def test_reseal_code_ignores_records_it_has_no_business_with(tmp_path):
    """★ 음성 셋 — 실패한 레코드 · 봉인지가 없는 것 · **이미 같은 것.**

    셋 다 「건너뜀」이 아니라 **아무 말도 안 한다** — 건너뜀은 「받아줄
    자격이 있었는데 증거가 안 맞았다」는 뜻이고, 그 둘을 섞으면 보고가
    거짓이 된다.
    """
    m = _reseal_mod()
    rec, cfg, out, raw = _sealed(tmp_path)
    def paths(_key, _entry):
        return [raw]

    bad_status = {**rec, "status": "FAIL"}
    assert m.reseal_code([bad_status], cfg, out, "새코드", paths) == ([], [])

    no_seal = {"key": "k", "status": "OK"}
    assert m.reseal_code([no_seal], cfg, out, "새코드", paths) == ([], [])

    half = {"key": "k", "status": "OK", "seal": {"raw": "r", "out": {}}}
    assert m.reseal_code([half], cfg, out, "새코드", paths) == ([], [])

    same, cfg2, out2, raw2 = _sealed(tmp_path / "b", code="새코드")
    assert m.reseal_code([same], cfg2, out2, "새코드",
                         lambda _k, _e: [raw2]) == ([], [])
