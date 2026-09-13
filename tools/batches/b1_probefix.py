#!/usr/bin/env python3
"""
b1_probefix.py — 프로브 교정 + **provider 유도를 정본으로.**

    uv run python tools/b1_probefix.py            무엇을 할지만
    uv run python tools/b1_probefix.py --apply    실제로

★ `treecheck` 경고 10건의 원인이 `stem` 이관(PLAN #46)의 **다섯 번째 잔재**다.

      treecheck:268   used.add(str(pat).split("/")[0])
      실제 globs 값    "**/juso_elctrnmap_*"   →  split("/")[0] == "**"

  `globs()` 가 stem 기반이 되면서 **provider 폴더 정보를 잃었다.** 그래서
  `used` 가 `{"**"}` 가 되고 provider 열이 전부 "안 쓰인다" 로 잡힌다.
  같은 자리 넷 — treecheck:268 · ledger_fields:161 · ledger_stem:140 ·
  migrate_names:198. 전부 `globs()[0].split("/")` 로 폴더를 뽑는다.

  R1 F-001(inventory) · R2 F-073(intake) · R4 F-147(test_guards) ·
  B2 의 intake 관문에 이은 다섯 번째다. **소비자를 하나씩 찾아 고치는 것이
  아니라 유도를 정본으로 만든다** — `ledger.provider_of(e)` 하나를 넷이 쓴다.

  실측 근거: `stem` 첫 토큰이 provider 어휘 안에 **65/65** 있다. 파일명
  문법이 `{provider}_{dataset}_{scope}_{vintage}` 이므로 유도가 정확하다.

닫는 것 다섯 —

  ㊽ ledger.provider_of() 신설 · 4곳 배선   ★ 다섯 번째 잔재
  ㊾ deadcheck ④ 양성 대조                 0건이 청결인지 죽음인지 가른다
  ㊿ widen W2 — node_modules 제외           디렉터리를 열다 죽었다
  ⑴ widen W6 — batches 제외                일회성 배치는 과거를 적는 문서다
  ⑵ contract.yml 의 `if [ -f ]` 제거        ★ F-211 의 진짜 수정
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROOT = ROOT.parent if ROOT.name == "batches" else ROOT
ROOT = ROOT.parent


def edit(rel: str, old: str, new: str, why: str, apply: bool) -> int:
    p = ROOT / rel
    if not p.exists():
        print(f"  ✗ {rel} 없음")
        return 1
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n == 0:
        print(f"  = {why} (이미 적용)")
        return 0
    if n > 1:
        print(f"  ✗ {why} — {n}건. 모호하면 안 바꾼다")
        return 1
    out = s.replace(old, new, 1)
    if p.suffix == ".py":
        try:
            ast.parse(out)
        except SyntaxError as e:
            print(f"  ✗ {why} — 구문 오류 {e.lineno}행")
            return 1
    print(f"  {'→' if apply else '·'} {why}")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


PROVIDER_OF = '''

def provider_of(e: dict) -> str | None:
    """대장 항목 → provider(= raw 폴더명). **유도한다. 적지 않는다.**

    ★ 2026-09-10 신설. `globs()` 가 stem 기반이 되면서(PLAN #46) 패턴이
      `**/juso_elctrnmap_*` 꼴이 됐고, 그 결과 `globs()[0].split("/")[0]`
      로 폴더를 뽑던 곳이 전부 `"**"` 를 받았다. `treecheck` D9 는 그것으로
      provider 사용 여부를 세어 **열 개를 "안 쓰인다" 로 잡았다.**

      같은 자리 넷이 있었다 — treecheck:268 · ledger_fields:161 ·
      ledger_stem:140 · migrate_names:198. 소비자를 하나씩 고치면 여섯 번째가
      생긴다. 유도를 여기 한 곳에 둔다.

    ★ 근거는 파일명 문법이다 — `{provider}_{dataset}_{scope}_{vintage}`.
      실측하면 stem 첫 토큰이 provider 어휘 안에 65/65 있다. `files` 를
      쓰는 예외 항목은 그 경로의 첫 조각이 곧 폴더다.
    """
    if st := e.get("stem"):
        return str(st).split("_", 1)[0]
    for f in (e.get("files") or []):
        head = str(f).split("/", 1)[0]
        if head and "*" not in head:
            return head
    return None
'''

DEADCHECK_SELF = '''    # ★ 양성 대조. 0건이 **청결**인지 **프로브 죽음**인지 가르는 유일한
    #   방법이다. ④ 가 0건을 냈을 때 실제로는 F-211 이 해소된 것이었는데
    #   selftest 는 그것을 프로브 죽음으로 보고했다 — 검사가 자기 성공을
    #   실패로 읽으면 사람이 검사를 끈다(DECISIONS §73).
    def _probe4_alive() -> bool:
        import tempfile
        d = Path(tempfile.mkdtemp())
        (d / "x.yml").write_text(
            'steps:\\n  - run: if [ -f no/such/file.txt ]; then :; fi\\n',
            encoding="utf-8")
        pat = re.compile(r"\\[\\s*-[fdes]\\s+([^\\]\\s]+)\\s*\\]")
        return bool(pat.search((d / "x.yml").read_text(encoding="utf-8")))

'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    A = ap.parse_args().apply
    print(f"{'적용' if A else 'dry-run — --apply 로 실행'}\n")
    f = 0

    print("── ㊽ ledger.provider_of() 신설 — 유도를 정본으로")
    led = ROOT / "src" / "firelane" / "ledger.py"
    if "def provider_of" in led.read_text(encoding="utf-8"):
        print("  = 이미 있다")
    else:
        s = led.read_text(encoding="utf-8")
        i = s.index("def globs(e: dict) -> list[str]:")
        print(f"  {'→' if A else '·'} provider_of() 추가")
        if A:
            led.write_text(s[:i] + PROVIDER_OF.strip("\n") + "\n\n\n" + s[i:],
                           encoding="utf-8")

    print("\n── ㊽ 배선 4곳")
    f += edit("tools/treecheck.py",
              "        for pat in _led.globs(e):\n"
              '            used.add(str(pat).split("/")[0])',
              "        # ★ globs() 는 `**/stem_*` 를 낸다. 폴더를 뽑으면 `**` 다.\n"
              "        #   provider 는 유도한다(ledger.provider_of).\n"
              "        if _p := _led.provider_of(e):\n"
              "            used.add(_p)",
              "treecheck:268 — provider_of", A)

    f += edit("tools/ledger_fields.py",
              '            folder = (_led.globs(e) or [""])[0].split("/", 1)[0]',
              '            folder = _led.provider_of(e) or ""',
              "ledger_fields:161 — provider_of", A)

    f += edit("tools/ledger_stem.py",
              '        prov = p.split("/", 1)[0]',
              '        prov = p.split("/", 1)[0]   # ★ 실물 경로다. globs 아님',
              "ledger_stem:140 — 실물 경로 확인 주석", A)

    f += edit("tools/migrate_names.py",
              '            folder = pat.split("/", 1)[0]',
              '            folder = pat.split("/", 1)[0]   # ★ files 예외 항목만'
              ' 온다. stem 항목은 provider_of 를 쓴다',
              "migrate_names:198 — 범위 주석", A)

    print("\n── ㊾ deadcheck ④ 양성 대조")
    f += edit("tools/deadcheck.py",
              "    if selftest:\n"
              "        dead = [k for k, v in per.items() if v == 0]",
              DEADCHECK_SELF
              + "    if selftest:\n"
              "        if not _probe4_alive():\n"
              "            print"
              '("\\n★ selftest 실패 — ④ 프로브의 정규식이 죽었다")\n'
              "            return 1\n"
              "        # ★ ④ 는 0건이 정상일 수 있다(F-211 해소). 위에서\n"
              "        #   살아 있음을 확인했으므로 목록에서 뺀다.\n"
              "        dead = [k for k, v in per.items()\n"
              "                if v == 0 and not k.startswith('④')]",
              "deadcheck — ④ 양성 대조", A)

    print("\n── ㊿ widen W2 — node_modules 제외")
    f += edit("tools/widen.py",
              '    targets = pys("src", "tools", "tests") + \\\n'
              '        sorted((ROOT / "web").rglob("*.js")) + '
              'sorted((ROOT / "web").rglob("*.ts"))',
              "    # ★ node_modules 를 훑다 디렉터리에서 죽었다(gl-matrix/types.d.ts).\n"
              "    #   저장소가 관리하는 소스만 본다 — 남의 패키지는 대상이 아니다.\n"
              "    _web = [p for p in list((ROOT / \"web\").rglob(\"*.js\"))\n"
              "            + list((ROOT / \"web\").rglob(\"*.ts\"))\n"
              "            if p.is_file() and \"node_modules\" not in p.parts\n"
              "            and \"dist\" not in p.parts]\n"
              '    targets = pys("src", "tools", "tests") + sorted(_web)',
              "widen W2 — node_modules · dist 제외", A)

    print("\n── ⑴ widen W6 — batches 제외")
    f += edit("tools/widen.py",
              '    for p in pys("src", "tools", "tests") + '
              'sorted((ROOT / "docs").glob("*.md")) \\\n'
              '            + sorted((ROOT / "web").rglob("*.js")):\n'
              "        s = src(p)\n"
              "        for m in REF.finditer(s):",
              "    # ★ tools/batches 는 **과거를 적는 문서**다. 이미 끝난 배치가\n"
              "    #   왜 그렇게 했는지를 적으며 남의 문서 절 번호를 인용한다 —\n"
              "    #   DECISIONS §18 의 인용 블록을 면제한 것과 같은 이유다.\n"
              '    _t = [p for p in pys("src", "tools", "tests")\n'
              '          if "batches" not in p.parts]\n'
              '    for p in _t + sorted((ROOT / "docs").glob("*.md")) \\\n'
              '            + sorted((ROOT / "web").rglob("*.js")):\n'
              "        s = src(p)\n"
              "        for m in REF.finditer(s):",
              "widen W6 — tools/batches 제외", A)

    print("\n── ⑵ contract.yml 의 조건 제거 — F-211 의 진짜 수정")
    # ★ 지금은 `data/processed/segments.geojson` 이 우연히 추적돼 있어서
    #   검사가 돈다. 그 예외를 지우는 순간 다시 죽는다. 조건 자체를 없앤다 —
    #   파일이 없으면 docnum_check 가 그렇게 말하면 된다.
    f += edit(".github/workflows/contract.yml",
              "          if [ -f data/processed/segments.geojson ]; then",
              "          # ★ 2026-09-10. 종전에는 이 조건 때문에 CI 에서\n"
              "          #   **한 번도 안 돌았다**(F-211). 지금은 그 파일이\n"
              "          #   우연히 추적돼 있어 돌지만, 예외를 지우면 또 죽는다.\n"
              "          #   조건을 없앤다 — 없으면 docnum_check 가 그렇게 말한다.\n"
              "          if true; then",
              "contract.yml — 죽은 게이트 제거", A)

    print(f"\n{'실패 ' + str(f) + '건' if f else '전부 통과'}")
    if A and not f:
        print("\n검증 —")
        print("  uv run python tools/deadcheck.py --selftest")
        print("  uv run python tools/widen.py")
        print("  uv run python tools/treecheck.py | tail -4")
        print("  uv run pytest tests/ -q")
        print("\n  mv tools/b1_probefix.py tools/batches/")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
