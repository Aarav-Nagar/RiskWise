const fs = require("fs");
const http = require("http");
const path = require("path");

const args = parseArgs(process.argv.slice(2));
const port = Number(args.port || process.env.RISKWISE_QA_PORT || 8099);
const root = path.resolve(process.cwd(), args.dir || "dist-web");

if (!fs.existsSync(path.join(root, "index.html"))) {
  console.error(`Missing exported app at ${root}. Run npm run export:web before smoke tests.`);
  process.exit(1);
}

const server = http.createServer((request, response) => {
  const requestUrl = new URL(request.url || "/", `http://127.0.0.1:${port}`);
  const cleanPath = decodeURIComponent(requestUrl.pathname).replace(/^\/+/, "");
  const candidate = path.resolve(root, cleanPath || "index.html");
  const safeCandidate = candidate.startsWith(root) ? candidate : path.join(root, "index.html");
  const target = fs.existsSync(safeCandidate) && fs.statSync(safeCandidate).isFile()
    ? safeCandidate
    : path.join(root, "index.html");

  fs.readFile(target, (error, content) => {
    if (error) {
      response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("RiskWise QA server could not read the exported file.");
      return;
    }
    response.writeHead(200, {
      "Content-Type": contentType(target),
      "Cache-Control": "no-store",
    });
    response.end(content);
  });
});

server.listen(port, "127.0.0.1", () => {
  console.log(`RiskWise QA static server ready at http://127.0.0.1:${port}`);
});

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token.startsWith("--")) {
      parsed[token.slice(2)] = argv[index + 1];
      index += 1;
    }
  }
  return parsed;
}

function contentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
    ".ttf": "font/ttf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
  }[ext] || "application/octet-stream";
}
