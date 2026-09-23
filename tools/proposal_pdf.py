#!/usr/bin/env python3
"""
proposal_pdf.py — 기획서를 **PDF 로 굽고, 구운 것이 성한지 본다.**

    uv run python tools/proposal_pdf.py             굽는다 → web/proposal.pdf
    uv run python tools/proposal_pdf.py --check     이미 구운 것이 성한가 (변환 없음)
    uv run python tools/proposal_pdf.py --selftest  ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-24 (DECISIONS §231). 종전 뷰어(`web/proposal.html`)는 `.docx` 를
  브라우저에서 `docx-preview` 로 그렸다. 그 선택의 근거가 이렇게 적혀 있었다 —

      변환 단계를 두지 않는다. PDF 로 굽으면 "굽는 과정에서 깨졌나" 를
      의심할 자리가 하나 생기고, **그 의심을 확인할 방법이 없다.**

  근거의 앞 절반은 옳고 뒤 절반이 틀렸다. 확인할 방법이 있다 —
  `pdfinfo` 로 쪽수를, `pdftotext` 로 본문 글자를, `pdfimages` 로 그림을
  센다. 그리고 **안 구우면 다른 의심이 생긴다** — 실물이 그랬다.
  브라우저 렌더러는 글꼴 치환과 그림 배치를 제 방식대로 하고, 화면에서
  의도한 글꼴과 그림이 무너졌다. **제출본과 화면이 이미 갈려 있었다.**

★ 굽는 쪽이 이기는 이유는 하나 더 있다 — **PDF 는 글꼴을 안에 넣는다.**
  받는 사람 기계에 한글 글꼴이 없어도 같게 보인다. `.docx` 를 브라우저가
  그리면 그 기계의 글꼴에 의존한다.

── 무엇을 보는가 ──────────────────────────────────────────────
① **한글 글꼴이 깔려 있는가** — 없으면 LibreOffice 가 네모로 굽는다.
   글자층은 멀쩡해서 `pdftotext` 로는 안 걸린다. **굽기 전에** 본다.
② **쪽수** — `PAGES_MIN` 하한. 변환이 반쯤 죽으면 쪽수부터 준다.
③ **본문 글자** — 한글 줄 수 하한 + 판정 수치가 실제로 들어 있는가.
   정본은 `data/golden/segments.fingerprint.json` 이고 `docx_check` 와
   **같은 자리에서 읽는다**(`docx_check._canon`) — 숫자를 두 곳에 적지 않는다.
④ **그림** — `IMAGES_MIN` 하한. 그림이 통째로 빠진 PDF 도 글자는 멀쩡하다.

IN    docs/proposal.docx · data/golden/segments.fingerprint.json
OUT   web/proposal.pdf  (생성물. .gitignore)
PARAM PAGES_MIN · IMAGES_MIN · KOREAN_LINES_MIN
밖    **레이아웃이 예쁜가는 못 본다.** 쪽이 밀렸는지, 표가 쪽 경계에서
      잘렸는지, 글꼴이 의도한 그것인지는 사람이 눈으로 본다. 이 검사가
      드는 것은 「통째로 망가지지 않았다」까지다.
      그리고 **`.docx` 자체가 옳은가도 안 본다** — 그쪽은 `tools/docx_check.py`
      (숫자·용어)와 `tools/docx_figs.py --check`(그림 ↔ 정본) 소관이다.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "proposal.docx"
OUT = ROOT / "web" / "proposal.pdf"

# ── 하한. **오늘 값보다 넉넉히 아래**로 둔다. 이 수는 「망가졌다」를 가르는
#    선이지 「몇 쪽이어야 한다」가 아니다. 기획서는 늘어난다.
PAGES_MIN = 40            # 2026-09-24 실측 63쪽
IMAGES_MIN = 8            # 2026-09-24 실측 — 그림이 통째로 빠지면 여기서 걸린다
KOREAN_LINES_MIN = 800    # 2026-09-24 실측 2,255줄

HANGUL = re.compile(r"[가-힣]")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def korean_font() -> str | None:
    """한글 글꼴 하나. 없으면 None — 굽기 전에 막는 자리다."""
    if not shutil.which("fc-list"):
        return None
    r = _run(["fc-list", ":lang=ko"])
    first = (r.stdout or "").splitlines()
    return first[0] if first else None


def bake(src: Path = SRC, out: Path = OUT) -> list[str]:
    """`.docx` → `.pdf`. 실패 사유 목록을 돌려준다(비면 성공)."""
    if not src.exists():
        return [f"정본이 없다 — {src.relative_to(ROOT)}"]
    if not shutil.which("soffice"):
        return ["`soffice` 가 없다 — libreoffice-writer 를 깔아라"]
    if korean_font() is None:
        return ["한글 글꼴이 없다 — fonts-noto-cjk 를 깔아라. "
                "없이 구우면 본문이 네모가 되고 글자층은 멀쩡해서 안 걸린다"]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / "_pdfbake"
    tmp.mkdir(exist_ok=True)
    r = _run(["soffice", "--headless", "--norestore", "--convert-to", "pdf",
              "--outdir", str(tmp), str(src)], timeout=900)
    made = tmp / (src.stem + ".pdf")
    if not made.exists():
        return [f"변환이 아무것도 안 냈다 — {r.stdout.strip()} {r.stderr.strip()}"]
    made.replace(out)
    shutil.rmtree(tmp, ignore_errors=True)
    return []


# ── 판정 ────────────────────────────────────────────────────────
def pages(pdf: Path) -> int:
    r = _run(["pdfinfo", str(pdf)])
    m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
    return int(m.group(1)) if m else 0


def images(pdf: Path) -> int:
    r = _run(["pdfimages", "-list", str(pdf)])
    return max(0, len([x for x in r.stdout.splitlines() if re.match(r"^\s*\d+", x)]))


def body(pdf: Path) -> str:
    return _run(["pdftotext", str(pdf), "-"]).stdout


def wanted_numbers() -> dict[str, int]:
    """판정 수치의 정본. **`docx_check` 와 같은 자리에서 읽는다.**"""
    import docx_check          # ★ 같은 tools/ 안. 경로 조작을 하지 않는다
    return {k: v for k, v in docx_check._canon().items()
            if isinstance(v, int) and v > 0}


def judge(n_pages: int, n_images: int, text: str,
          want: dict[str, int] | None = None) -> list[str]:
    """빨간불 사유들. 비면 초록. **순수 함수** — 합성 입력으로 부를 수 있다."""
    bad = []
    if n_pages < PAGES_MIN:
        bad.append(f"쪽수 {n_pages} < 하한 {PAGES_MIN} — 변환이 반쯤 죽었다")
    if n_images < IMAGES_MIN:
        bad.append(f"그림 {n_images} < 하한 {IMAGES_MIN} — 그림이 빠졌다. "
                   "글자층은 멀쩡하므로 본문 검사로는 안 걸린다")
    ko = sum(1 for ln in text.splitlines() if HANGUL.search(ln))
    if ko < KOREAN_LINES_MIN:
        bad.append(f"한글 줄 {ko} < 하한 {KOREAN_LINES_MIN} — 본문이 안 나왔다")
    for label, n in (want or {}).items():
        if f"{n:,}" not in text and str(n) not in text:
            bad.append(f"판정 수치가 PDF 본문에 없다 — {label} {n:,}")
    return bad


def check(pdf: Path = OUT) -> list[str]:
    if not pdf.exists():
        return [f"{pdf.relative_to(ROOT)} 이 없다 — 먼저 구워라"]
    for exe in ("pdfinfo", "pdftotext", "pdfimages"):
        if not shutil.which(exe):
            return [f"`{exe}` 가 없다 — poppler-utils 를 깔아라"]
    return judge(pages(pdf), images(pdf), body(pdf), wanted_numbers())


# ── 자기검사 ────────────────────────────────────────────────────
def selftest() -> int:
    """★ 빈 그물인가. 네 갈래를 합성 입력으로 본다."""
    ok_text = ("가나다라마바사\n" * (KOREAN_LINES_MIN + 10)) + "1,281 구간\n"
    dead = []
    if judge(PAGES_MIN, IMAGES_MIN, ok_text, {"구간 수": 1281}):
        dead.append("정상 입력에서 운다")
    if not judge(PAGES_MIN - 1, IMAGES_MIN, ok_text, {}):
        dead.append("쪽수 미달을 안 운다")
    if not judge(PAGES_MIN, IMAGES_MIN - 1, ok_text, {}):
        dead.append("그림 미달을 안 운다")
    if not judge(PAGES_MIN, IMAGES_MIN, "abc\n" * 9999, {}):
        dead.append("본문에 한글이 없는데 안 운다")
    if not judge(PAGES_MIN, IMAGES_MIN, ok_text, {"구간 수": 9999}):
        dead.append("판정 수치가 없는데 안 운다")
    if not wanted_numbers():
        dead.append("판정 수치 정본을 못 읽었다 — golden 지문이 없다")
    if dead:
        print("✗ 판정기 자기검사 실패 — " + ", ".join(dead))
        return 1
    print("✓ 판정기 자기검사 — 다섯 갈래 전부 운다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="기획서를 PDF 로 굽고 성한지 본다")
    ap.add_argument("--check", action="store_true", help="변환 없이 판정만")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    if not a.check:
        if err := bake():
            print("✗ 기획서 PDF")
            for e in err:
                print(f"   {e}")
            return 1
        print(f"  docs/proposal.docx → {OUT.relative_to(ROOT)} "
              f"({OUT.stat().st_size // 1024}KB)")

    bad = check()
    if bad:
        print("✗ 기획서 PDF")
        for b in bad:
            print(f"   {b}")
        return 1
    print(f"✓ 기획서 PDF — {pages(OUT)}쪽 · 그림 {images(OUT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
