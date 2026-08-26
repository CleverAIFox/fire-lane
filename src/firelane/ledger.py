#!/usr/bin/env python3
"""
ledger.py — 대장 항목 스키마의 정본. **산문을 필드로 바꾼다.**

── 왜 ─────────────────────────────────────────────────────────
`sources.yaml` 은 이미 대장 노릇을 하고 있고 내용도 두껍다. 문제는 그 두께가
**산문**이라는 것이다. `feeds: 미투입 — STEP 4 관측점 랜드마크 후보` 는
사람은 읽지만 기계는 못 읽는다. 그래서 "지금 아무도 안 쓰는 소스가 몇 개냐"
를 물으면 사람이 눈으로 세야 하고, 실제로 2026-08-26 에 손으로 세다가
네 건을 틀렸다(PLAN #23 — `node_point` · `fire_access` · `enforcement` ·
`hydrant_summary` 가 이미 코드에 붙어 있었다).

**세어야 하는 것은 필드여야 한다.** 산문은 그 옆에 남긴다.

── 항목 스키마 ────────────────────────────────────────────────
    what        한 줄. 무슨 데이터인가                        [필수]
    provider    제공기관                                       [필수]
    scope       행정 범위. firelane.scope 통제 어휘            [필수]
    authority   관할기관. ★ 행정구역과 경계가 다르다           [선택]
    updated     데이터 갱신일. 다운로드일이 아니다             [필수]
    acquired    우리가 받은 날                                 [필수]
    license     이용 조건. TODO 금지                           [필수]
    files       실물 파일 목록. 와일드카드 금지                [필수]
    primary     그중 파이프라인이 읽는 하나                    [단수 kind 필수]
    encoding    선언 인코딩. 실물과 대조된다                   [텍스트 필수]
    schema      구조 — columns / layers / key                  [필수]
    feeds       ★ 구조화. 소비자 키의 리스트                   [필수]
    grade       활용도. **자동 산출이며 손으로 쓰지 않는다**
    note        산문. 주의사항                                 [선택]

── 활용도(grade) ──────────────────────────────────────────────
    active      파이프라인이 읽고 산출물에 반영된다
    reference   보관·대조용. 읽되 판정에 안 들어간다 (raw_only)
    unused      ★ feeds 가 비었다. R4 대상 — raw 에 둘 이유를 못 댄다
    declared    선언만 있고 실물이 없다 (pending)

`grade` 를 사람이 못 쓰게 하는 것이 요점이다. 쓸 수 있으면 낙관적으로 적고,
그러면 "안 쓰이는 소스" 목록이 영원히 비어 있는다.

IN    sources.yaml
OUT   없음 (검증 전용)
PARAM 없음
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from firelane import naming as nm
from firelane import paths
from firelane import scope as sc

REQUIRED = ("what", "provider", "scope", "updated", "acquired",
            "license", "files", "schema", "feeds")

# 텍스트 소스는 인코딩 선언이 있어야 한다. 실물과 대조하기 위해서다.
TEXT_KINDS = {"csv_points", "csv_table", "csv_table_multi",
              "csv_points_in_zip", "csv_point", "json_points"}
# hits[0] 하나만 읽는 kind. 여러 파일이 걸리면 조용히 뒤집힌다.
SINGLE_PICK = TEXT_KINDS | {"shp_zip", "dbf_in_zip"}

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FORBIDDEN_VALUES = {"TODO", "todo", "TBD", "?", "-", ""}

FAIL, WARN = "FAIL", "WARN"


@dataclass
class Issue:
    level: str
    key: str
    msg: str

    def __str__(self) -> str:
        return f"{self.level} [{self.key}] {self.msg}"


def load() -> dict:
    f = paths.ROOT / "sources.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8")) or {}


# ── 활용도 ────────────────────────────────────────────────────
def grade(entry: dict) -> str:
    """**자동 산출.** 대장에 적힌 값이 있어도 무시한다."""
    feeds = entry.get("feeds")
    if isinstance(feeds, str):
        # 산문이다. 아직 마이그레이션 전이므로 판정을 보류한다.
        return "prose"
    if not feeds:
        return "unused"
    if entry.get("kind") == "raw_only":
        return "reference"
    return "active"


def check_entry(key: str, e: dict) -> list[Issue]:
    out: list[Issue] = []

    def bad(v) -> bool:
        return v is None or (isinstance(v, str) and v.strip() in FORBIDDEN_VALUES)

    for f in REQUIRED:
        if f not in e:
            out.append(Issue(FAIL, key, f"필수 필드 없음: {f}"))
        elif bad(e[f]):
            out.append(Issue(FAIL, key, f"{f} 가 비었거나 TODO 다: {e[f]!r}"))

    # ── 스코프 ────────────────────────────────────────────────
    s = e.get("scope")
    if isinstance(s, str) and s not in FORBIDDEN_VALUES:
        try:
            alias, state = sc.resolve(s)
            if state != "ok":
                out.append(Issue(WARN, key,
                                 f"스코프 토큰 {s!r} 가 정규형이 아니다 → {alias!r}"))
            elif not sc.covers_project(alias):
                out.append(Issue(
                    FAIL, key,
                    f"스코프 {alias!r}({sc.label(alias)}) 가 분석 대상을 덮지 "
                    "않는다. 결손이 조용히 난다 — 2026-08-18 도엽 누락과 같은 형태"))
        except sc.ScopeError as ex:
            out.append(Issue(FAIL, key, str(ex).splitlines()[0]))

    # ── 날짜 ──────────────────────────────────────────────────
    for f in ("updated", "acquired"):
        v = e.get(f)
        if isinstance(v, str) and not DATE.match(v):
            out.append(Issue(WARN, key, f"{f} 가 YYYY-MM-DD 가 아니다: {v!r}"))
    if isinstance(e.get("updated"), str) and isinstance(e.get("acquired"), str):
        if DATE.match(e["updated"]) and DATE.match(e["acquired"]):
            if e["acquired"] < e["updated"]:
                out.append(Issue(
                    FAIL, key,
                    f"갱신일({e['updated']}) 이 취득일({e['acquired']}) 보다 "
                    "뒤다. 아직 없던 판을 받을 수는 없다"))

    # ── 파일 ──────────────────────────────────────────────────
    files = e.get("files")
    if files is None and "file" in e:
        out.append(Issue(WARN, key,
                         "`file` 단수는 옛 형식이다. `files:` 리스트로 옮긴다"))
        files = [e["file"]]
    for f in (files or []):
        for m in nm.audit_pattern(f):
            out.append(Issue(FAIL, key, m.splitlines()[0]))
    if e.get("kind") in SINGLE_PICK and files and len(files) > 1:
        if not e.get("primary"):
            out.append(Issue(
                FAIL, key,
                f"kind={e['kind']} 는 하나만 읽는데 files 가 {len(files)}개다. "
                "`primary:` 로 못박아라 — 안 그러면 hits[0] 가 조용히 뒤집힌다"))
        elif e["primary"] not in files:
            out.append(Issue(FAIL, key,
                             f"primary 가 files 에 없다: {e['primary']!r}"))

    # ── 인코딩 ────────────────────────────────────────────────
    if e.get("kind") in TEXT_KINDS and not e.get("encoding"):
        out.append(Issue(FAIL, key,
                         "텍스트 소스인데 encoding 선언이 없다 — 실물과 대조할 수 없다"))

    # ── 스키마 ────────────────────────────────────────────────
    schema = e.get("schema")
    if isinstance(schema, dict):
        if not (schema.get("columns") or schema.get("layers")):
            out.append(Issue(WARN, key, "schema 에 columns 도 layers 도 없다"))
    elif schema is not None:
        out.append(Issue(FAIL, key, "schema 는 매핑이어야 한다"))

    # ── 활용도 ────────────────────────────────────────────────
    if "grade" in e:
        out.append(Issue(FAIL, key,
                         "grade 는 자동 산출이다. 대장에 손으로 쓰지 않는다"))
    g = grade(e)
    if g == "prose":
        out.append(Issue(WARN, key,
                         "feeds 가 산문이다. 소비자 키 리스트로 옮긴다 — "
                         "산문은 셀 수 없고, 못 세면 R4 를 손으로 세다 틀린다"))
    elif g == "unused":
        out.append(Issue(WARN, key,
                         "★ feeds 가 비었다(R4). raw 에 둘 이유를 대거나 "
                         "retired 로 내린다"))
    return out


def check_all() -> list[Issue]:
    d = load()
    out: list[Issue] = []
    ds = d.get("datasets") or {}
    for k, e in ds.items():
        out += check_entry(k, e)

    # 같은 실물을 두 항목이 다른 스코프로 적으면 하나는 틀린 것이다.
    byfile: dict[str, list[tuple[str, str]]] = {}
    for k, e in ds.items():
        for f in (e.get("files") or ([e["file"]] if "file" in e else [])):
            byfile.setdefault(f, []).append((k, str(e.get("scope"))))
    for f, rows in byfile.items():
        scopes = {s for _, s in rows}
        if len(scopes) > 1:
            out.append(Issue(
                FAIL, ",".join(k for k, _ in rows),
                f"같은 파일 {f} 를 서로 다른 스코프로 적는다: {sorted(scopes)}"))
    return out


def summary() -> dict[str, int]:
    ds = load().get("datasets") or {}
    tally: dict[str, int] = {}
    for e in ds.values():
        g = grade(e)
        tally[g] = tally.get(g, 0) + 1
    return tally


if __name__ == "__main__":
    import sys
    issues = check_all()
    for i in issues:
        print(i)
    print(f"\nFAIL {sum(i.level == FAIL for i in issues)} · "
          f"WARN {sum(i.level == WARN for i in issues)}")
    print("활용도 —", summary())
    sys.exit(1 if any(i.level == FAIL for i in issues) else 0)
