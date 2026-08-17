#!/usr/bin/env python3
"""
docfix_20260817.py — MASTER 를 2026-08-17 산출과 맞추고 빠진 절을 넣는다.

    uv run python tools/docfix_20260817.py --check
    uv run python tools/docfix_20260817.py

★ 8/14판 기준으로 만든 docfix_20260815 · docfix2 · docnorm 은 폐기했다.
  8/15 개편으로 MASTER·PLAN 구조가 바뀌어 앵커가 전부 깨졌다.

무엇을 넣나
  §2      판정 숫자 1093 / 383·216·65·429. CCTV 유효범위 재계산
  §10-0   D-XX 대응표. 46회 인용되는데 정의가 저장소 밖에 있었다
  §11     데이터 필드 절의 구간 수
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "docs/MASTER.md"

SEC2_OLD = """## 2. 현재 판정 (2026-08-14)

| 판정 | 구간 | 뜻 |
|---|---:|---|
| `clear` 통행 가능 | 386 | 양쪽 주차가 있어도 통과. 영상판정 불필요 |
| `needs_cv` 판정 보류 | 210 | 상습주차 여부로 갈린다. 영상판정 대상 |
| `blocked` 통행 불가 | 62 | 차가 없어도 통과 불가 |
| `unknown` 영상판정 불가 | 444 | CCTV 25m 밖. 영상판정 자체가 불가능 |

```
segments 1102 · 경로사용 580
```

> 08-13 대비 `clear` 443 → 386. **미탐(막혔는데 통과 판정) 77건 제거**다.
> `width_min>30m` 인 47구간이 전부 `clear` 였다. §13 0-3 참조.

**`unknown` 396 은 전부 `no_cctv` 다.** 8/12 에 127 개였던 `width`(폭 산출 불가)는
8/13 에 0 이 됐다. 회색은 이제 한 가지 뜻만 갖는다 — 카메라가 없어 못 본다."""

SEC2_NEW = """## 2. 현재 판정 (2026-08-17)

| 판정 | 구간 | 뜻 |
|---|---:|---|
| `clear` 통행 가능 | 383 | 양쪽 주차가 있어도 통과. 영상판정 불필요 |
| `needs_cv` 판정 보류 | 216 | 상습주차 여부로 갈린다. 영상판정 대상 |
| `blocked` 통행 불가 | 65 | 차가 없어도 통과 불가 |
| `unknown` 영상판정 불가 | 429 | CCTV 25m 밖. 영상판정 자체가 불가능 |

```
segments 1093
```

> 08-14 대비 `1102 → 1093`. 수치지형도를 통째로 교체하고 평면교차점 실형상을
> 도입한 결과다. 판정이 바뀐 구간은 59 / 1093 (5.4%)이고 총연장 48,580m 는
> 변하지 않았다. 구간 경계는 재배치됐으나 도로망 총량은 같다는 뜻이다.
>
> 구 판정은 원본 소실로 **재생성 불가**라 봉인돼 있다(§18-8-1).
> `uv run python tools/baseline.py diff 20260814-ngii-ngi20` 로 전이 행렬을 본다.
>
> 주요 전이 — `unknown → clear` 22 · `clear → unknown` 15 · `clear → needs_cv` 10.
> 74도엽 확장으로 판정 근거가 생긴 쪽과 사라진 쪽이 함께 있다.

**`unknown` 429 는 전부 `no_cctv` 다.** 8/12 에 127 개였던 `width`(폭 산출 불가)는
8/13 에 0 이 됐고 지금도 0 이다. 회색은 한 가지 뜻만 갖는다 — 카메라가 없어 못 본다.
`pipeline.py` 의 `EXPECT["unknown_reason"]` 이 매 실행 이것을 대조한다."""

D_TABLE_ANCHOR = "# 10. 용어"
D_TABLE = """# 10. 용어

## 10-0. `D-XX` 는 날짜가 아니다

**미결정 항목 번호(Decision)** 다. 출처는 2026-08-07 「미결정 사항 정리」이며,
2026-08-11 문서 3축 통합 때 번호만 살아남고 정의가 빠져 있었다.
아래 9개가 MASTER · PLAN 에서 실제로 인용되는 전부다.

| 번호 | 항목 | 현재 |
|---|---|---|
| `D-03` | 판정 오류의 비대칭 · 안전마진 | 반영 완료 |
| `D-05` | 도로를 간선으로 — 교차로 분할 확인 | 해소. `NODE_TOL 0.5m` |
| `D-07` | 그래프 방향성 (무향 / 유향) | **미결.** PLAN §5-7 |
| `D-08` | 회전 반경 · 코너 판정 | 미결. 적용 범위 한정안만 있음 |
| `D-13` | 야간 성능 · 가로등 데이터 | 데이터 확보. 야간 답사 미실시 |
| `D-21` | 주정차/주행 판별 · 시간대 촬영 | 미착수. 영상 담당 |
| `D-25` | 레이저 거리계 실측 | **미착수.** 폭 검증 전건이 걸려 있다 |
| `D-28` | 시나리오 자동 탐색 | 미착수 |
| `D-30` | 소방서 정식 인터뷰 | 미착수. 소화전 좌표 · 차량 제원 |

원문에는 D-01~D-33 이 있으나 나머지는 이 저장소가 인용하지 않는다.
**새 D 번호를 만들지 않는다.** 남은 결정은 PLAN 에 절 번호로 쓴다.

---
"""

PAIRS: list[tuple[str, str]] = [
    (SEC2_OLD, SEC2_NEW),
    ("`web/data/segments.geojson` — 1,102개",
     "`web/data/segments.geojson` — 1,093개"),
]


def main() -> int:
    check = "--check" in sys.argv
    t = M.read_text(encoding="utf-8")
    bad = 0

    if "## 10-0." in t:
        print("  §10-0 이미 있음 — 건너뜀")
    elif t.count(D_TABLE_ANCHOR) != 1:
        print(f"! §10 앵커 {t.count(D_TABLE_ANCHOR)}회")
        bad += 1

    for i, (old, _) in enumerate(PAIRS, 1):
        if t.count(old) != 1:
            print(f"! #{i} 앵커 {t.count(old)}회 — {old.splitlines()[0][:55]}")
            bad += 1

    if bad:
        print(f"\n★ 앵커 {bad}건 실패. 아무것도 쓰지 않았다.")
        return 1
    if check:
        print("앵커 전건 일치. --check 이므로 쓰지 않았다.")
        return 0

    for old, new in PAIRS:
        t = t.replace(old, new, 1)
    if "## 10-0." not in t:
        t = t.replace(D_TABLE_ANCHOR, D_TABLE.rstrip("\n"), 1)

    M.write_text(t, encoding="utf-8")
    print("  docs/MASTER.md — §2 판정 · §10-0 D-XX 대응표 · §11 구간 수")
    print("\n다음: uv run python tools/docnum_check.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
