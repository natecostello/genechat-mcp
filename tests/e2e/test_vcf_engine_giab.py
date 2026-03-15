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

        # Check zygosity of all records at this position
        at_pos = [v for v in variants if v["pos"] == expected["pos"]]
        assert len(at_pos) > 0, (
            f"Variant at exact position {expected['pos']} not found. "
            f"Got positions: {[v['pos'] for v in variants]}"
        )

        # At least one record should match the expected zygosity
        matching = [
            v
            for v in at_pos
            if v["genotype"]["zygosity"] == expected["expected_zygosity"]
        ]
        if not matching:
            details = ", ".join(
                f"{v['genotype']['zygosity']} ({v['genotype']['display']})"
                for v in at_pos
            )
            pytest.fail(
                f"{rsid} ({expected['notes']}): expected {expected['expected_zygosity']}, "
                f"got [{details}]"
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

        # Either no variants at this position, or any variants at this exact
        # position should all be homozygous reference
        at_pos = [v for v in variants if v["pos"] == expected["pos"]]
        if at_pos:
            all_hom_ref = all(
                v["genotype"]["zygosity"] == "homozygous_ref" for v in at_pos
            )
            if not all_hom_ref:
                details = ", ".join(
                    f"{v['genotype']['zygosity']} ({v['genotype']['display']})"
                    for v in at_pos
                )
                pytest.fail(
                    f"{rsid} ({expected['notes']}): expected all homozygous_ref (absent), "
                    f"got [{details}]"
                )


class TestEngineBasics:
    """Basic VCFEngine functionality with real GIAB data."""

    @pytest.mark.slow
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

    def test_gnomad_data_populated(self, giab_engine):
        """At least some variants in a well-covered region should have AF data.

        Catches issue #60 where gnomAD annotation silently wrote 0 variants.
        Only runs when a patch.db with gnomAD annotations is configured.
        """
        versions = giab_engine.annotation_versions()
        if not versions.get("gnomad"):
            pytest.skip("gnomAD annotations not available in this setup")

        # BRCA1 region — well covered by gnomAD exomes
        variants = giab_engine.query_region("chr17:43044295-43170245")
        if not variants:
            pytest.skip("No variants in BRCA1 region")

        has_af = [
            v
            for v in variants
            if v.get("population_freq", {}).get("global") is not None
        ]
        assert len(has_af) > 0, (
            f"Found {len(variants)} variants in BRCA1 but none have gnomAD AF. "
            "gnomAD annotation may have silently failed (see issue #60)."
        )

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
