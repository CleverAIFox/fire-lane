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

★ gitleaks 는 Go RE2 이고 여기는 파이썬 `re` 다. 쓰는 문법이 `\\s` `\\w` 문자류와
  수량자뿐이라 두 엔진에서 뜻이 같다. 엔진 차이가 나는 문법(역참조·전방탐색)을
  넣으면 이 검사가 거짓말을 하게 된다 — 넣지 마라.
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
    out = []
    for rule in _cfg().get("rules", []):
        for al in rule.get("allowlists", []):
            out.append({"rule": rule.get("id"), **al})
        if "allowlist" in rule:
            out.append({"rule": rule.get("id"), "_old_form": True, **rule["allowlist"]})
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
