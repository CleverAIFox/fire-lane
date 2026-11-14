#!/usr/bin/env python3
"""
firstscreen.py — **첫 화면이 받는 gzip 바이트** 래칫.  (DECISIONS §787-H · PLAN #245)

    uv run python tools/firstscreen.py              두 화면을 재서 선언과 대조(늘면 종료 1)
    uv run python tools/firstscreen.py --report     선언 없이 숫자만(요청별 상위 · 화면별 합)
    uv run python tools/firstscreen.py --lte        ★ 10Mbps · RTT 70ms 로 느리게 서빙하고 「지도 원천이 도착한 시각」도 낸다
    uv run python tools/firstscreen.py --selftest

── 왜 있나 ────────────────────────────────────────────────────
현장 로딩의 진짜 축은 `web/data` 총량이 아니다. 총량(37MB)의 5.6% 만 첫 화면이 받는다(정사영상은 보이는 타일만 · DECISIONS §787-C).
총량 래칫(`expectation.WEB_*_BYTES`)은 저장소 비만을 지키고, **이 래칫이 현장 로딩을 지킨다** — 이것이 늘면 울어야 한다.

── 어떻게 재나 ────────────────────────────────────────────────
Pages 모양 로컬 서버(텍스트 gzip 6 · `no-store`)를 이 프로세스 안에 세우고, 헤드리스 크로미움(`firstscreen_drive.cjs` · 소프트웨어 GL · 서비스 워커
차단 = 콜드 캐시)이 화면을 열고, **서버가 응답마다 (경로 · 선 바이트 · 시각)을 기록한다.** 브라우저 쪽에서 재면 지도 워커가 내는 GeoJSON 요청이 안 보인다(처음
시도가 건물을 못 찍었다). 화면은 둘 — 내비(`?dev=1`) · 관제(`?view=ops`).

IN    `web/navi/dist`(빌드본) · `web/data` · `web/navi/node_modules`(playwright · 헤드리스 크로미움)
OUT   표준출력 · 종료 코드(0 통과 · 1 래칫 초과 · 2 못 쟀다)
PARAM `FIRST_SCREEN_KB` — **타일을 뺀** gzip 합(KB). 사유는 아래
밖    **렌더링 시간을 안 잰다** — 소프트웨어 GL 이라 실기 GPU 를 대신하지 못한다(DECISIONS §787-D · PLAN #246 이 따로 잰다).
      **서비스 워커가 든 2회차 방문을 안 잰다**(콜드 캐시만). **Pages 가 gzip 을 주는지는 모른다**(가정 — 배포본에서 확인할 일 · PLAN #245 ④).
      **타일(지형 · 정사영상)은 래칫에서 뺀다** — 어느 타일을 받는지가 렌더 타이밍에 따라 달라 실행마다 ±20KB 흔들린다(238 · 221KB 실측). 보고만 한다.
"""
from __future__ import annotations

import argparse
import gzip
import json
import mimetypes
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DIST = WEB / "navi" / "dist"
DRIVER = ROOT / "tools" / "firstscreen_drive.cjs"

VIEWS = {"navi": "/fire-lane/navi/?dev=1", "ops": "/fire-lane/navi/?view=ops"}

#: 래칫(KB · 타일을 뺀 gzip 합 · **내려가는 쪽으로만**). 2026-11-14 (DECISIONS §787-H) — 건물 4,296면 전부를 얹은 판의 실측을 올림했다.
#: ★ 올리는 것은 사람이 하고 **무엇을 사서 올렸는지**를 §787 에 적는다(`naviweight.py` 의 진입 청크 래칫과 같은 규약).
#: ★ 내려간 것은 받아 적는다 — 느슨한 채로 두면 이 수는 상한이 아니라 지난 기록이다.
FIRST_SCREEN_KB = {"navi": 1950, "ops": 1980}   # 실측 1,939 · 1,969(3회 같음)를 10KB 로 올림

#: 지도 원천 — LTE 흉내에서 「이 다섯이 도착한 시각」을 낸다.
SOURCES = ("buildings", "segments", "road_area", "sidewalk", "poi")
TILE = re.compile(r"/data/(terrain|ortho)/")
TEXT = {".json", ".geojson", ".js", ".css", ".html", ".svg", ".webmanifest", ".mjs"}
mimetypes.add_type("application/json", ".geojson")


class Server:
    """Pages 모양 서버. 응답마다 기록한다. `bw`(바이트/초) · `rtt`(초)가 0 이면 안 늦춘다."""

    def __init__(self, bw: float = 0.0, rtt: float = 0.0):
        self.bw, self.rtt = bw, rtt
        self.log: list[dict] = []
        self.t0 = time.time()
        self._free = 0.0
        self._lock = threading.Lock()
        self._gz: dict[Path, bytes] = {}
        outer = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                outer._get(self)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def _pace(self, n: int) -> None:
        if not self.bw:
            return
        with self._lock:
            end = max(time.time(), self._free) + n / self.bw
            self._free = end
        d = end - time.time()
        if d > 0:
            time.sleep(d)

    def _get(self, h: BaseHTTPRequestHandler) -> None:
        p = h.path.split("?")[0]
        if p == "/__log":
            return self._send(h, json.dumps(self.log).encode(), "application/json", None, False)
        if p.startswith("/fire-lane/navi/"):
            f = DIST / p[len("/fire-lane/navi/"):]
        elif p.startswith("/fire-lane/"):
            f = WEB / p[len("/fire-lane/"):]
        else:
            f = WEB / p.lstrip("/")
        if f.is_dir():
            f = f / "index.html"
        if not f.is_file():
            return self._send(h, b"", "text/plain", None, False, 404)
        b, enc = f.read_bytes(), None
        if f.suffix in TEXT and "gzip" in h.headers.get("Accept-Encoding", ""):
            b = self._gz.setdefault(f, gzip.compress(b, 6))
            enc = "gzip"
        self._send(h, b, mimetypes.guess_type(str(f))[0] or "application/octet-stream", enc, True, 200, p)

    def _send(self, h, b, ct, enc, track, code=200, p=None):
        t_in = time.time() - self.t0
        if track and self.rtt:
            time.sleep(self.rtt)
        h.send_response(code)
        h.send_header("Content-Type", ct)
        if enc:
            h.send_header("Content-Encoding", enc)
        h.send_header("Content-Length", str(len(b)))
        h.send_header("Cache-Control", "no-store")
        h.end_headers()
        try:
            for i in range(0, len(b), 16384):
                c = b[i:i + 16384]
                if track:
                    self._pace(len(c))
                h.wfile.write(c)
        except (BrokenPipeError, ConnectionResetError):
            pass
        if track:
            self.log.append({"p": p, "wire": len(b), "t0": round(t_in, 3), "t1": round(time.time() - self.t0, 3)})

    def reset(self) -> None:
        self.log.clear()
        self.t0 = time.time()
        self._free = 0.0


def summarize(log: list[dict]) -> dict:
    """응답 기록 → 화면 한 장의 합. 순수 함수 — 시험이 합성 기록으로 민다."""
    def kb(rows) -> float:
        return sum(r["wire"] for r in rows) / 1024

    tiles = [r for r in log if TILE.search(r["p"])]
    rest = [r for r in log if not TILE.search(r["p"])]
    src = [r for r in log if any(r["p"].endswith(f"/data/{s}.geojson") for s in SOURCES)]
    return {
        "n": len(log), "total_kb": kb(log), "gated_kb": kb(rest), "tiles_kb": kb(tiles),
        "js_css_kb": kb([r for r in rest if re.search(r"\.(js|css)$", r["p"])]),
        "data_kb": kb([r for r in rest if re.search(r"/data/[^/]+\.(geo)?json$", r["p"])]),
        "buildings_kb": kb([r for r in log if r["p"].endswith("/data/buildings.geojson")]),
        "sources_done_s": max((r["t1"] for r in src), default=None),
        "top": sorted(log, key=lambda r: -r["wire"])[:8],
    }


def verdict(view: str, got_kb: float, declared: dict[str, int] | None = None) -> list[str]:
    """래칫 대조. **선언을 넘을 때만** 운다. 선언이 0(미선언)이면 그것도 운다 — 안 적은 래칫은 래칫이 아니다."""
    lim = (declared or FIRST_SCREEN_KB).get(view, 0)
    if lim <= 0:
        return [f"첫 화면 래칫 `{view}` 가 선언되지 않았다(FIRST_SCREEN_KB)"]
    if got_kb > lim:
        return [f"첫 화면({view}) {got_kb:,.0f}KB(gzip · 타일 제외) — 래칫 {lim:,}KB 를 넘었다(+{got_kb - lim:,.0f}KB). "
                "무엇이 늘었는지 `--report` 로 보고, 사서 올리는 것이면 DECISIONS §787 에 적고 선언을 올려라"]
    return []


def measure(srv: Server, view: str) -> dict:
    srv.reset()
    r = subprocess.run(["node", str(DRIVER), f"http://127.0.0.1:{srv.port}", VIEWS[view]],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"{view}: 브라우저가 화면을 못 띄웠다(종료 {r.returncode}) {r.stderr.strip()[:300]}")
    return summarize(list(srv.log))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="첫 화면 gzip 전송량 래칫")
    ap.add_argument("--report", action="store_true", help="선언 대조 없이 숫자만")
    ap.add_argument("--lte", action="store_true", help="10Mbps · RTT 70ms 로 서빙(원천 도착 시각을 낸다)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (DIST / "index.html").is_file():
        print("첫 화면: web/navi/dist 가 없다 — `cd web/navi && npm run build` 뒤에 다시. 못 쟀으므로 통과가 아니다.")
        return 2
    srv = Server(bw=10e6 / 8 if a.lte else 0.0, rtt=0.07 if a.lte else 0.0)
    bad: list[str] = []
    try:
        for view in VIEWS:
            s = measure(srv, view)
            line = (f"  {view:5s} 총 {s['total_kb']:,.0f}KB · 래칫 몫(타일 뺀) {s['gated_kb']:,.0f}KB · 타일 {s['tiles_kb']:,.0f}KB · "
                    f"JS/CSS {s['js_css_kb']:,.0f} · data {s['data_kb']:,.0f} · 건물 {s['buildings_kb']:,.0f}KB · 요청 {s['n']}")
            if s["sources_done_s"] is not None and a.lte:
                line += f" · 원천 도착 {s['sources_done_s']:.1f}s"
            print(line)
            if a.report:
                for r in s["top"]:
                    print(f"        {r['wire'] / 1024:7.0f}KB  {r['p'].replace('/fire-lane/', '')}")
            else:
                bad += verdict(view, s["gated_kb"])
    except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"첫 화면: 못 쟀다 — {e}")
        return 2
    finally:
        srv.httpd.shutdown()
    if bad:
        print("\033[31m첫 화면 래칫 초과\033[0m")
        print("\n".join("  ✗ " + b for b in bad))
        return 1
    if not a.report:
        print("첫 화면 래칫 OK")
    return 0


def selftest() -> int:
    log = [
        {"p": "/fire-lane/data/buildings.geojson", "wire": 2048, "t0": 0, "t1": 1.0},
        {"p": "/fire-lane/data/terrain/15/1/1.png", "wire": 1024, "t0": 0, "t1": 2.0},
        {"p": "/fire-lane/navi/assets/a.js", "wire": 1024, "t0": 0, "t1": 0.5},
    ]
    s = summarize(log)
    ok = (abs(s["total_kb"] - 4.0) < 1e-9 and abs(s["gated_kb"] - 3.0) < 1e-9 and abs(s["tiles_kb"] - 1.0) < 1e-9
          and s["sources_done_s"] == 1.0)
    d = {"navi": 100}
    ok = ok and verdict("navi", 100, d) == [] and len(verdict("navi", 100.5, d)) == 1 and len(verdict("ops", 1, d)) == 1
    print("selftest", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
