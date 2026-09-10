#!/usr/bin/env python3
"""
b2_intake.py — B2 ① **처분한 것을 도구가 읽게 한다.**

    uv run python tools/b2_intake.py            무엇을 할지만
    uv run python tools/b2_intake.py --apply    실제로

멱등이다. `b2_final` 다음에 돈다.

★ 왜 필요한가. `b2_final` ⑯에서 `lakecheck` 이 `landing_disposition` 을
  읽게 했는데 `intake` 는 안 고쳤다. 그래서 같은 파일에 두 도구가 다른
  말을 한다 —

    교통소통정보_도로구간정보_설명.pdf
      landing_disposition   action: retired · "API 설명서다. 데이터가 아니다"
      intake --stage        "대장에 없다. 먼저 datasets 또는 retired 에 적어라"

  **적어놨는데 못 읽는다.** 이 저장소를 232건 감사하며 스무 번 지적한
  형태를 고치는 과정에서 새로 만든 것이다.

★ 더 나쁜 것이 있다. `intake._ledger()` 는 `datasets` 만 읽는데(107행)
  실패 메시지는 "datasets **또는 retired** 에 적어라" 라고 한다.
  **메시지와 코드가 다르다.** retired 에 적어도 통과 안 된다. 그러면
  사람이 `--force` 를 쓰게 되고, 그 순간 관문이 죽는다 — 같은 파일
  123행이 "관문은 정확해야 한다. 정상 파일을 막으면 사람이 --force 를
  쓴다" 고 스스로 적어놨다.

닫는 것 셋 —

  ⑰ intake 가 retired 를 읽는다   메시지대로 동작하게 한다
  ⑱ 폐기 항목은 조용히 건너뛴다    판단이 끝난 것을 다시 묻지 않는다
  ⑲ 5종 등재                       .hwp 는 datasets · 나머지 넷은 retired
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sources.yaml"
INTAKE = ROOT / "tools" / "intake.py"


def keyset(text: str) -> set[str]:
    d = yaml.safe_load(text) or {}
    out: set[str] = set()
    for blk, items in d.items():
        out.add(blk)
        if isinstance(items, dict):
            for k, v in items.items():
                out.add(f"{blk}.{k}")
                if isinstance(v, dict):
                    out |= {f"{blk}.{k}.{f}" for f in v}
    return out


# ── ⑰⑱ intake 가 retired 를 읽는다 ────────────────────────────
RETIRED_FN = '''

def _retired() -> dict:
    """폐기 대장. `_ledger()` 가 datasets 만 읽어서 신설했다.

    ★ 2026-09-10. 실패 메시지는 "datasets **또는 retired** 에 적어라" 인데
      코드는 datasets 만 봤다. retired 에 적어도 통과가 안 되니 사람이
      `--force` 를 쓰게 되고, 그 순간 관문이 죽는다 — 같은 파일 123행이
      "관문은 정확해야 한다. 정상 파일을 막으면 사람이 --force 를 쓴다"
      고 스스로 적어놓은 그 자리다.
    """
    f = ROOT / "sources.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return d.get("retired", {}) or {}


def retired_hit(name: str) -> str | None:
    """이 원본명이 폐기 대장에 있나 → 항목 키.

    ★ 폐기는 **판단이 끝난 것**이다. 다시 묻지 않고 조용히 건너뛴다.
      `_quarantine` 이 "판단 보류지 폐기가 아니다" 인 것과 짝이다.
    """
    for k, v in _retired().items():
        if not isinstance(v, dict):
            continue
        if v.get("origin_name") == name:
            return k
        st = v.get("stem")
        stem = name.rsplit(".", 1)[0]
        if st and stem.startswith(st):
            return k
    return None
'''

GATE_OLD = '''        if not force and propose(p, ds)["matched_key"] is None:
            print(f"건너뜀  {p.name}\\n"
                  f"        대장에 없다. 먼저 datasets 또는 retired 에 적어라"
                  f"(§18-3c). 정말 올리려면 --force")
            skipped += 1
            continue'''

GATE_NEW = '''        rk = retired_hit(p.name)
        if rk:
            # ★ 판단이 끝난 것이다. 다시 묻지 않는다.
            print(f"건너뜀  {p.name}\\n"
                  f"        폐기 대장 `{rk}` 에 있다. 편입하지 않는다")
            skipped += 1
            continue
        if not force and propose(p, ds)["matched_key"] is None:
            print(f"건너뜀  {p.name}\\n"
                  f"        대장에 없다. 먼저 datasets 또는 retired 에 적어라"
                  f"(§18-3c). 정말 올리려면 --force")
            skipped += 1
            continue'''


# ── ⑲ 5종 등재 ────────────────────────────────────────────────
# ★ `.hwp` 만 datasets 다. 나머지 넷은 쓸 일이 없다고 판정이 끝났고,
#   그 판정을 지우면 3개월 뒤 또 받고 또 열어본다(retired 머리말).
# ★ `origin_name` 을 새로 둔다. 폐기 항목은 정규명이 없을 수 있는데
#   intake 는 **취득처가 준 이름**으로 묻기 때문이다. stem 만으로는 못 잡는다.
RETIRED_NEW = """  road_facility_pdf_2022:
    what: 도로시설물 현황 378개소 — PDF 판 (hwp 에서 저장)
    origin_name: 1663144302440.pdf
    at: '2026-09-10'
    successor: gjcity_road_facility (hwp 판)
    reason: |
      2026-09-06 에 hwp 를 열어 한컴에서 PDF 로 저장한 것이다
      (Creator: Hwp 2020 · CreationDate D:20260906184943). 배포 원본이
      아니라 우리가 만든 사본이므로 hwp 만 남긴다.

  its_api_guide_hwp:
    what: 교통소통정보 API 제공 안내 (한글)
    origin_name: 교통소통정보 API 제공.hwp
    at: '2026-09-10'
    successor: null
    reason: |
      API 사용 안내 문서다. 데이터가 아니다. its 계열은 이미
      nodelink·changelog 로 반입돼 있고 이 문서에는 좌표도 제원도 없다.

  its_road_section_pdf:
    what: 교통소통정보 도로구간정보 설명서
    origin_name: 교통소통정보_도로구간정보_설명.pdf
    at: '2026-09-10'
    successor: null
    reason: |
      컬럼 설명서다. 데이터가 아니다. 실제 스키마는 반입 후
      inventory 가 contract 로 기록한다 — 문서를 대장에 둘 이유가 없다.

  juso_bldg_alter_2608:
    what: 도로명주소 건물 도형 일변동분 (AlterD 31일치)
    origin_name: 도로명주소 건물 도형.zip
    at: '2026-09-10'
    successor: juso_bldg_geom (전체분)
    reason: |
      AlterD.JUSURB.2026080X.ZIP 31개가 든 일변동분이다. 전체분
      (juso_bldg_geom · 2026-08-01)이 있으면 불필요하다. 변동 이력이
      필요해지면 그때 다시 받는다 — 제공처가 한 달치를 상시 배포한다.

  juso_bldggrp_alter_2608:
    what: 건물군 내 상세주소 동 도형 일변동분 (AlterD 31일치)
    origin_name: 건물군 내 상세주소 동 도형.zip
    at: '2026-09-10'
    successor: juso_bldggrp_geom (전체분)
    reason: |
      위와 같다. 전체분(juso_bldggrp_geom)이 있으면 불필요하다.

"""

DATASETS_NEW = """
  # ── 2026-09-10 도로시설물 (제공처 미상) ──────────────────────
  gjcity_road_facility:
    stem: gjcity_road_facility
    ext: [hwp]
    kind: raw_only
    layer: raw
    scope: jngj
    updated: '2022-09-14'
    origin_name: 1663144302440.hwp
    what: |
      도로시설물 현황 378개소 — 교량 207 · 고가교 14 · 복개도로 2 ·
      천변구조물 4 · 지하차도 15 · 터널/공동구 17 · 옹벽 111 · 절토사면 7
    feeds: []
    feeds_why: |
      ★ 미투입이다. `kind: raw_only` 이라 ingest 가 SKIP 한다. 표를
        파싱하지 않고 사람이 읽은 값을 여기 적는다 — nfa_spec_* 7종과
        같은 방식이다.
    used_for: |
      ★ sources.yaml 이 "동명동에 터널·고가 하부는 없다" 를 근거 없이
        단정했다. 이 표가 그 확인 수단 중 하나다(다른 하나는
        juso_etc_geom 의 TL_SPOT_TUNNEL 10건).
        동구 지명 출현 — 지산 4 · 서석 1 · 두암 1 · 동구 2.
    note: |
      ★ **제공처 미상.** 2026-09-06 에 hwp 를 열어 PDF 로 저장한 흔적만
        남았고 원본 URL 을 잃었다. 기관은 내용으로 확정했다 — 유촌3교 ·
        광신대교 · 어등대교 · 첨단대교 · 평동 · 비아 · 하남산단이 나오므로
        광주 전역 시설물이고 provider 는 gjcity 다.
      ★ `updated` 2022-09-14 는 **추정**이다. 첨부 ID 1663144302440 을
        밀리초 시각으로 읽은 값이고, 표 안의 유일한 날짜는 2021.10.29 다.
        기준일 표기가 없다. 제공처를 찾으면 고친다.
"""

RULE_NEW = '''
    # 도로시설물 현황 378개소. 제공처 미상이라 파일명이 첨부 ID 그대로다.
    # ★ updated 8자리는 그 ID 를 밀리초로 읽은 추정값이다(2022-09-14).
    #   "8자리를 못 얻으면 채우지 않는다" 원칙의 예외라 대장 note 에 적었다.
    (r"^1663144302440\\.hwp$",
     "gjcity", "gjcity_road_facility_jngj_20220914.hwp"),
'''


class Ledger:
    def __init__(self) -> None:
        self.orig = LEDGER.read_text(encoding="utf-8")
        self.text = self.orig
        self.log: list[str] = []
        self.skip: list[str] = []

    def sub(self, old: str, new: str, *, why: str) -> None:
        n = self.text.count(old)
        if n == 0:
            self.skip.append(why)
            return
        if n > 1:
            raise RuntimeError(f"`{old[:44]}` 가 {n}건이다")
        self.text = self.text.replace(old, new, 1)
        self.log.append(why)

    def commit(self, *, apply: bool) -> bool:
        if self.text == self.orig:
            print(f"  = sources.yaml  변경 없음 ({len(self.skip)}건 이미 적용)")
            return True
        try:
            after = keyset(self.text)
        except yaml.YAMLError as e:
            print(f"  ✗ sources.yaml  YAML 오류 — {e}")
            return False
        lost = keyset(self.orig) - after
        if lost:
            print(f"  ✗ sources.yaml  키가 사라졌다 — {sorted(lost)[:6]}")
            return False
        print(f"  {'→' if apply else '·'} sources.yaml")
        for x in self.log:
            print(f"      + {x}")
        for x in self.skip:
            print(f"      = {x} (이미 적용)")
        if apply:
            LEDGER.write_text(self.text, encoding="utf-8")
        return True


def patch_intake(apply: bool) -> int:
    s = INTAKE.read_text(encoding="utf-8")
    if "def retired_hit(" in s:
        print("  = 이미 적용")
        return 0
    m = re.search(r'^    return d\.get\("datasets", \{\}\)\n', s, re.M)
    if not m:
        print("  ✗ _ledger() 앵커를 못 찾았다")
        return 1
    out = s[:m.end()] + RETIRED_FN + s[m.end():]
    if GATE_OLD not in out:
        print("  ✗ cmd_stage 관문 앵커를 못 찾았다")
        return 1
    out = out.replace(GATE_OLD, GATE_NEW, 1)
    import ast
    try:
        ast.parse(out)
    except SyntaxError as e:
        print(f"  ✗ 구문 오류 — {e.lineno}행")
        return 1
    print(f"  {'→' if apply else '·'} _retired() · retired_hit() · 관문 분기")
    if apply:
        INTAKE.write_text(out, encoding="utf-8")
    return 0


def patch_rule(apply: bool) -> int:
    p = ROOT / "src" / "firelane" / "normalize_raw.py"
    s = p.read_text(encoding="utf-8")
    if "gjcity_road_facility_jngj" in s:
        print("  = 이미 적용")
        return 0
    anchor = "    # ── juso · 도로명주소 ────────────────────────────────────"
    if anchor not in s:
        print("  ✗ RULES 앵커를 못 찾았다")
        return 1
    out = s.replace(anchor, RULE_NEW.strip("\n") + "\n\n" + anchor, 1)
    import ast
    try:
        ast.parse(out)
    except SyntaxError as e:
        print(f"  ✗ 구문 오류 — {e.lineno}행")
        return 1
    print(f"  {'→' if apply else '·'} RULES 에 road_facility 1줄")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.apply:
        bak = LEDGER.with_suffix(".yaml.b2intake")
        if not bak.exists():
            shutil.copy2(LEDGER, bak)
            print(f"백업 {bak.name}\n")
    print(f"{'적용' if a.apply else 'dry-run — --apply 로 실행'}\n")

    fail = 0
    print("── ⑰⑱ intake 가 retired 를 읽고, 폐기는 조용히 건너뛴다")
    fail += patch_intake(a.apply)

    print("\n── ⑲ 5종 등재 — retired 5 · datasets 1")
    L = Ledger()
    try:
        if "road_facility_pdf_2022" not in L.text:
            L.sub("  kfs_paint_marking_20241224:\n",
                  RETIRED_NEW + "  kfs_paint_marking_20241224:\n",
                  why="retired 5종 등재 (origin_name 으로 지목)")
        else:
            L.skip.append("retired 5종")
        if "gjcity_road_facility:" not in L.text:
            m = re.search(r"^datasets:\n", L.text, re.M)
            if not m:
                raise RuntimeError("datasets 블록을 못 찾았다")
            L.text = L.text[:m.end()] + DATASETS_NEW.lstrip("\n") + L.text[m.end():]
            L.log.append("datasets.gjcity_road_facility 등재")
        else:
            L.skip.append("gjcity_road_facility")
        if not L.commit(apply=a.apply):
            fail += 1
    except RuntimeError as e:
        print(f"  ✗ sources.yaml  {e}")
        fail += 1

    print("\n── RULES 에 road_facility")
    fail += patch_rule(a.apply)

    print(f"\n{'실패 ' + str(fail) + '건' if fail else '전부 통과'}")
    if a.apply and not fail:
        print("\n다음 —")
        print("  uv run python tools/intake.py --stage --yes   # 폐기 4종이 조용히")
        print("  uv run python tools/acquire.py --stage --yes  # hwp 반입")
        print("  uv run python tools/lakecheck.py")
        print("  uv run python -m firelane.datalog fsck")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
