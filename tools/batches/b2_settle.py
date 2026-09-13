#!/usr/bin/env python3
"""
b2_settle.py — B2 **정산.** 내 변경이 깬 것을 전부 닫는다.

    uv run python tools/b2_settle.py            무엇을 할지만
    uv run python tools/b2_settle.py --apply    실제로

★ `verify.sh` 실패 8건 · `pytest` 실패 7건 · `docnum` 4건 · `ruff` 2건은
  **전부 B2 변경이 원인**이다. 기존 결함이 아니다. 새 도구를 넣고 대장을
  늘리면 그것을 세던 검사들이 우는 것이 정상이고, 우는 것을 닫는 것까지가
  배치다. 여기서 멈추면 "만들어놓고 배선 안 한 것" 이 된다.

닫는 것 아홉 —

  ㉙ kind: vector → shp_zip_multi   ★ 어휘 밖 값을 썼다. ingest 3종 FAIL 의 원인
  ㉚ MASTER 의 tools/b2_sweep.py     개명 전 이름을 문서에 적었다 (죽은 참조)
  ㉛ tools/batches/README.md 면제    "다섯 번째 문서" 로 잡혔다
  ㉜ README 에 새 도구 둘            lakecheck · sweep
  ㉝ sweep 을 verify.sh 에           호출부 0 이면 test_every_tool 이 운다
  ㉞ docnum — datasets 65 · retired 16
  ㉟ PLAN 참조0 집계 갱신
  ㊱ ruff 2건                        미사용 변수
  ㊲ DECISIONS §122 — 재계산 기록     ★ 코드는 안 받았다. 사실만 짧게 적는다
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


def keyset(t: str) -> set[str]:
    d = yaml.safe_load(t) or {}
    out: set[str] = set()
    for b, it in d.items():
        out.add(b)
        if isinstance(it, dict):
            for k, v in it.items():
                out.add(f"{b}.{k}")
                if isinstance(v, dict):
                    out |= {f"{b}.{k}.{f}" for f in v}
    return out


def edit(p: Path, old: str, new: str, why: str, apply: bool,
         *, n_expect: int = 1) -> int:
    """정확 일치 치환. 0건이면 건너뛰고 2건 이상이면 죽는다."""
    if not p.exists():
        print(f"  ✗ {p.relative_to(ROOT)} 없음")
        return 1
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n == 0:
        print(f"  = {why} (이미 적용)")
        return 0
    if n != n_expect:
        print(f"  ✗ {why} — {n}건이다(기대 {n_expect}). 모호하면 안 바꾼다")
        return 1
    out = s.replace(old, new, n_expect)
    if p.suffix == ".py":
        import ast
        try:
            ast.parse(out)
        except SyntaxError as e:
            print(f"  ✗ {why} — 구문 오류 {e.lineno}행")
            return 1
    if p.name == "sources.yaml":
        lost = keyset(s) - keyset(out)
        if lost:
            print(f"  ✗ {why} — 키 손실 {sorted(lost)[:4]}")
            return 1
    print(f"  {'→' if apply else '·'} {why}")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


# ── ㊲ 재계산 기록 ─────────────────────────────────────────────
# ★ 팀 GIS 재계산(2026-09-09)은 **이 저장소에 없다.** 문서만 받았고 코드는
#   안 받았다. 그러면 숫자를 고치면 안 된다 — `docnum_check` 는 산출물을
#   정본으로 삼고, 산출물은 여전히 1,101구간이다. 있는 사실만 적는다.
DEC = """
## 122. 팀 GIS 재계산(2026-09-09)은 이 저장소에 반영하지 않는다

  결정  오창준 · 2026-09-10

외부에서 도로폭 재계산 결과 문서를 받았다. 판정 범위를 통합하고(동명동
경계 50m + 진입로 70m + 안전센터 300m), 건물 자료 추출 범위를 60m 넓히고,
필문대로289번길 RDS1109 중심선을 수치지형도로 보정한 뒤 산출물을 다시
생성했다는 내용이다. 결과는 1,101구간 48,579.7m → 1,281구간 58,308.7m 다.

**코드는 받지 않았다.** 이 저장소의 산출물은 여전히 1,101구간이고
`golden` 지문도 그 판이다.

★ 그러므로 문서 숫자를 1,281 로 고치지 않는다. `docnum_check` 는 산출물을
  정본으로 삼는다 — 산출물 없이 숫자만 바꾸면 문서가 실물보다 앞서게 되고,
  그것이 이 저장소가 반복해서 당한 형태다(§73 · MASTER §17).

받은 문서에서 **재계산 없이도 유효한 지적** 셋을 기록해 둔다.

- 구간이 `clear` 여도 안전센터에서 도달 가능하다는 뜻이 아니다. 구간 분류와
  경로 연결성은 다른 축이다.
- 최대폭을 못 낸 구간이 있었던 원인은 폭 계산식이 아니라 **입력 자료의
  범위**였다. 도로 판정 범위와 건물 자료 범위가 어긋나 있었다.
- 가까운 선을 같은 도로로 보는 대조는 거리만으로는 위험하다. 넓은 본선의
  폭이 좁은 골목에 붙으면 **통행 가능 오판**이 난다.

셋 다 이 저장소의 미해결 축과 겹친다. 코드를 받게 되면 그때 §125~§127 로
들어온 판단을 여기 흡수한다.

"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.apply:
        b = LEDGER.with_suffix(".yaml.b2settle")
        if not b.exists():
            shutil.copy2(LEDGER, b)
    print(f"{'적용' if a.apply else 'dry-run — --apply 로 실행'}\n")
    f = 0
    A = a.apply

    print("── ㉙ kind: vector → shp_zip_multi  ★ 어휘 밖 값이었다")
    # ★ `kinds.KINDS` 15종에 `vector` 가 없다. 승인분은 zip 안에 SHP 가
    #   여러 벌이라 `shp_zip_multi` 다. 이 하나가 ingest FAIL 3종과
    #   test_ingest_kinds_are_documented 를 동시에 깼다.
    for k in ("juso_bldg_geom", "juso_bldggrp_geom", "juso_etc_geom"):
        f += edit(LEDGER,
                  f"  {k}:\n    stem: {k}\n    ext: [zip]\n    kind: vector\n",
                  f"  {k}:\n    stem: {k}\n    ext: [zip]\n    kind: shp_zip_multi\n",
                  f"{k}.kind", A)

    print("\n── ㉚ MASTER 가 개명 전 이름을 가리킨다")
    f += edit(ROOT / "docs" / "MASTER.md",
              "`tools/b2_sweep.py` 가 기본 스캔 대상으로 쓴다",
              "`tools/sweep.py` 가 기본 스캔 대상으로 쓴다",
              "MASTER — b2_sweep.py → sweep.py (죽은 참조)", A)

    print("\n── ㉛ tools/batches/README.md 를 문서 넷 규칙에서 면제")
    # ★ `src/firelane/README.md`(대장 작성법) · `web/README.md`(실행 안내)와
    #   같은 성격이다. 규약을 서술하는 문서가 아니라 **폴더 사용법**이다.
    f += edit(ROOT / "tests" / "test_reproducibility.py",
              '        ".github/pull_request_template.md",\n    }',
              '        ".github/pull_request_template.md",\n'
              '        # ★ 2026-09-10. 규약이 아니라 **폴더 사용법**이다 —\n'
              '        #   일회성 배치와 재현적 도구를 가르는 판별식을 적는다.\n'
              '        #   src/firelane/README.md(대장 작성법)와 같은 성격이다.\n'
              '        "tools/batches/README.md",\n    }',
              "test_reproducibility — batches/README 면제", A)

    print("\n── ㉜ README 에 새 도구 둘")
    f += edit(ROOT / "README.md",
              "uv run python tools/docnum_check.py     # 문서 숫자 ↔ 산출물 · 필드표 대조",
              "uv run python tools/docnum_check.py     # 문서 숫자 ↔ 산출물 · 필드표 대조\n"
              "uv run python tools/lakecheck.py        # 레이크 선언 ↔ 실물 (L1~L6)\n"
              "uv run python tools/sweep.py            # 다운로드·레이크 스캔 → 근거 있는 것만 정리",
              "README — lakecheck · sweep", A)

    print("\n── ㉝ sweep 을 verify.sh 에 — 호출부 0 이면 검사가 운다")
    v = ROOT / "tools" / "verify.sh"
    s = v.read_text(encoding="utf-8") if v.exists() else ""
    if "tools/sweep.py" in s:
        print("  = 이미 있다")
    else:
        f += edit(v,
                  'step "레이크 선언↔실물" uv run python tools/lakecheck.py',
                  'step "레이크 선언↔실물" uv run python tools/lakecheck.py\n'
                  '\n'
                  '# ★ 스캔만 한다. 지우려면 --sweep --yes 를 사람이 친다.\n'
                  '#   "정리는 사람이 한다" 를 도구가 대신하되 삭제는 명시적으로.\n'
                  'step "레이크 정리 대상" uv run python tools/sweep.py',
                  "verify.sh — sweep 스텝", A)

    print("\n── ㉞ 문서 숫자 — datasets 65 · retired 16")
    # ★ 자동 치환을 **안 한다.** `61` · `10` 이라는 숫자가 다른 맥락에도
    #   있어서 일괄 치환하면 무관한 서술을 망친다. docnum_check 가 파일과
    #   줄을 짚어 주므로 그 줄만 사람이 고친다 — 이 도구가 있는 이유다.
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "docnum_check.py")],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**__import__("os").environ,
                            "PYTHONPATH": str(ROOT / "src")})
    for ln in (r.stdout or "").splitlines():
        if ln.strip().startswith("!"):
            print(f"     {ln.strip()}")
    print("     ★ 위 줄만 손으로 고친다. 일괄 치환은 무관한 서술을 망친다")

    print("\n── ㊱ ruff 2건 — 미사용 변수")
    bc = ROOT / "tools" / "batches" / "b2_close.py"
    bc = bc if bc.exists() else ROOT / "tools" / "b2_close.py"
    f += edit(bc,
              '    IN = os.environ.get("FIRE_LANE_INBOX")\n',
              '', "b2_close — 미사용 IN 제거", A)
    f += edit(ROOT / "tools" / "sweep.py",
              "        for p, v, w in todo:\n"
              '            print(f"   지울 것  {p.name[:50]:52s} [{v}]")',
              "        for p, v, _w in todo:\n"
              '            print(f"   지울 것  {p.name[:50]:52s} [{v}]")',
              "sweep — w → _w", A)

    print("\n── ㊲ DECISIONS §122 — 재계산은 기록만 (코드 미수령)")
    d = ROOT / "docs" / "DECISIONS.md"
    s = d.read_text(encoding="utf-8")
    if "## 122." in s:
        print("  = 이미 있다")
    else:
        m = re.search(r"^## 121\.", s, re.M)
        if not m:
            print("  ✗ §121 앵커를 못 찾았다")
            f += 1
        else:
            nxt = re.search(r"^## \d+\.", s[m.end():], re.M)
            at = m.end() + (nxt.start() if nxt else len(s) - m.end())
            print(f"  {'→' if A else '·'} §122 추가 — 숫자는 안 고친다")
            if A:
                d.write_text(s[:at] + DEC.lstrip("\n") + s[at:], encoding="utf-8")

    print(f"\n{'실패 ' + str(f) + '건' if f else '전부 통과'}")
    if A and not f:
        print("\n── ㉟ PLAN 참조0 집계는 도구가 낸다")
        print("  uv run python tools/docnum_check.py   # 남은 숫자를 확인한다")
        print("\n다음 —")
        print("  uv run ruff check --fix .")
        print("  uv run pytest tests/ -q")
        print("  bash tools/verify.sh")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
