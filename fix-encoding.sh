#!/usr/bin/env bash
# fix-encoding.sh — 인코딩·개행을 경계에서 정규화하고 CI 게이트를 세운다
#
#   저장소 루트에서:  bash fix-encoding.sh
#   BOM 까지 제거:    bash fix-encoding.sh --fix-bom
#
# ── 왜 지금까지 새어 나왔나 ─────────────────────────────────
# `.gitattributes` 가 `*.py text eol=lf` 하나뿐이었다. csv·md·yaml·json
# 규칙이 없으니 파일마다 제각각이 됐다. 그리고 그걸 검사하는 것이 없었다.
#
#   .wslconfig          CRLF + 마지막 줄 개행 없음
#   data/field/*.csv    BOM → 첫 컬럼이 '\ufeffw_ngi' 가 된다
#   processed CSV       utf-8-sig
#   raw shapefile       cp949 (2026-08-17 utf-8 오선언 발견)
#   ortho TIF 메타      cp949 → rasterio UnicodeDecodeError 매 실행 4회
#
# 이 프로젝트는 계보·판정·문서를 전부 테스트로 강제하면서 인코딩만
# 강제자가 없었다. 여기서 그 구멍을 막는다.
#
# ── 원칙 ───────────────────────────────────────────────────
#   1. 저장소 안 텍스트는 UTF-8(BOM 없음) · LF · 마지막 줄 개행.
#   2. 예외는 명시한다 — .wslconfig 는 윈도우가 읽으므로 CRLF 유지.
#   3. raw 는 불변이다. 원본 인코딩은 sources.yaml 이 선언하고
#      ingest 가 읽을 때 변환한다. 원본 파일을 고치지 않는다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }
FIX_BOM=0
[ "${1:-}" = "--fix-bom" ] && FIX_BOM=1

echo "── 1. .gitattributes"
cat > .gitattributes <<'GA_EOF'
# 인코딩·개행 정규화
#
# 원칙 — 저장소 안 텍스트는 UTF-8(BOM 없음) · LF · 마지막 줄 개행.
# raw 는 불변이므로 여기 대상이 아니다. 원본 인코딩은 sources.yaml 이
# 선언하고 ingest 가 읽을 때 변환한다.
#
# 2026-08-21. 이전에는 `*.py text eol=lf` 하나뿐이라 csv·md·yaml·json 이
# 제각각이었다. data/field CSV 에 BOM 이 붙어 첫 컬럼명이 '\ufeffw_ngi' 로
# 읽히던 것이 그 결과다.

# 기본: git 이 텍스트로 판단하면 저장소에는 LF 로 넣는다.
* text=auto eol=lf

# ── 텍스트 (명시) ──────────────────────────────────────────
*.py     text eol=lf
*.sh     text eol=lf
*.md     text eol=lf
*.yml    text eol=lf
*.yaml   text eol=lf
*.csv    text eol=lf
*.txt    text eol=lf
*.html   text eol=lf
*.css    text eol=lf
*.js     text eol=lf

# ── 바이너리 취급 (diff 하지 않는다) ───────────────────────
# geojson/json 은 텍스트지만 좌표 배열이라 줄 단위 diff 가 의미 없다.
# 다만 정규화는 받아야 하므로 -text 대신 eol 만 고정한다.
*.geojson text eol=lf -diff
*.json    text eol=lf

*.gpkg   binary
*.tif    binary
*.zip    binary
*.jpg    binary
*.png    binary
*.docx   binary
*.hwpx   binary
*.pdf    binary
*.shp    binary
*.dbf    binary
*.shx    binary
GA_EOF
echo "  ✓ .gitattributes"

echo
echo "── 2. 검사 도구"
cat > tools/encoding_check.py <<'ENC_EOF'
#!/usr/bin/env python3
"""
tools/encoding_check.py — 저장소 텍스트의 인코딩·개행을 검사한다.

    uv run python tools/encoding_check.py           검사만
    uv run python tools/encoding_check.py --fix     고칠 수 있는 것을 고친다

── 무엇을 보나 ────────────────────────────────────────────────
    BOM           UTF-8 BOM. 첫 컬럼명이 '\\ufeffw_ngi' 가 되는 원인
    CRLF          윈도우 개행이 저장소에 들어온 것
    비 UTF-8      cp949 등이 그대로 들어온 것
    개행 없음     마지막 줄에 개행이 없어 다음 출력이 붙는다

── 왜 필요한가 ────────────────────────────────────────────────
이 프로젝트는 계보(lineage) · 판정(golden) · 문서(docnum) 를 전부
테스트로 강제한다. 인코딩만 강제자가 없어서 새어 나왔다.

`.gitattributes` 는 **커밋 시점**에만 개입한다. 이미 들어온 것과
저장소 밖(.wslconfig 등)은 못 잡는다. 그래서 검사가 따로 필요하다.

★ data/field 는 실측 원자료다. raw 와 같은 등급이고 재생성이 불가하다.
  `--fix` 로 고치기 전에 반드시 백업을 남긴다(.bak_enc).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 검사 대상 확장자
TEXT_EXT = {".py", ".sh", ".md", ".yml", ".yaml", ".csv", ".txt",
            ".html", ".css", ".js", ".json", ".geojson", ".cfg", ".toml"}

# 예외 — 윈도우가 직접 읽는 파일은 CRLF 를 유지한다.
CRLF_OK = {".wslconfig", ".bat", ".cmd", ".ps1"}

SKIP_DIR = {".git", ".venv", "node_modules", "__pycache__",
            ".work", ".pytest_cache", ".ruff_cache", "data/raw"}

# ★ 생성물. 절대 손으로 고치지 않는다.
#   _manifest.json 과 segments.fingerprint.json 은 **바이트 sha256** 으로
#   계보를 대조한다. 개행 하나만 붙여도 sha 가 바뀌어 lineage 가 교착에
#   빠진다(2026-08-21 실제로 겪음). 고치려면 생성하는 코드를 고쳐야 한다.
GENERATED = ("data/processed/", "data/golden/", "data/baseline/", "web/data/")


def tracked() -> list[Path]:
    """git 이 추적하는 파일만 본다. 산출물 노이즈를 피한다."""
    try:
        out = subprocess.run(["git", "ls-files"], capture_output=True,
                             text=True, check=True).stdout
    except Exception:
        return []
    return [Path(x) for x in out.splitlines() if x]


def check(p: Path):
    """(문제 목록, 원본 바이트)."""
    try:
        b = p.read_bytes()
    except OSError:
        return [], b""
    if not b:
        return [], b
    bad = []
    if b.startswith(b"\xef\xbb\xbf"):
        bad.append("BOM")
    if b"\r\n" in b and p.name not in CRLF_OK and p.suffix not in CRLF_OK:
        bad.append("CRLF")
    try:
        b.decode("utf-8")
    except UnicodeDecodeError:
        bad.append("비UTF-8")
    if not b.endswith(b"\n"):
        bad.append("개행없음")
    return bad, b


def fix(p: Path, b: bytes) -> bool:
    if p.suffix == ".csv" and "field" in p.parts:
        p.with_suffix(p.suffix + ".bak_enc").write_bytes(b)
    n = b
    if n.startswith(b"\xef\xbb\xbf"):
        n = n[3:]
    if p.name not in CRLF_OK and p.suffix not in CRLF_OK:
        n = n.replace(b"\r\n", b"\n")
    if n and not n.endswith(b"\n"):
        n += b"\n"
    if n == b:
        return False
    p.write_bytes(n)
    return True


def main() -> int:
    do_fix = "--fix" in sys.argv
    hits, fixed = [], 0

    for p in tracked():
        if any(s in str(p) for s in SKIP_DIR):
            continue
        if p.suffix.lower() not in TEXT_EXT:
            continue
        if not p.exists():
            continue
        bad, b = check(p)
        if not bad:
            continue
        gen = str(p).startswith(GENERATED)
        hits.append((p, bad, gen))
        if do_fix and not gen and "비UTF-8" not in bad and fix(p, b):
            fixed += 1

    if not any(not g for _, _, g in hits):
        print(f"인코딩 OK — 손으로 쓰는 파일은 전부 UTF-8 · LF · 개행 있음"
              + (f" (생성물 {sum(1 for _,_,g in hits if g)}건은 대상 아님)" if hits else ""))
        return 0

    hand = [(p, b) for p, b, g in hits if not g]
    gen = [(p, b) for p, b, g in hits if g]

    if hand:
        print(f"손으로 쓰는 파일 {len(hand)}건 — 고쳐야 한다")
        for p, bad in sorted(hand):
            print(f"  {','.join(bad):16s} {p}")
    if gen:
        print(f"\n생성물 {len(gen)}건 — 손대지 마라. 생성하는 코드를 고쳐라.")
        print("  (_manifest.json · fingerprint 는 바이트 sha 로 계보를 대조한다)")
        for p, bad in sorted(gen)[:8]:
            print(f"  {','.join(bad):16s} {p}")
        if len(gen) > 8:
            print(f"  ... 외 {len(gen) - 8}건")

    if do_fix:
        print(f"\n고친 파일 {fixed}건. data/field CSV 는 .bak_enc 백업을 남겼다.")
        left = [p for p, b in hand if "비UTF-8" in b]
        if left:
            print("★ 비UTF-8 은 자동으로 안 고친다. 원본 인코딩을 확인하고 판단할 것:")
            for p in left:
                print(f"    {p}")
        return 0

    print("\n고치려면:  uv run python tools/encoding_check.py --fix")
    return 1 if hand else 0


if __name__ == "__main__":
    raise SystemExit(main())
ENC_EOF
python3 -m py_compile tools/encoding_check.py && echo "  ✓ tools/encoding_check.py"

echo
echo "── 3. 현재 상태"
python3 tools/encoding_check.py || true

echo
if [ "$FIX_BOM" -eq 1 ]; then
    echo "── 4. 정규화 실행"
    python3 tools/encoding_check.py --fix
    echo
    echo "  ★ data/field CSV 를 고쳤다면 파이프라인을 다시 돌려 확인해라."
    echo "    실측 원자료이므로 .bak_enc 백업이 남아 있다."
else
    echo "── 4. (건너뜀) 고치려면:  bash fix-encoding.sh --fix-bom"
fi

echo
echo "── 5. CI 게이트"
python3 - <<'CI'
from pathlib import Path

p = Path(".github/workflows/contract.yml")
s = p.read_text(encoding="utf-8")
if "encoding_check" in s:
    print("  · 이미 등록됨")
    raise SystemExit(0)

anchor = "      - name: 파이썬 린트"
add = """      - name: 인코딩·개행
        # ★ .gitattributes 는 커밋 시점에만 개입한다. 이미 들어온 것은
        #   못 잡는다. BOM 이 붙은 CSV 는 첫 컬럼명이 '\\ufeffw_ngi' 가
        #   되고, 그것을 아무도 모른 채 파이프라인이 돈다.
        run: python tools/encoding_check.py

"""
if anchor not in s:
    print("  ✗ 앵커 없음. contract.yml 에 수동으로 넣어라")
    raise SystemExit(1)
p.write_text(s.replace(anchor, add + anchor, 1), encoding="utf-8")
print("  ✓ contract.yml — 인코딩 검사 추가")
CI

echo
echo "── 6. .wslconfig 마지막 줄 개행"
CFG="/mnt/c/Users/${FL_WINUSER:-Fox}/.wslconfig"
if [ -f "$CFG" ] && [ -n "$(tail -c1 "$CFG")" ]; then
    printf '\r\n' >> "$CFG"
    echo "  ✓ $CFG — 개행 추가 (CRLF 유지. 윈도우가 읽는 파일이다)"
else
    echo "  · 이상 없음"
fi

git add -A
git diff --cached --quiet || {
  git commit -q -m "fix: 인코딩·개행을 경계에서 정규화하고 CI 게이트 추가

.gitattributes 가 *.py 하나뿐이라 csv·md·yaml·json 이 제각각이었다.
data/field CSV 의 BOM 때문에 첫 컬럼명이 '\\ufeffw_ngi' 로 읽히고 있었다.

계보·판정·문서는 전부 테스트로 강제하면서 인코딩만 강제자가 없었다.
tools/encoding_check.py 로 그 구멍을 막는다."
  echo
  echo "  ✓ 커밋"
}

cat <<'NEXT'

── 남은 것: ortho TIF 의 cp949 메타데이터

  매 실행 UnicodeDecodeError 4회. PLAN 은 "라이브러리 내부라 못 막고
  타일은 정상" 으로 무해 판정했다. 맞는 판정이지만 로그가 더러워
  진짜 오류를 가린다. 시도해볼 것:

      import rasterio
      with rasterio.Env(CPL_LOG="/dev/null", GDAL_PAM_ENABLED="NO"):
          ...

  GDAL 로그 핸들러를 우회하는 방향이다. 안 되면 지금처럼 두고
  PLAN 에 "무해·억제 불가" 로 못박아라 — 그게 이미 결론이었다.
NEXT
