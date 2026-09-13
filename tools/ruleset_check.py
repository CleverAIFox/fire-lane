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
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def _repo_slug() -> str:
    """`git remote` 에서 owner/name 을 읽는다. **저장소가 자기 이름의 정본이다.**

    ★ 2026-09-12 (B5). 종전에는 `"woongtopia/fire-lane"` 이 상수로 박혀 있었고,
      개인 계정으로 미러 이관한 뒤 `gh api` 가 404 를 냈다. 화면은
      "로그인·권한을 확인하라" 고 해서 원인을 엉뚱한 데서 찾게 만들었다.
      **룰셋 검사가 도는 척하고 아무것도 안 봤다.**

    ★ 새 값으로 바꾸기만 하면 다음 이관에서 똑같이 깨진다.
      remote 를 못 읽을 때만 상수로 떨어지고, **떨어졌다는 사실을 적는다** —
      모르는 것을 아는 척하지 않는다(HANDOFF 원칙 ⑥).
    """
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=ROOT, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ""
    if url:
        slug = url.removesuffix(".git")
        slug = slug.split(":")[-1] if slug.startswith("git@") else \
            "/".join(slug.split("/")[-2:])
        if slug.count("/") == 1 and all(slug.split("/")):
            return slug
    print("★ git remote 를 못 읽었다 — 아래 값으로 진행한다. 틀릴 수 있다.",
          file=sys.stderr)
    return FALLBACK_REPO


# remote 가 없을 때만 쓴다. 정본이 아니다.
FALLBACK_REPO = "CleverAIFox/fire-lane"
REPO = _repo_slug()

# docs/MASTER.md §12-1 의 표와 같아야 한다.
# 여기를 고치면 그 둘도 같이 고친다.
# ★ bypass 는 개인이 아니라 역할에 준다. admin 이 늘면 우회 가능자도
#   는다(DECISIONS 80). 2026-09-01 실측에서 팀 전원이 admin 이었고
#   MASTER §12-1 에 그 선언이 없었다. 실물이 이 목록과 다르면 운다.
# ★ 2026-09-03. AIMasterFox 이탈로 제거. bypass 는 개인이 아니라 역할에
#   주므로 admin 이 줄면 우회 가능자도 준다(MASTER §12-1a).
# ★ MASTER §12-1a 가 선언한 예외. 여기 없는 bypass 는 운다.
#   "RepositoryRole:5" 는 Repository admin 역할이다 — 개인이 아니라 역할에 준다.
BYPASS_DECLARED = {"RepositoryRole:5(always)"}

ADMINS = ["CleverAIFox"]  # 2026-09-12 개인 저장소 이관. 옛 팀 넷은 MASTER §12-1 이력에 남는다

EXPECT = {
    "release": {
        # ★ Code Owners 는 끈다. 켜면 릴리즈 PR 을 올리는 사람이 곧 포괄
        #   소유자라 자기 PR 을 자기가 승인 못 한다(DECISIONS §108).
        "ref": "refs/heads/main", "approvals": 1, "codeowners": False,
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


def _secret_gaps() -> list[str]:
    """워크플로가 부르는 `secrets.X` 중 **등록 안 된 것**을 돌려준다.

    ★ 2026-09-12 (B5). `pages.yml` 에 Secret 참조를 넣고 등록을 안 하면
      빈 문자열이 조용히 들어간다. 워크플로는 초록불이고 배포본만 깨진다.
      VWORLD_KEY 를 배선하면서 실제로 그 상태를 한 번 만들었다.

    ★ **값은 못 본다.** API 가 이름과 시각만 준다. 그래서 이 검사가
      보증하는 것은 "있다" 뿐이다. 값이 맞는지 · 만료됐는지는 사람 몫이다.

    ★ 반대 방향(등록됐는데 안 쓴다)은 일부러 안 본다. 다른 워크플로나
      수동 실행이 쓸 수 있어서 지우라고 할 근거가 없다.

    ★ `secrets.GITHUB_TOKEN` 은 GitHub 이 자동으로 준다. 등록 대상이 아니다.
    """
    want: dict[str, list[str]] = {}
    wf = ROOT / ".github/workflows"
    for p in sorted(wf.glob("*.yml")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            for m in re.finditer(r"secrets\.([A-Z_][A-Z0-9_]*)", code):
                name = m.group(1)
                if name == "GITHUB_TOKEN":
                    continue
                want.setdefault(name, []).append(f"{p.name}:{i}")

    if not want:
        # ★ 0건이 청결인지 죽음인지 가른다(HANDOFF 원칙 ④).
        return ["워크플로가 부르는 Secret 이 0건이다 — 프로브를 의심하라"
                "\n      ★ pages.yml 은 최소 MAPBOX_TOKEN 을 부른다"]

    try:
        have = {s["name"] for s in _gh(f"repos/{REPO}/actions/secrets")["secrets"]}
    except (KeyError, TypeError, SystemExit):
        return ["Secret 목록을 못 읽었다 — gh 권한(repo)이 필요하다"
                "\n      ★ 못 읽은 것을 '없다' 로 적지 않는다"]

    return [f"Secret 미등록: {n}   ← {', '.join(want[n])}"
            "\n      ★ 참조는 있는데 값이 없으면 **빈 문자열**이 들어간다."
            "\n        워크플로는 초록불이고 배포본만 깨진다."
            f"\n        gh secret set {n} --repo {REPO}"
            for n in sorted(set(want) - have)]


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
            # ★ 선언된 예외는 통과시킨다. MASTER §12-1a (2026-09-12).
            #   개인 저장소라 승인 1을 혼자 만족할 수 없다. 규칙을 낮추지
            #   않고 예외를 뒀다. **회수는 날짜가 아니라 조건이다** —
            #   협업자가 둘이 되면 아래에서 운다.
            if set(who) <= BYPASS_DECLARED:
                continue
            bad.append(f"{name}: bypass actor {who}"
                       "\n      ★ 예외는 문서 밖에서 자란다. 08-31 에 한 사람이"
                       "\n        PR 요구를 우회할 수 있었고 아무 문서에도 없었다")

    people = _gh(f"repos/{REPO}/collaborators")

    # ★ 회수 조건. §12-1a 가 "본인 외 협업자가 생기면 제거한다" 고 적었고
    #   여기가 그것을 **실제로 거는** 자리다. 문서만 적으면 잊는다 —
    #   `contract.yml` 죽은 게이트가 CI 에서 한 번도 안 돌았던 그 모양이다.
    if len(people) > 1 and BYPASS_DECLARED:
        bad.append(
            f"bypass 회수 조건이 찼다 — 협업자 {len(people)}명"
            "\n      ★ MASTER §12-1a 의 예외는 '본인 외 협업자가 생기면"
            "\n        제거한다' 는 조건부다. 지금이 그때다."
            "\n        룰셋 셋에서 bypass_actors 를 비우고 §12-1a 를 회수로 고쳐라")

    admins = sorted(c["login"] for c in people
                    if (c.get("permissions") or {}).get("admin"))
    if admins != sorted(ADMINS):
        bad.append(f"admin 명단 {admins} != {sorted(ADMINS)}"
                   "\n      ★ admin 이 늘면 bypass 대상도 는다. 개인 지정은"
                   "\n        룰셋이 지원하지 않는다(DECISIONS 80)")

    bad += _secret_gaps()

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
