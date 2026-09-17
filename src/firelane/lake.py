#!/usr/bin/env python3
"""
lake.py — 레이크 해석기. **대장 + 디스크 → 파일마다 주인 · 층 · 상태.**

    uv run python -m firelane.lake scan            층 × 상태 표 (읽기만)
    uv run python -m firelane.lake scan --json F   행 전부를 F 에
    uv run python -m firelane.lake gate            이동 · 삭제 전 관문. 막히면 종료코드 1
    uv run python -m firelane.lake plan F --out D  계획표를 레이크에서 다시 재고 mv · rm 명령을 D 에 쓴다

── 왜 생겼나 ──────────────────────────────────────────────────
2026-09-17 (DECISIONS §172-5 · §173-4 · §174). 파일의 주인을 다섯 곳이 제각각
판정했다 — `ledger.globs`(raw 활성) · `acquire.retired_names`(폐기 — raw 에서만) ·
`_prep.json`(norm) · `lakecheck.disposed`(landing) · `lake_scan` S8(격리 — raw 에서만).
같은 파일을 두 곳이 다르게 읽은 날 살아 있는 raw 둘이 격리됐고, 다른 날
격리 7건이 "근거 없음" 으로 나왔다. 이 모듈이 **하나뿐인 판정처**다.

── 상태 ───────────────────────────────────────────────────────
    정상      있어야 할 층에 주인이 하나
    자리틀림  주인은 있는데 층이 틀렸다 (폐기본이 raw · 활성본이 격리 등)
    주인없음  대장 · 기록 · 처분 어디에도 없다
    두주인    같은 구체성의 주장이 둘 이상 — 이름 대 이름 · 글롭 대 글롭 (§172-5 의 형태)
              이름으로 적은 주장이 글롭 주장을 이긴다(`_pick`)
    결손      대장이 이름으로 주장하는데 레이크 어디에도 없다
    선언밖    선언된 층 밖의 폴더 · 레이크 루트 파일
    폐지층    §173-2 에서 없애기로 한 자리(_quarantine · _meta) — 옮길 대상
    기록      층을 설명하는 사람 문서(QUARANTINE.md)

── 관문 ───────────────────────────────────────────────────────
`gate()` 는 두주인 · 주인없음 · 선언밖 · 폐지층 이 하나라도 있거나, 대장의 폐기 항목이
글롭으로 파일을 가리키면 **이동 · 삭제를 거부한다.** 알리는 검사가 아니라
먼저 막는 관문이다(§173-4 ①). 계획표가 처분하는 경로는 `planned` 로 넘겨 뺀다 —
그것을 치우려는 계획이 그것 때문에 막히면 안 된다.

★ 2026-09-17 (§176). 폐지층이 막는 쪽으로 옮겼다. `_quarantine` 을 비운 뒤 누가
  다시 쓰면(acquire `--quarantine` 은 아직 그 자리에 쓴다 — PLAN #56) verify 가 운다.

★ 층 목록 `LAYERS` 는 §173-2 목표 구조다. 대장 `layers` 에 retired 가 들어가는
  것은 레이크를 세운 뒤다(PLAN 「대장 · SSD 디렉토리 구조와 해석기 하나」) —
  그때 이 상수를 대장에서 읽도록 바꾼다.
★ sha 는 여기서 재지 않는다. 3.7GB 를 매 해석마다 읽지 않는다. 사본 판정은
  계획 단계가 레이크 기계에서 한 번 잰다.

IN    sources.yaml(datasets · retired · landing_disposition) · data/_prep.json · FIRE_LANE_DATA
OUT   없음 (scan --json 만 지정한 파일)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from firelane import ledger, paths

LAYERS = ("landing", "raw", "norm", "retired", "interim")   # §173-2
ABOLISHED = ("_quarantine",)                                # §173-2 — retired 로 흡수
RECORD_NAMES = ("QUARANTINE.md",)
STATES = ("정상", "자리틀림", "주인없음", "두주인", "결손", "선언밖", "폐지층", "기록")
BLOCKING = ("두주인", "주인없음", "선언밖", "폐지층")


@dataclass(frozen=True)
class Row:
    rel: str                     # 레이크 루트 상대 (예: raw/safety/x.csv)
    layer: str                   # 첫 조각. 루트 파일은 ""
    state: str
    owners: tuple[str, ...] = ()  # "datasets:<key>" · "retired:<key>" · "prep" · "landing:<file>"
    note: str = ""


@dataclass
class Claims:
    active: dict[str, list[str]] = field(default_factory=dict)    # key → raw 상대 패턴
    retired: dict[str, list[str]] = field(default_factory=dict)
    retired_globbed: list[str] = field(default_factory=list)      # 글롭으로 가리키는 폐기 키
    disposed: list[str] = field(default_factory=list)             # landing 처분 패턴(사유 있는 것)
    layer: dict[str, str] = field(default_factory=dict)           # 활성 key → 원본 안 레이어


def _is_glob(p: str) -> bool:
    return any(c in p for c in "*?[")


def claims(y: dict) -> Claims:
    """대장에서 주장을 뽑는다. **패턴 해석은 `ledger.globs` 하나를 쓴다.**"""
    c = Claims()
    for k, e in (y.get("datasets") or {}).items():
        c.active[k] = ledger.globs(e or {})
        if (e or {}).get("layer"):
            c.layer[k] = str(e["layer"])
    for k, e in (y.get("retired") or {}).items():
        pats = ledger.globs(e or {})
        if pats:
            c.retired[k] = pats
            if any(_is_glob(p) for p in pats):
                c.retired_globbed.append(k)
    for it in ((y.get("landing_disposition") or {}).get("items") or []):
        if isinstance(it, dict) and it.get("file") and str(it.get("why") or "").strip():
            c.disposed.append(str(it["file"]))
    return c


def _match(sub_rel: str, pats: list[str]) -> bool:
    """층 안 상대경로가 raw 상대 패턴에 맞는가. `**/` 는 0단 이상."""
    for p in pats:
        if not _is_glob(p):
            if sub_rel == p:
                return True
            continue
        if fnmatch.fnmatchcase(sub_rel, p):
            return True
        if p.startswith("**/") and fnmatch.fnmatchcase(sub_rel, p[3:]):
            return True
    return False


def _owners(sub_rel: str, table: dict[str, list[str]], tag: str) -> list[tuple[str, bool]]:
    """(주인, 이름으로 주장했나). 글롭 주장은 False."""
    if ledger.is_acquisition_meta(sub_rel):
        return []
    out = []
    for k, pats in table.items():
        if sub_rel in pats:
            out.append((f"{tag}:{k}", True))
        elif _match(sub_rel, [q for q in pats if _is_glob(q)]):
            out.append((f"{tag}:{k}", False))
    return out


def _pick(cands: list[tuple[str, bool]]) -> tuple[str, ...]:
    """주장이 여럿이면 **이름으로 적은 쪽이 글롭을 이긴다.**

    ★ 2026-09-17 모의 레이크 실측. 활성 `fire_station` 은 stem 글롭
      `**/safety_firestation_*` 로 주장하고, 폐기 `firestation_kr_20250701` 은
      파일 이름으로 주장한다. 둘을 같은 무게로 세면 격리된 폐기본 셋이
      전부 두주인이 된다 — §172-5 를 뒤집어 놓은 형태다. 파일 단위 주인이
      패턴 주인보다 구체적이다. 같은 구체성에서 둘 이상이면 그때가 두주인이다.
    """
    lit = [o for o, is_lit in cands if is_lit]
    if lit:
        return tuple(lit)
    return tuple(o for o, _ in cands)


def _shared(own: tuple[str, ...], c: Claims) -> bool:
    """활성 여럿이 **한 원본의 서로 다른 레이어**를 주장하는가 — 그것은 공유다.

    ★ 2026-09-17 모의 레이크 실측. 도로명주소 전자지도 zip 하나를 `road_link` ·
      `road_rw` · `building` 등 여섯이, 표준노드링크 zip 하나를 셋이 쓴다. 각자
      `layer` 가 다르다. 이것을 두주인으로 세면 관문이 영영 안 열린다.
      레이어를 안 적었거나 같은 레이어를 둘이 주장하면 그때는 두주인이다.
    """
    keys = [o.split(":", 1)[1] for o in own]
    if len(keys) < 2 or any(not o.startswith("datasets:") for o in own):
        return False
    lays = [c.layer.get(k) for k in keys]
    return all(lays) and len(set(lays)) == len(lays)


def resolve(y: dict, root: Path, prep: dict | None = None) -> list[Row]:
    """레이크 루트(`FIRE_LANE_DATA`) 아래 모든 파일을 판정한다. **읽기만 한다.**"""
    c = claims(y)
    # ★ `_prep.json` 의 키는 raw 상대경로다. 변환기가 확장자를 바꾸면(관리카드 pdf → csv)
    #   norm 실물은 `dst` 에 있다(§172-3). 키만 보면 그 넷이 주인없음이 된다.
    prep_files = {str((v or {}).get("dst") or k)
                  for k, v in ((prep or {}).get("files") or {}).items()}
    rows: list[Row] = []
    seen_literal: set[str] = set()

    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(root).as_posix()
        parts = rel.split("/")
        layer = parts[0] if len(parts) > 1 else ""
        sub = "/".join(parts[1:])

        if not layer:
            rows.append(Row(rel, "", "선언밖", note="레이크 루트 파일"))
            continue
        if layer not in LAYERS and layer not in ABOLISHED:
            rows.append(Row(rel, layer, "선언밖", note=f"선언되지 않은 폴더 `{layer}`"))
            continue
        if ledger.is_acquisition_meta(rel):
            rows.append(Row(rel, layer, "폐지층", note="_meta 사이드카 — 대장 note 로 옮기고 지운다(§173-2)"))
            continue

        own = _pick(_owners(sub, c.active, "datasets") + _owners(sub, c.retired, "retired"))
        act = [o for o in own if o.startswith("datasets:")]
        ret = [o for o in own if o.startswith("retired:")]
        seen_literal.add(sub)

        if layer == "raw":
            if len(own) > 1 and _shared(own, c):
                rows.append(Row(rel, layer, "정상", own, f"한 원본 · 레이어 {len(own)}"))
            elif len(own) > 1:
                rows.append(Row(rel, layer, "두주인", own,
                                "같은 구체성의 주장이 둘 이상이다"))
            elif act:
                rows.append(Row(rel, layer, "정상", tuple(act)))
            elif ret:
                rows.append(Row(rel, layer, "자리틀림", tuple(ret), "폐기본이 raw 에 있다 → retired"))
            else:
                rows.append(Row(rel, layer, "주인없음"))
        elif layer == "norm":
            st = "정상" if sub in prep_files else "주인없음"
            rows.append(Row(rel, layer, st, ("prep",) if st == "정상" else ()))
        elif layer in ("retired", *ABOLISHED):
            if parts[-1] in RECORD_NAMES:
                rows.append(Row(rel, layer, "기록" if layer == "retired" else "폐지층",
                                note="층 설명 문서" + ("" if layer == "retired" else " → retired")))
            elif len(own) > 1:
                rows.append(Row(rel, layer, "두주인", own, "같은 구체성의 주장이 둘 이상이다"))
            elif ret:
                st = "정상" if layer == "retired" else "폐지층"
                rows.append(Row(rel, layer, st, tuple(ret),
                                "" if st == "정상" else "은퇴 사유 있음 → retired"))
            elif act:
                rows.append(Row(rel, layer, "자리틀림", tuple(act), "활성본이 raw 밖에 있다 → raw"))
            else:
                rows.append(Row(rel, layer, "주인없음" if layer == "retired" else "폐지층",
                                note="" if layer == "retired" else "★ 은퇴 사유 없음 — 사람이 정한다"))
        elif layer == "landing":
            hit = [f for f in c.disposed if fnmatch.fnmatchcase(parts[-1], f)]
            rows.append(Row(rel, layer, "정상" if hit else "주인없음",
                            tuple(f"landing:{h}" for h in hit)))
        else:  # interim — 재생성 가능. 주인이 없어도 된다
            rows.append(Row(rel, layer, "정상", note="재생성 가능"))

    # 결손 — 이름으로(글롭 아닌) 주장했는데 어느 층에도 없다
    for tag, table in (("datasets", c.active), ("retired", c.retired)):
        for k, pats in table.items():
            for pat in pats:
                if not _is_glob(pat) and pat not in seen_literal:
                    rows.append(Row(f"?/{pat}", "", "결손", (f"{tag}:{k}",)))
    return rows


def gate(y: dict, rows: list[Row], planned: tuple[str, ...] = ()) -> list[str]:
    """이동 · 삭제를 막는 사유. 빈 리스트여야 움직인다. `planned` 는 계획이 처분하는 경로 접두."""
    why = [f"{r.state}  {r.rel}  {' · '.join(r.owners) or r.note}"
           for r in rows if r.state in BLOCKING
           and not any(r.rel == p or r.rel.startswith(p.rstrip("/") + "/") for p in planned)]
    why += [f"폐기 글롭  retired:{k} — 파일 이름으로 적어라(§173-2)"
            for k in claims(y).retired_globbed]
    return why


# ── 계획표 검증 → 명령 ────────────────────────────────────────────
# ★ 2026-09-17 (§176). 계획표(보조 스크립트가 낸 판정)를 **믿지 않는다.** 레이크 기계에서
#   조건을 다시 재고, 전부 맞을 때만 mv · rm 명령을 파일로 쓴다. 명령은 사람이 친다(§10 적용 원형).
#   조건은 **지금 상태**로 잰다 — 이동 전이면 원천에서, 이동 뒤면 목적지에서 찾는다.
#   그래서 이동 앞뒤로 두 번 돌려도 같은 답이 나온다.
PLAN_ACTIONS = ("보존", "삭제·사본", "삭제·압축재생", "삭제·스냅숏", "삭제·재생성")


@dataclass
class PlanResult:
    fails: list[str] = field(default_factory=list)
    moves: list[tuple[str, str]] = field(default_factory=list)     # (원천 절대, 목적지 절대)
    deletes: list[str] = field(default_factory=list)               # 파일 절대
    delete_dirs: list[str] = field(default_factory=list)           # 비면 지울 폴더 절대
    counts: Counter = field(default_factory=Counter)


def _sha(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(4 << 20):
            h.update(b)
    return h.hexdigest()


def read_plan(tsv: Path) -> list[dict]:
    import csv
    with tsv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    bad = sorted({r["action"] for r in rows} - set(PLAN_ACTIONS))
    if bad:
        raise ValueError(f"계획표에 모르는 action: {bad}")
    return rows


def retired_dst(row: dict) -> str:
    """보존 목적지 — 보조 스크립트가 제안한 `data/archive/…` 를 `retired` 로 읽는다(§173-1)."""
    d = row["dst_or_reason"]
    for old in ("data/archive/", "data/retired/"):
        if d.startswith(old):
            return "retired/" + d[len(old):]
    raise ValueError(f"보존 목적지가 data/archive · data/retired 아래가 아니다: {d}")


def verify_plan(rows: list[dict], top: Path, legacy: str = "raw-legacy",
                repo_tiles: Path | None = None, ledger_retired: dict[str, str] | None = None) -> PlanResult:
    """`top` = 레이크 상위(`FIRE_LANE_DATA` 의 부모). `ledger_retired` = 대장이 든 폐기 파일 → sha."""
    import tarfile
    import zipfile
    res = PlanResult()
    data, leg = top / "data", top / legacy
    fail = res.fails.append

    # 보존 — 원천 또는 목적지에 같은 sha 로 있어야 한다. 대장이 그 이름 · sha 를 들어야 한다
    where: dict[str, Path] = {}
    for r in (x for x in rows if x["action"] == "보존"):
        src, dst = leg / r["src"], data / retired_dst(r)
        sub = retired_dst(r).split("/", 1)[1]
        if ledger_retired is not None and ledger_retired.get(sub) != r["sha256"]:
            fail(f"보존  {r['src']}: 대장 retired 에 `{sub}` 가 sha 와 함께 없다")
        if src.exists() and dst.exists():
            fail(f"보존  {r['src']}: 원천과 목적지에 둘 다 있다 — 반쯤 옮겨졌다. 사람이 본다")
            continue
        cur = src if src.exists() else dst if dst.exists() else None
        if cur is None:
            fail(f"보존  {r['src']}: 원천에도 목적지에도 없다")
            continue
        if _sha(cur) != r["sha256"]:
            fail(f"보존  {r['src']}: sha 가 계획표와 다르다 ({cur})")
            continue
        where[r["src"]] = cur
        res.counts["보존"] += 1
        if cur == src:
            res.moves.append((str(src), str(dst)))

    # 사본 — 레이크 data 안에 같은 sha 가 **실재**해야 지운다. 크기가 같은 것만 잰다
    copies = [x for x in rows if x["action"] == "삭제·사본"]
    sizes = {int(x["bytes"]) for x in copies}
    index: dict[str, str] = {}
    for p in data.rglob("*"):
        if p.is_file() and not p.is_symlink() and p.stat().st_size in sizes:
            index.setdefault(_sha(p), str(p))
    for r in copies:
        src = leg / r["src"]
        if not src.exists():
            res.counts["삭제·사본(이미 없음)"] += 1
            continue
        if _sha(src) != r["sha256"]:
            fail(f"사본  {r['src']}: sha 가 계획표와 다르다")
        elif r["sha256"] not in index:
            fail(f"사본  {r['src']}: 레이크에 같은 sha 가 없다 — 유일본일 수 있다. 지우지 않는다")
        else:
            res.deletes.append(str(src))
            res.counts["삭제·사본"] += 1

    # 압축재생 — 보존 zip 멤버에 같은 sha 가 있어야 한다
    members: dict[str, set[str]] = {}
    for r in (x for x in rows if x["action"] == "삭제·압축재생"):
        src = leg / r["src"]
        if not src.exists():
            res.counts["삭제·압축재생(이미 없음)"] += 1
            continue
        z = r["dst_or_reason"].split(" 안에", 1)[0].strip()
        if z not in where:
            fail(f"압축재생  {r['src']}: 근거 zip `{z}` 이 보존 목록에 없거나 확인되지 않았다")
            continue
        if z not in members:
            with zipfile.ZipFile(where[z]) as zf:
                import hashlib
                members[z] = set()
                for i in zf.infolist():
                    if i.is_dir():
                        continue
                    h = hashlib.sha256()
                    with zf.open(i) as fh:
                        while b := fh.read(4 << 20):
                            h.update(b)
                    members[z].add(h.hexdigest())
        if _sha(src) not in members[z]:
            fail(f"압축재생  {r['src']}: `{z}` 안에 같은 내용이 없다")
        else:
            res.deletes.append(str(src))
            res.counts["삭제·압축재생"] += 1

    # 스냅숏 — 멤버 전부가 원천(또는 옮긴 목적지)과 같아야 한다
    for r in (x for x in rows if x["action"] == "삭제·스냅숏"):
        arc = top / r["src"]
        if not arc.exists():
            res.counts["삭제·스냅숏(이미 없음)"] += 1
            continue
        plan_by_src = {x["src"]: x for x in rows}
        n = 0
        with tarfile.open(arc, "r:*") as t:
            import hashlib
            for m in t:
                if not m.isfile():
                    continue
                rel = m.name.split("/", 1)[1] if "/" in m.name else m.name
                pr = plan_by_src.get(rel)
                if pr is None:
                    fail(f"스냅숏  멤버 `{m.name}` 가 계획표에 없다 — 유일본일 수 있다")
                    continue
                f = t.extractfile(m)
                h = hashlib.sha256()
                while f and (b := f.read(4 << 20)):   # ★ 1.3GB 멤버가 있다. 통째로 읽으면 8GB 기계가 죽는다
                    h.update(b)
                got = h.hexdigest() if f else ""
                if got != pr["sha256"]:
                    fail(f"스냅숏  멤버 `{m.name}` 가 계획표 sha 와 다르다")
                n += 1
        if n and not any(x.startswith("스냅숏") for x in res.fails):
            res.deletes.append(str(arc))
            res.counts["삭제·스냅숏 멤버"] += n

    # 재생성 — 레이크 타일 키가 전부 저장소에 있어야 한다(내용은 재인코딩이라 sha 가 다르다 · §173-5)
    for r in (x for x in rows if x["action"] == "삭제·재생성"):
        d = top / r["src"]
        if not d.exists():
            res.counts["삭제·재생성(이미 없음)"] += 1
            continue
        if repo_tiles is None or not repo_tiles.is_dir():
            fail(f"재생성  {r['src']}: 대조할 저장소 타일 폴더가 없다")
            continue
        files = [p for p in d.rglob("*") if p.is_file()]
        # data/tiles/ortho/15/x/y.jpg ↔ web/data/ortho/15/x/y.jpg
        miss = [p for p in files if not (repo_tiles / p.relative_to(d / "ortho")).exists()] \
            if (d / "ortho").is_dir() else files
        if miss:
            fail(f"재생성  {r['src']}: 저장소에 없는 타일 {len(miss)} — 예 {miss[0]}")
        else:
            res.deletes += [str(p) for p in files]
            res.delete_dirs.append(str(d))
            res.counts["삭제·재생성 파일"] += len(files)

    if (leg.is_dir()):
        res.delete_dirs.append(str(leg))
    return res


def write_commands(res: PlanResult, out: Path, top: Path) -> tuple[Path, Path]:
    """mv 는 덮어쓰지 않고(-n), rm 은 파일 하나씩 · 폴더는 빈 것만. `rm -rf` 는 쓰지 않는다."""
    import shlex
    out.mkdir(parents=True, exist_ok=True)
    head = ("#!/usr/bin/env bash\n# firelane.lake plan 이 생성 — 손으로 고치지 않는다\n"
            "set -euo pipefail\n")
    q = top / "data" / "_quarantine"
    mv = [head, "# ① 레이크 밖 유일본 → retired\n"]
    for s_, d_ in res.moves:
        mv.append(f"mkdir -p {shlex.quote(str(Path(d_).parent))} && mv -n {shlex.quote(s_)} {shlex.quote(d_)}"
                  f" && test -e {shlex.quote(d_)}\n")
    if q.is_dir():
        mv.append("# ② 폐지층 _quarantine → retired (기록 QUARANTINE.md 포함)\n")
        for p in sorted(q.rglob("*")):
            if p.is_file():
                d_ = top / "data" / "retired" / p.relative_to(q)
                mv.append(f"mkdir -p {shlex.quote(str(d_.parent))} && mv -n {shlex.quote(str(p))} "
                          f"{shlex.quote(str(d_))} && test -e {shlex.quote(str(d_))}\n")
        mv.append(f"find {shlex.quote(str(q))} -depth -type d -empty -delete\n")
    mv.append("echo \"이동 끝 — 적용 스크립트를 다시 돌려라\"\n")
    rm = [head, "# ★ 삭제 블록. 이동이 끝나고 적용 스크립트가 다시 잰 뒤에만 친다\n"]
    rm += [f"rm -- {shlex.quote(p)}\n" for p in res.deletes]
    rm += [f"find {shlex.quote(d)} -depth -type d -empty -delete\n" for d in res.delete_dirs]
    rm += [f"test ! -e {shlex.quote(d)} || {{ echo \"✗ {d} 에 계획 밖 파일이 남았다\"; exit 1; }}\n"
           for d in res.delete_dirs]
    rm.append("echo \"삭제 끝 — 적용 스크립트를 다시 돌려라\"\n")
    pm, pr = out / "l2_moves.sh", out / "l2_deletes.sh"
    pm.write_text("".join(mv), encoding="utf-8")
    pr.write_text("".join(rm), encoding="utf-8")
    return pm, pr


def ledger_retired_sha(y: dict) -> dict[str, str]:
    out = {}
    for e in (y.get("retired") or {}).values():
        sha = (e or {}).get("sha256") or {}
        if isinstance(sha, dict):
            out.update({str(k): str(v) for k, v in sha.items()})
    return out


def table(rows: list[Row]) -> str:
    cnt = Counter((r.layer or "(루트)", r.state) for r in rows)
    layers = sorted({lay for lay, _ in cnt})
    head = f"{'층':14}" + "".join(f"{s:>7}" for s in STATES)
    lines = [head]
    for lay in layers:
        lines.append(f"{lay:14}" + "".join(f"{cnt.get((lay, s), 0) or '·':>7}" for s in STATES))
    return "\n".join(lines)


def _load_prep() -> dict:
    p = paths.ROOT / "data" / "_prep.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="firelane.lake")
    ap.add_argument("cmd", choices=["scan", "gate", "plan"])
    ap.add_argument("plan_tsv", nargs="?", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--out", type=Path, help="plan — 명령 파일을 쓸 폴더(레이크 밖)")
    ap.add_argument("--planned", action="append", default=[],
                    help="gate — 계획이 처분하는 경로 접두(레이크 루트 상대)")
    a = ap.parse_args(argv)
    paths.require_lake(need=("raw",))
    y = ledger.load()
    if a.cmd == "plan":
        if not a.plan_tsv or not a.out:
            ap.error("plan 은 계획표와 --out 이 필요하다")
        top = paths.DATA.parent
        res = verify_plan(read_plan(a.plan_tsv), top, repo_tiles=paths.ROOT / "web" / "data" / "ortho",
                          ledger_retired=ledger_retired_sha(y))
        for k, v in sorted(res.counts.items()):
            print(f"  {k:24} {v}")
        for f in res.fails[:40]:
            print("  ✗", f)
        if res.fails:
            print(f"\n계획표 조건 실패 {len(res.fails)} — 명령을 쓰지 않는다")
            return 1
        pm, pr = write_commands(res, a.out, top)
        print(f"\n이동 {len(res.moves)} → {pm}\n삭제 {len(res.deletes)} → {pr}")
        return 0
    rows = resolve(y, paths.DATA, _load_prep())
    print(table(rows))
    if a.json:
        a.json.write_text(json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        print(f"\n행 {len(rows)} → {a.json}")
    blocked = gate(y, rows, tuple(a.planned))
    if a.cmd == "gate":
        for b in blocked[:40]:
            print("  ✗", b)
        print(f"\n관문 {'닫힘 — 아무것도 움직이지 않는다' if blocked else '열림'} ({len(blocked)})")
        return 1 if blocked else 0
    print(f"\n관문을 막는 것 {len(blocked)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
