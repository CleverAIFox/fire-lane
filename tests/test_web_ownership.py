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
    사람     web/style.css        UI 단독
             web/index.html       공동 소유. 코드가 수정하지 않는다
             web/config.js        공동 소유. 양측이 함께 참조하는 유일한 파일

코드가 사람 소유 파일을 수정하기 시작하면 경로 기반 분리가 성립하지
않는다. 이 검사는 그 경계를 강제한다.

IN    .github/CODEOWNERS · src/firelane/*.py · web/index.html
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# CODEOWNERS 가 사람 소유로 선언한 web 파일. 코드가 쓰면 안 된다.
HUMAN_OWNED = ["web/index.html", "web/style.css", "web/config.js",
               "web/README.md"]
GENERATED_DIR = "web/data"


def test_repo_index_html_has_no_baked_stamp():
    """저장소의 index.html 에는 ?v=BUILD 만 있어야 한다.

    실제 해시는 배포 시점에 `.github/workflows/pages.yml` 이 찍는다.
    """
    s = (ROOT / "web/index.html").read_text(encoding="utf-8")
    baked = re.findall(r"\?v=([0-9a-fA-F]{8})\b", s)
    assert not baked, (
        f"index.html 에 해시 스탬프가 커밋돼 있다: {sorted(set(baked))}\n"
        "  ?v=BUILD 로 두고 배포 시점에 찍는다. 그 파일은 공동 소유라\n"
        "  파이프라인이 고치면 GIS 작업마다 UI 리뷰가 걸린다.")


def test_pipeline_does_not_write_human_owned_web_files():
    """★ 코드가 사람 소유 파일을 쓰지 않는가.

    문자열로 경로를 조립하는 경우까지 잡으려고 파일명 조각을 본다.
    쓰기 함수(write_text · open(... "w") · to_file)와 같은 줄에 있으면 걸린다.
    """
    WRITE = re.compile(r"write_text|write_bytes|\.open\(\s*[\"']w|to_file|"
                       r"open\([^)]*[\"']w[\"']")
    bad = []
    for p in sorted((ROOT / "src").rglob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if not WRITE.search(code):
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
    if not co.exists():
        return
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
    if not m.exists():
        return
    assert "손으로 고치지 마라" in m.read_text(encoding="utf-8"), \
        "web/data/_manifest.json 에 생성물 경고가 없다"
