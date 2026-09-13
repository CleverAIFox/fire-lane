#!/usr/bin/env python3
"""
b5_vworld.py — **V-World 키를 커밋 대상에서 뺀다.**

    uv run python tools/batches/b5_vworld.py            무엇을 할지만
    uv run python tools/batches/b5_vworld.py --apply    실제로

★★ 먼저 알아야 할 것 — **이 배치는 지금 키를 안전하게 만들지 못한다.**

  그 키는 이미 공개 저장소의 **git 이력에 박혀 있다.** 지금 지워도 옛
  커밋에 남고, 이력은 누구나 clone 한다. 이 배치가 막는 것은 **앞으로**이지
  이미 나간 것이 아니다.

      → **재발급이 유일한 복구다.** V-World 콘솔에서 키를 새로 받고,
        새 키는 커밋하지 말고 `.env` 와 GitHub Secrets 에만 넣어라.
        이 배치를 적용한 뒤에 재발급해야 새 키가 또 안 박힌다.

  ★ 그리고 재발급해도 **은닉은 불가능하다.** 브라우저가 WMTS 를 직접 부르니
    빌드 결과에 실려 나가고 F12 한 번에 보인다. 실효 방어는 도메인 잠금
    하나뿐이다(만료 2027-02-04). 이 배치의 목적은 딱 둘이다 —
      ⒜ 이력에 더 안 쌓이게 한다   ⒝ 재발급을 값싸게 만든다
    지금은 키를 바꾸려면 커밋을 해야 한다. 바꾼 뒤에는 Secret 만 고치면 된다.

★ 어떻게 — 생성물을 하나 끼운다.

      web/key.js        ★ 생성물 · gitignore.  window.__VWORLD_KEY__ 를 정의
      web/config.js     `key: window.__VWORLD_KEY__ || ""`  자리표시자만 커밋
      tools/stage_pages.py  환경에서 읽어 key.js 를 만든다
      web/index.html    key.js 를 config.js **앞에** 싣는다

  ★ 왜 `stage_pages.py` 인가. 그 파일 머리말이 이미 답을 적어놨다 —
    *"준비를 워크플로마다 인라인으로 쓰지 않는다. 지금 셋이 같은 web/ 을
    올린다."* 주입을 `pages.yml` 에 인라인으로 쓰면 나머지 둘이 갈린다.
    **한 곳에서 하고, 로컬(serve.py)과 CI 가 같은 경로를 탄다.**

  ★ 왜 `config.js` 를 직접 치환하지 않는가. 그러면 배포할 때마다 커밋된
    파일이 더러워지고, `커밋된 web/data 가 최신인가` 류 검사와 싸운다.
    생성물은 생성물 자리에 둔다.

  ★ 순서. `index.html:117` 이 *"순서가 중요하다. config.js 가 먼저
    실행돼야 한다"* 고 적어놨다. `key.js` 는 그보다 더 앞이다.

★ 키가 없으면 — 조용히 빈 지도를 주지 않는다.
  `key.js` 가 없으면 콘솔에 이유와 고치는 법을 찍는다. "왜 배경이 안 뜨지"
  로 한 시간 쓰는 것이 이 저장소가 반복해 겪은 모양이다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

KEY_RE = re.compile(r'^    key    : "[0-9A-Fa-f-]{20,}",\n', re.M)

STAGE_FN = '''STAGED = [("docs/proposal.docx", "web/proposal.docx")]


def _write_key_js() -> None:
    """`web/key.js` 를 환경에서 만든다. **생성물이고 커밋하지 않는다.**

    ★ 2026-09-12 (B5). 종전에는 `web/config.js` 에 키가 평문으로 커밋돼
      있었다. 공개 저장소라 이력에 그대로 남는다 — 지금 지워도 옛 커밋에
      남으므로 **재발급이 유일한 복구다.** 이 함수는 앞으로를 막는다.

    ★ 로컬은 `.env`(paths._load_dotenv 가 환경에 얹는다), CI 는
      GitHub Secrets 가 같은 이름으로 넣는다. **경로가 하나다.**

    ★ 값이 없으면 빈 문자열을 쓰되 화면에 적는다. 조용히 빈 지도를 주면
      "왜 배경이 안 뜨지" 로 한 시간을 쓴다(원칙 ⑥ — 모르면 모른다고 적는다).
    """
    key = os.environ.get("VWORLD_KEY", "")
    if not key:
        print("  ★ VWORLD_KEY 가 없다 — 배경지도 없이 나간다.\\n"
              "    로컬:  .env 에 VWORLD_KEY=... 를 적는다\\n"
              "    배포:  GitHub Secrets 에 VWORLD_KEY 를 넣는다")
    out = ROOT / "web/key.js"
    out.write_text(
        "/* 생성물. 커밋하지 않는다 — tools/stage_pages.py 가 만든다.\\n"
        "   ★ 이 키는 브라우저가 쓴다. 숨길 수 없다. 여기 두는 목적은\\n"
        "     git 이력에 안 쌓이게 하고 재발급을 값싸게 만드는 것이다.\\n"
        "     실효 방어는 V-World 도메인 잠금 하나다(만료 2027-02-04). */\\n"
        f'window.__VWORLD_KEY__ = "{key}";\\n', encoding="utf-8")
    print(f"  web/key.js   {'생성' if key else '빈 값으로 생성'}")
'''

EDITS: list[tuple[str, str, str, str]] = [
    # ── config.js — 자리표시자 ───────────────────────────────
    ("web/config.js",
     "  vworld: {\n",
     "  vworld: {\n"
     "    /* ★ 키는 여기 적지 않는다. `web/key.js`(생성물 · gitignore)가 넣는다.\n"
     "       tools/stage_pages.py 가 환경(.env · GitHub Secrets)에서 만든다.\n"
     "       ★ 2026-09-12 이전 커밋에는 평문으로 박혀 있다. 이력은 못 지운다 —\n"
     "         **재발급해야 복구된다.** */\n",
     "★ 키는 여기 적지 않는다"),

    # ── index.html — key.js 를 먼저 싣는다 ───────────────────
    ("web/index.html",
     '<script src="./config.js?v=BUILD"></script>\n',
     "<!-- ★ config.js 보다 먼저다. window.__VWORLD_KEY__ 를 정의한다.\n"
     "     생성물이라 저장소에 없다 — tools/stage_pages.py 가 만든다. -->\n"
     '<script src="./key.js?v=BUILD"></script>\n'
     '<script src="./config.js?v=BUILD"></script>\n',
     './key.js?v=BUILD'),

    # ── stage_pages.py — 주입 ────────────────────────────────
    ("tools/stage_pages.py",
     'STAGED = [("docs/proposal.docx", "web/proposal.docx")]\n',
     STAGE_FN,
     "def _write_key_js("),

    # ── stage_pages main() 이 실제로 부르게 한다 ─────────────
    #   ★ 함수를 넣고 안 부르면 "만들어놓고 배선 안 한 것" 이다.
    #     처음에 정의만 하고 호출을 빼먹어 key.js 가 안 생겼다.
    ("tools/stage_pages.py",
     '        print("배포 준비 OK" if check else "배포 준비 완료")\n',
     "        _write_key_js()\n"
     '        print("배포 준비 OK" if check else "배포 준비 완료")\n',
     "    _write_key_js()\n"),

    # ── .gitignore ───────────────────────────────────────────
    (".gitignore",
     "web/proposal.docx\n",
     "web/proposal.docx\n"
     "# 생성물. V-World 키가 들어간다 — 절대 커밋하지 않는다.\n"
     "web/key.js\n",
     "web/key.js"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    # ── 키 제거는 정규식으로 따로 — 값을 화면에 안 찍는다 ────
    cfg = ROOT / "web/config.js"
    t = cfg.read_text(encoding="utf-8")
    has_key = bool(KEY_RE.search(t))
    if has_key:
        print("  ★ web/config.js 에 평문 키가 있다. 자리표시자로 바꾼다.")
        print("    이 키는 이미 git 이력에 있다 — **재발급해야 복구된다.**")
    elif '__VWORLD_KEY__' in t:
        print("  = web/config.js  이미 적용됨")

    changed = skipped = 0
    by_file: dict[str, list[tuple[str, str, str]]] = {}
    for rel, old, new, done in EDITS:
        by_file.setdefault(rel, []).append((old, new, done))

    for rel, pairs in by_file.items():
        p = ROOT / rel
        before = p.read_text(encoding="utf-8")
        text = before
        for old, new, done in pairs:
            if done in text:
                skipped += 1
                continue
            if text.count(old) != 1:
                sys.exit(f"★ {rel} — 대상이 {text.count(old)}곳이다. 멈춘다.")
            text = text.replace(old, new)
            changed += 1
        if rel == "web/config.js" and has_key:
            text = KEY_RE.sub(
                '    key    : (typeof window !== "undefined"\n'
                '              && window.__VWORLD_KEY__) || "",\n', text)
            changed += 1
        if rel == "tools/stage_pages.py" and "import os" not in text:
            text = text.replace("import shutil\n", "import os\nimport shutil\n", 1)
        if text == before:
            print(f"  = {rel}  이미 적용됨")
            continue
        print(f"  {'✓' if a.apply else '·'} {rel}")
        if a.apply:
            p.write_text(text, encoding="utf-8")

    print(f"\n변경 {changed} · 건너뜀 {skipped}"
          + ("" if a.apply else "   ★ dry-run. --apply 를 붙일 것"))
    if a.apply:
        print("""
다음 — 순서를 지킨다
  1  .env 에  VWORLD_KEY=<지금 키>  를 적는다
  2  uv run python tools/stage_pages.py     web/key.js 가 생기는지
     node tools/web_boot_check.mjs
  3  pages.yml 의 stage_pages 단계에 env 를 붙인다:
         env:
           VWORLD_KEY: ${{ secrets.VWORLD_KEY }}
  4  GitHub Secrets 에 VWORLD_KEY 등록
  5  ★ 여기까지 하고 **키를 재발급한다.** 지금 키는 이력에 공개돼 있다.
     새 키는 .env 와 Secrets 에만 넣는다 — 커밋하면 원점이다.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
