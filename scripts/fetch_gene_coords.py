#!/usr/bin/env python3
"""Fetch gene coordinates from Ensembl REST API for all genes in gene_lists.tsv.

Input:  data/seed/curated/gene_lists.tsv (symbol, category)
Output: data/seed/genes_grch38.tsv (symbol, name, chrom, start, end, strand)

Uses Ensembl POST /lookup/symbol/homo_sapiens endpoint (batch, up to 1000 per request).
Rate limit: 15 req/s — uses 0.1s delay between batches.
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
BATCH_SIZE = 200

# Chromosome sort order
CHROM_ORDER = {f"chr{i}": i for i in range(1, 23)}
CHROM_ORDER.update({"chrX": 23, "chrY": 24, "chrM": 25, "chrMT": 25})


def load_gene_list(path: Path) -> list[str]:
    """Load unique gene symbols from curated gene_lists.tsv."""
    with open(path, encoding="utf-8") as f:
        lines = [line for line in f if not line.startswith("#")]
    reader = csv.DictReader(io.StringIO("".join(lines)), delimiter="\t")
    seen = set()
    genes = []
    for row in reader:
        symbol = row["symbol"].strip()
        if symbol and symbol not in seen:
            seen.add(symbol)
            genes.append(symbol)
    return genes


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
            with urllib.request.urlopen(req, timeout=60) as resp:
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


def fetch_gene_coords(genes: list[str]) -> list[dict]:
    """Fetch coordinates for all genes from Ensembl in batches."""
    results = []
    not_found = []

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
            time.sleep(0.1)

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

    if not gene_list_path.exists():
        print(f"ERROR: {gene_list_path} not found")
        sys.exit(1)

    genes = load_gene_list(gene_list_path)
    print(f"Loaded {len(genes)} unique genes from {gene_list_path.name}")

    print("Fetching coordinates from Ensembl REST API...")
    results, not_found = fetch_gene_coords(genes)

    results = sort_by_genome(results)
    write_tsv(results, output_path)

    print("\nResults:")
    print(f"  Found: {len(results)} genes")
    print(f"  Not found: {len(not_found)} genes")
    if not_found:
        print(f"  Missing: {', '.join(not_found)}")

    # Check that all genes referenced by other curated files are present
    found_symbols = {r["symbol"] for r in results}
    # Also check case-insensitive
    found_lower = {s.lower() for s in found_symbols}

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

    print(f"\nOutput: {output_path}")

    if missing_critical:
        print("ERROR: Critical genes missing — aborting.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
