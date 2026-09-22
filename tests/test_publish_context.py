#!/usr/bin/env python3
"""
test_publish_context.py — 받아 두고 안 쓰던 데이터가 **화면까지 가는가.**  (DECISIONS §216-3)

2026-09-22. 72종 중 판정에 11종, 좌표까지 있는데 아무도 안 읽는 것이 여럿이었다. 발행물이
빠지거나 비어도 부팅 · 타입 · golden 은 초록이다 — 여기서 센다. 그리고 배포에 **안 실을** 것을
배포 준비가 실제로 빼는지 본다(§216-5).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"


def _fc(name: str) -> dict:
    return json.loads((WEB / name).read_text(encoding="utf-8"))


def test_context_carries_all_four_kinds():
    fc = _fc("context.geojson")
    kinds = {f["properties"]["kind"] for f in fc["features"]}
    assert kinds == {"speedbump", "speedcam", "child_zone", "senior_zone"}, kinds
    assert all(f["geometry"]["type"] == "Point" for f in fc["features"]), "보호구역을 구역으로 지어냈다 — 자료는 시설 점이다"


def test_history_response_times_are_sane():
    fc = _fc("history.geojson")
    rs = [f["properties"]["resp_s"] for f in fc["features"] if f["properties"]["resp_s"] is not None]
    assert len(rs) >= 100, f"도착 시간이 {len(rs)}건 — 시각 칸 파싱이 죽었다"
    assert all(0 < r <= 7200 for r in rs), "음수 · 2시간 초과가 남았다 — 기록 오류를 안 거른다"
    s = fc["summary"]
    assert s["resp_n"] == len(rs) and s["resp_median_s"] is not None
    assert s["fire_donggu"]["n"] > 0, "화재 요약(좌표 없음)이 비었다"


def test_navi_graph_parking_is_road_level_and_optional():
    g = _fc("navi_graph.json")
    park = [e.get("park", 0) for e in g["edges"]]
    assert sum(1 for p in park if p) >= 100, "단속 이력이 거의 안 붙었다 — 도로명 대조가 죽었다"
    by_road: dict[str, set[int]] = {}
    for e in g["edges"]:
        if e.get("road_name"):
            by_road.setdefault(e["road_name"], set()).add(e.get("park", 0))
    assert all(len(v) == 1 for v in by_road.values()), "같은 도로명 구간이 다른 수를 받았다 — 도로 단위가 아니다"


def test_publish_web_calls_publish_context():
    src = (ROOT / "src" / "firelane" / "publish_web.py").read_text(encoding="utf-8")
    assert "_ctx.main()" in src, "publish_web 이 publish_context 를 안 부른다 — 파이프라인이 다시 안 낸다"


def test_stage_pages_deploy_refuses_outside_ci():
    """★ 로컬에서 템플릿(playbook.html)을 지우면 렌더러가 협업 방침을 못 만든다."""
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
    r = subprocess.run([sys.executable, str(ROOT / "tools/stage_pages.py"), "--deploy"],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode != 0 and "CI 전용" in (r.stdout + r.stderr), r.stdout + r.stderr
    assert (ROOT / "web" / "playbook.html").exists(), "로컬 템플릿이 지워졌다"


def test_deploy_uses_drop_list():
    y = (ROOT / ".github/actions/stage-site/action.yml").read_text(encoding="utf-8")
    assert "stage_pages.py --deploy" in y, "배포가 템플릿을 안 뺀다 — playbook.html 이 또 배포된다"
    d = (ROOT / ".github/workflows/_deploy.yml").read_text(encoding="utf-8")
    assert d.count("./.github/actions/stage-site") == 2, "배포와 시운전이 같은 본문을 안 쓴다(§217-5)"
    dry = (ROOT / ".github/workflows/deploy-dry.yml").read_text(encoding="utf-8")
    assert "pull_request" in dry and "dry-run: true" in dry, "PR 시운전이 없다 — 배포 본문이 main 전에 안 돈다(W3-15)"


def test_parking_place_text_is_split_by_token():
    """독립 검토 2026-09-22 — 공백을 지우고 뽑아 「동명동 동계천로」 가 한 덩어리가 됐고 41,929행을 놓쳤다."""
    from firelane.publish_navi import _road_of
    have = {"동계천로", "구성로", "구성로204번길", "서석로", "제봉로140번길"}
    assert _road_of("동명동 동계천로", have) == "동계천로"
    assert _road_of("대인동 구성로204번길", have) == "구성로204번길", "긴 이름을 짧은 이름으로 셌다"
    assert _road_of("서석로 7(웨딩의거리)", have) == "서석로"
    assert _road_of("동명동 35-2", have) is None
