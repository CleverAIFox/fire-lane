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
부류  생산   산출물·대장·그림을 만든다  (DECISIONS §398)
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



# ── 감지 단위 ────────────────────────────────────────────────────
#
# ★ 2026-09-29 (DECISIONS §307). **어떤 단위로 쪼개고 어떻게 감지하는가.**
#   §297 이 이 물음에 `tools/verify.sh` **하나에 대해서만** 답했다. 같은 병이
#   다른 파일에 그대로 남아 있었고, 배치 L 이 실측했다 — 도장 67개가 죽었고
#   원인을 세니 —
#
#       sources.yaml               25절   블록 하나를 **추가**했다
#       tests/test_contract.py     21절   함수 하나를 고쳤다
#       tests/test_r3.py            7절   상수 한 글자(16→17)
#       tests/test_ledger_outputs   6절
#       본문(정말 글이 바뀜)         5절   ← 이것만 진짜다
#       나머지                      3절
#
#   **67 중 62 가 「절의 주장은 그대로인데 지목한 파일이 자랐다」다.**
#
# ★ 규약 — 감지 단위는 **절이 지목한 대상의, 절이 주장하는 부분**이다.
#
#       목록 파일(verify.sh)   절이 함께 지목한 도구를 부르는 줄      §297
#       대장(sources.yaml)     절이 이름을 든 최상위 키 블록          §307
#       시험 파일(tests/*.py)  절이 이름을 든 시험 함수               §307
#       그 외                  파일 전체 (기본값)
#
#   셋 다 **같은 안전장치**를 갖는다 — 절이 이름을 든 것이 파일에서 **사라지면**
#   지문이 움직인다. 빈 지문을 내지 않는다. 그것이 없으면 「관문을 떼는 것」이
#   조용히 통과하고, 그때 이 관점은 검사를 끄는 것과 한 글자 차이가 된다.
#
# ★ 이 변경이 죽이는 도장은 **위 셋을 지목하는 절뿐이다.** 다른 절의 지문은
#   `return raw` 경로라 한 비트도 안 움직인다 — 즉 §298 이 정한 이관을 62절에
#   대해서만 하면 된다. 그리고 그 62절은 **이미 무효**다.
LIST_VIEW = ("tools/verify.sh",)
#: 대장 — 최상위 키가 곧 「무엇을 선언하는 칸인가」다. 배치마다 항목이 는다.
KEY_VIEW = ("sources.yaml",)
# ★ 지문 공식의 판. 공식이 바뀌면 그 공식이 **관점을 바꾼 파일을 지목하는** 도장이
#   무효가 되므로, 그때는 「옛 공식에서 유효했는가」를 증명해 옮긴다(§297 · §298).
#   이 값이 도장에 박혀 있어 **어느 공식으로 찍힌 도장인지** 나중에 갈릴 수 있다.
FP_METHOD = "view-v2"
_STEP = re.compile(r'^\s*(?:step|note)\s+"([^"]+)"', re.M)
_YKEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):", re.M)


def _is_test(path: str) -> bool:
    """파이썬 시험 파일인가. **규칙이지 목록이 아니다** — 시험은 수십 개다.

    ★ `web/navi/test/*.ts` 는 안 든다. 타입스크립트를 여기서 파싱하지 않는다 —
      파서를 하나 더 들이는 것이 이 고침의 내용이 아니고, 그 파일들을 지목하는
      절은 지금 없다. 생기면 그때 넓힌다(그때까지는 파일 전체를 문다 = 엄격한 쪽).
    """
    return path.startswith("tests/") and path.endswith(".py")


def _blocks(txt: str, keys: list[str]) -> str:
    """최상위 키 `keys` 의 블록만 남긴다. 들여쓴 줄은 그 키에 딸린 것으로 본다."""
    out, take = [], False
    for ln in txt.splitlines():
        m = _YKEY.match(ln)
        if m:
            take = m.group(1) in keys
        if take:
            out.append(ln)
    return "\n".join(out)


def _funcs(txt: str, names: list[str]) -> str:
    """시험 함수 `names` 의 본문만 남긴다. 못 파싱하면 파일 전체를 돌려준다."""
    import ast as _ast
    try:
        tree = _ast.parse(txt)
    except SyntaxError:
        return txt
    lines = txt.splitlines()
    out = []
    for node in tree.body:
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and node.name in names:
            out.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
    return "\n\n".join(out)




def view_v1(path: str, raw: bytes, others: list[str], text: str = "") -> bytes:
    """**옛 관점(`view-v1`).** `legacy` 지문을 내려고 남긴다 — 지우면 v1 로 찍힌
    도장을 받을 길이 없고, 그러면 공식을 바꾼 배치가 도장 320개를 죽인다.

    ★ 이관 코드가 아니다. §298 이 「이관 코드는 도구에 남기지 않는다」고 적은
      것은 **「옛 공식에서 유효했다」로 도장을 옮기는 길**을 상설하지 않겠다는
      뜻이었다. 이것은 다르다 — `LEGACY_BODIES`(§273-10)와 같은 자리이고,
      옮기는 것이 아니라 **같은 사실을 옛 표기로도 읽는 것**이다. 내용이 한 글자라도
      움직이면 v1 지문도 같이 움직여 여전히 죽는다.
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


#: 옛 관점 판들. **새것이 앞이다.** `docseal.survey` 가 `legacy` 지문을 여기서 낸다.
LEGACY_VIEWS = (view_v1,)


def view(path: str, raw: bytes, others: list[str], text: str = "") -> bytes:
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
    txt = raw.decode("utf-8", errors="replace")

    if path in LIST_VIEW:
        keys = [o for o in others if o != path]
        if keys:
            lines = [ln for ln in txt.splitlines() if any(k in ln for k in keys)]
            if lines:
                return "\n".join(lines).encode("utf-8")
            return ("★ 안 부른다: " + " ".join(sorted(keys))).encode("utf-8")
        return "\n".join(_STEP.findall(txt)).encode("utf-8")

    # ── 대장 · 절이 이름을 든 최상위 키 블록 ────────────────────
    if path in KEY_VIEW:
        keys = sorted(set(_YKEY.findall(txt)))
        named = [k for k in keys if k in text]
        if not named:
            # 절이 키를 하나도 안 든다 — 그 절의 주장은 「이런 칸들이 있다」다.
            # 항목이 늘어도 안 죽고, 칸이 **없어지면** 죽는다.
            return ("칸: " + " ".join(keys)).encode("utf-8")
        return _blocks(txt, named).encode("utf-8")

    # ── 시험 파일 · 절이 이름을 든 시험 함수 ────────────────────
    if _is_test(path):
        import ast as _ast
        try:
            tree = _ast.parse(txt)
        except SyntaxError:
            return raw
        have = sorted(n.name for n in tree.body
                      if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                      and n.name.startswith("test"))
        named = [n for n in have if n in text]
        # ★ 제거 감지는 **대체 목록이 한다.** 절이 든 시험이 사라지면 `named` 가
        #   비고, 그러면 아래 「시험: …」 목록으로 떨어지는데 그 목록에서 그 이름이
        #   빠졌으므로 지문이 움직인다. 「없어진 시험」을 따로 박으려 했다가 오작동을
        #   냈다 — 절은 **다른 파일의** 시험 이름도 들기 때문에, 이 파일에 없다는 것이
        #   「없어졌다」를 뜻하지 않는다(실측: 한 절이 세 파일에 같은 거짓 지문을 냈다).
        if not named:
            # 절이 함수를 안 든다 — 주장은 「이 시험들이 있다」다. 시험을 **빼면**
            # 죽고, 새 시험을 붙이면 안 죽는다. 후자는 그 절의 주장이 아니다.
            return ("시험: " + " ".join(sorted(have))).encode("utf-8")
        return _funcs(txt, named).encode("utf-8")

    return raw


def digest(text: str, files: list[str], vf=view) -> str:
    """절의 지문. `vf` 는 관점 — 기본은 현행(`view`), `LEGACY_VIEWS` 로 옛 판도 낸다."""
    h = hashlib.sha256(text.encode("utf-8"))
    for f in files:
        h.update(f.encode("utf-8"))
        h.update(hashlib.sha256(vf(f, (ROOT / f).read_bytes(), files, text)).digest())
    return h.hexdigest()[:16]


def parts(text: str, files: list[str], vf=view) -> dict[str, str]:
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
        out[f] = hashlib.sha256(vf(f, (ROOT / f).read_bytes(), files, text)).hexdigest()[:16]
    return out




def claim(text: str, dms) -> str:
    """절이 **산문으로** 주장하는 부분 — 강제자 칸을 뺀다.  (DECISIONS §348)

    도장의 물음은 「이 절의 본문이 아직 참인가」다. 그 물음이 성립하려면 본문이
    지목 파일의 **내용에 대해 주장**을 해야 한다. 강제자 칸은 주장이 아니라
    **배선**이고, 배선의 실재는 `tools/dms.py` 의 `verify` 가 멤버까지 이미
    기계로 본다(§229). 그래서 칸만이 코드 쪽인 절은 도장 대상이 아니다.

    ★ 칸을 가르는 정규식의 정본은 `tools/dms.py` 다 — 여기서 다시 적지 않고
      모듈을 **받는다.** 두 벌이 되면 갈린다(2족).
    ★ 코드펜스 안의 `강제자` 는 예시다. `dms` 의 수집 루프와 같은 규칙으로 센다.

    ★ 2026-10-02 **정정**(§348-4). `dms.FIELD` 만으로는 모자랐다. 그 정규식은
      줄머리 「강제자」 뒤가 한글이 아니면 칸으로 보는데, **띄어쓰기는 한글이
      아니다** — 그래서 「강제자 칸만이 코드 쪽인 절은 …」 같은 **산문**이 칸으로
      잡혔다. `dms` 에서는 칸이 하나 더 붙을 뿐이지만 여기서는 그 줄부터 빈 줄까지를
      **버린다.** 같은 정규식이 두 곳에서 심각도가 다르다. 실측으로 세 절이
      산문 지목을 잃었고 그중 하나가 **`MASTER §21-0`, 도장 장치를 정의하는 바로
      그 절**이다 — 이 함수가 제 근거 문서를 분모에서 밀어냈다.
      그래서 **칸의 꼴**을 하나 더 본다: 칸은 백틱 경로를 들거나 `없음` · `—` 로
      시작한다. 못 가리면 **안 버린다** — 넓게 틀리면 안 찍어도 될 것을 찍고,
      좁게 틀리면 **주장하는 절이 도장 밖으로 나간다.** 뒤쪽이 되돌릴 수 없다.
    """
    out: list[str] = []
    drop = fence = False
    for ln in text.splitlines():
        if dms.FENCE.match(ln):
            fence = not fence
        if drop:
            drop = not dms.FIELD_END.match(ln)
            if drop:
                continue
        elif not fence and dms.FIELD.match(ln) and _looks_like_field(ln, dms):
            drop = True
            continue
        out.append(ln)
    return "\n".join(out)


def _looks_like_field(line: str, dms) -> bool:
    """그 줄이 **정말 강제자 칸인가.** 산문과 가르는 둘째 물음(§348-4)."""
    rest = dms.FIELD.sub("", line).strip()
    return "`" in rest or rest.startswith(("없음", "—", "-", "("))
