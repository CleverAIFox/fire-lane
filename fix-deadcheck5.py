#!/usr/bin/env python3
"""⑤ 좁은 범위 1건 — REDLIST 가 적은 **그 자리**를 면제에 넣는다. 짐작 안 한다."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not (ROOT / "tools" / "deadcheck.py").exists():
    ROOT = Path.cwd()

red = ROOT / "REDLIST.json"
if not red.is_file():
    print("✗ REDLIST.json 이 없다 — 먼저 재서 쓴다")
    subprocess.run(["uv", "run", "python", "tools/deadcheck.py"], cwd=ROOT, check=False)
if not red.is_file():
    sys.exit("✗ 그래도 없다. deadcheck 출력을 보내라")

rows = json.loads(red.read_text(encoding="utf-8"))
flat = rows if isinstance(rows, list) else [v for vs in rows.values()
                                            for v in (vs if isinstance(vs, list) else [vs])]
keys = set()
for r in flat:
    s = json.dumps(r, ensure_ascii=False)
    if "test_guards" not in s:
        continue
    for m in re.finditer(r"(tests/test_guards\.py)::([A-Za-z_][A-Za-z0-9_]*)", s):
        keys.add(f"{m.group(1)}::{m.group(2)}")
    for m in re.finditer(r"\"(?:where|func|name|함수)\"\s*:\s*\"([A-Za-z_][A-Za-z0-9_]*)\"", s):
        keys.add(f"tests/test_guards.py::{m.group(1)}")

if not keys:
    print("REDLIST 전문 —")
    print(json.dumps(flat, ensure_ascii=False, indent=1)[:3000])
    sys.exit("\n✗ `파일::함수` 를 못 읽었다. 위 전문을 보내라 — 짐작으로 안 적는다")

print("면제에 넣을 자리:", *sorted(keys), sep="\n  ")

p = ROOT / "tools" / "deadcheck.py"
src = p.read_text(encoding="utf-8")
anchor = "EXEMPT_SCOPE = {\n"
assert src.count(anchor) == 1, "EXEMPT_SCOPE 를 못 찾았다"
block = "".join(
    f'''    # ★ 2026-10-10 (DECISIONS §445 · PLAN #56 ③). 이 축이 묻는 것은 「**생산 코드**가
    #   도장 키를 가진 사전을 직접 파일로 쓰는가」다. 시험은 그 결함을 **일부러 심어**
    #   축이 무는지 보는 자리이므로 과녁이 아니다 — 넓히면 합성 입력이 결함으로 세진다.
    "{k}": _PROD_ONLY + " — 합성 입력이 과녁이 되면 카나리아가 결함으로 세진다",\n'''
    for k in sorted(keys))
p.write_text(src.replace(anchor, anchor + block, 1), encoding="utf-8")
print("\n넣었다. 다시 잰다 —\n")
rc = subprocess.run(["uv", "run", "python", "tools/deadcheck.py", "--ratchet"],
                    cwd=ROOT, check=False).returncode
print(f"\n종료코드 {rc}" + ("  ✓ 초록" if rc == 0 else "  ✗ 아직 — 출력을 보내라"))
