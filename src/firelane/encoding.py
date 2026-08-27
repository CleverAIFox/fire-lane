#!/usr/bin/env python3
"""
encoding.py — 인코딩 판별과 정규화. **디코드 성공은 증거가 아니다.**

── 왜 이 모듈이 필요한가 ───────────────────────────────────────
`chardet` 을 쓰지 않는다. 한국어 레거시 인코딩에서 confidence 가 낮게 나오고,
그 값을 임계값으로 자르는 순간 판정이 확률이 된다. 우리는 소스가 여섯
기관뿐이고 인코딩이 사실상 넷이다. **후보를 좁히고 검증을 세게 하는 편이
낫다.**

★ 핵심 — **CP949 는 거의 모든 바이트열을 디코드한다.** 아무 이진 파일이나
  넣어도 성공한다. 그래서 "cp949 로 읽히니까 cp949 다" 는 추론이 성립하지
  않는다. UTF-8 은 자기검증적이라 그쪽이 먼저다. CP949 는 디코드가 아니라
  **결과물의 한글 비율**로 판정한다.

    UTF-8   strict 디코드 성공 = 강한 증거 (오탐률 매우 낮다)
    CP949   디코드 성공 = 증거 아님. 한글이 나와야 증거다

── 이 저장소가 겪은 것 ─────────────────────────────────────────
    building_ledger   BOM 붙은 utf-8. 나머지 CSV 는 전부 cp949 — 여기만 다르다
    juso zip          .dbf 가 CP949 · 내부 한글 파일명이 CP437 로 깨진다
    ngii basemap      .cpg 가 UTF-8 이라 적혀 있으나 실제 dbf 는 cp949 였다
                      (2026-08-17 실물 확인. 선언이 틀렸다)

세 번째가 제일 중요하다 — **선언을 믿으면 안 된다.** `.cpg` · `.prj` 는
제공기관이 적는 것이고 틀린 채로 배포된다. 실물로 판정하고 선언과 대조한다.

── 계층별 정책 ─────────────────────────────────────────────────
    raw    바이트를 건드리지 않는다. 판별만 하고 기록한다
    norm   UTF-8(BOM 없음) · LF 로 통일한다. **값은 안 바꾼다**

IN    파일 경로
OUT   없음 (판별) / norm 계층 (정규화 시 호출자가 쓴다)
PARAM 없음
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 판별 순서가 곧 신뢰도 순서다. 자기검증적인 것부터 본다.
CANDIDATES = ("utf-8-sig", "utf-8", "cp949", "utf-16", "cp437")

BOMS = {
    b"\xef\xbb\xbf": "utf-8-sig",
    b"\xff\xfe\x00\x00": "utf-32",
    b"\x00\x00\xfe\xff": "utf-32",
    b"\xff\xfe": "utf-16",
    b"\xfe\xff": "utf-16",
}

HANGUL = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
# CP949 로 잘못 읽힌 UTF-8 의 지문. 한글 UTF-8 3바이트가 CP949 에서
# 한자·특수문자로 튄다. 이 글자들이 뭉쳐 나오면 이중 디코드다.
MOJIBAKE = re.compile(r"[¿½Ã¬â€™ìíîï]{2,}|[\ufffd]")
# 한글 파일명이 CP437 로 깨진 꼴. juso zip 이 이 형태다.
CP437_MANGLED = re.compile(r"[\u2500-\u25ff\u2190-\u21ff]{2,}")

TEXT_EXT = {"csv", "txt", "tsv", "json", "yaml", "xml", "prj", "cpg", "dbf"}


class EncodingError_(RuntimeError):
    pass


@dataclass
class Verdict:
    encoding: str | None          # 판정. 못 정하면 None
    confidence: str               # strong | weak | none
    hangul_ratio: float
    newline: str | None           # lf | crlf | cr | mixed | None
    bom: bool
    notes: list[str]

    @property
    def ok(self) -> bool:
        return self.encoding is not None and self.confidence != "none"


def sniff_bom(head: bytes) -> str | None:
    for sig, name in BOMS.items():
        if head.startswith(sig):
            return name
    return None


def _hangul_ratio(text: str) -> float:
    if not text:
        return 0.0
    return len(HANGUL.findall(text)) / len(text)


def _corruption_notes(text: str) -> list[str]:
    """이미 한 번 깨진 뒤 저장된 파일의 지문.

    ★ 이 검사는 **디코드에 성공한 뒤에** 한다. 디코드 성공은 파일이
      멀쩡하다는 뜻이 아니다 — 깨진 결과를 다시 저장하면 그 파일은
      문법적으로 완전한 UTF-8 이 된다. U+FFFD 가 그 증거다.
      원본은 복구 불가이므로 재취득 대상이다.
    """
    out = []
    if "\ufffd" in text:
        n = text.count("\ufffd")
        out.append(
            f"★ 치환문자 U+FFFD {n}개. 이 파일은 이미 한 번 깨진 뒤 저장됐다. "
            "복구 불가 — 재취득 대상이다")
    if MOJIBAKE.search(text):
        out.append("★ 이중 디코드 지문. UTF-8 을 CP949 로 읽은 꼴이다")
    if CP437_MANGLED.search(text):
        out.append(
            "★ CP437 로 깨진 한글로 보인다. juso zip 내부 파일명이 이 형태다 "
            "— recover_cp437() 로 되돌린다")
    return out


def _newline(raw: bytes) -> str | None:
    crlf, lf, cr = raw.count(b"\r\n"), raw.count(b"\n"), raw.count(b"\r")
    lf_only, cr_only = lf - crlf, cr - crlf
    kinds = [k for k, n in (("crlf", crlf), ("lf", lf_only), ("cr", cr_only)) if n]
    if not kinds:
        return None
    return kinds[0] if len(kinds) == 1 else "mixed"


def detect(path: Path, *, sample: int = 1 << 20) -> Verdict:
    """실물 바이트로 판정한다. 선언은 보지 않는다."""
    raw = Path(path).read_bytes()[:sample]
    notes: list[str] = []
    bom = sniff_bom(raw)
    nl = _newline(raw)

    if bom:
        try:
            text = raw.decode(bom, errors="strict")
        except UnicodeDecodeError:
            # 자를 때 멀티바이트 경계를 밟은 것일 수 있다. 관대하게 한 번 더.
            text = raw.decode(bom, errors="ignore")
            notes.append("표본 경계에서 잘렸다. 전량 검증 필요")
        return Verdict(bom, "strong", _hangul_ratio(text), nl, True, notes)

    # ⓪ ASCII 전용 — 어느 후보로 읽어도 같다. **판정하지 않는 것이 맞다.**
    #    ★ 여기를 utf-8 로 단정하면 `encoding: cp949` 선언과 충돌하는
    #      것으로 보고돼 오탐이 난다. ASCII 는 넷 모두와 호환이므로
    #      "겹친다" 고 말해야지 "utf-8 이다" 라고 말하면 안 된다.
    if not raw.translate(None, bytes(range(0x80))):
        notes.append("ASCII 전용이라 인코딩을 특정할 수 없다(모두와 호환)")
        return Verdict("ascii", "strong", 0.0, nl, False, notes)

    # ① UTF-8 — 자기검증적이다. 성공하면 강한 증거.
    utf_ok = False
    try:
        text = raw.decode("utf-8", errors="strict")
        utf_ok = True
    except UnicodeDecodeError:
        # 표본 끝에서 잘린 경우를 배제한다.
        for back in range(1, 5):
            try:
                text = raw[:-back].decode("utf-8", errors="strict")
                utf_ok = True
                notes.append("표본 끝 멀티바이트 경계 보정")
                break
            except UnicodeDecodeError:
                continue
    if utf_ok:
        hr = _hangul_ratio(text)
        notes += _corruption_notes(text)
        return Verdict("utf-8", "strong", hr, nl, False, notes)

    # ② CP949 — 디코드는 거의 항상 된다. 한글이 나와야 증거다.
    text = None
    try:
        text = raw.decode("cp949", errors="strict")
    except UnicodeDecodeError:
        # ★ 표본 끝에서 멀티바이트가 잘린 경우를 먼저 배제한다.
        #   UTF-8 경로에는 이 보정이 있었는데 CP949 경로에는 없었다.
        #   그래서 1MB 표본을 읽는 5MB CSV 가 **매번 U+FFFD 1개**를 냈고,
        #   "이미 깨진 뒤 저장됐다 — 재취득 대상" 이라는 오탐이 떴다.
        #   재취득해도 같은 경고가 나와 무엇이 진짜인지 알 수 없었다
        #   (2026-08-27, gjcity_parking_enforce_..._20240108.csv).
        #
        #   ★ 잘못된 경보는 진짜 경보를 못 믿게 만든다. 경계 오차를
        #     손상으로 세면 안 된다.
        for back in range(1, 3):
            try:
                text = raw[:-back].decode("cp949", errors="strict")
                notes.append("표본 끝 멀티바이트 경계 보정")
                break
            except UnicodeDecodeError:
                continue
    if text is None:
        text = raw.decode("cp949", errors="replace")
        notes.append("cp949 로도 완전히 안 읽힌다 — 이진 파일이거나 손상")
    hr = _hangul_ratio(text)
    notes += _corruption_notes(text)
    if hr >= 0.02:
        return Verdict("cp949", "strong", hr, nl, False, notes)
    if hr > 0:
        notes.append(f"한글 비율 {hr:.4f} 로 낮다. 표본을 늘려 재확인할 것")
        return Verdict("cp949", "weak", hr, nl, False, notes)

    notes.append(
        "한글이 하나도 없다. 인코딩을 확정할 수 없다 — "
        "ASCII 전용이거나 텍스트가 아니다")
    return Verdict(None, "none", 0.0, nl, False, notes)


def recover_cp437(name: str) -> str:
    """CP437 로 깨진 한글 문자열을 되돌린다.

    zip 스펙은 파일명 인코딩을 CP437 로 못박고 있고, 한국 공공기관이
    만든 zip 은 실제로는 CP949 를 그대로 넣는다. 파이썬 zipfile 이
    스펙대로 CP437 로 읽어 깨진다. 왕복시키면 원문이 나온다.
    """
    try:
        return name.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def verify_declared(path: Path, declared: str) -> list[str]:
    """대장의 선언과 실물을 대조한다. **선언을 믿지 않는 자리다.**"""
    v = detect(path)
    out = []
    if not v.ok:
        out.append(f"{Path(path).name}: 인코딩 판별 실패 ({'; '.join(v.notes)})")
        return out
    norm = {"utf8": "utf-8", "utf-8-sig": "utf-8-sig", "euc-kr": "cp949",
            "ms949": "cp949", "uhc": "cp949"}
    d = norm.get(declared.lower(), declared.lower())
    got = v.encoding
    if got == "ascii":
        # 한글이 하나도 없다. 어느 선언이든 참이고 어느 선언도 반증되지
        # 않는다. 문제로 올리지 않는다 — 매번 뜨는 경고는 아무도 안 읽고,
        # 그러면 진짜 하나를 놓친다(ingest.build 가 같은 이유로 SINGLE_PICK
        # 을 좁혔다).
        return [x for x in v.notes if x.startswith("★")]
    same = (d == got) or (d, got) in {("utf-8", "utf-8-sig"),
                                      ("utf-8-sig", "utf-8")}
    if not same:
        out.append(
            f"{Path(path).name}: 선언 {declared!r} · 실물 {got!r}"
            f" (한글 비율 {v.hangul_ratio:.3f}, 신뢰도 {v.confidence})\n"
            "  ★ .cpg · .prj 는 제공기관이 적는 값이고 틀린 채로 배포된다.\n"
            "    2026-08-17 에 ngii basemap 이 정확히 그랬다.")
    if v.confidence == "weak":
        out.append(f"{Path(path).name}: 판정 신뢰도 낮음 — {'; '.join(v.notes)}")
    out += [f"{Path(path).name}: {n}" for n in v.notes if n.startswith("★")]
    return out


def to_norm(src: Path, dst: Path, *, declared: str | None = None) -> dict:
    """raw → norm. **인코딩과 개행만 바꾼다. 값은 안 바꾼다.**

    ★ 여기서 컬럼명을 고치거나 공백을 털고 싶어지는데, 하면 안 된다.
      norm 은 '형식만 통일한 raw' 이고 그 경계가 흐려지는 순간
      "원본이 그랬는지 우리가 고친 건지" 를 못 가린다.
    """
    v = detect(src)
    enc = declared or v.encoding
    if enc is None:
        raise EncodingError_(
            f"{src} 의 인코딩을 확정할 수 없다. 대장에 encoding 을 적어라.")
    text = src.read_bytes().decode(enc, errors="strict")
    text = text.removeprefix("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(text.encode("utf-8"))
    return {"src_encoding": enc, "src_newline": v.newline,
            "dst_encoding": "utf-8", "dst_newline": "lf",
            "hangul_ratio": round(v.hangul_ratio, 4), "notes": v.notes}
