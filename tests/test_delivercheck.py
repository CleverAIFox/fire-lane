#!/usr/bin/env python3
"""
test_delivercheck.py — 배달물 판별식이 **살아 있는가.**  (DECISIONS §276-1)

── 왜 생겼나 ──────────────────────────────────────────────────
`deliver.py` 가 밑동·폐포·산출물·스윕·pytest 를 다 재면서 **PR 본문만 안 쟀다.**
검사기(`pr_body_check.py`)는 저장소에 있었고 그날 아침에 그것을 고치기까지 했는데,
**보내기 전 예습에는 안 걸었다.** 배치 B 에서 본문 둘이 체크박스를 안 골라
왕복 둘을 태웠다 — 둘 다 보내기 전에 기계가 알 수 있었다.

IN    tools/delivercheck.py
OUT   없음 (검사)
밖    **패치가 붙는지는 안 본다** — 워크트리를 떠야 알고 `deliver.dryrun` 이 든다.
      **본문의 내용이 옳은지도 안 본다** — 템플릿을 채웠는가만 본다.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ★ `sys.path` 를 건드리지 않는다 — `test_layering::test_sys_path_해킹이_없다` 가
#   막는다. 경로를 박으면 그 파일이 어디 있는지가 두 곳에 적히고, 옮기는 날
#   한쪽만 따라간다. 저장소 관례대로 파일에서 직접 올린다.
# ★ 경로를 **한 줄 리터럴**로 적는다. `test_tools_are_wired` 의 배선 탐지가
#   줄 단위라, 두 줄로 나누면 「아무도 안 부른다」로 읽힌다(§276-1 꼬리).
_spec = importlib.util.spec_from_file_location("delivercheck", ROOT / "tools/delivercheck.py")
assert _spec and _spec.loader
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)


def _run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


BODY_OK = """## 무엇을 · 왜

배선만 바꿨다.

## 리뷰어가 볼 곳 — **한 곳만**

`src/firelane/ingest.py:230`

## 산출물이 바뀌는가

- [x] 안 바뀐다
- [ ] 바뀐다 → `tools/golden.py lock` 재잠금 + 아래에 전후 값

## 계약을 건드리는가

- [x] 안 건드린다
- [ ] `src/contracts/` · `test_contract.py` · `web/config.js` 를 건드린다
"""


def test_a_delivery_without_a_pr_body_cries():
    """★ 본문이 없으면 열차 2단계가 죽는다 — 보내기 전에 안다."""
    bad = D.bodies_missing(["0001-x.patch", "EXPECT", "BASE"])
    assert bad, "`PR_BODY.md` 가 없는데 안 운다"
    assert "2단계" in bad[0], "왜 문제인지 안 알려준다"


def test_a_delivery_with_a_pr_body_is_quiet():
    assert not D.bodies_missing(["PR_BODY.md", "PR_BODY_DEV.md", "0001-x.patch"])


def test_a_body_that_skips_the_template_cries(tmp_path: Path):
    """★ 2026-09-27 실제 사고. 체크박스를 안 골라 열차가 두 번 죽었다."""
    (tmp_path / "PR_BODY.md").write_text("## 무엇을 · 왜\n\n대충\n", encoding="utf-8")
    bad = D.bodies_bad(tmp_path, _run, sys.executable)
    assert bad, "템플릿을 안 채웠는데 안 운다"
    assert "PR_BODY.md" in bad[0]


def test_a_body_that_fills_the_template_is_quiet(tmp_path: Path):
    (tmp_path / "PR_BODY.md").write_text(BODY_OK, encoding="utf-8")
    assert not D.bodies_bad(tmp_path, _run, sys.executable)


def test_every_pr_body_is_checked_not_just_the_first(tmp_path: Path):
    """★ `PR_BODY_DEV.md` 가 이번에 빠졌다. 하나만 보면 나머지가 8단계에서 죽는다."""
    (tmp_path / "PR_BODY.md").write_text(BODY_OK, encoding="utf-8")
    (tmp_path / "PR_BODY_DEV.md").write_text("## 무엇을 · 왜\n\n대충\n", encoding="utf-8")
    bad = D.bodies_bad(tmp_path, _run, sys.executable)
    assert bad and any("DEV" in b for b in bad), "둘째 본문을 안 본다"


def test_the_checker_it_calls_actually_exists():
    """★ 카나리아. 검사기가 없으면 `bodies_bad` 는 **언제나 빨갛다** — 그것은 검사가 아니다."""
    assert (ROOT / D.BODY_CHECK).exists(), f"{D.BODY_CHECK} 가 없다"


@pytest.mark.parametrize(("names", "want"), [
    (["0001-a.patch", "0001-a.patch"], True),
    (["0001-a.patch", "0002-b.patch"], False),
])
def test_duplicate_patch_names_are_caught(names, want):
    assert bool(D.collide(names)) is want


@pytest.mark.parametrize(("names", "want"), [
    (["0001-x.patch", "0003-x.patch"], True),
    (["0001-x.patch", "0002-y.patch"], False),
])
def test_same_tail_different_number_is_caught(names, want):
    assert bool(D.tails(names)) is want


def test_forbidden_strings_are_read_from_the_message_not_the_diff(tmp_path: Path):
    """규약은 커밋 메시지에 걸린다. diff 안의 같은 글자는 결함이 아니다."""
    msg = tmp_path / "0001-x.patch"
    msg.write_text(f"제목\n\n{D.FORBIDDEN[0]} <x@y>\n", encoding="utf-8")
    assert D.forbidden([msg])
    clean = tmp_path / "0002-y.patch"
    clean.write_text("제목\n\n본문뿐이다\n", encoding="utf-8")
    assert not D.forbidden([clean])


def test_the_forbidden_list_is_not_empty():
    """★ 대장이 비면 통과가 아니라 **볼 것이 없음**이다(`deadcheck ③`)."""
    assert D.FORBIDDEN, "`FORBIDDEN` 이 비었다"


# ── ⑥ 스윕 채집과 기준선 대조 (§290-6) ───────────────────────────
# ★ `deliver.py` 가 상한을 또 넘어 이 블록이 여기로 왔다. 순수해서 시험이
#   직접 부를 수 있고, 그것이 옮긴 이유다 — 종전에는 `deliver --selftest` 만
#   들었고 그 자기검사는 `bad.append` 목록이라 **어느 팔이 죽었는지** 안 보였다.
SWEEP_OUT = (
    "\x1b[36m── 취입 계약 실물\x1b[0m\n\x1b[33m   생략\x1b[0m  레이크가 없다\n"
    "\n── 폭 교차대조\n   생략  산출물이 없다. 파이프라인을 먼저 돌려라\n"
    "\n── pytest\n   OK  1825 passed\n"
    "\n  실패 2\n    ✗ pytest                      1 failed\n"
    "    ✗ 문서 정합 도장              stamp --only <절>\n")


def test_sweep_verdict_reads_both_the_red_and_the_unexercised():
    red, skipped = D.sweep_verdict(1, SWEEP_OUT)
    assert red == {"pytest", "문서 정합 도장"}
    assert set(skipped) == {"취입 계약 실물", "폭 교차대조"}
    assert "레이크" in skipped["취입 계약 실물"]


def test_a_red_axis_is_not_swallowed_by_the_line_before_it():
    """★ **빨간 축을 조용히 떨구던 자리**(DECISIONS §319-3).

    종전 판별식은 끝맺음이 `(?:\\s{2,}|$)` 였고 `\\s` 가 **줄바꿈을 먹었다.**
    이름과 힌트 사이가 한 칸뿐인 줄은 `\\n` + 다음 줄 들여쓰기를 끝맺음으로
    삼켰고, 그러면 그 **다음 `✗` 줄이 통째로 안 잡힌다.**

    실측 2026-09-30 — 밑동 스윕에서 「선언 ↔ 실물」이 그렇게 빠졌다. 그리고
    배치 쪽에서는 앞 줄이 달라 잡혔으므로 **없던 「새 빨간불」이 생겨** 배달이
    거부됐다. 둘 중 **빠지는 쪽이 더 나쁘다** — 빨간 채로 나간다.
    """
    out = ("\n  실패 2\n"
           # ★ 이름과 힌트 사이가 **한 칸**이다. 이것이 방아쇠였다.
           "    ✗ 의존성 동기화 (uv sync) (v0.1.0) depends on `actionlint-py`\n"
           "    ✗ 선언 ↔ 실물                        죽은 참조 1 · 경고 12\n")
    red, _ = D.sweep_verdict(1, out)
    assert "선언 ↔ 실물" in red, f"앞 줄이 뒤 줄을 먹었다 — {red}"
    assert len(red) == 2, red
    # ★ 반대 방향. 힌트 칸은 이름에 들어오지 않는다.
    assert not any("죽은 참조" in x for x in red), red


def test_a_passing_step_is_not_counted_as_unexercised():
    """★ 초록을 생략으로 세면 **못 돈 축** 칸이 거짓이 된다."""
    assert not D.sweep_verdict(0, "── 이름\n   OK  잘 됐다\n")[1]


def test_a_dead_sweep_is_never_zero_red():
    """★ 죽었는데 이름을 못 읽으면 **0건이 아니라 한 건**이다(빈 그물 금지)."""
    red, _ = D.sweep_verdict(2, "세그멘테이션 오류")
    assert len(red) == 1 and "rc=2" in next(iter(red))
    assert not D.sweep_verdict(0, "다 초록이다")[0]


def test_the_lake_only_excuse_needs_its_predicate_to_hold(tmp_path):
    frag = next(iter(D.LAKE_ONLY))
    assert D.excused(frag, tmp_path), "레이크가 없는데 면제를 안 해준다"
    (tmp_path / "data" / "raw").mkdir(parents=True)
    assert D.excused(frag, tmp_path) is None, "레이크가 있는데 면제해준다 — 판별식이 죽었다"
    assert D.excused("test_아무거나", tmp_path) is None


def test_only_what_this_batch_newly_reddened_is_refused(tmp_path):
    assert D.new_red({"a::b"}, {"a::b"}, tmp_path, "시험") == []
    with pytest.raises(SystemExit):
        D.new_red({"a::b"}, {"a::b", "c::d"}, tmp_path, "시험")


def test_the_relock_axes_are_only_forgiven_when_relock_was_declared(tmp_path):
    axis = next(iter(D.RELOCK_AXES))
    assert "새 빨간불 0" in D.diff_sweep(set(), {axis}, tmp_path, relock=True)
    with pytest.raises(SystemExit):
        D.diff_sweep(set(), {axis}, tmp_path, relock=False)


def test_the_relock_axes_are_not_empty():
    """★ 대장이 비면 통과가 아니라 **볼 것이 없음**이다(`deadcheck ③`)."""
    assert D.RELOCK_AXES and D.LAKE_ONLY
    for why in D.RELOCK_AXES.values():
        assert len(why) > 30, "면제에 사유가 없다 — 사유 없는 면제는 도장 찍기다"


# ── §294 · zip 이 제 목록에 드는가 ──────────────────────────────


def _stage(tmp):
    for n in ("fire-lane-0001-x.patch", "EXPECT", "PR_BODY.md"):
        (tmp / n).write_text("x", encoding="utf-8")
    z = tmp / "fire-lane-batch.zip"
    z.write_text("", encoding="utf-8")
    return z


def test_zip_은_제_목록에_안_든다(tmp_path):
    """★ 이것이 4.5GB 를 만든 줄이다. 되돌리면 여기서 걸린다."""
    z = _stage(tmp_path)
    assert z.name not in [f.name for f in D.zip_items(tmp_path, z)]


def test_멀쩡한_것은_하나도_안_뺀다(tmp_path):
    """한쪽만 재면 「전부 빼기」가 통과한다."""
    z = _stage(tmp_path)
    assert sorted(f.name for f in D.zip_items(tmp_path, z)) == [
        "EXPECT", "PR_BODY.md", "fire-lane-0001-x.patch"]


def test_경로_꼴이_달라도_뺀다(tmp_path):
    """`--zip ../h/x.zip` 은 같은 파일을 다른 글자로 가리킨다."""
    z = _stage(tmp_path)
    odd = tmp_path / ".." / tmp_path.name / z.name
    assert z.name not in [f.name for f in D.zip_items(tmp_path, odd)]


def test_디렉터리는_안_넣는다(tmp_path):
    z = _stage(tmp_path)
    (tmp_path / "하위폴더").mkdir()
    assert "하위폴더" not in [f.name for f in D.zip_items(tmp_path, z)]


# ── ⑦ 축 목록은 **verify.sh 가 선언한 것**이다 (DECISIONS §431) ──────
#: 2026-10-07~08 배달을 **세 번** 막은 실물 꼴. 도구가 제 몸통에서 찍는 `✗` 줄이
#: 요약 밖에 있는데 종전 파서가 그것을 축으로 셌다.
REAL_OUT = """\
── norm 계보 재현
   실패
  미등록  eais/eais_roadledger_dm_jngj-dongmyeong_20260801.csv
✗ 상한 0 을 넘었다 (37). 늘었다.

── 레이크 관문
   실패
       ✗ 주인없음  landing/juso_adrdc_kr_20260801.zip

══════════════════════════════════════════════
  19분13초 · 통과 99 · 실패 2 · 생략 0

  실패 2
    ✗ 레이크 관문                        관문 닫힘 — 아무것도 움직이지 않는다 (5)
    ✗ 문서 정합 도장                     docseal.py stamp --only DECISIONS/401

  통과 99 — 전부 보려면 --table
"""


def test_a_cross_printed_inside_a_step_is_not_an_axis():
    """★ **이 판에서 세 번 물린 자리.**  (DECISIONS §431)

    `✗ 상한 0 을 넘었다 (37). 늘었다.` 는 `firelane.prep` 이 제 안에서 찍는 줄이다.
    축이 아니다. 그런데 **수가 이름에 들어 있어** 37 → 36 으로 좋아져도
    「처음 보는 축」이 되고, 그러면 「이 배치가 새로 빨갛게 만들었다」가 된다.
    """
    red, _ = D.sweep_verdict(1, REAL_OUT)
    assert red == {"레이크 관문", "문서 정합 도장"}, red
    assert not any("상한" in x for x in red), f"도구가 찍은 줄을 축으로 셌다 — {red}"
    assert not any("주인없음" in x for x in red), red


def test_the_declared_count_and_the_parsed_count_must_agree():
    """★ **카나리아.** 수가 둘이다 — 합계 줄과 우리가 주운 수. 어긋나면 운다.

    파서가 낡아 조용히 덜 세는 것이 **제일 나쁘다** — 빨간 채로 나간다.
    """
    # ★ **합계 줄**을 고친다 — 그쪽이 `verify.sh` 가 센 수다. 블록만 고치면
    #   두 수가 여전히 같아서 대조가 안 선다(이 시험을 처음 쓸 때 그렇게 틀렸다).
    lying = REAL_OUT.replace("· 실패 2 ·", "· 실패 9 ·")
    red, _ = D.sweep_verdict(1, lying)
    assert any("거짓말" in x for x in red), f"선언 9 ≠ 읽은 2 인데 조용하다 — {red}"


def test_a_green_sweep_is_empty_even_when_the_body_is_noisy():
    """초록인데 몸통에 `✗` 가 있어도 **축은 0** 이다."""
    green = REAL_OUT.split("══")[0] + "\n  19분02초 · 통과 101 · 실패 0 · 생략 0\n\n"
    assert D.sweep_verdict(0, green)[0] == set()


# ── 자기검사를 뗀 뒤의 배선 (2026-10-08 · DECISIONS §436-6) ────────
# ★ `deliver.py` 가 상한에 붙어 살아 자기검사를 `tools/delivertest.py` 로 뗐다.
#   뗀 순간 **`--selftest` 가 아무것도 안 불러도 조용하다** — 지연 임포트라
#   임포트 시점에 안 터지고, 플래그를 안 쓰는 경로는 전부 멀쩡하다.
#   그 조용함을 이 셋이 깬다.
# ★ 경로는 **한 줄 리터럴**이다(위 꼬리와 같은 사유 — 배선 탐지가 줄 단위다).
_tspec = importlib.util.spec_from_file_location("delivertest", ROOT / "tools/delivertest.py")


def _delivertest():
    assert _tspec and _tspec.loader
    m = importlib.util.module_from_spec(_tspec)
    sys.modules[_tspec.name] = m
    _tspec.loader.exec_module(m)
    return m


def test_the_split_selftest_is_still_reachable():
    """`deliver.py --selftest` 가 **떼낸 파일에 닿는가.**"""
    src = (ROOT / "tools/deliver.py").read_text(encoding="utf-8")
    assert "from delivertest import selftest" in src, (
        "`deliver.py` 가 떼낸 자기검사를 안 부른다 — `--selftest` 가 빈 깡통이 된다")
    assert "def selftest(" in (ROOT / "tools/delivertest.py").read_text(encoding="utf-8")


def test_the_selftest_counts_its_own_arms_from_source():
    """판별식 수는 **소스에서** 센다 — 손으로 적으면 팔을 더해도 안 따라온다."""
    m = _delivertest()
    import inspect

    src = inspect.getsource(m.selftest)
    arms = src.count("bad.append(")
    assert arms >= 29, f"판별식이 {arms}개로 줄었다 — 팔을 지웠나"
    # ★ 셈을 **다른 꼴로 바꾸면 계수기가 눈을 감는다.** `bad += [...]` 로 줄을
    #   줄이면 수가 조용히 내려간다 — 이 판에서 실제로 그렇게 했다.
    # ★ 그물을 **리터럴 목록으로 좁힌다.** `bad += zip_items_broken()` 은 팔이
    #   아니라 **남의 판별식 결과를 합치는 줄**이고, 그것까지 막으면 멀쩡한
    #   줄에 우는 검사가 된다 — 거짓 경보는 검사를 끄게 만든다.
    assert "bad += [" not in src, (
        "판별식을 `bad.append` 가 아닌 꼴로 적었다 — `arms` 가 그것을 못 센다.\n"
        "  줄이 길면 파일을 쪼개라. 셈의 꼴은 바꾸지 않는다(DECISIONS §436-6)")


def test_the_relock_exemption_matches_real_pytest_ids():
    """★ 면제가 **실물 id** 에 걸리는가. 함수 이름만 적으면 죽은 그물이다."""
    for name in D.RELOCK_TESTS:
        nid = f"tests/test_x.py::{name}[some/param.json]"
        assert D.func_name(nid) == name, f"{nid} 에서 이름을 못 뽑는다"
    assert D.func_name("tests/a.py::test_b") == "test_b"
    assert D.func_name("test_c") == "test_c"


# ── 외로운 시험 (2026-10-08 · DECISIONS §439 · PLAN #138) ─────────
def _patch(tmp, name, *paths, names=()):
    """★ 2026-10-09 (§443-7). `names` 를 **첫 파일의 헌크 안**에 넣는다.
    종전에는 패치 **맨 뒤**에 붙였고, 그러면 `lonely_tests` 가 시험이 든 줄만
    보도록 좁힌 뒤로는 그 줄이 **마지막 파일**(문서)의 것이 된다. 먹이는 꼴이
    실물과 달라지면 그 검사는 제 그물이 아니라 **내 손**을 잰다(§436-6).
    """
    q = tmp / name
    out = []
    for i, x in enumerate(paths):
        out.append(f"--- a/{x}\n+++ b/{x}\n")
        if i == 0:
            out += [f"+# {n}\n" for n in names]
    q.write_text("".join(out), encoding="utf-8")
    return q


def test_a_test_only_commit_in_the_middle_is_refused(tmp_path):
    """★ §258-13 의 사고 — 시험이 앞 커밋, 구현이 뒤 커밋.

    앞 커밋만 실기에 얹히면 `DID NOT RAISE` 가 난다. 예습은 **마지막 상태**만
    보므로 그 지점을 아무도 서 보지 않는다.
    """
    lonely = _patch(tmp_path, "0001-t.patch", "tests/test_x.py", names=("tools/z.py",))
    impl = _patch(tmp_path, "0002-i.patch", "tools/z.py")
    bad = D.lonely_tests([lonely, impl])
    assert bad and "tools/z.py" in bad[0], bad


def test_a_test_for_code_that_is_already_there_is_accepted(tmp_path):
    """★ **이미 있는 코드를 시험하는 커밋은 혼자 초록이다.**

    이 문을 세운 날 제 더미에서 그런 커밋 하나를 잡았다 —
    `tests/test_figure_ink.py` 는 **앞 커밋에 이미 있는** 그림 코드를 시험한다.
    문을 세운 자가 첫 손님이 됐고, 그래서 규칙을 좁혔다: 그 시험이 **이름으로
    드는 파일을 뒤 패치가 건드릴 때만** 외롭다(§258-13 의 실제 꼴이다).
    """
    settled = _patch(tmp_path, "0001-t.patch", "tests/test_w.py", names=("tools/w.py",))
    impl = _patch(tmp_path, "0002-i.patch", "tools/z.py")
    assert not D.lonely_tests([settled, impl])


def test_a_commit_that_brings_its_implementation_is_accepted(tmp_path):
    """짝이 있으면 그 지점은 혼자 초록이다 — 넓은 문이 되지 않게 민다."""
    paired = _patch(tmp_path, "0001-tp.patch", "tests/test_y.py", "src/firelane/y.py")
    impl = _patch(tmp_path, "0002-i.patch", "tools/z.py")
    assert not D.lonely_tests([paired, impl])


def test_the_last_patch_is_not_asked(tmp_path):
    """마지막 지점은 예습이 **이미 전수로** 본다 — 두 번 세지 않는다."""
    impl = _patch(tmp_path, "0001-i.patch", "tools/z.py")
    tail = _patch(tmp_path, "0002-t.patch", "tests/test_z.py")
    assert not D.lonely_tests([impl, tail])
    assert not D.lonely_tests([tail]), "패치가 하나면 그것이 마지막이다"


def test_docs_do_not_count_as_the_implementation(tmp_path):
    """★ 문서·산출물은 시험을 초록으로 만들지 않는다 — **여전히 외롭다.**"""
    withdocs = _patch(tmp_path, "0001-td.patch", "tests/test_x.py",
                      "docs/DECISIONS.md", "data/golden/x.json",
                      names=("tools/z.py",))
    impl = _patch(tmp_path, "0002-i.patch", "tools/z.py")
    assert D.lonely_tests([withdocs, impl]), "문서를 구현으로 센다"


def test_only_the_lines_added_to_tests_name_the_implementation(tmp_path):
    """★ 2026-10-09 (§443-7). **문서가 든 이름은 시험이 든 것이 아니다.**

    종전에는 패치 **전문**을 댔고, 그래서 같은 커밋의 `docs/` 가 어떤 도구를
    언급하기만 해도 외로운 시험으로 걸렸다 — 실제로 걸렸다(§442 커밋).
    「문서는 시험을 초록으로 만들지 않는다」(§439-3)는 축이 **분모에만**
    적용되고 본문 읽기에는 안 적용되고 있었다.
    """
    q = tmp_path / "0001-td.patch"
    q.write_text("--- a/tests/test_v.py\n+++ b/tests/test_v.py\n+def test_v(): pass\n"
                 "--- a/docs/DECISIONS.md\n+++ b/docs/DECISIONS.md\n"
                 "+tools/z.py 를 고쳤다\n", encoding="utf-8")
    impl = _patch(tmp_path, "0002-i.patch", "tools/z.py")
    assert "tools/z.py" not in D.test_body(q), "문서 줄을 시험 본문으로 읽는다"
    assert not D.lonely_tests([q, impl]), "문서가 든 이름을 시험이 든 것으로 센다"
    # ★ 반대 방향 — 시험이 **직접** 들면 여전히 잡는다
    named = _patch(tmp_path, "0003-t.patch", "tests/test_x.py", names=("tools/z.py",))
    assert "tools/z.py" in D.test_body(named)
    assert D.lonely_tests([named, impl]), "좁히다가 그물이 비었다"


def test_paths_come_from_the_diff_header_only(tmp_path):
    """`git` 을 안 묻는다 — 워크트리·인덱스 없이 파일 하나로 답이 난다."""
    q = _patch(tmp_path, "0001-x.patch", "a/b.py", "c/d.py")
    assert D.patch_paths(q) == ["a/b.py", "c/d.py"]
