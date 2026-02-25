/**
 * PPTX Exporter — Express microservice.
 * POST /export  → converts resolved layout JSON → PPTX, uploads to S3.
 * GET  /health  → liveness probe.
 */

import express from "express";
import { convertToBuffer } from "./converter";
import { uploadToS3 } from "./s3";
import type { ExportRequest, ExportResponse } from "./types";

const app = express();
app.use(express.json({ limit: "10mb" }));

const PORT = parseInt(process.env.PORT ?? "4100", 10);
const SUPPORTED_SCHEMA_VERSION = 1;

/** Health check. */
app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

/** Export endpoint. */
app.post("/export", async (req, res) => {
  const start = Date.now();

  try {
    const body = req.body as ExportRequest;

    // Validate schema version
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

    // Convert to PPTX buffer
    const buffer = await convertToBuffer(body);

    // Build S3 key
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const s3Key = `exports/${body.tenant_id}/${body.presentation_id}/${body.export_id}_${timestamp}.pptx`;

    // Upload to S3
    const uploadResult = await uploadToS3(buffer, s3Key);

    const duration = Date.now() - start;

    const response: ExportResponse = {
      s3_key: uploadResult.s3_key,
      file_size: uploadResult.file_size,
      duration_ms: duration,
    };

    console.log(
      `Export ${body.export_id}: ${body.slides.length} slides, ${uploadResult.file_size} bytes, ${duration}ms`,
    );

    res.json(response);
  } catch (err: any) {
    const duration = Date.now() - start;
    console.error(`Export failed after ${duration}ms:`, err);
    res.status(500).json({
      error: err.message ?? "Internal export error",
    });
  }
});

app.listen(PORT, () => {
  console.log(`pptx-exporter listening on port ${PORT}`);
});
