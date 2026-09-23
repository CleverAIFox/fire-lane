#!/usr/bin/env python3
"""
test_docx_targets.py — `PLAN §12` 가 지목한 것이 기획서에 실재하는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-31. `PLAN §12`(기획서 갱신 대상)의 남은 다섯 건을 처리하려고
문서를 뒤졌더니 **셋이 문서에 없는 것을 고치라고 적고 있었다** —
소방서 대조를 "검증" 으로 쓴 자리(`검증` 33회 중 소방서 문맥 0회),
소화전 "동명동 1개"(0회), CCTV 낡은 값(집계 범위가 다른 것이었다).

`docx_check.py` 는 **문서에 있는 숫자**를 산출물과 대조한다. 없는 것은
못 센다. 그래서 이 표가 낡아도 조용하다 — 강제자가 한 방향만 보면
반대 방향이 사각지대가 된다(DECISIONS §78 · R23).

★ 이 저장소가 이미 같은 것을 배웠다. `docnum_check` 는 `PRESENT`(있는가)와
  `RETIRED`(없는가)를 짝으로 갖는다. 그 원리를 §12 표에 적용한다.

── 무엇을 보는가 ───────────────────────────────────────────────
`§12` 표의 **남은** 행에서 백틱 안 문자열을 뽑아 docx 평문에 있는지 본다.
없으면 "고칠 대상이 없다" 는 뜻이고 그 행은 ⬛ 로 내려야 한다.

★ ⬛ 행은 보지 않는다. 이미 처리됐고, 고친 뒤에는 옛 문자열이 없는 것이
  정상이다. 그것까지 검사하면 정반대로 운다.

IN    docs/PLAN.md §12 · docs/proposal.docx
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/PLAN.md"
DOCX = ROOT / "docs/proposal.docx"

# 지목이 아니라 **참조**인 것. 문서 안에 있을 이유가 없다.
# ★ 도구·필드·파일 이름이 여기 들어온다. `#2` 가 처리 수단으로 적은
#   `docx_fix` 를 "기획서에 없다" 로 잡은 것이 이 목록이 생긴 이유다.
SKIP = re.compile(
    r"^(MASTER|PLAN|DECISIONS|docs/|src/|tools/|tests/|\.github/|#\d)"
    r"|^[a-z][a-z0-9_]*(\.py)?$"          # docx_fix · segments.geojson 류
    r"|^[a-z_]+/[a-z_./]+$")


def _docx_text() -> str:
    xml = zipfile.ZipFile(DOCX).read("word/document.xml").decode("utf-8")
    return re.sub(r"<[^>]+>", "", xml)


def _open_rows() -> list[tuple[str, str]]:
    """`§12` 표의 ⬛ 가 아닌 행 → (번호, 본문)."""
    t = PLAN.read_text(encoding="utf-8")
    i = t.find("## 12. 기획서 갱신 대상")
    if i < 0:
        return []
    body = t[i:]
    out = []
    for line in body.splitlines():
        m = re.match(r"^\| ([0-9]+[a-z]?) \| (.*)$", line)
        # ★ ⬛ 뿐 아니라 "완료" 도 처리된 것으로 본다. `#2` `#7` 이
        #   `| 완료 `docx_fix` |` 형식이라 ⬛ 만 보면 남은 행으로 잡힌다.
        if m and "⬛" not in line and "완료" not in line:
            out.append((m.group(1), m.group(2)))
    return out


def test_plan12_targets_exist_in_docx():
    """§12 가 지목한 문자열이 기획서에 있는가.

    ★ 방향이 `docx_check` 와 반대다. 그것은 "문서의 숫자가 산출물과 같은가",
      이것은 "표가 가리키는 것이 문서에 있는가" 를 본다. 둘 다 있어야
      표와 문서가 같이 낡지 않는다.
    """
    assert DOCX.exists(), "docs/proposal.docx 가 없다 — 커밋된 기획서다"
    # ★ 2026-09-22 (PLAN §13 W10-1 · deadcheck ③). 종전에는 `if not rows: return` 이었고 주석이 「파서 사망은
    #   카나리아가 가린다」고 적었다. **그 카나리아가 없었다** — `_open_rows()` 는
    #   §12 제목을 못 찾으면 `[]` 를 돌려주고, 그러면 이 검사가 초록이었다.
    #   남은 행 0 은 여전히 통과다(아래 루프가 빈다). 다만 **닻은 있어야 한다.**
    assert "## 12. 기획서 갱신 대상" in PLAN.read_text(encoding="utf-8"), (
        "PLAN §12 제목(`## 12. 기획서 갱신 대상`)이 없다 — `_open_rows()` 가 빈 목록을 "
        "내고 이 검사가 조용히 통과한다. 제목을 바꿨으면 여기도 같이 옮겨라")
    rows = _open_rows()

    txt = _docx_text()
    bad = []
    for num, body in rows:
        quoted = [q for q in re.findall(r"`([^`]+)`", body)
                  if not SKIP.match(q) and len(q) >= 3]
        if not quoted:
            continue
        missing = [q for q in quoted if q not in txt]
        if len(missing) == len(quoted):
            bad.append(f"  #{num}  지목 {quoted} 가 기획서에 하나도 없다")

    assert not bad, (
        "PLAN §12 가 문서에 없는 것을 고치라고 적는다:\n" + "\n".join(bad) +
        "\n\n  고칠 대상이 없으면 그 행을 ⬛ '해당 없음' 으로 내려라.\n"
        "  08-31 에 다섯 건 중 셋이 이 상태였다 — 표가 문서보다 먼저 낡았다.")


def _check_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_docx_check", ROOT / "tools" / "docx_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_docx_check_is_bidirectional(tmp_path):
    """`docx_check` ⑤ 정방향 · ⑥ 역방향 · ⑦ 참조가 **실제로 운다** (PLAN §13 W4-2 · DECISIONS §217-5).

    기획서 사본의 회색 문단을 1,101 세대로 되돌리면 ⑤ 가, 규칙의 닻 문장을 지우면 ⑥ 이,
    없는 경로를 적으면 ⑦ 이 울어야 한다. 셋 다 안 울면 검사가 빈 그물이다.
    """
    import docx
    chk = _check_mod()
    assert not chk.audit(DOCX), "지금 기획서가 이미 어긋난다 — docx_fix --write"
    d = docx.Document(str(DOCX))
    hit = anchor = False
    for p in d.paragraphs:
        if "CCTV 유효범위 25m 안에 드는 구간이" in p.text and not hit:
            p.runs[0].text = re.sub(r"구간이 [\d,]+ / [\d,]+\([\d.]+%\)", "구간이 380 / 1,101(34.5%)", p.text)
            for r in p.runs[1:]:
                r.text = ""
            hit = True
        elif "담당하는 소방 통행량은" in p.text and not anchor:
            for r in p.runs:
                r.text = ""
            p.runs[0].text = "지워진 문단 src/firelane/없는파일.py"
            anchor = True
    assert hit and anchor, "시험이 고칠 문단을 못 찾았다 — 기획서 문구가 바뀌었다"
    bad_p = tmp_path / "proposal.docx"
    d.save(str(bad_p))
    out = "\n".join(chk.audit(bad_p))
    assert "정방향" in out, "1,101 세대로 되돌렸는데 ⑤ 정방향이 안 운다"
    assert "역방향" in out, "규칙의 닻 문장을 지웠는데 ⑥ 역방향이 안 운다"
    assert "없는파일.py" in out, "없는 경로를 적었는데 ⑦ 참조가 안 운다"


def test_long_cell_ratchet_bites(monkeypatch):
    """W4-7 — 개요표 긴 칸은 양식이라 쪼개지 않고, **자라거나 줄면** 운다 (DECISIONS §218-6)."""
    chk = _check_mod()
    assert not chk.audit(DOCX), "지금 기획서가 이미 어긋난다"
    monkeypatch.setattr(chk, "LONG_MAX_N", chk.LONG_MAX_N - 1)
    assert any("긴 칸" in x and "초과" in x for x in chk.audit(DOCX)), "칸이 늘었는데 안 운다"
    monkeypatch.setattr(chk, "LONG_MAX_N", chk.LONG_MAX_N + 2)
    assert any("줄었다" in x for x in chk.audit(DOCX)), "칸이 줄었는데 상한을 내리라고 안 한다"


def _figs_mod():
    """`tools/docx_figs.py` 를 파일에서 연다 — 도구는 패키지가 아니다."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_docx_figs", ROOT / "tools" / "docx_figs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_every_generated_figure_declares_where_it_goes():
    """생성 그림은 **전부** 기획서 자리를 선언한다 — 「나중에 넣는다」 가 남는 길을 막는다 (§221-1)."""
    f = _figs_mod()
    missing = sorted(set(f.FIGURES) - set(f.PLACE))
    assert not missing, f"tools/docx_figs.py 의 PLACE 에 선언이 없다: {missing}"
    ghost = sorted(set(f.PLACE) - set(f.FIGURES))
    assert not ghost, f"PLACE 가 없는 그림을 든다: {ghost}"
    for name, spec in f.PLACE.items():
        assert ("fig" in spec) ^ ("internal" in spec), f"{name}: fig 아니면 internal 하나만"
        if "internal" in spec:
            assert len(spec["internal"]) >= 20, f"{name}: 사유가 너무 짧다 — 왜 기획서에 없는가"


def test_placed_figures_match_the_proposal():
    """기획서가 든 그림이 정본과 같다 — 다르면 `--sync` 를 안 돌린 것이다 (§221-1)."""
    f = _figs_mod()
    assert f.check() == 0, "기획서 그림이 정본과 어긋난다 — uv run python tools/docx_figs.py --sync"


def test_check_does_not_need_a_converter(monkeypatch):
    """`--check` 는 SVG→PNG 변환기 없이 돈다 — CI 러너에 변환기가 없다 (§221-1)."""
    f = _figs_mod()
    monkeypatch.setattr(f.shutil, "which", lambda _exe: None)
    assert f.check() == 0, "변환기가 없다고 검사가 죽는다 — 그러면 CI 가 이 검사를 못 단다"


def test_manual_insertion_instruction_is_gone():
    """「사람이 넣는다」 가 도구에 남아 있으면 안 된다 — 도구가 넣는다 (§221-1)."""
    src = (ROOT / "tools" / "render_figures.py").read_text(encoding="utf-8")
    out = [ln for ln in src.splitlines()
           if "사람이 넣는다" in ln and not ln.lstrip().startswith("#")]
    assert not out, f"안내가 아직 손 작업을 시킨다: {out}"
