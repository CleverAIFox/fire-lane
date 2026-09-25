#!/usr/bin/env python3
"""
dms.py — **이미 쓰인 것을 지금 규약으로 전수 검사한다.**

    uv run python tools/dms.py scan          분모 산출 · data/dms/DMS.json
    uv run python tools/dms.py verify        기재된 강제자가 실재하는가
    uv run python tools/dms.py seal          ★ 강제자 전수 실행 → 통과해야 봉인
    uv run python tools/dms.py seal --log /tmp/verify.log   ★ 방금 돌린 것을 읽는다
    uv run python tools/dms.py seal --quick  pytest 만 (빠르게)
    uv run python tools/dms.py seal --red golden   아는 빨강을 적고 봉인
    uv run python tools/dms.py delta         ★ 봉인 뒤 바뀐 절만. 전수가 아니다
    uv run python tools/dms.py propose 1     회차 파일 — 후보까지 뽑아준다
    uv run python tools/dms.py fill round-1.txt --apply   고른 것을 문서에 적는다
    uv run python tools/dms.py round         후보 없이 목록만
    uv run python tools/dms.py mark ID …     읽은 절을 북마크에 적는다
    uv run python tools/dms.py --selftest    ★ 프로브가 살아 있나

── 왜 CDC 앞인가 ──────────────────────────────────────────────
지금까지 만든 강제자는 전부 **증분(CDC)** 이다. 만들 때 이미 통과하는
상태로 맞춰놨으므로 **이미 어긴 것은 안 센다.** 증거 —
`DECISIONS §123~143` 스물한 절이 없는 검사를 강제자로 들고 있었는데
어떤 검사도 안 잡았다. 사람이 눈으로 봤다.

소급이 끝나야 기준선이 서고, 기준선이 서야 증분이 의미를 갖는다.

── 이 도구가 잡은 것 — 만들면서 ───────────────────────────────
★ `test_doc_style.py::test_recent_decisions_name_their_enforcer` 가
  `if "강제자" not in text` **부분문자열 검사**다. 그래서

      "인코딩만 **강제자가 없었다.**"        ← 산문. 통과한다
      "규칙은 있고 강제자가 없었다."          ← 산문. 통과한다

  DECISIONS 에서 23곳이 이 형태다. 칸을 안 적어도 초록이다.
  원칙 ② 그 자체 — *잘못된 것을 정확히 지키게 만드는 검사* 이고,
  검사가 있다는 사실이 규약을 검증한 것처럼 보이게 했다.
  이 도구는 **줄머리 칸**만 센다.

★ 표기 정본이 둘이다. 규약(DECISIONS 서술 규약 표)은

      강제자 없음 — 사유: …

  인데 실물은 `강제자 없음`(9) · `강제자  없다`(7) 로 갈렸다.
  `없다` 를 세는 grep 은 9건을 놓친다. 규약을 정본으로 삼고
  `scan` 이 갈린 것을 `표기` 로 따로 센다.

── 절의 정의 ──────────────────────────────────────────────────
    절 = 코드펜스 밖의 `##` · `###`      3축 + README
    칸 = **줄머리**의 `강제자`            산문 언급은 칸이 아니다

    wired   칸이 검사·도구를 지목한다
    none    칸이 "없음" 을 선언한다      ★ 적는 순간 세어진다
    blank   칸이 없다                     ← **분모는 이것이다**

★ 분모를 이 도구가 낸 값으로 고정한다. 2026-09-13 수기 실측 417 은
  프로브가 없어 재현되지 않는다. 이 도구가 420 을 낸다면 420 이 정본이고
  417→420 은 전이로 기록한다. **재현되지 않는 숫자는 분모가 아니다.**

IN    docs/MASTER.md · docs/DECISIONS.md · docs/PLAN.md · README.md
OUT   data/dms/DMS.json · data/dms/BOOKMARK.json
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

from firelane.generated import prefixes  # ★ 생성물 경로의 정본(W3-13)
from firelane.hashing import sha256  # ★ 파일 해시는 한 곳에서만 잰다(firelane/hashing.py)

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "dms"
DOCS = ("docs/MASTER.md", "docs/DECISIONS.md", "docs/PLAN.md", "README.md")

# 줄머리 칸. 뒤에 한글 조사가 붙으면 산문이다 — `강제자가 없었다`
# ★ 2026-09-17 (DECISIONS §174-4 · §180). 뒤에 `(` 가 붙어도 산문이다 — `강제자(`test_x`)가 단언해` 는
#   괄호 속 이름을 설명하는 문장이지 칸이 아니다. 이 줄이 칸으로 읽혀 지운 테스트를 가리키는 "죽은 참조 1" 이
#   봉인마다 찍혔다(§171-1).
FIELD = re.compile(r"^\s{0,6}(?:[-*>]\s*)?\*{0,2}강제자\*{0,2}(?![가-힣(])")
HEAD = re.compile(r"^(#{2,3}) (.+)$")
FENCE = re.compile(r"^\s*(```|~~~)")

# 규약 정본. DECISIONS 서술 규약 표가 든 형태다
CANON_NONE = "강제자 없음 — 사유:"
# ★ 2026-09-24 (DECISIONS §228). **줄머리에 있을 때만** 「없음」 선언이다.
#   종전에는 `없음|없다` 를 칸 **아무 데서나** 찾았다. 그래서 강제자를 제대로
#   지목하면서 「진입점 수는 실측값이라 대조 도구가 없다」처럼 범위를 덧붙인 칸이
#   **`none` 으로 세어졌다.** 실측 8건 — 그중 넷(`DECISIONS/162-1` · `199-1` ·
#   `212` · `215`)은 2026-09-17 부터 그 상태였다.
#   분모를 세는 도구가 분모를 틀리게 세고 있었고, 방향은 **wired 를 줄이는 쪽**이라
#   「강제자가 있는 절」이 실제보다 적어 보였다. 좁아지는 쪽으로 망가지는 프로브다.
NONE_ANY = re.compile(r"^(?:없음|없다)")

# ── 정밀 프로브 — 1차 소급 192건 중 174가 오탐이었다 ──────────
EXAMPLE_NAMES = {"xxx", "yyy", "zzz", "foo", "bar", "baz", "name", "test_xxx",
                 "test_yyy", "tests/test_xxx.py", "tools/xxx.py"}
DELETED = re.compile(r"\(삭제됨\)")
DATED_SCRIPT = re.compile(r"_20\d{6}")
REF = re.compile(r"`([^`]+)`")


def sections(rel: str) -> list[dict]:
    """코드펜스 밖의 `##` · `###` 를 절로 센다."""
    lines = (ROOT / rel).read_text(encoding="utf-8").split("\n")
    out: list[dict] = []
    cur: dict | None = None
    fence = False
    for i, line in enumerate(lines, 1):
        if FENCE.match(line):
            fence = not fence
            if cur is not None:
                cur["body"].append((i, line))
            continue
        m = HEAD.match(line) if not fence else None
        if m:
            cur = {"doc": rel, "line": i, "depth": len(m.group(1)),
                   "title": m.group(2).strip(), "body": [], "at": i}
            out.append(cur)
        elif cur is not None:
            cur["body"].append((i, line))
    _assign_ids(Path(rel).stem, out)
    return out


# ★ 절 ID 는 **제목 경로**다 — `MASTER/12-8` · `DECISIONS/63/1` · `README/실행`.
#   2026-09-22 (PLAN §13 W3-5 닫힘 · DECISIONS §217-5). 종전엔 문서 안 **순번**
#   (`MASTER-082`)이라 중간에 절 하나를 끼우면 뒤 70절이 전부 「변경」으로 떴다.
#   번호가 있으면 번호, 없으면 제목을 잘라 쓴다. `###` 는 번호가 부모 번호로 시작하지
#   않으면 부모 아래에 둔다(DECISIONS 의 `### 1.` 이 수십 번 되풀이된다).
#   겹치면 `~2` 를 붙인다 — 지금 네 문서에서 0건이고 `tests/test_dms.py` 가 본다.
SEC_NUM = re.compile(r"^§?\s*(\d+[0-9A-Za-z-]*?)\.?(?:\s|$)")


def _slug(title: str) -> str:
    t = re.sub(r"[`*★()\[\]「」'\",·:—./]", " ", title)
    return "_".join(t.split())[:40]


def _assign_ids(stem: str, secs: list[dict]) -> None:
    parent: str | None = None
    seen: dict[str, int] = {}
    for s in secs:
        m = SEC_NUM.match(s["title"])
        own = m.group(1) if m else _slug(s["title"])
        if s["depth"] == 2 or parent is None:
            key = own
            if s["depth"] == 2:
                parent = own
        else:
            key = own if (m and own.startswith(parent + "-")) else f"{parent}/{own}"
        seen[key] = seen.get(key, 0) + 1
        s["id"] = f"{stem}/{key}" + (f"~{seen[key]}" if seen[key] > 1 else "")


#: 칸 블록이 끝나는 줄. 제목 · 표 · 별표 문단 · 펜스 · 빈 줄에서 끊는다.
FIELD_END = re.compile(r"^(#|---|\||★|```|\s*$)")


def classify(sec: dict) -> tuple[str, str, int]:
    """(상태, 칸 **전문**, 칸 줄번호). 코드펜스 안의 줄은 칸으로 안 센다.

    ★ 2026-09-24 (DECISIONS §243). 종전에는 절마다 **첫 칸에서 멈췄다.**
      한 절에 강제자 칸이 둘 이상인 곳이 있고(PLAN §0-2 는 셋), 둘째부터는
      이 도구 눈에 없었다. 그래서 `PLAN:98` 이 **개명된 시험**
      (`test_plan_has_no_closed_items` → `test_plan_status_vocabulary_is_closed`)
      을 가리킨 채 「죽은 강제자 참조 0건」이 찍히고 있었다. 검사를 세워 두고
      그 검사가 못 보는 자리에 결함이 살았다.

      상태는 칸 **전부**로 정한다 — 하나라도 배선이면 배선이다.

    ★ 2026-09-24 (DECISIONS §241). 종전에는 **첫 줄만** 칸으로 들었다. 칸은
      113곳에서 여러 줄에 걸친다 — 이어지는 줄에 적힌 강제자 이름도, 물림
      선언도 이 도구 눈에 안 보였다. 그래서 「하위 둘이 이 칸을 물려받는다」를
      이어지는 줄에 적으면 **적어도 안 적은 것으로 세어졌다.**

      물음이 「이 절에 칸이 있는가」이므로 답은 칸 **전체**여야 한다.
      첫 줄만 보는 것은 범위가 이름보다 좁은 자리다(§226).
    """
    fence = False
    body = sec["body"]
    blocks: list[str] = []
    wired = False
    at = sec["line"]
    for i, (n, line) in enumerate(body):
        if FENCE.match(line):
            fence = not fence
            continue
        if fence or not FIELD.match(line):
            continue
        block = [line.strip()]
        for _, nxt in body[i + 1:]:
            if FIELD_END.match(nxt):
                break
            block.append(nxt.strip())
        if not blocks:
            at = n
        blocks.append(" ".join(block))
        wired |= not NONE_ANY.search(FIELD.sub("", line).strip())
    if not blocks:
        return "blank", "", sec["line"]
    return ("wired" if wired else "none"), " ".join(blocks), at


def scan() -> dict:
    """★ `###` 는 부모 `##` 의 칸을 물려받는다 — `inherit`.

    DECISIONS §91 이 그 형태다. 칸이 `§91-3` 안에 있고 `§91` 본문에는
    없다. 절마다 한 줄을 요구하면 사람이 읽을 것이 부풀고, 부모 칸이
    실제로 그 하위 논점까지 덮는 경우가 대부분이다.
    분모는 **자기 칸도 부모 칸도 없는 것**으로 센다.
    """
    rows = []
    for rel in DOCS:
        parent = "blank"
        for sec in sections(rel):
            state, raw, at = classify(sec)
            if sec["depth"] == 2:
                parent = state
            elif state == "blank" and parent != "blank":
                state = "inherit"
            rows.append({"id": sec["id"], "doc": rel, "line": sec["line"],
                         "at": at, "depth": sec["depth"], "title": sec["title"],
                         "state": state, "field": raw})
    return {"rows": rows}


SKIP_DIR = {".git", ".venv", "node_modules", "__pycache__", "data", "uv.lock"}
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".mjs", ".sh"}
# 이름 꼴이 아닌 것 — 셸 한 줄 · 설정값 인용 · 문장
NOT_A_NAME = re.compile(r"[ =]|(?<!:):(?!:)")   # `::` 는 pytest 표기다


def _corpus() -> tuple[str, set[str]]:
    """저장소 **전문** 과 파일명 집합.

    ★ 선언(`def` · `const` · 대문자 상수)만 모으면 안 된다. 2026-09-13 에
      그렇게 만들었더니 8건이 나왔고 **8건 전부 오탐**이었다 —

        index() · can_turn()        괄호가 붙어 있었다
        turn_radius_verified        산출물 필드명. 선언이 아니다
        contract-strict · data-fill CI job id · HTML data 속성. 하이픈이다
        width_samples.csv           `data/` 밑이라 건너뛰었다

      강제자 칸이 지목할 수 있는 것의 종류를 미리 못 센다. 그래서
      **종류를 세지 않고 전문에 있는지만 본다.** 이름이 저장소 어디에도
      없으면 죽은 것이고, 어디엔가 있으면 사람이 볼 값어치가 있다.
    """
    buf: list[str] = []
    files: set[str] = set()
    for p in ROOT.rglob("*"):
        if not p.is_file() or SKIP_DIR & set(p.relative_to(ROOT).parts):
            continue
        files |= {p.name, p.stem, str(p.relative_to(ROOT))}
        if p.suffix in CODE_EXT or p.suffix in {".yml", ".yaml", ".html", ".toml"}:
            try:
                buf.append(p.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, OSError):
                continue
    return "\n".join(buf), files


def _missing_member(head: str, member: str) -> str:
    """`파일::이름` 에서 그 이름이 파일에 없으면 사유를, 있으면 빈 문자열."""
    # ★ 첨자는 떼고 본다 — `EXPECT["part"]` 가 지목하는 것은 `EXPECT` 다.
    member = re.sub(r"\[.*$", "", member.strip().rstrip("()").strip("`")).strip()
    if not member or NOT_A_NAME.search(member):
        return ""
    cands = [p for p in (ROOT / "x").parent.rglob(Path(head).name)
             if p.is_file() and not any(s in p.parts for s in SKIP_DIR)]
    exact = [p for p in cands if p.as_posix().endswith(head)]
    for p in (exact or cands):
        if member in _members(p):
            return ""
    if not (exact or cands):
        return ""                                   # 파일을 못 찾으면 ⑥ 이 본다
    return f"`{member}` 가 {head} 에 없다"


def _members(path: Path) -> set[str]:
    """그 파일이 **선언한 이름들.** `.py` 는 AST, 나머지는 문자열로 본다."""
    txt = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix != ".py":
        return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", txt))
    try:
        tree = ast.parse(txt)
    except SyntaxError:
        return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", txt))
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)          # `EXEMPT = {...}` 같은 모듈 상수도 칸이 지목한다
    return out


def verify(data: dict, corpus: tuple[str, set[str]] | None = None) -> list[str]:
    """칸이 지목한 이름이 실재하는가. **오탐 다섯을 먼저 뺀다.**"""
    text, files = corpus or _corpus()
    dead = []
    for r in data["rows"]:
        if r["state"] != "wired":
            continue
        if DELETED.search(r["title"]):          # ① 삭제된 것을 적은 절
            continue
        for raw in REF.findall(r["field"]):
            tok = raw.strip().rstrip("()")
            head = tok.split("::")[0]
            leaf, stem = Path(head).name, Path(head).stem
            if NOT_A_NAME.search(tok) or len(tok) < 3:   # ② 이름 꼴이 아니다
                continue
            if tok in EXAMPLE_NAMES or stem in EXAMPLE_NAMES:   # ③ 예시 이름
                continue
            if DATED_SCRIPT.search(tok):        # ④ 과거 서술 — 일회성 패처
                continue
            if {leaf, stem, head} & files:      # ⑤ 파일 참조
                # ★ 2026-09-24 (DECISIONS §229). **`::` 뒤를 안 봤다.**
                #   파일만 있으면 통과시켰으므로 `tests/test_guards.py::없는함수`
                #   가 초록이었다. 칸이 지목하는 것은 파일이 아니라 **검사**인데
                #   검사가 실재하는지는 한 번도 안 본 것이다 —
                #   「선언이 이름보다 넓다」 족(PLAN §13 · §226)의 문서판이다.
                if "::" in tok and (bad := _missing_member(head, tok.split("::", 1)[1])):
                    dead.append(f"  {r['doc']}:{r['at']}  {r['id']}  {raw}  ← {bad}")
                continue
            parts = [p for p in re.split(r"[:/]+", tok) if p]   # ⑥ 전문 대조
            if all(p in text or Path(p).stem in text for p in parts):
                continue
            dead.append(f"  {r['doc']}:{r['at']}  {r['id']}  {raw}")
    return dead


def notation(data: dict) -> list[str]:
    """`없음` 선언의 표기가 규약과 갈렸는가."""
    return [f"  {r['doc']}:{r['at']}  {r['id']}  {r['field'][:60]}"
            for r in data["rows"]
            if r["state"] == "none" and not r["field"].startswith(CANON_NONE)]


#: ★ 2026-09-24 (DECISIONS §241). 「하나」 가 빠져 있었다 — 하위 절이 **하나뿐인**
#:   부모는 아무리 적어도 「아무 말 없음」으로 세어졌다. 어휘는 아래 `WORD_N` 과
#:   같은 자리에서 만든다. 손으로 두 벌 적으면 또 갈린다(2족).
INHERIT_SAID = re.compile(r"물려받|하위\s*(?:절\s*)?(?:한|하나|둘|셋|넷|다섯|여섯|일곱|"
                          r"여덟|아홉|열하나|열둘|열|[0-9]+|절)")

#: 우리말 수. 선언은 사람이 읽는 줄이라 말로 적고, 기계는 여기서 수로 되짚는다.
WORD_N = {"한": 1, "하나": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5, "여섯": 6,
          "일곱": 7, "여덟": 8, "아홉": 9, "열": 10, "열하나": 11, "열둘": 12}
#: `하위 절 여덟이` · `하위 넷이` · `하위 3절` — 셋 다 인정한다.
#: ★ **절 번호는 수가 아니다.** `하위 절 187-1 ~ 187-3` 의 `187` 을 수로 읽으면
#:   그 줄이 「하위 187절」이 된다(2026-09-24 에 둘 실제로 났다). 숫자 꼴은
#:   뒤에 `절` 이 붙을 때만 수로 본다 — `하위 3절` 은 수, `하위 절 187-1` 은 번호다.
SAID_N = re.compile(
    r"하위\s*(?:절\s*)?(?:(열하나|열둘|열|한|하나|둘|셋|넷|다섯|여섯|일곱|여덟|아홉)"
    r"|([0-9]+)\s*절)(?![\d-])")


def _said_count(field: str) -> int | None:
    """부모 칸이 적은 **하위 절 수**. 수가 없으면 `None`."""
    m = SAID_N.search(field)
    if not m:
        return None
    return WORD_N.get(m.group(1)) if m.group(1) else int(m.group(2))


def inherit_counts(data: dict) -> list[str]:
    """부모가 적은 **하위 절 수**가 실제와 같은가.

    ★ 2026-09-24 (DECISIONS §241). 「하위 절이 이 칸을 물려받는다」는 한 줄은
      **검증된 적이 없는 주장**이다. 하위 절이 하나 늘어도 그 줄은 그대로 참인
      것처럼 보인다 — 새로 생긴 절은 아무도 안 본 채 물림으로 들어간다.

      수를 적게 하면 그 자리가 **세어진다.** 절이 늘거나 줄면 수가 어긋나고,
      어긋나면 사람이 **그 새 절을 실제로 본다.** 이 저장소가 래칫에 거는
      논리와 같다 — 선언을 세는 것으로 바꾼다.

    ★ 수를 안 적은 옛 표기(`물려받는다` 만)는 세지 않는다. 그것까지 한 번에
      강제하면 이 검사가 첫날부터 시끄러워지고, 시끄러운 검사는 꺼진다.
      **수를 적은 선언만** 그 수를 지킨다.
    """
    field = {r["id"]: r.get("field", "") for r in data["rows"]}
    kids: dict[str, int] = {}
    for r in data["rows"]:
        if r["state"] != "inherit":
            continue
        doc, _, tail = r["id"].partition("/")
        parent = f"{doc}/{tail.split('/')[0].split('-')[0]}"
        kids[parent] = kids.get(parent, 0) + 1
    at = {r["id"]: (r["doc"], r["at"]) for r in data["rows"]}
    bad = []
    for pid, n in sorted(kids.items()):
        said = _said_count(field.get(pid, ""))
        if said is None or said == n:
            continue
        doc, line = at.get(pid, ("?", 0))
        bad.append(f"  {doc}:{line}  {pid}  「하위 {said}」 라고 적었는데 실제 {n} 이다")
    return bad


def inherit_split(data: dict) -> tuple[list[str], list[str]]:
    """`inherit` 을 둘로 가른다 — 부모가 **덮는다고 적은 것** / 아무 말 없는 것.

    ★ 2026-09-24 (DECISIONS §230). `inherit` 은 「부모 칸이 하위 논점까지
      덮는다」는 **가정**이고 그 가정은 검증된 적이 없다. 실제로 `MASTER §12` 에
      칸을 적자 자식 열하나가 한 번에 분모에서 빠졌는데, 그 칸은 §12-8a(매체
      저장)나 §12-11(한글 파일명)을 안 덮었다.
      분모(blank)가 0 이 된 지금, **남은 의심은 전부 여기 있다.**
      세는 자리를 만들어 두면 다음 배치가 줄일 수 있다.
    """
    field = {r["id"]: r.get("field", "") for r in data["rows"]}
    said, mute = [], []
    for r in data["rows"]:
        if r["state"] != "inherit":
            continue
        # `DOC/12-8a` → `DOC/12` · `DOC/22/3` → `DOC/22` · `DOC/18/원칙_다섯` → `DOC/18`
        doc, _, tail = r["id"].partition("/")
        parent = f"{doc}/{tail.split('/')[0].split('-')[0]}"
        f = field.get(parent, "")
        (said if INHERIT_SAID.search(f) else mute).append(r["id"])
    return said, mute


def summary(data: dict) -> None:
    from collections import Counter
    per: dict[str, Counter] = {}
    for r in data["rows"]:
        per.setdefault(r["doc"], Counter())[r["state"]] += 1
    print(f"{'문서':22} {'절':>5} {'wired':>6} {'none':>6} {'inherit':>8} {'blank':>6}")
    tot = Counter()
    for rel in DOCS:
        c = per.get(rel, Counter())
        n = sum(c.values())
        print(f"{rel:22} {n:5} {c['wired']:6} {c['none']:6} "
              f"{c['inherit']:8} {c['blank']:6}")
        tot += c
    print(f"{'합계':20} {sum(tot.values()):5} {tot['wired']:6} "
          f"{tot['none']:6} {tot['inherit']:8} {tot['blank']:6}")
    print(f"\n★ 분모(blank) = {tot['blank']}")
    said, mute = inherit_split(data)
    print(f"★ 물림(inherit) = {len(said) + len(mute)}"
          f"   부모가 **덮는다고 적은 것** {len(said)}"
          f" · 아무 말 없는 것 {len(mute)}")


# ══ 후보 추천 — 사람은 고르기만 한다 ═════════════════════════
# ★ 350절을 맨눈으로 읽으면 회차가 열몇 번이다. 기계가 못 **판정**하는 것이지
#   못 **추천**하는 것이 아니다. 절이 든 백틱 토큰을 검사 본문과 대조해
#   순위를 매기고, 사람은 셋 중 하나를 고르거나 "없음" 을 적는다.
#   판정은 여전히 사람이 한다 — 바뀌는 것은 백지에서 시작하지 않는다는 것뿐.
TOK = re.compile(r"`([^`]+)`")
UNIT_TEST_W, UNIT_TOOL_W = 1.0, 0.55   # 규약상 강제자는 검사다. 도구는 재현이다


def _units() -> dict[str, tuple[str, float]]:
    """검사 함수 단위 · 도구 파일 단위. (본문, 가중치)"""
    out: dict[str, tuple[str, float]] = {}
    for p in sorted((ROOT / "tests").glob("*.py")):
        parts = re.split(r"(?m)^def (test_\w+)", p.read_text(encoding="utf-8"))
        for i in range(1, len(parts), 2):
            out[f"tests/{p.name}::{parts[i]}"] = (parts[i] + parts[i + 1],
                                                  UNIT_TEST_W)
    for p in sorted((ROOT / "tools").glob("*.py")) + sorted((ROOT / "tools").glob("*.sh")):
        try:
            out[f"tools/{p.name}"] = (p.read_text(encoding="utf-8"), UNIT_TOOL_W)
        except (UnicodeDecodeError, OSError):
            continue
    return out


def propose(data: dict, top: int = 3) -> dict[str, list[tuple[str, float]]]:
    import math
    units = _units()
    n_units = len(units)
    secs = {s["id"]: s for rel in DOCS for s in sections(rel)}
    df: dict[str, int] = {}
    out: dict[str, list[tuple[str, float]]] = {}
    for r in data["rows"]:
        if r["state"] != "blank":
            continue
        sec = secs.get(r["id"])
        toks = {t.strip().rstrip("()")
                for _, line in sec["body"] for t in TOK.findall(line)}
        toks = {t for t in toks if 4 <= len(t) <= 60 and not NOT_A_NAME.search(t)}
        score: dict[str, float] = {}
        for t in toks:
            if t not in df:
                df[t] = sum(1 for b, _ in units.values() if t in b)
            # 흔한 토큰은 아무것도 안 가른다. 15% 를 넘으면 버린다
            if df[t] == 0 or df[t] > n_units * 0.15:
                continue
            w = math.log(n_units / df[t])
            for k, (body, uw) in units.items():
                if t in body:
                    score[k] = score.get(k, 0.0) + w * uw
        ranked = sorted(score.items(), key=lambda kv: -kv[1])[:top]
        out[r["id"]] = [(k, round(v, 1)) for k, v in ranked if v >= 4.0]
    return out


def cmd_propose(data: dict, size: int, out_path: Path,
                only: list[str] | None = None) -> None:
    cand = propose(data)
    bm = load_bookmark()
    done = set(bm["done"])
    rows = {r["id"]: r for r in data["rows"]}
    todo = [r for r in data["rows"]
            if r["state"] == "blank" and r["id"] not in done]
    if only:
        todo = [r for r in data["rows"] if r["id"] in set(only)]
    todo = todo[:size]
    lines = ["# DMS 회차 — 한 줄에 하나. **숫자만 남기고 지운다.**",
             "#   1·2·3  그 후보를 강제자로 적는다",
             "#   0      강제자 없음 — 사유를 뒤에 적는다",
             "#   (비움) 이번 회차에서 건너뛴다. 북마크에 안 들어간다",
             "#",
             "# 다 고치면 — uv run python tools/dms.py fill "
             f"{out_path.name} --apply", ""]
    for r in todo:
        lines.append(f"[{r['id']}] {r['doc']}:{r['line']}  "
                     f"{'#' * r['depth']} {r['title'][:62]}")
        for i, (k, v) in enumerate(cand.get(r["id"], []), 1):
            lines.append(f"    {i}) {k}   ({v})")
        if not cand.get(r["id"]):
            lines.append("    (후보 없음 — 백틱 토큰이 없거나 다 흔한 것이다)")
        lines.append("고름 = ")
        lines.append("")
    STATE.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    have = sum(1 for r in todo if cand.get(r["id"]))
    print(f"{out_path}  {len(todo)}절 · 후보 있음 {have} · 없음 {len(todo) - have}")
    print(f"남은 분모 {sum(1 for r in data['rows'] if r['state'] == 'blank') - len(done)}")
    _ = rows


PICK = re.compile(r"^고름\s*=\s*(\S+)\s*(.*)$")
SEC_HEAD = re.compile(r"^\[([^\]\s]+)\] (\S+?):(\d+)")


def cmd_fill(path: Path, apply: bool) -> int:
    """회차 파일의 선택을 문서에 적는다. **고르지 않은 것은 안 건드린다.**"""
    cur: dict | None = None
    picks: list[tuple[str, str, int, str]] = []
    opts: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        if m := SEC_HEAD.match(line):
            cur, opts = {"id": m.group(1), "doc": m.group(2),
                         "line": int(m.group(3))}, {}
        elif m := re.match(r"^\s+(\d)\) (\S+)", line):
            opts[int(m.group(1))] = m.group(2)
        elif (m := PICK.match(line)) and cur:
            sel, rest = m.group(1), m.group(2).strip()
            if sel == "0":
                field = f"강제자 없음 — 사유: {rest or '(사유 미기재)'}"
            elif sel.isdigit() and int(sel) in opts:
                field = f"강제자  `{opts[int(sel)]}`" + (f" — {rest}" if rest else "")
            else:
                continue
            picks.append((cur["doc"], cur["id"], cur["line"], field))
    by_doc: dict[str, list] = {}
    for doc, sid, line, field in picks:
        by_doc.setdefault(doc, []).append((line, sid, field))
    marked = []
    for doc, items in by_doc.items():
        p = ROOT / doc
        lines = p.read_text(encoding="utf-8").split("\n")
        for line, sid, field in sorted(items, reverse=True):
            end = next((j for j in range(line, len(lines))
                        if HEAD.match(lines[j])), len(lines))
            at = end
            while at > line and lines[at - 1].strip() in ("", "---"):
                at -= 1
            lines.insert(at, "\n" + field)
            marked.append(sid)
        if apply:
            p.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(picks)}절 {'적용' if apply else '(미적용 — --apply)'}")
    if apply and marked:
        cmd_mark(marked)
    return 0


# ══ 봉인 — **여기까지는 정합이 보장된다** ═════════════════════
# ★ 북마크는 "어디까지 읽었나" 가 아니라 **증표**다. 봉인 지점까지는
#   전수로 봤고 정합했다는 사실을 지문으로 못박는다. 그 다음 감사는
#   539절을 다시 세지 않고 **봉인 뒤 바뀐 것만** 센다. 이것이 CDC 다.
#
# ★ 봉인이 깨지는 조건은 셋이다.
#     ① 절 내용이 바뀌었다        그 절만 다시 본다
#     ② 절이 새로 생겼다·사라졌다  그 절만 다시 본다
#     ③ **이 도구가 바뀌었다**     전수 재검사. 봉인 전체가 무효다
#   ③ 이 제일 중요하다. 판정 규칙이 바뀌면 옛 통과는 증표가 아니다.
#   `golden.py lock` 이 코드 지문을 같이 넣는 것과 같은 이유다.
SEAL = "SEAL.json"
REDFILE = "RED.txt"


def load_red() -> dict[str, str]:
    """아는 빨강 선언. **사유가 없으면 선언이 아니다.**

    ★ `--red 이름` 만으로는 부족하다. 이름만 적으면 왜 빨간지가 사라지고,
      반년 뒤 그 빨강이 고쳐졌는지 원래 그런지 아무도 모른다.
      강제자 칸에 `없음 — 사유:` 를 강제하는 것과 같은 이유다.
    """
    p = STATE / REDFILE
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, why = line.partition("|")
        if why.strip():
            out[name.strip()] = why.strip()
    return out


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ★ 2026-09-20 (W4-8 · DECISIONS §202). **이름이 약속한 범위가 실제보다 넓었다.**
#   `_tool_print()` 는 `dms.py` **한 파일**만 해시했는데, 이 값이 뜻하는 것은
#   「판정 규칙이 바뀌었는가 — 바뀌었으면 옛 통과는 증표가 아니다」다.
#   그 판정을 실제로 내리는 것은 `dms.py` 혼자가 아니라 **그것이 돌리는 것들**이다:
#   `verify.sh` 전 단계 · 프로브 넷 · `dupcheck`. 2026-09-18 에 `verify.sh` 가
#   +58 −9 로 바뀌었는데 지문이 `4e5793923f7cb248` 에서 한 글자도 안 움직였다 —
#   **분모가 바뀌었는데 봉인은 여전히 유효하다고 말했다.**
#
# ★ 손 목록을 만들지 않는다(그러면 W3-8 과 같은 병이다). `dms.py` 본문에서
#   `tools/…` 경로 리터럴을 **뽑아서** 센다 — 부르는 자리가 곧 범위다.
#   새 도구를 부르기 시작하면 그 순간 지문이 움직인다.
TOOLREF = re.compile(r"\btools/([A-Za-z_][\w]*\.(?:py|sh|mjs))\b")


def _tool_scope() -> list[Path]:
    """`dms` 의 판정 분모를 이루는 파일. 자기 자신 + 자기가 부르는 `tools/…`."""
    me = Path(__file__)
    names = sorted(set(TOOLREF.findall(me.read_text(encoding="utf-8"))))
    out = [me]
    out += [q for n in names if (q := ROOT / "tools" / n).is_file() and q != me]
    return sorted(set(out))


def _tool_print() -> str:
    """도구 전체 지문. **무효화 범위로는 쓰지 않는다** — `AXIS_TOOLS` 를 봐라."""
    return _sha("\n".join(f"{p.relative_to(ROOT).as_posix()}\0"
                          f"{_sha(p.read_text(encoding='utf-8'))}"
                          for p in _tool_scope()))


def _tool_prints() -> dict[str, str]:
    """도구 **하나씩** 지문. 축별 무효 판정의 재료다."""
    return {p.relative_to(ROOT).as_posix(): _sha(p.read_text(encoding="utf-8"))
            for p in _tool_scope()}


#: 봉인 축 → **그 축의 값을 만드는 도구.** 이 목록에 든 도구가 바뀐 축만 무효다.
#:
#: ★ 2026-09-25 (DECISIONS §255). 종전에는 `tool` 지문 **하나**가 봉인 전체를
#:   무효화했다 — `dupcheck.py` 한 줄만 고쳐도 절 1,036개가 통째로 재검사
#:   대상이 됐다. `dupcheck` 는 **코드 사본을 세는 도구**이고 절 내용과 아무
#:   상관이 없는데도 그랬다.
#:
#:   그 구조가 「감사할 일을 만든다」. 전수 재검사는 비싸고(OOM 위험) 사람이
#:   그것을 회피하기 시작하면 봉인이 장식이 된다. 실제로 이 배치가
#:   `verify.sh` 에 단계 하나를 더한 순간 봉인 전체가 무효가 됐다.
#:
#: ★ **무효화는 실제 영향만큼만 넓어야 한다.** §243 이 「선언이 검사보다 넓으면
#:   거짓 초록이 된다」를 적었고, 이것은 그 거울상이다 — **무효화가 영향보다
#:   넓으면 재검사가 습관적으로 건너뛰어진다.**
#:
#: ★ 축 이름은 `SEAL.json` 의 키와 같다. 새 축이 생겼는데 여기 없으면
#:   `tests/test_seal_axes.py` 가 운다 — 손목록이 실물보다 좁아지는 것을 막는다.
AXIS_TOOLS: dict[str, tuple[str, ...]] = {
    # 절 해시·상태·물림은 `dms.py` 의 파싱·분류 규칙만이 정한다.
    "sections": ("tools/dms.py",),
    "denominator": ("tools/dms.py",),
    "dead_refs": ("tools/dms.py",),
    # 사본군은 `dupcheck` 가 센다. 절과 무관하다.
    "dup_groups": ("tools/dupcheck.py",),
    # 강제자 통과 기록은 관문이 정한다.
    "enforcers": ("tools/verify.sh", "tools/deadcheck.py", "tools/env_check.py"),
    # 아래 넷은 **도구와 무관하다** — 순수 파일·입력 해시다.
    "docs": (),
    "raw": (),
    "code": (),
    "declared_red": (),
}

#: 축이 아니라 봉인 자신의 기록. 무효 판정 대상이 아니다.
SEAL_META = ("sealed_at", "commit", "tool", "tools", "scope", "red_ages", "red_reasons")


def stale_axes(old: dict) -> dict[str, list[str]]:
    """봉인 뒤 **어느 축이 무효가 됐나.** 축 → 바뀐 도구 목록.

    ★ 옛 봉인(`tools` 칸이 없다)은 축별 판정을 할 수 없으므로 전 축을 무효로
      본다. 모를 때 유효하다고 말하는 것은 검사를 끄는 것과 같다.
    """
    was = old.get("tools")
    if not isinstance(was, dict):
        return {a: ["(옛 봉인 — 도구별 지문이 없다)"] for a in AXIS_TOOLS}
    now = _tool_prints()
    out: dict[str, list[str]] = {}
    for axis, tools in AXIS_TOOLS.items():
        moved = [t for t in tools if was.get(t) != now.get(t)]
        if moved:
            out[axis] = moved
    return out


def _state_now(data: dict) -> dict:
    secs = {s["id"]: s for rel in DOCS for s in sections(rel)}
    out = {}
    for r in data["rows"]:
        s = secs[r["id"]]
        body = "\n".join(line for _, line in s["body"])
        out[r["id"]] = {"h": _sha(s["title"] + "\n" + body),
                        "state": r["state"], "doc": r["doc"],
                        "title": r["title"][:72]}
    return out


# ══ 강제자 전수 실행 — 봉인의 근거 ═══════════════════════════
# ★ 지문만 박은 봉인은 증표가 아니다. "문서가 안 바뀌었다" 는 말이지
#   "정합한다" 는 말이 아니다. 봉인하기 전에 **강제자를 전부 돌린다.**
#
#   분모 — verify.sh 전 단계 + pytest + 프로브 셀프테스트 + 훅
#
# ★ 빨간 것이 있으면 **봉인을 거부한다.** 다만 아는 빨강은 이름을 대면
#   적고 넘어간다 — `--red golden`. 적는 순간 세어지고, 적지 않으면
#   못 지나간다. 강제자 칸에 "없다" 를 적게 하는 것과 같은 설계다.
ANSI = re.compile(r"\x1b\[[0-9;]*m")
STEP = re.compile(r"^── (.+)$")
VERDICT = re.compile(r"^\s+(OK|실패|생략)\b\s*(.*)$")

PROBES = [("deadcheck", ["tools/deadcheck.py", "--selftest"]),
          ("env_check", ["tools/env_check.py", "--selftest"]),
          ("dms", ["tools/dms.py", "--selftest"]),
          ("dupcheck", ["tools/dupcheck.py", "--selftest"])]


def _run(cmd: list[str], timeout: int = 2400) -> tuple[int, str]:
    try:
        # ★ 2026-09-14. `stdin=DEVNULL`. 부모 stdin 을 물려주면 자식이
        #   그것을 읽으려다 죽는다 — `verify.sh` 의 `step()` 이 같은
        #   이유로 `jijeok` 을 죽였다고 적었는데 **그것도 틀렸다** —
        #   진짜 원인은 메모리였다(2026-09-14, `Errno 12`).
        #   `stdin=DEVNULL` 자체는 옳으므로 남긴다. 배치 파이프라인이
        #   부모 stdin 을 물려받을 이유가 없다.
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return r.returncode, ANSI.sub("", (r.stdout + r.stderr)).strip()
    except FileNotFoundError:
        return 127, "명령이 없다"
    except subprocess.TimeoutExpired:
        return 124, f"{timeout}초를 넘겼다"


def _parse_verify(txt: str, rc: int) -> dict[str, dict]:
    """`verify.sh` 출력 → 단계별 판정.

    ★ `실패` 줄 자체는 비어 있다. verify.sh 가 사유를 **그 다음 줄부터**
      들여써서 뱉는다. 그것을 안 모으면 "무엇이 왜 빨간지" 가 사라진다.
      실패 이름만 있고 사유가 없는 보고는 침묵보다 낫지 않다(원칙 ④).
    """
    out: dict[str, dict] = {}
    name = None
    lines = txt.split("\n")
    for i, line in enumerate(lines):
        if m := STEP.match(line.rstrip()):
            name = m.group(1).strip()
        elif name and (m := VERDICT.match(line)):
            why = m.group(2).strip()
            if not why:
                body = []
                for nxt in lines[i + 1:]:
                    if not nxt.strip() or STEP.match(nxt.rstrip()):
                        break
                    body.append(nxt.strip())
                why = " / ".join(body[-3:])
            out[f"verify/{name}"] = {"rc": 0 if m.group(1) == "OK" else 1,
                                     "state": m.group(1), "tail": why[:200]}
            name = None
    # ★ 집계는 강제자가 아니다. 단계가 빨가면 당연히 빨간 파생값이라
    #   이것까지 세면 사람이 같은 빨강을 두 번 설명하게 된다.
    out["verify.sh(집계)"] = {"rc": rc, "state": "생략",
                              "tail": f"단계 {len(out)}"}
    return out


def _log_head(log: Path) -> str | None:
    """로그 머리말의 `HEAD    <해시>` 줄. 없으면 옛 로그다."""
    for line in log.read_text(encoding="utf-8", errors="replace").split("\n")[:12]:
        m = re.match(r"^HEAD\s+(\S+)(.*)$", ANSI.sub("", line))
        if m:
            return m.group(1) + ("+미커밋" if "미커밋" in m.group(2) else "")
    return None


# ★ 파이프라인이 돌 때마다 갱신되는 생성물. **신선도 판정에서 뺀다.**
#   2026-09-14 에 `web/data/_manifest.json` 하나 때문에 `seal` 이 세 번
#   거부했고 그때마다 20분짜리를 다시 돌렸다. 커밋하면 HEAD 가 바뀌어
#   또 거부다 — 빠져나갈 데가 없는 고리였다.
# ★ 이것들은 **커밋 시점이 따로**다. 판정의 입력이 아니라 산출이고,
#   같은 입력이면 같은 값이 다시 나온다(그 재현성 자체를 `golden` 이
#   검사한다). 로그가 낡았다는 신호가 될 수 없다.
# ★ 반대로 `src`·`tools`·`docs` 는 그대로 센다. 그쪽이 바뀌면 로그는
#   정말로 다른 저장소 얘기다.
# ★ 목록의 정본은 firelane/generated.py 의 역할 "seal" 이다(W3-13).
GENERATED = prefixes("seal")


def tree_is_dirty() -> bool:
    """생성물을 뺀 작업나무가 더러운가."""
    out = _run(["git", "status", "--porcelain"], 60)[1]
    for line in out.split("\n"):
        if not line.strip():
            continue
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if not rel.startswith(GENERATED):
            return True
    return False


def _log_is_fresh(log: Path) -> list[str]:
    """로그가 **지금 나무보다 나중인가.** 아니면 그 로그는 다른 저장소 얘기다."""
    # ★ 2026-09-14. 커밋으로 먼저 본다. mtime 은 **내용이 안 바뀌어도**
    #   잡는다 — `golden.py lock` 뒤에 `seg/width.py` · `MASTER.md` 가
    #   그렇게 걸려 30분짜리 재실행을 시켰다.
    #   "언제 만졌나" 가 아니라 "무엇이 다른가" 를 묻는 것이 맞다.
    head = _log_head(log)
    if head is not None:
        now = _run(["git", "rev-parse", "--short", "HEAD"], 30)[1]
        dirty = tree_is_dirty()
        want = now + ("+미커밋" if dirty else "")
        return [] if head == want else [f"로그 {head} \u2194 지금 {want}"]
    # 옛 로그다. HEAD 줄이 없으면 mtime 으로 떨어진다 — 더 엄한 쪽이다.
    cut = log.stat().st_mtime
    newer = []
    names = _run(["git", "ls-files"], 60)[1].split("\n")
    for rel in names:
        if not rel:
            continue
        f = ROOT / rel
        try:
            if f.stat().st_mtime > cut:
                newer.append(rel)
        except OSError:
            continue
    return newer[:20]


def run_enforcers(quick: bool, log: Path | None = None) -> dict[str, dict]:
    """★ 결과를 **이름별로** 남긴다. 총합만 남기면 어느 것이 빨간지 못 센다."""
    out: dict[str, dict] = {}

    if log is not None:
        # ★ 방금 돌린 `verify.sh` 를 다시 20분 돌리지 않는다. 다만 로그가
        #   **지금 나무보다 나중**이어야 한다. 아니면 봉인이 옛 상태를
        #   증언하게 된다 — 가짜 증표다.
        print(f"  {log} 를 읽는다 (다시 안 돌린다)", flush=True)
        txt = ANSI.sub("", log.read_text(encoding="utf-8", errors="replace"))
        rc = 0 if "\n실패가 있다" not in txt else 1
        out.update(_parse_verify(txt, rc))
    elif quick:
        print("  pytest …", flush=True)
        rc, txt = _run(["uv", "run", "pytest", "tests/", "-q"])
        out["pytest"] = {"rc": rc, "state": "OK" if rc == 0 else "실패",
                         "tail": txt.split("\n")[-1][:120]}
    else:
        print("  verify.sh 전 단계 … (몇 분 걸린다)", flush=True)
        rc, txt = _run(["bash", "tools/verify.sh"])
        out.update(_parse_verify(txt, rc))

    for label, cmd in PROBES:
        if not (ROOT / cmd[0]).exists():
            continue
        rc, txt = _run([sys.executable, *cmd], timeout=600)
        out[f"probe/{label}"] = {"rc": rc, "state": "OK" if rc == 0 else "실패",
                                 "tail": (txt.split("\n") or [""])[-1][:120]}

    # 훅 — 전역이 살아 있는가. `core.hooksPath` 가 로컬로 박히면 전역이 죽는다
    # ★ 값이 *있는가* 를 rc 로 본다. 저장소 밖이면 git 이 오류 문자열을
    #   내는데 그것을 값으로 읽으면 멀쩡한 기계가 빨개진다.
    rc_l, local = _run(["git", "config", "--local", "core.hooksPath"], 20)
    has_local = rc_l == 0 and bool(local)
    out["hook/local-hooksPath"] = {
        "rc": 1 if has_local else 0, "state": "실패" if has_local else "OK",
        "tail": f"로컬이 전역을 이긴다: {local}" if has_local else "전역에 위임"}
    rc_g, glob = _run(["git", "config", "--global", "core.hooksPath"], 20)
    has_glob = rc_g == 0 and bool(glob)
    out["hook/global-hooksPath"] = {
        "rc": 0 if has_glob else 1, "state": "OK" if has_glob else "실패",
        "tail": glob if has_glob else "전역 훅이 없다 — 자격증명 검사가 안 돈다"}
    return out



def _red_ages(red: list[str]) -> dict[str, int]:
    """이 빨강이 **몇 번째 봉인인가.** 직전 SEAL 에서 이어 센다."""
    p = STATE / SEAL
    if not p.exists():
        return {k: 1 for k in red}
    try:
        prev = json.loads(p.read_text(encoding="utf-8")).get("red_ages") or {}
    except (OSError, ValueError):
        prev = {}
    return {k: int(prev.get(k, 0)) + 1 for k in red}


def _closed_declarations(declared: dict[str, str], red: list[str],
                         unproven: list[str] | None = None) -> list[str]:
    """선언됐는데 **지금 초록인** 이름.

    ★ 2026-09-15. `unproven` 이 생겼다. 종전에는 *빨갛지 않으면 닫혔다*
      였는데, `생략` 은 빨갛지도 초록도 아니다. `--fast` 로 돌리면
      `파이프라인 전량` 이 `생략` 이라 빨갛지 않고, **안 닫혔는데 닫혔다고
      판정한다.** 2026-09-14 에 실제로 선언 둘을 지우게 만들었다.
      `생략` 은 통과가 아니다.

    ★ 사유를 적는 순간 그 항목은 검사에서 빠지고, 빠진 것은 낡는다.
      `EXEMPT` 여섯이 그렇게 낡아 있었다 — 다섯은 이미 `verify.sh` 가
      부르는 도구인데 면제 목록에 남아 배선을 끊어도 우는 곳이 없었다.
      같은 병을 `RED.txt` 가 물려받지 않게 한다.
    """
    return sorted(set(declared) - set(red) - set(unproven or []))

# 봉인할 때 커밋 안 돼도 되는 추적 파일 — 봉인 자신과, 봉인 커밋에 함께 넣는 생성 매니페스트
# 정본은 firelane/generated.py 의 역할 "seal-dirty" 다(W3-13).
SEAL_MAY_BE_DIRTY = prefixes("seal-dirty")


def uncommitted(root: Path = ROOT) -> list[str]:
    """커밋 안 된 **추적** 파일. 봉인은 커밋본의 기준선이어야 한다.

    ★ 2026-09-17 (DECISIONS §180-7). L2d 적용 스크립트가 패치의 `src/firelane/normalize_raw.py` 를 커밋에서
      빠뜨렸다. 레이크 기계의 verify 는 작업 트리를 보고 41 단계 초록, 봉인도 찍혔다(헤더에 `+미커밋`).
      CI 는 커밋본을 보고 `test_every_required_file_is_reachable_by_rules` 로 빨강. 봉인이 거짓이었다.
    """
    import subprocess
    r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                       cwd=root, capture_output=True, text=True, check=False)
    out = []
    for ln in r.stdout.splitlines():
        rel = ln[3:].strip().strip('"')
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        if not any(rel == d or rel.startswith(d) for d in SEAL_MAY_BE_DIRTY):
            out.append(rel)
    return out


def cmd_seal(data: dict, quick: bool, allow: list[str],
             log: Path | None = None) -> int:
    """★ 분모가 0 이 아니어도 봉인한다. 봉인은 *완료* 가 아니라 *기준선*이다.
    다만 빨간 강제자가 설명 없이 있으면 거부한다 — 그것은 기준선도 아니다."""
    import datetime
    print("── 강제자 전수 ───────────────────────────────────────")
    if log is not None:
        if not log.exists():
            print(f"✗ {log} 가 없다")
            return 2
        newer = _log_is_fresh(log)
        if newer:
            print(f"✗ 로그보다 나중에 바뀐 파일이 {len(newer)}개다. 그 로그는 옛 상태다.")
            for f in newer[:8]:
                print(f"    {f}")
            print("  ★ 다시 돌려라 —  bash tools/verify.sh 2>&1 | tee /tmp/verify.log")
            return 1
    dirty = uncommitted()
    if dirty:
        print(f"✗ 커밋 안 된 추적 파일이 {len(dirty)}개다 — 봉인은 커밋본의 기준선이다. CI 는 커밋본만 본다.")
        for f in dirty[:8]:
            print(f"    {f}")
        print("  ★ 커밋하고 verify 부터 다시 돌려라(§180-7)")
        return 1
    enf = run_enforcers(quick, log)
    red = sorted(k for k, v in enf.items() if v["state"] == "실패")
    for k in sorted(enf):
        v = enf[k]
        if v["state"] != "OK" or k in ("verify.sh", "pytest"):
            mark = {"OK": "✓", "실패": "✗"}.get(v["state"], "-")
            print(f"  {mark} {k:42} {v['tail'][:62]}")
    print(f"  강제자 {len(enf)} · 빨강 {len(red)}")

    declared = load_red()
    unexplained = [k for k in red
                   if k not in declared and not any(a and a in k for a in allow)]
    if unexplained:
        p = STATE / REDFILE
        STATE.mkdir(parents=True, exist_ok=True)
        old = p.read_text(encoding="utf-8") if p.exists() else (
            "# 아는 빨강. `이름 | 사유` 한 줄에 하나.\n"
            "# ★ 사유를 안 적으면 선언이 아니다 — 봉인이 계속 거부한다.\n"
            "# ★ 고쳤으면 줄을 지워라. 남겨두면 진짜 빨강을 덮는다.\n")
        add = "".join(f"{k} | \n" for k in unexplained if f"{k} |" not in old)
        p.write_text(old.rstrip("\n") + "\n" + add, encoding="utf-8")
        print("\n✗ 봉인하지 않는다. 빨간 강제자에 사유가 없다.")
        for k in unexplained:
            print(f"    {k}\n        {enf[k]['tail'][:96] or '(사유를 못 읽었다)'}")
        print(f"\n  고치거나, {p} 의 `|` 뒤에 사유를 적어라.")
        print("  ★ 사유 없는 이름은 선언이 아니다. 적는 순간 세어진다.")
        return 1
    # ★ 2026-09-14. 닫힌 선언을 잡는다. 네 번째 봉인이 `빨강 0 · 선언 2`
    #   로 찍혔다 — 둘 다 이미 닫혔는데 줄이 남아 있었다. 남은 줄은
    #   그 이름이 **진짜로 다시 빨개져도 조용히 통과시킨다.**
    # ★ `_red_ages` 는 지금 빨간 것만 세므로 죽은 선언은 영원히 1회째다.
    #   6회 거부 장치가 정작 낡은 선언을 못 잡았다.
    # ★ `OK` 도 `실패` 도 아닌 것 — `생략` · 미실행. 증명되지 않았다.
    unproven = sorted(k for k, v in enf.items()
                      if v["state"] not in ("OK", "실패"))
    closed = _closed_declarations(declared, red, unproven)
    if closed:
        print(f"\n✗ 봉인하지 않는다. 닫힌 선언이 {len(closed)}건 남아 있다.")
        for k in closed:
            print(f"    {k}   지금 초록이다")
        print(f"\n  {STATE / REDFILE} 에서 그 줄을 지워라.")
        print("  ★ 선언은 유예지 면제가 아니다. 남겨두면 진짜 빨강을 덮는다.")
        return 1
    ages = _red_ages(red)
    if declared:
        print(f"  선언된 빨강 {len(declared)}")
        for k in sorted(declared):
            n = ages.get(k, 1)
            mark = "★" if n >= 3 else " "
            print(f"    {mark} {k}   {n}회째")
    # ★ 사유를 적는 순간 그 항목은 검사에서 빠지고, 빠진 것은 낡는다.
    #   `EXEMPT` 여섯이 그렇게 낡아 있었다 — 다섯은 이미 verify.sh 가
    #   부르는 도구인데 면제 목록에 남아 배선을 끊어도 우는 곳이 없었다.
    #   같은 병을 `RED.txt` 가 물려받지 않게 나이를 센다.
    old = [k for k in declared if ages.get(k, 1) >= 6]
    if old:
        print("\n✗ 봉인하지 않는다. 여섯 번째 봉인까지 안 닫힌 빨강이 있다.")
        for k in old:
            print(f"    {k}   {ages[k]}회째")
        print("\n  닫거나, 못 닫는 이유가 바뀌었으면 사유를 다시 써라.")
        print("  ★ 선언은 유예지 면제가 아니다.")
        return 1

    now = _state_now(data)
    blank = sum(1 for v in now.values() if v["state"] == "blank")
    dup = (_run([sys.executable, "tools/dupcheck.py", "--min", "25"], 600)[0]
           if (ROOT / "tools/dupcheck.py").exists() else -1)
    rec = {
        "sealed_at": datetime.datetime.now().astimezone()
                     .isoformat(timespec="seconds"),
        "commit": _run(["git", "rev-parse", "--short", "HEAD"], 20)[1] or "(git 밖)",
        "tool": _tool_print(),
        # ★ 2026-09-25 (§255). **도구 하나씩** 남긴다. `delta` 가 이것으로
        #   축별 무효를 판정한다 — 종전에는 위 한 줄이 봉인 전체를 무효화했다.
        "tools": _tool_prints(),
        "scope": ("verify.sh 로그" if log else
                  "pytest+프로브" if quick else "verify.sh 전 단계"),
        "docs": {rel: _sha((ROOT / rel).read_text(encoding="utf-8"))
                 for rel in DOCS},
        # ★ PLAN #68. 입력이 봉인과 같으면 판정도 같다. `rawdiff` 가
        #   이것을 대조해 파이프라인 전량(4분30초)을 **근거 있게** 생략한다.
        #   못 재면 None 이고, None 이면 다음 대조가 생략하지 않는다.
        "raw": raw_print(),
        # ★ §164. 코드가 같다는 증거 없이 raw 만 같다고 생략하면 안 된다.
        "code": code_print(),
        "sections": now,
        "denominator": blank,
        "dead_refs": len(verify(data)),
        "dup_groups": dup,
        "enforcers": enf,
        "declared_red": red,
        "red_ages": ages,
        "red_reasons": {k: declared.get(k, "(인자로 넘김)") for k in red},
    }
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / SEAL).write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")
    print(f"\n봉인 {rec['sealed_at']}  {rec['commit']}  [{rec['scope']}]")
    # ★ 2026-09-17 (§180). "죽은 참조" 는 refcheck 의 경로 참조와 이름이 같아 두 숫자가 어긋나 보였다
    print(f"  절 {len(now)} · 분모 {blank} · 죽은 강제자 참조 {rec['dead_refs']} "
          f"· 사본군 {dup}")
    print(f"  강제자 {len(enf)} 통과"
          + (f"  아는 빨강 {len(red)} — {', '.join(red)}" if red else ""))
    print(f"  도구 지문 {rec['tool']}")
    print("★ 이 지점까지 정합한다. 다음부터 `delta` 가 여기 뒤만 센다.")
    return 0


def cmd_delta(data: dict) -> int:
    p = STATE / SEAL
    if not p.exists():
        # ★ 기준선이 없는 것은 *어긋난 것*이 아니다. 여기서 빨개지면
        #   verify.sh 가 빨개지고, 그러면 `seal` 이 영영 못 찍힌다.
        print("봉인이 없다. 전수가 곧 분모다 — `dms.py seal` 로 찍어라.")
        print(f"  지금 분모 {sum(1 for r in data['rows'] if r['state'] == 'blank')}")
        return 0
    old = json.loads(p.read_text(encoding="utf-8"))
    # ★ 2026-09-25 (§255). **축별로** 무효를 판정한다. 종전에는 `tool` 지문
    #   하나가 봉인 전체를 무효화해서, `dupcheck.py` 한 줄만 고쳐도 절
    #   1,036개가 재검사 대상이 됐다 — 절 내용과 아무 상관이 없는데도.
    #   무효화가 실제 영향보다 넓으면 재검사가 습관적으로 건너뛰어진다.
    stale = stale_axes(old)
    if stale:
        print("★ 도구가 바뀐 축:")
        for axis, tools in sorted(stale.items()):
            print(f"    {axis:14} ← {' · '.join(Path(x).name for x in tools)}")
        live = sorted(set(AXIS_TOOLS) - set(stale))
        print(f"  **살아 있는 축 {len(live)}/{len(AXIS_TOOLS)}** — {' · '.join(live)}")
        print("  무효인 축만 다시 본다. 전수가 아니다.")
        # ★ 여기서 빨개지면 안 된다. `seal` 이 verify.sh 를 돌리고 verify.sh 가
        #   이 단계를 부르므로, 빨강이면 seal 이 영영 못 찍힌다(자기참조).
        #   봉인의 유효성은 `seal` 이 판정한다. 이 단계는 **보고**만 한다.
        if "sections" in stale:
            print("  ★ `sections` 가 무효다 — 절 대조는 전수로 봐야 한다.")
            return 0
    same = [rel for rel in DOCS
            if old["docs"].get(rel) == _sha((ROOT / rel).read_text(encoding="utf-8"))]
    now, prev = _state_now(data), old["sections"]
    new = [k for k in now if k not in prev]
    gone = [k for k in prev if k not in now]
    moved = [k for k in now if k in prev and now[k]["h"] != prev[k]["h"]]
    print(f"봉인 {old['sealed_at']}  {old['commit']}  분모 {old['denominator']}")
    print(f"  건드리지 않은 문서 {len(same)}/{len(DOCS)}  "
          + (" · ".join(Path(r).name for r in same) if same else "(없다)"))
    print(f"\n신설 {len(new)} · 변경 {len(moved)} · 삭제 {len(gone)}")
    for k in new + moved:
        tag = "신설" if k in new else "변경"
        print(f"  {tag}  {now[k]['doc']}  {k}  [{now[k]['state']}] "
              f"{now[k]['title'][:50]}")
    for k in gone:
        print(f"  삭제  {prev[k]['doc']}  {k}  {prev[k]['title'][:50]}")
    todo = [k for k in new + moved if now[k]["state"] == "blank"]
    print(f"\n★ 이번에 사람이 볼 것 {len(todo)}절. "
          f"전수 {len(now)}절이 아니다.")
    if todo:
        print(f"  uv run python tools/dms.py propose d --only {' '.join(todo[:40])}")
    return min(len(todo), 255)


def bookmark_path() -> Path:
    return STATE / "BOOKMARK.json"


def load_bookmark() -> dict:
    p = bookmark_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"done": []}


def cmd_round(data: dict, size: int) -> None:
    bm = load_bookmark()
    done = set(bm["done"])
    blanks = [r for r in data["rows"] if r["state"] == "blank"]
    todo = [r for r in blanks if r["id"] not in done]
    read = len(blanks) - len(todo)
    print(f"분모 {len(blanks)} · 읽은 절 {read} · 남은 절 {len(todo)}\n")
    for r in todo[:size]:
        print(f"{r['id']}  {r['doc']}:{r['line']}")
        print(f"    {'#' * r['depth']} {r['title'][:64]}")
    print(f"\n다 읽었으면 — tools/dms.py mark {' '.join(r['id'] for r in todo[:size])}")


def cmd_mark(ids: list[str]) -> None:
    bm = load_bookmark()
    bm["done"] = sorted(set(bm["done"]) | set(ids))
    STATE.mkdir(parents=True, exist_ok=True)
    bookmark_path().write_text(json.dumps(bm, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(f"북마크 {len(bm['done'])}건")


def selftest() -> int:
    """프로브가 한 건도 못 내면 프로브가 죽은 것이지 저장소가 깨끗한 게 아니다."""
    bad = []
    data = scan()
    if not data["rows"]:
        bad.append("절을 하나도 못 셌다")
    # ★ 2026-09-24 (DECISIONS §230). 종전에는 「실제 트리에 blank 가 하나도
    #   없으면 칸 판정이 무르다」로 봤다. **그 0 이 목표 상태**인데 목표에
    #   닿는 날 관문이 빨개지는 검사이고, 그러면 사람이 검사를 끈다.
    #   `deadcheck` 가 2026-09-21 에, `test_defect_ledger_counts_agree_everywhere`
    #   가 2026-09-24 에 같은 것을 배웠다. **생사는 합성 입력이 증명한다.**
    empty = {"line": 0, "body": [(1, "칸이 없는 절이다"), (2, "두 줄이다")]}
    if classify(empty)[0] != "blank":
        bad.append("칸 없는 절을 blank 로 안 센다 — 판정이 무르다")
    if not any(r["state"] == "wired" for r in data["rows"]):
        bad.append("wired 가 0 이다 — 칸 판정이 너무 세다")
    if not data["rows"] or len(data["rows"]) < 500:
        bad.append(f"절을 {len(data['rows'])}개밖에 못 셌다 — 수집기가 죽었다")
    # 산문을 칸으로 세면 안 된다
    fake = {"line": 0, "body": [(1, "인코딩만 **강제자가 없었다.** 그래서")]}
    if classify(fake)[0] != "blank":
        bad.append("산문 `강제자가 없었다` 를 칸으로 셌다")
    # 닫힌 선언을 잡는가 — 선언 둘 중 하나만 아직 빨갛다면 나머지는 닫힌 것
    if _closed_declarations({"a": "사유", "b": "사유"}, ["a"]) != ["b"]:
        bad.append("닫힌 선언을 못 잡았다")
    # ★ 생략은 닫힘이 아니다. 이 줄이 없으면 `unproven` 이 죽어도 조용하다.
    if _closed_declarations({"a": "사유"}, [], ["a"]) != []:
        bad.append("생략된 선언을 닫힘으로 읽는다 — unproven 이 죽었다")
    if _closed_declarations({"a": "사유"}, ["a"]) != []:
        bad.append("아직 빨간 선언을 닫혔다고 했다")
    # 코드펜스 안은 칸이 아니다
    fenced = {"line": 0, "body": [(1, "```"), (2, "강제자  tests/test_x.py"),
                                 (3, "```")]}
    if classify(fenced)[0] != "blank":
        bad.append("코드펜스 안을 칸으로 셌다")
    # 진짜 칸은 세야 한다
    real = {"line": 0, "body": [(1, "강제자  `tests/test_guards.py::test_x`")]}
    if classify(real)[0] != "wired":
        bad.append("정상 칸을 못 셌다")
    # ★ 2026-09-24 (DECISIONS §241). 칸은 **여러 줄**에 걸친다(실측 113곳).
    #   첫 줄만 들면 이어지는 줄의 강제자 이름도 물림 선언도 안 보인다.
    wrapped = {"line": 0, "body": [(1, "강제자  `tests/test_a.py` ·"),
                              (2, "`tests/test_b.py`. 하위 둘이 이 칸을 물려받는다"),
                              (3, ""),
                              (4, "다음 문단은 칸이 아니다")]}
    st, field, _ = classify(wrapped)
    if st != "wired" or "test_b" not in field:
        bad.append("여러 줄 칸의 뒷줄을 안 본다 — 범위가 이름보다 좁다")
    if "다음 문단" in field:
        bad.append("빈 줄 뒤까지 칸으로 먹는다")
    # ★ 물림 선언이 적은 **수**를 되짚는가. 안 되짚으면 수를 적어도 안 세어진다.
    for txt, want in (("하위 둘이 이 칸을", 2), ("하위 절 여덟이", 8), ("하위 3절", 3),
                      ("하위 한 절도 같은", 1), ("하위 절 187-1 ~ 187-3", None),
                      ("강제자 `tests/test_x.py`", None)):
        if _said_count(txt) != want:
            bad.append(f"물림 수 오독 — {txt!r} → {_said_count(txt)} (기대 {want})")
    # ★ 수가 어긋나면 우는가. 합성 데이터로 본다 — 실물이 0 이어도 판정기는 살아야 한다.
    synth = {"rows": [
        {"id": "D/9", "doc": "d.md", "at": 1, "state": "wired",
         "field": "강제자 `tests/test_x.py`. 하위 셋이 이 칸을 물려받는다"},
        {"id": "D/9-1", "doc": "d.md", "at": 2, "state": "inherit", "field": ""},
        {"id": "D/9-2", "doc": "d.md", "at": 3, "state": "inherit", "field": ""},
    ]}
    if not inherit_counts(synth):
        bad.append("물림 수 어긋남(선언 3 · 실제 2)을 안 잡는다 — 그물이 비었다")
    synth["rows"][0]["field"] = "강제자 `tests/test_x.py`. 하위 둘이 이 칸을 물려받는다"
    if inherit_counts(synth):
        bad.append("맞는 수를 어긋남으로 잡는다 — 거짓 빨강")
    # ★ 2026-09-24 (DECISIONS §228). 강제자를 지목하면서 **범위를 덧붙인** 칸을
    #   `none` 으로 세면 안 된다. 실측 8건이 그 상태였다.
    ranged = {"line": 0, "body": [
        (1, "강제자  `tests/test_x.py::test_y`. 나머지 수는 실측값이라 대조 도구가 없다")]}
    if classify(ranged)[0] != "wired":
        bad.append("강제자를 지목한 칸을 `없다` 한 단어 때문에 none 으로 셌다")
    # 「없음」 선언은 **줄머리**에 있을 때만이다
    declared = {"line": 0, "body": [(1, "강제자 없음 — 사유: 기록이다")]}
    if classify(declared)[0] != "none":
        bad.append("줄머리 `없음` 선언을 none 으로 안 셌다")
    # ★ 전문 대조는 무르다. 확실히 죽은 이름을 넣어 프로브가 우는지 본다
    # ★ 이름을 조립한다. 리터럴로 적으면 이 파일 자신이 전문에 걸려 통과한다
    ghost = "test_" + "zq7" + "_absent"
    canary = {"rows": [{"state": "wired", "doc": "x", "at": 0, "id": "CANARY",
                        "title": "canary",
                        "field": f"강제자  `tests/{ghost}.py::{ghost}`"}]}
    if not verify(canary):
        bad.append("합성 죽은 참조를 못 잡았다 — 프로브가 죽었다")
    # ★ 2026-09-24 (DECISIONS §229). **실재하는 파일 + 없는 함수**가 제일 위험하다.
    #   파일만 보던 시절에는 26건이 초록으로 앉아 있었고 그중 22건이
    #   `test_plan_has_no_closed_items` 하나였다 — 이 도구 머리말이 「§123~143
    #   스물한 절이 없는 검사를 강제자로 들고 있었다」고 적은 바로 그것이다.
    #   **적어만 두고 잡지는 못했다.**
    live = {"rows": [{"state": "wired", "doc": "x", "at": 0, "id": "MEMBER",
                      "title": "member", "field":
                      f"강제자  `tests/test_guards.py::{ghost}`"}]}
    if not verify(live):
        bad.append("실재하는 파일 안의 **없는 함수**를 못 잡았다")
    if _missing_member("tests/test_guards.py", "test_no_dated_scripts_in_tools"):
        bad.append("실재하는 함수를 없다고 한다 — 오탐")
    for line in bad:
        print(f"  {line}")
    print("selftest " + ("빨강" if bad else "초록"))
    return len(bad)


# ── raw 지문 (PLAN #68) ────────────────────────────────────────
# ★ 입력이 봉인과 같으면 판정도 같다. 그런데 `SEAL.json` 이 문서·절·도구
#   지문만 갖고 raw 지문이 없어서 `verify.sh` 가 매번 파이프라인 전량
#   4분30초를 돈다. 하루에 다섯 번 돌리면 그것만 20분 이상이다.
#
# ★ **대장(`_manifest.json`)의 `source_sha256` 을 쓰지 않는다.** 그것은
#   ingest 가 돌 때 찍힌 값이라 raw 가 바뀌어도 ingest 전까지 안 바뀐다.
#   그 값으로 대조하면 "같다" 가 항상 참인 죽은 검사가 된다 —
#   오늘(2026-09-15) `⬛` 를 찾던 문서 검사와 같은 형태다(DECISIONS §159).
#   실물을 훑는 것은 `ingest --check` 이고, 그것은 아무것도 쓰지 않는다.
#
# ★ 못 재면 `None` 이다. **빈 dict 가 아니다.** 빈 dict 는 "raw 가 0종"
#   으로 읽혀 다음 대조에서 조용히 통과한다. 모르는 것을 아는 척하지
#   않는다 — 지문이 없으면 생략도 없다.
_RAW_MARK = "@@ingest-result@@ "


def raw_print() -> dict[str, list[str]] | None:
    """raw 실물의 소스별 sha256. 못 재면 None."""
    cmd = [sys.executable, "-c",
           "from firelane.ingest import main; main()",
           "--check", "--emit-json"]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=900, check=False)
    except Exception:                                       # noqa: BLE001
        return None
    if p.returncode:
        return None
    out = {}
    for line in p.stdout.splitlines():
        if line.startswith(_RAW_MARK):
            r = json.loads(line[len(_RAW_MARK):])
            if r.get("key") and r.get("sha256"):
                out[r["key"]] = r["sha256"]
    return out or None


# ★ 2026-09-16. 판정은 **raw 와 코드의 함수**다. raw 만 대조하면 코드를
#   바꾼 배치(판정 범위 · 중심선 보정)가 전량 생략으로 옛 산출물을 남기고,
#   golden 은 옛 산출물을 옛 지문과 맞춰 초록을 낸다(DECISIONS §164).
#   파이프라인 산출에 닿는 추적 경로를 전부 넣는다 — 모르면 넣는다.
CODE_PATHS = ("src", "sources.yaml", "pyproject.toml", "uv.lock", "data/field")


def code_print(root: Path = ROOT) -> dict | None:
    """파이프라인 코드의 지문. `{"sha256"(16자), "files"}`. 못 재면 None.

    ★ **추적 파일 목록은 git 에서, 내용은 디스크에서** 읽는다. 커밋 전에
      고친 것도 잡히고, 추적 안 된 찌꺼기(`__pycache__`)는 안 섞인다.
      지워진 추적 파일은 `<gone>` 으로 섞어 삭제도 차이로 센다.
    """
    try:
        r = subprocess.run(["git", "ls-files", "-z", "--", *CODE_PATHS],
                           cwd=root, capture_output=True, timeout=60, check=False)
    except Exception:                                       # noqa: BLE001
        return None
    if r.returncode:
        return None
    files = sorted(f for f in r.stdout.decode("utf-8").split("\0") if f)
    if not files:
        return None
    per = {rel: (sha256(root / rel) if (root / rel).is_file() else "<gone>")
           for rel in files}
    lines = [f"{rel}\0{d}" for rel, d in per.items()]
    # ★ 2026-09-20 (W4-4 · DECISIONS §203). 종전에는 `"files": len(files)` 였다.
    #   파일별 지문을 **계산해놓고 세어서 버렸다.** 그래서 코드가 달라졌을 때
    #   `rawdiff` 가 할 수 있는 말이 「파일 N → M」뿐이었고, 바로 아래 `raw` 블록은
    #   같은 자리에서 신설·변경·삭제를 키별로 말한다 — **같은 함수 안에서 한쪽만
    #   말을 못 했다.** 무엇이 바뀌었는지 못 말하는 봉인은 봉인이 아니다.
    #   `golden._logic_fingerprint` 의 `per` 와 같은 꼴로 남긴다.
    # ★ 수는 `len(files)` 로 언제든 다시 나온다. 지문은 그 시점에만 잴 수 있다.
    return {"sha256": _sha("\n".join(lines)), "files": per}


def cmd_rawdiff() -> int:
    """raw **와 파이프라인 코드**가 봉인 지점과 같은가. **같으면 0, 다르면 1.**

    `verify.sh` 가 이 결과로 파이프라인 전량을 생략할지 정한다.

    ★ 지금 `--fast` 는 **근거 없이** 전부/전무로 건너뛴다. 그 로그로
      봉인하면 반쪽 증표다. 여기는 근거가 있다 — 입력이 같다.
    ★ 모르면 **안 건너뛴다.** 봉인이 없거나 지문을 못 재면 1 이다.
      의심스러울 때 생략하는 것은 검사를 끄는 것과 같다.
    """
    p = STATE / SEAL
    if not p.exists():
        print("봉인이 없다 — 전량을 돈다.")
        return 1
    seal = json.loads(p.read_text(encoding="utf-8"))
    # ★ 코드부터 본다. raw 지문은 수 분이 걸리고 코드 지문은 1초다.
    oc = seal.get("code")
    if not oc:
        print("봉인에 코드 지문이 없다(옛 봉인) — 전량을 돈다.")
        return 1
    nc = code_print()
    if nc is None:
        print("코드 지문을 못 쟀다 — 전량을 돈다.")
        return 1
    if nc["sha256"] != oc.get("sha256"):
        # ★ 2026-09-20 (W4-4). 종전에는 「파일 N → M」만 찍었다. 수가 같으면
        #   (고치기만 하면 언제나 같다) 아무 정보도 없는 줄이었다.
        #   아래 `raw` 블록이 이미 키별로 말하고 있었다 — 같은 말을 여기서도 한다.
        ofs, nfs = oc.get("files"), nc["files"]
        if isinstance(ofs, dict):
            gone = sorted(set(ofs) - set(nfs))
            new = sorted(set(nfs) - set(ofs))
            moved = sorted(k for k in nfs if k in ofs and nfs[k] != ofs[k])
            print(f"파이프라인 코드가 봉인과 다르다 — 전량을 돈다 "
                  f"(신설 {len(new)} · 변경 {len(moved)} · 삭제 {len(gone)})")
            for k in (new + moved + gone)[:12]:
                tag = "신설" if k in new else ("변경" if k in moved else "삭제")
                print(f"    {tag}  {k}")
            rest = len(new) + len(moved) + len(gone) - 12
            if rest > 0:
                print(f"    … 그리고 {rest}개 더")
        else:
            # 옛 봉인은 `files` 가 개수다. 셀 수만 있고 이름은 없다.
            print(f"파이프라인 코드가 봉인과 다르다 — 전량을 돈다 "
                  f"(옛 봉인이라 파일별 지문이 없다 · 파일 {ofs} → {len(nfs)})")
        print(f"    git diff --stat {seal.get('commit', 'HEAD')} -- {' '.join(CODE_PATHS)}")
        return 1
    old = seal.get("raw")
    if not old:
        print("봉인에 raw 지문이 없다(옛 봉인) — 전량을 돈다.")
        return 1
    now = raw_print()
    if now is None:
        print("raw 지문을 못 쟀다 — 전량을 돈다.")
        return 1
    gone = sorted(set(old) - set(now))
    new = sorted(set(now) - set(old))
    moved = sorted(k for k in now if k in old and now[k] != old[k])
    if not (gone or new or moved):
        print(f"raw 가 봉인과 같다 — {len(now)}종 전부 일치 · 코드 {len(nc['files'])}파일 일치.")
        return 0
    print(f"raw 가 다르다 — 신설 {len(new)} · 변경 {len(moved)} · 삭제 {len(gone)}")
    for k in (new + moved + gone)[:12]:
        tag = "신설" if k in new else ("변경" if k in moved else "삭제")
        print(f"  {tag}  {k}")
    print("\n  바뀐 소스만 돌리려면:")
    print("    uv run python -m firelane.ingest --only "
          + " ".join((new + moved)[:8]))
    return 1


def ancestry(root: Path = ROOT) -> tuple[int, str]:
    """**봉인이 가리키는 커밋이 이 트리의 조상인가.** (rc, 사유)

    ★ 2026-09-21 (PLAN §13 W11-1 · DECISIONS §204 · §207 · §210). 봉인이
      `2130b14` 를 가리켰는데 그 커밋은 `refs/pull/108/head` 에만 살아 있었다.
      feat 가지 위에서 찍고 그 가지를 스쿼시했기 때문이다. `git clone` 만 한
      사람에게는 **없는 커밋**이었고 `delta` 는 「전수 재검사다」만 찍고 rc=0 이었다
      — 이틀 동안 아무것도 안 울었다.

    ★ 물음은 「`main` 의 조상인가」가 아니라 **「봉인 파일을 싣고 있는 이 트리의
      조상인가」**다. 봉인 파일은 제가 실린 트리의 역사를 가리켜야 한다. feat 가지에서
      물어도, part/infra 에서 물어도, main 에서 물어도 같은 답이 나와야 옳다.

    ★ 판정 셋 — 전부 **실패**다. 못 잰 것을 통과로 치지 않는다.
        얕은 클론     조상을 잴 역사가 없다 (CI 기본 `fetch-depth: 1`)
        없는 커밋     이 저장소가 모르는 해시다 — `2130b14` 의 모양
        조상 아님     있기는 한데 이 트리의 역사 밖이다
    """
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=root, capture_output=True,
                              text=True, check=False, stdin=subprocess.DEVNULL)

    seal = root / "data" / "dms" / SEAL
    if not seal.is_file():
        return 1, f"봉인이 없다 — {seal.relative_to(root)}"
    try:
        c = json.loads(seal.read_text(encoding="utf-8")).get("commit") or ""
    except json.JSONDecodeError as e:
        return 1, f"봉인을 못 읽었다 — {e}"
    if not re.fullmatch(r"[0-9a-f]{7,40}", c):
        return 1, f"봉인의 `commit` 이 해시 꼴이 아니다 — {c!r}"
    sh = git("rev-parse", "--is-shallow-repository")
    if sh.returncode != 0:
        return 1, "git 저장소가 아니다 — 조상을 잴 수 없다"
    if sh.stdout.strip() == "true":
        return 1, ("얕은 클론이다 — 조상을 잴 역사가 없다. "
                   "`git fetch --unshallow` 뒤 다시 돌려라")
    if git("cat-file", "-e", f"{c}^{{commit}}").returncode != 0:
        return 1, (f"봉인이 가리키는 `{c}` 가 이 저장소에 없다 — "
                   "스쿼시로 사라진 커밋이다(DECISIONS §204 의 `2130b14` 모양)")
    if git("merge-base", "--is-ancestor", c, "HEAD").returncode != 0:
        return 1, (f"봉인이 가리키는 `{c}` 가 HEAD 의 조상이 아니다 — "
                   "다른 가지에서 찍었거나 그 가지가 스쿼시됐다")
    return 0, f"봉인 `{c}` 는 HEAD 의 조상이다"


def cmd_ancestry() -> int:
    rc, why = ancestry()
    print(("✓ " if rc == 0 else "✗ ") + why)
    if rc:
        # ★ 고치는 길을 적는다. 이 단계가 빨가면 `seal`(전수 모드)은 verify 빨강 때문에
        #   못 찍는다. `--quick` 은 verify 를 안 부르므로 그 고리를 끊는다.
        print("\n  고치는 길 — part/infra 머리에서 새로 찍어 PR 로 들인다.\n"
              "    uv run python tools/dms.py seal --quick\n"
              "  릴리즈 절차(merge_batch.sh A-0)가 매번 그렇게 한다(DECISIONS §209).\n"
              "  ★ 전수 `seal` 은 이 단계가 빨간 동안 verify 빨강으로 거부된다 — `--quick` 이 답이다.")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="scan",
                    choices=["scan", "verify", "round", "mark",
                             "propose", "fill", "seal", "delta",
                             "rawdiff", "ancestry"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="이 절 ID 만")
    ap.add_argument("--quick", action="store_true",
                    help="verify.sh 대신 pytest 만. 봉인 범위가 좁아진다")
    ap.add_argument("--red", nargs="*", default=None,
                    help="아는 빨강의 이름. 적는 순간 봉인에 기록된다")
    ap.add_argument("--log", default=None,
                    help="방금 돌린 verify.sh 로그. 20분을 다시 안 쓴다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    if a.cmd == "mark":
        cmd_mark(a.ids)
        return 0

    # ★ scan() 이 필요 없다. 문서가 아니라 raw 를 본다.
    if a.cmd == "rawdiff":
        return cmd_rawdiff()

    # ★ 문서가 아니라 git 역사를 본다 — scan() 이 필요 없다.
    if a.cmd == "ancestry":
        return cmd_ancestry()

    if a.cmd == "fill":
        if not a.ids:
            print("회차 파일을 달라 — tools/dms.py fill round-1.txt --apply")
            return 2
        f = Path(a.ids[0])
        return cmd_fill(f if f.exists() else STATE / f.name, a.apply)

    data = scan()
    if a.cmd == "seal":
        return cmd_seal(data, a.quick, a.red or [],
                        Path(a.log) if a.log else None)
    if a.cmd == "delta":
        return cmd_delta(data)
    if a.cmd == "scan":
        summary(data)
        STATE.mkdir(parents=True, exist_ok=True)
        (STATE / "DMS.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        off = notation(data)
        if off:
            print(f"\n표기 갈림 {len(off)}건 — 규약은 `{CANON_NONE} …`")
            print("\n".join(off[:10]))
        return min(sum(1 for r in data["rows"] if r["state"] == "blank"), 255)

    if a.cmd == "verify":
        dead = verify(data)
        print(f"죽은 강제자 참조 {len(dead)}건")
        print("\n".join(dead))
        # ★ 2026-09-24 (DECISIONS §241). 물림 선언이 적은 **수**가 실제와 같은가.
        #   선언만으로는 하위 절이 늘어도 조용하다 — 수를 세면 늘 때 운다.
        cnt = inherit_counts(data)
        print(f"물림 수 어긋남 {len(cnt)}건")
        print("\n".join(cnt))
        return min(len(dead) + len(cnt), 255)

    if a.cmd == "propose":
        n = a.ids[0] if a.ids else "1"
        cmd_propose(data, a.size, STATE / f"round-{n}.txt", a.only)
        return 0

    cmd_round(data, a.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
