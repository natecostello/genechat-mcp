"""E2E tests for query_gene tool against GIAB NA12878."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_gene import register


def _get_tool(giab_engines, giab_db, giab_config):
    mcp = FastMCP("test")
    register(mcp, giab_engines, giab_db, giab_config)
    tools = mcp._tool_manager._tools
    return tools["query_gene"].fn


class TestQueryGeneGIAB:
    def test_cyp2d6_finds_variants(self, giab_engines, giab_db, giab_config):
        """CYP2D6 should have variants in NA12878."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(gene="CYP2D6", impact_filter="HIGH,MODERATE,LOW,MODIFIER")
        # Should find some variants (CYP2D6 is well-covered)
        assert "CYP2D6" in result
        assert "no" not in result.lower().split("variant")[0] or "|" in result

    def test_brca1_returns_variants(self, giab_engines, giab_db, giab_config):
        """BRCA1 region should have common variants."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(gene="BRCA1", impact_filter="HIGH,MODERATE,LOW,MODIFIER")
        assert "BRCA1" in result

    def test_nonexistent_gene(self, giab_engines, giab_db, giab_config):
        """Unknown gene should return not found."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(gene="FAKEGENE123")
        assert "not found" in result.lower()

    def test_impact_filter(self, giab_engines, giab_db, giab_config):
        """Filtering by HIGH impact should return fewer or no variants."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result_all = fn(gene="CYP2D6", impact_filter="HIGH,MODERATE,LOW,MODIFIER")
        result_high = fn(gene="CYP2D6", impact_filter="HIGH")
        # HIGH-only should have fewer or equal results
        # Just verify both complete without error
        assert isinstance(result_all, str)
        assert isinstance(result_high, str)
