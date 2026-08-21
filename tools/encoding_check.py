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
