"""Parse VCF GT (genotype) field."""


def parse_genotype(gt: str, ref: str, alt: str) -> dict:
    """Parse VCF GT field into human-readable form.

    Returns dict with 'display' (e.g. 'T/C') and 'zygosity'
    (homozygous_ref, heterozygous, homozygous_alt, no_call).
    """
    if gt in (".", "./.", ".|."):
        return {"display": "no call", "zygosity": "no_call"}
    separator = "/" if "/" in gt else "|"
    alleles_idx = gt.split(separator)
    allele_map = {"0": ref}
    for i, a in enumerate(alt.split(","), 1):
        allele_map[str(i)] = a
    alleles = [allele_map.get(idx, "?") for idx in alleles_idx]
    display = "/".join(alleles)
    if len(alleles) >= 2 and alleles[0] == alleles[1]:
        zygosity = "homozygous_ref" if alleles[0] == ref else "homozygous_alt"
    else:
        zygosity = "heterozygous"
    return {"display": display, "zygosity": zygosity}
