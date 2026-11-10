"""기획서의 영상판정 문단 수가 **발행본에서 유도한 값**과 같다.  (감사 5-3 · Zm22)

`docnum_check` 는 판정 건수와 사유별 수만 본다 — 이 문단의 연장(m) · 비율(%) · CCTV 거리 요약은 손으로 적혀 있었고
Zm19 뒤에도 옛 값(400구간 · 17,181m · 29% · 65%)으로 남았다. 여기서 발행본이 말하는 값을 재서 문장에 댄다.

IN    docs/proposal.md · web/data/segments.geojson
OUT   없음 (검사)
PARAM 없음
밖    **그 비율이 옳은 해석인가**는 안 본다 — 문장의 수가 발행본에서 나온 수와 같은지만 본다.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "web/data/segments.geojson"


def _facts() -> dict:
    if not SEG.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 발행본이 없다")
    P = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    total = sum(p["length_m"] for p in P)
    unk = [p for p in P if p["verdict"] == "unknown"]
    dist = [p["cctv_dist_m"] for p in P if p["cctv_dist_m"] is not None]
    inn = sum(1 for p in P if p["cv_feasible"])
    return {"unk_n": len(unk), "unk_m": round(sum(p["length_m"] for p in unk)),
            "unk_pct": round(sum(p["length_m"] for p in unk) / total * 100, 1),
            "out_pct": round((1 - inn / len(P)) * 100, 1),
            "med": round(statistics.median(dist), 1), "max": round(max(dist))}


def _doc() -> str:
    return (ROOT / "docs/proposal.md").read_text(encoding="utf-8")


def test_unavailable_video_span_matches_the_publication() -> None:
    f, doc = _facts(), _doc()
    want = f"영상판정 불가는 {f['unk_n']}구간 · {f['unk_m']:,}m 이며 전체 연장의 {f['unk_pct']}%에 해당한다"
    assert want in doc, f"기획서 영상판정 문단이 발행본과 다르다 — 기대: {want}"


def test_video_share_and_cctv_distance_match_the_publication() -> None:
    f, doc = _facts(), _doc()
    assert f"골목의 {f['out_pct']}%에는 적용할 수 없다" in doc
    assert f"CCTV 최단거리 중앙값은 {f['med']}m, 최대 {f['max']}m다" in doc


def test_the_stale_values_are_gone() -> None:
    doc = _doc()
    for stale in ("400구간 · 17,181m", "전체 연장의 29%", "골목의 65%"):
        assert stale not in doc, f"낡은 값이 남았다: {stale}"


def test_the_repair_door_reports_a_cover_date_repair_as_a_repair_not_as_nothing():
    """PLAN #217 후속 — (★ 이 자리에 둔 이유: 이 파일은 변이 장부의 과녁 도구 이름을 안 든다 — `test_fix_door.py` 에 두면 장부 넷이 낡는다.)

     문이 표지 날짜를 **고치고도** 「고칠 것이 없다 · 고침 0」으로 보고했다(`--touch-today` 의 `줄 N개 수정` 이 판별 정규식에 없었다).

    실제로 낡은 표지를 주입해 문을 돌렸더니 날짜는 돌아오고 ⑥ 은 초록인데 요약이 「고침 0」이었다. 사람은 아무것도 안 움직였다고 읽는다.
    판별은 **바뀐 줄이 1 이상일 때만** 고침이다 — `줄 0개 수정` 은 같은 문장 꼴이라 그대로여야 한다(날짜가 이미 오늘일 때도 「표지를 옮겼다」가 찍히므로 그 문장은 못 쓴다)."""
    import re
    import subprocess

    body = (ROOT / "tools" / "fix.sh").read_text(encoding="utf-8")
    pat = re.search(r"grep -qE '([^']*)'; then\s*\n\s*RESULTS\+=\(\"고침\"\)", body)
    assert pat, "fix.sh 의 고침 판별 줄을 못 찾았다 — 이 시험을 고쳐라"
    rx = pat.group(1)

    def hit(text: str) -> bool:
        return subprocess.run(["grep", "-qE", rx], input=text, text=True, timeout=30, check=False).returncode == 0

    assert hit("  proposal.md  줄 1개 수정\n  ★ 표지를 옮겼다 — 화면을 다시 구워라\n"), "표지를 고친 줄을 고침으로 안 센다"
    assert hit("  proposal.md  줄 12개 수정\n")
    assert not hit("  proposal.md  줄 0개 수정\n  ★ 표지를 옮겼다 — 화면을 다시 구워라\n"), "날짜가 이미 오늘인데 고침으로 센다 — 거짓 보고다"
    assert "proposal.md  줄 {n}개 {'수정' if write else '수정 예정'}" in (ROOT / "tools" / "build_proposal.py").read_text(encoding="utf-8"), \
        "생산자의 문장이 바뀌었다 — 판별 정규식도 맞춰라"
