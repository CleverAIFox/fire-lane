#!/usr/bin/env python3
"""
tools/web_manifest.py — web/data 계보. 얇은 래퍼다.

    uv run python tools/web_manifest.py --check

★ 2026-08-22. 본체를 src/firelane/webmanifest.py 로 옮겼다. 두 가지 때문이다.

  1. 생산자가 아닌 곳에 있었다. publish_web.py 는 web/data 를 쓰면서 이
     매니페스트는 안 만들었고, 사람이 이 스크립트를 기억해서 따로 돌려야
     했다. 아무도 안 돌렸다. 지금은 publish 가 자기 계보를 자기가 쓴다.
  2. cwd 에 의존했다(`Path("web/data")`). 저장소 루트에서만 동작했다.

이 파일은 CI 와 손 검사용 진입점으로만 남긴다. `--check` 가 주 용도다.
지문을 다시 뜨려면 `fire-lane --only publish` 를 돌려라 — 그래야 산출물과
계보가 같은 실행에서 나온다.
"""
import sys

from firelane.webmanifest import main

if __name__ == "__main__":
    sys.exit(main())
