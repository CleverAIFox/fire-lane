#!/usr/bin/env python3
"""
vehiclecard.py — 소방자동차 관리카드([별지 제48호서식] 1쪽) PDF → 한 행 CSV.

    python -m firelane.vehiclecard <카드.pdf>      추출 결과를 찍는다 (아무것도 안 쓴다)

`prep` 이 raw → norm 에서 부른다(DECISIONS §172). **형식만 바꾼다. 값은 안 바꾼다.**
`7,770` 은 `7,770` 으로, `중형(신규)` 는 `중형(신규)` 로 옮긴다 — 쉼표를 털거나 단위를
붙이는 것은 ingest 의 일이다(prep 머리말의 경계).

── 왜 좌표로 읽나 ──────────────────────────────────────────────
서식이 표다. 텍스트를 줄로만 뽑으면 `구입 가격` 의 네 칸(보조금 · 교부세 · 지방비 ·
기증 등) 중 **어느 칸에 값이 있는지가 사라진다** — 지산2호는 교부세, 대인11호는 지방비다.
글자 조각의 좌표를 받아 머리글 칸의 중심에 붙인다.

★ poppler(`pdftotext`)는 Adobe-Korea1 언어팩이 없어 한글을 전부 잃었다(2026-09-17).
  pypdf 는 폰트에 실린 CID 매핑으로 읽는다.

IN    관리카드 PDF 1개 (raw)
OUT   CSV 1개 (norm) — 머리 한 줄 + 값 한 줄 · UTF-8 · LF
PARAM VERSION — 추출 규칙이 바뀌면 올린다. `_prep.json` 이 기록한다
"""
from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path

VERSION = "2026-09-17.1"

# 표의 머리글 → CSV 칸 이름. 순서가 곧 CSV 칸 순서다.
ROW1 = [("차 종", "차종"), ("등 록 일", "등록일"),
        ("보 조 금", "구입가격_보조금"), ("교 부 세", "구입가격_교부세"),
        ("지 방 비", "구입가격_지방비"), ("기 증 등", "구입가격_기증등"),
        ("차 제", "제작회사_차체"), ("특 장", "제작회사_특장")]
ROW2 = [("길이(mm)", "길이(mm)"), ("너비(mm)", "너비(mm)"), ("높이(mm)", "높이(mm)"),
        ("엔진", "엔진(마력/토크)"), ("물탱크 용량", "물탱크 용량(ℓ)"),
        ("폼탱크 용량", "폼탱크 용량(ℓ)"), ("분말탱크 용량", "분말탱크 용량(㎏)")]
HEAD = ["서식", "쪽", "차명", "등록번호", "소속"] + [c for _, c in ROW1] + \
       [c for _, c in ROW2] + ["그 밖의 특기사항"]

# 글자 폭 근사(em). 칸 배정에만 쓴다 — 칸 중심 간격이 69pt 라 오차 여유가 크다.
_HANGUL = re.compile(r"[가-힣]")
_ASCII_GAP = re.compile(r"(?<=[A-Za-z0-9-]) (?=[A-Za-z0-9-])")


class CardError(ValueError):
    pass


def _width(text: str, size: float) -> float:
    return sum(size * (1.0 if _HANGUL.match(ch) else 0.55) for ch in text)


def chunks_of(pdf: Path) -> list[tuple[float, float, float, str]]:
    """첫 쪽 글자 조각 → (y, x, 글자크기, 글자)."""
    from pypdf import PdfReader
    page = PdfReader(pdf).pages[0]
    out: list[tuple[float, float, float, str]] = []

    def visit(text, cm, tm, _fd, size):
        t = text.strip()
        if not t:
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        scale = (cm[0] ** 2 + cm[1] ** 2) ** 0.5 * (tm[0] ** 2 + tm[1] ** 2) ** 0.5 or 1.0
        out.append((round(y, 1), round(x, 1), float(size) * scale, t))

    page.extract_text(visitor_text=visit)
    return out


def _find(chs, label):
    hit = [c for c in chs if c[3] == label]
    if len(hit) != 1:
        raise CardError(f"머리글 `{label}` 이 {len(hit)}번 나온다 — 서식이 다르다")
    return hit[0]


def _center(c) -> float:
    return c[1] + _width(c[3], c[2]) / 2


def _row(chs, heads, y_head, y_below):
    """머리글 칸 중심에 그 아래 첫 값 줄의 조각을 붙인다."""
    cols = [(_center(_find(chs, h)), name) for h, name in heads]
    vals = [c for c in chs if y_below < c[0] < y_head - 6]
    if not vals:
        return {name: "" for _, name in cols}
    top = max(c[0] for c in vals)
    line = [c for c in vals if abs(c[0] - top) < 3]
    got: dict[str, list[str]] = {name: [] for _, name in cols}
    for c in sorted(line, key=lambda c: c[1]):
        name = min(cols, key=lambda h: abs(h[0] - _center(c)))[1]
        got[name].append(c[3])
    return {k: " ".join(v) for k, v in got.items()}


def parse(chs: list[tuple[float, float, float, str]]) -> dict[str, str]:
    """조각 → 칸. 파일을 안 읽는다 — 테스트가 조각 목록으로 부른다."""
    text = " ".join(c[3] for c in sorted(chs, key=lambda c: (-c[0], c[1])))
    if "소방자동차 관리카드" not in text:
        raise CardError("소방자동차 관리카드 서식이 아니다")
    rec = {h: "" for h in HEAD}
    m = re.search(r"\[(별지 제\d+호서식)\]", text)
    rec["서식"] = m.group(1) if m else ""
    m = re.search(r"\((\d+쪽 중 제 \d+쪽)\)", text)
    rec["쪽"] = m.group(1) if m else ""

    lab_car, lab_no, lab_org = _find(chs, "차명 :"), _find(chs, "등록번호 :"), _find(chs, "소속 :")
    band = [c for c in chs if abs(c[0] - lab_car[0]) <= 8 and c not in (lab_car, lab_no, lab_org)]
    by_y = sorted(band, key=lambda c: (-c[0], c[1]))
    # ★ pypdf 가 영숫자 글리프 사이에 공백을 끼운다 — 원문 `SMC-B4A1S3D175L3` 가
    #   `SM C-B4A 1S3D175L3` 로 나왔다(대인11호). 공백은 원문에 없는 값이라 뺀다.
    #   **양옆이 ASCII 영숫자·하이픈일 때만** 뺀다. `27m 급` · `동부 소방서` 는 그대로다.
    rec["차명"] = _ASCII_GAP.sub("", " ".join(c[3] for c in by_y if c[1] < lab_no[1]))
    rec["등록번호"] = " ".join(c[3] for c in by_y if lab_no[1] <= c[1] < lab_org[1])
    rec["소속"] = " ".join(c[3] for c in by_y if c[1] >= lab_org[1])

    y1 = _find(chs, "보 조 금")[0]
    y2 = _find(chs, "길이(mm)")[0]
    rec.update(_row(chs, ROW1, y1, y2 + 10))
    note = _find(chs, "그 밖의 특기사항")
    rec.update(_row(chs, ROW2, y2 - 6, note[0] + 6))
    rec["그 밖의 특기사항"] = " ".join(
        c[3] for c in sorted(chs, key=lambda c: c[1])
        if abs(c[0] - note[0]) < 3 and c is not note)
    if not rec["등록번호"] or not rec["소속"]:
        raise CardError(f"등록번호·소속을 못 읽었다 — {rec['등록번호']!r} · {rec['소속']!r}")
    return rec


def to_csv_bytes(rec: dict[str, str]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEAD)
    w.writerow([rec.get(h, "") for h in HEAD])
    return buf.getvalue().encode("utf-8")


def convert(src: Path, dst: Path) -> dict:
    """raw PDF → norm CSV. `_prep.json` 에 남길 메타를 돌려준다."""
    rec = parse(chunks_of(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(to_csv_bytes(rec))
    return {"converter": "vehiclecard", "converter_version": VERSION,
            "src_encoding": "pdf", "dst_encoding": "utf-8", "dst_newline": "lf"}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    rec = parse(chunks_of(Path(sys.argv[1])))
    for k in HEAD:
        print(f"  {k:18s} {rec[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
