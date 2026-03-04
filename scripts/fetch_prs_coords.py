#!/usr/bin/env python3
"""Fetch PRS variant coordinates from Ensembl REST API.

Input:  data/seed/curated/prs_scores.tsv (prs_id, trait, rsid, effect_allele, weight, reference)
Output: data/seed/prs_weights.tsv (with verified chrom, pos)

Uses Ensembl POST /variation/homo_sapiens endpoint.
"""

import csv
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CURATED_DIR = REPO_ROOT / "data" / "seed" / "curated"
SEED_DIR = REPO_ROOT / "data" / "seed"

ENSEMBL_BASE = "https://rest.ensembl.org"
BATCH_SIZE = 200


def load_tsv(path: Path) -> list[dict]:
    """Load TSV file, skipping comment lines."""
    with open(path, encoding="utf-8") as f:
        lines = [line for line in f if not line.startswith("#")]
    reader = csv.DictReader(io.StringIO("".join(lines)), delimiter="\t")
    return list(reader)


def batch_variation_lookup(rsids: list[str], max_retries: int = 3) -> dict:
    """POST batch variation lookup to Ensembl with retries."""
    url = f"{ENSEMBL_BASE}/variation/homo_sapiens"
    payload = json.dumps({"ids": rsids}).encode("utf-8")
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


def extract_coords(variant_data: dict) -> dict | None:
    """Extract GRCh38 coordinates from Ensembl variation response."""
    mappings = variant_data.get("mappings", [])
    for m in mappings:
        assembly = m.get("assembly_name", "")
        loc = m.get("location", "")
        if "GRCh38" in assembly and ":" in loc:
            chrom_raw = loc.split(":")[0]
            chrom = chrom_raw if chrom_raw.startswith("chr") else f"chr{chrom_raw}"
            if not (
                chrom.startswith("chr")
                and (chrom[3:].isdigit() or chrom[3:] in ("X", "Y", "M", "MT"))
            ):
                continue
            return {
                "chrom": chrom,
                "pos": m.get("start"),
            }
    return None


def main():
    prs_path = CURATED_DIR / "prs_scores.tsv"
    output_path = SEED_DIR / "prs_weights.tsv"

    if not prs_path.exists():
        print(f"ERROR: {prs_path} not found")
        sys.exit(1)

    prs_rows = load_tsv(prs_path)
    print(f"Loaded {len(prs_rows)} PRS entries from {prs_path.name}")

    # Collect unique rsIDs
    rsids = list(dict.fromkeys(row["rsid"] for row in prs_rows))
    print(f"Unique rsIDs to look up: {len(rsids)}")

    # Fetch coordinates
    coords = {}
    not_found = []

    for i in range(0, len(rsids), BATCH_SIZE):
        batch = rsids[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(rsids) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches}: {len(batch)} variants...")

        try:
            response = batch_variation_lookup(batch)
        except Exception as e:
            print(f"  ERROR in batch {batch_num}: {e}")
            not_found.extend(batch)
            continue

        for rsid in batch:
            data = response.get(rsid)
            if not data or not isinstance(data, dict):
                not_found.append(rsid)
                continue
            c = extract_coords(data)
            if c:
                coords[rsid] = c
            else:
                not_found.append(rsid)

        if i + BATCH_SIZE < len(rsids):
            time.sleep(0.1)

    print("\nResults:")
    print(f"  Found: {len(coords)} variants")
    print(f"  Not found: {len(not_found)} variants")
    if not_found:
        print(f"  Missing: {', '.join(not_found)}")

    # Build output with coordinates
    output_rows = []
    skipped = 0
    for row in prs_rows:
        rsid = row["rsid"]
        c = coords.get(rsid)
        if not c:
            print(f"  WARNING: No coordinates for PRS variant {rsid}, skipping")
            skipped += 1
            continue

        output_rows.append(
            {
                "prs_id": row["prs_id"],
                "trait": row["trait"],
                "rsid": rsid,
                "chrom": c["chrom"],
                "pos": c["pos"],
                "effect_allele": row["effect_allele"],
                "weight": row["weight"],
                "reference": row["reference"],
            }
        )

    # Write output
    fieldnames = [
        "prs_id",
        "trait",
        "rsid",
        "chrom",
        "pos",
        "effect_allele",
        "weight",
        "reference",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in output_rows:
            writer.writerow(row)

    print(f"\nWrote {len(output_rows)} PRS weights to {output_path}")
    if skipped:
        print(f"Skipped {skipped} variants without coordinates")

    return 0


if __name__ == "__main__":
    sys.exit(main())
