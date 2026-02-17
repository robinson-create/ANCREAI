/**
 * CopilotKit Runtime - Minimal self-hosted runtime for Ancre.
 *
 * This Express server hosts the CopilotKit runtime which orchestrates
 * LLM calls and tool/action execution for the CopilotKit frontend.
 *
 * Architecture decision:
 *   CopilotKit requires a Node.js runtime to handle its protocol.
 *   We keep this as a thin orchestrator - heavy business logic stays
 *   in our FastAPI backend, invoked as "remote actions" by the runtime.
 */

import express from "express";
import cors from "cors";
import {
  CopilotRuntime,
  OpenAIAdapter,
  copilotRuntimeNodeHttpEndpoint,
} from "@copilotkit/runtime";

const app = express();
const PORT = parseInt(process.env.COPILOT_RUNTIME_PORT || "4000", 10);

app.use(cors());

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "healthy", service: "copilot-runtime" });
});

// CopilotKit runtime - create once at startup
const runtime = new CopilotRuntime({
  remoteActions: [
    {
      url: process.env.BACKEND_ACTIONS_URL || "http://localhost:8000/api/v1/copilotkit/actions",
    },
  ],
});

const copilotHandler = copilotRuntimeNodeHttpEndpoint({
  endpoint: "/copilotkit",
  runtime,
  serviceAdapter: new OpenAIAdapter({
    model: process.env.COPILOT_LLM_MODEL || "gpt-4o-mini",
  }),
});

// Mount at root so the handler sees the full /copilotkit path
app.use(copilotHandler);

app.listen(PORT, () => {
  console.log(`🤖 CopilotKit Runtime running on http://localhost:${PORT}`);
  console.log(`   Runtime endpoint: http://localhost:${PORT}/copilotkit`);
});
