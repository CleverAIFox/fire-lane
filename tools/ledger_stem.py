#!/usr/bin/env python3
"""
ledger_stem.py — [B] 대장에 `stem` 을 명시해 **역산을 조회로** 바꾼다.

    uv run python tools/ledger_stem.py            계획 + 무손실 검증
    uv run python tools/ledger_stem.py --apply

FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다

── 왜 ─────────────────────────────────────────────────────────
2026-08-27 하루에 같은 사고가 세 번 났다. 전부 한 뿌리다 —
**대장의 `file` 값에서 `provider_dataset` 을 역산**하고 있고, 그 역산이
서로 다르게 세 곳에 구현돼 있다.

    migrate_names.plan()          base = safety_kfs_pumptruck_kr_20251224
    normalize_raw._entry_for()    base = safety_kfs_pumptruck
    migrate_names._repair_globs() 또 다른 규칙

한 곳을 고칠 때마다 다른 곳을 안 봤다. 개명이 "0건" 으로 조용히 실패했고,
`ortho` 는 `stem.split("_")[2]` 로 도엽을 꺼내다 `KeyError: 'gj-dong'` 으로
파이프라인을 죽였고, `RULES` 의 `\\w+` 는 하이픈을 몰라 재취득 시
landing 에 갇히게 됐다.

★ **역산이 필요한 이유는 정본이 파생값이기 때문이다.** `file` 은
  `stem` · `scope` · `vintage` · `part` · `ext` 다섯을 이어 붙인 결과인데,
  대장이 결과만 적고 재료를 안 적었다. 그래서 도구가 결과를 뜯어 재료를
  복원해야 했고, 뜯는 방법이 도구마다 달랐다.

  재료를 적으면 역산이 사라진다. `file` 은 도구가 만들고 사람은 안 적는다.

── 새 스키마 ──────────────────────────────────────────────────
    stem      provider_dataset. 예: `safety_kfs_pumptruck`     [필수]
    scope     통제 어휘. 예: `kr` · `jngj-donggu`                 [필수]
    updated   ISO 갱신일. 파일명 vintage 는 여기서 유도          [필수]
    ext       확장자 목록. `.hwp` 와 `.pdf` 는 다른 자산이다     [필수]
    primary   파이프라인이 읽는 확장자                          [복수일 때]
    parts     도엽·분할본 목록                                  [선택]

    file/files  ★ 파생값. `_derive()` 가 만든다

── 무손실 증명 ────────────────────────────────────────────────
★ 이관의 안전성은 "파생값이 지금 값과 같다" 로 증명한다.
  같지 않으면 재료를 잘못 읽은 것이므로 **그 항목은 손대지 않고 보고만**
  한다. 전량 자동 변환은 하지 않는다 — 오늘 그것으로 세 번 데였다.

IN    sources.yaml
OUT   sources.yaml
PARAM 없음
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# 대장 조회기는 하나다(firelane.ledger.globs).
from firelane import ledger as _led

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "sources.yaml"

DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

# ★ 여러 파일이 **한 데이터셋**인 kind. `ingest.py:65` 가 그렇게 적고 있다.
#
#   `ngii1k` 이 그 예다 — SHP 판(74도엽)과 NGI 텍스트 판(143도엽)이
#   서로 다른 zip 인데 `collect()` 가 **도엽번호를 키로 병합**한다.
#   같은 도엽·같은 연도면 SHP 를 쓴다는 우선순위도 코드에 있다.
#
#   `_ngi` 는 도엽 조각이 아니라 **포맷 판**이라 `part` 로 표현이 안 된다.
#   파일명 문법상 `dataset` 토큰의 일부이므로 `stems` 복수로 적는다.
#
# ★ 묶음 kind 에만 허용한다. 단수 kind 에서 stem 이 여럿이면 여전히
#   오류다 — 2026-08-18 에 `src = hits[0]` 가 SHP 판만 쓰고 NGI 보완분
#   12도엽을 통째로 버려 755구간(69%)이 폴리곤 밖이었다.
#   "여럿이어도 괜찮다" 를 전역으로 열면 그 사고가 되돌아온다.
BUNDLE_KINDS = {"ngii1k", "ngii_1k", "shp_dir"}


def _vintage(e: dict) -> str | None:
    """파일명에 들어갈 8자리. `updated` 가 정본이다."""
    u = str(e.get("updated") or "")
    m = DATE.match(u)
    if m:
        return "".join(m.groups())
    v = str(e.get("vintage") or "")
    return v if re.fullmatch(r"\d{8}", v) else None


def _derive(stem: str, scope: str, vintage: str, ext: str,
            part: str | None = None) -> str:
    """재료 → 파일 경로. **여기가 유일한 조립 지점이다.**"""
    provider = stem.split("_", 1)[0]
    bits = [stem, scope, vintage] + ([part] if part else [])
    return f"{provider}/{'_'.join(bits)}.{ext}"


def read(key: str, e: dict) -> tuple[dict | None, str, list[str]]:
    """지금 항목에서 재료를 읽는다. 못 읽으면 (None, 사유, []).

    세 번째 값은 **비교 기준**이다 — 글롭 항목은 원문이 아니라 그것이
    실제로 잡는 실물 목록과 대조해야 한다. 원문과 비교하면 정확한
    파생값이 "어긋남" 으로 잡힌다(실증했다).
    """
    from firelane import naming as nm
    pats = [str(x) for x in
            _led.globs(e)]
    if not pats:
        return None, "file/files 가 없다", []
    if any(c in p for c in "*?[" for p in pats):
        # ★ 글롭은 **실물로 편다.** 대장이 패턴을 적는 이유는 도엽처럼
        #   여러 장이기 때문이고, 그 여러 장이 곧 `parts` 다. sha 대장이
        #   실물 목록을 갖고 있으므로 추측할 필요가 없다.
        #
        #   실물이 없으면 손을 뗀다 — 패턴만 보고 parts 를 지어내면
        #   그것이 또 하나의 역산이 된다.
        import fnmatch
        import json
        led_f = ROOT / "data" / "_acquire.json"
        if not led_f.exists():
            return None, "글롭인데 sha 대장이 없다 — raw 가 붙은 기계에서 돌려라", []
        led = json.loads(led_f.read_text(encoding="utf-8"))["files"]
        hit = sorted({r for p in pats for r in led if fnmatch.fnmatch(r, p)})
        if not hit:
            return None, (f"글롭이 실물 0건: {pats}\n"
                          "      raw 가 붙은 기계에서 돌려라 — 실물을 봐야 "
                          "parts 를 안 지어낸다"), []
        pats = hit

    stems, scopes, vints, parts, exts = set(), set(), set(), [], []
    for p in pats:
        try:
            n = nm.parse(p.rsplit("/", 1)[-1], strict=False)
        except nm.NameError_ as ex:
            return None, f"파싱 실패: {str(ex).splitlines()[0]}", []
        prov = p.split("/", 1)[0]
        if prov != n.provider:
            return None, f"폴더({prov}) ≠ provider({n.provider})", []
        stems.add(f"{n.provider}_{n.dataset}")
        scopes.add(n.scope)
        vints.add(n.vintage)
        exts.append(n.ext)
        if n.part:
            parts.append(n.part)
    if len(stems) > 1 and e.get("kind") not in BUNDLE_KINDS:
        return None, f"stem 이 여럿이다: {sorted(stems)}", []
    if len(scopes) > 1:
        return None, f"scope 가 여럿이다: {sorted(scopes)}", []
    if len(vints) > 1:
        return None, f"vintage 가 여럿이다: {sorted(vints)} — 판이 둘이다", []

    # ★ 같은 stem·scope·vintage 를 가진 raw 실물을 함께 본다.
    #
    #   순환이 있었다 — `.pdf` 가 대장에 없어서 `--quarantine` 이 내리고,
    #   내려가니 실물이 없어 대장에 못 들어간다. 그 둘이 서로를 막았다.
    #   2026-08-25 에 근거로 인용한 PDF 두 건이 그렇게 격리됐다.
    #
    #   대장이 `file` 로 가리키는 것만 보면 "지금 대장에 적힌 것" 밖으로
    #   못 나간다. **실물이 정본**이므로 stem·scope·vintage 가 같은
    #   형제 파일은 같은 자산의 다른 판이다. 그것까지 본다.
    #
    #   ★ 세 축이 전부 같아야 한다. 그래야 `fire-lane-gis.zip` 같은
    #     무관한 파일이 섞이지 않는다 — 관문의 정확도가 여기서도 요건이다.
    _st, _sc, _vt = sorted(stems)[0], sorted(scopes)[0], sorted(vints)[0]
    _acq = ROOT / "data" / "_acquire.json"
    if _acq.exists():
        import json as _json
        for rel in _json.loads(_acq.read_text(encoding="utf-8"))["files"]:
            if rel in pats:
                continue
            try:
                n2 = nm.parse(rel.rsplit("/", 1)[-1], strict=False)
            except nm.NameError_:
                continue
            if (f"{n2.provider}_{n2.dataset}" == _st and n2.scope == _sc
                    and n2.vintage == _vt and n2.part is None):
                exts.append(n2.ext)
                pats.append(rel)

    out = {"stems": sorted(stems), "scope": scopes.pop(),
           "vintage": vints.pop(), "ext": sorted(set(exts))}
    if parts:
        out["parts"] = sorted(set(parts))
    if len(out["stems"]) == 1:
        out["stem"] = out.pop("stems")[0]
    if len(out["ext"]) > 1:
        prim = e.get("primary")
        prim = str(prim).rsplit(".", 1)[-1] if prim else None
        out["primary"] = prim if prim in out["ext"] else out["ext"][0]
    return out, "", sorted(pats)


def verify(mat: dict, now: list[str]) -> tuple[bool, list[str]]:
    """★ 무손실 증명 — 재료로 만든 것이 실물 목록과 같은가."""
    got = sorted(
        _derive(st, mat["scope"], mat["vintage"], x, p)
        for st in (mat.get("stems") or [mat["stem"]])
        for x in mat["ext"] for p in (mat.get("parts") or [None]))
    return got == now, got


def run(*, apply: bool) -> int:
    s = YAML.read_text(encoding="utf-8")
    d = yaml.safe_load(s) or {}
    ds = d.get("datasets") or {}
    ok, skip, drift = [], [], []

    for key, e in ds.items():
        mat, why, now = read(key, e)
        if mat is None:
            skip.append((key, why))
            continue
        cur = str(e.get("scope") or "")
        if cur and cur != mat["scope"]:
            # ★ 대장의 `scope` 가 산문이면 파일명이 이긴다.
            #   `광주 동구 74도엽` 은 통제 어휘가 아니고, 게다가 지금은
            #   부정확하다 — SHP 74 + NGI 143 이다. 숫자는 note 로 간다.
            mat["scope_was"] = cur
        v = _vintage(e)
        if v and v != mat["vintage"]:
            drift.append((key, f"updated({v}) ≠ 파일명 vintage"
                               f"({mat['vintage']})"))
            continue
        same, got = verify(mat, now)
        if not same:
            drift.append((key, f"파생 {got} ≠ 현재"))
            continue
        ok.append((key, mat))

    print(f"═══ 무손실 이관 가능 {len(ok)}건 ═══")
    for key, m in ok[:6]:
        p = f" parts={m['parts']}" if "parts" in m else ""
        st = ("stems=" + ",".join(m["stems"])) if "stems" in m \
            else "stem=" + m["stem"]
        print(f"  {key:24} {st:32} {m['scope']:11} "
              f"{m['vintage']} {m['ext']}{p}")
    if len(ok) > 6:
        print(f"  … 외 {len(ok) - 6}건")

    if skip:
        print(f"\n═══ 사람 판단 {len(skip)}건 ═══")
        for key, why in skip:
            print(f"  {key:24} {why}")
    if drift:
        print(f"\n═══ ★ 어긋남 {len(drift)}건 — 손대지 않는다 ═══")
        for key, why in drift:
            print(f"  {key:24} {why}")

    if not apply:
        print("\n아무것도 바꾸지 않았다.  --apply 로 기입한다.")
        return 0

    # ★ 멱등 — 관리 필드를 **먼저 걷어내고** 다시 넣는다.
    #   종전에는 무조건 삽입해서 --apply 를 두 번 돌리면 stem·ext 가
    #   두 줄씩 들어갔다. YAML 은 뒤 값이 이기므로 동작은 하지만 대장이
    #   지저분해지고 "무엇이 정본인가" 가 눈으로 안 갈린다.
    #
    #   블록을 통째로 다시 쓴다. 부분 치환은 인덱스가 어긋나기 쉽다.
    MANAGED = ("stem", "stems", "ext", "primary", "parts")
    wrote = 0
    for key, m in ok:
        blk = re.search(
            rf"^(  {re.escape(key)}:\n)((?:    .*\n|      .*\n|\n)*)", s, re.MULTILINE)
        if not blk:
            continue
        head, body = blk.group(1), blk.group(2)
        for f in MANAGED:
            body = re.sub(rf"^    {f}:.*\n", "", body, flags=re.MULTILINE)
        if m.get("scope_was"):
            body = re.sub(r"^    scope:.*\n", "", body, count=1, flags=re.MULTILINE)
        add = ["    stems: [{}]".format(", ".join(m["stems"]))
               if "stems" in m else f"    stem: {m['stem']}",
               "    ext: [{}]".format(", ".join(m["ext"]))]
        if "primary" in m:
            add.append(f"    primary: {m['primary']}")
        if "parts" in m:
            add.append("    parts: [{}]".format(", ".join(m["parts"])))
        if m.get("scope_was"):
            add.append(f"    scope: {m['scope']}"
                       f"        # 종전 {m['scope_was']!r} — 산문이었다")
        s = s[:blk.start()] + head + "\n".join(add) + "\n" + body + s[blk.end():]
        wrote += 1

    yaml.safe_load(s)
    YAML.write_text(s, encoding="utf-8")
    print(f"\n기입 {wrote}건 · YAML 파싱 OK")
    print("★ file/files 는 아직 지우지 않았다. 도구가 stem 을 읽도록")
    print("  바꾼 뒤에 지운다 — 한 번에 둘을 바꾸면 무엇이 깨졌는지 모른다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    return run(apply=ap.parse_args().apply)


if __name__ == "__main__":
    sys.exit(main())
