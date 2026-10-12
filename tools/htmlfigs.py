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
`SLOT` 이 든 다섯의 **내용**만. 나머지 열아홉은 정본이 없는 래스터라 내용을
못 대지만 **수는 센다** — `SOURCELESS_MAX` 양방향 래칫이고, 2026-10-09 에
`docx_figs` 에서 이리로 왔다(§444). 세는 자리가 docx 였고 이제 화면 캡션이다.

★ **비교는 바이트가 아니라 SVG 지문이다.** PNG 는 변환기 판·글꼴·압축에 따라
  바이트가 달라진다. 바이트로 대면 기계가 바뀔 때마다 빨갛고, 그러면 사람이
  검사를 끈다(§411 의 그 교훈). 그래서 **구운 원본 SVG 의 지문**을 잠금 파일에
  적고 그것을 댄다 — `docs/figures/.lock.json` 과 같은 규약이다.

IN    tools/render_figures.FIGURES · web/proposal/fig/*.png · LOCK · docs/proposal.md (캡션)
OUT   web/proposal/fig/fig??.png · LOCK   (`--sync` 일 때만)
PARAM SLOT · WIDTH · SOURCELESS_MAX
밖    **열아홉 장은 안 본다**(정본이 없다). **md 본문이 그 자리를 가리키는가도
      안 본다** — `tools/build_proposal.py --check` 소관이다. 그림이 **옳은가**도
      안 본다 — 그리는 쪽(`tools/figures/*.py`)과 그 시험이 든다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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

#: 정본이 **없는** 그림 수의 상한. 저장소 밖에서 그려 손으로 붙인 래스터들이다.
#:
#: ★ 2026-09-28 (DECISIONS §278-4) 21 에서 시작했다. 「모든 그림은 표에 선언돼야
#:   한다」는 강제가 **코드가 그리는 것**에만 걸렸고, 손으로 붙인 그림은 애초에
#:   대장 밖이라 아무도 안 봤다 — [그림 8] 이 라벨 둘을 겹쳐 찍은 채 제출본에
#:   살아 있었다(검사 59개가 전부 초록인 채로). 21 → 20([그림 8] · §278-4)
#:   → **19**([그림 14] · §281-1).
#: ★ 2026-10-09 (DECISIONS §444 · PLAN #142). `docx_figs.SOURCELESS_MAX` 에서
#:   왔다. 이 파일 머리말이 「그 수도 §440 이 옮긴다」고 적어 둔 그 수다 —
#:   세는 자리가 docx 였고 이제 **화면 캡션**이다. 수는 그대로 19 다.
SOURCELESS_MAX = 19

#: 캡션 줄. `docs/proposal.md` 가 `[그림 N] …` 꼴로 적는다.
CAP = re.compile(r"^\[?그림\s*(\d+)\]?")

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


def captions(txt: str | None = None) -> set[int]:
    """기획서 정본이 드는 그림 번호 전부. **없으면 빈 집합이 아니라 예외다.**"""
    if txt is None:
        md = ROOT / "docs" / "proposal.md"
        if not md.is_file():
            raise SystemExit(f"★ {md} 가 없다 — 기획서 정본이 사라졌다")
        txt = md.read_text(encoding="utf-8")
    return {int(m.group(1)) for ln in txt.splitlines()
            if (m := CAP.match(ln.strip()))}


def sourceless(caps: set[int] | None = None) -> list[int]:
    """캡션에는 있는데 `SLOT` 이 안 대는 그림 번호. **고칠 수 없는 것들이다.**"""
    return sorted((captions() if caps is None else caps) - set(SLOT.values()))


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


def sourceless_faults(n: int, limit: int = SOURCELESS_MAX) -> list[str]:
    """양방향 래칫. 줄었는데 기록을 안 내리면 **느슨해진 래칫이 초록으로 위장한다.**"""
    if n > limit:
        return [f"정본 없는 그림이 {n} 장 — 기록 {limit} 보다 늘었다. "
                "저장소 밖에서 그린 그림은 **고칠 수가 없다** — 겹치거나 낡아도 "
                "다시 그리는 수밖에 없다. `render_figures.FIGURES` 에 그리는 "
                "함수를 얹고 `SLOT` 에 한 줄을 달아라"]
    if n < limit:
        return [f"정본 없는 그림이 {n} 장으로 줄었다 — "
                f"tools/htmlfigs.py 의 SOURCELESS_MAX 를 {n} 으로 조여라"]
    return []


def check() -> int:
    bad = drift() + sourceless_faults(len(sourceless()))
    if bad:
        print("★ 기획서 화면의 그림이 정본과 어긋난다\n  " + "\n  ".join(bad))
        print("  uv run python tools/htmlfigs.py --sync")
        return 1
    print(f"기획서 화면 그림 OK — 생성 {len(SLOT)}장이 정본과 같다 "
          f"(정본 없는 {SOURCELESS_MAX}장은 대상이 아니고 그 수가 래칫이다)")
    return 0


def selftest() -> int:
    bad: list[str] = []
    # ★ 빈 그물 — 자리가 비면 무엇을 해도 통과한다
    if not SLOT:
        bad.append("자리 표가 비었다")
    got = svgs()
    if set(got) != set(SLOT):
        bad.append(f"그리는 쪽에 없는 이름이 있다 — {sorted(set(SLOT) - set(got))}")

    # ★ 2026-10-09 (DECISIONS §444 · PLAN #142). **그 대조가 사라졌다** —
    #   §440 이 「docx 가 은퇴하면 이 대조가 사라지고 `SLOT` 만 남는다」고 적어
    #   둔 그대로다. 같은 그림이 두 곳에 가던 동안은 번호가 갈릴 수 있었고,
    #   이제 가는 곳이 하나뿐이라 갈릴 자리가 없다.
    # ★ **자리 번호가 캡션과 같은가**는 아래 `sourceless` 축이 든다 —
    #   `SLOT` 이 안 대는 번호가 몇 개인지를 세므로, 번호를 잘못 적으면
    #   그 수가 움직인다.

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

    # ★ 정본 없는 그림의 **양방향 래칫**. 합성 입력으로만 민다.
    if not sourceless_faults(SOURCELESS_MAX + 1):
        bad.append("정본 없는 그림이 늘었는데 안 운다")
    if not sourceless_faults(SOURCELESS_MAX - 1):
        bad.append("정본 없는 그림이 줄었는데 안 운다 — 느슨한 래칫은 지난 기록이다")
    if sourceless_faults(SOURCELESS_MAX):
        bad.append("기록과 같은데 운다")
    # ★ 캡션 파서 — **번호를 못 읽으면 `sourceless` 가 통째로 거짓이 된다.**
    if captions("[그림 7] 가\n그림 8 나\n본문 그림 이야기\n") != {7, 8}:
        bad.append("캡션에서 그림 번호를 못 읽는다")
    if sourceless({*SLOT.values(), 99}) != [99]:
        bad.append("자리 밖 그림을 못 고른다")
    if sourceless(set(SLOT.values())) != []:
        bad.append("자리 안 그림을 정본 없음으로 센다")

    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 자리 {len(SLOT)} · 지문 · 음성 대조"
          f" · 정본 없음 {SOURCELESS_MAX} 양방향")
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


#: ★ 래칫을 도구가 스스로 조인다(§309). 선언이 실측과 같은가는 `ratchet.py` 가 본다.
RATCHETS = {"SOURCELESS_MAX": "down"}


def ratchet_values() -> dict[str, int]:
    """**재기만 한다** — 판정은 `sourceless_faults` 가 든다."""
    return {"SOURCELESS_MAX": len(sourceless())}
