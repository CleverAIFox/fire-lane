#!/usr/bin/env python3
"""
test_declaration_reality.py — 선언이 실물을 덮는가. **역방향이다.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-03 감사에서 34건이 나왔는데 원인은 넷뿐이었고, 그중 둘이
전체의 3분의 2였다.

    ① 검사가 한 방향만 본다        목록 → 실물만 보고 실물 → 목록을 안 본다
    ② 선언이 실물보다 좁다          Step · IN/OUT 헤더 · consumers 가 부분집합

★ ②가 ①의 결과다. `pipeline.Step` 은 writes 충돌 · 하류 무효화 ·
  후진 의존을 전부 잡도록 만들어졌는데, **선언이 비어 있어서 잡을 것이
  없었다.** 검사가 없는 게 아니라 검사가 볼 것이 없었다.

  실증 — `tests/test_guards.py::test_every_read_is_produced_by_an_earlier_step`
  는 \"뒤 단계가 만드는 것을 앞 단계가 읽으면 지난 실행 산출물을 조용히
  읽는다\" 를 잡으려고 2026-08-17 에 만들어졌다. `ortho` 가 정확히 그
  버그를 갖고 있는데(`web/data/scope.geojson` 을 읽고 그것은 `publish` 가
  쓴다) **선언이 없어서 초록불이었다.**

  그래서 여기는 선언을 검사하지 않는다. **선언과 소스 코드를 대조한다.**

── 무엇을 보는가 ───────────────────────────────────────────────
    A  모듈이 실제로 쓰는 경로 ↔ `pipeline.Step.produces`
    B  모듈이 실제로 읽는 경로 ↔ `pipeline.Step.consumes`
    C  모듈 머리말 `IN`/`OUT` 줄 ↔ 위 둘
    D  `sources.yaml outputs.*.consumers` ↔ 그 경로를 실제로 읽는 파일

★ 소스에서 경로 리터럴을 뽑는다. AST 가 아니라 정규식인 이유는
  `W/"x.geojson"` · `PROCESSED / "y.csv"` 처럼 **경로 조립이 상수 문자열
  로 끝나기** 때문이다. 동적 조립은 못 잡고, 못 잡는다는 사실을 R23 대로
  여기 적는다.

── 안 보는 것 ──────────────────────────────────────────────────
★ 변수로 조립되는 경로(`for k in keys: W/f"{k}.geojson"`)는 못 본다.
  `publish_web` 의 마커 발행 루프가 그렇다. 그것은 `web/data/_manifest.json`
  이 실물로 덮으므로 `test_ledger_outputs` 소관이다.
★ `raw` 아래는 안 본다. 저장소 밖이라 존재를 확인할 수 없다.

IN    src/firelane/pipeline.py · src/firelane/*.py · sources.yaml
OUT   없음 (검사)
PARAM ALLOW — 선언에서 빼는 것. **사유를 함께 적는다**
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# ── 선언에서 빼는 것. 사유 없이 늘리지 않는다 ──────────────────
# ★ `test_tools_are_wired.EXEMPT` 와 같은 규약이다. 그리고 같은 이유로
#   **역방향 검사를 함께 둔다**(test_allow_entries_are_real).
ALLOW: dict[str, str] = {
    # 진단 덤프. 사람이 볼 때만 생기고 하류가 없다.
    "uncovered_units.json": "진단 덤프. 소비자 없음 · PLAN #12 가 든다",
    "width_samples.csv": "표본 덤프. 실측 지점 선정에만 쓴다",
    # 계보 자신. 모든 단계가 쓰므로 선언하면 전 단계가 서로를 물고 돈다.
    "_lineage.json": "계보 기록 자신. lineage.record 가 쓴다",
    # 산출물이 아니라 **잔재 제거**다. publish_web:286 이 unlink 한다.
    "markers.geojson": "옛 산출물의 잔재를 지운다. 만들지 않는다(2026-09-03)",
    # ★ 2026-09-04. 발행을 멈추면서 잔재 제거만 남았다. 처음부터 화면이
    #   읽지 않았고 ortho 전용 중간 산출물이었다 — 그것을 web/data 에 둔
    #   것이 ortho → publish 후진 의존의 원인이었다.
    #   정본은 processed/scope_5186.gpkg 다.
    "scope.geojson": "발행 중단. publish 가 남은 것을 지운다(2026-09-04)",
}

# `X / "이름.확장자"` · `X/"이름.확장자"` 꼴만 잡는다.
_WRITE = re.compile(
    r"""(?:^|[^\w])(?:P|W|OUT|PROCESSED|WEB|GOLDEN)\s*/\s*["']([\w./-]+\.\w{1,8})["']"""
)


def _steps():
    spec = importlib.util.spec_from_file_location(
        "pipeline", ROOT / "src/firelane/pipeline.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["pipeline"] = m
    spec.loader.exec_module(m)
    return m


def _src(module: str) -> str:
    return (ROOT / "src/firelane" / f"{module}.py").read_text(encoding="utf-8")


def _literals(text: str) -> set[str]:
    """소스가 드는 산출물 경로 리터럴. 주석·문서화 줄은 뺀다."""
    out = set()
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        out |= set(_WRITE.findall(line))
    return out


def _declared(step) -> set[str]:
    return {p.name for p in (*step.writes, *step.mutates, *step.reads)}


def _covered(name: str, declared: set[str]) -> bool:
    """글롭 선언도 인정한다. `*_5186.gpkg` 가 `node_point_5186.gpkg` 를 덮는다."""
    import fnmatch
    return name in declared or any(
        "*" in d and fnmatch.fnmatch(name, d) for d in declared)


def test_step_declares_every_artifact_its_module_names():
    """모듈이 이름으로 드는 산출물이 `Step` 선언에 있는가.

    ★ 2026-09-03. `segments` 가 `route_vehicle.csv` 를, `publish` 가
      `route_vehicle.json` 을 내는데 둘 다 선언 밖이었다. 그래서 segments 를
      다시 돌려도 publish 가 stale 로 안 잡혔고, 커밋된
      `web/data/route_vehicle.json` 이 이틀 낡은 채로 전 게이트를
      통과했다(PLAN #70).
    """
    m = _steps()
    bad = []
    for s in m.STEPS:
        declared = _declared(s)
        for name in sorted(_literals(_src(s.module))):
            if name in ALLOW or _covered(name, declared):
                continue
            bad.append(f"  {s.module}.py 가 {name} 을 드는데 "
                       f"Step({s.name!r}) 선언에 없다")
    assert not bad, (
        "모듈이 만지는 파일이 Step 선언 밖이다.\n" + "\n".join(bad)
        + "\n\n  reads/writes/mutates 중 맞는 자리에 넣어라. 하류가 없으면"
          "\n  ALLOW 에 **사유와 함께** 적는다 — 사유 없이 넣으면"
          "\n  이 검사가 항상 통과하는 검사가 된다(DECISIONS §69).")


def test_module_header_matches_step_declaration():
    """머리말 `IN`/`OUT` 줄이 `Step` 과 같은 파일을 드는가.

    ★ 2026-09-03. `terrain.py` OUT 이 `segments.geojson` 을 안 든다.
      z 를 덧쓰는 것이 그 파일의 최대 부작용이고 z 소실 사고의 원인인데,
      `pipeline.py` 만 `mutates` 로 적고 모듈 자신은 침묵했다.
      `publish_web.py` OUT 은 반대로 **자기가 지우는** `markers.geojson`
      을 산출물로 든다(286줄이 unlink 한다).
    """
    m = _steps()
    bad = []
    for s in m.STEPS:
        src = _src(s.module)
        head = src.split('"""')[1] if '"""' in src else ""
        for p in (*s.writes, *s.mutates):
            # ★ 디렉터리 선언(`web/terrain`)은 건너뛴다. 머리말은 `web/data/
            #   terrain/**` 처럼 글롭으로 적는 것이 정상이다.
            if p.name in ALLOW or "*" in p.name or not p.suffix:
                continue
            if p.name not in head:
                bad.append(f"  {s.module}.py 머리말 OUT 에 {p.name} 이 없다 "
                           f"(Step 은 낸다고 선언한다)")
    assert not bad, (
        "모듈 머리말과 Step 선언이 다르다.\n" + "\n".join(bad)
        + "\n\n  R1 은 머리말이 있는지만 본다. 내용이 맞는지는 여기가 본다.")


def test_ledger_consumers_are_complete():
    """`outputs.*.consumers` 가 **실제로 읽는 파일 전부**를 드는가.

    ★ 2026-09-03. `route_vehicle` 의 consumers 가 `tools/route_probe.py`
      하나였는데 `publish_web.py:379` 도 읽는다. `datalog impact` 가
      publish 를 안 내므로 \"이 소스를 바꾸면 뭐가 깨지나\" 에 답을 못 했다.

    ★ `datasets.feeds` 에는 `tools/ledger_feeds.py` 라는 역산기가 있는데
      `outputs.consumers` 에는 짝이 없어 손으로 유지되고 있었다.
    """
    led = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    scan = [p for d in ("src", "tools", "tests", "web/js")
            for p in (ROOT / d).rglob("*")
            if p.suffix in (".py", ".js") and p.is_file()]
    texts = {p: p.read_text(encoding="utf-8", errors="ignore") for p in scan}

    # ★ 이름이 나온다고 소비자가 아니다. **읽는 호출과 같은 줄**일 때만 센다.
    #   처음에 이름 등장으로 셌더니 `paths.py` · `ledger.py` · `lineage.py`
    #   같은 인프라가 전부 걸려 14건이 나왔다 — 경로를 조립만 하고 열지는
    #   않는 파일들이다. **시끄러운 검사는 사람이 끈다**(DECISIONS §78).
    READ = re.compile(r"read_file|read_text|read_csv|open\(|json\.load|fetch\(")

    bad = []
    for key, e in (led.get("outputs") or {}).items():
        path = (e or {}).get("path")
        if not path:
            continue
        name = Path(path).name
        listed = set((e or {}).get("consumers") or [])
        producer = (e or {}).get("produced_by")
        for p, t in texts.items():
            rel = str(p.relative_to(ROOT))
            if rel in listed or rel == producer or name not in t:
                continue
            if not any(name in ln and READ.search(ln) for ln in t.splitlines()):
                continue
            bad.append(f"  outputs.{key} ({name}) 를 {rel} 이 읽는데 "
                       f"consumers 에 없다")
    assert not bad, (
        "대장 consumers 가 실물보다 좁다.\n" + "\n".join(bad)
        + "\n\n  `datalog impact` 가 이 목록으로 영향분석을 한다."
          "\n  좁으면 소스를 바꿀 때 깨지는 것을 못 센다(MASTER §18-3a).")


def test_allow_entries_are_real():
    """ALLOW 가 아무도 안 만지는 파일을 들면 목록이 낡은 것이다. 양방향이다."""
    m = _steps()
    seen = set()
    for s in m.STEPS:
        seen |= _literals(_src(s.module))
    ghost = sorted(n for n in ALLOW if n not in seen and not n.startswith("_"))
    assert not ghost, (
        f"ALLOW 가 아무도 안 드는 파일을 든다 — {', '.join(ghost)}\n"
        "  그 산출물이 없어졌으면 줄도 지워라.")


def test_allow_entries_carry_a_reason():
    """사유가 비면 면제가 아니라 방치다."""
    blank = sorted(n for n, why in ALLOW.items() if not (why or "").strip())
    assert not blank, f"사유 없는 ALLOW — {', '.join(blank)}"


# ── 문서가 적은 "수" ↔ 코드가 세는 "수" ────────────────────────
# ★ 2026-09-03. 감사에서 셋이 낡아 있었다 — 제공기관 8(실물 9) ·
#   JS 모듈 27(실물 29) · WMAX_CAP 주석 40(코드 60 · 그런 주석 자체가 없음).
#   셋 다 **코드가 매번 정확한 수를 찍고 있었는데** 그 값을 문서와
#   대조하는 곳이 없었다. `docnum_check` 는 판정 숫자만 본다.
def _count_providers() -> int:
    led = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    return len(led["layers"]["raw"]["providers"])


def _count_js_modules() -> int:
    return len(list((ROOT / "web/js").rglob("*.js")))


COUNTS = (
    ("제공기관 폴더", _count_providers,
     ("README.md", "docs/MASTER.md", "tools/scan_data.py"), "{n}폴더"),
    ("web/js 모듈", _count_js_modules,
     ("README.md", "docs/MASTER.md", "web/README.md"), "{n}개 모듈"),
)


def test_document_counts_match_reality():
    """문서가 적은 수가 코드가 세는 수와 같은가.

    ★ 문서에 그 표현이 **한 번도 안 나오면 넘어간다.** 모든 문서가 모든
      수를 들어야 하는 것이 아니다. 여기서 보는 것은 \"적었는데 틀렸나\" 다.
    """
    bad = []
    for label, fn, files, tmpl in COUNTS:
        n = fn()
        want = tmpl.format(n=n)
        for rel in files:
            txt = (ROOT / rel).read_text(encoding="utf-8")
            # 같은 형식의 다른 수가 있는가
            for k in range(1, 200):
                if k == n:
                    continue
                other = tmpl.format(n=k)
                # ★ 숫자 경계를 본다. `29개 모듈` 안에 `9개 모듈` 이
                #   들어 있어서 첫 판에 오탐 셋이 났다.
                if re.search(r"(?<!\d)" + re.escape(other), txt):
                    bad.append(f"  {rel} 이 '{other}' 라고 적는데 "
                               f"실물은 {label} {n}개다 ('{want}')")
    assert not bad, (
        "문서의 수가 실물과 다르다.\n" + "\n".join(bad)
        + "\n\n  실물을 세는 명령 —"
          "\n    제공기관  python -c \"import yaml;print(len(yaml.safe_load("
          "open('sources.yaml'))['layers']['raw']['providers']))\""
          "\n    JS 모듈   node tools/js_graph_check.mjs")


# ── 검증은 양쪽에서 한다 — 방향뿐 아니라 **범위**도 ────────────
# ★ 2026-09-03. 모든 검사가 선언된 루트에서 **아래로만** 봤다.
#   treecheck · refcheck · doc_fsck ④ · acquire 가 전부 그렇다.
#   그래서 `FIRE_LANE_DATA` 의 **형제**에 있는 것은 아무도 못 봤고,
#   SSD 에 `data/field/`(네이버 산출 넷 포함)가 몇 달간 남아 있었다.
#
#   방향의 단방향은 오늘 ALLOW·BACKWARD 역방향으로 막았다.
#   범위의 단방향은 `scan_data §7` 이 막는다. 그 절이 살아 있는지 여기서 본다.
def test_scan_data_looks_outside_the_declared_lake():
    """`scan_data` 가 데이터 레이크의 **형제**를 훑는가.

    ★ 선언 안쪽만 보는 검사는 "선언 밖에 둔 것" 을 영원히 못 본다.
      숨기려는 사람이 아니라 **옮기고 원본을 안 지운 사람** 때문에 생긴다.
    """
    src = (ROOT / "tools/scan_data.py").read_text(encoding="utf-8")
    assert "7. 선언 밖 형제" in src, (
        "scan_data 에 형제 스캔 절이 없다.\n"
        "  FIRE_LANE_DATA 의 이웃 폴더는 어떤 선언에도 안 들어간다.")
    assert "lake.parent" in src or "base = lake.parent" in src, (
        "형제를 보려면 레이크의 부모에서 훑어야 한다.")


def test_field_exempt_has_no_ghosts():
    """`doc_fsck.FIELD_EXEMPT` 가 없는 파일을 면제하지 않는가. **역방향이다.**

    ★ 목록이 실물보다 넓으면 방패가 아니라 사각지대다. 그 이름의 파일이
      다시 생겨도 조용히 통과한다(오늘 감사 A-4 · PATH_EXEMPT 와 같은 형태).
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("doc_fsck", ROOT / "tools/doc_fsck.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    field = ROOT / "data" / "field"
    if not field.exists():
        return
    real = {p.name for p in field.iterdir() if p.is_file()}
    ghost = sorted(n for n in m.FIELD_EXEMPT if n not in real)
    assert not ghost, (
        f"FIELD_EXEMPT 가 없는 파일을 면제한다 — {', '.join(ghost)}\n"
        "  그 파일이 사라졌으면 줄도 지워라.")


def test_raw_only_is_true_to_the_lake():
    """`kind: raw_only` 가 실물과 맞는가. **양방향이다.**

    ★ `raw_only` 는 "ingest 가 읽지 않는다. 존재만 기록한다" 다
      (ingest.py:523). 그러면 `norm` 에 그 파일이 있을 수 없다.

    ★ 2026-09-03. `gjfire_district_dongbu` · `node_link_changelog` 가
      `raw_only` 인데 norm 에 실물이 있었다 — **선언이 거짓이었다.**
      note 는 "편입 시 UTF-8 로 옮긴다" 고 정확히 적고 있었고 kind 만 틀렸다.
      "소비자가 없다" 와 "형식이 정규화 불가다" 를 구분하지 않은 것이다.

    ★ norm 은 저장소 밖(SSD)이라 CI 에서는 건너뛴다. 데이터가 붙은
      기계에서만 판정한다 — 그 사실을 여기 적는다(R23).
    """
    import yaml

    from firelane.paths import NORM

    norm = Path(NORM)
    if not norm.exists():
        return  # 레이크가 없다. CI 다.

    led = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    have = {f.name for f in norm.rglob("*") if f.is_file()}
    bad = []
    for k, e in (led.get("datasets") or {}).items():
        e = e or {}
        if e.get("kind") != "raw_only":
            continue
        st = e.get("stem")
        if st and any(n.startswith(f"{st}_") for n in have):
            bad.append(f"  {k:26s} stem={st}  norm 에 실물이 있다")
    assert not bad, (
        "raw_only 인데 norm 에 실물이 있다 — 선언이 거짓이다.\n"
        + "\n".join(bad)
        + "\n\n  ingest 가 실제로 읽고 있다면 kind 를 고쳐라"
          "\n  (csv_table · shp_zip 등). raw_only 는 형식이 정규화"
          "\n  불가일 때만 쓴다 — 소비자가 없는 것은 feeds 가 든다.")
