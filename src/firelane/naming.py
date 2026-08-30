#!/usr/bin/env python3
"""
naming.py — raw 파일명 문법의 정본. **파서가 곧 규칙이다.**

── 문법 ────────────────────────────────────────────────────────
    {provider}/{provider}_{dataset}_{scope}_{vintage}[_{part}][_r{rev}].{ext}

    provider   제공기관. 폴더명과 **같아야 한다**(이중 기록 → 대조 가능)
    dataset    무엇인가. snake_case. 언더스코어 허용
    scope      행정 범위. firelane.scope 통제 어휘
    vintage    ★ 데이터 기준일. 다운로드일이 아니다. YYYYMMDD|YYYYMM|YYYY
    part       도엽·분할본. 선택
    rev        같은 vintage 재배포분. 선택
    ext        소문자 정규화본

── 왜 오른쪽에서 파싱하나 ──────────────────────────────────────
`dataset` 에 언더스코어가 들어간다(`kfs_pumptruck` · `parking_enforce` ·
`bldg_ledger`). 왼쪽부터 세면 필드 경계를 못 찾는다. 그래서 **오른쪽 끝을
고정점으로 잡는다** — `ext` 는 점 뒤, `rev` 는 `r\\d+`, `vintage` 는 순수
숫자, `scope` 는 통제 어휘. 이 넷이 결정되면 남은 가운데가 `dataset` 이다.

이 선택의 값어치는 **기존 36건을 한 건도 개명하지 않고 문법을 세울 수
있다는 것**이다. 개명은 `_acquire.json` 38건의 sha 키와 대장 `file` 36줄을
동시에 무효화한다. 문법을 위해 대장을 깨는 것은 앞뒤가 바뀐 것이다.

── 확장자 ──────────────────────────────────────────────────────
철자만 통일한다. **포맷이 다르면 다른 파일이다.**

    .JPEG .jpeg → .jpg      같은 포맷의 다른 철자
    .TIFF .tiff → .tif
    .htm        → .html
    .hwp .hwpx .pdf         ★ 통합하지 않는다

★ `.hwp` 와 `.pdf` 를 같은 자산으로 뭉갠 것이 2026-08-25 사고의 원인이다.
  대장이 `safety/safety_kfs_pumptruck_20251224.*` 라고 적어 두 판을 하나로
  봤고, `ingest.build()` 는 `hits[0]` 만 쓰는데 `kind: raw_only` 는
  다중매칭 경고(`SINGLE_PICK`)에서 빠져 있었다. PDF 를 한 장 넣으면
  `_manifest.json` 의 `source_sha256` 이 **경고 없이** 바뀐다.

  그래서 이 모듈은 확장자 와일드카드를 **문법 위반으로 판정한다.**
  대장은 `files:` 리스트와 `primary:` 로 적는다.

IN    없음 (순수 함수)
OUT   없음
PARAM 없음
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from firelane import scope as sc

# ── 확장자 정규화 ─────────────────────────────────────────────
EXT_ALIAS = {
    "jpeg": "jpg", "tiff": "tif", "htm": "html", "yml": "yaml",
    "shx": "shx", "dbf": "dbf",
}
# 압축·이중 확장자. `.tar.gz` 를 `.gz` 로 읽으면 내용물을 오판한다.
DOUBLE_EXT = ("tar.gz", "tar.bz2", "tar.xz")

PROVIDER_RE = re.compile(r"^[a-z][a-z0-9]{1,15}$")
DATASET_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
VINTAGE_RE = re.compile(r"^(\d{4})(\d{2})?(\d{2})?$")
PART_RE = re.compile(r"^[a-z0-9]+$")
REV_RE = re.compile(r"^r(\d+)$")

WILDCARD = set("*?[]")


class NameError_(ValueError):
    """파일명이 문법 밖이다."""


@dataclass
class Name:
    provider: str
    dataset: str
    scope: str
    vintage: str
    ext: str
    part: str | None = None
    rev: int | None = None
    #  파싱 중 발견한 것. 실패는 아니지만 사람이 봐야 한다.
    warnings: list[str] = field(default_factory=list)

    def filename(self) -> str:
        bits = [self.provider, self.dataset, self.scope, self.vintage]
        if self.part:
            bits.append(self.part)
        if self.rev is not None:
            bits.append(f"r{self.rev}")
        return "_".join(bits) + "." + self.ext

    def relpath(self) -> str:
        return f"{self.provider}/{self.filename()}"

    @property
    def clean(self) -> bool:
        return not self.warnings


# ── 확장자 ────────────────────────────────────────────────────
def split_ext(name: str) -> tuple[str, str]:
    """(줄기, 정규화 확장자). 이중 확장자를 먼저 본다."""
    low = name.lower()
    for d in DOUBLE_EXT:
        if low.endswith("." + d):
            return name[: -(len(d) + 1)], d
    if "." not in name:
        raise NameError_(f"확장자가 없다: {name!r}")
    stem, _, ext = name.rpartition(".")
    ext = ext.lower()
    if not ext.isalnum():
        raise NameError_(f"확장자가 영숫자가 아니다: {ext!r}")
    return stem, EXT_ALIAS.get(ext, ext)


def normalize_ext(name: str) -> str:
    stem, ext = split_ext(name)
    return f"{stem}.{ext}"


# ── 원본명 → 정규 줄기 ────────────────────────────────────────
_HANGUL = re.compile(r"[가-힣]")


def slugify(text: str) -> str:
    """사람이 준 문자열을 dataset 토큰 후보로 바꾼다.

    ★ **자동 채택하지 않는다.** 제안까지만 한다. 한글 원본명을 기계가
      영문으로 옮기면 `소방펌프차` 가 `sobangpeompeuca` 가 되고, 대장의
      `kfs_pumptruck` 과 아무 관계 없는 이름이 생긴다. 사람이 정한다.
    """
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"\([^)]*\)", " ", t)          # 괄호 안 문서번호 등
    t = re.sub(r"[^a-z0-9가-힣]+", "_", t)
    return re.sub(r"_+", "_", t).strip("_")


def has_hangul(text: str) -> bool:
    return bool(_HANGUL.search(text))


# ── 파싱 ──────────────────────────────────────────────────────
def parse(name: str, *, folder: str | None = None, strict: bool = True) -> Name:
    """파일명 하나를 문법에 따라 오른쪽부터 가른다.

    `folder` 를 주면 `provider` 와 대조한다. 둘은 같은 사실의 두 기록이고
    어긋나면 어느 쪽이 맞는지 아무도 모른다.
    """
    if WILDCARD & set(name):
        raise NameError_(
            f"파일명에 와일드카드가 있다: {name!r}\n"
            "  ★ 대장의 file 글롭은 여기로 넘기지 않는다. 실물 이름을 준다.")

    stem, ext = split_ext(name)
    if has_hangul(stem):
        raise NameError_(
            f"파일명에 한글이 있다: {name!r}\n"
            "  ★ raw 는 기계가 읽는 자리다. 한글 원본명은 대장의\n"
            "    origin_name 에 보존하고 파일명은 정규화한다.")
    if stem != stem.lower():
        raise NameError_(f"대문자가 있다: {name!r}")

    bits = stem.split("_")
    if len(bits) < 4:
        raise NameError_(
            f"필드가 {len(bits)}개다. 최소 4개가 필요하다: "
            "provider_dataset_scope_vintage\n"
            f"  받은 것 — {name!r}\n"
            "  ★ 전국 자료도 스코프를 적는다(`kr`). 비워두면 '전국이라\n"
            "    생략한 것'과 '적기를 잊은 것'이 구분되지 않는다.")

    warn: list[str] = []

    # ── 고정점은 scope 다 ─────────────────────────────────────
    # ★ 처음엔 오른쪽 끝을 vintage 로 잡았다. 틀렸다 —
    #     ngii_ortho_jngj-donggu_20251231_35616037.tif
    #   에서 도엽번호 `35616037` 도 8자리 숫자라 vintage 와 안 갈린다.
    #   `3561-60-37` 은 달력에도 있는 날이 되어 조용히 통과했다.
    #
    #   숫자 모양으로는 못 가른다. **통제 어휘만이 고정점이 될 수 있다.**
    #   scope 를 오른쪽부터 찾고, 그 뒤는 전부 vintage·part·rev,
    #   그 앞은 전부 provider·dataset 이다.
    # ★ 두 번 훑는다. **정규·옛 스코프가 도엽 접두보다 우선**이다.
    #   한 번에 훑으면 `ngii_basemap_jngj-donggu_20260812_gj9708` 에서
    #   오른쪽의 `gj9708`(도엽)을 먼저 잡아 이미 정규화된 이름을 위반으로
    #   판정한다. 개명해 놓고 그것을 다시 지적하는 꼴이었다.
    idx = None
    for i in range(len(bits) - 1, 0, -1):
        if sc.known(bits[i]) or bits[i] in sc.LEGACY:
            idx = i
            break
    if idx is None:
        for i in range(len(bits) - 1, 0, -1):
            if bits[i].startswith(sc.LEGACY_PART_PREFIXES):
                idx = i
                break
    if idx is None:
        raise NameError_(
            f"스코프 토큰을 못 찾았다: {name!r}\n"
            f"  선언된 것 — {', '.join(sorted(sc.spec()))}\n"
            "  ★ 전국 자료도 `kr` 을 적는다. 스코프는 파일명 문법의\n"
            "    고정점이라, 없으면 vintage 와 도엽번호가 안 갈린다.")
    if idx > len(bits) - 2:
        raise NameError_(f"스코프 뒤에 vintage 가 없다: {name!r}")

    scope_tok = bits[idx]
    tail = bits[idx + 1:]
    bits = bits[:idx]

    rev = None
    m = REV_RE.match(tail[-1]) if len(tail) >= 2 else None
    if m:
        rev = int(m.group(1))
        tail = tail[:-1]

    part = None
    if len(tail) == 2:
        part = tail[1]
        if not PART_RE.match(part):
            raise NameError_(f"part 가 영숫자가 아니다: {part!r}")
    elif len(tail) != 1:
        raise NameError_(
            f"스코프 뒤 필드가 {len(tail)}개다. vintage[_part][_r{{n}}] 만 온다: "
            f"{name!r}")

    vintage = tail[0]
    if not VINTAGE_RE.match(vintage):
        # ★ 이 자리에 걸리는 실제 사례는 하나다 — `_gj_dong_`.
        #   `gj` 가 옛 스코프로 잡히고 `dong` 이 vintage 자리에 남는다.
        #   원인 진단을 붙여준다. 이건 오타가 아니라 **축 혼동**이다.
        hint = ""
        if scope_tok in sc.LEGACY and not vintage.isdigit():
            hint = (
                f"\n  ★ {scope_tok}_{vintage} 는 스코프가 아닐 가능성이 높다.\n"
                f"    `gj_dong` 은 행정구역 동구가 아니라 **동부소방서**다\n"
                f"    (fire_access · hydrant_summary). 관할기관은 행정구역과\n"
                f"    경계가 다르므로 scope 에 적으면 안 된다 —\n"
                f"      scope: jngj-donggu   authority: 동부소방서")
        raise NameError_(
            f"vintage 형식이 아니다: {vintage!r} (YYYYMMDD|YYYYMM|YYYY){hint}")
    if not _plausible_date(vintage):
        raise NameError_(f"vintage 가 달력에 없는 날이다: {vintage!r}")

    try:
        scope_alias, state = sc.resolve(scope_tok)
    except sc.ScopeError as e:
        if strict:
            raise NameError_(str(e)) from None
        scope_alias, state = scope_tok, "unknown"
        warn.append(f"스코프 미선언: {scope_tok!r}")
    if state == "legacy":
        warn.append(
            f"옛 스코프 토큰 {scope_tok!r} → {scope_alias!r} 로 개명 대상")
    elif state == "part":
        warn.append(
            f"{scope_tok!r} 는 스코프가 아니라 도엽이다. "
            f"scope 자리를 비우고 part 로 옮겨야 한다")

    if len(bits) < 2:
        raise NameError_(
            f"provider 또는 dataset 이 없다: {name!r}\n"
            "  문법 — provider_dataset_scope_vintage[_part][_r{n}].ext")
    provider = bits[0]
    dataset = "_".join(bits[1:])
    if not PROVIDER_RE.match(provider):
        raise NameError_(f"provider 가 문법 밖이다: {provider!r}")
    if not dataset:
        raise NameError_(f"dataset 이 비었다: {name!r}")
    if not DATASET_RE.match(dataset):
        raise NameError_(f"dataset 이 문법 밖이다: {dataset!r}")
    if folder is not None and folder != provider:
        raise NameError_(
            f"폴더({folder!r}) 와 provider({provider!r}) 가 다르다.\n"
            "  ★ 같은 사실의 두 기록이다. 어긋나면 어느 쪽이 맞는지 모른다.")

    if name != normalize_ext(name):
        warn.append(f"확장자 철자 정규화 대상 → {normalize_ext(name)}")

    return Name(provider, dataset, scope_alias, vintage, ext, part, rev, warn)


def _plausible_date(v: str) -> bool:
    y = int(v[:4])
    if not (1990 <= y <= 2100):
        return False
    if len(v) >= 6 and not (1 <= int(v[4:6]) <= 12):
        return False
    if len(v) == 8 and not (1 <= int(v[6:8]) <= 31):
        return False
    return True


def check(name: str, *, folder: str | None = None) -> tuple[bool, list[str]]:
    """예외를 던지지 않는 판정. fsck 가 쓴다."""
    try:
        n = parse(name, folder=folder, strict=False)
    except NameError_ as e:
        return False, [str(e)]
    return n.clean, n.warnings


# ── 정규명 산출 ───────────────────────────────────────────────
# ★ 여기가 규칙의 정본이다. 도구가 아니라 함수에 산다.
#
#   종전에는 `migrate_names.py` 안에 `NEEDS_SCOPE = (8개 키)` 로 박혀
#   있었다. 규칙이 도구 안에 살면 그 도구는 매번 고쳐야 하고, 안 고치면
#   조용히 통과한다. 이 저장소가 `docs` 에는 강제자를 붙여놓고 파일명은
#   사람 기억에 맡기고 있었다.
#
#   판단은 대장이 한다 — `scope` · `part` · `authority` 를 적으면
#   그 조합으로 정규명이 결정된다. 코드는 조립만 한다.


def canonical(rel: str, entry: dict) -> str | None:
    """대장 항목이 요구하는 정규 경로. 지금 이름이 이미 맞으면 None.

    `rel` 은 raw 기준 상대경로(`safety/safety_cctv_jngj_20260630.csv`).
    `entry` 는 `sources.yaml` 의 datasets 항목이다.

    ★ 대장 필드가 파일명을 이긴다. `scope:` 가 적혀 있으면 파일명의
      스코프 토큰이 무엇이든 그것으로 바뀐다. 그래야 판단을 대장에
      적는 것만으로 개명이 따라온다.

    ★ 파일명에서 못 읽고 대장에도 없으면 None 을 준다 — **추측하지
      않는다.** 2026-08-26 에 "끝이 날짜면 그 앞이 스코프" 라고 추측했다가
      도엽번호(`gj037`)와 관할서(`gj_dong`) 뒤에 스코프를 또 박을 뻔했다.
      30건 중 22건이 그 오작동이었고 드라이런이 아니었으면 raw 가 망가졌다.
    """
    folder, _, fn = rel.partition("/")
    stem, dot, ext = fn.rpartition(".")
    if not dot:
        return None
    bits = stem.split("_")

    want_scope = entry.get("scope")
    want_part = entry.get("part")
    if want_scope is not None and not sc.known(str(want_scope)):
        return None                       # 대장 스코프가 통제 어휘 밖이다

    # 현재 이름에서 스코프 토큰의 자리를 찾는다.
    idx = None
    for i in range(len(bits) - 1, 0, -1):
        b = bits[i]
        if sc.known(b) or b in sc.LEGACY or b.startswith(sc.LEGACY_PART_PREFIXES):
            idx = i
            break

    if idx is None:
        # 스코프 토큰이 아예 없다. 대장이 적어줘야 넣는다.
        if want_scope is None:
            return None
        if not re.fullmatch(r"\d{8}|\d{6}|\d{4}", bits[-1]):
            return None
        head, vintage, tail = bits[:-1], bits[-1], []
    else:
        cur, state = bits[idx], None
        try:
            cur, state = sc.resolve(bits[idx])
        except sc.ScopeError:
            return None
        head, tail = bits[:idx], bits[idx + 1:]
        if state == "part":
            # 스코프인 척한 도엽이다. 대장이 scope 를 줘야 자리를 비운다.
            if want_scope is None:
                return None
            want_part = want_part or bits[idx]
            if not tail or not re.fullmatch(r"\d{8}|\d{6}|\d{4}", tail[0]):
                return None
            vintage, tail = tail[0], tail[1:]
        else:
            if want_scope is None:
                want_scope = cur
            if not tail or not re.fullmatch(r"\d{8}|\d{6}|\d{4}", tail[0]):
                # `gj_dong` 처럼 스코프 토큰이 두 낱말인 경우가 여기 온다.
                # 대장이 scope 를 적어야 나머지를 버릴 수 있다.
                if entry.get("scope") is None:
                    return None
                rest = [x for x in tail if not re.fullmatch(r"\d{4,8}", x)]
                nums = [x for x in tail if re.fullmatch(r"\d{8}|\d{6}|\d{4}", x)]
                if len(nums) != 1:
                    return None
                # 버려지는 낱말은 authority 로 옮겨졌어야 한다.
                if rest and not entry.get("authority"):
                    return None
                vintage, tail = nums[0], []
            else:
                vintage, tail = tail[0], tail[1:]

    rev = None
    if tail and REV_RE.match(tail[-1]):
        rev = tail[-1]
        tail = tail[:-1]
    if want_part is None and tail:
        want_part = tail[0]

    out = head + [str(want_scope), vintage]
    if want_part:
        out.append(str(want_part))
    if rev:
        out.append(rev)
    new = f"{folder}/{'_'.join(out)}.{EXT_ALIAS.get(ext.lower(), ext.lower())}"
    return None if new == rel else new


# ── 대장 패턴 ─────────────────────────────────────────────────
def audit_pattern(pat: str) -> list[str]:
    """대장의 `file` 값을 심사한다.

    확장자 와일드카드는 **금지**다. 나머지 와일드카드는 kind 에 따라
    정상일 수 있으므로(도엽 묶음 등) 경고까지만 한다.
    """
    # ★ 2026-08-30. 빈 문자열을 받으면 "provider 폴더가 없다" 를
    #   정상적으로 냈다. 그래서 호출부가 대장을 못 읽고 있어도 검사는
    #   **옳게 우는 것처럼 보였다** — 42종이 전부 같은 말을 했고,
    #   원인은 검사가 아니라 호출부였다.
    #   **빈 입력에 정상적으로 우는 검사는 오탐 공장이다.** 여기서 죽는다.
    if not str(pat).strip():
        raise ValueError(
            "audit_pattern 이 빈 패턴을 받았다. 호출부가 대장을 못 읽고 "
            "있다 — firelane.ledger.globs(e) 를 써라")
    out = []
    if "/" not in pat:
        out.append(f"provider 폴더가 없다: {pat!r}")
    stem = pat.rsplit("/", 1)[-1]
    if "." in stem and WILDCARD & set(stem.rpartition(".")[2]):
        out.append(
            f"★ 확장자에 와일드카드가 있다: {pat!r}\n"
            "    포맷이 다르면 다른 파일이다. `.hwpx` 와 `.pdf` 를 한 항목으로\n"
            "    묶으면 ingest 의 hits[0] 가 조용히 뒤집힌다(2026-08-25).\n"
            "    files: 리스트 + primary: 로 적어라.")
    if WILDCARD & set(stem.rpartition(".")[0]) and not stem.startswith(
            pat.split("/", maxsplit=1)[0]):
        out.append(
            f"글롭이 provider 접두를 강제하지 않는다: {pat!r} — "
            "다른 기관 파일이 걸릴 수 있다")
    return out
