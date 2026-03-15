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
    """Always regenerate the test VCF to stay in sync with generate_test_vcf.py."""
    from scripts.generate_test_vcf import generate_vcf

    generate_vcf()


@pytest.fixture(scope="session", autouse=True)
def ensure_test_patch_db(ensure_test_vcf):
    """Build test patch.db from annotated test VCF if missing."""
    vcf_path = TEST_DATA / "test_sample.vcf.gz"
    patch_path = TEST_DATA / "test_sample.patch.db"
    if patch_path.exists():
        # Rebuild if VCF changed (e.g. new variants added) to avoid stale data
        from genechat.patch import PatchDB

        existing = PatchDB(patch_path, readonly=True)
        has_fingerprint = existing.get_vcf_fingerprint() is not None
        fingerprint_ok = has_fingerprint and existing.check_vcf_fingerprint(vcf_path)
        existing.close()
        if fingerprint_ok:
            return
        patch_path.unlink()  # stale — rebuild below
    if not vcf_path.exists():
        return  # VCF generation must have failed

    import pysam

    from genechat.patch import PatchDB

    # Extract annotations as VCF text lines for the stream parsers
    ann_lines = []
    with pysam.VariantFile(str(vcf_path)) as vcf:
        for record in vcf:
            alt = ",".join(record.alts) if record.alts else "."
            rsid = record.id if record.id and record.id != "." else "."
            info_parts = []
            for key in [
                "ANN",
                "CLNSIG",
                "CLNDN",
                "CLNREVSTAT",
                "AF",
                "AF_popmax",
                "AF_grpmax",
            ]:
                try:
                    val = record.info[key]
                except KeyError:
                    continue
                if val is None:
                    continue
                if isinstance(val, tuple):
                    val_str = ",".join(str(v) for v in val)
                else:
                    val_str = str(val)
                info_parts.append(f"{key}={val_str}")
            info = ";".join(info_parts) if info_parts else "."
            gt_alleles = record.samples[0]["GT"]
            gt_str = "/".join(str(a) for a in gt_alleles)
            line = (
                f"{record.chrom}\t{record.pos}\t{rsid}\t{record.ref}\t{alt}\t"
                f".\tPASS\t{info}\tGT\t{gt_str}\n"
            )
            ann_lines.append(line)

    # Simulate cross-tool contig mismatch (issue #60): SnpEff strips chr
    # prefix while bcftools (ClinVar, gnomAD) preserves it
    snpeff_lines = []
    for line in ann_lines:
        if line.startswith("chr"):
            line = line[3:]  # "chr1\t..." -> "1\t..."
        snpeff_lines.append(line)

    db = PatchDB.create(patch_path)
    db.populate_from_snpeff_stream(iter(snpeff_lines))
    # ClinVar and gnomAD streams keep chr prefix (bcftools behavior)
    db.update_clinvar_from_stream(iter(ann_lines))
    db.update_gnomad_from_stream(iter(ann_lines))
    db.store_vcf_fingerprint(vcf_path)
    db.set_metadata("snpeff", "test")
    db.set_metadata("clinvar", "test")
    db.set_metadata("gnomad", "test")
    db.close()


@pytest.fixture
def test_config():
    """Config pointing to test data."""
    return AppConfig(
        genomes={
            "default": {
                "vcf_path": str(TEST_DATA / "test_sample.vcf.gz"),
                "genome_build": "GRCh38",
                "patch_db": str(TEST_DATA / "test_sample.patch.db"),
            },
        },
        databases={"lookup_db": str(DB_PATH)},
        server={"max_variants_per_response": 100},
    )


@pytest.fixture
def test_db(test_config):
    """LookupDB using the built package database."""
    if not DB_PATH.exists():
        pytest.skip("Lookup database not built. Run: python scripts/build_lookup_db.py")
    # Verify DB has actual tables (not just an empty file)
    import sqlite3

    try:
        conn = sqlite3.connect(str(DB_PATH))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        if not tables:
            pytest.skip(
                "Lookup database is empty. Rebuild: python scripts/build_lookup_db.py"
            )
    except sqlite3.DatabaseError:
        pytest.skip(
            "Lookup database is corrupt. Rebuild: python scripts/build_lookup_db.py"
        )
    db = LookupDB(test_config)
    yield db
    db.close()


@pytest.fixture
def mock_engine():
    """Mock VCFEngine for tool tests (no VCF required)."""
    engine = MagicMock()
    engine.max_variants = 100
    engine.annotation_versions.return_value = {}
    return engine


@pytest.fixture
def mock_engine2():
    """Second mock VCFEngine for multi-genome / genome2 tests."""
    engine = MagicMock()
    engine.max_variants = 100
    engine.annotation_versions.return_value = {}
    return engine


@pytest.fixture
def mock_engines(mock_engine):
    """Engines dict wrapping mock_engine as 'default'."""
    return {"default": mock_engine}


@pytest.fixture
def mock_engines_multi(mock_engine, mock_engine2):
    """Engines dict with two genomes for paired-query tests."""
    return {"default": mock_engine, "partner": mock_engine2}


@pytest.fixture
def test_config_multi():
    """Config with two genomes for paired-query tests."""
    return AppConfig(
        genomes={
            "default": {
                "vcf_path": str(TEST_DATA / "test_sample.vcf.gz"),
                "genome_build": "GRCh38",
                "patch_db": str(TEST_DATA / "test_sample.patch.db"),
            },
            "partner": {
                "vcf_path": str(TEST_DATA / "test_sample.vcf.gz"),
                "genome_build": "GRCh38",
                "patch_db": str(TEST_DATA / "test_sample.patch.db"),
            },
        },
        databases={"lookup_db": str(DB_PATH)},
        server={"max_variants_per_response": 100},
    )


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
