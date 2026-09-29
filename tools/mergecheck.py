#!/usr/bin/env python3
"""
mergecheck.py — **빨간불 위에서 머지된 PR 이 있는가.**

    uv run python tools/mergecheck.py            최근 머지 20건
    uv run python tools/mergecheck.py --limit 50
    uv run python tools/mergecheck.py --selftest  ★ 판정기가 빨강을 빨강이라 하는가

── 왜 생겼나 (DECISIONS §310-2) ────────────────────────────────
2026-09-29. 배치 L 을 세 PR(#235 · #236 · #237)로 머지했는데 **셋 다
`gh pr merge --admin` 이었고, PR 을 만든 지 3초 뒤였다.** CI 는 시작도 못 했다.

나중에 보니 `contract` 가 빨갰다. 사유는 `tools/pr_body_check.py` — PR 본문이
템플릿의 「리뷰어가 볼 곳」을 안 채웠다는 것이었다. **관문은 있었다.** 2026-08-27
에 바로 그 일을 하려고 지어졌고, 머리말에 이렇게 적혀 있다 —

    승인이 도장이 되는 것을 규율로 막을 수 없다. 형식으로 막는다.

★ 그 형식을 `--admin` 하나가 껐다. 이 저장소가 `bypass` 를 두는 사유는 단독
  개발자가 **승인 1명**을 못 채우기 때문이고(MASTER §12-1c), 그것은 사람이
  없어서 못 채우는 요건이다. **상태 검사는 혼자서도 돈다.** 둘을 한 깃발로
  끄면, 사람을 대신하려고 만든 기계까지 같이 꺼진다.

★ 배운 것 — **우회 권한은 무엇을 우회했는지까지 기록돼야 우회다.** 안 그러면
  「승인이 없어서 눌렀다」와 「빨간불이라 눌렀다」가 같은 흔적을 남긴다.

── 무엇을 보는가 ───────────────────────────────────────────────
머지 커밋마다 **그 PR 의 머리 커밋이 어떤 상태였는지**를 묻는다. 셋으로 가른다 —

    SUCCESS   초록에서 머지했다                        정상
    FAILURE   **빨간불 위에서 머지했다**               빨간불
    (없음)    검사가 하나도 안 돌고 머지했다           빨간불 — 3초 머지가 이 꼴이다

IN    `gh api` (GitHub GraphQL · 러너 토큰)
OUT   표준출력
PARAM `--limit` 볼 머지 건수 (기본 20)
밖    **왜 빨갰는지는 안 본다.** 그것은 그 검사 소관이다 — 여기는 「빨간 채로
      넘어갔는가」만 든다.
      **승인 요건을 우회한 것은 안 든다.** 단독 개발자의 선언된 예외다
      (MASTER §12-1c). 이 도구가 무는 것은 **상태 검사**를 우회한 경우뿐이다.
      **`gh` 와 토큰이 없으면 못 돈다.** 그래서 **CI 전용**이다 — 러너에는 늘
      있고, 이 물음은 원격 저장소에만 답이 있다. 로컬에서 건너뛰는 것이
      아니라 **로컬에는 물음이 성립하지 않는다.**
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess

#: 초록으로 받아 주는 상태. `EXPECTED` 는 「검사가 걸려는 있는데 아직」이라
#: 머지 시점에는 빨강과 같다 — 기다리지 않고 누른 것이다.
OK_STATES = ("SUCCESS",)

QUERY = """
query($owner:String!, $name:String!, $n:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequests(states:MERGED, first:$n, orderBy:{field:UPDATED_AT, direction:DESC}) {
      nodes {
        number title mergedAt
        commits(last:1) { nodes { commit {
          statusCheckRollup { state }
        } } }
      }
    }
  }
}
"""


def _repo() -> tuple[str, str] | None:
    """`owner/name`. 원격이 없으면 None."""
    if not shutil.which("gh"):
        return None
    r = subprocess.run(["gh", "repo", "view", "--json", "owner,name"],  # noqa: S607 — PATH 의 gh 를 쓴다. 러너 표준이다
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return None
    d = json.loads(r.stdout)
    return d["owner"]["login"], d["name"]


def fetch(owner: str, name: str, n: int) -> list[dict]:
    r = subprocess.run(  # noqa: S607 — 위와 같다
        ["gh", "api", "graphql", "-f", f"query={QUERY}",
         "-F", f"owner={owner}", "-F", f"name={name}", "-F", f"n={n}"],
        capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "gh api 가 실패했다")
    return json.loads(r.stdout)["data"]["repository"]["pullRequests"]["nodes"]


def judge(nodes: list[dict]) -> tuple[list[str], int]:
    """(빨간불 사유들, 초록으로 머지된 건수)."""
    bad, ok = [], 0
    for pr in nodes:
        c = pr["commits"]["nodes"]
        roll = (c[0]["commit"].get("statusCheckRollup") or {}) if c else {}
        state = roll.get("state")
        if state in OK_STATES:
            ok += 1
        elif state is None:
            bad.append(f"#{pr['number']} {pr['title'][:56]}\n"
                       "       **검사가 하나도 안 돌고 머지됐다** — 만들자마자 눌렀다는 뜻이다")
        else:
            bad.append(f"#{pr['number']} {pr['title'][:56]}\n"
                       f"       **{state} 인 채로 머지됐다** — 우회가 상태 검사까지 껐다")
    return bad, ok


def selftest() -> int:
    """★ 판정기가 셋을 실제로 가르는가. 원격 없이 돈다."""
    fails = []
    def node(n, st):
        return {"number": n, "title": "t", "mergedAt": "",
                "commits": {"nodes": [{"commit": {"statusCheckRollup":
                                                  ({"state": st} if st else None)}}]}}

    bad, ok = judge([node(1, "SUCCESS")])
    if bad or ok != 1:
        fails.append("초록을 초록이라 안 한다")

    bad, ok = judge([node(2, "FAILURE")])
    if not bad or ok:
        fails.append("**빨간불 머지를 통과시킨다** — 이 도구의 존재 이유가 그것이다")

    bad, _ = judge([node(3, None)])
    if not bad:
        fails.append("검사가 안 돈 머지를 통과시킨다 — 3초 머지가 이 꼴이다")

    bad, _ = judge([node(4, "PENDING")])
    if not bad:
        fails.append("PENDING 을 초록으로 본다 — 기다리지 않고 누른 것이다")

    bad, _ = judge([{"number": 5, "title": "t", "mergedAt": "", "commits": {"nodes": []}}])
    if not bad:
        fails.append("커밋이 없는 PR 을 통과시킨다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 5")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="빨간불 위에서 머지된 PR 이 있는가")
    ap.add_argument("--limit", type=int, default=20, help="볼 머지 건수")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    who = _repo()
    if who is None:
        # ★ 건너뛰는 것이 아니다. **로컬에는 이 물음의 답이 없다** — 상태는
        #   원격에만 산다. CI 에서 이 자리가 나오면 그것은 결함이다.
        print("gh 가 없거나 원격을 못 읽는다 — 이 물음은 원격에만 답이 있다")
        print("  ★ CI 에서 이 줄이 보이면 러너 토큰이 빠진 것이다")
        return 0 if not os.environ.get("CI") else 1

    nodes = fetch(*who, a.limit)
    bad, ok = judge(nodes)
    print(f"머지 {len(nodes)}건 · 초록에서 머지 {ok} · 빨간 채로 머지 {len(bad)}")
    if bad:
        print("\n✗ 우회가 상태 검사를 껐다")
        for b in bad:
            print(f"   {b}")
        print("\n  `--admin` 은 **승인 1명**을 못 채우는 단독 개발자용이다(MASTER §12-1c).")
        print("  상태 검사는 혼자서도 돈다 — 머지 전에 `gh pr checks --watch` 로 끝까지 본다.")
        return 1
    print("✓ 전부 초록에서 머지됐다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
