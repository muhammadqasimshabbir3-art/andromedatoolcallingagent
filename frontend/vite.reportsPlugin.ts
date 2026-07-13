import fs from "node:fs";
import path from "node:path";
import type { Connect, Plugin } from "vite";

/** Serve PDFs from the monorepo ./reports folder at /generated-reports/<file>.pdf */
export function serveReportsPlugin(reportsDir: string): Plugin {
  const handler: Connect.NextHandleFunction = (req, res, next) => {
    const url = req.url ?? "";
    if (!url.startsWith("/generated-reports/")) {
      next();
      return;
    }

    const rawName = decodeURIComponent(url.slice("/generated-reports/".length).split("?")[0] ?? "");
    const name = path.basename(rawName);
    if (!name || name !== rawName || !name.toLowerCase().endsWith(".pdf") || name.includes("..")) {
      res.statusCode = 400;
      res.end("Invalid PDF name");
      return;
    }

    const filePath = path.join(reportsDir, name);
    if (!fs.existsSync(filePath)) {
      res.statusCode = 404;
      res.end("PDF not found");
      return;
    }

    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename="${name}"`);
    fs.createReadStream(filePath).pipe(res);
  };

  return {
    name: "serve-andromeda-reports",
    configureServer(server) {
      server.middlewares.use(handler);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler);
    },
  };
}
