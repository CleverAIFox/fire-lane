#!/usr/bin/env python3
"""
b5_secrets.py — **워크플로가 부르는 Secret 이 실제로 등록돼 있나.**

    uv run python tools/batches/b5_secrets.py            무엇을 할지만
    uv run python tools/batches/b5_secrets.py --apply    실제로

★ 오늘 이 구멍에 빠질 뻔했다.
  `pages.yml` 에 `VWORLD_KEY: ${{ secrets.VWORLD_KEY }}` 를 넣었는데
  등록을 안 하면 **빈 문자열이 조용히 들어간다.** 워크플로는 초록불이고,
  배포본만 배경지도가 없다. **초록불인데 화면이 깨지는 부류**이고
  이 저장소가 제일 싫어하는 모양이다 —
  `contract.yml` 죽은 게이트 · `deadcheck ⑤` 의 조용한 return 과 같다.

★ **값은 안 본다. 못 본다.** GitHub API 는 이름과 갱신 시각만 준다.
  그래서 이 검사가 말할 수 있는 것은 하나다 — *"부르는데 없다."*
  값이 맞는지 · 만료됐는지는 **코드로 못 닫는다**(HANDOFF §6 부류).
  할 수 있는 것만 하고, 못 하는 것은 못 한다고 적는다(원칙 ⑥).

★ 새 도구를 만들지 않는다.
  `ruleset_check.py` 가 이미 ⒜ `gh` 를 쓰고 ⒝ "GitHub 설정 ↔ 선언" 을 보고
  ⒞ verify.sh 에 배선돼 있다. 여기 붙이면 `test_tools_are_wired` 도 안 운다.
  같은 자리가 또 나오면 유도를 정본으로 만든다(원칙 ⑤).

★ 방향은 **한쪽만**이다. `.env.example` 때와 다르다.
  "등록됐는데 아무도 안 쓰는 Secret" 은 잡지 않는다 — 다른 워크플로나
  수동 실행이 쓸 수 있고, 지우면 그쪽이 죽는다. 안 쓰는 것을 지우는 판단은
  사람이 한다. **검사가 할 말이 있는 쪽만 말한다.**
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

ANCHOR = '''    if bad:
        print("★ 룰셋 실물이 방침과 다르다.\\n")
'''

CHECK = '''    bad += _secret_gaps()

    if bad:
        print("★ 룰셋 실물이 방침과 다르다.\\n")
'''

FN = '''def _secret_gaps() -> list[str]:
    """워크플로가 부르는 `secrets.X` 중 **등록 안 된 것**을 돌려준다.

    ★ 2026-09-12 (B5). `pages.yml` 에 Secret 참조를 넣고 등록을 안 하면
      빈 문자열이 조용히 들어간다. 워크플로는 초록불이고 배포본만 깨진다.
      VWORLD_KEY 를 배선하면서 실제로 그 상태를 한 번 만들었다.

    ★ **값은 못 본다.** API 가 이름과 시각만 준다. 그래서 이 검사가
      보증하는 것은 "있다" 뿐이다. 값이 맞는지 · 만료됐는지는 사람 몫이다.

    ★ 반대 방향(등록됐는데 안 쓴다)은 일부러 안 본다. 다른 워크플로나
      수동 실행이 쓸 수 있어서 지우라고 할 근거가 없다.

    ★ `secrets.GITHUB_TOKEN` 은 GitHub 이 자동으로 준다. 등록 대상이 아니다.
    """
    want: dict[str, list[str]] = {}
    wf = ROOT / ".github/workflows"
    for p in sorted(wf.glob("*.yml")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            for m in re.finditer(r"secrets\\.([A-Z_][A-Z0-9_]*)", code):
                name = m.group(1)
                if name == "GITHUB_TOKEN":
                    continue
                want.setdefault(name, []).append(f"{p.name}:{i}")

    if not want:
        # ★ 0건이 청결인지 죽음인지 가른다(HANDOFF 원칙 ④).
        return ["워크플로가 부르는 Secret 이 0건이다 — 프로브를 의심하라"
                "\\n      ★ pages.yml 은 최소 MAPBOX_TOKEN 을 부른다"]

    try:
        have = {s["name"] for s in _gh(f"repos/{REPO}/actions/secrets")["secrets"]}
    except (KeyError, TypeError, SystemExit):
        return ["Secret 목록을 못 읽었다 — gh 권한(repo)이 필요하다"
                "\\n      ★ 못 읽은 것을 '없다' 로 적지 않는다"]

    return [f"Secret 미등록: {n}   ← {', '.join(want[n])}"
            "\\n      ★ 참조는 있는데 값이 없으면 **빈 문자열**이 들어간다."
            "\\n        워크플로는 초록불이고 배포본만 깨진다."
            f"\\n        gh secret set {n} --repo {REPO}"
            for n in sorted(set(want) - have)]


'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    p = ROOT / "tools/ruleset_check.py"
    before = p.read_text(encoding="utf-8")
    if "_secret_gaps" in before:
        print("  = tools/ruleset_check.py  이미 적용됨")
        return 0
    if before.count(ANCHOR) != 1:
        sys.exit(f"★ 앵커가 {before.count(ANCHOR)}곳이다. 멈춘다.")

    text = before.replace(ANCHOR, CHECK)
    text = text.replace("def main() -> int:", FN + "def main() -> int:", 1)
    if "\nimport re\n" not in text:
        text = text.replace("import json\n", "import json\nimport re\n", 1)

    try:
        ast.parse(text)
    except SyntaxError as e:
        sys.exit(f"★ 편집 결과가 파싱 안 된다: {e}")

    print(f"  {'✓' if a.apply else '·'} tools/ruleset_check.py   _secret_gaps()")
    if a.apply:
        p.write_text(text, encoding="utf-8")
        print("\n다음 — uv run python tools/ruleset_check.py")
        print("       ★ 일부러 깨뜨려 본다:")
        print("         gh secret delete VWORLD_KEY --repo <repo>  후 다시 돌려")
        print("         '미등록' 이 뜨는지 보고, 다시 등록한다.")
        print("         뜨지 않으면 이 검사는 있으나 마나다(원칙 ④).")
    else:
        print("\n★ dry-run. --apply 를 붙일 것")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
