import { file } from "bun";
import path from "path";
import fs from "fs";

const DIST_DIR = path.resolve(import.meta.dir, "dist");
const API_TARGET = process.env.API_PROXY_TARGET || "http://127.0.0.1:8105";
const PORT = Number(process.env.PORT) || 5176;

Bun.serve({
  port: PORT,
  hostname: "0.0.0.0",
  async fetch(req) {
    const url = new URL(req.url);

    // Proxy /api/ to backend FastAPI
    if (url.pathname.startsWith("/api/")) {
      const backendPath = url.pathname.replace(/^\/api/, "") + url.search;
      const backendUrl = `${API_TARGET}${backendPath}`;
      try {
        return await fetch(backendUrl, {
          method: req.method,
          headers: req.headers,
          body: req.body,
        });
      } catch (err) {
        return new Response(JSON.stringify({ error: "Backend proxy error", details: String(err) }), {
          status: 502,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    // 1. Exact /game shell check precedes any existing dist/game snapshot folder so 503 cannot bypass
    if (url.pathname === "/game" || url.pathname === "/game/") {
      const gameShell = path.join(DIST_DIR, "game-shell.html");
      if (fs.existsSync(gameShell)) {
        return new Response(file(gameShell), {
          headers: { "Content-Type": "text/html; charset=utf-8", "X-Robots-Tag": "noindex, follow" },
        });
      }
      return new Response("Game shell unavailable", { status: 503 });
    }

    // 2. Root / serves bare SPA shell for this local preview entrypoint (never game-shell from dist/index.html)
    if (url.pathname === "/" || url.pathname === "") {
      const spaShell = path.join(DIST_DIR, "spa-shell.html");
      if (fs.existsSync(spaShell)) {
        return new Response(file(spaShell), {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        });
      }
      return new Response("SPA shell unavailable", { status: 503 });
    }

    // 3. Static files from dist/ (including prerendered HTML snapshots)
    const rawPath = url.pathname.slice(1);
    // nosemgrep: javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal
    const filePath = path.resolve(DIST_DIR, rawPath);
    if (filePath !== DIST_DIR && !filePath.startsWith(DIST_DIR + path.sep)) {
      return new Response("Forbidden", { status: 403 });
    }

    // If directory, serve directory/index.html
    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      // nosemgrep: javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal
      const indexPath = path.resolve(filePath, "index.html");
      if (indexPath.startsWith(DIST_DIR + path.sep) && fs.existsSync(indexPath)) {
        return new Response(file(indexPath));
      }
    }

    // Direct file (e.g. assets/index-xxx.js, favicon, etc.)
    if (fs.existsSync(filePath) && !fs.statSync(filePath).isDirectory()) {
      return new Response(file(filePath));
    }

    // 4. SPA fallback: other SPA/private routes use bare spa-shell (503 if missing, no index.html shim)
    const spaShell = path.join(DIST_DIR, "spa-shell.html");
    if (fs.existsSync(spaShell)) {
      return new Response(file(spaShell), {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    return new Response("SPA shell unavailable", { status: 503 });
  },
});

console.log(`Countrydle local server running at http://localhost:${PORT}/ (Proxying API to ${API_TARGET})`);
