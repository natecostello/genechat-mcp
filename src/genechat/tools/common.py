"""Shared utilities for MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from genechat.config import AppConfig
    from genechat.vcf_engine import VCFEngine


def resolve_engine(
    engines: dict[str, VCFEngine],
    genome: str | None,
    config: AppConfig,
) -> tuple[str, VCFEngine]:
    """Resolve a genome label to its VCFEngine.

    Returns (label, engine). Raises ValueError with available genome names
    if the requested label is not found.
    """
    if genome is None:
        genome = config.default_genome
    if genome not in engines:
        available = ", ".join(engines.keys())
        raise ValueError(f"Unknown genome '{genome}'. Available: {available}")
    return genome, engines[genome]
