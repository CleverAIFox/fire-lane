#!/usr/bin/env python3
"""
docx_fix.py — 기획서의 낡은 숫자·용어를 산출물 기준으로 고친다.

── 왜 별도 도구인가 ────────────────────────────────────────────
`docx_check.py` 는 어긋남을 **찾을** 뿐이다. docx 는 텍스트가 run 단위로
쪼개져 있어 손으로 고치면 반드시 빠뜨린다 — 같은 문장이 표 안에 다시
나오는 자리가 여섯 곳이었다.

★ R9(문자열 치환 패처 금지)의 예외가 아니다. R9 가 막는 것은 **소스
  코드**를 스크립트로 고치는 것이다. docx 는 git diff 가 안 되는 바이너리라
  사람이 diff 로 검토할 수 없고, 그래서 도구가 필요한 반대 경우다.

IN    docs/*.docx · data/golden/segments.fingerprint.json
OUT   docs/*.docx (제자리 수정)
PARAM --write 없이는 아무것도 쓰지 않는다
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


def rules() -> list[tuple[str, str, str]]:
    """(정규식, 치환, 사유)."""
    g = json.loads(GOLDEN.read_text(encoding="utf-8"))["L1"]
    v = g["verdict"]
    n = g["n"]
    out = [
        (r"1,?102\s*구간", f"{n:,}구간", "노드접합·산출단위 병합 + 수치지형도 교체"),
        (r"src/etl/pipeline\.py", "src/firelane/pipeline.py", "패키지화 2026-08-21"),
        (r"src/etl\b", "src/firelane", "패키지화 2026-08-21"),
        (r"requirements-etl\.txt[^/]*/\s*", "", "삭제됨. uv.lock 이 정본"),
    ]
    for label, key in (("통행 불가", "blocked"), ("통행 가능", "clear"),
                       ("판정 보류", "needs_cv"), ("영상판정 불가", "unknown")):
        out.append((rf"({label})\s*\d{{2,4}}", rf"\g<1> {v[key]}", "golden 기준"))

    # ── PostGIS 미채택 (docker-compose.yml 주석이 근거) ──
    # segments.geojson 996KB · 1,101구간이라 PostGIS 를 쓸 규모가 아니고,
    # 파이프라인이 285초에 결정론적으로 재생성되므로 DB 의 주 가치인
    # 상태 보존이 필요 없다. DB 가 필요해지는 시점은 동적 계층뿐이며
    # 그때도 seg_uid → status 한 테이블이면 된다(PLAN §2-2).
    out += [
        (r"PostgreSQL\s*\+\s*PostGIS\s*정적·동적\s*계층\s*분리\s*적재",
         "정적 계층 파일(GeoJSON) + 동적 상태 테이블 분리", "PostGIS 미채택"),
        (r"FastAPI,\s*PostGIS,\s*프론트엔드를",
         "FastAPI, 상태 DB, 프론트엔드를", "PostGIS 미채택"),
        (r"PostGIS\s*적재", "동적 상태 테이블 적재", "PostGIS 미채택"),
        (r"PostgreSQL\s*\+\s*PostGIS", "동적 상태 테이블", "PostGIS 미채택"),
        (r"(?<![\w])PostGIS(?![\w])", "상태 DB", "PostGIS 미채택"),
    ]
    # ── 소방용수 (PLAN §12-7 · MASTER §3-12) ──
    # 기획서는 소화전과 소방용수시설을 한 숫자로 뭉쳐 588 이라 적었다.
    # 둘은 다른 집계다 — 소화전 589 는 소방용수시설 654 의 부분집합이다.
    # 공개율 논거는 소방용수시설 전체가 분모여야 맞다(MASTER §16-3).
    out += [
        (r"소방용수\s*588개\s*\(\s*지상식\s*431\s*[+·]\s*지하식\s*157\s*\)",
         "소화전 589개(지상식 418 · 지하식 171) · 소방용수시설 총계 654개",
         "MASTER §3-12"),
        (r"588개\s*\(\s*지상식\s*431\s*[·+]\s*지하식\s*157\s*\)",
         "654개(소화전 589 = 지상식 418 · 지하식 171)", "MASTER §3-12"),
        (r"588개\s*중\s*31개", "654개 중 31개", "분모는 소방용수시설 총계"),
        (r"5%\s*\(\s*588개\s*중\s*31개\s*\)", "5%(654개 중 31개)", "MASTER §3-12"),
        (r"(?<![\d,])588개", "654개", "MASTER §3-12"),
    ]

    # ── 차량 제원 (PLAN §12-2 · MASTER §3-13) ──
    # 규격은 확보됐다. 남은 추정은 축거·최소회전반경 둘뿐이며 그것이
    # `wheelbase_verified: false` 다. "제원 미확보" 로 뭉뚱그리면 이미 한
    # 근거를 안 한 것으로 적는 셈이고, 외부 독자가 그대로 읽는다.
    _SPEC = ("소방청 「소방장비 기본규격」 소방펌프차 KFS-1-0073-2025-00 §3.3"
             "(2025-12-24 고시)")
    out += [
        (r"정확한 표준 제원은 소방청 소방차량 제작규격 및 소방서 문의로 "
         r"확보 예정이며,\s*그 이전까지는 잠정값을 사용한다\.",
         f"표준 제원은 {_SPEC}으로 확보했다. 중형 기준 전폭 2.5m 이하이며 "
         "통과 하한 3.0m 는 여기에 미러·조향 여유 0.5m 를 더한 값이다. "
         "다만 축거와 최소회전반경은 공식 규격에 없어 추정값으로 남으며, "
         "내륜차 계산에 그 둘이 필요하다.", "MASTER §3-13"),
        (r"현재 세 값 모두 잠정이며 확정 경로가 각각 다르다\.",
         "전폭은 KFS-1-0073-2025-00 §3.3 으로 확정했고, 축거·최소회전반경은 "
         "공식 규격에 없어 추정으로 남는다. 확정 경로가 각각 다르다.",
         "MASTER §3-13"),
        (r"차량 제원 미확보", "축거·회전반경 미확보", "규격은 확보됨"),
        (r"판정 통과선의 근거가 잠정값에 머무름",
         "내륜차 계산의 근거가 추정값에 머무름", "MASTER §3-13"),
        (r"소방청 소방차량 제작규격 확보 및 동부소방서 현장대응과 문의 병행",
         f"{_SPEC} 확보 완료. 축거·회전반경은 동부소방서 인터뷰로 확정",
         "MASTER §3-13"),
        (r"제원 확보 시 재검증한다\.",
         "축거·회전반경 확보 시 내륜차를 재산출한다.", "MASTER §3-13"),
    ]

    return out


def fix(p: Path, write: bool) -> int:
    import docx
    d = docx.Document(str(p))
    R = rules()
    n = 0

    def do(par) -> int:
        """run 단위로 먼저, 안 되면 문단 단위로.

        ★ docx 는 텍스트가 run 으로 임의 분할된다. `PostGIS 적재` 가
          `PostG` + `IS 적재` 두 run 에 걸쳐 있으면 run 단위 치환이
          조용히 통과한다 — 이 저장소가 계속 겪은 조용한 실패다.
          그래서 문단 전체로 한 번 더 본다.
        """
        c = 0
        for run in par.runs:
            t0 = run.text
            t = t0
            for rx, rep, _ in R:
                t = re.sub(rx, rep, t)
            if t != t0:
                run.text = t
                c += 1

        # run 경계를 넘는 구절
        whole = par.text
        fixed = whole
        for rx, rep, _ in R:
            fixed = re.sub(rx, rep, fixed)
        if fixed != whole and par.runs:
            # ★ 첫 run 에 몰아넣으면 그 문단의 부분 서식이 사라진다.
            #   숫자·용어 교정이 서식보다 중요하므로 감수하되 세어서 알린다.
            par.runs[0].text = fixed
            for r in par.runs[1:]:
                r.text = ""
            c += 1
        return c

    for par in d.paragraphs:
        n += do(par)
    for t in d.tables:
        for r in t.rows:
            for cell in r.cells:
                for par in cell.paragraphs:
                    n += do(par)

    if write and n:
        d.save(str(p))
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    total = 0
    for p in sorted((ROOT / "docs").glob("*.docx")):
        c = fix(p, a.write)
        total += c
        print(f"  {p.name}  run {c}개 {'수정' if a.write else '수정 예정'}")
    if not a.write:
        print("\n아무것도 안 썼다. 적용하려면 --write")
        print("★ docx 는 git diff 가 안 된다. 적용 후 워드로 눈으로 확인할 것.")
    else:
        print(f"\n{total}개 run 수정. tools/docx_check.py 로 대조해라.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

