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
    scope       행정 범위. firelane.scope 통제 어휘            [필수]
    kind        자료 형태. 아래 `kinds.py` 통제 어휘            [필수]
    authority   관할기관. ★ 행정구역과 경계가 다르다           [선택]
    updated     데이터 갱신일. 다운로드일이 아니다             [필수]
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

import yaml

from firelane import naming as nm
from firelane import paths

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
# ★ 2026-09-24 (PLAN §13 W13-15). 이 파일 머리말이 `provider` · `acquired` ·
#   `license` 를 **[필수]** 로 적고 있었다. 셋 다 2026-08-30 재작성에서 제거된
#   필드이고 실측 **0/72** 다 — 바로 아래 옛 주석이 그 제거를 스스로 기록한다.
#   반대로 `kind` 는 REQUIRED 인데 머리말 목록에 **없었다.**
#   `sources.yaml` 이 2026-09-10 에 자기 머리말에 대해 똑같은 정정을 했는데
#   (「대장이 자기 스키마를 틀리게 적고 있었다」) **대장의 정본이라고 선언한
#   이 파일은 안 고쳤다.** 정본이 스키마를 틀리게 아는 것이 제일 나쁘다.
REQUIRED = ("what", "scope", "updated", "kind", "schema", "feeds")
# ★ 2026-09-07. **코드가 읽지 않는 문서 필드.** 검사 대상이 아니다.
#   `used_for` 는 12종에 있고 전부 차량 제원표다 — `vehicle.py` 의
#   전폭 2.5m · 축거 · 최소회전반경의 유일한 공식 근거가 여기 산다.
#   코드 참조가 0 이라고 지우면 근거가 사라진다. 지우지 않고, 필수로도
#   요구하지 않는다는 것을 선언으로 남긴다.
DOC_FIELDS = ("used_for", "note", "feeds_why", "feeds_note", "authority")
# 실물 경로를 낼 수 있어야 한다 — `stem`(또는 `stems`) 이나 `files` 중 하나.
PATHABLE = ("stem", "stems", "files")

# ★ 2026-09-07. 셋을 손으로 나열하던 것을 `firelane.kinds` 에서 유도한다.
#   kind 분류가 여섯 자리에 흩어져 있었고 `json_points` 는 그중 **둘에만**
#   들어갔다 — `ledger_schema` 와 `inventory` 가 빠졌다. 둘 다 실패하지
#   않고 조용히 건너뛰었다. 정본은 하나고 나머지는 사본이거나 없어야 한다.
#
#     NO_SCHEMA_KINDS  schema is None    구조 선언을 요구할 근거가 없다
#     TEXT_KINDS       text=True         인코딩 선언이 있어야 실물과 대조한다
#     SINGLE_PICK      single=True       hits[0] 하나만 읽는다
#       ★ csv_table_multi 는 hits 전부를 이어붙이므로 single=False 다.
#         넣으면 "하나만 읽는데 files 가 2개다" 를 매번 오탐한다.

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FORBIDDEN_VALUES = {"TODO", "todo", "TBD", "?", "-", ""}

# ── 계약 어휘 (2026-09-28 · DECISIONS §284-1) ──────────────────
# ★ `contract:` 블록의 키를 **아무도 세지 않았다.** 실측 3방향 어긋남 —
#
#     키                머리말  읽는 코드  대장
#     crs                 ○       ✗        0    ★ 개명 전 이름이 남아 있었다
#     delimiter           ✗       ○        2    ★ 어휘인데 머리말에 없었다
#     optional_cols       ✗       ○        1    ★ 같다
#
#   `crs` 는 항목 수준 `crs_native` 로 개명됐는데(`crs_of()` 참조)
#   `contract.py` 머리말만 옛 이름을 들고 있었다. **낡은 참조 하나가
#   「CRS 대조를 한다」는 약속으로 읽혔다.** 아무도 안 했다.
#
#   오타는 더 조용하다. `required_col` 이라 적으면 `c.get("required_cols")`
#   가 `None` 을 받고 **검사가 그냥 사라진다.** 빨강도 경고도 없다.
#   그래서 어휘를 여기 하나로 두고 셋을 대조한다.
#: 키 → (한 줄, 읽는 모듈). **읽는 모듈이 실제로 읽는지 시험이 본다.**
CONTRACT_KEYS: dict[str, tuple[str, str]] = {
    "encoding":         ("선언 인코딩과 실물 디코딩이 맞는가", "firelane.contract"),
    "required_cols":    ("있어야 하는 컬럼. 소실은 실패, 추가는 경고", "firelane.contract"),
    "optional_cols":    ("없어도 되는 컬럼. 결손을 보정한다", "firelane.read.delimited"),
    "rows":             ("건수 선언. 기본 허용폭 0.30", "firelane.contract"),
    "rows_tolerance":   ("건수 허용폭", "firelane.contract"),
    "scope_min":        ("스코프 안 유효 건수 하한. 조용한 0건을 막는다", "firelane.contract"),
    "layer_must_exist": ("zip 안에 layer 가 실제로 있는가", "firelane.contract"),
    "delimiter":        ("구분자. 안 적으면 갈래 기본값", "firelane.ledger"),
    "columns":          ("헤더 없는 원본의 컬럼 이름. 사람이 적는다", "firelane.read.delimited"),
}


def delimiter_of(e: dict) -> str:
    """구분자. **기본값의 정본은 여기 하나다.**

    ★ 2026-09-28. 기본값이 두 곳에 각기 있었다 — `read/delimited.py` 와
      `tools/ledger_schema.py` 가 `"|"`, `contract.py` 는 pandas 기본 쉼표.
      셋이 같은 대장 키를 다르게 해석했다. 갈래가 정하는 값이므로
      `kinds.DELIM_KINDS`(= `schema="delim"`) 에서 유도한다.
    """
    from firelane.kinds import DELIM_KINDS
    c = e.get("contract") or {}
    if (v := c.get("delimiter")) not in (None, ""):
        return str(v)
    return "|" if e.get("kind") in DELIM_KINDS else ","

FAIL, WARN = "FAIL", "WARN"


def load() -> dict:
    f = paths.ROOT / "sources.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8")) or {}


# ── 대장 → raw · 단일 조회기 ──────────────────────────────────
# ★ 2026-08-30. `e.get("files") or ([e["file"]] if "file" in e else [])` 가
#   **열 곳**에 각기 복사돼 있었다. 대장에서 `file` 단수를 제거하자
#   ingest 만 `e["file"]` 를 대괄호로 읽어 42종이 전부 죽었고, 나머지
#   아홉 곳은 조용히 빈 리스트가 됐다. **죽은 쪽이 나은 쪽이었다.**
#
#   조회기는 하나여야 한다. 대장을 아는 이 모듈이 그 자리다
#   (`stem_index` · `entry_of` 와 같은 이유).


def provider_of(e: dict) -> str | None:
    """대장 항목 → provider(= raw 폴더명). **유도한다. 적지 않는다.**

    ★ 2026-09-10 신설. `globs()` 가 stem 기반이 되면서(PLAN #46) 패턴이
      `**/juso_elctrnmap_*` 꼴이 됐고, 그 결과 `globs()[0].split("/")[0]`
      로 폴더를 뽑던 곳이 전부 `"**"` 를 받았다. `treecheck` D9 는 그것으로
      provider 사용 여부를 세어 **열 개를 "안 쓰인다" 로 잡았다.**

      같은 자리 넷이 있었다 — treecheck:268 · ledger_fields:161 ·
      ledger_stem:140 · migrate_names:198. 소비자를 하나씩 고치면 여섯 번째가
      생긴다. 유도를 여기 한 곳에 둔다.

    ★ 근거는 파일명 문법이다 — `{provider}_{dataset}_{scope}_{vintage}`.
      실측하면 stem 첫 토큰이 provider 어휘 안에 65/65 있다. `files` 를
      쓰는 예외 항목은 그 경로의 첫 조각이 곧 폴더다.
    """
    if st := e.get("stem"):
        return str(st).split("_", 1)[0]
    for f in (e.get("files") or []):
        head = str(f).split("/", 1)[0]
        if head and "*" not in head:
            return head
    return None


def vehicle_spec() -> dict:
    """대장의 `vehicle_spec` 블록. **읽는 것은 인프라의 일이다.**  (PLAN #122)

    ★ 2026-10-08 (DECISIONS §431). 종전에는 `seg/vehicle.py` 가 제 루트를
      손수 계산해 직접 읽었다 — 도메인이 파일을 읽은 것이다(§279-8).
      여기로 올리고 도메인은 `vehicle.use()` 로 받는다.

    ★ 비었는지 · 칸이 모자라는지는 **안 본다.** 무엇이 필요한가는
      도메인이 알고 `vehicle.NEED` 가 든다. 여기는 건네줄 뿐이다.
    """
    return (load_sources() or {}).get("vehicle_spec") or {}


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


def files_decl(e: dict) -> list[str]:
    """대장 항목이 **명시한** 경로만. 유도로 내려가지 않는다.

    ★ 2026-10-08 (DECISIONS §431). `globs()` 는 선언이 없으면 `stem` 에서
      **만들어 준다** — 「있나 없나」를 묻는 쪽에는 그게 맞다. 그런데
      「**사람이 뭐라고 적었나**」를 묻는 쪽에는 그 친절이 독이다. 선언과
      유도를 대조하는 자리에서 `globs()` 를 쓰면 양쪽이 같은 값이 되어
      **대조가 공집합을 낸다.** 그래서 접근자를 둘로 가른다.

    ★ 그래서 이것이 `e.get("files")` 를 직접 읽던 자리의 **정본**이다.
      `test_ledger_accessor.py` 가 그 자리 수를 래칫으로 든다.
    """
    e = e or {}
    if v := e.get("files"):
        return [str(x) for x in v]
    if f := e.get("file"):          # `retired` 블록이 아직 단수를 쓴다
        return [str(f)]
    return []


# ★ 취득 사이드카. **자료가 아니다.**
#   2026-09-13. `**/safety_hydrant_point_*` 가 확장자를 안 가려서
#   `_meta/safety_hydrant_point_jngj_20260830.meta.json` 까지 잡았다.
#   `prep` 은 그것을 norm 에 안 만들고 `ingest` 는 요구해서 파이프라인이
#   16분 돌다 죽었다. 파일은 레이크 전체에 하나뿐이었지만 고칠 것은
#   파일이 아니라 글롭이다 — 하나 더 생기는 날 똑같이 터진다.
META_DIR = "_meta"


def is_acquisition_meta(p) -> bool:
    """취득 기록인가. `prep` 과 `ingest` 가 **같은 규칙**을 봐야 한다.

    ★ `pathlib` 을 안 쓴다. 이 모듈은 그것을 import 하지 않고, 검사
      하나 때문에 import 를 늘리면 계층 검사가 그 이유를 못 읽는다.
    """
    s = "/" + str(p).replace("\\", "/").lower()
    return f"/{META_DIR}/" in s or s.endswith(".meta.json")


def paths_of(e: dict, root) -> list:
    """대장 항목 → 실물 경로(정렬·중복 제거). 글롭이 아닌 것도 받는다.

    ★ 취득 사이드카는 뺀다. 자료 글롭은 자료만 잡는다.
    """
    out = []
    for pat in globs(e):
        if any(c in pat for c in "*?["):
            out += list(root.glob(pat))
        elif (root / pat).exists():
            out.append(root / pat)
    return sorted({p for p in set(out) if not is_acquisition_meta(p)})


def bbox_4326() -> tuple[float, float, float, float]:
    """동명동 + 여유. **정본은 대장의 `bbox_4326` 이다.**

    ★ 2026-09-16 (§169). 종전에는 `ingest.py` 에 튜플이 박혀 있었고 대장과
      **두 벌**이었다 — 샤드 봉인지 cfg 칸은 대장 값을 재는데 실제 거르기는
      그 튜플이 했다. 대장만 고치면 샤드가 찢어져 다시 빌드하고도 산출은
      그대로인, 근거와 실물이 갈린 상태였다.

    ★ 2026-09-27 (§274-4). 그 뒤 `read/_io.py` 가 같은 값을 필요로 했다.
      거기서 `load()` 를 또 부르면 **대장 문이 하나 더 는다** — 값 하나를
      쓰려고 문을 늘리지 않는다. 대장의 칸은 대장이 내준다.
    """
    return tuple(load()["bbox_4326"])


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


def yaml_span(s: str, key: str) -> tuple[int, int, str]:
    """`sources.yaml` 원문에서 `  <key>:` 블록의 (시작, 끝, 본문).

    ★ 2026-09-13. `ledger_feeds` · `ledger_schema` 가 같은 구현을 한 벌씩
      들고 있었다(96노드). `sources.yaml` 의 들여쓰기 규약을 아는 것은
      대장 모듈의 일이다 — 두 벌이면 규약이 바뀌는 날 한쪽만 따라온다.

    ★ 원문을 그대로 다루는 이유는 `yaml.safe_load` → `dump` 왕복이
      주석과 블록 스칼라를 잃기 때문이다. 대장은 사람이 읽는 문서다.
    """
    import re as _re

    m = _re.search(rf"^  {_re.escape(key)}:\n", s, _re.MULTILINE)
    if not m:
        return -1, -1, ""
    b = _re.search(rf"^  {_re.escape(key)}:\n((?:    .*\n|      .*\n|\n)*)",
                   s, _re.MULTILINE)
    return m.end(), m.end() + len(b.group(1)), b.group(1)


def load_sources() -> dict:
    """`sources.yaml` 을 읽는 **유일한 자리.**

    ★ 2026-09-14. 같은 일을 하는 함수가 다섯이었다 —
      `prep._sources` · `sweep.led` · `vintage_check._sources` ·
      `acquire._yaml` · `lakecheck.led`.

    ★ 그런데 **다섯이 같은 함수가 아니었다.** 셋은 `or {}` 가 있고
      둘은 없다. 빈 파일일 때 한쪽은 `{}` 를, 다른 쪽은 `None` 을 낸다.
      사본을 합치는 것이 아니라 **갈린 동작을 하나로 세우는 것**이다.
      `dupcheck` 가 "합칠지는 사람이 정한다" 고 한 자리가 이런 곳이다.

    ★ `ledger` 가 `sources.yaml` 의 주인이다. 읽는 법도 여기 있어야 한다.
    """
    return yaml.safe_load(
        (paths.ROOT / "sources.yaml").read_text(encoding="utf-8")) or {}
