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

    When only one genome is registered, ``genome`` may be None and defaults to
    the only available engine.  When multiple genomes are registered, ``genome``
    is required — omitting it raises ValueError listing available genomes.

    The returned label is always included so callers can name the genome in
    their response.

    Returns (label, engine).  Raises ValueError if resolution fails.
    """
    if genome is None:
        if len(engines) == 1:
            genome = next(iter(engines))
        else:
            available = ", ".join(engines.keys())
            raise ValueError(
                f"Multiple genomes registered. Please specify which one: {available}"
            )
    if genome not in engines:
        available = ", ".join(engines.keys())
        raise ValueError(f"Unknown genome '{genome}'. Available: {available}")
    return genome, engines[genome]
