"""`tools/docgen.py` — **문서에 실물을 넣는 도구가 살아 있는가.**

★ 2026-09-25 (DECISIONS §246). 축은 §246 이 세웠고 **울기만 했다.** 절 수를
  하루에 네 번 손으로 맞췄고, 봉인 소스 종수는 64 → 71, PLAN §1 제목은
  열두 번 고쳐졌다. 검사가 사람을 부르고 사람이 같은 줄을 고치는 구조는
  반드시 갈린다 — 그래서 값을 **넣는** 자리가 생겼다.

★ **주입기에는 고유한 위험이 둘 있다.**
  ① 조용히 아무것도 안 넣는다. 표기가 바뀌면 정규식이 0곳을 찾고, 0곳은
     초록이다. `deadcheck` ③ 이 보는 그 형태다.
  ② 조용히 **틀린 것을 넣는다.** 문서를 실물로 맞추는 도구가 실물을 잘못
     읽으면, 그 순간부터 문서는 「기계가 보증한 거짓」이 된다. 검사보다
     나쁘다 — 검사는 사람을 부르고 주입기는 사람을 안 부른다.
  둘을 합성 문서로 직접 문다. 실물 저장소가 초록인 것만으로는 못 묻는다.

IN    `tools/docgen.py` · 합성 문서 · 실물 저장소
OUT   없음
PARAM 없음
밖    ① **채워진 값이 참인가는 여기서 안 본다.** `truth()` 가 부르는
         `ledger.load()` · `dms.scan()` · `plan_renumber` 는 각자의 강제자가
         든다(`test_lake` · `test_dms_ids` · `test_declaration_sync`). 여기서
         보는 것은 **그 값이 문서에 그대로 들어가는가**다.
      ② **블록 밖의 같은 표기는 안 본다.** 그것은
         `tests/test_repo_numbers.py` 가 문서 넷 전부에서 본다.
      ③ **마크다운 렌더링은 안 본다.** 블록 표시가 화면에서 안 보이는지는
         사람이 발행물로 확인한다 — 이 저장소에 마크다운 변환기가 없다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import docgen

ROOT = Path(__file__).resolve().parent.parent

#: 합성 문서 하나로 여섯 축 전부를 덮는다. 실물 문서를 베끼지 않는다 —
#: 베끼면 실물이 바뀌는 날 이 시험이 실물을 따라가는 사본이 된다.
SYNTH = "\n".join([
    "머리말. 블록 밖의 표기는 `SYNTH_OUT` 이 따로 본다.",
    "",
    "<!--gen: datasets sealable-->",
    "대장은 하나다. `datasets` 1종 · `retired` 4종.",
    "`SEAL.json` 이 소스 2종의 raw sha256 을 갖는다.",
    "<!--/gen-->",
    "",
    "<!--gen: sections inherit blank-->",
    "절 3 전수 · **분모(blank) 4절** · 물림(inherit) 5절.",
    "<!--/gen-->",
    "",
    "<!--gen: plan_open-->",
    "## 1. 남은 일 — 6행",
    "<!--/gen-->",
    "",
    # ★ 2026-09-25 (§258). 커버리지 래칫 축. 정본은 `tools/verify.sh` 의 선언 한 줄이고
    #   문서가 그 수를 손으로 들면 올릴 때 한쪽만 움직인다 — 그날 실제로 그랬다.
    "<!--gen: cov_min-->",
    "커버리지는 래칫이다. `COV_MIN=7` 로 걸려 있다.",
    "<!--/gen-->",
    "",
])

#: 블록 **밖**에 같은 표기가 있는 문서. 축 하나를 블록으로 덮고 같은 표기를
#: 블록 밖에 한 번 더 둔다 — 고치는 자리가 좁은지 이것으로 묻는다.
SYNTH_OUT = "\n".join([
    "블록 밖이다 — `datasets` 999종 은 안 고쳐져야 한다.",
    "",
    "<!--gen: datasets-->",
    "블록 안이다 — `datasets` 1종.",
    "<!--/gen-->",
    "",
])

WANT = {"datasets": 72, "sealable": 71, "sections": 1036,
        "inherit": 352, "blank": 0, "plan_open": 108, "cov_min": 32}


def _one(text: str, want: dict[str, int] | None = None) -> docgen.Result:
    return docgen.apply_all({"x.md": text}, want or WANT)


# ── ① 넣는가 ────────────────────────────────────────────────────
def test_every_axis_is_injected_into_the_block():
    """모든 축이 **합성 문서에서** 실제로 갈린다. 축 하나가 죽으면 여기서 운다."""
    res = _one(SYNTH)
    got = res.texts["x.md"]
    for axis, v in WANT.items():
        assert docgen.claims(axis, got) == [v], (
            f"`{axis}` 가 블록에서 안 갈렸다 — 실물 {v} · 문서 {docgen.claims(axis, got)}\n"
            "  주입기가 그 축의 표기를 못 찾거나 자리를 잘못 잡았다.")
    assert res.seen == dict.fromkeys(WANT, 1), f"축별 치환 건수가 1이 아니다: {res.seen}"
    assert not res.broken, res.broken


def test_the_notation_itself_survives_injection():
    """수만 갈아 넣는다 — **앵커와 산문은 그대로다.**

    ★ 앵커까지 새로 쓰면 이 도구가 문서의 문장을 쓰게 되고, 사람이 쓴 산문이
      배치마다 되돌려진다. 그리고 `docnum_check` · `test_repo_numbers` 의
      정규식이 앵커를 보고 무는데, 앵커가 흔들리면 그 검사들이 조용히 0건이 된다.
    """
    got = _one(SYNTH).texts["x.md"]
    assert "대장은 하나다. `datasets` 72종 · `retired` 4종." in got, \
        "앵커나 주변 산문이 바뀌었다"
    assert "## 1. 남은 일 — 108행" in got, "제목 꼴이 깨졌다"
    assert "`retired` 4종" in got, "축이 아닌 수를 건드렸다 — `retired` 는 감시 밖이다(§246)"


def test_nothing_outside_a_block_is_touched():
    """블록 **밖**은 안 고친다. 고치는 자리는 좁아야 한다(도구 머리말 `밖` ①)."""
    res = _one(SYNTH_OUT)
    got = res.texts["x.md"]
    assert "블록 밖이다 — `datasets` 999종 은 안 고쳐져야 한다" in got, \
        "블록 밖의 표기를 고쳤다 — 문서 전체를 기계가 쓰게 된다"
    assert "블록 안이다 — `datasets` 72종." in got, "블록 안을 안 고쳤다"
    assert not [d for d in res.drift if "999" in d], \
        f"블록 밖을 어긋남으로 셌다: {res.drift}"


def test_a_document_without_blocks_comes_back_byte_identical():
    """블록이 없는 문서는 **한 바이트도** 안 바뀐다."""
    plain = "제목\n\n`datasets` 999종 이라고 적힌 산문.\n"
    res = docgen.apply_all({"x.md": plain}, WANT)
    assert res.texts["x.md"] == plain, "블록이 없는데 문서를 고쳤다"


# ── ② 무는가 — 판정기 자기검사 ──────────────────────────────────
def test_wrong_value_in_a_block_is_reported():
    """블록 값이 실물과 다르면 **어긋남으로 센다.** 이것이 `--check` 의 rc 다."""
    res = _one(SYNTH)
    assert len(res.drift) == len(WANT), (
        f"어긋남 {len(res.drift)}건 — 축 {len(WANT)} 개가 전부 틀린 합성 문서인데\n"
        f"  {len(WANT)} 건을 안 냈다: {res.drift}")
    assert all("→ 실물" in d for d in res.drift), f"어긋남이 실물을 안 말한다: {res.drift}"

    same = _one(_one(SYNTH).texts["x.md"])
    assert not same.drift, f"이미 맞는 문서에서 운다 — 멱등이 아니다: {same.drift}"
    assert not same.broken, same.broken


def test_a_block_that_matches_nothing_is_a_failure_not_a_pass():
    """표기가 바뀌어 **0곳**을 찾으면 실패다 — 0건은 통과가 아니다(`deadcheck` ③).

    ★ 주입기의 제일 조용한 죽음이다. 사람이 앵커 낱말 하나를 고치면 정규식이
      0곳을 찾고, 그 뒤로 그 수는 영원히 안 갈린다. 아무도 안 운다.
    """
    res = _one("<!--gen: sections-->\n절이 몇인지 안 적는다.\n<!--/gen-->\n")
    assert any("0곳" in b for b in res.broken), (
        f"표기를 0곳 찾았는데 안 운다 — 빈 그물이다: {res.broken}")


def test_an_axis_with_no_block_anywhere_is_a_failure():
    """축이 **어느 블록에도** 없으면 실패다. 축만 늘고 블록이 없는 상태를 막는다."""
    res = _one("<!--gen: sections-->\n절 1 전수.\n<!--/gen-->\n")
    dead = [b for b in res.broken if "한 곳도 없다" in b]
    assert dead, f"축 다섯이 블록 없이 남았는데 안 운다: {res.broken}"
    assert "plan_open" in dead[0] and "datasets" in dead[0], \
        f"안 걸린 축을 이름으로 말하지 않는다: {dead[0]}"


def test_an_unclosed_or_unknown_block_is_a_failure():
    """문법이 깨진 블록은 조용히 지나가지 않는다."""
    res = _one("<!--gen: sections-->\n절 1 전수.\n")
    assert any("안 닫혔다" in b for b in res.broken), f"안 닫힌 블록을 안 운다: {res.broken}"
    res = _one("<!--gen: 없는축-->\n아무 말.\n<!--/gen-->\n")
    assert any("모르는 축" in b for b in res.broken), f"모르는 축을 안 운다: {res.broken}"


def test_dead_truth_is_refused_before_anything_is_written():
    """정본이 죽었으면 **채우기 전에** 죽는다.

    ★ 값이 0인 채로 채우면 문서가 「기계가 보증한 거짓」이 된다. 검사는 사람을
      부르는데 주입기는 안 부르므로, 주입기의 전제는 주입 전에 봐야 한다.
    """
    # ★ 2026-09-25. **축 목록에서 짓는다.** 손목록이던 종전 판은 축을 더한 날
    #   `KeyError` 로 죽었다 — 축이 늘면 손목록이 낡는다(§255-3 과 같은 형태).
    dead = dict.fromkeys(docgen.AXES, 0)
    why = docgen.alive(dead)
    assert len(why) >= 3, f"죽은 정본을 안 운다: {why}"
    assert not docgen.alive(WANT), f"정상 입력에서 운다: {docgen.alive(WANT)}"
    # 축이 통째로 빠진 것도 결함이다 — 조용히 0으로 읽으면 안 된다
    short = {a: v for a, v in WANT.items() if a != "cov_min"}
    assert any("실물이 없다" in w for w in docgen.alive(short)), "빠진 축을 안 운다"


def test_the_axis_pattern_captures_exactly_one_number():
    """축 정규식의 1번 그룹이 **수 하나**인가. 주입기가 그 자리만 갈아 넣는다.

    ★ 그룹이 앵커까지 품으면 주입이 산문을 먹는다. 그룹이 없으면 주입이
      아무것도 못 한다 — 둘 다 조용하다.
    """
    bad = []
    for name, ax in docgen.AXES.items():
        if ax.pat.groups != 1:
            bad.append(f"{name}: 그룹 {ax.pat.groups}개 — 하나여야 한다")
        if not ax.what.strip():
            bad.append(f"{name}: 뜻이 비었다 — 실패 메시지가 무의미해진다")
    assert not bad, "\n".join(bad)


# ── ③ 관문 ──────────────────────────────────────────────────────
def test_the_repository_blocks_agree_with_reality():
    """**실물 저장소**의 블록이 실물과 같은가. `verify.sh` 와 같은 판정이다."""
    want = docgen.truth()
    assert not docgen.alive(want), "\n".join(docgen.alive(want))
    res = docgen.apply_all(docgen.read_docs(), want)
    assert not res.broken, "생성 블록 구조:\n  " + "\n  ".join(res.broken)
    assert not res.drift, (
        "생성 블록이 실물과 다르다:\n  " + "\n  ".join(res.drift)
        + "\n  ★ 손으로 고치지 마라 — `uv run python tools/docgen.py` 가 채운다.")


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["uv", "run", "--no-sync", "python", "tools/docgen.py", *args],
                          cwd=ROOT, capture_output=True, text=True, check=False)


def test_the_command_line_returns_nonzero_when_a_block_is_wrong(tmp_path: Path):
    """`--check` 가 **종료코드로** 말하는가. 관문에 걸리는 것은 rc 다.

    ★ 판정 함수가 어긋남을 세는 것과 명령이 rc≠0 을 내는 것은 다른 일이다.
      이 저장소는 그 둘이 끊긴 도구를 겪었다 — `python -m firelane.ledger` 는
      FAIL 9 로 rc 1 을 내고 있었는데 `verify` · CI · 시험 어디에도 없어서
      초록이었다(DECISIONS §182-2).

    ★ **추적 문서를 흔들지 않는다.** 문서 셋을 복사한 트리에 틀린 값을 심고
      `--root` 로 그 트리를 보게 한다. 실물(대장 · `dms.scan()`)은 여전히 이
      저장소라, 심은 값과 실물이 어긋나는 상황이 그대로 재현된다.
    """
    ok = _cli("--check")
    assert ok.returncode == 0, f"실물이 맞는데 운다:\n{ok.stdout}{ok.stderr}"
    assert "생성 블록" in ok.stdout, f"무엇을 봤는지 안 말한다:\n{ok.stdout}"

    n = docgen.truth()["plan_open"]
    for rel in docgen.DOCS:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    plan = tmp_path / "docs" / "PLAN.md"
    head = plan.read_text(encoding="utf-8")
    assert f"## 1. 남은 일 — {n}행" in head, "PLAN §1 제목 블록이 사라졌다"
    plan.write_text(head.replace(f"## 1. 남은 일 — {n}행",
                                 f"## 1. 남은 일 — {n + 7}행"), encoding="utf-8")

    red = _cli("--check", "--root", str(tmp_path))
    assert red.returncode != 0, (
        "블록 값을 틀리게 만들었는데 `--check` 가 rc 0 을 냈다 — 관문이 비었다.\n"
        + red.stdout + red.stderr)
    assert "plan_open" in red.stdout, f"어느 축이 틀렸는지 안 말한다:\n{red.stdout}"

    # ★ 그리고 **채우면 낫는가.** 대조만 되고 주입이 안 되면 도구가 반쪽이다.
    fill = _cli("--root", str(tmp_path))
    assert fill.returncode == 0, f"채우기가 실패한다:\n{fill.stdout}{fill.stderr}"
    assert f"## 1. 남은 일 — {n}행" in plan.read_text(encoding="utf-8"), \
        "채웠는데 제목이 실물로 안 돌아왔다"
    assert _cli("--check", "--root", str(tmp_path)).returncode == 0, \
        "채운 뒤에도 `--check` 가 운다 — 주입과 대조가 다른 것을 본다"
    assert (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8") != \
        head.replace(f"## 1. 남은 일 — {n}행", f"## 1. 남은 일 — {n + 7}행"), \
        "`--root` 가 실물 저장소를 건드렸다"


def test_the_gate_and_the_workflow_both_run_it():
    """`verify.sh` 가 `--check` 를 부르는가. **만드는 것과 거는 것은 다른 일이다.**

    ★ `test_tools_are_wired` 가 「어디서든 도는가」를 보고, 여기서는 **관문
      단계로서** 도는지를 본다. 시험만 부르면 `dms seal` 이 그 통과를
      단계 통과로 읽지 않는다.
    """
    vs = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    assert "tools/docgen.py --check" in vs, \
        "verify.sh 에 `docgen --check` 단계가 없다 — 도구만 만들고 안 걸었다"
    assert "ci-exempt: tools/docgen.py" in vs, (
        "CI 에서 안 도는데 `# ci-exempt:` 선언이 없다 — `gate_parity` 가 미선언으로 센다.\n"
        "  CI 에 단계를 붙였으면 이 줄과 면제 선언을 같이 지워라.")
