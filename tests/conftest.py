"""Test fixtures for GeneChat."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from genechat.config import AppConfig
from genechat.lookup import LookupDB

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA = Path(__file__).resolve().parent / "data"
DB_PATH = REPO_ROOT / "src" / "genechat" / "data" / "lookup_tables.db"


@pytest.fixture(scope="session", autouse=True)
def ensure_test_vcf():
    """Auto-generate the test VCF if missing (session-scoped, runs once)."""
    gz_path = TEST_DATA / "test_sample.vcf.gz"
    tbi_path = TEST_DATA / "test_sample.vcf.gz.tbi"
    if not gz_path.exists() or not tbi_path.exists():
        from scripts.generate_test_vcf import generate_vcf

        generate_vcf()


@pytest.fixture
def test_config():
    """Config pointing to test data."""
    return AppConfig(
        genome={
            "vcf_path": str(TEST_DATA / "test_sample.vcf.gz"),
            "genome_build": "GRCh38",
        },
        databases={"lookup_db": str(DB_PATH)},
        server={"max_variants_per_response": 100},
    )


@pytest.fixture
def test_db(test_config):
    """LookupDB using the built package database."""
    if not DB_PATH.exists():
        pytest.skip("Lookup database not built. Run: python scripts/build_lookup_db.py")
    db = LookupDB(test_config)
    yield db
    db.close()


@pytest.fixture
def mock_engine():
    """Mock VCFEngine for tool tests (no VCF required)."""
    engine = MagicMock()
    engine.max_variants = 100
    return engine


# Sample variant dicts for testing
SAMPLE_VARIANT_SLCO1B1 = {
    "chrom": "chr12",
    "pos": 21178615,
    "rsid": "rs4149056",
    "ref": "T",
    "alt": "C",
    "genotype": {"display": "T/C", "zygosity": "heterozygous"},
    "annotation": {
        "gene": "SLCO1B1",
        "effect": "missense_variant",
        "impact": "MODERATE",
        "transcript": "ENST00000256958",
        "hgvs_c": "c.521T>C",
        "hgvs_p": "p.Val174Ala",
    },
    "clinvar": {
        "significance": "drug response",
        "condition": "Simvastatin response",
        "review_status": "criteria provided, multiple submitters, no conflicts",
    },
    "population_freq": {"global": 0.14, "popmax": 0.21},
}

SAMPLE_VARIANT_CFTR = {
    "chrom": "chr7",
    "pos": 117559590,
    "rsid": "rs113993960",
    "ref": "ATCT",
    "alt": "A",
    "genotype": {"display": "ATCT/A", "zygosity": "heterozygous"},
    "annotation": {
        "gene": "CFTR",
        "effect": "frameshift_variant",
        "impact": "HIGH",
        "transcript": "ENST00000003084",
        "hgvs_c": "c.1521_1523del",
        "hgvs_p": "p.Phe508del",
    },
    "clinvar": {
        "significance": "Pathogenic",
        "condition": "Cystic fibrosis",
        "review_status": "reviewed by expert panel",
    },
    "population_freq": {"global": 0.02, "popmax": 0.04},
}
