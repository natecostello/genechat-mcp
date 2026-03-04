"""Unit tests for setup_giab.py helper functions.

Tests the pure functions (chr mapping, ClinVar parsing, chrom prefix fix)
without downloading any files.
"""

import sys
from pathlib import Path

# Add scripts directory to path so we can import setup_giab
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from setup_giab import CHR_TO_REFSEQ, REFSEQ_TO_CHR, fix_chrom, parse_clinvar_info


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
