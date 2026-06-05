"""HQ Model Router API routes (Phase 3)."""

from fastapi import APIRouter

from hq.model_router import AGENT_CAPABILITY_MAP, get_registry

router = APIRouter(prefix="/api/hq", tags=["model_router"])


@router.get("/models")
async def get_models():
    """Return all registered model profiles + agent→capability mapping."""
    registry = get_registry()
    profiles = registry.get_all_profiles()
    return {
        "profiles": [p.model_dump() for p in profiles],
        "agent_mapping": dict(AGENT_CAPABILITY_MAP),
    }


@router.post("/agents/{agent_type}/trigger")
async def trigger_agent(agent_type: str):
    """Send a test prompt to the best provider for *agent_type*."""
    registry = get_registry()
    cap = AGENT_CAPABILITY_MAP.get(agent_type, "conversation")
    prompt = f"As a {agent_type} agent ({cap} task), provide your analysis."
    result = await registry.chat(
        agent_type,
        [{"role": "system", "content": f"You are a {agent_type} agent."},
         {"role": "user", "content": prompt}],
    )
    return {
        "agent_type": agent_type,
        "capability": cap,
        "provider": result.provider,
        "model": result.model,
        "content": result.content,
    }
