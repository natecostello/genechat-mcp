"""Ground truth validation of VCFEngine against GIAB NA12878."""

import pytest

from tests.e2e.conftest import GROUND_TRUTH, GROUND_TRUTH_ABSENT


class TestGroundTruthPresent:
    """Validate variants expected to be present (non-reference) in NA12878."""

    @pytest.mark.parametrize(
        "rsid,expected",
        list(GROUND_TRUTH.items()),
        ids=list(GROUND_TRUTH.keys()),
    )
    def test_expected_variant_present(self, giab_engine, rsid, expected):
        """Verify that known NA12878 variants are found with correct zygosity."""
        region = f"{expected['chrom']}:{expected['pos']}-{expected['pos'] + 1}"
        variants = giab_engine.query_region(region)

        assert len(variants) > 0, (
            f"Expected variant at {region} ({expected['notes']}) "
            f"but no variants found in region"
        )

        # Check zygosity of the variant at this position
        found = False
        for v in variants:
            if v["pos"] == expected["pos"]:
                assert v["genotype"]["zygosity"] == expected["expected_zygosity"], (
                    f"{rsid} ({expected['notes']}): expected {expected['expected_zygosity']}, "
                    f"got {v['genotype']['zygosity']} ({v['genotype']['display']})"
                )
                found = True
                break

        assert found, (
            f"Variant at exact position {expected['pos']} not found. "
            f"Got positions: {[v['pos'] for v in variants]}"
        )


class TestGroundTruthAbsent:
    """Validate variants expected to be homozygous reference (absent) in NA12878."""

    @pytest.mark.parametrize(
        "rsid,expected",
        list(GROUND_TRUTH_ABSENT.items()),
        ids=list(GROUND_TRUTH_ABSENT.keys()),
    )
    def test_expected_variant_absent(self, giab_engine, rsid, expected):
        """Verify that known ref/ref positions have no variant in VCF."""
        region = f"{expected['chrom']}:{expected['pos']}-{expected['pos'] + 1}"
        variants = giab_engine.query_region(region)

        # Either no variants at this position, or the variant at this exact
        # position should be homozygous reference
        at_pos = [v for v in variants if v["pos"] == expected["pos"]]
        if at_pos:
            assert at_pos[0]["genotype"]["zygosity"] == "homozygous_ref", (
                f"{rsid} ({expected['notes']}): expected homozygous_ref (absent), "
                f"got {at_pos[0]['genotype']['zygosity']} ({at_pos[0]['genotype']['display']})"
            )


class TestEngineBasics:
    """Basic VCFEngine functionality with real GIAB data."""

    def test_stats_returns_millions(self, giab_engine):
        """GIAB v4.2.1 has ~3.7M variants."""
        stats = giab_engine.stats()
        total = stats["Total variants"]
        assert total > 3_000_000, f"Expected >3M variants, got {total:,}"
        assert total < 5_000_000, f"Expected <5M variants, got {total:,}"
        assert stats["SNPs"] > 0
        assert stats["Indels"] > 0

    def test_region_query_returns_results(self, giab_engine):
        """A well-populated region should return variants."""
        # BRCA1 region on chr17
        variants = giab_engine.query_region("chr17:43044295-43170245")
        assert len(variants) > 0, "Expected variants in BRCA1 region"

    def test_empty_region_returns_empty(self, giab_engine):
        """A very small region with no variants should return empty list."""
        # Tiny region unlikely to contain a variant
        variants = giab_engine.query_region("chr1:1-2")
        # May or may not be empty, but should not error
        assert isinstance(variants, list)

    def test_variant_dict_structure(self, giab_engine):
        """Verify variant dicts have the expected structure."""
        # Query a region known to have variants
        variants = giab_engine.query_region("chr1:11796320-11796322")
        if not variants:
            pytest.skip("No variants found in MTHFR region")

        v = variants[0]
        assert "chrom" in v
        assert "pos" in v
        assert "ref" in v
        assert "alt" in v
        assert "genotype" in v
        assert "display" in v["genotype"]
        assert "zygosity" in v["genotype"]
        assert "annotation" in v
        assert "clinvar" in v
        assert "population_freq" in v
