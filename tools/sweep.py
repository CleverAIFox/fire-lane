#!/usr/bin/env python3
"""
sweep.py — **스캔 → 검증 → 정리.** 근거 있는 것만 지운다.

    uv run python tools/sweep.py               스캔·판정만 (아무것도 안 지운다)
    uv run python tools/sweep.py --sweep       지울 것을 보여준다
    uv run python tools/sweep.py --sweep --yes 실제로 지운다

환경변수는 **이미 쓰던 것**을 그대로 쓴다. 새로 만들지 않는다.

    FIRE_LANE_DATA    레이크 (raw · norm · landing · _quarantine · interim)
    FIRE_LANE_INBOX   윈도우 다운로드 폴더

★ 왜 필요한가. `intake` 가 자기 출력에 이렇게 적는다 —

      ★ 다운로드 폴더의 원본은 지우지 않았다. **정리는 사람이 한다.**

  그게 결함이다. 파이프라인이 반입까지만 하고 뒷정리를 떠넘기니 원본이
  쌓이고, 다음 도구가 그걸 또 옮기려 하고, 그러다 죽는다(cross-device).
  **삭제도 파이프라인의 일이다.** 단 근거 없이는 안 지운다.

판정 넷. 근거가 대장에 있는 것만 지운다.

    반입 완료   sha 가 레이크에 있다        → 지운다
    판단 완료   retired 대장에 있다          → 지운다
    보류        landing_disposition held     → 남긴다
    미판단      어디에도 없다                → 남긴다. 먼저 대장에 적어라

레이크 안도 같은 원리로 본다 —

    landing     raw 에 sha 가 있으면 반입 끝났다 → 지운다
    interim     재생성 가능(layers 선언) → 오래된 것 보고만 한다
    _quarantine lakecheck L2 소관이라 여기서 안 건드린다
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

from firelane import (
    ledger,
    paths,  # noqa: F401  ★ import 만으로 .env 를 환경에 얹는다
)

ROOT = Path(__file__).resolve().parents[1]
JUNK = {".tmp", ".crdownload", ".part", ".partial"}

# ★ 데이터 확장자만 판정한다. 다운로드 폴더에는 스크립트·설정 파일도
#   섞이는데 그것까지 "미판단" 으로 내면 목록이 시끄러워지고, 시끄러우면
#   사람이 검사를 끈다. lakecheck L3 와 같은 어휘를 쓴다.
DATA_EXT = {".zip", ".7z", ".csv", ".json", ".shp", ".gpkg", ".tif",
            ".hwp", ".hwpx", ".xls", ".xlsx", ".txt", ".dbf", ".pdf", ".xml"}


#: 읽다 실패한 파일 — 사유와 함께. 비어야 통과다.
UNREAD: list[tuple[str, str]] = []

#: 레이크 지문 **북마크**.  (§258-17)
#:
#: ★ 2026-09-26. 종전에는 매 실행 2.5GB 를 처음부터 다시 해싱했다(30~90초).
#:   이 저장소는 이미 「안 바뀐 것은 다시 안 한다」를 샤드 봉인으로 하고 있는데
#:   **여기만 그 원리가 없었다** — ENOMEM 을 버퍼 크기로 때운 것이 그 증상이다.
#:   증상을 고치기 전에 「왜 2.5GB 를 매번 읽나」를 물었어야 했다.
#:
#: ★ 샤드 봉인의 `seal.raw` 는 **데이터셋 단위 집계 지문 하나**라 여기 못 쓴다 —
#:   sweep 이 묻는 것은 「이 파일 하나가 레이크 어디에 있나」이고 그것은 파일별
#:   해시를 요구한다. 그래서 같은 원리로 **파일별 북마크**를 따로 둔다.
#:
#: ★ 무효 조건은 **크기와 mtime_ns** 다. 둘 중 하나라도 다르면 다시 판다.
#:   내용이 같은데 mtime 만 바뀌면 헛일을 한 번 하지만 그것은 안전한 쪽이다 —
#:   반대(내용이 바뀌었는데 재사용)는 「지워도 된다」를 거짓으로 만든다.
FP_CACHE = ROOT / ".work" / "lake_fp.json"


def _fp_load() -> dict[str, list]:
    try:
        return json.loads(FP_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}          # 없거나 깨졌으면 전부 다시 판다 — 조용히 비어도 안전하다


def fp_valid(was: list | None, size: int, mtime_ns: int) -> bool:
    """북마크를 **재사용해도 되는가.** 이 한 줄이 이 기능의 전부다.

    ★ 판단을 이름 있는 자리로 뺀 이유. 처음 판은 이 비교를 `main` 루프 안에
      인라인으로 뒀고, 시험은 `_fp_load`/`_fp_save` 만 쟀다. 그래서 **「mtime 을
      무시하고 무조건 재사용」 주입이 안 잡혔다** — 헬퍼만 재고 판단을 안 쟀다.
      이 저장소가 반복한 형태다(§258-10 의 배선 미검사와 같다).

    ★ **안전한 쪽이 어느 쪽인지가 비대칭이다.** 내용이 같은데 mtime 만 바뀌면
      헛일을 한 번 한다 — 느릴 뿐이다. 반대로 내용이 바뀌었는데 재사용하면
      sweep 이 「이 파일은 레이크에 이미 있다 = 지워도 된다」를 **거짓으로**
      말하고, 지우는 것은 되돌릴 수 없다. 그래서 의심스러우면 다시 판다.
    """
    return bool(was) and list(was[:2]) == [size, mtime_ns]


def _fp_save(fp: dict[str, list]) -> None:
    try:
        FP_CACHE.parent.mkdir(parents=True, exist_ok=True)
        FP_CACHE.write_text(json.dumps(fp) + "\n", encoding="utf-8")
    except OSError:
        pass               # 못 써도 다음 실행이 느려질 뿐이다. 판단은 안 바뀐다


def sha(p: Path, *, chunks=(1 << 18, 1 << 15)) -> str | None:
    """파일의 sha256. **못 읽으면 None 을 내고 `UNREAD` 에 적는다.**

    ★ 2026-09-26 (§258-15). 종전에는 1MB 씩 읽었고, 외장 SSD 가 붙은
      `/mnt/` (DrvFs) 에서 `OSError: [Errno 12] Cannot allocate memory` 로
      **트레이스백을 내며 죽었다.** 실기에서 사흘 연속 같은 자리였다.
      진짜 메모리 부족이 아니다 — 그때 스왑은 16GB 중 377MB 만 쓰고 있었다.
      DrvFs 가 큰 읽기 버퍼를 호스트 쪽에 못 맵핑할 때 나는 오류다.

    ★ **두 가지를 고친다.**
      ㉠ 버퍼를 256KB 로 줄이고, 그래도 실패하면 32KB 로 한 번 더 시도한다.
      ㉡ 그래도 못 읽으면 **어느 파일인지 적고 넘어간다.** 종전 트레이스백은
         파일 이름을 한 글자도 안 냈다 — 사흘 동안 무엇이 안 읽히는지 몰랐다.

    ★ 넘어가되 **조용히 넘어가지 않는다.** `UNREAD` 가 비지 않으면 `main` 이
      빨갛게 끝낸다. 못 읽은 원본을 「레이크에 없다」로 세면 그 다음 판단
      (중복인가 · 지워도 되는가)이 전부 거짓이 된다.
    """
    for n in chunks:
        h = hashlib.sha256()
        try:
            with open(p, "rb") as f:
                for b in iter(lambda n=n: f.read(n), b""):
                    h.update(b)
            return h.hexdigest()
        except OSError as e:
            last = f"{type(e).__name__}: {e}"
    UNREAD.append((str(p), last))
    return None


def led() -> dict:
    return ledger.load_sources()


def torn_down(y: dict, root: Path = ROOT) -> list[tuple[Path, str, str]]:
    """**철거된 산출물**이 디스크에 남아 있는가. 대장 `retired_outputs` 가 근거다.

    ★ 2026-09-29 (DECISIONS §305). `processed` 를 통째로 훑지 않는다 — 그쪽을
      무는 것은 `tests/test_ledger_outputs.py::test_no_undeclared_output` 이고,
      여기서 또 판단하면 「대장에 없다」의 뜻이 두 집에 산다(R3). 이 함수는
      **철거를 선언한 경로만** 본다. 선언 밖은 안 지운다.

    `root` 는 시험이 임시 트리를 가리키게 하는 자리다 — 저장소를 건드리지 않고
    이 판정을 잴 수 있어야 한다.

    ★ 왜 sweep 이 하나. 단계를 철거하면 그 단계가 예전에 만든 파일이 **기계마다
      남는다.** 배치 K 가 71/72 로 죽은 원인이고(내 기계엔 그 파일이 없어서
      초록이었다), 네 파트 기계가 각자 같은 파일을 들고 있다. 사람이 `rm` 을
      기억할 일이 아니다 — 「삭제도 파이프라인의 일이다」가 이 도구의 전제다.
    """
    out: list[tuple[Path, str, str]] = []
    for k, v in (y.get("retired_outputs") or {}).items():
        if not isinstance(v, dict) or not v.get("path"):
            continue
        q = root / str(v["path"])
        if q.is_file():
            out.append((q, "판단 완료", f"retired_outputs.{k} · {v.get('decided', '?')}"))
    return out


def retired_names(y: dict) -> dict[str, str]:
    """폐기 대장이 지목하는 이름 → 항목 키.

    ★ `origin_name`(취득처가 준 이름) · `stem`(우리가 정한 이름) ·
      `file`/`files`(경로) 셋 다 본다. 하나만 보면 못 잡는 것이 생긴다 —
      2026-09-10 에 `intake` 가 정확히 그래서 retired 를 통째로 놓쳤다.
    """
    out: dict[str, str] = {}
    for k, v in (y.get("retired") or {}).items():
        if not isinstance(v, dict):
            continue
        if v.get("origin_name"):
            out[str(v["origin_name"])] = k
        for f in ([v["file"]] if v.get("file") else []) + (v.get("files") or []):
            out[Path(str(f)).name] = k
        if v.get("stem"):
            out[f"stem::{v['stem']}"] = k
    return out


def held_names(y: dict) -> dict[str, str]:
    """`landing_disposition` 에 적힌 처분. **보류도 처분이다.**"""
    out: dict[str, str] = {}
    for it in ((y.get("landing_disposition") or {}).get("items") or []):
        if isinstance(it, dict) and it.get("file"):
            out[str(it["file"])] = str(it.get("action", "?"))
    return out


def judge(p: Path, lake_sha: dict[str, Path], ret: dict[str, str],
          held: dict[str, str]) -> tuple[str, str, bool]:
    """(판정, 근거, 지워도 되나)"""
    if p.suffix.lower() in JUNK:
        return "찌꺼기", "다운로드 중단 파일", True
    h = sha(p)
    if h in lake_sha:
        return "반입 완료", f"sha 일치 — {lake_sha[h]}", True
    if p.name in ret:
        return "판단 완료", f"retired.{ret[p.name]}", True
    stem = p.stem
    for key, k in ret.items():
        if key.startswith("stem::") and stem.startswith(key[6:]):
            return "판단 완료", f"retired.{k} (stem)", True
    if p.name in held:
        a = held[p.name]
        return ("보류", f"landing_disposition action={a}", False) if a == "held" \
            else (f"처분 {a}", f"landing_disposition action={a}", a == "retired")
    return "미판단", "대장 어디에도 없다 — 먼저 적어라", False


def scan(label: str, d: Path, lake_sha: dict[str, Path], ret, held,
         *, min_mb: float = 0.0) -> list[tuple[Path, str, str]]:
    print(f"\n══ {label}  {d}")
    if not d.is_dir():
        print("   ✗ 폴더가 없다 — 스캔 못 한다")
        return []
    files = [p for p in sorted(d.iterdir())
             if p.is_file() and p.stat().st_size >= min_mb * 1e6
             and (p.suffix.lower() in DATA_EXT
                  or p.suffix.lower() in JUNK)]
    if not files:
        print("   비어 있다")
        return []
    dele: list[tuple[Path, str, str]] = []
    tally: dict[str, int] = defaultdict(int)
    for p in files:
        verdict, why, can = judge(p, lake_sha, ret, held)
        tally[verdict] += 1
        mark = "🗑" if can else "  "
        print(f"   {mark} [{verdict:9s}] {p.name[:44]:46s} {p.stat().st_size / 1e6:7.1f}MB")
        print(f"        {why}")
        if can:
            dele.append((p, verdict, why))
    print(f"   ── {len(files)}건 · " + " · ".join(f"{k} {v}" for k, v in tally.items()))
    return dele


MASTER_OLD = """```bash
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"      # 리눅스
setx FIRE_LANE_DATA "<raw 상위 폴더 경로>"        # 윈도우
```

미설정 시 `<repo>/data/raw` 를 쓴다. 단일 머신이면 그걸로 충분하다."""

MASTER_NEW = """```bash
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"          # 리눅스
export FIRE_LANE_INBOX="/mnt/c/Users/<사용자명>/Downloads"
setx FIRE_LANE_DATA "<raw 상위 폴더 경로>"            # 윈도우
```

미설정 시 `<repo>/data/raw` 를 쓴다. 단일 머신이면 그걸로 충분하다.

★ **`FIRE_LANE_INBOX` 는 파이프라인의 머리다.** `tools/intake.py` 가
브라우저 다운로드 폴더를 관측하는 자리이고, `tools/lakecheck.py` L3 와
`tools/sweep.py` 가 기본 스캔 대상으로 쓴다. 없으면 **레이크 밖을
아무도 안 본다** — 2026-08-25 에 KFS PDF 두 판을 열어보고 대장 결론을
뒤집었는데 그 PDF 가 raw 에 편입되지 않았고 아무 도구도 그 사실을 몰랐다.

★ 2026-09-10 정정. 이 줄이 **`web/playbook.html` 에는 있는데 여기 없었다.**
그 HTML 은 `render_workflow.py` 가 이 문서에서 생성하는 것이라 정본에
없는 내용이 생성물에만 있던 셈이다. 협업자가 보는 문서와 대장이 갈렸다."""


def fix_docs(apply: bool) -> int:
    """★ 환경변수 선언이 생성물에만 있고 정본에 없었다."""
    print("\n══ ④ 문서 정합 — FIRE_LANE_INBOX")
    n = 0
    m = ROOT / "docs" / "MASTER.md"
    s = m.read_text(encoding="utf-8")
    if "FIRE_LANE_INBOX" in s:
        print("   = MASTER.md 이미 있다")
    elif s.count(MASTER_OLD) != 1:
        print("   ✗ MASTER.md 앵커를 못 찾았다")
        return 1
    else:
        print(f"   {'→' if apply else '·'} MASTER.md 환경변수 절에 INBOX")
        if apply:
            m.write_text(s.replace(MASTER_OLD, MASTER_NEW), encoding="utf-8")
        n += 1
    e = ROOT / ".env.example"
    if e.exists():
        t = e.read_text(encoding="utf-8")
        if "FIRE_LANE_INBOX" in t:
            print("   = .env.example 이미 있다")
        else:
            print(f"   {'→' if apply else '·'} .env.example 에 INBOX")
            if apply:
                e.write_text(t.replace(
                    "FIRE_LANE_DATA=",
                    "FIRE_LANE_DATA=\n"
                    "# 브라우저 다운로드 폴더. intake·lakecheck·b2_sweep 이 관측한다\n"
                    "FIRE_LANE_INBOX=", 1), encoding="utf-8")
            n += 1
    if n and apply:
        print("   ★ web/playbook.html 은 render_workflow.py 가 다시 만든다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep", action="store_true", help="지울 것을 판정한다")
    ap.add_argument("--yes", action="store_true", help="실제로 지운다")
    a = ap.parse_args()

    D = str(paths.DATA or "")
    IN = paths.env("FIRE_LANE_INBOX")
    if not D or not Path(D).is_dir():
        print("✗ FIRE_LANE_DATA 가 없거나 폴더가 아니다")
        print("  ★ 0건이 아니라 실패다 — 스캔을 못 했는데 깨끗하다고 하면 안 된다")
        return 1
    if not IN or not Path(IN).is_dir():
        print("✗ FIRE_LANE_INBOX 가 없거나 폴더가 아니다")
        print("  ★ 다운로드 폴더를 못 보면 '레이크 밖' 을 아무도 안 본다")
        return 1
    D, IN = Path(D), Path(IN)
    y = led()
    ret, held = retired_names(y), held_names(y)

    # 레이크 지문 — raw·norm 이 정본이다. **북마크가 아는 것은 다시 안 판다**(§258-17)
    print("레이크 지문화 중…", end="", flush=True)
    lake: dict[str, Path] = {}
    fp, seen, reused, hashed = _fp_load(), {}, 0, 0
    for zone in ("raw", "norm"):
        for p in (D / zone).rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(D).as_posix()
            try:
                st = p.stat()
                key = [st.st_size, st.st_mtime_ns]
            except OSError as e:
                UNREAD.append((str(p), f"{type(e).__name__}: {e}"))
                continue
            was = fp.get(rel)
            if fp_valid(was, *key):
                d, reused = was[2], reused + 1
            elif (d := sha(p)) is not None:
                hashed += 1
            else:
                continue
            seen[rel] = [*key, d]
            lake.setdefault(d, p.relative_to(D))
    _fp_save(seen)          # 사라진 파일은 자연히 빠진다 — 북마크가 안 자란다
    print(f" {len(lake)}건 (북마크 {reused} · 새로 {hashed})")

    dele = scan("① 다운로드 폴더", IN, lake, ret, held, min_mb=0.0)

    # landing — raw 에 들어갔으면 여기 남을 이유가 없다
    land = scan("② landing (레이크 입구)", D / "landing", lake, ret, held)

    print("\n══ ③ 레이크 나머지")
    for zone, note in (("_quarantine", "lakecheck L2 소관 — 여기서 안 건드린다"),
                       ("interim", "재생성 가능(layers 선언) — 보고만 한다"),
                       ("norm", "raw 의 파생 — lakecheck L5 소관")):
        z = D / zone
        n = sum(1 for p in z.rglob("*") if p.is_file()) if z.is_dir() else 0
        sz = sum(p.stat().st_size for p in z.rglob("*") if p.is_file()) if z.is_dir() else 0
        print(f"   {zone:12s} {n:3d}건 {sz / 1e6:8.1f}MB   {note}")

    torn = torn_down(y)
    print("\n══ ④ 철거된 산출물 (repo processed)")
    if not torn:
        print("   없다 — 철거 선언 "
              f"{len(y.get('retired_outputs') or {})}건 모두 디스크에서 사라졌다")
    for q, v, w in torn:
        print(f"   🗑 [{v:9s}] {q.relative_to(ROOT)}  {q.stat().st_size / 1e6:.1f}MB")
        print(f"        {w}")

    fix_docs(a.yes)

    # ★ 2026-09-26 (§258-15). **못 읽은 원본이 있으면 이 실행의 판단은 부분이다.**
    #   레이크 지문이 비어 있는 파일은 「레이크에 없다」로 세어지고, 그러면
    #   「중복이라 지워도 된다」가 거짓이 된다. 목록은 끝까지 내되 빨갛게 끝낸다 —
    #   조용히 넘어가면 지우면 안 될 것을 지우라고 말하게 된다.
    if UNREAD:
        print(f"\n★ 못 읽은 원본 {len(UNREAD)}건 — 이 실행의 판단은 **부분**이다")
        for q, why in UNREAD[:10]:
            print(f"   {q}\n     {why}")
        if len(UNREAD) > 10:
            print(f"   … 외 {len(UNREAD) - 10}건")
        print("   외장 SSD 가 /mnt/ (DrvFs) 로 붙어 있으면 큰 읽기가 ENOMEM 을 낸다.")
        print("   그 원본을 리눅스 쪽 디스크로 옮기거나, 그 파일만 빼고 판단해라.")

    todo = dele + land + torn
    total = sum(p.stat().st_size for p, _, _ in todo)
    print(f"\n══ 정리 대상 {len(todo)}건 · {total / 1e6:.0f}MB")
    if not todo:
        print("   없다")
        return 1 if UNREAD else 0
    if not a.sweep:
        print("   `--sweep` 으로 지울 목록을 확정한다")
        return 1 if UNREAD else 0
    if not a.yes:
        for p, v, _w in todo:
            print(f"   지울 것  {p.name[:50]:52s} [{v}]")
        print("\n   실제로 지우려면 --sweep --yes")
        return 1 if UNREAD else 0
    n = 0
    for p, v, w in todo:
        p.unlink()
        print(f"   지움  {p.name[:50]:52s} [{v}] {w}")
        n += 1
    print(f"\n   {n}건 삭제 · {total / 1e6:.0f}MB 확보")
    print("   ★ 근거가 대장에 있는 것만 지웠다. 보류·미판단은 남아 있다")
    return 1 if UNREAD else 0


if __name__ == "__main__":
    sys.exit(main())
