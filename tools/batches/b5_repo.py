#!/usr/bin/env python3
"""
b5_repo.py — **이관으로 죽은 두 줄을 고친다.**

    uv run python tools/batches/b5_repo.py            무엇을 할지만
    uv run python tools/batches/b5_repo.py --apply    실제로

★ ① `ruleset_check.py:43  REPO = "woongtopia/fire-lane"`

  저장소가 `woongtopia` 조직 → `CleverAIFox` 개인으로 **미러 이관**됐다.
  옛 조직은 기록으로 남기는 것이 의도이고, 문서·그림의 `@woongtopia`
  흔적은 **일부러 안 건드린다.** 그것은 "그때 그랬다" 는 사실이다.

  그런데 이 한 줄은 기록이 아니라 **지금 동작하는 코드**다.
  없는 저장소에 `gh api` 를 치고 404 를 받는다 —

      ★ gh api 실패 — 로그인·권한을 확인하라
        gh: Not Found (HTTP 404)

  화면이 "로그인·권한" 을 의심하라고 하니 원인을 엉뚱한 데서 찾게 된다.
  **룰셋 검사가 도는 척하고 아무것도 안 본다.** 이 저장소가 반복해 겪은
  모양이다 — `contract.yml` 죽은 게이트가 CI 에서 한 번도 안 돌았고,
  `deadcheck ⑤` 가 git 없을 때 조용히 return 했다.

  ★ 상수를 새 값으로 바꾸는 것은 같은 병을 한 번 더 앓는 것이다.
    다음에 또 옮기면 또 404 가 난다. **`git remote` 가 정본이다** —
    저장소가 자기 이름을 이미 알고 있는데 코드가 따로 적어둘 이유가 없다.
    못 읽으면 상수로 떨어지되 **그 사실을 화면에 적는다**(원칙 ⑥).

★ ② `web/config.js:18  // 2026-09-01 woongtopia.github.io 등록 완료`

  V-World 콘솔의 등록 도메인은 이미 `cleveraifox.github.io` 로 바뀌었다.
  주석만 옛 상태를 말한다 — **선언이 실물보다 뒤처진** 자리다.
  실측 —

      gh api … /pages   https://cleveraifox.github.io/fire-lane/
      woongtopia  200 · cleveraifox  200   두 주소가 다 산다

  ★ 키 자체는 이 배치가 못 고친다. 브라우저가 쓰는 키라 어디에 두든
    사용자에게 평문으로 도달하고, 실효 방어는 도메인 잠금 하나다.
    만료 2027-02-04 — HANDOFF §6 "코드로 못 닫는 것" 그대로다.

건드리지 않는 것 —
  `doc_fsck.py:320` · `render_figures.py:222` · `docs/PLAN.md:149`
  운영 이력과 옛 CODEOWNERS 그림이다. 지우면 이력이 거짓이 된다.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

OLD_REPO = 'REPO = "woongtopia/fire-lane"\n'

NEW_REPO = '''def _repo_slug() -> str:
    """`git remote` 에서 owner/name 을 읽는다. **저장소가 자기 이름의 정본이다.**

    ★ 2026-09-12 (B5). 종전에는 `"woongtopia/fire-lane"` 이 상수로 박혀 있었고,
      개인 계정으로 미러 이관한 뒤 `gh api` 가 404 를 냈다. 화면은
      "로그인·권한을 확인하라" 고 해서 원인을 엉뚱한 데서 찾게 만들었다.
      **룰셋 검사가 도는 척하고 아무것도 안 봤다.**

    ★ 새 값으로 바꾸기만 하면 다음 이관에서 똑같이 깨진다.
      remote 를 못 읽을 때만 상수로 떨어지고, **떨어졌다는 사실을 적는다** —
      모르는 것을 아는 척하지 않는다(HANDOFF 원칙 ⑥).
    """
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=ROOT, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ""
    if url:
        slug = url.removesuffix(".git")
        slug = slug.split(":")[-1] if slug.startswith("git@") else \\
            "/".join(slug.split("/")[-2:])
        if slug.count("/") == 1 and all(slug.split("/")):
            return slug
    print("★ git remote 를 못 읽었다 — 아래 값으로 진행한다. 틀릴 수 있다.",
          file=sys.stderr)
    return FALLBACK_REPO


# remote 가 없을 때만 쓴다. 정본이 아니다.
FALLBACK_REPO = "CleverAIFox/fire-lane"
REPO = _repo_slug()
'''

EDITS: list[tuple[str, str, str, str]] = [
    ("tools/ruleset_check.py", OLD_REPO, NEW_REPO, "def _repo_slug("),
    ("tools/ruleset_check.py",
     "import json\nimport subprocess\nimport sys\n",
     "import json\nimport subprocess\nimport sys\nfrom pathlib import Path\n\n"
     "ROOT = Path(__file__).resolve().parent.parent\n",
     "ROOT = Path(__file__).resolve().parent.parent"),
    ("web/config.js",
     "    enabled: true,           // 2026-09-01 woongtopia.github.io 등록 완료\n",
     "    enabled: true,           // 등록 도메인 cleveraifox.github.io (2026-09-12 갱신)\n"
     "                             // ★ 이관 전 등록은 woongtopia.github.io 였다. 두 주소가\n"
     "                             //   다 살아 있으니 어느 쪽을 쓰는지 배포 origin 으로 본다:\n"
     "                             //     gh api repos/<owner>/fire-lane/pages --jq .html_url\n"
     "                             // ★ 이 키는 브라우저가 쓴다. 숨길 수 없다 —\n"
     "                             //   실효 방어는 도메인 잠금 하나뿐이고 만료는 2027-02-04.\n",
     "cleveraifox.github.io (2026-09-12 갱신)"),
]


def _names(src: str) -> set[str]:
    out: set[str] = set()
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

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
        if rel.endswith(".py"):
            lost = _names(before) - _names(text)
            if lost:
                sys.exit(f"★ {rel} — 이름이 사라진다: {sorted(lost)}")
            ast.parse(text)
        print(f"  {'✓' if a.apply else '·'} {rel}")
        if a.apply:
            p.write_text(text, encoding="utf-8")

    print(f"\n변경 {changed} · 건너뜀 {skipped}"
          + ("" if a.apply else "   ★ dry-run. --apply 를 붙일 것"))
    if a.apply:
        print("\n다음 — uv run python tools/ruleset_check.py")
        print("       ★ 404 가 아니라 실제 룰셋 내용이 나와야 한다.")
        print("         여전히 404 면 gh 로그인 문제이고, 그때는 진짜로 권한이다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
