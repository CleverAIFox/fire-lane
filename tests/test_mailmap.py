"""`.mailmap` 이 본인 커밋의 표시를 하나로 모은다.  (감사 4-4 · Zm22)

IN    .mailmap · git
OUT   없음 (검사)
PARAM 없음
밖    **이력을 안 바꾼다** — `.mailmap` 은 로컬 표시만 바꾼다. GitHub 화면과 커밋 해시는 이 파일과 무관하다.
      팀원 커밋도 합치지 않는다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANON = "CleverAIFox <cleveraifox@gmail.com>"
VARIANTS = ("CleverFox <cleveraifox@gmail.com>", "Fox <AIMasterFox@gmail.com>", "Fox <aimasterfox@gmail.com>",
            "CleverAIFox <CleverAIFox@gmail.com>", "fire-lane-init <team@fire-lane.local>")
OTHERS = ("someone <someone@example.org>", "dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>")


def _map(who: str) -> str:
    return subprocess.run(["git", "check-mailmap", who], cwd=ROOT, capture_output=True, text=True, check=True, timeout=30).stdout.strip()


def test_every_variant_of_the_author_maps_to_one_identity() -> None:
    assert not [v for v in VARIANTS if _map(v) != CANON], "본인 변형이 하나로 안 모인다"


def test_other_people_are_not_merged() -> None:
    assert all(_map(o) == o for o in OTHERS), "남의 커밋을 합쳤다"
