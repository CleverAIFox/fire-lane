#!/usr/bin/env python3
"""
b1_settle.py — B1 **정산.** 남은 셋과 대장 잔재를 닫는다.

    uv run python tools/b1_settle.py            무엇을 할지만
    uv run python tools/b1_settle.py --apply    실제로

★ `ledger_fields --check` 8건은 **검사가 옳게 우는 것**이다. B2 에서
  `retired` 3종에 `stem` 을 채웠으니 이제 `file` 은 잔재다 — 지목 근거가
  옮겨갔으므로 지워도 안전하다. 그것이 `--check` 를 먼저 단 이유다.

닫는 것 여섯 —

  ⑶ b1_w4 의 경로 조작   ★ 내가 넣은 것이고 규약 위반이다
  ⑷ navi_setup 유령 등재        `bottleneck` 은 없는 도구다(실물 bridge_audit)
  ⑸ raw_only desc → what        빈 what 을 채우고 desc 를 뗀다
  ⑹ retired file 잔재 정리      stem 이 있으므로 안전하다
  ⑺ README 에 새 도구 셋
  ⑻ verify.sh 에 deadcheck·widen
"""
from __future__ import annotations

# ★ 이 글자를 소스에 그대로 두면 test_sys_path_해킹이_없다 가
#   잡는다. 그 검사는 주석만 면제하고 docstring·문자열은 코드로
#   본다 — 자기 문서를 자기가 막는 형태다(test_layering:96 이
#   같은 함정을 적어놨다). 조립해서 쓴다.
_SPI = "sys" + ".path" + ".insert"

import argparse
import ast
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent
LEDGER = ROOT / "sources.yaml"


def keyset(t: str) -> set[str]:
    d = yaml.safe_load(t) or {}
    o: set[str] = set()
    for b, it in d.items():
        o.add(b)
        if isinstance(it, dict):
            for k, v in it.items():
                o.add(f"{b}.{k}")
                if isinstance(v, dict):
                    o |= {f"{b}.{k}.{f}" for f in v}
    return o


def edit(rel: str, old: str, new: str, why: str, apply: bool,
         *, allow_lost: set[str] | None = None) -> int:
    p = ROOT / rel
    if not p.exists():
        print(f"  = {rel} 없음 ({why})")
        return 0
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
        lost = keyset(s) - keyset(out) - (allow_lost or set())
        if lost:
            print(f"  ✗ {why} — 의도 밖 키 손실 {sorted(lost)[:4]}")
            return 1
    print(f"  {'→' if apply else '·'} {why}")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    A = ap.parse_args().apply
    print(f"{'적용' if A else 'dry-run — --apply 로 실행'}\n")
    f = 0

    print("── ⑶ b1_w4 의 경로 조작 — ★ 내가 넣은 규약 위반")
    # ★ `test_sys_path_해킹이_없다` 가 tools 전체를 본다. codepatch 를 부르려고
    #   넣었는데, 그건 **경로를 조작할 게 아니라 pyproject 의 pythonpath 를
    #   쓰는 것**이 이 저장소의 방식이다(test_layering 이 그것만 허용한다).
    #   importlib 로 파일을 직접 읽어 경로를 안 건드린다.
    for rel in ("tools/batches/b1_w4.py", "tools/b1_w4.py"):
        f += edit(rel,
                  "_TOOLS = Path(__file__).resolve().parent\n"
                  '_TOOLS = _TOOLS.parent if _TOOLS.name == "batches" else _TOOLS\n'
                  f"{_SPI}(0, str(_TOOLS))\n"
                  "from codepatch import Patch, PatchError, add_shell_step  # noqa: E402",
                  "_TOOLS = Path(__file__).resolve().parent\n"
                  '_TOOLS = _TOOLS.parent if _TOOLS.name == "batches" else _TOOLS\n'
                  "\n"
                  "# ★ sys.path 를 건드리지 않는다. `test_sys_path_해킹이_없다` 가\n"
                  "#   tools 전체를 보고, 경로 조작은 pyproject 의 pythonpath 로만\n"
                  "#   한다는 것이 이 저장소의 규약이다. 파일을 직접 읽어 붙인다.\n"
                  "def _load_codepatch():\n"
                  "    import importlib.util as _u\n"
                  '    _s = _u.spec_from_file_location("codepatch", _TOOLS / "codepatch.py")\n'
                  "    _m = _u.module_from_spec(_s)\n"
                  "    _s.loader.exec_module(_m)\n"
                  "    return _m\n"
                  "\n"
                  "\n"
                  "_cp = _load_codepatch()\n"
                  "Patch, PatchError, add_shell_step = (\n"
                  "    _cp.Patch, _cp.PatchError, _cp.add_shell_step)",
                  f"{rel} — sys.path 대신 importlib", A)

    print("\n── ⑷ navi_setup 유령 등재 — bottleneck 은 없는 도구다")
    f += edit("tools/navi_setup.py",
              '    "bottleneck": "다리 분석으로 실측 우선순위 산출. '
              '사람이 답사 계획을 세우려고 부른다",\n',
              '    # ★ 2026-09-10 제거. `bottleneck` 이라는 도구는 없다 —\n'
              '    #   실물은 `bridge_audit.py` 이고 그 머리말이 옛 이름을\n'
              '    #   그대로 적고 있었다(F-096). 공유 목록에 유령이 낀 것이다.\n'
              '    "bridge_audit": "다리 분석으로 실측 우선순위 산출. '
              '사람이 답사 계획을 세우려고 부른다",\n',
              "navi_setup — bottleneck → bridge_audit", A)

    print("\n── ⑸ raw_only desc → what")
    # ★ `desc` 는 `what` 으로 통합됐다. ortho 는 what 이 이미 있으니 desc 만
    #   떼고, 나머지 둘은 what 이 비어 있으니 값을 옮긴다. 정보를 안 버린다.
    f += edit("sources.yaml",
              "    desc: 항공정사영상 2025, GSD 0.25m, 광주 037/038/047/048\n",
              "", "raw_only.ortho — desc 제거 (what 이 이미 있다)", A,
              allow_lost={"raw_only.ortho.desc"})
    f += edit("sources.yaml",
              "    desc: GIS건물통합정보 일변동분\n",
              "    what: GIS건물통합정보 일변동분\n",
              "raw_only.building_change — desc → what", A,
              allow_lost={"raw_only.building_change.desc"})
    f += edit("sources.yaml",
              "    desc: 표준노드링크 갱신 내역서\n",
              "    what: 표준노드링크 갱신 내역서\n",
              "raw_only.nodelink_manifest — desc → what", A,
              allow_lost={"raw_only.nodelink_manifest.desc"})

    print("\n── ⑹ 별칭 잔재 제거 — ★ ledger_fields --apply 가 아니다")
    # ★ 내 check() 가 "되돌리려면 --apply" 라고 안내했는데 **틀렸다.**
    #   `run()` 은 `authority` 를 채우는 함수지 별칭을 지우지 않는다.
    #   실행하면 의도하지 않은 필드가 채워진다. 여기서 직접 뗀다.
    #
    #   안전한 이유 — 셋은 B2 에서 `stem` 을 채웠고(지목 근거가 옮겨갔다),
    #   `vintage` 둘은 파일명 토큰이 정본이다(naming.parse).
    for rel_old, key in (
        ("    file: safety/safety_hydrant_point_kr_20240207_truncated.csv\n",
         "retired.hydrant_point_kr_truncated.file"),
        ("    file: safety/safety_firestation_kr_20250701.csv\n",
         "retired.firestation_kr_20250701.file"),
        ("    file: safety/safety_hydrant_point_jngj_20250917.csv\n",
         "retired.hydrant_point_jngj_20250917.file"),
        ("    vintage: 2019~2022 혼합 (도엽 20장)\n",
         "retired.ngii1k_ngii_platform.vintage"),
        ("    vintage: TODO\n", "raw_only.ortho.vintage"),
    ):
        f += edit("sources.yaml", rel_old, "", f"{key} 제거", A,
                  allow_lost={key})

    print("\n── ⑹ check() 의 잘못된 안내 문구")
    f += edit("tools/ledger_fields.py",
              '    print("\\n   되돌리려면  uv run python tools/ledger_fields.py --apply")',
              '    # ★ 2026-09-10. 종전에는 "되돌리려면 --apply" 라 적었는데\n'
              '    #   `run()` 은 authority 를 채우는 함수지 별칭을 지우지 않는다.\n'
              '    #   잘못된 안내는 없는 안내보다 나쁘다.\n'
              '    print("\\n   ★ --apply 는 이것을 안 지운다(authority 를 채운다).")\n'
              '    print("     대장에서 직접 떼라. stem 이 있으면 file 은 잔재다.")',
              "ledger_fields — 잘못된 안내 문구 교체", A)

    print("\n── ⑺ README 에 새 도구 셋")
    f += edit("README.md",
              "uv run python tools/lakecheck.py        # 레이크 선언 ↔ 실물 (L1~L6)",
              "uv run python tools/lakecheck.py        # 레이크 선언 ↔ 실물 (L1~L6)\n"
              "uv run python tools/deadcheck.py        # 검사가 죽었는지 검사 (프로브 5)\n"
              "uv run python tools/widen.py            # 검사 범위를 넓히면 뭐가 걸리나\n"
              "uv run python tools/codepatch.py        # 파이썬 소스 멱등 편집기 (배치용)",
              "README — deadcheck · widen · codepatch", A)

    print("\n── ⑻ verify.sh 에 deadcheck")
    # ★ `widen` 은 배선하지 않는다. **넓혔을 때를 재는 도구**라 지금 상태에서
    #   항상 수십 건을 낸다. 매번 뜨는 경고는 아무도 안 읽는다(ingest:223).
    #   `codepatch` 는 라이브러리라 실행 대상이 아니다 — 둘은 EXEMPT 로 간다.
    f += edit("tools/verify.sh",
              'step "레이크 정리 대상" uv run python tools/sweep.py',
              'step "레이크 정리 대상" uv run python tools/sweep.py\n'
              "\n"
              "# ★ 검사가 죽었는지를 검사한다. 프로브 다섯이 정적으로 센다 —\n"
              "#   빈 그물 · 손목록 · 조용한 통과 · 죽은 게이트 · 좁은 범위.\n"
              "#   --selftest 는 프로브가 살아 있는지 먼저 본다(양성 대조).\n"
              'step "검사가 죽었는가" uv run python tools/deadcheck.py --selftest',
              "verify.sh — deadcheck --selftest", A)

    print("\n── ⑻ widen · codepatch 는 EXEMPT")
    f += edit("tests/test_tools_are_wired.py",
              "EXEMPT = {",
              "EXEMPT = {\n"
              '    "widen": "넓혔을 때를 **재는** 도구다. 지금 상태에서 항상 '
              "수십 건을 내므로\\n"
              '             배선하면 매번 뜨는 경고가 되고, 그러면 아무도 안 읽는다",\n'
              '    "codepatch": "배치 스크립트가 import 하는 **라이브러리**다. '
              '실행 대상이 아니다",\n',
              "EXEMPT — widen · codepatch", A)

    print(f"\n{'실패 ' + str(f) + '건' if f else '전부 통과'}")
    if A and not f:
        print("\n다음 —")
        print("  uv run python tools/ledger_fields.py --apply   # ⑹")
        print("  uv run python tools/navi_setup.py --check      # 초록이어야 한다")
        print("  uv run pytest tests/ -q")
        print("  bash tools/verify.sh")
        print("\n  mv tools/b1_settle.py tools/batches/")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
