"""
test_unusedcheck.py — 「미활용」이 **0 으로 갈 수 있는 수인가.**
(DECISIONS §317 · `tools/unusedcheck.py` · `firelane.ledger.grade`)

── 왜 이 파일이 생겼나 (2026-09-30) ────────────────────────────
「미활용 25」가 한 달 동안 25 였다. 대장 검사는 그 수를 **찍기만** 했고 목표가
없었다 — 목표 없는 수는 아무도 안 본다. 뜯어 보니 25 가 셋이었다 —

    ①  9  `raw_only` 인데 `feeds` 가 비어 미사용으로 뒤집혔다 (`grade()` 갈래 순서)
    ②  4  「참조용 · 대조용 · 근거 자료」 — 소비자가 **사람**이고 feeds 가 생길 일이 없다
    ③ 12  「미투입 · 미배선」 — 이것만 내릴 대상이다

★ ①이 제일 나쁘다. 그 함수의 주석이 「이 갈래를 뒤로 미루면 raw_only 열다섯이
  미사용으로 뒤집힌다」고 **경고하고 있었는데** 코드 순서로는 안 지켰다.
  같은 파일 안에서 글과 코드가 갈렸고, 글은 아무것도 못 막는다.

IN    firelane.ledger · tools/unusedcheck.py · sources.yaml
OUT   없음
밖    **어느 자료를 붙여야 하는가는 안 본다.** 배선 순서는 PLAN 이 든다.
      **참조용이 옳은 분류인가는 안 본다** — 낱말을 고르는 것은 사람이고,
      여기는 「낱말이 선언된 것인가」와 「③이 래칫과 같은가」만 든다.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from firelane import ledger  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_t", ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


UC = _load("unusedcheck")


# ── ① 갈래 순서 (§317 ①) ───────────────────────────────────────

def test_raw_only_with_no_feeds_is_reference_not_unused():
    """★ 실기의 그 결함. 「원본만 보관」은 `feeds` 가 **없는 것이 정상**이다."""
    assert ledger.grade({"kind": "raw_only"}) == "reference"
    assert ledger.grade({"kind": "raw_only", "feeds": []}) == "reference"
    assert ledger.grade({"kind": "raw_only", "feeds": None}) == "reference"
    # ★ 반대 방향. `raw_only` 가 아니고 feeds 도 없으면 여전히 미배선이다.
    assert ledger.grade({"kind": "csv_table", "feeds": []}) == "unused"


def test_the_warning_in_the_code_is_now_the_code():
    """★ 주석이 경고를 적고 코드 순서가 그것을 어기던 자리. 순서를 시험이 든다."""
    src = (ROOT / "src" / "firelane" / "ledger.py").read_text(encoding="utf-8")
    body = src[src.index("def grade("):src.index("def check_entry(")]
    assert body.index('"raw_only"') < body.index("if not feeds"), (
        "`raw_only` 갈래가 `if not feeds` 보다 뒤에 있다 — 아홉이 다시 뒤집힌다")


# ── ② 영구 참조와 미배선 (§317 ②③) ────────────────────────────

def test_permanent_reference_is_not_counted_as_pending():
    for w in ledger.REFERENCE_WHY:
        assert ledger.grade({"kind": "csv_table", "feeds": [], "feeds_why": f"{w} — 사유"}) \
            == "reference", f"「{w}」을 미배선으로 센다 — 그 수는 0 이 못 된다"
    for w in ledger.PENDING_WHY:
        assert ledger.grade({"kind": "csv_table", "feeds": [], "feeds_why": f"{w} — 사유"}) \
            == "unused", f"「{w}」을 영구 참조로 센다 — 내릴 대상이 사라진다"


def test_the_token_is_read_from_the_first_line_only():
    assert ledger.why_token({"feeds_why": "★ 미투입 — 후보다"}) == "미투입"
    assert ledger.why_token({"feeds_why": "쓸 데가 없다\n참조용으로 볼 수도"}) is None, (
        "첫 줄 밖의 낱말을 집는다 — 본문에 우연히 든 것까지 선언으로 읽는다")
    assert ledger.why_token({}) is None
    assert ledger.why_token({"feeds_why": ["목록이다"]}) is None, "산문이 아닌 값에서 죽는다"


def test_the_rename_only_feed_still_does_not_count_as_a_consumer():
    """`normalize_raw` 는 배치기다 — 이름표만 붙는 것은 아무도 안 읽는 것과 같다(§243)."""
    e = {"kind": "csv_table", "feeds": sorted(ledger.RENAME_ONLY)}
    assert ledger.grade(e) == "unused"


# ── ③ 실물 (래칫) ──────────────────────────────────────────────

def test_every_pending_entry_declares_its_word():
    bad = UC.undeclared()
    assert not bad, (
        f"선언 낱말 없는 미배선 {len(bad)}건 — {sorted(bad)}\n"
        f"  {' · '.join(ledger.REFERENCE_WHY + ledger.PENDING_WHY)} 중 하나로 시작해라.\n"
        "  산문으로 흐리면 영구 참조와 미배선이 한 수에 섞이고, 섞인 수는 0 으로 못 간다.")


def test_the_real_tree_is_at_its_ratchet():
    got = len(UC.pending())
    assert got == UC.PENDING_MAX, (
        f"미배선 {got} ≠ 래칫 {UC.PENDING_MAX} — "
        "늘었으면 붙이거나 `retired:` 로 내려라. 줄었으면 "
        "`uv run python tools/ratchet.py --write` 로 조여라")


def test_the_ratchet_is_on_the_protocol():
    """★ 손으로 받아적지 않는다(§309). 규약에 태워 `ratchet.py` 가 조인다."""
    assert UC.RATCHETS == {"PENDING_MAX": "down"}
    assert UC.ratchet_values()["PENDING_MAX"] == len(UC.pending())


def test_the_gate_is_wired_both_sides():
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    yml = (ROOT / ".github" / "workflows" / "contract.yml").read_text(encoding="utf-8")
    assert "tools/unusedcheck.py" in sh, "전수 verify 가 안 부른다"
    assert "tools/unusedcheck.py" in yml, "CI 가 안 부른다 — 대장만 읽으므로 레이크가 필요 없다"


def test_the_selftest_is_alive():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "unusedcheck.py"),  # noqa: S603
                        "--selftest"], capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
