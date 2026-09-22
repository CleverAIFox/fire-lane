import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

// 저장소 이름이 fire-lane 이 아니면 VITE_BASE 로 넘긴다.
//   VITE_BASE=/fire-lane-dev/navi/ npm run build
const base = process.env.VITE_BASE ?? "/fire-lane/navi/";

/**
 * 개발 서버가 상위 `web/data` 를 내주게 한다.
 *
 * ── 왜 필요한가 ────────────────────────────────────────────────
 * 앱은 `../data/` 를 읽는다. 배포에서는 `web/` 전체가 올라가므로
 * `/<repo>/navi/` 의 `../data/` 가 곧 `/<repo>/data/` 다 — 맞는다.
 *
 * 그런데 dev 서버는 루트가 `web/navi` 다. 그 위로는 안 내준다.
 * `server.fs.allow` 는 `/@fs/` 경로를 허용할 뿐이고 평범한 URL 은
 * 여전히 404 다. 그래서 미들웨어로 직접 잇는다.
 *
 * ★ **사본을 만들지 않는다.** `public/` 에 복사하거나 심링크를 걸면
 *   파이프라인이 갱신해도 앱이 옛 판정을 본다. 29MB 를 두 벌 두는
 *   문제이기도 하다. 원본을 그 자리에서 읽는다.
 *
 * ★ 캐시 헤더를 안 준다. `tools/serve.py` 가 캐시 없는 개발 서버를
 *   따로 만든 이유와 같다 — 개발 중에 옛 판정이 화면에 남으면
 *   그것을 버그로 착각하고 하루를 태운다.
 */
function serveWebData(): Plugin {
  const DATA = path.resolve(__dirname, "..", "data");
  const prefix = base.replace(/navi\/$/, "data/");   // /fire-lane/data/

  const MIME: Record<string, string> = {
    ".json": "application/json; charset=utf-8",
    ".geojson": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".js": "text/javascript; charset=utf-8",
  };

  return {
    name: "serve-web-data",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? "").split("?")[0];
        if (!url.startsWith(prefix)) return next();

        // 경로 탈출 차단. `..` 로 저장소 밖을 읽지 못하게 한다.
        const rel = decodeURIComponent(url.slice(prefix.length));
        const file = path.resolve(DATA, rel);
        if (!file.startsWith(DATA)) {
          res.statusCode = 403;
          return res.end("forbidden");
        }
        if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) return next();

        res.setHeader("Content-Type", MIME[path.extname(file)] ?? "application/octet-stream");
        res.setHeader("Cache-Control", "no-store");
        fs.createReadStream(file).pipe(res);
      });
      // 무엇을 잇고 있는지 시작할 때 한 번 알린다. 조용히 404 나는 것보다 낫다.
      const ok = fs.existsSync(path.join(DATA, "navi_graph.json"));
      server.config.logger.info(
        `  ➜  data:    ${prefix} → ${DATA}` +
        (ok ? "" : "\n  ★ navi_graph.json 이 없다: uv run python -m firelane.publish_navi"),
      );
    },
  };
}

/**
 * Mapbox 토큰 한 자리.  (DECISIONS §214-6)
 *
 * ★ 2026-09-22. 종전에는 `web/navi/.env.local` 의 `VITE_MAPBOX_TOKEN` 만 읽었다.
 *   VWorld 키는 저장소 루트 `.env` 에 있고 `tools/matchcheck.py` 도 루트 `.env`
 *   의 `MAPBOX_TOKEN` 을 읽는데, 내비만 다른 파일 · 다른 이름을 봤다 — 토큰이
 *   두 벌로 갈리고 한쪽만 재발급되는 사고의 모양이다.
 *   우선순위(먼저 것이 이긴다):
 *     1. 셸/CI 환경 `VITE_MAPBOX_TOKEN`  — build-navi 액션이 시크릿으로 준다
 *     2. `web/navi/.env.local` 의 `VITE_MAPBOX_TOKEN`  — 옛 자리. 호환으로 둔다
 *     3. 저장소 루트 `.env` 의 `MAPBOX_TOKEN`  — **정본**
 * ★ 값을 로그에 찍지 않는다. 있다/없다만 안다.
 */
function mapboxToken(mode: string): string {
  const navi = loadEnv(mode, __dirname, "VITE_");                 // 1 · 2
  const root = loadEnv(mode, path.resolve(__dirname, "..", ".."), "");
  return navi.VITE_MAPBOX_TOKEN || root.VITE_MAPBOX_TOKEN || root.MAPBOX_TOKEN || "";
}

export default defineConfig(({ mode }) => ({
  base,
  plugins: [react(), serveWebData()],
  define: { "import.meta.env.VITE_MAPBOX_TOKEN": JSON.stringify(mapboxToken(mode)) },
  build: { outDir: "dist", emptyOutDir: true },
}));
