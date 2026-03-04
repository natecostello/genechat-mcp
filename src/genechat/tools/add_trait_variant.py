"""Add a new trait variant to the curated seed data."""

import csv
import re

from genechat.tools._seed_utils import CURATED_DIR, ensure_gene_in_gene_lists

VALID_CATEGORIES = {
    "nutrigenomics",
    "exercise",
    "metabolism",
    "cardiovascular",
    "sleep",
    "skin",
    "vitamins",
    "immune",
    "cognition",
    "longevity",
    "other",
}

VALID_EVIDENCE_LEVELS = {"strong", "moderate", "preliminary"}

RSID_PATTERN = re.compile(r"^rs\d+$")


def register(mcp, engine, db, config):
    @mcp.tool()
    def add_trait_variant(
        rsid: str,
        gene: str,
        trait_category: str,
        trait: str,
        ref: str,
        alt: str,
        effect_allele: str,
        effect_description: str,
        evidence_level: str,
        pmid: str,
    ) -> str:
        """Add a new trait-associated variant to the curated seed data.

        Use this when the user wants to add a new trait variant (e.g. a SNP associated
        with a trait like caffeine metabolism, muscle fiber type, etc.) to the GeneChat
        database. After adding, run rebuild_database to fetch coordinates and update SQLite.

        Parameters:
        - rsid: dbSNP rsID (e.g. rs7501331)
        - gene: HGNC gene symbol (e.g. BCMO1)
        - trait_category: One of nutrigenomics, exercise, metabolism, cardiovascular,
          sleep, skin, vitamins, immune, cognition, longevity, other
        - trait: Short trait name (e.g. "Beta-carotene conversion")
        - ref: GRCh38 plus-strand reference allele
        - alt: GRCh38 plus-strand alternate allele
        - effect_allele: The allele with the described effect (must be ref or alt)
        - effect_description: What the effect allele does (be specific)
        - evidence_level: One of strong, moderate, preliminary
        - pmid: PubMed ID of the primary source paper
        """
        # Validate rsid
        if not RSID_PATTERN.match(rsid):
            return f"Invalid rsID format: '{rsid}'. Expected format: rs followed by digits (e.g. rs7501331)."

        # Validate trait_category
        if trait_category not in VALID_CATEGORIES:
            return (
                f"Invalid trait_category: '{trait_category}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}."
            )

        # Validate evidence_level
        if evidence_level not in VALID_EVIDENCE_LEVELS:
            return (
                f"Invalid evidence_level: '{evidence_level}'. "
                f"Must be one of: {', '.join(sorted(VALID_EVIDENCE_LEVELS))}."
            )

        # Validate allele fields are non-empty
        if not ref.strip():
            return "Reference allele (ref) cannot be empty."
        if not alt.strip():
            return "Alternate allele (alt) cannot be empty."
        if not effect_allele.strip():
            return "Effect allele cannot be empty."

        # Validate effect_allele
        if effect_allele not in (ref, alt):
            return (
                f"effect_allele '{effect_allele}' must be either the ref allele "
                f"('{ref}') or the alt allele ('{alt}')."
            )

        # Check for required non-empty fields
        if not gene.strip():
            return "Gene symbol cannot be empty."
        if not trait.strip():
            return "Trait name cannot be empty."
        if not effect_description.strip():
            return "Effect description cannot be empty."
        if not pmid.strip():
            return "PubMed ID cannot be empty."

        trait_metadata_path = CURATED_DIR / "trait_metadata.tsv"
        if not trait_metadata_path.exists():
            return f"trait_metadata.tsv not found at {trait_metadata_path}"

        # Check for duplicate rsid
        try:
            with open(trait_metadata_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.strip().split("\t")
                    if len(parts) >= 1 and parts[0] == rsid:
                        return f"Variant {rsid} already exists in trait_metadata.tsv."
        except OSError as e:
            return f"Error reading trait_metadata.tsv: {e}"

        # Ensure gene is in gene_lists.tsv
        try:
            err = ensure_gene_in_gene_lists(gene, "trait", CURATED_DIR)
            if err:
                return f"Error updating gene_lists.tsv: {err}"
        except OSError as e:
            return f"Error updating gene_lists.tsv: {e}"

        # Append to trait_metadata.tsv
        row = [
            rsid,
            gene,
            trait_category,
            trait,
            ref,
            alt,
            effect_allele,
            effect_description,
            evidence_level,
            pmid,
        ]
        try:
            with open(trait_metadata_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter="\t", lineterminator="\n")
                writer.writerow(row)
        except OSError as e:
            return f"Error writing to trait_metadata.tsv: {e}"

        return (
            f"## Trait Variant Added\n\n"
            f"**{rsid}** ({gene}) added to trait_metadata.tsv.\n\n"
            f"- Category: {trait_category}\n"
            f"- Trait: {trait}\n"
            f"- Alleles: ref={ref}, alt={alt}, effect={effect_allele}\n"
            f"- Evidence: {evidence_level}\n"
            f"- PMID: {pmid}\n\n"
            f"Run **rebuild_database** to fetch genomic coordinates from Ensembl "
            f"and update the SQLite database."
        )
