#!/usr/bin/env python3
"""
ledger_feeds.py — `feeds` 산문을 **셀 수 있는 리스트**로 바꾼다.

    uv run python tools/ledger_feeds.py            계획만
    uv run python tools/ledger_feeds.py --apply

FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다

── 왜 ─────────────────────────────────────────────────────────
`feeds` 36건이 전부 산문이다.

    feeds: 미투입 — STEP 4 관측점 랜드마크 후보
    feeds: ★ 참조 0곳. 85,380행을 ingest 하고 아무도 안 읽는다

사람은 읽지만 기계는 못 읽는다. 그래서 "지금 아무도 안 쓰는 소스가 몇
개냐" 를 물으면 눈으로 세야 하고, **2026-08-26 에 실제로 세다가 틀렸다**
— `enforcement` 를 "코드에 붙었다" 로 판정했는데 근거가 주석 한 줄이었다.

**세어야 하는 것은 필드여야 한다.** 산문은 옆에 남긴다.

── 어떻게 채우나 ──────────────────────────────────────────────
소비자는 대장 키를 **문자열로** 부른다(`ing("road_link")`). 그것을 센다.

★ 주석과 docstring 을 뺀다. `test_declaration_sync._code_only` 와 같은
  방법이고 같은 이유다 — 주석에 이름만 적어도 "쓴다" 가 되면, 그 오류는
  미참조를 **줄이는** 쪽으로 틀려 낡음을 숨긴다.

★ 산문을 버리지 않는다. `feeds_note` 로 옮긴다. 거기 적힌 "★ 참조 0곳",
  "노딩 입력", "guards CRITICAL" 은 자동으로 못 얻는 판단이다.

── grade ──────────────────────────────────────────────────────
`firelane.ledger.grade()` 가 `feeds` 를 보고 자동 산출한다.

    active      feeds 있음 · kind != raw_only
    reference   feeds 있음 · raw_only
    unused      ★ feeds 비었음. R4 대상

`grade` 를 사람이 못 쓰게 하는 것이 요점이다. 쓸 수 있으면 낙관적으로
적고, 그러면 "안 쓰이는 소스" 목록이 영원히 빈다.

IN    sources.yaml · src/ · tools/ · web/
OUT   sources.yaml
PARAM 없음
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

import yaml

# 대장 조회기는 하나다(firelane.ledger.globs).
from firelane import ledger as _led
from firelane.ledger import yaml_span as _led_yaml_span

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "sources.yaml"

SCAN = [("src", "*.py"), ("tools", "*.py"), ("web", "*.js")]
SELF = {"ledger_feeds.py", "ledger_fields.py", "ledger_schema.py",
        "migrate_names.py", "refcheck.py", "intake.py"}

#: 훑지 않는 디렉터리 — **생성물이다.**
#: ★ 2026-09-23 (DECISIONS §222-8). 종전에는 `web/**/*.js` 를 통째로 훑어
#:   `web/navi/dist/assets/index-<해시>.js` 를 **소비자로 등재했다.** 번들에는
#:   `src` 의 키 문자열이 컴파일돼 들어 있으니 형식상 「참조」가 맞다. 그런데
#:   그 파일명은 **내용 해시**라 의존성 하나만 올려도 이름이 바뀐다 — 대장이
#:   가리키는 경로가 사라지고 `doc_fsck ②` 가 운다. 실제로 maplibre 를
#:   6.9.1 → 6.11.0 으로 올린 배치가 그것으로 빨개졌다.
#: ★ 소비자는 **소스**다. 빌드 산출물을 소비자로 세면 (1) 이름이 안 고정이고
#:   (2) 같은 참조를 두 벌 세며 (3) 빌드 전에는 아예 없다.
SKIP_DIRS = ("dist", "node_modules", "__pycache__", "data", ".work")


def _is_machine_list(old: str) -> bool:
    """이 `feeds` 값이 **앞 실행이 쓴 리스트**인가 — 사람 산문이 아닌가.

    리스트는 `- <경로>` 항목만으로 이뤄진다. 산문은 `★` · 한글 · 설명이 섞인다.
    """
    # ★ 경로에 `-` 가 들어 있다(`index-EtqbR_zm.js`). 낱낱의 `-` 로 가르면 안 된다 —
    #   **줄머리의 `- `** 로만 가른다.
    items = [x.strip() for x in re.split(r"(?:^|\s)-\s+", old) if x.strip()]
    return bool(items) and all(
        re.fullmatch(r"[\w./-]+\.(py|js|ts|tsx|sh|mjs)", x) for x in items)


def _code_only(src: str) -> str:
    """주석·docstring 을 뺀 코드. 문자열 리터럴은 남긴다."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef,
                          ast.AsyncFunctionDef, ast.ClassDef)):
            b = n.body
            if (b and isinstance(b[0], ast.Expr)
                    and isinstance(getattr(b[0], "value", None), ast.Constant)
                    and isinstance(b[0].value.value, str)):
                n.body = b[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _js_code_only(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", src, flags=re.MULTILINE)


def consumers() -> dict[str, list[str]]:
    """대장 키 → 그 데이터를 쓰는 파일 목록.

    ★ 판정 축이 **셋**이다. 첫 판은 대장 키만 봤고 unused 가 22건 나왔다.
      오탐이었다 — 소비자는 이름을 세 가지로 부른다.

        ① 대장 키        ing("road_link")
        ② raw 파일명     RAW/"safety"/"safety_fire_access_...csv"
        ③ 산출물 이름    P/"poi_store.geojson"

      ②가 특히 위험하다. 대장을 안 거치므로 개명에 조용히 깨진다
      (2026-08-26, terrain.py · report.py). 그것을 "안 쓴다" 로 세면
      **깨진 코드를 못 쓰는 데이터로 오인**해 소스를 지우게 된다.

    ★ 주석·docstring 은 뺀다. 주석에 이름만 적어도 "쓴다" 가 되면 그
      오류는 미참조를 줄이는 쪽으로 틀려 낡음을 숨긴다.
    """
    d = yaml.safe_load(YAML.read_text(encoding="utf-8")) or {}
    ds = d.get("datasets") or {}
    outs = d.get("outputs") or {}
    keys = list(ds)

    # 키 → 찾을 이름 집합
    alias: dict[str, set[str]] = {}
    for k, e in ds.items():
        names = {k}
        for pat in _led.globs(e):
            stem = str(pat).rsplit("/", 1)[-1]
            names.add(stem)
            names.add(stem.split("*")[0].rstrip("_"))   # 글롭 접두
            names.add(stem.rsplit(".", 1)[0])
        for lay in ([e["layer"]] if e.get("layer") else []):
            # ★ 2026-09-17 (§181-3). 글롭 레이어(`*.shp`)는 이름이 아니다 — 별칭으로 넣으면
            #   `*.shp` 를 적은 모든 파일이 소비자가 된다(civil_office 가 inventory · ngii1k 로 셌다).
            if not any(ch in str(lay) for ch in "*?["):
                names.add(str(lay))
        alias[k] = {n for n in names if len(n) >= 4}

    # 산출물 이름 → 그것을 만든 입력 키
    for o in outs.values():
        pth = Path(str(o.get("path", ""))).name
        if not pth:
            continue
        for inp in (o.get("inputs") or []):
            if inp in alias:
                alias[inp].add(pth)

    out: dict[str, list[str]] = {k: [] for k in keys}
    for sub, pat in SCAN:
        base = ROOT / sub
        if not base.is_dir():
            continue
        for p in sorted(base.rglob(pat)):
            if p.name in SELF:
                continue       # 대장 도구는 전 키를 훑는다. 소비자가 아니다
            if set(p.relative_to(ROOT).parts) & set(SKIP_DIRS):
                continue       # 생성물은 소비자가 아니다 (§222-8)
            txt = p.read_text(encoding="utf-8", errors="ignore")
            code = _code_only(txt) if p.suffix == ".py" else _js_code_only(txt)
            rel = str(p.relative_to(ROOT))
            for k in keys:
                if any(re.search(rf"[\"\'`]{re.escape(n)}", code)
                       for n in alias[k]):
                    out[k].append(rel)
    return out


# ★ 2026-09-13. 구현은 `firelane.ledger.yaml_span` 한 곳이다. 여기와
#   짝 파일이 글자 하나까지 같았다 — `sources.yaml` 의 구조를 아는 것은
#   `ledger` 소관이고, 두 벌이면 한쪽만 고치는 날이 온다.
_span = _led_yaml_span


def _drop(body: str, field: str) -> tuple[str, str]:
    """`    field:` 와 딸린 블록을 떼어내고 (남은 본문, 뗀 값) 반환."""
    m = re.search(rf"^    {re.escape(field)}:(.*)\n((?:      .*\n|\n(?=      ))*)",
                  body, re.MULTILINE)
    if not m:
        return body, ""
    inline = m.group(1).strip()
    block = m.group(2)
    val = inline
    if block:
        txt = " ".join(x.strip() for x in block.splitlines() if x.strip())
        val = (val + " " + txt).strip() if val in ("|", ">", "") else val
    return body[:m.start()] + body[m.end():], val


def run(*, apply: bool) -> int:
    s = YAML.read_text(encoding="utf-8")
    d = yaml.safe_load(s) or {}
    ds = d.get("datasets") or {}
    cons = consumers()

    active = ref = unused = 0
    for k, e in ds.items():
        c = cons[k]
        kind = e.get("kind")
        if c:
            g = "reference" if kind == "raw_only" else "active"
            active += g == "active"
            ref += g == "reference"
        else:
            g = "unused"
            unused += 1
        mark = "★" if g == "unused" else " "
        print(f"  {mark} {k:22} {g:10} {len(c):2}곳  "
              f"{', '.join(x.split('/')[-1] for x in c[:3])}"
              f"{' …' if len(c) > 3 else ''}")

    print(f"\nactive {active} · reference {ref} · ★ unused {unused}")
    if unused:
        print("  unused 는 R4 대상이다 — raw 에 둘 이유를 대거나 retired 로 내린다")

    if not apply:
        print("\n아무것도 바꾸지 않았다.  --apply 로 적용한다.")
        return 0

    for k in ds:
        st, en, body = _span(s, k)
        if st < 0:
            continue
        nb, old = _drop(body, "feeds")
        nb, _ = _drop(nb, "feeds_note")
        c = cons[k]
        add = "    feeds:" + ("\n" + "\n".join(f"      - {x}" for x in c)
                              if c else " []") + "\n"
        if old and not _is_machine_list(old):
            # ★ 산문을 버리지 않는다. "★ 참조 0곳" · "노딩 입력" 같은
            #   판단은 자동으로 못 얻는다.
            # ★ 2026-09-23 (DECISIONS §222-8). **이미 리스트인 것은 산문이 아니다.**
            #   두 번째 `--apply` 에서 앞 실행이 쓴 리스트를 「산문」으로 보고 그대로
            #   `feeds_note` 에 밀어 넣었고, 그 안에 옛 경로(빌드 해시 파일명)가 화석으로
            #   남아 `doc_fsck ②` 가 없는 파일을 가리킨다고 울었다. 기계가 쓴 것을
            #   사람 판단으로 보존하면 그때부터 그 칸은 **낡기만 한다.**
            q = old.replace("'", "''")
            add += f"    feeds_note: '{q}'\n"
        s = s[:st] + add + nb + s[en:]

    yaml.safe_load(s)
    YAML.write_text(s, encoding="utf-8")
    print("\n적용 · YAML 파싱 OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    return run(apply=ap.parse_args().apply)


if __name__ == "__main__":
    sys.exit(main())
