#!/usr/bin/env bash
# fix-ortho-log.sh — ortho TIF 의 cp949 메타 로그 스팸을 실제로 막는다
#
#   저장소 루트에서:  bash fix-ortho-log.sh
#
# ── 무엇이 문제였나 ────────────────────────────────────────
# 정사영상 TIF 4장을 열 때마다 이 두 개가 나온다.
#
#   NotGeoreferencedWarning: Dataset has no geotransform...
#   UnicodeDecodeError: 'utf-8' codec can't decode byte 0xa0
#   Exception ignored in: 'rasterio._env.log_error'
#
# 원인
#   원본 TIF 메타데이터가 cp949 다. GDAL 이 C 문자열로 로그를 내보내고
#   rasterio 의 `_env.log_error` 콜백이 그것을 UTF-8 로 디코딩하다 터진다.
#   콜백 안에서 난 예외라 `sys.unraisablehook` 으로 출력된다.
#
#   geotransform 이 없는 것은 사실이다. PLAN #11 이 이미 적어놨다 —
#   ".xml·TIF 에 경계좌표 없음. 도엽 bbox + 사방 균등 pad **가정**".
#   ortho.py 가 스코프 bbox 로 직접 배치하므로 동작에는 지장이 없다.
#
# ── 왜 고치나 ──────────────────────────────────────────────
# PLAN 은 "라이브러리 내부라 못 막고 타일은 정상" 으로 무해 판정했다.
# 무해는 맞다. 그러나 매 실행 트레이스백 4벌이 쌓이면 **진짜 오류가
# 묻힌다.** 실제로 2026-08-21 `OSError: Errno 12` 를 이 스팸 사이에서
# 찾느라 시간을 태웠다.
#
# ── 어떻게 막나 ────────────────────────────────────────────
# `logging` 으로는 안 된다. unraisablehook 출력은 로깅 경로가 아니다.
# 훅을 감싸서 **rasterio._env 에서 난 UnicodeDecodeError 만** 버린다.
# 다른 예외와 다른 모듈은 그대로 통과시킨다 — 진짜 오류를 가리면 안 된다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

echo "── 1. 억제 모듈"
cat > src/etl/quiet_gdal.py <<'QG_EOF'
#!/usr/bin/env python3
"""
quiet_gdal.py — GDAL/rasterio 의 알려진 무해 잡음만 걷어낸다.

    import quiet_gdal  # rasterio 를 쓰기 전에

── 무엇을 막나 ────────────────────────────────────────────────
1. `NotGeoreferencedWarning`
   정사영상 TIF 에 geotransform 이 없다. 사실이고 이미 알고 있다
   (PLAN #11 — 도엽 bbox + 사방 균등 pad 가정). ortho.py 가 스코프
   bbox 로 직접 배치하므로 동작에 지장이 없다.

2. `rasterio._env.log_error` 안에서 난 `UnicodeDecodeError`
   원본 TIF 메타가 cp949 인데 rasterio 콜백이 UTF-8 로 디코딩한다.
   콜백 내부 예외라 sys.unraisablehook 으로 트레이스백이 찍힌다.
   매 실행 4벌.

── 무엇을 막지 않나 ★ ─────────────────────────────────────────
그 **둘만** 막는다. 다른 예외, 다른 모듈, 다른 경고는 그대로 통과한다.
2026-08-21 `OSError: Errno 12`(메모리 부족) 를 이 스팸 사이에서 찾느라
시간을 태웠다. 잡음을 지우는 목적은 진짜 오류를 보이게 하는 것이지
오류를 감추는 것이 아니다.

억제 건수는 `suppressed()` 로 셀 수 있다. 예상보다 많이 세어지면
새로운 문제가 섞여 들어온 것이다.
"""
from __future__ import annotations

import sys
import warnings

_count = {"unicode": 0, "warning": 0}
_installed = False


def suppressed() -> dict[str, int]:
    """억제한 건수. 예상 밖으로 늘면 새 문제가 섞인 것이다."""
    return dict(_count)


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    # 1. geotransform 없음 경고
    try:
        from rasterio.errors import NotGeoreferencedWarning
        warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
    except Exception:                                        # noqa: BLE001
        warnings.filterwarnings("ignore", message=".*not georeferenced.*")

    # 2. rasterio 로그 콜백의 cp949 디코딩 실패
    prev = sys.unraisablehook

    def _hook(un):
        if un.exc_type is UnicodeDecodeError and \
                "rasterio._env" in repr(getattr(un, "object", None)):
            _count["unicode"] += 1
            return
        prev(un)

    sys.unraisablehook = _hook


install()
QG_EOF
python3 -m py_compile src/etl/quiet_gdal.py && echo "  ✓ src/etl/quiet_gdal.py"

echo
echo "── 2. rasterio 를 쓰는 단계에 배선"
python3 - <<'PATCH'
import re
from pathlib import Path

done, skip, fail = [], [], []
for f in ("src/etl/ortho.py", "src/etl/terrain.py"):
    p = Path(f)
    if not p.exists():
        continue
    s = p.read_text(encoding="utf-8")
    if "quiet_gdal" in s:
        skip.append(f)
        continue
    if "rasterio" not in s:
        skip.append(f + " (rasterio 안 씀)")
        continue
    # 첫 rasterio import 바로 앞에 넣는다. 훅이 먼저 걸려야 한다.
    m = re.search(r"^(import rasterio.*|from rasterio.*)$", s, re.M)
    if not m:
        fail.append(f)
        continue
    add = ("import quiet_gdal  # noqa: F401  GDAL cp949 로그 잡음 억제. "
           "rasterio 보다 먼저\n")
    s = s[:m.start()] + add + s[m.start():]
    p.write_text(s, encoding="utf-8")
    done.append(f)

for f in done:
    print(f"  ✓ {f}")
for f in skip:
    print(f"  · {f} — 건너뜀")
for f in fail:
    print(f"  ✗ {f} — rasterio import 를 못 찾았다")
PATCH

python3 -m py_compile src/etl/ortho.py src/etl/terrain.py 2>/dev/null && echo "  ✓ 문법"

echo
echo "── 3. 필터 동작 검증"
python3 - <<'VERIFY'
import sys
sys.path.insert(0, "src/etl")
import quiet_gdal


def would(objrepr, exc):
    return exc is UnicodeDecodeError and "rasterio._env" in repr(objrepr)


cases = [
    ("'rasterio._env.log_error'", UnicodeDecodeError, True,  "막아야 함"),
    ("<function foo.__del__>",    UnicodeDecodeError, False, "다른 모듈은 통과"),
    ("'rasterio._env.log_error'", OSError,            False, "다른 예외는 통과"),
    ("'src.etl.ortho'",           UnicodeDecodeError, False, "우리 코드는 통과"),
]
ok = True
for o, e, want, why in cases:
    got = would(o, e)
    if got != want:
        ok = False
    print(f"  {'✓' if got == want else '✗'} {why:20s} 억제={got}")
print("\n  ★ Errno 12 같은 진짜 오류는 그대로 나온다" if ok else "\n  ✗ 필터 이상")
VERIFY

git add -A
git diff --cached --quiet || {
  git commit -q -m "fix: ortho/terrain 의 GDAL cp949 로그 스팸 억제

원본 TIF 메타가 cp949 인데 rasterio 의 로그 콜백이 UTF-8 로 디코딩하다
터진다. 콜백 내부 예외라 sys.unraisablehook 으로 트레이스백이 찍히고,
매 실행 4벌이 쌓였다.

무해한 것은 맞지만 진짜 오류가 묻힌다 — 08-21 OSError Errno 12 를
이 스팸 사이에서 찾느라 시간을 태웠다.

rasterio._env 에서 난 UnicodeDecodeError 와 NotGeoreferencedWarning
둘만 막는다. 다른 예외·모듈은 그대로 통과한다."
  echo
  echo "  ✓ 커밋"
}

cat <<'NEXT'

── 확인

  flrun --only ortho

  나와야 하는 것:   037/038/047/048 ... px 읽음 · 타일 1423장
  사라져야 하는 것: UnicodeDecodeError · NotGeoreferencedWarning · Traceback

★ ortho 를 돌리면 _manifest.json 이 또 바뀐다.
  다음 실행 전에:  rm -f data/processed/_lineage.json
NEXT
