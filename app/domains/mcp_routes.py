"""MCP protocol routes (JSON-RPC 2.0 over SSE) + health endpoint."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.services.mcp_service import mcp_service

router = APIRouter(tags=["mcp"])


@router.get("/mcp/sse")
async def mcp_sse(request: Request):
    """SSE endpoint for MCP protocol — JSON-RPC 2.0 event stream."""
    await mcp_service.initialize()

    return StreamingResponse(
        mcp_service.sse_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/mcp/message")
async def mcp_message(request: Request):
    """POST endpoint for MCP JSON-RPC 2.0 requests."""
    body = await request.body()
    response = await mcp_service.handle_message(body)
    if not response:
        return JSONResponse(content={"status": "accepted"}, status_code=202)
    data = json.loads(response)
    return JSONResponse(content=data)


@router.get("/health")
async def health():
    return {"status": "ok", "app": "CrossWave", "version": "1.0.0"}
