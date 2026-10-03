#!/usr/bin/env python3
"""
datalog.py — 데이터 대장 도구

    python -m firelane.datalog record      매니페스트 갱신(파이프라인 끝에서 호출)
    python -m firelane.datalog graph       의존 그래프 → data/interim/lineage.mmd
    python -m firelane.datalog impact KEY  이 소스를 바꾸면 깨지는 것
    python -m firelane.datalog backup DIR  외장으로 복사 + sha 기록
    python -m firelane.datalog verify DIR  외장 대조
    python -m firelane.datalog check       대장 정합성 검사
    python -m firelane.datalog fsck        계층 선언 ↔ 실물 대조

── 설계 원칙 ──────────────────────────────────────────────────
사람이 손으로 쓰는 대장은 sources.yaml 하나다.
이 스크립트가 만드는 것(_manifest.json, lineage.mmd)은 전부 생성물이고
손으로 고치지 않는다. 손대장이 둘이 되면 반드시 어긋난다.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from firelane import gitq
from firelane.cli import USAGE_EXIT
from firelane.layerfsck import cmd_fsck  # 사용법 오류 종료코드는 정본 하나다
from firelane.paths import ROOT


def _tracked_paths() -> frozenset[str] | None:
    """git 이 추적하는 경로. **추적 밖은 「안 지었다」이고 결함이 아니다**(§290-7).

    ★ 2026-10-03 (DECISIONS §372). **못 물었으면 `None` 이다.** 종전에는
      `check=False` 로 돌리고 `stdout` 을 그대로 갈랐고, 그래서 두 가지가
      빈 집합으로 뭉개졌다 —

        git 바이너리가 없다      `FileNotFoundError` — `check=False` 는 안 막는다
        `.git` 이 없다          rc=128, stdout 비어 있음

      빈 집합이면 **모든 산출물이 「추적 밖」**이 되고, 그러면 §290-7 이 세운
      「대장이 틀린 것」과 「이 기계가 안 지은 것」의 구분이 통째로 사라진다.
      컨테이너가 바로 그 기계다 — `Dockerfile` 은 git 을 안 깔고 `.git` 도
      안 담는다. 거기서 이 검사는 **아무것도 못 묻고 전부 초록**이었다.
    """
    return gitq.tracked(ROOT)

KST = timezone(timedelta(hours=9))
SOURCES = ROOT / "sources.yaml"
PROCESSED = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"   # 재생성 가능 계층 — 생성물이 사는 곳
MANIFEST = PROCESSED / "_manifest.json"
RUNLOG = PROCESSED / "_runlog.json"     # ★ datalog 소유. `_manifest.json` 은 ingest 소유다(§280-1)
# ★ processed 는 백업하지 않는다. raw + 코드 + 대장으로 재생성된다.
#   보관 우선순위: raw·field(재생성 불가) > norm(재정규화 가능) > processed(버림)
# 저장소 **안**에 있을 때만 해당한다. 밖에 있으면 external_targets() 가 잡는다.
# ★ 2026-08-31. 손목록이었고 `layers` 선언과 **양방향으로 어긋났다** —
#   `quarantine`(18.9MB · 판단 보류)은 `backup: true` 인데 빠져 있었고,
#   `norm` 은 `regenerable: true` 라 대상이 아닌데 들어 있었다.
#   같은 것을 `tools/doctor.py` 는 `layers` 에서 옳게 유도하고 있었다.
#   **정본이 둘이면 반드시 어긋난다**(R3). 이제 하나만 읽는다.
def _layer_rels(flag: str) -> list[str]:
    from firelane import layers as _ly
    from firelane.lake import ABOLISHED
    # ★ `ABOLISHED` 는 층 **이름이 아니라 `sub`** 다(`("_quarantine",)`). 이름으로
    #   견주면 안 걸린다 — 실제로 안 걸리고 있었다. 같은 종류의 실수가 바로
    #   아래 경로 조립에도 있었다: 이름으로 경로를 만들면 `sub` 가 다른 층에서
    #   어긋난다.
    return [n for n in _ly.names()
            if _ly.policy(n).get(flag)
            and (_ly.policy(n).get("sub") or n) not in ABOLISHED]


def _layer_path(name: str) -> str:
    """층의 실제 상대경로. **이름이 아니라 `sub` 를 쓴다**(§280-2)."""
    from firelane import layers as _ly
    sub = _ly.policy(name).get("sub") or name
    return sub if sub.startswith("data/") else f"data/{sub}"


# ★ 2026-09-28 (§280-2). 종전에는 **층 이름**으로 경로를 조립했다 — `sub` 가
#   이름과 다른 층에서 어긋난다. 실물이 그랬다: `quarantine` 의 `sub` 는
#   `_quarantine` 인데 `data/quarantine` 을 가리켰고, 그 경로는 **실재하지
#   않는다.** 없는 경로를 훑는 백업은 매번 0건을 복사하고 조용히 통과한다.
#   게다가 그 층은 2026-09-17 에 **폐지**됐다(`lake.ABOLISHED`).
BACKUP_TARGETS = [_layer_path(n) for n in _layer_rels("backup")]
# raw 는 레포 밖에 있다. 상대경로만 훑으면 2.5GB 가 통째로 빠진다.
# 백업 대상에서 raw 가 빠졌다는 것을 파일 개수로만 알 수 있으면 조용한 결측이다.
#
# ★ 2026-08-23 버그 수정. 종전에는 **폐기된 `FIRE_LANE_RAW` 만** 봤다.
#   현행 변수는 `FIRE_LANE_DATA` 이고(MASTER §6-2), 그것만 설정한 기계에서는
#   external_targets() 가 빈 리스트가 되어 **raw 가 백업에서 통째로 빠졌다.**
#   `data/raw` 상대경로는 저장소 안이라 존재하지 않으므로 "백업 대상 없음"
#   한 줄만 찍고 넘어간다 — 정확히 이 파일이 경고하는 조용한 결측이다.
#   경로 정본은 paths.py 다. 여기서 환경변수를 직접 읽지 않는다.
from firelane.paths import FIELD as _FIELD
from firelane.paths import NORM as _NORM
from firelane.paths import RAW as _RAW


def external_targets() -> list[Path]:
    """저장소 밖에 있는 백업 대상. **호출 시점에** 판정한다.

    ★ 2026-08-26. 종전에는 모듈 최상위 상수였다. `q.exists()` 가 임포트
      시점에 돌았고, 외장 SSD 마운트가 끊기면 `OSError: [Errno 19]
      No such device` 로 **모듈을 불러오지도 못했다.** 그날 문서만
      고치던 작업까지 `verify.sh` 에서 통째로 막혔다.

      계층 경로는 기계마다 다르고 마운트는 언제든 끊긴다(§18-1).
      그 사실을 임포트가 아니라 호출이 감당해야 한다.
    """
    out = []
    for q in (_RAW, _NORM, _FIELD):
        try:
            if q.exists() and ROOT not in q.parents and q != ROOT:
                out.append(q)
        except OSError:
            continue          # 마운트 끊김. 대상이 아닐 뿐 오류가 아니다
    return out

# ★ raw 와 field 는 재생성이 불가능하다. processed 는 재생성되지만 시간이 든다.
#   이 우선순위가 백업 순서이자 복원 훈련 대상 순서다.
# ★ 재생성 불가 = `regenerable` 이 거짓인 계층. 손으로 세지 않는다.
CRITICAL = ["data/" + n for n in _layer_rels("backup")
            if not _layer_rels("regenerable").count(n)]


# ──────────────────────────────────────────────────────────────
from firelane.hashing import sha256 as _h_sha256


def sha256(p, chunk: int = 1 << 20) -> str:
    # ★ 2026-09-13. 구현은 `firelane.hashing` 한 곳이다.
    #   이름은 호출부 때문에 남긴다 — 옮긴 것과 고친 것을
    #   한 커밋에 섞지 않는다(원칙 ⑤).
    return _h_sha256(p, chunk)


def git_state() -> dict:
    """산출물의 재현 기반. **못 물었으면 `dirty` 가 `None`** — `False` 가 아니다.

    ★ 2026-10-03 (DECISIONS §372). 종전에는 `dirty: bool(dirty)` 였다. git 이
      못 답하면 `None` → `bool(None)` → **`False`**, 즉 「깨끗하다」로 기록됐다.
      「깨끗함을 확인했다」와 「확인할 수 없었다」가 같은 값이 된 것이고,
      `git_dirty 인 상태의 산출물은 재현 불가`라는 규율(아래 ★)이 그 기계에서
      조용히 무력해졌다. **회색은 NULL 이다.**
    """
    d = gitq.dirty(ROOT)
    return {"sha": gitq.head(ROOT),
            "dirty": None if d is None else bool(d),
            "dirty_files": (d[:10] if d else [])}


def load_sources() -> dict:
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}


# ──────────────────────────────────────────────────────────────
def cmd_record() -> None:
    """
    파이프라인 끝에서 호출한다. processed 산출물의 지문을 남긴다.

    ★ git_dirty 인 상태로 만든 산출물은 재현이 불가능하다.
      커밋 안 한 코드로 만든 결과가 발표 자료가 되는 걸 막기 위해 경고한다.
    """
    src = load_sources()
    outputs = src.get("outputs", {}) or {}
    g = git_state()

    rec = {}
    for p in sorted(PROCESSED.glob("*")):
        if p.name.startswith("_") or p.is_dir():
            continue
        entry = {"sha256": sha256(p)[:32], "bytes": p.stat().st_size}
        # 대장에 선언된 산출물이면 계보를 함께 박는다
        for _key, meta in outputs.items():
            if meta.get("path", "").endswith(p.name):
                entry["produced_by"] = meta.get("produced_by")
                entry["inputs"] = meta.get("inputs", [])
                entry["stable_key"] = meta.get("stable_key")
                entry["verified"] = meta.get("verified", False)
                break
        else:
            # 대장에 없는 산출물. 이게 쌓이면 아무도 뭔지 모르는 파일이 늘어난다
            entry["undeclared"] = True
        rec[p.name] = entry

    manifest = {
        "run": {"at": datetime.now(KST).isoformat(timespec="seconds"),
                "git": g, "python": sys.version.split()[0]},
        "outputs": rec,
    }
    # ★ 2026-09-28 (DECISIONS §280-1). **종전에는 `MANIFEST` 를 덮었다.**
    #   그 파일은 `ingest` 소유이고 모양이 아예 다르다 —
    #     ingest   {"datasets": [72종], "terrain", "ortho", "bbox_4326", …}
    #     여기     {"run": {...git...}, "outputs": {...}}
    #   한 번만 돌면 `datasets` 블록이 사라지고 **계보 지문**
    #   (`lineage._manifest_digest` 가 그 블록을 해시한다)과 **샤드 봉인 45개**
    #   (`seal` 칸)가 통째로 날아간다. 그리고 이 명령은 MASTER §18-7 에
    #   명령줄까지 적혀 있다 — 문서를 읽고 그대로 친 사람이 파이프라인을 지운다.
    #
    #   같은 경로에 두 주인을 두지 않는다(R3). 제 기록은 제 파일에 쓴다.
    if MANIFEST.exists():
        cur = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if "datasets" in cur:
            print(f"  ★ {MANIFEST.name} 은 ingest 소유다 — 안 덮는다. "
                  f"{RUNLOG.name} 에 쓴다")
    RUNLOG.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    n_und = sum(1 for v in rec.values() if v.get("undeclared"))
    print(f"기록 {len(rec)}개 → {MANIFEST}")
    if n_und:
        print(f"  ! 대장에 없는 산출물 {n_und}개. sources.yaml outputs 에 추가할 것")
        for k, v in rec.items():
            if v.get("undeclared"):
                print(f"      {k}")
    if g["dirty"]:
        print("  ! git 워킹트리가 더럽다. 이 산출물은 재현 불가다")
        for f in g["dirty_files"]:
            print(f"      {f}")


# ──────────────────────────────────────────────────────────────
def cmd_graph() -> None:
    """의존 그래프. 손으로 그리지 않는다 — 그리는 순간 낡는다."""
    src = load_sources()
    ds = src.get("datasets", {}) or {}
    out = src.get("outputs", {}) or {}

    L = ["```mermaid", "graph LR"]
    # ★ 2026-09-22 (PLAN §13 W10-1 · deadcheck ①). 종전에는 `verified` 로 ✓/? 를,
    #   `vintage` 로 날짜를 찍었다. datasets 72종 중 **어느 것도** 두 키를 안 가진다
    #   (`verified` 는 outputs 의 키다). 그래서 모든 노드가 늘 `?` 였고 날짜는 빈칸이었다
    #   — 표시가 있는데 안 변하는 자리다. 실재하는 `updated`(72/72, REQUIRED)를 찍고
    #   거짓 `?` 는 뺀다.
    for k, v in ds.items():
        L.append(f'  {k}["{k}<br/>{v.get("updated", "")}"]')
    for k, v in out.items():
        L.append(f'  {k}(["{k}"])')
        for i in v.get("inputs", []):
            L.append(f"  {i} --> {k}")
        for c in v.get("consumers", []):
            cid = c.replace("/", "_").replace(".", "_")
            L.append(f'  {cid}["{c}"]')
            L.append(f"  {k} --> {cid}")
    L.append("```")

    # ★ 2026-09-28. 예전엔 `docs/lineage.mmd` 였다. 세 가지가 동시에 틀렸다 —
    #   ① `docs/` 는 문서 넷만 사는 곳인데 생성물이 거기 살았고, 이 명령을
    #      한 번 돌리면 `test_docs_dir_holds_only_the_allowed_documents` 가
    #      빨강이 됐다. **검사를 깨는 도구**였다.
    #   ② gitignore 되어 있어서 아무도 diff 로 못 봤다.
    #   ③ **아무도 안 읽었다** — 저장소 전체에서 이 파일을 가리키는 곳이 0.
    #   생성물은 재생성 가능 계층에 산다(§283-7). 그림으로 쓸 것이면
    #   `tools/figures/` 가 대장에서 직접 그린다 — PLAN 참조.
    p = INTERIM / "lineage.mmd"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(L), encoding="utf-8")
    print(f"→ {p.relative_to(ROOT)}  (노드 {len(ds)+len(out)})")


def cmd_impact(key: str) -> None:
    """
    이 소스를 갱신하면 무엇이 깨지는가.
    소스 재다운로드 전에 반드시 돌린다. 이게 consumers 필드의 존재 이유다.
    """
    src = load_sources()
    out = src.get("outputs", {}) or {}
    hit_out = [k for k, v in out.items() if key in v.get("inputs", [])]
    hit_con = sorted({c for k in hit_out for c in out[k].get("consumers", [])})

    print(f"[{key}] 를 바꾸면")
    print(f"  재생성 필요 산출물 {len(hit_out)}")
    for k in hit_out:
        print(f"    - {k}  ({out[k].get('produced_by')})")
    print(f"  영향받는 소비자 {len(hit_con)}")
    for c in hit_con:
        print(f"    - {c}")
    if not hit_out:
        print("  없음 — 대장에 inputs 가 안 적혀 있을 가능성이 크다. check 를 먼저 돌려라")


# ──────────────────────────────────────────────────────────────
def cmd_check() -> None:
    """
    대장 정합성. 셋 다 '조용히 틀어지는' 종류라 자동 검사가 필요하다.
    """
    src = load_sources()
    ds = src.get("datasets", {}) or {}
    out = src.get("outputs", {}) or {}
    bad = 0

    # 1. outputs.inputs 가 datasets 나 outputs 에 실제로 있는가
    known = set(ds) | set(out)
    for k, v in out.items():
        for i in v.get("inputs", []):
            if i not in known:
                print(f"  ! {k}.inputs 의 '{i}' 가 대장에 없다"); bad += 1

    # 2. 필수 필드 누락
    # ★ 2026-09-07. 여기가 **대장 필수 필드의 두 번째 정본**이었다.
    #
    #     ledger.REQUIRED   what · scope · updated · kind · schema · feeds
    #     datalog.need_ds   what · crs_native · license · vintage
    #
    #   겹치는 것이 `what` 하나뿐이다. 그래서 `ledger.check_all()` 은
    #   통과하는데 `datalog check` 는 158건을 냈다. 내역은 이렇다 —
    #
    #     vintage      0/61   `updated` 로 통합이 끝났다(ledger_fields.py:17).
    #                         "한 축에 이름이 둘이면 사람은 아무 쪽에나 적는다"
    #                         고 적어놓고 이 검사만 옛 이름을 계속 봤다
    #     license      0/61   어느 종에도 없고 코드 참조 0. 죽은 요구다
    #     crs_native  33/61   그중 31 이 **좌표가 없는 kind** 다.
    #                         raw_only 문서에까지 좌표계를 요구했다
    #
    #   ★ 게이트가 정상 상태에서 울면 사람이 무시하기 시작하고, 그 순간
    #     게이트가 죽는다. `golden` 낡음 검사에서 이미 배운 것이다
    #     (2026-08-23). 158건은 아무도 안 읽고 있었다.
    #
    #   정본은 `ledger.REQUIRED` 하나다.
    #
    # ★ 2026-09-28 (§285-2). **교훈을 절반만 적용하고 있었다.** 목록
    #   베끼기는 멈췄는데 **판정은 여전히 베꼈다** — `not v.get(f)` 는
    #   「키가 없다」와 「비었다」를 뭉갠다. `ledger` 는 그 둘을 가른다:
    #   키 부재는 FAIL 이고, 빈 `feeds` 는 `grade()` 가 `unused` 로 읽어
    #   **`feeds_why` 에 사유를 적으면 통과**한다(§77 의 탈출구).
    #
    #   그래서 같은 대장을 두고 `firelane.ledger` 는 FAIL 0 인데 여기는
    #   「feeds 없음」 18건을 냈다. **판정이 둘이면 배선을 못 한다** —
    #   이미 배선된 쪽이 통과시키는 것을 새로 배선할 쪽이 막으니까.
    #   이것이 이 도구가 §280 이후에도 안 붙어 있던 진짜 이유다.
    #
    #   목록이 아니라 **함수**를 부른다. 필드 판정은 `ledger` 소관이고
    #   여기는 아래 그래프 축만 본다.
    from firelane import ledger as _L

    for k, v in ds.items():
        for iss in _L.check_entry(k, v):
            if iss.level == _L.FAIL:
                print(f"  ! datasets.{k}: {iss.msg}"); bad += 1
    for k, v in out.items():
        for f in ["produced_by", "inputs", "consumers", "what"]:
            # consumers 는 빈 리스트가 정상일 수 있다(아직 아무도 안 쓰는 산출물).
            # 키 자체가 없는 것과 비어 있는 것을 구분한다.
            if f == "consumers":
                if "consumers" not in v:
                    print(f"  ! outputs.{k} 에 consumers 키 없음"); bad += 1
                elif not v["consumers"]:
                    print(f"  · outputs.{k} 는 아직 소비자가 없다")
                continue
            if not v.get(f):
                print(f"  ! outputs.{k} 에 {f} 없음"); bad += 1

    # 3. 선언된 산출물이 실제로 존재하는가
    #
    # ★ 2026-09-28 (DECISIONS §290-7). **추적 밖 산출물의 부재는 결함이 아니다.**
    #   `data/processed/*.gpkg` 는 `.gitignore` 가 덮는 재생성물이고, 파이프라인을
    #   안 돌린 기계(새 워크트리 · CI)에는 당연히 없다. 그것을 실패로 세면 이
    #   단계는 **레이크 있는 기계에서만 초록**이 되고, 그 사실이 선언 안 돼 있어서
    #   배달 예습을 통째로 막았다 — 예습이 워크트리에서 돌기 때문이다.
    #
    #   대장이 틀린 것과 이 기계가 안 지은 것은 다른 사실이다. **추적되는 경로가
    #   없으면 대장이 틀린 것이고, 추적 밖이면 안 지은 것이다.** `docseal` 이
    #   같은 규율을 쓴다(§278-10 — 추적 밖은 도장의 기반이 못 된다).
    #
    # ★ 2026-10-03 (§372). **못 물었으면 가르지 않는다.** 빈 집합을 받아
    #   「전부 추적 밖」으로 읽으면 이 구분이 사라진 채 초록이 된다.
    tracked = _tracked_paths()
    missing = [(k, v.get("path", "")) for k, v in out.items()
               if v.get("path") and not (ROOT / v["path"]).exists()]
    if tracked is None and missing:
        print(f"  ! git 이 추적 목록을 못 줬다 — 없는 산출물 {len(missing)}건을"
              " **「대장이 틀렸다」와 「안 지었다」로 가를 수 없다**(§372)")
        for k, rel in missing:
            print(f"    ? outputs.{k}.path 없음: {rel} (추적 여부 미측정)")
    else:
        for k, rel in missing:
            if rel in (tracked or ()):
                print(f"  ! outputs.{k}.path 없음: {rel} — **추적되는데 없다**"); bad += 1
            else:
                print(f"  · outputs.{k}.path 아직 안 지었다: {rel} (추적 밖 · 재생성물)")

    # 4. verified=false 인데 발표에 쓰이는 것 (경고만)
    unver = [k for k, v in out.items() if not v.get("verified")]
    if unver:
        print(f"  · 미검증 산출물 {len(unver)}: {', '.join(unver)}")
        print("    미검증 값을 검증된 값처럼 쓰지 마라")

    print("OK" if bad == 0 else f"문제 {bad}건")
    sys.exit(1 if bad else 0)


# ──────────────────────────────────────────────────────────────
def _walk(base: Path):
    for p in sorted(base.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            yield p


def cmd_backup(dest: str) -> None:
    """
    복사하고 지문을 남긴다. rsync 만으로는 부족하다 —
    exFAT 에서 2.5GB 를 날렸을 때 문제는 백업이 없어서가 아니라
    백업이 깨진 걸 몰랐던 것이다.
    """
    import shutil
    D = Path(dest)
    D.mkdir(parents=True, exist_ok=True)
    index = {}
    n = 0
    _pairs = [(ROOT / rel, ROOT) for rel in BACKUP_TARGETS
              if (ROOT / rel).exists()]
    # ★ 저장소 밖 계층(raw · norm). 위와 겹치지 않는다 — 위는 exists() 로
    #   걸러지고 raw 가 밖에 있으면 저장소 안 경로는 존재하지 않는다.
    _pairs += [(ext, ext.parent) for ext in external_targets()]
    if not _pairs:
        print("  ★ 백업 대상이 하나도 없다. FIRE_LANE_DATA 를 확인하라.")
        print("     복사할 것이 없는 것과 못 찾은 것은 다르다.")
    for base, anchor in _pairs:
        if not base.exists():
            print(f"  ! 백업 대상 없음: {base}")
            continue
        for p in _walk(base):
            r = str(p.relative_to(anchor))
            t = D / r
            t.parent.mkdir(parents=True, exist_ok=True)
            if not t.exists() or t.stat().st_size != p.stat().st_size:
                # ★ copy2 가 아니라 copyfile 이다.
                #   WSL drvfs(외장 하드) 는 utime 설정을 막아 copy2 가
                #   PermissionError 로 죽는다. 우리가 보존해야 하는 것은
                #   타임스탬프가 아니라 내용이고, 그 검증은 sha256 이 한다.
                shutil.copyfile(p, t)
            index[r] = {"sha256": sha256(p), "bytes": p.stat().st_size}
            n += 1
    (D / "_backup_index.json").write_text(
        json.dumps({"at": datetime.now(KST).isoformat(timespec="seconds"),
                    "files": index}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"백업 {n}개 → {D}")
    print("★ 복원 훈련 주기는 팀 합의 사항이다. 임의로 정하지 않는다.")
    print("  복원해 본 적 없는 백업은 백업이 아니다")


def cmd_verify(dest: str) -> None:
    D = Path(dest)
    idx_p = D / "_backup_index.json"
    if not idx_p.exists():
        print("! _backup_index.json 없음. backup 을 먼저 돌려라")
        sys.exit(1)
    idx = json.loads(idx_p.read_text(encoding="utf-8"))["files"]
    missing, corrupt, ok = [], [], 0
    for rel, meta in idx.items():
        t = D / rel
        if not t.exists():
            missing.append(rel); continue
        if sha256(t) != meta["sha256"]:
            corrupt.append(rel); continue
        ok += 1
    print(f"정상 {ok} · 누락 {len(missing)} · 손상 {len(corrupt)}")
    for r in (missing + corrupt)[:20]:
        crit = " ★재생성불가" if any(r.startswith(c) for c in CRITICAL) else ""
        print(f"  {r}{crit}")
    sys.exit(1 if (missing or corrupt) else 0)



# ──────────────────────────────────────────────────────────────
# ★ 2026-09-28. 분기부가 `{...}[cmd](*rest)` 였다. 세 갈래로 깨져 있었다 —
#   ① 모르는 명령 → `KeyError`  ② 인자 수가 틀림 → `TypeError` + 역추적
#   ③ **인자가 뭔지 아무도 모른다** → `verify.sh` 가 배선을 못 했다(§283-1).
#   머리말은 `impact KEY` · `backup DIR` 을 옳게 적고 있었고 분기부만 안 지켰다.
#   **선언과 실물이 갈린 자리는 늘 선언 쪽이 아니라 부르는 쪽이 조용히 죽는다.**
#: 이름 → (함수, 인자 이름들). 인자 이름은 사용법 출력과 시험이 같이 읽는다.
COMMANDS: dict[str, tuple] = {
    "record": (cmd_record, ()),
    "graph":  (cmd_graph, ()),
    "check":  (cmd_check, ()),
    "fsck":   (cmd_fsck, ()),
    "impact": (cmd_impact, ("KEY",)),
    "backup": (cmd_backup, ("DIR",)),
    "verify": (cmd_verify, ("DIR",)),
}


def usage(why: str = "") -> int:
    """사용법. **역추적이 아니라 이것을 낸다.**"""
    if why:
        print(f"✗ {why}\n")
    for name, (_fn, args) in COMMANDS.items():
        print(f"  python -m firelane.datalog {name} {' '.join(args)}".rstrip())
    return USAGE_EXIT


def dispatch(argv: list[str]) -> int:
    if not argv:
        return usage("명령이 없다")
    cmd, *rest = argv
    if cmd not in COMMANDS:
        return usage(f"모르는 명령 {cmd!r}")
    fn, args = COMMANDS[cmd]
    if len(rest) != len(args):
        need = " ".join(args) or "(없음)"
        return usage(f"{cmd} 는 인자 {len(args)}개가 필요하다 — {need}")
    fn(*rest)
    return 0


if __name__ == "__main__":
    sys.exit(dispatch(sys.argv[1:]))
