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
    **코드**      `open` · `read_text` · `write_text` 에 `encoding=` 이 없는 자리
                  (DECISIONS §372 · 래칫 `CODE_NO_ENCODING`)

★ 2026-10-03 (§372). 넷은 **저장소 안의 파일**을 봤고 코드는 안 봤다. 파일이
  전부 UTF-8 이어도 **읽는 코드가 기계 로케일을 쓰면** 그 기계에서 터진다.
  실측 — `PYTHONUTF8=0 LC_ALL=C` 에서 기본 인코딩은 `ANSI_X3.4-1968`(ASCII)이고,
  `Path.read_text()` 가 한글 한 글자에 `UnicodeDecodeError` 를 던진다.
  지금 세 기계(WSL · CI · 컨테이너)가 전부 UTF-8 인 것은 **환경의 운**이고
  선언이 아니다. 운을 관문으로 바꾼다.

★ **`PYTHONUTF8=1` 을 안 박는다.** 그것은 가정을 숨기는 쪽이다 — 코드가
  제 인코딩을 말하게 하는 것이 고침이고, 환경변수는 덮는 것이다.

── 왜 필요한가 ────────────────────────────────────────────────
이 프로젝트는 계보(lineage) · 판정(golden) · 문서(docnum) 를 전부
테스트로 강제한다. 인코딩만 강제자가 없어서 새어 나왔다.

`.gitattributes` 는 **커밋 시점**에만 개입한다. 이미 들어온 것과
저장소 밖(.wslconfig 등)은 못 잡는다. 그래서 검사가 따로 필요하다.

★ data/field 는 실측 원자료다. raw 와 같은 등급이고 재생성이 불가하다.
  `--fix` 로 고치기 전에 반드시 백업을 남긴다(.bak_enc).
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

# 검사 대상 확장자. 정본은 firelane/encoding.py 의 TEXT_EXT_SOURCE 다.
# ★ 자료 형식이 아니라 **저장소 소스**다. encoding.TEXT_EXT 와 다른 것이 정상이다.
from firelane import gitq
from firelane.encoding import TEXT_EXT_SOURCE as TEXT_EXT
from firelane.generated import prefixes

# 예외 — 윈도우가 직접 읽는 파일은 CRLF 를 유지한다.
CRLF_OK = {".wslconfig", ".bat", ".cmd", ".ps1"}

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIR = {".git", ".venv", "node_modules", "__pycache__",
            ".work", ".pytest_cache", ".ruff_cache", "data/raw"}

# ★ 생성물. 절대 손으로 고치지 않는다.
#   _manifest.json 과 segments.fingerprint.json 은 **바이트 sha256** 으로
#   계보를 대조한다. 개행 하나만 붙여도 sha 가 바뀌어 lineage 가 교착에
#   빠진다(2026-08-21 실제로 겪음). 고치려면 생성하는 코드를 고쳐야 한다.
#   목록의 정본은 firelane/generated.py 의 역할 "encoding" 이다(W3-13).
GENERATED = prefixes("encoding")


def tracked() -> list[Path] | None:
    """git 이 추적하는 파일만 본다. 산출물 노이즈를 피한다.

    ★ 2026-10-03 (DECISIONS §372). 종전에는 `except Exception: return []` 이었다.
      그러면 git 이 없는 기계에서 **이 관문의 우주가 0 이 되고 초록이 뜬다** —
      「검사할 파일이 없다」와 「못 물었다」가 섞인 것이고, 둘 중 조용한 쪽이
      이긴다. 이제 `None` 을 돌려주고 `main()` 이 빨간불을 낸다.
    """
    return None if (t := gitq.tracked()) is None else [Path(x) for x in t]


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



# ──────────────────────────────────────────────────────────────
# 코드 쪽 — **기계 로케일을 가정하는 자리.** (DECISIONS §372)
# ──────────────────────────────────────────────────────────────
#: 이 이름으로 부르는 `open` 은 **텍스트가 아니다** — 인코딩 인자가 없거나 뜻이 다르다.
#: ★ 이 목록이 좁으면 거짓 양성이 나고, 넓으면 미탐이 난다. 미탐이 더 나쁘므로
#:   **이름을 하나씩 사유와 함께** 적는다. 짐작으로 넓히지 않는다.
NOT_TEXT = (
    "rasterio", "rio",      # 래스터. 인코딩 인자가 없다
    "Image", "PIL",         # 그림
    "zipfile", "tarfile",   # 묶음 — 언제나 이진
    "gzip", "bz2", "lzma",  # 압축 — 기본이 이진
    "h5py", "fiona", "np", "numpy", "shapefile", "sqlite3", "cv2",
)
#: 묶음 핸들의 흔한 지역명. `z.open(name)` 은 **모드 인자가 없어도 이진**이다.
ARCH_RECV = ("z", "zf", "zip", "tar")

#: 인코딩을 안 적은 텍스트 IO. **0 이 목표다.**
#: ★ 이력 — 2026-10-03 §372 첫 실측 37 → 그 배치가 전부 고쳐 0.
CODE_NO_ENCODING = 0

RATCHETS = {"CODE_NO_ENCODING": "down"}


def _const(x):
    return x.value if isinstance(x, ast.Constant) else None


def _mode(call: ast.Call, builtin: bool) -> str:
    """모드 문자열. **빌트인 `open` 은 두 번째 · `Path.open` 은 첫 번째다.**

    ★ 이 한 칸이 거짓 양성 일곱을 만들었다 — `p.open("rb")` 를 텍스트로 셌다.
    """
    i = 1 if builtin else 0
    if len(call.args) > i and isinstance(_const(call.args[i]), str):
        return _const(call.args[i])
    for k in call.keywords:
        if k.arg == "mode" and isinstance(_const(k.value), str):
            return _const(k.value)
    return ""


def _has_encoding(call: ast.Call, name: str, builtin: bool) -> bool:
    """인코딩이 **위치 인자로** 올 수 있다.

    ★ `read_text("utf-8")` 은 **인코딩을 준 것**이다(첫 인자가 encoding).
      키워드만 보면 이것을 결함으로 센다 — 실측에서 둘이 그렇게 세어졌다.
    """
    if any(k.arg == "encoding" for k in call.keywords):
        return True
    pos = {"read_text": 0, "write_text": 1, "open": (3 if builtin else 2)}[name]
    return len(call.args) > pos and _const(call.args[pos]) is not None


def code_hits(files: list[str] | None = None) -> list[tuple[str, int, str]]:
    """`encoding=` 없는 텍스트 IO 의 (경로, 줄, 갈래)."""
    if files is None:
        t = gitq.tracked(ROOT)
        if t is None:
            raise RuntimeError("git 이 추적 목록을 못 줬다 — 우주를 못 정한다(§372)")
        files = sorted(f for f in t
                       if f.endswith(".py") and f.split("/")[0] in ("src", "tools", "tests"))
    out = []
    for f in files:
        try:
            src = (ROOT / f).read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            fn = n.func
            if isinstance(fn, ast.Attribute):
                name, recv, builtin = fn.attr, ast.unparse(fn.value), False
            elif isinstance(fn, ast.Name):
                name, recv, builtin = fn.id, "", True
            else:
                continue
            if name not in ("open", "read_text", "write_text"):
                continue
            if name == "open":
                head = recv.split(".")[0].split("(")[0]
                if head in NOT_TEXT or head in ARCH_RECV:
                    continue
                if "ZipFile" in recv or "TarFile" in recv:
                    continue
                if "b" in _mode(n, builtin):
                    continue
            if _has_encoding(n, name, builtin):
                continue
            out.append((f, n.lineno, name))
    return out


def ratchet_values() -> dict[str, int]:
    return {"CODE_NO_ENCODING": len(code_hits())}


def code_check() -> int:
    hits = code_hits()
    print(f"  코드 텍스트 IO — 인코딩 없음 {len(hits)}  (래칫 {CODE_NO_ENCODING})")
    if len(hits) > CODE_NO_ENCODING:
        for f, ln, nm in hits:
            print(f"    ✗ {f}:{ln}  [{nm}]")
        print("  ★ 기계 로케일이 UTF-8 이 아니면 **여기서 터진다.** 한글이 들어가는")
        print("    자리면 `UnicodeDecodeError` · `UnicodeEncodeError` 다.")
        print('    고침은 `encoding="utf-8"` 한 인자다.')
        return 1
    if len(hits) < CODE_NO_ENCODING:
        print(f"  ✗ 줄었다 — {__file__} 의 CODE_NO_ENCODING 을 {len(hits)} 로 조여라")
        return 1
    return 0


SELFTEST = [
    # ★ 거짓 양성 — 실측에서 **실제로 걸렸던** 꼴들이다
    ('p.open("rb")', False, "Path.open 의 모드는 **첫 인자**다"),
    ('open(f, "rb")', False, "빌트인 open 의 모드는 두 번째 인자다"),
    ('p.read_text("utf-8")', False, "read_text 의 첫 인자가 encoding 이다"),
    ('p.write_text(s, "utf-8")', False, "write_text 의 **두 번째**가 encoding 이다"),
    ('rasterio.open(f)', False, "래스터는 텍스트가 아니다"),
    ('Image.open(f)', False, "그림은 텍스트가 아니다"),
    ('z.open(name)', False, "묶음 핸들의 open 은 모드 인자가 없어도 이진이다"),
    ('tarfile.open(p)', False, "묶음은 이진이다"),
    # ★ 미탐 — 이쪽이 더 나쁘다
    ('p.read_text()', True, "인코딩 없는 read_text 를 안 센다"),
    ('p.write_text(s)', True, "인코딩 없는 write_text 를 안 센다"),
    ('open(p, "w")', True, "인코딩 없는 텍스트 open 을 안 센다"),
    ('open(p)', True, "기본 모드(텍스트) open 을 안 센다"),
    ('(d / "x.json").write_text(j)', True, "괄호 안 수식을 받는 자리를 안 센다"),
    ('p.open("w")', True, "인코딩 없는 Path.open 텍스트 모드를 안 센다"),
    # ★ 키워드로 준 것은 센 것이 아니다
    ('p.read_text(encoding="utf-8")', False, "키워드 encoding 을 결함으로 센다"),
    ('open(p, "w", encoding="utf-8")', False, "키워드 encoding 을 결함으로 센다"),
]


def code_selftest() -> int:
    """★ 판별식이 **거짓 양성과 미탐을 둘 다** 가르는가."""
    import tempfile
    bad = []
    with tempfile.TemporaryDirectory() as d:
        for i, (expr, want, why) in enumerate(SELFTEST):
            f = Path(d) / f"c{i}.py"
            f.write_text(f"def f(p, f, s, j, d, name, z, tarfile, rasterio, Image):\n    {expr}\n",
                         encoding="utf-8")
            got = bool(_hits_of(f))
            if got is not want:
                bad.append(f"{why} — {expr!r} (기대 {want} · 실제 {got})")
    # ★ 빈 그물 — 실물에서 파일을 못 읽으면 래칫이 늘 0 이다
    t = gitq.tracked(ROOT)
    if t is None or sum(1 for f in t if f.endswith(".py")) < 100:
        bad.append("추적된 파이썬 파일이 100개 미만이다 — 우주가 비었다")
    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 코드 인코딩 판별식 {len(SELFTEST) + 1}")
    return 1 if bad else 0


def _hits_of(path: Path) -> list:
    """한 파일만 — 자기검사용. `code_hits` 와 **같은 판별식**을 쓴다."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        if isinstance(fn, ast.Attribute):
            name, recv, builtin = fn.attr, ast.unparse(fn.value), False
        elif isinstance(fn, ast.Name):
            name, recv, builtin = fn.id, "", True
        else:
            continue
        if name not in ("open", "read_text", "write_text"):
            continue
        if name == "open":
            head = recv.split(".")[0].split("(")[0]
            if head in NOT_TEXT or head in ARCH_RECV:
                continue
            if "ZipFile" in recv or "TarFile" in recv:
                continue
            if "b" in _mode(n, builtin):
                continue
        if _has_encoding(n, name, builtin):
            continue
        out.append((path.name, n.lineno, name))
    return out

def main() -> int:
    # ★ 2026-09-24 (PLAN §13 W13-6 · DECISIONS §243). 종전에는 `"--x" in sys.argv`
    #   였다 — **오타가 조용히 무시된다.** `--fx` 는 고치는 대신 대조만 하고 통과했다.
    #   argparse 는 모르는 인자에 스스로 운다. 직접 구현할 일이 아니다(4족).
    ap = argparse.ArgumentParser(description="인코딩 위생 — 대조 또는 교정")
    ap.add_argument("--fix", action="store_true", help="찾은 것을 고친다")
    ap.add_argument("--selftest", action="store_true", help="판별식이 사는가")
    a = ap.parse_args()
    if a.selftest:
        return code_selftest()
    do_fix = a.fix
    hits, fixed = [], 0

    files = tracked()
    if files is None:
        print("✗ git 이 추적 목록을 못 줬다 — **이 검사의 우주가 비었다.**")
        print("  빈 우주는 초록이 아니다. git 이 있고 저장소 안인지 보라 —")
        print("    git rev-parse --is-inside-work-tree")
        print("  (컨테이너는 `.git` 을 안 담는다. 그 기계에서는 이 검사를 안 돈다)")
        return 1
    if not files:
        print("✗ 추적 파일이 0건이다 — 빈 커밋이 아니면 저장소를 의심하라")
        return 1

    for p in files:
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

    # ★ §372. **파일 축과 코드 축을 한 판정에 묶는다.** 따로 돌리면 둘 중
    #   하나는 안 돌고, 안 도는 관문은 없는 관문이다.
    rc_code = code_check()

    if not any(not g for _, _, g in hits):
        print("인코딩 OK — 손으로 쓰는 파일은 전부 UTF-8 · LF · 개행 있음"
              + (f" (생성물 {sum(1 for _,_,g in hits if g)}건은 대상 아님)" if hits else ""))
        return rc_code

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
        # ★ §372. `--fix` 도 **코드 축의 판정은 그대로 들고 나간다** — 이 문은
        #   코드에 `encoding=` 을 안 넣는다(인자를 넣는 일은 호출마다 뜻이 달라
        #   기계적으로 답이 하나가 아니다). 고칠 것을 적어 주고 종료코드로 말한다.
        return rc_code

    print("\n고치려면:  uv run python tools/encoding_check.py --fix")
    return 1 if (hand or rc_code) else 0


if __name__ == "__main__":
    raise SystemExit(main())
