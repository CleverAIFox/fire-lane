#!/usr/bin/env python3
"""
manifest.py — 매니페스트를 내용이 바뀔 때만 쓴다.

── 왜 생겼나 ───────────────────────────────────────────────────
`data/processed/_manifest.json` 과 `web/data/_manifest.json` 은 커밋되는
재현성 기록이다(MASTER §12-6). 그런데 매 실행 `generated_at` 만 바뀌어
diff 가 났고, `verify.sh` 를 한 번 돌릴 때마다 워킹트리가 더러워져
`git checkout` 이 막혔다.

    error: Your local changes to the following files would be overwritten
            data/processed/_manifest.json
            web/data/_manifest.json

**커밋해야 하는 파일과 매 실행 바뀌는 파일이 같은 파일**인 것이 원인이다.
셋 중 하나를 골라야 했다.

    그대로 두기      의미 없는 diff 가 커밋 이력에 쌓인다
    커밋에서 빼기    재현성 기록이 사라진다. §18-5 R2 위반
    시각을 안정화    ← 이것

`generated_at` 의 뜻을 **"마지막 실행 시각"에서 "내용이 마지막으로 실제
달라진 시각"으로** 바꾼다. 재현성 기록으로는 후자가 옳다 — 같은 입력으로
같은 산출을 냈다는 사실이 시각 때문에 흐려지지 않는다.

★ 시각을 지우지 않는다. 지우면 "언제 만들어진 기록인가"를 잃는다.
  **바뀌지 않았을 때 갱신하지 않을 뿐이다.**

IN    기존 매니페스트 파일(있으면)
OUT   같은 파일. 내용이 같으면 손대지 않는다
PARAM STAMP_KEYS
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 이 키들은 "언제" 를 담을 뿐 내용이 아니다. 같은지 비교할 때 제외한다.
STAMP_KEYS = ("generated_at",)


def _borrow_stamps(new: Any, old: Any, keys: tuple[str, ...]) -> Any:
    """`new` 를 복사하되 시각 키만 `old` 것으로 바꾼다.

    중첩을 따라간다. `terrain` · `ortho` 는 자기 블록 안에 시각을 넣는다.
    """
    if isinstance(new, dict) and isinstance(old, dict):
        return {k: (old[k] if k in keys and k in old
                    else _borrow_stamps(v, old.get(k), keys))
                for k, v in new.items()}
    if isinstance(new, list) and isinstance(old, list) and len(new) == len(old):
        return [_borrow_stamps(a, b, keys) for a, b in zip(new, old, strict=False)]
    return new


def write_stable(path: Path, obj: dict, *,
                 keys: tuple[str, ...] = STAMP_KEYS) -> bool:
    """시각을 뺀 내용이 같으면 쓰지 않는다. 썼으면 True.

    ★ mtime 도 안 건드린다. 안 쓰는 것이 곧 "안 바뀌었다" 의 표현이다.
    """
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = None
        if isinstance(old, dict) and _borrow_stamps(obj, old, keys) == old:
            return False
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return True


def read(path: Path) -> dict:
    """없거나 깨졌으면 빈 dict. 부르는 쪽이 매번 try 를 쓰지 않게 한다."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}
