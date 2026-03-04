"""Add a new carrier screening gene to the curated seed data."""

import csv

from genechat.tools._seed_utils import CURATED_DIR, ensure_gene_in_gene_lists

VALID_INHERITANCE = {"AR", "AD", "X-linked"}


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
        After adding, run the full seed data pipeline to update the SQLite database:
        `uv run python scripts/build_seed_data.py`

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
            err = ensure_gene_in_gene_lists(gene, "carrier", CURATED_DIR)
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
            f"Run the full seed data pipeline to update the SQLite database:\n"
            f"`uv run python scripts/build_seed_data.py`"
        )
