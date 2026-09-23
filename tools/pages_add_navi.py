#!/usr/bin/env python3
"""
tools/pages_add_navi.py — 배포가 React 내비를 빌드하는가.

    uv run python tools/pages_add_navi.py --check

── ★ 이름이 낡았다 (2026-09-23 · 선언해 둔다) ──────────────────
이 도구는 2026-09-06 에 `pages.yml` 에 내비 빌드 스텝을 **끼워 넣는** 것이었다.
그 뒤 블록이 `.github/actions/build-navi` 합성 액션으로 갔고(W1), 배포 본문이
`stage-site` 로 갔고(§217-5), 2026-09-23 에 배포 워크플로가 **하나**가 됐다(§224).
끼워 넣을 자리가 없어졌으므로 **지금 이 도구는 검사만 한다.**

이름을 안 바꾸는 이유 — `verify.sh` · README · 대장 · 인용 시험이 이 이름으로
서로를 가리킨다. 이름을 옮기는 것은 그 자체로 한 배치다. **범위가 이름보다
좁고 그것이 선언돼 있지 않은 것**이 이 저장소가 반복해서 당한 결함이므로
(PLAN §13 W3-8 · W4-8), 여기 선언해 둔다.

── 무엇을 보는가 ───────────────────────────────────────────────
`web/navi/dist` 는 `.gitignore` 다. 저장소에 없으므로 CI 가 만들어야 한다.
`web/data` 를 커밋하는 것과 반대 원칙인데 이유가 다르다 — `web/data` 는
재생성에 raw 2.5GB 가 필요하고 `dist` 는 `npm ci` 하나면 된다.

빌드가 빠지면 배포는 **초록인 채로** `/navi/` 가 404 인 사이트를 올린다.
08-31 부분 배포 사고와 같은 형태다. 그래서 호출 사슬을 정적으로 본다:

    deploy.yml -> .github/actions/stage-site -> .github/actions/build-navi

IN    .github/workflows/*.yml · .github/actions/stage-site/action.yml
OUT   없음 (종료코드)
PARAM --check
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ── 배포에 내비 빌드가 얹혀 있는가 ──────────────────────────────
# ★ 원래 앵커가 한국어 주석(`내비 빌드 (web/navi -> ...)`)이었다. 주석을
#   다듬는 순간 검사가 죽는다. **동작**을 앵커로 잡는다.
def check() -> int:
    # ★ 2026-09-18 (W1). 앵커가 `pages.yml` 에서 `_deploy.yml` 로 갔다.
    # ★ 2026-09-23 (DECISIONS §224). 지금은 `deploy.yml` 이다 — 배포 여섯을
    #   워크플로 **하나**로 합쳤다. 본문이 하나이므로 재사용 워크플로로 뺄
    #   중복 자체가 없어졌다. **동작은 그대로다** — 배포가 내비를 빌드하는가.
    #   본문이 어디 있든 그것을 묻는 것이 이 검사의 뜻이다(위 머리말).
    wf_dir = ROOT / ".github" / "workflows"
    site = ROOT / ".github" / "actions" / "stage-site" / "action.yml"

    # ★ 파일 이름을 박지 않는다. **사이트를 짓는 워크플로**를 찾는다 —
    #   이름을 박으면 다음에 파일을 옮길 때 검사가 조용히 죽는다.
    dep = [q for q in sorted(wf_dir.glob("*.yml"))
           if "./.github/actions/stage-site" in q.read_text(encoding="utf-8")]
    if not dep:
        print("✗ `stage-site` 를 부르는 워크플로가 없다 — 배포 본문이 사라졌다")
        return 1

    # ★ 하나여야 한다. 둘이면 둘 다 `web/` 을 통째로 올리므로 나중에 도는 쪽이
    #   앞의 것을 덮고, 본문이 갈리면 반드시 어긋난다(W1 이 닫은 2족).
    if len(dep) > 1:
        print(f"✗ 사이트를 짓는 워크플로가 {len(dep)}개다: "
              + ", ".join(q.name for q in dep))
        print("  Pages 는 저장소당 사이트 하나다 — 배포 워크플로도 하나여야 한다(§224)")
        return 1

    f = dep[0]
    body = f.read_text(encoding="utf-8")
    if not site.exists() \
            or "./.github/actions/build-navi" not in site.read_text(encoding="utf-8"):
        print(f"✗ {f.name} 에서 stage-site 로, 거기서 build-navi 로 가는 "
              "사슬이 끊겼다 — 배포에서 내비가 빠진다")
        return 1

    # ★ 배포와 시운전이 **같은** 본문을 태우는가. PR 에서 통과한 것과 main 에서
    #   도는 것이 다르면 시운전이 아무것도 보증하지 않는다(§217-5).
    n = body.count("./.github/actions/stage-site")
    if n != 2:
        print(f"✗ {f.name} 이 stage-site 를 {n}번 부른다 "
              "— 배포와 시운전이 같은 본문을 써야 한다(2번)")
        return 1

    if "push:" not in body or "pull_request:" not in body:
        print(f"✗ {f.name} 이 push 와 pull_request 를 둘 다 안 든다 "
              "— 배포와 시운전 중 하나가 빠졌다")
        return 1

    print(f"✓ {f.name} 하나가 배포와 시운전을 맡고 "
          "stage-site 에서 build-navi 로 내비를 빌드한다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="배포가 내비를 빌드하는가")
    ap.add_argument("--check", action="store_true",
                    help="호출 사슬을 본다. 아무것도 안 바꾼다 (기본이자 유일한 동작)")
    ap.parse_args()
    # ★ 끼워 넣기(--apply)는 2026-09-23 에 없앴다. 끼울 자리가 사라진 코드를
    #   남겨두면 다음 사람이 그것을 돌려보고 시간을 버린다(1족).
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
