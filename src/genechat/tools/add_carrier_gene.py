"""Add a new carrier screening gene to the curated seed data."""

import csv
from pathlib import Path

VALID_INHERITANCE = {"AR", "AD", "X-linked"}

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CURATED_DIR = REPO_ROOT / "data" / "seed" / "curated"


def _ensure_gene_in_gene_lists(gene: str, category: str) -> str | None:
    """Ensure gene is in gene_lists.tsv with the given category. Returns error string or None."""
    gene_lists_path = CURATED_DIR / "gene_lists.tsv"
    if not gene_lists_path.exists():
        return f"gene_lists.tsv not found at {gene_lists_path}"

    # Check if gene already present
    with open(gene_lists_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 1 and parts[0] == gene:
                return None  # Already present

    # Append gene
    with open(gene_lists_path, "a", encoding="utf-8") as f:
        f.write(f"{gene}\t{category}\n")

    return None


def register(mcp, engine, db, config):
    @mcp.tool()
    def add_carrier_gene(
        gene: str,
        condition: str,
        inheritance: str,
        carrier_frequency: str = ".",
        acmg_recommended: bool = False,
    ) -> str:
        """Add a new carrier screening gene to the curated seed data.

        Use this when the user wants to add a gene to the carrier screening panel.
        After adding, run rebuild_database to update the SQLite database.

        Parameters:
        - gene: HGNC gene symbol (e.g. SLC22A5)
        - condition: Human-readable condition name (e.g. "Systemic primary carnitine deficiency")
        - inheritance: AR (autosomal recessive), AD (autosomal dominant), or X-linked
        - carrier_frequency: e.g. "1 in 100 (European)" or "." if unknown
        - acmg_recommended: True if on ACMG recommended list, False otherwise
        """
        # Validate gene
        if not gene.strip():
            return "Gene symbol cannot be empty."

        # Validate condition
        if not condition.strip():
            return "Condition name cannot be empty."

        # Validate inheritance
        if inheritance not in VALID_INHERITANCE:
            return (
                f"Invalid inheritance: '{inheritance}'. "
                f"Must be one of: {', '.join(sorted(VALID_INHERITANCE))}."
            )

        carrier_metadata_path = CURATED_DIR / "carrier_metadata.tsv"
        if not carrier_metadata_path.exists():
            return f"carrier_metadata.tsv not found at {carrier_metadata_path}"

        # Check for duplicate gene
        try:
            with open(carrier_metadata_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.strip().split("\t")
                    if len(parts) >= 1 and parts[0] == gene:
                        return f"Gene {gene} already exists in carrier_metadata.tsv."
        except OSError as e:
            return f"Error reading carrier_metadata.tsv: {e}"

        # Ensure gene is in gene_lists.tsv
        try:
            err = _ensure_gene_in_gene_lists(gene, "carrier")
            if err:
                return f"Error updating gene_lists.tsv: {err}"
        except OSError as e:
            return f"Error updating gene_lists.tsv: {e}"

        # Append to carrier_metadata.tsv
        acmg_val = "1" if acmg_recommended else "0"
        row = [gene, condition, inheritance, carrier_frequency, acmg_val]
        try:
            with open(carrier_metadata_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter="\t", lineterminator="\n")
                writer.writerow(row)
        except OSError as e:
            return f"Error writing to carrier_metadata.tsv: {e}"

        acmg_str = "Yes" if acmg_recommended else "No"
        return (
            f"## Carrier Gene Added\n\n"
            f"**{gene}** added to carrier_metadata.tsv.\n\n"
            f"- Condition: {condition}\n"
            f"- Inheritance: {inheritance}\n"
            f"- Carrier frequency: {carrier_frequency}\n"
            f"- ACMG recommended: {acmg_str}\n\n"
            f"Run **rebuild_database** to update the SQLite database."
        )
