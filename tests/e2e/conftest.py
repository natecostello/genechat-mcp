"""E2E test fixtures for GIAB NA12878 testing.

These tests are auto-skipped when GENECHAT_GIAB_VCF is not set.
To run:
    export GENECHAT_GIAB_VCF=./giab/HG001_annotated.vcf.gz
    uv run pytest tests/e2e/ -v
"""

import os
from pathlib import Path

import pytest

from genechat.config import AppConfig
from genechat.lookup import LookupDB
from genechat.vcf_engine import VCFEngine

GIAB_VCF_ENV = "GENECHAT_GIAB_VCF"
DB_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "genechat"
    / "data"
    / "lookup_tables.db"
)


def pytest_collection_modifyitems(config, items):
    """Auto-skip all e2e tests when GENECHAT_GIAB_VCF is not set."""
    vcf_path = os.environ.get(GIAB_VCF_ENV)
    if vcf_path and Path(vcf_path).exists():
        return

    skip_marker = pytest.mark.skip(
        reason=f"{GIAB_VCF_ENV} not set or file not found. "
        "Run: bash scripts/setup_giab.sh ./giab && "
        f"export {GIAB_VCF_ENV}=./giab/HG001_annotated.vcf.gz"
    )
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(skip_marker)


# --- Ground truth: known NA12878 genotypes ---
# Sources: PharmGKB GeT-RM, 1000 Genomes, published literature
#
# "absent" means homozygous reference — the variant is NOT in the VCF
# (correct VCF behavior: only non-reference genotypes are stored).

GROUND_TRUTH = {
    # CYP2D6 *4 — rs3892097 — intermediate metabolizer (*1/*4)
    # NA12878 is heterozygous for *4 allele
    "rs3892097": {
        "gene": "CYP2D6",
        "chrom": "chr22",
        "pos": 42128945,
        "expected_zygosity": "heterozygous",
        "notes": "CYP2D6 *4, intermediate metabolizer",
    },
    # VKORC1 -1639G>A — rs9923231 — intermediate warfarin dose
    "rs9923231": {
        "gene": "VKORC1",
        "chrom": "chr16",
        "pos": 31096368,
        "expected_zygosity": "heterozygous",
        "notes": "VKORC1 -1639G>A, intermediate warfarin sensitivity",
    },
    # MTHFR C677T — rs1801133 — heterozygous carrier
    "rs1801133": {
        "gene": "MTHFR",
        "chrom": "chr1",
        "pos": 11796321,
        "expected_zygosity": "heterozygous",
        "notes": "MTHFR C677T carrier",
    },
    # MCM6/LCT lactose tolerance — rs4988235 — heterozygous (lactose tolerant)
    "rs4988235": {
        "gene": "MCM6",
        "chrom": "chr2",
        "pos": 135851076,
        "expected_zygosity": "heterozygous",
        "notes": "Lactose tolerance variant",
    },
}

# Variants expected to be homozygous reference (absent from VCF)
GROUND_TRUTH_ABSENT = {
    # CYP2C19 *2 — rs4244285 — NA12878 is *1/*1 (normal metabolizer)
    "rs4244285": {
        "gene": "CYP2C19",
        "chrom": "chr10",
        "pos": 94781859,
        "notes": "CYP2C19 *1/*1, normal metabolizer",
    },
    # SLCO1B1 *5 — rs4149056 — NA12878 is T/T (normal function)
    "rs4149056": {
        "gene": "SLCO1B1",
        "chrom": "chr12",
        "pos": 21178615,
        "notes": "SLCO1B1 normal function",
    },
    # Factor V Leiden — rs6025 — NA12878 is negative
    "rs6025": {
        "gene": "F5",
        "chrom": "chr1",
        "pos": 169549811,
        "notes": "Factor V Leiden negative",
    },
    # APOE ε4 — rs429358 — NA12878 is ε3/ε3 (no ε4)
    "rs429358": {
        "gene": "APOE",
        "chrom": "chr19",
        "pos": 44908684,
        "notes": "APOE ε3/ε3 (no ε4 allele)",
    },
    # APOE ε2 — rs7412 — NA12878 is ε3/ε3 (no ε2)
    "rs7412": {
        "gene": "APOE",
        "chrom": "chr19",
        "pos": 44908822,
        "notes": "APOE ε3/ε3 (no ε2 allele)",
    },
}


@pytest.fixture(scope="session")
def giab_config():
    """AppConfig pointing to GIAB VCF and built-in lookup DB."""
    vcf_path = os.environ.get(GIAB_VCF_ENV, "")
    return AppConfig(
        genome={
            "vcf_path": vcf_path,
            "genome_build": "GRCh38",
        },
        databases={"lookup_db": str(DB_PATH)},
        server={"max_variants_per_response": 200},
    )


@pytest.fixture(scope="session")
def giab_engine(giab_config):
    """VCFEngine opened once for the entire test session."""
    return VCFEngine(giab_config)


@pytest.fixture(scope="session")
def giab_db(giab_config):
    """LookupDB opened once for the entire test session."""
    if not DB_PATH.exists():
        pytest.skip(
            "Lookup database not built. Run: uv run python scripts/build_lookup_db.py"
        )
    db = LookupDB(giab_config)
    yield db
    db.close()
