#!/usr/bin/env bash
# fix-0xa0.sh — 사이드카 스캔을 꺼서 cp949 디코딩 오류를 없앤다
#
#   저장소 루트에서:  bash fix-0xa0.sh
#
# ── 원인 (2026-08-21 실측으로 특정) ────────────────────────
#   raw/ngii/ngii_ortho_gj037_20251231.tif   328MB
#   raw/ngii/ngii_ortho_gj037_20251231.xml   2,428B   ← 국토지리정보원 메타
#
#   GDAL 은 래스터를 열 때 같은 디렉터리를 훑어 사이드카를 찾는다.
#   그 과정에서 이 .xml 을 만나고, C 레벨에서 디코딩하다 0xa0 에서 터진다.
#   콜백 안의 예외라 파이썬에서는 잡을 수 없다.
#
#   XML 자체는 멀쩡한 UTF-8 이다(`<?xml encoding="UTF-8"?>`). 로케일도
#   C.UTF-8 이다. 그런데도 터진다 — GDAL 내부 경로의 문제다.
#
# ── 시험 결과 ──────────────────────────────────────────────
#   XML 있음                                unraisable 1회
#   XML 없음                                unraisable 0회   ← 원인 확정
#   GDAL_PAM_ENABLED=NO                     1회  (.aux.xml 만 막는다)
#   CPL_LOG_ERRORS=OFF                      1회
#   rasterio._env.log_error 치환            1회
#   rasterio 로거 무력화                     1회
#   LC_ALL=C.UTF-8                          1회
#   GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR  0회   ★ 해답
#
# ── 왜 ortho 에만 거나 ─────────────────────────────────────
#   EMPTY_DIR 은 .tfw 같은 **정당한** 사이드카도 같이 막는다.
#   ortho.py 는 스코프 bbox 로 직접 배치하고 geotransform 을 쓰지 않는다
#   (그래서 NotGeoreferencedWarning 이 뜬다). 그러므로 안전하다.
#
#   ★ PLAN #11(정사영상 미터 단위 정합 미검증)을 제대로 하려면 사이드카
#     좌표가 필요해질 수 있다. 그때는 이 옵션을 끄고 대신 norm 계층에
#     XML 없는 심링크를 만드는 쪽으로 가야 한다. MASTER §5 의
#     "norm — 파일명·인코딩·확장자만 통일" 이 원래 이 용도다.
#
#   terrain 은 DEM 사이드카가 필요할 수 있으므로 걸지 않는다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

echo "── 1. quiet_gdal 에 함수 추가"
python3 - <<'PATCH'
import sys
from pathlib import Path

p = Path("src/etl/quiet_gdal.py")
s = p.read_text(encoding="utf-8")
if "disable_sidecar_scan" in s:
    print("  · 이미 적용됨")
    sys.exit(0)

add = '''

def disable_sidecar_scan() -> None:
    """GDAL 이 래스터를 열 때 디렉터리를 훑지 않게 한다.

    ── 왜 필요한가 ────────────────────────────────────────────
    정사영상 TIF 옆에 같은 이름의 국토지리정보원 메타 `.xml` 이 있다.
    GDAL 은 래스터를 열 때 사이드카를 찾으려고 디렉터리를 훑고, 그
    과정에서 이 XML 을 C 레벨에서 디코딩하다 0xa0 에서 터진다.
    콜백 안의 예외라 파이썬 훅으로는 못 막는다.

    2026-08-21 실측:

        XML 있음                                1회
        XML 없음                                0회   ← 원인
        GDAL_PAM_ENABLED=NO                     1회  (.aux.xml 만 막는다)
        CPL_LOG_ERRORS=OFF                      1회
        rasterio._env.log_error 치환            1회
        LC_ALL=C.UTF-8                          1회  (로케일은 이미 UTF-8)
        GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR  0회   ★

    ── 부작용 ★ ──────────────────────────────────────────────
    `.tfw` 같은 **정당한** 사이드카도 같이 막힌다. ortho.py 는 스코프
    bbox 로 직접 배치하고 geotransform 을 쓰지 않으므로 안전하다.

    PLAN #11(정사영상 정합 검증)을 제대로 하려면 사이드카 좌표가
    필요해질 수 있다. 그때는 이 함수를 빼고 norm 계층에 XML 없는
    심링크를 만드는 쪽으로 가라 — MASTER §5 의 "norm: 파일명·인코딩·
    확장자만 통일" 이 원래 이 용도다.

    그래서 import 만으로 걸지 않고 명시적으로 호출하게 둔다.
    terrain 은 DEM 사이드카가 필요할 수 있으므로 부르지 않는다.
    """
    import os
    os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
'''
p.write_text(s.rstrip("\n") + add, encoding="utf-8")
print("  ✓ src/etl/quiet_gdal.py — disable_sidecar_scan()")
PATCH

echo
echo "── 2. ortho.py 에서만 호출"
python3 - <<'PATCH2'
import sys
from pathlib import Path

p = Path("src/etl/ortho.py")
s = p.read_text(encoding="utf-8")
if "disable_sidecar_scan()" in s:
    print("  · 이미 적용됨")
    sys.exit(0)

old = "import quiet_gdal  # noqa: F401  GDAL cp949 로그 잡음 억제. rasterio 보다 먼저"
new = ("import quiet_gdal  # noqa: F401  GDAL cp949 로그 잡음 억제. rasterio 보다 먼저\n"
       "quiet_gdal.disable_sidecar_scan()  # 정사영상 옆 .xml 을 GDAL 이 읽지 않게")
if old not in s:
    print("  ✗ quiet_gdal import 앵커 없음")
    sys.exit(1)
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("  ✓ src/etl/ortho.py — disable_sidecar_scan() 호출")
PATCH2

python3 -m py_compile src/etl/quiet_gdal.py src/etl/ortho.py && echo "  ✓ 문법"

echo
echo "── 3. 실제 확인 (ortho 단독 실행)"
echo
BEFORE_TILES=$(find web/data/ortho -name '*.jpg' 2>/dev/null | wc -l)
uv run python src/etl/pipeline.py --only ortho 2>&1 | grep -v "^ *$" | tail -20
AFTER_TILES=$(find web/data/ortho -name '*.jpg' 2>/dev/null | wc -l)

echo
echo "  타일 수 $BEFORE_TILES → $AFTER_TILES"
if [ "$BEFORE_TILES" = "$AFTER_TILES" ]; then
    echo "  ✓ 산출물 동일 — 옵션이 타일 생성을 바꾸지 않았다"
else
    echo "  ★ 타일 수가 달라졌다. 사이드카 차단이 배치에 영향을 줬는지 확인할 것"
fi

git add -A
git diff --cached --quiet || {
  git commit -q -m "fix: GDAL 사이드카 스캔을 꺼서 정사영상 cp949 오류 제거

정사영상 TIF 옆에 같은 이름의 국토지리정보원 메타 .xml 이 있다.
GDAL 이 래스터를 열 때 디렉터리를 훑어 사이드카를 찾다가 이 XML 을
C 레벨에서 디코딩하며 0xa0 에서 터진다. 매 실행 4회.

실측으로 원인을 특정했다 — XML 을 치우면 0회, 두면 1회.
PAM_ENABLED · CPL_LOG_ERRORS · 로거 무력화 · 로케일은 전부 실패했고
GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR 만 통했다.

ortho 에만 건다. .tfw 같은 정당한 사이드카도 막히는데, ortho 는 스코프
bbox 로 직접 배치하므로 안전하다. terrain 은 DEM 사이드카가 필요할 수
있어 부르지 않는다.

★ PLAN #11 정합 검증에서 사이드카 좌표가 필요해지면 이 옵션을 빼고
  norm 계층에 XML 없는 심링크를 만드는 쪽으로 가야 한다."
  echo
  echo "  ✓ 커밋"
}

cat <<'NEXT'

── 남은 잡음 하나

  NotGeoreferencedWarning 은 quiet_gdal 이 이미 막고 있는데도 뜬다면,
  warnings 필터가 rasterio import 뒤에 걸린 것이다. ortho.py 의
  import 순서를 확인해라 — quiet_gdal 이 rasterio 보다 먼저여야 한다.

── 그리고 이건 PLAN 에 올려라

  MASTER §5 는 norm 계층을 "파일명·인코딩·확장자만 통일" 로 정의해놨다.
  이 문제는 원래 거기서 처리됐어야 한다. norm 계층이 실제로는
  비어 있다(scan_data 출력: "norm — 없음").
NEXT
