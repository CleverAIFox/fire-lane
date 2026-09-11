#!/usr/bin/env python3
"""
b3_const.py — **인코딩 후보 4벌 · TEXT_EXT 3벌을 한 파일로 모은다.**

    uv run python tools/batches/b3_const.py            무엇을 할지만
    uv run python tools/batches/b3_const.py --apply    실제로

★ **합치지 않는다. 모으기만 한다.** 이것이 이 배치의 전부다.

  감사는 이 일곱 줄을 "사본"으로 셌다. 열어보니 **값도 순서도 다르다.**

      인코딩 후보
        encoding.CANDIDATES     utf-8-sig · utf-8 · cp949 · utf-16 · cp437
        ingest._read_csv        utf-8-sig · utf-8 · cp949 · euc-kr
        inventory.CSV_ENCODINGS utf-8-sig · cp949 · utf-8        ← 순서 다름
        contract (보고용)        cp949 · utf-8-sig · utf-8 · utf-16  ← cp949 먼저

      TEXT_EXT
        encoding.TEXT_EXT       점 없음 · 자료 형식 9종(dbf · yaml · xml 포함)
        prep.TEXT_EXT           점 있음 · 6종
        encoding_check.TEXT_EXT 점 있음 · 저장소 소스 14종(.py · .sh · .md …)

  **순서를 바꾸면 판정이 바뀐다.** cp949 를 먼저 시도하면 UTF-8 파일도
  cp949 로 "성공적으로" 읽히고 모지바케가 된다. encoding.py 머리말이
  그것을 이미 적어놨다 — "판별 순서가 곧 신뢰도 순서다."
  그러니 넷을 하나로 합치는 것은 사본 제거(B3·불변)가 아니라
  **판정 변경(B4·재잠금)** 이다.

  TEXT_EXT 셋도 같다. 자료 형식 판별 · 전처리 대상 · 저장소 소스 검사는
  서로 다른 질문이다. 같은 이름을 쓴 것이 잘못이지 값이 다른 것이 잘못이 아니다.

★ 그래서 여기서 하는 일은 하나다 — **값을 한 글자도 바꾸지 않고**
  전부 `seg` 가 아닌 `firelane/encoding.py` 로 올리고, 쓰임이 드러나는
  이름을 준다. 소비자는 import 로 바꾼다.

      얻는 것 ⒜ 정본 파일이 하나가 된다. 다음에 누가 후보를 더할 때
                 네 곳을 뒤지지 않는다
             ⒝ **차이가 한 화면에 보인다.** 지금은 네 파일에 흩어져 있어
                 누구도 순서가 다르다는 것을 모른다
             ⒞ B4 에서 사람이 "합칠 것인가"를 근거를 놓고 정할 수 있다

  ★ 이름을 안 바꾸고 그냥 합쳤으면 이 배치가 조용히 판정을 바꿨을 것이다.
    원칙 ⑥ — 모르는 건 모른다고 적는다. 여기서는 "다른 건 다르다고 적는다".
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

ANCHOR = 'TEXT_EXT = {"csv", "txt", "tsv", "json", "yaml", "xml", "prj", "cpg", "dbf"}\n'

BLOCK = '''TEXT_EXT = {"csv", "txt", "tsv", "json", "yaml", "xml", "prj", "cpg", "dbf"}

# ══ 흩어져 있던 후보·확장자 목록의 정본 ═══════════════════════════
# ★ 2026-09-11 (B3). 네 파일에 있던 것을 **값과 순서를 그대로 둔 채**
#   여기로 올렸다. 합치지 않았다 — 아래 셋은 서로 다르고, 다른 이유가 있다.
#
#   합치는 판단은 B4 다. 순서를 바꾸면 판별 결과가 바뀌기 때문이다
#   (cp949 를 먼저 보면 UTF-8 도 "읽히고" 모지바케가 된다).
#   지금은 차이를 한 화면에 모아 사람이 볼 수 있게만 한다.

# ingest 가 CSV 를 **읽을 때**. sources.yaml 의 선언을 먼저 쓰고 이걸 잇는다.
#   euc-kr 이 있고 utf-16 · cp437 이 없다 — 공공데이터포털 CSV 만 상대한다.
CANDIDATES_CSV_READ = ("utf-8-sig", "utf-8", "cp949", "euc-kr")

# inventory 가 스키마 표본을 **훑을 때**.
#   ★ cp949 가 utf-8 보다 앞이다. CANDIDATES 와 순서가 다르다.
#     의도인지 사고인지 확인되지 않았다. B4 항목.
CANDIDATES_CSV_SCAN = ("utf-8-sig", "cp949", "utf-8")

# contract 가 "선언과 다르다" 를 **보고할 때** 실제 인코딩 후보.
#   ★ cp949 가 맨 앞이다. 판별이 아니라 열거라 순서가 화면 출력 순서다.
CANDIDATES_REPORT = ("cp949", "utf-8-sig", "utf-8", "utf-16")

# prep 이 바이트를 정규화할 대상. 점을 포함한다(`Path.suffix` 와 대조).
#   zip · tif · shp 는 바이트를 건드릴 수 없어 빠져 있다.
TEXT_EXT_PREP = {".csv", ".txt", ".tsv", ".json", ".prj", ".cpg"}

# encoding_check 가 검사할 **저장소 소스**. 자료 형식이 아니라 우리 코드다.
TEXT_EXT_SOURCE = {".py", ".sh", ".md", ".yml", ".yaml", ".csv", ".txt",
                   ".html", ".css", ".js", ".json", ".geojson", ".cfg", ".toml"}
# ══════════════════════════════════════════════════════════════════
'''

EDITS: list[tuple[str, str, str, str]] = [
    # ── 정본에 모은다 ──────────────────────────────────────────
    ("src/firelane/encoding.py", ANCHOR, BLOCK,
     "흩어져 있던 후보·확장자 목록의 정본"),

    # ── ingest ────────────────────────────────────────────────
    ("src/firelane/ingest.py",
     '    cands += ["utf-8-sig", "utf-8", "cp949", "euc-kr"]\n',
     "    cands += list(CANDIDATES_CSV_READ)\n",
     "cands += list(CANDIDATES_CSV_READ)"),

    # ── inventory ─────────────────────────────────────────────
    ("src/firelane/inventory.py",
     'CSV_ENCODINGS = ("utf-8-sig", "cp949", "utf-8")\n',
     "CSV_ENCODINGS = CANDIDATES_CSV_SCAN   # 정본 firelane/encoding.py\n",
     "CSV_ENCODINGS = CANDIDATES_CSV_SCAN"),

    # ── contract ──────────────────────────────────────────────
    ("src/firelane/contract.py",
     '                got = [x for x in ("cp949", "utf-8-sig", "utf-8", "utf-16")\n'
     "                       if decode_ok(p, x)]\n",
     "                got = [x for x in CANDIDATES_REPORT if decode_ok(p, x)]\n",
     "got = [x for x in CANDIDATES_REPORT if decode_ok(p, x)]"),

    # ── prep ──────────────────────────────────────────────────
    ("src/firelane/prep.py",
     '# 텍스트만 정규화한다. zip · tif · shp 는 바이트를 건드릴 수 없다.\n'
     'TEXT_EXT = {".csv", ".txt", ".tsv", ".json", ".prj", ".cpg"}\n',
     "# 텍스트만 정규화한다. zip · tif · shp 는 바이트를 건드릴 수 없다.\n"
     "# 정본은 firelane/encoding.py. 이름이 쓰임을 말한다 — 여기 것은 '전처리 대상'이고\n"
     "# encoding.TEXT_EXT(자료 형식)와 값이 다르다. 같은 이름을 쓰던 것이 잘못이었다.\n"
     "TEXT_EXT = TEXT_EXT_PREP\n",
     "TEXT_EXT = TEXT_EXT_PREP"),

    # ── encoding_check ────────────────────────────────────────
    ("tools/encoding_check.py",
     '# 검사 대상 확장자\n'
     'TEXT_EXT = {".py", ".sh", ".md", ".yml", ".yaml", ".csv", ".txt",\n'
     '            ".html", ".css", ".js", ".json", ".geojson", ".cfg", ".toml"}\n',
     "# 검사 대상 확장자. 정본은 firelane/encoding.py 의 TEXT_EXT_SOURCE 다.\n"
     "# ★ 자료 형식이 아니라 **저장소 소스**다. encoding.TEXT_EXT 와 다른 것이 정상이다.\n"
     "from firelane.encoding import TEXT_EXT_SOURCE as TEXT_EXT\n",
     "from firelane.encoding import TEXT_EXT_SOURCE as TEXT_EXT"),
]

IMPORTS: list[tuple[str, str, str]] = [
    ("src/firelane/ingest.py", "CANDIDATES_CSV_READ", "from firelane.encoding import CANDIDATES_CSV_READ\n"),
    ("src/firelane/inventory.py", "CANDIDATES_CSV_SCAN", "from firelane.encoding import CANDIDATES_CSV_SCAN\n"),
    ("src/firelane/contract.py", "CANDIDATES_REPORT", "from firelane.encoding import CANDIDATES_REPORT\n"),
    ("src/firelane/prep.py", "TEXT_EXT_PREP", "from firelane.encoding import TEXT_EXT_PREP\n"),
]


def _names(src: str) -> set[str]:
    out: set[str] = set()
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return out


def _insert_import(text: str, line: str) -> str:
    """`from firelane...` 그룹 안 **알파벳 자리**에 끼운다.

    ★ 처음엔 "머리 import 블록 끝" 에 붙였다. 두 번 틀렸다 —
      ⒜ `inventory.py` 는 196줄에 `# noqa: E402` 늦은 import 가 있어서
         "마지막 최상위 import" 로 잡으면 52줄의 사용처보다 아래에 꽂힌다.
         NameError 로 터졌다.
      ⒝ 끝에 붙이면 isort 순서가 깨져 `ruff I001` 이 운다. verify.sh 의
         ruff 단계가 통과 21 → 20 으로 떨어졌다. **검사가 잡았다.**

    그래서 first-party 그룹만 보고 그 안에서 정렬 자리를 찾는다.
    그룹이 없으면 머리 블록 끝(첫 비-import 문장 앞)에 붙인다.
    """
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    head_end, group = 0, []
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            head_end = max(head_end, n.end_lineno or n.lineno)
            mod = getattr(n, "module", None) or ""
            if isinstance(n, ast.ImportFrom) and mod.split(".")[0] == "firelane":
                group.append((n.lineno, lines[n.lineno - 1]))
        elif not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)):
            break
    if group:
        at = next((ln for ln, src in group if src > line), None)
        lines.insert((at - 1) if at else group[-1][0], line)
    else:
        lines.insert(head_end, line)
    return "".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    changed = skipped = 0
    by_file: dict[str, list[tuple[str, str, str]]] = {}
    for rel, old, new, done in EDITS:
        by_file.setdefault(rel, []).append((old, new, done))

    for rel, pairs in by_file.items():
        p = ROOT / rel
        before = p.read_text(encoding="utf-8")
        text = before
        for old, new, done in pairs:
            if done in text:
                skipped += 1
                continue
            if text.count(old) != 1:
                sys.exit(f"★ {rel} — 대상이 {text.count(old)}곳이다. 멈춘다.\n{old!r}")
            text = text.replace(old, new)
            changed += 1

        for irel, need, line in IMPORTS:
            if irel != rel or need not in text or line.strip() in text:
                continue
            text = _insert_import(text, line)

        if text == before:
            print(f"  = {rel}  이미 적용됨")
            continue
        lost = _names(before) - _names(text)
        if lost:
            sys.exit(f"★ {rel} — 최상위 이름이 사라진다: {sorted(lost)}. 되돌린다.")
        try:
            ast.parse(text)
        except SyntaxError as e:
            sys.exit(f"★ {rel} — 편집 결과가 파싱 안 된다: {e}")
        print(f"  {'✓' if a.apply else '·'} {rel}")
        if a.apply:
            p.write_text(text, encoding="utf-8")

    print(f"\n변경 {changed} · 건너뜀 {skipped}"
          + ("" if a.apply else "   ★ dry-run. --apply 를 붙일 것"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
