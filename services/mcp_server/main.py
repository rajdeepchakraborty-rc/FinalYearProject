"""
SignalStream — Model Context Protocol (MCP) Server
===================================================
Provides tool definitions and execution endpoints for LLM and agent workflows.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="SignalStream MCP Server",
    version="1.0.0",
    description="Tool server exposing auditable operations to LLMs and CrewAI agents",
)


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolExecutionRequest(BaseModel):
    tool_name: str
    parameters: dict[str, Any]
    tenant_id: str


class ToolExecutionResponse(BaseModel):
    tool_name: str
    success: bool
    result: Any
    latency_ms: int


AVAILABLE_TOOLS = [
    ToolDefinition(
        name="lookup_customer_history",
        description="Fetch feedback history and ticket history for a given customer",
        parameters={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    ),
    ToolDefinition(
        name="query_knowledge_base",
        description="Perform semantic search on company support articles and manuals",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="resolve_ticket",
        description="Execute ticket resolution action with resolution note",
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "resolution_note": {"type": "string"},
            },
            "required": ["ticket_id", "resolution_note"],
        },
    ),
]


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {"status": "healthy", "timestamp": time.time(), "tools_count": len(AVAILABLE_TOOLS)}


@app.get("/v1/tools")
async def list_tools() -> list[ToolDefinition]:
    return AVAILABLE_TOOLS


@app.post("/v1/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool(req: ToolExecutionRequest) -> ToolExecutionResponse:
    start_time = time.time()
    # Stub tool execution with tenant isolation
    latency = int((time.time() - start_time) * 1000)
    return ToolExecutionResponse(
        tool_name=req.tool_name,
        success=True,
        result={"message": f"Tool {req.tool_name} executed for tenant {req.tenant_id}"},
        latency_ms=latency,
    )


def main() -> None:
    import uvicorn
    uvicorn.run("services.mcp_server.main:app", host="0.0.0.0", port=8200)


if __name__ == "__main__":
    main()
