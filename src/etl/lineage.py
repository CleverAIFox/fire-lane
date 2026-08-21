#!/usr/bin/env python3
"""
lineage.py — 무엇으로 만들어졌나. 단계별 입출력 지문의 정본.

    uv run python src/etl/lineage.py show      기록된 계보를 본다
    uv run python src/etl/lineage.py verify    현재 디스크와 대조한다

── 왜 이 파일이 생겼나 ─────────────────────────────────────────
2026-08-18. 같은 커밋을 두 기계에서 돌렸는데 한쪽이 미커버 13.4% 로 죽었다.
원인은 `ngii1k_5186.gpkg` 안에 08-17 판 레이어가 남아 있던 것이었고,
`segments` 가 그 옛 레이어를 읽고 있었다.

    _manifest  ngii1k 14336 feat   ← ingest 가 썼다고 적은 값
    segments   ngii1k  6675 feat   ← 실제로 읽은 값
    둘을 비교하는 코드가 없었다

숫자는 이미 다 있었다. 연결이 없었을 뿐이다. 그날 나온 여덟 건이 전부
같은 병이었다 — **측정은 하는데 대조가 없다.**

`_manifest.json` 은 이것을 못 막는다. 그것은 **대장**이다(무엇을 받았나 ·
라이선스 · 출처 URL · 컬럼). 갱신 주기가 다르고 성격이 다르다. 공문으로
받은 자료의 근거 사슬이라 실행마다 흔들려서도 안 된다.

    _manifest.json   대장 — 무엇을 받았나. 소스가 바뀔 때만 갱신
    _lineage.json    계보 — 무엇으로 만들었나. 매 실행 갱신

── 왜 파일 해시만으로는 부족한가 ───────────────────────────────
GPKG 는 매 실행 바이트가 달라진다(타임스탬프 · 페이지 배치). 해시만 보면
"항상 바뀜"이라 신호가 죽는다. 그래서 **내용 지문**을 같이 잡는다.

    layers    레이어 이름 목록   ← 옛 레이어 잔존을 잡는다
    features  피처 수            ← 14336 vs 6675 를 잡는다
    sha256    JSON·CSV 등 결정적 산출물에만

── 무엇을 대조하나 ─────────────────────────────────────────────
    1. 상류 미실행   inputs 에 적힌 산출물의 기록이 없다
    2. 입력 변경     현재 지문 != 상류가 기록한 지문
    3. 산출 변조     현재 지문 != 자기가 기록한 outputs 지문

3 이 종전에 없던 것이다. 사람이 손으로 파일을 만들어 둔 경우, `--only` 로
일부만 돈 경우, 다른 기계 산출물을 복사한 경우가 전부 여기서 걸린다.

── 계층 ────────────────────────────────────────────────────────
단계 스크립트는 계보를 **모른다.** `pipeline.py` 가 실행 전 `verify`,
실행 후 `record` 를 부른다. 종전에는 `segments.py` 안에서 `lineage_check`
를 불렀고, 그래서 단계마다 손으로 배선해야 했다. `--only publish` 가 그
구멍으로 빠져나가 `z` 를 소실시켰다.

    pipeline   계보를 안다. Step.reads / Step.writes 선언을 이미 갖고 있다
    단계       계산만 한다
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LINEAGE = "_lineage.json"

# 내용 지문을 뜨는 방식. 확장자로 고른다.
#   vector  레이어 목록 + 피처 수. 바이트는 매 실행 달라지므로 안 본다
#   bytes   sha256. JSON·CSV 처럼 결정적으로 쓰이는 것
#   tree    디렉터리. 파일 수 + 총 바이트. 타일 묶음이 여기 해당
#   ★ .geojson 은 결정적 텍스트라 바이트 해시로 충분하다. vector 로 다루면
#     pyogrio 없는 환경에서 지문이 error 로 새고, error 끼리는 비교가 안 돼
#     검사가 조용히 무력해진다. gpkg 만 vector 로 본다.
VECTOR = {".gpkg", ".shp"}
BYTES = {".json", ".geojson", ".csv", ".tif", ".txt", ".yaml", ".yml"}


class LineageError(RuntimeError):
    """계보 대조 실패. 파이프라인을 여기서 세운다."""


def _sha(p: Path, limit: int = 1 << 24) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
            if f.tell() > limit:      # 큰 파일은 앞부분만. 변경 검출에 충분하다
                h.update(str(p.stat().st_size).encode())
                break
    return h.hexdigest()[:16]


def fingerprint(p: Path) -> dict | None:
    """파일·디렉터리의 내용 지문. 없으면 None."""
    if not p.exists():
        return None
    if p.is_dir():
        files = [f for f in p.rglob("*") if f.is_file()]
        return {"kind": "tree", "n": len(files),
                "bytes": sum(f.stat().st_size for f in files)}
    ext = p.suffix.lower()
    if ext in VECTOR:
        try:
            import pyogrio
            layers = sorted(r[0] for r in pyogrio.list_layers(p))
            n = sum(pyogrio.read_info(p, layer=lay)["features"] for lay in layers)
            return {"kind": "vector", "layers": layers, "features": int(n)}
        except Exception as e:                       # noqa: BLE001
            # 조용히 넘어가지 않는다. 지문을 못 뜬 사실 자체를 기록한다.
            return {"kind": "vector", "error": f"{type(e).__name__}: {e}"[:120]}
    if p.name == "_manifest.json":
        return _manifest_digest(p)
    if ext in BYTES:
        return {"kind": "bytes", "sha256": _sha(p)}
    return {"kind": "stat", "bytes": p.stat().st_size}


# ── _manifest.json 만 다르게 본다 ──────────────────────────────
# 이 파일은 ingest 가 쓰고 terrain 이 자기 기록을 덧쓴다. 바이트 전체를
# 비교하면 terrain 이 돌 때마다 segments 의 입력 지문이 어긋난다.
# 전량 실행이 성공할 때마다 다음 --from segments 가 깨지는 원인이었다.
#
# segments 가 의존하는 것은 **ingest 가 쓴 datasets 블록** 이다.
# 그 블록만 정규화해서 해시한다. 08-18 사고(ngii1k 14336 기록 vs 옛
# 레이어 6675 사용)는 이 블록의 변화이므로 그대로 잡힌다.
_MANIFEST_OWNED = ("datasets", "bbox_4326", "standard_crs")


def _manifest_digest(p: Path) -> dict:
    """대장의 ingest 소유 블록만으로 지문을 뜬다."""
    import json as _json
    try:
        d = _json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001
        # 파싱 실패는 숨기지 않는다. 바이트 해시로 떨어뜨린다.
        return {"kind": "bytes", "sha256": _sha(p)}
    owned = {k: d.get(k) for k in _MANIFEST_OWNED if k in d}
    blob = _json.dumps(owned, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
    return {"kind": "manifest",
            "sha256": hashlib.sha256(blob).hexdigest()[:16],
            "n": len(d.get("datasets", []))}


def _same(a: dict | None, b: dict | None) -> bool:
    if a is None or b is None:
        return False
    if a.get("kind") != b.get("kind"):
        return False
    if a["kind"] == "vector":
        # error 가 든 지문끼리는 같다고 보지 않는다. 못 읽은 것은 통과가 아니다.
        if "error" in a or "error" in b:
            return False
        return a.get("layers") == b.get("layers") and \
            a.get("features") == b.get("features")
    if a["kind"] == "tree":
        return a.get("n") == b.get("n") and a.get("bytes") == b.get("bytes")
    if a["kind"] in ("bytes", "manifest"):
        return a.get("sha256") == b.get("sha256")
    return a.get("bytes") == b.get("bytes")


def load(processed: Path) -> dict:
    f = Path(processed) / LINEAGE
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _key(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(p)


def record(processed: Path, root: Path, step, expand) -> None:
    """단계 실행 **후**. 읽은 것과 쓴 것의 지문을 남긴다."""
    lg = load(processed)
    lg[step.name] = {
        "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "inputs": {_key(root, p): fingerprint(p) for p in expand(step.consumes)},
        "outputs": {_key(root, p): fingerprint(p) for p in expand(step.produces)},
    }
    (Path(processed) / LINEAGE).write_text(
        json.dumps(lg, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8")


def _skip_mutated(step) -> set:
    """mutates 는 자기가 덧쓴다. 상류가 다시 만들면 지문이 당연히 달라진다.

    terrain 이 segments.geojson 에 z 를 넣는다. 그러면 terrain 이 기억하는
    지문은 'z 가 든 상태' 이고, segments 가 재실행되면 'z 가 없는 상태' 가
    된다. 매번 다르다 — 이것은 오탐이다.

    낡은 입력 탐지는 reads 로 충분하다. reads 는 아무도 덧쓰지 않는다.
    """
    return {str(p) for p in getattr(step, "mutates", ())}


def verify(processed: Path, root: Path, step, expand, steps) -> None:
    """단계 실행 **전**. 세 가지를 본다. 어긋나면 LineageError."""
    lg = load(processed)
    if not lg:
        return                       # 첫 실행. 기록이 없는 것은 실패가 아니다

    # 이 단계의 입력을 만드는 **직전** 상류. STEPS 순서에서 자기 앞만 본다.
    # ★ terrain 이 segments.geojson 을 mutates 하므로 그 파일의 마지막
    #   기록자는 segments 가 아니라 terrain 이다. 뒤쪽 단계를 포함하면
    #   아직 안 돈 단계를 상류로 착각한다.
    order = [s.name for s in steps]
    here = order.index(step.name)
    producer = {}
    for s in steps[:here]:
        for p in expand(s.produces):
            producer[_key(root, p)] = s.name

    problems: list[str] = []
    unknown: list[str] = []

    # ★ mutates 는 이 단계가 읽고 그 자리에 덧쓰는 대상이다. 그래서 이 단계가
    #   기억하는 지문은 '덧쓴 뒤' 상태이고, 상류가 재실행되면 '덧쓰기 전'
    #   상태가 된다. 구조적으로 매번 다르다 — ③ 자가대조의 오탐이다.
    #
    #   terrain 이 segments.geojson 에 z 를 넣는 것이 그 사례다.
    #   기억 32dd6aac(z 있음) vs 디스크 372ee587(z 없음).
    #
    #   ② 상류 대조는 그대로 둔다. 08-18 사고를 잡는 것이 그쪽이다.
    _mutated_keys = {_key(root, m) for m in expand(step.mutates)}

    for p in expand(step.consumes):
        k = _key(root, p)
        up = producer.get(k)
        now = fingerprint(p)

        # ① 상류 기록 없음 — **경고**지 실패가 아니다.
        #   계보를 막 도입한 저장소, --only 로 뒤쪽만 도는 경우가 정상적으로
        #   여기 걸린다. 모르는 것과 틀린 것은 다르다. 대조할 근거가 없으면
        #   말만 하고 넘어가고, 진짜 방어는 ②③(지문 불일치)이 한다.
        if up and up not in lg:
            unknown.append(f"  {k}  ← {up} 기록 없음")
            up = None          # ② 는 못 하지만 ③ 은 그대로 한다

        # ② 입력 변경 — 상류가 쓴 것과 지금 디스크가 다른가
        if up:
            was = lg[up].get("outputs", {}).get(k)
            if was is not None and not _same(was, now):
                problems.append(
                    f"  {k}\n"
                    f"      {up} 가 쓴 것  {was}\n"
                    f"      지금 디스크    {now}")
                continue

        # ③ 자기가 지난번에 읽은 것과 다른가 — 상류가 없는 raw 도 여기서 걸린다
        #   단, mutates 는 제외한다. 자기가 덧쓴 것을 자기가 다시 읽으면
        #   다른 것이 정상이다. reads 는 아무도 덧쓰지 않으므로 그대로 본다.
        if k in _mutated_keys:
            continue
        mine = lg.get(step.name, {}).get("inputs", {}).get(k)
        if mine is not None and not _same(mine, now):
            problems.append(
                f"  {k}\n"
                f"      {step.name} 이 지난 실행에 읽은 것  {mine}\n"
                f"      지금 디스크                    {now}")

    if unknown and not problems:
        print(f"  계보 미기록 {len(unknown)}건 — 대조 없이 진행한다")
        for u in unknown[:3]:
            print(f"  {u}")

    if problems:
        raise LineageError(
            f"계보 대조 실패 — {step.name} 을 돌리지 않는다\n"
            + "\n".join(problems) + "\n"
            "  입력이 바뀌었으면 상류부터 다시 돌려라.\n"
            "    uv run python src/etl/pipeline.py --from <상류단계>\n"
            "  ★ 이 검사가 없던 2026-08-18, ngii1k 가 14336 으로 기록됐는데\n"
            "    segments 는 옛 레이어 6675 개를 읽고 있었다.")


def _cli() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from paths import PROCESSED                                   # noqa: E402

    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    lg = load(PROCESSED)
    if not lg:
        print(f"! {PROCESSED / LINEAGE} 없음 — 파이프라인을 한 번 돌려라")
        return 1
    if cmd == "show":
        for name, rec in lg.items():
            print(f"\n[{name}]  {rec['at']}")
            for tag in ("inputs", "outputs"):
                for k, v in rec.get(tag, {}).items():
                    if v is None:
                        d = "없음"
                    elif v["kind"] == "vector":
                        d = (v.get("error")
                             or f"{v['features']}건 · {v['layers']}")
                    elif v["kind"] == "tree":
                        d = f"{v['n']}개 · {v['bytes'] / 1e6:.1f}MB"
                    else:
                        d = v.get("sha256", v.get("bytes"))
                    print(f"  {tag[0]}  {k:48s} {d}")
        return 0
    if cmd == "verify":
        bad = 0
        for name, rec in lg.items():
            for tag in ("inputs", "outputs"):
                for k, was in rec.get(tag, {}).items():
                    now = fingerprint(Path(k) if Path(k).is_absolute()
                                      else Path(k))
                    if was is not None and not _same(was, now):
                        print(f"! {name}.{tag}  {k}\n    기록 {was}\n    현재 {now}")
                        bad += 1
        print("계보 일치" if not bad else f"\n★ {bad}건 어긋남")
        return 1 if bad else 0
    print(f"모르는 명령: {cmd}  (show | verify)")
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
