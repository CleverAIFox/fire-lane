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
    stem        실물 파일 접두. ext 와 짝을 이룬다              [필수]
    files       stem 으로 못 가르는 항목의 글롭 예외            [선택]
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
                사유를 `feeds_why` 에 적으면 판정은 남고 경보만 거둔다
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

# ★ 2026-08-30. provider · acquired · license 는 대장 재작성에서 제거된
#   필드다. 여기 남겨두면 검증기가 대장 42종을 전부 거부한다(126 FAIL).
#   **파생값을 지우려면 그것을 읽는 곳이 하나여야 한다** — 이 줄이 그
#   원칙을 어긴 열한 번째 자리였고, 하필 그 원칙을 강제하는 도구다.
# ★ 2026-08-31. `files` 를 필수에서 뺐다(PLAN #46). 실물 경로의 정본은
#   `stem` + `ext` 이고 `files` 는 그것으로 표현 못 하는 항목만 남는
#   **글롭 예외**다. 종전에는 두 자리가 같은 것을 따로 요구했다 —
#   `globs()` 는 `files` 를 읽고 `REQUIRED` 는 그 존재를 강제했다.
#   그래서 `globs()` 만 stem 우선으로 바꾸면 37종이 "필수 필드 없음"
#   으로 죽는다. 실제로 그렇게 죽였고 `golden` 은 초록불이었다 —
#   `segments.geojson` 만 읽으니 대장이 깨진 것을 모른다.
REQUIRED = ("what", "scope", "updated", "kind", "schema", "feeds")
# 실물 경로를 낼 수 있어야 한다 — `stem`(또는 `stems`) 이나 `files` 중 하나.
PATHABLE = ("stem", "stems", "files")

# raw_only 는 파이프라인이 읽지 않는다. 구조 선언을 요구할 근거가 없다.
NO_SCHEMA_KINDS = {"raw_only"}

# 텍스트 소스는 인코딩 선언이 있어야 한다. 실물과 대조하기 위해서다.
TEXT_KINDS = {"csv_points", "csv_table", "csv_table_multi",
              "csv_points_in_zip", "csv_point", "json_points"}
# hits[0] 하나만 읽는 kind. 여러 파일이 걸리면 조용히 뒤집힌다.
# ★ csv_table_multi 는 hits 전부를 이어붙인다(ingest.py 의 해당 분기).
#   여기 넣으면 "하나만 읽는데 files 가 2개다" 를 매번 오탐한다.
#   ingest 가 이 집합을 import 한다 — 같은 개념의 사본을 두지 않는다.
SINGLE_PICK = (TEXT_KINDS - {"csv_table_multi"}) | {"shp_zip", "dbf_in_zip"}

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
        if f == "schema" and e.get("kind") in NO_SCHEMA_KINDS:
            continue
        if f not in e:
            out.append(Issue(FAIL, key, f"필수 필드 없음: {f}"))
        elif bad(e[f]):
            out.append(Issue(FAIL, key, f"{f} 가 비었거나 TODO 다: {e[f]!r}"))

    # ── 실물 경로를 낼 수 있는가 ──────────────────────────────
    # ★ 2026-08-31. `files` 를 REQUIRED 에서 뺐다(#46). 빼기만 하면 경로를
    #   못 내는 항목이 조용히 통과한다 — 선언은 지웠는데 배선을 안 한
    #   그 형태다(DECISIONS §77). 그래서 **선언과 실물을 둘 다** 본다.
    if not any(e.get(f) for f in PATHABLE):
        out.append(Issue(FAIL, key,
                         "실물 경로를 낼 수 없다 — stem · stems · files 중 "
                         "하나가 있어야 한다"))
    elif not globs(e):
        out.append(Issue(FAIL, key,
                         "선언은 있는데 globs() 가 빈 목록이다. "
                         "stem 이 비었거나 files 가 빈 리스트다"))

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
    # ★ 2026-08-30. 종전 조건이 `isinstance(v, str)` 이었다. YAML 은
    #   따옴표 없는 `updated: 2026-03-07` 을 **date 객체**로 읽으므로 그
    #   항목만 형식 검사에서 조용히 빠졌다. 검사가 있는데 안 도는 자리다.
    #   대장에 두 표기가 섞여 있다(dem_public 문자열 · ngii1k date).
    #   문자열로 눌러서 본다 — 그러면 표기 혼재 자체도 드러난다.
    for f in ("updated",):
        v = e.get(f)
        if v is not None and not DATE.match(str(v)):
            out.append(Issue(WARN, key, f"{f} 가 YYYY-MM-DD 가 아니다: {v!r}"))
    # acquired 대조는 제거했다. 대장에 없는 필드를 보는 검사는 영원히
    # 통과한다 — 근거 없이 초록불을 켜는 것이 아무 검사도 없는 것보다 나쁘다.

    # ── 파일 ──────────────────────────────────────────────────
    files = globs(e)

    # stem 은 조회의 열쇠다. 없으면 stem_index() 에서 빠지고 migrate_names
    # 가 "개명 대상 0건" 을 낸다 — 없는 것이 아니라 못 찾은 것이다.
    if not (e.get("stems") or e.get("stem")):
        out.append(Issue(FAIL, key,
                         "stem 도 stems 도 없다. 조회 인덱스에서 빠져 "
                         "개명·격리 판정이 조용히 이 항목을 건너뛴다"))
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
    # ★ 2026-08-30. 산문 feeds 는 항목마다 WARN 하지 않는다.
    #   42종이 전부 산문이라 42줄이 같은 말을 했고, 그 사이에 진짜
    #   FAIL 4건이 묻혔다. **근거 없이 우는 검사가 아니라, 옳은데
    #   너무 자주 우는 검사도 진짜 경보를 죽인다.**
    #   판정은 유지하고(summary 가 센다) 출력만 총계로 낸다.
    if g == "unused" and not e.get("feeds_why"):
        # ★ 2026-08-30. `feeds_why` 가 있으면 판단이 끝난 것이다.
        #   unused 는 판정 결과로 남기고(summary 가 센다) 경보만 거둔다.
        #   판단이 끝난 사안을 미해결처럼 보이게 하는 것이 잘못된 경보다
        #   — backup_policy 와 같은 자리.
        out.append(Issue(WARN, key,
                         "★ feeds 가 비었다(R4). raw 에 둘 이유를 "
                         "feeds_why 에 적거나 retired 로 내린다"))
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
        for f in globs(e):
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


# ── 대장 → raw · 단일 조회기 ──────────────────────────────────
# ★ 2026-08-30. `e.get("files") or ([e["file"]] if "file" in e else [])` 가
#   **열 곳**에 각기 복사돼 있었다. 대장에서 `file` 단수를 제거하자
#   ingest 만 `e["file"]` 를 대괄호로 읽어 42종이 전부 죽었고, 나머지
#   아홉 곳은 조용히 빈 리스트가 됐다. **죽은 쪽이 나은 쪽이었다.**
#
#   조회기는 하나여야 한다. 대장을 아는 이 모듈이 그 자리다
#   (`stem_index` · `entry_of` 와 같은 이유).


def globs(e: dict) -> list[str]:
    """대장 항목 → raw 상대 글롭 패턴 목록. 없으면 빈 리스트.

    ★ 2026-08-31. `stem` 우선으로 뒤집었다(PLAN #46). `files` 는 stem 으로
      표현할 수 없는 항목만 남는 **명시적 글롭 예외**다.

        ngii1k                    도엽 74+143 묶음. 글롭이 곧 정체성
        node_link · node_point ·  `its_nodelink_*` 가
        turn_restriction          `its_nodelink_changelog_*` 를 함께 잡는다.
                                  구분자 `_` 를 붙여도 안 갈린다 —
                                  `changelog` 가 같은 토큰 자리에 온다

      **접두사 포함 관계는 stem 으로 못 가른다.** 실물 대조로 확인했다 —
      38종은 두 방식이 같은 파일을 잡았고 셋만 갈렸다. 확인 없이 지웠으면
      그 셋이 남의 파일을 먹었다.
    """
    if v := e.get("files"):
        return [str(x) for x in v]
    # ★ 2026-08-31. `file` 단수를 지웠다가 되살렸다. `datasets` 에는 없지만
    #   **`retired` 블록이 아직 쓴다** — 이 함수는 두 블록을 다 받는다.
    #   지운 뒤 acquire 의 폐기 판정이 조용히 빈 목록을 받았고,
    #   `test_acquire_stage_and_quarantine_do_not_fight` 가 그것을 잡았다.
    if f := e.get("file"):
        return [str(f)]
    stems = e.get("stems") or ([e["stem"]] if e.get("stem") else [])
    return [f"**/{s}_*" for s in stems]


def paths_of(e: dict, root) -> list:
    """대장 항목 → 실물 경로(정렬·중복 제거). 글롭이 아닌 것도 받는다."""
    out = []
    for pat in globs(e):
        if any(c in pat for c in "*?["):
            out += list(root.glob(pat))
        elif (root / pat).exists():
            out.append(root / pat)
    return sorted(set(out))


def crs_of(e: dict) -> str:
    """crs_native → 'EPSG:NNNN'.

    ★ 대장은 `crs_native: 5186` 으로 **정수**를 적는다(종전 `crs` 는
      'EPSG:5186' 문자열이었다). pyproj 는 둘 다 받지만 계보에 정수가
      박히면 문자열로 비교하는 하류가 조용히 어긋난다. 여기서 정규화한다.
    """
    v = e.get("crs_native")
    if v in (None, ""):
        return ""
    s = str(v).strip()
    return f"EPSG:{s}" if s.isdigit() else s


if __name__ == "__main__":
    import sys
    issues = check_all()
    for i in issues:
        print(i)
    print(f"\nFAIL {sum(i.level == FAIL for i in issues)} · "
          f"WARN {sum(i.level == WARN for i in issues)}")
    tally = summary()
    print("활용도 —", tally)
    if tally.get("prose"):
        print(f"  ! feeds 가 산문인 항목 {tally['prose']}종 — 소비자 키 "
              "리스트로 옮겨야 R4 를 셀 수 있다 (uv run python "
              "tools/ledger_feeds.py)")
    sys.exit(1 if any(i.level == FAIL for i in issues) else 0)


# ── 역산 대신 조회 ────────────────────────────────────────────
# ★ 2026-08-27. `file` 값에서 provider_dataset 을 **역산**하는 코드가
#   세 곳에 각기 다르게 있었다 —
#     migrate_names.plan() · normalize_raw._entry_for() · _repair_globs()
#   한 곳을 고칠 때마다 다른 곳을 안 봤고 같은 사고가 세 번 났다.
#
#   [B] 로 대장에 `stem` 을 명시했으므로 **조회**가 가능하다.
#   조회기는 하나여야 하고, 대장을 아는 이 모듈이 그 자리다.


def stem_index() -> dict[str, tuple[str, dict]]:
    """provider_dataset → (대장 키, 항목). 묶음은 stem 마다 등록한다."""
    out: dict[str, tuple[str, dict]] = {}
    for k, e in (load().get("datasets") or {}).items():
        for st in (e.get("stems") or ([e["stem"]] if e.get("stem") else [])):
            out.setdefault(str(st), (k, e))
    return out


def entry_of(rel: str) -> tuple[str | None, dict]:
    """raw 상대경로 → (대장 키, 항목). 못 찾으면 (None, {}).

    ★ 파일명에서 **스코프·날짜 뒤를 떨어내** provider_dataset 만 남긴다.
      이것은 역산이 아니라 파싱이다 — 문법이 `firelane.naming` 에
      정의돼 있고 파서가 하나뿐이다.
    """
    from firelane import naming as nm
    idx = stem_index()
    name = rel.rsplit("/", 1)[-1]
    try:
        n = nm.parse(name, strict=False)
        hit = idx.get(f"{n.provider}_{n.dataset}")
        if hit:
            return hit
    except nm.NameError_:
        pass

    # ★ 스코프 토큰이 없는 **옛 이름**도 조회돼야 한다. 개명 대상이
    #   정확히 그 형태이기 때문이다 —
    #     safety_kfs_pumptruck_20251224.hwpx   (스코프 없음)
    #   파서는 스코프를 고정점으로 쓰므로 여기서 실패한다. 그러면
    #   `migrate_names` 가 대장 항목을 못 찾고 "개명 대상 0건" 이 된다.
    #   오늘 12건이 그렇게 조용히 실패했다.
    #
    #   접두가 가장 긴 stem 을 고른다. `safety_kfs_ladder_small` 과
    #   `safety_kfs_ladder_articulated` 처럼 접두가 겹치는 것이 있으므로
    #   짧은 쪽이 먼저 잡히면 안 된다.
    stem = name.rsplit(".", 1)[0]
    best = None
    for st, hit in idx.items():
        if stem.startswith(st + "_") and (best is None or len(st) > best[0]):
            best = (len(st), hit)
    return best[1] if best else (None, {})

