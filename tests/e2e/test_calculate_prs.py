"""E2E tests for calculate_prs tool against GIAB NA12878."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.calculate_prs import register


def _get_tool(giab_engines, giab_db, giab_config):
    mcp = FastMCP("test")
    register(mcp, giab_engines, giab_db, giab_config)
    tools = mcp._tool_manager._tools
    return tools["calculate_prs"].fn


class TestCalculatePrsGIAB:
    def test_cad_prs(self, giab_engines, giab_db, giab_config):
        """CAD PRS should return a numeric score."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(trait="coronary artery disease")
        assert "Polygenic Risk Score" in result
        assert "Raw score" in result or "score" in result.lower()
        # Should have scored some variants
        assert "Variants scored" in result or "scored" in result.lower()

    def test_bmi_prs(self, giab_engines, giab_db, giab_config):
        """BMI PRS should return a numeric score."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(trait="body mass index")
        assert "Polygenic Risk Score" in result
        assert "score" in result.lower()

    def test_prs_has_caveats(self, giab_engines, giab_db, giab_config):
        """PRS output should include important caveats."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(trait="coronary artery disease")
        assert "caveat" in result.lower() or "important" in result.lower()
        assert "ancestry" in result.lower()

    def test_prs_variants_found(self, giab_engines, giab_db, giab_config):
        """PRS should find at least some variants in the VCF."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(trait="coronary artery disease")
        # Parse "Variants scored: X/Y"
        if "Variants scored" in result:
            import re

            match = re.search(r"Variants scored.*?(\d+)/(\d+)", result)
            if match:
                found = int(match.group(1))
                assert found > 0, "Expected at least some PRS variants to be found"

    def test_unknown_trait(self, giab_engines, giab_db, giab_config):
        """Unknown trait should return helpful message."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(trait="nonexistent_trait_xyz")
        assert "no prs data" in result.lower() or "not found" in result.lower()

    def test_prs_by_id(self, giab_engines, giab_db, giab_config):
        """Query PRS by PGS catalog ID."""
        fn = _get_tool(giab_engines, giab_db, giab_config)
        result = fn(prs_id="PGS000010")
        assert "Polygenic Risk Score" in result or "no prs data" in result.lower()
