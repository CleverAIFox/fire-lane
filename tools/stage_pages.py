#!/usr/bin/env python3
"""
stage_pages.py — 배포 직전에 web/ 을 완성한다.

    uv run python tools/stage_pages.py
    uv run python tools/stage_pages.py --check   빠졌으면 종료코드 1
    uv run python tools/stage_pages.py --deploy  ★ CI 전용 — 배포에 안 실을 파일을 web/ 에서 뺀다
    uv run python tools/stage_pages.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-02. `web/proposal.html` 이 `./proposal.docx` 를 부르는데 그 파일은
`docs/` 에 있었다 — **로컬에서도 배포에서도 404 였다.** Pages 는 `web/` 만
올린다. 그래서 정본을 배포 직전에 옮기는 자리가 생겼다.

★ 2026-10-09 (DECISIONS §444 · PLAN #142). **옮길 것이 없어졌다.** 기획서
  정본이 `docs/proposal.md` 이고 화면은 `web/proposal.html` 이다 — 그 화면은
  `build_proposal.py` 가 구워 **커밋되는** 생성물이라 `web/` 안에 이미 있다.
  `docs/proposal.docx` · `web/proposal.pdf` 는 은퇴했고, PDF 를 굽던
  `tools/proposal_pdf.py`(삭제)와 그 변환기(libreoffice · noto-cjk · poppler)도
  같이 갔다. 남은 일은 **배포에서 뺄 것을 빼는 것** 하나다.
  ★ `STAGED` 를 **표로 남긴다.** 지우면 다음에 옮길 것이 생길 때 자리를
    다시 만들고, 비었다는 사실도 화면에 안 찍힌다 — 비면 비었다고 말한다.

★ 2026-09-22. `web/key.js`(V-World 키) 생성을 뺐다. 그 키를 쓰던 것은 옛 GIS 지도
  하나였고 지도를 걷어냈다(관제 화면이 넘겨받았다). 내비 · 관제는 V-World 를 안 부른다 —
  배경은 커밋된 `web/data/ortho` 타일과 Mapbox(빌드 시 `MAPBOX_TOKEN`)다.

IN    없음 (STAGED 가 비었다)
OUT   web/ 에서 DEPLOY_DROP 제거  (`--deploy` 이고 CI 일 때만)
PARAM STAGED · DEPLOY_DROP · --check · --deploy · --selftest
밖    **화면을 굽지 않는다** — `tools/build_proposal.py` 소관이고 그 산출물은
      커밋된다. **그림도 안 만진다**(`htmlfigs.py`).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from firelane import paths  # ★ import 만으로 .env 를 환경에 얹는다

ROOT = Path(__file__).resolve().parents[1]

# (정본, 배포 위치). 늘어나면 여기 한 줄이다.
# ★ 2026-10-09 (§444 · #142). 비었다. `docs/proposal.docx` 한 줄이 있었고
#   그 파일이 은퇴했다 — 지금 배포에 올라가는 기획서는 커밋된
#   `web/proposal.html` 이라 옮길 것이 없다.
STAGED: list[tuple[str, str]] = []

# ★ 2026-09-22 (DECISIONS §216-5) 배포에 **안 싣는** 것. Pages 는 `web/` 을 통째로 올린다.
#   사용자 지적 — 「플레이북은 협업 방침을 돋보이게 하는 **템플릿**인데 왜 따로 배포하나」.
#   `playbook.html` 은 `render_workflow.py` 가 `workflow.html`(협업 방침)을 만들 때 쓰는 틀이고,
#   배포된 협업 방침은 `workflow.html` 하나다. 같은 모양의 페이지가 두 주소로 떠 있었다.
#   `web/README.md` 는 저장소 안내이지 화면이 아니다.
#   ★ 로컬에서는 지우지 않는다 — `--deploy` 와 `GITHUB_ACTIONS=true` 둘 다일 때만.
#     렌더러가 템플릿을 읽어야 하므로 저장소에서 파일을 빼면 안 된다.
DEPLOY_DROP = ["web/playbook.html", "web/README.md"]


def drop_faults(drop: list[str], exists) -> list[str]:
    """빼라고 적힌 것이 **실재하는가.** 순수 함수다 — `exists` 를 받는다.

    ★ 2026-10-09 (DECISIONS §444). 죽은 항목은 **아무것도 안 하고 조용하다** —
      파일이 이름을 바꿔 배포에 그대로 올라가도 이 목록은 「뺐다」고 말하지
      않고, 안 뺐다고도 말하지 않는다(1족 · 무음 통과). 그래서 센다.
    """
    return [f"{rel} — 빼라고 적혀 있는데 저장소에 없다. 이름이 바뀌었거나 "
            "지워졌다. 목록을 고쳐라 — 죽은 항목은 조용하다"
            for rel in drop if not exists(rel)]


def staged_faults(staged: list[tuple[str, str]], exists) -> list[str]:
    """옮길 정본이 **실재하는가.** 비면 아무 말도 안 한다 — 판정은 `main()` 이 든다."""
    return [f"{src} — 옮길 정본이 없다" for src, _ in staged if not exists(src)]


def selftest() -> int:
    """★ 판정기가 살아 있나. 합성 입력으로 양방향을 민다."""
    bad: list[str] = []
    yes, no = (lambda _r: True), (lambda _r: False)
    if not drop_faults(["web/없는것.html"], no):
        bad.append("죽은 `DEPLOY_DROP` 항목을 안 문다")
    if drop_faults(["web/있는것.html"], yes):
        bad.append("멀쩡한 항목을 문다")
    if drop_faults([], no):
        bad.append("빈 목록에서 운다")
    if not staged_faults([("docs/없는것.md", "web/x.md")], no):
        bad.append("없는 정본을 안 문다")
    if staged_faults([], no):
        bad.append("빈 `STAGED` 에서 운다")
    # ★ 실물 — 목록이 둘 다 참인가
    real = drop_faults(DEPLOY_DROP, lambda rel: (ROOT / rel).exists())
    real += staged_faults(STAGED, lambda rel: (ROOT / rel).exists())
    bad += real
    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 뺄 것 {len(DEPLOY_DROP)}개 · "
          f"옮길 것 {len(STAGED)}개 · 양방향")
    return 1 if bad else 0


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
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
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
    # ★ 빈 표를 **비었다고 말한다.** 종전에는 여기서 `_pdf()` 가 PDF 를 굽고
    #   판정했다. 둘 다 은퇴했으므로 이 반복문은 0회 돈다 — 아무 말도 안 하면
    #   「옮겼다」와 「옮길 것이 없다」가 같은 침묵이 된다(1족 · 무음 통과).
    if not STAGED:
        print("  옮길 정본이 없다 — STAGED 가 비었다(기획서 화면은 커밋된 생성물이다)")
    if not bad:
        print("배포 준비 OK" if check else "배포 준비 완료")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
