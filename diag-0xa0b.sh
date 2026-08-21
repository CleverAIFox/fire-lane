#!/usr/bin/env bash
# diag-0xa0b.sh — 사이드카 XML 확인 + 억제 방법 3종 시험
#
#   저장소 루트에서:  bash diag-0xa0b.sh
#
# 1차 진단에서 나온 것
#   · TIF 옆에 같은 이름의 .xml 2,428바이트가 있다  ← 유력
#   · TIF 헤더의 0xa0 970곳은 픽셀 데이터다. 무관
#   · osgeo 모듈이 없다. rasterio 번들 GDAL 을 써야 한다
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }
: "${FIRE_LANE_DATA:?}"

XML="$(ls "$FIRE_LANE_DATA"/raw/ngii/ngii_ortho_gj037_*.xml 2>/dev/null | head -1)"
TIF="$(ls "$FIRE_LANE_DATA"/raw/ngii/ngii_ortho_gj037_*.tif 2>/dev/null | head -1)"

echo "══ 1. 사이드카 XML 의 57바이트째"
if [ -f "$XML" ]; then
    python3 - "$XML" <<'PY'
import sys
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
print(f"  {Path(sys.argv[1]).name} · {len(b)} bytes")
try:
    b.decode("utf-8")
    print("  utf-8 디코딩 성공 — 이 파일은 아니다")
except UnicodeDecodeError as e:
    print(f"  ★ utf-8 실패: position {e.start} · byte 0x{b[e.start]:02x}")
    if e.start == 57:
        print("  ★★ position 57 일치. 범인이다.")
    s = max(0, e.start - 40)
    print(f"    앞뒤 바이트: {b[s:e.start + 40]!r}")
    for enc in ("cp949", "euc-kr"):
        try:
            print(f"    {enc}: {b[s:e.start + 40].decode(enc)}")
            break
        except Exception:
            pass
print("\n  첫 줄:", b[:120])
PY
else
    echo "  XML 없음"
fi

echo
echo "══ 2. XML 을 잠시 치우면 오류가 사라지나 (원본 불변 · 복사본으로 시험)"
uv run python - "$TIF" "$XML" <<'PY'
import shutil
import sys
import tempfile
from pathlib import Path

import rasterio

tif, xml = Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None
tmp = Path(tempfile.mkdtemp())

# TIF 는 328MB 라 복사하지 않고 심링크. XML 만 있고/없고를 바꾼다.
link = tmp / tif.name
link.symlink_to(tif)


def count(with_xml: bool) -> int:
    n = [0]
    old = sys.unraisablehook
    sys.unraisablehook = lambda un: n.__setitem__(0, n[0] + 1)
    side = tmp / xml.name if xml else None
    if with_xml and side and not side.exists():
        shutil.copy2(xml, side)
    if not with_xml and side and side.exists():
        side.unlink()
    try:
        with rasterio.open(link) as ds:
            _ = ds.width
    finally:
        sys.unraisablehook = old
    return n[0]


a = count(True)
b = count(False)
print(f"  XML 있음: unraisable {a}회")
print(f"  XML 없음: unraisable {b}회")
print("  ★ 사이드카 XML 이 원인이다" if a > b else "  XML 은 원인이 아니다")
PY

echo
echo "══ 3. 억제 방법 시험"
uv run python - "$TIF" <<'PY'
import sys
from pathlib import Path

tif = Path(sys.argv[1])


def trial(name, setup):
    import importlib
    n = [0]
    old = sys.unraisablehook
    sys.unraisablehook = lambda un: n.__setitem__(0, n[0] + 1)
    try:
        import rasterio
        setup(rasterio)
        with rasterio.open(tif) as ds:
            _ = ds.width
    except Exception as e:                                   # noqa: BLE001
        print(f"  {name:38s} 오류: {type(e).__name__}: {e}")
        sys.unraisablehook = old
        return
    sys.unraisablehook = old
    mark = "★ 해답" if n[0] == 0 else ""
    print(f"  {name:38s} unraisable {n[0]}회  {mark}")


trial("(a) 아무것도 안 함", lambda r: None)

trial("(b) GDAL_PAM_ENABLED=NO 옵션",
      lambda r: r.Env(GDAL_PAM_ENABLED="NO").__enter__())

trial("(c) CPL_LOG_ERRORS=OFF 옵션",
      lambda r: r.Env(CPL_LOG_ERRORS="OFF").__enter__())


def quiet_handler(r):
    # rasterio 번들 GDAL 의 오류 핸들러를 C 레벨에서 교체한다.
    from rasterio._err import CPLE_BaseError  # noqa: F401
    import rasterio._env as _env
    if hasattr(_env, "log_error"):
        _env.log_error = lambda *a, **k: None


trial("(d) rasterio._env.log_error 치환", quiet_handler)


def null_logger(r):
    import logging
    for nm in ("rasterio", "rasterio._env", "rasterio._io"):
        lg = logging.getLogger(nm)
        lg.handlers = [logging.NullHandler()]
        lg.propagate = False
        lg.setLevel(logging.CRITICAL)


trial("(e) rasterio 로거 무력화", null_logger)
PY

cat <<'NEXT'

══ 판정

  1번이 position 57 이면 사이드카 XML 이 확정 원인이다.
  2번에서 XML 없을 때 0회면 같은 결론이다.

  그 경우 해법 두 가지 — 둘 다 raw 를 건드리지 않는다.
    · GDAL_PAM_ENABLED / GDAL_DISABLE_READDIR_ON_OPEN 으로 사이드카를 안 읽게
    · ingest 가 norm 계층에 XML 없는 심링크를 만들고 ortho 가 그것을 읽게

  3번에서 (b)~(e) 중 0회가 나오면 그것을 quiet_gdal.py 에 넣으면 끝난다.
NEXT
