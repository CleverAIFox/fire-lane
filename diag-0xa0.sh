#!/usr/bin/env bash
# diag-0xa0.sh — UnicodeDecodeError 0xa0 의 출처를 특정한다
#
#   저장소 루트에서:  bash diag-0xa0.sh
#
# 지금까지 훅·환경변수로 찍어봤다. 어디서 나오는지 모르는 채로 막으려
# 했으니 안 맞은 게 당연하다. 원인부터 특정한다.
#
# 단서
#   "position 57"  — 어떤 문자열의 57바이트째다. 매번 같다.
#   4번            — TIF 4장. 파일당 정확히 1번.
#   타일은 정상    — 읽기 자체는 성공한다. 메타 문자열만 문제다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }
: "${FIRE_LANE_DATA:?}"

TIF="$(ls "$FIRE_LANE_DATA"/raw/ngii/*.tif 2>/dev/null | head -1)"
[ -f "$TIF" ] || { echo "TIF 없음"; exit 1; }
echo "대상: $TIF"

echo
echo "══ 1. 사이드카 파일 (.aux.xml / .tfw / .xml)"
ls -la "${TIF%.tif}".* 2>/dev/null | sed 's/^/  /'

echo
echo "══ 2. TIF 헤더에서 0xa0 이 든 문자열"
python3 - "$TIF" <<'PY'
import sys
from pathlib import Path

p = Path(sys.argv[1])
head = p.read_bytes()[:200000]

hits = []
i = 0
while True:
    i = head.find(b"\xa0", i)
    if i < 0:
        break
    # 앞뒤로 출력가능 문자를 확장해 문자열 경계를 잡는다
    s = i
    while s > 0 and (32 <= head[s - 1] < 127 or head[s - 1] >= 128):
        s -= 1
    e = i
    while e < len(head) - 1 and (32 <= head[e + 1] < 127 or head[e + 1] >= 128):
        e += 1
    blob = head[s:e + 1]
    if len(blob) > 4:
        hits.append((s, i - s, blob))
    i += 1

print(f"  헤더 200KB 안에 0xa0 {len(hits)}곳")
for off, pos, blob in hits[:6]:
    print(f"\n  파일오프셋 {off} · 문자열내 위치 {pos}")
    print(f"    utf-8 : {blob.decode('utf-8', 'replace')[:120]}")
    for enc in ("cp949", "euc-kr", "latin-1"):
        try:
            print(f"    {enc:8s}: {blob.decode(enc)[:120]}")
            break
        except Exception:
            pass
    if pos == 57:
        print("    ★ position 57 — 오류 메시지의 그 문자열이다")
PY

echo
echo "══ 3. GDAL 이 이 TIF 에서 무엇을 읽나"
uv run python - "$TIF" <<'PY'
import sys

from osgeo import gdal

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")
ds = gdal.Open(sys.argv[1])
print(f"  드라이버: {ds.GetDriver().ShortName}")
print(f"  크기: {ds.RasterXSize}x{ds.RasterYSize}")
print(f"  파일목록: {ds.GetFileList()}")
for dom in [None] + (ds.GetMetadataDomainList() or []):
    md = ds.GetMetadata(dom) if dom else ds.GetMetadata()
    if not md:
        continue
    print(f"  도메인 {dom or '(기본)'}:")
    for k, v in list(md.items())[:6]:
        bad = any(ord(c) > 127 for c in str(v))
        print(f"    {k} = {str(v)[:90]}{'   ← 비ASCII' if bad else ''}")
PY

echo
echo "══ 4. 오류가 나는 순간의 파이썬 스택"
uv run python - "$TIF" <<'PY'
import sys
import traceback

import rasterio

_orig = sys.unraisablehook
shown = [0]


def hook(un):
    if shown[0] < 1:
        shown[0] += 1
        print("  ── unraisable 스택 ──")
        traceback.print_exception(un.exc_type, un.exc_value, un.exc_traceback)
        print(f"  object = {un.object!r}")
        print(f"  err_msg = {un.err_msg!r}")
    return


sys.unraisablehook = hook
with rasterio.open(sys.argv[1]) as ds:
    print(f"  열기 성공: {ds.width}x{ds.height}")
print(f"  unraisable 발생 {shown[0]}회")
PY

echo
echo "══ 5. GDAL 오류 핸들러를 갈아끼우면 막히나"
uv run python - "$TIF" <<'PY'
import sys

from osgeo import gdal

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")   # ★ C 레벨에서 조용히
import rasterio

n = [0]
sys.unraisablehook = lambda un: n.__setitem__(0, n[0] + 1)

with rasterio.open(sys.argv[1]) as ds:
    _ = ds.width
print(f"  CPLQuietErrorHandler 적용 후 unraisable {n[0]}회")
print("  ★ 0 이면 이것이 해답이다" if n[0] == 0 else "  이 방법은 아니다")
PY

cat <<'NEXT'

══ 판정

  2번에서 position 57 문자열이 나오면 그것이 원인이다.
  3번의 GetFileList 에 .aux.xml 이 있으면 사이드카가 원인이다.
  5번이 0 이면 gdal.PushErrorHandler("CPLQuietErrorHandler") 가 해답이고,
  quiet_gdal.py 에 그것을 넣으면 끝난다.

  전부 실패하면 원본 TIF 의 메타를 벗겨 쓰는 쪽이 남는다.
  raw 는 불변이므로 norm 계층에 정리본을 만드는 방향이다.
NEXT
