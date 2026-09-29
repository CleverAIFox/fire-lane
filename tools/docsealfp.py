#!/usr/bin/env python3
"""
docsealfp.py — 도장의 **지문**을 낸다. 판정도 대장도 여기 없다.

★ 왜 갈랐나 (2026-09-29 · DECISIONS §297 · §298). `docseal.py` 가 621줄로 상한을
  넘었다. 그 파일이 하는 일은 둘이다 —

    지문을 낸다        절이 주장하는 것을 어떤 관점으로 해시하는가
    대장을 운영한다     찍고 · 세고 · 무효를 보이고 · 읽을 줄을 낸다

  앞의 것이 이 파일이다. `deliver.py` ↔ `delivercheck.py` 와 같은 꼴이고, 같은
  이유다 — **판별식은 순수하고 시험에서 직접 부를 수 있어야 한다.**

★ 이 파일은 저장소에만 산다. `tools/fl.sh` 처럼 zip 으로 배달되는 파일이 아니므로
  갈라도 배달물이 둘이 되지 않는다(§295 의 예외 사유와 반대쪽이다).

IN    저장소 파일 · `firelane.generated.REGISTRY`
OUT   없음 (순수 함수)
PARAM LIST_VIEW · FP_METHOD
밖    **판정을 안 한다.** 유·무효를 정하는 것은 `docseal.valid` 이고 여기서는
      지문만 낸다. 어느 절이 어느 파일을 지목하는가(`refs`)도 저 파일이 든다.
      생성물인지 아닌지의 정본도 여기가 아니라 `firelane.generated.REGISTRY` 다.
"""
from __future__ import annotations

import functools
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=1)
def _gen_roots() -> tuple[tuple[str, str], ...]:
    """생성물 등록부. **정본은 `firelane.generated.REGISTRY` 하나다.**

    ★ 2026-09-29 (DECISIONS §298). §278-10 이 「매번 바뀌는 것은 도장의 기반이 못
      된다」를 적고 그 규칙을 **미추적 파일에만** 걸었다. 그런데 추적되는 생성물이
      있다 — `web/data/_manifest.json` · `data/processed/_manifest.json` ·
      `data/dms/SEAL.json`. 재잠금이 그것들을 다시 쓰므로 **재잠금마다 그 파일을
      지목한 절 아홉이 죽었다.** 실기 2026-09-29(배치 H 재잠금 PR #230)에서 그랬다.

    ★ 판정 기준은 「추적되는가」가 아니라 **「기계가 매번 다시 쓰는가」**다.
      그 물음의 정본은 `generated.REGISTRY` 이고, 여기서 또 목록을 쓰면 두 집에
      사는 사실이 된다(2족). 등록부를 읽는다.
    """
    # ★ `sys.path` 를 손대지 않는다 — `pyproject` 의 `pythonpath` 가 `src` 를 얹고,
    #   손대면 `test_layering::test_sys_path_해킹이_없다` 가 운다(그 관문이 이 줄을 잡았다).
    from firelane import generated as _g
    return tuple((x.path, x.kind) for x in _g.REGISTRY)


def _generated(path: str) -> bool:
    """`path` 가 등록부가 든 생성물인가. 디렉터리 항목은 그 아래 전부를 덮는다."""
    for base, kind in _gen_roots():
        if path == base or (kind == "dir" and path.startswith(base + "/")):
            return True
    return False



# ── 목록 파일의 절별 관점 ────────────────────────────────────────
#   `tools/verify.sh` 는 **검사의 목록**이다. 바이트로 물면 단계를 하나 붙이거나
#   래칫 한 글자를 고칠 때마다 그 파일을 지목한 절 전부가 죽는다.
LIST_VIEW = ("tools/verify.sh",)
# ★ 지문 공식의 판. 공식이 바뀌면 옛 도장은 **전부** 무효가 되므로, 그때는
#   「옛 공식에서 유효했는가」를 증명해 옮긴다(일회성 이관 · §297). 이 값이
#   도장에 박혀 있어 **어느 공식으로 찍힌 도장인지** 나중에 갈릴 수 있다.
FP_METHOD = "view-v1"
_STEP = re.compile(r'^\s*(?:step|note)\s+"([^"]+)"', re.M)


def view(path: str, raw: bytes, others: list[str]) -> bytes:
    """절이 **주장하는 것만** 지문에 넣는다.  (DECISIONS §297 · PLAN W13-10)

    ★ 실측 2026-09-29 — `verify.sh` 의 `COV_MIN` 을 34 에서 35 로 **한 글자**
      바꾸자 27절의 도장이 한꺼번에 무효가 됐다. 그 절들이 주장하는 것은
      「이 관문이 이 도구를 부른다」이고, 단계가 늘어난 것이 그 주장을 거짓으로
      만들지 않는다. 배치마다 27절을 다시 찍으면 그것이 도장 찍기다(§290-2).

    ★ 그래서 `verify.sh` 에서는 **그 절이 함께 지목한 도구를 부르는 줄**만 본다.
      26/27 절이 다른 도구를 함께 지목하므로 이 관점이 거의 전부를 덮는다.
      함께 지목한 것이 없으면 **단계 이름 목록**을 본다 — 그 절의 주장이
      「이런 단계가 있다」이기 때문이다.

    ★ **느슨해지는 것이 아니다.** 지목한 도구를 `verify.sh` 에서 떼면 그 줄이
      사라져 지문이 바뀌고 여전히 운다. 안 무는 것은 **그 절과 무관한 줄**뿐이다.
      그리고 도구를 아예 안 부르는 경우에는 빈 지문을 내지 않고 그 사실을 박는다 —
      빈 것을 해시하면 「안 부른다」가 조용히 통과한다(빈 그물).
    """
    if path not in LIST_VIEW:
        return raw
    keys = [o for o in others if o != path]
    txt = raw.decode("utf-8", errors="replace")
    if keys:
        lines = [ln for ln in txt.splitlines() if any(k in ln for k in keys)]
        if lines:
            return "\n".join(lines).encode("utf-8")
        return ("★ 안 부른다: " + " ".join(sorted(keys))).encode("utf-8")
    return "\n".join(_STEP.findall(txt)).encode("utf-8")


def digest(text: str, files: list[str]) -> str:
    h = hashlib.sha256(text.encode("utf-8"))
    for f in files:
        h.update(f.encode("utf-8"))
        h.update(hashlib.sha256(view(f, (ROOT / f).read_bytes(), files)).digest())
    return h.hexdigest()[:16]


def parts(text: str, files: list[str]) -> dict[str, str]:
    """**한 덩어리 지문을 쪼갠 것.** 무효가 됐을 때 어디가 움직였는지 말하려고 든다.

    ★ 2026-09-28 (DECISIONS §290). F 배치에서 이 관문이 네 절에 빨간불을 켰고
      메시지는 그 절이 **지목하는 파일 목록**을 냈다. 그것은 「무엇이 바뀌었나」가
      아니라 「무엇을 보고 있나」다. 네 절이 왜 무효인지 알아내려고 지문을 손으로
      다시 계산했다 — **관문이 사람에게 조사를 미룬 것이고, 미룬 조사는 미뤄진다.**
      한 덩어리 sha 는 「같다/다르다」만 말할 수 있으므로 판별식 자체를 쪼갠다.

    ★ `sha` 는 그대로 둔다. 이 칸은 **판정을 안 바꾼다** — 유·무효는 여전히
      `sha` 하나로 정해지고, 이 칸은 무효일 때 읽는 설명이다. 판정을 두 군데서
      내면 그 둘이 어긋나는 날이 온다(2족).
    """
    out = {"본문": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]}
    for f in files:
        # ★ `digest` 와 **같은 관점**을 써야 한다. 다르면 「무효인데 어디가 움직였는지
        #   아무 칸도 안 바뀌었다」가 나온다 — 설명이 판정과 어긋나는 꼴이다(§297).
        out[f] = hashlib.sha256(view(f, (ROOT / f).read_bytes(), files)).hexdigest()[:16]
    return out


