/**
 * Slide Export Service — Express microservice.
 * POST /export      → converts resolved layout JSON → PPTX, uploads to S3.
 * POST /export-pdf  → React SSR → Playwright PDF, uploads to S3.
 * GET  /health      → liveness probe + renderer version.
 */

import express from "express";
import { convertToBuffer } from "./converter.js";
import { uploadToS3 } from "./s3.js";
import { renderPdf, type PdfExportRequest } from "./pdf-renderer.js";
import { shutdown as shutdownBrowser } from "./browser-pool.js";
import type { ExportRequest, ExportResponse } from "./types.js";

const app = express();
app.use(express.json({ limit: "10mb" }));

const PORT = parseInt(process.env.PORT ?? "4100", 10);
const SUPPORTED_SCHEMA_VERSION = 1;
const RENDERER_VERSION = "1.1.0";

/** Health check + renderer version. */
app.get("/health", (_req, res) => {
  res.json({ status: "ok", renderer_version: RENDERER_VERSION });
});

/** PPTX export endpoint (existing). */
app.post("/export", async (req, res) => {
  const start = Date.now();

  try {
    const body = req.body as ExportRequest;

    if (body.schema_version !== SUPPORTED_SCHEMA_VERSION) {
      res.status(400).json({
        error: `Unsupported schema_version: ${body.schema_version}. Expected ${SUPPORTED_SCHEMA_VERSION}.`,
      });
      return;
    }

    if (!body.slides || body.slides.length === 0) {
      res.status(400).json({ error: "No slides provided." });
      return;
    }

    const buffer = await convertToBuffer(body);

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const s3Key = `exports/${body.tenant_id}/${body.presentation_id}/${body.export_id}_${timestamp}.pptx`;

    const uploadResult = await uploadToS3(buffer, s3Key);

    const duration = Date.now() - start;

    const response: ExportResponse = {
      s3_key: uploadResult.s3_key,
      file_size: uploadResult.file_size,
      duration_ms: duration,
    };

    console.log(
      `[PPTX] Export ${body.export_id}: ${body.slides.length} slides, ${uploadResult.file_size} bytes, ${duration}ms`
    );

    res.json(response);
  } catch (err: any) {
    const duration = Date.now() - start;
    console.error(`[PPTX] Export failed after ${duration}ms:`, err);
    res.status(500).json({
      error: err.message ?? "Internal export error",
    });
  }
});

/** PDF export endpoint (new — React SSR + Playwright). */
app.post("/export-pdf", async (req, res) => {
  const start = Date.now();

  try {
    const body = req.body as PdfExportRequest;

    if (!body.slides || body.slides.length === 0) {
      res.status(400).json({ error: "No slides provided." });
      return;
    }

    if (!body.theme) {
      res.status(400).json({ error: "No theme provided." });
      return;
    }

    const pdfBuffer = await renderPdf(body.slides, body.theme);

    const s3Key = `exports/${body.tenant_id}/${body.presentation_id}/${body.export_id}.pdf`;

    const uploadResult = await uploadToS3(pdfBuffer, s3Key);

    const duration = Date.now() - start;

    console.log(
      `[PDF] Export ${body.export_id}: ${body.slides.length} slides, ${uploadResult.file_size} bytes, ${duration}ms`
    );

    res.json({
      s3_key: uploadResult.s3_key,
      file_size: uploadResult.file_size,
      duration_ms: duration,
      renderer_version: RENDERER_VERSION,
    });
  } catch (err: any) {
    const duration = Date.now() - start;
    console.error(`[PDF] Export failed after ${duration}ms:`, err);
    res.status(500).json({
      error: err.message ?? "Internal PDF export error",
    });
  }
});

// Graceful shutdown
async function gracefulShutdown() {
  console.log("[shutdown] Closing browser and exiting...");
  await shutdownBrowser();
  process.exit(0);
}

process.on("SIGTERM", gracefulShutdown);
process.on("SIGINT", gracefulShutdown);

app.listen(PORT, () => {
  console.log(`slide-export-service listening on port ${PORT} (renderer v${RENDERER_VERSION})`);
});
