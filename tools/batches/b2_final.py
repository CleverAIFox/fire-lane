#!/usr/bin/env python3
"""
b2_final.py — B2 **최종 마감**. 데이터 축을 닫는다.

    uv run python tools/b2_final.py            무엇을 할지만
    uv run python tools/b2_final.py --apply    실제로

멱등이다. `b2_lake` → `b2_close` 다음에 돈다.

★ 앞 배치에서 내가 두 번 추정했고 두 번 다 도구가 반박했다.
  ① `\\nretired:` 를 앵커로 써서 4종이 basemap 하위로 들어갔다 (키 대조가 잡음)
  ② `intake.propose()` 가 무엇으로 매칭하는지 안 보고 등재했다 (--plan 이 잡음)
  이번에는 도구에 먼저 물었다. 아래 셋은 그 답이다.

닫는 것 —

  ⑬ RULES 3줄        intake ②(취득 규칙)가 승인분 3종을 배치하게
  ⑭ 중복 항목 제거    juso_spotaddr_geom_2608 은 spotaddr_geom 과 같은 자산이다
  ⑮ scope 정정        juso 관용은 `jngj` 다. 9종 전부 그렇다
  ⑯ lakecheck 보정    landing_disposition 에 적힌 것은 초록이다
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


# ── ⑬ RULES 3줄 ────────────────────────────────────────────────
# ★ `propose()` 는 단서를 셋 본다 — ① 문서번호 ② 취득 규칙 ③ 대장 stem.
#   ③은 파일명이 **이미 정규명**일 때만 붙는다. 취득처가 준 원본명은
#   ②로만 잡힌다. 그래서 `sources.yaml` 등재는 **필요조건이지 충분조건이
#   아니었다** — 4종을 등재했는데 3종이 안 붙은 이유가 이것이다.
# ★ 날짜 근거: zip 내부 파일명이 `Total.JUSURB.20260801.*` 이다.
#   기존 juso 자산(spotaddr_geom·spotaddr_ref)도 20260801 이라 같은 회차다.
# ★ scope 는 `jngj` 다. 대장의 juso 9종이 전부 그렇다 — 파일 자체는 동구분
#   이지만 제공처가 시 단위로 배포하고 우리 관용이 그것을 따랐다.
RULES_NEW = '''
    # ── 2026-09-10 승인분 3종 ────────────────────────────────
    #   도로명주소 승인이 나서 받은 건물·건물군·기타 도형이다.
    #   zip 내부가 `Total.JUS???.20260801.*` 이라 회차는 2026-08-01 이고,
    #   기존 spotaddr_geom·spotaddr_ref 와 같은 회차다.
    #
    #   ★ 이 세 줄이 없으면 `intake --plan` 이 "대장 매칭 없음" 을 낸다.
    #     대장 등재만으로는 안 된다 — `propose()` ③(stem)은 파일명이 이미
    #     정규명일 때만 붙고, 취득처가 준 원본명은 ②(RULES)로만 잡힌다.
    #
    #   ★ 건물 도형에는 TL_SPOT_CNTC(건물↔도로 접속선) 15,518건이 있다.
    #     CNT_DST_LN 중앙 7.6m · 최대 402.5m. 출동 종점을 "도로 위
    #     최근접점" 이 아니라 실제 출입구로 잡을 수 있다.
    (r"^건물도형_전체분_전남광주통합특별시_동구\\.zip$",
     "juso", "juso_bldg_geom_jngj_20260801.zip"),
    (r"^건물군내동도형_전체분_전남광주통합특별시_동구\\.zip$",
     "juso", "juso_bldggrp_geom_jngj_20260801.zip"),
    #   ★ 기타자료에 터널 10(지산·산수·지원·소태) · 고가 4(너릿재로·
    #     제2순환로) · 교량 36 이 있다. sources.yaml 이 "동명동에 터널·
    #     고가 하부는 없다" 를 근거 없이 단정했는데 이것이 확인 수단이다.
    (r"^기타자료_전체분_전남광주통합특별시_동구\\.zip$",
     "juso", "juso_etc_geom_jngj_20260801.zip"),
'''

RULES_ANCHOR = '''    # ── juso · 도로명주소 ────────────────────────────────────'''


# ── ⑭⑮ 대장 정정 ───────────────────────────────────────────────
SCOPE_FIX = [
    ("  juso_bldg_geom:\n    stem: juso_bldg_geom\n    ext: [zip]\n"
     "    kind: vector\n    layer: raw\n    scope: jngj-donggu\n",
     "  juso_bldg_geom:\n    stem: juso_bldg_geom\n    ext: [zip]\n"
     "    kind: vector\n    layer: raw\n    scope: jngj\n",
     "juso_bldg_geom.scope → jngj (juso 9종 관용)"),
    ("  juso_bldggrp_geom:\n    stem: juso_bldggrp_geom\n    ext: [zip]\n"
     "    kind: vector\n    layer: raw\n    scope: jngj-donggu\n",
     "  juso_bldggrp_geom:\n    stem: juso_bldggrp_geom\n    ext: [zip]\n"
     "    kind: vector\n    layer: raw\n    scope: jngj\n",
     "juso_bldggrp_geom.scope → jngj"),
    ("  juso_etc_geom:\n    stem: juso_etc_geom\n    ext: [zip]\n"
     "    kind: vector\n    layer: raw\n    scope: jngj-donggu\n",
     "  juso_etc_geom:\n    stem: juso_etc_geom\n    ext: [zip]\n"
     "    kind: vector\n    layer: raw\n    scope: jngj\n",
     "juso_etc_geom.scope → jngj"),
]

DISP_FIX = ("""    - file: 사물주소도형_전체분_전남광주통합특별시_동구.zip
      key: juso_spotaddr_geom_2608
      action: ledgered""",
            """    - file: 사물주소도형_전체분_전남광주통합특별시_동구.zip
      key: spotaddr_geom
      action: ingested""")


def drop_duplicate(text: str) -> tuple[str, bool]:
    """`juso_spotaddr_geom_2608` 블록을 통째로 뺀다.

    ★ 이것은 신규 자산이 아니었다. `spotaddr_geom` 이 같은 stem 으로 이미
      있고 실물 `juso_spotaddr_geom_jngj_20260801.zip` 이 raw 에 있다.
      `intake --plan` 이 이것만 매칭한 것은 내 등재 때문이 아니라 RULES 에
      `사물주소도형.*동구\\.zip$` 이 원래 있었기 때문이다.
    """
    m = re.search(r"\n  juso_spotaddr_geom_2608:\n(?:    .*\n|\n(?=    ))*", text)
    if not m:
        return text, False
    return text[:m.start()] + "\n" + text[m.end():], True


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
        before = keyset(self.orig)
        lost = before - after
        # ★ 중복 제거는 **의도한 손실**이다. 그것만 허용한다.
        allowed = {k for k in lost if "juso_spotaddr_geom_2608" in k}
        if lost - allowed:
            print(f"  ✗ sources.yaml  의도 밖 키 손실 — {sorted(lost - allowed)[:6]}")
            return False
        print(f"  {'→' if apply else '·'} sources.yaml")
        for x in self.log:
            print(f"      + {x}")
        for x in self.skip:
            print(f"      = {x} (이미 적용)")
        if allowed:
            print(f"      − 중복 항목 제거 {len(allowed)}키")
        if apply:
            LEDGER.write_text(self.text, encoding="utf-8")
        return True


# ── ⑯ lakecheck 보정 ───────────────────────────────────────────
# ★ landing_disposition 에 `held`/`retired` 로 **기록된** 것을 L3·L4 가
#   계속 운다. 기록된 보류는 초록이어야 한다 — 안 그러면 영구 빨간불이
#   되고 사람이 검사를 끈다(DECISIONS §73).
LAKE_HELPER = '''

def disposed(y: dict) -> set[str]:
    """`landing_disposition` 에 처분이 적힌 파일 이름.

    ★ **판단 보류도 처분이다.** `_quarantine` 이 "판단 보류지 폐기가
      아니다" 인 것과 같다. 적힌 것은 운지 않는다 — 영구 빨간불은
      사람이 검사를 끄게 만든다.
    """
    d = (y.get("landing_disposition") or {}).get("items") or []
    return {str((it or {}).get("file", "")) for it in d if isinstance(it, dict)}
'''


def patch_lakecheck(apply: bool) -> int:
    p = ROOT / "tools" / "lakecheck.py"
    if not p.exists():
        print("  ✗ tools/lakecheck.py 없음")
        return 1
    s = p.read_text(encoding="utf-8")
    if "def disposed(" in s:
        print("  = 이미 적용")
        return 0
    m = re.search(r"^def led\(\) -> dict:\n(?:.*\n)*?    return.*\n", s, re.M)
    if not m:
        print("  ✗ led() 앵커를 못 찾았다")
        return 1
    s = s[:m.end()] + LAKE_HELPER + s[m.end():]
    # L3 — 처분 기록된 것은 제외
    s = s.replace("        out = [p for p in out if _sha(p) not in fp]",
                  "        out = [p for p in out if _sha(p) not in fp]\n"
                  "        skip = disposed(y)          # ★ 적힌 것은 운지 않는다\n"
                  "        out = [p for p in out if p.name not in skip]")
    # L4 — 처분 기록된 것은 제외
    s = s.replace('''        for e, n in Counter(p.suffix.lstrip(".").lower()
                            for p in d.rglob("*") if p.is_file()).items():''',
                  '''        skip = disposed(y)
        for e, n in Counter(p.suffix.lstrip(".").lower()
                            for p in d.rglob("*")
                            if p.is_file() and p.name not in skip).items():''')
    if "disposed(y)" not in s:
        print("  ✗ L3/L4 앵커를 못 찾았다")
        return 1
    print(f"  {'→' if apply else '·'} L3·L4 가 landing_disposition 을 읽는다")
    if apply:
        p.write_text(s, encoding="utf-8")
    return 0


def patch_rules(apply: bool) -> int:
    p = ROOT / "src" / "firelane" / "normalize_raw.py"
    s = p.read_text(encoding="utf-8")
    if "juso_bldg_geom_jngj" in s:
        print("  = 이미 적용")
        return 0
    if RULES_ANCHOR not in s:
        print("  ✗ RULES 의 juso 절 앵커를 못 찾았다")
        return 1
    out = s.replace(RULES_ANCHOR, RULES_NEW.strip("\n") + "\n\n" + RULES_ANCHOR, 1)
    # 문법 확인 — 정규식 이스케이프가 깨지면 여기서 잡힌다
    import ast
    try:
        ast.parse(out)
    except SyntaxError as e:
        print(f"  ✗ 편집 결과가 구문 오류다 — {e.lineno}행")
        return 1
    print(f"  {'→' if apply else '·'} RULES 에 승인분 3종")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.apply:
        bak = LEDGER.with_suffix(".yaml.b2final")
        if not bak.exists():
            shutil.copy2(LEDGER, bak)
            print(f"백업 {bak.name}\n")
    print(f"{'적용' if a.apply else 'dry-run — --apply 로 실행'}\n")

    fail = 0
    print("── ⑬ RULES 3줄  ★ 등재만으로는 intake 가 못 붙인다")
    fail += patch_rules(a.apply)

    print("\n── ⑭ 중복 항목 제거 · ⑮ scope 정정")
    L = Ledger()
    try:
        for old, new, why in SCOPE_FIX:
            L.sub(old, new, why=why)
        L.sub(DISP_FIX[0], DISP_FIX[1],
              why="disposition — 사물주소도형은 이미 반입된 spotaddr_geom 이다")
        t, dropped = drop_duplicate(L.text)
        if dropped:
            L.text = t
            L.log.append("juso_spotaddr_geom_2608 제거 (spotaddr_geom 과 같은 자산)")
        else:
            L.skip.append("중복 항목 제거")
        if not L.commit(apply=a.apply):
            fail += 1
    except RuntimeError as e:
        print(f"  ✗ sources.yaml  {e}")
        fail += 1

    print("\n── ⑯ lakecheck 이 landing_disposition 을 읽게")
    fail += patch_lakecheck(a.apply)

    print(f"\n{'실패 ' + str(fail) + '건' if fail else '전부 통과'}")
    if a.apply and not fail:
        print("\n다음 —")
        print("  uv run python tools/intake.py --plan        # 3종이 붙는지")
        print("  uv run python tools/intake.py --stage --yes")
        print("  uv run python tools/acquire.py --stage --yes")
        print("  uv run python tools/lakecheck.py            # ★ 0건이어야 한다")
        print("  uv run python -m firelane.datalog fsck")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
