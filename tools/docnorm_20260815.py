#!/usr/bin/env python3
"""
docnorm_20260815.py — 문서·주석의 사적 조어를 표준 용어로 바꾼다.

    uv run python tools/docnorm_20260815.py --check
    uv run python tools/docnorm_20260815.py

왜
    이 문서는 인수인계 문서이자 UI 담당의 작업 지시서다(MASTER §14-8).
    "손딕셔너리" "눈대중" "발목을 잡았다" 는 작성자에게만 뜻이 통한다.
    읽는 쪽이 사전을 물어봐야 하면 문서가 제 역할을 못 한다.

무엇을 바꾸나
    1. 사적 조어 → 표준 용어          전역 치환
    2. 발표 수사 → `발표 논거:` 표기   문장 단위 치환
       내용은 지운다는 뜻이 아니라, 기술 진술과 섞어 쓰지 않는다는 뜻이다.

무엇을 안 바꾸나
    비유가 값을 담고 있으면 남긴다. "회색으로 도망치지 않는다" 는 작업 원칙의
    이름 자체이고 대체어가 더 길다. 판단 기준은 "처음 읽는 사람이 사전 없이
    뜻을 맞힐 수 있는가" 하나다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 1. 사적 조어 → 표준 용어 (전역) ─────────────────────────────────
GLOBAL: list[tuple[str, str]] = [
    ("손딕셔너리", "하드코딩 매핑"),
    ("손나열", "하드코딩 목록"),
    ("손토글", "하드코딩 토글"),
    ("눈대중", "근거 미기재 임의값"),
    ("발목을 잡았다", "실행을 막았다"),
    ("갈아엎힌다", "재작성된다"),
    ("갈아엎었기", "재작성했기"),
    ("갈아엎는다", "재작성한다"),
]

GLOBAL_FILES = [
    ROOT / "docs/MASTER.md",
    ROOT / "docs/PLAN.md",
    ROOT / "src/etl/ngii1k.py",
    ROOT / "src/etl/segments.py",
    ROOT / "web/app.js",
]

# ── 2. 문장 단위 ────────────────────────────────────────────────────
PLAN_SENT: list[tuple[str, str]] = [
    ("이 오해가 지적도 캘리브레이션 3주를 태웠다(§6-1).",
     "이 오해로 지적도 캘리브레이션에 3주를 소모했다(§6-1)."),
    ("**발표 방어 논리로 최강이다** — \"우리는 틀릴 수 있다. 그래서 틀리는 방향을 설계했다.\"",
     "발표 논거: \"우리는 틀릴 수 있다. 그래서 틀리는 방향을 설계했다.\""),
    ("경로 산출 후 \"이 경로상 소화전 3개 경유\"를 바로 뽑을 수 있다. 시연에서 강하다.",
     "경로 산출 후 \"이 경로상 소화전 3개 경유\"를 바로 뽑을 수 있다.\n발표 논거: 시연에서 이 한 줄이 경로 품질을 보여준다."),
    ("**실제 CCTV 배포에서도 쓸모가 있다** — 카메라 흔들림·재설치 시 자동 복구. 발표 논거로 강하다.",
     "실제 CCTV 배포에서도 쓸모가 있다 — 카메라 흔들림·재설치 시 자동 복구.\n발표 논거로도 쓴다."),
    ("- \"14시 통과 가능 / 19시 불가\" → 서비스 필요성 최강 소재",
     "- \"14시 통과 가능 / 19시 불가\" → 서비스 필요성을 보이는 사례"),
    ("**\"1개밖에 없다\"보다 \"588개 중 31개만 공개돼 있다\"가 훨씬 강하다.**",
     "**\"1개밖에 없다\"가 아니라 \"588개 중 31개만 공개돼 있다\"로 쓴다.**\n결측이 아니라 공개 범위의 문제임이 드러난다."),
    ("- 그래프 방향성 결정(§5-7) ← 안 정하면 코드 두 번 재작성된다",
     "- 그래프 방향성 결정(§5-7) ← 미결이면 구현 후 재작성이 불가피하다"),
    ("안전장치가 아니라 새 벌레였다.",
     "안전장치가 아니라 새로 만든 결함이었다."),
    ("상수만 보면 근거 미기재 임의값처럼 보이지만 **근거가 붙어 있으면 함부로 못 건드린다.**",
     "값만 보면 임의값과 구분되지 않는다. **근거가 붙어 있으면 함부로 못 건드린다.**"),
]

MASTER_SENT: list[tuple[str, str]] = [
    ("G-06 폐기          시군구코드 29110 통일. 실행하면 파이프라인이 죽는다 (12210 유지)",
     "G-06 폐기          시군구코드 29110 통일. 실행하면 파이프라인이 중단된다 (12210 유지)"),
    ("제가 같은 파일을 두 번 재작성했기 때문입니다.",
     "제가 같은 파일을 두 번 재작성했기 때문입니다. 브랜치 수명을 짧게 가져가면 재발하지 않습니다."),
]


def apply(path: Path, pairs, *, glob: bool, check: bool) -> int:
    text = orig = path.read_text(encoding="utf-8")
    fail = 0
    for old, new in pairs:
        n = text.count(old)
        if n == 0:
            if not glob:
                print(f"! {path.name} 앵커 없음 — {old.splitlines()[0][:50]}")
                fail += 1
            continue
        text = text.replace(old, new)
    if not check and not fail and text != orig:
        path.write_text(text, encoding="utf-8")
        print(f"  {path.relative_to(ROOT)}")
    return fail


def main() -> int:
    check = "--check" in sys.argv
    fail = 0
    for p in GLOBAL_FILES:
        fail += apply(p, GLOBAL, glob=True, check=check)
    fail += apply(ROOT / "docs/PLAN.md", PLAN_SENT, glob=False, check=check)
    fail += apply(ROOT / "docs/MASTER.md", MASTER_SENT, glob=False, check=check)
    print("\n" + ("★ 앵커 실패 %d" % fail if fail else
                  "정규화 " + ("검사 통과." if check else "적용 완료.")))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
