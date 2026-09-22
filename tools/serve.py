#!/usr/bin/env python3
"""
tools/serve.py — web/ 개발 서버. 캐시를 끈다.

════════════════════════════════════════════════════════════════
★ `python -m http.server` 를 쓰지 마라.

  그것은 Cache-Control 을 보내지 않고 Last-Modified 만 보낸다. 브라우저는
  헤더가 없으면 휴리스틱으로 캐시하는데, ES 모듈에 대해서는 특히 세게 잡는다.
  2026-08-22 에 툴팁을 고치고 몇 번을 새로고침해도 옛 화면이 떴다.
  시크릿 창을 열어야 바뀌는 상태였다.

  개발 중에는 성가신 정도지만, 같은 일이 배포에서 일어나면 관제사가
  옛 segments.geojson 을 보게 된다 — **판정 색이 틀린 지도**다.
  배포 쪽은 publish_web.py 의 내용 해시 스탬프가 막고, 개발 쪽은 이 서버가 막는다.

사용:
    uv run python tools/serve.py           # 8000
    uv run python tools/serve.py 8080
════════════════════════════════════════════════════════════════

★ 2026-09-22. 옛 지도(web/js)를 걷어냈다. `web/index.html` 은 `navi/?view=ops` 로
  넘기는 입구다. 그래서 이 서버는 **배포 모양**을 흉내 낸다 —

    /navi/...        web/navi/dist/...   (빌드본. 배포에서도 이 자리에 앉는다)
    /<repo>/...      /... 와 같다         (빌드본의 base 가 /fire-lane/navi/ 라서)
    그 밖            web/...             (index.html · data/ · proposal.html · review.html)

  빌드본이 없으면 입구가 소스 index.html 로 떨어져 빈 화면이 된다 — 시작할 때 말한다.
  개발 중에는 `cd web/navi && npm run dev` 가 낫다(vite 가 ../data 를 같이 준다).
"""
from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web"
DIST = ROOT / "navi" / "dist"
# 빌드본의 base(`vite.config.ts` 기본값 `/fire-lane/navi/`)의 저장소 몫. 떼고 서빙한다.
BASE = "/fire-lane"


class NoCacheHandler(SimpleHTTPRequestHandler):
    """모든 응답에 no-store. 조건부 요청도 막는다."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_header(self, keyword, value):
        # ★ Last-Modified 를 보내면 브라우저가 304 로 되돌아온다.
        #   no-store 를 붙였어도 조건부 요청 자체를 없애는 편이 확실하다.
        if keyword == "Last-Modified":
            return
        super().send_header(keyword, value)

    def translate_path(self, path):
        # ★ 배포 모양. 빌드본은 /fire-lane/navi/assets/... 를 부르고, 입구는 navi/ 로 넘긴다.
        if path == BASE or path.startswith(BASE + "/"):
            path = path[len(BASE):] or "/"
        if (path == "/navi" or path.startswith("/navi/")) and DIST.is_dir():
            return str(DIST) + super().translate_path(path[len("/navi"):] or "/")[len(str(ROOT)):]
        return super().translate_path(path)

    def log_message(self, fmt, *args):
        # 304 는 이제 안 나오는 게 정상이다. 200 만 조용히 남긴다.
        code = args[1] if len(args) > 1 else ""
        if str(code).startswith("2"):
            return
        super().log_message(fmt, *args)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not ROOT.exists():
        raise SystemExit(f"★ {ROOT} 가 없다")
    handler = partial(NoCacheHandler, directory=str(ROOT))
    print(f"web/ → http://localhost:{port}   (캐시 없음)")
    print(f"  관제  http://localhost:{port}/navi/?view=ops")
    if not DIST.is_dir():
        print("  ★ web/navi/dist 가 없다 — 관제·내비가 빈 화면이다.\n"
              "    cd web/navi && npm run build   (개발은 npm run dev)")
    print("  Ctrl+C 로 종료")
    try:
        ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()
    except KeyboardInterrupt:
        print("\n종료")


if __name__ == "__main__":
    main()
