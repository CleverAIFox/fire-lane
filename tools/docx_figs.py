#!/usr/bin/env python3
"""
docx_figs.py — 정본에서 만든 그림을 **기획서 안에 직접 넣는다.**

    uv run python tools/docx_figs.py --sync     docx 안 이미지를 다시 그린 것으로 교체
    uv run python tools/docx_figs.py --check    기획서 그림이 정본과 어긋나면 종료코드 1

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-02 에 `render_figures.py` 를 만들면서 이렇게 적었다 — 「`.docx` 안 이미지를
코드가 교체하지는 않는다. 기획서는 대외 제출본이고 생성물이 아니다. 알리기만 하고
넣는 것은 사람이 한다」(DECISIONS §110). **그 결정이 틀렸다.**

틀린 이유는 두 가지다 ——

  ① 기획서는 이미 기계가 고친다. `tools/docx_fix.py` 가 문단을 넣고 표를 고치고
     표지 날짜를 만진다. 「생성물이 아니다」 는 그때 이미 사실이 아니었다.
     같은 파일에 대해 규칙이 둘이었다 — 글자는 기계가, 그림은 사람이.
  ② 사람이 넣는 일은 **매번 미뤄진다.** 2026-09-22 배치가 그림 넷을 다시 그렸고,
     그림은 저장소에서만 새것이 됐다. 제출본은 옛 그림을 든 채 남았다.
     검사는 「어긋났다」 고 울지만 우는 것과 고치는 것은 다르다.

<!--voice-ok-->
> 미친 기획서가 재생성한 그림을 수동으로 왜 끼워. 그럼 앞으로도 수동으로 끼워야
> 하는 건데. 도구를 수정하면 되는 거 아니야 — 2026-09-23

── 규칙 ───────────────────────────────────────────────────────
`render_figures.FIGURES` 의 **모든** 그림은 여기 `PLACE` 에 선언돼야 한다. 둘 중 하나다 —

    {"fig": 22, "caption": "유효 측정 범위"}   기획서 [그림 22] 다. `--sync` 가 교체한다
    {"internal": "<사유>"}                     기획서에 대응 그림이 없다. 사유를 적는다

선언이 없으면 `tests/test_docx_targets.py` 가 운다. 「어디에 넣을지 아직 안 정했다」 가
조용히 남는 길을 막는다 — 그것이 2026-09-02 부터 오늘까지 있었던 상태다.

★ `--check` 는 변환기가 없어도 돈다. SVG 지문만 대조하기 때문이다(PNG 바이트는 렌더러
  판마다 달라서 대조 대상이 못 된다). 변환기가 필요한 것은 `--sync` 뿐이다.

IN    docs/figures/*.svg · docs/proposal.docx
OUT   docs/proposal.docx · docs/figures/.lock.json 의 `placed`
PARAM --sync --check
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

#: `.rels` 의 기본 이름공간. 등록해야 다시 쓸 때 `ns0:` 접두가 안 붙는다.
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("", RELS_NS)

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "docs/proposal.docx"
#: 그림 잠금은 **하나**다. `render_figures` 가 `figures`(정본 지문)를 쓰고
#: 이 도구가 `placed`(기획서에 박힌 지문)를 쓴다. 파일을 하나 더 만들지 않는다 —
#: `docs/` 는 문서 넷과 그림만 담는다(DECISIONS §220-5 의 규칙).
LOCK = ROOT / "docs/figures/.lock.json"


def _render_figures():
    """`tools/render_figures.py` 를 파일에서 연다 — `sys.path` 를 건드리지 않는다."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_render_figures", Path(__file__).resolve().parent / "render_figures.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


FIGURES = _render_figures().FIGURES

#: 생성 그림 → 기획서 자리. 새 그림을 만들면 여기에도 한 줄을 단다.
PLACE: dict[str, dict] = {
    "cctv": {"fig": 22, "caption": "유효 측정 범위"},
    "deploy": {"fig": 24, "caption": "배포 아키텍처"},
    # ★ 2026-09-24 (PLAN §12 #15). 캡션은 2026-09-01 에 「평면교차점 실형상 제외」로
    #   고쳤는데 **그림은 반경 5m 원 하나만 그린 채**였다. 캡션을 보는 검사는
    #   그림을 못 본다 — 그것이 이 도구가 생긴 이유고, 이 줄이 그 자리를 덮는다.
    "xsec": {"fig": 13, "caption": "법선 트랜섹트 샘플링과 평면교차점 실형상 제외"},
    "verdict": {"internal": "기획서에 대응 그림이 없다 — 판정 4종 수는 본문 숫자로 들어가고 "
                            "tools/docnum_check.py 가 golden 과 대조한다"},
    "unknown": {"internal": "기획서에 대응 그림이 없다 — 사유 분해는 본문 표가 든다"},
    "threshold": {"internal": "기획서에 대응 그림이 없다 — 폭 임계는 본문과 표가 들고 "
                              "tools/docx_check.py 가 params.py 와 대조한다"},
    "branch": {"internal": "개발 가지 구조는 대외 제출본의 주제가 아니다 — MASTER §12-1 이 정본이고 "
                           "그림은 저장소 리뷰용이다"},
}

#: SVG → PNG 변환기. 앞의 것부터 있는 것을 쓴다. 파이썬 의존성을 늘리지 않는다 —
#: 이 변환은 `--sync` 한 번에만 필요하고, CI 와 `--check` 는 변환기 없이 돈다.
CONVERTERS = (
    ("rsvg-convert", lambda exe, src, out, w: [exe, "-w", str(w), str(src), "-o", str(out)]),
    ("inkscape", lambda exe, src, out, w: [exe, str(src), "--export-type=png",
                                           f"--export-width={w}", f"--export-filename={out}"]),
    ("magick", lambda exe, src, out, w: [exe, "-density", "288", str(src),
                                         "-resize", f"{w}x", str(out)]),
)
APT = "sudo apt-get install -y librsvg2-bin"

NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _svgs() -> dict[str, str]:
    """이름 → SVG 본문. 파일이 아니라 **함수**에서 낸다 — 파일이 낡아도 대조가 산다."""
    return {name: fn() for name, fn in FIGURES.items()}


def _lock_all() -> dict:
    if not LOCK.exists():
        return {}
    return json.loads(LOCK.read_text(encoding="utf-8"))


def _lock() -> dict[str, str]:
    return _lock_all().get("placed", {})


def _converter() -> tuple[str, object] | None:
    for exe, argv in CONVERTERS:
        path = shutil.which(exe)
        if path:
            return path, argv
    return None


def _png(svg: str, width: int) -> bytes:
    conv = _converter()
    if conv is None:
        raise SystemExit(
            "★ SVG → PNG 변환기가 없다 — `--sync` 는 이것 하나가 필요하다.\n"
            f"  {APT}\n"
            "  (inkscape · ImageMagick 도 쓴다. `--check` 는 변환기 없이 돈다.)")
    exe, argv = conv
    with tempfile.TemporaryDirectory() as d:
        src, out = Path(d) / "f.svg", Path(d) / "f.png"
        src.write_text(svg, encoding="utf-8")
        r = subprocess.run(argv(exe, src, out, width), capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            raise SystemExit(f"★ {Path(exe).name} 변환 실패 — {r.stderr.strip()[:300]}")
        return out.read_bytes()


def _figure_anchors(doc) -> dict[int, object]:
    """그림 번호 → 그 그림을 든 `<w:p>`. 캡션 문단 **바로 앞**의 그림이 그 번호다."""
    out, cur = {}, None
    for p in doc.paragraphs:
        blips = p._p.findall(f".//{NS_A}blip")
        if blips:
            cur = p._p
            continue
        m = re.match(r"^\[?그림\s*(\d+)\]?", p.text.strip())
        if m and cur is not None:
            out[int(m.group(1))] = cur
            cur = None
    return out


def _svg_px(svg: str) -> tuple[int, int]:
    w = int(float(re.search(r'width="([\d.]+)"', svg).group(1)))
    h = int(float(re.search(r'height="([\d.]+)"', svg).group(1)))
    return w, h


def _replace(doc, p_el, png: bytes, ratio: float) -> None:
    """그림 문단의 이미지를 갈아끼운다. 폭은 그대로 두고 높이만 새 비율로 맞춘다."""
    blip = p_el.find(f".//{NS_A}blip")
    rid, _ = doc.part.get_or_add_image(io.BytesIO(png))
    blip.set(f"{NS_R}embed", rid)
    for tag in (f"{NS_WP}extent", f"{NS_A}ext"):
        for ext in p_el.iter(tag):
            cx = int(ext.get("cx"))
            ext.set("cy", str(round(cx / ratio)))


def _prune_media(path: Path) -> None:
    """쓰이지 않는 media 와 그 관계를 버린다.

    ★ python-docx 는 이미지를 갈아끼워도 **옛 관계(`document.xml.rels`)를 안 지운다.**
      관계가 남아 있으면 media 도 남는다 — `--sync` 를 돌 때마다 제출본이 150KB 씩
      불어난다. 그래서 「rels 가 가리키는가」 가 아니라 **「본문이 그 rId 를 쓰는가」**
      로 본다.
    """
    rels_name = "word/_rels/document.xml.rels"
    with zipfile.ZipFile(path) as z:
        blobs = {n: z.read(n) for n in z.namelist()}
    if rels_name not in blobs:
        return
    # ★ 2026-09-23. 종전에는 `lxml` 을 직접 import 했다 — `deptry` DEP003 이 잡았다.
    #   lxml 은 python-docx 가 끌고 오는 **전이 의존**이라 선언 없이 기대면, python-docx 가
    #   내부 구현을 바꾸는 날 이 도구가 조용히 죽는다(4족). 표준 라이브러리로 쓴다.
    body = blobs["word/document.xml"]
    used_ids = {m.group(1).decode() for m in re.finditer(rb'r:(?:embed|link)="([^"]+)"', body)}
    rels = ET.fromstring(blobs[rels_name])
    drop_media = set()
    for rel in list(rels):
        target = rel.get("Target", "")
        if "media/" in target and rel.get("Id") not in used_ids:
            drop_media.add("word/" + target.lstrip("./").replace("../", ""))
            rels.remove(rel)
    if not drop_media:
        return
    blobs[rels_name] = ET.tostring(rels, xml_declaration=True, encoding="UTF-8")
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as z, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as o:
        for item in z.infolist():
            if item.filename in drop_media:
                continue
            o.writestr(item.filename, blobs[item.filename])
    tmp.replace(path)
    print(f"  안 쓰는 이미지 {len(drop_media)}개와 그 관계를 버렸다")


def _undeclared() -> list[str]:
    return sorted(set(FIGURES) - set(PLACE))


def check() -> int:
    bad = _undeclared()
    if bad:
        print("★ 선언되지 않은 그림 — tools/docx_figs.py 의 PLACE 에 한 줄을 달아라: "
              + " · ".join(bad))
        print("  기획서 [그림 N] 이면 {\"fig\": N, \"caption\": \"…\"}, 아니면 {\"internal\": \"사유\"}")
        return 1
    placed = _lock()
    svgs = _svgs()
    stale = [n for n, spec in PLACE.items()
             if "fig" in spec and placed.get(n) != _sha(svgs[n])]
    if stale:
        print("★ 기획서 그림이 정본과 어긋난다 — " + " · ".join(stale))
        print("  값이 바뀌었는데 기획서가 옛 그림을 든다.")
        print("  uv run python tools/docx_figs.py --sync")
        return 1
    n = sum(1 for s in PLACE.values() if "fig" in s)
    print(f"기획서 그림 OK — {n}장이 정본과 같다 (내부 {len(PLACE) - n}장은 선언됨)")
    return 0


def sync() -> int:
    if _undeclared():
        return check()
    import docx  # 여기서만 필요하다

    doc = docx.Document(str(DOCX))
    anchors = _figure_anchors(doc)
    svgs, placed, done = _svgs(), _lock(), []
    for name, spec in PLACE.items():
        if "fig" not in spec:
            continue
        no, svg = spec["fig"], svgs[name]
        if no not in anchors:
            raise SystemExit(f"★ 기획서에 [그림 {no}] 가 없다 — PLACE 선언과 문서가 어긋났다")
        cap = next(p.text for p in doc.paragraphs
                   if re.match(rf"^\[?그림\s*{no}\]?", p.text.strip()))
        if spec["caption"] not in cap:
            raise SystemExit(f"★ [그림 {no}] 캡션이 선언({spec['caption']})과 다르다 — {cap.strip()[:60]}\n"
                             "  번호가 밀렸을 수 있다. PLACE 를 고치거나 캡션을 고쳐라.")
        if placed.get(name) == _sha(svg):
            print(f"  [그림 {no}] {name} — 이미 같다")
            continue
        w, h = _svg_px(svg)
        _replace(doc, anchors[no], _png(svg, w * 2), w / h)
        placed[name] = _sha(svg)
        done.append(f"[그림 {no}] {name}")
    if not done:
        print("바꿀 그림이 없다 — 기획서가 이미 정본과 같다")
        return 0
    doc.save(str(DOCX))
    _prune_media(DOCX)
    LOCK.write_text(json.dumps({**_lock_all(), "placed": placed}, ensure_ascii=False,
                               indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("교체 " + " · ".join(done))
    print("★ 기획서가 바뀌었다 — docs/proposal.docx 를 커밋해라")
    return 0


def main() -> int:
    # ★ 2026-09-24 (PLAN §13 W13-6 · DECISIONS §243). 종전에는 `"--x" in sys.argv`
    #   였다 — **오타가 조용히 무시된다.** `--snyc` 는 바꿔 넣는 대신 대조만 하고 끝났다.
    #   argparse 는 모르는 인자에 스스로 운다. 직접 구현할 일이 아니다(4족).
    ap = argparse.ArgumentParser(description="기획서 그림 ↔ 정본")
    ap.add_argument("--sync", action="store_true", help="기획서의 그림을 정본으로 바꿔 넣는다")
    return sync() if ap.parse_args().sync else check()


if __name__ == "__main__":
    raise SystemExit(main())
