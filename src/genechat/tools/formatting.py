"""Shared formatting helpers for MCP tools."""

_ENHANCED_WARNING = (
    "\u26a0\ufe0f **SENSITIVE RESULT**: This gene is associated with a serious "
    "condition that may have limited treatment options. Consider consulting a "
    "genetic counselor before interpreting these findings. Results like these "
    "are typically delivered in a clinical setting with professional support.\n\n"
)


def enhanced_warning_for_genes(db, genes: set[str]) -> str:
    """Return enhanced-warning text if any gene in the set is a warning gene.

    Returns empty string if no genes match or the table doesn't exist.
    """
    for gene in genes:
        if db.is_enhanced_warning_gene(gene):
            return _ENHANCED_WARNING
    return ""


def short_zygosity(zygosity: str) -> str:
    """Abbreviate zygosity for table display."""
    return {
        "homozygous_ref": "ref",
        "heterozygous": "het",
        "homozygous_alt": "hom alt",
        "no_call": "no call",
    }.get(zygosity, zygosity)
