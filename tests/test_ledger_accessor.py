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

#: 아직 정본 접근자를 안 거치는 소비자. **줄여야 할 빚이다.**
#: `triage` 3 · `lakecheck` 2 · `sweep` 1
#: ★ 2026-10-08 (DECISIONS §431). `acquire` 둘이 빠졌다 — 4파일 7자리 → 3파일 6자리.
#:   「선언만 읽는다」는 요구가 생겨 `ledger.files_decl()` 을 세웠고, 유도로
#:   내려가는 `globs()` 와 쓰임이 갈린다. 남은 셋도 둘 중 하나로 간다.
DIRECT_READER_FILES = 3
DIRECT_READER_SITES = 6

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

    ★ 이 수는 목표가 아니라 **빚**이다. 줄면 이 상수를 내린다.
    """
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
