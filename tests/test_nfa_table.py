"""소방서 대조 표 — **문서가 봉인 사본을 따라가는가.**  (DECISIONS §346)

── 왜 생겼나 ───────────────────────────────────────────────────
`MASTER §4` 가 소방서 지정 7구간과 우리 폭의 편차를 표로 든다. 그 절의 강제자
칸이 2026-10-01 까지 이렇게 적고 있었다 —

    절대편차 값 자체는 **실측이라 대조 도구가 없다**

그 말이 참인 동안 표가 낡았다. 봉인 `20260930-covrate` 가 9월 30일에 이미
`abs_dev_sum_m: 8.78` 을 적었는데 문서는 **8.31** 이었다 — 즉 **저장소 안에
정본이 있었고 아무도 대조하지 않았다.** 「대조 도구가 없다」는 선언이 그 자리를
영구 사각지대로 만든 것이다.

★ 이것이 §92 가 세 번 겪은 꼴의 변형이다. 그때는 어휘가 갈려 검사가 비껴갔고,
  여기는 **검사가 없다고 적어 두고 끝냈다.** 적어 두는 것은 보이게 만드는
  것이고 고치는 것이 아니다(§342-4 가 `밖` 칸에서 배운 것과 같다).

── 무엇을 정본으로 보는가 ──────────────────────────────────────
**가장 최근 봉인 사본** `data/baseline/*/nfa_compare.json` 이다. 매 실행이 쓰는
`data/processed/nfa_compare.json` 이 아니다 — 그쪽은 `.gitignore` 라 **저장소만
받은 사람에게는 없고**, 없는 것을 정본으로 삼으면 이 검사가 clone 직후 환경에서
통째로 건너뛴다(그러면 또 사각지대다).

★ 봉인은 커밋된다(`.gitignore` 머리말 — 「봉인과 북마크는 증표라서 커밋한다」).
  그래서 이 검사는 레이크도 파이프라인도 없이 돈다.

★ **봉인이 움직이면 이 시험이 빨개지고, 그것이 맞다.** `golden` 이 산출물에
  대해 하는 일을 이 시험이 문서에 대해 한다 — 값이 움직였으면 사람이 문서를
  고친다.

IN    docs/MASTER.md §4 표 · data/baseline/*/nfa_compare.json
OUT   없음 (검사)
밖    **편차가 작은지는 안 본다.** 그것은 적합이지 검증이 아니고(§4-1),
      몇이어야 옳은지는 이 검사가 말할 수 없다. 여기가 드는 것은
      **문서와 봉인이 같은 수를 말하는가** 하나다.
      **매 실행 산출물과도 안 댄다.** 봉인 뒤에 파이프라인이 한 번 더 돌면
      값이 달라질 수 있고, 그 차이는 `baseline.py diff` 의 일이다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs" / "MASTER.md"
#: 표 한 행. `| 도로명 | 5m | 4.99m | **-0.01** | 35 |`
ROW = re.compile(r"^\|\s*(\S+)\s*\|\s*(\d+(?:\.\d+)?)m\s*\|\s*(\d+(?:\.\d+)?)m\s*\|"
                 r"\s*\*{0,2}([+-]?\d+(?:\.\d+)?)\*{0,2}\s*\|\s*(\d+)\s*\|\s*$", re.M)
SUM = re.compile(r"절대편차 합 (\d+(?:\.\d+)?)m")


def _seal() -> dict:
    """가장 최근 봉인 사본. `as_of` 로 고른다 — 폴더 이름이 아니다."""
    got = []
    for q in sorted((ROOT / "data" / "baseline").glob("*/nfa_compare.json")):
        d = json.loads(q.read_text(encoding="utf-8"))
        if d.get("rows"):
            got.append((d.get("as_of", ""), q.parent.name, d))
    assert got, "`data/baseline/*/nfa_compare.json` 을 하나도 못 찾았다 — 수집기가 죽었다"
    return max(got)[2]


def _table() -> list[tuple[str, float, float, float, int]]:
    """MASTER §4 의 표 행들."""
    return [(m[1], float(m[2]), float(m[3]), float(m[4]), int(m[5]))
            for m in ROW.finditer(MASTER.read_text(encoding="utf-8"))]


def test_the_row_pattern_is_not_an_empty_net() -> None:
    """★ **빈 그물 물음**(MASTER §17-0 ③). 정규식이 죽으면 아래 전부가 조용히
    통과한다 — 0행을 0행과 비교하기 때문이다."""
    rows = _table()
    assert len(rows) >= 7, f"MASTER §4 표에서 {len(rows)}행만 읽었다 — 표기가 바뀌었다"
    assert {r[0] for r in rows} >= {"동명로20번길", "필문대로289번길"}, "도로명을 못 읽는다"


def test_every_road_in_the_seal_is_in_the_table() -> None:
    """봉인이 든 도로가 문서에 있는가. 빠지면 **표가 조용히 줄어든** 것이다."""
    seal = {r["road"] for r in _seal()["rows"]}
    doc = {r[0] for r in _table()}
    assert not (seal - doc), f"봉인에 있는데 MASTER §4 표에 없다 — {sorted(seal - doc)}"


def test_each_width_and_deviation_agrees_with_the_seal() -> None:
    """행마다 **우리 중앙폭 · 편차 · 세그 수**가 봉인과 같은가.

    ★ 합만 보면 두 행이 서로 상쇄될 때 못 본다. 행을 본다.
    """
    doc = {r[0]: r for r in _table()}
    bad = []
    for r in _seal()["rows"]:
        d = doc.get(r["road"])
        if d is None:
            continue                       # 위 시험이 든다
        for what, docv, sealv in (("소방서", d[1], r["nfa_m"]),
                                  ("우리 중앙", d[2], r["ours_median_m"]),
                                  ("편차", d[3], r["dev_m"]),
                                  ("세그", float(d[4]), float(r["n_seg"]))):
            if abs(docv - sealv) > 0.005:
                bad.append(f"  {r['road']:16} {what:6} 문서 {docv} ≠ 봉인 {sealv}")
    assert not bad, (
        "MASTER §4 표가 봉인 사본과 다르다 —\n" + "\n".join(bad)
        + "\n\n  봉인이 정본이다. 값이 움직였으면 **문서를 고쳐라**(MASTER §17).\n"
          "  2026-10-01 에 이 자리가 사흘 낡아 있었다(DECISIONS §346).")


def test_the_stated_sum_is_the_seal_sum() -> None:
    """서술된 합이 봉인의 `abs_dev_sum_m` 인가."""
    seal = _seal()
    text = MASTER.read_text(encoding="utf-8")
    stated = [float(x) for x in SUM.findall(text)]
    assert stated, "「절대편차 합 N m」 서술을 못 찾았다 — 표기가 바뀌었다"
    want = float(seal["abs_dev_sum_m"])
    assert any(abs(v - want) < 0.005 for v in stated), (
        f"MASTER 가 든 합 {stated} 에 봉인 값 {want} 가 없다.\n"
        "  ★ 옛 회차를 사연으로 적은 수는 그대로 둔다 — 이 시험은 **하나라도**\n"
        "    봉인과 같은 수가 서술돼 있는지만 본다. 역사를 고치라는 것이 아니다.")


def test_the_sum_is_the_sum_of_the_rows() -> None:
    """★ 봉인 자신이 **제 안에서** 맞는가. 합과 행이 어긋나면 문서를 맞춰도
    헛되다 — 정본이 먼저 틀린 것이다."""
    seal = _seal()
    rows = sum(abs(float(r["dev_m"])) for r in seal["rows"])
    assert abs(rows - float(seal["abs_dev_sum_m"])) < 0.02, (
        f"봉인의 합 {seal['abs_dev_sum_m']} ≠ 행 절대값 합 {rows:.2f}")
