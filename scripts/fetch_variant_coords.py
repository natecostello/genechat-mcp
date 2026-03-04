#!/usr/bin/env python3
"""Fetch variant coordinates from Ensembl REST API for trait and PGx variants.

Input:  data/seed/curated/trait_metadata.tsv (rsid, gene, ref, alt, ...)
        data/seed/pgx_variants.tsv (gene, rsid, chrom, pos, ref, alt, ...)
Output: data/seed/trait_variants.tsv (with verified chrom, pos from Ensembl + curated ref/alt)
        data/seed/pgx_variants.tsv (with verified chrom/pos; curated ref/alt preserved)

Uses Ensembl POST /variation/homo_sapiens endpoint (batch, up to 200 per request).
Ensembl's allele_string is an unordered list of observed alleles and must NOT be
assumed to be ordered as REF/ALT. We only trust Ensembl for coordinates (chrom, pos).
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
    """POST batch variation lookup to Ensembl with retries. Returns dict of rsid -> data."""
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
    """Extract GRCh38 coordinates from Ensembl variation response.

    Only returns chrom and pos. Ensembl's allele_string is an unordered list
    of observed alleles and must not be assumed to be ordered as REF/ALT.
    """
    mappings = variant_data.get("mappings", [])
    if not mappings:
        return None

    # Find the GRCh38 mapping on a primary assembly chromosome
    for m in mappings:
        assembly = m.get("assembly_name", "")
        loc = m.get("location", "")
        if "GRCh38" in assembly and ":" in loc:
            chrom_raw = loc.split(":")[0]
            chrom = chrom_raw if chrom_raw.startswith("chr") else f"chr{chrom_raw}"
            # Skip non-standard chromosomes
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


def fetch_variant_coords(rsids: list[str]) -> tuple[dict, list[str]]:
    """Fetch coordinates for all rsIDs. Returns (dict of rsid -> coords, not_found list)."""
    results = {}
    not_found = []

    unique_rsids = list(dict.fromkeys(rsids))  # dedupe preserving order

    for i in range(0, len(unique_rsids), BATCH_SIZE):
        batch = unique_rsids[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(unique_rsids) + BATCH_SIZE - 1) // BATCH_SIZE
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

            coords = extract_coords(data)
            if coords:
                results[rsid] = coords
            else:
                not_found.append(rsid)

        if i + BATCH_SIZE < len(unique_rsids):
            time.sleep(0.1)

    return results, not_found


def build_trait_variants(trait_metadata: list[dict], coords: dict) -> list[dict]:
    """Merge trait metadata with fetched coordinates.

    Uses curated ref/alt from trait_metadata (not Ensembl allele_string).
    """
    output_rows = []
    for row in trait_metadata:
        rsid = row["rsid"]
        c = coords.get(rsid)
        if not c:
            print(
                f"  WARNING: No coordinates for trait variant {rsid} ({row.get('gene', '?')}), skipping"
            )
            continue

        ref = row.get("ref")
        alt = row.get("alt")
        if not ref or ref == "." or not alt or alt == ".":
            raise ValueError(
                f"Missing or invalid ref/alt for trait variant {rsid} "
                f"({row.get('gene', '?')}). Please ensure curated "
                "trait_metadata.tsv includes non-'.' ref and alt values."
            )

        output_rows.append(
            {
                "rsid": rsid,
                "chrom": c["chrom"],
                "pos": c["pos"],
                "ref": ref,
                "alt": alt,
                "gene": row["gene"],
                "trait_category": row["trait_category"],
                "trait": row["trait"],
                "effect_allele": row["effect_allele"],
                "effect_description": row["effect_description"],
                "evidence_level": row["evidence_level"],
                "pmid": row["pmid"],
            }
        )

    return output_rows


def update_pgx_variants(pgx_rows: list[dict], coords: dict) -> list[dict]:
    """Update PGx variant chrom/pos from Ensembl; never overwrite curated ref/alt."""
    updated = []
    for row in pgx_rows:
        rsid = row.get("rsid", "")
        c = coords.get(rsid)

        if c:
            old_pos = row.get("pos", "")
            new_pos = str(c["pos"])
            if old_pos and old_pos != new_pos:
                print(
                    f"  POS UPDATE: {rsid} pos {old_pos} -> {new_pos} (using Ensembl)"
                )

            row_out = dict(row)
            row_out["chrom"] = c["chrom"]
            row_out["pos"] = c["pos"]
            # Never overwrite curated ref/alt — Ensembl allele_string is unordered
            updated.append(row_out)
        else:
            # Keep existing coordinates
            updated.append(dict(row))

    return updated


def write_tsv(
    rows: list[dict],
    path: Path,
    fieldnames: list[str],
    header_comments: list[str] | None = None,
):
    """Write TSV with optional header comments."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        if header_comments:
            for comment in header_comments:
                f.write(f"# {comment}\n")
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    trait_path = CURATED_DIR / "trait_metadata.tsv"
    pgx_path = SEED_DIR / "pgx_variants.tsv"

    if not trait_path.exists():
        print(f"ERROR: {trait_path} not found")
        sys.exit(1)

    # Collect all rsIDs
    trait_rows = load_tsv(trait_path)
    pgx_rows = load_tsv(pgx_path) if pgx_path.exists() else []

    rsids = []
    for row in trait_rows:
        rsids.append(row["rsid"])
    for row in pgx_rows:
        rsid = row.get("rsid", "")
        if rsid:
            rsids.append(rsid)

    # Filter out non-standard rsIDs (like rs8175347 which may have merged) and dedupe
    valid_rsids = sorted(
        {r for r in rsids if r.startswith("rs") and r[2:].replace("_", "").isdigit()}
    )
    print(f"Collected {len(valid_rsids)} unique rsIDs to look up")

    print("Fetching coordinates from Ensembl REST API...")
    coords, not_found = fetch_variant_coords(valid_rsids)

    print("\nResults:")
    print(f"  Found: {len(coords)} variants")
    print(f"  Not found: {len(not_found)} variants")
    if not_found:
        print(f"  Missing: {', '.join(not_found)}")

    # Build trait_variants.tsv
    print("\nBuilding trait_variants.tsv...")
    trait_output = build_trait_variants(trait_rows, coords)
    trait_fields = [
        "rsid",
        "chrom",
        "pos",
        "ref",
        "alt",
        "gene",
        "trait_category",
        "trait",
        "effect_allele",
        "effect_description",
        "evidence_level",
        "pmid",
    ]
    trait_out_path = SEED_DIR / "trait_variants.tsv"
    write_tsv(trait_output, trait_out_path, trait_fields)
    print(f"  Wrote {len(trait_output)} trait variants to {trait_out_path}")

    # Update pgx_variants.tsv
    if pgx_rows:
        print("\nUpdating pgx_variants.tsv coordinates...")
        pgx_output = update_pgx_variants(pgx_rows, coords)
        pgx_fields = list(pgx_rows[0].keys())
        pgx_out_path = SEED_DIR / "pgx_variants.tsv"
        pgx_comments = [
            "Source: PharmVar, CPIC, dbSNP (GRCh38.p14). Coordinates verified via Ensembl REST API.",
            "Note: rs8175347 (UGT1A1 *28) was merged into rs3064744 in dbSNP Build 152.",
            "Note: TPMT is on the minus strand; ref/alt alleles are given on the genomic plus strand per VCF convention.",
        ]
        write_tsv(pgx_output, pgx_out_path, pgx_fields, pgx_comments)
        print(f"  Wrote {len(pgx_output)} PGx variants to {pgx_out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
