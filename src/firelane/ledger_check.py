"""
ledger_check.py — **대장 항목이 계약을 지키나.** 그리고 **누가 읽나.**

    uv run python -m firelane.ledger_check      대장 필드 검사 (FAIL 이면 종료 1)

── 왜 생겼나 (2026-10-08 · DECISIONS §431 · PLAN #157) ────────
`ledger.py` 가 **633줄**로 상한 600 을 넘었다. 읽으면 그 파일이 **두 일**을
하고 있었다 —

    조회   선언 → raw 경로 · 좌표계 · 제원 · 역색인        `ledger.py`
    판정   필수 칸 · 어휘 · 활용도 등급 · 스코프 충돌      **이 파일**

★ 이 가르기에는 선례가 있다 — §426 때 `normalize_raw` 의 판정을
  `firelane.lake.raw_verdict` 로 옮겼다. 「선언을 읽는 집」과 「선언으로
  판정하는 집」은 다른 집이다. 읽는 쪽은 아무 데서나 불리고(ingest 폐포
  안이다), 판정하는 쪽은 관문에서만 불린다.

★ `ledger.py` 를 고치면 **샤드 봉인 코드 지문이 바뀐다**(ingest 폐포 27 안이다).
  이 판은 이미 그것을 움직였으므로 — `#122` 가 `vehicle_spec()` 을, `§430` 이
  `files_decl()` 을 더했다 — 쪼개는 값이 **0** 이다. 산출물은 그대로이니
  `firelane.ingest --reseal-code` 로 넘긴다. 다시 빌드하지 않는다.

IN    `sources.yaml`
OUT   없음 — `Issue` 목록. 종료 코드는 `__main__` 이 정한다
PARAM `REQUIRED` · `DOC_FIELDS` · `RENAME_ONLY` · `REFERENCE_WHY` · `PENDING_WHY`
밖    **실물을 안 본다.** 「선언이 제 규칙을 지키나」만 묻고, 선언과 실물이
      맞는지는 `lakecheck` · `acquire --verify` 가 든다. 그래서 레이크 없이 돈다.
"""
from __future__ import annotations

from dataclasses import dataclass

from firelane import naming as nm
from firelane import scope as sc
from firelane.cli import no_args
from firelane.kinds import NO_SCHEMA_KINDS, SINGLE_PICK, TEXT_KINDS
from firelane.ledger import (
    DATE,
    FAIL,
    FORBIDDEN_VALUES,
    PATHABLE,
    REQUIRED,
    WARN,
    crs_of,
    globs,
    load,
)


@dataclass
class Issue:
    level: str
    key: str
    msg: str

    def __str__(self) -> str:
        return f"{self.level} [{self.key}] {self.msg}"


# ── 활용도 ────────────────────────────────────────────────────
#: 데이터를 **소비하지 않는** 피드. 이름표를 붙여 `data/raw` 에 놓을 뿐이다.
#: ★ 2026-09-24 (PLAN §13 W13-5 · DECISIONS §243). `normalize_raw` 는 배치기이지
#:   소비자가 아니다. 그런데 `grade()` 가 「feeds 가 비지 않았다」만 봐서 이 한
#:   줄짜리 일곱을 활성으로 셌다 — 일곱 다 제 `feeds_note` 에 「미투입」이라 적고
#:   있었다. **대장이 제 자신과 어긋났고 집계가 산문을 이겼다.**
RENAME_ONLY = frozenset({"src/firelane/normalize_raw.py"})


#: `feeds_why` 의 **첫 낱말 = 선언**(DECISIONS §317). ① 영구 참조 ② 미배선 —
#: 둘을 한 수로 세니 「미활용 25」가 한 달 동안 25 였다.
REFERENCE_WHY = ("참조용", "대조용", "근거 자료")
PENDING_WHY = ("미투입", "미배선")


def why_token(entry: dict) -> str | None:
    """`feeds_why` **첫 줄**이 든 선언 낱말. `★` 장식은 건너뛴다 — 산문 전체에서
    찾으면 본문에 우연히 든 낱말까지 선언으로 읽힌다."""
    w = entry.get("feeds_why")
    head = w.lstrip("★ *·\n").split("\n", 1)[0] if isinstance(w, str) else ""
    return next((t for t in REFERENCE_WHY + PENDING_WHY if head.startswith(t)), None)


def grade(entry: dict) -> str:
    """**자동 산출.** 대장에 적힌 값이 있어도 무시한다."""
    feeds = entry.get("feeds")
    if isinstance(feeds, str):
        # 산문이다. 아직 마이그레이션 전이므로 판정을 보류한다.
        return "prose"
    if entry.get("kind") == "raw_only":
        # 「원본만 보관」은 **왜 여기 있나**의 답이지 소비 여부가 아니다.
        # 이 갈래를 뒤로 미루면 raw_only 열다섯이 미사용으로 뒤집힌다.
        # ★ 2026-09-30 (§317). **위 경고를 이 함수가 어기고 있었다** — `if not
        #   feeds` 가 앞에 있어 feeds 빈 아홉이 뒤집혔다. 글과 코드가 갈렸다.
        return "reference"
    if not feeds or not set(feeds) - RENAME_ONLY:
        # 이름표만 붙는다 — 아무도 안 읽는 것과 같다. 그중 **영구 참조**는
        # 소비자가 없는 것이 아니라 **소비자가 사람**이다(§317).
        return "reference" if why_token(entry) in REFERENCE_WHY else "unused"
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

    # ── 좌표가 나오는 갈래에는 좌표계 선언이 있어야 한다 ──────
    # ★ 2026-09-28 (§285-2). 이 규칙이 **세 곳에 생길 뻔했다** —
    #   `datalog.cmd_check` 에 하나, `contract --declared` 에 하나(그날
    #   새로 쓰다 잡았다), 그리고 여기. 항목 필드의 판정은 이 함수가
    #   정본이고, 나머지는 여기를 부른다.
    # ★ `kinds.KINDS[*].geom` 이 「좌표가 나오나」의 정본이다 — 목록을
    #   또 만들면 사본이 하나 더 생긴다. `raw_only` 문서에까지 좌표계를
    #   요구하던 옛 판이 그래서 158건을 냈고 아무도 안 읽었다.
    # ★ WARN 이다. 35/72 가 비어 있고 FAIL 로 올리면 대장이 통째로
    #   빨개진다 — 정상 상태에서 우는 게이트는 사람이 무시하고, 무시되는
    #   게이트는 죽은 것이다. 수는 `contract --declared` 의 래칫이 든다.
    from firelane import kinds as _kinds
    _kd = _kinds.KINDS.get(e.get("kind"))
    if _kd and _kd.geom and not crs_of(e):
        out.append(Issue(WARN, key,
                         f"좌표가 나오는 갈래({e.get('kind')})인데 crs_native 가 "
                         "없다 — 계보에 빈 좌표계가 박힌다"))

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
        # ★ 2026-09-17 (§182-2). zip 안 여러 텍스트 표(juso_building_db)는 `files` 가 스키마의 몸이다.
        if not (schema.get("columns") or schema.get("layers") or schema.get("files")):
            out.append(Issue(WARN, key, "schema 에 columns 도 layers 도 files 도 없다"))
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
    # ★ 선언 낱말이 없는 `feeds_why` 는 `tools/unusedcheck.py` 가 든다(§317).
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


if __name__ == "__main__":
    no_args(__doc__)          # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
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
