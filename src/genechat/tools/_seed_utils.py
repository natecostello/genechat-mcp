"""Shared utilities for seed data editing tools."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CURATED_DIR = REPO_ROOT / "data" / "seed" / "curated"
SEED_DIR = REPO_ROOT / "data" / "seed"


def ensure_gene_in_gene_lists(
    gene: str, category: str, curated_dir: Path | None = None
) -> str | None:
    """Ensure gene is in gene_lists.tsv with the given category. Returns error string or None."""
    base = curated_dir or CURATED_DIR
    gene_lists_path = base / "gene_lists.tsv"
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
