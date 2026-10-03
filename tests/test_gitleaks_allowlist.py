#!/usr/bin/env python3
"""
test_gitleaks_allowlist.py — **비밀 검사의 예외가 살아 있고, 좁은가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-21 (DECISIONS §209). v0.29 방송의 A-0 이 찍은 봉인이 secret-scan 에 걸렸다.

    RuleID:  generic-api-key
    File:    data/dms/SEAL.json:304
    Finding: "src/firelane/segkey.py": "fb1d88a1…"    ← 파일 지문(sha256)

파일 이름 `segkey` 의 `key` 뒤 영숫자를 API 키로 읽었다. 봉인이 **파일별 지문**을
담게 된 뒤 처음 찍힌 봉인이라 처음 났다. 거짓 경보라 예외를 더했다.

그리고 그 예외를 짜다가 **이미 있던 예외가 죽어 있는 것**을 찾았다.

    regexes = ['''key: [a-z][a-z0-9_]{8,}''']      ← regexTarget 없음

gitleaks 는 regexTarget 을 안 적으면 **비밀값 자체**에 정규식을 댄다. 비밀값에는
`key: ` 가 없으므로 이 정규식은 **한 번도 맞은 적이 없다.** 2026-09-10 부터
죽어 있었고, 설명이 이름까지 들어 푼다고 적은 `tools/batches/b2_*.py` 두 건이
이력 전수 스캔에서 그대로 걸렸다. CI 가 초록이었던 것은 그 파일들이 이미
지워져 push 범위에 안 들어왔기 때문이다 — **틀린 이유로 초록이었다.**

★ 이 저장소의 결함 대장이 세는 족 그대로다 —— 예외가 **있다고 적혀 있는데**
  실제로는 아무것도 안 풀었다. `test_tools_are_wired` 가 면제 31개 중 12개가
  죽은 것을 찾은 날과 같은 모양이다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 설정이 읽히는가 (안 읽히면 gitleaks 가 **조용히 기본값으로** 돈다)
    2. allowlist 마다 regexTarget 이 명시돼 있는가 — 기본값이 그것을 죽였다
    3. 각 allowlist 가 **자기가 푼다고 적은 예**를 실제로 푸는가 (양성 대조)
    4. 봉인 예외가 지금의 `SEAL.json` 지문 줄을 **전부** 푸는가
    5. 봉인 예외가 **토큰 모양은 안 푸는가** (음성 대조) · 경로가 봉인 하나인가
    6. 트리 전수 단계가 `verify.sh` 에 **있고** `--redact` 이고 범위 선언이 없는가
    7. 전역 경로 예외가 **gitignore 된 자리뿐인가** (그 전제는 treecheck T2 가 든다)
    8. 추적되는 파일에 **UUID 꼴 값**이 없는가 — 2026-10-03 에 새던 그 모양

★ gitleaks 는 Go RE2 이고 여기는 파이썬 `re` 다. 쓰는 문법이 `\\s` `\\w` 문자류와
  수량자뿐이라 두 엔진에서 뜻이 같다. 엔진 차이가 나는 문법(역참조·전방탐색)을
  넣으면 이 검사가 거짓말을 하게 된다 — 넣지 마라.

★ 2026-10-03 (DECISIONS §376). **6·7·8 이 생긴 사유.** V-World 키가
  `sources.yaml` 의 추적되는 줄에 2026-08-09 부터 평문으로 있었다. 세 관문이
  다 **변화량**만 봤다(훅=스테이지 · 액션=커밋 범위 · 없음=트리). 그래서
  「훅보다 먼저 들어온 값」은 세 관문 모두에게 영원히 안 보였다.

  8 은 **바이너리를 안 쓴다.** `gitleaks` 가 없는 기계에서도 pytest 는 도므로,
  트리 전수(6)가 `note` 로 빠지는 날에도 이 한 모양은 계속 막힌다.
  실측 — 추적 파일 2,057개에서 **0건**이다. 상한을 0 으로 못박는다.
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / ".gitleaks.toml"
SEAL = ROOT / "data" / "dms" / "SEAL.json"


def _cfg() -> dict:
    return tomllib.loads(CFG.read_text(encoding="utf-8"))


def _allowlists() -> list[dict]:
    """설정 안의 예외 **전부.** 규칙별과 전역 둘 다.

    ★ 2026-10-03 (DECISIONS §376). 종전에는 `cfg["rules"]` 밑만 모았다 —
      **전역 예외(`[[allowlists]]`)를 안 봤다.** 그러면 `regexTarget` 검사
      (2)의 우주가 설정보다 좁고, 전역에 정규식 예외를 더하는 날 그것만
      기본값 `"secret"` 으로 조용히 죽는다. §209 가 당한 그 모양 그대로다.
      분모를 설정에서 읽는다.
    """
    cfg = _cfg()
    out = []
    for rule in cfg.get("rules", []):
        for al in rule.get("allowlists", []):
            out.append({"rule": rule.get("id"), **al})
        if "allowlist" in rule:
            out.append({"rule": rule.get("id"), "_old_form": True, **rule["allowlist"]})
    for al in cfg.get("allowlists", []):
        out.append({"rule": "(전역)", **al})
    if "allowlist" in cfg:
        out.append({"rule": "(전역)", **cfg["allowlist"]})
    return out


def _seal_allowlist() -> dict:
    hits = [a for a in _allowlists()
            if any("SEAL" in p for p in a.get("paths", []))]
    assert len(hits) == 1, f"봉인 예외가 {len(hits)}개다 — 하나여야 한다"
    return hits[0]


def _digest_lines() -> list[str]:
    """`SEAL.json` 에서 **gitleaks 가 물 수 있는 16진 값**을 담은 줄 전부.

    ★ 기준은 값이 **16진 10자 이상**인가다(generic-api-key 가 무는 최소 길이 언저리).
      `"commit": "ad1c679"`(7자) 같은 짧은 해시는 빠진다 — 처음 짰을 때 그것까지
      물어 「예외가 못 푼다」로 빨개졌다.
    ★ **예외가 받아주는 길이(16·64)로 거르지 않는다.** 그렇게 거르면 「예외가 푸는
      줄만 골라 예외가 푸는지 본다」는 동어반복이 되고, 지문이 32자로 바뀌어도
      이 검사는 초록이다. 키가 경로인지도 안 거른다 — 절 ID(`MASTER-082`)를 키로
      쓰는 지문이 850줄 넘게 있고, 그 절 이름에 `key` 가 들어가는 날 똑같이 걸린다.
    """
    pat = re.compile(r'^\s*"[^"]+": "[0-9a-f]{10,}",?\s*$')
    return [ln for ln in SEAL.read_text(encoding="utf-8").splitlines() if pat.match(ln)]


# ── 1 · 읽히는가 ────────────────────────────────────────────────
def test_config_parses_and_has_allowlists():
    """설정이 읽히는가. **안 읽히면 gitleaks 는 조용히 기본값으로 돈다**(2026-09-13 에 한 번 당했다)."""
    cfg = _cfg()
    assert cfg.get("extend", {}).get("useDefault") is True, "기본 규칙 위에 얹는 설정이 아니다"
    assert _allowlists(), "allowlist 가 0개다 — 이 검사가 빈 그물이 됐다"


# ── 2 · 기본값이 죽이지 않는가 ─────────────────────────────────
def test_every_allowlist_states_its_regex_target():
    """정규식을 가진 allowlist 는 regexTarget 을 **명시**한다.

    ★ 기본값 "secret" 이 첫 allowlist 를 죽였다. 정규식은 `key: ` 로 시작하는데
      비밀값에는 `key: ` 가 없다. 적지 않은 기본값은 **읽는 사람 머릿속의 값**과
      다르다 — 그래서 적게 한다.
    ★ 옛 형식 `[rules.allowlist]` 도 금한다. 한 규칙에 예외 하나만 되고, 둘째를
      더하려면 형식을 바꿔야 한다 — 섞으면 판마다 해석이 갈린다.
    """
    for al in _allowlists():
        assert not al.get("_old_form"), (
            f"`{al['rule']}` 가 옛 형식 `[rules.allowlist]` 를 쓴다 — `[[rules.allowlists]]` 로 옮겨라")
        if al.get("regexes"):
            assert al.get("regexTarget") in ("secret", "match", "line"), (
                f"`{al['rule']}` 의 allowlist 에 regexTarget 이 없다.\n"
                "  기본값은 \"secret\"(비밀값 자체)이다. 2026-09-10~09-21 에 그 기본값이\n"
                "  `key: ` 로 시작하는 정규식을 **한 번도 안 맞게** 만들었다(DECISIONS §209).")


# ── 3 · 자기가 푼다고 적은 것을 푸는가 ─────────────────────────
def test_the_ledger_key_allowlist_is_alive():
    """대장 키 예외가 **설명에 적힌 예**를 실제로 푸는가.

    ★ 설명은 `key: juso_spotaddr_geom_2608` 를 푼다고 적는다. regexTarget 이
      "match" 면 gitleaks 가 정규식을 대는 글은 규칙이 잡은 **매치 전체**이고,
      그것이 `key: juso_…` 꼴이다. 거기 맞아야 살아 있는 것이다.
    """
    als = [a for a in _allowlists() if any("key: " in r for r in a.get("regexes", []))]
    assert als, "대장 키 예외를 못 찾았다 — 지웠으면 이 검사도 같이 지워라"
    al = als[0]
    assert al["regexTarget"] in ("match", "line"), (
        "대장 키 예외의 정규식이 `key: ` 로 시작하는데 regexTarget 이 \"secret\" 이다 —\n"
        "  비밀값에는 `key: ` 가 없으므로 **영원히 안 맞는다.** 그것이 2026-09-21 까지의 상태였다.")
    example = "key: juso_spotaddr_geom_2608"
    assert example in al["description"], "설명의 예가 바뀌었다 — 이 검사도 같이 옮겨라"
    assert any(re.search(r, example) for r in al["regexes"]), (
        f"대장 키 예외가 자기 설명의 예 `{example}` 를 안 푼다 — 죽은 예외다")


# ── 4 · 봉인을 전부 푸는가 ─────────────────────────────────────
def test_seal_allowlist_covers_every_digest_line():
    """봉인 예외가 지금 `SEAL.json` 의 지문 줄을 **전부** 푸는가.

    ★ 지문의 길이·모양이 바뀌면(예: 16자 → 32자) 예외가 조용히 빗나가고,
      다음 봉인이 또 secret-scan 에 걸린다. **봉인 파일과 예외를 묶는다.**
    """
    al = _seal_allowlist()
    assert al.get("regexTarget") == "line", "봉인 예외는 줄 모양으로 푼다 — regexTarget = \"line\""
    lines = _digest_lines()
    assert len(lines) > 100, (
        f"SEAL.json 에 지문 줄이 {len(lines)}개뿐이다 — 추출이 죽었거나 봉인이 바뀌었다")
    miss = [ln.strip() for ln in lines
            if not any(re.search(r, ln) for r in al["regexes"])]
    assert not miss, (
        f"봉인 예외가 지문 줄 {len(miss)}개를 못 푼다 — 예: {miss[:3]}\n"
        "  지문 모양이 바뀌었으면 `.gitleaks.toml` 의 봉인 예외도 같이 고쳐라.\n"
        "  안 고치면 다음 A-0 봉인 PR 이 secret-scan 에서 빨개진다.")
    # 걸렸던 그 줄
    assert any('"src/firelane/segkey.py"' in ln for ln in lines), (
        "2026-09-21 에 걸렸던 `segkey.py` 줄이 봉인에 없다 — 판정 코드 범위가 바뀌었나")


# ── 5 · 좁은가 ──────────────────────────────────────────────────
def test_seal_allowlist_does_not_let_tokens_through():
    """봉인 예외가 **토큰 모양은 안 푸는가.** 푸는 쪽만 보면 넓어져도 모른다.

    ★ 토큰 문자열은 **여기서 조립한다.** 파일에 그대로 적으면 이 시험 파일이
      secret-scan 에 걸린다 — 봉인 파일이 걸린 것과 같은 이유로.
    """
    al = _seal_allowlist()
    tok = {
        "대문자 16진": '"src/firelane/segkey.py": "' + "AB12" * 16 + '",',
        "gh 접두 토큰": '"src/firelane/segkey.py": "' + "gh" + "p_" + "a1B2" * 9 + '",',
        "길이가 지문이 아님": '"src/firelane/segkey.py": "' + "ab" * 20 + '",',
        "경로 키가 아님": '"api_key": "' + "ab" * 32 + '" "tail"',
    }
    let = [k for k, ln in tok.items() if any(re.search(r, ln) for r in al["regexes"])]
    assert not let, f"봉인 예외가 토큰 모양을 푼다 — {let}. 줄 모양을 다시 좁혀라"
    assert al.get("condition") == "AND", (
        "봉인 예외가 경로 **또는** 줄 모양으로 푼다 — AND 가 아니면 저장소 어디서든 그 줄 모양이 풀린다")
    assert al.get("paths") == [r"^data/dms/SEAL\.json$"], (
        f"봉인 예외의 경로가 봉인 하나가 아니다 — {al.get('paths')}")


def test_seal_file_is_json_the_allowlist_reads():
    """봉인이 JSON 으로 읽히고 줄 단위 구조가 유지되는가.

    ★ 줄 모양 예외는 **들여쓰기 한 줄에 키 하나**라는 전제 위에 선다.
      `dms.py` 가 `indent=` 를 빼고 한 줄로 쓰면 줄 모양이 통째로 바뀌어 예외가
      빗나간다. 그 전제를 여기서 못박는다.
    """
    data = json.loads(SEAL.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and "commit" in data, "봉인이 봉인 모양이 아니다"
    assert SEAL.read_text(encoding="utf-8").count("\n") > 100, (
        "봉인이 한 줄로 쓰였다 — 줄 모양 예외의 전제가 깨졌다")


# ── 6 · 트리를 보는 자리가 있는가 ──────────────────────────────
def test_the_working_tree_scan_is_wired_into_verify():
    """`verify.sh` 가 **트리 전수**를 도는가. (DECISIONS §376)

    ★ 이것이 없던 동안 비밀값 방어 셋이 다 **변화량**만 봤다 — 훅은 스테이지,
      액션은 커밋 범위. 「훅보다 먼저 트리에 들어온 값」은 셋 모두에게 영원히
      안 보였고, V-World 키가 56일 그 상태로 있었다.

    ★ **범위 선언이 붙으면 안 된다.** `step()` 은 `scope` 가 붙은 단계를
      `--since` 범위 밖이면 건너뛴다. 비밀값은 「이번에 뭘 만졌나」와 무관하게
      트리에 있거나 없다 — 문서만 고친 배치에서 안 도는 관문은 관문이 아니다.
    """
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    lines = sh.splitlines()
    idx = [i for i, ln in enumerate(lines)
           if ln.lstrip().startswith("step ") and "비밀값 — 작업 트리 전수" in ln]
    assert len(idx) == 1, (
        "`verify.sh` 에 「비밀값 — 작업 트리 전수」 단계가 "
        f"{len(idx)}개다 — 하나여야 한다 (DECISIONS §376)")
    i = idx[0]
    body = lines[i] + (lines[i + 1] if lines[i].rstrip().endswith("\\") else "")
    # ★ 2026-10-04 (§381). 종전에는 이 자리에서 `gitleaks dir` 이라는 **글자**를
    #   찾았다. 그 하위명령은 8.19 에서 생겼고 apt 가 주는 것은 8.16 이라
    #   사람 기계에서 「unknown command "dir"」로 터졌다. 호출 꼴을
    #   `tools/treescan.sh` 하나로 모았으므로, 여기서는 **그 문을 부르는지**를
    #   보고 꼴은 그 파일에 묻는다. 같은 글자를 두 집에 적지 않는다.
    scan = ROOT / "tools" / "treescan.sh"
    assert "treescan.sh" in body, (
        "그 단계가 `tools/treescan.sh` 를 안 부른다 — 트리 전수의 정본이 거기다")
    assert scan.exists(), "`tools/treescan.sh` 가 없다"
    src = scan.read_text(encoding="utf-8")
    assert "--no-git" in src and "dir ." in src, (
        "`treescan.sh` 가 **트리**를 안 본다 — `gitleaks git` 은 이력·범위이고\n"
        "  이 문이 맡는 물음(지금 트리에 있나)이 아니다.\n"
        "  8.19 이상은 `dir`, 그 이전은 `detect --no-git` 이 같은 일을 한다")
    assert "--redact" in src, (
        "`--redact` 가 없다 — 걸리는 날 값이 화면·로그·`dms` 봉인에 남는다.\n"
        "  그것 자체가 두 번째 유출이다")
    assert "--exit-code 1" in src, (
        "걸려도 0 으로 끝나면 단계가 초록이 된다 — 검사가 아니라 장식이다")
    # ★ 창은 **앞 `step` 까지**다. `step()` 이 제 안에서 `SCOPE=""` 로 지우므로
    #   (`local _scope="$SCOPE"; SCOPE=""`), 직전 `step` 이후에 적힌 `scope` 만
    #   이 단계에 걸린다. 「바로 윗 줄」만 보면 `if …; then` 에서 멈춰
    #   그 **위**에 붙은 선언을 놓친다 — 처음 짰을 때 실제로 놓쳤다.
    window = []
    for j in range(i - 1, -1, -1):
        s = lines[j].strip()
        if s.startswith("step ") or s.startswith("note "):
            break
        window.append((j + 1, s))
    dangling = [(n, s) for n, s in window if s.startswith("scope ")]
    assert not dangling, (
        f"그 단계에 범위 선언이 걸린다 ({dangling[0][0]}행: {dangling[0][1]}) —\n"
        "  `--since` 가 범위 밖이면 건너뛴다. 비밀값 검사는 만진 파일과 무관하게 돌아야 한다")
    assert 'note "비밀값 — 작업 트리 전수"' in sh, (
        "gitleaks 가 없는 기계에서 **미측정을 세는** `note` 갈래가 없다.\n"
        "  조용히 빠지면 「검사했다」와 「검사기가 없었다」가 같은 초록이 된다 — 회색 = NULL")


# ── 7 · 전역 경로 예외가 좁은가 ────────────────────────────────
def test_the_global_path_allowlist_is_only_gitignored_files():
    """전역 경로 예외는 **gitignore 된 자리뿐인가.** (DECISIONS §376)

    트리 전수는 디스크를 훑으므로 `.env` 처럼 **키를 담는 것이 제 일인** 파일을
    빼야 한다. 안 빼면 제 기계에서 영원히 빨갛고, 그러면 사람이 단계를 끈다(§73).

    ★ **그 예외가 안전한 까닭은 다른 관문이 들고 있다** — 「무시인데 추적 중」은
      `treecheck` 의 T2 가 운다. 이 시험은 **그 전제를 못박는다**: 예외로 뺀
      경로가 `.gitignore` 에 없으면, 추적되는 파일을 조용히 면제하는 것이 된다.
    """
    glob_als = [a for a in _allowlists() if a["rule"] == "(전역)"]
    # ★ 처음에는 `if not glob_als: return` 이었다 — `deadcheck` 의 프로브 ③
    #   (조용한 통과)이 **그 자리에서 울었다.** 전역 예외가 사라지면 이 시험은
    #   조용히 통과하고, 그 사이 트리 전수가 `.env` 때문에 영원히 빨개진다.
    #   **없는 것이 정상인 상태가 아니다** — 그래서 단정으로 바꿨다.
    assert glob_als, (
        "전역 경로 예외가 없다. 트리 전수(`gitleaks dir`)는 디스크를 훑으므로\n"
        "  `.env` · `web/key.js` 가 걸려 **제 기계에서 영원히 빨갛다** —\n"
        "  그러면 사람이 그 단계를 끈다(§73). 지웠다면 트리 전수도 같이 지웠는지 보라")
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    ignored_pats = {ln.strip().lstrip("/") for ln in gi.splitlines()
                    if ln.strip() and not ln.strip().startswith("#")}
    for al in glob_als:
        assert not al.get("regexes"), (
            "전역 예외에 정규식이 붙었다 — 전역 정규식은 **저장소 어디서든** 푼다.\n"
            "  규칙별 예외(`[[rules.allowlists]]`)로 옮기고 경로를 함께 걸어라")
        assert al.get("paths"), "전역 예외에 경로가 없다 — 그러면 아무것도 안 푼다"
        for pat in al["paths"]:
            # `^\.env$` → `.env` 꼴로 되돌려 `.gitignore` 와 맞춘다
            plain = pat.strip("^$").replace("\\.", ".")
            assert any(plain == p or p.startswith(plain) or plain.startswith(p.rstrip("*"))
                       for p in ignored_pats), (
                f"전역 예외가 `{pat}` 를 푸는데 그 자리가 `.gitignore` 에 없다.\n"
                "  gitignore 되지 않은 경로를 면제하면 **추적되는 파일**을 조용히 푼다.\n"
                "  빼야 하는 자리면 `.gitignore` 에 먼저 넣어라 — 그러면 `treecheck` T2 가\n"
                "  「무시인데 추적 중」을 들어 주고, 이 예외의 전제가 선다")


# ── 8 · 바이너리 없이도 막히는 한 모양 ─────────────────────────
#: UUID 꼴. V-World 인증키가 이 모양이고, 2026-10-03 까지 추적되는 줄에 있었다.
_UUID = re.compile(
    r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b")
#: 글이 아닌 것. 읽어도 뜻이 없다.
_NOT_TEXT = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".gpkg", ".zip",
             ".pbf", ".woff", ".woff2", ".pdf", ".xlsx", ".docx", ".tif"}
#: **상한 0.** 실측(2026-10-03) — 추적 파일 2,057개에서 0건이다.
UUID_IN_TRACKED = 0


def _uuid_hits() -> list[tuple[str, int]]:
    from firelane import gitq
    tracked = gitq.tracked(ROOT)
    assert tracked is not None, (
        "git 에게 추적 목록을 못 물었다 — **빈 목록으로 안 바꾼다**(§372).\n"
        "  우주가 0 이 되면 이 검사가 「0건」으로 초록이 된다")
    out = []
    for rel in sorted(tracked):
        p = ROOT / rel
        if p.suffix.lower() in _NOT_TEXT or not p.is_file():
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out += [(rel, i) for i, ln in enumerate(txt.splitlines(), 1) if _UUID.search(ln)]
    return out


def test_no_tracked_file_carries_a_uuid_shaped_value():
    """추적되는 파일에 **UUID 꼴 값**이 없는가. (DECISIONS §376)

    ★ `gitleaks` 바이너리를 **안 쓴다.** 트리 전수 단계는 바이너리가 없으면
      `note`(미측정)로 빠진다 — 그 날에도 이 한 모양은 pytest 가 계속 막는다.
      새던 실물이 정확히 이 모양이었으므로, 가장 좁게 그것만 못박는다.

    ★ 세는 자리는 **추적 목록**이다(`gitq`). 디스크를 훑으면 `.env` 가 걸린다.
    """
    hits = _uuid_hits()
    assert len(hits) <= UUID_IN_TRACKED, (
        f"추적되는 파일에 UUID 꼴 값이 {len(hits)}건이다 (상한 {UUID_IN_TRACKED}) —\n"
        + "".join(f"    {rel}:{i}\n" for rel, i in hits[:10])
        + "  V-World 인증키가 이 모양이다. 비밀값이면 `.env` 로 옮기고 `.gitignore` 를 믿어라.\n"
        "  비밀이 아니면 **왜 아닌가를 적고** 상한을 올려라 — 올린 값은 내려가기만 한다.")


def test_the_uuid_net_is_not_empty():
    """양성 대조 — 그물이 **UUID 를 실제로 잡는가.**

    ★ 상한이 0 이고 실측이 0 이면 정규식이 깨져도 초록이다. 합성 한 줄로 그물이
      사는지 본다. 값은 **여기서 조립한다** — 파일에 UUID 를 그대로 적으면
      바로 윗 시험이 이 파일을 잡는다(그 자체가 양성 대조이기도 하다).
    """
    synth = "-".join(["AB12CD34", "EF56", "7890", "ABCD", "EF1234567890"])
    assert _UUID.search(f"  key: {synth}"), "UUID 그물이 죽었다 — 정규식을 고쳐라"
    assert not _UUID.search("  key: juso_spotaddr_geom_2608"), (
        "그물이 대장 키를 잡는다 — 오탐이면 사람이 이 검사를 끈다")
    assert not _UUID.search("  uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"), (
        "그물이 액션 고정 sha(16진 40자)를 잡는다 — 그것은 비밀이 아니다")
