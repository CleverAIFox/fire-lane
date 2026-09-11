#!/usr/bin/env python3
"""
b1_retired.py — **F-148 이 예고한 그 자리.**

    uv run python tools/b1_retired.py --apply

★ 감사 F-148 이 이렇게 적었다 —

      1000행의 `assert ret` 는 대장을 `files` 로 통일하면 **실패한다**.
      **대장을 고치면 테스트가 깨지는 구조**다.

  별칭 5건을 떼자 `retired.file` 이 0 이 됐고 그 전제가 사라졌다.

★ **보호는 안 깨졌다.** `acquire.retired_names()` 는 `ledger.globs(v)` 를
  쓰고 그것이 `stem` 을 탄다(acquire:241). 깨진 것은 테스트의 `ret` 조립뿐이다.
  같은 파일 235행이 이미 적어놨다 — *"조회기의 정본은 firelane.ledger.globs
  하나다. 따로 구현하지 않는다."* 테스트만 그 규칙 밖에 있었다.

  → 테스트도 같은 조회기를 쓰게 한다. `provider_of` 때와 같은 처방이다.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

OLD = '''    ret = {v["file"] for v in (y.get("retired") or {}).values()
           if isinstance(v, dict) and v.get("file")}
    assert ret, "retired 에 file 이 적힌 항목이 없다 — 이 검사가 무의미해진다"'''

NEW = '''    # ★ 2026-09-10. 종전에는 `v["file"]` 단수만 읽었다. 그래서 retired
    #   10종 중 **2종만** 이 검사를 받았고(F-148), 별칭을 폐기하자
    #   0건이 되어 `assert ret` 가 죽었다 — **대장을 고치면 검사가 깨지는
    #   구조**였다. 감사가 그 구조를 미리 적어 두었다.
    #
    #   `acquire.retired_names()` 는 `ledger.globs(v)` 로 지목을 유도한다
    #   (acquire:241). 같은 파일 235행 — "조회기의 정본은
    #   firelane.ledger.globs 하나다. 따로 구현하지 않는다."
    #   **테스트만 그 규칙 밖에 있었다.** 같은 조회기를 쓴다.
    from firelane import ledger as _led

    ret = set()
    for v in (y.get("retired") or {}).values():
        if not isinstance(v, dict):
            continue
        for g in _led.globs(v):
            s = str(g)
            if not any(c in s for c in "*?["):
                ret.add(s)                      # files 예외 항목 — 리터럴이다
                continue
            # `**/stem_*` 는 패턴이다. 이 검사는 실물을 만들어 acquire 에
            # 먹이므로 그 패턴에 맞는 **구체적 이름**이 필요하다.
            if st := v.get("stem"):
                ext = (v.get("ext") or ["csv"])[0]
                ret.add(f"{_led.provider_of(v)}/{st}_jngj_20200101.{ext}")
    assert ret, (
        "retired 가 아무 파일도 지목하지 않는다 — 이 검사가 무의미해진다.\\n"
        "  stem 도 files 도 없는 항목만 남았다는 뜻이다.")'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    A = ap.parse_args().apply
    print(f"{'적용' if A else 'dry-run — --apply 로 실행'}\n")

    p = ROOT / "tests" / "test_guards.py"
    s = p.read_text(encoding="utf-8")
    print("── F-148 — retired 지목을 유도로")
    if "ledger.globs(v)" in s or "_led.globs(v)" in s:
        print("  = 이미 적용")
        return 0
    if s.count(OLD) != 1:
        print(f"  ✗ 앵커를 못 찾았다 ({s.count(OLD)}건)")
        return 1
    out = s.replace(OLD, NEW, 1)
    try:
        ast.parse(out)
    except SyntaxError as e:
        print(f"  ✗ 구문 오류 {e.lineno}행")
        return 1
    print(f"  {'→' if A else '·'} test_acquire_stage_and_quarantine_do_not_fight")
    print("      v['file'] 단수 → ledger.globs(v) 유도")
    if A:
        p.write_text(out, encoding="utf-8")
        print("\n다음 —")
        print("  uv run pytest tests/test_guards.py -q")
        print("  bash tools/verify.sh")
        print("  mv tools/b1_retired.py tools/batches/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
