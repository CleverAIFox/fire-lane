"""소방자동차 관리카드 — **받은 이름과 카드 내용이 같은가 · norm 이 raw 를 옮겼는가.**

★ 2026-09-17 (DECISIONS §172). 첫 수령 넷 중 `관리카드_대인5호_.pdf` 가 **지산2호 카드**였다
  (등록번호 998더7338 · 소속 지산119안전센터). sha 는 달랐다 — PDFium 재저장본이다.
  intake · acquire 는 이름과 sha 로만 판정하므로 이름과 내용을 대조하는 곳이 체계 안에 없었다.

원본은 받은 이름 그대로 보존한다. 어긋남은 대장 `mismatch` 에 **선언**한다.
  ① 이름의 센터(part 앞부분) = 카드 `소속` — 선언 없이 어긋나면 운다
  ② 등록번호가 카드끼리 겹치지 않는다 — 선언된 어긋남이 설명하는 겹침만 허용
  ③ 선언했는데 이제 맞으면 운다 — 선언은 유예지 면제가 아니다

★ 레이크가 없으면(CI) 실물 검사는 건너뛴다. 판별식과 추출기는 카나리아가 CI 에서 지킨다.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KEY = "gjfire_vehicle_card"
CENTER = {"jisan": "지산119안전센터", "daein": "대인119안전센터"}
PART = re.compile(r"^([a-z]+)(\d+)$")


def check(cards: dict[str, dict], declared: dict[str, str]) -> list[str]:
    """part → norm 한 행(dict). 어긋난 것을 문장으로 돌려준다."""
    bad, seen = [], {}
    for part, row in sorted(cards.items()):
        m = PART.match(part)
        if not m or m.group(1) not in CENTER:
            bad.append(f"{part}: part 문법 밖이다 — <센터><호수> ({'·'.join(CENTER)})")
            continue
        plate, org = row.get("등록번호", ""), row.get("소속", "")
        if not plate or not org:
            bad.append(f"{part}: norm 에 등록번호·소속이 없다")
            continue
        off = not org.endswith(CENTER[m.group(1)])
        if off and part not in declared:
            bad.append(f"{part}: 이름은 {CENTER[m.group(1)]} 인데 카드 소속은 {org} (등록번호 {plate})")
        if not off and part in declared:
            bad.append(f"{part}: mismatch 로 선언했는데 이제 맞다 — 대장에서 그 줄을 지운다")
        if plate in seen and part not in declared and seen[plate] not in declared:
            bad.append(f"{part}: 등록번호 {plate} 가 {seen[plate]} 와 같다 — 같은 카드다")
        seen.setdefault(plate, part)
    for part in sorted(set(declared) - set(cards)):
        bad.append(f"{part}: mismatch 로 선언했는데 그 카드가 없다")
    return bad


def test_vehicle_card_probe_is_alive():
    """카나리아 — 2026-09-17 의 실제 사고 형태를 그대로 넣는다."""
    js2 = {"등록번호": "998더7338", "소속": "전남광주통합특별시 동부 소방서 지산119안전센터"}
    dn6 = {"등록번호": "998더7376", "소속": "전남광주통합특별시 동부 소방서 대인119안전센터"}
    assert check({"jisan2": js2, "daein6": dn6}, {}) == []
    bad = check({"jisan2": js2, "daein5": js2, "daein6": dn6}, {})
    assert any("daein5" in b and "지산119안전센터" in b for b in bad)
    assert any("daein5" in b and "같은 카드" in b for b in bad)
    assert check({"jisan2": js2, "daein5": js2, "daein6": dn6}, {"daein5": "사본"}) == []
    assert "이제 맞다" in check({"daein6": dn6}, {"daein6": "옛 선언"})[0]
    assert "그 카드가 없다" in check({}, {"daein9": "x"})[0]


def test_vehiclecard_parser_on_recorded_chunks():
    """추출기 카나리아 — 대인11호 첫 쪽의 실제 글자 조각 좌표(pypdf, 2026-09-17)."""
    from firelane import vehiclecard as vc
    S = 8.0
    chs = [(802, 22, S, "■ 소방장비 관리업무 처리기준 [별지 제48호서식] <이 동>"),
           (748, 214, 14, "소방자동차 관리카드"), (703, 98, S, "진우고가소방차,"),
           (703, 455, S, "전남광주통합특별시 동부"), (697, 35, S, "차명 :"),
           (697, 212, S, "등록번호 :"), (697, 305, S, "998더7380"), (697, 403, S, "소속 :"),
           (690, 86, S, "SM C-B4A 1S3D175L3"), (690, 457, S, "소방서 대인119안전센터"),
           (662, 504, S, "(3쪽 중 제 1쪽)"), (627, 43, S, "차 종"), (627, 107, S, "등 록 일"),
           (613, 176, S, "보 조 금"), (613, 245, S, "교 부 세"), (613, 314, S, "지 방 비"),
           (613, 383, S, "기 증 등"), (613, 459, S, "차 제"), (613, 528, S, "특 장"),
           (585, 24, S, "27m 급(신규)"), (585, 102, S, "20250205"), (585, 302, S, "650,000,000"),
           (585, 440, S, "타타대우(구쎈)"), (585, 510, S, "진우에스엠씨"),
           (550, 288, S, "엔진"), (550, 363, S, "물탱크 용량"), (550, 444, S, "폼탱크 용량"),
           (550, 509, S, "분말탱크 용량"), (543, 32, S, "길이(mm)"), (543, 102, S, "너비(mm)"),
           (543, 183, S, "높이(mm)"), (512, 42, S, "8,670"), (512, 111, S, "2,480"),
           (512, 192, S, "3,795"), (512, 289, S, "320"), (512, 386, S, "0"), (512, 468, S, "0"),
           (512, 538, S, "0"), (484, 51, S, "그 밖의 특기사항"),
           (484, 296, S, "2024년 화재진압 기동장비 구매")]
    r = vc.parse(chs)
    assert r["차명"] == "진우고가소방차, SMC-B4A1S3D175L3"
    assert (r["등록번호"], r["차종"], r["등록일"]) == ("998더7380", "27m 급(신규)", "20250205")
    assert r["소속"].endswith("대인119안전센터")
    assert (r["구입가격_지방비"], r["구입가격_교부세"]) == ("650,000,000", "")
    assert (r["제작회사_차체"], r["제작회사_특장"]) == ("타타대우(구쎈)", "진우에스엠씨")
    assert (r["길이(mm)"], r["너비(mm)"], r["높이(mm)"], r["엔진(마력/토크)"]) == \
        ("8,670", "2,480", "3,795", "320")
    assert r["그 밖의 특기사항"] == "2024년 화재진압 기동장비 구매"
    with pytest.raises(vc.CardError):
        vc.parse([c for c in chs if c[3] != "보 조 금"])


def _entry():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))["datasets"][KEY]


def test_received_vehicle_cards_match_their_names():
    """대장 parts 의 카드가 raw 에 있고, norm 에 옮겨졌고, 이름과 내용이 같은가."""
    from firelane import paths
    if not paths.DATA or not (Path(paths.DATA) / "raw").is_dir():
        pytest.skip("환경skip(레이크) — 실물 대조는 레이크 기계에서 돈다")
    e = _entry()
    vt = str(e["updated"]).replace("-", "")
    prov = e["stem"].split("_", 1)[0]
    cards, missing = {}, []
    for part in e["parts"]:
        name = f"{e['stem']}_{e['scope']}_{vt}_{part}"
        raw = Path(paths.DATA) / "raw" / prov / f"{name}.pdf"
        norm = Path(paths.DATA) / "norm" / prov / f"{name}.csv"
        if not raw.exists():
            missing.append(f"raw {raw.name}")
            continue
        if not norm.exists():
            missing.append(f"norm {norm.name}")
            continue
        with norm.open(encoding="utf-8", newline="") as fh:
            cards[part] = next(csv.DictReader(fh))
    assert not missing, f"대장 parts 는 적었는데 없다 — {missing} (pull_data --yes 먼저)"
    bad = check(cards, e.get("mismatch") or {})
    assert not bad, "관리카드 이름 ↔ 내용이 어긋난다\n  " + "\n  ".join(bad)
