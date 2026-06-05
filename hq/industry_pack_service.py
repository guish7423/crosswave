"""Industry Pack loader — YAML-based startup templates.

Each pack defines:
- Which agents to activate/deactivate
- Pricing tiers
- Deliverable templates
- Celery schedule suggestions
- Startup tips & revenue targets

Packs live in ``hq/industry-packs/*.yaml``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PACKS_DIR = Path(__file__).resolve().parent / "industry-packs"


def list_packs() -> list[dict[str, Any]]:
    """Return metadata for all available industry packs."""
    import yaml

    packs: list[dict[str, Any]] = []
    if not PACKS_DIR.is_dir():
        return packs

    for fpath in sorted(PACKS_DIR.glob("*.yaml")):
        with open(fpath) as f:
            data = yaml.safe_load(f)
        packs.append({
            "name": data.get("name", fpath.stem),
            "slug": data.get("slug", fpath.stem),
            "description": data.get("description", ""),
            "niche": data.get("niche", ""),
            "difficulty": data.get("difficulty", "Beginner"),
            "monthly_revenue_target": data.get("monthly_revenue_target", ""),
            "agent_count": len(data.get("agents", {}).get("activate", [])),
        })
    return packs


def get_pack(slug: str) -> dict[str, Any] | None:
    """Return the full pack data for a given slug, or None."""
    import yaml

    fpath = PACKS_DIR / f"{slug}.yaml"
    if not fpath.is_file():
        return None
    with open(fpath) as f:
        return yaml.safe_load(f)


def get_difficulty_packs(difficulty: str) -> list[dict[str, Any]]:
    """Filter packs by difficulty level."""
    return [p for p in list_packs() if p.get("difficulty", "").lower() == difficulty.lower()]


def pack_slugs() -> list[str]:
    """Return all available pack slugs."""
    if not PACKS_DIR.is_dir():
        return []
    return sorted(f.stem for f in PACKS_DIR.glob("*.yaml"))
