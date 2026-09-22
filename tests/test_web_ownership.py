#!/usr/bin/env python3
"""
test_web_ownership.py — web/ 의 소유 경계를 코드가 지키는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-24. `publish_web.py` 가 `web/index.html` 을 직접 고치고 있었다.
그 파일은 CODEOWNERS 상 `@marscoolcat @AIMasterFox` 공동 소유다.

    ?v=72297f4e  →  ?v=2a038ad8      × 4곳

스탬프는 판정 데이터의 내용 해시다. 따라서 이 변경은 무작위 잡음이
아니라 **판정이 실제로 바뀐 실행에서만** 발생한다. 결과적으로 GIS 측이
의미 있는 산출 변경을 낼 때마다 UI 담당 리뷰가 요구된다.

`index.html` 주석은 이미 올바른 방식을 명시하고 있었다 —
*"저장소에 커밋된 상태에서는 문자 그대로 BUILD 이고, 그래도 동작한다."*
규약이 주석으로만 존재했고 이를 강제하는 검사가 없었다.

── 원칙 ────────────────────────────────────────────────────────
소유 경계는 **경로**로 구분하며 CODEOWNERS 가 이를 선언한다.

    생성물   web/data/            GIS 단독. 코드가 생성한다
    사람     web/index.html       사이트 입구(관제 화면으로 넘기는 한 쪽). 코드가 수정하지 않는다
             web/config.js        공동 소유. 파이프라인이 **읽는다**(판정색 · 편성 · 지형) — 쓰지 않는다

★ 2026-09-22. 옛 GIS 지도(web/js · style.css)를 걷어냈다. `web/index.html` 은 관제 화면
  (`navi/?view=ops`)으로 넘기는 정적 입구가 됐고 캐시 스탬프(`?v=BUILD`)가 없어져
  「스탬프가 커밋됐는가」 검사도 지웠다. 소유 경계 검사는 그대로다.

코드가 사람 소유 파일을 수정하기 시작하면 경로 기반 분리가 성립하지
않는다. 이 검사는 그 경계를 강제한다.

IN    .github/CODEOWNERS · src/firelane/*.py · tools/*.py
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from firelane.generated import for_role

ROOT = Path(__file__).resolve().parent.parent

# CODEOWNERS 가 사람 소유로 선언한 web 파일. 코드가 쓰면 안 된다.
HUMAN_OWNED = ["web/index.html", "web/config.js", "web/README.md"]
(GENERATED_DIR,) = for_role("web-out")   # 정본은 firelane/generated.py (W3-13)


def test_pipeline_does_not_write_human_owned_web_files():
    """★ 코드가 사람 소유 파일을 쓰지 않는가.

    문자열로 경로를 조립하는 경우까지 잡으려고 파일명 조각을 본다.
    쓰기 함수(write_text · open(... "w") · to_file)와 같은 줄에 있으면 걸린다.
    """
    WRITE = re.compile(r"write_text|write_bytes|\.open\(\s*[\"']w|to_file|"
                       r"open\([^)]*[\"']w[\"']")
    bad = []
    # ★ 2026-09-22 (§217-5 · deadcheck ⑤). src 는 파일명 조각으로, tools 는 **경로**로 본다 —
    #   tools 는 제 산출 폴더에 `README.md` 를 쓰는 것이 정상이라(`baseline.py`) 조각 대조는 오검이다.
    #   `web` 이 같은 줄에 있어야 web 파일이다.
    for root, need_web in ((ROOT / "src", False), (ROOT / "tools", True)):
      for p in sorted(root.rglob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if not WRITE.search(code):
                continue
            if need_web and "web" not in code:
                continue
            for f in HUMAN_OWNED:
                name = f.rsplit("/", 1)[1]
                if f'"{name}"' in code or f"'{name}'" in code:
                    bad.append(f"  {p.relative_to(ROOT)}:{i}  {name}\n"
                               f"      {line.strip()[:70]}")
    assert not bad, (
        "코드가 사람 소유 web 파일을 쓴다. 생성물은 web/data/ 안에서 끝나야 한다.\n"
        + "\n".join(bad))


def test_codeowners_covers_every_web_path():
    """web/ 아래 모든 경로에 소유자가 있는가.

    소유자 없는 파일은 아무나 고치고 아무도 리뷰하지 않는다.
    """
    co = ROOT / ".github/CODEOWNERS"
    # ★ 2026-09-22 (PLAN §13 W10-1 · deadcheck ③). 추적 파일이다. 종전 `return` 은 지워지면 초록이었다.
    assert co.exists(), ".github/CODEOWNERS 가 없다 — 추적 파일이다"
    owned = [l.split()[0].strip("/")
             for l in co.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.lstrip().startswith("#")]

    # ★ 2026-08-24. 디스크가 아니라 **git 이 추적하는 것**만 본다.
    #
    #   종전에는 `rglob("*")` 로 디스크를 훑었다. 그래서 기기마다 결과가
    #   달랐다 — 같은 커밋에서 한쪽은 통과하고 다른 쪽은 실패했다.
    #   원인은 `.gitignore` 에 등재된 생성물이 로컬에만 남아 있던 것이다
    #   (`web/review.html`, `jijeok_review.py` 산출물).
    #
    #   CODEOWNERS 는 **리뷰 권한**을 정하는 파일이다. 저장소에 들어오지
    #   않는 파일은 리뷰 대상이 아니므로 소유자를 요구할 이유가 없다.
    #   `index.html` 처럼 커밋되는 파일과는 성격이 다르다.
    #
    #   ★ 이 변경이 검사의 기기 의존성도 함께 제거한다.
    import subprocess
    tracked = subprocess.run(
        ["git", "ls-files", "web"], cwd=ROOT,
        capture_output=True, text=True).stdout.split()
    # ★ 2026-09-22. 작업 트리에서 지웠고 아직 커밋 전인 경로는 뺀다 — 옛 지도(web/js)를 걷어낸
    #   작업 트리에서 CODEOWNERS 줄을 먼저 지우면 여기가 「지운 파일에 주인이 없다」로 울었다.
    gone = set(subprocess.run(
        ["git", "ls-files", "--deleted", "web"], cwd=ROOT,
        capture_output=True, text=True).stdout.split())
    tracked = [t for t in tracked if t not in gone]
    bad = []
    for rel in sorted(tracked):
        if not any(rel == o or rel.startswith(o.rstrip("/") + "/") for o in owned):
            bad.append(f"  {rel}")
    assert not bad, (
        f"CODEOWNERS 에 소유자가 없는 web 경로 {len(bad)}건\n"
        + "\n".join(bad[:20])
        + "\n  소유자 없는 파일은 아무도 리뷰하지 않는다.")


def test_generated_web_data_is_not_hand_editable():
    """web/data 산출물에 '손으로 고치지 마라' 가 적혀 있는가."""
    m = ROOT / GENERATED_DIR / "_manifest.json"
    # ★ 2026-09-22 (PLAN §13 W10-1 · deadcheck ③). `_manifest.json` 은 생성물이지만 **추적된다**(clone 직후에도
    #   있다). 종전 `return` 은 지워지면 경고 검사를 초록으로 껐다.
    assert m.exists(), f"{m.relative_to(ROOT)} 가 없다 — 추적되는 생성물이다"
    assert "손으로 고치지 마라" in m.read_text(encoding="utf-8"), \
        "web/data/_manifest.json 에 생성물 경고가 없다"


def test_old_map_is_retired_and_entry_redirects():
    """옛 GIS 지도가 되살아나지 않았고, 입구가 관제로 넘기는가.

    ★ 2026-09-22. 옛 지도(web/js 30모듈 · style.css · 패널 index.html)를 걷어냈다 — 관제 화면
      (`navi/?view=ops`)이 넘겨받았다. W9-4 · W9-5(토글 이름이 index.html 에 손으로 박혀
      map.js 와 갈렸다)는 그 표면이 없어져 **재발할 자리가 없다.** 이 시험이 그 증표다 —
      지도가 돌아오면 여기서 운다.

    ★ 입구는 **상대 주소**여야 한다. Pages 는 `/<repo>/` 아래에, serve.py 는 `/` 에 서빙한다.
      외부 자원도 안 부른다 — 입구가 CDN 하나에 걸려 빈 화면이 되면 안 된다.
    """
    # ★ 추적 파일로 본다 — `web/key.js` 는 gitignore 된 생성물이라 사용자 기계에 남아 있을 수 있다
    #   (옛 stage_pages 가 만들었다). 남은 것은 tidy 가 치운다. 되살아난 것은 **커밋**이다.
    tracked = subprocess.run(["git", "ls-files", "web/js", "web/style.css", "web/key.js"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    assert not tracked, f"{tracked[:3]} 이 되살아났다 — 옛 지도는 걷어냈다(관제가 넘겨받았다)"
    s = (ROOT / "web/index.html").read_text(encoding="utf-8")
    assert re.search(r'http-equiv="refresh"\s+content="0;\s*url=navi/\?view=ops"', s), \
        "web/index.html 이 관제(navi/?view=ops)로 넘기지 않는다"
    assert 'href="navi/?view=ops"' in s, "meta refresh 가 막힌 환경을 위한 링크가 없다"
    assert "<script" not in s, "입구에 스크립트가 있다 — 넘기기만 하는 한 쪽이다"
    ext = re.findall(r'(?:src|href)="(?:https?:)?//[^"]+"', s)
    assert not ext, f"입구가 외부 자원을 부른다: {ext}"
    assert not re.search(r'(?:src|href|url)=\s*"?/', s), "입구에 절대 경로가 있다 — Pages 의 /<repo>/ 밑에서 깨진다"
