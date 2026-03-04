"""Performance benchmarks for VCFEngine against GIAB NA12878."""

import time

import pytest


class TestPerformanceGIAB:
    @pytest.mark.slow
    def test_region_query_under_1s(self, giab_engine):
        """Indexed region query should complete in < 1 second."""
        start = time.perf_counter()
        variants = giab_engine.query_region("chr22:42126000-42130000")
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"Region query took {elapsed:.2f}s (expected < 1s)"
        assert isinstance(variants, list)

    @pytest.mark.slow
    def test_rsid_query_under_2min(self, giab_engine):
        """Full-scan rsID query should complete in < 2 minutes."""
        start = time.perf_counter()
        variants = giab_engine.query_rsid("rs3892097")
        elapsed = time.perf_counter() - start

        assert elapsed < 120.0, f"rsID query took {elapsed:.2f}s (expected < 120s)"
        assert isinstance(variants, list)

    @pytest.mark.slow
    def test_stats_under_5min(self, giab_engine):
        """Stats computation should complete in < 5 minutes."""
        start = time.perf_counter()
        stats = giab_engine.stats()
        elapsed = time.perf_counter() - start

        assert elapsed < 300.0, f"Stats took {elapsed:.2f}s (expected < 300s)"
        assert stats["Total variants"] > 3_000_000

    def test_multiple_region_queries(self, giab_engine):
        """Multiple region queries should complete quickly."""
        regions = [
            "chr1:11796000-11800000",
            "chr16:31096000-31100000",
            "chr22:42126000-42130000",
        ]
        start = time.perf_counter()
        for region in regions:
            giab_engine.query_region(region)
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0, f"3 region queries took {elapsed:.2f}s (expected < 3s)"
