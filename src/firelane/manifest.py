#!/usr/bin/env python3
"""
manifest.py — 매니페스트를 내용이 바뀔 때만 쓴다.

── 왜 생겼나 ───────────────────────────────────────────────────
`data/processed/_manifest.json` 과 `web/data/_manifest.json` 은 커밋되는
재현성 기록이다(MASTER §12-10). 그런데 매 실행 `generated_at` 만 바뀌어
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

★ 2026-10-09 (DECISIONS §445). **봉인 셋이 같은 병으로 열차를 세웠다** —
  `data/baseline/<태그>/{meta,eval,nfa_compare}.json` 이 매 실행 `as_of` ·
  `frozen_at` · `git_sha` 만 바뀌어 「전수는 초록인데 추적 파일이 더럽다」가
  났다. `git_sha` 는 **직전 커밋**을 적으므로 커밋하면 또 바뀐다 —
  **닿을 수 없는 고정점**이고, 몇 번을 돌려도 안 닫힌다.
  두 번째 구현을 만들 자리가 아니다(족 2). 키를 넷으로 넓히고 끝개행만
  인자로 받는다 — 매니페스트는 끝개행이 없고 봉인은 있다.

IN    기존 파일(있으면)
OUT   같은 파일. 시각·커밋을 뺀 내용이 같으면 손대지 않는다
PARAM STAMP_KEYS · tail
밖    **무엇이 내용인가는 안 정한다** — 시각과 커밋만 뺀다. 수가 옳은가는
      산출한 쪽이 든다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 이 키들은 "언제" 와 "어느 커밋" 을 담을 뿐 내용이 아니다. 비교할 때 제외한다.
# ★ 2026-10-09. 하나에서 넷으로. `as_of`(지표·대조) · `frozen_at`(봉인) ·
#   `git_sha`(봉인 · 지표)가 같은 성질이고, **그 셋이 봉인 셋을 영구히**
#   **더럽게 만들고 있었다**(DECISIONS §445).
# ★ 넓히는 것이 **가릴 수 있는 자리**가 하나 있다 — `_borrow_stamps` 는
#   중첩을 따라가므로, 어느 매니페스트가 이 이름을 **내용으로** 들면 그
#   변화를 조용히 빌려 온다. 실측(2026-10-09): `web/data` ·
#   `data/processed` 의 `_manifest.json` 키 317종 중 `as_of` · `frozen_at` ·
#   `git_sha` 는 **0종**이다. 생기면 울어야 하므로 그 실측을
#   `tests/test_write_stable.py` 가 든다.
STAMP_KEYS = ("generated_at", "as_of", "frozen_at", "git_sha")


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
                 keys: tuple[str, ...] = STAMP_KEYS,
                 tail: str = "") -> bool:
    """시각을 뺀 내용이 같으면 쓰지 않는다. 썼으면 True.

    ★ mtime 도 안 건드린다. 안 쓰는 것이 곧 "안 바뀌었다" 의 표현이다.

    ★ 2026-08-25 정정. 비교를 **JSON 왕복 뒤에** 한다. 파이썬 객체끼리 비교하면
      파일에 나가는 형태와 다르다.

          BBOX_4326 = (126.907, ...)      ingest 가 넘기는 튜플
          "bbox_4326": [126.907, ...]     파일 안의 리스트
          (1, 2) != [1, 2]                → 항상 달라졌다고 본다

      실측 diff 는 `generated_at` 한 줄뿐인데 비교는 계속 실패하는, 눈으로는
      안 보이는 자리였다. 직렬화도 한 번만 한다 — 쓸 때 이 문자열을 그대로 쓴다.
    """
    # ★ `tail` 은 끝개행이다. 매니페스트는 안 붙이고(종전 그대로) 봉인 셋은
    #   붙인다 — 그 차이를 뭉개면 두 쪽 중 하나가 매 실행 한 바이트 다르다.
    text = json.dumps(obj, ensure_ascii=False, indent=2) + tail
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = None
        if isinstance(old, dict) and _borrow_stamps(json.loads(text), old, keys) == old:
            return False
    path.write_text(text, encoding="utf-8")
    return True


def read(path: Path) -> dict:
    """없거나 깨졌으면 빈 dict. 부르는 쪽이 매번 try 를 쓰지 않게 한다."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}
