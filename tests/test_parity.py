"""Parity tests: annotated VCF output == raw VCF + patch.db output.

Proves that the patch-mode engine produces identical results to the
legacy annotated-VCF engine for all query methods.
"""

from pathlib import Path

import pysam
import pytest

from genechat.config import AppConfig
from genechat.patch import PatchDB
from genechat.vcf_engine import VCFEngine

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA = Path(__file__).resolve().parent / "data"


def _build_raw_vcf_and_patch(tmp_path: Path, annotated_vcf: Path) -> tuple[Path, Path]:
    """Build a raw VCF (no INFO) + patch.db from an annotated VCF.

    Reads the annotated test VCF, strips all INFO fields to create
    a raw VCF, and populates a patch.db with the annotations.
    """
    raw_vcf_path = tmp_path / "raw.vcf.gz"
    patch_db_path = tmp_path / "patch.db"

    # Read annotated VCF, write raw VCF (no INFO) and collect annotation lines
    src = pysam.VariantFile(str(annotated_vcf))

    # Build a clean header without INFO fields
    new_header = pysam.VariantHeader()
    new_header.add_sample(src.header.samples[0])
    for contig in src.header.contigs:
        new_header.contigs.add(contig, length=src.header.contigs[contig].length)
    new_header.add_line('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">')

    # Write raw VCF
    with pysam.VariantFile(str(raw_vcf_path), "wz", header=new_header) as out:
        for record in src:
            new_rec = out.new_record(
                contig=record.chrom,
                start=record.start,
                stop=record.stop,
                alleles=record.alleles,
                id=None,  # strip rsID — it will come from patch.db
                qual=record.qual,
                filter=None,
            )
            # Copy genotype
            new_rec.samples[0]["GT"] = record.samples[0]["GT"]
            new_rec.samples[0].phased = record.samples[0].phased
            out.write(new_rec)

    src.close()
    pysam.tabix_index(str(raw_vcf_path), preset="vcf", force=True)

    # Build patch.db from the annotated VCF's text representation
    db = PatchDB.create(patch_db_path)

    # Re-read the annotated VCF as text lines for the stream parser
    ann_lines = []
    with pysam.VariantFile(str(annotated_vcf)) as vcf:
        for record in vcf:
            alt = ",".join(record.alts) if record.alts else "."
            rsid = record.id if record.id and record.id != "." else "."

            # Reconstruct INFO string
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

            # Build VCF line
            line = (
                f"{record.chrom}\t{record.pos}\t{rsid}\t{record.ref}\t{alt}\t"
                f".\tPASS\t{info}\tGT\t{'/'.join(str(a) for a in record.samples[0]['GT'])}\n"
            )
            ann_lines.append(line)

    # Step 1: SnpEff (creates rows with ANN data + rsID)
    db.populate_from_snpeff_stream(iter(ann_lines))

    # Step 2: ClinVar (updates CLNSIG/CLNDN/CLNREVSTAT)
    db.update_clinvar_from_stream(iter(ann_lines))

    # Step 3: gnomAD (updates AF/AF_grpmax)
    db.update_gnomad_from_stream(iter(ann_lines))

    # Store fingerprint
    db.store_vcf_fingerprint(raw_vcf_path)
    db.set_metadata("snpeff", "test")
    db.set_metadata("clinvar", "test")
    db.set_metadata("gnomad", "test")
    db.close()

    return raw_vcf_path, patch_db_path


@pytest.fixture(scope="module")
def parity_engines(tmp_path_factory):
    """Create both legacy and patch engines for parity testing."""
    annotated_vcf = TEST_DATA / "test_sample.vcf.gz"
    if not annotated_vcf.exists():
        pytest.skip("Test VCF not found")

    tmp_path = tmp_path_factory.mktemp("parity")
    raw_vcf_path, patch_db_path = _build_raw_vcf_and_patch(tmp_path, annotated_vcf)

    db_path = REPO_ROOT / "src" / "genechat" / "data" / "lookup_tables.db"

    legacy_config = AppConfig(
        genome={"vcf_path": str(annotated_vcf), "genome_build": "GRCh38"},
        databases={"lookup_db": str(db_path)},
        server={"max_variants_per_response": 100},
    )
    patch_config = AppConfig(
        genome={
            "vcf_path": str(raw_vcf_path),
            "genome_build": "GRCh38",
            "patch_db": str(patch_db_path),
        },
        databases={"lookup_db": str(db_path)},
        server={"max_variants_per_response": 100},
    )

    legacy = VCFEngine(legacy_config)
    patch = VCFEngine(patch_config)
    assert patch._use_patch is True

    return legacy, patch


def _normalize_variant(v: dict) -> dict:
    """Strip ephemeral keys for comparison."""
    out = dict(v)
    out.pop("_truncated", None)
    out.pop("_truncation_notice", None)
    return out


def _compare_variants(legacy_list: list[dict], patch_list: list[dict]):
    """Assert two variant lists are equivalent."""
    assert len(legacy_list) == len(patch_list), (
        f"Count mismatch: legacy={len(legacy_list)}, patch={len(patch_list)}"
    )
    for lv, pv in zip(legacy_list, patch_list):
        ln = _normalize_variant(lv)
        pn = _normalize_variant(pv)
        # Compare key fields
        assert ln["chrom"] == pn["chrom"]
        assert ln["pos"] == pn["pos"]
        assert ln["rsid"] == pn["rsid"]
        assert ln["ref"] == pn["ref"]
        assert ln["alt"] == pn["alt"]
        assert ln["genotype"] == pn["genotype"]
        assert ln["annotation"] == pn["annotation"], (
            f"Annotation mismatch at {ln['chrom']}:{ln['pos']}: "
            f"legacy={ln['annotation']}, patch={pn['annotation']}"
        )
        assert ln["clinvar"] == pn["clinvar"], (
            f"ClinVar mismatch at {ln['chrom']}:{ln['pos']}: "
            f"legacy={ln['clinvar']}, patch={pn['clinvar']}"
        )
        # Population freq: compare available keys
        for key in ("global", "popmax"):
            lf = ln["population_freq"].get(key)
            pf = pn["population_freq"].get(key)
            if lf is not None and pf is not None:
                assert lf == pytest.approx(pf, abs=0.001), (
                    f"Freq mismatch for {key} at {ln['chrom']}:{ln['pos']}"
                )


class TestParityQueryRegion:
    def test_slco1b1_region(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_region("chr12:21178600-21178700")
        pv = patch.query_region("chr12:21178600-21178700")
        _compare_variants(lv, pv)
        assert len(lv) == 1
        assert lv[0]["rsid"] == "rs4149056"

    def test_cftr_region(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_region("chr7:117559580-117559600")
        pv = patch.query_region("chr7:117559580-117559600")
        _compare_variants(lv, pv)
        assert len(lv) == 1

    def test_empty_region(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_region("chr1:1-10")
        pv = patch.query_region("chr1:1-10")
        assert lv == pv == []


class TestParityQueryRsid:
    def test_known_rsid(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_rsid("rs4149056")
        pv = patch.query_rsid("rs4149056")
        _compare_variants(lv, pv)

    def test_missing_rsid(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_rsid("rs999999999")
        pv = patch.query_rsid("rs999999999")
        assert lv == pv == []

    def test_cftr_rsid(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_rsid("rs113993960")
        pv = patch.query_rsid("rs113993960")
        _compare_variants(lv, pv)


class TestParityQueryClinvar:
    def test_pathogenic(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_clinvar("Pathogenic")
        pv = patch.query_clinvar("Pathogenic")
        _compare_variants(lv, pv)
        assert len(lv) >= 3

    def test_drug_response(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_clinvar("drug_response")
        pv = patch.query_clinvar("drug_response")
        _compare_variants(lv, pv)

    def test_clinvar_with_region(self, parity_engines):
        legacy, patch = parity_engines
        lv = legacy.query_clinvar("drug_response", region="chr12:21178600-21178700")
        pv = patch.query_clinvar("drug_response", region="chr12:21178600-21178700")
        _compare_variants(lv, pv)


class TestParityQueryRegions:
    def test_multiple_regions(self, parity_engines):
        legacy, patch = parity_engines
        regions = [
            "chr12:21178600-21178700",
            "chr7:117559580-117559600",
        ]
        lv = legacy.query_regions(regions)
        pv = patch.query_regions(regions)
        _compare_variants(lv, pv)


class TestParityStats:
    def test_stats_match(self, parity_engines):
        legacy, patch = parity_engines
        ls = legacy.stats()
        ps = patch.stats()
        # Stats are computed from VCF structure, not annotations
        # Raw VCF has same records, so counts should match
        assert ls["Total variants"] == ps["Total variants"]
        assert ls["SNPs"] == ps["SNPs"]
        assert ls["Indels"] == ps["Indels"]


class TestParityAnnotationVersions:
    def test_patch_has_versions(self, parity_engines):
        _, patch = parity_engines
        versions = patch.annotation_versions()
        assert "Snpeff" in versions
        assert "Clinvar" in versions
        assert "Gnomad" in versions
