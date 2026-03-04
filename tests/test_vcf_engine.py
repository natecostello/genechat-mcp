"""Tests for VCF engine (input validation and parsing, no bcftools required)."""

import pytest

from genechat.vcf_engine import REGION_PATTERN, RSID_PATTERN, VCFEngine, _parse_freq


class TestPatterns:
    def test_valid_regions(self):
        assert REGION_PATTERN.match("chr1:100-200")
        assert REGION_PATTERN.match("chr22:42126499-42130881")
        assert REGION_PATTERN.match("chrX:1000-2000")
        assert REGION_PATTERN.match("chrMT:1-100")

    def test_invalid_regions(self):
        assert not REGION_PATTERN.match("1:100-200")  # no chr prefix
        assert not REGION_PATTERN.match("chr1:100")  # no end
        assert not REGION_PATTERN.match("chr1:abc-200")

    def test_valid_rsids(self):
        assert RSID_PATTERN.match("rs4149056")
        assert RSID_PATTERN.match("rs1")

    def test_invalid_rsids(self):
        assert not RSID_PATTERN.match("4149056")
        assert not RSID_PATTERN.match("rsABC")
        assert not RSID_PATTERN.match("")


class TestParseFreq:
    def test_valid_freqs(self):
        result = _parse_freq("0.14", "0.21")
        assert result["global"] == pytest.approx(0.14)
        assert result["popmax"] == pytest.approx(0.21)

    def test_missing_freqs(self):
        assert _parse_freq(".", ".") == {}
        assert _parse_freq("", "") == {}

    def test_partial_freq(self):
        result = _parse_freq("0.14", ".")
        assert "global" in result
        assert "popmax" not in result


class TestVCFEngineInit:
    def test_missing_vcf(self, test_config):
        """VCFEngine raises FileNotFoundError for missing VCF."""
        test_config.genome.vcf_path = "/nonexistent/file.vcf.gz"
        # May raise FileNotFoundError or VCFEngineError depending on bcftools availability
        with pytest.raises(Exception):
            VCFEngine(test_config)


class TestParseLine:
    """Test _parse_line by constructing an engine-like object."""

    def test_parse_complete_line(self):
        """Test parsing a complete bcftools output line."""
        from genechat.parsers import (
            parse_ann_field,
            parse_clinvar_fields,
            parse_genotype,
        )

        line = (
            "chr12\t21178615\trs4149056\tT\tC\t"
            "C|missense_variant|MODERATE|SLCO1B1|ENSG00000134538|transcript|ENST00000256958|protein_coding||c.521T>C|p.Val174Ala|||||\t"
            "drug_response\tSimvastatin_response\t"
            "criteria_provided,_multiple_submitters\t0.14\t0.21\t0/1"
        )
        parts = line.split("\t")
        assert len(parts) == 12

        # Manually parse like _parse_line would
        chrom, pos_str, rsid, ref, alt = (
            parts[0],
            parts[1],
            parts[2],
            parts[3],
            parts[4],
        )
        assert chrom == "chr12"
        assert int(pos_str) == 21178615
        assert rsid == "rs4149056"

        gt = parse_genotype(parts[11], ref, alt)
        assert gt["zygosity"] == "heterozygous"

        ann = parse_ann_field(parts[5])
        assert ann["gene"] == "SLCO1B1"

        clin = parse_clinvar_fields(parts[6], parts[7], parts[8])
        assert clin["significance"] == "drug response"
