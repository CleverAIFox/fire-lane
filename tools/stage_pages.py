#!/usr/bin/env python3
"""
stage_pages.py — 배포 직전에 web/ 을 완성한다.

    uv run python tools/stage_pages.py
    uv run python tools/stage_pages.py --check   빠졌으면 종료코드 1
    uv run python tools/stage_pages.py --deploy  ★ CI 전용 — 배포에 안 실을 파일을 web/ 에서 뺀다

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-02. `web/proposal.html` 이 `./proposal.docx` 를 부르는데 그 파일은
`docs/` 에 있다. **로컬에서도 배포에서도 404 였다** — Pages 는 `web/` 만
올린다.

정본은 `docs/proposal.docx` 다. 사본을 커밋하지 않고 배포 직전에 옮긴다 —
`workflow.html` 이 `MASTER §12` 에서 생성되는 것과 같은 관계다(R2).

★ 준비를 워크플로마다 인라인으로 쓰지 않는다. 지금 셋이 같은 `web/` 을
  올리는데(`pages` · `협업 방침` · `기획서`) 준비가 세 벌이면 하나만
  고치는 날이 온다. 이 파일이 그 한 벌이다.

★ 2026-09-22. `web/key.js`(V-World 키) 생성을 뺐다. 그 키를 쓰던 것은 옛 GIS 지도
  하나였고 지도를 걷어냈다(관제 화면이 넘겨받았다). 내비 · 관제는 V-World 를 안 부른다 —
  배경은 커밋된 `web/data/ortho` 타일과 Mapbox(빌드 시 `MAPBOX_TOKEN`)다.

★ 2026-09-24 (DECISIONS §231). 기획서 **PDF** 도 여기서 굽는다. 뷰어가
  `.docx` 를 브라우저에서 그리던 것을 PDF 로 바꿨다 — 글꼴과 그림이 무너졌고,
  PDF 는 글꼴을 안에 넣으므로 받는 기계와 무관하게 같다.
  굽는 판정은 `tools/proposal_pdf.py` 가 든다(쪽수 · 본문 · 판정 수치 · 그림).

IN    docs/proposal.docx
OUT   web/proposal.docx · web/proposal.pdf  (둘 다 생성물. .gitignore)
PARAM --check · --deploy
밖    **PDF 를 여기서 판정하지 않는다.** 이 파일이 하는 것은 「굽기를 부른다」
      까지이고, 성한지는 `tools/proposal_pdf.py --check` 가 CI 에서 본다.
      로컬에 변환기가 없으면 **경고하고 넘어간다** — `serve.py` 로 화면을
      보려는 사람을 libreoffice 설치 앞에서 막지 않는다. 뷰어는 PDF 가 없으면
      내려받기 안내로 바뀐다.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from firelane import paths  # ★ import 만으로 .env 를 환경에 얹는다

ROOT = Path(__file__).resolve().parents[1]

# (정본, 배포 위치). 늘어나면 여기 한 줄이다.
STAGED = [("docs/proposal.docx", "web/proposal.docx")]

# ★ 2026-09-22 (DECISIONS §216-5) 배포에 **안 싣는** 것. Pages 는 `web/` 을 통째로 올린다.
#   사용자 지적 — 「플레이북은 협업 방침을 돋보이게 하는 **템플릿**인데 왜 따로 배포하나」.
#   `playbook.html` 은 `render_workflow.py` 가 `workflow.html`(협업 방침)을 만들 때 쓰는 틀이고,
#   배포된 협업 방침은 `workflow.html` 하나다. 같은 모양의 페이지가 두 주소로 떠 있었다.
#   `web/README.md` 는 저장소 안내이지 화면이 아니다.
#   ★ 로컬에서는 지우지 않는다 — `--deploy` 와 `GITHUB_ACTIONS=true` 둘 다일 때만.
#     렌더러가 템플릿을 읽어야 하므로 저장소에서 파일을 빼면 안 된다.
DEPLOY_DROP = ["web/playbook.html", "web/README.md"]


def _drop_for_deploy() -> None:
    # ★ 환경은 paths 한 곳이 읽는다(env_check — 단일 독자). GITHUB_ACTIONS 는 CI 가 주는 값이다
    if paths.env("GITHUB_ACTIONS") != "true":
        raise SystemExit("★ --deploy 는 CI 전용이다 — 로컬 web/ 에서 템플릿을 지우지 않는다")
    for rel in DEPLOY_DROP:
        p = ROOT / rel
        if p.exists():
            p.unlink()
            print(f"  {rel}  배포에서 뺐다")


def main() -> int:
    # ★ 2026-09-24 (PLAN §13 W13-6 · DECISIONS §243). 종전에는 `"--x" in sys.argv`
    #   였다 — **오타가 조용히 무시된다.** `--delpoy` 는 배포본에서 뺄 것을 안 뺐다.
    #   argparse 는 모르는 인자에 스스로 운다. 직접 구현할 일이 아니다(4족).
    ap = argparse.ArgumentParser(description="발행 페이지 staging")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 낡았는지만 본다")
    ap.add_argument("--deploy", action="store_true", help="배포본에서 뺄 것을 뺀다")
    a = ap.parse_args()
    check = a.check
    if a.deploy:
        _drop_for_deploy()
    bad = 0
    for src_rel, dst_rel in STAGED:
        src, dst = ROOT / src_rel, ROOT / dst_rel
        if not src.exists():
            print(f"★ 정본이 없다 — {src_rel}")
            bad += 1
            continue
        same = dst.exists() and dst.stat().st_size == src.stat().st_size
        if check:
            if not same:
                print(f"! {dst_rel} 이 {src_rel} 과 다르다 — stage_pages 를 돌려라")
                bad += 1
            continue
        if same:
            print(f"  {dst_rel}  이미 최신")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  {src_rel} → {dst_rel}  ({dst.stat().st_size // 1024}KB)")
    bad += _pdf(check)
    if not bad:
        print("배포 준비 OK" if check else "배포 준비 완료")
    return 1 if bad else 0


def _pdf(check: bool) -> int:
    """기획서 PDF. **CI 에서는 필수, 로컬에서는 최선.**

    ★ 판정은 `proposal_pdf` 가 든다 — 여기서 다시 세면 정본이 둘이 된다(§18-3).
    """
    import proposal_pdf  # ★ 같은 tools/ 안. 경로 조작을 하지 않는다

    ci = paths.env("GITHUB_ACTIONS") == "true"
    if not check:
        if err := proposal_pdf.bake():
            for e in err:
                print(("★ 기획서 PDF — " if ci else "! 기획서 PDF 를 못 구웠다 — ") + e)
            if ci:
                return 1
            print("  로컬이라 넘어간다. 뷰어는 내려받기 안내로 바뀐다.")
            return 0
    if bad := proposal_pdf.check():
        for b in bad:
            print(("★ " if ci else "! ") + b)
        return 1 if ci else 0
    print(f"  web/proposal.pdf  {proposal_pdf.pages(proposal_pdf.OUT)}쪽")
    return 0


if __name__ == "__main__":
    sys.exit(main())
