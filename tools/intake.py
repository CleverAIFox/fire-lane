#!/usr/bin/env python3
"""
intake.py — 출발지 게이트. **윈도우 다운로드 폴더에서 시작한다.**

    uv run python tools/intake.py                 관측만 (아무것도 안 옮긴다)
    uv run python tools/intake.py --plan          정규명 제안 + 대장 매칭
    uv run python tools/intake.py --stage --yes   landing 으로 복사 + sha 기록

── 왜 만들었나 ────────────────────────────────────────────────
파이프라인의 머리가 `landing` 이었다. 그런데 `paths.LANDING` 은 외장 SSD 이고,
브라우저는 `C:\\Users\\...\\Downloads` 로 떨군다. **그 사이 한 칸이 선언
밖이었다.**

`landing` 은 "규칙 없음" 이지만 관측은 된다 — `acquire.py` 가 스캔하고 세
판정을 낸다. 다운로드 폴더는 규칙도 없고 관측도 안 된다. 그래서 2026-08-25 에
KFS PDF 두 판을 열어보고 `sources.yaml` 의 결론을 뒤집었는데, **그 PDF 가
raw 에 편입되지 않았고 아무 도구도 그 사실을 몰랐다.** 대장은 근거를
인용하고 근거 파일은 그물 밖에 있었다.

이 저장소가 반복해 배운 것과 같은 형태다 —
**선언 밖에 있으면 그물에 안 걸린다**(interim 신설 · golden/baseline 등재).

── 설계 ───────────────────────────────────────────────────────
    ① 다운로드 폴더는 **읽기 전용**으로 취급한다
       사용자의 폴더지 파이프라인의 것이 아니다. 복사만 하고 지우지 않는다.
       정리는 사람이 한다. 도구가 남의 다운로드 폴더를 비우면 안 된다.

    ② 원본 파일명을 **대장에 보존**한다
       `6. 소방차 도장 및 표기(KFS-1-0006-2024-00).pdf` 가 정규명이 되면
       제공기관에 문의할 때 대조가 안 된다(MASTER §18 R1). raw 에는
       정규명으로 두고 원본명은 `origin_name` 으로 남긴다.

    ③ 개명은 **제안까지만** 한다
       한글 원본명을 기계가 영문으로 옮기면 `소방펌프차` 가
       `sobangpeompeuca` 가 되고 대장의 `kfs_pumptruck` 과 무관한 이름이
       생긴다. `--plan` 이 후보를 내고 사람이 정한다.

    ④ 멱등하다
       sha256 으로 판정한다. 크기가 아니다 — `normalize_raw` 의 크기 비교가
       313MB 정사영상이 잘려도 통과시키던 것이 2026-08-23 의 교훈이다.

── 계층 ───────────────────────────────────────────────────────
    Downloads (읽기 전용)          ← 여기가 출발지다
        │  intake.py --stage       원본명 보존 · sha 기록
        ▼
    landing (SSD)                  규칙 없음
        │  acquire.py --stage      대장 매칭 · 세 판정
        ▼
    raw                            불변
        │  prep.py                 인코딩·개행 통일
        ▼
    norm                           값은 안 바꾼다

IN    $FIRE_LANE_INBOX (기본값 자동탐색) · sources.yaml
OUT   $FIRE_LANE_DATA/landing · data/_intake.json (커밋한다)
PARAM 없음
부류  생산   산출물·대장·그림을 만든다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from firelane import ledger as _led
from firelane import naming as nm
from firelane.paths import LANDING, ROOT
from firelane.paths import inbox as _inbox

KST = timezone(timedelta(hours=9))
LEDGER = ROOT / "data" / "_intake.json"

# JUNK 정본은 firelane.intake_rules 다. 여기서 재정의하지 않는다.
from firelane.intake_rules import JUNK

# ★ inbox() 는 `firelane.paths` 로 옮겼다(2026-08-26). 경로 정본은 거기다 —
#   여기 두었더니 `doctor.py` 가 쓰려고 sys.path 를 조작했고 규칙에 걸렸다.
inbox = _inbox

from firelane.hashing import sha256 as _h_sha256


def sha256(p, chunk: int = 1 << 20) -> str:
    # ★ 2026-09-13. 구현은 `firelane.hashing` 한 곳이다.
    #   이름은 호출부 때문에 남긴다 — 옮긴 것과 고친 것을
    #   한 커밋에 섞지 않는다(원칙 ⑤).
    return _h_sha256(p, chunk)


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"files": {}, "at": None}


def ledger_shas() -> set[str]:
    return {v["sha256"] for v in load_ledger()["files"].values()}


def sources_index() -> dict[str, dict]:
    f = ROOT / "sources.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return d.get("datasets", {})


def _retired() -> dict:
    """폐기 대장. `_ledger()` 가 datasets 만 읽어서 신설했다.

    ★ 2026-09-10. 실패 메시지는 "datasets **또는 retired** 에 적어라" 인데
      코드는 datasets 만 봤다. retired 에 적어도 통과가 안 되니 사람이
      `--force` 를 쓰게 되고, 그 순간 관문이 죽는다 — 같은 파일 123행이
      "관문은 정확해야 한다. 정상 파일을 막으면 사람이 --force 를 쓴다"
      고 스스로 적어놓은 그 자리다.
    """
    f = ROOT / "sources.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return d.get("retired", {}) or {}


def retired_hit(name: str) -> str | None:
    """이 원본명이 폐기 대장에 있나 → 항목 키.

    ★ 폐기는 **판단이 끝난 것**이다. 다시 묻지 않고 조용히 건너뛴다.
      `_quarantine` 이 "판단 보류지 폐기가 아니다" 인 것과 짝이다.
    """
    for k, v in _retired().items():
        if not isinstance(v, dict):
            continue
        if v.get("origin_name") == name:
            return k
        st = v.get("stem")
        stem = name.rsplit(".", 1)[0]
        if st and stem.startswith(st):
            return k
    return None


# ── 원본명 → 정규명 제안 ──────────────────────────────────────
# ★ 2026-10-08 (DECISIONS §431 · PLAN #157). `firelane/intake_name.py` 로
#   떼어 냈다. 2026-10-05 에 **본문 단서**를 뗀 것과 같은 수술이다 —
#   그때 656 → 내려왔고, §430 의 `_pick` 통합이 다시 609 로 올렸다.
from firelane.intake_name import propose, rule_path


# ── 명령 ──────────────────────────────────────────────────────
def cmd_observe(inb: Path) -> int:
    """무엇이 있고 무엇이 이미 편입됐나. **아무것도 안 옮긴다.**"""
    print(f"출발지  {inb}")
    if not inb.is_dir():
        print("  ★ 없다. FIRE_LANE_INBOX 로 지정하라.")
        return 1
    known = ledger_shas()
    files = [p for p in sorted(inb.iterdir())
             if p.is_file() and not JUNK.search(p.name)]
    if not files:
        print("  비어 있다.")
        return 0
    new = stale = 0
    print(f"\n{'상태':6} {'MB':>8}  파일")
    for p in files:
        s = sha256(p)
        seen = s in known
        new += not seen
        stale += seen
        print(f"{'편입됨' if seen else '★ 신규':6} "
              f"{p.stat().st_size/1e6:8.1f}  {p.name}")
    print(f"\n신규 {new} · 이미 편입 {stale}")
    if new:
        print("  → `--plan` 으로 정규명 후보를 본다")
    return 0


def waiting(ds: dict) -> list[tuple[str, str]]:
    """**방아쇠.** 대장이 선언했는데 raw 에 없는 `(키, 상대경로)`.

    ★ 2026-10-05 (DECISIONS §401). 이 도구는 **다운로드 폴더 전부**를 제
      일거리로 봤다. 사람의 폴더에 배치 zip · 채용공고 · 남의 패치가 같이
      사는데, 그 전부에 대고 「대장에 항목을 만들어라」라고 말했다 —

          「이상한거 까지 다 들어갔잖아」

      방향이 반대였다. **대장이 기다리는 자리가 방아쇠다.** 결손이 0 이면
      이 도구는 다운로드 폴더를 **열지도 않는다.** 그러면 안 건드리는 것이
      규칙이 아니라 **구조**가 된다 — 규칙은 잊히고 구조는 안 잊힌다.
    """
    from fnmatch import fnmatch

    from firelane.paths import RAW

    have = {q.relative_to(RAW).as_posix()
            for q in RAW.rglob("*") if q.is_file()} if RAW.is_dir() else set()
    out = []
    for key in sorted(ds):
        e = ds[key] or {}
        if e.get("status") == "missing":
            continue
        # ★ 2026-10-07 (DECISIONS §430). 두 군데를 고쳤다.
        #   ① `e.get("files")` → `_led.globs(e)`. **대장 여든 중 예순여섯이
        #      `stem`+`ext` 식**이라 종전 코드에는 **자리가 아예 안 생겼다** —
        #      「대장이 기다리는 자리」가 방아쇠인데 방아쇠가 안 당겨졌다.
        #   ② `rel not in have` 는 **글롭을 문자열 그대로** 비교했다.
        #      `ngii1k` 는 실물 둘이 있는데 영구히 「못 찾았다」로 떴다.
        for pat in _led.globs(e):
            if not any(fnmatch(h, pat) for h in have):
                out.append((key, pat))
    return out


def _fits(suggest: str | None, pat: str) -> bool:
    """제안 경로가 그 자리의 글롭에 맞나. 자리는 글롭일 수도 구체 경로일 수도 있다."""
    from fnmatch import fnmatch

    if not suggest:
        return False
    return (fnmatch(suggest, pat)
            or fnmatch(Path(suggest).name, Path(pat).name))


#: 파일 하나의 `propose()` 결과. **자리와 무관**하므로 파일당 한 번만 센다.
#: ★ 없으면 자리 × 파일 만큼 PDF 를 다시 연다 — 자리 82 · 파일 7 이면 574번이다.
_PROPOSED: dict[tuple[str, int, int], dict] = {}


def _proposal(q: Path, ds: dict) -> dict:
    st = q.stat()
    k = (str(q), st.st_size, int(st.st_mtime))
    if k not in _PROPOSED:
        _PROPOSED[k] = propose(q, ds)
    return _PROPOSED[k]


def _pick(files: list[Path], ds: dict, key: str, pat: str,
          taken: tuple[Path, ...] = ()) -> tuple[Path | None, str]:
    """그 자리에 올 다운로드 하나 — **단서 넷을 전부 쓴다.**  (DECISIONS §431)

    ★ 종전에는 `cmd_plan` · `_auto` · `_match_one` 셋이 **각자** 고르면서
      단서 ④(본문)만 봤다. 그런데 `body_text` 는 **PDF 가 아니면 빈 문자열**을
      돌려준다(`test_body_text_refuses_everything_that_is_not_a_pdf`) — zip 과
      csv 는 읽을 본문이 없어 **영영 못 맞춘다.**

      2026-10-08 실측 — 자리 다섯 중 PDF 하나만 자동으로 붙었고 넷은
      사람이 `--assign` 으로 찍었다. 그런데 **`normalize_raw.RULES` 가 그 넷의
      이름을 전부 알고 있었다.** `propose()` 가 그 규칙을 단서 ②로 쓰는데
      이 세 자리가 `propose()` 를 **안 불렀다.**

    ★ 셋을 여기 하나로 합친다 — 같은 질문에 답이 셋이면 반드시 갈린다.
    """
    for q in files:
        if q in taken:
            continue
        got = _proposal(q, ds)
        if got["matched_key"] != key:
            continue
        if _fits(got["suggest"], pat):
            return q, " · ".join(got["why"][-2:]) or "대장 매칭"
    return None, ""


def _match_one(inb: Path, ds: dict, key: str, rel: str,
               assign: list[str] | None) -> Path | None:
    """그 자리에 올 다운로드 하나. 못 고르면 `None`. **사람이 이긴다.**

    ★ `--assign N=조각` 은 번호로 찍는다. 번호는 `--plan` 이 매긴 순서다 —
      대장은 파일 이름을 이미 정확히 적고 있고, 모르는 것은 「이 다운로드가
      그중 어느 것이냐」 하나뿐이며 그것은 사람이 안다.
    """
    want = waiting(ds)
    files = [q for q in sorted(inb.iterdir())
             if q.is_file() and not JUNK.search(q.name)] if inb.is_dir() else []
    for a in assign or []:
        i, _, frag = a.partition("=")
        if not i.strip().isdigit() or not frag:
            continue
        k = int(i) - 1
        if 0 <= k < len(want) and want[k] == (key, rel):
            hit = [q for q in files if frag in q.name]
            return hit[0] if len(hit) == 1 else None
    return _pick(files, ds, key, rel)[0]


def cmd_plan(inb: Path, assign: list[str] | None = None) -> int:
    """대장이 기다리는 자리마다 **어느 다운로드가 그것인가.**

    ★ 사람이 번호로 찍을 수 있다 — `--assign 1=인쇄`. 대장은 파일 이름을
      이미 정확히 적고 있고, 모르는 것은 「이 다운로드가 그중 어느 것이냐」
      하나뿐이며 **그것은 사람이 안다.** 추측기와 싸우게 만들지 않는다.
    """
    ds = sources_index()
    want = waiting(ds)
    if not want:
        print("대장이 기다리는 자리가 없다 — 결손 0. 볼 것이 없다.")
        return 0

    files = [q for q in sorted(inb.iterdir())
             if q.is_file() and not JUNK.search(q.name)]
    picked: dict[int, Path] = {}
    for a in assign or []:
        i, _, frag = a.partition("=")
        if not frag or not i.strip().isdigit():
            print(f"★ --assign 꼴이 아니다: {a!r} — `--assign 1=인쇄` 처럼 적는다")
            return 2
        k = int(i) - 1
        hit = [q for q in files if frag in q.name]
        if k < 0 or k >= len(want):
            print(f"★ 자리 {i} 가 없다 — 지금 {len(want)}개다")
            return 2
        if len(hit) != 1:
            print(f"★ {frag!r} 가 {len(hit)}개 걸린다 — 더 길게 적어라")
            return 2
        picked[k] = hit[0]

    print(f"대장이 기다리는 자리 {len(want)}\n")
    for k, (key, rel) in enumerate(want, 1):
        src = picked.get(k - 1)
        why = "사람이 찍었다(--assign)"
        if src is None:
            src, why = _pick(files, ds, key, rel, tuple(picked.values()))
            why = why or "본문으로 못 가른다"
        print(f"  [{k}] {key}")
        print(f"      자리  {rel}")
        print(f"      파일  {src.name[:60] if src else '★ 못 찾았다'}")
        hint = f"본문으로 못 가른다 — `--assign {k}=<이름 조각>` 으로 찍어라"
        print(f"      근거  {why if src else hint}")
    n = sum(1 for k in range(len(want)) if k in picked) + \
        sum(1 for k, (key, rel) in enumerate(want)
            if k not in picked and _auto(files, picked, ds, key, rel))
    print(f"\n  찾은 것 {n} / {len(want)}")
    print("  ★ 다운로드 폴더의 나머지는 **안 본다** — 대장이 안 기다리는 것이다.")
    return 0


def _auto(files, picked, ds, key, rel) -> bool:
    return _pick(files, ds, key, rel, tuple(picked.values()))[0] is not None


def cmd_stage(inb: Path, *, apply: bool, force: bool = False,
              assign: list[str] | None = None) -> int:
    """다운로드 → landing. **원본은 지우지 않는다.**

    ★ 관문 둘을 통과해야 한다 —
      ① 레이크가 붙어 있는가(`require_lake`)
      ② 대장이 아는 파일인가

      ②가 없어서 `apply.sh` · `fire-lane-gis.zip` · 진행일지 PDF 가
      landing 에 올라갔다. `--plan` 은 "★ 대장에 없는 문서다" 라고
      경고해 놓고 `--stage` 는 그냥 복사했다 — **경고가 게이트로
      이어지지 않았다.** 이 저장소가 반복해 배운 그 형태다.

      확장자로는 못 막는다. `.zip` 은 정상 데이터 형식이고
      `fire-lane-gis.zip` 은 저장소 사본이다. **대장이 판단한다.**
    """
    from firelane.paths import require_lake
    require_lake(need=("raw",))
    ds = sources_index()
    L = load_ledger()
    LANDING.mkdir(parents=True, exist_ok=True)
    moved = skipped = 0

    # ★ 2026-10-05 (DECISIONS §401). **대장이 기다리는 자리만 돈다.** 종전에는
    #   다운로드 폴더를 훑어 매칭되는 것을 복사했고, 그래서 사람의 폴더에 있는
    #   남의 파일까지 한 줄씩 「대장에 없다」로 찍었다.
    # ★ 그리고 **대장이 적은 이름으로** 복사한다. 종전에는 `LANDING / p.name`
    #   이라 브라우저가 붙인 이름이 그대로 올라갔고, 그러면 `acquire --stage`
    #   가 또 못 맞춘다 — 사슬이 거기서 끊겨 있었다. 원본명은 대장이 든다.
    for key, rel in waiting(ds):
        src = _match_one(inb, ds, key, rel, assign)
        if src is None:
            skipped += 1
            continue
        s = sha256(src)
        # ★ 2026-10-07 (DECISIONS §430). `rel` 은 **글롭**이다. 종전 코드가
        #   `Path(rel).name` 을 그대로 썼기 때문에 `ngii1k` 를 반입하면
        #   `vworld_map1k*_jngj-donggu_20260307.zip` — **이름에 `*` 가 박힌
        #   파일**이 landing 에 생길 참이었다. 터지지 않은 이유는 위 두 결함이
        #   그 자리까지 못 가게 막고 있었기 때문이다.
        #   `rel` 하나가 **「없음 판정」과 「목적지 이름」 두 일**을 했다. 가른다 —
        #   없음은 대장이 판정하고, **이름은 `normalize_raw.RULES` 가 든다.**
        if not (dest := rule_path(src.name) or (rel if "*" not in rel else "")):
            print(f"  ★ {src.name}: 목적지 이름을 못 정한다 — 대장은 글롭 "
                  f"{rel} 만 적고 `normalize_raw.RULES` 도 이 이름을 모른다.\n"
                  f"     규칙을 먼저 적어라 (src/firelane/normalize_raw.py)")
            skipped += 1
            continue
        dst = LANDING / Path(dest).name
        if dst.exists() and sha256(dst) == s:
            skipped += 1
            continue
        print(f"{'복사' if apply else '복사예정'}  {src.name}\n"
              f"        → {dst.name}   ({key})")
        if apply:
            shutil.copyfile(src, dst)
            if sha256(dst) != s:
                print("  ★ 복사 후 sha 불일치. 중단한다.")
                return 1
            L["files"][dst.name] = {
                "sha256": s, "bytes": src.stat().st_size,
                "origin_name": src.name,
                "dataset": key,
                "seen_at": datetime.now(KST).isoformat(timespec="seconds"),
                "from": str(inb),
            }
        moved += 1
    if apply:
        L["at"] = datetime.now(KST).isoformat(timespec="seconds")
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(
            json.dumps(L, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n{'편입' if apply else '편입 예정'} {moved} · 건너뜀 {skipped}")
    if not apply and moved:
        print("  실제로 옮기려면 --yes")
    print("\n★ 다운로드 폴더의 원본은 지우지 않았다. 정리는 사람이 한다.")
    if apply and moved:
        print("★ 다음 — uv run python tools/acquire.py   (landing → raw 판정)")
    return 0


def cmd_audit() -> int:
    """raw 실물 이름과 대장 패턴을 문법으로 심사한다."""
    ds = sources_index()
    bad = 0
    print("═══ 대장 file 패턴 ═══")
    for k, v in ds.items():
        # ★ 2026-08-30. `v.get("file", "")` — 대장에서 `file` 단수가
        #   사라지자 42종 전부 빈 문자열을 넘겼고, audit_pattern 이
        #   42번 "provider 폴더가 없다: ''" 를 냈다. 열한 번째 사본이다.
        for _pat in _led.globs(v):
            for msg in nm.audit_pattern(_pat):
                bad += 1
                print(f"  [{k}] {msg}")
    acq = ROOT / "data" / "_acquire.json"
    if acq.exists():
        print("\n═══ raw 파일명 문법 ═══")
        f = json.loads(acq.read_text(encoding="utf-8"))["files"]
        for rel in sorted(f):
            folder, _, fn = rel.partition("/")
            ok, msgs = nm.check(fn, folder=folder)
            for m in msgs:
                bad += 1
                print(f"  {rel}\n      {m.splitlines()[0]}")
    print(f"\n지적 {bad}건")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="대장 결손 ↔ 다운로드 (아무것도 안 옮긴다)")
    ap.add_argument("--assign", action="append", metavar="N=조각",
                    help="자리 N 에 이름 조각이 맞는 파일을 찍는다")
    ap.add_argument("--stage", action="store_true", help="다운로드 → landing")
    ap.add_argument("--audit", action="store_true", help="raw·대장 문법 심사")
    ap.add_argument("--yes", action="store_true", help="실제로 복사한다")
    ap.add_argument("--force", action="store_true",
                    help="대장에 없는 파일도 올린다. ★ 먼저 대장에 적어라")
    a = ap.parse_args()
    if a.audit:
        return cmd_audit()
    inb = inbox()
    if a.plan:
        return cmd_plan(inb, a.assign)
    if a.stage:
        return cmd_stage(inb, apply=a.yes, force=a.force, assign=a.assign)
    return cmd_observe(inb)


if __name__ == "__main__":
    sys.exit(main())
