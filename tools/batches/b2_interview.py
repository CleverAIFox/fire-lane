#!/usr/bin/env python3
"""
b2_interview.py — **D-30 인터뷰를 기한에서 미확보로 옮긴다.**

    uv run python tools/b2_interview.py            무엇을 할지만
    uv run python tools/b2_interview.py --apply    실제로

★ `doc_fsck.DEFERRED` 는 **우리가 할 일**을 재는 기계다. 기한이 오면
  "왜 안 했나" 를 묻는다. 그런데 D-30 은 남이 하고 결과만 받는 일이라
  그 틀에 안 맞는다 — 기한이 와도 우리가 할 수 있는 것이 없고, 그러면
  **매주 울기만 한다.** 우는 것 말고 대응이 없는 빨간불은 사람이 검사를
  끄게 만든다(DECISIONS §73).

  `retired` 도 아니다. 개인 프로젝트로 갈라진 뒤에도 연락이 오가므로
  결과를 실제로 받을 수 있다. 포기한 것이 아니다.

  **세 번째 자리는 이미 있다** — `sources.yaml` 의 `pending`("미확보 목록").
  거기로 옮기고 `fallback` 을 적는다.

★ `fallback` 이 이 배치의 요점이다. 지금은 그것이 안 적혀 있어서 인터뷰가
  프로젝트의 발목을 영구히 잡는다. 결과가 안 와도 앞으로 갈 수 있어야 한다.

닫는 것 셋 —

  ⒜ pending 에 D-30 등재 (fallback 포함)
  ⒝ DEFERRED 에서 그 줄 제거
  ⒞ PLAN 의 앵커 문장 정리   ★ 양쪽 다 해야 한다. 한쪽만 하면 반대로 운다
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent


def keyset(t: str) -> set[str]:
    d = yaml.safe_load(t) or {}
    o: set[str] = set()
    for b, it in d.items():
        o.add(b)
        if isinstance(it, dict):
            for k, _v in it.items():
                o.add(f"{b}.{k}")
    return o


def edit(rel: str, old: str, new: str, why: str, apply: bool) -> int:
    p = ROOT / rel
    if not p.exists():
        print(f"  ✗ {rel} 없음")
        return 1
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n == 0:
        print(f"  = {why} (이미 적용)")
        return 0
    if n > 1:
        print(f"  ✗ {why} — {n}건. 모호하면 안 바꾼다")
        return 1
    out = s.replace(old, new, 1)
    if p.suffix == ".py":
        try:
            ast.parse(out)
        except SyntaxError as e:
            print(f"  ✗ {why} — 구문 오류 {e.lineno}행")
            return 1
    if p.name == "sources.yaml":
        if keyset(s) - keyset(out):
            print(f"  ✗ {why} — 키 손실")
            return 1
    print(f"  {'→' if apply else '·'} {why}")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


PENDING = """- key: vehicle_spec_measured
  desc: 소방차 축거·회전반경 실측 (D-30)
  source: 동부소방서 인터뷰 · 정보공개청구
  status: 외부 진행 — 웅토피아 4인. 우지혜가 청구를 넣었다(2026-09-03)
  blocking: |
    ★ 2026-09-10. `doc_fsck.DEFERRED` 에서 여기로 옮겼다. 그쪽은 **우리가
      할 일**을 재는 기계인데 이것은 남이 하고 결과만 받는 일이다. 기한이
      와도 우리가 할 수 있는 것이 없으므로 매주 울기만 한다 — 우는 것
      말고 대응이 없는 빨간불은 사람이 검사를 끄게 만든다(DECISIONS §73).

      `retired` 도 아니다. 개인 프로젝트로 갈라진 뒤에도 연락이 오가므로
      결과를 실제로 받을 수 있다. 포기한 것이 아니라 **우리가 일정을
      못 정하는 것**이다.

      막고 있는 것 — `vehicle_spec.wheelbase_verified` ·
      `turn_radius_verified` 가 둘 다 false 라 내륜차가 0 으로 나온다.
      회전 판정이 사실상 폭 판정과 같아진다.
  fallback: |
    ★ 결과가 안 와도 앞으로 간다. 관측 최대값으로 못박는다(안전 방향) —
      축거 4.3m · 회전반경 KFS 규격 상한. **값을 크게 잡는 쪽이 안전하다**
      — 작게 잡으면 필요폭이 작게 나오고 그것이 미탐이다(MASTER §3-13).

    ★ 그래도 `wheelbase_verified` 는 **false 로 남긴다.** 값을 정하는 것과
      검증됐다고 적는 것은 다르다. 화면에도 "추정" 이 나가야 한다.

    이 판단은 B4(판정 규칙)에서 확정한다. 그때까지 값은 그대로 둔다.
"""

DEFERRED_OLD = '''    # ★ 2026-09-03. 기한이 지났다. **연기하되 사유를 적는다**(§76 —
    #   적어두지 않은 완화는 영구가 된다).
    #   그날 우지혜가 정보공개청구를 넣었다. 인터뷰 일정보다 그쪽이
    #   먼저 답이 오고, 물어볼 것도 그 결과에 따라 갈린다 —
    #   축거를 청구로 받으면 D-30 질문 다섯 중 셋이 없어진다.
    #   ★ 오창준 이탈일이라 이 항목의 담당은 우지혜다.
    ("2026-09-17", "docs/PLAN.md",
     "한 달째 미착수이고 공문도 안 나갔다", "D-30 인터뷰 일정 확정"),
'''

DEFERRED_NEW = '''    # ★ 2026-09-10 이관. D-30 인터뷰를 `sources.yaml` 의 `pending` 으로
    #   옮겼다(key: vehicle_spec_measured). 여기는 **우리가 할 일**을 재는
    #   기계인데 그것은 남이 하고 결과만 받는 일이라 기한이 와도 우리가
    #   할 수 있는 것이 없다 — 매주 울기만 하고, 우는 것 말고 대응이 없는
    #   빨간불은 사람이 검사를 끄게 만든다(§73).
    #
    #   `pending` 에 `fallback` 을 적었다. 결과가 안 와도 앞으로 간다 —
    #   관측 최대값으로 못박되 `wheelbase_verified` 는 false 로 남긴다.
    #   값을 정하는 것과 검증됐다고 적는 것은 다르다.
'''

PLAN_OLD = "한 달째 미착수이고 공문도 안 나갔다"
PLAN_NEW = ("일정을 우리가 못 정한다 — `sources.yaml` `pending`"
            "(vehicle_spec_measured)로 옮겼고 fallback 을 적었다")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    A = ap.parse_args().apply
    print(f"{'적용' if A else 'dry-run — --apply 로 실행'}\n")
    f = 0

    print("── ⒜ pending 에 D-30 등재 (fallback 포함)")
    led = ROOT / "sources.yaml"
    s = led.read_text(encoding="utf-8")
    if "vehicle_spec_measured" in s:
        print("  = 이미 있다")
    else:
        anchor = "- key: fire_incident\n"
        if s.count(anchor) != 1:
            print(f"  ✗ pending 앵커를 못 찾았다 ({s.count(anchor)}건)")
            f += 1
        else:
            out = s.replace(anchor, PENDING + anchor, 1)
            if keyset(s) - keyset(out):
                print("  ✗ 키 손실")
                f += 1
            else:
                print(f"  {'→' if A else '·'} pending.vehicle_spec_measured")
                if A:
                    led.write_text(out, encoding="utf-8")

    print("\n── ⒝ DEFERRED 에서 제거")
    f += edit("tools/doc_fsck.py", DEFERRED_OLD, DEFERRED_NEW,
              "doc_fsck.DEFERRED — D-30 줄 제거", A)

    print("\n── ⒞ PLAN 앵커 정리  ★ 양쪽 다 해야 한다")
    # ★ 한쪽만 하면 반대로 운다 — 앵커가 살아 있으면 "기한이 지났다",
    #   DEFERRED 에만 남으면 "해소됐다. 그 줄을 지워라".
    f += edit("docs/PLAN.md", PLAN_OLD, PLAN_NEW,
              "PLAN — 앵커 문장 교체", A)

    print(f"\n{'실패 ' + str(f) + '건' if f else '전부 통과'}")
    if A and not f:
        print("\n검증 —")
        print("  uv run python tools/doc_fsck.py | tail -12")
        print("  bash tools/verify.sh 2>&1 | tail -4")
        print("\n  mv tools/b2_interview.py tools/batches/")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
