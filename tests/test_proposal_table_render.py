#!/usr/bin/env python3
"""
test_proposal_table_render.py — 기획서 표의 **첫 칸이 세로로 눌리지 않는가**를 브라우저로 잰다. (PLAN #175)

── 왜 생겼나 ───────────────────────────────────────────────────
「프로젝트 주제」가 한 글자씩 내려오는 것을 **만들어졌는가**를 묻는 관문은 못 잡는다(`#174` 와 같은 병).
그래서 헤드리스 크롬으로 `web/proposal.html` 의 **모든 탭을 펴고** 표 56개의 첫 칸 399개마다 글자가 몇 줄에
앉는지 쟀다. 측정기가 눈이 있는지는 **CSS 한 줄을 빼서** 같은 잣대로 다시 재어 확인한다(음성 대조).

★ 실측 2026-10-22 — 규칙이 있으면 줄바꿈한 첫 칸 **0**, 규칙을 빼면 **112(1440px) ~ 178(500px)**.
★ 헤드리스 크롬은 창이 500px 아래로 안 줄어든다(360 을 달라 해도 `innerWidth` 500). **그 아래는 못 쟀다.**
★ 크롬이 없는 기계에서는 **건너뛴다 — 통과가 아니다.** 건너뛰었다는 사실이 시험 출력에 남는다.

IN    web/proposal.html · 헤드리스 크롬(`CHROME_BIN` 또는 Playwright 캐시)
OUT   없음 (검사)
PARAM 없음
밖    **글꼴이 예쁜가·표가 읽기 쉬운가는 안 본다** — 첫 칸이 한 글자 폭이거나 여러 줄로 접히는가, 칸이 표
      밖으로 넘치는가만 잰다. 500px 아래 폭도 못 잰다.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "web" / "proposal.html"
RULE = "table th:first-child, table td:first-child{white-space:nowrap; width:1%}"
WIDTHS = (500, 900, 1440)

PROBE = """<style>.pane{display:block !important}</style><script>addEventListener('load',()=>{setTimeout(()=>{
 const o={tables:0,cells:0,multiline:[],vert:[],over:[]};
 document.querySelectorAll('table').forEach((t,ti)=>{o.tables++;const tb=t.getBoundingClientRect();
  t.querySelectorAll('tr').forEach(tr=>{const c=tr.children[0];if(!c)return;o.cells++;
   const rg=document.createRange();rg.selectNodeContents(c);
   const tops=new Set([...rg.getClientRects()].map(r=>Math.round(r.top/4)));
   const txt=c.textContent.trim();const r=c.getBoundingClientRect();
   if(tops.size>1)o.multiline.push([ti,txt.slice(0,14),tops.size]);
   if(txt.length>=3&&r.width<parseFloat(getComputedStyle(c).fontSize)*2.2)o.vert.push([ti,txt.slice(0,14)]);
   if(r.right>tb.right+1)o.over.push([ti,txt.slice(0,14)]);});});
 document.body.insertAdjacentHTML('beforeend','<pre id="PROBE">'+JSON.stringify(o)+'</pre>');},300)})</script>"""


def _chrome() -> str | None:
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    hit = sorted(glob.glob(str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux*/chrome")))
    return hit[-1] if hit else shutil.which("chromium") or shutil.which("google-chrome")


def _measure(html: str, width: int) -> dict:
    chrome = _chrome()
    if chrome is None:
        pytest.skip("헤드리스 크롬이 없다 — 표 렌더를 **확인 못 했다**(통과가 아니다)")
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "p.html"
        f.write_text(html.replace("</body>", PROBE + "</body>"), encoding="utf-8")
        out = subprocess.run(
            [chrome, "--headless", "--no-sandbox", "--disable-gpu", f"--window-size={width},900",
             "--virtual-time-budget=3000", "--dump-dom", f"file://{f}"],
            capture_output=True, text=True, timeout=120, check=False).stdout
    m = re.search(r'id="PROBE">(\{[^<]*\})', out)
    assert m, "측정기가 결과를 못 냈다 — 페이지가 안 열렸다"
    return json.loads(m.group(1))


@pytest.fixture(scope="module")
def html() -> str:
    return HTML.read_text(encoding="utf-8")


def test_the_generated_page_carries_the_rule(html):
    """생성물에 첫 칸 규칙이 **글자로** 있다 — 렌더를 못 도는 기계의 바닥."""
    assert RULE in html, "web/proposal.html 에 첫 칸 규칙이 없다 — 템플릿을 고치고 build_proposal 을 돌려라"


@pytest.mark.parametrize("width", WIDTHS)
def test_no_first_cell_folds_or_collapses(html, width):
    r = _measure(html, width)
    assert r["tables"] >= 50 and r["cells"] >= 300, f"표를 덜 쟀다 — {r['tables']}표 {r['cells']}칸"
    assert not r["multiline"], f"{width}px 첫 칸이 여러 줄로 접힌다 — {r['multiline'][:5]}"
    assert not r["vert"], f"{width}px 첫 칸이 한 글자 폭으로 눌린다 — {r['vert'][:5]}"
    assert not r["over"], f"{width}px 첫 칸이 표 밖으로 넘친다 — {r['over'][:5]}"


def test_the_probe_sees_the_bug_when_the_rule_is_gone(html):
    """★ 음성 대조 — 규칙을 빼면 이 측정기가 **운다.** 안 울면 위 통과는 아무것도 아니다."""
    assert RULE in html
    r = _measure(html.replace(RULE, ""), 1440)
    assert len(r["multiline"]) > 50, f"규칙을 뺐는데 측정기가 못 본다 — {len(r['multiline'])}"
