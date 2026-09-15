"""
hashing.py — 파일 sha256. **한 곳에서만 잰다.**

★ 2026-09-13. 같은 구현이 10곳이었다. `dupcheck` 가 ×7(44노드) ·
  ×3(51노드) 두 군으로 셌다. 이름만 달랐다 — `sha256` · `sha` · `_sha`,
  게다가 `doctor` 는 `_sha256 = _sha` 별칭까지 달고 있었다.

★ 같은 것을 두 이름으로 부르면 사람도 도구도 한 번 더 속는다. 이 저장소가
  232번 당한 형태다.

★ 청크 크기를 바꿔도 결과가 같아야 한다 — 그래서 인자로 두되 기본값을
  한 곳에 둔다. 사본이던 시절에는 한 곳만 고치면 나머지 아홉이 안 따라왔다.

IN    파일 경로
OUT   64자 소문자 16진수
"""
from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK = 1 << 20


def sha256(p: Path, chunk: int = CHUNK) -> str:
    """파일 전체의 sha256. 큰 파일을 통째로 안 읽는다."""
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()
