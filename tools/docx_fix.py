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
GOLDEN = ROOT / "data/golden/segments.fingerprint.json"


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

