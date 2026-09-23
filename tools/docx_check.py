#!/usr/bin/env python3
"""
docx_check.py — 기획서가 산출물과 어긋나지 않는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-27. 기획서는 문서 넷 중 **유일하게 외부가 읽는 것**인데,
시제 규칙 밖이라는 이유로 강제자가 없었다. 그래서 낡았다.

    docnum_check.py     README · MASTER · PLAN · DECISIONS  ← md 만 본다
    (없음)              proposal.docx               ← 아무도 안 본다

`PLAN §12` 가 갱신 대상 열 건을 표로 들고 있었으나 그 표 자체가 낡았다 —
"대상 222구간" 을 고치라고 적혀 있는데 문서에 `222` 는 없고 실제로는
`1,102` 가 박혀 있었다. **강제자 없는 목록은 목록도 낡는다.**

이 저장소가 반복해 배운 형태다 — 규약은 문서에 존재하고 강제하는 검사가
없다(MASTER §17).

── 무엇을 보는가 ───────────────────────────────────────────────
정본은 `data/golden/segments.fingerprint.json` 이다. 문서에 적힌 판정
숫자가 그것과 다르면 **산출물이 옳다**(MASTER §0-3).

    구간 수 · 판정 4종 · 총연장 · 폐기된 경로·기술명
    ⑤ 정방향  `docx_fix` 규칙이 아직 바꿀 것이 있는가 — 있으면 기획서가 산출물보다 낡았다
    ⑥ 역방향  규칙의 **닻**이 문서에 남았는가 — 찾을 것도 바꾼 결과도 없으면 배선이 떨어졌다
    ⑦ 참조    기획서가 드는 저장소 경로 · 파일 이름이 실재하는가
    ⑧ 긴 칸   표 칸이 250자를 넘는 수 · 최장 길이가 래칫 위로 자라지 않는가

★ 2026-09-22 (PLAN §13 W4-2 닫힘 · DECISIONS §217-5) — ⑤⑥⑦ 을 더했다. 종전엔 ①~④ 만 봐서
  「회색」 문단의 1,101 세대 수치 열한 자리가 **초록으로 통과했다**(구간 수 · 판정 4종만 봤다).
  고치는 쪽(`docx_fix`)과 잡는 쪽이 따로 놀면 잡는 쪽이 늘 좁다. 그래서 잡는 쪽이 고치는 쪽의
  규칙을 **그대로 돌려** 본다 — 규칙 목록이 하나다.

★ 모든 숫자를 보지 않는다. 시장 통계·법령 조항·비용 산정은 산출물과
  무관하며, 그것까지 검사하면 거짓 경보로 사람이 검사를 끈다.

IN    docs/*.docx · data/golden/segments.fingerprint.json
OUT   없음 (검사). --json 이면 stdout
PARAM RETIRED · 허용 오차 없음(정수 대조)
밖    **`docs/*.md` 는 안 본다.** 정본 셋의 숫자는 `docnum_check.py` 소관이고
      이 도구는 기획서(`.docx`) 하나만 든다 — 둘이 겹치면 정본이 둘이 된다(§18-3).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from firelane import paths as _p

GOLDEN = _p.GOLDEN / "segments.fingerprint.json"

# 폐기된 이름. 문서에 남아 있으면 독자가 그대로 따라 한다.
RETIRED = {
    "src/etl": "패키지가 src/firelane 으로 바뀌었다(2026-08-21)",
    "app.js": "web/js/ 모듈로 쪼갰다가(DECISIONS §27) 2026-09-22 에 옛 지도째 걷어냈다 — 관제 화면(web/navi ?view=ops)이 넘겨받았다",
    "requirements-etl": "삭제됐다. uv.lock 이 정본이다(2026-08-23)",
    "PostGIS": "미채택. segments.geojson 996KB 규모라 쓸 자리가 아니다",
    "apply.py": "패치 zip 절차를 폐기했다(DECISIONS §65)",
}

# 그림 캡션에서만 보는 어휘. 본문에서는 맥락이 다를 수 있어 캡션에 한정한다.
CAPTION_STALE = {
    # ★ 2026-09-02. 종전에 `datasets 41종` 을 **하드코딩**했다가 하루 만에
    #   낡았다(실물 43). 도구가 스스로 같은 병에 걸린 것이다. 대장에서 센다.
    "원천 11종": (
        "기획서 `§ 원천 데이터 목록` 표(T16)의 행 수를 센 값이다. 그 표가"
        " 낡았다 — 대장은 {ds}종이다(MASTER §6). 캡션만 고치면 안 되고"
        " 표와 다섯 자리를 같이 본다(PLAN §12 #20)"),
}


def _ledger_counts() -> dict[str, int]:
    """대장 규모. 숫자를 손으로 적지 않는다."""
    import yaml
    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    return {"ds": len(y.get("datasets") or {}),
            "ret": len(y.get("retired") or {})}


def _load_docx(p: Path) -> list[tuple[str, str]]:
    """(위치, 텍스트) 목록. 표 안까지 본다."""
    try:
        import docx
    except ImportError:
        return []
    d = docx.Document(str(p))
    out = [(f"P{i}", x.text) for i, x in enumerate(d.paragraphs) if x.text.strip()]
    for ti, t in enumerate(d.tables):
        for ri, r in enumerate(t.rows):
            for c in r.cells:
                if c.text.strip():
                    out.append((f"T{ti}R{ri}", c.text))
    return out


def _canon() -> dict[str, int | float]:
    if not GOLDEN.exists():
        return {}
    g = json.loads(GOLDEN.read_text(encoding="utf-8")).get("L1", {})
    v = g.get("verdict", {})
    return {
        "구간 수": g.get("n"),
        "통행 불가": v.get("blocked"),
        "통행 가능": v.get("clear"),
        "판정 보류": v.get("needs_cv"),
        "영상판정 불가": v.get("unknown"),
        "총연장": g.get("length_total_m"),
    }


def audit(p: Path) -> list[str]:
    cells = _load_docx(p)
    if not cells:
        return [f"  {p.name} 을 읽지 못했다 (python-docx 미설치?)"]

    bad: list[str] = []
    c = _canon()
    n = c.get("구간 수")

    # ── 1 · 구간 수 ──
    if n:
        for where, txt in cells:
            # ★ 2026-09-02. 종전에는 `구간` 뒤에 붙은 수만 봤다. 기획서는
            #   같은 것을 `산출단위` · `세그먼트` 로도 부르고, 실제로
            #   `산출단위 1,102` 가 두 곳에 살아 있었다 — **이 도구의 머리말이
            #   그 숫자를 만들어진 이유로 드는데 정작 못 잡고 있었다.**
            #   어휘가 갈려 검사가 비껴간 세 번째다(§49 · §91 · §92).
            #   수가 앞에 오는 형태(`1,102 산출단위`)도 함께 본다.
            for m in re.finditer(
                    r"(?:(\d{1,2},?\d{3})\s*(?:구간|산출단위|세그먼트)"
                    r"|(?:구간|산출단위|세그먼트)\s*(\d{1,2},?\d{3}))", txt):
                val = int((m.group(1) or m.group(2)).replace(",", ""))
                if 900 < val < 1400 and val != n:
                    bad.append(
                        f"  [{where}] 구간 수 {m.group(1) or m.group(2)}"
                        f" → **{n:,}**\n"
                        f"      …{txt.strip()[:70]}…")

    # ── 2 · 판정 4종 ──
    for label in ("통행 불가", "통행 가능", "판정 보류", "영상판정 불가"):
        want = c.get(label)
        if not want:
            continue
        for where, txt in cells:
            for m in re.finditer(rf"{label}\s*(\d{{2,4}})", txt):
                if int(m.group(1)) != want:
                    bad.append(
                        f"  [{where}] {label} {m.group(1)} → **{want}**\n"
                        f"      …{txt.strip()[:70]}…")

    # ── 3 · 그림 캡션 ──
    # ★ 그림은 이미지라 기계가 못 본다. 그러나 **캡션은 텍스트다.**
    #   24장 전부 `[그림 N] 제목 — 설명` 형식이 일정해서 파싱이 되고,
    #   캡션에 든 고유명이 저장소 어휘와 다르면 그림도 낡았을 가능성이 높다.
    #   그림 자체는 여전히 사람이 봐야 한다 — 여기서 잡는 것은 절반이다.
    for where, txt in cells:
        if not re.match(r"\s*\[?그림\s*\d+", txt):
            continue
        for name, why in CAPTION_STALE.items():
            if name in txt:
                why = why.format(**_ledger_counts())
                bad.append(f"  [{where}] 캡션이 낡았다: `{name}` — {why}\n"
                           f"      …{txt.strip()[:70]}…")

    # ── 4 · 폐기된 이름 ──
    for where, txt in cells:
        for name, why in RETIRED.items():
            if name in txt:
                bad.append(f"  [{where}] 폐기: `{name}` — {why}\n"
                           f"      …{txt.strip()[:70]}…")

    # ── 5 · 6 · 정방향 · 역방향 — 고치는 쪽의 규칙을 그대로 돌린다 ──
    import importlib.util
    spec = importlib.util.spec_from_file_location("_docx_fix", ROOT / "tools" / "docx_fix.py")
    fx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fx)
    full = "\n".join(txt for _, txt in cells)
    for rx, rep, why in fx.rules():
        hits = [(w, x) for w, x in cells if re.search(rx, x)]   # docx_fix 와 같은 플래그(re.M 없음)
        changed = [(w, x) for w, x in hits if re.sub(rx, rep, x) != x]
        for w, x in changed[:3]:
            bad.append(f"  [{w}] 정방향 — `docx_fix` 가 아직 바꾼다({why}). `tools/docx_fix.py --write`\n"
                       f"      …{x.strip()[:70]}…")
        plain = re.sub(r"\\g<\d+>", "", rep).replace("&lt;", "<").strip()
        if not hits and plain and plain not in full:
            bad.append(f"  역방향 — 닻이 떨어진 규칙: `{rx[:50]}` → 찾을 것도 바꾼 결과도 문서에 없다({why})")

    for anchor, new, why in fx.inserts():
        if anchor not in full and new not in full:
            bad.append(f"  역방향 — 닻이 떨어진 삽입: `{anchor[:40]}` 도 넣을 문단도 문서에 없다({why})")
        elif new not in full:
            bad.append(f"  정방향 — 넣을 문단이 아직 없다: `{new[:40]}…` `tools/docx_fix.py --write`")

    # ── 7 · 참조 — 기획서가 드는 저장소 경로 · 파일이 실재하는가 ──
    #   `data/` 아래는 저장소 밖(FIRE_LANE_DATA)이라 뺀다. 파일 이름은 추적 파일의 이름과 대조한다
    import subprocess
    # ★ 2026-09-24 (DECISIONS §239). `CompletedProcess` 를 안 받아 **종료코드를 볼
    #   방법이 없었다.** 아래 판정 둘이 `if tracked and …` 라, git 이 없거나
    #   저장소 밖에서 돌면 `tracked` 가 비어 두 갈래가 **0건으로 초록**이 됐다.
    #   이 도구는 verify · CI 양쪽에 걸린 관문이다 — 빈 그물이 초록으로 위장한다.
    _g = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    if _g.returncode != 0 or not _g.stdout.split():
        bad.append("  참조 — `git ls-files` 가 실패했다(또는 추적 파일 0건). "
                   "⑦ 이 아무것도 못 본다 — 0건은 청결이 아니다: "
                   f"rc={_g.returncode} {_g.stderr.strip()[:120]}")
        return bad
    tracked = _g.stdout.split()
    names = {Path(x).name for x in tracked}
    for m in sorted(set(re.findall(r"(?<![\w/.])((?:src|tools|web|docs|tests|infra|\.github)/[\w./-]+)", full))):
        q = m.rstrip(".")
        if tracked and not (ROOT / q).exists():
            bad.append(f"  참조 — 기획서가 드는 경로가 없다: `{q}`")
    for m in sorted(set(re.findall(r"\b[\w-]+\.(?:py|js|ts|tsx|yml|yaml)\b", full))):
        if tracked and m not in names:
            bad.append(f"  참조 — 기획서가 드는 파일이 저장소에 없다: `{m}`")

    # ── 8 · 긴 칸 래칫 (W4-7 닫힘 · DECISIONS §218-6) ──
    #   표0(개요표)의 여섯 칸이 250자를 넘는다. 그 표는 **제출 양식의 개요표**라 칸 안에 문단이
    #   드는 것이 양식이다 — 쪼개면 양식이 깨진다. 그래서 분해하지 않고 **자라지 않게** 묶는다.
    #   줄면 상한을 내린다(양방향 래칫 · sizecheck 와 같은 규율).
    import docx as _docx
    _d = _docx.Document(str(p))
    _seen: set = set()
    _lens = []
    for _t in _d.tables:
        for _r in _t.rows:
            for _c in _r.cells:
                if _c._tc in _seen:
                    continue
                _seen.add(_c._tc)
                _lens.append(len(_c.text))
    _long = [n for n in _lens if n > LONG_CELL]
    if len(_long) > LONG_MAX_N or max(_lens, default=0) > LONG_MAX_LEN:
        bad.append(f"  긴 칸 — {LONG_CELL}자 초과 {len(_long)}칸 · 최장 {max(_lens, default=0)}자 "
                   f"(상한 {LONG_MAX_N}칸 · {LONG_MAX_LEN}자). 표를 문단 저장소로 키우지 않는다")
    elif len(_long) < LONG_MAX_N or max(_lens, default=0) < LONG_MAX_LEN - 50:
        bad.append(f"  긴 칸 — 줄었다({len(_long)}칸 · 최장 {max(_lens, default=0)}자). "
                   "tools/docx_check.py 의 LONG_MAX_N · LONG_MAX_LEN 을 내린다")
    return bad


#: 긴 칸 래칫 — 2026-09-22 실측 6칸 · 최장 1,343자(표0). 최장은 위로 37자 여유를 둔다(문구 한 줄 손질)
LONG_CELL = 250
LONG_MAX_N = 6
LONG_MAX_LEN = 1380


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    docs = sorted((ROOT / "docs").glob("*.docx"))
    if not docs:
        print("docs/ 에 docx 가 없다 — 건너뛴다")
        return 0

    allbad: list[str] = []
    for p in docs:
        allbad += audit(p)

    if a.json:
        print(json.dumps({"stale": len(allbad)}, ensure_ascii=False))

    if not allbad:
        print(f"기획서 OK — 산출물과 일치 (구간 {_canon().get('구간 수'):,})")
        return 0

    print(f"기획서가 산출물과 어긋난다. {len(allbad)}건\n")
    print("\n".join(allbad[:40]))
    if len(allbad) > 40:
        print(f"  … 외 {len(allbad) - 40}건")
    print("\n  정본은 data/golden/segments.fingerprint.json 이다.")
    print("  문서와 어긋나면 산출물이 옳다(MASTER §0-3).")
    print("  기획서는 넷 중 유일하게 외부가 읽는다 — 어긋나면 비용이 가장 크다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

