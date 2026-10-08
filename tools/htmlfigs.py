#!/usr/bin/env python3
"""
htmlfigs.py — **생성 그림을 기획서 화면 자리에 바로 굽는다.** docx 를 안 거친다.

    uv run python tools/htmlfigs.py --check     자리의 그림이 정본과 같은가
    uv run python tools/htmlfigs.py --sync      다시 구워 앉힌다 (변환기 필요)
    uv run python tools/htmlfigs.py --selftest  ★ 판정기가 살아 있나

── 왜 생겼나 (2026-10-09 · DECISIONS §440 · PLAN #142) ─────────
기획서 정본이 `docs/proposal.md` 로 옮겨졌고(§425) 화면은 그 md 와
`web/proposal/fig/*.png` 스물넷으로 굽는다. 그런데 **그 스물넷 중 다섯이
코드가 만드는 그림**이고, 지금까지 그 다섯은 이 길로 갔다 —

```
figures/*.py → SVG → docx_figs --sync → docs/proposal.docx → (사람) → fig??.png
```

**정본이 md 인데 생성 그림은 docx 를 거쳐서 왔다.** 그래서 docx 를 은퇴시키려면
(`#142`) 이 다리를 먼저 놓아야 한다. 안 놓고 지우면 다섯 그림이 **영원히 옛
값으로 굳는다** — 값이 바뀌어도 아무도 모른다. §236 이 폐기된 반경 5m 원을
석 주 동안 그리고 있던 자리와 같다.

── 무엇을 보는가 ───────────────────────────────────────────────
`SLOT` 이 든 다섯만. **나머지 열아홉은 안 본다** — 정본이 없는 래스터이고
그쪽은 `docx_figs.SOURCELESS_MAX` 가 세던 수다(그 수도 §440 이 옮긴다).

★ **비교는 바이트가 아니라 SVG 지문이다.** PNG 는 변환기 판·글꼴·압축에 따라
  바이트가 달라진다. 바이트로 대면 기계가 바뀔 때마다 빨갛고, 그러면 사람이
  검사를 끈다(§411 의 그 교훈). 그래서 **구운 원본 SVG 의 지문**을 잠금 파일에
  적고 그것을 댄다 — `docs/figures/.lock.json` 과 같은 규약이다.

IN    tools/render_figures.FIGURES · web/proposal/fig/*.png · LOCK
OUT   web/proposal/fig/fig??.png · LOCK   (`--sync` 일 때만)
PARAM SLOT · WIDTH
밖    **열아홉 장은 안 본다**(정본이 없다). **md 본문이 그 자리를 가리키는가도
      안 본다** — `tools/build_proposal.py --check` 소관이다. 그림이 **옳은가**도
      안 본다 — 그리는 쪽(`tools/figures/*.py`)과 그 시험이 든다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import render_figures

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "web" / "proposal" / "fig"
LOCK = FIG / ".lock.json"

#: 생성 그림 → 기획서 화면의 자리 번호. **`docx_figs.PLACE` 와 같은 수여야
#: 한다** — 같은 그림이 두 곳에 가는 동안은 번호가 갈리면 안 된다. 도구가
#: 그것을 본다(`selftest`). docx 가 은퇴하면 그 대조는 사라지고 이 표만 남는다.
SLOT: dict[str, int] = {
    "boundary": 8,
    "xsec": 13,
    "verdict_flow": 14,
    "cctv": 22,
    "deploy": 24,
}

#: 굽는 가로 픽셀. 화면이 1x 로 띄우고 인쇄가 2x 를 쓰므로 넉넉히 둔다.
WIDTH = 1600

#: SVG → PNG 변환기. 앞의 것부터 있는 것을 쓴다 — `docx_figs` 와 같은 목록이고
#: 같은 사유다(파이썬 의존성을 안 늘린다 · `--check` 는 변환기 없이 돈다).
CONVERTERS = (
    ("rsvg-convert", lambda exe, src, out, w: [exe, "-w", str(w), str(src), "-o", str(out)]),
    ("inkscape", lambda exe, src, out, w: [exe, str(src), "--export-type=png",
                                           f"--export-width={w}", f"--export-filename={out}"]),
    ("magick", lambda exe, src, out, w: [exe, "-density", "288", str(src),
                                         "-resize", f"{w}x", str(out)]),
)
APT = "sudo apt-get install -y librsvg2-bin"


def slot_path(n: int) -> Path:
    return FIG / f"fig{n:02d}.png"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def svgs() -> dict[str, str]:
    """이름 → SVG 본문. **함수에서 낸다** — 파일이 낡아도 대조가 산다."""
    fns = render_figures.FIGURES
    return {n: fns[n]() for n in SLOT if n in fns}


def locked() -> dict[str, str]:
    if not LOCK.is_file():
        return {}
    return json.loads(LOCK.read_text(encoding="utf-8")).get("placed", {})


def drift() -> list[str]:
    """자리마다 **지금 그림의 지문**이 잠긴 것과 같은가. 판정은 안 한다."""
    was, out = locked(), []
    for name, body in svgs().items():
        n = SLOT[name]
        p = slot_path(n)
        if not p.is_file():
            out.append(f"fig{n:02d}.png 이 없다 — {name}")
        elif was.get(name) != sha(body):
            out.append(f"fig{n:02d}.png  {name} 가 정본과 다르다 "
                       f"(잠김 {was.get(name, '없음')} ≠ 지금 {sha(body)})")
    return out


def _converter() -> tuple[str, object] | None:
    for exe, argv in CONVERTERS:
        path = shutil.which(exe)
        if path:
            return path, argv
    return None


def png(body: str, width: int = WIDTH) -> bytes:
    conv = _converter()
    if conv is None:
        raise SystemExit(
            "★ SVG → PNG 변환기가 없다 — `--sync` 는 이것 하나가 필요하다.\n"
            f"  {APT}\n  (`--check` 는 변환기 없이 돈다.)")
    exe, argv = conv
    with tempfile.TemporaryDirectory() as d:
        src, out = Path(d) / "f.svg", Path(d) / "f.png"
        src.write_text(body, encoding="utf-8")
        r = subprocess.run(argv(exe, src, out, width),  # noqa: S603 — 목록 안의 변환기다
                           capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            raise SystemExit(f"★ {Path(exe).name} 변환 실패 — {r.stderr.strip()[:300]}")
        return out.read_bytes()


def sync() -> int:
    """다시 구워 앉히고 잠금을 고쳐 적는다."""
    was = dict(locked())
    moved = []
    for name, body in svgs().items():
        n = SLOT[name]
        p = slot_path(n)
        if was.get(name) == sha(body) and p.is_file():
            print(f"  [그림 {n}] {name} — 이미 같다")
            continue
        p.write_bytes(png(body))
        was[name] = sha(body)
        moved.append(f"[그림 {n}] {name}")
    LOCK.write_text(json.dumps({"placed": was}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    if moved:
        print("교체 " + " · ".join(moved))
        print("★ 기획서 화면이 바뀌었다 — web/proposal/fig 와 그 잠금을 커밋해라")
    else:
        print("바꿀 그림이 없다 — 화면이 이미 정본과 같다")
    return 0


def check() -> int:
    bad = drift()
    if bad:
        print("★ 기획서 화면의 그림이 정본과 어긋난다\n  " + "\n  ".join(bad))
        print("  uv run python tools/htmlfigs.py --sync")
        return 1
    print(f"기획서 화면 그림 OK — 생성 {len(SLOT)}장이 정본과 같다 "
          f"(정본 없는 19장은 대상이 아니다)")
    return 0


def selftest() -> int:
    bad: list[str] = []
    # ★ 빈 그물 — 자리가 비면 무엇을 해도 통과한다
    if not SLOT:
        bad.append("자리 표가 비었다")
    got = svgs()
    if set(got) != set(SLOT):
        bad.append(f"그리는 쪽에 없는 이름이 있다 — {sorted(set(SLOT) - set(got))}")

    # ★ **같은 그림이 두 곳에 가는 동안은 번호가 갈리면 안 된다.**
    #   docx 가 은퇴하면 이 대조가 사라지고 `SLOT` 만 남는다(§440).
    try:
        import docx_figs  # noqa: PLC0415  은퇴 전까지만 있는 짝이다
    except Exception:                       # noqa: BLE001 — 은퇴하면 없는 것이 정상이다
        pass
    else:
        for name, n in SLOT.items():
            want = (docx_figs.PLACE.get(name) or {}).get("fig")
            if want is not None and want != n:
                bad.append(f"{name} 의 자리가 갈린다 — 여기 {n} · docx_figs {want}")

    # ★ 지문이 **내용을 따라 움직이는가.** 안 움직이면 대조가 장식이다.
    if sha("a") == sha("b"):
        bad.append("지문이 내용을 안 따른다")
    with tempfile.TemporaryDirectory() as d:
        probe = Path(d) / "x.png"
        probe.write_bytes(b"x")
        if probe.read_bytes() != b"x":
            bad.append("임시 파일을 못 쓴다")

    # ★ 음성 대조 — 잠금이 비면 **전부 어긋난 것**으로 나와야 한다
    real = LOCK.read_text(encoding="utf-8") if LOCK.is_file() else None
    try:
        LOCK.write_text('{"placed": {}}', encoding="utf-8")
        if len(drift()) != len(SLOT):
            bad.append("잠금이 비었는데 어긋남이 자리 수와 다르다 — 그물이 샌다")
    finally:
        if real is None:
            LOCK.unlink(missing_ok=True)
        else:
            LOCK.write_text(real, encoding="utf-8")

    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 자리 {len(SLOT)} · 지문 · 음성 대조")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.sync:
        return sync()
    return check()


if __name__ == "__main__":
    sys.exit(main())
