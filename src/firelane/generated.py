#!/usr/bin/env python3
"""
generated.py — 생성물 경로 등록부. **역할을 든다.** (PLAN §13 W3-13)

    from firelane.generated import for_role, prefixes
    for_role("fresh")       → ("web/data", "data/processed")
    prefixes("encoding")    → ("web/data/", "data/processed/", ...)   startswith 용

    uv run python -m firelane.generated --role fresh [--prefix]      셸용

★ 왜 생겼나 (2026-09-22)
  생성물 경로 목록이 아홉 곳에 따로 살았다 — encoding_check · dms(둘) ·
  freshcheck(verify.sh 「커밋된 web/data 가 최신인가」) · commit_policy ·
  tidy · test_web_ownership · test_ledger_outputs · (.pre-commit-config.yaml).
  「최신인가」 단계가 `segments.geojson` 한 파일만 들어 `_manifest.json` 과
  `seg_uid_map.csv` 를 놓쳤다(DECISIONS §192). 목록이 여럿이면 하나만 고친다.

★ 평평한 튜플 하나로 합치지 않는다. **목록이 서로 다른 것이 정상이다** —
  각자 다른 질문을 한다. 그래서 경로마다 **역할**을 달고, 호출부는 자기
  질문의 역할만 뽑는다. 경로를 더할 때는 「어느 질문에 답하는가」를 정한다.

역할 (질문)
  encoding     인코딩·개행 검사에서 뺀다 — 바이트 sha 로 계보를 대조한다
               (tools/encoding_check.py · .pre-commit-config.yaml exclude)
  seal         봉인 로그 신선도(작업나무 더러움)에서 뺀다 (tools/dms.py GENERATED)
  seal-dirty   봉인할 때 미커밋이어도 된다 (tools/dms.py SEAL_MAY_BE_DIRTY)
  fresh        재실행 뒤 커밋본과 같아야 한다 (tools/freshcheck.py --paths)
  committed    data/processed 중 커밋하는 UI 입력 (tools/commit_policy.py)
  never-delete 정리 도구가 절대 안 지운다 (tools/tidy.py NEVER 의 생성물 몫)
  web-out      파이프라인이 쓰는 web 디렉터리 (tests/test_web_ownership.py)
  ledger-skip  대장 outputs 등재 검사에서 뺀다 (tests/test_ledger_outputs.py)

★ 2026-09-22 (DECISIONS §218-6) 가족표 FAMILIES 를 더했다(계급 가드 5).
  역할은 「어느 검사가 이 경로를 빼는가」를 묻고, 가족은 「누가 만들고 · 무엇이
  재현을 확인하고 · 누가 읽는가」를 묻는다. 커밋된 생성물마다 셋이 다 있어야
  한다 — 셋 중 하나가 없는 생성물은 낡아도 아무도 모른다. `GEN_ROOTS` 아래
  추적 파일은 전부 정확히 한 가족에 든다(tests/test_generated_families.py).

IN    없음
OUT   없음 (상수)
PARAM REGISTRY · FAMILIES · GEN_ROOTS
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Gen:
    path: str                 # 저장소 상대 · 끝 `/` 없음
    kind: str                 # "dir" | "file"
    roles: frozenset[str]


def _g(path: str, kind: str, *roles: str) -> Gen:
    return Gen(path, kind, frozenset(roles))


# ★ 순서가 곧 for_role 의 순서다(freshcheck 의 출력 순서가 여기에 기댄다).
REGISTRY: tuple[Gen, ...] = (
    _g("web/data", "dir",
       "encoding", "seal", "fresh", "never-delete", "web-out", "ledger-skip"),
    _g("data/processed", "dir", "encoding", "seal", "fresh"),
    _g("data/dms", "dir", "seal", "seal-dirty"),
    _g("data/golden", "dir", "encoding", "never-delete"),
    _g("data/baseline", "dir", "encoding", "never-delete"),
    _g("data/processed/segments.geojson", "file", "committed", "never-delete"),
    _g("data/processed/segments.schema.json", "file", "committed", "never-delete"),
    _g("data/processed/_manifest.json", "file",
       "committed", "never-delete", "seal-dirty"),
    _g("data/processed/seg_uid_map.csv", "file", "committed", "never-delete"),
    # ★ 2026-09-23 (PLAN §1 #44 닫힘). `data/processed/_manifest.json` 만 「봉인 때 더러워도
    #   된다」 로 두고 **짝인 `web/data/_manifest.json` 을 빠뜨렸다.** 파이프라인은 둘을 같이
    #   쓰고 커밋 시점도 같다 — 하나만 면제하면 봉인이 매번 나머지 하나로 거부한다.
    #   2026-09-22 에 실제로 배치 도구 1단계가 이 파일로 멈췄다.
    _g("web/data/_manifest.json", "file", "never-delete", "seal-dirty"),
)

ROLES: frozenset[str] = frozenset(r for g in REGISTRY for r in g.roles)


@dataclass(frozen=True)
class Family:
    """커밋된 생성물 한 가족 — (만드는 것, 재현 확인, 읽는 것).

    globs      저장소 상대 패턴. `*` 는 `/` 를 안 넘고 `**` 는 넘는다
    generator  `firelane.모듈` 또는 `tools/파일` — 이 가족을 쓰는 코드
    checks     재현·일치를 확인하는 명령. `uv run python <도구> [인자]` 꼴
    consumers  이 가족을 읽는 파일·디렉터리
    """
    name: str
    globs: tuple[str, ...]
    generator: str
    checks: tuple[str, ...]
    consumers: tuple[str, ...]


# ★ 가족표가 보는 루트. 이 아래 추적 파일은 전부 한 가족에 들어야 한다.
GEN_ROOTS: tuple[str, ...] = (
    "web/data", "data/processed", "data/dms", "data/golden", "data/baseline",
    "docs/figures", "web/workflow.html", "docs/proposal.docx",
)

FAMILIES: tuple[Family, ...] = (
    Family("web-data", ("web/data/*",),
           # publish_web 이 publish_navi · publish_fleet · publish_basemap ·
           # publish_context 를 불러 **열일곱** 파일을 낸다(publish_web 머리말 OUT).
           # ★ 2026-09-24. 여기 「스물세」라 적혀 있었다 — 머리말을 근거로 인용하면서
           #   머리말과 다른 수를 말했다. 실물 `web/data/*` 는 18이고 차이 하나는
           #   `view.json` 이다. 그것은 terrain·ortho 가 만들고 publish 가 **덧쓴다**
           #   (Step 의 writes 가 아니라 mutates). 발행 수와 실물 수는 다르다.
           "firelane.publish_web",
           ("uv run python tools/freshcheck.py",
            "uv run python tools/web_manifest.py --check"),
           ("web/navi/src", "tools/stage_pages.py")),
    Family("web-ortho", ("web/data/ortho/**",), "firelane.ortho",
           ("uv run python tools/web_manifest.py --check",),
           ("web/navi/src/components/OpsMap.tsx",)),
    Family("web-terrain", ("web/data/terrain/**",), "firelane.terrain",
           ("uv run python tools/web_manifest.py --check",),
           ("web/navi/src/components/layers.ts",)),
    Family("processed-committed", ("data/processed/*",),
           # 커밋 예외 넷만 추적된다(sources.yaml committed_exceptions · 역할 committed)
           "firelane.pipeline",
           ("uv run python tools/freshcheck.py", "uv run python tools/golden.py check"),
           ("src/firelane/publish_web.py", "tools/golden.py", "tools/baseline.py")),
    Family("golden", ("data/golden/*",), "tools/golden.py",
           ("uv run python tools/golden.py check",),
           # ★ 2026-09-24. `docnum_check` 가 여기 있었는데 그 도구는 golden 을
           #   **주석으로만** 든다 — 읽는 것은 `data/processed/segments.geojson` 이다.
           #   실제 독자 둘(`docx_fix.py` · `pipeline.py`)이 빠져 있었다.
           ("tools/render_figures.py", "tools/docx_check.py", "tools/docx_fix.py",
            "tools/proposal_pdf.py", "tools/release_brief.py",
            "src/firelane/pipeline.py")),
    Family("baseline", ("data/baseline/**",),
           # ★ 봉인 사본이다 — 원본이 교체돼 재생성할 수 없다(baseline.py 머리말).
           #   재현 검사가 성립하지 않고 `list` 가 meta.json 을 읽어 집계를 보일 뿐이다.
           "tools/baseline.py",
           ("uv run python tools/baseline.py list",),
           ("tools/baseline.py",)),
    Family("dms-seal", ("data/dms/SEAL.json", "data/dms/RED.txt"), "tools/dms.py",
           ("uv run python tools/dms.py ancestry", "uv run python tools/dms.py delta"),
           ("tools/verify.sh",)),
    Family("dms-bookmark", ("data/dms/BOOKMARK.json",), "tools/dms.py",
           ("uv run python tools/dms.py delta",),
           ("tools/dms.py",)),
    Family("figures", ("docs/figures/*",), "tools/render_figures.py",
           ("uv run python tools/render_figures.py --check",),
           # 기획서에 그림을 넣는 것은 사람이다(render_figures 머리말)
           ("docs/proposal.docx", "tests/test_figure_text.py")),
    Family("workflow", ("web/workflow.html",), "tools/render_workflow.py",
           ("uv run python tools/render_workflow.py --check",),
           ("tools/stage_pages.py",)),
    Family("proposal-numbers", ("docs/proposal.docx",),
           # ★ 대외 제출본이라 생성물이 아니다. 판정 숫자만 docx_fix 가 제자리에서 고친다
           "tools/docx_fix.py",
           ("uv run python tools/docx_check.py",),
           ("web/proposal.html", "tools/stage_pages.py")),
)


def _glob_re(pat: str) -> re.Pattern[str]:
    out = ""
    for part in re.split(r"(\*\*|\*|\?)", pat):
        out += {"**": ".*", "*": "[^/]*", "?": "[^/]"}.get(part, re.escape(part))
    return re.compile(out + r"\Z")


def families_of(path: str) -> tuple[Family, ...]:
    """경로가 드는 가족. 정상이면 정확히 하나다."""
    return tuple(f for f in FAMILIES if any(_glob_re(g).match(path) for g in f.globs))


def entries(role: str) -> tuple[Gen, ...]:
    if role not in ROLES:
        raise KeyError(f"모르는 역할 {role!r} — {sorted(ROLES)}")
    return tuple(g for g in REGISTRY if role in g.roles)


def for_role(role: str) -> tuple[str, ...]:
    """역할의 경로. 끝 `/` 없음. 등록 순서."""
    return tuple(g.path for g in entries(role))


def prefixes(role: str) -> tuple[str, ...]:
    """`str.startswith` 에 바로 넣는 모양 — 디렉터리는 끝에 `/` 를 붙인다."""
    return tuple(g.path + "/" if g.kind == "dir" else g.path for g in entries(role))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="생성물 경로 등록부")
    ap.add_argument("--role", required=True, choices=sorted(ROLES))
    ap.add_argument("--prefix", action="store_true", help="디렉터리에 끝 / 를 붙인다")
    a = ap.parse_args(argv)
    print("\n".join(prefixes(a.role) if a.prefix else for_role(a.role)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
