"""
contract_verdict.py — **수를 세고 래칫과 댄다.** 선언만 보는 갈래.

── 왜 생겼나 (2026-10-08 · DECISIONS §431 · PLAN #157) ────────
`contract.py` 가 **정확히 상한 600 에서 살고 있었다**(§398-8 때 주석을 깎아
맞춘 자리다). §427 이 `awaiting` 세 갈래를 더해 612, §429 가 래칫 둘의 사유를
더해 621, §431 이 import **한 줄**을 더해 622 — 상한에 붙어 사는 파일은
**기능 하나에 넘친다.** 행이 쪼갤 자리를 미리 적어 뒀고 그것이 이 묶음이다.

★ 래칫은 **양방향**이다. 늘면 울고, **줄여도 기록을 안 내리면 운다** —
  느슨해진 래칫은 초록으로 위장한다(§398-7 · W4-9).

★ `real_verdict` 는 감소를 rc=0 으로 보낸다(「조여라」 주석). 그런데
  `verify.sh` 의 「래칫 정합」 단계는 **정확히 같기**를 요구한다 — 둘이 다른
  엄격함을 쓰는 것은 의도다. 앞은 사람에게 권하고, 뒤는 머지를 막는다.

IN    `sources.yaml::datasets` (선언만)
OUT   없음 — `(bad, warn, no_contract, crs_n)` 과 `(rc, 할 말)`
PARAM `NO_CONTRACT_RATCHET` · `CRS_DECLARED_RATCHET` · `REAL_FAIL_RATCHET` ·
      `REAL_WARN_RATCHET`
밖    **실물을 안 본다.** 레이크 없이 돌고, 그래서 CI 에서도 돈다. 실물
      갈래(`check_one`)는 `contract.py` 가 들고 그쪽은 레이크를 요구한다.
"""
from __future__ import annotations

# ── 선언만 보는 갈래 — 레이크 불필요 ──────────────────────────
#: 실측 2026-09-28. 72종 중 36종이 `contract` 블록이 없다. **줄기만 한다.**
#: 늘면 울고, 줄여도 기록을 안 내리면 운다 — 느슨해진 래칫은 초록으로 위장한다.
#:
#: ★ 2026-10-05 (DECISIONS §397). 36 → 39. 법령·행정규칙·보도자료 PDF 셋을
#:   대장에 올렸다. **PDF 는 열 계약을 가질 수 없다** — 무계약 39 중 **11이
#:   PDF** 이고 그 열하나가 이 수의 바닥이다. 바닥을 안 적으면 「39를 0으로
#:   줄여라」가 영영 못 갚는 빚으로 읽힌다. 갚을 수 있는 몫은 **28**이다.
#: ★ 2026-10-07 (DECISIONS §429). 39 → 40. 소방청 「건축위원회(심의) 표준
#:   가이드라인 2023.12」을 정보공개청구로 받아 올렸다. **PDF 는 열 계약을 가질 수
#:   없다** — 바닥이 11 → **12** 가 됐고 갚을 수 있는 몫은 그대로 28 이다.
#: ★ 2026-10-13 (DECISIONS §515). 40 → 43. 정보공개 회신 셋을 올렸다 —
#:   xlsx 둘(`gjcity_oneway` · `safety_dongmyeong_fires`) · hwpx 하나
#:   (`gjpolice_oneway`). **PDF 와 같은 자리다** — 서식은 열 계약을 가질 수
#:   없고, 열이 생기는 것은 변환기를 지난 **뒤**다(`norm_convert`).
#:   바닥이 12 → **15** 가 됐고 갚을 수 있는 몫은 그대로 **28** 이다.
#: ★ `contract:` 를 적지 않은 것이 **고의다.** `raw_only` 는 읽는 자리가
#:   없어 그 블록이 한 번도 안 불린다 — 적으면 「선언은 섰는데 부르는 자리가
#:   없다」가 하나 더 생긴다(§243-2 부터 여섯 번 난 족). 변환기 산출 CSV 의
#:   열 계약은 그 CSV 가 ingest 에 **배선되는 판**이 적는다.
#: ★ 2026-11-07 (PLAN #55 ③). 38 → **37.** `nfa_mas_spec_2025` 를 `retired` 로 옮겼다 —
#:   hwp 라 열 계약이 없던 항목이 살아 있는 대장에서 빠졌다. 늘리지 않았고 **내렸다**
#:   (바닥 15 는 그대로 · 갚을 수 있는 몫만 하나 준다).
NO_CONTRACT_RATCHET = 37
#: 실측 2026-09-28. `crs_native` 35종. 좌표가 없는 갈래는 적을 근거가 없다 — 전수는 목표가 아니다.
#: ★ 2026-10-06 (§419). 35 → 37. V-World SHP 둘 — `raw_only` 라도 `.prj` 에 근거가 있으면 적는다.
CRS_DECLARED_RATCHET = 41

# ── 실물 갈래의 래칫 ──────────────────────────────────────────
#: 실측 2026-10-05, 레이크 있는 기계(Zd 전수 verify [64/99]). **75종 · 실패 8 · 경고 54.**
#:
#: ★ 이 수를 왜 래칫으로 두는가. 이 단계를 F 에서 `verify.sh` 에 처음 붙였고,
#:   처음 켜자마자 빨갰다. 그 빨간불은 **이 배치가 만든 회귀가 아니라 원래
#:   그랬던 것을 처음 재서 본 것**이다. 고치려면 대장 72종을 실물과 하나씩
#:   맞춰야 하고 그것은 한 배치의 일이 아니다.
#:
#: ★ 그런데 영구히 빨간 관문은 **꺼진 관문보다 나쁘다.** 사람이 그 빨강을
#:   풍경으로 만들고, 그 옆에서 진짜 회귀가 지나간다(§69 와 같은 자리).
#:   그래서 「지금 값」을 기록하고 **늘면 울게** 한다. 이 저장소가
#:   `suppress` · `gate_parity` · 커버리지에서 이미 쓰는 규약이다.
#:
#: ★ 래칫은 **목표가 아니다.** 8 과 51 은 갚아야 할 빚이고 PLAN 이 그 줄을 든다.
#:   줄면 기록을 조이라고 운다 — 느슨해진 래칫은 초록으로 위장한다.
#: ★ 2026-11-07 (DECISIONS §657). 8 → **7.** 레이크 기계의 실측이 7 이고 관문이 조이라고 울었다. 조이는 쪽이라 판정 폐포 밖이다. 경고 쪽(58)은 안 건드린다 — 아래.
REAL_FAIL_RATCHET = 7
#: ★ 2026-10-05 — 51 → 54 (DECISIONS §398-8). `raw_only` PDF 셋이 대장에 올라
#:   각각 「contract 블록 없음」 경고를 낸다. **같은 원인이 래칫 둘을 움직이는데
#:   하나만 적었다** — `NO_CONTRACT_RATCHET` 만 올려서 레이크 있는 기계가
#:   「이 배치가 늘렸다」로 빨갰다. 셋은 바닥이다(위 머리말).
#: ★ 2026-10-07 — 54 → 59 (DECISIONS §427 · §428 · §429). 다섯이 움직인다 —
#:     `vworld_uq153` · `vworld_uq164` · `eais_roadledger_dm`  실패 → 경고 (§427)
#:     `juso_adrdc`                                           새 항목 · awaiting (§428)
#:     `nfa_bldgcomm_guide`                                   새 항목 · 무계약 PDF (§429)
#:   즉 실패 11 → **8**(= `REAL_FAIL_RATCHET`) · 경고 54 → **59**.
#:   ★ 같은 원인이 래칫 둘을 움직이므로 둘을 같이 적는다(바로 위 §398-8 이 하나만
#:     적어 당한 그것). 그리고 **항목을 더할 때마다 이 수를 다시 센다** — 처음에
#:     57 로 적고 `juso_adrdc` 를 더하면서 안 고쳤다가 §429 에서 같이 잡았다.
#:   ★ **반입되면 내려간다.** `awaiting` 을 지우는 판이 이 수를 조인다.
#:
#: ★ 2026-10-08 (DECISIONS §433). 59 → **57.** 그 판이 왔다 — 다섯이 전부
#:   반입됐고 `awaiting` 다섯 줄을 지웠다. 사람이 **재서** 보낸 수로 갈랐다 —
#:
#:     vworld_uq153        awaiting → `.prj` 7변수 경고   ±0
#:     vworld_uq164        awaiting → 없음                −1
#:     juso_adrdc          awaiting → 없음                −1
#:     nfa_bldgcomm_guide  awaiting → 무계약 PDF 경고      ±0
#:     eais_roadledger_dm  awaiting → 컬럼 추가 경고       ±0
#:
#: ★ **실패는 안 움직인다(8 그대로).** 지우자마자 실측은 9 였다 —
#:   `vworld_uq153` 이 「선언 5174 인데 `.prj` 는 …」로 떨어졌다. 읽어 보니
#:   `.prj` 가 **스스로 5174 라고 적고** 다른 것은 `TOWGS84` 하나였다.
#:   관문이 옳은 선언을 틀렸다고 운 것이고, 그것을 고쳤다(`_datum_shift_only`).
#:   **실패 9 를 받아적었으면 그 결함이 래칫 안에 숨었다.**
#:
#: ★ 2026-10-13 (DECISIONS §515). 57 → **60.** 새 항목 셋이 각각 경고 하나를
#:   낸다(`awaiting` 하나 = 경고 하나 · 위 §433 표가 그 단가를 쟀다).
#:   **같은 원인이 래칫 둘을 움직이므로 둘을 같이 적는다** — §398-8 이 하나만
#:   적어 당한 그것이고, `NO_CONTRACT_RATCHET` 도 같이 40 → 43 이다.
#: ★ **이 수는 레이크 있는 기계에서만 재진다.** 짜는 쪽은 단가(+1/항목)로
#:   더했다. 실측이 다르면 관문이 정확한 수를 찍으니 그 수로 고친다 —
#:   §429 가 「항목을 더할 때마다 다시 센다」로 적은 그 자리다.
#: ★ **반입되면 내려간다.** `awaiting` 셋을 지우는 판이 이 수를 조인다.
#:
#: ★ 2026-11-02. 59 → **58.** 실물을 raw 에 넣은 판(`vworld_uq153` 등)이 경고 하나를 걷었다.
#:   조이는 쪽이라 판정 폐포 밖이고 재잠금이 따라오지 않는다. 실패 쪽(8)은 건드리지 않는다.
#:
#: ★ 2026-11-07 (DECISIONS §657). **58 을 그대로 둔다 — 실측은 67 이고 관문이 「이 배치가 늘렸다」로 운다.** 내역 아홉은 §657-8 이 든다 —
#:   이 배치(§647 ~ §649)가 `nfa_*` 다섯을 `status: missing` 으로 내려 5 · §602 의 결손 선언 둘(`eais_roadledger_dm` · `vworld_uq164`) · 11-04 `a5a3467e` 의 `.prj` 없음 둘(`building_connector` · `building_entrance`).
REAL_WARN_RATCHET = 58


#: ★ 2026-11-09 (PLAN #185 ②). 래칫 넷 중 **선언 갈래 둘**을 `tools/ratchet.py` 의 선언 안으로 들였다 — 이 행의 문제가 「선언 밖 래칫이 샌다」였다
#:   (`ratchet --write` 가 못 올리고 못 조인다). 방향: 무계약은 늘면 우는 쪽(`down`) · `crs_native` 선언 수는 줄면 우는 쪽(`up`). 둘 다 레이크 없이 재서 CI 에서도 돈다.
#:   ★ **실물 갈래 둘(`REAL_FAIL_RATCHET` · `REAL_WARN_RATCHET`)은 선언 밖에 남겼다** — 사유 둘: ① 레이크(raw)가 있어야 재는데 `tools/ratchet.py` 가 CI 에서
#:   건너뛰는 길(`# ci-exempt:`)은 `tools/verify.sh` 의 **단계에 매달려** 있고 이 실물 갈래는 그 단계가 아니다 ② `REAL_WARN_RATCHET` 은 **일부러 느슨한 채**다 —
#:   위 DECISIONS §657 이 「58 을 그대로 둔다」고 적었고 실측은 그보다 높다. 선언 안에 들이면 이 기계에서 `ratchet.py` 가 영구히 빨갛다(「느슨해진 쪽 0」을 못 지킨다).
RATCHETS = {"NO_CONTRACT_RATCHET": "down", "CRS_DECLARED_RATCHET": "up"}


def real_counts(reports: list, unknown: int = 0) -> tuple[int, int]:
    """(실패, 경고) — 실물 갈래의 두 수. `contract.main` 이 쓰는 **셈의 자리**다(셈이 한 곳이어야 판정이 갈리지 않는다)."""
    from firelane.contract_crs import FAIL, WARN
    return (sum(1 for r in reports if r.worst == FAIL) + unknown, sum(1 for r in reports if r.worst == WARN))


def ratchet_values() -> dict[str, int]:
    """`tools/ratchet.py` 가 부르는 실측 — 선언 갈래 둘의 지금 값. **레이크를 안 읽는다**(실물 갈래는 안 잰다 — 위 사유)."""
    from firelane import ledger as _led

    _bad, _warn, no_contract, crs_n = declared_issues(_led.load().get("datasets", {}))
    return {"NO_CONTRACT_RATCHET": no_contract, "CRS_DECLARED_RATCHET": crs_n}


def real_verdict(nf: int, nw: int) -> tuple[int, list[str]]:
    """전수 갈래의 판정. **키를 짚어 부른 것에는 안 쓴다** — 그때는 정확히 그 종이다."""
    say: list[str] = []
    rc = 0
    for what, got, rat, name in (("실패", nf, REAL_FAIL_RATCHET, "REAL_FAIL_RATCHET"),
                                 ("경고", nw, REAL_WARN_RATCHET, "REAL_WARN_RATCHET")):
        if got > rat:
            say.append(f"✗ {what} {got} — 기록 {rat} 보다 늘었다. **이 배치가 늘렸다**")
            rc = 1
        elif got < rat:
            say.append(f"★ {what} {got} 로 줄었다 — `{name}` 을 {got} 으로 조여라."
                       f" 안 조이면 되돌아간다")
        else:
            say.append(f"  {what} {got} = 래칫 {rat} (갚아야 할 빚이다 · PLAN)")
    return rc, say


def declared_issues(ds: dict) -> tuple[list[str], list[str], int, int]:
    """대장 선언 자체만 본다. **실물을 안 읽는다** → CI 에서 돈다.

    (실패, 경고, 무계약 수, crs_native 채운 수)
    """
    from firelane import ledger as _led
    from firelane import ledger_check as lgc

    bad: list[str] = []
    warn: list[str] = []
    no_contract = crs_n = 0
    for key in sorted(ds):
        e = ds[key] or {}
        c = e.get("contract") or {}
        if not c:
            no_contract += 1
        # ★ 오타 난 키는 **검사를 사라지게 한다.** `required_col` 이라 적으면
        #   `c.get("required_cols")` 가 None 을 받고 아무 일도 안 일어난다.
        for k2 in c:
            if k2 not in _led.CONTRACT_KEYS:
                bad.append(f"{key}: 모르는 계약 키 `{k2}` — "
                           f"오타면 검사가 조용히 사라진다. "
                           f"어휘는 `ledger.CONTRACT_KEYS`")
        # ★ 좌표계 **판정**은 여기가 안 한다. `ledger_check.check_entry` 가
        #   정본이고(§285-2) 여기는 **센다.** 규칙을 또 적으면 세 번째
        #   사본이 된다 — 그날 실제로 만들 뻔했다.
        if _led.crs_of(e):
            crs_n += 1
        else:
            warn += [f"{key}: {i.msg}" for i in lgc.check_entry(key, e)
                     if i.level == _led.WARN and "crs_native" in i.msg]
    return bad, warn, no_contract, crs_n
