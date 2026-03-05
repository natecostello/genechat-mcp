"""Unit tests for setup_giab.py helper functions.

Tests the pure functions (chr mapping, ClinVar parsing, chrom prefix fix)
without downloading any files.
"""

import sys
from pathlib import Path

# Add scripts directory to path so we can import setup_giab
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from unittest.mock import MagicMock

from setup_giab import (
    CHR_TO_REFSEQ,
    REFSEQ_TO_CHR,
    fix_chrom,
    lookup_clinvar,
    parse_clinvar_info,
)


class TestFixChrom:
    def test_bare_number(self):
        assert fix_chrom("1") == "chr1"

    def test_bare_x(self):
        assert fix_chrom("X") == "chrX"

    def test_bare_mt(self):
        assert fix_chrom("MT") == "chrMT"

    def test_already_prefixed(self):
        assert fix_chrom("chr1") == "chr1"

    def test_already_prefixed_x(self):
        assert fix_chrom("chrX") == "chrX"

    def test_two_digit(self):
        assert fix_chrom("22") == "chr22"


class TestChrToRefseq:
    def test_all_autosomes_present(self):
        for i in range(1, 23):
            assert str(i) in CHR_TO_REFSEQ

    def test_sex_chromosomes(self):
        assert "X" in CHR_TO_REFSEQ
        assert "Y" in CHR_TO_REFSEQ

    def test_mt(self):
        assert "MT" in CHR_TO_REFSEQ

    def test_refseq_format(self):
        for chrom, refseq in CHR_TO_REFSEQ.items():
            assert refseq.startswith("NC_"), f"Bad RefSeq for {chrom}: {refseq}"

    def test_reverse_map_consistent(self):
        for chrom, refseq in CHR_TO_REFSEQ.items():
            assert REFSEQ_TO_CHR[refseq] == chrom


class TestParseClinvarInfo:
    def test_all_fields_present(self):
        info = "DP=30;CLNSIG=Pathogenic;CLNDN=Cystic_fibrosis;CLNREVSTAT=reviewed_by_expert_panel;AF=0.02"
        result = parse_clinvar_info(info)
        assert result["CLNSIG"] == "Pathogenic"
        assert result["CLNDN"] == "Cystic_fibrosis"
        assert result["CLNREVSTAT"] == "reviewed_by_expert_panel"

    def test_only_clnsig(self):
        info = "CLNSIG=Benign"
        result = parse_clinvar_info(info)
        assert result == {"CLNSIG": "Benign"}
        assert "CLNDN" not in result

    def test_no_clinvar_fields(self):
        info = "DP=30;AF=0.5"
        result = parse_clinvar_info(info)
        assert result == {}

    def test_empty_info(self):
        result = parse_clinvar_info(".")
        assert result == {}

    def test_flag_field_without_equals(self):
        info = "CLNSIG=risk_factor;DB;CLNDN=some_condition"
        result = parse_clinvar_info(info)
        assert result["CLNSIG"] == "risk_factor"
        assert result["CLNDN"] == "some_condition"

    def test_complex_significance(self):
        info = "CLNSIG=Pathogenic/Likely_pathogenic;CLNDN=Hereditary_breast_cancer"
        result = parse_clinvar_info(info)
        assert result["CLNSIG"] == "Pathogenic/Likely_pathogenic"


def _make_mock_tabix(contig_prefix=""):
    """Create a mock TabixFile that only responds to a specific contig prefix.

    If contig_prefix is "" (bare), fetch("1", ...) works but fetch("chr1", ...) raises.
    If contig_prefix is "chr", fetch("chr1", ...) works but fetch("1", ...) raises.
    """
    clinvar_line = (
        "1\t11796321\trs1801133\tG\tA\t.\t.\t"
        "CLNSIG=drug_response;CLNDN=MTHFR_variant;CLNREVSTAT=reviewed_by_expert_panel"
    )

    def mock_fetch(contig, start, end):
        # Only respond to the expected contig format
        if contig_prefix == "" and contig.startswith("chr"):
            raise ValueError(f"could not create iterator for region '{contig}'")
        if contig_prefix == "chr" and not contig.startswith("chr"):
            raise ValueError(f"could not create iterator for region '{contig}'")
        # Only return data for the right position
        if start == 11796320 and end == 11796321:
            return [clinvar_line]
        return []

    tbx = MagicMock()
    tbx.fetch = mock_fetch
    return tbx


class TestLookupClinvar:
    def test_bare_contig_fallback(self):
        """ClinVar with bare contigs (1, 2, ...) should be found via fallback."""
        tbx = _make_mock_tabix(contig_prefix="")
        result = lookup_clinvar(tbx, "chr1", 11796321, "G", "A")
        assert result["CLNSIG"] == "drug_response"

    def test_chr_contig_direct(self):
        """ClinVar with chr-prefixed contigs should be found directly."""
        tbx = _make_mock_tabix(contig_prefix="chr")
        result = lookup_clinvar(tbx, "chr1", 11796321, "G", "A")
        assert result["CLNSIG"] == "drug_response"

    def test_no_match_returns_empty(self):
        """Variant not in ClinVar returns empty dict."""
        tbx = _make_mock_tabix(contig_prefix="")
        result = lookup_clinvar(tbx, "chr1", 99999999, "G", "A")
        assert result == {}

    def test_wrong_alt_returns_empty(self):
        """Matching position but wrong alt allele returns empty dict."""
        tbx = _make_mock_tabix(contig_prefix="")
        result = lookup_clinvar(tbx, "chr1", 11796321, "G", "T")
        assert result == {}
