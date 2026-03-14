"""Fetch enhanced-warning gene list from ClinVar and HPO.

Derives a list of genes where unsolicited disclosure may cause psychological
harm: genes with known pathogenic variants (ClinVar) associated with severe
untreatable conditions (HPO death/neurodegeneration terms), excluding
clinically actionable genes (ACMG SF v3.3).

Pipeline:
    1. ClinVar variant_summary.txt.gz → genes with Pathogenic significance
    2. HPO genes_to_phenotype.txt → genes with death/neurodegeneration terms
    3. Intersect step 1 ∩ step 2
    4. Subtract ACMG SF v3.3 actionable genes

Output: enhanced_warning_genes.tsv
"""

import csv
import gzip
import io
import sys
import urllib.request
from pathlib import Path

_DEFAULT_SEED_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "seed"
)

# ---------------------------------------------------------------------------
# Source URLs
# ---------------------------------------------------------------------------

CLINVAR_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
)

HPO_URL = "https://purl.obolibrary.org/obo/hp/hpoa/genes_to_phenotype.txt"

# ---------------------------------------------------------------------------
# HPO phenotype terms indicating death or progressive neurodegeneration
# ---------------------------------------------------------------------------

HPO_TERMS = {
    # Death / lethality
    "HP:0003826",  # Stillbirth
    "HP:0003811",  # Neonatal death
    "HP:0001522",  # Death in infancy
    "HP:0003819",  # Death in childhood
    "HP:0011421",  # Death in adolescence
    "HP:0100613",  # Death in early adulthood
    "HP:0033041",  # Death in middle age
    # Neurodegeneration / progressive deterioration
    "HP:0002180",  # Neurodegeneration
    "HP:0001268",  # Mental deterioration
    "HP:0002344",  # Progressive neurologic deterioration
    "HP:0007272",  # Progressive psychomotor deterioration
    "HP:0006964",  # Cerebral cortical neurodegeneration
    "HP:0007064",  # Progressive language deterioration
    "HP:0002529",  # Neuronal loss in central nervous system
}

# ---------------------------------------------------------------------------
# ACMG Secondary Findings v3.3 (PMID:37347242)
# Clinically actionable genes — findings empower the patient.
# These are EXCLUDED from the enhanced-warning list.
# ---------------------------------------------------------------------------

ACMG_SF_V3_3 = {
    # Hereditary cancer
    "APC",
    "BMPR1A",
    "BRCA1",
    "BRCA2",
    "BRIP1",
    "CDH1",
    "CDK4",
    "CDKN2A",
    "CHEK2",
    "DICER1",
    "EPCAM",
    "GREM1",
    "HOXB13",
    "KIT",
    "MAX",
    "MEN1",
    "MET",
    "MLH1",
    "MSH2",
    "MSH6",
    "MUTYH",
    "NF2",
    "NTHL1",
    "PALB2",
    "PDGFRA",
    "PMS2",
    "POLD1",
    "POLE",
    "PTEN",
    "RAD51C",
    "RAD51D",
    "RB1",
    "RET",
    "SDHA",
    "SDHAF2",
    "SDHB",
    "SDHC",
    "SDHD",
    "SMAD4",
    "STK11",
    "TMEM127",
    "TP53",
    "TSC1",
    "TSC2",
    "VHL",
    # Cardiovascular
    "ACTA2",
    "ACTC1",
    "APOB",
    "COL3A1",
    "DSC2",
    "DSG2",
    "DSP",
    "FBN1",
    "FLNC",
    "GLA",
    "HFE",
    "KCNH2",
    "KCNQ1",
    "LDLR",
    "LMNA",
    "MYBPC3",
    "MYH11",
    "MYH7",
    "MYL2",
    "MYL3",
    "PCSK9",
    "PKP2",
    "PLN",
    "RBM20",
    "RPE65",
    "RYR2",
    "SCN5A",
    "SMAD3",
    "TGFBR1",
    "TGFBR2",
    "TMEM43",
    "TNNC1",
    "TNNI3",
    "TNNT2",
    "TPM1",
    "TRDN",
    "TTN",
    "TTR",
    # Other
    "ATP7B",
    "BTD",
    "GAA",
    "OTC",
    "RYR1",
}


def fetch_clinvar_genes() -> set[str]:
    """Download ClinVar variant_summary and extract genes with Pathogenic variants.

    Filters:
    - Assembly = GRCh38
    - ClinicalSignificance contains "Pathogenic" (not just "Likely_pathogenic")
    - ReviewStatus != "no assertion criteria provided"
    """
    print("  Downloading ClinVar variant_summary.txt.gz (streaming)...")
    req = urllib.request.Request(CLINVAR_URL, headers={"User-Agent": "genechat/1.0"})
    genes: set[str] = set()
    with urllib.request.urlopen(req, timeout=120) as resp:
        gz_stream = gzip.GzipFile(fileobj=resp)
        text_stream = io.TextIOWrapper(gz_stream, encoding="utf-8", errors="replace")
        reader = csv.DictReader(text_stream, delimiter="\t")
        for row in reader:
            assembly = row.get("Assembly", "")
            if assembly != "GRCh38":
                continue
            sig = row.get("ClinicalSignificance", "")
            # Must contain "Pathogenic" as a standalone term (not just "Likely_pathogenic")
            sig_terms = [t.strip().lower() for t in sig.replace("/", ",").split(",")]
            if "pathogenic" not in sig_terms:
                continue
            review = row.get("ReviewStatus", "")
            if review == "no assertion criteria provided":
                continue
            gene_symbol = row.get("GeneSymbol", "").strip()
            if gene_symbol and gene_symbol != "-":
                genes.add(gene_symbol)

    print(f"  ClinVar: {len(genes)} genes with Pathogenic variants on GRCh38")
    return genes


def fetch_hpo_genes() -> set[str]:
    """Download HPO genes_to_phenotype and extract genes with target phenotypes."""
    print("  Downloading HPO genes_to_phenotype.txt...")
    req = urllib.request.Request(HPO_URL, headers={"User-Agent": "genechat/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    genes: set[str] = set()
    reader = csv.DictReader(
        (line for line in text.splitlines() if not line.startswith("#")),
        delimiter="\t",
    )
    for row in reader:
        hpo_id = row.get("hpo_id", "").strip()
        if hpo_id in HPO_TERMS:
            gene = row.get("gene_symbol", "").strip()
            if gene:
                genes.add(gene)

    print(f"  HPO: {len(genes)} genes with death/neurodegeneration phenotypes")
    return genes


def build_warning_list(
    clinvar_genes: set[str],
    hpo_genes: set[str],
) -> list[str]:
    """Intersect ClinVar and HPO, subtract ACMG SF v3.3."""
    intersection = clinvar_genes & hpo_genes
    print(f"  Intersection (ClinVar ∩ HPO): {len(intersection)} genes")

    result = sorted(intersection - ACMG_SF_V3_3)
    removed = intersection & ACMG_SF_V3_3
    if removed:
        print(
            f"  Removed {len(removed)} ACMG SF v3.3 actionable genes: {', '.join(sorted(removed))}"
        )
    print(f"  Final enhanced-warning gene list: {len(result)} genes")
    return result


def write_tsv(genes: list[str], output_path: Path) -> None:
    """Write enhanced_warning_genes.tsv."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        f.write(
            "# Enhanced-warning genes: ClinVar Pathogenic ∩ HPO death/neurodegeneration - ACMG SF v3.3\n"
        )
        f.write(
            "# Sources: ClinVar variant_summary, HPO genes_to_phenotype, ACMG SF v3.3\n"
        )
        writer = csv.DictWriter(
            f, fieldnames=["symbol"], delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for gene in genes:
            writer.writerow({"symbol": gene})
    print(f"  Written: {output_path} ({len(genes)} genes)")


def main(output_dir: Path | None = None) -> int:
    """Fetch and build enhanced-warning gene list. Returns 0 on success."""
    output_dir = output_dir or _DEFAULT_SEED_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "enhanced_warning_genes.tsv"

    print("Enhanced-Warning Gene List Pipeline")
    print("=" * 60)

    try:
        clinvar_genes = fetch_clinvar_genes()
        hpo_genes = fetch_hpo_genes()
        genes = build_warning_list(clinvar_genes, hpo_genes)
        write_tsv(genes, output_path)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        return 1

    # Validation: check known genes
    gene_set = set(genes)
    expected_present = {"HTT", "SOD1", "PRNP", "MAPT", "FUS", "TARDBP", "SNCA", "APP"}
    expected_absent = {"BRCA1", "BRCA2", "MLH1", "LDLR", "RYR1", "TP53"}

    missing = expected_present - gene_set
    wrongly_included = expected_absent & gene_set

    if missing:
        print(
            f"\n  WARNING: Expected genes missing from list: {', '.join(sorted(missing))}"
        )
    if wrongly_included:
        print(
            f"\n  WARNING: Actionable genes wrongly included: {', '.join(sorted(wrongly_included))}"
        )

    if not missing and not wrongly_included:
        print(
            "\n  Validation: all expected genes present, no actionable genes included"
        )

    return 0


if __name__ == "__main__":
    _dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(main(output_dir=_dir))
