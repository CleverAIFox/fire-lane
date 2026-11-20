"""관문 다섯 칸이 지금도 자기 분모를 내는가.  (PLAN #259 · 도착 ④ — 「오늘의 다섯 구멍」을 시험으로 고정)

구멍 다섯과 그 분모를 내는 곳:
  ① `pushready` ㉠ 가 변이 장부 항목을 건너뜀   → `pushdenom.ratchet_denom` 「래칫 N개 중 읽은 수 · 넘긴 수 · 규칙마다 사유」
  ② 변이 지문이 표본 고르는 규칙을 안 해시     → `pushdenom.print_denom` 「정의 N개 중 지문에 든 것 · 선언표」 + 지문이 그 규칙의 소스 변화에 달라지는가
  ③ 같은 지문이 연산자 표를 안 해시            → 위와 같다(연산자 표 소스를 바꾸면 지문이 달라지는가)
  ④ ㉥ 가 읽기 장부 낡음에 초록                → `pushdenom.tests_denom` 「읽기 실측 n/M개 파일」(실물 `testpick --list` 한 번)
  ⑤ 주행 화면의 정적 래칫이 범위 밖을 못 봄     → `uidrive.drive_census` 「N파일 중 M파일 · 범위 밖 묶음 · 사유」

★ 수 자체는 못 박지 않는다 — 박으면 파일이 늘 때마다 낡는다. 묻는 것은 「분모 출력이 있다 · 분모가 0 이 아니다 · 본 몫이 숫자로 나온다 ·
  안 본 목록에 사유가 있다」 넷이고, 합성 입력으로 우는 것(카나리아)을 칸마다 하나씩 보인다.
IN    저장소에 든 파일만(`tools/` · `web/navi/src` · `data/golden/` 의 읽기 장부). 생성물(`data/processed` 등)은 안 읽는다
OUT   없음 (검사)
밖    실제 래칫 전수는 안 돈다(분 단위) — ① 은 그 도구의 요약줄 꼴을 닮은 합성 출력으로 본다. 분모의 % 는 래칫으로 안 건다.
★ 이 파일은 지문을 가진 도구의 이름을 낱말로 적지 않는다 — 적으면 그 도구의 변이 장부가 낡는다.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import mutatescope as MS
import pushdenom as D
import pytest
import uidrive as UD

ROOT = Path(__file__).resolve().parents[1]
REASON_MIN = 12     # 사유가 이보다 짧으면 「사유」가 아니다 — 판별식과 같다
SEAL = "doc" + "seal.py"     # 낱말로 안 적는다(위 ★) — 그 도구의 변이 장부가 이 파일을 해시하지 않게
SUMMARY = "래칫 {n}개 · 낡음 {s} (조이는 쪽 0 · 느슨해진 쪽 {s}) · 건너뜀 {k}\n"


# ── ① ㉠ 래칫 분모 ────────────────────────────────────────────
def test_hole_1_the_gate_column_for_ratchets_states_read_over_total_with_a_reason_per_skip_rule() -> None:
    out = SUMMARY.format(n=92, s=2, k=0) + f"  ✗ {SEAL} · UNSEALED — **느슨해지는 쪽**이다\n  ✗ mutate.py · — — 죽었다\n"
    first, *rules = D.ratchet_denom(out)
    m = re.match(r"㉠ 래칫 (\d+)개 중 (\d+)개를 읽었다 · 넘긴 (\d+)개", first)
    assert m, first
    total, read, skipped = map(int, m.groups())
    assert total > 0 and read + skipped == total and skipped == 2, "본 몫 + 넘긴 몫 = 분모"
    assert len(rules) == len(D.RATCHET_SKIPS) >= 2
    assert all(len(why.strip()) >= REASON_MIN for _, why in D.RATCHET_SKIPS.values()), "넘기는 규칙마다 사유가 있다"


def test_hole_1_canary_a_missing_summary_says_unread_instead_of_a_zero_and_an_undeclared_skip_is_read() -> None:
    got = D.ratchet_denom("✓ 아무 말\n")
    print("카나리아(요약줄 없음):", got)
    assert len(got) == 1 and "분모를 못 읽었다" in got[0]
    assert D.skip_rule("✗", SEAL, "OTHER") is None and D.skip_rule("✗", "x.py", "UNSEALED") is None, "선언 밖 항목은 읽힌다"
    assert D.skip_rule("✗", "mutate.py", "—") and D.skip_rule("·", "mutate.py", "SURVIVORS"), "선언된 둘은 넘긴다"


# ── ②③ 변이 지문 분모 ─────────────────────────────────────────
def test_holes_2_3_the_print_column_states_seen_over_total_and_every_unseen_definition_has_a_reason() -> None:
    first, *rest = D.print_denom()
    m = re.search(r"정의 (\d+)개 중 지문에 든 것 (\d+)개\((\d+\.\d)%\) · 폐포 안\(지문 밖\) (\d+)개 · 선언표 (\d+)개 · 선언이 어긋난 것 (\d+)개", first)
    assert m, first
    total, seen, pct, clo, table, bad = int(m[1]), int(m[2]), float(m[3]), int(m[4]), int(m[5]), int(m[6])
    assert total > 0 and 0 < seen <= total and abs(pct - 100 * seen / total) < 0.06, "분모가 0 이 아니고 본 몫이 숫자다"
    assert seen + clo + table == total, "본 몫 · 폐포 · 선언표가 분모를 빠짐없이 나눈다"
    assert bad == 0, "선언이 정의와 어긋나면 분모 줄이 그것을 센다"
    assert all(len(w.strip()) >= REASON_MIN for w in {**D.OUT_OF_PRINT, **D.CLOSURE_OUT}.values()), "안 본 정의마다 사유가 있다"
    assert len(rest) == 2 and "OUT_OF_PRINT" in rest[0] and "ast" in rest[1], "못 세는 값이 갈 칸 · 전제를 같이 둔다"


def test_hole_2_the_print_hashes_the_sampling_rule_so_changing_it_changes_the_print(monkeypatch: pytest.MonkeyPatch) -> None:
    assert {"mutatescope.py::pick", "mutatescope.py::_site_keys"} <= D.IN_PRINT
    before = MS.sampler_print()

    def pick(muts, cap, src=None):      # 같은 이름의 다른 소스
        return muts[:cap]

    monkeypatch.setattr(MS, "pick", pick)
    after = MS.sampler_print()
    print("카나리아(표본 규칙 소스 바꿈):", before, "→", after)
    assert before != after


def test_hole_3_the_print_hashes_the_operator_table_so_changing_it_changes_the_print(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert {"mutate.py::mutants", "mutate.py::_CMP", "mutate.py::_CMP_SRC"} <= D.IN_PRINT
    real = (ROOT / "tools" / "mutate.py").read_text(encoding="utf-8")
    before = MS.sampler_print()
    edited = real.replace("_CMP = ", "_CMP = {} if False else ", 1)
    assert edited != real
    copy = tmp_path / "mutate.py"
    copy.write_text(edited, encoding="utf-8")
    monkeypatch.setattr(MS, "MUTATE_SRC", copy)
    after = MS.sampler_print()
    print("카나리아(연산자 표 소스 바꿈):", before, "→", after)
    assert before != after


def test_holes_2_3_canary_a_definition_outside_the_declaration_is_counted_as_a_mismatch() -> None:
    srcs = {f: (ROOT / "tools" / f).read_text(encoding="utf-8") for f in D.PRINT_FILES}
    srcs["mutate.py"] += "\n\ndef brand_new_helper():\n    return 1\n"
    got = D.problems(srcs, D.IN_PRINT, D.OUT_OF_PRINT, D.CLOSURE_OUT)
    print("카나리아(선언 밖 새 정의):", got)
    assert got == ["선언 밖의 새 정의: mutate.py::brand_new_helper"]


def test_holes_2_3_canary_the_same_check_is_quiet_on_the_real_sources_and_cries_on_a_new_definition() -> None:
    """카나리아 쌍(DECISIONS §445) — 같은 판별 함수를 실물 소스에는 `assert not` 으로, 선언 밖 정의를 얹은 합성 소스에는 `assert` 로 민다."""
    srcs = {f: (ROOT / "tools" / f).read_text(encoding="utf-8") for f in D.PRINT_FILES}
    assert not D.problems(srcs, D.IN_PRINT, D.OUT_OF_PRINT, D.CLOSURE_OUT)
    bad = {**srcs, "mutate.py": srcs["mutate.py"] + "\n\ndef brand_new_helper():\n    return 1\n"}
    assert D.problems(bad, D.IN_PRINT, D.OUT_OF_PRINT, D.CLOSURE_OUT)


# ── ④ ㉥ 읽기 실측 분모 ────────────────────────────────────────
def test_hole_4_the_tests_column_states_measured_over_total_from_the_real_list() -> None:
    r = subprocess.run([sys.executable, str(ROOT / "tools/testpick.py"), "--list"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", timeout=120, check=False)
    assert r.returncode == 0, r.stderr[-300:]
    g = D.reads_gap(r.stdout + r.stderr)
    assert g is not None, "읽기 실측 줄이 없다 — 분모가 안 나온다"
    n, total, _unexplained = g
    assert total > 0 and 0 < n <= total, "분모가 0 이 아니고 본 몫이 숫자다"
    line = D.tests_denom(r.stdout + r.stderr)[0]
    assert re.match(rf"㉥ 읽기 실측 {n}/{total}개 파일\(\d+\.\d%\)", line), line


def test_hole_4_canary_a_gap_the_new_tests_do_not_explain_blocks_and_a_missing_line_says_unread() -> None:
    out = "  (정적 스캔 ∪ 실측 읽기 270/280개 파일 — 장부에 없거나 낡은 시험은 **하한**)\n"
    block = D.gap_block(out)
    print("카나리아(설명 안 되는 몫):", block and block[0])
    assert block is not None and "10개" in block[0]
    assert "분모를 못 읽었다" in D.tests_denom("✓ 묶음\n")[0]


# ── ⑤ 주행 화면 분모 ───────────────────────────────────────────
def test_hole_5_the_drive_census_states_seen_over_total_and_every_unseen_group_has_a_reason() -> None:
    c = UD.drive_census()
    assert c["total"] > 0 and 0 < c["seen"] <= c["total"], "분모가 0 이 아니고 본 몫이 숫자다"
    assert c["undeclared"] == [] and UD.census_faults() == [], "범위 밖 파일은 전부 묶음 선언에 든다"
    assert UD.OUT_OF_SCOPE and all(len(why.strip()) >= REASON_MIN and files for why, files in UD.OUT_OF_SCOPE.values()), "안 본 묶음마다 사유와 파일이 있다"
    assert re.match(rf"{c['total']}파일 중 {c['seen']}파일\(\d+\.\d%\)을 보고 · 범위 밖 {c['total'] - c['seen']}파일", UD.census_line())


def test_hole_5_canary_dropping_the_declaration_makes_the_unseen_files_undeclared() -> None:
    c = UD.drive_census(groups={})
    got = UD.census_faults(groups={})
    print("카나리아(선언표를 비움):", got[0][:60])
    assert c["undeclared"] and any("선언이 없는 파일" in g for g in got)
