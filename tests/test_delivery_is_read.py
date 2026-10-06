#!/usr/bin/env python3
"""
test_delivery_is_read.py — 배달물의 **모든 칸에 독자가 있는가.**

── 왜 생겼나 (2026-09-28 · DECISIONS §290-4) ───────────────────
`tools/deliver.py` 는 `EXPECT` 를 원격 팁 위에서 **재서** 썼다. zip 에 담겼고
건너갔고 **거기서 끝이었다** — 저장소 전체에서 그 파일을 읽는 코드가 0개였고
`fl.sh` 에는 `EXPECT` 라는 글자가 없었다. 그런데 그 파일의 머리말은
「go.sh 가 제가 잰 값과 대조한다」고 **적혀 있었다.**

★ 이 도구가 생긴 이유가 「주장의 저자를 사람에서 기계로 바꾼다」였다. 저자만
  바꾸고 **독자를 안 만들었다.** 기계가 쓴 주장도 아무도 안 읽으면 사람이 쓴
  주장과 값이 같다(5족 · 파이프 단절).

★ **한 번 이었으니 끝이 아니다.** 배달물에 칸을 새로 더하는 것은 쉽고, 그 칸의
  독자를 만드는 것은 잊기 쉽다. 그래서 「쓰는 쪽」에서 칸을 **유도해서** 독자를
  찾는다 — 손목록을 두면 칸이 늘어도 목록이 안 따라간다(deadcheck ②).

IN    tools/deliver.py (쓰는 쪽) · 저장소 전체 (읽는 쪽)
OUT   없음 (검사)
밖    **독자가 그 값을 옳게 쓰는지는 안 본다** — 그것은 `deliver.py --selftest`
      의 판별식과 `accept` 의 대조가 든다. 여기가 드는 것은 「독자가 있는가」다.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVER = ROOT / "tools" / "deliver.py"


def _written_files() -> set[str]:
    """`pack` 이 배달 디렉터리에 **이름으로** 쓰는 파일. 소스에서 유도한다."""
    src = DELIVER.read_text(encoding="utf-8")
    # `(out / "BASE").write_text(...)` · `out / "EXPECT"` 꼴
    return set(re.findall(r'out\s*/\s*"([A-Za-z0-9_.]+)"', src))


def _readers(name: str) -> list[str]:
    """그 이름을 **읽는** 곳. 쓰는 쪽(`deliver.py`)과 이 시험은 뺀다."""
    hits = []
    for p in sorted(ROOT.glob("tools/*")) + sorted(ROOT.glob("tests/*.py")) \
            + sorted(ROOT.glob(".githooks/*")):
        if p.name in {DELIVER.name, Path(__file__).name} or not p.is_file():
            continue
        try:
            if name in p.read_text(encoding="utf-8"):
                hits.append(p.name)
        except (UnicodeDecodeError, OSError):
            continue
    return hits


def test_every_file_the_packer_writes_has_a_reader():
    written = _written_files()
    assert written, "쓰는 쪽에서 칸을 하나도 못 뽑았다 — 유도가 깨졌다(빈 그물)"
    assert "EXPECT" in written, "`EXPECT` 를 못 뽑았다 — 유도가 좁다"
    orphan = {n: _readers(n) for n in sorted(written)}
    dead = [n for n, r in orphan.items() if not r]
    assert not dead, (
        "배달물에 **독자가 없는 칸**이 있다: " + " · ".join(dead)
        + "\n\n  기계가 재서 쓰고 아무도 안 읽으면 사람이 쓴 주장과 값이 같다."
        "\n  읽는 쪽을 만들어라 — `deliver.py accept` 가 `EXPECT` 에 한 것처럼.")


def test_expect_is_read_by_the_receiving_script():
    """★ 독자가 **열차 안에** 있어야 한다. 시험만 읽는 것은 독자가 아니다."""
    fl = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    assert "EXPECT" in fl, "`fl.sh` 가 `EXPECT` 를 안 읽는다 — 배달 계약이 죽은 칸이다"
    assert "tools/expectcheck.py" in fl, (
        "`fl.sh` 가 `EXPECT` 를 **제 손으로** 파싱하고 있다면 2족이다 — "
        "꼴을 아는 곳은 `deliver.py` 의 `render`·`parse` 하나여야 한다")


def test_the_reader_does_not_reimplement_the_format():
    """★ 읽는 쪽이 `parse` 를 **빌려 쓰는가.** 제 손으로 쪼개면 꼴이 두 집에 산다."""
    src = (ROOT / "tools" / "expectcheck.py").read_text(encoding="utf-8")
    assert "from deliver import" in src and "parse" in src, (
        "받는 쪽이 `deliver.parse` 를 안 쓴다 — 꼴이 갈린다(2족)")
    body = src.split('"""', 2)[2]
    assert ".partition(\"=\")" not in body and ".split(\"=\")" not in body, (
        "받는 쪽이 `=` 를 제 손으로 쪼갠다 — 그것이 두 번째 파서다")


def test_the_contract_header_names_a_consumer_that_exists():
    """머리말이 지목하는 독자가 **실재하는가.** 종전에는 없는 `go.sh` 를 댔다."""
    import deliver  # noqa: PLC0415   # `pyproject` 의 `pythonpath` 가 tools 를 든다

    head = deliver.render({})
    named = re.findall(r"`?([a-z_]+\.(?:py|sh))`?", head)
    assert named, f"머리말이 독자를 지목하지 않는다 — {head!r}"
    for n in named:
        assert (ROOT / "tools" / n).is_file(), (
            f"머리말이 `{n}` 를 독자로 대는데 그런 파일이 없다. "
            "**없는 소비자를 있다고 적는 것**이 §290-4 의 결함이다")


def test_the_tool_the_train_calls_exists_and_takes_that_argument():
    """`fl.sh` 가 부르는 도구가 실재하고 **그 인자를 받는가.** 이름만 맞춘 것이 아니어야 한다."""
    tool = ROOT / "tools" / "expectcheck.py"
    assert tool.is_file(), "`fl.sh` 가 없는 도구를 부른다"
    tree = ast.parse(tool.read_text(encoding="utf-8"))
    args = {n.args[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "add_argument"
            and n.args and isinstance(n.args[0], ast.Constant)}
    assert "expect" in args, f"EXPECT 경로를 받는 인자가 없다 — {sorted(args)}"
    assert "--selftest" in args, "`--selftest` 가 없다 — 「자기검사 전수」가 못 든다"


def test_a_delivery_without_a_contract_is_refused_not_warned():
    """★ 계약이 **없는** 경우(§319-2). 「읽는 쪽이 있는가」와 다른 물음이다.

    위 시험들은 `EXPECT` 가 있을 때 누가 읽는가를 묻는다. 2026-09-30 까지
    `fl.sh` 4c 의 `else` 는 `warn` 이었다 — **손으로 싼 묶음이 경고 한 줄을
    남기고 끝까지 갔다.** 받는 기계는 아무도 안 잰 주장을 걸고 8GB 와 20분을 쓴다.

    ★ 손으로 **쓴** `EXPECT` 는 이미 막혀 있었다(`expectcheck` 가 「읽을 줄이
      없다」로 rc 1). 구멍은 「쓴 것」이 아니라 **「없는 것」**이었다.

    ★ 2026-10-06 (DECISIONS §408). 닻이 바뀌었다 — 4c 가 `$WORK` 를 먼저 보고
      없으면 INBOX 를 보므로 조건이 `[ -n "$EXPECT_F" ]` 다. **묻는 것은 그대로다.**
    """
    sh = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    assert 'for _e in "$WORK/EXPECT" "$IN/EXPECT"' in sh, (
        "계약을 찾는 자리가 둘이 아니다 — zip 에서 꺼낸 것과 사람이 푼 것 둘 다 본다")
    i = sh.index('if [ -n "$EXPECT_F" ]; then')
    blk = sh[i:sh.index("# ══ 5.", i)]
    tail = blk[blk.index("else"):]
    assert "die " in tail, "EXPECT 가 없어도 배치가 계속된다 — 계약 없는 배달이 통과한다"
    assert "warn " not in tail, "경고로 넘긴다 — 경고는 곧 안 읽히는 줄이 된다"
    # ★ 반대 방향. 있을 때는 **대조**해야 한다 — 죽는 것만 보면 초록도 못 간다.
    assert "tools/expectcheck.py" in blk, "있을 때 아무도 안 댄다"


# ── pack 이 같은 전수를 네 번 돌고 있었다  (DECISIONS §396 · PLAN #155) ──

def test_verify_keeps_green_logs_only_when_asked(tmp_path):
    """`FL_VERIFY_KEEP_LOGS=1` 이면 초록 단계도 전문을 남긴다. 기본은 안 남긴다.

    ★ 기본을 켜면 평소 실행이 /tmp 에 99개를 흘린다 — 그것대로 쓰레기다.
    """
    s = (ROOT / "tools/verify.sh").read_text(encoding="utf-8")
    assert '[ "${FL_VERIFY_KEEP_LOGS:-0}" = 1 ]' in s, "깃발이 없다"
    # 전문 경로를 **한 번만** 짓는다 — 두 벌이면 초록·빨강이 다른 이름으로 간다
    assert s.count('_flog="/tmp/verify-') == 1, "전문 경로가 두 벌이다"


def test_pack_reads_the_pytest_log_instead_of_running_it_again():
    """★ 실측 — pack 한 번에 전수 pytest 가 **네 번** 돌았다.

        따로        밑동 한 번 · 얹은 뒤 한 번
        verify 안   밑동 verify 안에 한 번 · 얹은 뒤 verify 안에 한 번

    사용자 기계에서 pytest 7분40초 · verify 14분43초다 — 둘을 두 번씩이면
    45분이 넘는다. 10분 상한에 걸린 것은 **한 가지가 느려서가 아니라 같은
    것을 네 번 돌려서**였다. 이제 verify 가 남긴 전문을 읽는다.
    """
    d = (ROOT / "tools/deliver.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in d.splitlines() if not l.lstrip().startswith("#"))
    assert "_pytest_log()" in code, "전문을 안 찾는다"
    assert '"FL_VERIFY_KEEP_LOGS": "1"' in code, "verify 에 전문을 남기라고 안 한다"
    assert "old.unlink(missing_ok=True)" in code, (
        "옛 전문을 안 지운다 — 지난 실행의 pytest 를 이번 것으로 읽는다")
    # 순서: verify(기준선) 가 pytest 채집보다 **먼저** 와야 전문이 있다
    i_sweep = code.index("base_sweep = _sweep_red")
    i_red = code.index("base_red = _redlist")
    assert i_sweep < i_red, "기준선 pytest 가 verify 보다 먼저다 — 전문이 없다"


def test_the_pytest_scanner_is_pure_and_bites():
    """채집 판별식을 **꺼냈다**(§17-0) — 합성 입력으로 재고, 안 걸리는 것도 댄다."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_dlv", ROOT / "tools/deliver.py")
    m = importlib.util.module_from_spec(spec)
    # ★ `@dataclass` 가 `cls.__module__` 로 되짚는다 — 없으면 터진다(지연 신관).
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    red, tail = m._scan_pytest(
        "FAILED tests/test_a.py::test_x - boom\n"
        "FAILED tests/test_b.py::test_y\n"
        "2 failed, 9 passed in 3.1s\n", 1)
    assert red == {"tests/test_a.py::test_x", "tests/test_b.py::test_y"}
    assert "2 failed" in tail
    red2, tail2 = m._scan_pytest("2291 passed, 1 warning in 457.32s\n", 0)
    assert red2 == set() and "2291 passed" in tail2, "초록을 빨강으로 읽는다"
    assert m._scan_pytest("", 7)[1] == "rc=7", "요약이 없으면 종료코드를 든다"
