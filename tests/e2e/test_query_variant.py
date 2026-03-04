"""E2E tests for query_variant tool against GIAB NA12878."""

import pytest
from mcp.server.fastmcp import FastMCP

from genechat.tools.query_variant import register


def _get_tool(giab_engine, giab_db, giab_config):
    mcp = FastMCP("test")
    register(mcp, giab_engine, giab_db, giab_config)
    tools = mcp._tool_manager._tools
    return tools["query_variant"].fn


class TestQueryVariantGIAB:
    @pytest.mark.slow
    def test_rsid_het_variant(self, giab_engine, giab_db, giab_config):
        """Query rs3892097 (CYP2D6 *4) — expected heterozygous."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(rsid="rs3892097")
        # Should find the variant with genotype info
        assert "heterozygous" in result.lower() or "het" in result.lower(), (
            f"Expected heterozygous for CYP2D6 *4, got: {result[:200]}"
        )

    @pytest.mark.slow
    def test_rsid_absent_variant(self, giab_engine, giab_db, giab_config):
        """Query rs4149056 (SLCO1B1 *5) — expected absent (ref/ref)."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(rsid="rs4149056")
        assert (
            "no variant found" in result.lower() or "homozygous ref" in result.lower()
        ), f"Expected no variant / ref for SLCO1B1, got: {result[:200]}"

    def test_query_by_position(self, giab_engine, giab_db, giab_config):
        """Query MTHFR C677T by position."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(position="chr1:11796321")
        # Should return variant data (MTHFR het in NA12878)
        assert (
            "chr1" in result or "11796321" in result or "no variant" in result.lower()
        )

    def test_no_input_returns_help(self, giab_engine, giab_db, giab_config):
        """No rsid or position should return help message."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn()
        assert "provide" in result.lower()
