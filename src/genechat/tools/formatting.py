"""Shared formatting helpers for MCP tools."""


def short_zygosity(zygosity: str) -> str:
    """Abbreviate zygosity for table display."""
    return {
        "homozygous_ref": "ref",
        "heterozygous": "het",
        "homozygous_alt": "hom alt",
        "no_call": "no call",
    }.get(zygosity, zygosity)
