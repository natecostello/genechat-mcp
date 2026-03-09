"""E2E tests for genome_summary tool against GIAB NA12878."""

import pytest

from mcp.server.fastmcp import FastMCP

from genechat.tools.genome_summary import register


def _get_tool(giab_engines, giab_db, giab_config):
    mcp = FastMCP("test")
    register(mcp, giab_engines, giab_db, giab_config)
    tools = mcp._tool_manager._tools
    return tools["genome_summary"].fn


class TestGenomeSummaryGIAB:
    @pytest.mark.slow
    def test_summary_completes(self, giab_engines, giab_db, giab_config):
        """Genome summary should complete on full GIAB VCF."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn()
        assert "Genome Summary" in result

    @pytest.mark.slow
    def test_reports_millions_of_variants(self, giab_engines, giab_db, giab_config):
        """Summary should report millions of total variants."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn()
        # Should contain comma-formatted numbers in the millions
        assert "Total variants" in result or "variant" in result.lower()
        # Check for at least 7-digit numbers (3,000,000+)
        import re

        numbers = re.findall(r"[\d,]+", result)
        large_numbers = [
            int(n.replace(",", "")) for n in numbers if len(n.replace(",", "")) >= 7
        ]
        assert len(large_numbers) > 0, (
            "Expected at least one number >= 1,000,000 in summary"
        )

    @pytest.mark.slow
    def test_has_pgx_section(self, giab_engines, giab_db, giab_config):
        """Summary should include PGx quick check."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn()
        assert "pharmacogenomics" in result.lower() or "pgx" in result.lower()

    @pytest.mark.slow
    def test_has_clinvar_section(self, giab_engines, giab_db, giab_config):
        """Summary should include ClinVar section."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn()
        assert "clinvar" in result.lower() or "pathogenic" in result.lower()
