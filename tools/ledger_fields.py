#!/usr/bin/env python3
"""
ledger_fields.py — 대장의 별칭 필드를 통합하고, 유도 가능한 것을 채운다.

FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다
  `test_no_source_patching_scripts` 의 예외 마커. 이 도구는 대장(데이터)만
  고치고 소스 코드는 건드리지 않는다. 대장 값은 저장소 밖 raw 실물에서
  나오므로 diff 로 담을 수 없다.

    uv run python tools/ledger_fields.py           계획만
    uv run python tools/ledger_fields.py --apply

── 무엇이 문제였나 ────────────────────────────────────────────
`firelane.ledger` 가 필수 필드 결손을 180건 냈는데, 그중 상당수는 결손이
아니라 **같은 뜻의 필드가 두 이름으로 살아 있는 것**이었다.

    데이터 기준일   vintage    27건   ↔  updated    10건
    취득일          retrieved  23건   ↔  acquired   10건
    한 줄 설명      desc       22건   ↔  what       36건

한 축에 이름이 둘이면 검사는 둘 다 봐야 하고, 사람은 아무 쪽에나 적는다.
이 저장소가 `params.py` ↔ `config.js` 에서 세운 규칙 그대로다 —
**정본은 하나고 나머지는 사본이거나 없어야 한다.**

── updated 를 무엇으로 채우나 ─────────────────────────────────
★ `vintage` 를 그대로 옮기지 않는다. 값이 `2026`(연도만) 이 25건이고
  `updated` 는 `2025-12-24`(ISO) 다. **같은 축인데 정밀도가 다르다.**
  옮기면 `updated: 2026` 이 되어 ISO 검사에 걸리고, 정밀도도 잃는다.

  정본은 **파일명의 vintage 토큰**이다. 이미 명명 규칙이 8자리로
  정규화해 놓았고(`juso_elctrnmap_jngj_20260711` → 2026-07-11),
  실물과 어긋날 수 없다. 파일명이 대장을 채우는 것이 아니라, **둘 다
  같은 사실의 표현이고 더 정밀한 쪽을 남기는 것**이다.

  8자리를 못 얻으면 채우지 않는다. 추측하지 않는다.

── 무엇을 안 하나 ─────────────────────────────────────────────
    provider   기관명은 산문이다(`소방청` · `브이월드`). 폴더 코드(`safety`)
               와 다르고, `safety/` 안에 소방청과 공공데이터포털이 섞여
               있다. 자동으로 못 채운다 — 후보만 제시한다
    schema     실물을 읽어야 한다. 별도 도구
    feeds      코드를 읽어야 한다. 별도 도구

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

from firelane import ledger as _led
from firelane import providers

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "sources.yaml"

# 옛 이름 → 정본. 값이 그대로 옮겨가도 되는 것만.
ALIAS = {"retrieved": "acquired", "desc": "what"}

# 폴더 코드 → 기관명 후보. **자동 적용하지 않는다.** 제시만 한다.
# ★ 2026-08-27. 여기 8종이 하드코딩돼 있었다(nsdi 없음). 같은 목록이
#   여섯 곳에 있었고 값이 갈려 있었다. 정본은 layers.raw.providers 다.
#   `safety` 처럼 기관이 섞인 것은 등재 쪽 org 에 적는다 — 힌트가 두
#   군데면 어느 쪽이 맞는지 다음 사람이 판단해야 한다.
PROVIDER_HINT = {k: v["org"] for k, v in providers.spec().items()}

DATE8 = re.compile(r"_(\d{8})(?:_|\.)")


def _iso(v8: str) -> str:
    return f"{v8[:4]}-{v8[4:6]}-{v8[6:8]}"


def load() -> str:
    return YAML.read_text(encoding="utf-8")


def _entry_span(s: str, key: str) -> tuple[int, int, str]:
    """`  key:` 블록의 (본문 시작, 본문 끝, 본문). datasets 항목은 2칸이다."""
    m = re.search(rf"^  {re.escape(key)}:\n", s, re.MULTILINE)
    if not m:
        return -1, -1, ""
    body = re.search(rf"^  {re.escape(key)}:\n((?:    .*\n|\n)*)", s, re.MULTILINE)
    return m.end(), m.end() + len(body.group(1)), body.group(1)


def _has(body: str, field: str) -> bool:
    return re.search(rf"^    {re.escape(field)}:", body, re.MULTILINE) is not None


def _drop(body_text: str, field: str) -> str:
    """`    field:` 줄과 그에 딸린 블록 스칼라를 지운다."""
    return re.sub(
        rf"^    {re.escape(field)}:.*\n(?:      .*\n|\n(?=      ))*", "",
        body_text, count=1, flags=re.MULTILINE)


def run(*, apply: bool) -> int:
    s = load()
    d = yaml.safe_load(s) or {}
    ds = d.get("datasets") or {}
    plan: list[tuple[str, str, str]] = []      # (key, 동작, 설명)
    hints: list[str] = []

    for key, e in ds.items():
        # ── ① 별칭 통합 ───────────────────────────────────────
        for old, new in ALIAS.items():
            if old not in e:
                continue
            if new in e:
                a, b = str(e[new]).strip(), str(e[old]).strip()
                if a == b or b.startswith(a[:20]):
                    plan.append((key, "drop", f"{old} (={new})"))
                else:
                    plan.append((key, "keep", f"★ {old} 와 {new} 가 다르다 — "
                                              "손으로 합쳐라"))
            else:
                plan.append((key, "rename", f"{old} → {new}"))

        # ── ② updated — 파일명 8자리에서 ──────────────────────
        if "updated" not in e:
            fn = " ".join(_led.globs(e))
            m = DATE8.search(fn + ".")
            if m:
                plan.append((key, "add", f"updated: '{_iso(m.group(1))}'"))
            else:
                plan.append((key, "skip", "updated — 파일명에 8자리가 없다"))

        # ── ③ scope — 파일명 토큰에서 · 산문은 매핑 ───────────
        cur = e.get("scope")
        if isinstance(cur, str) and cur.strip() in ("전국",):
            plan.append((key, "set", "scope: kr   (산문 '전국')"))
        elif isinstance(cur, str) and cur not in ("kr",) and " " in cur:
            plan.append((key, "keep", f"★ scope 산문 {cur!r} — 손으로 정하고 "
                                      "원문은 note 로 옮겨라"))
        elif cur is None:
            from firelane import scope as sc
            fn = ((_led.globs(e) or [""])[0]
                  .rsplit("/", 1)[-1].rsplit(".", 1)[0])
            toks = [b for b in fn.split("_") if sc.known(b) or b in sc.LEGACY]
            if len(toks) == 1:
                alias, _ = sc.resolve(toks[0])
                plan.append((key, "add", f"scope: {alias}"))
            else:
                plan.append((key, "skip", f"scope — 파일명 토큰 {toks or '없음'}"))

        # ── ④ files — file 단수를 리스트로 ────────────────────
        # ★ 2026-08-30. `file` 단수는 대장에서 완전히 사라졌다(42/42 가
        #   `files:` 리스트다). 이 계획문은 영원히 안 나온다 — 남겨두면
        #   "아직 할 일이 있다" 로 읽힌다. 마이그레이션은 끝났다.
        pass

        # ── ⑤ provider — 후보만 ──────────────────────────────
        if "provider" not in e:
            folder = (_led.globs(e) or [""])[0].split("/", 1)[0]
            hints.append(f"  {key:22} {PROVIDER_HINT.get(folder, '?')}")

    # ── 출력 ──────────────────────────────────────────────────
    from collections import Counter
    c = Counter(a for _, a, _ in plan)
    for key, act, msg in plan:
        if act in ("keep", "skip"):
            print(f"  {act:6} [{key}] {msg}")
    print(f"\n자동 {c['rename'] + c['add'] + c['set'] + c['drop']}건 "
          f"(rename {c['rename']} · add {c['add']} · set {c['set']} · "
          f"drop {c['drop']}) · 손 판단 {c['keep'] + c['skip']}건")

    if hints:
        print(f"\n── provider 후보 {len(hints)}건 (자동 적용하지 않는다) ──")
        for h in hints[:8]:
            print(h)
        if len(hints) > 8:
            print(f"  … 외 {len(hints) - 8}건")

    if not apply:
        print("\n아무것도 바꾸지 않았다.  --apply 로 적용한다.")
        return 0

    # ── 적용 — 텍스트 편집. round-trip 하면 주석 1,500줄이 날아간다 ──
    for key, act, msg in plan:
        st, en, body = _entry_span(s, key)
        if st < 0:
            continue
        new_body = body
        if act == "rename":
            old, new = msg.split(" → ")
            new_body = re.sub(rf"^    {old}:", f"    {new}:", new_body,
                              count=1, flags=re.MULTILINE)
        elif act == "drop":
            new_body = _drop(new_body, msg.split()[0])
        elif act in ("add", "set"):
            field = msg.split(":")[0]
            val = msg.split(":", 1)[1].split("#")[0].strip()
            if act == "set":
                val = val.split()[0]
                new_body = _drop(new_body, field)
            if field == "files":
                val = val.strip("[]")
                new_body = f"    files:\n      - {val}\n" + new_body
            else:
                new_body = f"    {field}: {val}\n" + new_body
        if new_body != body:
            s = s[:st] + new_body + s[en:]

    yaml.safe_load(s)          # ★ 즉시 검증
    YAML.write_text(s, encoding="utf-8")
    print("\n적용 완료 · YAML 파싱 OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    return run(apply=ap.parse_args().apply)


if __name__ == "__main__":
    sys.exit(main())
