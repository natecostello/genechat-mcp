"""Tests for VCF engine (pysam-based, integration tests against test VCF)."""

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
        result = _parse_freq(0.14, 0.21)
        assert result["global"] == pytest.approx(0.14)
        assert result["popmax"] == pytest.approx(0.21)

    def test_missing_freqs(self):
        assert _parse_freq(None, None) == {}

    def test_partial_freq(self):
        result = _parse_freq(0.14, None)
        assert "global" in result
        assert "popmax" not in result


class TestVCFEngineInit:
    def test_missing_vcf(self, test_config):
        """VCFEngine raises FileNotFoundError for missing VCF."""
        test_config.genome.vcf_path = "/nonexistent/file.vcf.gz"
        with pytest.raises(FileNotFoundError):
            VCFEngine(test_config)


class TestAnnotationVersions:
    def test_returns_dict(self, test_config):
        """annotation_versions() returns a dict (empty if no GeneChat_ headers)."""
        engine = VCFEngine(test_config)
        result = engine.annotation_versions()
        assert isinstance(result, dict)

    def test_custom_prefix(self, test_config):
        """annotation_versions() accepts a custom prefix."""
        engine = VCFEngine(test_config)
        result = engine.annotation_versions(prefix="NonExistent_")
        assert result == {}


class TestQueryRegion:
    """Integration tests querying known variants from the test VCF."""

    def test_query_slco1b1_region(self, test_config):
        engine = VCFEngine(test_config)
        # SLCO1B1 rs4149056 is at chr12:21178615
        variants = engine.query_region("chr12:21178600-21178700")
        assert len(variants) == 1
        v = variants[0]
        assert v["rsid"] == "rs4149056"
        assert v["chrom"] == "chr12"
        assert v["pos"] == 21178615
        assert v["ref"] == "T"
        assert v["alt"] == "C"
        assert v["genotype"]["zygosity"] == "heterozygous"
        assert v["annotation"]["gene"] == "SLCO1B1"
        assert v["annotation"]["effect"] == "missense_variant"
        assert v["clinvar"]["significance"] == "drug response"
        assert v["population_freq"]["global"] == pytest.approx(0.14)

    def test_query_cftr_region(self, test_config):
        engine = VCFEngine(test_config)
        variants = engine.query_region("chr7:117559580-117559600")
        assert len(variants) == 1
        v = variants[0]
        assert v["rsid"] == "rs113993960"
        assert v["annotation"]["gene"] == "CFTR"
        assert v["annotation"]["impact"] == "HIGH"
        assert v["clinvar"]["significance"] == "Pathogenic"

    def test_query_empty_region(self, test_config):
        engine = VCFEngine(test_config)
        variants = engine.query_region("chr1:1-10")
        assert variants == []

    def test_invalid_region_raises(self, test_config):
        engine = VCFEngine(test_config)
        with pytest.raises(ValueError, match="Invalid region"):
            engine.query_region("1:100-200")


class TestQueryRsid:
    def test_query_known_rsid(self, test_config):
        engine = VCFEngine(test_config)
        variants = engine.query_rsid("rs4149056")
        assert len(variants) == 1
        assert variants[0]["rsid"] == "rs4149056"
        assert variants[0]["genotype"]["zygosity"] == "heterozygous"

    def test_query_missing_rsid(self, test_config):
        engine = VCFEngine(test_config)
        variants = engine.query_rsid("rs999999999")
        assert variants == []

    def test_invalid_rsid_raises(self, test_config):
        engine = VCFEngine(test_config)
        with pytest.raises(ValueError, match="Invalid rsID"):
            engine.query_rsid("notanrsid")


class TestQueryClinvar:
    def test_query_pathogenic(self, test_config):
        engine = VCFEngine(test_config)
        variants = engine.query_clinvar("Pathogenic")
        # Test VCF has: DPYD, F5, HFE, CFTR as Pathogenic
        assert len(variants) >= 3
        genes = {v["annotation"].get("gene") for v in variants}
        assert "CFTR" in genes
        assert "DPYD" in genes

    def test_query_drug_response(self, test_config):
        engine = VCFEngine(test_config)
        variants = engine.query_clinvar("drug_response")
        assert len(variants) >= 1
        rsids = {v["rsid"] for v in variants}
        assert "rs4149056" in rsids  # SLCO1B1

    def test_query_clinvar_with_region(self, test_config):
        engine = VCFEngine(test_config)
        variants = engine.query_clinvar(
            "drug_response", region="chr12:21178600-21178700"
        )
        assert len(variants) == 1
        assert variants[0]["rsid"] == "rs4149056"


class TestQueryRegions:
    def test_multiple_regions(self, test_config):
        engine = VCFEngine(test_config)
        variants = engine.query_regions(
            [
                "chr12:21178600-21178700",  # SLCO1B1
                "chr7:117559580-117559600",  # CFTR
            ]
        )
        assert len(variants) == 2
        rsids = {v["rsid"] for v in variants}
        assert rsids == {"rs4149056", "rs113993960"}


class TestStats:
    def test_stats_returns_counts(self, test_config):
        engine = VCFEngine(test_config)
        result = engine.stats()
        assert isinstance(result, dict)
        assert result["Total variants"] == 26
        assert result["SNPs"] > 0


class TestAfGrpmaxFallback:
    """Test gnomAD v4 AF_grpmax → popmax fallback."""

    def test_af_grpmax_fallback(self, test_config):
        engine = VCFEngine(test_config)
        # rs6053810 has AF_grpmax=0.18 but no AF_popmax
        variants = engine.query_rsid("rs6053810")
        assert len(variants) == 1
        v = variants[0]
        assert v["population_freq"]["popmax"] == pytest.approx(0.18)
        assert v["population_freq"]["global"] == pytest.approx(0.15)

    def test_af_popmax_preferred_over_grpmax(self, test_config):
        engine = VCFEngine(test_config)
        # rs4149056 has AF_popmax=0.21 — should use that, not AF_grpmax
        variants = engine.query_rsid("rs4149056")
        assert len(variants) == 1
        assert variants[0]["population_freq"]["popmax"] == pytest.approx(0.21)


class TestMaxVariantsCap:
    def test_cap_limits_results(self, test_config):
        test_config.server.max_variants_per_response = 3
        engine = VCFEngine(test_config)
        # Query ClinVar Pathogenic — should hit cap at 3
        variants = engine.query_clinvar("Pathogenic")
        assert len(variants) == 3
        assert variants[-1].get("_truncated") is True
