"""`doc_fsck ③` — 대장이 「없다」고 적은 값이 실물에 있는가.  (§258-19)

IN    sources.yaml 의 `absent` 선언 · 그 선언이 지목한 실물
OUT   결함 문장 목록 (비면 통과)
밖    「있다」고 적은 값이 실제로 있는가는 안 본다 — 그것은 `check_schema` 다.
      값이 **옳은가**도 안 본다. 여기서 묻는 것은 「없다고 했는데 있나」 하나다.
부류  생산   산출물·대장·그림을 만든다  (DECISIONS §398)
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


# ── 3. 부재 선언 — "없다" 고 적은 값이 실물에 있는가 ──────────────
def _key_in_text(path: str, text: str, key: str) -> bool:
    """그 파일 형식에서 `key` 가 **필드로** 있는가.

    ★ 2026-09-03. 종전에는 형식과 무관하게 `f'"{key}"'` 로만 찾았다 —
      큰따옴표로 감싼 JSON 키 문법이다. 그래서 CSV 는 헤더에 컬럼이
      분명히 있어도 영원히 "그 키가 없다" 로 울었다.

      `nfa_dispatch_119.csv` 의 헤더가 `DCLR_PSTN_LAT,DCLR_PSTN_LOT,...`
      인데 검사는 `"DCLR_PSTN_LAT"` 를 찾았다. **필드 이름이 `json_key`
      인데 대장은 CSV 컬럼도 그 이름으로 적게 되어 있다** — 이름과
      실제 형식이 어긋난 것이고, 건초더미에 `.csv` 를 더해도 안 풀렸다.

    ★ 형식으로 갈라 본다. `json_key` 라는 필드명은 그대로 둔다 —
      바꾸면 대장 전건과 DECISIONS §91 참조가 함께 움직여야 한다.
    """
    if path.endswith(".csv"):
        head = text.split("\n", 1)[0]
        cols = [c.strip().strip('"').lstrip("\ufeff") for c in head.split(",")]
        return key in cols
    return f'"{key}"' in text


def _has_key(p, key: str) -> bool:
    return _key_in_text(str(p).replace("\\", "/"), 
                        p.read_text(encoding="utf-8", errors="ignore"), key)


def check_absent(led: dict) -> list[str]:
    """`absent:` 선언을 실물과 **양방향**으로 대조한다.

    ★ `absent` 는 "어디에도 없다" 가 아니라 **"이 출처에 없다"** 다.
      스코프가 없으면 후자로 읽히고, 2026-09-02 에 셋 다 거짓 선언으로
      드러났다 — `profiles.json` 이 커밋되자 값이 다 있었다.

    ★ 이름을 추측하지 않는다. 종전에는 `turn_radius_m` 을 camelCase 로
      바꾸고 접미를 떼어 찾았는데 실물은 `turningRadius` 였다. **우연히
      엇갈려 통과했다.** 소화전 속성이 `속성 0종` 으로 조용히 발행된 것과
      같은 형태다(DECISIONS §49). `json_key` 로 못박는다.

    판정 둘 —
        elsewhere 있음   그 파일에 json_key 가 **있어야** 한다. 없으면
                        이름이 바뀐 것이고 선언이 낡았다
        elsewhere 없음   진짜 부재. 저장소 어디에도 **없어야** 한다
    """
    entries: list[tuple[str, str, object]] = []

    def walk(node, trail: str):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "absent" and isinstance(v, dict):
                    entries.extend((trail or "(최상위)", f, s)
                                   for f, s in v.items())
                else:
                    walk(v, f"{trail}.{k}" if trail else k)

    walk(led, "")
    if not entries:
        return []

    bad: list[str] = []
    hay: list[tuple[str, str]] = []
    # ★ 2026-09-03. 건초더미가 `data/processed/*.json` 만 봤다. 그런데
    #   `ingest` 는 `<key>.csv` 도 낸다(nfa_dispatch_119.csv 등).
    #   그래서 `.csv` 를 `elsewhere` 로 적으면 파일이 실재해도 영원히
    #   "그 키가 없다" 로 울었다 — **검사 범위가 실물보다 좁았다.**
    #   오늘 네 번째로 같은 형태다(scan_data §4 · intake stem ·
    #   normalize_raw 정규식 · 여기).
    for g in ("web/**/*.json", "web/**/*.js", "data/field/*.csv",
              "data/processed/*.json", "data/processed/*.csv"):
        for f in ROOT.glob(g):
            if f.is_file():
                hay.append((str(f.relative_to(ROOT)),
                            f.read_text(encoding="utf-8", errors="ignore")))

    for where, field, spec in entries:
        tag = f"{where}.absent.{field}"
        if not isinstance(spec, dict):
            bad.append(f"{tag} 이 스코프를 안 든다. `in:` · `json_key:` 를 "
                       f"적는다 — absent 는 '어디에도 없다' 가 아니라 "
                       f"'그 출처에 없다' 이다(DECISIONS §91)")
            continue
        for need in ("in", "json_key"):
            if not spec.get(need):
                bad.append(f"{tag} 에 `{need}:` 가 없다")
        key = spec.get("json_key")
        if not key:
            continue
        src = spec.get("elsewhere")
        if src:
            p = ROOT / src
            if not p.exists():
                bad.append(f"{tag}.elsewhere 가 가리키는 {src} 이 없다")
            elif not _has_key(p, key):
                bad.append(f"{tag} 은 {src} 에 `{key}` 로 있다고 하는데 "
                           f"그 키가 없다. 이름이 바뀌었거나 선언이 낡았다 "
                           f"— 추측으로 메우지 않는다(§49)")
        else:
            hits = sorted({q for q, txt in hay
                            if _key_in_text(q, txt, key)})
            if hits:
                bad.append(f"{tag} 은 없다고 선언했는데 "
                           f"{' · '.join(hits[:3])} 에 `{key}` 가 있다. "
                           f"`elsewhere:` 로 어디에 있는지 적는다")
    return bad
