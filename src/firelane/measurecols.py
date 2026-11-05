#!/usr/bin/env python3
"""
measurecols.py — 측정 절의 「쓴 칸」 머릿줄을 **기계가 강제한다.**  (PLAN #193 · DECISIONS §631-5 · §637)

    uv run python -m firelane.measurecols            DECISIONS 의 측정 절을 전부 본다(rc 1 = 위반)
    uv run python -m firelane.measurecols --section 635

── 왜 있나 ────────────────────────────────────────────────────
「측정 스크립트는 저장소에 들이지 않는다」(§622-2)는 규약은 일회성 조사를 **어떤 검사도 안 보는** 안전지대로 만들었고, 2026-11-04 의 `#39` 측정이 그 안에서
틀렸다(신고자 휴대폰 좌표를 위치로 쓴 572쌍 · `HSPTL_ARVL_DT` 공백 문자열을 `notna()` 로 센 구급 가르기). 스크립트는 못 들여도 **쓴 칸은 선언에 묶을 수 있다.**

── 무엇을 보나 ────────────────────────────────────────────────
측정 절(2026-11-05 §635 이후 번호의 절 중 제목에 `측정` · `EDA` 가 들었거나 `쓴 칸` 줄이 있는 것)은 머릿줄에 `쓴 칸  <원천>.<칸>(<역할> · <메모>) · …` 를 적는다
(`<원천>.` 는 앞 항목을 이어받으면 생략 · `A/B` 는 칸 둘 · 칸을 안 읽는 측정은 `쓴 칸  없음 — 사유: …`). 역할 어휘는 닫혀 있다(`ROLES`).
  ① 칸이 대장 `schema.columns` 에 **실재**하는가(오탈자 · 없는 원천)
  ② 역할 `위치` 의 칸은 `coords:` 가 **위치로 써도 된다고** 말하는가 — `not_for` 에 `위치 분석` 이 든 칸(신고자 휴대폰) · 좌표 없음 선언 · 지목 없는 칸 ·
     뜻이 `미확인` 인데 메모에 `미확인` 이 없는 칸은 운다
  ③ 역할 `시각` · `가르기` 의 칸이 **「없음」을 가지면**(프로필이 재거나 `none:` 이 선언했으면) `none:` 선언이 있고 메모에 `없음=…` 이 있는가
  ④ **빠뜨림 방지** — 본문의 백틱 토큰 중 `<원천>.<칸>`(대장에 실재) 과 **좌표 칸 이름**이 `쓴 칸` 에 없으면 운다. 적은 것만 보면 안 적은 칸이 안전지대가 된다.

IN    docs/DECISIONS.md · sources.yaml(`coords` · `none` · `schema`)
OUT   없음
밖    **측정이 옳은가는 안 본다** · **소급하지 않는다**(`START` 앞 절에는 이 머릿줄이 없다) · 본문에 칸을 아예 안 적고 머릿줄도 안 적은 측정은 **못 본다**(자기 선언의 한계) ·
      **발행 코드는 안 본다**(그것은 `tests/test_coord_literals.py` 의 몫 — DECISIONS §637-3).
"""
from __future__ import annotations

import argparse
import re
import sys

from firelane import ledger as led
from firelane.paths import ROOT

START = 635
SCOPE_WORDS = ("측정", "EDA")
#: 닫힌 어휘 — 오타(`위친`)가 검사를 조용히 건너뛰게 두지 않는다.
ROLES = ("위치", "위치 비교 대상", "시각", "가르기", "거리", "소요", "센터", "차종", "판 가르기")
ITEM = re.compile(r"^(?:(?P<src>[a-z][a-z0-9_]*)\.)?(?P<cols>[\w가-힣]+(?:/[\w가-힣]+)*)\((?P<role>[^)·]+?)\s*(?:·\s*(?P<note>[^)]*))?\)")
TOKEN = re.compile(r"`([^`\n]+)`")
PREFIXED = re.compile(r"^([a-z][a-z0-9_]*)\.([^\s.`/]+)$")


def sections(text: str) -> list[tuple[int, str, str]]:
    """DECISIONS 원문 → `(번호, 제목, 본문)`. 절 머리는 `## N. 제목` 이다."""
    marks = list(re.finditer(r"^## (\d+)\. (.*)$", text, re.M))
    return [(int(m.group(1)), m.group(2), text[m.end():(marks[i + 1].start() if i + 1 < len(marks) else len(text))])
            for i, m in enumerate(marks)]


def _top_split(s: str) -> list[str]:
    out, depth, cur, i = [], 0, "", 0
    while i < len(s):
        depth += s[i] in "({[" ; depth -= s[i] in ")}]"
        if depth == 0 and s.startswith(" · ", i):
            out.append(cur.strip()); cur, i = "", i + 3
            continue
        cur += s[i]; i += 1
    return out + [cur.strip()]


def used_line(body: str) -> str | None:
    m = re.search(r"^쓴 칸[ \t]+(.+)$", body, re.M)
    return m.group(1).replace("`", "") if m else None


def parse_used(line: str) -> tuple[list[dict], list[str]]:
    """머릿줄 → (항목들, 문법 오류). 항목 `{src, col, role, note}` — `A/B` 는 둘로 펴고 `<원천>.` 생략은 앞 항목에서 잇는다."""
    items, errs, src = [], [], None
    for raw in _top_split(line):
        m = ITEM.match(raw)
        if not m:
            errs.append(f"쓴 칸 항목을 못 읽는다 — `{raw[:50]}` (형식: 원천.칸(역할 · 메모))")
            continue
        src = m.group("src") or src
        role, note = m.group("role").strip(), (m.group("note") or "").strip()
        head = None
        for c in m.group("cols").split("/"):
            # `DCLR_PSTN_LAT/LOT` 의 꼬리는 앞 칸의 접두를 잇는 것일 수 있다 — 어느 쪽이 실재하는지는 대장을 아는 쪽(`check_section`)이 고른다
            alt = head.rsplit("_", 1)[0] + "_" + c if head and "_" in head else None
            items.append({"src": src, "col": c, "alt": alt, "role": role, "note": note})
            head = head or c
    return items, errs


def _cols(e: dict) -> set[str]:
    return {str(c) for c in ((e.get("schema") or {}).get("columns") or [])}


def check_section(num: int, title: str, body: str, ledger: dict) -> list[str]:
    ds = ledger.get("datasets") or {}
    line = used_line(body)
    if line is None:
        return [f"§{num} 측정 절인데 `쓴 칸` 머릿줄이 없다 — `쓴 칸  원천.칸(역할 · 메모) · …`(칸을 안 읽으면 `쓴 칸  없음 — 사유: …`)"]
    body_wo = body.replace(line, "")
    toks = {t.strip() for t in TOKEN.findall(body_wo)}
    pre = {(m.group(1), m.group(2)) for t in toks if (m := PREFIXED.match(t)) and m.group(1) in ds and m.group(2) in _cols(ds[m.group(1)])}
    if line.startswith("없음"):
        return ([] if re.match(r"없음 — 사유[:：]\s*\S", line) else [f"§{num} `쓴 칸  없음` 은 `— 사유: …` 가 따라야 한다"]) + \
            [f"§{num} 쓴 칸을 `없음` 이라 했는데 본문이 `{s}.{c}` 를 쓴다" for s, c in sorted(pre)]
    items, errs = parse_used(line)
    errs = [f"§{num} {e}" for e in errs]
    used = set()
    for it in items:
        s, c, role, note = it["src"], it["col"], it["role"], it["note"]
        if it["alt"] and s in ds and c not in _cols(ds[s]) and it["alt"] in _cols(ds[s]):
            c = it["alt"]
        used.add((s, c))
        tag = f"§{num} {s}.{c}({role})"
        if role not in ROLES:
            errs.append(f"{tag} — 역할은 {list(ROLES)} 중 하나"); continue
        e = ds.get(s)
        if e is None:
            errs.append(f"{tag} — 대장에 원천 `{s}` 가 없다"); continue
        if _cols(e) and c not in _cols(e):
            errs.append(f"{tag} — `{s}` 의 schema.columns 에 `{c}` 가 없다"); continue
        if role in ("위치", "위치 비교 대상"):
            co = led.coords_decl(e) or {}
            roles = {str(d[a]): (r, d) for r, d in co.items() if isinstance(d, dict) for a in ("x", "y") if a in d}
            if "none" in co:
                errs.append(f"{tag} — 대장이 「좌표가 없다」고 선언했다({co['none']})")
            elif c not in roles:
                errs.append(f"{tag} — `coords:` 가 지목하지 않은 칸이다 — 어느 칸이 무엇의 위치인지 대장에 먼저 적는다")
            elif c in roles and role == "위치":
                r, d = roles[c]
                if "위치 분석" in (d.get("not_for") or []):
                    errs.append(f"{tag} — coords.{r}({d.get('means')})는 `위치 분석` 에 쓰지 않는다(not_for)")
                elif r == "unconfirmed" and "미확인" not in note:
                    errs.append(f"{tag} — 뜻이 `미확인` 인 칸이다 — 메모에 `미확인` 을 적어 알고 쓴다고 밝힌다")
        if role in ("시각", "가르기"):
            st = (((e.get("schema") or {}).get("profile") or {}).get("cols") or {}).get(c) or {}
            has_none = any(st.get(k) for k in ("empty", "ws", "sentinel", "text_none")) or bool(led.none_forms(e, c))
            if has_none and not led.none_forms(e, c):
                errs.append(f"{tag} — 이 칸에 「없음」이 있는데 대장 `none:` 선언이 없다")
            if has_none and "없음=" not in note:
                errs.append(f"{tag} — 이 칸은 「없음」을 가진다 — 메모에 `없음=…` 을 적는다(선언 {sorted(led.none_forms(e, c))})")
    names = {str(d[a]) for e in ds.values() for d in (led.coords_decl(e) or {}).values() if isinstance(d, dict) for a in ("x", "y") if a in d}
    have = {c for _, c in used}
    errs += [f"§{num} 본문이 `{s}.{c}` 를 쓰는데 `쓴 칸` 에 없다" for s, c in sorted(pre - used)]
    errs += [f"§{num} 본문이 좌표 칸 `{t}` 를 쓰는데 `쓴 칸` 에 없다" for t in sorted(toks & names - have)]
    return errs


def check_all(ledger: dict | None = None, text: str | None = None) -> list[str]:
    ledger = ledger if ledger is not None else led.load_sources()
    text = text if text is not None else (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    out = []
    for num, title, body in sections(text):
        if num >= START and (any(w in title for w in SCOPE_WORDS) or used_line(body) is not None):
            out += check_section(num, title, body, ledger)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="측정 절의 쓴 칸 머릿줄")
    ap.add_argument("--section", type=int, help="번호 하나만(소급 확인용 — START 앞 절도 본다)")
    a = ap.parse_args(argv)
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    ledger = led.load_sources()
    if a.section:
        errs = [e for n, t, b in sections(text) if n == a.section for e in check_section(n, t, b, ledger)]
    else:
        errs = check_all(ledger, text)
    for e in errs:
        print(f"  ✗ {e}")
    print(f"측정 절의 쓴 칸 — {'위반 ' + str(len(errs)) + '건' if errs else 'OK'}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
