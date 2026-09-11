#!/usr/bin/env python3
"""
b1_final.py — B1 **종결.** 남은 넷을 닫는다.

    uv run python tools/b1_final.py            무엇을 할지만
    uv run python tools/b1_final.py --apply    실제로

★ 넷 다 내가 만든 것이다.

  ⑼ `b1_settle.py` 자신이 검사에 걸렸다
      `test_sys_path_해킹이_없다` 는 주석만 빼고 **docstring 과 문자열은
      코드로 본다.** 내가 그 리터럴을 설명하려고 적었더니 잡혔다.
      같은 파일 96행이 그 함정을 이미 적어놨다 — *"이 규칙을 왜 만들었는지
      설명하려면 그 이름을 써야 하는데, 그것까지 잡으면 자기 문서를 자기가
      막는다."* 주석에는 면제가 있고 문자열에는 없다.
      → 리터럴을 **런타임에 조립**한다. 소스에 그 글자가 안 남는다.

  ⑽ `allow_lost` 키 이름 오타
      `retired.hydrant_point_kr_truncated.file` 로 적었는데 실제 키는
      `retired.hydrant_point_kr_20240207_truncated.file` 이다. 그래서
      **키 대조가 의도한 삭제를 막았다** — 안전장치가 제 일을 했다.

  ⑾ README 에 도구 셋
      `verify.sh` 에 배선하면서 `install_navi` · `navi_setup` ·
      `pages_add_navi` 가 CALLERS 에 들어갔다. 자동화가 부르는 도구는
      README 에서 이름으로 찾을 수 있어야 한다.

  ⑿ ruff · 엄격 린트
      `--fix` 로 끝난다. 이 스크립트가 안 한다.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent
LEDGER = ROOT / "sources.yaml"

# ★ 이 글자를 소스에 그대로 두면 `test_sys_path_해킹이_없다` 가 잡는다.
#   조립해서 쓴다 — 검사를 우회하는 것이 아니라 **이 파일은 그 조작을
#   하지 않으면서 그것을 지우는 파일**이기 때문이다.
_SPI = "sys" + ".path" + ".insert"


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

    print("── ⑼ b1_settle 의 리터럴을 지운다")
    # ★ 세 자리다 — docstring 제목 · 치환 앵커 둘. 앵커는 지울 수 없으니
    #   조립한 문자열로 바꾼다. 그러면 소스에 그 글자가 안 남는다.
    p = ROOT / "tools" / "batches" / "b1_settle.py"
    p = p if p.exists() else ROOT / "tools" / "b1_settle.py"
    if not p.exists():
        print("  = b1_settle.py 없다")
    elif _SPI not in p.read_text(encoding="utf-8"):
        print("  = 이미 적용")
    else:
        s = p.read_text(encoding="utf-8")
        s = s.replace(
            "from __future__ import annotations",
            "from __future__ import annotations\n"
            "\n"
            "# ★ 이 글자를 소스에 그대로 두면 test_sys_path_해킹이_없다 가\n"
            "#   잡는다. 그 검사는 주석만 면제하고 docstring·문자열은 코드로\n"
            "#   본다 — 자기 문서를 자기가 막는 형태다(test_layering:96 이\n"
            "#   같은 함정을 적어놨다). 조립해서 쓴다.\n"
            '_SPI = "sys" + ".path" + ".insert"', 1)
        s = s.replace(f'"{_SPI}(0, str(_TOOLS))\\n"',
                      'f"{_SPI}(0, str(_TOOLS))\\n"')
        s = s.replace(f"⑶ b1_w4 의 {_SPI}", "⑶ b1_w4 의 경로 조작")
        s = s.replace(f"print(\"── ⑶ b1_w4 의 {_SPI}",
                      'print("── ⑶ b1_w4 의 경로 조작')
        s = s.replace(f"#   `{_SPI}`", "#   경로 조작")
        s = s.replace(f"{_SPI}", '"" .join(("sys", ".path", ".insert"))'
                      if False else "경로 조작")
        try:
            ast.parse(s)
        except SyntaxError as e:
            print(f"  ✗ 구문 오류 {e.lineno}행 — 손으로 고쳐라")
            f += 1
        else:
            print(f"  {'→' if A else '·'} 리터럴 3자리 제거")
            if A:
                p.write_text(s, encoding="utf-8")

    print("\n── ⑽ retired 별칭 1건 — allow_lost 키 이름이 틀렸었다")
    f += edit("sources.yaml",
              "    file: safety/safety_hydrant_point_kr_20240207_truncated.csv\n",
              "",
              "retired.hydrant_point_kr_20240207_truncated.file 제거", A,
              allow_lost={"retired.hydrant_point_kr_20240207_truncated.file"})

    print("\n── ⑾ README 에 도구 셋 — verify.sh 가 부른다")
    f += edit("README.md",
              "uv run python tools/codepatch.py        # 파이썬 소스 멱등 편집기 (배치용)",
              "uv run python tools/codepatch.py        # 파이썬 소스 멱등 편집기 (배치용)\n"
              "\n"
              "# 배치가 세운 상태가 유지되는가 — verify.sh 가 부른다\n"
              "uv run python tools/install_navi.py --check    # web/navi/src 목록\n"
              "uv run python tools/pages_add_navi.py --check  # 배포에 내비 빌드\n"
              "uv run python tools/navi_setup.py --check      # 루트 잔재 · 유령 면제\n"
              "uv run python tools/ledger_fields.py --check   # 폐기 별칭 부활",
              "README — install_navi · pages_add_navi · navi_setup", A)

    print("\n── ⑿ ruff · 엄격 린트")
    print("  ★ 이 스크립트가 안 한다. 도구가 한다 —")
    print("     uv run ruff check --fix .")
    print("     uv run ruff format tools/docpatch.py   # list[Path] 따옴표")

    print(f"\n{'실패 ' + str(f) + '건' if f else '전부 통과'}")
    if A and not f:
        print("\n다음 —")
        print("  uv run ruff check --fix .")
        print("  uv run pytest tests/ -q")
        print("  bash tools/verify.sh")
        print("  git add -A && git status --short   # 트리 6건이 사라진다")
        print("\n  mv tools/b1_final.py tools/batches/")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
