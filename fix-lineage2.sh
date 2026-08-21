#!/usr/bin/env bash
# fix-lineage2.sh — 계보 설계 결함 2건을 고친다
#
#   저장소 루트에서:  bash fix-lineage2.sh
#
# ── 결함 1. _manifest.json 을 바이트 전체로 비교한다 ───────
#   ingest    _manifest.json 을 쓴다                  sha = A
#   segments  이 파일을 reads 로 선언 → 지문 A 기록
#   terrain   같은 파일에 자기 기록을 덧쓴다           sha = A → B
#   ─── 다음 실행 ───
#   segments  기대 A · 디스크 B  →  반드시 실패
#
#   전량 실행이 **성공할 때마다** 다음 --from segments 가 깨졌다.
#   2026-08-21 에 _lineage.json 을 네 번 지웠다.
#
#   segments 가 실제로 의존하는 것은 파일 전체가 아니라 **ingest 가 쓴
#   datasets 블록** 이다. terrain 이 덧쓴 부분은 segments 와 무관하다.
#   그래서 _manifest.json 만 그 블록으로 지문을 뜬다.
#
#   ★ 검사를 느슨하게 하는 것이 아니다. 08-18 사고(ngii1k 14336 기록 vs
#     옛 레이어 6675 사용)는 datasets 블록의 변화였으므로 그대로 잡힌다.
#     오탐만 걷어낸다 — 오탐이 잦으면 진짜 경보를 무시하게 된다.
#
# ── 결함 2. terrain 의 선언이 실제와 다르다 ────────────────
#   reads 로 선언해놓고 실제로는 덧쓴다. Step docstring 이 이 경우를
#   mutates 로 정의해놨다. 선언을 실제에 맞춘다.
#
# ── 결함 3. 탈출구가 rm 뿐이다 ─────────────────────────────
#   --reset-lineage 를 만든다. 원칙("낡은 입력으로 판정하지 않는다")은
#   유지하되 사람이 명시적으로 책임지고 넘어가는 문을 둔다.
#   몰래 rm 하는 것보다 로그에 남는 편이 낫다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

echo "── 1. lineage.py — _manifest.json 지문을 datasets 블록으로"
python3 - <<'PATCH'
import sys
from pathlib import Path

p = Path("src/etl/lineage.py")
s = p.read_text(encoding="utf-8")
if "_manifest_digest" in s:
    print("  · 이미 적용됨")
    sys.exit(0)

old = '''    if ext in BYTES:
        return {"kind": "bytes", "sha256": _sha(p)}'''
new = '''    if p.name == "_manifest.json":
        return _manifest_digest(p)
    if ext in BYTES:
        return {"kind": "bytes", "sha256": _sha(p)}'''
if old not in s:
    print("  ✗ fingerprint 앵커 없음")
    sys.exit(1)
s = s.replace(old, new, 1)

helper = '''
# ── _manifest.json 만 다르게 본다 ──────────────────────────────
# 이 파일은 ingest 가 쓰고 terrain 이 자기 기록을 덧쓴다. 바이트 전체를
# 비교하면 terrain 이 돌 때마다 segments 의 입력 지문이 어긋난다.
# 전량 실행이 성공할 때마다 다음 --from segments 가 깨지는 원인이었다.
#
# segments 가 의존하는 것은 **ingest 가 쓴 datasets 블록** 이다.
# 그 블록만 정규화해서 해시한다. 08-18 사고(ngii1k 14336 기록 vs 옛
# 레이어 6675 사용)는 이 블록의 변화이므로 그대로 잡힌다.
_MANIFEST_OWNED = ("datasets", "bbox_4326", "standard_crs")


def _manifest_digest(p: Path) -> dict:
    """대장의 ingest 소유 블록만으로 지문을 뜬다."""
    import json as _json
    try:
        d = _json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001
        # 파싱 실패는 숨기지 않는다. 바이트 해시로 떨어뜨린다.
        return {"kind": "bytes", "sha256": _sha(p)}
    owned = {k: d.get(k) for k in _MANIFEST_OWNED if k in d}
    blob = _json.dumps(owned, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
    return {"kind": "manifest",
            "sha256": hashlib.sha256(blob).hexdigest()[:16],
            "n": len(d.get("datasets", []))}


'''
anchor = "def _same(a: dict | None, b: dict | None) -> bool:"
if anchor not in s:
    print("  ✗ _same 앵커 없음")
    sys.exit(1)
s = s.replace(anchor, helper.lstrip("\n") + anchor, 1)

old2 = '''    if a["kind"] == "bytes":
        return a.get("sha256") == b.get("sha256")'''
new2 = '''    if a["kind"] in ("bytes", "manifest"):
        return a.get("sha256") == b.get("sha256")'''
if old2 not in s:
    print("  ✗ _same 비교 앵커 없음")
    sys.exit(1)
s = s.replace(old2, new2, 1)

if "import hashlib" not in s:
    print("  ✗ hashlib 임포트가 없다. 수동 확인 필요")
    sys.exit(1)

p.write_text(s, encoding="utf-8")
print("  ✓ src/etl/lineage.py — _manifest.json 은 datasets 블록으로 비교")
PATCH

echo
echo "── 2. pipeline.py — terrain 선언을 실제에 맞춘다"
python3 - <<'PATCH2'
import sys
from pathlib import Path

p = Path("src/etl/pipeline.py")
s = p.read_text(encoding="utf-8")

old = '''         reads=(P / "_manifest.json",),
         writes=(WEB / "terrain", P / "dem_scope.tif"),
         # ★ 여기가 z 소실의 자리다. segments.geojson 을 읽어 z 를 덧쓴다.
         mutates=(P / "segments.geojson",)),'''
new = '''         writes=(WEB / "terrain", P / "dem_scope.tif"),
         # ★ 여기가 z 소실의 자리다. segments.geojson 을 읽어 z 를 덧쓴다.
         # ★ _manifest.json 도 reads 가 아니라 mutates 다. terrain 기록을
         #   덧쓴다("→ _manifest.json 에 terrain 기록"). reads 로 적어두면
         #   선언과 실제가 달라 하류 무효화 경고가 안 뜬다.
         mutates=(P / "segments.geojson", P / "_manifest.json")),'''
if "mutates=(P / \"segments.geojson\", P / \"_manifest.json\")" in s:
    print("  · 이미 적용됨")
elif old in s:
    p.write_text(s.replace(old, new, 1), encoding="utf-8")
    print("  ✓ terrain: _manifest.json 을 reads → mutates")
else:
    print("  ✗ terrain Step 앵커 없음 — 수동 확인 필요")
    sys.exit(1)
PATCH2

echo
echo "── 3. pipeline.py — --reset-lineage 탈출구"
python3 - <<'PATCH3'
import sys
from pathlib import Path

p = Path("src/etl/pipeline.py")
s = p.read_text(encoding="utf-8")
if "--reset-lineage" in s:
    print("  · 이미 적용됨")
    sys.exit(0)

old = '''    ap.add_argument("--no-test", action="store_true", help="계약 테스트 생략")
    a = ap.parse_args()
'''
new = '''    ap.add_argument("--no-test", action="store_true", help="계약 테스트 생략")
    ap.add_argument("--reset-lineage", action="store_true",
                    help="계보 기록을 지우고 시작한다 (교착 탈출구)")
    a = ap.parse_args()

    if a.reset_lineage:
        # ★ 명시적 탈출구. 지금까지는 _lineage.json 을 손으로 rm 하는 것이
        #   유일한 방법이었고 문서에도 없었다. 몰래 지우는 것보다 로그에
        #   남는 편이 낫다 — 무엇을 근거로 넘어갔는지가 남는다.
        _lin = PROCESSED / "_lineage.json"
        if _lin.exists():
            _lin.unlink()
            print(f"★ 계보 기록을 지웠다: {_lin}")
            print("  이번 실행의 입력은 대조 없이 진행한다. "
                  "산출물이 낡았을 가능성을 사람이 책임진다.")
        else:
            print("· 계보 기록이 이미 없다")
'''
if old not in s:
    print("  ✗ argparse 앵커 없음")
    sys.exit(1)
s = s.replace(old, new, 1)

if "PROCESSED" not in s:
    print("  ✗ PROCESSED 가 pipeline.py 에 없다. 수동 확인 필요")
    sys.exit(1)

p.write_text(s, encoding="utf-8")
print("  ✓ pipeline.py — --reset-lineage 추가")
PATCH3

python3 -m py_compile src/etl/lineage.py src/etl/pipeline.py && echo "  ✓ 문법"

echo
echo "── 4. 지문 동작 검증"
python3 - <<'VERIFY'
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src/etl")
import lineage

tmp = Path(tempfile.mkdtemp())
m = tmp / "_manifest.json"

base = {"generated_at": "2026-08-21T00:00:00+09:00",
        "bbox_4326": [126.9, 35.1, 126.94, 35.16],
        "standard_crs": {"metric": "EPSG:5186"},
        "datasets": [{"key": "ngii1k", "features": 14336}]}

m.write_text(json.dumps(base), encoding="utf-8")
a = lineage.fingerprint(m)

# terrain 이 덧쓴 상황
after = dict(base, terrain={"tiles": 22}, generated_at="2026-08-21T01:00:00+09:00")
m.write_text(json.dumps(after), encoding="utf-8")
b = lineage.fingerprint(m)

# 08-18 사고: datasets 가 바뀐 상황
sabo = dict(base, datasets=[{"key": "ngii1k", "features": 6675}])
m.write_text(json.dumps(sabo), encoding="utf-8")
c = lineage.fingerprint(m)

ok = True
if not lineage._same(a, b):
    ok = False
print(f"  {'✓' if lineage._same(a, b) else '✗'} terrain 덧씀 → 같다고 본다 (오탐 제거)")
if lineage._same(a, c):
    ok = False
print(f"  {'✓' if not lineage._same(a, c) else '✗'} datasets 변화 → 다르다고 본다 (08-18 사고 탐지)")
print(f"\n  {'★ 검사는 유지하고 오탐만 걷었다' if ok else '✗ 이상'}")
VERIFY

git add -A
git diff --cached --quiet || {
  git commit -q -m "fix: 계보 오탐 제거 — _manifest.json 을 datasets 블록으로 비교

ingest 가 쓴 _manifest.json 에 terrain 이 자기 기록을 덧쓴다. 바이트
전체를 비교하니 전량 실행이 성공할 때마다 다음 --from segments 가
반드시 깨졌다. 08-21 에 _lineage.json 을 네 번 지웠다.

segments 가 의존하는 것은 ingest 가 쓴 datasets 블록이다. 그 블록만
해시한다. 08-18 사고(ngii1k 14336 기록 vs 옛 레이어 6675 사용)는
이 블록의 변화이므로 그대로 잡힌다.

terrain 의 _manifest.json 선언도 reads → mutates 로 실제에 맞췄다.
--reset-lineage 로 명시적 탈출구를 만들었다 — rm 으로 몰래 지우는
것보다 로그에 남는 편이 낫다.

오탐이 잦으면 진짜 경보를 무시하게 된다. 그것이 08-18 의 반대편 위험이다."
  echo
  echo "  ✓ 커밋"
}

cat <<'NEXT'

── 확인

  hathor 가 끝났으면:
    flnice flrun --from ingest
    flrun --from segments      ← ★ 이번엔 계보가 통과해야 한다

  두 번째 명령이 핵심이다. 지금까지는 전량 실행 직후 이걸 돌리면
  반드시 계보 실패였다. 통과하면 결함이 고쳐진 것이다.

  탈출구도 생겼다:
    flrun --from segments --reset-lineage
NEXT
