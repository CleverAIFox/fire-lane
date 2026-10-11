"""대장 항목의 파일 목록은 `ledger.globs()` 로만 읽는다.  (DECISIONS §430)

2026-08-31 에 대장을 `file`/`files` 에서 `stem`+`ext` 로 뒤집었다(PLAN #46).
`files` 는 그 뒤로 **stem 으로 표현할 수 없는 항목만 남은 명시적 글롭 예외**다.
그런데 이관이 전수로 안 됐고, 직접 읽는 소비자들은 **나머지 예순여섯 종을
못 보게** 됐다. 반입의 방아쇠인 `intake.waiting()` 이 거기 있었다 —
자리가 안 생기니 사람이 `--assign` 으로 찍을 번호조차 없었다.

★ **배치가 인스턴스를 지우고 가드가 족을 닫는다**(PLAN §13-4).
  그래서 이 시험은 고친 둘의 이름을 안 적는다. **대장에서 유도한다.**

IN    sources.yaml · src/firelane/ledger.py · src/firelane/intake_body.py ·
      tools/intake.py · tools/acquire.py
OUT   없음 (검사)
PARAM 없음
밖    **레이크를 안 본다.** 대장과 코드만 읽으므로 어느 기계에서도 같은 수가
      난다. 그래서 「실물이 실제로 반입되는가」는 이 시험이 모른다 — 그것은
      `acquire --verify` 와 `lakecheck` 가 든다. 그리고 **넷이 남은 빚인지**는
      수로만 든다. 그 넷이 고쳐져야 할 이유는 DECISIONS §430-2a 가 적는다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from firelane import ledger
from firelane.intake_body import body_file_of

ROOT = Path(__file__).resolve().parents[1]

#: 아직 정본 접근자를 안 거치는 소비자. **줄여야 할 빚이었고 0 이 됐다.**
#: ★ 2026-10-08 (DECISIONS §431). `acquire` 둘이 빠졌다 — 4파일 7자리 → 3파일 6자리.
#:   「선언만 읽는다」는 요구가 생겨 `ledger.files_decl()` 을 세웠고, 유도로
#:   내려가는 `globs()` 와 쓰임이 갈린다.
#: ★ 같은 날 (DECISIONS §438 · PLAN #160 닫힘) 남은 여섯이 **전부** 그 접근자로
#:   갔다 — `triage` 3 · `lakecheck` 2 · `sweep` 1. 셋 다 **선언만** 묻는 자리라
#:   `files_decl()` 이 맞고 `globs()` 가 아니다: 이 셋은 「사람이 뭐라고 적었나」를
#:   보고 실물과 댄다. `globs()` 는 선언이 없으면 `stem` 에서 만들어 주므로
#:   그 자리에서 쓰면 **양쪽이 같은 값이 되어 대조가 공집합을 낸다**(§431).
#: ★ **0 은 「없다」가 아니라 「다시 나면 운다」는 뜻이다.** 0 에서 오르면 누군가
#:   접근자를 비껴간 것이다 — 그 자리는 대장 80 중 66 이 `stem` 식이라
#:   **안 보이는 파일을 조용히 놓친다**(§430-2 가 그 꼴을 적었다).
DIRECT_READER_FILES = 0
DIRECT_READER_SITES = 0

#: 대장 항목을 받는 이름. 이 저장소가 `e` · `v` · `entry` 로 쓴다.
_DIRECT = re.compile(r'\b(?:e|v|entry)\b[^\n]{0,12}\.get\(\s*"files"\s*\)')


def _code(src: str) -> str:
    """주석을 뺀 줄만. **언급은 호출이 아니다.**(DECISIONS §398-3 · §425-6)

    ★ 이 시험을 처음 쓸 때 글자 전체를 셌고, 그래서 **고친 자리에 적은
      해설 주석 둘**이 위반으로 잡혔다. 래칫이 제 설명문을 세는 꼴이다.
    """
    return "\n".join(ln for ln in src.split("\n")
                     if not ln.lstrip().startswith("#"))


def _direct_readers() -> dict[str, int]:
    out: dict[str, int] = {}
    for d in ("src/firelane", "tools"):
        for p in sorted((ROOT / d).rglob("*.py")):
            if p.name == "ledger.py":      # 정본 접근자가 사는 집이다
                continue
            n = len(_DIRECT.findall(_code(p.read_text(encoding="utf-8"))))
            if n:
                out[p.relative_to(ROOT).as_posix()] = n
    return out


# ── 족 ──────────────────────────────────────────────────────────────
def test_every_dataset_is_visible_through_the_one_accessor() -> None:
    """대장의 **모든** 항목이 `globs()` 로 자리를 낸다.

    하나라도 빈 목록이면 그 항목은 반입·검사의 눈에서 사라진다.
    """
    ds = ledger.load_sources()["datasets"]
    blind = sorted(k for k, v in ds.items() if not ledger.globs(v or {}))
    assert blind == [], (
        f"{len(blind)}종이 `globs()` 로 아무 패턴도 못 낸다 — "
        f"반입이 자리를 못 만든다: {blind[:8]}")


def test_body_file_of_reads_stem_entries_not_only_files_entries() -> None:
    """`stem`+`ext` 로만 쓴 항목에서도 **파일을 집는다.**

    고친 자리의 이름을 안 적는다 — 대장에서 그런 항목을 **골라서** 민다.
    """
    ds = ledger.load_sources()["datasets"]
    stem_only = [k for k, v in ds.items()
                 if not (v or {}).get("files") and len(ledger.globs(v or {})) == 1]
    assert stem_only, "대장에 `stem` 식 항목이 하나도 없다 — 이 시험의 전제가 깨졌다"
    for k in stem_only[:20]:
        got, why = body_file_of("", ds[k])
        assert got is not None, (
            f"{k}: `stem` 식인데 파일을 못 집는다 — {why}. "
            "`files` 를 직접 읽는 자가 또 생겼다")


def test_waiting_matches_globs_instead_of_comparing_strings(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """실물이 있으면 **기다리지 않는다.** 글롭을 문자열로 비교하면 영원히 기다린다."""
    from intake import waiting

    import firelane.paths as fp

    raw = tmp_path / "raw" / "vworld"
    raw.mkdir(parents=True)
    monkeypatch.setattr(fp, "RAW", tmp_path / "raw")
    ds = {"zz_demo": {"stem": "vworld_zzdemo", "ext": ["zip"]}}

    assert waiting(ds) == [("zz_demo", "**/vworld_zzdemo_*")], \
        "실물이 없는데 자리를 안 만든다"
    (raw / "vworld_zzdemo_kr_20260101.zip").write_bytes(b"x")
    assert waiting(ds) == [], "실물이 있는데도 기다린다 — 글롭을 문자열로 비교한다"


def test_the_two_derivers_agree_on_every_dataset() -> None:
    """**파생기가 둘이다.** 둘 다 모든 항목에 답해야 사슬이 안 끊긴다.

    `ledger.globs()`          느슨한 글롭 — 「있나 없나」를 판정한다 (intake)
    `acquire_rules.derive_files()` 정확한 경로 — 「어디에 둘까」를 정한다 (acquire)

    ★ 2026-10-07. `juso_adrdc` · `eais_roadledger_dm` 이 `updated: '2026-08'`
      이라 뒤엣것만 빈 목록을 냈다. intake 는 자리를 만드는데 acquire 는 그
      항목을 모르는 상태 — **반입이 중간에서 끊긴다.** 답은 구체 `files:` 다
      (`parking_enforce` 와 같은 꼴). 대장의 `vintage` 는 **폐기된 칸**이고
      기준 시점의 정본은 `naming.parse(파일명).vintage` — 선언이 아니라
      **파일명에서 읽는 값**이다. 처음에 그 칸을 썼다가 `ledger_fields
      --check` 에 물렸다.
    """
    from firelane.acquire_rules import derive_files

    ds = ledger.load_sources()["datasets"]
    mute = sorted(k for k, v in ds.items()
                  if not (derive_files(v or {})
                          or (v or {}).get("files") or (v or {}).get("file")))
    assert mute == [], (
        f"{len(mute)}종을 `acquire` 가 어디에 둘지 못 정한다 — 반입이 거기서 "
        f"끊긴다. `files:` 에 구체 경로를 적어라: {mute}")


# ── 빚 ──────────────────────────────────────────────────────────────
def test_direct_ledger_files_readers_do_not_grow() -> None:
    """`globs()` 를 안 거치는 자가 **늘지 않는다.**

    ★ 이 수는 목표가 아니라 **빚**이었고 2026-10-08 에 **0 이 됐다**(§438).

    ★ **0 이 되면 빈 그물이 새 위험이다.** 정규식이 죽어도 0 이 나오고 그 0 은
      초록이다. 그래서 아래가 **합성 위반으로 그물이 살아 있는지 먼저 민다** —
      §69 가 적은 「검사가 항상 통과하는 검사가 되는 자리」다.
    """
    pos = 'for f in (e.get("files") or []):'
    assert _DIRECT.findall(_code(pos)), (
        "합성 위반을 못 잡는다 — 정규식이 죽었고 0 은 **거짓 초록**이다")
    neg = 'for f in cfg.get("files_v2"):'
    assert not _DIRECT.findall(_code(neg)), "엉뚱한 글자를 위반으로 센다"
    found = _direct_readers()
    sites = sum(found.values())
    assert (len(found), sites) == (DIRECT_READER_FILES, DIRECT_READER_SITES), (
        f"직접 읽는 자 {len(found)}파일 {sites}자리 — 기록은 "
        f"{DIRECT_READER_FILES}파일 {DIRECT_READER_SITES}자리다. 실측: {found}")


def test_the_counter_does_not_count_its_own_explanation() -> None:
    """**카나리아.** 주석 속 `e.get("files")` 는 위반이 아니다.

    고친 두 파일이 해설 주석에 그 글자를 그대로 들고 있다. 그것이 잡히면
    이 래칫은 제 설명문을 세고 있는 것이다(§425-6 과 같은 병).
    """
    found = _direct_readers()
    for f in ("tools/intake.py", "src/firelane/intake_body.py"):
        body = (ROOT / f).read_text(encoding="utf-8")
        assert _DIRECT.search(body), f"{f}: 카나리아의 전제가 사라졌다 — 주석이 바뀌었다"
        assert f not in found, f"{f}: **주석**을 위반으로 세고 있다"


# ── 원문 구간 — 시험이 이름을 안 부르고 있었다 (DECISIONS §493) ─
# ★ `ledger.yaml_span` 은 §205 가 `ledger_feeds` · `ledger_schema` 의 두 벌을
#   합친 자리다(96노드). 합친 뒤로 **맞는지 물은 자가 없었다** —
#   `tools/srccov.py` 가 셌다.
#
# ★ 왜 원문을 다루는가. `yaml.safe_load` → `dump` 왕복이 주석과 블록
#   스칼라를 잃는다. 대장은 사람이 읽는 문서다. 그래서 이 함수가 아는 것은
#   **`sources.yaml` 의 들여쓰기 규약**이고, 그 규약이 이 시험의 과녁이다.
_SPAN_SRC = """datasets:
  alpha:
    file: a/a.csv
    note: |
      여러 줄
      블록 스칼라

    encoding: cp949
  beta:
    file: b/b.csv
  alphabet:
    file: c/c.csv
"""


def test_yaml_span_keeps_block_scalars_and_blank_lines() -> None:
    """★ 본체. 블록 스칼라와 **그 안의 빈 줄**이 구간 안에 남는가.

    빈 줄에서 끊으면 `encoding: cp949` 가 구간 밖으로 떨어지고, 그것을
    고쳐 쓰는 자(`ledger_schema`)가 **옆 항목에 덧쓴다.**
    """
    b, e, body = ledger.yaml_span(_SPAN_SRC, "alpha")
    assert (b, e) != (-1, -1), "있는 키를 못 찾았다"
    assert _SPAN_SRC[b:e] == body, "낸 자리와 낸 본문이 다르다"
    assert "블록 스칼라" in body and "\n\n" in body, "블록·빈 줄을 잃었다"
    assert body.endswith("    encoding: cp949\n"), "빈 줄에서 끊었다"
    assert "beta" not in body, "다음 항목까지 먹었다"


def test_yaml_span_does_not_match_a_longer_key_with_the_same_prefix() -> None:
    """★ `alpha` 를 찾으며 `alphabet` 을 잡으면 **남의 항목을 고친다**."""
    _, _, a = ledger.yaml_span(_SPAN_SRC, "alpha")
    _, _, abc = ledger.yaml_span(_SPAN_SRC, "alphabet")
    assert "a/a.csv" in a and "c/c.csv" not in a
    assert "c/c.csv" in abc and "a/a.csv" not in abc


def test_yaml_span_is_silent_for_a_key_that_is_not_there() -> None:
    """★ 음성 — 없으면 `(-1, -1, "")` 이다. 0 을 주면 **머리에 덧쓴다**."""
    assert ledger.yaml_span(_SPAN_SRC, "zzz") == (-1, -1, "")
    assert ledger.yaml_span("", "alpha") == (-1, -1, "")
    # 들여쓰기가 두 칸이 아니면 대장 항목이 아니다
    assert ledger.yaml_span("alpha:\n  file: a\n", "alpha") == (-1, -1, "")


def test_yaml_span_only_sees_a_block_value() -> None:
    """★ **한 줄 값은 못 본다** — 결함이 아니라 규약이다.

    대장 항목은 언제나 블록이다(`  key:` 다음 줄부터 네 칸). 인라인
    매핑(`  key: {a: 1}`)으로 적으면 이 자가 「없다」고 답하고, 그래야
    고쳐 쓰는 자가 **모양을 모르는 줄에 손대지 않는다.**
    """
    assert ledger.yaml_span("datasets:\n  alpha: {a: 1}\n", "alpha") == (-1, -1, "")


# ── 줄기 색인과 항목 조회 (DECISIONS §496) ────────────────────
# ★ `ledger.entry_of` 머리말이 **그날의 조용한 실패**를 적는다 — 스코프
#   토큰이 없는 옛 이름(`safety_kfs_pumptruck_20251224.hwpx`)은 파서가
#   고정점을 못 찾아 실패하고, 그러면 `migrate_names` 가 대장 항목을 못 찾아
#   「개명 대상 0건」이 된다. **개명해야 할 것이 바로 그 형태인데** 그것만
#   조회가 안 됐다. 열두 건이 그렇게 조용히 실패했다.
#   `tools/srccov.py` 는 이 둘을 `e.get(...)` 때문에 **입출력으로 가르고**
#   있었고(§496), 그래서 「안 드는 순수 함수」 목록에 안 떴다.
def test_stem_index_registers_every_stem_of_a_bundle() -> None:
    """묶음(`stems`)은 **줄기마다** 등재된다 — 하나만 등재하면 나머지가 사라진다."""
    idx = ledger.stem_index()
    assert len(idx) > 50, f"줄기 {len(idx)}개 — 색인이 비었다"
    # `ngii1k` 은 SHP 판과 NGI 판 **두 줄기**를 든다
    assert idx["vworld_map1k"][0] == idx["vworld_map1k_ngi"][0] == "ngii1k"


def test_entry_of_finds_a_name_that_has_no_scope_token() -> None:
    """★ 본체. **개명 대상의 형태**가 조회돼야 한다.

    스코프가 없으면 `naming.parse` 가 고정점을 못 찾는다. 그 갈래가 없으면
    개명 도구가 「대상 0건」을 내고 아무도 그것이 거짓인지 모른다.
    """
    k, e = ledger.entry_of("safety/safety_kfs_pumptruck_20251224.hwpx")
    assert k == "kfs_pumptruck", k
    assert e.get("stem") == "safety_kfs_pumptruck"
    # 정규 이름도 같은 답이다 — 두 꼴이 **같은 항목**을 가리켜야 한다
    assert ledger.entry_of(
        "safety/safety_kfs_pumptruck_kr_20251224.hwpx")[0] == "kfs_pumptruck"


def test_entry_of_picks_the_longest_matching_stem() -> None:
    """★ 접두가 겹친다 — `..._ladder_small` 과 `..._ladder_articulated`.

    짧은 쪽을 집으면 두 자산이 **한 항목**으로 조회되고, 그러면 개명과
    반입이 서로의 파일을 덮어쓴다.
    """
    assert ledger.entry_of(
        "safety/safety_kfs_ladder_small_20251224.pdf")[0] == "kfs_ladder_small"
    assert ledger.entry_of(
        "safety/safety_kfs_ladder_articulated_20251224.hwpx")[0] == \
        "kfs_ladder_articulated"


def test_entry_of_is_silent_for_a_file_the_ledger_does_not_know() -> None:
    """★ 음성 — 모르면 `(None, {})` 이다. 아무 항목이나 주면 남의 칸을 쓴다."""
    for rel in ("safety/모르는것_kr_20200101.csv", "safety/x.csv", "x"):
        assert ledger.entry_of(rel) == (None, {}), rel


def test_entry_of_resolves_every_real_raw_file() -> None:
    """★ 전수 — raw 실물이 전건 조회돼야 한다. 하나라도 못 찾으면 그 파일은
    반입·개명·계보에서 **고아**가 된다.
    """
    import json

    raw = sorted(json.loads(
        (ROOT / "data/_acquire.json").read_text(encoding="utf-8"))["files"])
    assert len(raw) > 50, "실물 목록이 비었다 — 이 검사가 빈 그물이 됐다"
    orphan = [p for p in raw if ledger.entry_of(p)[0] is None]
    assert not orphan, "대장이 모르는 실물:\n  " + "\n  ".join(orphan)


def test_retired_sha_collects_every_hash_without_tripping_on_blanks() -> None:
    """폐기 등재의 sha 표를 모은다. 빈 칸·`None` 에 죽지 않는다.

    이 표가 비면 `lake` 가 「폐기한 것이 아직 있나」를 **아무것도 안 보고**
    통과시킨다 — 0 이 청결이 아니라 죽음인 자리다(§69).
    """
    from firelane.lake import ledger_retired_sha

    got = ledger_retired_sha(ledger.load())
    assert len(got) > 20, f"{len(got)}건 — 폐기 sha 표가 비었다"
    assert all(isinstance(k, str) and "/" in k for k in got), "키가 경로가 아니다"
    assert all(len(v) == 64 for v in got.values()), "sha256 길이가 아니다"
    # ★ 빈 꼴들 — 죽지 않고 빈 표를 낸다
    for y in ({}, {"retired": None}, {"retired": {"a": None}},
              {"retired": {"a": {"sha256": None}}},
              {"retired": {"a": {"sha256": "글자하나"}}}):
        assert ledger_retired_sha(y) == {}, y
