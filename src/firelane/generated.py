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

IN    없음
OUT   없음 (상수)
PARAM REGISTRY
"""
from __future__ import annotations

import argparse
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
)

ROLES: frozenset[str] = frozenset(r for g in REGISTRY for r in g.roles)


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
