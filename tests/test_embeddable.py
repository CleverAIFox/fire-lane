#!/usr/bin/env python3
"""
test_embeddable.py — 산출물이 **출동 패드에 끼워질 수 있는가.**  (PLAN §1 #28 · §273-8)

── 왜 생겼나 ──────────────────────────────────────────────────
#28 은 「독립 앱인가 기존 출동 패드의 부가기능인가」였다. 회의록 `P-60` 에서
현장은 **부가기능**을 선호한다고 답했고, 2026-09-27 에 **둘 다 되게** 로 정했다 —
지금 산출은 정적 파일이라 어느 쪽이든 인터페이스가 같고, 한쪽으로 못 박으면
화면 설계서를 두 벌 짜거나 나중에 다시 짠다.

★ 그 결정은 **이미 참이었다.** 프레임 차단 헤더가 0건이고 `main.tsx` 가
  `?view=` 로 화면을 고른다. 없던 것은 구현이 아니라 **선언과 강제자**다.
  선언이 없으면 내일 누가 `X-Frame-Options: DENY` 한 줄을 넣고, 그것은
  **아무 검사도 안 울린다** — 끼우려는 날에야 안다.

★ 여기가 재는 것은 「끼웠을 때 예쁜가」가 아니다. **끼울 수 없게 만드는 변경이
  들어왔는가** 하나다. 그 성질은 헤더 · 태그 · 진입점 셋으로 다 잡힌다.

IN    web/** · .github/workflows/**
OUT   없음 (검사)
밖    **끼운 화면이 쓸 만한가는 안 본다** — 패드 화면 크기 · 터치 표적은 화면
      설계서 소관이고 그것은 아직 없다. **실제 임베드도 안 해 본다** — 브라우저가
      필요하고, 그것은 `web/navi/test` 의 vitest 가 아니라 별도 축이다.
      그리고 **정적인가만 본다** — 서버가 필요해지는 변경(API 호출 · SSR)은
      `tools/treecheck.py` 와 배포 워크플로가 든다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

#: 이것이 들어오면 `<iframe>` 안에서 안 뜬다. 값은 안 본다 — 있는 것 자체가 결함이다.
BLOCKERS = ("X-Frame-Options", "frame-ancestors")

#: 임베드와 무관하게 이 낱말이 나올 수 있는 자리. **사유와 함께** 적는다.
ALLOW = {
    "docs": "문서가 결정을 설명하며 낱말을 인용할 수 있다",
}


def _files() -> list[Path]:
    out = []
    for p in (*WEB.rglob("*"), *(ROOT / ".github").rglob("*")):
        if not p.is_file() or "node_modules" in p.parts or ".vite" in p.parts:
            continue
        if p.suffix.lower() in (".html", ".yml", ".yaml", ".ts", ".tsx", ".js",
                                ".json", ".toml", ".conf"):
            out.append(p)
    return out


def test_nothing_blocks_being_put_in_a_frame():
    """★ 이 시험이 이 파일의 본체다. 한 줄이면 부가기능 안이 죽는다."""
    bad = []
    for p in _files():
        if any(a in p.parts for a in ALLOW):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        for b in BLOCKERS:
            if b.lower() in t.lower():
                bad.append(f"{p.relative_to(ROOT)} 가 `{b}` 를 든다")
    assert not bad, (
        "출동 패드에 끼울 수 없게 만드는 것이 들어왔다(PLAN §1 #28 — 둘 다 되게).\n"
        "  정말 필요하면 이 시험의 `ALLOW` 에 **사유와 함께** 적어라.\n  "
        + "\n  ".join(bad))


def test_the_view_is_chosen_by_a_query_parameter_not_by_the_path():
    """끼우는 쪽은 주소 하나만 준다. 경로로 화면을 고르면 그 주소를 못 만든다."""
    src = (WEB / "navi" / "src" / "main.tsx").read_text(encoding="utf-8")
    assert 'get("view")' in src, "`?view=` 로 화면을 고르지 않는다 — 임베드 주소를 못 만든다"
    # ★ 주석은 걷는다. 그 파일은 **경로로 판정하지 않는 이유**를 주석으로 적고 있고,
    #   그것까지 결함으로 세면 설명을 지워야 통과하는 검사가 된다.
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = "\n".join(l for l in code.splitlines() if not l.lstrip().startswith(("//", "*")))
    assert "location.pathname" not in code, (
        "진입점이 경로로 화면을 고른다 — 끼우는 쪽의 경로는 우리 것이 아니다")


def test_every_screen_is_a_static_file():
    """정적 파일이라는 것이 「둘 다 되게」의 근거다. 서버가 끼면 그 근거가 사라진다."""
    idx = [p for p in (WEB.glob("*.html"), (WEB / "navi").glob("*.html")) for p in p]
    assert idx, "화면 진입점이 하나도 없다"
    for p in idx:
        t = p.read_text(encoding="utf-8")
        assert not re.search(r"<\?php|{%\s*\w+|<%[=-]", t), \
            f"{p.relative_to(ROOT)} 가 서버 템플릿이다 — 정적 파일이 아니다"


def test_the_decision_is_written_where_values_live():
    """★ 결정이 시험에만 있으면 사람이 못 읽는다. MASTER 가 값을 든다."""
    m = (ROOT / "docs" / "MASTER.md").read_text(encoding="utf-8")
    assert "임베드" in m, (
        "MASTER 에 산출물 형태 결정이 없다 — 검사만 있고 선언이 없으면 "
        "다음 사람이 왜 이런지 모른다(PLAN §1 #28)")


# ── 로컬과 배포가 같은 주소를 쓰는가 (§273-12) ─────────────────
SERVE = ROOT / "tools" / "serve.py"
BUILD = ROOT / ".github" / "actions" / "build-navi" / "action.yml"


def test_the_local_server_seats_ops_at_the_root_like_the_deploy_does():
    """★ 2026-09-27 실측. 배포는 `/` 가 관제인데 로컬은 `navi/?view=ops` 였다.

    §258 이 「쿼리스트링은 주소가 아니다」라며 배포만 옮겼고 이 도구는 안 따라왔다.
    **같은 화면이 두 주소를 갖는다.** 그러면 눈으로 보는 사람이 배포와 다른 것을
    보고 판단한다 — 실제로 그 화면을 놓고 「이게 뭐냐」가 나왔다.

    재는 것은 「똑같이 생겼는가」가 아니라 **둘 다 루트에 관제를 앉히는가**다.
    """
    serve = SERVE.read_text(encoding="utf-8")
    build = BUILD.read_text(encoding="utf-8")
    tag = '__FL_VIEW="ops"'
    assert tag in build, "배포가 루트에 관제를 안 앉힌다 — 이 시험의 전제가 깨졌다"
    assert tag in serve, (
        "로컬 서버가 루트에 관제를 안 앉힌다 — 배포는 앉힌다.\n"
        "  같은 화면이 두 주소를 가지면 눈으로 보는 사람이 배포와 다른 것을 본다")


def test_the_local_server_does_not_advertise_the_retired_query_address():
    """안내문이 낡으면 사람이 그 주소로 간다. 화면보다 안내가 먼저 낡는다."""
    printed = [ln for ln in SERVE.read_text(encoding="utf-8").splitlines()
               if "print(" in ln and "localhost" in ln]
    assert printed, "서버가 주소를 하나도 안 찍는다"
    bad = [ln.strip() for ln in printed if "view=ops" in ln]
    assert not bad, (
        "폐기된 쿼리 주소를 아직 안내한다(§258 — 쿼리스트링은 주소가 아니다).\n  "
        + "\n  ".join(bad))
    assert any("/navi/" in ln for ln in printed), "내비 주소를 안 찍는다"
