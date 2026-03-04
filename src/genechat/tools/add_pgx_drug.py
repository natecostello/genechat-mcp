"""Add a new pharmacogenomics drug-gene pair to the seed data."""

import csv

from genechat.tools._seed_utils import CURATED_DIR, SEED_DIR, ensure_gene_in_gene_lists


def register(mcp, engine, db, config):
    @mcp.tool()
    def add_pgx_drug(
        drug_name: str,
        gene: str,
        guideline_source: str = "CPIC",
        drug_aliases: str = ".",
        guideline_url: str = ".",
        clinical_summary: str = ".",
    ) -> str:
        """Add a new pharmacogenomics drug-gene pair to the seed data.

        Use this when the user wants to add a new drug-gene interaction
        (e.g. a CPIC guideline pair) to the GeneChat database.
        After adding, run rebuild_database to update the SQLite database.

        Parameters:
        - drug_name: Generic drug name (e.g. "pantoprazole")
        - gene: HGNC gene symbol (e.g. "CYP2C19")
        - guideline_source: Source of the guideline (default: "CPIC")
        - drug_aliases: Comma-separated brand names (e.g. "protonix") or "." if none
        - guideline_url: URL to the guideline or "." if unavailable
        - clinical_summary: Brief clinical guidance text or "." if unavailable
        """
        # Validate required fields
        if not drug_name.strip():
            return "Drug name cannot be empty."
        if not gene.strip():
            return "Gene symbol cannot be empty."

        pgx_drugs_path = SEED_DIR / "pgx_drugs.tsv"
        if not pgx_drugs_path.exists():
            return f"pgx_drugs.tsv not found at {pgx_drugs_path}"

        # Check for duplicate drug+gene combination
        try:
            with open(pgx_drugs_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.strip().split("\t")
                    if len(parts) >= 3:
                        existing_drug = parts[0].lower()
                        existing_gene = parts[2].upper()
                        if (
                            existing_drug == drug_name.lower()
                            and existing_gene == gene.upper()
                        ):
                            return (
                                f"Drug-gene pair {drug_name}/{gene} already exists "
                                f"in pgx_drugs.tsv."
                            )
        except OSError as e:
            return f"Error reading pgx_drugs.tsv: {e}"

        # Ensure gene is in gene_lists.tsv
        try:
            err = ensure_gene_in_gene_lists(gene, "pgx", CURATED_DIR)
            if err:
                return f"Error updating gene_lists.tsv: {err}"
        except OSError as e:
            return f"Error updating gene_lists.tsv: {e}"

        # Append to pgx_drugs.tsv
        row = [
            drug_name,
            drug_aliases,
            gene,
            guideline_source,
            guideline_url,
            clinical_summary,
        ]
        try:
            with open(pgx_drugs_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter="\t", lineterminator="\n")
                writer.writerow(row)
        except OSError as e:
            return f"Error writing to pgx_drugs.tsv: {e}"

        return (
            f"## PGx Drug-Gene Pair Added\n\n"
            f"**{drug_name}** / **{gene}** added to pgx_drugs.tsv.\n\n"
            f"- Aliases: {drug_aliases}\n"
            f"- Guideline: {guideline_source}\n"
            f"- URL: {guideline_url}\n"
            f"- Summary: {clinical_summary}\n\n"
            f"Run **rebuild_database** to update the SQLite database."
        )
