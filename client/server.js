import { file } from "bun";
import path from "path";
import fs from "fs";

const DIST_DIR = path.join(import.meta.dir, "dist");
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

    // Static files from dist/ (including prerendered HTML snapshots)
    const rawPath = url.pathname.slice(1);
    let filePath = path.join(DIST_DIR, rawPath);

    // If directory, serve directory/index.html
    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      const indexPath = path.join(filePath, "index.html");
      if (fs.existsSync(indexPath)) {
        return new Response(file(indexPath));
      }
    }

    // Direct file (e.g. assets/index-xxx.js, favicon, etc.)
    if (fs.existsSync(filePath) && !fs.statSync(filePath).isDirectory()) {
      return new Response(file(filePath));
    }

    // SPA fallback
    const fallbackPath = path.join(DIST_DIR, "index.html");
    if (fs.existsSync(fallbackPath)) {
      return new Response(file(fallbackPath));
    }

    return new Response("Not Found", { status: 404 });
  },
});

console.log(`Countrydle local server running at http://localhost:${PORT}/ (Proxying API to ${API_TARGET})`);
