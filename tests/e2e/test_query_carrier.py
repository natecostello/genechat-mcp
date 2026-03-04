"""E2E tests for query_carrier tool against GIAB NA12878."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_carrier import register


def _get_tool(giab_engine, giab_db, giab_config):
    mcp = FastMCP("test")
    register(mcp, giab_engine, giab_db, giab_config)
    tools = mcp._tool_manager._tools
    return tools["query_carrier"].fn


class TestQueryCarrierGIAB:
    def test_acmg_panel_completes(self, giab_engine, giab_db, giab_config):
        """ACMG carrier panel should complete without error."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(acmg_only=True)
        assert isinstance(result, str)
        assert "Carrier Screening" in result

    def test_expanded_panel_completes(self, giab_engine, giab_db, giab_config):
        """Expanded carrier panel should complete without error."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(acmg_only=False)
        assert isinstance(result, str)
        assert "Carrier Screening" in result

    def test_output_structure(self, giab_engine, giab_db, giab_config):
        """Carrier output should have proper sections."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(acmg_only=True)
        # Should have gene count info
        assert "screened" in result.lower() or "genes" in result.lower()
        # Should have the important disclaimer
        assert "absence" in result.lower() or "important" in result.lower()

    def test_mostly_negative_for_healthy(self, giab_engine, giab_db, giab_config):
        """NA12878 is a healthy individual — most genes should be clear."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(acmg_only=True)
        # Should have "No Pathogenic Variants Found" section
        assert "no pathogenic" in result.lower() or "clear" in result.lower()

    def test_condition_filter(self, giab_engine, giab_db, giab_config):
        """Filter by specific condition."""
        fn = _get_tool(giab_engine, giab_db, giab_config)
        result = fn(condition="cystic fibrosis")
        assert isinstance(result, str)
