"""HQ MCP protocol routes (JSON-RPC 2.0 over SSE) — exposes CrossWave AI OS tools."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from hq.mcp_server import hq_mcp_server

router = APIRouter(tags=["mcp-hq"])


@router.get("/api/hq/mcp/sse")
async def hq_mcp_sse(request: Request):
    """SSE endpoint for HQ MCP — JSON-RPC 2.0 event stream."""
    await hq_mcp_server.initialize()
    return StreamingResponse(
        hq_mcp_server.sse_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/hq/mcp/message")
async def hq_mcp_message(request: Request):
    """POST endpoint for HQ MCP JSON-RPC 2.0 requests."""
    body = await request.body()
    response = await hq_mcp_server.handle_message(body)
    if not response:
        return JSONResponse(content={"status": "accepted"}, status_code=202)
    data = __import__("json").loads(response)
    return JSONResponse(content=data)
