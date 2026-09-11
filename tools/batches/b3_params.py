#!/usr/bin/env python3
"""
b3_params.py — **임계값 사본 세 벌을 정본 import 로 바꾼다.** (B3 첫 타)

    uv run python tools/batches/b3_params.py            무엇을 할지만
    uv run python tools/batches/b3_params.py --apply    실제로

★ `widen W2` 가 짚은 세 줄이다.

      tools/jijeok_probe.py:109   COV_MIN  = 0.5
      tools/route_probe.py:66     NODE_TOL = 0.5
      tools/wmax_audit.py:47      TRUCK    = 3.0

  셋 다 `src/firelane/seg/params.py` 에 정본이 있다. R3 — 임계값의 정본은
  params.py 하나다(MASTER §18-5).

★ **값이 같은지 먼저 확인했다.** 이것이 이 배치가 "불변"인 근거다.

      COV_MIN  0.5 ↔ 0.5      NODE_TOL 0.5 ↔ 0.5      TRUCK 3.0 ↔ 3.0

  하나라도 달랐으면 import 로 바꾸는 순간 프로브 출력이 바뀐다. 그건 사본
  제거가 아니라 **판정 변경**이고 B4(재잠금)로 가야 한다. 그래서 이 스크립트는
  지우기 전에 `_assert_same()` 로 리터럴을 다시 대조하고, 어긋나면 멈춘다.
  ★ 사람이 눈으로 본 것을 스크립트가 한 번 더 본다 — 원칙 ①.

★ 선례가 있다. `tools/corner_probe.py:73` 은 이미
  `from firelane.seg.params import NODE_TOL` 를 쓰고, 같은 격자 반올림
  (`round(x / NODE_TOL)`)을 한다. route_probe 만 제 숫자를 들고 있었다.

★ `wmax_audit.py` 는 순수 표준 라이브러리 도구다. params.py 가 `os` 말고는
  아무것도 import 하지 않으므로 무거운 의존이 붙지 않는다.

건드리지 않은 것 —
  `tools/jijeok_review.py:58  TH = 3.0` 은 TRUCK 의 **네 번째 사본**인데
  `tests/test_guards.py:1231` 이 소스 문자열 `"TH = 3.0"` 을 못박아 강제한다.
  import 로 바꾸면 그 가드가 깨진다. 가드와 함께 고쳐야 하므로 별건이다.
  ★ 검사가 사본을 강제하는 자리다. B3 남은 목록에 올린다.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

PARAMS = "src/firelane/seg/params.py"


# ── 양성 대조: 사본 값이 정본과 같은가 ─────────────────────────
def _const(rel: str, name: str) -> str | None:
    """모듈 최상위 `name = <리터럴>` 의 리터럴을 문자열로 돌려준다."""
    src = (ROOT / rel).read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == name:
                try:
                    return repr(ast.literal_eval(node.value))
                except ValueError:
                    return None
    return None


def _assert_same(rel: str, name: str) -> str:
    want = _const(PARAMS, name)
    got = _const(rel, name)
    if want is None:
        sys.exit(f"★ 정본에 {name} 이 없다 — {PARAMS}")
    if got is None:
        return f"  · {name:9s} 사본 없음 (이미 import 된 듯)"
    if want != got:
        sys.exit(
            f"★ 멈춘다. {rel} 의 {name}={got} 가 정본 {want} 와 다르다.\n"
            f"  import 로 바꾸면 출력이 바뀐다. 이건 B3(불변)가 아니라\n"
            f"  B4(판정 규칙 · 재잠금) 항목이다. 전이표에 올릴 것.")
    return f"  · {name:9s} {got} ↔ 정본 {want}  일치"


# ── 손실 금지: 편집 전후 최상위 이름 집합 대조 ─────────────────
def _names(src: str) -> set[str]:
    """import 로 묶인 이름도 정의로 센다. 그래야 상수→import 가 손실이 아니다."""
    out: set[str] = set()
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return out


# (rel, old, new, done)  — done 이 이미 있으면 건너뛴다.
#   ★ "new 가 이미 있나" 로 판정하면 안 된다. 삭제 편집의 new 는 원문의
#     부분집합이라 처음부터 참이 되고, 그 줄이 조용히 안 지워진다.
#     실제로 한 번 그렇게 났다 — TRUCK 이 안 지워진 채 "이미 적용됨" 이 떴다.
EDITS: list[tuple[str, str, str, str]] = [
    # ── jijeok_probe: 커버율 자격 ──────────────────────────────
    ("tools/jijeok_probe.py",
     "from firelane.paths import INTERIM, PROCESSED, QUARANTINE, RAW\n",
     "from firelane.paths import INTERIM, PROCESSED, QUARANTINE, RAW\n"
     "from firelane.seg.params import COV_MIN\n",
     "from firelane.seg.params import COV_MIN"),
    ("tools/jijeok_probe.py",
     "COV_MIN = 0.5               # 유효 표본이 이 비율 미만이면 산출하지 않는다\n",
     "# COV_MIN — 정본을 import 한다(위). 구간의 절반 미만을 잰 소스는\n"
     "#           대표시키지 않는다. 폭 판정과 지적 대조가 같은 자격을 써야\n"
     "#           두 값의 비교가 선다.\n",
     "# COV_MIN — 정본을 import 한다(위)."),

    # ── route_probe: 노드 동일시 반경 ──────────────────────────
    ("tools/route_probe.py",
     "from firelane.seg.graph import STATIONS\n",
     "from firelane.seg.graph import STATIONS\n"
     "from firelane.seg.params import NODE_TOL\n",
     "from firelane.seg.params import NODE_TOL"),
    ("tools/route_probe.py",
     "CRS_M = 5186\nNODE_TOL = 0.5\n",
     "CRS_M = 5186\n"
     "# NODE_TOL — 정본을 import 한다(위). `corner_probe.py` 와 같은 격자\n"
     "#            반올림이다. 다른 값을 쓰면 경로 그래프의 노드가 segments 와\n"
     "#            갈리고, 같은 도로가 두 그래프에서 다르게 끊긴다.\n",
     "# NODE_TOL — 정본을 import 한다(위)."),

    # ── wmax_audit: 통과 하한 ──────────────────────────────────
    ("tools/wmax_audit.py",
     "import collections\nimport json\nimport sys\nfrom pathlib import Path\n",
     "import collections\nimport json\nimport sys\nfrom pathlib import Path\n"
     "\n"
     "# 정본. params.py 는 os 말고 아무것도 import 하지 않으므로 이 도구의\n"
     "# 순수 표준 라이브러리 성격이 깨지지 않는다.\n"
     "from firelane.seg.params import TRUCK\n",
     "from firelane.seg.params import TRUCK"),
    ("tools/wmax_audit.py",
     'SEG = ROOT / "data/processed/segments.geojson"\nTRUCK = 3.0\n',
     'SEG = ROOT / "data/processed/segments.geojson"\n'
     "# TRUCK — 정본을 import 한다(위). 이 도구는 판정을 고치지 않고 규모만\n"
     "#         재므로, 임계가 정본과 갈리면 잰 숫자가 곧바로 무의미해진다.\n",
     "# TRUCK — 정본을 import 한다(위)."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    print("양성 대조 — 사본 값이 정본과 같은가")
    for rel, name in (("tools/jijeok_probe.py", "COV_MIN"),
                      ("tools/route_probe.py", "NODE_TOL"),
                      ("tools/wmax_audit.py", "TRUCK")):
        print(_assert_same(rel, name))
    print()

    by_file: dict[str, list[tuple[str, str, str]]] = {}
    for rel, old, new, done in EDITS:
        by_file.setdefault(rel, []).append((old, new, done))

    changed = skipped = 0
    for rel, pairs in by_file.items():
        p = ROOT / rel
        before = p.read_text(encoding="utf-8")
        text = before
        for old, new, done in pairs:
            if done in text:
                skipped += 1
                continue
            if text.count(old) != 1:
                sys.exit(f"★ {rel} — 대상이 {text.count(old)}곳이다. 멈춘다.\n{old!r}")
            text = text.replace(old, new)
            changed += 1
        if text == before:
            print(f"  = {rel}  이미 적용됨")
            continue

        lost = _names(before) - _names(text)
        if lost:
            sys.exit(f"★ {rel} — 최상위 이름이 사라진다: {sorted(lost)}. 되돌린다.")
        try:
            ast.parse(text)
        except SyntaxError as e:
            sys.exit(f"★ {rel} — 편집 결과가 파싱 안 된다: {e}")

        print(f"  {'✓' if a.apply else '·'} {rel}")
        if a.apply:
            p.write_text(text, encoding="utf-8")

    print(f"\n변경 {changed} · 건너뜀 {skipped}"
          + ("" if a.apply else "   ★ dry-run. --apply 를 붙일 것"))
    if a.apply:
        print("\n다음 — uv run python tools/widen.py; bash tools/verify.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
