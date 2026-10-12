#!/usr/bin/env python3
"""
proposalcheck.py — **기획서 정본(`docs/proposal.md`)이 낡았는가.**

    uv run python tools/proposalcheck.py            판정 (verify.sh · CI)
    uv run python tools/proposalcheck.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 (2026-10-09 · DECISIONS §444 · PLAN #142) ─────────
`tools/docx_check.py`(삭제)가 종전에 여덜 축으로 기획서를 봤다. 그 도구가 읽은 것은
`docs/proposal.docx` 이고, 정본은 2026-10-09 에 `docs/proposal.md` 로
옮겨졌다(§425) — **그때부터 그 검사는 사본을 봤다.** 정본이 틀려도 사본이
맞으면 초록이고, 실제로 그 틈으로 「GRAY 사유는 네 가지」가 살아남았다.

docx 를 은퇴시키려면 그 여덜 축이 **먼저** 정본 쪽에 서야 한다. 어디로
갔는지 한 곳에 적는다 —

    ①~④ 수치 (구간 수 · 판정 4종 · 회색 사유별)  → `tools/docnum_check.py`
         ★ 회색 사유 다섯과 그 **가짓수 낱말**도 거기 섰다(§444).
    ⑤ 정방향 (고칠 것이 남았는가)                → **없앴다.** md 는 diff 가
         되므로 도구가 글을 고칠 이유가 없다(R9). docx 가 바이너리라서
         필요했던 도구였고, 그 사유가 사라졌다.
    ⑥ 역방향 (규칙의 닻이 남았는가)              → ⑤ 가 없으니 짝도 없다.
         대신 **폐기된 이름**(아래 `RETIRED`)이 같은 일을 한다 — 옛 문구가
         남았는가를 묻는 축이고, 고치는 쪽이 없어도 선다.
    ⑦ 참조 · ⑧ 긴 칸 · 총연장 · 캡션             → **이 파일**
    개요 층 (`docstyle`)                        → 없앴다. 63쪽 PDF 의 북마크
         0개가 그 검사의 사유였고, HTML 은 `h1`~`h6` 가 개요다.

── 판정 ──────────────────────────────────────────────────────
    총연장이 적혀 있는데 다르다        실패 — **안 적힌 것은 어긋남이 아니다**
    캡션에 낡은 어휘가 있다            실패
    폐기된 이름이 본문에 있다          실패
    드는 경로·파일이 저장소에 없다      실패
    긴 칸이 래칫과 다르다              실패 — 늘어도 줄어도 (sizecheck 와 같은 규율)

IN    docs/proposal.md · data/golden/segments.fingerprint.json · sources.yaml
OUT   표준출력 (판정)
PARAM RETIRED · CAPTION_STALE · LONG_*
밖    **수는 안 본다** — 구간 수 · 판정 4종 · 회색 사유는 `docnum_check` 가
      든다. 둘이 겹치면 정본이 둘이 된다(§18-3). **그림이 옳은가**도 안 본다
      (`render_figures --check` · `htmlfigs --check`). **화면이 md 와 같은가**도
      안 본다(`build_proposal --check`).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from firelane import paths as _p

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "docs" / "proposal.md"
GOLDEN = _p.GOLDEN / "segments.fingerprint.json"

#: 폐기된 이름. 문서에 남아 있으면 독자가 그대로 따라 한다.
#: ★ 종전 `tools/docx_check.py`(삭제)의 `RETIRED` 에서 그대로 왔다.
#:   사유도 그대로다 — 날짜가 근거다.
RETIRED = {
    "src/etl": "패키지가 src/firelane 으로 바뀌었다(2026-08-21)",
    "app.js": "web/js/ 모듈로 쪼갰다가(DECISIONS §27) 2026-09-22 에 옛 지도째 "
              "걷어냈다 — 관제 화면(web/navi ?view=ops)이 넘겨받았다",
    "requirements-etl": "삭제됐다. uv.lock 이 정본이다(2026-08-23)",
    "PostGIS": "미채택. segments.geojson 규모라 쓸 자리가 아니다",
    "apply.py": "패치 zip 절차를 폐기했다(DECISIONS §65)",
    # ★ 2026-10-09 (§444 · #142) 신설. 이 판이 없앤 것들이다. 기획서가 제
    #   산출 경로를 적는 자리가 있어, 지운 뒤 그 이름이 남으면 거짓이 된다.
    "proposal.docx": "은퇴했다(§440-1). 정본은 docs/proposal.md 하나다",
    "proposal.pdf": "은퇴했다(§440-1). 화면은 web/proposal.html 이다",
    "docx_fix": "없앴다(§444). md 는 diff 가 되므로 글을 고치는 도구를 두지 않는다",
}

#: 그림 캡션에서만 보는 어휘. 본문에서는 맥락이 다를 수 있어 캡션에 한정한다.
CAPTION_STALE = {
    # ★ 2026-09-02. 종전에 `datasets 41종` 을 **하드코딩**했다가 하루 만에
    #   낡았다(실물 43). 도구가 스스로 같은 병에 걸린 것이다. 대장에서 센다.
    "원천 11종": (
        "기획서 원천 데이터 표의 행 수를 센 값이다. 그 표가 낡았다 — 대장은"
        " {ds}종이다(MASTER §6). 캡션만 고치면 안 되고 표와 그 파급을 같이 본다"),
}

#: 긴 칸 래칫 — 2026-10-09 실측 **6칸 · 최장 1,376자**(개요표). docx 판의
#: 수(6칸 · 1,343자)와 거의 같다. 개요표는 **제출 양식**이라 칸 안에 문단이
#: 드는 것이 양식이고, 쪼개면 양식이 깨진다. 그래서 **자라지 않게** 묶는다.
LONG_CELL = 250
LONG_MAX_N = 6
LONG_MAX_LEN = 1376

#: 「총연장 58.3km」 꼴. `km` 과 `m` 둘 다 받는다.
TOTAL_RE = re.compile(
    r"총\s*연장\s*(?:은|이|:)?\s*(?:약\s*)?([\d,]+(?:\.\d+)?)\s*(km|m)\b")

#: 기획서가 드는 저장소 경로. `data/` 는 저장소 밖(FIRE_LANE_DATA)이라 뺀다.
PATH_RE = re.compile(
    r"(?<![\w/.])((?:src|tools|web|docs|tests|infra|\.github)/[\w./-]+)")
FILE_RE = re.compile(r"\b[\w-]+\.(?:py|js|ts|tsx|yml|yaml)\b")


def text(p: Path = MD) -> str | None:
    """정본 본문. **없으면 `None`** — 빈 문자열을 내면 모든 축이 조용히 통과한다."""
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8")


def cells(txt: str) -> list[str]:
    """파이프 표의 칸. 구분선(`---`)은 칸이 아니다."""
    out = []
    for ln in txt.splitlines():
        if not ln.startswith("|"):
            continue
        for c in ln.strip("|").split("|"):
            c = c.strip()
            if c and not set(c) <= set("-: "):
                out.append(c)
    return out


def captions(txt: str) -> list[str]:
    return [ln for ln in txt.splitlines() if re.match(r"\s*\[?그림\s*\d+", ln)]


def ledger_scale() -> dict[str, int]:
    """대장 규모. 숫자를 손으로 적지 않는다."""
    import yaml
    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    return {"ds": len(y.get("datasets") or {}), "ret": len(y.get("retired") or {})}


def total_m() -> float | None:
    if not GOLDEN.exists():
        return None
    return json.loads(GOLDEN.read_text(encoding="utf-8")).get("L1", {}).get(
        "length_total_m")


def total_faults(txt: str, want: float | None) -> list[str]:
    """총연장이 **적혀 있는데 다른가.** 안 적힌 것은 어긋남이 아니다.

    ★ 함수로 떼어 둔 사유는 하나다 — **실물에 이 수가 0회 나온다.** 실물만
      보면 이 축이 살았는지 죽었는지 영원히 모르고, 그것이 2026-09-22 부터
      이 축을 사문으로 둔 이유다(§409). 합성 입력으로 양방향을 밀 수 있어야 한다.
    """
    if not want:
        return []
    want_km = round(float(want) / 1000, 1)
    out = []
    for m in TOTAL_RE.finditer(txt):
        raw = float(m.group(1).replace(",", ""))
        km = raw if m.group(2) == "km" else raw / 1000
        if abs(km - want_km) > 0.05:
            out.append(f"총연장 {m.group(1)}{m.group(2)} → "
                       f"**{want_km}km ({float(want):,.1f}m)**")
    return out


def retired_faults(txt: str, table: dict[str, str] | None = None) -> list[str]:
    t = RETIRED if table is None else table
    return [f"폐기: `{k}` — {why}" for k, why in t.items() if k in txt]


def caption_faults(lines: list[str], scale: dict[str, int],
                   table: dict[str, str] | None = None) -> list[str]:
    t = CAPTION_STALE if table is None else table
    out = []
    for ln in lines:
        for k, why in t.items():
            if k in ln:
                out.append(f"캡션이 낡았다: `{k}` — {why.format(**scale)}")
    return out


def tracked() -> tuple[list[str], str | None]:
    """추적 파일 목록. **실패하면 `None` 사유를 같이 낸다**(§372 · 회색 = NULL).

    ★ 2026-09-24 (DECISIONS §239) 의 교훈을 그대로 가져왔다. 종전 docx 판은
      `git ls-files` 의 종료코드를 안 봐서, git 이 없으면 참조 축이 **0건으로
      초록**이 됐다. 0건은 청결이 아니다.
    """
    g = subprocess.run(["git", "ls-files"], cwd=ROOT,  # noqa: S603 S607 — 고정 인자
                       capture_output=True, text=True, check=False)
    if g.returncode != 0 or not g.stdout.split():
        return [], f"rc={g.returncode} {g.stderr.strip()[:120]}"
    return g.stdout.split(), None


def ref_faults(txt: str, files: list[str]) -> list[str]:
    """드는 경로·파일이 실재하는가. `files` 가 비면 **아무 말도 안 한다** —
    판정은 부르는 쪽이 든다(빈 목록에서 0건을 「청결」로 읽지 않게)."""
    if not files:
        return []
    names = {Path(x).name for x in files}
    out = []
    for m in sorted(set(PATH_RE.findall(txt))):
        q = m.rstrip(".")
        if not (ROOT / q).exists():
            out.append(f"드는 경로가 없다: `{q}`")
    for m in sorted(set(FILE_RE.findall(txt))):
        if m not in names:
            out.append(f"드는 파일이 저장소에 없다: `{m}`")
    return out


def long_faults(lens: list[int]) -> list[str]:
    """긴 칸 **양방향** 래칫. 줄었을 때도 운다 — 안 내리면 다시 늘어도 안 운다."""
    long = [n for n in lens if n > LONG_CELL]
    top = max(lens, default=0)
    if len(long) > LONG_MAX_N or top > LONG_MAX_LEN:
        return [f"긴 칸 — {LONG_CELL}자 초과 {len(long)}칸 · 최장 {top}자 "
                f"(상한 {LONG_MAX_N}칸 · {LONG_MAX_LEN}자). "
                "표를 문단 저장소로 키우지 않는다"]
    if len(long) < LONG_MAX_N or top < LONG_MAX_LEN:
        return [f"긴 칸 — 줄었다({len(long)}칸 · 최장 {top}자). "
                "tools/proposalcheck.py 의 LONG_MAX_N · LONG_MAX_LEN 을 내려라"]
    return []


RATCHETS = {"LONG_MAX_N": "down", "LONG_MAX_LEN": "down"}


def ratchet_values() -> dict[str, int]:
    """**재기만 한다** — 판정은 `long_faults` 가 든다."""
    txt = text()
    lens = [len(c) for c in cells(txt)] if txt else []
    return {"LONG_MAX_N": sum(1 for n in lens if n > LONG_CELL),
            "LONG_MAX_LEN": max(lens, default=0)}


def audit() -> list[str]:
    txt = text()
    if txt is None:
        return [f"{MD.relative_to(ROOT)} 이 없다 — 기획서 정본이 사라졌다"]
    bad = total_faults(txt, total_m())
    bad += caption_faults(captions(txt), ledger_scale())
    bad += retired_faults(txt)
    files, why = tracked()
    if why:
        bad.append(f"참조 — `git ls-files` 가 실패했다. 참조 축이 "
                   f"아무것도 못 본다 — **0건은 청결이 아니다**: {why}")
    bad += ref_faults(txt, files)
    bad += long_faults([len(c) for c in cells(txt)])
    return bad


def selftest() -> int:
    bad: list[str] = []
    scale = {"ds": 9, "ret": 1}
    # ★ 총연장 — 양방향. 안 적힌 것은 어긋남이 아니다
    if not total_faults("총연장 50.0km 다", 58308.7):
        bad.append("총연장이 달라도 안 운다")
    if total_faults("총연장 58.3km 다", 58308.7):
        bad.append("맞는 총연장에서 운다")
    if total_faults("총연장이라는 말이 없다", 58308.7):
        bad.append("안 적힌 것을 어긋남으로 읽는다")
    if total_faults("총연장 50.0km", None):
        bad.append("정본이 없는데 판정한다")
    # ★ 폐기 이름 · 캡션
    if not retired_faults("우리는 src/etl 을 쓴다"):
        bad.append("폐기된 이름을 안 문다")
    if retired_faults("우리는 src/firelane 을 쓴다"):
        bad.append("멀쩡한 이름을 문다")
    if not caption_faults(["[그림 9] 원천 11종 개요"], scale):
        bad.append("낡은 캡션을 안 문다")
    # ★ 캡션 축의 **범위**는 `captions()` 가 가른다 — 본문에 같은 낱말이 있어도
    #   안 문다(그쪽은 맥락이 다를 수 있다). 그 가름을 여기서 못박는다.
    if captions("원천 11종이라고 본문에 적었다\n") != []:
        bad.append("캡션이 아닌 줄을 캡션으로 읽는다")
    if captions("[그림 9] 원천 11종 개요\n") == []:
        bad.append("캡션 줄을 못 찾는다")
    # ★ 참조 — 빈 목록에서 조용한가 · 없는 경로를 무는가
    if ref_faults("tools/없는파일.py 를 본다", []):
        bad.append("추적 목록이 비었는데 판정한다")
    if not ref_faults("tools/절대없는이름.py 를 본다", ["tools/proposalcheck.py"]):
        bad.append("없는 경로를 안 문다")
    if ref_faults("tools/proposalcheck.py 를 본다", ["tools/proposalcheck.py"]):
        bad.append("있는 경로를 문다")
    # ★ 긴 칸 — 늘어도 줄어도 운다
    if not long_faults([LONG_CELL + 1] * (LONG_MAX_N + 1) + [LONG_MAX_LEN]):
        bad.append("긴 칸이 늘었는데 안 운다")
    if not long_faults([LONG_CELL + 1] * LONG_MAX_N + [LONG_MAX_LEN + 1]):
        bad.append("최장이 넘었는데 안 운다")
    if not long_faults([LONG_CELL + 1]):
        bad.append("긴 칸이 줄었는데 안 운다 — 느슨한 래칫은 지난 기록이다")
    # ★ **정상 입력에서 안 우는가.** 2026-10-09 돌연변이가 이 구멍을 냈다 —
    #   `>` 를 `>=` 로 바꿨는데 자기검사가 통과했다(실물을 보는 시험만 울었다).
    #   양방향을 미는 문이 셋이어도 **경계에서 안 우는 쪽**을 안 밀면 비어 있다.
    ok = [LONG_CELL + 1] * (LONG_MAX_N - 1) + [LONG_MAX_LEN]
    if long_faults(ok):
        bad.append("기록과 **똑같은데** 운다 — 경계가 한 칸 밀렸다")
    # ★ 표 파싱 — 구분선은 칸이 아니다
    if cells("| --- | :--- |\n") != []:
        bad.append("표 구분선을 칸으로 센다")
    if cells("| 가 | 나 |\n") != ["가", "나"]:
        bad.append("표 칸을 못 읽는다")
    if text(ROOT / "없는파일.md") is not None:
        bad.append("없는 파일에서 빈 문자열을 낸다 — 모든 축이 조용히 통과한다")

    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 총연장 · 폐기 · 캡션 · 참조 · 긴 칸 양방향")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="기획서 정본 대조")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    bad = audit()
    if bad:
        print(f"✗ 기획서 정본이 어긋난다. {len(bad)}건")
        for b in bad:
            print(f"    {b}")
        print(f"\n  정본은 {MD.relative_to(ROOT)} 이고 수의 정본은 산출물이다"
              " (MASTER §0-3).")
        print("  기획서는 문서 넷 중 **유일하게 외부가 읽는다** — 어긋나면"
              " 비용이 가장 크다.")
        return 1
    txt = text() or ""
    print(f"✓ 기획서 정본 OK — 표 칸 {len(cells(txt))} · 캡션 {len(captions(txt))}"
          f" · 폐기 어휘 {len(RETIRED)}종 · 긴 칸 {LONG_MAX_N}칸 상한 {LONG_MAX_LEN}자")
    return 0


if __name__ == "__main__":
    sys.exit(main())
