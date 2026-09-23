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


# ── raw 지문 기억표 ────────────────────────────────────────────
# ★ 2026-09-23 (DECISIONS §224-2). **봉인지가 빌드만 아끼고 판정은 안 아꼈다.**
#   `check()` 는 봉인이 맞든 틀리든 `raw_print(hits)` 를 부르고, 그것이 그 소스의
#   원천 파일을 **통째로 다시 읽어** 해시했다. `[SEALED] 다시 빌드하지 않는다` 를
#   찍기 위해 raw 2.5GB 를 읽은 것이다. 2026-09-23 에 8GB WSL 이 거기서
#   `Errno 12` 로 죽었다 — 봉인은 일치했는데 죽었다.
#
#   봉인지의 값어치는 **「판정이 빌드보다 싸다」** 에 있다. 판정 비용이 원천
#   크기에 비례하면 그 값어치가 없다. 같은 병을 ①(--split)으로 한 번,
#   ②(샤드 봉인)로 한 번 막았는데 **판정 경로만 남아 있었다.**
#
# ★ 열쇠는 `(크기, mtime_ns)` 다. `data/raw` 는 **불변**이 이 저장소의 원칙 1
#   이고(ingest.py 머리말) 어떤 코드도 거기에 쓰지 않는다. 그러므로 크기와
#   수정 시각이 같으면 내용이 같다 — 사람이 일부러 바이트를 바꾸면서 둘 다
#   맞추지 않는 한. 그 경우까지 잡는 것은 `tools/acquire.py` 의 원천 대장
#   (raw 전수 sha256)이 맡는다. **여기는 봉인 판정이지 위변조 감사가 아니다.**
#
# ★ 하나라도 어긋나면 **그 파일만** 다시 읽는다. 캐시 전체를 버리지 않는다.
# ★ 캐시가 없거나 깨졌으면 그냥 전부 읽는다 — 판정은 같고 느릴 뿐이다.
#   **캐시는 답을 바꾸지 않는다.** 답을 바꾸면 그것은 캐시가 아니라 우회다.
_RAWCACHE: dict[str, list] | None = None


def _rawcache_file() -> Path:
    from firelane.paths import PROCESSED

    return PROCESSED / ".rawprint.json"


def _rawcache() -> dict[str, list]:
    global _RAWCACHE
    if _RAWCACHE is None:
        try:
            got = json.loads(_rawcache_file().read_text(encoding="utf-8"))
            _RAWCACHE = got if isinstance(got, dict) else {}
        except (OSError, ValueError):
            _RAWCACHE = {}
    return _RAWCACHE


def _rawcache_save() -> None:
    if _RAWCACHE is None:
        return
    f = _rawcache_file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(_RAWCACHE, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass                    # 못 써도 판정은 옳다. 다음 실행이 느릴 뿐이다


def raw_one(p: Path) -> str:
    """파일 하나의 raw 지문(16자). `(크기, mtime_ns)` 가 같으면 안 읽는다."""
    st = p.stat()
    key = str(p.resolve())
    hit = _rawcache().get(key)
    if (isinstance(hit, list) and len(hit) == 3
            and hit[0] == st.st_size and hit[1] == st.st_mtime_ns):
        return str(hit[2])
    got = sha256(p)[:16]
    _rawcache()[key] = [st.st_size, st.st_mtime_ns, got]
    return got


def raw_print(hits: list[Path]) -> str | None:
    if not hits or not all(Path(h).is_file() for h in hits):
        return None
    before = dict(_rawcache())
    out = ",".join(raw_one(Path(h)) for h in sorted(hits))
    if _rawcache() != before:
        _rawcache_save()
    return out


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


def reseal_code(records: list[dict], cfg: dict, out_dir: Path, code: str,
                paths_for) -> tuple[list[str], list[str]]:
    """`code` 칸**만** 지금 코드 지문으로 고친다. (고친 key, 못 고친 key).

    ── 왜 있나 (2026-09-23 · DECISIONS §224-2) ──────────────────────
    `code` 는 ingest 가 import 하는 firelane 모듈 전부의 로직 지문이다. 이미
    두 겹으로 좁혀 놨다 — 주석 · docstring 을 뺀 AST 로 재고(`logic_print`),
    봉인 로직 자신은 아예 뺀다(`NOT_PRODUCERS`, §165-8). 그런데도 **ingest 본체나
    `guards` 를 한 줄 고치면 65종이 전부 찢어진다.** 산출물을 한 바이트도 바꾸지
    않는 변경(안내 문구 · 종료코드 · 새 플래그)이어도 그렇다.

    이 8GB 기계에서 전량 재빌드는 `ngii_road` 에서 거의 반드시 죽는다(§165).
    즉 **ingest 를 고칠 수 없는 구조**였다. 도구를 못 고치면 결함도 못 고친다.
    좁히는 길(로직 지문 · 제외 목록)은 이미 다 썼으므로, 남은 길은 **사람이
    판단해서 받아주는 문**이다 — `cfg` 칸의 `cfg_print_legacy`, `out` 칸의
    `reseal_out` 과 같은 자리.

    ★ 공짜로 열어주지 않는다. 여기서 고치는 것은 **raw 와 out 이 둘 다 봉인과
      같은** 레코드뿐이다. 그 둘이 같다는 것은 「같은 입력으로 만든 같은
      산출물이 지금 디스크에 있다」 는 뜻이고, 그러면 코드가 무엇을 하든
      **이번 판정에 쓰인 결과는 그 산출물**이다.
    ★ 그래도 **판단은 사람이 한다.** 코드 변경이 산출물을 바꿀 수 있는
      것이었다면 out 이 이미 달라졌거나, 다음 전량에서 달라진다. 이 함수는
      「지금 디스크의 산출물이 봉인과 같다」 만 말한다 — `--stamp` 와 같은 급이다.
    ★ 옛 지문 → 새 지문을 **화면에 찍는다**(호출부). 대장 레코드에 칸을 더하지
      않는다 — 봉인지는 네 칸이고, 다섯 번째 칸은 다음 사람이 그것도 봉인의
      일부라고 읽는다. 무엇을 받아줬는지는 DECISIONS 가 든다.
    """
    fixed, skipped = [], []
    for r in records:
        s = r.get("seal") if isinstance(r, dict) else None
        if r.get("status") != "OK" or not isinstance(s, dict) \
                or not all(k in s for k in ("raw", "cfg", "code", "out")):
            continue
        key = r["key"]
        if s["code"] == code:
            continue                                   # 이미 같다
        try:
            hits = paths_for(key, cfg["datasets"][key])
        except Exception:                              # noqa: BLE001
            skipped.append(key); continue
        if raw_print(hits) != s["raw"] or out_print(out_dir, list(s["out"])) != s["out"]:
            skipped.append(key); continue              # 입력이나 산출물이 달라졌다 — 다시 빌드해야 한다
        s["code"] = code
        fixed.append(key)
    return fixed, skipped


def reseal_out_cli(man_path: Path, out_dir: Path, manifest) -> int:
    """`ingest --reseal-out` 의 본문. 파이프라인이 terrain 뒤에 부른다."""
    if not man_path.exists():
        return 0
    doc = manifest.read(man_path)
    fixed, missing = reseal_out(doc.get("datasets", []), out_dir)
    wrote = manifest.write_stable(man_path, doc)
    print(f"샤드 봉인지 out 갱신 {len(fixed)}종"
          + (f" ({', '.join(fixed)})" if fixed else "")
          + (f" · 산출물 없음 {len(missing)}종: {', '.join(missing)}" if missing else "")
          + ("" if wrote else " · 대장 불변"))
    return 0


def reseal_code_cli(man_path: Path, cfg: dict, out_dir: Path, code: str,
                    paths_for, manifest) -> int:
    """`ingest --reseal-code` 의 본문. 대장을 읽고 고치고 적고 화면에 남긴다.

    ★ ingest 본체가 아니라 여기 산다. 봉인지를 아는 것은 이 모듈이고,
      ingest 는 그것을 부를 뿐이다 — 봉인 규칙이 두 파일에 흩어지지 않는다.
    """
    if not man_path.exists():
        print("★ _manifest.json 이 없다. 고칠 봉인지가 없다.")
        return 0
    doc = manifest.read(man_path)
    fixed, skipped = reseal_code(doc.get("datasets", []), cfg, out_dir, code, paths_for)
    wrote = manifest.write_stable(man_path, doc)
    print(f"샤드 봉인지 code 갱신 {len(fixed)}종 → {code}"
          + (f"\n  고침  {', '.join(fixed)}" if fixed else "")
          + (f"\n  거절  {len(skipped)}종 — raw 나 산출물이 봉인과 다르다: "
             f"{', '.join(skipped)}" if skipped else "")
          + ("" if wrote else "\n  대장 불변"))
    if skipped:
        print("  ★ 거절된 것은 **다시 빌드해야 한다.** 봉인은 그래서 있다.")


def _short(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
