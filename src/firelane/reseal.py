"""
reseal.py — **재도장을 어떻게 부르나.** 봉인지 한 칸만 지금 실물로 고친다.

── 왜 생겼나 (2026-10-11 · DECISIONS §460) ────────────────────
`shardseal.py` 가 581 → 647 이 됐다(상한 600). 늘어난 66줄은 `layers` 를
**계층 단위로 가르는** 판별식과 그 사유다. 깎을 줄이 아니라 **물음이 둘**이다 —

    shardseal.py   지문을 뜨고 비교한다      「무엇으로 만들었나 · 같은가」
    reseal.py      봉인지 한 칸을 고쳐 적는다  「받아도 되는가 · 누가 부르나」

`sealkeys.py` 가 2026-10-08 에 같은 사유로 갈라졌다(§431) — 그때 나간 것은
「무엇을 재나」였다. **받는 규칙은 `shardseal.check()` 와 같은 하나**를 쓴다 —
옛 판 지문과 같을 때만 받는다. 그 규칙을 두 벌로 적으면 갈린다(2족).

★ 이 파일은 **산출물을 한 바이트도 안 만든다.** `shardseal.py` · `stagerun.py`
  와 같은 자리이므로 `NOT_PRODUCERS` 가 같이 든다 — 안 넣으면 안내 문구 한 줄에
  45샤드가 찢어지고, 8GB 기계에서 그것은 `ngii_road` OOM 이다(§165-8 · §266).

IN    `data/processed/_manifest.json` · `sources.yaml`
OUT   그 대장(칸 하나) · `_lineage.json` 의 대장 해시
PARAM 없음
부류  몸통   진입점이 **아니다.** `firelane.ingest` 의 세 깃발이 이것을 부른다  (DECISIONS §398)
밖    **무엇을 고칠지는 안 판단한다.** 받아도 되는가는 `shardseal` 의
      `reseal_*` 가 들고, 여기는 **읽고 적고 사람에게 말하는** 일만 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from firelane.shardseal import (
    LEGACY_PRINTS,
    cfg_print,
    out_print,
    raw_print,
)


def reseal_out(records: list[dict], out_dir: Path) -> tuple[list[str], list[str]]:
    """봉인지가 있는 레코드의 `out` 칸만 지금 실물로 고친다. (고친 key, 못 고친 key).

    ★ 파이프라인 **하류가 ingest 산출물을 덧쓴 뒤**에만 부른다(terrain 의 z).
      raw · cfg · code 는 건드리지 않는다. 그 셋이 "무엇으로 만들었나" 의 증거이고,
      이 함수는 "하류가 덧쓴 결과가 지금 실물이다" 만 적는다.
    ★ 파일이 하나라도 없으면 그 레코드는 안 고친다 — 다음 실행에서 찢어져야 한다.
    """
    fixed, missing = [], []
    for r in records:
        s = r.get("seal") if isinstance(r, dict) else None
        if r.get("status") != "OK" or not isinstance(s, dict) or "out" not in s:
            continue
        now = out_print(out_dir, list(s["out"]))
        if now is None:
            missing.append(r["key"])
        elif now != s["out"]:
            s["out"] = now
            fixed.append(r["key"])
    return fixed, missing


def reseal_cfg(records: list[dict], cfg: dict) -> tuple[list[str], list[str]]:
    """`cfg` 칸**만** 지금 판의 지문으로 고쳐 적는다. (고친 key, 거절한 key).

    ── 왜 있나 (2026-10-11 · DECISIONS §460) ───────────────────
    `check()` 가 이미 「옛 판 지문이면 받고 새 판으로 고쳐 적는다」를 한다 —
    그러나 그것은 **ingest 가 도는 동안**이다. 지문 판이 바뀐 뒤 ingest 를 한
    번도 안 돌린 사이에 `sources.yaml` 이 바뀌면, 그 비교는 **옛 판 함수를 새
    설정에 대고** 하므로 안 맞고 전수가 찢어진다. 2026-10-10 에 계층 하나를
    선언했다가 되돌린 자리가 그것이다(§457-2).

    ★ 받는 규칙은 `check()` 와 **같은 하나**다 — 옛 판 지문 중 하나와 같아야
      받는다. 아무 지문이나 고쳐 적으면 그것은 재도장이 아니라 **봉인 해제**다.
    ★ `raw` · `out` · `code` 는 건드리지 않는다. 그 셋이 「무엇으로 만들었나」의
      증거이고, 이 함수가 적는 것은 「같은 설정을 지금 판으로 뜬 값」뿐이다.
    """
    fixed, refused = [], []
    for r in records:
        s = r.get("seal") if isinstance(r, dict) else None
        if r.get("status") != "OK" or not isinstance(s, dict) or "cfg" not in s:
            continue
        key = r["key"]
        now = cfg_print(cfg, key)
        if s["cfg"] == now:
            continue
        if any(s["cfg"] == f(cfg, key) for f in LEGACY_PRINTS):
            s["cfg"] = now
            fixed.append(key)
        else:
            refused.append(key)
    return fixed, refused


def reseal_code(records: list[dict], cfg: dict, out_dir: Path, code: str,
                paths_for) -> tuple[list[str], list[str]]:
    """`code` 칸**만** 지금 코드 지문으로 고친다. (고친 key, 못 고친 key).

    ── 왜 있나 (2026-09-23 · DECISIONS §224-2) ──────────────────────
    `code` 는 ingest 가 import 하는 firelane 모듈 전부의 로직 지문이다. 이미
    두 겹으로 좁혀 놨다 — 주석 · docstring 을 뺀 AST 로 재고(`logic_print`),
    봉인 로직 자신은 아예 뺀다(`NOT_PRODUCERS`, §165-8). 그런데도 **ingest 본체나
    `guards` 를 한 줄 고치면 65종이 전부 찢어진다.** 산출물을 한 바이트도 바꾸지
    않는 변경(안내 문구 · 종료코드 · 새 플래그)이어도 그렇다.

    이 8GB 기계에서 전량 재빌드는 `ngii_road` 에서 거의 반드시 죽는다(§165).
    즉 **ingest 를 고칠 수 없는 구조**였다. 도구를 못 고치면 결함도 못 고친다.
    좁히는 길(로직 지문 · 제외 목록)은 이미 다 썼으므로, 남은 길은 **사람이
    판단해서 받아주는 문**이다 — `cfg` 칸의 `cfg_print_legacy`, `out` 칸의
    `reseal_out` 과 같은 자리.

    ★ 공짜로 열어주지 않는다. 여기서 고치는 것은 **raw 와 out 이 둘 다 봉인과
      같은** 레코드뿐이다. 그 둘이 같다는 것은 「같은 입력으로 만든 같은
      산출물이 지금 디스크에 있다」 는 뜻이고, 그러면 코드가 무엇을 하든
      **이번 판정에 쓰인 결과는 그 산출물**이다.
    ★ 그래도 **판단은 사람이 한다.** 코드 변경이 산출물을 바꿀 수 있는
      것이었다면 out 이 이미 달라졌거나, 다음 전량에서 달라진다. 이 함수는
      「지금 디스크의 산출물이 봉인과 같다」 만 말한다 — `--stamp` 와 같은 급이다.
    ★ 옛 지문 → 새 지문을 **화면에 찍는다**(호출부). 대장 레코드에 칸을 더하지
      않는다 — 봉인지는 네 칸이고, 다섯 번째 칸은 다음 사람이 그것도 봉인의
      일부라고 읽는다. 무엇을 받아줬는지는 DECISIONS 가 든다.
    """
    fixed, skipped = [], []
    for r in records:
        s = r.get("seal") if isinstance(r, dict) else None
        if r.get("status") != "OK" or not isinstance(s, dict) \
                or not all(k in s for k in ("raw", "cfg", "code", "out")):
            continue
        key = r["key"]
        if s["code"] == code:
            continue                                   # 이미 같다
        try:
            hits = paths_for(key, cfg["datasets"][key])
        except Exception:
            skipped.append(key); continue
        if raw_print(hits) != s["raw"] or out_print(out_dir, list(s["out"])) != s["out"]:
            skipped.append(key); continue              # 입력이나 산출물이 달라졌다 — 다시 빌드해야 한다
        s["code"] = code
        fixed.append(key)
    return fixed, skipped



def reseal_out_cli(man_path: Path, out_dir: Path, manifest) -> int:
    """`ingest --reseal-out` 의 본문. 파이프라인이 terrain 뒤에 부른다."""
    if not man_path.exists():
        return 0
    doc = manifest.read(man_path)
    fixed, missing = reseal_out(doc.get("datasets", []), out_dir)
    wrote = manifest.write_stable(man_path, doc)
    print(f"샤드 봉인지 out 갱신 {len(fixed)}종"
          + (f" ({', '.join(fixed)})" if fixed else "")
          + (f" · 산출물 없음 {len(missing)}종: {', '.join(missing)}" if missing else "")
          + ("" if wrote else " · 대장 불변"))
    return 0


def reseal_code_cli(man_path: Path, cfg: dict, out_dir: Path, code: str,
                    paths_for, manifest) -> int:
    """`ingest --reseal-code` 의 본문. 대장을 읽고 고치고 적고 화면에 남긴다.

    ★ ingest 본체가 아니라 여기 산다. 봉인지를 아는 것은 이 모듈이고,
      ingest 는 그것을 부를 뿐이다 — 봉인 규칙이 두 파일에 흩어지지 않는다.
    """
    if not man_path.exists():
        print("★ _manifest.json 이 없다. 고칠 봉인지가 없다.")
        return 0
    doc = manifest.read(man_path)
    fixed, skipped = reseal_code(doc.get("datasets", []), cfg, out_dir, code, paths_for)
    wrote = manifest.write_stable(man_path, doc)
    print(f"샤드 봉인지 code 갱신 {len(fixed)}종 → {code}"
          + (f"\n  고침  {', '.join(fixed)}" if fixed else "")
          + (f"\n  거절  {len(skipped)}종 — raw 나 산출물이 봉인과 다르다: "
             f"{', '.join(skipped)}" if skipped else "")
          + ("" if wrote else "\n  대장 불변"))
    if skipped:
        print("  ★ 거절된 것은 **다시 빌드해야 한다.** 봉인은 그래서 있다.")
    if wrote:
        _relineage(man_path)
    return 0


def _relineage(man_path: Path) -> None:
    """재도장으로 바뀐 대장 해시를 **계보 기록에도** 반영한다.  (DECISIONS §267)

    ★ 2026-09-27 실측. 재도장은 대장을 고치는데 `_lineage.json` 의
      `ingest.outputs["data/processed/_manifest.json"]` 은 옛 해시를 든 채였다.
      그래서 바로 다음 `segments` 가 「입력이 바뀌었으니 상류부터 다시 돌려라」로
      막혔다 — **재도장이 재빌드를 부르는** 자리였고, 그것은 이 도구가 없애려던
      바로 그 비용이다(DECISIONS §224-2).

    ★ 갱신이 안전한 이유는 재도장의 정의다 — `code` 칸만 고치고 **산출물은 한
      바이트도 안 건드린다.** 거절된 종은 애초에 안 고쳐지므로 여기 안 온다.
      바꾸는 것은 대장 한 칸이고, 나머지 계보는 그대로 둔다.
    """
    from firelane import lineage

    lin = man_path.parent / lineage.LINEAGE
    if not lin.exists():
        return                       # 계보가 없으면 다음 실행이 새로 적는다
    doc = json.loads(lin.read_text(encoding="utf-8"))
    key = f"data/processed/{man_path.name}"
    for step in doc.values():
        out = (step or {}).get("outputs") or {}
        if key in out:
            out[key] = lineage._manifest_digest(man_path)
    lin.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  계보 기록의 `{key}` 도 같이 갱신했다 — 재도장이 재빌드를 안 부르게")




def reseal_cfg_cli(man_path: Path, cfg: dict, manifest) -> int:
    """`ingest --reseal-cfg` 의 본문. 지문 **판**이 바뀐 뒤 한 번 부른다.

    ★ 재빌드가 아니다. 고치는 것은 대장의 `cfg` 칸 하나이고, 받는 규칙은
      `check()` 와 같다 — 옛 판 지문과 같을 때만 받는다(DECISIONS §460).
    """
    if not man_path.exists():
        print("★ _manifest.json 이 없다. 고칠 봉인지가 없다.")
        return 0
    doc = manifest.read(man_path)
    fixed, refused = reseal_cfg(doc.get("datasets", []), cfg)
    wrote = manifest.write_stable(man_path, doc)
    print(f"샤드 봉인지 cfg 갱신 {len(fixed)}종"
          + (f"\n  고침  {', '.join(fixed)}" if fixed else "")
          + (f"\n  거절  {len(refused)}종 — 옛 판 지문도 아니다(설정이 실제로 바뀌었다): "
             f"{', '.join(refused)}" if refused else "")
          + ("" if wrote else "\n  대장 불변"))
    if refused:
        print("  ★ 거절된 것은 **다시 빌드해야 한다.** 봉인은 그래서 있다.")
    if wrote:
        _relineage(man_path)
    return 0
