#!/usr/bin/env python3
"""
widen.py — 검사 범위를 **원본 유도**로 넓혔을 때 무엇이 새로 걸리는가.

★ 40개 파일을 먼저 고치면 크기를 모른 채 40개를 건드리게 된다.
  넓히는 것은 편집이지만 **넓혔을 때의 결과는 계산**이다. 계산이 먼저다.

여기서 넓히는 축 여섯. 전부 지금 손목록·부분범위로 좁혀져 있다.

  W1  정적 검사 범위      src/ 만  →  src + tools + tests
  W2  임계값 정본 검사    segments.py 만  →  전 저장소
  W3  파일 쓰기 검사      WRITE 10개  →  tools 전량
  W4  도구 배선 검사      EXEMPT 33 면제  →  전량 대조
  W5  문체 검사 대상      문서 7  →  + sources.yaml
  W6  절 참조 검사        하위절 3개 이상 절  →  전 절

OUT  표준출력 — 축별 신규 빨간불 수. REDLIST 에 더할 예상치다.
"""
from __future__ import annotations

import ast
import builtins
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILTIN = set(dir(builtins)) | {
    # ★ 모듈 전역은 바인딩 없이도 산다. 이것을 빼면 71건 중 대부분이
    #   `__file__` 오탐이 된다 — 시끄러운 검사는 사람이 끈다.
    "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__", "__annotations__", "__debug__",
}


def src(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def pys(*dirs: str) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        out += sorted((ROOT / d).rglob("*.py"))
    return out


# ── W1  정적 검사 범위 ──────────────────────────────────────────
def _undef(t: ast.Module, tag: str) -> list[str]:
    bound: set[str] = set()
    for n in ast.walk(t):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            bound.add(n.id)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            bound |= set(n.names)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
    return [f"{tag}:{n.lineno}  미정의 이름 `{n.id}`"
            for n in ast.walk(t)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
            and n.id not in bound and n.id not in BUILTIN]


def w1() -> tuple[int, list[str]]:
    """undefined_names 를 tools + tests 까지. 지금은 src 만 본다."""
    # ★ 양성 대조. 0건이 나왔을 때 그것이 **청결**인지 **프로브 죽음**인지
    #   가르는 유일한 방법이다. 이 저장소가 반복해서 놓친 자리다.
    probe = ast.parse("def f():\n    return _no_such_name_\n")
    if not _undef(probe, "<대조>"):
        return 1, ["★ 양성 대조 실패 — 프로브가 죽었다. 0건을 믿지 마라"]
    bad: list[str] = []
    for p in pys("tools", "tests"):
        try:
            t = ast.parse(src(p))
        except SyntaxError as e:
            bad.append(f"{p.relative_to(ROOT)}  구문 오류 {e.lineno}")
            continue
        bad += _undef(t, str(p.relative_to(ROOT)))
    return len(bad), bad[:12]


# ── W2  임계값 정본 검사 ────────────────────────────────────────
def w2() -> tuple[int, list[str]]:
    """params.py 의 상수를 다른 곳이 재정의하는가. 지금은 segments.py 만 본다."""
    par = ROOT / "src" / "firelane" / "seg" / "params.py"
    if not par.exists():
        return 0, ["★ params.py 없음 — 이 축을 못 잰다"]
    names = {m.group(1) for m in
             re.finditer(r"^([A-Z][A-Z0-9_]*)\s*[:=]", src(par), re.M)}
    names -= {"__all__"}
    bad: list[str] = []
    # ★ node_modules 를 훑다 디렉터리에서 죽었다(gl-matrix/types.d.ts).
    #   저장소가 관리하는 소스만 본다 — 남의 패키지는 대상이 아니다.
    _web = [p for p in list((ROOT / "web").rglob("*.js"))
            + list((ROOT / "web").rglob("*.ts"))
            if p.is_file() and "node_modules" not in p.parts
            and "dist" not in p.parts]
    targets = pys("src", "tools", "tests") + sorted(_web)
    for p in targets:
        if p == par:
            continue
        s = src(p)
        for nm in sorted(names):
            for m in re.finditer(rf"^\s*(?:const\s+|let\s+)?{nm}\s*[:=]\s*[\d.\[]", s, re.M):
                ln = s[:m.start()].count("\n") + 1
                bad.append(f"{p.relative_to(ROOT)}:{ln}  {nm} 재정의 — 정본은 seg/params.py")
    return len(bad), bad[:12]


# ── W3  파일 쓰기 검사 ──────────────────────────────────────────
def w3() -> tuple[int, list[str]]:
    """선언된 계층 밖에 쓰는가. 지금은 손목록 10개 도구만 본다."""
    import yaml
    lay = yaml.safe_load(src(ROOT / "sources.yaml")).get("layers") or {}
    subs = {str(v.get("sub")) for v in lay.values() if v and v.get("sub")}
    WRITE = re.compile(r"\.(?:write_text|write_bytes|to_csv|to_file|to_json|mkdir)\(|open\([^)]*[\"']w")
    bad: list[str] = []
    for p in pys("tools", "src"):
        s = src(p)
        if not WRITE.search(s):
            continue
        for m in re.finditer(r"""ROOT\s*/\s*["']([\w./-]+)["']""", s):
            frag = m.group(1)
            if frag.split("/")[0] in {"data", "web"} and \
                    not any(frag.startswith(x) for x in subs):
                ln = s[:m.start()].count("\n") + 1
                bad.append(f"{p.relative_to(ROOT)}:{ln}  선언 밖 경로 조립 `{frag}`")
    return len(bad), bad[:12]


# ── W4  도구 배선 검사 ──────────────────────────────────────────
def w4() -> tuple[int, list[str]]:
    """tools 전량이 어디선가 불리는가. 지금은 33개가 면제다."""
    tools = sorted((ROOT / "tools").glob("*.py"))
    # ★ tools 끼리의 호출도 배선이다. 자기 자신만 뺀다 — 이것을 빼먹어
    #   `codepatch` 가 `b1_w4` 에 import 되는데도 "호출부 0" 으로 잡혔다.
    # ★ 배치 적용 스크립트(b1_*)는 뺀다. 그것은 도구 이름을 **고치려고**
    #   들고 있는 것이지 배선이 아니다. 넣었더니 일곱이 배선된 것처럼 보였다.
    hay = "\n".join(src(p) for p in
                    [x for x in pys("src", "tests", "tools")
                     if not x.name.startswith(("b1_", "b2_", "b3_", "b4_", "b5_"))] +
                    sorted(ROOT.glob("verify.sh")) + sorted((ROOT / "tools").glob("*.sh")) +
                    sorted((ROOT / ".github").rglob("*.yml")) +
                    sorted((ROOT / "docs").glob("*.md")))
    bad: list[str] = []
    for p in tools:
        stem = p.stem
        if stem in ("deadcheck", "widen"):
            continue
        # 자기 파일 안의 자기 이름은 배선이 아니다
        hay_x = hay.replace(src(p), "")
        # ★ 이름이 **언급**된 것과 **불리는** 것은 다르다. 언급으로 재면
        #   0건이 나오고, 0건은 깨끗한 것이 아니라 프로브가 죽은 것이다.
        called = re.search(
            rf"(?:python\s+)?tools/{stem}\.py"          # 셸·CI·문서
            rf"|python\s+-m\s+tools\.{stem}\b"
            rf"|\bimport\s+{stem}\b|\bfrom\s+{stem}\s+import", hay_x)
        if not called:
            bad.append(f"tools/{p.name}  호출부 0건 — 이름만 있고 부르는 곳이 없다")
    return len(bad), bad[:12]


# ── W5  문체 검사 대상 ──────────────────────────────────────────
def w5() -> tuple[int, list[str]]:
    """sources.yaml 의 산문도 문체 규약 대상인가. 지금은 대상 밖이다."""
    p = ROOT / "sources.yaml"
    s = src(p)
    VOICE = re.compile(r"(마라|말라|해라|하라|봐라|보라|써라|쳐라|둬라|들어라|물어라|"
                       r"적어라|지워라|옮겨라|받아라|만들어라|정해라|고쳐라|넣어라|빼라|"
                       r"걸어라|돌려라|쪼개라|세라|끄라|남겨라|믿지 말고)")
    bad = [f"sources.yaml:{s[:m.start()].count(chr(10)) + 1}  명령형 `{m.group(1)}`"
           for m in VOICE.finditer(s)]
    stars = Counter()
    for i, ln in enumerate(s.splitlines(), 1):
        if "★" in ln:
            stars[i // 50] += 1
    dense = [f"sources.yaml:~{k * 50}  ★ {v}개 (한도 8)" for k, v in stars.items() if v > 8]
    return len(bad) + len(dense), (bad + dense)[:12]


# ── W6  절 참조 검사 ────────────────────────────────────────────
def w6() -> tuple[int, list[str]]:
    """§N-M 참조가 실재하는가. 지금은 하위절 3개 이상인 절만 본다."""
    # ★ § 참조가 전부 MASTER 를 가리키지 않는다 — PLAN 23 · DECISIONS 6 이
    #   섞여 있다. 전부 MASTER 에 물으면 그 29건이 통째로 거짓 빨간불이다.
    real: dict[str, set[str]] = {}
    for nm in ("MASTER", "PLAN", "DECISIONS"):
        f = ROOT / "docs" / f"{nm}.md"
        real[nm] = ({f"{a}-{b}" for a, b in
                     re.findall(r"^#{2,4}\s*(\d+)-(\d+)", src(f), re.M)}
                    | set(re.findall(r"^#{2,4}\s*(\d+)[.\s]", src(f), re.M))
                    ) if f.exists() else set()
    REF = re.compile(r"(MASTER|PLAN|DECISIONS)?\s*§\s*(\d+)(?:-(\d+))?")
    bad: list[str] = []
    # ★ tools/batches 는 **과거를 적는 문서**다. 이미 끝난 배치가
    #   왜 그렇게 했는지를 적으며 남의 문서 절 번호를 인용한다 —
    #   DECISIONS §18 의 인용 블록을 면제한 것과 같은 이유다.
    _t = [p for p in pys("src", "tools", "tests")
          if "batches" not in p.parts]
    for p in _t + sorted((ROOT / "docs").glob("*.md")) \
            + sorted((ROOT / "web").rglob("*.js")):
        s = src(p)
        for m in REF.finditer(s):
            ref = f"{m.group(2)}-{m.group(3)}" if m.group(3) else m.group(2)
            named = m.group(1)
            if named:
                # 문서를 지목했으면 그 문서에서만 찾는다
                if real.get(named) and ref not in real[named]:
                    ln = s[:m.start()].count("\n") + 1
                    bad.append(f"{p.relative_to(ROOT)}:{ln}  {named} §{ref} 없음")
            else:
                # ★ 표기 없는 참조를 MASTER 로 단정하면 §104(DECISIONS)가
                #   거짓 빨간불이 된다. **세 문서 어디에도 없을 때만** 죽은
                #   참조다. 어느 문서인지 모호한 것은 별개 축이다.
                if not any(ref in v for v in real.values() if v):
                    ln = s[:m.start()].count("\n") + 1
                    bad.append(f"{p.relative_to(ROOT)}:{ln}  §{ref} 가 세 문서 어디에도 없다")
    return len(bad), bad[:12]


AXES = [
    ("W1  정적 검사 범위", "src → src+tools+tests", w1),
    ("W2  임계값 정본", "segments.py → 전 저장소", w2),
    ("W3  파일 쓰기", "손목록 10 → tools 전량", w3),
    ("W4  도구 배선", "EXEMPT 33 면제 → 전량", w4),
    ("W5  문체 대상", "문서 7 → + sources.yaml", w5),
    ("W6  절 참조", "하위절 3+ → 전 절", w6),
]


def main() -> int:
    tot = 0
    print("넓혔을 때 새로 걸리는 것 — 편집 전 실측\n")
    for name, how, fn in AXES:
        try:
            n, sample = fn()
        except Exception as e:
            print(f"  {name:20s} ★ 프로브 예외 — {type(e).__name__}: {e}")
            continue
        tot += n
        flag = "   ★ 0건 — 프로브를 의심하라" if n == 0 else ""
        print(f"  {name:20s} {n:5d}건   {how}{flag}")
        for x in sample[:5]:
            print(f"        {x}")
        if n > 5:
            print(f"        … 외 {n - min(5, len(sample))}건")
        print()
    print(f"신규 예상 빨간불 합계  {tot}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
