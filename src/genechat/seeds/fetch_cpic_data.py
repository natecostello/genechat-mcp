#!/usr/bin/env python3
"""Fetch pharmacogenomics data from CPIC API.

Downloads CPIC Level A and B drug-gene pairs, star allele definitions, and
variant positions from the CPIC REST API (https://api.cpicpgx.org/v1/).

Outputs:
  data/seed/pgx_drugs.tsv   — drug-gene pairs with clinical guidance
  data/seed/pgx_variants.tsv — star-allele defining variants with positions

Data license: CPIC content is freely available (CC0).
Rate limits: Be polite — 0.5s between requests.
"""

import csv
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_SEED_DIR = _REPO_ROOT / "data" / "seed"

API_BASE = "https://api.cpicpgx.org/v1"
REQUEST_DELAY = 0.5  # seconds between API calls


def _api_get(endpoint: str, max_retries: int = 3) -> list | dict:
    """GET from CPIC API with retries."""
    url = f"{API_BASE}{endpoint}"
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"    Retry {attempt + 1}/{max_retries} after {wait}s ({e})")
                time.sleep(wait)
            else:
                raise


def fetch_drug_gene_pairs() -> list[dict]:
    """Fetch all CPIC Level A and B drug-gene pairs."""
    print("Fetching CPIC Level A/B drug-gene pairs...")
    data = _api_get(
        "/pair_view?select=drugname,cpiclevel,pgxtesting,guidelineurl,"
        "genesymbol&cpiclevel=in.(A,B)"
    )
    print(f"  {len(data)} drug-gene pairs found")
    return data


def fetch_gene_info(gene: str) -> dict | None:
    """Fetch gene info (chromosome) from CPIC gene table."""
    data = _api_get(f"/gene?symbol=eq.{gene}")
    if data and isinstance(data, list) and len(data) > 0:
        return data[0]
    return None


def fetch_alleles(gene: str) -> list[dict]:
    """Fetch star alleles with clinical function status."""
    return _api_get(
        f"/allele?select=name,clinicalfunctionalstatus&genesymbol=eq.{gene}"
    )


def fetch_allele_definitions(gene: str) -> list[dict]:
    """Fetch allele definitions (links to variant locations)."""
    return _api_get(
        f"/allele_definition?select=id,name,genesymbol&genesymbol=eq.{gene}"
    )


def fetch_sequence_locations(gene: str) -> list[dict]:
    """Fetch variant positions for a gene's allele definitions."""
    return _api_get(
        f"/sequence_location?select=id,dbsnpid,chromosomelocation,position,"
        f"genesymbol&genesymbol=eq.{gene}"
    )


def fetch_allele_location_values(definition_ids: list[int]) -> list[dict]:
    """Fetch which variants define each star allele."""
    if not definition_ids:
        return []
    ids_str = ",".join(str(i) for i in definition_ids)
    return _api_get(
        f"/allele_location_value?select=alleledefinitionid,locationid,"
        f"variantallele&alleledefinitionid=in.({ids_str})"
    )


def parse_hgvs_alleles(hgvs: str) -> dict | None:
    """Parse ref/alt alleles from HGVS genomic notation like 'g.94761900C>T'.

    Returns dict with ref, alt. Position comes from the API's position field.
    """
    if not hgvs:
        return None

    # SNV pattern: g.12345C>T
    m = re.search(r"g\.\d+([A-Z]+)>([A-Z]+)", hgvs)
    if m:
        return {"ref": m.group(1), "alt": m.group(2)}

    # Deletion pattern: g.12345del or g.12345delA
    m = re.search(r"g\.\d+del([A-Z]*)", hgvs)
    if m:
        return {"ref": m.group(1) if m.group(1) else "N", "alt": "del"}

    return None


def build_pgx_drugs(pairs: list[dict]) -> list[dict]:
    """Build pgx_drugs.tsv rows from CPIC pair data."""
    rows = []
    for p in pairs:
        drug = p.get("drugname", "").strip().lower()
        gene = p.get("genesymbol", "").strip()
        level = p.get("cpiclevel", "")
        testing = p.get("pgxtesting", "")
        url = p.get("guidelineurl", "") or "."

        if not drug or not gene:
            continue

        clinical_summary = f"CPIC Level {level} drug-gene pair."
        if testing:
            clinical_summary += f" PGx testing: {testing}."

        rows.append(
            {
                "drug_name": drug,
                "gene": gene,
                "guideline_source": "CPIC",
                "guideline_url": url,
                "clinical_summary": clinical_summary,
                "cpic_level": level,
                "pgx_testing": testing or ".",
            }
        )

    # Sort by drug name then gene
    rows.sort(key=lambda r: (r["drug_name"], r["gene"]))
    return rows


def build_pgx_variants(pairs: list[dict]) -> list[dict]:
    """Build pgx_variants.tsv rows by querying allele/variant data per gene."""
    # Get unique genes
    genes = sorted({p["genesymbol"] for p in pairs if p.get("genesymbol")})
    print(f"\nFetching allele definitions for {len(genes)} genes...")

    all_variants = []

    for gene in genes:
        print(f"  {gene}...")
        time.sleep(REQUEST_DELAY)

        # Get chromosome from gene table
        try:
            gene_info = fetch_gene_info(gene)
        except Exception as e:
            print(f"    WARNING: Could not fetch gene info for {gene}: {e}")
            continue

        if not gene_info or not gene_info.get("chr"):
            print(f"    WARNING: No chromosome info for {gene}, skipping")
            continue

        chrom = gene_info["chr"]
        if not chrom.startswith("chr"):
            chrom = f"chr{chrom}"

        time.sleep(REQUEST_DELAY)

        # Get sequence locations (variant positions)
        try:
            locations = fetch_sequence_locations(gene)
        except Exception as e:
            print(f"    WARNING: Could not fetch locations for {gene}: {e}")
            continue

        if not locations:
            continue

        time.sleep(REQUEST_DELAY)

        # Get alleles (for clinical function status) — join by name
        try:
            alleles = fetch_alleles(gene)
        except Exception as e:
            print(f"    WARNING: Could not fetch alleles for {gene}: {e}")
            alleles = []

        # Map allele name -> clinical function
        allele_function = {}
        for a in alleles:
            name = a.get("name", "")
            func = a.get("clinicalfunctionalstatus", "")
            if name:
                allele_function[name] = func or ""

        time.sleep(REQUEST_DELAY)

        # Get allele definitions (links alleles to locations)
        try:
            allele_defs = fetch_allele_definitions(gene)
        except Exception as e:
            print(f"    WARNING: Could not fetch allele definitions for {gene}: {e}")
            allele_defs = []

        # Map definition ID -> allele name
        def_id_to_name = {}
        for ad in allele_defs:
            if ad.get("id") and ad.get("name"):
                def_id_to_name[ad["id"]] = ad["name"]

        # Get allele-location mappings
        def_ids = [ad["id"] for ad in allele_defs if ad.get("id")]
        alv_data = []
        if def_ids:
            time.sleep(REQUEST_DELAY)
            try:
                alv_data = fetch_allele_location_values(def_ids)
            except Exception as e:
                print(
                    f"    WARNING: Could not fetch allele-location values for {gene}: {e}"
                )

        # Build location_id -> dbsnpid mapping
        loc_id_to_info: dict[int, dict] = {}
        for loc in locations:
            loc_id = loc.get("id")
            dbsnp = loc.get("dbsnpid", "")
            pos = loc.get("position")
            chrom_loc = loc.get("chromosomelocation", "")

            if not loc_id or not dbsnp or not pos:
                continue

            # Parse ref/alt from HGVS — skip if unparseable
            allele_info = parse_hgvs_alleles(chrom_loc)
            if not allele_info:
                continue
            ref = allele_info["ref"]
            alt = allele_info["alt"]

            loc_id_to_info[loc_id] = {
                "dbsnpid": dbsnp,
                "pos": pos,
                "ref": ref,
                "alt": alt,
            }

        # Group ALV by location_id -> list of (star_allele_name, function)
        dbsnp_alleles: dict[str, list[tuple[str, str]]] = {}
        for alv in alv_data:
            lid = alv.get("locationid")
            aid = alv.get("alleledefinitionid")
            if lid and aid and lid in loc_id_to_info and aid in def_id_to_name:
                allele_name = def_id_to_name[aid]
                func = allele_function.get(allele_name, "")
                dbsnp = loc_id_to_info[lid]["dbsnpid"]
                dbsnp_alleles.setdefault(dbsnp, []).append((allele_name, func))

        # Build output rows: one row per (gene, rsid, star_allele)
        for loc_id, info in loc_id_to_info.items():
            dbsnp = info["dbsnpid"]
            star_alleles = dbsnp_alleles.get(dbsnp, [])
            if star_alleles:
                for star_name, func_status in star_alleles:
                    all_variants.append(
                        {
                            "gene": gene,
                            "rsid": dbsnp,
                            "chrom": chrom,
                            "pos": info["pos"],
                            "ref": info["ref"],
                            "alt": info["alt"],
                            "star_allele": star_name,
                            "function_impact": func_status or ".",
                            "notes": ".",
                        }
                    )
            else:
                # Variant has position but no star allele mapping
                all_variants.append(
                    {
                        "gene": gene,
                        "rsid": dbsnp,
                        "chrom": chrom,
                        "pos": info["pos"],
                        "ref": info["ref"],
                        "alt": info["alt"],
                        "star_allele": ".",
                        "function_impact": ".",
                        "notes": ".",
                    }
                )

        var_count = sum(1 for v in all_variants if v["gene"] == gene)
        print(f"    {var_count} variants")

    # Deduplicate: same (gene, rsid, star_allele) -> keep first
    seen = set()
    deduped = []
    for v in all_variants:
        key = (v["gene"], v["rsid"], v["star_allele"])
        if key not in seen:
            seen.add(key)
            deduped.append(v)

    # Sort by gene, rsid
    deduped.sort(key=lambda r: (r["gene"], r["rsid"], r["star_allele"]))
    return deduped


def write_drugs_tsv(rows: list[dict], path: Path):
    """Write pgx_drugs.tsv."""
    fieldnames = [
        "drug_name",
        "gene",
        "guideline_source",
        "guideline_url",
        "clinical_summary",
        "cpic_level",
        "pgx_testing",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(
            "# Source: CPIC via API (https://api.cpicpgx.org/v1/). "
            "Auto-generated by fetch_cpic_data.py.\n"
        )
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_variants_tsv(rows: list[dict], path: Path):
    """Write pgx_variants.tsv."""
    fieldnames = [
        "gene",
        "rsid",
        "chrom",
        "pos",
        "ref",
        "alt",
        "star_allele",
        "function_impact",
        "notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write("# Source: CPIC via API. Coordinates from CPIC sequence_location.\n")
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(output_dir: Path | None = None):
    output_dir = output_dir or _DEFAULT_SEED_DIR

    # Step 1: Fetch drug-gene pairs
    try:
        pairs = fetch_drug_gene_pairs()
    except Exception as e:
        print(f"ERROR: Failed to fetch CPIC data: {e}")
        return 1

    if not pairs:
        print("ERROR: No drug-gene pairs returned from CPIC API")
        return 1

    # Step 2: Build drugs TSV
    drugs = build_pgx_drugs(pairs)
    drugs_path = output_dir / "pgx_drugs.tsv"
    write_drugs_tsv(drugs, drugs_path)
    print(f"\nWrote {len(drugs)} drug-gene pairs to {drugs_path.name}")

    # Step 3: Build variants TSV
    variants = build_pgx_variants(pairs)
    variants_path = output_dir / "pgx_variants.tsv"
    write_variants_tsv(variants, variants_path)
    print(f"Wrote {len(variants)} PGx variants to {variants_path.name}")

    return 0


if __name__ == "__main__":
    _dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(main(output_dir=_dir))
