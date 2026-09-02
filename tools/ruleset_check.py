#!/usr/bin/env python3
"""
ruleset_check.py — GitHub 룰셋 실물이 문서의 방침과 같은가.

    uv run python tools/ruleset_check.py

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-31. `MASTER §12-1` 이 스스로 이렇게 적고 있었다 —
*"강제자가 없다. 룰셋은 저장소 밖이라 코드가 못 본다. 이 표는 사람이
손으로 적는다."*

그리고 그날 실제로 어긋났다. 세션 인수인계 문서가 `part/gis` 에 승인 1이
걸려 있다고 적었고 그것을 전제로 대책을 논했는데, **실물은 0이었다.**
룰셋에 그 항목이 애초에 없었다. 같은 문서가 `PR #79` 를 "승인 대기 중"
이라고 적었으나 이미 머지된 상태였다.

★ 더 나쁜 것은 `bypass_actors` 였다. 한 사람이 PR 요구를 우회할 수 있었고
  **그 사실이 어느 문서에도 없었다.** 사람이 손으로 적는 표는 자기가
  모르는 항목을 적지 못한다.

`MASTER §14-6` 은 *"일회성 스크립트를 만들지 않는다. 진단 도구는 저장소에
있다"* 고 적는다. 그날 `/tmp/rulesets.sh` 를 다섯 번 만들어 썼다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 룰셋 셋이 존재하고 active 인가
    2. 대상 ref · 승인 수 · Code Owners · 머지 방식 · 필수 검사
    3. bypass_actors 가 비어 있는가            ← 예외는 문서 밖에서 자란다

★ 이 도구는 **CI 에 붙이지 않는다.** 룰셋 읽기에는 관리자 토큰이 필요하고,
  그 토큰을 CI 시크릿에 두면 룰셋을 지킬 물건이 룰셋을 바꿀 수 있게 된다.
  사람이 주기적으로 친다. 절차는 workflow §7 에 적는다.

IN    gh api repos/:owner/:repo/rulesets  ·  아래 EXPECT
OUT   없음 (검사). 어긋나면 종료코드 1
PARAM 없음
"""
from __future__ import annotations

import json
import subprocess
import sys

REPO = "woongtopia/fire-lane"

# docs/MASTER.md §12-1 의 표와 같아야 한다.
# 여기를 고치면 그 둘도 같이 고친다.
# ★ bypass 는 개인이 아니라 역할에 준다. admin 이 늘면 우회 가능자도
#   는다(DECISIONS 80). 2026-09-01 실측에서 팀 전원이 admin 이었고
#   MASTER §12-1 에 그 선언이 없었다. 실물이 이 목록과 다르면 운다.
ADMINS = ["AIMasterFox", "diyon13", "gayeoniii", "marscoolcat", "wlsdnr052475"]

EXPECT = {
    "release": {
        "ref": "refs/heads/main", "approvals": 1, "codeowners": True,
        "merge": ["merge"], "checks": ["contract-shared", "contract-strict"],
    },
    "trunk": {
        "ref": "refs/heads/dev", "approvals": 0, "codeowners": False,
        "merge": ["merge"], "checks": ["contract-shared"],
    },
    # ★ 2026-08-31 정정. 처음엔 `["squash"]` 단독으로 걸었다. **해보고 틀린 것을
    #   알았다** — `part` 가 `dev` 를 받는 PR 자체가 squash 로 막힌다.
    #   그것을 squash 하면 `dev` 커밋이 조상에서 사라져 다음 통합이 통째로
    #   충돌한다(§12-2, 여섯 번 겪음).
    #
    #   ★ 예외가 생겼지만 **취향이 아니라 PR 종류로 결정된다.**
    #       feat → part   작업        squash
    #       dev  → part   일일 동기화  merge commit
    #     "이 PR 이 base 밖 커밋을 흡수했나" 는 사실 판단이고,
    #     `base 와의 간극` 스텝이 이미 그것을 재고 있다.
    "part": {
        "ref": "refs/heads/part/**", "approvals": 0, "codeowners": False,
        "merge": ["squash", "merge"], "checks": ["contract-shared"],
    },
}

# 브랜치를 지우거나 히스토리를 덮어쓰는 것은 셋 다 막는다.
REQUIRED_RULES = {"deletion", "non_fast_forward", "pull_request",
                  "required_status_checks"}

# ★ 2026-09-02. 룰셋만 보고 **저장소 설정**은 안 봤다. 그래서
#   `delete_branch_on_merge: true` 를 아무도 못 봤고, 그것이 4계층 모델과
#   충돌해 영구 브랜치가 두 번 사라졌다(`main` · `part/gis`).
#
#   ★ 룰셋에는 `deletion` 이 **있었다.** bypass_actors 가 그것도 뚫었다 —
#     머지를 admin 이 하므로 자동 삭제가 admin 권한으로 실행된다.
#     규칙이 있어도 예외가 있으면 없는 것과 같다(DECISIONS §79 · §101).
REPO_SETTINGS = {
    # 켜면 **머지된 head 브랜치를 전부** 지운다. head 를 가리지 않는다 —
    # `part → dev` 는 head 가 `part/gis` 이고 `main → dev` 는 `main` 이다.
    # feat 정리는 .github/workflows/branch_cleanup.yml 이 대신한다.
    "delete_branch_on_merge": False,
    # 보호 브랜치는 rebase 로 되돌리지 않는다(§12-2). merge · squash 만.
    "allow_rebase_merge": False,
}

# 수명이 영구인 브랜치. 사라지면 그 사실을 아무도 안 알려준다.
PERMANENT = ("main", "dev", "part/gis", "part/cv", "part/infra")


def _gh(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode:
        print("★ gh api 실패 — 로그인·권한을 확인하라")
        print("  " + (r.stderr or "").strip()[:200])
        sys.exit(2)
    return json.loads(r.stdout)


def main() -> int:
    try:
        listing = _gh(f"repos/{REPO}/rulesets")
    except FileNotFoundError:
        print("★ gh 가 없다. https://cli.github.com")
        return 2

    got = {}
    for row in listing:
        got[row["name"]] = _gh(f"repos/{REPO}/rulesets/{row['id']}")

    bad: list[str] = []

    # ── 저장소 설정 ──
    repo = _gh(f"repos/{REPO}")
    for k, want in REPO_SETTINGS.items():
        cur = repo.get(k)
        if cur != want:
            bad.append(
                f"저장소 설정 {k}: {cur} != {want}\n"
                f"      gh api -X PATCH repos/{REPO} -f {k}={str(want).lower()}")

    # ── 영구 브랜치가 실재하는가 ──
    # ★ 사라져도 아무도 안 운다. 2026-09-02 에 `main` 과 `part/gis` 가
    #   차례로 사라졌고, 사라진 동안 **룰셋이 안 붙어 직푸시가 나갔다.**
    try:
        refs = {b["name"] for b in _gh(f"repos/{REPO}/branches?per_page=100")}
    except Exception as e:                      # noqa: BLE001
        refs = None
        print(f"  (브랜치 목록을 못 읽었다: {e})")
    if refs is not None:
        gone = [b for b in PERMANENT if b not in refs]
        if gone:
            bad.append(
                f"영구 브랜치가 없다: {gone}\n"
                "      ★ 수명이 영구인 브랜치다(§12-1). 머지 자동 삭제나\n"
                "        실수로 지워진 것이며, 없는 동안은 룰셋도 안 붙는다.\n"
                "        git push origin <복구커밋>:refs/heads/<이름>")

    missing = sorted(set(EXPECT) - set(got))
    extra = sorted(set(got) - set(EXPECT))
    if missing:
        bad.append(f"룰셋이 없다: {missing}")
    if extra:
        bad.append(f"문서에 없는 룰셋이 있다: {extra} — §4 표에 적거나 지워라")

    for name, want in EXPECT.items():
        d = got.get(name)
        if not d:
            continue
        if d.get("enforcement") != "active":
            bad.append(f"{name}: enforcement={d.get('enforcement')} — active 여야 한다")

        refs = (d.get("conditions", {}).get("ref_name", {}) or {}).get("include") or []
        if refs != [want["ref"]]:
            bad.append(f"{name}: 대상 {refs} != [{want['ref']}]")

        types = {r["type"] for r in d.get("rules", [])}
        for miss in sorted(REQUIRED_RULES - types):
            bad.append(f"{name}: 규칙 없음 — {miss}")

        pr = next((r.get("parameters") or {} for r in d.get("rules", [])
                   if r["type"] == "pull_request"), {})
        if pr:
            n = pr.get("required_approving_review_count")
            if n != want["approvals"]:
                bad.append(f"{name}: 승인 {n} != {want['approvals']}")
            co = bool(pr.get("require_code_owner_review"))
            if co != want["codeowners"]:
                bad.append(f"{name}: Code Owners {co} != {want['codeowners']}")
            mm = pr.get("allowed_merge_methods") or []
            if sorted(mm) != sorted(want["merge"]):
                bad.append(f"{name}: 머지 방식 {mm} != {want['merge']}"
                           "\n      ★ 고를 여지가 있으면 사람이 틀린다(§12-2)")

        sc = next((r.get("parameters") or {} for r in d.get("rules", [])
                   if r["type"] == "required_status_checks"), {})
        ctx = sorted(c["context"] for c in sc.get("required_status_checks", []))
        if ctx != sorted(want["checks"]):
            bad.append(f"{name}: 필수 검사 {ctx} != {sorted(want['checks'])}"
                       "\n      ★ 승인을 낮춰도 검사는 낮추지 않는다")

        by = d.get("bypass_actors") or []
        if by:
            who = [f"{a.get('actor_type')}:{a.get('actor_id')}"
                   f"({a.get('bypass_mode')})" for a in by]
            bad.append(f"{name}: bypass actor {who}"
                       "\n      ★ 예외는 문서 밖에서 자란다. 08-31 에 한 사람이"
                       "\n        PR 요구를 우회할 수 있었고 아무 문서에도 없었다")

    admins = sorted(c["login"] for c in _gh(f"repos/{REPO}/collaborators")
                    if (c.get("permissions") or {}).get("admin"))
    if admins != sorted(ADMINS):
        bad.append(f"admin 명단 {admins} != {sorted(ADMINS)}"
                   "\n      ★ admin 이 늘면 bypass 대상도 는다. 개인 지정은"
                   "\n        룰셋이 지원하지 않는다(DECISIONS 80)")

    if bad:
        print("★ 룰셋 실물이 방침과 다르다.\n")
        for b in bad:
            print(f"  ✗ {b}")
        print("\n  정본 — docs/MASTER.md §12-1")
        print("  한시로 낮춘 것이면 MASTER §12-1 에 **되돌릴 날과 함께** 적어라.")
        print("  적어두지 않은 완화는 영구가 된다(DECISIONS §76).")
        return 1

    for name, want in EXPECT.items():
        print(f"  {name:<8} {want['ref']:<22} 승인={want['approvals']}"
              f" CO={want['codeowners']} 머지={want['merge'][0]}"
              f" 검사={len(want['checks'])}종")
    print("\n룰셋 OK — 실물이 §4 표와 같다. bypass 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
