"""
test_norm_wiring.py — `layers.norm` 의 **선언과 배선이 같은가**.

★ 2026-08-31. DECISIONS §77 이 이 검사가 없어서 났다.
  `migrated` 를 채우고 "norm 이관 완료" 로 커밋했는데 `ingest.py` 가
  여전히 `RAW` 를 읽고 있었다. **아무 일도 안 났고 golden 은 초록이었다.**
  golden 은 `data/processed/segments.geojson` 하나만 읽으므로 입력 계층이
  바뀌었는지 알 방법이 없다. 통과가 증명이 아니었다.

  같은 날 `parts` 사고도 같은 형태였다 — 선언(대장)과 실물(zip 구조)이
  두 뜻이었는데 검사가 한 뜻만 봤다. 이 저장소가 반복해서 당하는 것은
  **선언이 실물보다 앞서는 것**이다.

── 무엇을 보나 ────────────────────────────────────────────────
raw 없이 돈다. CI 에는 데이터 레이크가 없으므로 실물은 보지 않는다.
실물 대조는 `tools/doctor.py` ② 파이프라인 정체가 맡는다. 여기는
`sources.yaml` 의 선언과 `src/firelane/ingest.py` 의 코드만 본다.

    선언 → 배선   migrated 에 키가 있으면 ingest 가 NORM 을 읽어야 한다
    배선 → 선언   ingest 가 NORM 을 읽으면 migrated 가 비면 안 된다
    status 정합   "미구현" 과 migrated 가 서로를 배반하지 않는가
    키 실재       migrated 의 키가 datasets 에 있는가

── 지금 상태에서는 통과한다 ───────────────────────────────────
`migrated: []` · `status: 미구현` · `ingest` 는 `RAW` 를 읽는다. 셋이
일관되므로 초록이다. **한 건이라도 옮기는 순간 배선 없이는 빨간불이 된다.**
그것이 이 검사의 목적이다 — 지금을 막는 게 아니라 다음을 막는다.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources.yaml"
INGEST = ROOT / "src" / "firelane" / "ingest.py"


def _layer() -> dict:
    d = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    return d.get("layers", {}).get("norm") or {}


def _datasets() -> dict:
    d = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    return d.get("datasets") or {}


def _ingest_src() -> str:
    """주석을 뺀 본문. 머리말이 NORM 을 언급해도 배선은 아니다."""
    out = []
    for line in INGEST.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0]
        out.append(s)
    return "\n".join(out)


def _reads_norm(src: str) -> bool:
    """`ingest` 가 실제로 NORM 을 입력으로 쓰는가.

    임포트만으로는 부족하다. `NORM` 이 import 만 돼 있고 안 쓰이면 §77
    그대로다. 둘 중 하나여야 인정한다 — `prep.source_path()` 호출(권장.
    선언과 실물이 어긋나면 거기서 죽는다) 또는 `paths_of()` 인자의 `NORM`.
    """
    if re.search(r"\bprep\.source_path\s*\(", src):
        return True
    if not re.search(r"\bfrom\s+firelane\.paths\s+import\b[^\n]*\bNORM\b", src):
        return False
    return bool(re.search(r"paths_of\s*\([^)]*\bNORM\b", src)
                or re.search(r"\bNORM\b[^\n]*paths_of", src))


def _hardcodes_raw(src: str) -> bool:
    """입력 경로가 RAW 로 못 박혀 있는가."""
    return bool(re.search(r"paths_of\s*\([^)]*\bRAW\b", src))


def test_migrated_keys_exist_in_datasets():
    """`migrated` 의 키가 대장에 실재하는가."""
    ds, mig = _datasets(), _layer().get("migrated") or []
    ghost = [k for k in mig if k not in ds]
    assert not ghost, (
        f"layers.norm.migrated 에 대장에 없는 키가 있다: {ghost}\n"
        "  오타이거나 datasets 에서 지운 키다. 어느 쪽이든 이관 기록이\n"
        "  가리키는 대상이 없으므로 무엇을 옮겼는지 알 수 없다.")


def test_declaration_matches_wiring():
    """**선언과 배선이 서로를 배반하지 않는가.** §77 재발 차단.

    migrated 가 찼는데 ingest 가 RAW 만 읽으면, 옮겼다고 적어놓고
    아무 일도 안 한 것이다. 반대도 같다.
    """
    mig = _layer().get("migrated") or []
    src = _ingest_src()
    reads_norm, raw_only = _reads_norm(src), _hardcodes_raw(src)

    if mig and not reads_norm:
        raise AssertionError(
            f"layers.norm.migrated 에 {len(mig)}건이 있는데 "
            "ingest 가 NORM 을 읽지 않는다.\n"
            f"  선언: {mig}\n"
            f"  코드: paths_of(e, RAW) 로 못 박힘\n\n"
            "  ★ DECISIONS §77 이 정확히 이 상태였다. 선언만 채우고\n"
            "    배선을 안 해서 파이프라인은 그대로 raw 를 읽었고,\n"
            "    golden 은 segments.geojson 만 보므로 초록이었다.\n"
            "  ingest.build 와 main 의 paths_of(e, RAW) 를 이관 여부에\n"
            "  따라 갈리는 base 로 바꾼다.")

    # ★ 배선이 선언보다 먼저 들어오는 것은 정상이다. 그것이 이 저장소가
    #   정한 순서다 — 검사 → 배선 → 한 건 이관 → golden. 다만 배선이
    #   **대장을 읽고 갈리는지**는 봐야 한다. 무조건 norm 을 읽으면
    #   migrated 에서 키를 빼도 안 돌아가고, 그러면 되돌릴 수가 없다.
    if reads_norm and not re.search(r"\bprep\.migrated\s*\(\s*\)", src):
        raise AssertionError(
            "ingest 가 NORM 을 읽는데 `prep.migrated()` 로 갈리지 않는다.\n"
            "  대장이 입력 계층을 못 끄면 한 건씩 옮기는 절차가 성립하지\n"
            "  않는다(layers.norm.caveats). 이관 여부로 분기시킨다.")

    if mig and raw_only and len(mig) >= len(_datasets()):
        raise AssertionError(
            "전 소스를 이관했다고 선언했는데 RAW 하드코딩이 남아 있다.\n"
            "  일부만 갈렸을 수 있다. paths_of(e, RAW) 호출 자리를 전부 확인한다.")


def test_status_matches_migrated():
    """`status` 문자열과 `migrated` 가 같은 말을 하는가."""
    lay = _layer()
    status, mig = (lay.get("status") or "").strip(), lay.get("migrated") or []

    if status == "미구현":
        assert not mig, (
            f"status 는 '미구현' 인데 migrated 에 {len(mig)}건이 있다.\n"
            f"  {mig}\n"
            "  한 건이라도 옮겼으면 '미구현' 이 아니다. doctor.py ② 가\n"
            "  이 문자열을 읽어 '해야 할 것' 을 낸다 — 낡으면 안내가 틀린다.")
    else:
        assert mig, (
            f"status 가 '{status}' 인데 migrated 가 비어 있다.\n"
            "  미구현을 벗어났다고 적으려면 옮긴 키가 있어야 한다.")


def test_norm_naming_is_stricter_than_raw():
    """norm 의 파일명 규약이 실재하는가.

    ★ norm 은 '형식만 정규화한 것' 이다(layers.norm.what). 이름 규약이
      없으면 raw 와 구분이 안 되고, 두 계층에 같은 파일이 있을 때
      어느 쪽을 읽는지 사람이 알 수 없다.
    """
    lay = _layer()
    assert lay.get("naming"), "layers.norm.naming 이 없다."
    assert lay.get("encoding") == "utf-8", (
        "layers.norm.encoding 이 utf-8 이 아니다.\n"
        "  norm 의 존재 이유가 BOM · cp949 · CRLF 를 한 자리에서 없애는 것이다"
        "(PLAN #16).")
    re.compile(lay["naming"])  # 깨진 정규식이면 여기서 죽는다
