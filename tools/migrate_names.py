#!/usr/bin/env python3
"""
migrate_names.py — raw 실물 · 대장 · sha 대장을 **한꺼번에** 개명한다.

    uv run python tools/migrate_names.py            계획만 (아무것도 안 바꾼다)
    uv run python tools/migrate_names.py --apply --yes

FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다
  `tests/test_guards.py::test_no_source_patching_scripts` 의 예외 마커다.
  raw 2.6GB 는 저장소 밖이고, 개명은 실물·sha대장·대장 셋을 함께 바꿔야
  한다. diff 로는 둘밖에 못 담는다.

── 왜 도구여야 하나 ───────────────────────────────────────────
파일 하나를 개명하면 **세 곳이 동시에 바뀌어야 한다.**

    ① $FIRE_LANE_DATA/raw 의 실물
    ② data/_acquire.json 의 키 (sha256 대장)
    ③ sources.yaml 의 datasets[*].file

셋 중 하나만 바뀌면 그 순간부터 어느 쪽이 정본인지 아무도 모른다.
`mv` 여덟 번 치고 에디터로 대장을 고치는 방식은 중간에 손이 미끄러지면
복구가 안 된다 — 그리고 이 저장소는 exFAT 에서 2.5GB 를 날린 전력이 있다.

★ 순서가 정해져 있다. **대장을 먼저 바꾸고 실물을 나중에** 바꾼다.
  반대로 하면 실물만 바뀐 중간 상태에서 파이프라인이 돌 때 대장이 옛
  이름을 가리켜 MISSING 이 나고, 그게 "결손" 인지 "개명 중" 인지 안 갈린다.
  대장이 먼저 바뀌면 그 창에서는 대장이 새 이름을 가리키고 실물이 없어
  **MISSING 이 정직하게 뜬다.** 같은 실패라도 진단 가능한 쪽을 고른다.

★ 롤백 저널을 남긴다. `data/_migrate_journal.json` 에 (before, after, sha)
  를 적고, 중간에 죽으면 `--rollback` 이 그것을 되감는다.

── 무엇을 바꾸나 ──────────────────────────────────────────────
`firelane.naming` 이 지적한 것만 고친다. 판단이 필요한 것은 손대지 않는다.

    ① 스코프 토큰 없음        → `_kr_` 삽입          (KFS 8건)
    ② 옛 스코프 토큰          → 정규 별칭            (gjdonggu·dongu 6건)
    ③ 확장자 와일드카드       → files: + primary:    (대장만, 실물 무관)

★ 도엽(`gj9708` 등 11건)은 **여기서 안 한다.** `part` 필드로 옮기려면
  대장의 `file` 글롭 구조(`ngii_basemap_gj9*.zip`)를 같이 바꿔야 하고,
  그것은 `ingest.shp_zip_multi` 의 동작을 건드린다. 별도 작업이다.

★ `gj_dong`(2건)도 안 한다. 그것은 개명이 아니라 **축 분리**다 —
  `scope: jngj-dong` + `authority: 동부소방서`. 사람이 판단해야 한다.

IN    $FIRE_LANE_DATA/raw · data/_acquire.json · sources.yaml
OUT   위 셋 · data/_migrate_journal.json
PARAM 없음
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from firelane import scope as sc
from firelane.paths import QUARANTINE, RAW, ROOT

KST = timezone(timedelta(hours=9))
LEDGER = ROOT / "data" / "_acquire.json"
YAML = ROOT / "sources.yaml"
JOURNAL = ROOT / "data" / "_migrate_journal.json"

def sha256(p: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


# ── 개명 규칙은 여기 없다 ─────────────────────────────────────
# ★ 2026-08-26. 종전에는 이 자리에 `NEEDS_SCOPE = (8개 키)` 가 박혀 있었다.
#   **규칙이 도구 안에 살면 그 도구를 매번 고쳐야 한다.** 다음에 스코프 없는
#   파일이 들어오면 리스트를 손으로 늘려야 하고, 안 늘리면 조용히 통과한다.
#
#   규칙은 `firelane.naming.canonical()` 로 옮겼고 판단은 대장이 한다 —
#   `scope` · `part` · `authority` 를 적으면 정규명이 결정된다.
#   이 도구는 그 결과를 실물에 적용하는 **얇은 백필**이다.
#
#   그래서 도엽 11건 · `gj_dong` 2건도 자동으로 풀린다. 대장에
#   `part: '35616037'` 이나 `authority: 동부소방서` 를 적으면 다음 실행이
#   개명한다. 도구를 고칠 일이 없다.


def plan() -> list[dict]:
    """(old, new) 목록. **규칙은 naming.canonical() 이 정한다.**"""

    from firelane import naming as nm
    led = json.loads(LEDGER.read_text(encoding="utf-8"))["files"]

    # ★ 역산을 걷어냈다(2026-08-27). `firelane.ledger.entry_of` 로 조회한다.
    #   종전에는 대장 `file` 에서 정규식으로 provider_dataset 을 복원했고,
    #   그 규칙이 `normalize_raw` 와 달라 12건이 "개명 대상 0건" 으로
    #   조용히 실패했다. 조회기는 하나여야 한다.
    from firelane.ledger import entry_of

    out = []
    for rel in sorted(led):
        new = nm.canonical(rel, entry_of(rel)[1])
        if new:
            out.append({"old": rel, "new": new,
                        "sha256": led[rel]["sha256"], "bytes": led[rel]["bytes"]})
    return out


def _yaml_rewrite(pairs: list[dict], *, apply: bool) -> list[str]:
    """대장의 `file` 값을 텍스트로 치환한다.

    ★ yaml.safe_load → dump 를 하지 않는다. 이 대장은 1,500줄 중 대부분이
      주석과 산문이고, round-trip 하면 **그게 전부 날아간다.**
      대장의 값어치는 값이 아니라 옆에 붙은 경고문이다.
    """
    s = YAML.read_text(encoding="utf-8")
    hits = []
    for p in pairs:
        o_stem = p["old"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        n_stem = p["new"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        n = s.count(o_stem)
        if n:
            s = s.replace(o_stem, n_stem)
            hits.append(f"{o_stem} → {n_stem}  ({n}곳)")
    if apply:
        YAML.write_text(s, encoding="utf-8")
    return hits


def _fix_ext_wildcards(*, apply: bool) -> list[str]:
    """`...20251224.*` 를 실물 확장자로 못박는다.

    ★ 08-25 사고의 원인이다. `.hwpx` 옆에 `.pdf` 를 놓으면 ingest 의
      hits[0] 이 사전순으로 뒤집히고 _manifest 의 source_sha256 이
      조용히 바뀐다. 실물이 하나뿐인 지금 못박아 두면 나중에 판이
      추가돼도 **시끄럽게** 실패한다(MISSING).
    """
    led = json.loads(LEDGER.read_text(encoding="utf-8"))["files"]
    s = YAML.read_text(encoding="utf-8")
    out = []
    for m in sorted(set(re.findall(r"([\w/]+_\d{4,8})\.\*", s))):
        cands = [r for r in led if r.rsplit(".", 1)[0].endswith(
            m.rsplit("/", 1)[-1])]
        if len(cands) != 1:
            out.append(f"★ {m}.* — 실물 {len(cands)}건. 손으로 정해라")
            continue
        ext = cands[0].rsplit(".", 1)[1]
        s = s.replace(f"{m}.*", f"{m}.{ext}")
        out.append(f"{m}.* → {m}.{ext}")
    if apply:
        YAML.write_text(s, encoding="utf-8")
    return out



def _repair_globs(*, apply: bool) -> list[str]:
    """개명 뒤 **아무 실물도 못 잡는 글롭**을 다시 만든다.

    ★ 첫 판은 개명 저널을 봤다. 틀렸다 — 저널은 **매 실행 덮어써진다.**
      이전 실행의 개명 기록이 없으면 복구가 통째로 실패하고, 실제로
      2026-08-26 에 넷이 "이력에도 없다" 로 빠졌다.

      **이력에 의존하면 안 된다.** 실물은 지금 거기 있고, 대장 항목은
      자기가 어느 provider · 어느 dataset 인지 안다. 그 둘만으로 복구된다.
      과거를 안 봐도 되는 설계가 항상 낫다.

    ★ 추측하지 않는다. `provider_dataset` 접두로 후보를 모으고, 옛 글롭이
      요구하던 **확장자**가 같은 것만 남긴다. 하나도 없거나 애매하면
      손을 뗀다.
    """
    import fnmatch
    led = json.loads(LEDGER.read_text(encoding="utf-8"))["files"]
    s = YAML.read_text(encoding="utf-8")
    d = yaml.safe_load(s) or {}
    out = []
    for key, e in (d.get("datasets") or {}).items():
        for pat in (e.get("files") or ([e["file"]] if "file" in e else [])):
            pat = str(pat)
            # ★ 글롭만 보지 않는다. **정확한 이름도 죽는다** —
            #   실물은 개명됐는데 대장이 옛 이름을 가리키는 상태가 있다
            #   (롤백 후 재적용 · 대장만 되돌린 경우). `plan()` 은 실물이
            #   이미 정규명이라 0건을 내고, 그러면 `_yaml_rewrite` 가 돌지
            #   않아 대장이 영영 옛 이름으로 남는다. 실증했다(9건).
            #
            #   복구는 **가리키는 쪽이 0건이냐**만 보면 된다. 글롭인지
            #   정확한 이름인지는 상관없다.
            if [r for r in led if fnmatch.fnmatch(r, pat)]:
                continue                       # 살아 있다
            folder = pat.split("/", 1)[0]
            stem = pat.rsplit("/", 1)[-1]
            # provider_dataset — 첫 와일드카드 앞까지에서 마지막 `_` 제거
            head = re.split(r"[*?\[]", stem)[0]
            head = head.rsplit(".", 1)[0] if "." in head else head
            head = head.rstrip("_")
            # 옛 이름에서 스코프·도엽 토큰을 떨어낸다: provider_dataset 만 남긴다
            bits = head.split("_")
            while len(bits) > 2 and (bits[-1].isdigit()
                                     or bits[-1] in ("dongu", "gjdonggu", "gj")
                                     or bits[-1].startswith("gj")):
                bits.pop()
            head = "_".join(bits)
            ext = Path(stem).suffix
            cand_files = [r for r in led
                          if r.startswith(f"{folder}/{head}_")
                          and (not ext or ext == ".*" or r.endswith(ext))]
            if not cand_files:
                out.append(f"★ {pat} — {folder}/{head}_* 로도 0건. 손으로 봐라")
                continue
            cand_files.sort()
            # ★ 1순위 — **옛 글롭의 구조를 보존**하고 스코프 토큰만 바꾼다.
            #   commonprefix 는 파일 하나가 다른 하나의 접두일 때 무너진다:
            #     vworld_map1k_jngj-dong_...zip
            #     vworld_map1k_ngi_jngj-dong_...zip
            #   → `map1k_*_jngj-dong` 이 되어 앞의 것을 놓친다(1/2건).
            #   옛 글롭 `vworld_map1k*_gjdonggu_...` 에서 토큰만 갈면
            #   `vworld_map1k*_jngj-dong_...` 이 되어 둘 다 잡는다.
            keep = pat
            for old_tok, new_tok in sc.LEGACY.items():
                keep = keep.replace(f"_{old_tok}_", f"_{new_tok}_")
            if keep != pat:
                got0 = sorted(r for r in led if fnmatch.fnmatch(r, keep))
                if got0 == cand_files:
                    s = s.replace(pat, keep)
                    out.append(f"[{key}] {pat} → {keep}  ({len(got0)}건)")
                    continue
            pre = os.path.commonprefix(cand_files)
            suf = os.path.commonprefix([x[::-1] for x in cand_files])[::-1]
            cand = (pre + "*" + suf) if len(cand_files) > 1 else cand_files[0]
            if not any(c in pat for c in "*?[") and len(cand_files) == 1:
                cand = cand_files[0]           # 정확한 이름은 정확하게
            got = sorted(r for r in led if fnmatch.fnmatch(r, cand))
            if got != cand_files:
                out.append(f"★ {pat} → {cand} 가 {len(got)}건(후보 "
                           f"{len(cand_files)}건)을 잡는다. 채택하지 않는다")
                continue
            s = s.replace(pat, cand)
            out.append(f"[{key}] {pat} → {cand}  ({len(got)}건)")
    if apply and out:
        YAML.write_text(s, encoding="utf-8")
    return out


def _ledger_rewrite(pairs: list[dict], *, apply: bool) -> None:
    d = json.loads(LEDGER.read_text(encoding="utf-8"))
    for p in pairs:
        if p["old"] in d["files"]:
            d["files"][p["new"]] = d["files"].pop(p["old"])
    d["files"] = dict(sorted(d["files"].items()))
    d["at"] = datetime.now(KST).isoformat(timespec="seconds")
    if apply:
        LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")


def _move_files(pairs: list[dict]) -> list[dict]:
    """실물 개명. sha 로 검증하고 저널에 남긴다."""
    done = []
    for p in pairs:
        src, dst = RAW / p["old"], RAW / p["new"]
        if not src.exists():
            if dst.exists():
                print(f"    = {p['new']}  (이미 개명됨)")
                continue
            print(f"    ! {p['old']}  실물 없음 — 건너뛴다")
            continue
        if dst.exists():
            # ★ 옛 이름과 새 이름이 **둘 다** raw 에 있는 상태.
            #   개명이 중간에 끊긴 채 acquire 가 새 이름으로 또 넣으면
            #   이렇게 된다(2026-08-27, 3건).
            #
            #   sha 가 같으면 완전한 중복이므로 옛 것을 격리한다.
            #   다르면 판단이 필요하니 **거기서만** 멈춘다 — 종전에는
            #   첫 충돌에서 전체가 죽어 나머지 개명이 통째로 막혔다.
            if sha256(src) == sha256(dst):
                q = QUARANTINE / p["old"]
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(q))
                print(f"    격리 {p['old']}  (새 이름과 sha 동일 — 중복)")
                done.append({**p, "quarantined": True})
                continue
            print(f"    ✗ {p['old']}\n"
                  f"      대상이 이미 있고 sha 가 다르다: {dst.name}\n"
                  f"      어느 쪽이 정본인지 사람이 정해야 한다. 건너뛴다.")
            continue
        got = sha256(src)
        if got != p["sha256"]:
            sys.exit(
                f"✗ {p['old']} 의 sha 가 대장과 다르다.\n"
                f"  대장 {p['sha256'][:16]} · 실물 {got[:16]}\n"
                "  개명 전에 acquire.py --verify 로 원인을 밝혀라.")
        shutil.move(str(src), str(dst))
        if sha256(dst) != got:
            sys.exit(f"✗ 개명 후 sha 불일치: {dst}")
        print(f"    ~ {p['old']}  →  {p['new']}")
        done.append(p)
        JOURNAL.write_text(json.dumps(
            {"at": datetime.now(KST).isoformat(timespec="seconds"),
             "moved": done}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
    return done


def cmd_rollback() -> int:
    if not JOURNAL.exists():
        print("저널이 없다. 되돌릴 것이 없다.")
        return 0
    j = json.loads(JOURNAL.read_text(encoding="utf-8"))
    for p in reversed(j["moved"]):
        if p.get("quarantined"):
            q, back = QUARANTINE / p["old"], RAW / p["old"]
            if q.exists() and not back.exists():
                back.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(q), str(back))
                print(f"  ← 격리해제 {p['old']}")
            continue
        src, dst = RAW / p["new"], RAW / p["old"]
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
            print(f"  ← {p['new']}  →  {p['old']}")
    print("\n★ 실물만 되돌렸다. sources.yaml · _acquire.json 은 git 으로 되돌려라 —")
    print("    git checkout -- sources.yaml data/_acquire.json")
    JOURNAL.unlink()
    return 0


def main() -> int:
    # ★ 관문. 레이크가 없으면 여기서 멈춘다 — 판정만 하고 안 막으면
    #   엉뚱한 곳에 계층을 만든다(2026-08-27).
    from firelane.paths import require_lake
    require_lake(need=("raw",))

    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true", help="실물을 실제로 옮긴다")
    ap.add_argument("--rollback", action="store_true")
    a = ap.parse_args()
    if a.rollback:
        return cmd_rollback()

    pairs = plan()
    print(f"═══ 개명 대상 {len(pairs)}건 ═══")
    for p in pairs:
        print(f"  {p['old']}\n    → {p['new']}")

    print("\n═══ 대장 file 확장자 와일드카드 ═══")
    for line in _fix_ext_wildcards(apply=False):
        print(f"  {line}")

    print("\n═══ 죽은 글롭 ═══")
    for line in _repair_globs(apply=False):
        print(f"  {line}")

    if not (a.apply and a.yes):
        print("\n아무것도 바꾸지 않았다. 실제로 하려면 —")
        print("    uv run python tools/migrate_names.py --apply --yes")
        print("\n★ 먼저 git 작업트리를 깨끗이 해라. 되돌릴 수 있어야 한다.")
        return 0

    # ★ 순서 — 대장 먼저, 실물 나중.
    print("\n① sources.yaml — 이름 치환")
    for line in _yaml_rewrite(pairs, apply=True):
        print(f"    {line}")
    print("② data/_acquire.json")
    _ledger_rewrite(pairs, apply=True)
    print(f"    키 {len(pairs)}건 갱신")
    print("③ raw 실물")
    _move_files(pairs)
    # ★ 확장자 확정은 **개명 뒤** 다. 앞에서 돌면 대장은 이미 새 이름을
    #   가리키는데 sha 대장은 아직 옛 이름이라 실물 조회가 0건이 된다.
    #   실증했다 — 2026-08-26 에 KFS 8건이 통째로 그렇게 빠졌다.
    #   확장자는 **실물을 봐야만** 정할 수 있으므로 순서가 강제된다.
    print("④ sources.yaml — 확장자 와일드카드 확정")
    for line in _fix_ext_wildcards(apply=True):
        print(f"    {line}")
    print("⑤ sources.yaml — 죽은 참조 복구")
    for line in _repair_globs(apply=True):
        print(f"    {line}")

    print("\n검증 —")
    print("    uv run python tools/acquire.py --verify")
    print("    uv run python tools/intake.py --audit")
    print("    uv run python -m pytest tests/ -q")
    print("\n실패하면 —")
    print("    uv run python tools/migrate_names.py --rollback")
    print("    git checkout -- sources.yaml data/_acquire.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
