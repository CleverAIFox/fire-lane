"""
shardseal.py — ingest 샤드(소스 하나)의 봉인지. **넷이 전부 같을 때만 재사용한다.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-14 에 OOM 을 두 갈래로 막기로 정했다. ① 소스마다 자식 프로세스로 쪼갠다
(`--split`) ② 입력이 봉인과 같으면 다시 만들지 않는다. **①만 들어갔다.** ingest 는
매 실행 65종을 무조건 전부 다시 빌드했고, ②는 `verify.sh` 에서 파이프라인을
**통째로** 건너뛰는 모양으로만 들어갔다. 통째 생략이 OOM 을 가렸고, 2026-09-16 에
코드 변경도 전량을 돌게 하자(DECISIONS §164) `ngii_road` 가 다시 `Errno 12` 로 죽었다.
이 8GB 기계에서 `ngii_road` 는 **다시 빌드하면 거의 반드시 죽는다.**

그래서 봉인 단위를 파이프라인 전체에서 **소스 하나**로 내린다. 다시 빌드하는 것은
봉인지가 찢어진 소스뿐이다. raw 가 안 바뀌는 소스는 영원히 다시 안 돈다.

── 봉인지 네 칸 ────────────────────────────────────────────────
    raw    이 소스가 읽는 실물 파일의 sha256[:16]        paths_for()
    cfg    sources.yaml 의 이 소스 항목 + 전역 설정       datasets 밖 전부 + 자기 항목
    code   ingest 가 **실제로 import 하는** firelane 모듈   AST 로 닫힘을 계산 · uv.lock
    out    산출물 파일 각각의 sha256[:16]                 대장의 outputs

★ **모르면 안 건너뛴다.** 칸 하나라도 없거나(옛 대장), 못 재거나, 다르면 다시 빌드한다.
★ `code` 를 손 목록으로 두지 않는다. `segments` 쪽을 고쳐도 ingest 샤드는 안 찢어지고,
  ingest 가 쓰는 `guards` 를 고치면 전부 찢어진다 — 그 경계를 import 가 정한다.
★ `out` 을 보는 이유 — 2026-09-16 에 FAIL 격리가 옆 소스 산출물을 `.stale_` 로
  개명했다. 대장은 멀쩡한데 파일이 없는 샤드를 재사용하면 하류가 옛 것도 아닌
  **빈 것**을 읽는다. 샤드를 재사용하기 전에 실물을 대조한다.

IN    sources.yaml · src/firelane/**.py · uv.lock · raw 실물 · data/processed 산출물
OUT   대장 레코드의 `seal` 칸 (ingest 가 쓴다)
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from firelane.hashing import sha256
from firelane.paths import ROOT

PKG = ROOT / "src" / "firelane"


def _module_file(dotted: str) -> Path | None:
    """`firelane.a.b` → 파일. 패키지면 `__init__.py`. 없으면 None."""
    parts = dotted.split(".")
    if parts[0] != "firelane":
        return None
    base = PKG.joinpath(*parts[1:])
    for cand in (base.with_suffix(".py"), base / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def code_closure(start: str = "firelane.ingest") -> list[Path]:
    """`start` 가 import 하는 firelane 모듈 전부(자기 포함). 함수 안 늦은 import 도 센다."""
    seen: dict[str, Path] = {}
    todo = [start]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        f = _module_file(name)
        if f is None:
            continue
        seen[name] = f
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                todo += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                todo.append(node.module)
                # `from firelane import ledger` — 이름이 모듈일 수 있다
                todo += [f"{node.module}.{a.name}" for a in node.names]
    return sorted(set(seen.values()))


def logic_print(p: Path) -> str:
    """파일의 **로직** 지문. 주석 · docstring 을 뺀 AST 로 잰다.

    ★ 2026-09-16. 바이트로 재면 머리말 한 줄에 40 샤드가 전부 찢어지고, 이 기계에서는
      그것이 곧 `ngii_road` OOM 이다. 산출물을 바꿀 수 있는 것은 로직뿐이다.
    """
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return _short(ast.dump(tree, include_attributes=False))


# ★ 봉인 로직 자신은 산출물을 만들지 않는다. 넣으면 봉인 규칙을 고칠 때마다 40 샤드가
#   찢어지고, 이 기계에서는 그것이 `ngii_road` OOM 이다(DECISIONS §165-8).
NOT_PRODUCERS = ("shardseal.py",)


def code_print(start: str = "firelane.ingest") -> str:
    lines = [f"{p.relative_to(ROOT).as_posix()}\0{logic_print(p)}" for p in code_closure(start)
             if p.name not in NOT_PRODUCERS]
    lock = ROOT / "uv.lock"
    if lock.is_file():
        lines.append(f"uv.lock\0{sha256(lock)[:16]}")   # geopandas 판이 바뀌면 산출물도 바뀐다
    return _short("\n".join(lines))


# ★ 2026-09-16. cfg 칸의 전역은 **ingest 산출에 닿는 최상위 키만**이다. 종전에는
#   datasets 밖 전부였고, `outputs.<x>.consumers` 에 테스트 파일 한 줄을 적는 것만으로
#   40 샤드가 찢어질 뻔했다 — 이 기계에서 그것은 OOM 이다(DECISIONS §166-3).
#   ingest 가 새 최상위 키를 읽기 시작하면 test_ingest_global_keys_are_declared 가 운다.
INGEST_GLOBAL = ("target_area", "bbox_4326", "standard_crs", "scopes", "layers", "raw_only")


# ★ 2026-09-22 (DECISIONS §216-1). 자기 항목에서도 **산출에 안 닿는 서술 칸**은 뺀다.
#   종전에는 항목 전체를 쟀고, `feeds` 에 소비자 한 줄(`publish_navi.py`)을 적은 것만으로
#   ngii1k · node_link · node_point · turn_restriction 넷이 찢어져 다시 빌드됐다. 그중
#   turn_restriction 이 실패해 verify 가 빨개졌다 — 전역 칸에서 §166-3 이 막은 사고가
#   자기 항목 칸에서 그대로 났다. 목록은 **빼는 쪽**으로 둔다: 모르는 칸은 여전히 잰다
#   (틀리면 한 번 더 빌드할 뿐이고, 반대로 틀리면 낡은 산출물을 재사용한다).
DOC_KEYS = frozenset({
    "feeds", "feeds_note", "feeds_why", "used_for", "note", "authority",
    "what", "what_fix", "read_note",
    "schema",        # AUTO — ledger_schema.py 가 raw 에서 뽑는다. raw 칸이 이미 잰다
})


def cfg_print(cfg: dict, key: str) -> str:
    glob = {k: cfg.get(k) for k in INGEST_GLOBAL}
    own = cfg.get("datasets", {}).get(key)
    if isinstance(own, dict):
        own = {k: v for k, v in own.items() if k not in DOC_KEYS}
    return _short(json.dumps({"global": glob, "own": own}, sort_keys=True,
                             ensure_ascii=False, default=str))


def cfg_print_legacy(cfg: dict, key: str) -> str:
    """2026-09-22 이전 판 — 자기 항목 전체. 옛 봉인지를 **다시 빌드 없이** 받으려고 남긴다."""
    glob = {k: cfg.get(k) for k in INGEST_GLOBAL}
    own = cfg.get("datasets", {}).get(key)
    return _short(json.dumps({"global": glob, "own": own}, sort_keys=True,
                             ensure_ascii=False, default=str))


def raw_print(hits: list[Path]) -> str | None:
    if not hits or not all(Path(h).is_file() for h in hits):
        return None
    return ",".join(sha256(h)[:16] for h in sorted(hits))


def gpkg_print(p: Path) -> str:
    """GeoPackage 의 **내용** 지문. 쓸 때마다 바뀌는 칸을 뺀다.

    ★ 2026-09-16 실측. 같은 데이터를 1초 간격으로 두 번 쓰면 바이트가 다르다 —
      `gpkg_contents.last_change` 에 쓴 시각이 들어간다. terrain 은 매 실행 z 를
      덧쓰므로 바이트 지문이면 봉인지가 **매 실행** 찢어지거나 다시 봉인된다.
      R-tree 색인 테이블(`rtree_*`)은 기하에서 파생이라 뺀다.
    """
    import sqlite3
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        lines = []
        try:
            tables = sorted(r[0] for r in con.execute(
                "select name from sqlite_master where type='table'"))
        except sqlite3.DatabaseError:
            # 깨졌거나 gpkg 가 아니다. 바이트로 잰다 — 정상 파일과 달라 봉인지가 찢어진다
            return "bytes:" + sha256(p)[:16]
        for t in tables:
            if t.startswith(("rtree_", "sqlite_")):
                continue
            cols = [r[1] for r in con.execute(f'pragma table_info("{t}")')]
            keep = [c for c in cols if not (t == "gpkg_contents" and c == "last_change")]
            sel = ", ".join(f'"{c}"' for c in keep)
            try:
                rows = con.execute(f'select {sel} from "{t}" order by rowid').fetchall()
            except sqlite3.OperationalError:
                rows = sorted(con.execute(f'select {sel} from "{t}"').fetchall(), key=repr)
            lines.append(f"{t}\0{keep}\0{rows!r}")
        return _short("\n".join(lines))
    finally:
        con.close()


def out_print(out_dir: Path, names: list[str]) -> dict[str, str] | None:
    got = {}
    for n in names:
        p = Path(out_dir) / n
        if not p.is_file():
            return None
        got[n] = gpkg_print(p) if p.suffix == ".gpkg" else sha256(p)[:16]
    return got


def make(cfg: dict, key: str, hits: list[Path], out_dir: Path, outputs: list[str],
         code: str) -> dict | None:
    """새 봉인지. 칸 하나라도 못 재면 None — 봉인하지 않는다."""
    raw = raw_print(hits)
    out = out_print(out_dir, outputs)
    if raw is None or out is None or not outputs:
        return None
    return {"raw": raw, "cfg": cfg_print(cfg, key), "code": code, "out": out}


def check(prev: dict | None, cfg: dict, key: str, hits: list[Path], out_dir: Path,
          code: str) -> tuple[bool, str]:
    """이전 레코드의 봉인지가 지금과 같은가. (재사용 가능?, 사유)."""
    if not prev or prev.get("status") != "OK":
        return False, "지난 결과가 OK 가 아니다"
    s = prev.get("seal")
    if not isinstance(s, dict) or not all(k in s for k in ("raw", "cfg", "code", "out")):
        return False, "봉인지가 없다(옛 대장)"
    if s["code"] != code:
        return False, "ingest 코드가 바뀌었다"
    if s["cfg"] != cfg_print(cfg, key):
        # ★ 옛 판 지문이면 받고 **새 판으로 고쳐 적는다**(재빌드 없음). 한 번 지나면 서술 칸을
        #   고쳐도 안 찢어진다. prev 는 ingest 가 그대로 대장에 되쓰는 레코드다.
        if s["cfg"] != cfg_print_legacy(cfg, key):
            return False, "sources.yaml 설정이 바뀌었다"
        s["cfg"] = cfg_print(cfg, key)
    raw = raw_print(hits)
    if raw is None:
        return False, "raw 를 못 쟀다"
    if s["raw"] != raw:
        return False, "raw 가 바뀌었다"
    out = out_print(out_dir, list(s["out"]))
    if out is None:
        return False, "산출물 파일이 없다"
    if out != s["out"]:
        return False, "산출물이 봉인과 다르다"
    return True, "봉인 일치"


def reseal_out(records: list[dict], out_dir: Path) -> tuple[list[str], list[str]]:
    """봉인지가 있는 레코드의 `out` 칸만 지금 실물로 고친다. (고친 key, 못 고친 key).

    ★ 파이프라인 **하류가 ingest 산출물을 덧쓴 뒤**에만 부른다(terrain 의 z).
      raw · cfg · code 는 건드리지 않는다. 그 셋이 "무엇으로 만들었나" 의 증거이고,
      이 함수는 "하류가 덧쓴 결과가 지금 실물이다" 만 적는다.
    ★ 파일이 하나라도 없으면 그 레코드는 안 고친다 — 다음 실행에서 찢어져야 한다.
    """
    fixed, missing = [], []
    for r in records:
        s = r.get("seal") if isinstance(r, dict) else None
        if r.get("status") != "OK" or not isinstance(s, dict) or "out" not in s:
            continue
        now = out_print(out_dir, list(s["out"]))
        if now is None:
            missing.append(r["key"])
        elif now != s["out"]:
            s["out"] = now
            fixed.append(r["key"])
    return fixed, missing


def _short(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
