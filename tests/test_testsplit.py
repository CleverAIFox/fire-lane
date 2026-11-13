"""tests/test_testsplit.py — `tools/testsplit.py`(`contract-tests` 조각을 CI 시간으로 가른다 · DECISIONS §760).

IN    tools/testsplit.py · data/golden/ci_testtimes.json · tests/
OUT   없음 (검사)
밖    **장부의 초가 CI 의 실제 초와 맞는지는 안 본다**(다시 재는 법은 DECISIONS §760) · 러너 속도 · 시험끼리의 의존
PLAN 본문  규칙 없음 — 조각을 가르는 도구를 무는 검사이고 PLAN 의 어느 행도 이 파일을 근거로 서지 않는다
"""
import json
from pathlib import Path

import testsplit as ts

ROOT = Path(__file__).resolve().parents[1]


def test_the_selftest_probe_is_alive():
    assert ts.selftest() == 0


def test_the_split_is_balanced_deterministic_and_complete():
    files = ts.test_files()
    sec = ts.load_seconds()
    assert sec, "장부(data/golden/ci_testtimes.json)가 없다 — 가르기가 파일 수 균형으로 떨어진다"
    a, b = ts.split(files, sec, 4), ts.split(files, sec, 4)
    assert a == b, "같은 입력에 다른 조각 — 결정적이 아니다"
    flat = [f for part in a for f in part]
    assert sorted(flat) == sorted(files) and len(set(flat)) == len(flat), "빠짐 · 겹침"
    med = sorted(sec.values())[len(sec) // 2]
    sums = [sum(sec.get(Path(f).name, med) for f in part) for part in a]
    assert max(sums) <= 1.15 * min(sums), f"장부로 센 조각이 크게 어긋난다: {[round(x) for x in sums]}"


def test_a_new_file_without_a_ledger_row_still_lands_in_a_piece():
    files = ts.test_files() + ["tests/test_brand_new.py"]
    assert any("tests/test_brand_new.py" in part for part in ts.split(files, ts.load_seconds(), 4))


def test_the_ledger_is_in_the_documented_shape():
    d = json.loads((ROOT / "data" / "golden" / "ci_testtimes.json").read_text(encoding="utf-8"))
    assert set(d) == {"_", "seconds"} and all(isinstance(v, (int, float)) and v >= 0 for v in d["seconds"].values())
    assert "DECISIONS §760" in d["_"], "장부가 만든 법을 안 적었다"


def test_the_judge_is_quiet_on_a_clean_split_and_loud_on_a_synthetic_defect():
    files, sec = ts.test_files(), ts.load_seconds()
    parts = ts.split(files, sec, 4)
    assert not ts.defects(files, parts, sec)                                       # 깨끗하다 — 비어 있다
    assert ts.defects(files, [parts[0][1:], *parts[1:]], sec)                      # 합성 결함: 한 파일이 빠졌다
    assert ts.defects(files, [parts[0] + parts[1][:1], *parts[1:]], sec)           # 합성 결함: 한 파일이 겹쳤다
    assert ts.defects(files, [parts[0] + parts[1] + parts[2], parts[3], [], []], sec)   # 합성 결함: 한 조각이 몰렸다
