#!/usr/bin/env python3
"""
tools/pages_add_navi.py — 배포에 React 내비 빌드를 얹는다.

    uv run python tools/pages_add_navi.py            무엇이 바뀔지만
    uv run python tools/pages_add_navi.py --apply

── 왜 필요한가 ─────────────────────────────────────────────────
`pages.yml` 이 `web/` 통째를 Pages 아티팩트로 올린다. 그래서 내비를
**빌드해서 `web/navi/dist` 에 두기만 하면** 자동으로 배포된다.

문제는 `dist` 가 `.gitignore` 라는 것이다. 저장소에 없으므로 CI 가 만들어야
한다. `web/data` 를 커밋하는 것과 반대 원칙인데 이유가 다르다 —
`web/data` 는 재생성에 raw 2.5GB 가 필요하고 `dist` 는 `npm ci` 하나면 된다.

── ★ 왜 npm ci 인가 ────────────────────────────────────────────
`npm install` 은 `package-lock.json` 을 갱신할 수 있다. CI 가 잠금을 바꾸면
"내 기계에서는 됐는데" 가 그대로 재현된다. `ci` 는 잠금 그대로 설치하고
어긋나면 죽는다 — `uv sync --frozen` 과 같은 자리다.

── ★ base 경로 ────────────────────────────────────────────────
Pages 가 `https://<user>.github.io/<repo>/` 로 서빙하므로 내비는
`/<repo>/navi/` 아래에 산다. Vite 의 `base` 를 그렇게 줘야 자산 경로가
맞는다. 저장소 이름은 `github.repository` 에서 온다 — 손으로 박지 않는다.

★ 빌드가 실패하면 **배포를 멈춘다.** 낡은 내비가 올라가면 그것이
  `web/data` 와 갈리고, 갈렸다는 것을 아무도 모른다.

IN    .github/workflows/pages.yml
OUT   같은 파일 (--apply 일 때만)
PARAM --apply
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / ".github" / "workflows" / "pages.yml"

# 이 스텝 **앞에** 끼워넣는다. 아티팩트를 올리기 전이어야 한다.
ANCHOR = "      - name: 배포 준비 (docs/proposal.docx → web/)"

BLOCK = """      - name: 내비 빌드 (web/navi → web/navi/dist)
        # ★ `web/navi/dist` 는 .gitignore 다. `web/data` 를 커밋하는 것과
        #   반대인데 이유가 다르다 — web/data 는 재생성에 raw 2.5GB 가
        #   필요하고 dist 는 `npm ci` 하나면 된다.
        #
        # ★ `npm ci` 다. `install` 은 package-lock 을 갱신할 수 있고,
        #   CI 가 잠금을 바꾸면 "내 기계에서는 됐는데" 가 재현된다.
        #   `uv sync --frozen` 과 같은 자리다.
        #
        # ★ base 는 `github.repository` 에서 온다. Pages 가
        #   `https://<user>.github.io/<repo>/` 로 서빙하므로 내비는
        #   `/<repo>/navi/` 아래에 산다. 저장소 이름을 손으로 박지 않는다.
        #
        # ★ 빌드가 실패하면 **배포가 멈춘다.** 낡은 내비가 올라가면
        #   그것이 web/data 와 갈리고, 갈렸다는 것을 아무도 모른다.
        env:
          VITE_MAPBOX_TOKEN: ${{ secrets.MAPBOX_TOKEN }}
        run: |
          REPO="${GITHUB_REPOSITORY#*/}"
          echo "base = /$REPO/navi/"
          cd web/navi
          npm ci
          VITE_BASE="/$REPO/navi/" npm run build
          test -f dist/index.html || { echo "★ dist/index.html 이 없다"; exit 1; }
          echo "내비 빌드 $(du -sh dist | cut -f1)"

"""

NODE_STEP = """      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: web/navi/package-lock.json

"""



# ── 배포에 내비 빌드가 얹혀 있는가 ──────────────────────────────
# ★ 원래 앵커가 한국어 주석(`내비 빌드 (web/navi → …)`)이었다. 주석을
#   다듬는 순간 검사가 죽는다. **동작**을 앵커로 잡는다.
def check() -> int:
    f = ROOT / ".github" / "workflows" / "pages.yml"
    if not f.exists():
        print("\u2717 pages.yml 이 없다")
        return 1
    if "./.github/actions/build-navi" not in f.read_text(encoding="utf-8"):
        print("\u2717 pages.yml 에 build-navi 액션이 없다 — 배포에서 내비가 빠진다")
        return 1
    print("\u2713 pages.yml 이 build-navi 액션을 부른다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="상태만 본다. 아무것도 안 바꾼다")
    a = ap.parse_args()
    # ★ --check 는 아무것도 안 바꾼다. verify.sh 전용
    if a.check:
        return check()

    if not F.exists():
        print(f"★ {F} 가 없다"); return 1
    txt = F.read_text(encoding="utf-8")

    if "내비 빌드 (web/navi → web/navi/dist)" in txt:
        print("  이미 적용됨. 건너뜀")
        return 0

    if txt.count(ANCHOR) != 1:
        print(f"★ 앵커가 {txt.count(ANCHOR)}번 나온다 (1이어야 한다).")
        print(f"  {ANCHOR}")
        print("  손으로 넣어라.")
        return 1

    add = BLOCK
    if "setup-node" not in txt:
        add = NODE_STEP + BLOCK
        print("  추가  actions/setup-node@v4")
    print("  추가  내비 빌드 스텝")
    print("  위치  '배포 준비' 앞 — 아티팩트 업로드 전이어야 한다")

    if a.apply:
        F.write_text(txt.replace(ANCHOR, add + ANCHOR, 1), encoding="utf-8")
        print("\n  적용")
        print("\n★ Mapbox 토큰이 없어도 배포는 된다.")
        print("  `config.ts` 의 MATCHING_ENABLED 가 false 로 떨어지고")
        print("  음성 안내가 전부 자체 문구로 나간다.")
        print("  토큰을 쓰려면 Settings → Secrets → MAPBOX_TOKEN")
        print("\n확인:")
        print("  cd web/navi && npm ci && VITE_BASE=/fire-lane/navi/ npm run build")
    else:
        print("\n  실행:  uv run python tools/pages_add_navi.py --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
