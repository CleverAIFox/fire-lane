"""
rawcache.py — **raw 파일 지문의 기억표.** 같은 파일을 두 번 안 읽는다.

── 왜 떼어 냈나 (2026-10-08 · DECISIONS §433) ─────────────────
`shardseal.py` 가 622 예외에서 **634** 가 됐다. `logic_print` 가 빈 몸통을
안 맞춰서 0바이트 `__init__.py` 에 머리말을 다는 순간 샤드를 찢던 것을
고치면서다. 예외를 올리는 대신 **제 구분선을 가진 묶음**을 뗐다 — 부르는
쪽이 `shardseal` 안에만 있었고, 물음도 다르다: 저쪽은 **봉인**이고
여기는 **읽기를 아끼는 기억**이다. 561 로 내려와 예외 표에서 사라진다.

IN    `data/processed/.rawprint.json` (추적 밖 · 캐시)
OUT   같은 파일 (갱신될 때만 쓴다)
PARAM 없음
밖    **봉인 판정은 안 한다.** 지문을 내고 멈춘다 — 그 지문이 맞는지 틀린지는
      `shardseal.check` 가 든다. 그리고 **캐시가 없어도 답이 같다** —
      못 읽거나 못 쓰면 느려질 뿐이고 판정은 옳다.
"""
from __future__ import annotations

import json
from pathlib import Path

from firelane.hashing import sha256

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
