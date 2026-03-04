#!/usr/bin/env python3
"""Fetch gene coordinates from Ensembl REST API for ALL human protein-coding genes.

Downloads the complete HGNC protein-coding gene list (~19,000 genes), merges with
any additional genes from data/seed/curated/gene_lists.tsv, then batch-queries
Ensembl for GRCh38 coordinates.

Output: data/seed/genes_grch38.tsv (symbol, name, chrom, start, end, strand)

This ensures the LLM is never blocked by "gene not found" — every protein-coding
gene has coordinates in the database. The curated gene_lists.tsv is for documenting
clinical categories, not for limiting which genes are queryable.
"""

import csv
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_DIR = REPO_ROOT / "data" / "seed" / "curated"
OUTPUT_DIR = REPO_ROOT / "data" / "seed"

ENSEMBL_BASE = "https://rest.ensembl.org"
BATCH_SIZE = 1000  # Ensembl POST /lookup/symbol supports up to 1000

HGNC_URL = (
    "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/"
    "locus_types/gene_with_protein_product.txt"
)

# Chromosome sort order
CHROM_ORDER = {f"chr{i}": i for i in range(1, 23)}
CHROM_ORDER.update({"chrX": 23, "chrY": 24, "chrM": 25, "chrMT": 25})


def download_hgnc_genes() -> list[str]:
    """Download all approved protein-coding gene symbols from HGNC."""
    print("Downloading HGNC protein-coding gene list...")
    req = urllib.request.Request(HGNC_URL)
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    symbols = []
    for row in reader:
        status = row.get("status", "")
        symbol = row.get("symbol", "").strip()
        if status == "Approved" and symbol:
            symbols.append(symbol)

    print(f"  {len(symbols)} approved protein-coding genes from HGNC")
    return symbols


def load_curated_genes(path: Path) -> list[str]:
    """Load gene symbols from curated gene_lists.tsv (supplementary)."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        lines = [line for line in f if not line.startswith("#")]
    reader = csv.DictReader(io.StringIO("".join(lines)), delimiter="\t")
    return [row["symbol"].strip() for row in reader if row["symbol"].strip()]


def merge_gene_lists(hgnc_genes: list[str], curated_genes: list[str]) -> list[str]:
    """Merge HGNC and curated gene lists, deduplicating."""
    seen = set()
    merged = []
    for symbol in hgnc_genes:
        if symbol not in seen:
            seen.add(symbol)
            merged.append(symbol)
    extra = 0
    for symbol in curated_genes:
        if symbol not in seen:
            seen.add(symbol)
            merged.append(symbol)
            extra += 1
    if extra:
        print(f"  {extra} additional genes from curated gene_lists.tsv")
    return merged


def batch_lookup(symbols: list[str], max_retries: int = 3) -> dict:
    """POST batch lookup to Ensembl with retries. Returns dict of symbol -> response."""
    url = f"{ENSEMBL_BASE}/lookup/symbol/homo_sapiens"
    payload = json.dumps({"symbols": symbols}).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"    Retry {attempt + 1}/{max_retries} after {wait}s ({e})")
                time.sleep(wait)
            else:
                raise


def clean_description(desc: str | None) -> str:
    """Remove [Source:HGNC...] suffix from Ensembl descriptions."""
    if not desc:
        return ""
    return re.sub(r"\s*\[Source:.*?\]", "", desc).strip()


def is_standard_chrom(chrom: str) -> bool:
    """Check if chromosome is standard (1-22, X, Y, MT)."""
    suffix = chrom.replace("chr", "")
    return suffix.isdigit() or suffix in ("X", "Y", "M", "MT")


def fetch_gene_coords(genes: list[str]) -> tuple[list[dict], list[str]]:
    """Fetch coordinates for all genes from Ensembl in batches."""
    results = []
    not_found = []
    skipped_alt = 0  # genes on non-standard chromosomes

    for i in range(0, len(genes), BATCH_SIZE):
        batch = genes[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(genes) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches}: {len(batch)} genes...")

        try:
            response = batch_lookup(batch)
        except Exception as e:
            print(f"  ERROR in batch {batch_num}: {e}")
            not_found.extend(batch)
            continue

        for symbol in batch:
            data = response.get(symbol)
            if not data or not isinstance(data, dict) or "seq_region_name" not in data:
                not_found.append(symbol)
                continue

            chrom = data["seq_region_name"]
            if not chrom.startswith("chr"):
                chrom = f"chr{chrom}"

            # Skip genes on non-standard chromosomes (patches, scaffolds)
            if not is_standard_chrom(chrom):
                skipped_alt += 1
                continue

            strand_int = data.get("strand", 1)
            strand = "+" if strand_int == 1 else "-"

            results.append(
                {
                    "symbol": data.get("display_name", symbol),
                    "name": clean_description(data.get("description")),
                    "chrom": chrom,
                    "start": data["start"],
                    "end": data["end"],
                    "strand": strand,
                }
            )

        if i + BATCH_SIZE < len(genes):
            time.sleep(0.5)  # conservative rate limiting for large batches

    if skipped_alt:
        print(f"  Skipped {skipped_alt} genes on non-standard chromosomes")

    return results, not_found


def sort_by_genome(results: list[dict]) -> list[dict]:
    """Sort results by chromosome order then start position."""
    return sorted(
        results,
        key=lambda r: (CHROM_ORDER.get(r["chrom"], 99), r["start"]),
    )


def write_tsv(results: list[dict], output_path: Path):
    """Write genes_grch38.tsv."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["symbol", "name", "chrom", "start", "end", "strand"],
            delimiter="\t",
        )
        writer.writeheader()
        for row in results:
            writer.writerow(row)


def main():
    gene_list_path = CURATED_DIR / "gene_lists.tsv"
    output_path = OUTPUT_DIR / "genes_grch38.tsv"

    # Download ALL protein-coding genes from HGNC
    try:
        hgnc_genes = download_hgnc_genes()
    except Exception as e:
        print(f"ERROR: Failed to download HGNC gene list: {e}")
        print(
            "Check internet connection. The pipeline requires HGNC access at build time."
        )
        return 1

    # Merge with curated list (picks up any non-protein-coding genes we track)
    curated_genes = load_curated_genes(gene_list_path)
    genes = merge_gene_lists(hgnc_genes, curated_genes)
    print(f"Total unique genes to look up: {len(genes)}")

    print("\nFetching coordinates from Ensembl REST API...")
    results, not_found = fetch_gene_coords(genes)

    results = sort_by_genome(results)
    write_tsv(results, output_path)

    print("\nResults:")
    print(f"  Found: {len(results)} genes with standard chromosome coordinates")
    print(f"  Not found in Ensembl: {len(not_found)} genes")
    if not_found and len(not_found) <= 50:
        print(f"  Missing: {', '.join(not_found)}")
    elif not_found:
        print(f"  First 50 missing: {', '.join(not_found[:50])}...")

    # Validate that all genes referenced by other curated files are present
    found_lower = {r["symbol"].lower() for r in results}

    critical_files = [
        CURATED_DIR / "carrier_metadata.tsv",
        CURATED_DIR / "trait_metadata.tsv",
    ]
    missing_critical = []
    for fpath in critical_files:
        if not fpath.exists():
            continue
        with open(fpath, encoding="utf-8") as f:
            lines = [line for line in f if not line.startswith("#")]
        reader = csv.DictReader(io.StringIO("".join(lines)), delimiter="\t")
        gene_col = "gene" if "gene" in reader.fieldnames else "symbol"
        for row in reader:
            gene = row.get(gene_col, "").strip()
            if gene and gene.lower() not in found_lower:
                missing_critical.append(f"{gene} (from {fpath.name})")

    if missing_critical:
        print(
            "\nWARNING: Genes referenced by other curated files but not found in Ensembl:"
        )
        for m in missing_critical:
            print(f"  - {m}")
        print("ERROR: Critical genes missing — aborting.")
        return 1

    print(f"\nOutput: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
