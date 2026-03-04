"""Parse ClinVar INFO fields from annotated VCFs."""


def parse_clinvar_fields(clnsig: str, clndn: str, clnrevstat: str) -> dict:
    """Parse ClinVar INFO fields. Returns empty dict if no ClinVar data."""
    if not clnsig or clnsig == ".":
        return {}
    return {
        "significance": clnsig.replace("_", " "),
        "condition": (clndn.replace("_", " ") if clndn and clndn != "." else None),
        "review_status": (
            clnrevstat.replace("_", " ") if clnrevstat and clnrevstat != "." else None
        ),
    }
